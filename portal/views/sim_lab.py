import numpy as np
import pandas as pd
import streamlit as st

import charts as C
import core
from eventlog import StationTruth, generate_orders

M, D = core.M, core.D

st.title("Simulation lab")
st.markdown("Run the independent simulator yourself and watch it converge on what the "
            "equations predict. The simulator builds the operation customer by customer "
            "and **shares no code with the model**, so agreement between them is evidence.")

scenario = st.radio("What to simulate", ["One station with a crew", "Customers who give up",
                                         "A line of stations"], horizontal=True)

with st.sidebar:
    st.subheader("Simulation settings")
    n = st.select_slider("Customers to simulate", [20_000, 50_000, 100_000, 200_000, 400_000, 1_000_000],
                         value=1_000_000,
                         help="More customers shrink the confidence interval. Busy stations "
                              "need more: waits there are long and strongly correlated.")
    seed = st.number_input("Random seed", 1, 99_999, 7)
    warm_frac = st.slider("Warmup discarded", 0.0, 0.3, 0.10, 0.05, format="%.2f",
                          help="Simulations start empty, which is not normal operation. "
                               "The first share of customers is thrown away.")
    batches = st.slider("Batches (for batch means)", 10, 30, 20)
    margin = st.slider("Equivalence margin (±%)", 1, 20, 5) / 100

exact = True
unit = "min"

# ---------------------------------------------------------------- scenarios
if scenario == "One station with a crew":
    a, b, c = st.columns(3)
    lam = a.number_input("Arrivals per hour", 0.1, 500.0, 10.0, 0.5)
    mu = b.number_input("Each worker handles per hour", 0.1, 500.0, 4.0, 0.5)
    k = c.number_input("Workers", 1, 50, 3)
    cv = a.number_input("Work-time variability (cv)", 0.2, 2.5, 1.0, 0.1)
    try:
        th = M.mmc(lam, mu, int(k), cv)
    except core.ModelError as e:
        st.error(f"The model refuses: {e}")
        st.stop()
    theory = th.Wq * 60
    exact = (cv == 1.0) or (k == 1)
    with st.spinner("Simulating..."):
        _, waits, _ = core.cached_trace_mmc(lam, mu, int(k), n, int(seed), cv)
    series = waits * 60
    label = "wait in line"
    mech = ("Each customer arrives at a random time. The simulator keeps a list of when each "
            "worker will next be free, gives the customer to the worker who frees up first, "
            "and records how long they waited. This is exact for a first-come, first-served "
            "line with any work-time distribution.")
elif scenario == "Customers who give up":
    a, b, c = st.columns(3)
    lam = a.number_input("Arrivals per hour", 0.1, 500.0, 14.0, 0.5)
    mu = b.number_input("Each worker handles per hour", 0.1, 500.0, 4.0, 0.5)
    k = c.number_input("Workers", 1, 50, 3)
    pat = a.number_input("Average patience (minutes)", 0.5, 600.0, 20.0, 0.5)
    metric = b.selectbox("Compare", ["Time in line (all callers)", "Share who give up"])
    theta = 60.0 / pat
    th = M.erlang_a(lam, mu, int(k), theta)
    st.caption(f"Load = {lam / (k * mu):.0%} of crew capacity."
               + (" Over 100%: the plain model would refuse; here the line stays finite "
                  "because people give up." if lam > k * mu else ""))
    with st.spinner("Simulating..."):
        tq, ab = core.cached_trace_abandon(lam, mu, int(k), theta, n, int(seed))
    if metric.startswith("Time"):
        theory, series, label = th.Wq_all * 60, tq * 60, "time in line"
    else:
        theory, series, label, unit = th.p_abandon, ab, "share who give up", "share"
    mech = ("Each caller gets a random patience. If the wait for a free agent would exceed "
            "it, they hang up at that moment and never take an agent's time. Because the "
            "line is first-come, first-served, people who hang up never delay anyone behind "
            "them, which makes this simulation exact.")
else:
    st.caption("Stations in a row: each order goes through every station in order.")
    default = pd.DataFrame({"Station": ["Picking", "Packing", "Loading"],
                            "Workers": [3, 2, 1], "Per hour per worker": [8.0, 13.0, 30.0],
                            "Variability (cv)": [0.8, 0.6, 1.0]})
    sdf = st.data_editor(default, num_rows="dynamic", width="stretch", key="lab_line")
    lam = st.number_input("Orders per hour", 0.1, 500.0, 22.0, 0.5)
    sts = [StationTruth(str(r["Station"]), float(r["Per hour per worker"]), int(r["Workers"]),
                        float(r["Variability (cv)"])) for _, r in sdf.dropna().iterrows()]
    nn = len(sts)
    op = M.Operation(stations=tuple(M.Station(s.name, s.service_rate, s.workers, s.cv) for s in sts),
                     external_arrivals=tuple(lam if j == 0 else 0.0 for j in range(nn)),
                     routing=tuple(tuple(1.0 if q == j + 1 else 0.0 for q in range(nn)) for j in range(nn)))
    try:
        b = M.evaluate(op)
    except core.ModelError as e:
        st.error(f"The model refuses: {e}")
        st.stop()
    theory = sum(r.W for r in b.station_results) * 60
    exact = all(s.cv == 1.0 for s in sts)
    n_line = min(n, 200_000)

    @st.cache_data(show_spinner="Simulating the line...")
    def _line(lam_, rows, n_, seed_):
        o = generate_orders(lam_, [StationTruth(*r) for r in rows], n_, seed_)
        first = o[o["station"] == rows[0][0]].set_index("order_id")["arrived_at"]
        last = o[o["station"] == rows[-1][0]].set_index("order_id")["finished_at"]
        return ((last - first).dt.total_seconds() / 60).to_numpy()

    series = _line(lam, tuple((s.name, s.service_rate, s.workers, s.cv) for s in sts), n_line, int(seed))
    label = "total time through the line"
    if n > n_line:
        st.caption("Lines are capped at 200,000 orders to keep the page fast.")
    mech = ("Orders arrive at random at the first station. At each station, orders are taken "
            "in the order they arrived there, by whichever worker frees up first; finished "
            "orders move to the next station. The simulator records every timestamp, exactly "
            "like a real warehouse export.")

# ---------------------------------------------------------------- results
warm = int(len(series) * warm_frac)
est = core.batch_estimate(series[warm:], batches)
bm = np.asarray(series[warm:][: (len(series) - warm) // batches * batches]).reshape(batches, -1).mean(axis=1)
res = core.tost_from_estimate(est, batches, theory, margin)

st.subheader("Result")
a, b, c, d = st.columns(4)
fmt = (lambda x: f"{x:.2%}") if unit == "share" else (lambda x: f"{x:.3f} min")
a.metric("Model predicts", fmt(theory))
b.metric("Simulation measured", fmt(est.mean), help=f"95% CI {fmt(est.lo)} to {fmt(est.hi)}")
c.metric("Difference", f"{est.mean / theory - 1:+.2%}" if theory else "n/a")
if exact:
    d.metric(f"TOST p-value (±{margin:.0%})", f"{res.p_value:.2g}")
    if res.equivalent:
        st.success(f"**Equivalent within ±{margin:.0%}.** The simulation proves the equation is "
                   f"within the margin (TOST p = {res.p_value:.2g} < 0.05).")
    else:
        st.warning(f"**Not shown equivalent within ±{margin:.0%}** (TOST p = {res.p_value:.2g}). "
                   "If the difference is small but the interval is wide, the simulation is "
                   "too short to prove anything yet: add customers, never widen the margin.")
else:
    d.metric("Formula type", "Approximation")
    st.info("**This formula is an approximation here**, so no equivalence claim is made. "
            "Exact cases: exponential work times, or a single worker. The gap shown is a "
            "measured finding about the approximation, not a pass or fail.")

l, r = st.columns(2)
with l:
    st.markdown(f"**Running average of {label}**")
    st.altair_chart(C.convergence(C.running_average(series), theory, warm,
                                  unit if unit != "share" else "share", margin),
                    width="stretch")
    st.caption("Orange: the simulation's running average. Blue: the model. Gray band: the "
               "equivalence margin. Shaded start: warmup, thrown away.")
with r:
    st.markdown("**What the test actually judges: batch averages**")
    st.altair_chart(C.batch_dots(bm, theory, (est.lo, est.hi), margin,
                                 unit if unit != "share" else "share"), width="stretch")
    st.caption("Each dot is the average of one batch of customers. The orange band is the 95% "
               "confidence interval of their overall average. TOST passes when the 90% interval "
               "sits inside the gray margin band.")

if exact and not res.equivalent and abs(res.diff) < res.margin:
    t = 1.729  # t(0.95, 19)
    need = len(series) * (t * res.se / (res.margin - abs(res.diff))) ** 2
    st.info(f"**Sample-size estimate:** roughly {need:,.0f} customers would shrink the interval "
            f"enough to prove ±{margin:.0%}, if the difference stays where it is.")

with st.expander("How this simulation works"):
    st.markdown(mech)
with st.expander("Why throw away a warmup?"):
    st.markdown("The simulation starts with an empty building, which never happens during a "
                "normal day. Early customers wait less than they would in steady operation, "
                "so they would pull the average down. Discarding the first share removes that "
                "start-up bias.")
with st.expander("Why batch averages instead of every customer?"):
    st.markdown("Customers in the same rush wait similar amounts, so their waits are not "
                "independent. Treating 200,000 correlated waits as independent would make the "
                "confidence interval far too narrow and overstate certainty. Averaging over "
                "long batches makes the batch averages nearly independent, so their spread "
                "gives an honest interval (19 degrees of freedom with 20 batches).")
