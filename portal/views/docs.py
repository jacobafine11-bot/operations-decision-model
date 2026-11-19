import streamlit as st

import core

st.title("Documents")
st.markdown("Everything written about the model, as it lives in the repository.")

DOCS = {
    "README": ("README.md", "What the project is, how it's organized, current status"),
    "Notation and assumptions": ("docs/NOTATION.md", "Every symbol, its units, and where it comes from"),
    "Statistics study": ("docs/STATS_STUDY.md", "Which tests, why, and the defense"),
    "Simulation methods": ("docs/SIMULATION_METHODS.md", "How and where every simulation runs"),
    "Changelog": ("docs/CHANGELOG.md", "Every change to the model, with mechanism and evidence"),
    "Verification report": ("docs/VERIFICATION_REPORT.md", "Generated: every check with its result"),
    "Pre-registration (bank test)": ("docs/PREREGISTRATION_BANK.md", "Rules written before results"),
    "Real-data report": ("docs/REAL_DATA_VALIDATION.md", "Generated: the blind test results"),
    "Pre-registration (benchmark)": ("docs/PREREGISTRATION_BENCHMARK.md", "160 companies: rules and both amendments"),
    "Pre-registration (round 2)": ("docs/PREREGISTRATION_REAL2.md", "Warehouse and factory: rules first"),
    "Round 2 report": ("docs/REAL2_REPORT.md", "Real warehouse and factory results"),
    "Public data sources": ("data/public/README.md", "Datasets included and not included"),
    "Commit history": ("docs/GIT_HISTORY.txt", "Plain-text copy of the git log"),
}
name = st.selectbox("Document", list(DOCS), format_func=lambda k: f"{k}: {DOCS[k][1]}")
path = core.ROOT / DOCS[name][0]
body = path.read_text() if path.exists() else "*Not found*"
st.caption(f"`{DOCS[name][0]}`")
if path.suffix == ".txt":
    st.code(body)
else:
    st.markdown(body)
st.download_button("Download this document", body, file_name=path.name)
