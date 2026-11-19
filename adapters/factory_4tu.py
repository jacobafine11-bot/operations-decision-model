"""
factory_4tu.py — adapter: job-shop production event log → one row per
operation.

Source: Levy, D. (2014). Production Analysis with Process Mining
Technology [Data set]. 4TU.ResearchData.
https://data.4tu.nl/datasets/12697997 (attribution given here and in
data/public/README.md).

Run:  python adapters/factory_4tu.py <folder containing Production_Data.csv>
Writes data/public/factory_operations.csv with columns
work_order, seq, activity, resource, start, end.

An operation = consecutive rows with the same work order and activity
(the log splits one operation into setup / production / break reports).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "public"


def convert(folder: str) -> dict:
    d = pd.read_csv(Path(folder) / "Production_Data.csv")
    d["start"] = pd.to_datetime(d["Start Timestamp"], errors="coerce")
    d["end"] = pd.to_datetime(d["Complete Timestamp"], errors="coerce")
    bad = int(d[["start", "end"]].isna().any(axis=1).sum())
    d = d.dropna(subset=["start", "end"]).sort_values(["Case ID", "start", "end"], kind="stable")
    new_op = (d["Case ID"] != d["Case ID"].shift()) | (d["Activity"] != d["Activity"].shift())
    d["op"] = new_op.cumsum()
    ops = d.groupby("op").agg(work_order=("Case ID", "first"), activity=("Activity", "first"),
                              resource=("Resource", "first"), start=("start", "min"),
                              end=("end", "max")).reset_index(drop=True)
    ops = ops.sort_values(["work_order", "start"], kind="stable")
    ops["seq"] = ops.groupby("work_order").cumcount() + 1
    ops = ops[["work_order", "seq", "activity", "resource", "start", "end"]]
    OUT.mkdir(parents=True, exist_ok=True)
    ops.to_csv(OUT / "factory_operations.csv", index=False)
    return {"events": len(d), "bad_rows": bad, "operations": len(ops),
            "work_orders": ops["work_order"].nunique(), "resources": ops["resource"].nunique()}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    print(convert(sys.argv[1]))
