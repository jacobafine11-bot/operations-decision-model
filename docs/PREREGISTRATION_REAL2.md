# Pre-registration: real-data round 2 (warehouse and factory)

**Written and committed before any model prediction was compared with
these datasets.** Exploration so far: file layouts, column names, row
counts, date spans, and resource names only.

Why these datasets: the first real-data test used a call center, which
is not the project's target. These two are a distribution warehouse and
a production floor.

## R-A: warehouse inventory (best stock level on real demand)

**Data.** Order picking dataset from the warehouse of a footwear
manufacturer (Mendeley Data, CC BY 4.0): 122,370 order lines, 32,634
orders, 5 Jan to 19 Oct 2023. `adapters/mendeley_warehouse.py`.

**Demand.** Units ordered per product reference per week (Monday to
Sunday), full weeks from 9 Jan to 15 Oct 2023; a week with no order for
a product counts as zero demand.

**Split.** Calibration: weeks starting 9 Jan to 29 May (21 weeks). Test:
weeks starting 5 Jun to 9 Oct (19 weeks).

**Products scored.** At least 10 weeks with demand in the calibration
half.

**Model.** The inventory layer E3 (newsvendor, normal demand): order-up-to
level S = mean + z(τ) × sd of the calibration weeks, for target service
level τ.

**Outcome.** Share of (product, test week) pairs whose demand is at or
below S, i.e. the realized no-stockout rate.

| ID | Criterion | Pass if |
|---|---|---|
| R-A1 | Realized rate for target 90% | 85% to 95% |
| R-A2 | Realized rate for target 80% | 75% to 85% |
| R-A3 | Realized rate for target 95% | 90% to 99% |

Reported, not gated: the same for "lumpy" products (30% or more zero
weeks in calibration) separately; an empirical-quantile baseline (the
calibration weeks' own 90th percentile); and an input check of the
arrival assumption: chi-square test of Poisson order arrivals per
15-minute block, weekdays 08:00 to 17:00, by month.

## R-C: factory flow (routing math on a real job shop)

**Data.** "Production Analysis with Process Mining Technology" (Levy,
2014; 4TU.ResearchData): 4,543 events, 225 work orders, 31 resources,
2 Jan to 31 Mar 2012. `adapters/factory_4tu.py`.

**Operations.** Consecutive rows with the same work order and activity
form one operation at that resource; start = first start, end = last
completion.

**Split.** Work orders whose first operation starts before 15 Feb 2012
are calibration; the rest are test.

**Model.** The flow layer E1 (traffic equations): routing probabilities
between resources, and the share of work orders entering at each
resource, estimated from calibration work orders; visit ratios
v = (I − Pᵀ)⁻¹ e; predicted operations at each resource = number of test
work orders × v. Predicted busiest resource = largest v × mean
operation duration (calibration).

| ID | Criterion | Pass if |
|---|---|---|
| R-C1 | Median absolute error of predicted vs observed operations per resource (resources with at least 20 observed test operations) | ≤ 20% |
| R-C2 | The predicted busiest resource is among the 2 busiest observed in the test half (total operation time) | yes |

Not attempted, and why: waiting times on this floor are driven by
production scheduling, shifts, and batch setups, which the model does not
represent; with 100 to 300 operations per machine any waiting-time test
would be too weak to mean much.

## Procedure

Both tests run once. Results are reported as they come out, in
docs/REAL2_REPORT.md and the portal.
