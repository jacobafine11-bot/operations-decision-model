"""
bank_validation.py — the real-data blind test, exactly as pre-registered
in docs/PREREGISTRATION_BANK.md.

Two phases, run and committed separately so git history shows the order:

  python analysis/bank_validation.py calibrate
      Scores every model variant x agent-count rule on January-June only,
      freezes the best combination to results/bank_frozen_choice.json.
  python analysis/bank_validation.py holdout
      Runs ONLY the frozen combination on July-December, scores the
      pre-registered scorecard, writes docs/REAL_DATA_VALIDATION.md.

Clarification recorded before any prediction was computed (not in the
original pre-registration, and disclosed in the report): log ratios and
the S2 ratio use a +1 second offset on both predicted and observed mean
queue time, because a quiet hour can have an observed mean wait of
exactly zero, where a ratio is undefined.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "model"))

import opsmodel as M  # noqa: E402
import stats as ST  # noqa: E402
from guardrails import ModelError  # noqa: E402

DATA = ROOT / "data" / "clean" / "bank_queue_events.parquet"
FROZEN = ROOT / "results" / "bank_frozen_choice.json"
OFFSET_S = 1.0
WORKWEEK = {6, 0, 1, 2, 3}          # Sun..Thu (pandas: Mon=0 .. Sun=6)
HOURS = range(8, 22)                 # 08:00 .. 21:59
MIN_ARRIVALS, MIN_AGENTS = 30, 2
VARIANTS = ("V1", "V2", "V3")
RULES = ("C1", "C2", "C3", "C4")


# ---------------------------------------------------------------- windows

def build_windows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["win"] = df["arrived_at"].dt.floor("h")
    served = df[df["outcome"] == "served"].copy()

    g = df.groupby("win")
    w = pd.DataFrame({
        "n": g.size(),
        "abandoned": g["outcome"].apply(lambda s: (s == "abandoned").sum()),
        "wait_sum_s": g["wait_s"].sum(),
    })
    w["obs_wq_s"] = w["wait_sum_s"] / w["n"]
    w["obs_pab"] = w["abandoned"] / w["n"]

    sg = served.groupby("win")["service_s"]
    w["svc_mean_s"] = sg.mean()
    w["svc_cv"] = sg.std(ddof=1) / sg.mean()

    # C1: distinct agents whose service STARTED in the window.
    served["start_win"] = served["started_at"].dt.floor("h")
    w["c1"] = served.groupby("start_win")["server"].nunique()

    # C2: presence-weighted agents (first start .. last end, per agent-day).
    served["day"] = served["started_at"].dt.normalize()
    shifts = served.groupby(["server", "day"]).agg(
        on=("started_at", "min"), off=("finished_at", "max")).reset_index()
    pres = {}
    for _, s in shifts.iterrows():
        h = s["on"].floor("h")
        while h < s["off"]:
            ov = (min(s["off"], h + pd.Timedelta(hours=1)) - max(s["on"], h))
            pres[h] = pres.get(h, 0.0) + ov.total_seconds() / 3600.0
            h += pd.Timedelta(hours=1)
    w["c2"] = pd.Series(pres).reindex(w.index).fillna(0).round().clip(lower=1)

    # C3: effective agents = time-average busy agents while >= 1 caller waits.
    w["c3_raw"] = effective_agents(df).reindex(w.index)
    w["c3"] = w["c3_raw"].round().clip(lower=1).fillna(w["c1"])

    # theta: abandonments per waiting-hour (censored exponential MLE).
    w["theta_per_hr"] = np.where(w["wait_sum_s"] > 0,
                                 w["abandoned"] / (w["wait_sum_s"] / 3600.0), 0.0)

    w = w.reset_index().rename(columns={"index": "win"})
    w["dow"] = w["win"].dt.dayofweek
    w["hour"] = w["win"].dt.hour
    keep = (w["dow"].isin(WORKWEEK) & w["hour"].isin(HOURS)
            & (w["n"] >= MIN_ARRIVALS) & (w["c1"].fillna(0) >= MIN_AGENTS)
            & w["svc_mean_s"].notna() & (w["svc_mean_s"] > 0))
    w = w[keep].copy()
    w["half"] = np.where(w["win"].dt.month <= 6, "calibration", "holdout")

    # C4: median C3 for the same weekday-hour over the 4 most recent PRIOR
    # weeks that have one (nothing from the window itself); else C1.
    w = w.sort_values("win").reset_index(drop=True)
    c4 = []
    hist: dict[tuple, list] = {}
    for _, r in w.iterrows():
        key = (r["dow"], r["hour"])
        prior = [v for v in hist.get(key, []) if np.isfinite(v)][-4:]
        c4.append(max(1.0, round(float(np.median(prior)))) if prior else float(r["c1"]))
        hist.setdefault(key, []).append(r["c3_raw"])
    w["c4"] = c4
    return w


def effective_agents(df: pd.DataFrame) -> pd.Series:
    """Per hour window: integral of (busy agents) over the time the queue
    is non-empty, divided by that time. Exact piecewise-constant sweep:
    +1/-1 events for service start/end and for queue entry/exit of callers
    who waited, plus zero-change events at every hour boundary so no
    segment crosses a window."""
    served = df[df["outcome"] == "served"]
    waited = df[df["wait_s"] > 0]
    t0 = df["arrived_at"].min().floor("h")
    sec = lambda s: (s - t0).dt.total_seconds().to_numpy()  # noqa: E731
    t_end = (df["left_queue_at"].max().ceil("h") + pd.Timedelta(days=1) - t0).total_seconds()
    hours = np.arange(0.0, t_end, 3600.0)
    times = np.concatenate([sec(served["started_at"]), sec(served["finished_at"]),
                            sec(waited["arrived_at"]), sec(waited["left_queue_at"]), hours])
    dbusy = np.concatenate([np.ones(len(served)), -np.ones(len(served)),
                            np.zeros(2 * len(waited)), np.zeros(len(hours))])
    dq = np.concatenate([np.zeros(2 * len(served)), np.ones(len(waited)),
                         -np.ones(len(waited)), np.zeros(len(hours))])
    order = np.argsort(times, kind="stable")
    times, dbusy, dq = times[order], dbusy[order], dq[order]
    busy, q = np.cumsum(dbusy), np.cumsum(dq)
    dur = np.diff(times)
    seg_win = np.floor(times[:-1] / 3600.0).astype(np.int64)
    mask = (q[:-1] > 0) & (dur > 0)
    qt = np.bincount(seg_win[mask], weights=dur[mask], minlength=len(hours))
    bt = np.bincount(seg_win[mask], weights=(busy[:-1] * dur)[mask], minlength=len(hours))
    with np.errstate(invalid="ignore", divide="ignore"):
        ceff = np.where(qt > 0, bt / qt, np.nan)
    idx = t0 + pd.to_timedelta(np.arange(len(hours)) * 3600, unit="s")
    return pd.Series(ceff, index=idx)


# ---------------------------------------------------------------- predict

def predict(row, variant: str, rule: str, theta_override: float | None = None):
    lam = float(row["n"])                          # per hour (1-hour window)
    mu = 3600.0 / float(row["svc_mean_s"])         # per hour per agent
    c = int(row[rule.lower()])
    try:
        if variant == "V1":
            r = M.mmc(lam, mu, c)
            return r.Wq * 3600.0, 0.0
        if variant == "V2":
            cv = float(row["svc_cv"]) if np.isfinite(row["svc_cv"]) else 1.0
            r = M.mmc(lam, mu, c, service_cv=max(cv, 1e-6))
            return r.Wq * 3600.0, 0.0
        th = float(row["theta_per_hr"]) if theta_override is None else theta_override
        r = M.erlang_a(lam, mu, c, th)
        return r.Wq_all * 3600.0, r.p_abandon
    except ModelError:
        return float("nan"), float("nan")      # the model refused


def score_selection(w: pd.DataFrame, variant: str, rule: str) -> dict:
    preds = [predict(r, variant, rule) for _, r in w.iterrows()]
    pw = np.array([p[0] for p in preds])
    lr = np.abs(np.log((pw + OFFSET_S) / (w["obs_wq_s"].to_numpy() + OFFSET_S)))
    lr[~np.isfinite(lr)] = np.inf                  # refusals = worst possible
    return {"variant": variant, "rule": rule,
            "median_abs_log_ratio": float(np.median(lr)),
            "refusal_rate": float(np.mean(~np.isfinite(pw))),
            "windows": int(len(w))}


# ---------------------------------------------------------------- phases

def calibrate() -> int:
    w = build_windows(pd.read_parquet(DATA))
    cal = w[w["half"] == "calibration"]
    rows = [score_selection(cal, v, r) for v in VARIANTS for r in RULES]
    table = pd.DataFrame(rows).sort_values("median_abs_log_ratio")
    best = table.iloc[0]
    theta_pooled = float(cal["abandoned"].sum() / (cal["wait_sum_s"].sum() / 3600.0))
    FROZEN.parent.mkdir(exist_ok=True)
    FROZEN.write_text(json.dumps({
        "frozen_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "variant": best["variant"], "rule": best["rule"],
        "theta_pooled_calibration_per_hr": theta_pooled,
        "calibration_windows": int(len(cal)),
        "holdout_windows": int((w["half"] == "holdout").sum()),
        "calibration_table": rows,
    }, indent=2))
    print(table.to_string(index=False))
    print(f"\nFROZEN: {best['variant']} + {best['rule']}; pooled theta "
          f"{theta_pooled:.3f}/hr ({len(cal)} calibration windows)")
    return 0


def holdout() -> int:
    frz = json.loads(FROZEN.read_text())
    V, R = frz["variant"], frz["rule"]
    w = build_windows(pd.read_parquet(DATA))
    h_all = w[w["half"] == "holdout"].copy()
    h, card, tost, by_hour, by_load = run_scorecard(h_all, V, R, frz)
    extra = None
    if R != "C4":   # Amendment 1: also score the forecast rule C4
        _, card4, tost4, _, _ = run_scorecard(h_all, V, "C4", frz)
        extra = (card4, tost4)
    ctx = pd.DataFrame([score_selection(h_all, vv, rr) for vv in VARIANTS for rr in RULES])
    h.to_csv(ROOT / "results" / "bank_holdout_windows.csv", index=False)
    write_report(frz, card, tost, by_hour, by_load, ctx, len(h), extra)
    for label, cd, ts in [(f"{V}+{R}", card, tost)] + ([(f"{V}+C4", *extra)] if extra else []):
        print(f"Holdout scorecard {label}: {sum(c[4] for c in cd)}/{len(cd)} passed")
        for c in cd:
            print(f"  {c[0]} {'PASS' if c[4] else 'FAIL'}  {c[1]}: {c[2]} (need {c[3]})")
        print(f"  TOST mean log ratio within ±log(1.25): p={ts.p_value:.3g}; "
              f"mean ratio {math.exp(ts.diff):.3f}")
    return 0


def run_scorecard(h: pd.DataFrame, V: str, R: str, frz: dict):
    h = h.copy()
    preds = [predict(r, V, R) for _, r in h.iterrows()]
    h["pred_wq_s"] = [p[0] for p in preds]
    h["pred_pab"] = [p[1] for p in preds]
    preds6 = [predict(r, V, R, theta_override=frz["theta_pooled_calibration_per_hr"])
              for _, r in h.iterrows()]
    h["pred_wq_s_pooledtheta"] = [p[0] for p in preds6]

    ok = h["pred_wq_s"].notna()
    v = h[ok]
    ratio = (v["pred_wq_s"] + OFFSET_S) / (v["obs_wq_s"] + OFFSET_S)
    s1 = float(sp.spearmanr(v["pred_wq_s"], v["obs_wq_s"]).statistic)
    s2 = float(ratio.median())
    tot_pred = float((v["n"] * v["pred_wq_s"]).sum())
    tot_obs = float((v["n"] * v["obs_wq_s"]).sum())
    s3 = tot_pred / tot_obs - 1
    pab_pred = float((v["n"] * v["pred_pab"]).sum() / v["n"].sum())
    pab_obs = float(v["abandoned"].sum() / v["n"].sum())
    s4 = pab_pred / pab_obs - 1 if pab_obs > 0 else float("nan")
    s5 = float(ok.mean())
    ok6 = h["pred_wq_s_pooledtheta"].notna()
    s6 = float(((h.loc[ok6, "pred_wq_s_pooledtheta"] + OFFSET_S)
                / (h.loc[ok6, "obs_wq_s"] + OFFSET_S)).median())

    card = [
        ("S1", "Spearman rank correlation, predicted vs observed queue time", f"{s1:.3f}", "≥ 0.70", s1 >= 0.70),
        ("S2", "Median predicted / observed queue time", f"{s2:.3f}", "0.67 to 1.50", 0.67 <= s2 <= 1.50),
        ("S3", "Total predicted vs observed queue-hours", f"{s3:+.1%}", "within ±25%", abs(s3) <= 0.25),
        ("S4", "Predicted vs observed abandonment fraction", f"{pab_pred:.2%} vs {pab_obs:.2%} ({s4:+.1%})", "within ±25%", abs(s4) <= 0.25),
        ("S5", "Coverage (model gives a valid answer)", f"{s5:.1%}", "≥ 95%", s5 >= 0.95),
        ("S6", "Median ratio with out-of-window pooled θ", f"{s6:.3f}", "0.67 to 1.50", 0.67 <= s6 <= 1.50),
    ]

    # Reported, not gated: TOST on mean log ratio within ±log(1.25), with
    # day-clustered standard error (windows on the same day are correlated).
    v = v.assign(lr=np.log(ratio))
    day_means = v.groupby(v["win"].dt.normalize())["lr"].mean()
    se = float(day_means.std(ddof=1) / math.sqrt(len(day_means)))
    tost = ST.tost_one_sample(float(day_means.mean()), se, len(day_means) - 1,
                              0.0, math.log(1.25))

    by_hour = v.groupby("hour").apply(lambda d: pd.Series({
        "windows": len(d),
        "obs wait (s)": d["obs_wq_s"].mean(),
        "pred wait (s)": d["pred_wq_s"].mean(),
        "obs abandon": d["abandoned"].sum() / d["n"].sum(),
        "pred abandon": (d["n"] * d["pred_pab"]).sum() / d["n"].sum(),
    }), include_groups=False)
    v = v.assign(load=v["n"] * v["svc_mean_s"] / 3600.0 / v[R.lower()])
    v["load band"] = pd.cut(v["load"], [0, 0.6, 0.8, 0.9, 1.0, 1.2, 10],
                            labels=["<0.6", "0.6-0.8", "0.8-0.9", "0.9-1.0", "1.0-1.2", ">1.2"])
    by_load = v.groupby("load band", observed=True).apply(lambda d: pd.Series({
        "windows": len(d),
        "obs wait (s)": d["obs_wq_s"].mean(),
        "pred wait (s)": d["pred_wq_s"].mean(),
        "median ratio": ((d["pred_wq_s"] + OFFSET_S) / (d["obs_wq_s"] + OFFSET_S)).median(),
    }), include_groups=False)

    return h, card, tost, by_hour, by_load


def write_report(frz, card, tost, by_hour, by_load, ctx, n_hold, extra):
    V, R = frz["variant"], frz["rule"]
    names = {"V1": "Erlang C, exponential service", "V2": "Erlang C, measured-cv correction",
             "V3": "Erlang A (abandonment), exponential service",
             "C1": "distinct agents serving in the hour",
             "C2": "presence-weighted agents",
             "C3": "effective agents (busy while callers wait)",
             "C4": "staffing plan (median effective agents, prior 4 weeks)"}
    cal = pd.DataFrame(frz["calibration_table"]).sort_values("median_abs_log_ratio")
    L = [
        "# Real-Data Validation: Anonymous Bank Call Center (1999)",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by "
        "`analysis/bank_validation.py holdout`. Rules: "
        "`docs/PREREGISTRATION_BANK.md`, committed before any prediction was "
        "compared with real data. Raw window-level results: "
        "`results/bank_holdout_windows.csv`.",
        "",
        "## What was tested",
        "",
        "417,149 real agent-seeking calls (Technion SEE Center, Anonymous Bank). "
        "Each busy weekday hour is one test case: the model receives that hour's "
        "measured arrival rate, service times, agent count, and abandonment rate, "
        "and predicts the average time callers spent waiting and the share who "
        "hung up. Those predictions are compared with what actually happened.",
        "",
        "## Phase 1: model choice on January to June only",
        "",
        "| Variant | Agent rule | Median abs log ratio (lower is better) | Refusal rate |",
        "|---|---|---|---|",
    ]
    for _, r in cal.iterrows():
        mark = " ◀ frozen" if (r["variant"], r["rule"]) == (V, R) else ""
        L.append(f"| {r['variant']}: {names[r['variant']]} | {r['rule']}: {names[r['rule']]} "
                 f"| {r['median_abs_log_ratio']:.3f}{mark} | {r['refusal_rate']:.1%} |")
    L += [
        "",
        f"Frozen at {frz['frozen_utc']}: **{V} ({names[V]}) with {R} ({names[R]})**. "
        f"{frz['calibration_windows']} calibration windows.",
        "",
        f"## Phase 2: blind holdout, July to December ({n_hold} windows), frozen choice run once",
        "",
        "| ID | Criterion | Result | Pass if | Verdict |",
        "|---|---|---|---|---|",
    ]
    for c in card:
        L.append(f"| {c[0]} | {c[1]} | {c[2]} | {c[3]} | {'PASS' if c[4] else 'FAIL'} |")
    L += [
        "",
        f"Reported, not gated: TOST equivalence of the mean log ratio within "
        f"±log(1.25), day-clustered (df = {tost.df}): mean ratio "
        f"{math.exp(tost.diff):.3f}, p = {tost.p_value:.3g}, "
        f"**{'equivalent within ±25%' if tost.equivalent else 'not shown equivalent within ±25%'}**.",
        "",
    ]
    if extra:
        card4, tost4 = extra
        L += [
            f"### Forecast version: {V} with C4 (staffing plan from prior weeks only)",
            "",
            "Required by Amendment 1. Uses nothing from the hour being predicted "
            "except its arrivals and service times; agent capacity comes from "
            "the previous four weeks.",
            "",
            "| ID | Criterion | Result | Pass if | Verdict |",
            "|---|---|---|---|---|",
        ]
        for c in card4:
            L.append(f"| {c[0]} | {c[1]} | {c[2]} | {c[3]} | {'PASS' if c[4] else 'FAIL'} |")
        L += ["", f"TOST (reported): mean ratio {math.exp(tost4.diff):.3f}, "
                  f"p = {tost4.p_value:.3g}.", ""]
    L += [
        "### By hour of day (holdout)",
        "",
        by_hour.round(3).to_markdown(),
        "",
        "### By load ρ = λE[S]/c (holdout)",
        "",
        by_load.round(3).to_markdown(),
        "",
        "### Context only: every candidate on the holdout",
        "",
        "Computed after the frozen run; used for no decision. Shows what the "
        "other variants would have scored.",
        "",
        ctx.sort_values("median_abs_log_ratio").round(3).to_markdown(index=False),
        "",
        "## Disclosed clarification",
        "",
        "Log ratios and the S2 ratio add 1 second to both predicted and observed "
        "mean queue time, because a quiet hour can have an observed mean wait of "
        "exactly zero. This rule was written into the analysis code before any "
        "prediction was computed; it was not in the original pre-registration.",
    ]
    (ROOT / "docs" / "REAL_DATA_VALIDATION.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    if phase == "calibrate":
        raise SystemExit(calibrate())
    if phase == "holdout":
        raise SystemExit(holdout())
    print(__doc__)
    raise SystemExit(2)
