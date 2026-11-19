"""
logic.py — everything the portal computes, with no UI in it.

The Streamlit app (app.py) is a thin display layer over these
functions, which keeps the portal testable (tests/test_portal_logic.py)
and keeps every number on screen traceable to the verified model.
"""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "model"))

import opsmodel as M  # noqa: E402
from guardrails import ModelError  # noqa: E402

__all__ = ["ModelError", "build_operation", "station_table", "profit_table",
           "build_changes", "plan_table", "waiting_cost_flip", "DEFAULTS"]

DEFAULTS = {
    "stations": pd.DataFrame({
        "Station": ["Receiving", "Picking", "Packing", "Loading"],
        "Workers": [1, 3, 2, 1],
        "Orders per hour per worker": [30.0, 8.0, 13.0, 25.0],
        "Service variability (cv)": [1.0, 0.8, 0.6, 1.0],
    }),
    "arrival_rate": 20.0,
    "margin": 9.0,
    "waiting_cost": 4.0,
    "overhead": 120.0,
    "hours_per_year": 2000.0,
}


def build_operation(stations_df: pd.DataFrame, arrival_rate: float,
                    margin: float, waiting_cost: float, overhead: float,
                    hours_per_year: float) -> M.Operation:
    """Stations in series (row order = flow order), external arrivals
    into the first station."""
    df = stations_df.dropna()
    n = len(df)
    if n == 0:
        raise ModelError("add at least one station")
    stations = tuple(
        M.Station(str(r["Station"]),
                  float(r["Orders per hour per worker"]),
                  int(r["Workers"]),
                  float(r["Service variability (cv)"]))
        for _, r in df.iterrows())
    routing = tuple(
        tuple(1.0 if k == j + 1 else 0.0 for k in range(n)) for j in range(n))
    external = tuple(arrival_rate if j == 0 else 0.0 for j in range(n))
    return M.Operation(stations=stations, external_arrivals=external,
                       routing=routing, margin=margin,
                       waiting_cost=waiting_cost, hourly_overhead=overhead,
                       hours_per_year=hours_per_year)


def station_table(op: M.Operation) -> tuple[pd.DataFrame, str]:
    b = M.evaluate(op)
    cas = M.arrival_variability(op, b.loads)
    rows = []
    for st, load, r, ca in zip(op.stations, b.loads, b.station_results, cas):
        rows.append({
            "Station": st.name,
            "Workers": st.servers,
            "Load (orders/hr)": round(load, 2),
            "Arrival variability (cv)": round(ca, 2),
            "Utilization": f"{r.rho:.0%}",
            "Chance an order waits": f"{r.p_wait:.0%}",
            "Avg orders waiting": round(r.Lq, 2),
            "Avg minutes in station": round(r.W * 60, 1),
            "Bottleneck": "◀ bottleneck" if st.name == b.bottleneck else "",
        })
    return pd.DataFrame(rows), b.bottleneck


def profit_table(op: M.Operation) -> pd.DataFrame:
    b = M.evaluate(op)
    T = op.hours_per_year
    rows = [
        ("Revenue (margin x shipped orders)", b.revenue_per_hour),
        ("Cost of orders waiting", -b.waiting_cost_per_hour),
        ("Inventory cost", -b.inventory_cost_per_hour),
        ("Staff and equipment overhead", -b.overhead_per_hour),
        ("Operating profit", b.profit_per_hour),
    ]
    return pd.DataFrame({
        "Line": [r[0] for r in rows],
        "$/hour": [f"{r[1]:,.2f}" for r in rows],
        "$/year": [f"{r[1] * T:,.0f}" for r in rows],
    })


def _speed_change(idx: int, pct: float):
    def apply(op: M.Operation) -> M.Operation:
        sts = list(op.stations)
        sts[idx] = replace(sts[idx],
                           service_rate=sts[idx].service_rate * (1 + pct / 100))
        return op.with_changes(stations=tuple(sts))
    return apply


def _worker_change(idx: int, delta: int):
    def apply(op: M.Operation) -> M.Operation:
        sts = list(op.stations)
        new_c = sts[idx].servers + delta
        if new_c < 1:
            raise ModelError(f"{sts[idx].name}: crew cannot drop below 1")
        sts[idx] = replace(sts[idx], servers=new_c)
        return op.with_changes(stations=tuple(sts))
    return apply


def build_changes(changes_df: pd.DataFrame, station_names: list[str]) -> list[M.Change]:
    out = []
    for _, r in changes_df.dropna(subset=["Name"]).iterrows():
        idx = station_names.index(str(r["Station"]))
        kind = str(r["Type"])
        amount = float(r["Amount"])
        fn = (_speed_change(idx, amount) if kind == "Speed up station by %"
              else _worker_change(idx, int(amount)))
        out.append(M.Change(
            name=str(r["Name"]), apply=fn,
            install_cost=float(r["One-time cost $"]),
            annual_cost=float(r["Yearly upkeep $"]),
            amortize_years=float(r["Spread cost over (years)"]),
        ))
    return out


def plan_table(op: M.Operation, changes: list[M.Change],
               budget: float) -> pd.DataFrame:
    best, ranked = M.best_plan(op, changes, budget=budget)
    rows = []
    for cv in ranked[:12]:
        rows.append({
            "Plan": " + ".join(cv.names) if cv.names else "Do nothing",
            "Value $/year": round(cv.value_per_year),
            "Gross savings $/year": round(cv.gross_savings_per_year),
            "Annualized cost $/year": round(cv.annualized_cost),
            "Payback (years)": ("n/a" if math.isinf(cv.payback_years)
                                else f"{cv.payback_years:.1f}"),
            "Best": "◀ recommended" if cv.names == best.names else "",
        })
    return pd.DataFrame(rows)


def waiting_cost_flip(op: M.Operation, a: list[M.Change],
                      b: list[M.Change]) -> float | None:
    lo = max(op.waiting_cost / 8, 0.05)
    hi = op.waiting_cost * 8
    return M.sensitivity(op, a, b, "waiting_cost", lo, hi)
