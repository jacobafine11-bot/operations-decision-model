# Statistical Significance Testing: Study, Decision, and Defense

Step 1 of the Independent Study 2 plan. This document is the study
itself (the concepts, in plain language, each tied to where the project
uses it), the survey of candidate tests, the decision, and the defense.
Transcribe the worked pieces by hand; every claim here is demonstrated
numerically in tests/run_verification.py (Layer 0).

## 1. The problem statistics solves for this project

A simulation's output is random. Run the warehouse simulation twice with
different seeds and the average wait differs. So when the model says
Wq = 0.147 hours and the simulation says 0.146, two explanations
compete: the model is right and the 0.001 is noise, or the model is
wrong and the noise is hiding it. Statistics is the tool that separates
those two, with a stated error rate.

## 2. The concepts, in order

**Sampling distribution and standard error.** The simulation's average
wait is itself a random quantity. If you reran the whole simulation many
times, the averages would scatter around the true value. The standard
deviation of that scatter is the standard error (se). Bigger simulations
have smaller se: quadrupling the data roughly halves it.

**The correlation problem, and batch means.** Waits of consecutive
orders are correlated (a long line delays everyone in it), so the
textbook se formula, which assumes independent observations, understates
the noise. The remedy used everywhere in this project is batch means:
split the post-warmup waits into B = 20 batches, average each batch, and
treat the 20 batch averages as approximately independent. The se comes
from their spread, with 19 degrees of freedom.

**Confidence interval (CI).** mean ± t × se. A 95% CI is built so that
the procedure captures the true value 95% of the time. The t multiplier
(2.093 at 19 degrees of freedom) replaces 1.96 because the se is itself
estimated.

**Hypothesis test logic.** Choose a null hypothesis H0, compute how
surprising the data would be if H0 were true (the p-value), and reject
H0 when p falls below a pre-chosen alpha (0.05 here). Two error types:
Type I, rejecting a true H0 (rate controlled at alpha); Type II, failing
to reject a false H0 (its complement is power, which grows with data).

**The warmup.** A simulation starts empty, which is not the steady
state. The first 10% of customers are discarded so the averages describe
the running system, not the start-up transient.

## 3. Candidate tests for "does the model match the simulation?"

| Candidate | What it tests | Why it fails or fits here |
|---|---|---|
| Plain one-sample t-test | H0: model == simulation | Wrong shape for validation, two ways. With little data it has low power, so "no significant difference" is easy to get and proves nothing. With a lot of data it flags differences of 0.1% that no decision cares about. Passing by failing to reject is backwards. |
| Eyeball the CI ("theory inside the CI") | informal | Same backwards logic, and the pass gets EASIER as the simulation gets sloppier (wider CI). A validation standard should get harder with less evidence, not easier. |
| TOST equivalence test | H0: \|model − sim\| ≥ margin | The right shape. The burden of proof is on the model: a small p-value is positive evidence the difference is INSIDE a pre-registered margin. More data makes the test easier to pass only when the model is actually close. |
| Kolmogorov-Smirnov | whether data follows a distribution | Not for model-vs-sim means, but exactly right for input checks: are the inter-arrival gaps exponential? Caveat: fitting the rate from the same data makes the textbook p-value too forgiving, so the p-value comes from a parametric bootstrap (Lilliefors' approach). |
| Chi-square goodness of fit | whether counts follow a distribution | The input check for "are arrivals per period Poisson?", with tail bins merged so every expected count is at least 5. |

## 4. The decision

1. **Model validation** uses the **TOST equivalence test** on batch
   means: pre-registered relative margin **±5%**, **alpha = 0.05**,
   B = 20 batches (19 degrees of freedom). Applied to every exact
   formula in Layer 3a of the verification report, which prints the
   p-value for each scenario. Approximations (the multi-server
   variability factor, the absenteeism mixture) are never granted an
   equivalence claim; they are reported against stated tolerances and
   labeled as approximations.
2. **Input validation on real data** uses the **chi-square goodness-of-
   fit test** for Poisson arrival counts and the **parametric-bootstrap
   KS test** for exponential gaps, both at alpha = 0.05. These run in
   the pipeline before any dataset's estimates reach the model.
3. **Power is a design requirement, not an afterthought:** simulation
   sample sizes are chosen so the se is small enough that a correct
   model CAN pass (se below roughly margin/1.73). When a TOST fails with
   a tiny point difference and a wide CI, the required response is more
   data, never a wider margin. This exact situation occurred on first
   run (two high-utilization cases missed at p = 0.06 and 0.15 with
   point differences under 0.4%) and was resolved by increasing those
   simulations to 2.5M and 1.6M customers.

## 5. The defense (short form, for the proposal and the paper)

I validate the model with equivalence testing (TOST) rather than an
ordinary t-test because the two ask opposite questions, and only one of
them is mine. A t-test asks "can I prove the model and the simulation
differ?", so I would pass by failing, and failing is easiest exactly
when my evidence is weakest. TOST asks "can I prove the difference is
smaller than a margin I committed to in advance?", which puts the burden
of proof on my model and rewards more evidence instead of less. I set
the margin at ±5% because the decisions the model drives are not
sensitive below that level: a 5% error in a predicted waiting time moves
a change's dollar value far less than the uncertainty already in the
cost inputs, which my own data work measured at up to 15%. A tighter
margin would be false precision; a looser one could hide real model
errors. I keep alpha at the standard 0.05, I use batch means because
queue waits are correlated and would otherwise overstate my certainty,
and I validated the tests themselves before trusting them: the TOST
decision matches its independent confidence-interval formulation in 400
random cases, fires at the expected 5% rate when the true difference
sits exactly on the margin, and the input-check tests pass data built to
pass and reject data built to fail.

## 6. Demonstrations on record (Layer 0 of the verification report)

| Demonstration | Result |
|---|---|
| TOST decision vs. 90%-CI criterion, 400 random cases | 400/400 agree |
| TOST firing rate when the true difference equals the margin | ≈ 0.05, as designed |
| scipy t quantiles vs. independent hard-coded table | agree to 5e-4 |
| KS on true exponential gaps / uniform gaps | passes / rejects |
| Chi-square on Poisson counts / constant counts | passes / rejects |

## 7. What is still owed

- Hand-transcribe: the se of a mean, the CI construction, the two
  one-sided tests of TOST and why max(p1, p2) is the right combination,
  and one full worked example from the report's Layer 3a table.
- When real datasets arrive: run the chi-square and KS input checks
  before estimation, and report them in the dataset's validation record.
