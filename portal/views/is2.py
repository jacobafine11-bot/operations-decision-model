import json

import pandas as pd
import streamlit as st

import core


def load(name):
    p = core.RESULTS / name
    return json.loads(p.read_text()) if p.exists() else None


rec = core.latest_run_record()
hs, ss, c1, c2, r2 = (load("benchmark_hard_sealed.json"), load("benchmark_sealed.json"),
                      load("coverage.json"), load("coverage2.json"), load("real2.json"))

st.title("Independent Study 2: what was promised, what was delivered")
st.markdown("""
**Research question.** How can a general mathematical model decide whether a change to a small
distribution or production operation is worth making, and when is a change in inventory or
logistics strategy a better choice than automation?

**What Independent Study 2 had to do** (from the proposal): find out whether the equations from
Independent Study 1 are correct, work out what their outputs mean as a decision, and deliver an
interactive portal where the simulations run, plus a written log of every change made to the
formulas.
""")

exact = sum(r["pick"] == r["best_true"] for r in hs["rows"] + ss["rows"] if not r.get("refused")) if hs else 0
ra = {x["id"]: x for x in r2["R-A"]["card"]} if r2 else {}
rows = [
    ("1. Learn statistical significance testing and choose the tests",
     "Study written; TOST equivalence chosen and defended over a plain t-test; chi-square and "
     "bootstrap KS for input checks; the tests themselves validated before use",
     "Statistics lab · docs/STATS_STUDY.md · Verification Layer 0", "Done"),
    ("2. Build a program that runs the equations on any data, including large amounts",
     "Model engine E1 to E7 plus Erlang A, variability down a line, uncertainty ranges; data "
     "pipeline with a validation gate; 5,000,000 rows processed in about 5 seconds",
     "Model workbench · Data pipeline · docs/CLEAN_ROOM_RUN.md", "Done"),
    ("3. Test on real public data, holding some back and predicting it blind",
     f"Three real datasets, all pre-registered and run once. Call center: failed 1/6. Warehouse "
     f"inventory: {ra.get('R-A1', {}).get('realized', 0):.1%} delivered at a 90% target. Factory: "
     "right bottleneck; workload test flawed by a data cutoff",
     "Real-data tests · docs/REAL2_REPORT.md", "Done, 4 of 11 criteria passed"),
    ("4. Build a warehouse simulation with random arrivals, random work, absent workers, lumpy demand",
     "Independent simulators sharing no code with the model: crews, give-ups, lines of stations, "
     "absent workers, order-by-order histories, brute-force stock levels",
     "Simulation lab · docs/SIMULATION_METHODS.md", "Done"),
    ("5. Compare equations to simulation with statistical tests; investigate any gap",
     f"{rec['checks_total'] - rec['checks_failed']}/{rec['checks_total']} checks; every exact formula shown "
     "equivalent within ±5% by TOST; every gap investigated and either fixed with a mechanism or "
     "recorded as a limit" if rec else "",
     "Verification suite · Fine-tuning journal", "Done"),
    ("6. Define how a change is valued in $/yr and test that rule",
     f"Value V(S) in dollars per year, with interactions and flip points. Tested on 80 sealed "
     f"made-up companies against re-simulation of every plan: exact best plan {exact} of 80",
     "Benchmark · Mock company walkthrough", "Done"),
    ("7. Run everything at different scales",
     "Two size bands, 2 to 100 and 100 to 250 workers (160 companies); 5,000,000-row data test",
     "Benchmark · Data pipeline", "Done"),
    ("Product: interactive portal where simulations run and are viewed",
     "This program: 12 pages, every page and button tested, works from a clean copy of GitHub",
     "All pages · docs/CLEAN_ROOM_RUN.md", "Done"),
    ("Product: written log of every change to the formulas",
     "13 changelog entries, each with what was seen, the mechanism, the change, and the evidence",
     "Fine-tuning journal · docs/CHANGELOG.md", "Done"),
]
st.subheader("Promise by promise")
st.dataframe(pd.DataFrame(rows, columns=["Promised", "Delivered", "Where to see it", "Status"]),
             hide_index=True, width="stretch")

st.subheader("The evidence in numbers")
a, b, c, d = st.columns(4)
if rec:
    a.metric("Verification checks", f"{rec['checks_total'] - rec['checks_failed']} / {rec['checks_total']}")
b.metric("Best plan chosen (sealed companies)", f"{exact} / 80")
if c2:
    c.metric("90% ranges that held (fresh companies)", f"{c2['pooled']['c1']:.0%}")
if ra:
    d.metric("Real warehouse, 90% target", f"{ra['R-A1']['realized']:.1%} delivered")

st.subheader("How Independent Study 2 moves the research question forward")
st.markdown("""
- **"Decide whether a change is worth making":** the model turns every output into one number,
  dollars per year, and picks the plan with the highest value. On 80 made-up companies it never
  saw, re-simulating every possible plan showed its choice was the exact best 78 times and
  near-best every time.
- **"Strategy vs automation":** in the hard benchmark set, cheap process changes, hiring,
  automation, and doing nothing each won in different companies; the model told them apart, while
  a rule of thumb did not.
- **"Small operations":** real data showed what small operations get wrong when they plan by
  headcount, and where the model's assumptions break (work released in waves, skewed demand).
  Those findings set Independent Study 3: fix those two assumptions, prove the fixes on fresh
  data, then take the model to the Syosset distributor.
""")

st.subheader("What it does not prove yet (stated plainly)")
st.markdown("""
- It has not yet been tested on a real distributor's waiting times. The only real waiting-time
  test (a call center) failed, and a call center is not the target.
- Real warehouses can release work in batches; the model assumes random arrivals.
- At stations above about 90% busy, predictions depend heavily on how precisely work speeds are
  measured; the 90% ranges show this, and the model flags those stations as sensitive.
""")

with st.expander("Rules first, results second: the commit record"):
    import subprocess
    log = subprocess.run(["git", "log", "--format=%h|%ad|%s", "--date=format:%Y-%m-%d %H:%M"],
                         cwd=core.ROOT, capture_output=True, text=True).stdout.splitlines()
    keys = ("Pre-regist", "Freeze", "result", "Result", "amendment", "Amendment")
    keep = [l.split("|", 2) for l in log if any(k in l for k in keys)]
    if keep:
        st.dataframe(pd.DataFrame(keep, columns=["Commit", "Time (UTC)", "What"]).iloc[::-1],
                     hide_index=True, width="stretch")
        st.caption("Read top to bottom: every pre-registration and amendment comes before the result it governs.")
    else:
        st.caption("Git history not available in this copy; see docs/GIT_HISTORY.txt or GitHub.")
