"""
approx_error.py — measure the formula's own approximation error, on
DEVELOPMENT companies only (benchmark 'orig' 0-19 and 'hard' 0-9, both
bands), for changelog C-012.

With the TRUE inputs (so estimation error is excluded), compare predicted
station waits with a precise simulated truth (4 x 200,000 orders) and
record the spread of log(predicted / true), separately for:
  first      the first station (outside orders arrive at random; only the
             work-time variability approximation is involved)
  downstream later stations (the line-variability approximation, C-009,
             is involved as well)
Stations with true wait under 0.1 minute are excluded (ratios unstable).
The two spreads become fixed constants in model/uncertainty.py.
"""

from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("model", "simulation", "schema", "pipeline", "analysis"):
    sys.path.insert(0, str(ROOT / sub))

import numpy as np  # noqa: E402

import opsmodel as M  # noqa: E402
from benchmark import BANDS, N_TRUTH, TRUTH_RUNS, make_company  # noqa: E402
from eventlog import line_times  # noqa: E402


def one(args):
    band, idx, variant = args
    co = make_company(band, idx, variant)
    k = len(co.stations)
    op = M.Operation(stations=tuple(M.Station(s.name, s.service_rate, s.workers, s.cv) for s in co.stations),
                     external_arrivals=tuple(co.lam if j == 0 else 0.0 for j in range(k)),
                     routing=tuple(tuple(1.0 if q == j + 1 else 0.0 for q in range(k)) for j in range(k)))
    pred = [r.Wq for r in M.evaluate(op).station_results]
    tw = np.mean([line_times(co.lam, list(co.stations), N_TRUTH, co.seed + 2 + 1000 * r)[0]
                  for r in range(TRUTH_RUNS)], axis=0)
    return [{"pos": j, "rho": co.lam / (s.workers * s.service_rate), "cv": s.cv,
             "lr": float(np.log(pred[j] / tw[j]))}
            for j, s in enumerate(co.stations) if tw[j] * 60 >= 0.1]


def main() -> int:
    jobs = [(b, i, "orig") for b in BANDS for i in range(0, 20)] + \
           [(b, i, "hard") for b in BANDS for i in range(0, 10)]
    with Pool(2) as pool:
        st = [s for rows in pool.map(one, jobs) for s in rows]
    first = np.array([s["lr"] for s in st if s["pos"] == 0])
    down = np.array([s["lr"] for s in st if s["pos"] > 0])
    res = {"companies": len(jobs),
           "first": {"n": len(first), "mean": float(first.mean()), "sd": float(first.std(ddof=1))},
           "downstream": {"n": len(down), "mean": float(down.mean()), "sd": float(down.std(ddof=1))},
           "stations": st}
    (ROOT / "results" / "approx_error.json").write_text(json.dumps(res, indent=1))
    for g in ("first", "downstream"):
        r = res[g]
        print(f"{g:<10} n={r['n']:3d}  mean log-ratio {r['mean']:+.3f}  sd {r['sd']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
