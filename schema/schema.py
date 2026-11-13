"""
schema.py — the standard data format every dataset is converted into,
plus the validation gate that nothing passes without clearing.

Four tables. Every adapter's only job is to produce these; the model and
the estimation step read nothing else. Column names and units are law.

  orders      one row per order event at a station
              order_id (str), station (str), arrived_at (timestamp),
              started_at (timestamp), finished_at (timestamp)
  demand      one row per product per day
              product_id (str), date (date), units (float >= 0)
  inventory   one row per product per count date
              product_id (str), date (date), on_hand (float >= 0)
  costs       one row per named cost input, with provenance
              name (str), value (float), unit (str),
              source (str: measured | interview | assumed | public)

The validation gate (validate_orders / validate_demand) never silently
fixes anything: it writes a findings report and either passes the data
through or rejects it. Silent repair is how wrong numbers get into papers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

ORDERS_COLUMNS = ["order_id", "station", "arrived_at", "started_at", "finished_at"]
DEMAND_COLUMNS = ["product_id", "date", "units"]
INVENTORY_COLUMNS = ["product_id", "date", "on_hand"]
COSTS_COLUMNS = ["name", "value", "unit", "source"]
COST_SOURCES = {"measured", "interview", "assumed", "public"}


@dataclass
class ValidationReport:
    table: str
    n_rows: int
    findings: list[str] = field(default_factory=list)
    fatal: bool = False

    def add(self, msg: str, fatal: bool = False) -> None:
        self.findings.append(("FATAL: " if fatal else "") + msg)
        self.fatal = self.fatal or fatal

    def summary(self) -> str:
        status = "REJECTED" if self.fatal else ("PASSED with findings" if self.findings else "PASSED clean")
        lines = [f"[{self.table}] {self.n_rows:,} rows — {status}"]
        lines += [f"  - {f}" for f in self.findings]
        return "\n".join(lines)


def validate_orders(df: pd.DataFrame) -> ValidationReport:
    rep = ValidationReport("orders", len(df))
    missing = [c for c in ORDERS_COLUMNS if c not in df.columns]
    if missing:
        rep.add(f"missing columns {missing}", fatal=True)
        return rep

    for col in ("arrived_at", "started_at", "finished_at"):
        if not pd.api.types.is_datetime64_any_dtype(df[col]):
            rep.add(f"{col} is not a timestamp dtype", fatal=True)
    if rep.fatal:
        return rep

    n_null = int(df[ORDERS_COLUMNS].isna().any(axis=1).sum())
    if n_null:
        rep.add(f"{n_null:,} rows with missing values ({n_null/len(df):.2%})",
                fatal=n_null / len(df) > 0.05)

    dup = int(df.duplicated(subset=["order_id", "station"]).sum())
    if dup:
        rep.add(f"{dup:,} duplicate (order_id, station) rows", fatal=dup / len(df) > 0.01)

    ok = df.dropna(subset=["arrived_at", "started_at", "finished_at"])
    bad_order = int(((ok["started_at"] < ok["arrived_at"]) |
                     (ok["finished_at"] < ok["started_at"])).sum())
    if bad_order:
        rep.add(f"{bad_order:,} rows with impossible timestamp order "
                f"(start before arrival, or finish before start)",
                fatal=bad_order / len(df) > 0.01)

    svc_hours = (ok["finished_at"] - ok["started_at"]).dt.total_seconds() / 3600
    n_extreme = int((svc_hours > 24).sum())
    if n_extreme:
        rep.add(f"{n_extreme:,} service times over 24h — check units/time zones")

    span = (df["arrived_at"].max() - df["arrived_at"].min())
    rep.add(f"coverage: {df['arrived_at'].min()} to {df['arrived_at'].max()} "
            f"({span.days} days), stations: {sorted(df['station'].dropna().unique().tolist())}")
    return rep


def validate_demand(df: pd.DataFrame) -> ValidationReport:
    rep = ValidationReport("demand", len(df))
    missing = [c for c in DEMAND_COLUMNS if c not in df.columns]
    if missing:
        rep.add(f"missing columns {missing}", fatal=True)
        return rep
    neg = int((df["units"] < 0).sum())
    if neg:
        rep.add(f"{neg:,} negative demand rows (returns? decide a policy)", fatal=True)
    dup = int(df.duplicated(subset=["product_id", "date"]).sum())
    if dup:
        rep.add(f"{dup:,} duplicate (product, date) rows", fatal=dup / len(df) > 0.01)
    # Gap detection: products with missing dates understate demand sd.
    per = df.groupby("product_id")["date"].agg(["min", "max", "count"])
    expected = (pd.to_datetime(per["max"]) - pd.to_datetime(per["min"])).dt.days + 1
    gappy = int((per["count"] < 0.9 * expected).sum())
    if gappy:
        rep.add(f"{gappy} products with >10% of days missing — zero-fill or "
                f"treat as intermittent (D6) before estimating sd")
    return rep


def validate_costs(df: pd.DataFrame) -> ValidationReport:
    rep = ValidationReport("costs", len(df))
    missing = [c for c in COSTS_COLUMNS if c not in df.columns]
    if missing:
        rep.add(f"missing columns {missing}", fatal=True)
        return rep
    bad_src = df.loc[~df["source"].isin(COST_SOURCES), "name"].tolist()
    if bad_src:
        rep.add(f"cost inputs with unknown provenance {bad_src} — every cost "
                f"must be tagged measured/interview/assumed/public", fatal=True)
    assumed = df.loc[df["source"] == "assumed", "name"].tolist()
    if assumed:
        rep.add(f"assumed (weakest) inputs: {assumed} — these get sensitivity sweeps")
    return rep
