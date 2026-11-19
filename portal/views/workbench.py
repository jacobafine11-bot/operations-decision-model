import math

import altair as alt
import pandas as pd
import streamlit as st

import charts as C
import core
import logic as L

M = core.M

st.title("Model workbench")
st.caption("Describe an operation, see how it runs and what it earns, rank changes, and size a crew. "
           "Every number here comes from the verified model.")

tab_op, tab_decide, tab_crew = st.tabs(
    ["1 · Your operation", "2 · Decide on changes", "3 · Size one crew"])

# ---------------------------------------------------------------- tab 1
with tab_op:
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Stations, in flow order")
        stations_df = st.data_editor(L.DEFAULTS["stations"], num_rows="dynamic",
                                     width="stretch", key="wb_stations")
        st.caption("Service variability (cv): how uneven the work times are. 1.0 if "
                   "unmeasured; lower if work is steady, higher if erratic. The data "
                   "pipeline measures it from timestamps.")
    with right:
        st.subheader("Demand and costs")
        arrival = st.number_input("Orders arriving per hour", 0.1, 10_000.0,
                                  L.DEFAULTS["arrival_rate"], 0.5)
        margin = st.number_input("Margin per shipped order ($)", 0.0, 10_000.0,
                                 L.DEFAULTS["margin"], 0.5)
        waiting = st.number_input("Cost of one order waiting one hour ($)", 0.0, 1_000.0,
                                  L.DEFAULTS["waiting_cost"], 0.5,
                                  help="The weakest input in most operations: late "
                                       "shipments, overtime, lost customers. The "
                                       "decisions tab shows where its value flips a ranking.")
        overhead = st.number_input("Staff + equipment overhead ($/hour)", 0.0, 100_000.0,
                                   L.DEFAULTS["overhead"], 5.0)
        hours = st.number_input("Operating hours per year", 1.0, 8784.0,
                                L.DEFAULTS["hours_per_year"], 50.0)
    try:
        op = L.build_operation(stations_df, arrival, margin, waiting, overhead, hours)
        table, bottleneck = L.station_table(op)
        st.subheader("How the operation runs today")
        st.dataframe(table, width="stretch", hide_index=True)
        st.info(f"**Bottleneck: {bottleneck}.** Improving any other station barely "
                "moves the totals until this one is addressed.")
        st.caption("Arrival variability below 1 means a station receives work more "
                   "evenly than random, because the station before it releases work at "
                   "its own steady pace (changelog C-009).")
        st.subheader("What it earns")
        st.dataframe(L.profit_table(op), width="stretch", hide_index=True)
        st.session_state["op"] = op
        st.session_state["station_names"] = [s.name for s in op.stations]
    except L.ModelError as e:
        st.error(f"The model stopped instead of guessing: {e}")
        st.session_state.pop("op", None)

# ---------------------------------------------------------------- tab 2
with tab_decide:
    if "op" not in st.session_state:
        st.warning("Fix the operation on tab 1 first.")
    else:
        op = st.session_state["op"]
        names = st.session_state["station_names"]
        st.subheader("Candidate changes")
        st.caption("A change edits the operation: re-slotting or equipment speeds a "
                   "station up; hiring adds a worker. The model re-prices the whole "
                   "operation for every combination and subtracts what it costs.")
        default_changes = pd.DataFrame({
            "Name": ["Re-slot fast movers", "Pick-to-light system", "Hire a packer"],
            "Station": ["Picking", "Picking", "Packing"],
            "Type": ["Speed up station by %", "Speed up station by %", "Add workers"],
            "Amount": [25.0, 60.0, 1.0],
            "One-time cost $": [3000.0, 60_000.0, 0.0],
            "Yearly upkeep $": [0.0, 3000.0, 38_000.0],
            "Spread cost over (years)": [5.0, 5.0, 1.0],
        })
        changes_df = st.data_editor(
            default_changes, num_rows="dynamic", width="stretch", key="wb_changes",
            column_config={
                "Station": st.column_config.SelectboxColumn(options=names),
                "Type": st.column_config.SelectboxColumn(
                    options=["Speed up station by %", "Add workers"]),
            })
        budget = st.number_input("Budget for one-time costs ($)", 0.0, 10_000_000.0,
                                 100_000.0, 1000.0)
        try:
            changes = L.build_changes(changes_df, names)
            if changes:
                plans = L.plan_table(op, changes, budget)
                st.subheader("Every affordable plan, ranked")
                st.dataframe(plans, width="stretch", hide_index=True)
                st.caption("Value = yearly profit gain minus annualized cost. 'Do "
                           "nothing' is always a candidate, so a losing plan never wins. "
                           "Plans are priced as combinations because fixing one "
                           "bottleneck moves it elsewhere.")
                if len(changes) >= 2:
                    i = M.interaction(op, changes[0], changes[1])
                    kind = ("work better together" if i > 0 else
                            "overlap, so buying both wastes money" if i < 0 else "are independent")
                    st.markdown(f"**Interaction:** '{changes[0].name}' and '{changes[1].name}' "
                                f"{kind} ({core.money(i)}/yr).")
                    flip = L.waiting_cost_flip(op, [changes[0]], [changes[1]])
                    if flip is not None:
                        st.info(f"**Honesty check:** the ranking between '{changes[0].name}' "
                                f"and '{changes[1].name}' flips when the cost of a waiting "
                                f"order crosses **${flip:,.2f}/order-hour** (you entered "
                                f"${op.waiting_cost:,.2f}). If the real value is near that "
                                "line, measure it before deciding.")
        except L.ModelError as e:
            st.error(f"The model stopped instead of guessing: {e}")

# ---------------------------------------------------------------- tab 3
with tab_crew:
    st.subheader("How many people should one station have?")
    st.caption("One station, one crew. Compares the model variants side by side and "
               "applies the staffing rule: add a worker only while the waiting cost "
               "they remove is worth more than their wage.")
    a, b, c = st.columns(3)
    lam = a.number_input("Orders (or calls) per hour", 0.5, 2000.0, 20.0, 0.5, key="cr_lam")
    mu = a.number_input("Each worker handles per hour", 0.1, 500.0, 6.0, 0.5, key="cr_mu")
    cv = b.number_input("Work-time variability (cv)", 0.1, 3.0, 1.0, 0.1, key="cr_cv")
    patience_min = b.number_input("Average patience before giving up (minutes, 0 = never)",
                                  0.0, 600.0, 0.0, 1.0, key="cr_pat",
                                  help="Call centers and walk-in counters lose customers who "
                                       "wait too long. Warehouses usually don't: set 0.")
    wage = c.number_input("Loaded wage per worker ($/hour)", 0.0, 500.0, 22.0, 1.0, key="cr_wage")
    cw = c.number_input("Cost of one order waiting one hour ($)", 0.0, 1000.0, 4.0, 0.5, key="cr_cw")

    theta = 60.0 / patience_min if patience_min > 0 else 0.0
    c_min = max(1, math.floor(lam / mu) + (0 if theta > 0 else 1))
    rows = []
    for k in range(c_min, c_min + 8):
        row = {"Workers": k, "Utilization": lam / (k * mu)}
        try:
            r = M.mmc(lam, mu, k, cv)
            row["Wait (min), model"] = r.Wq * 60
            row["Waiting cost $/hr"] = cw * r.Lq
        except core.ModelError:
            row["Wait (min), model"] = float("nan")
            row["Waiting cost $/hr"] = float("nan")
        if theta > 0:
            ra = M.erlang_a(lam, mu, k, theta)
            row["Wait (min), with give-ups"] = ra.Wq_all * 60
            row["Give up"] = ra.p_abandon
            row["Waiting cost $/hr"] = cw * ra.Lq   # the give-up model is the right one here
        row["Wage $/hr"] = wage * k
        rows.append(row)
    df = pd.DataFrame(rows)
    df["Total $/hr"] = df["Waiting cost $/hr"] + df["Wage $/hr"]
    valid = df.dropna(subset=["Total $/hr"])
    if not valid.empty:
        best = valid.loc[valid["Total $/hr"].idxmin()]
        st.success(f"**Recommended crew: {int(best['Workers'])}** (lowest wage + waiting "
                   f"cost, {core.money(best['Total $/hr'])}/hr). Adding one more would cost "
                   f"{core.money(wage)}/hr and remove less waiting cost than that.")
    fmt = {"Utilization": "{:.0%}", "Give up": "{:.1%}", "Wait (min), model": "{:.2f}",
           "Wait (min), with give-ups": "{:.2f}", "Waiting cost $/hr": "${:,.2f}",
           "Wage $/hr": "${:,.2f}", "Total $/hr": "${:,.2f}"}
    st.dataframe(df.style.format({k: v for k, v in fmt.items() if k in df}, na_rep="refuses (overloaded)"),
                 width="stretch", hide_index=True)
    long = valid.melt(id_vars="Workers", value_vars=["Waiting cost $/hr", "Wage $/hr", "Total $/hr"],
                      var_name="Cost", value_name="dollars")
    ch = alt.Chart(long).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=64)).encode(
        x=alt.X("Workers:O"), y=alt.Y("dollars:Q", title="$ per hour"),
        color=alt.Color("Cost:N", scale=alt.Scale(domain=["Waiting cost $/hr", "Wage $/hr", "Total $/hr"],
                                                  range=[C.SIM, C.INK2, C.MODEL]),
                        legend=alt.Legend(title=None)),
        strokeDash=alt.StrokeDash("Cost:N", scale=alt.Scale(
            domain=["Waiting cost $/hr", "Wage $/hr", "Total $/hr"], range=[[6, 3], [2, 2], [1, 0]]),
            legend=None),
        tooltip=["Workers:O", "Cost:N", alt.Tooltip("dollars:Q", format="$,.2f")])
    st.altair_chart(C.finish(ch, 280), width="stretch")
    if theta > 0:
        st.caption("With give-ups, the line can't grow without limit, so the model "
                   "answers even when the crew is overloaded (Erlang A, changelog C-006). "
                   "The plain model refuses those rows.")
