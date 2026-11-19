"""
real2.py — real-data round 2, exactly as pre-registered in
docs/PREREGISTRATION_REAL2.md. Runs once; refuses to overwrite a result.

  python analysis/real2.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "model")]

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import opsmodel as M  # noqa: E402
import stats as ST  # noqa: E402

PUB = ROOT / "data" / "public"
OUT = ROOT / "results" / "real2.json"
TARGETS = {"R-A2": 0.80, "R-A1": 0.90, "R-A3": 0.95}
BANDS = {"R-A2": (0.75, 0.85), "R-A1": (0.85, 0.95), "R-A3": (0.90, 0.99)}


# ---------------------------------------------------------------- R-A

def r_a() -> dict:
    w = pd.read_csv(PUB / "warehouse_weekly_demand.csv", parse_dates=["week_start"])
    weeks = pd.date_range("2023-01-09", "2023-10-09", freq="7D")
    cal_w = weeks[weeks <= pd.Timestamp("2023-05-29")]
    test_w = weeks[weeks >= pd.Timestamp("2023-06-05")]
    assert len(cal_w) == 21 and len(test_w) == 19, (len(cal_w), len(test_w))
    grid = (w.pivot_table(index="reference", columns="week_start", values="units", aggfunc="sum")
            .reindex(columns=weeks).fillna(0.0))
    cal, test = grid[cal_w], grid[test_w]
    eligible = cal.index[(cal > 0).sum(axis=1) >= 10]
    lumpy = [r for r in eligible if (cal.loc[r] == 0).mean() >= 0.30]

    def realized(refs, tau, method="model"):
        hits, n = 0, 0
        for r in refs:
            x = cal.loc[r].to_numpy()
            if method == "model":
                sd = max(float(x.std(ddof=1)), 1e-9)
                inv = M.newsvendor_normal(float(x.mean()), sd, underage_cost=tau, overage_cost=1 - tau)
                S = inv.S_star
            else:
                S = float(np.quantile(x, tau))
            y = test.loc[r].to_numpy()
            hits += int((y <= S + 1e-9).sum())
            n += len(y)
        return hits / n if n else float("nan"), n

    card, extra = [], {}
    for cid, tau in TARGETS.items():
        rate, n = realized(eligible, tau)
        lo, hi = BANDS[cid]
        card.append({"id": cid, "target": tau, "realized": rate, "pairs": n,
                     "band": [lo, hi], "pass": bool(lo <= rate <= hi)})
        extra[cid] = {"lumpy": realized(lumpy, tau)[0] if lumpy else None,
                      "regular": realized([r for r in eligible if r not in lumpy], tau)[0],
                      "empirical_quantile_baseline": realized(eligible, tau, "empirical")[0]}

    # Input check (reported, not gated): Poisson arrivals per 15-min block, weekdays 08-17, by month.
    o = pd.read_csv(PUB / "warehouse_orders.csv", parse_dates=["created_at"])
    o = o[(o["created_at"].dt.dayofweek < 5) & (o["created_at"].dt.hour >= 8) & (o["created_at"].dt.hour < 17)]
    o["block"] = o["created_at"].dt.floor("15min")
    arrivals = []
    for month, g in o.groupby(o["created_at"].dt.to_period("M")):
        days = g["created_at"].dt.normalize().unique()
        blocks = pd.DatetimeIndex([d + pd.Timedelta(hours=8) + pd.Timedelta(minutes=15 * i)
                                   for d in days for i in range(36)])
        counts = g.groupby("block").size().reindex(blocks, fill_value=0).to_numpy()
        try:
            c = ST.chi2_poisson(counts)
            arrivals.append({"month": str(month), "blocks": len(counts), "mean": float(counts.mean()),
                             "var_to_mean": float(counts.var(ddof=1) / counts.mean()),
                             "p": c.p_value})
        except ValueError:
            pass
    return {"products_scored": len(eligible), "lumpy_products": len(lumpy), "card": card,
            "extra": extra, "arrival_checks": arrivals}


# ---------------------------------------------------------------- R-C

def r_c() -> dict:
    ops = pd.read_csv(PUB / "factory_operations.csv", parse_dates=["start", "end"])
    first = ops.groupby("work_order")["start"].min()
    cal_wo = set(first[first < pd.Timestamp("2012-02-15")].index)
    cal = ops[ops["work_order"].isin(cal_wo)]
    test = ops[~ops["work_order"].isin(cal_wo)]
    res = sorted(cal["resource"].unique())
    ix = {r: i for i, r in enumerate(res)}
    n = len(res)
    trans = np.zeros((n, n))
    visits = np.zeros(n)
    entry = np.zeros(n)
    for _, g in cal.sort_values(["work_order", "seq"]).groupby("work_order"):
        seq = [ix[r] for r in g["resource"]]
        entry[seq[0]] += 1
        for a in seq:
            visits[a] += 1
        for a, b in zip(seq, seq[1:]):
            trans[a, b] += 1
    P = trans / visits[:, None]
    gamma = entry / entry.sum()
    v = M.traffic(gamma, P)              # visits per work order, E1
    n_test = test["work_order"].nunique()
    pred_ops = pd.Series(v * n_test, index=res)
    obs_ops = test.groupby("resource").size()
    dur_h = (cal.assign(h=(cal["end"] - cal["start"]).dt.total_seconds() / 3600)
             .groupby("resource")["h"].mean())
    pred_load = (pd.Series(v, index=res) * dur_h.reindex(res)).sort_values(ascending=False)
    obs_load = (test.assign(h=(test["end"] - test["start"]).dt.total_seconds() / 3600)
                .groupby("resource")["h"].sum().sort_values(ascending=False))
    scored = obs_ops[obs_ops >= 20].index
    rel = [(pred_ops.get(r, 0.0) / obs_ops[r] - 1) for r in scored]
    c1 = float(np.median(np.abs(rel)))
    top_pred = pred_load.index[0]
    c2 = top_pred in list(obs_load.index[:2])
    table = pd.DataFrame({"predicted_ops": pred_ops.reindex(scored), "observed_ops": obs_ops.reindex(scored)})
    table["error"] = table["predicted_ops"] / table["observed_ops"] - 1
    unseen = sorted(set(test["resource"]) - set(res))
    return {"calibration_work_orders": len(cal_wo), "test_work_orders": int(n_test),
            "resources_scored": len(scored), "unseen_resources_in_test": unseen,
            "card": [{"id": "R-C1", "value": c1, "pass": bool(c1 <= 0.20)},
                     {"id": "R-C2", "predicted_busiest": top_pred,
                      "observed_top2": list(obs_load.index[:2]), "pass": bool(c2)}],
            "table": table.reset_index().rename(columns={"index": "resource"}).to_dict("records"),
            "predicted_load_top5": pred_load.head(5).round(3).to_dict(),
            "observed_load_top5_hours": obs_load.head(5).round(1).to_dict()}


def main() -> int:
    if OUT.exists():
        print("Refusing: round 2 has already been run once; its result stands.")
        return 2
    out = {"R-A": r_a(), "R-C": r_c()}
    OUT.write_text(json.dumps(out, indent=1, default=str))
    a, c = out["R-A"], out["R-C"]
    print(f"R-A: {a['products_scored']} products scored ({a['lumpy_products']} lumpy)")
    for x in a["card"]:
        e = a["extra"][x["id"]]
        print(f"  {x['id']} {'PASS' if x['pass'] else 'FAIL'}  target {x['target']:.0%}: realized "
              f"{x['realized']:.1%} over {x['pairs']} product-weeks (need {x['band'][0]:.0%}-{x['band'][1]:.0%}); "
              f"regular {e['regular']:.1%}, lumpy {e['lumpy'] if e['lumpy'] is None else round(e['lumpy']*100,1)}%, "
              f"empirical-quantile baseline {e['empirical_quantile_baseline']:.1%}")
    for m in a["arrival_checks"]:
        print(f"  arrivals {m['month']}: mean {m['mean']:.2f}/15min, variance/mean {m['var_to_mean']:.2f}, p={m['p']:.3g}")
    print(f"R-C: {c['calibration_work_orders']} calibration / {c['test_work_orders']} test work orders; "
          f"{c['resources_scored']} resources scored; unseen in test: {c['unseen_resources_in_test']}")
    print(f"  R-C1 {'PASS' if c['card'][0]['pass'] else 'FAIL'}  median abs error of operations per resource: "
          f"{c['card'][0]['value']:.1%} (need ≤ 20%)")
    print(f"  R-C2 {'PASS' if c['card'][1]['pass'] else 'FAIL'}  predicted busiest {c['card'][1]['predicted_busiest']!r}; "
          f"observed top 2 {c['card'][1]['observed_top2']}")
    for r in c["table"]:
        print(f"    {r['resource']:<32} predicted {r['predicted_ops']:6.1f}  observed {r['observed_ops']:4d}  {r['error']:+.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
