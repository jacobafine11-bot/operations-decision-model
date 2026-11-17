# Pre-registration: real-data blind test of the queue layer

**Written and committed before any model prediction was compared with the
real waiting times.** The git commit containing this file predates the
commit containing any results; that ordering is the evidence that the
pass/fail rules were not tuned to the outcome.

## Data

"Anonymous Bank" call center, Israel, every call from 1 Jan to 31 Dec 1999
(444,448 records; Technion SEE Center, Mandelbaum et al.). Each record has
queue entry and exit, service start and end, outcome (served, hung up,
phantom), and agent name. Raw data is not redistributed in this repository;
`adapters/anonymous_bank.py` documents how to obtain it and converts it to
the standard `queue_events` table.

Facts seen during exploration (before this document, no model run):
15.3% of queued callers abandon; served-call mean service 191 s with
cv 1.48; about 8 distinct agents per busy hour.

## Unit of analysis

A **window** is one clock hour on one date. Included windows:
weekdays of the Israeli work week (Sunday to Thursday), hours 08:00 to
21:59, at least 30 agent-seeking arrivals, at least 2 agents.

## Inputs measured per window (never the outcome)

- λ: agent-seeking arrivals per hour (queued callers plus callers served
  without queueing; phantoms excluded).
- E[S], cv: mean and coefficient of variation of service time of calls
  served in the window.
- c: agents on duty (two candidate counting rules, below).
- θ: abandonment rate, by the censored-exponential maximum likelihood
  estimate θ̂ = (number abandoned) / (total seconds spent waiting by all
  queued callers). Note: θ̂ uses the waiting times, so it is an input
  measured from the queue; this is disclosed, and the scorecard therefore
  includes a test (S6) where θ is NOT taken from the same window.

## Outcomes per window (never used as inputs, except as disclosed for θ)

- Observed mean time in queue over all agent-seeking arrivals
  (zero for callers served immediately; abandoners count their time
  until hanging up). This is exactly what Little's law gives as Lq/λ.
- Observed abandonment fraction.

## Candidate model variants (selection on calibration half only)

| Variant | Model |
|---|---|
| V1 | Erlang C (M/M/c), exponential service |
| V2 | Erlang C with the measured-cv correction (current model default) |
| V3 | Erlang A (M/M/c+M): abandonment with rate θ, exponential service |

| Agent-count rule | Definition |
|---|---|
| C1 | distinct agents who served at least one call in the window |
| C2 | sum over agents of the fraction of the window between that agent's first service start and last service end that day (presence-weighted), rounded to the nearest whole agent, minimum 1 |

## Procedure

1. Calibration half: January to June. Every variant × rule is scored; the
   single combination with the best calibration score is frozen. Score for
   selection = median absolute log ratio of predicted to observed mean
   queue time across windows (lower is better), with refusals counted as
   the worst possible ratio.
2. Holdout half: July to December. The frozen combination is run once.
   No change to rules, thresholds, or code paths after seeing holdout
   results; any later change is a new CHANGELOG entry and a new test.

## Scorecard (holdout, frozen combination)

| ID | Criterion | Pass if |
|---|---|---|
| S1 | Rank: Spearman correlation, predicted vs observed mean queue time across windows | ≥ 0.70 |
| S2 | Calibration: median of predicted / observed mean queue time | between 0.67 and 1.50 |
| S3 | Aggregate: total predicted queue-hours vs total observed, all windows | within ±25% |
| S4 | Abandonment: predicted vs observed overall abandonment fraction | within ±25% relative |
| S5 | Coverage: windows where the model returns a valid prediction | ≥ 95% |
| S6 | Out-of-window θ: rerun S2 with θ taken as the calibration-half pooled value instead of per-window | between 0.67 and 1.50 |

Why the margins are wider than the ±5% used against simulation: a real
hour is not a steady-state queue (arrival rate drifts within the hour,
agents take breaks, c is a proxy), so a structurally correct model is
expected to show window-level scatter. The tests are set so that a model
that is right in rank and in level passes, and a model that is
systematically biased by more than about 50% in a typical hour, or 25%
in aggregate, fails.

Reported but not gated: TOST equivalence of the mean log ratio within
±log(1.25), by-hour-of-day table, by-load table.

---

## Amendment 1 (2026-11-17), committed before any holdout result

**What happened.** Phase 1 (calibration half only) scored all six
variant × rule combinations. Every one was off by a typical factor of
about 18 (median absolute log ratio 2.9 to 3.3). Diagnosis, on calibration
data only: the median window has 11 distinct agents (C1) but an offered
load of only 5.2 agent-equivalents, so the model sees 47% utilization and
predicts sub-second waits, while callers actually waited 49 s on average
and 12% abandoned. Agents counted as on duty were not available to answer
much of the time (after-call work that is not in the recorded service
time, outbound work, breaks, skill restrictions by call type).
**Headcount is not capacity.** Because every equation variant failed the
same way, the fault is in the capacity input, not the queueing formulas.

**Holdout status.** The July to December half has not been scored by any
code. The frozen choice from Phase 1 is void and the phase is rerun under
this amendment.

**Two added agent-count rules.**

| Rule | Definition | Role |
|---|---|---|
| C3 | Effective agents: the time-average number of agents busy with calls during the moments in the window when at least one caller is waiting, rounded to the nearest whole agent (minimum 1). If no one waited in the window, fall back to C1. | Structural test. Rationale: when a caller is waiting, every agent who is actually available is serving, so busy agents during waiting periods measure true staffing. Disclosure: it uses the timeline of when the queue was non-empty (not wait lengths). |
| C4 | Staffing-plan estimate: the median C3 for the same weekday and hour over the 4 most recent prior weeks that have one; if none exist, fall back to C1. | Predictive test: uses nothing from the window being predicted, which is what a manager would actually have. |

**Procedure (unchanged otherwise).** Rerun Phase 1 on January to June
with variants V1 to V3 × rules C1 to C4, freeze the best by the same
selection score, run the holdout once. Scorecard S1 to S6 unchanged. In
addition, whichever variant is frozen is also scored on the holdout with
C4 and that result is reported under the same S1 to S6 criteria, since
C4 is the forecast a business could act on.
