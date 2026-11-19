# Operations Decision Model — Independent Study 2 build

A mathematical decision framework for small distribution and production
operations (2–30 workers): given measured data about an operation, decide
which changes are worth making, in dollars per year, and whether a
strategy change beats automation.

Jacob Fine · Mathematics Research (Ms. Badalian) · Jericho High School

## Architecture

```
data/raw        untouched source files (never edited)
adapters/       one script per dataset -> standard format
schema/         the standard tables + the validation gate
data/clean      validated standard-format Parquet
pipeline/       estimation (rows -> rates, with cv) and the scale test
model/          the equations E1–E7 + guardrails (never sees raw rows)
simulation/     independent discrete-event simulator (shares NO code
                with model/ — agreement is evidence, not circularity)
tests/          the three-layer verification suite; writes the report
results/        each run stored with inputs, code version, date
docs/           NOTATION.md, CHANGELOG.md, VERIFICATION_REPORT.md
portal/         (later) thin display layer over results/
```

## The equation stack

E1 traffic → E2 station queueing (M/M/c, Kingman-corrected per C-001) →
E3 inventory (newsvendor) → E4 coupling → **E5 profit rate Π ($/hr)** →
**E6 value of a change set V(S) ($/yr)** → E7 best affordable plan.

Decision rule: do a change set S iff V(S) > 0 **and** the sign survives
sensitivity sweeps on every assumed cost input (the sensitivity()
function reports flip points: "A beats B unless waiting cost exceeds $X").

## Verification (four layers, 87/87 passing)

0. The statistical tests themselves are validated: TOST against its
   independent CI formulation (400/400), its firing rate at the margin
   (≈ alpha), and the input-check tests against data built to pass and
   data built to fail.
1. Closed form vs. textbook values (exact).
2. Every result vs. a second, algorithmically independent computation
   (matrix solve vs. iteration; Erlang B recursion vs. direct sum;
   critical ratio vs. 1M-draw brute force).
3. Model vs. discrete-event simulation that shares no code with it.
   Exact formulas are judged by **TOST equivalence tests** at a
   pre-registered ±5% relative margin (alpha 0.05, batch means), with
   the p-value printed per scenario; approximations are held to stated
   tolerances and labeled. Deliberate assumption-breaking (steady or
   erratic service times, absenteeism) measures where assumptions bend.

Plus unit-invariance tests (hours vs. minutes must agree — the flaw we
found in a published formula, made into a standing test) and guardrail
tests (invalid inputs must raise, never return numbers). Every run
writes a run record (date, code revision, seeds, versions) to results/.

Run everything:

```
pip install -r requirements.txt
python3 tests/run_verification.py     # writes docs/VERIFICATION_REPORT.md
python3 pipeline/scale_test.py        # 5M-row pipeline proof
python3 tests/test_portal_logic.py    # portal compute layer
python3 tests/test_portal_pages.py    # every portal page + buttons
python3 analysis/benchmark.py dev     # benchmark (see docs/PREREGISTRATION_BENCHMARK.md)
streamlit run portal/app.py           # the user-facing portal
```

## Where this lives

- **Source of truth:** a private GitHub repository (this folder is a
  ready-to-push git repo). Version history, issues, and free deploys
  hang off it.
- **Interface:** the portal, a full program (`portal/app.py`) with eleven
  pages. See "The portal" below. Deployable free on Streamlit Community
  Cloud straight from this repository (main file `portal/app.py`).
- **Notebooks:** `notebooks/colab_quickstart.ipynb` runs the full suite
  and a worked decision in Google Colab with zero setup.
- **Docs:** NOTATION.md (symbols/units/provenance), STATS_STUDY.md (the
  test choice and its defense), SIMULATION_METHODS.md (how and where
  every simulation runs), CHANGELOG.md (every equation change with its
  mechanism), VERIFICATION_REPORT.md (generated tables with p-values).

## The portal

Run it: `pip install -r requirements.txt` then `streamlit run portal/app.py`
(from the repository root, so the theme in `.streamlit/` loads).

| Page | What it does |
|---|---|
| Overview | What the model is, an honest status table, where to go next |
| Model workbench | Describe an operation, see utilization, bottleneck, profit; rank changes with interactions and the flip point; size one crew (with or without customers who give up) |
| Mock company walkthrough | Harbor Supply Co. (fictional, with a known answer key): order history, validation gate, estimates, predictions checked against the history, ranked decisions, and a re-simulation that checks whether the decision delivered |
| Simulation lab | Run the independent simulator live (one station, customers who give up, a line of stations); watch it converge; TOST verdict; sample-size estimate |
| Statistics lab | TOST step by step; why a plain t-test would pass a wrong model; chi-square and KS input checks on real Tyler's Grill data; the tests, tested |
| Benchmark (160 companies) | Sealed scorecards for 2 to 100 and 100 to 250 workers, model vs a rule of thumb, predicted vs true, promised vs delivered savings, uncertainty coverage, a company explorer |
| Fine-tuning journal | Every changelog entry with mechanism, evidence, and a live demonstration |
| Real-data tests | Round 1 (call center) and round 2 (real warehouse inventory, real factory flow): pre-registered, run once, diagnosed |
| Verification suite | Run all 84 checks from the page; run history; the full report |
| Data pipeline | Upload an order CSV and run the gate and estimation; the standard format; scale proof |
| Documents | Every document in the repository |

Portal tests: `python tests/test_portal_pages.py` executes every page and
clicks the buttons that run real work (13 checks).

## Status (honest)

| Part | Against simulation | 160 made-up companies (sealed) | Real data |
|---|---|---|---|
| Waiting lines (stations, crews, lines, give-ups) | exactly verified, 87/87 checks | time through the line: median error 0.4% to 1.3% | call center **failed 1/6** (effective capacity hard to measure) |
| Uncertainty ranges (C-011, C-012) | exact limits checked | 90% ranges held 89% of the time | not yet |
| Decisions (value of a change, best plan) | behavior tested | exact best plan **78/80**; rule of thumb near-best 31/80 | not yet |
| Inventory (best stock level) | verified vs brute force | not in the benchmark | real warehouse: 90.6% at a 90% target, 92.9% at 95%, overstocks at 80% |
| Flow and routing (E1) | exactly verified | part of every company | real factory: right bottleneck; workload test flawed by data cutoff |

On operations that match its assumptions the model is accurate and its advice is
nearly perfect from 2 to 250 workers. Real data has shown where the assumptions
break, and those set the next work: **wave (batch) arrivals**, **skewed demand**,
and **effective capacity vs headcount**.

## Real-data testing protocol

Every real-data test is pre-registered (rules committed to git before
any prediction is compared with data), selects among model options on a
calibration half only, and runs the frozen choice once on a blind half.
See docs/PREREGISTRATION_BANK.md and docs/REAL_DATA_VALIDATION.md; the
commit history shows the order.

## Findings so far (see docs/CHANGELOG.md)

- **C-013** Real warehouse and factory (round 2): the inventory rule delivers 90.6% at a
  90% target on real demand; the routing math names the real factory bottleneck. Real
  orders arrive in waves, and demand is skewed: the next model changes.
- **C-012 / C-011** Every prediction now has a 90% range covering estimation and the
  formula's own error; on 80 fresh companies the ranges held 89% of the time.
- **C-010** 160-company benchmark (2 to 250 workers): sealed 27 of 28 criteria; exact
  best plan 78 of 80. Near capacity, small measurement errors are amplified.
- **C-009** Variability passes down a line of stations (QNA linking
  equation). Found through the mock company; a pre-registered held-out
  check on four new configurations cut downstream error from 24.3% to 5.9%.
- **C-008** First real-data blind test failed (1/6). Lesson: the score
  used to choose a model must penalize bias, not only scatter.
- **C-007** Headcount is not capacity: bank agents were available for
  inbound calls about 38% of the time. With headcount as capacity the
  model was off by a factor of about 18.
- **C-006** Erlang A (abandonment) added and verified; Erlang C cannot
  describe the overloaded hours that real call centers run through.

- **C-004/C-001** Raw M/M/c overstates waits by ~35% when work is
  steadier than exponential; the variability factor (1+Cs²)/2 is now the
  model default, exact at one server (Pollaczek-Khinchine) and a labeled
  approximation for crews. The pipeline measures cv per station so the
  correction is data-driven.
- **C-005** Validation standard: TOST equivalence testing at a
  pre-registered ±5% margin; a plain t-test rewards weak evidence, TOST
  rewards strong evidence.
- **C-002** Second-granularity timestamps bias short service times high
  by 4–9%. Policy set for real exports.
- **C-003** One year of daily demand leaves up to ~15% sampling error on
  a volatile SKU's sd — quantified, and fed into sensitivity sweeps.

## Scale proof

5,000,000 order events + 91,250 demand rows: generated, written to
Parquet (44 MB), validated, and estimated in ~5 s on a laptop-class
machine. Estimator exactness: DuckDB vs. independent engine agree to
1.4e-15; ground-truth rates recovered within 0.12%.

## Full git history

The commit history on GitHub is the evidence that every pre-registration
was committed before its results: compare the timestamps of the
PREREGISTRATION_BANK.md commits with the results commits
(`git log --date=iso`). A plain-text copy is in docs/GIT_HISTORY.txt.
