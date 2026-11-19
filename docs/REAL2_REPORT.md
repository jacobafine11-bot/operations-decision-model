# Real-Data Round 2: Warehouse and Factory

Rules: `docs/PREREGISTRATION_REAL2.md`, committed (319b60f) before any comparison. Code: `analysis/real2.py`, committed before its single run. Results: `results/real2.json`.

## Verdict

| Test | Result |
|---|---|
| R-A warehouse inventory (best stock level on real demand) | **2 of 3 pass** |
| R-C factory flow (routing math on a real job shop) | **1 of 2 pass** |

## R-A: does the best-stock-level rule deliver the service it promises?

Footwear manufacturer's warehouse (Mendeley Data, CC BY 4.0). 140 products, 21 calibration weeks, 19 unseen test weeks.

| ID | Target | Realized | Pass if | Verdict | Symmetric-demand products | Empirical-quantile baseline |
|---|---|---|---|---|---|---|
| R-A2 | 80% | 86.3% | 75% to 85% | FAIL | see below | 81.5% |
| R-A1 | 90% | 90.6% | 85% to 95% | PASS | see below | 88.9% |
| R-A3 | 95% | 92.9% | 90% to 99% | PASS | see below | 92.8% |

**Diagnosis of R-A2 (exploratory, after the result):** weekly demand is strongly right-skewed (median skewness 1.43). The 38 products with roughly symmetric demand delivered 80.3% at the 80% target; the 102 skewed products delivered 88.5%. The rule assumes a bell curve; skewed products need a skewed demand model (e.g. gamma). That fix must be tested on data not used here.

**Input check (reported, not gated):** order arrivals are nowhere near random. In every month the variance of orders per 15-minute block is 85 to 288 times the mean (random arrivals give 1). 32,634 orders were created in only 768 distinct minutes, up to 594 at once: this warehouse releases work in batches (picking waves). The model's random-arrival assumption does not hold for wave-based distribution centers.

## R-C: does the routing math predict workload in a real job shop?

Machining job shop (Levy 2014, 4TU.ResearchData). 126 calibration and 99 test work orders.

| ID | Criterion | Result | Verdict |
|---|---|---|---|
| R-C1 | Median abs error of operations per resource (≥ 20 ops) | 36.9% (need ≤ 20%) | FAIL |
| R-C2 | Predicted busiest resource in observed top 2 | predicted Quality Check 1; observed top 2 Quality Check 1, Machine 6 - Turning & Milling | PASS |

| Resource | Predicted ops | Observed ops | Error |
|---|---|---|---|
| Machine 1 - Lapping | 140.6 | 79 | +78% |
| Machine 11 - Grinding | 45.6 | 33 | +38% |
| Machine 4 - Turning & Milling | 47.1 | 34 | +39% |
| Machine 5 - Turning & Milling | 37.7 | 41 | -8% |
| Machine 6 - Turning & Milling | 33.0 | 48 | -31% |
| Machine 7- Laser Marking | 110.0 | 81 | +36% |
| Machine 8 - Turning & Milling | 32.2 | 46 | -30% |
| Machine 9 - Turning & Milling | 33.8 | 26 | +30% |
| Packing | 136.7 | 67 | +104% |
| Quality Check 1 | 447.9 | 282 | +59% |

**Diagnosis of R-C1 (exploratory):** the data ends on 31 March, so test work orders that started in March were cut off mid-route: 7.1 recorded operations each, against 13.8 for calibration orders; only 22% of test orders reached Packing, against 40% in calibration. The model predicted full routes, so it over-predicted, most of all at end-of-route steps (Packing +104%, Quality Check +59%). This is a flaw in the test design (right-censoring was not handled), recorded as a failure and as a lesson: compare only work that had time to finish.

## What this round shows

- The inventory rule works on real distribution demand at the service levels businesses usually target (90% and 95%), and misses where demand is skewed and the target is lower.
- The routing math identifies the real bottleneck of a real factory.
- Two assumptions break on real distribution data and set the next modeling work: batch (wave) arrivals, and skewed demand.
