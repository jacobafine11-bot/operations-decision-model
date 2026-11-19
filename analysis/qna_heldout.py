"""
qna_heldout.py — pre-registered held-out check of changelog C-009
(arrival-variability propagation through serial lines, QNA linking
equation, Whitt 1983).

Development configuration (where the problem was found and the fix was
first checked): the mock distributor, Harbor Supply Co. Those numbers do
not count as evidence. The four configurations below were written down
and committed BEFORE this script was first run; none was looked at
beforehand.

Pre-registered pass rule, judged only on stations whose simulated mean
wait is at least 1 minute (smaller waits make relative error unstable):
  (a) Mean absolute relative error of predicted wait, over all
      downstream stations (position 2 or later), is smaller WITH the
      correction than WITHOUT it (arrival cv forced to 1).
  (b) Every such downstream station is within ±25% WITH the correction.
First stations receive outside orders at random, so the correction does
not change them; they are reported for completeness only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "model"), str(ROOT / "simulation")]

import numpy as np  # noqa: E402

import opsmodel as M  # noqa: E402
from eventlog import StationTruth, generate_orders, observed_station_times  # noqa: E402

HELDOUT = {
    "H1": (10.0, [StationTruth("A", 4.0, 3, 0.5), StationTruth("B", 12.0, 1, 0.7)]),
    "H2": (30.0, [StationTruth("A", 35.0, 1, 1.3), StationTruth("B", 9.0, 4, 0.9),
                  StationTruth("C", 40.0, 1, 0.6)]),
    "H3": (15.0, [StationTruth("A", 6.0, 3, 0.6), StationTruth("B", 6.0, 3, 0.6),
                  StationTruth("C", 20.0, 1, 1.0)]),
    "H4": (50.0, [StationTruth("A", 20.0, 3, 0.4), StationTruth("B", 60.0, 1, 1.0)]),
}
N_ORDERS, SEED = 200_000, 2026
MIN_WAIT_MIN, TOL = 1.0, 0.25


def predicted_waits(lam, sts, correct: bool) -> list[float]:
    n = len(sts)
    op = M.Operation(
        stations=tuple(M.Station(s.name, s.service_rate, s.workers, s.cv) for s in sts),
        external_arrivals=tuple(lam if j == 0 else 0.0 for j in range(n)),
        routing=tuple(tuple(1.0 if k == j + 1 else 0.0 for k in range(n)) for j in range(n)))
    loads = M.traffic(op.external_arrivals, op.routing)
    cas = M.arrival_variability(op, loads) if correct else [1.0] * n
    return [M.mmc(l, s.service_rate, s.workers, s.cv, ca).Wq * 60
            for l, s, ca in zip(loads, sts, cas)]


def main() -> int:
    rows = []
    for key, (lam, sts) in HELDOUT.items():
        obs = observed_station_times(generate_orders(lam, sts, N_ORDERS, SEED)).set_index("station")
        with_c = predicted_waits(lam, sts, True)
        without = predicted_waits(lam, sts, False)
        for k, s in enumerate(sts):
            o = float(obs.loc[s.name, "obs_wait_h"]) * 60
            rows.append({"config": key, "station": s.name, "position": k + 1,
                         "observed_wait_min": o, "pred_without_min": without[k],
                         "pred_with_min": with_c[k],
                         "err_without": without[k] / o - 1, "err_with": with_c[k] / o - 1})
    judged = [r for r in rows if r["position"] >= 2 and r["observed_wait_min"] >= MIN_WAIT_MIN]
    mae_with = float(np.mean([abs(r["err_with"]) for r in judged]))
    mae_without = float(np.mean([abs(r["err_without"]) for r in judged]))
    a = mae_with < mae_without
    b = all(abs(r["err_with"]) <= TOL for r in judged)
    out = {"rows": rows, "judged_stations": len(judged), "mae_with": mae_with,
           "mae_without": mae_without, "rule_a": a, "rule_b": b, "passed": a and b}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "qna_heldout.json").write_text(json.dumps(out, indent=2))
    for r in rows:
        print(f"{r['config']} {r['station']} pos{r['position']}: obs {r['observed_wait_min']:.2f} min | "
              f"without {r['pred_without_min']:.2f} ({r['err_without']:+.1%}) | "
              f"with {r['pred_with_min']:.2f} ({r['err_with']:+.1%})")
    print(f"judged {len(judged)} downstream stations: MAE without {mae_without:.1%}, with {mae_with:.1%}")
    print(f"rule (a) {'PASS' if a else 'FAIL'}; rule (b) {'PASS' if b else 'FAIL'}; "
          f"overall {'PASS' if a and b else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
