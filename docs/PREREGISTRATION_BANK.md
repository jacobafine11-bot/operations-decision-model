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
