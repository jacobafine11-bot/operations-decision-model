"""
core.py — shared plumbing for every portal page: import paths, project
paths, cached simulation runners, and small formatting helpers.

Pages import this first:  import core
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("model", "simulation", "schema", "pipeline", "analysis", "portal"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402

import des as D  # noqa: E402,F401
import opsmodel as M  # noqa: E402,F401
import stats as ST  # noqa: E402,F401
from guardrails import ModelError  # noqa: E402,F401

DOCS = ROOT / "docs"
RESULTS = ROOT / "results"


# ---------------------------------------------------------------- formatting

def secs(hours: float) -> str:
    """Hours -> readable duration."""
    s = hours * 3600
    if s < 90:
        return f"{s:.1f} s"
    if s < 5400:
        return f"{s/60:.1f} min"
    return f"{hours:.2f} h"


def money(x: float) -> str:
    if x != x:  # NaN
        return "n/a"
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def latest_run_record() -> dict | None:
    recs = sorted(RESULTS.glob("run_record_*.json"))
    return json.loads(recs[-1].read_text()) if recs else None


def all_run_records() -> list[dict]:
    out = []
    for p in sorted(RESULTS.glob("run_record_*.json")):
        r = json.loads(p.read_text())
        r["file"] = p.name
        out.append(r)
    return out


def read_doc(name: str) -> str:
    p = DOCS / name
    return p.read_text() if p.exists() else f"*{name} not found*"


# ---------------------------------------------------------------- cached sims

@st.cache_data(show_spinner=False, max_entries=64)
def cached_trace_mmc(lam, mu, c, n, seed, cv):
    return D.trace_mmc(lam, mu, c, n, seed, cv)


@st.cache_data(show_spinner=False, max_entries=64)
def cached_trace_abandon(lam, mu, c, theta, n, seed):
    return D.trace_mmc_abandon(lam, mu, c, theta, n, seed)


def batch_estimate(x: np.ndarray, batches: int) -> D.Estimate:
    return D.batch_means(np.asarray(x), batches=batches)


def tost_from_estimate(est: D.Estimate, batches: int, target: float,
                       margin_rel: float, alpha: float = 0.05):
    se = est.half_width / D.t975(batches - 1)
    return ST.tost_one_sample(est.mean, max(se, 1e-300), batches - 1, target,
                              margin_rel * abs(target), alpha)
