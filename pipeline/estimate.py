"""
estimate.py — the estimation step: standard-format rows -> model inputs.

The equations never see raw rows. This module computes, with uncertainty:

  * arrival rate per station (orders/hr), from arrival timestamps
  * service rate per station (orders/hr per worker), from start->finish
  * service-time coefficient of variation cv (decides whether the
    Kingman variability correction is needed; see CHANGELOG C-001)
  * demand mean and sd per product per cycle

All heavy lifting runs in DuckDB over Parquet so the same code handles
a 500-row stopwatch sample from a warehouse visit and a 5M-row export.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class StationEstimate:
    station: str
    arrival_rate: float      # orders/hr
    service_rate: float      # orders/hr per worker
    service_cv: float        # sd/mean of service time
    n_orders: int


@dataclass(frozen=True)
class DemandEstimate:
    product_id: str
    mean_per_day: float
    sd_per_day: float
    n_days: int


def estimate_stations(orders_parquet: str) -> list[StationEstimate]:
    """One SQL pass per metric over the Parquet file; nothing loads fully
    into Python memory. Arrival rate = n / observed span; service rate =
    1 / mean service time; cv = sd(service)/mean(service)."""
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT
            station,
            COUNT(*)                                                    AS n,
            COUNT(*) / NULLIF(
                EXTRACT(EPOCH FROM (MAX(arrived_at) - MIN(arrived_at))) / 3600.0,
                0)                                                      AS arrival_rate,
            1.0 / NULLIF(AVG(
                EXTRACT(EPOCH FROM (finished_at - started_at)) / 3600.0), 0)
                                                                        AS service_rate,
            STDDEV_SAMP(EXTRACT(EPOCH FROM (finished_at - started_at)))
              / NULLIF(AVG(EXTRACT(EPOCH FROM (finished_at - started_at))), 0)
                                                                        AS service_cv
        FROM read_parquet('{orders_parquet}')
        WHERE arrived_at IS NOT NULL AND started_at IS NOT NULL
          AND finished_at IS NOT NULL
          AND started_at >= arrived_at AND finished_at >= started_at
        GROUP BY station
        ORDER BY station
    """).fetchall()
    con.close()
    return [StationEstimate(st, float(ar), float(sr), float(cv), int(n))
            for st, n, ar, sr, cv in rows]


def estimate_demand(demand_parquet: str) -> list[DemandEstimate]:
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT product_id,
               AVG(units)         AS mean_units,
               STDDEV_SAMP(units) AS sd_units,
               COUNT(*)           AS n_days
        FROM read_parquet('{demand_parquet}')
        GROUP BY product_id
        ORDER BY product_id
    """).fetchall()
    con.close()
    return [DemandEstimate(p, float(m), float(s or 0.0), int(n))
            for p, m, s, n in rows]
