import json

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import charts as C
import core

R = core.RESULTS


def load(name):
    p = R / name
    return json.loads(p.read_text()) if p.exists() else None


st.title("Benchmark: 160 made-up companies")
st.markdown(
    "Does the whole pipeline work across many different operations, from 2 to 250 "
    "workers? Every company goes through exactly what a real engagement would: its "
    "order history → validation gate → estimates → predictions → recommended plan. "
    "Then the **true** operation is re-simulated under every possible plan, so the "
    "model's advice can be graded against perfect knowledge.")

sealed, hard = load("benchmark_sealed.json"), load("benchmark_hard_sealed.json")
dev, hdev = load("benchmark_dev.json"), load("benchmark_hard_dev.json")
cov1, cov2 = load("coverage.json"), load("coverage2.json")
if not sealed:
    st.warning("Benchmark results not found in results/.")
    st.stop()

# ---------------------------------------------------------------- headline
rows_all = sealed["rows"] + hard["rows"]
exact = sum(r["pick"] == r["best_true"] for r in rows_all if not r.get("refused"))
heur = sum(s["diagnostics"]["heuristic_near_best"] for d in (sealed, hard) for s in d["scores"].values())
n = len(rows_all)
a, b, c, d = st.columns(4)
a.metric("Sealed companies", f"{n}", help="Run once each, after the model was frozen")
b.metric("Exact best plan chosen", f"{exact} / {n}")
c.metric("Rule of thumb near-best", f"{heur} / {n}",
         help="Always 'process change at the bottleneck': the comparison that shows skill vs luck")
tot_err = [abs(r["pred_total_h"] / r["true_total_h"] - 1) for r in rows_all if not r.get("refused")]
d.metric("Median error, time through the line", f"{np.median(tot_err):.1%}")

# ---------------------------------------------------------------- scorecards
st.subheader("Sealed scorecards (run once, as recorded)")
lab = {"S": "2 to 100 workers", "L": "100 to 250 workers"}
cards = []
for setname, data in (("Original", sealed), ("Hard decisions", hard)):
    for band, s in data["scores"].items():
        for cc in s["card"]:
            v = cc["value"]
            cards.append({"Set": setname, "Size": lab[band], "ID": cc["id"], "Criterion": cc["criterion"],
                          "Result": "n/a" if (v != v) else f"{v:.1%}", "Pass if": cc["pass_if"],
                          "Verdict": "N/A" if cc["pass"] is None else ("PASS" if cc["pass"] else "FAIL")})
cdf = pd.DataFrame(cards)
summary = cdf.groupby(["Set", "Size"]).apply(
    lambda g: f"{(g['Verdict'] == 'PASS').sum()} / {(g['Verdict'] != 'N/A').sum()}",
    include_groups=False).unstack()
st.dataframe(summary, width="stretch")
with st.expander("Every criterion, every set"):
    st.dataframe(cdf, hide_index=True, width="stretch")
st.caption("The one failure: hard decisions, 100 to 250 workers, P3 station waits 23.8% vs ≤ 15%. "
           "Diagnosis: 4 stations at 88% to 95% busy, where small estimation errors are amplified; "
           "with the true inputs the error was 5.7%. That finding led to the uncertainty ranges below.")

# ---------------------------------------------------------------- skill vs luck
st.subheader("Skill or luck? The model vs a rule of thumb")
sk = []
for setname, data in (("Original", sealed), ("Hard decisions", hard)):
    for band, s in data["scores"].items():
        dg = s["diagnostics"]
        sk += [{"Group": f"{setname} · {lab[band]}", "Who": "Model", "Near-best": dg["exact_best"] / dg["evaluated"]},
               {"Group": f"{setname} · {lab[band]}", "Who": "Rule of thumb",
                "Near-best": dg["heuristic_near_best"] / dg["evaluated"]}]
skdf = pd.DataFrame(sk)
ch = alt.Chart(skdf).mark_bar(cornerRadiusEnd=4).encode(
    y=alt.Y("Group:N", title=None, axis=alt.Axis(labelLimit=320)), yOffset="Who:N",
    x=alt.X("Near-best:Q", axis=alt.Axis(format="%"), title="Share of companies (model: exact best plan)"),
    color=alt.Color("Who:N", scale=alt.Scale(domain=["Model", "Rule of thumb"], range=[C.MODEL, C.INK2]),
                    legend=alt.Legend(title=None)),
    tooltip=["Group:N", "Who:N", alt.Tooltip("Near-best:Q", format=".0%")])
st.altair_chart(C.finish(ch, 220), width="stretch")
st.caption("The rule of thumb always fixes the bottleneck cheaply. It does well when that happens "
           "to be right; the hard set was built so that hiring, automation, or doing nothing win "
           "sometimes. The model kept choosing the exact best plan.")

# ---------------------------------------------------------------- predictions
l, r = st.columns(2)
with l:
    st.markdown("**Predicted vs true time through the line (all sealed companies)**")
    pts = pd.DataFrame([{"true": x["true_total_h"] * 60, "pred": x["pred_total_h"] * 60,
                         "company": f"{x['band']}{x['idx']}", "workers": x["workers"]}
                        for x in rows_all if not x.get("refused")])
    st.altair_chart(C.pred_vs_obs(pts, "true", "pred", "True (minutes, log)", "Predicted (minutes, log)",
                                  [alt.Tooltip("company:N"), alt.Tooltip("workers:Q")],
                                  color=C.MODEL, band=1.2), width="stretch")
    st.caption("Dashed: perfect. Band: ±20% (criterion P2). Every company is inside.")
with r:
    st.markdown("**Promised vs delivered savings, model's chosen plan**")
    sv = pd.DataFrame([{"delivered": x["pick_true_gross"], "promised": x["pick_promised_gross"],
                        "company": f"{x['band']}{x['idx']}"}
                       for x in rows_all if not x.get("refused") and x["pick"] != "Do nothing"
                       and x["pick_true_gross"] > 0])
    st.altair_chart(C.pred_vs_obs(sv, "delivered", "promised", "Delivered $/yr (log)", "Promised $/yr (log)",
                                  [alt.Tooltip("company:N")], color=C.MODEL, band=1.2), width="stretch")
    st.caption("Each dot: one company. Delivered = measured by re-simulating the true operation.")

# ---------------------------------------------------------------- coverage
st.subheader("How sure is each prediction? Uncertainty ranges, tested")
if cov1 and cov2:
    cv = pd.DataFrame([
        {"Round": "1 · estimation error only", "Measure": m, "Coverage": cov1["pooled"][k]}
        for m, k in (("Station waits", "c1"), ("Total time", "c2"), ("Near capacity", "c3"))] + [
        {"Round": "2 · plus formula error", "Measure": m, "Coverage": cov2["pooled"][k]}
        for m, k in (("Station waits", "c1"), ("Total time", "c2"), ("Near capacity", "c3"))])
    band = pd.DataFrame({"lo": [0.82], "hi": [0.97]})
    ch = (alt.Chart(band).mark_rect(color=C.BAND, opacity=0.5).encode(x="lo:Q", x2="hi:Q")
          + alt.Chart(cv).mark_bar(cornerRadiusEnd=4).encode(
              y=alt.Y("Measure:N", title=None, axis=alt.Axis(labelLimit=200)), yOffset="Round:N",
              x=alt.X("Coverage:Q", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1]),
                      title="Share of 90% ranges that contain the truth"),
              color=alt.Color("Round:N", scale=alt.Scale(range=[C.INK2, C.MODEL]), legend=alt.Legend(title=None)),
              tooltip=["Round:N", "Measure:N", alt.Tooltip("Coverage:Q", format=".1%")]))
    st.altair_chart(C.finish(ch, 200), width="stretch")
    st.caption("Gray band: the pass zone (82% to 97%). Round 1 ranges were too narrow at quiet "
               "stations, where the formula's own small error mattered more than estimation error. "
               "Round 2 adds that error, measured only on development companies, and passed all "
               "three criteria on 80 fresh companies.")

# ---------------------------------------------------------------- explorer
st.subheader("Explore one company")
choices = {f"{'Original' if i < len(sealed['rows']) else 'Hard'} · {x['band']}{x['idx']} · "
           f"{x['workers']} workers, {x['stations']} stations": x for i, x in enumerate(rows_all)}
pick = st.selectbox("Company", list(choices))
x = choices[pick]
if x.get("refused"):
    st.error(f"The model refused: {x['refusal']}")
else:
    plans = pd.DataFrame([{"Plan": k, "True value $/yr": v, "Model value $/yr": x["plans_model"].get(k, np.nan)}
                          for k, v in x["plans_true"].items()]).sort_values("True value $/yr", ascending=False)
    plans["Model's choice"] = np.where(plans["Plan"] == x["pick"], "◀ chosen", "")
    plans["True best"] = np.where(plans["Plan"] == x["best_true"], "★", "")
    st.dataframe(plans.style.format({"True value $/yr": core.money, "Model value $/yr": core.money}),
                 hide_index=True, width="stretch")
    st.caption(f"True time through the line {x['true_total_h']*60:.2f} min; model predicted "
               f"{x['pred_total_h']*60:.2f} min ({x['pred_total_h']/x['true_total_h']-1:+.1%}).")

with st.expander("How the benchmark works, and its rules"):
    st.markdown(core.read_doc("PREREGISTRATION_BENCHMARK.md"))
