"""
app.py — the Operations Decision Model program.

Run locally:   streamlit run portal/app.py
Deploy free:   Streamlit Community Cloud, pointed at this repository,
               main file portal/app.py.

Every page is a thin display layer. All numbers come from the verified
model (model/), the independent simulators (simulation/), the
statistical tests (model/stats.py), and stored results (results/).
"""

from __future__ import annotations

import streamlit as st

import core  # noqa: F401  (import paths)

st.set_page_config(page_title="Operations Decision Model", page_icon="📦",
                   layout="wide", initial_sidebar_state="expanded")

pages = {
    "Start here": [
        st.Page("views/home.py", title="Overview", icon=":material/home:", default=True),
    ],
    "Use the model": [
        st.Page("views/workbench.py", title="Model workbench", icon=":material/tune:"),
        st.Page("views/mock.py", title="Mock company walkthrough", icon=":material/warehouse:"),
    ],
    "How we know it works": [
        st.Page("views/sim_lab.py", title="Simulation lab", icon=":material/science:"),
        st.Page("views/stats_lab.py", title="Statistics lab", icon=":material/functions:"),
        st.Page("views/journal.py", title="Fine-tuning journal", icon=":material/history_edu:"),
        st.Page("views/real_data.py", title="Real-data test", icon=":material/fact_check:"),
        st.Page("views/verification.py", title="Verification suite", icon=":material/verified:"),
    ],
    "Data and documents": [
        st.Page("views/pipeline.py", title="Data pipeline", icon=":material/database:"),
        st.Page("views/docs.py", title="Documents", icon=":material/description:"),
    ],
}
st.navigation(pages).run()
