"""
coverage.py — pre-registered coverage test for changelog C-011
(uncertainty ranges). Written and committed before its first run.

Question: when the model says "90% range", does the truth land inside
about 90% of the time?

Companies: 80 FRESH benchmark companies never used before: generator
variants 'orig' and 'hard', indices 40 to 59, both size bands. Each goes
through the same pipeline as the benchmark (30,000-order history →
validation gate → DuckDB estimates), the model builds 90% ranges with
model/uncertainty.py (600 draws), and the truth is the mean of 4 runs of
200,000 orders of the true operation.

Pass rules (all bands pooled; also reported per band):
  C1  Station waits with true wait ≥ 0.1 min: share of 90% ranges that
      contain the truth is between 82% and 97%.
  C2  Total time through the line: same, between 82% and 97%.
  C3  Near-capacity stations (true utilization ≥ 0.88, true wait
      ≥ 0.1 min): coverage ≥ 75%.
ROUND 2 (changelog C-012), pre-registered and committed before its first
run: identical rules, applied to 80 FRESH companies (indices 60 to 79),
with ranges that also include the formula's approximation error measured
only on development companies. Run:  python analysis/coverage.py 2

Why a band, not exactly 90%: the truth has its own small simulation
noise, and the ranges ignore the formula's approximation error by design
(C-011); 82% to 97% is wide enough for those and narrow enough to catch
ranges that are badly too narrow or uselessly wide.
"""

from __future__ import annotations

import json
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("model", "simulation", "schema", "pipeline", "analysis"):
    sys.path.insert(0, str(ROOT / sub))

import numpy as np  # noqa: E402

import opsmodel as M  # noqa: E402
import uncertainty as U  # noqa: E402
from benchmark import BANDS, N_HISTORY, N_TRUTH, TRUTH_RUNS, make_company  # noqa: E402
from estimate import estimate_stations  # noqa: E402
from eventlog import generate_orders, line_times  # noqa: E402
from guardrails import ModelError  # noqa: E402

# Round 1 (C-011, estimation error only): indices 40-59 -> results/coverage.json
# Round 2 (C-012, plus approximation error): FRESH indices 60-79 -> results/coverage2.json
ROUNDS = {"1": (range(40, 60), "coverage.json", False), "2": (range(60, 80), "coverage2.json", True)}
ROUND = sys.argv[1] if len(sys.argv) > 1 else "1"
IDX, OUTFILE, INCLUDE_APPROX = ROUNDS[ROUND]


def one(args):
    band, idx, variant = args
    co = make_company(band, idx, variant)
    orders = generate_orders(co.lam, list(co.stations), N_HISTORY, co.seed + 1)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "o.parquet"
        orders.to_parquet(p, index=False)
        est = {e.station: e for e in estimate_stations(str(p))}
    k = len(co.stations)
    op = M.Operation(
        stations=tuple(M.Station(s.name, est[s.name].service_rate, s.workers, est[s.name].service_cv)
                       for s in co.stations),
        external_arrivals=tuple(est[co.stations[0].name].arrival_rate if j == 0 else 0.0 for j in range(k)),
        routing=tuple(tuple(1.0 if q == j + 1 else 0.0 for q in range(k)) for j in range(k)))
    runs = [line_times(co.lam, list(co.stations), N_TRUTH, co.seed + 2 + 1000 * r) for r in range(TRUTH_RUNS)]
    tw = np.mean([w for w, _ in runs], axis=0)
    tt = float(np.mean([t for _, t in runs]))
    out = {"band": band, "idx": idx, "variant": variant, "stations": []}
    try:
        iv = U.intervals(op, [est[s.name].n_orders for s in co.stations],
                         est[co.stations[0].name].n_orders, seed=idx,
                         include_approx=INCLUDE_APPROX)
    except ModelError as e:
        out["refused"] = str(e)
        return out
    for j, s in enumerate(co.stations):
        w = iv.waits[j]
        out["stations"].append({"rho": co.lam / (s.workers * s.service_rate), "true": float(tw[j]),
                                "point": w.point, "lo": w.lo, "hi": w.hi,
                                "covered": bool(w.lo <= tw[j] <= w.hi)})
    out["total"] = {"true": tt, "point": iv.total.point, "lo": iv.total.lo, "hi": iv.total.hi,
                    "covered": bool(iv.total.lo <= tt <= iv.total.hi)}
    return out


def main() -> int:
    if (ROOT / "results" / OUTFILE).exists():
        print("Refusing: the coverage test has already been run once; its result stands.")
        return 2
    jobs = [(b, i, v) for v in ("orig", "hard") for b in BANDS for i in IDX]
    with Pool(2) as pool:
        rows = list(pool.imap_unordered(one, jobs))
    rows.sort(key=lambda r: (r["variant"], r["band"], r["idx"]))

    def rates(sel):
        st = [s for r in sel if "stations" in r for s in r["stations"] if s["true"] * 60 >= 0.1]
        nc = [s for s in st if s["rho"] >= 0.88]
        tot = [r["total"] for r in sel if "total" in r]
        return {"c1": float(np.mean([s["covered"] for s in st])), "c1_n": len(st),
                "c2": float(np.mean([t["covered"] for t in tot])), "c2_n": len(tot),
                "c3": float(np.mean([s["covered"] for s in nc])) if nc else float("nan"), "c3_n": len(nc)}

    pooled = rates(rows)
    by_band = {b: rates([r for r in rows if r["band"] == b]) for b in BANDS}
    verdict = {"C1": 0.82 <= pooled["c1"] <= 0.97, "C2": 0.82 <= pooled["c2"] <= 0.97,
               "C3": pooled["c3"] >= 0.75}
    res = {"pooled": pooled, "by_band": by_band, "verdict": verdict,
           "refused": sum("refused" in r for r in rows), "rows": rows}
    (ROOT / "results" / OUTFILE).write_text(json.dumps(res, indent=1, default=float))
    print(f"C1 station waits:      {pooled['c1']:.1%} of {pooled['c1_n']} ranges contain the truth "
          f"(need 82%-97%) {'PASS' if verdict['C1'] else 'FAIL'}")
    print(f"C2 total time:         {pooled['c2']:.1%} of {pooled['c2_n']} (need 82%-97%) "
          f"{'PASS' if verdict['C2'] else 'FAIL'}")
    print(f"C3 near-capacity:      {pooled['c3']:.1%} of {pooled['c3_n']} (need ≥ 75%) "
          f"{'PASS' if verdict['C3'] else 'FAIL'}")
    for b, r in by_band.items():
        print(f"  band {b}: waits {r['c1']:.1%} (n={r['c1_n']}), total {r['c2']:.1%} (n={r['c2_n']}), "
              f"near-capacity {r['c3']:.1%} (n={r['c3_n']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
