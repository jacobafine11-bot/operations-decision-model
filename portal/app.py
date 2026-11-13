"""
app.py — the Operations Decision Model portal (Streamlit).

Run locally:   streamlit run portal/app.py
Deploy free:   push the repo to GitHub, connect it at
               share.streamlit.io (Streamlit Community Cloud).

Design rule: this file only displays. Every number comes from
portal/logic.py, which calls the verified model (model/opsmodel.py,
65/65 checks, docs/VERIFICATION_REPORT.md).
"""

from __future__ import annotations

import streamlit as st

import logic as L

st.set_page_config(page_title="Operations Decision Model",
                   page_icon="📦", layout="wide")

st.title("Operations Decision Model")
st.caption(
    "Describe a small distribution or production operation, and the model "
    "prices it in dollars, finds the bottleneck, and ranks which changes are "
    "worth making. Every formula behind this page is verified against "
    "independent simulation (see the Verification tab).")

tab_op, tab_decide, tab_verify = st.tabs(
    ["1 · Your operation", "2 · Decide on changes", "3 · Verification"])

# ---------------------------------------------------------------- tab 1
with tab_op:
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Stations, in flow order")
        stations_df = st.data_editor(
            L.DEFAULTS["stations"], num_rows="dynamic", width="stretch",
            key="stations")
        st.caption(
            "Service variability (cv) is how uneven the work times are: "
            "1.0 if unmeasured, lower if work is steady, higher if erratic. "
            "The pipeline measures it from timestamps when you have data.")
    with right:
        st.subheader("Demand and costs")
        arrival = st.number_input("Orders arriving per hour", 0.1, 10_000.0,
                                  L.DEFAULTS["arrival_rate"], 0.5)
        margin = st.number_input("Margin per shipped order ($)", 0.0, 10_000.0,
                                 L.DEFAULTS["margin"], 0.5)
        waiting = st.number_input("Cost of one order waiting one hour ($)",
                                  0.0, 1_000.0, L.DEFAULTS["waiting_cost"], 0.5)
        overhead = st.number_input("Staff + equipment overhead ($/hour)",
                                   0.0, 100_000.0, L.DEFAULTS["overhead"], 5.0)
        hours = st.number_input("Operating hours per year", 1.0, 8784.0,
                                L.DEFAULTS["hours_per_year"], 50.0)

    try:
        op = L.build_operation(stations_df, arrival, margin, waiting,
                               overhead, hours)
        table, bottleneck = L.station_table(op)
        st.subheader("How the operation runs today")
        st.dataframe(table, width="stretch", hide_index=True)
        st.info(f"**Bottleneck: {bottleneck}.** Improving any other station "
                "barely moves the totals until this one is addressed.")
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
        st.caption(
            "A change edits the operation: faster equipment or re-slotting "
            "speeds a station up; hiring adds a worker. The model re-prices "
            "the whole operation with each combination and subtracts what "
            "the change costs.")
        import pandas as pd
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
            default_changes, num_rows="dynamic", width="stretch",
            key="changes",
            column_config={
                "Station": st.column_config.SelectboxColumn(options=names),
                "Type": st.column_config.SelectboxColumn(
                    options=["Speed up station by %", "Add workers"]),
            })
        budget = st.number_input("Budget for one-time costs ($)", 0.0,
                                 10_000_000.0, 100_000.0, 1000.0)
        try:
            changes = L.build_changes(changes_df, names)
            if changes:
                st.subheader("Every affordable plan, ranked")
                st.dataframe(L.plan_table(op, changes, budget),
                             width="stretch", hide_index=True)
                st.caption(
                    "Value = yearly profit gain minus the change's annualized "
                    "cost. 'Do nothing' is always a candidate, so a losing "
                    "plan never wins. Combinations are priced together "
                    "because fixing one bottleneck moves it elsewhere.")
                if len(changes) >= 2:
                    flip = L.waiting_cost_flip(op, [changes[0]], [changes[1]])
                    if flip is not None:
                        st.info(
                            f"**Honesty check:** the ranking between "
                            f"'{changes[0].name}' and '{changes[1].name}' "
                            f"flips when the cost of a waiting order crosses "
                            f"**${flip:,.2f}/order-hour** (you entered "
                            f"${op.waiting_cost:,.2f}). If the real value is "
                            f"near that line, measure it before deciding.")
        except L.ModelError as e:
            st.error(f"The model stopped instead of guessing: {e}")

# ---------------------------------------------------------------- tab 3
with tab_verify:
    st.subheader("Why these numbers can be trusted")
    st.markdown(
        "- **65/65 verification checks pass**, across four layers: the "
        "statistical tests themselves, textbook closed forms, independent "
        "second computations, and discrete-event simulation that shares no "
        "code with the model.\n"
        "- Exact formulas are judged by **TOST equivalence tests** at a "
        "pre-registered ±5% margin with the p-value on record; "
        "approximations are labeled and held to stated tolerances.\n"
        "- Every run writes a **run record** (date, code revision, seeds, "
        "package versions) so any number traces to a reproducible run.\n"
        "- Invalid inputs **stop with an explanation** instead of returning "
        "numbers (an overloaded station has no steady state to report).\n\n"
        "Full detail: `docs/VERIFICATION_REPORT.md`, "
        "`docs/SIMULATION_METHODS.md`, `docs/STATS_STUDY.md`, "
        "`docs/CHANGELOG.md` in the repository.")
