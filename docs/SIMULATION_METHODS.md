# Simulation Methods

How every simulation in this project is built, run, and reported, so
that any number in the paper can be traced to a reproducible run.

## 1. What the simulations are

All simulators live in `simulation/des.py` and deliberately share **no
code** with the model (`model/opsmodel.py`). The model computes answers
from equations; the simulators build a warehouse event by event from
first principles. When the two agree, that is evidence; if they shared
arithmetic, agreement would be circular.

| Simulator | What it builds | Mechanics |
|---|---|---|
| `simulate_mmc` | one station, crew of c, FIFO line | For customer i with arrival A_i: pop the earliest server-free time from a min-heap, start at max(A_i, free), depart at start + S_i, push the departure back. Exact for FIFO multi-server queues. Service times: exponential, or gamma with a chosen cv to break the exponential assumption on purpose. |
| `simulate_tandem` | stations in a row | Exact departure recursions: D¹_i = max(A_i, D¹_{i−1}) + S¹_i, then each later stage D^k_i = max(D^{k−1}_i, D^k_{i−1}) + S^k_i. |
| `simulate_mmc_absenteeism` | crew with sick days | Each worker independently misses a day with probability p; each day runs as its own finite-horizon queue with the surviving crew (zero-worker days: one emergency server at half speed — a stated modeling choice). |
| `newsvendor_brute_force` | stock-level cost curve | One million demand draws, cost evaluated at 400 candidate stock levels, minimum taken by brute force. |
| `pipeline/scale_test.py` | a synthetic year of history | 5M order events with known ground-truth rates at millisecond timestamps, plus 250 SKUs × 365 days of gamma demand; exists to prove the data pipeline recovers known truth at full scale. |

## 2. Randomness and reproducibility

- Every simulator takes a **seed** (numpy PCG64). Every number in the
  verification report is reproducible by rerunning the suite: seeds are
  fixed in `tests/run_verification.py`.
- Each verification run writes a **run record** to
  `results/run_record_<timestamp>.json`: date, code revision, Python and
  package versions, platform, check counts, margin and alpha, wall time.
  A number in the paper cites its run record.

## 3. Warmup, estimation, and uncertainty

- **Warmup:** simulations start empty, which is not steady state. The
  first 10% of customers are discarded before any averaging.
- **Batch means:** consecutive waits are correlated, so the naive
  standard error would overstate certainty. Post-warmup observations are
  split into 20 batches; the batch averages are treated as approximately
  independent, giving a standard error with 19 degrees of freedom and
  the 95% CIs printed in every table.
- **Little's law estimates:** L (orders in system) is reported as
  λ̂ × W̄, with λ̂ the realized arrival rate over the measured span.

## 4. How model and simulation are compared

Per docs/STATS_STUDY.md: exact formulas are judged by **TOST
equivalence** at a pre-registered ±5% relative margin, alpha 0.05, with
the p-value printed per scenario (Layer 3a table of the verification
report). Approximations are judged against stated tolerances and
labeled, never granted an equivalence claim (Layer 3b table). Sample
sizes are a power decision: se must sit below ~margin/1.73 so a correct
model can pass; high-utilization cases therefore run 1.6M–2.5M
customers where low-utilization cases run 400k.

## 5. Where the simulations run

| Environment | Use | Notes |
|---|---|---|
| This project's cloud workspace (Linux, Python 3.11+) | development and the runs behind the current report | where all current numbers were produced; run records capture the platform string |
| Any laptop | full suite | `pip install -r requirements.txt`, then `python tests/run_verification.py` (≈7 s) and `python pipeline/scale_test.py` (≈5 s) |
| Google Colab | heavier experiments, sharing with the teacher | `notebooks/colab_quickstart.ipynb` installs dependencies and runs the full suite in the browser, no setup |
| Streamlit (local or Community Cloud) | the user-facing portal | the portal calls the closed-form model for instant answers and displays stored simulation results; long simulations are run by the suite, not inside the page |

## 6. Transparency rules

1. Every reported comparison carries: the theory value, the simulation
   mean with its 95% CI, the margin or tolerance, the p-value where an
   equivalence claim is made, and the verdict — in a table.
2. Approximations are always labeled as approximations.
3. A failed check is never deleted; it is either fixed (with a
   CHANGELOG entry naming the mechanism) or reported as a finding.
4. Simulation code never imports model code.
5. Seeds, sample sizes, warmup fractions, and batch counts live in the
   test file, not in prose, so the report and the code cannot drift
   apart.
