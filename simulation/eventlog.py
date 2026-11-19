"""
eventlog.py — generate a realistic order-by-order history for a
multi-station operation, in the standard `orders` table format.

Used by the mock distributor in the portal: it plays the role of a real
company's system export. Like the rest of simulation/, it shares no code
with the model, so the model must recover the truth from timestamps alone.

Mechanics (exact for FIFO crews in series):
  * Orders arrive by a Poisson process at rate lam (orders/hour).
  * Station k has a crew of c_k workers; each order's work time at k is
    gamma-distributed with mean 1/mu_k and coefficient of variation cv_k.
  * Orders reach station k when they leave station k-1. Because crews
    can finish out of order, arrivals at k are re-sorted before the
    server-availability heap assigns them (first come, first served).
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StationTruth:
    name: str
    service_rate: float   # orders/hour per worker
    workers: int
    cv: float             # work-time coefficient of variation


def _work_times(rng, mu: float, cv: float, n: int) -> np.ndarray:
    if abs(cv - 1.0) < 1e-12:
        return rng.exponential(1.0 / mu, n)
    shape = 1.0 / cv ** 2
    return rng.gamma(shape, 1.0 / (mu * shape), n)


def generate_orders(lam: float, stations: list[StationTruth], n_orders: int,
                    seed: int = 1, start: str = "2026-09-01 06:00:00"
                    ) -> pd.DataFrame:
    """Return one row per (order, station) with arrived/started/finished
    timestamps, millisecond precision (see CHANGELOG C-002)."""
    rng = np.random.default_rng(seed)
    t_arr = np.cumsum(rng.exponential(1.0 / lam, n_orders))  # hours
    base = pd.Timestamp(start)
    frames = []
    arrive = t_arr.copy()
    for st in stations:
        order = np.argsort(arrive, kind="stable")
        work = _work_times(rng, st.service_rate, st.cv, n_orders)
        begin = np.empty(n_orders)
        finish = np.empty(n_orders)
        free = [0.0] * st.workers
        heapq.heapify(free)
        for i in order:
            t_free = heapq.heappop(free)
            s = arrive[i] if arrive[i] > t_free else t_free
            begin[i] = s
            finish[i] = s + work[i]
            heapq.heappush(free, finish[i])
        to_ts = lambda h: base + pd.to_timedelta(np.round(h * 3.6e6), unit="ms")  # noqa: E731
        frames.append(pd.DataFrame({
            "order_id": [f"SO-{i:06d}" for i in range(n_orders)],
            "station": st.name,
            "arrived_at": to_ts(arrive),
            "started_at": to_ts(begin),
            "finished_at": to_ts(finish),
        }))
        arrive = finish
    return pd.concat(frames, ignore_index=True)


def observed_station_times(orders: pd.DataFrame, warmup_frac: float = 0.1
                           ) -> pd.DataFrame:
    """What actually happened, per station: mean wait and mean time at the
    station (hours), after discarding the start-up period."""
    out = []
    for name, g in orders.groupby("station", sort=False):
        g = g.sort_values("arrived_at")
        g = g.iloc[int(len(g) * warmup_frac):]
        wait = (g["started_at"] - g["arrived_at"]).dt.total_seconds() / 3600
        time_in = (g["finished_at"] - g["arrived_at"]).dt.total_seconds() / 3600
        out.append({"station": name, "obs_wait_h": wait.mean(),
                    "obs_time_h": time_in.mean(), "orders": len(g)})
    return pd.DataFrame(out)
