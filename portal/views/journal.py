import json
import re

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import charts as C
import core

M, D = core.M, core.D

st.title("Fine-tuning journal")
st.markdown("Every change to the model, in the order it happened: **what we saw, the "
            "mechanism behind it, what changed, and the evidence.** Each entry has a live "
            "demonstration you can run. The rule throughout: an equation changes only for a "
            "reason that can be explained from how the operation works, never to make a "
            "number match.")

text = core.read_doc("CHANGELOG.md")
entries = {}
for block in re.split(r"\n(?=## C-\d{3})", text):
    mm = re.match(r"## (C-\d{3}) — (.+)", block.strip())
    if mm:
        entries[mm.group(1)] = (mm.group(2), block.strip())

summary = pd.DataFrame([
    ("C-001", "Waits overstated 35% when work is steady", "Model fixed (via C-004)"),
    ("C-002", "Rounded timestamps bias speed estimates", "Data policy set"),
    ("C-003", "One year of demand still leaves 15% uncertainty", "Fed into sensitivity"),
    ("C-004", "Work-time variability built into the model", "Model changed, verified"),
    ("C-005", "Validation standard: equivalence testing", "Method set"),
    ("C-006", "Customers who give up (Erlang A)", "Model added, verified"),
    ("C-007", "Headcount is not capacity (real data)", "Finding"),
    ("C-008", "First real-data blind test failed", "Recorded, diagnosed"),
    ("C-009", "Variability passed down a line of stations", "Model changed, held-out pass"),
    ("C-010", "160-company benchmark", "Sealed: 27 of 28 criteria"),
    ("C-011", "Uncertainty ranges for every prediction", "Added; coverage 2 of 3"),
    ("C-012", "Ranges include the formula's own error", "Fixed; coverage 3 of 3"),
    ("C-013", "Real warehouse and factory data", "3 of 5; new limits found"),
], columns=["Entry", "What happened", "Status"])
st.dataframe(summary, hide_index=True, width="stretch")

pick = st.selectbox("Open an entry", list(summary["Entry"]), index=len(summary) - 1,
                    format_func=lambda k: f"{k} · {summary.set_index('Entry').loc[k, 'What happened']}")
st.divider()
st.subheader(f"{pick} · {entries.get(pick, ('',))[0]}")

# ---------------------------------------------------------------- demos
if pick in ("C-001", "C-004"):
    st.markdown("**Live demo:** one crew, work times from very steady (cv 0.3) to very "
                "erratic (cv 2). The original model ignores variability (flat gray line). The "
                "corrected model scales the wait by (1 + cv²)/2. Orange: the simulator.")
    k = st.radio("Workers", [1, 3], horizontal=True,
                 help="With 1 worker the correction is exact (Pollaczek-Khinchine); with a crew it is an approximation.")
    lam, mu = (4.0, 6.0) if k == 1 else (10.0, 4.0)

    @st.cache_data(show_spinner="Simulating 7 variability levels...")
    def _cv_sweep(k_, lam_, mu_):
        rows = []
        for cv in [0.3, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
            _, w, _ = D.trace_mmc(lam_, mu_, k_, 300_000, 11, cv)
            e = D.batch_means(w[30_000:] * 60)
            rows.append({"cv": cv, "sim": e.mean, "lo": e.lo, "hi": e.hi,
                         "raw": M.mmc(lam_, mu_, k_).Wq * 60,
                         "corrected": M.mmc(lam_, mu_, k_, cv).Wq * 60})
        return pd.DataFrame(rows)

    sw = _cv_sweep(k, lam, mu)
    lines = (alt.Chart(sw).mark_line(color=C.INK2, strokeDash=[4, 3], strokeWidth=2).encode(
                 x=alt.X("cv:Q", title="Work-time variability (cv)"),
                 y=alt.Y("raw:Q", title="Average wait (minutes)"),
                 tooltip=[alt.Tooltip("raw:Q", format=".3f", title="original model")])
             + alt.Chart(sw).mark_line(color=C.MODEL, strokeWidth=2).encode(
                 x="cv:Q", y="corrected:Q",
                 tooltip=["cv:Q", alt.Tooltip("corrected:Q", format=".3f", title="corrected model")])
             + C.errorbars(sw, "cv", "lo", "hi", "sim"))
    st.altair_chart(C.finish(lines, 300), width="stretch")
    st.caption("Gray dashed: original model (assumes cv = 1). Blue: corrected model. Orange "
               "dots with whiskers: simulation with 95% intervals.")
    worst = (sw["corrected"] / sw["sim"] - 1).abs().max()
    st.markdown(f"Largest gap between corrected model and simulation here: **{worst:.1%}** "
                f"({'exact formula, gaps are simulation noise' if k == 1 else 'approximation for crews'}).")

elif pick == "C-002":
    st.markdown("**Live demo:** many export systems round timestamps to the second. That "
                "shaves about half a second off every recorded work time, which matters a lot "
                "when jobs are short.")
    cv = st.slider("Work-time variability (cv)", 0.3, 1.5, 0.6, 0.1)
    rng = np.random.default_rng(3)
    rows = []
    for mean_s in [3, 5, 8, 12, 20, 30, 45, 60, 90, 120, 180]:
        shape = 1 / cv ** 2
        x = rng.gamma(shape, mean_s / shape, 200_000)
        rows.append({"mean_s": mean_s, "bias": (1 / np.floor(x).mean()) / (1 / x.mean()) - 1})
    bias = pd.DataFrame(rows)
    ch = alt.Chart(bias).mark_line(color=C.SIM, strokeWidth=2, point=alt.OverlayMarkDef(size=64)).encode(
        x=alt.X("mean_s:Q", scale=alt.Scale(type="log"), title="True average work time (seconds, log)"),
        y=alt.Y("bias:Q", axis=alt.Axis(format="%"), title="Speed overstated by"),
        tooltip=[alt.Tooltip("mean_s:Q", title="avg seconds"), alt.Tooltip("bias:Q", format=".1%")])
    st.altair_chart(C.finish(ch, 260), width="stretch")
    st.markdown("Policy that came out of this: if an export only has whole seconds and "
                "average work takes under about a minute, time the work with a stopwatch "
                "sample or correct for the rounding.")

elif pick == "C-003":
    st.markdown("**Live demo:** how well can you know a product's demand spread from its "
                "history? Each line shows the range that 95% of estimates fall in.")
    cv = st.slider("How volatile the product is (cv of daily demand)", 0.2, 1.2, 0.8, 0.1)
    rng = np.random.default_rng(5)
    rows = []
    for days in [30, 60, 90, 180, 365, 730]:
        shape = 1 / cv ** 2
        sims = rng.gamma(shape, 100 / shape, (3000, days))
        err = sims.std(axis=1, ddof=1) / (100 * cv) - 1
        rows.append({"days": days, "lo": np.quantile(err, 0.025), "hi": np.quantile(err, 0.975)})
    rr = pd.DataFrame(rows)
    ch = (alt.Chart(rr).mark_area(color=C.SIM, opacity=0.25).encode(
              x=alt.X("days:Q", title="Days of history"), y=alt.Y("lo:Q", axis=alt.Axis(format="%"),
                                                                   title="Error in estimated spread"), y2="hi:Q")
          + alt.Chart(rr).mark_line(color=C.SIM, strokeWidth=2).encode(x="days:Q", y="hi:Q",
              tooltip=["days:Q", alt.Tooltip("hi:Q", format="+.0%", title="upper"),
                       alt.Tooltip("lo:Q", format="+.0%", title="lower")])
          + alt.Chart(rr).mark_line(color=C.SIM, strokeWidth=2).encode(x="days:Q", y="lo:Q"))
    st.altair_chart(C.finish(ch, 260), width="stretch")
    st.markdown("That uncertainty doesn't go away, so it becomes an input range for the "
                "sensitivity checks rather than a single number.")

elif pick == "C-005":
    st.markdown("**Live demo of the power rule:** a busy single station (90% utilization) "
                "where the formula is exactly right. With too few customers, the test can't "
                "prove it; the fix is more evidence, never a wider margin.")
    n = st.select_slider("Customers simulated", [100_000, 400_000, 1_000_000, 2_500_000], value=400_000)
    _, w, _ = core.cached_trace_mmc(9.0, 10.0, 1, n, 90, 1.0)
    e = core.batch_estimate(w[n // 10:] * 60, 20)
    th = M.mm1(9.0, 10.0).Wq * 60
    r = core.tost_from_estimate(e, 20, th, 0.05)
    a, b, c = st.columns(3)
    a.metric("Model", f"{th:.2f} min")
    b.metric("Simulation", f"{e.mean:.2f} min", help=f"95% CI {e.lo:.2f} to {e.hi:.2f}")
    c.metric("TOST p", f"{r.p_value:.2g}", delta="equivalent" if r.equivalent else "not yet",
             delta_color="normal" if r.equivalent else "off")
    st.caption("This is what happened on the first run of the upgraded suite: two busy cases "
               "missed at p = 0.06 and 0.15 with differences under 0.4%. They were rerun at "
               "2.5M and 1.6M customers and passed.")
    st.page_link("views/stats_lab.py", label="Why equivalence testing: Statistics lab", icon=":material/functions:")

elif pick == "C-006":
    st.markdown("**Live demo:** as the load passes 100% of the crew's capacity, the plain model "
                "has no answer (the line would grow forever). When customers give up, the line "
                "stays finite and the give-up model keeps answering.")
    pat = st.slider("Average patience (minutes)", 1, 60, 10)
    rows = []
    for load in np.arange(0.5, 1.51, 0.05):
        lam = load * 3 * 4.0
        try:
            ec = M.mmc(lam, 4.0, 3).Wq * 60
        except core.ModelError:
            ec = None
        ea = M.erlang_a(lam, 4.0, 3, 60.0 / pat)
        rows.append({"load": load, "Without give-ups (Erlang C)": ec,
                     "With give-ups (Erlang A)": ea.Wq_all * 60, "give_up": ea.p_abandon})
    df = pd.DataFrame(rows)
    long = df.melt(id_vars="load", value_vars=["Without give-ups (Erlang C)", "With give-ups (Erlang A)"],
                   var_name="Model", value_name="wait").dropna()
    ch = alt.Chart(long).mark_line(strokeWidth=2).encode(
        x=alt.X("load:Q", axis=alt.Axis(format="%"), title="Load (share of crew capacity)"),
        y=alt.Y("wait:Q", title="Average time in line (minutes)", scale=alt.Scale(type="log")),
        color=alt.Color("Model:N", scale=alt.Scale(range=[C.MODEL, C.INK2]), legend=alt.Legend(title=None)),
        strokeDash=alt.StrokeDash("Model:N", scale=alt.Scale(range=[[1, 0], [6, 3]]), legend=None),
        tooltip=["Model:N", alt.Tooltip("load:Q", format=".0%"), alt.Tooltip("wait:Q", format=".2f")])
    st.altair_chart(C.finish(ch, 280), width="stretch")
    st.caption("Dashed gray: Erlang C, which shoots up toward infinity and stops at 100% load. "
               "Blue: Erlang A, which keeps answering. Verified against simulation, including "
               "overloaded cases (TOST, Verification suite).")

elif pick in ("C-007", "C-008"):
    w = pd.read_csv(core.RESULTS / "bank_holdout_windows.csv")
    w["availability"] = w["c3_raw"] / w["c1"]
    if pick == "C-007":
        st.markdown("**Real data:** for every busy hour of the call center, agents who answered "
                    "at least one call (headcount) versus agents actually available while "
                    "callers were waiting (effective capacity).")
        sc = alt.Chart(w.dropna(subset=["c3_raw"])).mark_circle(color=C.REAL, size=40, opacity=0.5).encode(
            x=alt.X("c1:Q", title="Agents who answered calls that hour (headcount)"),
            y=alt.Y("c3_raw:Q", title="Agents actually available while callers waited"),
            tooltip=["win:N", "c1:Q", alt.Tooltip("c3_raw:Q", format=".1f")])
        ref = alt.Chart(pd.DataFrame({"x": [0, 18]})).mark_line(color=C.INK2, strokeDash=[4, 3]).encode(x="x:Q", y="x:Q")
        st.altair_chart(C.finish(sc + ref, 320), width="stretch")
        st.markdown(f"Median availability: **{w['availability'].median():.0%}** of headcount. "
                    "The dashed line is where they'd be equal; nearly every hour sits far below it.")
    else:
        frz = json.loads((core.RESULTS / "bank_frozen_choice.json").read_text())
        st.markdown("**The lesson in one table.** The model was chosen by the *size* of its "
                    "errors on January to June. That score couldn't see that the errors all "
                    "pointed the same way, so a biased model was frozen and failed the blind test.")
        st.dataframe(pd.DataFrame(frz["calibration_table"]).sort_values("median_abs_log_ratio")
                     .rename(columns={"median_abs_log_ratio": "error size (median abs log ratio)"}),
                     hide_index=True)
        st.page_link("views/real_data.py", label="Full real-data test", icon=":material/fact_check:")

elif pick == "C-009":
    q = json.loads((core.RESULTS / "qna_heldout.json").read_text())
    st.markdown("**Held-out evidence.** Four line configurations written down and committed "
                "before the check was run. Error in predicted wait at each downstream station, "
                "without and with the correction:")
    rows = pd.DataFrame(q["rows"])
    rows = rows[rows["position"] >= 2]
    rows["Station"] = rows["config"] + " · " + rows["station"]
    long = pd.concat([rows[["Station", "err_without"]].rename(columns={"err_without": "err"}).assign(Version="Before (random arrivals)"),
                      rows[["Station", "err_with"]].rename(columns={"err_with": "err"}).assign(Version="After (C-009)")])
    ch = alt.Chart(long).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("Station:N", title=None), yOffset="Version:N",
        x=alt.X("err:Q", axis=alt.Axis(format="%"), title="Prediction error"),
        color=alt.Color("Version:N", scale=alt.Scale(domain=["Before (random arrivals)", "After (C-009)"],
                                                     range=[C.INK2, C.MODEL]), legend=alt.Legend(title=None)),
        tooltip=["Station:N", "Version:N", alt.Tooltip("err:Q", format="+.1%")])
    st.altair_chart(C.finish(ch, 300), width="stretch")
    st.markdown(f"Average error **{q['mae_without']:.1%} → {q['mae_with']:.1%}**. Pre-registered rule: "
                f"(a) smaller error with the correction: **{'PASS' if q['rule_a'] else 'FAIL'}**; "
                f"(b) every station within ±25%: **{'PASS' if q['rule_b'] else 'FAIL'}**.")

elif pick == "C-010":
    st.markdown("**The benchmark in one picture:** how often the model's plan was the exact best, "
                "against a rule of thumb, across all four sealed groups.")
    st.page_link("views/benchmark.py", label="Open the full Benchmark page", icon=":material/leaderboard:")
    hs = json.loads((core.RESULTS / "benchmark_hard_sealed.json").read_text())
    s = hs["scores"]["L"]
    st.markdown(f"**The one failure:** hard decisions, 100 to 250 workers, station waits "
                f"{[c for c in s['card'] if c['id'] == 'P3'][0]['value']:.1%} vs ≤ 15%. Four stations at "
                "88% to 95% busy: with the TRUE inputs the formula's error was 5.7%; with inputs "
                "estimated from history, 23.8%. Near capacity, small measurement errors are amplified.")
    rho = np.linspace(0.5, 0.97, 60)
    amp = pd.DataFrame({"rho": rho})
    amp["amp"] = (1 / (1 - (rho * 1.01).clip(max=0.999)) - 1 / (1 - rho)) / (1 / (1 - rho))
    a50, a97 = float(amp["amp"].iloc[0]), float(amp["amp"].iloc[-1])
    ch = alt.Chart(amp).mark_line(color=C.MODEL, strokeWidth=2).encode(
        x=alt.X("rho:Q", axis=alt.Axis(format="%"), title="How busy the station is"),
        y=alt.Y("amp:Q", axis=alt.Axis(format="%"), title="Wait error from a 1% speed error"),
        tooltip=[alt.Tooltip("rho:Q", format=".0%"), alt.Tooltip("amp:Q", format=".1%")])
    st.altair_chart(C.finish(ch, 240), width="stretch")
    st.caption("The amplification comes from the 1/(1 − utilization) factor in every waiting-time "
               f"formula: a 1% error in measured speed moves the predicted wait by about {a50:.0%} "
               f"at 50% busy and about {a97:.0%} at 97% busy.")

elif pick in ("C-011", "C-012"):
    c1 = json.loads((core.RESULTS / "coverage.json").read_text())
    c2 = json.loads((core.RESULTS / "coverage2.json").read_text())

    def by_rho(d):
        st_ = [s for r in d["rows"] for s in r.get("stations", []) if s["true"] * 60 >= 0.1]
        out = []
        for lo, hi, lab in ((0, .7, "under 70%"), (.7, .8, "70-80%"), (.8, .88, "80-88%"), (.88, 1, "88%+")):
            g = [s["covered"] for s in st_ if lo <= s["rho"] < hi]
            if g:
                out.append({"Busy": lab, "Coverage": float(np.mean(g)), "n": len(g)})
        return pd.DataFrame(out)

    df = pd.concat([by_rho(c1).assign(Round="1 · estimation error only"),
                    by_rho(c2).assign(Round="2 · plus formula error")])
    st.markdown("**Coverage of 90% ranges by how busy the station is.** Round 1 failed at quiet "
                "stations: tiny estimation error made ranges narrow, but the formula's own ~6% error "
                "remained. Round 2 adds that error (measured only on development companies).")
    band = pd.DataFrame({"y0": [0.82], "y1": [0.97]})
    ch = (alt.Chart(band).mark_rect(color=C.BAND, opacity=0.5).encode(y="y0:Q", y2="y1:Q")
          + alt.Chart(df).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=64)).encode(
              x=alt.X("Busy:N", sort=["under 70%", "70-80%", "80-88%", "88%+"], title="How busy the station is"),
              y=alt.Y("Coverage:Q", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0.3, 1]),
                      title="Ranges containing the truth"),
              color=alt.Color("Round:N", scale=alt.Scale(range=[C.INK2, C.MODEL]), legend=alt.Legend(title=None)),
              strokeDash=alt.StrokeDash("Round:N", scale=alt.Scale(range=[[6, 3], [1, 0]]), legend=None),
              tooltip=["Round:N", "Busy:N", alt.Tooltip("Coverage:Q", format=".0%"), "n:Q"]))
    st.altair_chart(C.finish(ch, 260), width="stretch")
    st.caption("Gray band: the pass zone, 82% to 97%. Each round ran once on its own 80 fresh companies.")

elif pick == "C-013":
    o = pd.read_csv(core.ROOT / "data" / "public" / "warehouse_orders.csv", parse_dates=["created_at"])
    per = o.groupby("created_at").size().rename("orders").reset_index()
    st.markdown("**Real warehouse orders arrive in waves, not one at a time.** Each bar is one "
                "minute in which orders were created; 32,634 orders fell into only "
                f"{len(per):,} distinct minutes.")
    ch = alt.Chart(per).mark_bar(color=C.REAL).encode(
        x=alt.X("orders:Q", bin=alt.Bin(maxbins=40), title="Orders created in the same minute"),
        y=alt.Y("count():Q", title="Minutes", scale=alt.Scale(type="symlog")),
        tooltip=["count():Q"])
    st.altair_chart(C.finish(ch, 240), width="stretch")
    st.markdown("Random arrivals would almost never put more than a handful of orders in one "
                "minute. Batches of dozens or hundreds mean the warehouse releases work in waves, "
                "so the model's random-arrival assumption fails here. Next model change: batch "
                "arrivals, tested on fresh data.")
    st.page_link("views/real_data.py", label="Full round 2 results", icon=":material/fact_check:")

with st.expander("Full changelog entry", expanded=False):
    st.markdown(entries.get(pick, ("", "*Entry not found*"))[1])
