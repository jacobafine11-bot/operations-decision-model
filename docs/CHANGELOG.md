# Change Log

Every change to an equation, estimator, or test gets an entry: what
changed, the mechanism-based reason, and the test that triggered it.
"Adjusted until the output matched" is not a valid reason and will not
appear here.

---

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
