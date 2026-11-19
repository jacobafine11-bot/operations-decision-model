import json
import subprocess

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats as sp

import charts as C
import core

st.title("Real-data test: Anonymous Bank call center (1999)")
st.error("**Verdict: FAILED, 1 of 6 pre-registered criteria.** The model answered for 97% "
         "of real hours, but predicted about twice the real waiting and twice the real "
         "hang-ups, and ranked busy versus quiet hours poorly. Recorded as a failure, not "
         "tuned away.", icon=":material/cancel:")

st.markdown("""
**What was tested.** 417,149 real calls to an Israeli bank's call center (Technion SEE Center
data). Each busy weekday hour is one test case: the model gets that hour's measured arrival
rate, call lengths, available agents, and hang-up rate, and predicts how long callers waited
and how many gave up. Then the predictions are compared with what really happened.
""")

# ---------------------------------------------------------------- timeline
st.subheader("Rules first, results second: the git record")
try:
    log = subprocess.run(["git", "log", "--format=%h|%ad|%s", "--date=iso"], cwd=core.ROOT,
                         capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
except Exception:
    log = []
if not log:
    log = [l for l in core.read_doc("GIT_HISTORY.txt").splitlines() if l and not l.startswith("#")]
    log = ["|".join([l[:7], l[9:34], l[36:]]) for l in log]
keep = [l.split("|", 2) for l in log
        if any(k in l for k in ("Anonymous Bank", "amendment 1", "Phase 1", "Holdout", "Erlang A (abandonment)"))]
tl = pd.DataFrame(keep, columns=["Commit", "Time (UTC)", "What was committed"]).iloc[::-1]
st.dataframe(tl, hide_index=True, width="stretch")
st.caption("Each row is a commit on GitHub. The pass/fail rules (first row) and the amendment "
           "were committed before the frozen choice, which was committed before any holdout "
           "result existed.")

# ---------------------------------------------------------------- scorecard (recomputed)
frz = json.loads((core.RESULTS / "bank_frozen_choice.json").read_text())
w = pd.read_csv(core.RESULTS / "bank_holdout_windows.csv")
v = w.dropna(subset=["pred_wq_s"])
ratio = (v["pred_wq_s"] + 1) / (v["obs_wq_s"] + 1)
s1 = sp.spearmanr(v["pred_wq_s"], v["obs_wq_s"]).statistic
s2 = ratio.median()
s3 = (v["n"] * v["pred_wq_s"]).sum() / (v["n"] * v["obs_wq_s"]).sum() - 1
pab_p = (v["n"] * v["pred_pab"]).sum() / v["n"].sum()
pab_o = v["abandoned"].sum() / v["n"].sum()
s5 = w["pred_wq_s"].notna().mean()
s6 = ((w["pred_wq_s_pooledtheta"] + 1) / (w["obs_wq_s"] + 1)).median()
card = pd.DataFrame([
    ("S1", "Ranks busy vs quiet hours (rank correlation)", f"{s1:.2f}", "≥ 0.70", s1 >= 0.7),
    ("S2", "Typical hour: predicted ÷ actual wait", f"{s2:.2f}", "0.67 to 1.50", 0.67 <= s2 <= 1.5),
    ("S3", "All hours: total predicted vs actual waiting", f"{s3:+.0%}", "within ±25%", abs(s3) <= .25),
    ("S4", "Share of callers who hung up", f"{pab_p:.1%} vs {pab_o:.1%}", "within ±25%", abs(pab_p / pab_o - 1) <= .25),
    ("S5", "Hours the model could answer", f"{s5:.1%}", "≥ 95%", s5 >= .95),
    ("S6", "S2 again, hang-up rate from other months", f"{s6:.2f}", "0.67 to 1.50", 0.67 <= s6 <= 1.5),
], columns=["ID", "Criterion", "Result", "Pass if", "ok"])
card["Verdict"] = np.where(card["ok"], "PASS", "FAIL")
st.subheader(f"Blind holdout scorecard (July to December, {len(w):,} hours)")
st.dataframe(card.drop(columns="ok"), hide_index=True, width="stretch")
st.caption(f"Recomputed live from results/bank_holdout_windows.csv. Frozen model: "
           f"{frz['variant']} (Erlang A, callers who give up) with {frz['rule']} (effective agents), "
           f"chosen on January to June only.")

# ---------------------------------------------------------------- charts
l, r = st.columns(2)
with l:
    st.markdown("**Every hour: predicted vs actual average wait**")
    d = v.assign(pred=v["pred_wq_s"] + 1, obs=v["obs_wq_s"] + 1)
    st.altair_chart(C.pred_vs_obs(d, "obs", "pred", "Actual wait + 1 s (log)", "Predicted wait + 1 s (log)",
                                  [alt.Tooltip("win:N", title="hour")]), width="stretch")
    st.caption("Dashed: perfect prediction. Gray band: within ±50%. Most hours sit above the "
               "line: the model is too pessimistic.")
with r:
    st.markdown("**By hour of day**")
    bh = v.groupby("hour").apply(lambda g: pd.Series({
        "Model": (g["n"] * g["pred_wq_s"]).sum() / g["n"].sum(),
        "Real data": (g["n"] * g["obs_wq_s"]).sum() / g["n"].sum()}), include_groups=False).reset_index()
    long = bh.melt(id_vars="hour", var_name="Series", value_name="wait")
    st.altair_chart(C.lines(long, "hour", "wait", "Series", "Hour of day", "Average wait (seconds)"),
                    width="stretch")
    st.caption("The model gets the daily shape roughly right but runs about twice too high "
               "all day, which points to a systematic input problem, not random noise.")

# ---------------------------------------------------------------- learning
st.subheader("Why it failed, and what's next")
st.markdown("""
1. **Headcount is not capacity.** In the first half, counting every agent who answered a call
   made the model wrong by a factor of about 18. Agents were available for incoming calls only
   about 38% of the time. Measuring *effective* agents (busy while callers wait) cut the error
   to about 2× (changelog C-007).
2. **The bias was visible before the blind test.** The model was chosen by the size of its
   errors, not their direction, so a model that was always too high still won. Next time the
   selection score must punish bias, like the scorecard does (C-008).
3. **Leading explanation:** lines form exactly when fewer agents are free, so counting busy
   agents during waits samples the worst moments of the hour and understates capacity.

**Round 2:** a capacity measure free of that effect, a selection score that matches the
scorecard, and a fresh blind dataset. July to December is retired as a blind set.

**What this means:** the queueing equations are proven against simulation. What failed is
turning a real company's records into the right inputs, which is exactly the gap for small
operations that plan by headcount.
""")
with st.expander("The pre-registration, as committed"):
    st.markdown(core.read_doc("PREREGISTRATION_BANK.md"))
with st.expander("The generated report"):
    st.markdown(core.read_doc("REAL_DATA_VALIDATION.md"))
