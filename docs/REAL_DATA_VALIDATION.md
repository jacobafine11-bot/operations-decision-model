# Real-Data Validation: Anonymous Bank Call Center (1999)

Generated 2026-11-17 17:09 UTC by `analysis/bank_validation.py holdout`. Rules: `docs/PREREGISTRATION_BANK.md`, committed before any prediction was compared with real data. Raw window-level results: `results/bank_holdout_windows.csv`.

## Verdict: FAILED (1 of 6 pre-registered criteria)

The frozen model covered 97% of real hours but predicted about twice the
real waiting and twice the real abandonment, and ranked busy versus quiet
hours poorly. Recorded as a failure and not tuned away; the July to
December half is retired as a blind set. Diagnosis and the round-2 plan
are in docs/CHANGELOG.md (C-007, C-008). What this does and does not
mean: the queueing equations are exactly verified against simulation
(76/76 checks); what failed is measuring a call center's effective
capacity from its records, which the equations take as an input.

## What was tested

417,149 real agent-seeking calls (Technion SEE Center, Anonymous Bank). Each busy weekday hour is one test case: the model receives that hour's measured arrival rate, service times, agent count, and abandonment rate, and predicts the average time callers spent waiting and the share who hung up. Those predictions are compared with what actually happened.

## Phase 1: model choice on January to June only

| Variant | Agent rule | Median abs log ratio (lower is better) | Refusal rate |
|---|---|---|---|
| V3: Erlang A (abandonment), exponential service | C3: effective agents (busy while callers wait) | 0.749 ◀ frozen | 3.1% |
| V3: Erlang A (abandonment), exponential service | C4: staffing plan (median effective agents, prior 4 weeks) | 0.775 | 1.7% |
| V2: Erlang C, measured-cv correction | C1: distinct agents serving in the hour | 2.896 | 4.7% |
| V3: Erlang A (abandonment), exponential service | C1: distinct agents serving in the hour | 2.921 | 0.0% |
| V1: Erlang C, exponential service | C1: distinct agents serving in the hour | 2.977 | 4.7% |
| V2: Erlang C, measured-cv correction | C2: presence-weighted agents | 3.204 | 2.4% |
| V1: Erlang C, exponential service | C2: presence-weighted agents | 3.233 | 2.4% |
| V3: Erlang A (abandonment), exponential service | C2: presence-weighted agents | 3.252 | 0.0% |
| V2: Erlang C, measured-cv correction | C4: staffing plan (median effective agents, prior 4 weeks) | inf | 66.8% |
| V2: Erlang C, measured-cv correction | C3: effective agents (busy while callers wait) | inf | 74.9% |
| V1: Erlang C, exponential service | C3: effective agents (busy while callers wait) | inf | 74.9% |
| V1: Erlang C, exponential service | C4: staffing plan (median effective agents, prior 4 weeks) | inf | 66.8% |

Frozen at 2026-11-17T17:09:10+00:00: **V3 (Erlang A (abandonment), exponential service) with C3 (effective agents (busy while callers wait))**. 1664 calibration windows.

## Phase 2: blind holdout, July to December (1783 windows), frozen choice run once

| ID | Criterion | Result | Pass if | Verdict |
|---|---|---|---|---|
| S1 | Spearman rank correlation, predicted vs observed queue time | 0.244 | ≥ 0.70 | FAIL |
| S2 | Median predicted / observed queue time | 1.957 | 0.67 to 1.50 | FAIL |
| S3 | Total predicted vs observed queue-hours | +121.4% | within ±25% | FAIL |
| S4 | Predicted vs observed abandonment fraction | 29.13% vs 15.33% (+90.0%) | within ±25% | FAIL |
| S5 | Coverage (model gives a valid answer) | 97.3% | ≥ 95% | PASS |
| S6 | Median ratio with out-of-window pooled θ | 1.787 | 0.67 to 1.50 | FAIL |

Reported, not gated: TOST equivalence of the mean log ratio within ±log(1.25), day-clustered (df = 130): mean ratio 2.497, p = 1, **not shown equivalent within ±25%**.

### Forecast version: V3 with C4 (staffing plan from prior weeks only)

Required by Amendment 1. Uses nothing from the hour being predicted except its arrivals and service times; agent capacity comes from the previous four weeks.

| ID | Criterion | Result | Pass if | Verdict |
|---|---|---|---|---|
| S1 | Spearman rank correlation, predicted vs observed queue time | 0.382 | ≥ 0.70 | FAIL |
| S2 | Median predicted / observed queue time | 2.163 | 0.67 to 1.50 | FAIL |
| S3 | Total predicted vs observed queue-hours | +131.2% | within ±25% | FAIL |
| S4 | Predicted vs observed abandonment fraction | 29.71% vs 15.26% (+94.7%) | within ±25% | FAIL |
| S5 | Coverage (model gives a valid answer) | 97.9% | ≥ 95% | PASS |
| S6 | Median ratio with out-of-window pooled θ | 2.045 | 0.67 to 1.50 | FAIL |

TOST (reported): mean ratio 2.478, p = 1.

### By hour of day (holdout)

|   hour |   windows |   obs wait (s) |   pred wait (s) |   obs abandon |   pred abandon |
|-------:|----------:|---------------:|----------------:|--------------:|---------------:|
|      8 |       124 |         31.132 |         121.966 |         0.101 |          0.316 |
|      9 |       128 |         71.08  |         139.898 |         0.172 |          0.309 |
|     10 |       127 |         81.253 |         132.065 |         0.201 |          0.297 |
|     11 |       126 |         65.091 |         137.332 |         0.161 |          0.274 |
|     12 |       125 |         49.743 |         118.38  |         0.131 |          0.267 |
|     13 |       126 |         53.786 |         126.915 |         0.131 |          0.28  |
|     14 |       123 |         60.47  |         244.66  |         0.147 |          0.27  |
|     15 |       128 |         97.222 |         154.949 |         0.216 |          0.306 |
|     16 |       127 |         58.44  |         105.959 |         0.171 |          0.295 |
|     17 |       126 |         57.4   |         133.189 |         0.161 |          0.314 |
|     18 |       122 |         52.197 |         147.355 |         0.156 |          0.31  |
|     19 |       115 |         36.948 |         122.814 |         0.108 |          0.295 |
|     20 |       116 |         31.254 |         162.207 |         0.072 |          0.262 |
|     21 |       121 |         42.604 |         179.388 |         0.099 |          0.278 |

### By load ρ = λE[S]/c (holdout)

| load band   |   windows |   obs wait (s) |   pred wait (s) |   median ratio |
|:------------|----------:|---------------:|----------------:|---------------:|
| <0.6        |        42 |         18.978 |           7.159 |          0.43  |
| 0.6-0.8     |       150 |         29.499 |          31.461 |          1.108 |
| 0.8-0.9     |       145 |         37.642 |          60.551 |          1.241 |
| 0.9-1.0     |       173 |         43.564 |         229.539 |          1.708 |
| 1.0-1.2     |       345 |         55.73  |          83.278 |          1.576 |
| >1.2        |       879 |         69.357 |         191.63  |          2.988 |

### Context only: every candidate on the holdout

Computed after the frozen run; used for no decision. Shows what the other variants would have scored.

| variant   | rule   |   median_abs_log_ratio |   refusal_rate |   windows |
|:----------|:-------|-----------------------:|---------------:|----------:|
| V3        | C3     |                  0.84  |          0.027 |      1783 |
| V3        | C4     |                  0.906 |          0.021 |      1783 |
| V2        | C1     |                  2.968 |          0.04  |      1783 |
| V3        | C1     |                  2.989 |          0     |      1783 |
| V1        | C1     |                  3.024 |          0.04  |      1783 |
| V2        | C2     |                  3.22  |          0.014 |      1783 |
| V1        | C2     |                  3.265 |          0.014 |      1783 |
| V3        | C2     |                  3.293 |          0     |      1783 |
| V2        | C4     |                inf     |          0.702 |      1783 |
| V2        | C3     |                inf     |          0.714 |      1783 |
| V1        | C3     |                inf     |          0.714 |      1783 |
| V1        | C4     |                inf     |          0.702 |      1783 |

## Disclosed clarification

Log ratios and the S2 ratio add 1 second to both predicted and observed mean queue time, because a quiet hour can have an observed mean wait of exactly zero. This rule was written into the analysis code before any prediction was computed; it was not in the original pre-registration.
