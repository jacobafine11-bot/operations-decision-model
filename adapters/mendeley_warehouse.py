"""
mendeley_warehouse.py — adapter: footwear-manufacturer warehouse order data
→ weekly demand per product, and order arrival times.

Source: "Order Picking Dataset from a Warehouse of a Footwear Manufacturing
Company", Mendeley Data, https://data.mendeley.com/datasets/pf2w725pw3/1,
CC BY 4.0 (attribution required; given here and in data/public/README.md).

Run:  python adapters/mendeley_warehouse.py <folder containing Customer_Order.csv>
Writes data/public/warehouse_weekly_demand.csv (reference, week_start, units;
weeks with zero demand are omitted and treated as zero downstream) and
data/public/warehouse_orders.csv (order_number, created_at).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "public"


def convert(folder: str) -> dict:
    o = pd.read_csv(Path(folder) / "Customer_Order.csv", sep=";", encoding="utf-8-sig")
    o.columns = [c.strip() for c in o.columns]
    o["created_at"] = pd.to_datetime(o["creationDate"], format="%d/%m/%Y %H:%M", errors="coerce")
    bad = int(o["created_at"].isna().sum())
    o = o.dropna(subset=["created_at"])
    o["reference"] = o["Reference"].astype(str).str.strip()
    o["week_start"] = (o["created_at"].dt.normalize()
                       - pd.to_timedelta(o["created_at"].dt.dayofweek, unit="D"))
    weekly = (o.groupby(["reference", "week_start"])["quantity (units)"].sum()
              .rename("units").reset_index())
    orders = (o.groupby("orderNumber")["created_at"].min().rename("created_at")
              .reset_index().rename(columns={"orderNumber": "order_number"}))
    OUT.mkdir(parents=True, exist_ok=True)
    weekly.to_csv(OUT / "warehouse_weekly_demand.csv", index=False)
    orders.to_csv(OUT / "warehouse_orders.csv", index=False)
    return {"lines": len(o), "bad_dates": bad, "references": weekly["reference"].nunique(),
            "orders": len(orders)}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    print(convert(sys.argv[1]))
