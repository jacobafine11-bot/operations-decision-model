"""
mock_company.py — "Harbor Supply Co.", a FICTIONAL 6-person janitorial-
supply distributor used to demonstrate the whole program end to end.

The point of a mock company is that we know the answer key: its true
arrival rate, work speeds, crew sizes, and variability are set here, then
hidden. The portal walks through exactly what a real engagement would do:

  1. Pull its order history          (simulation/eventlog.py plays the export)
  2. Run the validation gate         (schema.validate_orders)
  3. Estimate the inputs             (pipeline.estimate.estimate_stations)
  4. Predict with the model          (opsmodel.evaluate) and check against
                                     what the history shows
  5. Rank changes                    (opsmodel.best_plan)
  6. Check the decision delivered    (re-simulate with the change applied,
                                     several replications, compare realized
                                     savings with the model's promise)

Step 6 uses common random numbers: the "before" and "after" runs of each
replication share a seed, so the difference reflects the change, not luck.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

import core  # noqa: F401  (sets import paths)
import opsmodel as M
from estimate import estimate_stations
from eventlog import StationTruth, generate_orders, observed_station_times
from schema import validate_orders

# ---------------------------------------------------------------- answer key

TRUTH_LAMBDA = 22.0            # orders per hour
TRUTH = [
    StationTruth("Picking", service_rate=8.0, workers=3, cv=0.8),
    StationTruth("Packing", service_rate=13.0, workers=2, cv=0.6),
    StationTruth("Loading", service_rate=30.0, workers=1, cv=1.0),
]
COSTS = dict(margin=9.0, waiting_cost=4.0, hourly_overhead=140.0,
             hours_per_year=2500.0)


@dataclass(frozen=True)
class Candidate:
    name: str
    station: str
    kind: str          # "speed" (multiply service rate) or "workers" (add)
    amount: float
    install_cost: float
    annual_cost: float
    years: float


CANDIDATES = [
    Candidate("Re-slot fast movers near packing", "Picking", "speed", 1.25, 4_000, 0, 5),
    Candidate("Pick-to-light system", "Picking", "speed", 1.60, 65_000, 3_500, 5),
    Candidate("Hire a fourth picker", "Picking", "workers", 1, 0, 41_000, 1),
    Candidate("Hire a third packer", "Packing", "workers", 1, 0, 41_000, 1),
    Candidate("Faster tape and label station", "Packing", "speed", 1.20, 6_000, 500, 5),
]


def truth_after(cands: list[Candidate]) -> list[StationTruth]:
    out = list(TRUTH)
    for cd in cands:
        i = [s.name for s in out].index(cd.station)
        s = out[i]
        out[i] = (replace(s, service_rate=s.service_rate * cd.amount) if cd.kind == "speed"
                  else replace(s, workers=s.workers + int(cd.amount)))
    return out


# ---------------------------------------------------------------- steps 1-3

def history(n_orders: int, seed: int) -> pd.DataFrame:
    return generate_orders(TRUTH_LAMBDA, TRUTH, n_orders, seed)


def gate(orders: pd.DataFrame):
    return validate_orders(orders)


def estimates(orders: pd.DataFrame) -> pd.DataFrame:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "orders.parquet"
        orders.to_parquet(p, index=False)
        est = estimate_stations(str(p))
    df = pd.DataFrame([e.__dict__ for e in est]).set_index("station")
    key = {s.name: s for s in TRUTH}
    rows = []
    for name in [s.name for s in TRUTH]:
        e, t = df.loc[name], key[name]
        rows.append({
            "Station": name,
            "Arrivals/hr (estimated)": e["arrival_rate"], "Arrivals/hr (true)": TRUTH_LAMBDA,
            "Speed/hr per worker (estimated)": e["service_rate"],
            "Speed/hr per worker (true)": t.service_rate,
            "Variability cv (estimated)": e["service_cv"], "Variability cv (true)": t.cv,
            "Orders seen": int(e["n_orders"]),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- steps 4-5

def operation_from(est: pd.DataFrame, workers: dict[str, int]) -> M.Operation:
    names = list(est["Station"])
    n = len(names)
    stations = tuple(M.Station(r["Station"], float(r["Speed/hr per worker (estimated)"]),
                               int(workers[r["Station"]]),
                               float(r["Variability cv (estimated)"]))
                     for _, r in est.iterrows())
    lam = float(est["Arrivals/hr (estimated)"].iloc[0])
    return M.Operation(
        stations=stations,
        external_arrivals=tuple(lam if j == 0 else 0.0 for j in range(n)),
        routing=tuple(tuple(1.0 if k == j + 1 else 0.0 for k in range(n)) for j in range(n)),
        **COSTS)


def model_vs_history(op: M.Operation, orders: pd.DataFrame) -> pd.DataFrame:
    b = M.evaluate(op)
    obs = observed_station_times(orders).set_index("station")
    rows = []
    for st, r in zip(op.stations, b.station_results):
        o = obs.loc[st.name]
        rows.append({
            "Station": st.name,
            "Utilization (model)": r.rho,
            "Wait, model (min)": r.Wq * 60, "Wait, history (min)": o["obs_wait_h"] * 60,
            "Time at station, model (min)": r.W * 60,
            "Time at station, history (min)": o["obs_time_h"] * 60,
        })
    df = pd.DataFrame(rows)
    df["Wait error"] = df["Wait, model (min)"] / df["Wait, history (min)"] - 1
    return df


def to_change(cd: Candidate) -> M.Change:
    def apply(op: M.Operation) -> M.Operation:
        sts = list(op.stations)
        i = [s.name for s in sts].index(cd.station)
        s = sts[i]
        sts[i] = (replace(s, service_rate=s.service_rate * cd.amount) if cd.kind == "speed"
                  else replace(s, servers=s.servers + int(cd.amount)))
        return op.with_changes(stations=tuple(sts))
    return M.Change(cd.name, apply, cd.install_cost, cd.annual_cost, cd.years)


def rank(op: M.Operation, chosen: list[Candidate], budget: float):
    return M.best_plan(op, [to_change(c) for c in chosen], budget=budget)


# ---------------------------------------------------------------- step 6

def mean_time_in_system(stations: list[StationTruth], n: int, seed: int) -> float:
    o = generate_orders(TRUTH_LAMBDA, stations, n, seed)
    first = o[o["station"] == stations[0].name].set_index("order_id")["arrived_at"]
    last = o[o["station"] == stations[-1].name].set_index("order_id")["finished_at"]
    t = (last - first).dt.total_seconds() / 3600
    return float(t.iloc[int(len(t) * 0.1):].mean())


def verify_plan(cands: list[Candidate], reps: int, n: int, seed0: int = 500) -> dict:
    """Realized yearly waiting-cost savings of a plan, measured by
    re-simulating the TRUE operation before and after, with common random
    numbers, over `reps` replications. Returns mean and 95% CI."""
    from scipy import stats as sp
    after = truth_after(cands)
    diffs = []
    for r in range(reps):
        w0 = mean_time_in_system(TRUTH, n, seed0 + r)
        w1 = mean_time_in_system(after, n, seed0 + r)
        # L = lam W (Little); yearly cost = c_w * L * hours/year
        diffs.append(COSTS["waiting_cost"] * TRUTH_LAMBDA * (w0 - w1) * COSTS["hours_per_year"])
    d = np.array(diffs)
    se = d.std(ddof=1) / np.sqrt(len(d))
    t = float(sp.t.ppf(0.975, len(d) - 1))
    return {"mean": float(d.mean()), "lo": float(d.mean() - t * se),
            "hi": float(d.mean() + t * se), "reps": reps, "values": d}
