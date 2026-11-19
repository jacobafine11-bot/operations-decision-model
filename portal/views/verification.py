import subprocess
import sys

import pandas as pd
import streamlit as st

import core

st.title("Verification suite")
st.markdown("Every equation is checked **three independent ways**: against textbook values, "
            "against a second algorithm, and against a simulation that shares no code with "
            "the model. Before that, the statistical tests themselves are checked. You can "
            "run the whole suite now; it takes about 10 seconds.")

if st.button("Run all checks now", type="primary"):
    with st.spinner("Running the verification suite..."):
        p = subprocess.run([sys.executable, str(core.ROOT / "tests" / "run_verification.py")],
                           cwd=core.ROOT, capture_output=True, text=True, timeout=600)
    (st.success if p.returncode == 0 else st.error)(p.stdout.strip().splitlines()[0] if p.stdout else p.stderr[-500:])

recs = core.all_run_records()
if recs:
    st.subheader("Run history")
    st.dataframe(pd.DataFrame([{"When (UTC)": r["generated_utc"], "Code revision": r["code_revision"],
                                "Passed": f"{r['checks_total'] - r['checks_failed']} / {r['checks_total']}",
                                "Seconds": r.get("wall_time_s"), "Python": r.get("python")}
                               for r in reversed(recs)]), hide_index=True, width="stretch")
    st.caption("Every run writes a record (date, code version, package versions) to results/, "
               "so any number in the paper can be traced to a reproducible run.")

st.subheader("Latest full report")
rep = core.read_doc("VERIFICATION_REPORT.md")
parts = rep.split("\n### ")
st.markdown(parts[0])
for sec in parts[1:]:
    title, _, body = sec.partition("\n")
    with st.expander(title, expanded=title.startswith("Layer 3a")):
        st.markdown(body)
