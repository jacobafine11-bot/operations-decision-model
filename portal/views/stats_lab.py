import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats as sp

import charts as C
import core

ST = core.ST

st.title("Statistics lab")
st.markdown("The statistical tests this project relies on, shown working. Full study and "
            "defense: `docs/STATS_STUDY.md` (Documents page).")

t1, t2, t3, t4 = st.tabs(["1 · Equivalence test, step by step", "2 · Why not a plain t-test?",
                          "3 · Input checks on real data", "4 · The tests, tested"])

# ---------------------------------------------------------------- 1
with t1:
    st.markdown("**Question:** is the simulation's average close enough to the model's "
                "prediction? TOST (two one-sided tests) puts the burden of proof on the "
                "model: it must show the difference is *inside* a margin set in advance.")
    a, b, c = st.columns(3)
    target = a.number_input("Model prediction", value=0.3511, format="%.4f")
    mean = b.number_input("Simulation average", value=0.3478, format="%.4f")
    se = c.number_input("Standard error of that average", value=0.0040, format="%.4f", min_value=1e-6)
    df_ = a.number_input("Degrees of freedom (batches − 1)", 1, 200, 19)
    m_rel = b.slider("Margin (±% of prediction)", 1, 20, 5) / 100
    m = m_rel * abs(target)
    r = ST.tost_one_sample(mean, se, int(df_), target, m)
    d = mean - target
    tA, tB = (d + m) / se, (d - m) / se
    pA, pB = float(sp.t.sf(tA, df_)), float(sp.t.cdf(tB, df_))
    st.markdown(f"""
| Step | Calculation | Value |
|---|---|---|
| Difference | simulation − model | {d:+.5f} |
| Margin | {m_rel:.0%} × {target:.4f} | ±{m:.5f} |
| Test 1: is the difference above −margin? | t₁ = (d + m) / se | {tA:.3f} → p₁ = {pA:.3g} |
| Test 2: is the difference below +margin? | t₂ = (d − m) / se | {tB:.3f} → p₂ = {pB:.3g} |
| TOST p-value | the larger of p₁ and p₂ (both must pass) | **{r.p_value:.3g}** |
""")
    (st.success if r.equivalent else st.warning)(
        f"**{'Equivalent' if r.equivalent else 'Not shown equivalent'}** within ±{m_rel:.0%} "
        f"(p = {r.p_value:.3g} {'<' if r.equivalent else '≥'} 0.05).")
    tq = float(sp.t.ppf(0.95, df_))
    vis = pd.DataFrame({"lo": [target - m], "hi": [target + m]})
    ci = pd.DataFrame({"lo": [mean - tq * se], "hi": [mean + tq * se], "y": ["90% CI"]})
    ch = (alt.Chart(vis).mark_rect(color=C.BAND, opacity=0.6).encode(x="lo:Q", x2="hi:Q")
          + alt.Chart(ci).mark_rule(color=C.SIM, strokeWidth=6).encode(
              x=alt.X("lo:Q", title="Value", scale=alt.Scale(zero=False)), x2="hi:Q",
              tooltip=[alt.Tooltip("lo:Q", format=".5f"), alt.Tooltip("hi:Q", format=".5f")])
          + alt.Chart(pd.DataFrame({"t": [target]})).mark_rule(color=C.MODEL, strokeWidth=2).encode(
              x="t:Q", tooltip=[alt.Tooltip("t:Q", format=".5f", title="model")]))
    st.altair_chart(C.finish(ch, 90), width="stretch")
    st.caption("Gray band: the margin. Orange bar: the simulation's 90% confidence interval. "
               "Blue line: the model. Equivalence is proven exactly when the orange bar fits "
               "inside the gray band.")
    st.markdown("**Why max(p₁, p₂)?** Equivalence needs *both* one-sided claims to hold "
                "(not too low *and* not too high). Each test is run at 5%, and the claim "
                "stands only if both pass, so the weaker of the two decides.")

# ---------------------------------------------------------------- 2
with t2:
    st.markdown("A plain t-test asks *\"can I prove the model and simulation differ?\"* and a "
                "model **passes by failing to find a difference**. That is easiest when the "
                "evidence is weakest. Below, thousands of simulated experiments for a model "
                "that is right, and one that is **10% wrong**, at growing sample sizes.")

    @st.cache_data(show_spinner=False)
    def _rates(seed=0):
        rng = np.random.default_rng(seed)
        rows = []
        dfree, reps = 19, 4000
        for rel_se in [0.20, 0.12, 0.08, 0.05, 0.035, 0.025, 0.018, 0.012, 0.008, 0.005]:
            for truth, name in [(0.0, "Model is right"), (0.10, "Model is 10% wrong")]:
                means = rng.normal(1.0 + truth, rel_se, reps)
                se_hat = rel_se * np.sqrt(rng.chisquare(dfree, reps) / dfree)
                tval = (means - 1.0) / se_hat
                ttest_pass = np.abs(tval) < sp.t.ppf(0.975, dfree)
                tq = sp.t.ppf(0.95, dfree)
                tost_pass = (np.abs(means - 1.0) + tq * se_hat) < 0.05
                size = (1 / rel_se) ** 2
                rows += [{"Relative sample size": size, "Test": "t-test says 'no difference'",
                          "Truth": name, "Pass rate": ttest_pass.mean()},
                         {"Relative sample size": size, "Test": "TOST says 'equivalent'",
                          "Truth": name, "Pass rate": tost_pass.mean()}]
        return pd.DataFrame(rows)

    rates = _rates()
    ch = alt.Chart(rates).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=64)).encode(
        x=alt.X("Relative sample size:Q", scale=alt.Scale(type="log"), title="Sample size (relative, log scale)"),
        y=alt.Y("Pass rate:Q", axis=alt.Axis(format="%"), title="How often the model 'passes'"),
        color=alt.Color("Test:N", scale=alt.Scale(range=[C.INK2, C.MODEL]), legend=alt.Legend(title=None)),
        strokeDash=alt.StrokeDash("Test:N", scale=alt.Scale(range=[[6, 3], [1, 0]]), legend=None),
        tooltip=["Truth:N", "Test:N", alt.Tooltip("Pass rate:Q", format=".0%")],
    ).properties(width=330).facet(column=alt.Column("Truth:N", title=None))
    st.altair_chart(ch.configure_view(strokeWidth=0).configure_axis(gridColor=C.GRID, labelColor=C.INK2,
                                                                     titleColor=C.INK2)
                    .configure_legend(orient="top", labelColor=C.INK2))
    st.markdown("""
**Read the right panel.** With small samples, the t-test "passes" the 10%-wrong model most of
the time, because it can't see anything. TOST almost never passes it, at any size. In the left
panel, TOST passes the correct model more and more as evidence grows; the t-test stays stuck
near 95% whatever you do. **TOST rewards strong evidence; the t-test rewards weak evidence.**
That is why every exact formula in this project is judged by TOST.
""")

# ---------------------------------------------------------------- 3
with t3:
    st.markdown("Before real data feeds the model, its assumptions are tested. Data: **Tyler's "
                "Grill, University of Richmond**, one real day in 2005: 1,434 customer arrival "
                "times and 110 measured service times (source in `data/public/README.md`).")
    arr = pd.read_csv(core.ROOT / "data" / "public" / "tylers_grill_arrivals.csv").iloc[:, 0].to_numpy()
    svc = pd.read_csv(core.ROOT / "data" / "public" / "tylers_grill_service.csv").iloc[:, 0].to_numpy()
    clock = pd.Timestamp("2005-01-01 07:30") + pd.to_timedelta(arr, unit="s")
    per = pd.Series(1, index=clock).resample("10min").sum()
    per_df = pd.DataFrame({"time": per.index, "arrivals": per.values})
    st.markdown("**Arrivals per 10 minutes, across the day**")
    st.altair_chart(C.finish(alt.Chart(per_df).mark_bar(color=C.REAL, cornerRadiusTopLeft=2,
                                                         cornerRadiusTopRight=2).encode(
        x=alt.X("time:T", title=None, axis=alt.Axis(format="%H:%M")),
        y=alt.Y("arrivals:Q", title="Arrivals per 10 min"),
        tooltip=[alt.Tooltip("time:T", format="%H:%M"), "arrivals:Q"]), 220), width="stretch")

    a, b = st.columns(2)
    with a:
        st.markdown("**Test 1: are arrivals per block Poisson?** (chi-square goodness of fit)")
        win = st.select_slider("Time window", options=[f"{h:02d}:{mm:02d}" for h in range(7, 21) for mm in (0, 30)],
                               value=("07:30", "20:30"))
        bin_min = st.selectbox("Block size (minutes)", [2, 5, 10], index=1)
        lo, hi = (pd.Timestamp(f"2005-01-01 {w}") for w in win)
        sel = clock[(clock >= lo) & (clock < hi)]
        counts = (pd.Series(1, index=sel).resample(f"{bin_min}min").sum()
                  .reindex(pd.date_range(lo, hi, freq=f"{bin_min}min", inclusive="left"), fill_value=0))
        try:
            ch2 = ST.chi2_poisson(counts.to_numpy())
            verdict = "rejected" if ch2.p_value < 0.05 else "not rejected"
            st.markdown(f"{len(counts)} blocks, mean {counts.mean():.2f} per block: "
                        f"χ² = {ch2.statistic:.1f}, df = {ch2.df}, **p = {ch2.p_value:.3g}**: "
                        f"Poisson {verdict}.")
        except ValueError as e:
            st.caption(f"Pick a wider window: {e}")
        st.caption("Try the whole day, then a single hour. Over the whole day the rate "
                   "swings (lunch rush), so a single Poisson rate is rejected; within a short "
                   "window, arrivals often look Poisson. The model therefore uses rates "
                   "measured per period, never one rate for the whole day.")
    with b:
        st.markdown("**Test 2: are work times exponential?** (bootstrap KS test)")
        ks = ST.ks_exponential(svc / 3600.0, n_boot=499, seed=1)
        cvs = svc.std(ddof=1) / svc.mean()
        st.markdown(f"110 service times, mean {svc.mean():.0f} s, cv **{cvs:.2f}**: "
                    f"D = {ks.statistic:.3f}, **p = {ks.p_value:.3g}**: exponential "
                    f"{'rejected' if ks.p_value < 0.05 else 'not rejected'}.")
        hist = pd.DataFrame({"seconds": svc})
        st.altair_chart(C.finish(alt.Chart(hist).mark_bar(color=C.REAL, cornerRadiusTopLeft=2,
                                                          cornerRadiusTopRight=2).encode(
            x=alt.X("seconds:Q", bin=alt.Bin(maxbins=20), title="Service time (s)"),
            y=alt.Y("count():Q", title="Customers"), tooltip=["count():Q"]), 200), width="stretch")
        st.caption("When work times aren't exponential, the model uses the measured cv "
                   "(changelog C-004), so this test decides which formula applies.")

# ---------------------------------------------------------------- 4
with t4:
    st.markdown("Before any test judged the model, the tests were judged themselves. From "
                "the latest verification run:")
    rep = core.read_doc("VERIFICATION_REPORT.md")
    sec = rep.split("### Layer 0")[1].split("### ")[0] if "### Layer 0" in rep else ""
    st.markdown("### Layer 0" + sec)
