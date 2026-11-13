"""
scale_test.py — prove the pipeline handles a large export BEFORE any
real export arrives.

Generates a synthetic year of warehouse history with KNOWN ground-truth
parameters (5M order-station events across pick/pack/load, 250 products
of daily demand), runs it through the full pipeline (Parquet -> validation
gate -> DuckDB estimation), times every stage, and then closes the loop:
the estimated rates must recover the ground truth they were generated
from. A pipeline that is fast but estimates the wrong rates has failed.

This is itself a verification layer: generation and estimation share no
arithmetic, so recovery of the ground truth checks both.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "schema"))
sys.path.insert(0, str(ROOT / "pipeline"))

from schema import validate_demand, validate_orders  # noqa: E402
from estimate import estimate_demand, estimate_stations  # noqa: E402

RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"

# Ground truth the estimates must recover.
TRUTH = {
    "pick": dict(arrival_rate=240.0, service_rate=300.0, cv=0.60),
    "pack": dict(arrival_rate=240.0, service_rate=360.0, cv=0.50),
    "load": dict(arrival_rate=240.0, service_rate=600.0, cv=0.80),
}
N_PRODUCTS = 250
DEMAND_MEAN_LO, DEMAND_MEAN_HI = 5.0, 400.0


def gamma_params(mean_hours: float, cv: float) -> tuple[float, float]:
    shape = 1.0 / cv ** 2
    return shape, mean_hours / shape


def generate(n_target: int = 5_000_000, seed: int = 2026) -> tuple[Path, Path, dict]:
    rng = np.random.default_rng(seed)
    per_station = n_target // len(TRUTH)
    t0 = time.time()
    frames = []
    base = np.datetime64("2025-11-01T06:00:00")
    # Millisecond precision on purpose: a first draft of this generator
    # truncated to whole seconds and biased every service-rate estimate
    # high by 4-9% (worst at the fastest station). Lesson recorded in
    # CHANGELOG C-002: a real export with second-granularity timestamps
    # will bias short service times the same way; estimate from a
    # stopwatch sample or correct for rounding when that happens.
    for station, p in TRUTH.items():
        inter = rng.exponential(1.0 / p["arrival_rate"], per_station)  # hours
        arrived = base + (np.cumsum(inter) * 3.6e6).astype("timedelta64[ms]")
        queue_delay = rng.exponential(0.02, per_station)               # hours, incidental
        shape, scale = gamma_params(1.0 / p["service_rate"], p["cv"])
        service = rng.gamma(shape, scale, per_station)                 # hours
        started = arrived + (queue_delay * 3.6e6).astype("timedelta64[ms]")
        finished = started + (service * 3.6e6).astype("timedelta64[ms]")
        frames.append(pd.DataFrame({
            "order_id": np.char.add(f"{station}-", np.arange(per_station).astype(str)),
            "station": station,
            "arrived_at": arrived,
            "started_at": started,
            "finished_at": finished,
        }))
    orders = pd.concat(frames, ignore_index=True)

    # Gamma demand, not clipped normal: nonnegative by construction, so
    # the generated moments ARE the ground-truth moments. (A clipped
    # normal's true mean and sd differ from its parameters, which made
    # the first draft of this test compare estimates to the wrong truth.)
    days = pd.date_range("2025-01-01", periods=365, freq="D")
    means = rng.uniform(DEMAND_MEAN_LO, DEMAND_MEAN_HI, N_PRODUCTS)
    cvs = rng.uniform(0.2, 0.9, N_PRODUCTS)
    shape_d = 1.0 / cvs ** 2
    scale_d = means / shape_d
    demand = pd.DataFrame({
        "product_id": np.repeat([f"SKU{i:04d}" for i in range(N_PRODUCTS)], len(days)),
        "date": np.tile(days, N_PRODUCTS),
        "units": rng.gamma(np.repeat(shape_d, len(days)),
                           np.repeat(scale_d, len(days))),
    })
    gen_s = time.time() - t0

    t0 = time.time()
    RAW.mkdir(parents=True, exist_ok=True)
    op, dp = RAW / "orders_scale_test.parquet", RAW / "demand_scale_test.parquet"
    con = duckdb.connect()
    con.register("orders_df", orders)
    con.register("demand_df", demand)
    con.execute(f"COPY orders_df TO '{op}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.execute(f"COPY demand_df TO '{dp}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
    write_s = time.time() - t0
    truth_demand = dict(zip([f"SKU{i:04d}" for i in range(N_PRODUCTS)],
                            zip(means, means * cvs)))
    return op, dp, dict(rows=len(orders), demand_rows=len(demand),
                        gen_s=gen_s, write_s=write_s,
                        orders_mb=op.stat().st_size / 1e6,
                        demand_mb=dp.stat().st_size / 1e6,
                        truth_demand=truth_demand)


def main() -> int:
    print("Generating synthetic year (5M order events, 250 SKUs x 365 days)...")
    op, dp, info = generate()
    print(f"  generated {info['rows']:,} order rows in {info['gen_s']:.1f}s; "
          f"wrote Parquet ({info['orders_mb']:.0f} MB + {info['demand_mb']:.1f} MB) "
          f"in {info['write_s']:.1f}s")

    # Validation gate on a representative sample (full-file checks are the
    # same SQL shapes; sampling keeps the gate itself fast at any size).
    t0 = time.time()
    con = duckdb.connect()
    sample = con.execute(
        f"SELECT * FROM read_parquet('{op}') USING SAMPLE 400000 ROWS").df()
    demand_df = con.execute(f"SELECT * FROM read_parquet('{dp}')").df()
    con.close()
    rep_o = validate_orders(sample)
    rep_d = validate_demand(demand_df)
    gate_s = time.time() - t0
    print(f"  validation gate: {gate_s:.1f}s")
    print("  " + rep_o.summary().replace("\n", "\n  "))
    print("  " + rep_d.summary().replace("\n", "\n  "))
    if rep_o.fatal or rep_d.fatal:
        print("GATE REJECTED THE DATA")
        return 1

    # Estimation over the FULL files.
    t0 = time.time()
    stations = estimate_stations(str(op))
    demand_est = estimate_demand(str(dp))
    est_s = time.time() - t0
    print(f"  estimation over full files: {est_s:.1f}s")

    # Close the loop: recover ground truth.
    ok = True
    print("\nGround-truth recovery (estimate vs. truth):")
    for s in stations:
        t = TRUTH[s.station]
        for label, est, truth in (("arrival/hr", s.arrival_rate, t["arrival_rate"]),
                                  ("service/hr", s.service_rate, t["service_rate"]),
                                  ("service cv", s.service_cv, t["cv"])):
            rel = abs(est - truth) / truth
            flag = "ok" if rel < 0.02 else "OFF"
            ok &= rel < 0.02
            print(f"  {s.station:<5} {label:<11} est {est:10.2f}  truth {truth:10.2f}  "
                  f"rel {rel:6.3%}  {flag}")
    # Two separate questions, tested separately:
    # (1) Is the SQL estimator CORRECT? Compare against the realized
    #     sample moments computed by an independent engine (pandas).
    #     These must agree to numerical precision: any gap is a bug.
    ref = demand_df.groupby("product_id")["units"].agg(["mean", "std"])
    worst_est = max(
        max(abs(e.mean_per_day - ref.loc[e.product_id, "mean"]) / ref.loc[e.product_id, "mean"],
            abs(e.sd_per_day - ref.loc[e.product_id, "std"]) / ref.loc[e.product_id, "std"])
        for e in demand_est)
    print(f"  demand estimator (DuckDB vs. pandas on same rows): "
          f"worst rel diff {worst_est:.2e} {'ok' if worst_est < 1e-9 else 'OFF'}")
    ok &= worst_est < 1e-9
    # (2) How far are 365-day estimates from the GENERATING parameters?
    #     That is sampling error, not estimator error. For high-cv gamma
    #     demand the sd of 365 draws has relative standard error ~7%, so
    #     the worst of 500 estimates near 15% is expected. Reported as
    #     information with a loose sanity bound; it quantifies how much
    #     demand uncertainty one year of data leaves you with.
    worst_truth = max(
        max(abs(e.mean_per_day - m) / m, abs(e.sd_per_day - sd) / sd)
        for e in demand_est
        for m, sd in [info["truth_demand"][e.product_id]]
    )
    print(f"  demand sampling error (365 days vs. generating params): "
          f"worst {worst_truth:.2%} across 500 estimates "
          f"{'ok' if worst_truth < 0.25 else 'OFF'} "
          f"(expected ~15% for the worst high-cv sd)")
    ok &= worst_truth < 0.25

    total = info["gen_s"] + info["write_s"] + gate_s + est_s
    print(f"\nTotal wall time: {total:.1f}s for {info['rows']:,} order rows "
          f"+ {info['demand_rows']:,} demand rows")
    print("SCALE TEST", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
