import json
import subprocess

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats as sp

import charts as C
import core

st.title("Real-data tests")
st.markdown("Every real-data test is pre-registered: the pass/fail rules are committed to git "
            "before any prediction is compared with the data, and each test runs once.")
t1, t2 = st.tabs(["Round 1 · call center (failed 1/6)", "Round 2 · warehouse and factory"])

with t1:
    st.subheader("Anonymous Bank call center (1999)")
    st.error("**Verdict: FAILED, 1 of 6 pre-registered criteria.** The model answered for 97% "
             "of real hours, but predicted about twice the real waiting and twice the real "
             "hang-ups, and ranked busy versus quiet hours poorly. Recorded as a failure, not "
             "tuned away.", icon=":material/cancel:")

    st.markdown("""
    **What was tested.** 417,149 real calls to an Israeli bank's call center (Technion SEE Center
    data). Each busy weekday hour is one test case: the model gets that hour's measured arrival
    rate, call lengths, available agents, and hang-up rate, and predicts how long callers waited
    and how many gave up. Then the predictions are compared with what really happened.
    """)

    # ---------------------------------------------------------------- timeline
    st.subheader("Rules first, results second: the git record")
    try:
        log = subprocess.run(["git", "log", "--format=%h|%ad|%s", "--date=iso"], cwd=core.ROOT,
                             capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
    except Exception:
        log = []
    if not log:
        log = [l for l in core.read_doc("GIT_HISTORY.txt").splitlines() if l and not l.startswith("#")]
        log = ["|".join([l[:7], l[9:34], l[36:]]) for l in log]
    keep = [l.split("|", 2) for l in log
            if any(k in l for k in ("Anonymous Bank", "amendment 1", "Phase 1", "Holdout", "Erlang A (abandonment)"))]
    tl = pd.DataFrame(keep, columns=["Commit", "Time (UTC)", "What was committed"]).iloc[::-1]
    st.dataframe(tl, hide_index=True, width="stretch")
    st.caption("Each row is a commit on GitHub. The pass/fail rules (first row) and the amendment "
               "were committed before the frozen choice, which was committed before any holdout "
               "result existed.")

    # ---------------------------------------------------------------- scorecard (recomputed)
    frz = json.loads((core.RESULTS / "bank_frozen_choice.json").read_text())
    w = pd.read_csv(core.RESULTS / "bank_holdout_windows.csv")
    v = w.dropna(subset=["pred_wq_s"])
    ratio = (v["pred_wq_s"] + 1) / (v["obs_wq_s"] + 1)
    s1 = sp.spearmanr(v["pred_wq_s"], v["obs_wq_s"]).statistic
    s2 = ratio.median()
    s3 = (v["n"] * v["pred_wq_s"]).sum() / (v["n"] * v["obs_wq_s"]).sum() - 1
    pab_p = (v["n"] * v["pred_pab"]).sum() / v["n"].sum()
    pab_o = v["abandoned"].sum() / v["n"].sum()
    s5 = w["pred_wq_s"].notna().mean()
    s6 = ((w["pred_wq_s_pooledtheta"] + 1) / (w["obs_wq_s"] + 1)).median()
    card = pd.DataFrame([
        ("S1", "Ranks busy vs quiet hours (rank correlation)", f"{s1:.2f}", "≥ 0.70", s1 >= 0.7),
        ("S2", "Typical hour: predicted ÷ actual wait", f"{s2:.2f}", "0.67 to 1.50", 0.67 <= s2 <= 1.5),
        ("S3", "All hours: total predicted vs actual waiting", f"{s3:+.0%}", "within ±25%", abs(s3) <= .25),
        ("S4", "Share of callers who hung up", f"{pab_p:.1%} vs {pab_o:.1%}", "within ±25%", abs(pab_p / pab_o - 1) <= .25),
        ("S5", "Hours the model could answer", f"{s5:.1%}", "≥ 95%", s5 >= .95),
        ("S6", "S2 again, hang-up rate from other months", f"{s6:.2f}", "0.67 to 1.50", 0.67 <= s6 <= 1.5),
    ], columns=["ID", "Criterion", "Result", "Pass if", "ok"])
    card["Verdict"] = np.where(card["ok"], "PASS", "FAIL")
    st.subheader(f"Blind holdout scorecard (July to December, {len(w):,} hours)")
    st.dataframe(card.drop(columns="ok"), hide_index=True, width="stretch")
    st.caption(f"Recomputed live from results/bank_holdout_windows.csv. Frozen model: "
               f"{frz['variant']} (Erlang A, callers who give up) with {frz['rule']} (effective agents), "
               f"chosen on January to June only.")

    # ---------------------------------------------------------------- charts
    l, r = st.columns(2)
    with l:
        st.markdown("**Every hour: predicted vs actual average wait**")
        d = v.assign(pred=v["pred_wq_s"] + 1, obs=v["obs_wq_s"] + 1)
        st.altair_chart(C.pred_vs_obs(d, "obs", "pred", "Actual wait + 1 s (log)", "Predicted wait + 1 s (log)",
                                      [alt.Tooltip("win:N", title="hour")]), width="stretch")
        st.caption("Dashed: perfect prediction. Gray band: within ±50%. Most hours sit above the "
                   "line: the model is too pessimistic.")
    with r:
        st.markdown("**By hour of day**")
        bh = v.groupby("hour").apply(lambda g: pd.Series({
            "Model": (g["n"] * g["pred_wq_s"]).sum() / g["n"].sum(),
            "Real data": (g["n"] * g["obs_wq_s"]).sum() / g["n"].sum()}), include_groups=False).reset_index()
        long = bh.melt(id_vars="hour", var_name="Series", value_name="wait")
        st.altair_chart(C.lines(long, "hour", "wait", "Series", "Hour of day", "Average wait (seconds)"),
                        width="stretch")
        st.caption("The model gets the daily shape roughly right but runs about twice too high "
                   "all day, which points to a systematic input problem, not random noise.")

    # ---------------------------------------------------------------- learning
    st.subheader("Why it failed, and what's next")
    st.markdown("""
    1. **Headcount is not capacity.** In the first half, counting every agent who answered a call
       made the model wrong by a factor of about 18. Agents were available for incoming calls only
       about 38% of the time. Measuring *effective* agents (busy while callers wait) cut the error
       to about 2× (changelog C-007).
    2. **The bias was visible before the blind test.** The model was chosen by the size of its
       errors, not their direction, so a model that was always too high still won. Next time the
       selection score must punish bias, like the scorecard does (C-008).
    3. **Leading explanation:** lines form exactly when fewer agents are free, so counting busy
       agents during waits samples the worst moments of the hour and understates capacity.

    **Round 2:** a capacity measure free of that effect, a selection score that matches the
    scorecard, and a fresh blind dataset. July to December is retired as a blind set.

    **What this means:** the queueing equations are proven against simulation. What failed is
    turning a real company's records into the right inputs, which is exactly the gap for small
    operations that plan by headcount.
    """)
    with st.expander("The pre-registration, as committed"):
        st.markdown(core.read_doc("PREREGISTRATION_BANK.md"))
    with st.expander("The generated report"):
        st.markdown(core.read_doc("REAL_DATA_VALIDATION.md"))

with t2:
    import json as _json
    r2 = _json.loads((core.RESULTS / "real2.json").read_text())
    a2, c2 = r2["R-A"], r2["R-C"]
    st.markdown("Round 1 used a call center because it was the best free dataset with complete "
                "timestamps, not because it matches the project. Round 2 uses the project's "
                "actual targets: a **distribution warehouse** and a **production floor**.")
    m1, m2, m3 = st.columns(3)
    hit90 = [x for x in a2["card"] if x["id"] == "R-A1"][0]
    m1.metric("Warehouse: 90% service target delivered", f"{hit90['realized']:.1%}",
              help=f"{a2['products_scored']} real products, 19 unseen weeks")
    m2.metric("Factory: bottleneck identified", "Yes" if c2["card"][1]["pass"] else "No")
    m3.metric("Criteria passed", f"{sum(x['pass'] for x in a2['card']) + sum(x['pass'] for x in c2['card'])} / 5")

    st.subheader("R-A · Warehouse inventory: does the best-stock-level rule deliver its promise?")
    st.caption("Footwear manufacturer's warehouse, 2023 (Mendeley Data, CC BY 4.0). Stock levels set from "
               "January to May demand; judged on June to October, which the rule never saw.")
    ra = pd.DataFrame([{"Target service": f"{x['target']:.0%}", "Delivered": x["realized"],
                        "Pass if": f"{x['band'][0]:.0%} to {x['band'][1]:.0%}",
                        "Verdict": "PASS" if x["pass"] else "FAIL",
                        "Simple percentile baseline": a2["extra"][x["id"]]["empirical_quantile_baseline"]}
                       for x in a2["card"]])
    st.dataframe(ra.style.format({"Delivered": "{:.1%}", "Simple percentile baseline": "{:.1%}"}),
                 hide_index=True, width="stretch")
    pts = pd.DataFrame([{"Target": x["target"], "Delivered": x["realized"], "Series": "Real data"} for x in a2["card"]])
    diag = pd.DataFrame({"x": [0.78, 0.97]})
    sc = alt.Scale(domain=[0.78, 0.97])
    ch = (alt.Chart(diag).mark_line(color=C.INK2, strokeDash=[4, 3]).encode(
              x=alt.X("x:Q", scale=sc), y=alt.Y("x:Q", scale=sc))
          + alt.Chart(pts).mark_circle(color=C.REAL, size=110).encode(
              x=alt.X("Target:Q", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0.78, 0.97]),
                      title="Service level the rule promised"),
              y=alt.Y("Delivered:Q", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0.78, 0.97]),
                      title="Service level actually delivered"),
              tooltip=[alt.Tooltip("Target:Q", format=".0%"), alt.Tooltip("Delivered:Q", format=".1%")]))
    st.altair_chart(C.finish(ch, 260), width="stretch")
    st.markdown("""
**What it shows.** At the targets businesses usually pick (90% and 95%), the rule delivered what it
promised on real demand. At 80% it overstocked (86.3%). **Why (exploratory):** most products'
weekly demand is skewed: many small weeks, a few huge ones. Products with roughly symmetric demand
hit **80.3%** at the 80% target; skewed ones hit 88.5%. The rule assumes a bell curve; skewed demand
needs a skewed model, which has to be tested on data not used here.

**Unexpected finding:** this warehouse's orders don't arrive one at a time. 32,634 orders were
created in only 768 distinct minutes, up to 594 at once; per 15 minutes, the variance is 85 to 288
times what random arrivals give. The warehouse releases work in **waves**, so the model's random-arrival
assumption fails for wave-based distributors. That is the clearest next modeling step.
""")
    st.subheader("R-C · Factory: does the routing math work on a real job shop?")
    st.caption("Machining job shop, January to March 2012 (Levy 2014, 4TU.ResearchData). Routes learned "
               "from work orders that started before 15 February; judged on the rest.")
    tbl = pd.DataFrame(c2["table"])
    long = pd.concat([tbl[["resource", "predicted_ops"]].rename(columns={"predicted_ops": "ops"}).assign(Series="Model"),
                      tbl[["resource", "observed_ops"]].rename(columns={"observed_ops": "ops"}).assign(Series="Real data")])
    ch = alt.Chart(long).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("resource:N", title=None, sort="-x", axis=alt.Axis(labelLimit=260)), yOffset="Series:N",
        x=alt.X("ops:Q", title="Operations in the test period"),
        color=alt.Color("Series:N", scale=alt.Scale(domain=["Model", "Real data"], range=[C.MODEL, C.REAL]),
                        legend=alt.Legend(title=None)),
        tooltip=["resource:N", "Series:N", alt.Tooltip("ops:Q", format=".0f")])
    st.altair_chart(C.finish(ch, 360), width="stretch")
    st.markdown(f"""
| ID | Criterion | Result | Verdict |
|---|---|---|---|
| R-C1 | Workload per machine, median error | {c2['card'][0]['value']:.1%} (need ≤ 20%) | {'PASS' if c2['card'][0]['pass'] else 'FAIL'} |
| R-C2 | Predicted bottleneck among the 2 busiest | predicted **{c2['card'][1]['predicted_busiest']}**; actual top 2: {', '.join(c2['card'][1]['observed_top2'])} | {'PASS' if c2['card'][1]['pass'] else 'FAIL'} |

**Why R-C1 failed (exploratory):** the data ends on 31 March, so work orders that started in March were
cut off mid-route (7.1 recorded steps each, against 13.8 for complete orders). The model predicted full
routes, so it over-predicted, most at end-of-route steps like Packing. This is a flaw in how the test was
designed (it ignored that cutoff), recorded as a failure and as a lesson for the next test.
""")
    with st.expander("The round 2 pre-registration, as committed"):
        st.markdown(core.read_doc("PREREGISTRATION_REAL2.md"))
    with st.expander("The round 2 report"):
        st.markdown(core.read_doc("REAL2_REPORT.md"))
