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

## Verification (four layers, 76/76 passing)

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
streamlit run portal/app.py           # the user-facing portal
```

## Where this lives

- **Source of truth:** a private GitHub repository (this folder is a
  ready-to-push git repo). Version history, issues, and free deploys
  hang off it.
- **Interface:** the Streamlit portal (`portal/app.py`) — describe an
  operation, see utilization, bottleneck, profit, and a ranked table of
  change plans with an honesty check (the flip point). Deployable free
  on Streamlit Community Cloud straight from the repo.
- **Notebooks:** `notebooks/colab_quickstart.ipynb` runs the full suite
  and a worked decision in Google Colab with zero setup.
- **Docs:** NOTATION.md (symbols/units/provenance), STATS_STUDY.md (the
  test choice and its defense), SIMULATION_METHODS.md (how and where
  every simulation runs), CHANGELOG.md (every equation change with its
  mechanism), VERIFICATION_REPORT.md (generated tables with p-values).

## Status (honest)

| Layer | Against simulation | Against real data |
|---|---|---|
| Queueing equations (E1, E2, Erlang C, Erlang A) | exactly verified, 76/76 checks | first blind test **failed 1/6** (Anonymous Bank call center, 417k real calls): about 2x too pessimistic, because effective capacity is hard to measure from records (C-007, C-008) |
| Inventory (E3) | verified | not yet tested on real data |
| Decision layer (E5–E7) | behavior-tested | not yet tested on real data |

The model is not yet ready to be trusted for a real business decision.
The verification machinery that told us so is. Round 2 is planned in
CHANGELOG C-008.

## Real-data testing protocol

Every real-data test is pre-registered (rules committed to git before
any prediction is compared with data), selects among model options on a
calibration half only, and runs the frozen choice once on a blind half.
See docs/PREREGISTRATION_BANK.md and docs/REAL_DATA_VALIDATION.md; the
commit history shows the order.

## Findings so far (see docs/CHANGELOG.md)

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
