"""
anonymous_bank.py — adapter: Anonymous Bank call center (1999) -> queue_events.

Source: Technion SEE Center, "Anonymous Bank" database (Mandelbaum et al.).
  Download: https://see-center.iem.technion.ac.il/databases/AnonymousBank/Data/AnonymousBank.rar
  Docs:     https://see-center.iem.technion.ac.il/databases/AnonymousBank/Data/AnonymousBank.pdf
  The data is free to use with acknowledgment; the raw files are NOT
  redistributed in this repository. Extract the 12 monthly .txt files and
  run:  python adapters/anonymous_bank.py <folder-with-txt-files>

Mapping to the standard queue_events table (schema/schema.py):
  arrived_at     vru_exit (the moment the caller asks for an agent)
  left_queue_at  q_exit if the caller queued, else arrived_at
  outcome        'served' (AGENT) or 'abandoned' (HANG after queueing)
  wait_s         q_time as recorded (0 for callers served immediately)
  started_at / finished_at / service_s / server   for served calls
Excluded, and counted in the validation report: PHANTOM records,
callers who hung up inside the voice menu (never sought an agent), and
malformed rows.
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "schema"))

from schema import validate_queue_events  # noqa: E402

OUT = ROOT / "data" / "clean" / "bank_queue_events.parquet"


def _ts(date: pd.Series, hms: pd.Series) -> pd.Series:
    return pd.to_datetime(date.dt.strftime("%Y-%m-%d") + " " + hms,
                          format="%Y-%m-%d %H:%M:%S", errors="coerce")


def convert(folder: str) -> tuple[pd.DataFrame, dict]:
    files = sorted(glob.glob(str(Path(folder) / "*1999.txt")))
    if len(files) != 12:
        raise SystemExit(f"expected 12 monthly files, found {len(files)} in {folder}")
    raw = pd.concat([pd.read_csv(f, sep="\t", dtype=str) for f in files],
                    ignore_index=True)
    raw.columns = [c.strip() for c in raw.columns]
    raw = raw.apply(lambda s: s.str.strip())
    counts = {"raw_records": len(raw)}

    raw["date"] = pd.to_datetime(raw["date"], format="%y%m%d", errors="coerce")
    for c in ("q_time", "ser_time"):
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    bad = raw["date"].isna() | ~raw["outcome"].isin(["AGENT", "HANG", "PHANTOM"])
    counts["malformed_rows"] = int(bad.sum())
    raw = raw[~bad]
    counts["phantom"] = int((raw["outcome"] == "PHANTOM").sum())
    raw = raw[raw["outcome"] != "PHANTOM"]
    queued = raw["q_start"] != "0:00:00"
    vru_only = (raw["outcome"] == "HANG") & ~queued
    counts["hung_up_in_voice_menu"] = int(vru_only.sum())
    d = raw[~vru_only].copy()

    arrived = _ts(d["date"], d["vru_exit"])
    q_exit = _ts(d["date"], d["q_exit"])
    s_start = _ts(d["date"], d["ser_start"])
    s_end = _ts(d["date"], d["ser_exit"])
    # Calls crossing midnight: a later stamp earlier than arrival rolled over.
    one_day = pd.Timedelta(days=1)
    q_exit = q_exit.where(~(q_exit < arrived), q_exit + one_day)
    s_start = s_start.where(~(s_start < arrived), s_start + one_day)
    s_end = s_end.where(~(s_end < s_start), s_end + one_day)

    is_q = d["q_start"] != "0:00:00"
    served = d["outcome"] == "AGENT"
    out = pd.DataFrame({
        # call_id alone repeats across VRU lines (11,098 collisions, zero
        # identical rows): the unique key is line + call_id + date.
        "event_id": (d["vru+line"] + "-" + d["call_id"].astype(str) + "-"
                     + d["date"].dt.strftime("%y%m%d")),
        "station": "agents",
        "call_type": d["type"],
        "arrived_at": arrived,
        "left_queue_at": np.where(is_q, q_exit, arrived),
        "outcome": np.where(served, "served", "abandoned"),
        "wait_s": np.where(is_q, d["q_time"], 0.0).astype(float),
        "started_at": s_start.where(served),
        "finished_at": s_end.where(served),
        "service_s": d["ser_time"].where(served).astype(float),
        "server": d["server"].where(served),
    })
    out["left_queue_at"] = pd.to_datetime(out["left_queue_at"])
    # Recorded q_time vs. timestamp difference: a data-consistency metric.
    stamp_wait = (out["left_queue_at"] - out["arrived_at"]).dt.total_seconds()
    counts["wait_vs_timestamps_off_by_gt_2s"] = int(
        ((stamp_wait - out["wait_s"]).abs() > 2).sum())
    counts["agent_seeking_calls"] = len(out)
    return out.reset_index(drop=True), counts


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    df, counts = convert(sys.argv[1])
    rep = validate_queue_events(df)
    print(rep.summary())
    print("adapter counts:", counts)
    if rep.fatal:
        print("GATE REJECTED THE DATA; nothing written")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"wrote {len(df):,} rows to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
