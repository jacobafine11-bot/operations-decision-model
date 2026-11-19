# Change Log

Every change to an equation, estimator, or test gets an entry: what
changed, the mechanism-based reason, and the test that triggered it.
"Adjusted until the output matched" is not a valid reason and will not
appear here.

---

## C-012 — Ranges include the formula's own approximation error
**Date:** 2026-11-19
**Triggered by:** Coverage round 1 (C-011) FAILED on station waits: only
73.4% of 90% ranges contained the truth. Diagnosis: coverage was worst at
quiet stations (44% below 70% utilization), where estimation error is
tiny so ranges were narrow, while the formula's approximation error
(about 6%) remained; downstream stations (line-variability approximation
involved) covered 69%, first stations 90%.
**Change:** each simulated draw also multiplies each station's wait by a
log-normal factor whose spread is the formula's measured approximation
error: 5.5% at first stations, 11.5% downstream. Those two numbers were
measured ONLY on development companies (60 companies, 147 stations, true
inputs vs precise truth; `analysis/approx_error.py`); the formula is
unbiased there (mean log error about 0).
**Verification:** coverage round 2, pre-registered (40f264a) before its
first run, on 80 FRESH companies (indices 60 to 79): station waits 89.1%,
total time 88.8%, near-capacity stations 86.5%. All three PASS. The
suite checks that the approximation term alone reproduces the measured
spread. Suite 87/87.

## C-011 — Uncertainty ranges for every prediction
**Date:** 2026-11-19
**Triggered by:** C-010: near capacity, estimation error is amplified.
**Mechanism:** a station's predicted wait depends on (1 − utilization);
at 93% busy a 1% error in measured speed moves utilization by about 0.01
and the wait by about 15%.
**Change:** `model/uncertainty.py` re-runs the model over the sampling
error of each estimate (arrival rate: relative SE 1/√n; mean work time:
relative SE cv/√n) and reports a 90% range per station and for total
time; a draw past capacity counts as an unbounded wait. Stations whose
range exceeds ±25% are flagged "sensitive: collect more data".
**Verification:** ranges collapse onto the point with unlimited data and
narrow as data grows (suite). Coverage round 1, pre-registered (fea57d4)
on 80 fresh companies: total time PASS (85.0%), near-capacity PASS
(82.6%), station waits FAIL (73.4%) → C-012.

## C-010 — 160-company benchmark: results and findings
**Date:** 2026-11-19
**What was run:** the pre-registered benchmark (docs/PREREGISTRATION_
BENCHMARK.md, two amendments, all committed before the sealed runs):
two size bands (2 to 100 and 100 to 250 workers), development and
sealed sets, original and "hard decisions" generators; every company
goes through the full pipeline (history → gate → estimates → model →
best plan) and is graded against brute-force re-simulation of every
plan on the true operation.
**Sealed results (run once):**
| Set | Band S (2-100) | Band L (100-250) |
|---|---|---|
| Original | 7/7 | 7/7 |
| Hard decisions | 7/7 | 6/7 (P3 station waits 23.8% vs ≤ 15%) |
The model chose the exact best plan in 78 of 80 sealed companies and a
near-best plan in 80 of 80; a fixed rule of thumb was near-best in 31 of
80. Median total-time error 0.4% to 1.3%; promised vs delivered savings
2.6% to 7.3%.
**Findings:**
1. Estimation amplification near capacity: the hard L failure involved 4
   stations at 88% to 95% utilization; with true inputs their median
   error was 5.7%, with estimated inputs 23.8% → C-011.
2. Decisions are robust to station-level errors: errors largely cancel
   in before-vs-after comparisons.
3. Test-design lessons fixed by amendment before sealed runs: decisions
   were too predictable (hard set added); P3 undefined for big companies;
   one-run truth too noisy near capacity (truth now 4 × 200,000 orders).
4. Known model limit: a steady-work crew far down a line (L8 station 5,
   cv 0.33, 89% busy) is under-predicted by about 31% even with true
   inputs.
The model itself was not changed during the benchmark.

## C-009 — Arrival variability propagates down a serial line (QNA)
**Date:** 2026-11-19
**Triggered by:** The mock distributor (portal): with estimates within 1%
of the truth, predicted waits were right at the first station (−5%) but
24% and 43% too high at the second and third.
**Mechanism:** The model treated every station's arrivals as random
(Poisson). Inside a line, a station's arrivals are the previous
station's departures; a busy crew releases work at the pace of its own
(steadier) work times, so downstream arrivals are smoother than random
and lines are shorter. Whitt's QNA linking equation (Whitt, 1983) gives
the departure variability:
Cd² = 1 + (1 − ρ²)(Ca² − 1) + ρ²(Cs² − 1)/√c, and the wait factor
becomes (Ca² + Cs²)/2.
**Change:** `mmc()` takes `arrival_cv`; `evaluate()` propagates it
station by station for serial lines (`arrival_variability()`); other
network shapes keep random arrivals, a documented limit.
**Verification:**
- Exact limiting cases in the suite: Poisson in + exponential service
  gives Poisson out (Burke); an idle server passes arrivals through; a
  saturated one passes service through; arrival_cv = 1 changes nothing.
- Held-out check, pre-registered in `analysis/qna_heldout.py` and
  committed (acbc157, 17:04:53) before its first run: four new line
  configurations, 200,000 simulated orders each. Downstream-station
  wait error fell from 24.3% to 5.9% on average; all six judged
  stations within ±10% (rule: ±25%). Rule (a) PASS, rule (b) PASS.
  Includes a case where an erratic first station correctly RAISES the
  next station's predicted wait (error −22.6% → −0.9%).
- Development numbers on the mock configuration (not evidence, shown for
  transparency): packing 24% → 8%, loading 43% → 16%.
Suite now 84/84.

## C-008 — First real-data blind test FAILED (1/6); diagnosis and lessons
**Date:** 2026-11-17
**Triggered by:** Holdout run of the pre-registered Anonymous Bank test
(docs/REAL_DATA_VALIDATION.md), frozen choice V3 Erlang A + C3.
**Result, as recorded:** predicted waits about 2x too high (median ratio
1.96, aggregate +121%), predicted abandonment 29% vs 15% observed, rank
correlation across hours 0.24 (needed 0.70). Coverage passed (97%). The
forecast version (C4, staffing from prior weeks) failed the same way.
This result is not tuned away: the July to December half is no longer
blind and will never again be used as a blind test.
**Diagnosis (exploratory, calibration half):**
1. The bias was visible before the holdout (calibration median ratio
   1.74). The model-selection score measured the size of errors only, so
   it could not see their direction. Lesson: the selection score must
   penalize what the scorecard penalizes (bias as well as scatter).
2. Rounding effective agents is not the cause (interpolating between
   neighboring crew sizes gives 1.73).
3. Leading hypothesis, mechanism-based: C3 counts busy agents during
   the moments a line exists, and lines form precisely when fewer agents
   are free. It therefore samples the worst moments of the hour and
   understates the hour's average capacity, making every prediction
   pessimistic. This is testable and is the first item for round 2.
**Status of the model:** the equations remain exactly verified against
simulation (76/76). What failed on real data is the measurement of
effective capacity from records, which the equations take as given.
**Round 2 plan:** pre-register a capacity estimator free of the
selection effect, with a selection score that matches the scorecard,
and a genuinely unseen blind set (a different real system: the Syosset
distributor's stopwatch sample, or a second public dataset).

## C-007 — Headcount is not capacity (real-data finding)
**Date:** 2026-11-17
**Triggered by:** Calibration phase of the bank test: every model variant
was off by a typical factor of about 18 using agent headcount.
**Mechanism:** Agents counted as on duty were available for inbound
calls only about 38% of the time (after-call work outside the recorded
service time, outbound work, breaks, skill restrictions). With headcount
as capacity, the model sees 47% utilization and predicts sub-second
waits; callers actually waited 49 s and 12% hung up.
**Change:** Effective-agent estimators added to the analysis (C3: busy
agents while a line exists; C4: the same from the prior four weeks,
usable as a staffing plan). Pre-registered as Amendment 1 and committed
before any holdout scoring. Error fell from a factor of about 18 to
about 2 on the calibration half.
**Implication for the project's thesis:** for a small operation, the
input most likely to be wrong is effective capacity, and the model
must measure it rather than accept a headcount.

## C-006 — Erlang A: customers who give up (abandonment)
**Date:** 2026-11-17
**Triggered by:** Real call-center data: 15.3% of queued callers hang
up, and in effective-capacity terms many hours are overloaded, which
Erlang C cannot describe at all (it refuses about 70% of hours).
**Change:** model/opsmodel.py `erlang_a()`: M/M/c+M birth-death chain
with abandonment rate θ, summed exactly until the tail is below 1e-16;
outputs by Little's law (Wq = Lq/λ, P(abandon) = θLq/λ). θ is estimated
from data by the censored-exponential MLE (abandonments / total waiting
time).
**Verification:** θ → 0 reproduces Erlang C to 6e-9; θ = μ reproduces
the Poisson identity to 1e-12; busy servers equal throughput/μ exactly;
three scenarios (one overloaded) pass TOST equivalence against an
independent abandonment simulator on both waiting time and abandonment
probability. Suite now 76/76.

## C-005 — Validation standard set: TOST equivalence testing
**Date:** 2026-11-13
**Triggered by:** Independent Study 2 step 1 (the formal stats study,
docs/STATS_STUDY.md).
**Mechanism:** A plain t-test has the wrong shape for validation:
"no significant difference" is easiest to obtain with the weakest
evidence. TOST reverses the burden of proof: H0 is "difference at least
the margin", so a small p-value is positive evidence of closeness.
**Change:** Every exact-formula-vs-simulation comparison is judged by
TOST at a pre-registered ±5% relative margin, alpha 0.05, on batch
means (df = 19). Approximations are excluded from equivalence claims and
held to labeled tolerances. The statistical machinery itself is
validated first (Layer 0 of the report).
**Verification:** TOST agrees with its independent CI formulation in
400/400 random cases and fires at ≈5% when the true difference sits on
the margin. First application immediately exercised the power rule: two
high-utilization cases had point differences under 0.4% but CIs too
wide to prove ±5%; resolved by raising those runs to 2.5M and 1.6M
customers, never by widening the margin.

## C-004 — Kingman correction wired into the model as the default
**Date:** 2026-11-13
**Triggered by:** C-001's validated finding.
**Mechanism:** Waiting time scales with service-time variability;
exponential (cv = 1) is only the special case.
**Change:** Station carries a measured service_cv (from
pipeline/estimate.py); mmc() applies the factor (1 + Cs²)/2 to Wq.
At one server this is EXACT (it is the Pollaczek-Khinchine formula for
M/G/1); at several servers it is the Allen-Cunneen/Kingman
approximation and is labeled as such everywhere.
**Verification:** cv = 1 reduces to plain M/M/c to machine precision;
M/G/1 at cv 0.5 and 1.5 passes TOST equivalence against simulation
(exact theory); M/G/3 at cv 0.5 and 1.4 sits within the 12% stated
approximation tolerance. 65/65 checks pass end to end after the change.

## C-001 — Kingman variability correction for non-exponential service
**Date:** 2026-11-13
**Triggered by:** Layer 3 assumption-breaking run (tests/run_verification.py):
with service-time cv = 0.5 at a 3-worker station (λ=10/hr, μ=4/hr), raw
M/M/c predicted Wq = 0.3511 h while the independent simulation measured
0.2291 ± CI h, a 35% overstatement.
**Mechanism:** M/M/c assumes exponential service (cv = 1). Real picking
and packing are steadier. Kingman's approximation scales queueing delay
by (Ca² + Cs²)/2, which equals 0.625 at cv = 0.5.
**Change:** When estimated service cv differs materially from 1, waiting
time predictions carry the Kingman factor (Ca² + Cs²)/2 applied to Wq.
The estimation pipeline therefore measures cv per station
(pipeline/estimate.py) so the correction is driven by data, not by choice.
**Verification:** Corrected prediction 0.2195 h vs. simulation
0.2291 h (4.4% apart, inside tolerance; raw model was 35% off).
Recorded in docs/VERIFICATION_REPORT.md, Layer 3.
**Status:** superseded by C-004, which wired the correction into the
model as the default and re-verified end to end.

## C-002 — Timestamp granularity bias in service-rate estimation
**Date:** 2026-11-13
**Triggered by:** First run of pipeline/scale_test.py: service rates
estimated 4.3–9.0% high, worst at the fastest station.
**Mechanism:** Timestamps truncated to whole seconds shave an average
0.5 s off every service time. At a 6-second mean service time that is an
8–9% understatement of duration, hence an overstatement of rate. This is
not only a test artifact: any real export with second-granularity
timestamps biases short service times the same way.
**Change:** Synthetic data generated at millisecond precision; the
validation gate's findings now include a granularity note. Policy for
real data: if an export's timestamps are second-granularity and mean
service time is under ~60 s, estimate service times from a stopwatch
sample instead, or add the expected rounding correction.
**Verification:** Recovery error fell from 9.0% worst to 0.12% worst.

## C-003 — Demand ground truth: gamma, not clipped normal
**Date:** 2026-11-13
**Triggered by:** scale_test demand recovery missing by 18% on high-cv SKUs.
**Mechanism:** Clipping a normal at zero changes its mean and sd, so the
pre-clip parameters are the wrong ground truth to test recovery against.
**Change:** Synthetic demand is gamma(mean, cv): nonnegative by
construction, generated moments are the true moments. Estimator
correctness is additionally tested against realized sample moments via
an independent engine (DuckDB vs. pandas, agreement 1.4e-15), separating
"is the estimator right" from "how big is one year's sampling error"
(answer: up to ~15% on the sd of a volatile SKU, which is itself an
input to sensitivity sweeps).
