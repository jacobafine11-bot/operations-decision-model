import json

import streamlit as st

import core

st.title("Operations Decision Model")
st.markdown(
    "A decision tool for **small distribution and production operations** "
    "(roughly 2 to 30 workers). Describe how work flows through the building, "
    "and the model prices the whole operation in dollars, finds the "
    "bottleneck, and ranks which changes are worth making, including when a "
    "change in strategy beats buying automation.")
st.caption("Jacob Fine · Mathematics Research, Ms. Badalian · Jericho High School")

rec = core.latest_run_record()
qna = core.RESULTS / "qna_heldout.json"
qna_ok = json.loads(qna.read_text())["passed"] if qna.exists() else None

c1, c2, c3, c4 = st.columns(4)
if rec:
    c1.metric("Verification checks", f"{rec['checks_total'] - rec['checks_failed']} / {rec['checks_total']}",
              help=f"Last run {rec['generated_utc']} (code revision {rec['code_revision']})")
c2.metric("Held-out check, serial lines", "Passed" if qna_ok else "Not run",
          help="C-009: wait error 24.3% → 5.9% on four configurations the model never saw")
c3.metric("Real-data blind test", "Failed, 1 of 6",
          help="417,149 real calls. Recorded, not tuned away. See the Real-data test page.")
c4.metric("Data scale tested (≈5 s)", "5M rows",
          help="pipeline/scale_test.py: 5,000,000 order events processed in about 5 seconds; "
               "rates recovered within 0.12%")

st.subheader("Where the model stands")
st.markdown("""
| Part | Checked against simulation | Checked against real data |
|---|---|---|
| Waiting lines: stations, crews, lines of stations, callers who give up | Exactly verified (TOST equivalence at ±5%, pre-registered) | **First blind test failed** on a real call center: about 2× too pessimistic, because real *effective* capacity is hard to measure from records |
| Variability passed down a line of stations (C-009) | Held-out check passed: error 24% → 6% | Not yet |
| Inventory (best stock level) | Verified against 1M-draw brute force | Not yet |
| Decisions (value of a change, best plan) | Behavior tested; mock company: promised savings inside the realized 95% CI | Not yet |

**Bottom line:** the math is proven. Turning a real company's records
into correct inputs is the open problem, and the real-data test is what
showed it. The model is not yet ready to make a real company's decision
on its own.
""")

st.subheader("How to use this program")
a, b, c = st.columns(3)
with a:
    st.markdown("**Try it**")
    st.page_link("views/workbench.py", label="Model workbench", icon=":material/tune:")
    st.caption("Describe an operation, see the bottleneck and dollars, rank changes, size a crew.")
    st.page_link("views/mock.py", label="Mock company walkthrough", icon=":material/warehouse:")
    st.caption("A fictional distributor, start to finish: data, checks, estimates, decision, and whether the decision delivered.")
with b:
    st.markdown("**See the proof**")
    st.page_link("views/sim_lab.py", label="Simulation lab", icon=":material/science:")
    st.caption("Run the simulations yourself and watch them converge to the equations.")
    st.page_link("views/stats_lab.py", label="Statistics lab", icon=":material/functions:")
    st.caption("How equivalence testing works, and input checks on real data.")
    st.page_link("views/verification.py", label="Verification suite", icon=":material/verified:")
    st.caption("Run all checks now and read every result.")
with c:
    st.markdown("**See the history**")
    st.page_link("views/journal.py", label="Fine-tuning journal", icon=":material/history_edu:")
    st.caption("Every change to the model: what we saw, why, what we changed, and the evidence. Each one has a live demo.")
    st.page_link("views/real_data.py", label="Real-data test", icon=":material/fact_check:")
    st.caption("The pre-registered blind test on 417,149 real calls, and why it failed.")

with st.expander("The rules this project runs by"):
    st.markdown("""
1. **Every equation is checked three independent ways:** against textbook values,
   against a second algorithm, and against a simulation that shares no code with the model.
2. **Pass/fail rules come first.** Every test on new data is written down and committed to
   git before any result is seen. The commit timestamps are the proof.
3. **Changes need a mechanism.** An equation changes only for a reason that can be explained
   from how the operation works, never to make a number match. Every change is logged with
   the test that triggered it.
4. **Failures stay on the record.** A failed test is reported, diagnosed, and never re-run
   on the same data as if it were still blind.
5. **The model refuses rather than guesses.** Impossible inputs (an overloaded station with
   no one giving up) stop with an explanation instead of returning a number.
""")
