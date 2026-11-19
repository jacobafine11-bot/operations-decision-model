import json

import streamlit as st

import core

st.title("Operations Decision Model")
st.markdown(
    "A decision tool for **small distribution and production operations**. Describe how "
    "work flows through the building, and the model prices the whole operation in "
    "dollars, finds the bottleneck, ranks which changes are worth making (including when "
    "a change in strategy beats buying automation), and says how sure it is.")
st.caption("Jacob Fine · Mathematics Research, Ms. Badalian · Jericho High School")


def _load(name):
    p = core.RESULTS / name
    return json.loads(p.read_text()) if p.exists() else None


rec = core.latest_run_record()
hard, sealed, cov2 = _load("benchmark_hard_sealed.json"), _load("benchmark_sealed.json"), _load("coverage2.json")
c1, c2, c3, c4 = st.columns(4)
if rec:
    c1.metric("Verification checks", f"{rec['checks_total'] - rec['checks_failed']} / {rec['checks_total']}",
              help=f"Last run {rec['generated_utc']} (code revision {rec['code_revision']})")
if hard and sealed:
    rows = hard["rows"] + sealed["rows"]
    ex = sum(r["pick"] == r["best_true"] for r in rows if not r.get("refused"))
    c2.metric("Best plan chosen, unseen companies", f"{ex} / {len(rows)}",
              help="Sealed benchmark: 80 made-up companies of 2 to 250 workers, run once")
if cov2:
    c3.metric("90% ranges that held", f"{cov2['pooled']['c1']:.0%}",
              help="Coverage round 2 on 80 fresh companies: station-wait ranges containing the truth")
c4.metric("Real warehouse, 90% service target", "90.6% delivered",
          help="Real-data round 2: 140 real products, 19 weeks the model never saw")

st.subheader("Where the model stands")
st.markdown("""
| Part | Against simulation | Against made-up companies (160, sealed) | Against real data |
|---|---|---|---|
| Waiting lines (stations, crews, lines, give-ups) | Exactly verified (TOST ±5%, pre-registered) | Time through the line within 0.4% to 1.3% (median) | Call center **failed 1/6**: real effective capacity was hard to measure |
| Uncertainty ranges | Exact limits checked | Hold 89% of the time (target 90%) | Not yet |
| Decisions (value of a change, best plan) | Behavior tested | **Exact best plan 78/80**; rule of thumb near-best only 31/80 | Not yet |
| Inventory (best stock level) | Verified vs brute force | Not part of the benchmark | Real warehouse: **90.6%** at a 90% target, 92.9% at 95%; overstocks at 80% (skewed demand) |
| Flow and routing | Exactly verified | Part of every company | Real factory: **right bottleneck**; workload test flawed by data cutoff |

**Bottom line:** on operations that follow its assumptions, the model is accurate and its
advice is nearly perfect at every size tested. Real data has shown where those assumptions
break: work released in **waves**, **skewed** demand, and **effective capacity** that differs
from headcount. Those are the next things to build, each to be proven on fresh data.
""")

st.subheader("How to use this program")
a, b, c = st.columns(3)
with a:
    st.markdown("**Try it**")
    st.page_link("views/workbench.py", label="Model workbench", icon=":material/tune:")
    st.caption("Describe an operation: bottleneck, dollars, ranked changes, 90% ranges, crew size.")
    st.page_link("views/mock.py", label="Mock company walkthrough", icon=":material/warehouse:")
    st.caption("A fictional distributor from raw history to a checked decision.")
with b:
    st.markdown("**See the proof**")
    st.page_link("views/benchmark.py", label="Benchmark (160 companies)", icon=":material/leaderboard:")
    st.caption("2 to 250 workers, sealed tests, skill vs a rule of thumb, uncertainty coverage.")
    st.page_link("views/sim_lab.py", label="Simulation lab", icon=":material/science:")
    st.caption("Run the simulations yourself.")
    st.page_link("views/stats_lab.py", label="Statistics lab", icon=":material/functions:")
    st.caption("How equivalence testing works; input checks on real data.")
with c:
    st.markdown("**See the history**")
    st.page_link("views/journal.py", label="Fine-tuning journal", icon=":material/history_edu:")
    st.caption("Every change: what we saw, why, what changed, the evidence. Live demos.")
    st.page_link("views/real_data.py", label="Real-data tests", icon=":material/fact_check:")
    st.caption("Call center, warehouse, factory: pre-registered, run once, reported as is.")
    st.page_link("views/verification.py", label="Verification suite", icon=":material/verified:")
    st.caption("Run every check now.")

with st.expander("The rules this project runs by"):
    st.markdown("""
1. **Every equation is checked three independent ways:** against textbook values, against a
   second algorithm, and against a simulation that shares no code with the model.
2. **Pass/fail rules come first.** Every test on new data or new companies is written down and
   committed to git before any result exists. The commit timestamps are the proof.
3. **Fix on development data, prove on sealed data.** A fix is never judged on the cases that
   inspired it.
4. **Changes need a mechanism.** An equation changes only for a reason that can be explained
   from how the operation works, never to make a number match.
5. **Failures stay on the record.** A failed test is reported, diagnosed, and never re-run on
   the same data as if it were still blind.
6. **The model refuses rather than guesses,** and says how sure it is when it does answer.
""")
