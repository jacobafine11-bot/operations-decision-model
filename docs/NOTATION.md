# Notation and Assumptions

Every symbol in the model, its units, and where it comes from.
Provenance tags: **derived** (proved in the Derivation Board),
**cited** (from a source, APA 7 reference in the Source Deep Dives log),
**tested** (verified numerically in tests/), **assumed** (a modeling
choice that gets a sensitivity sweep).

Base units: hours and dollars. Dimensionless outputs (ρ, probabilities,
counts) must be identical in any time unit; tests/test "Unit invariance"
enforces this.

## Flow layer (E1, E2)

| Symbol | Meaning | Units | Provenance |
|---|---|---|---|
| γ_j | external arrivals into station j | orders/hr | measured from data |
| P_jk | routing probability j → k | — | measured from data |
| λ_j | effective load on station j, λ = (I − Pᵀ)⁻¹γ | orders/hr | derived (D3), tested |
| μ_j | service rate per worker at station j | orders/hr | measured from data |
| c_j | crew size at station j | workers | given |
| ρ_j | utilization λ_j/(c_j μ_j); steady state requires ρ_j < 1 | — | derived (D2), tested |
| C(c, a) | Erlang C probability of waiting, offered load a = λ/μ | — | derived (D4), tested |
| L_j, W_j | orders at station j; time at station j | orders; hr | derived (D2/D4), tested |
| Lq_j, Wq_j | orders waiting; wait in line | orders; hr | derived, tested |
| Cs | service-time coefficient of variation | — | measured from data |
| (Ca²+Cs²)/2 | Kingman variability factor on Wq | — | cited (Kingman), tested (C-001) |

## Inventory layer (E3)

| Symbol | Meaning | Units | Provenance |
|---|---|---|---|
| D_i | demand per cycle for product i, Normal(m_i, σ_i) | units | measured; normality assumed |
| S_i | order-up-to level | units | decision variable |
| p_i | underage (stockout) cost | $/unit | interview or assumed → sensitivity |
| h_i | overage (holding) cost | $/unit | interview or assumed → sensitivity |
| S_i* | optimal level, m_i + σ_i Φ⁻¹(p/(p+h)) | units | derived (D5), tested |
| G(z) | normal loss φ(z) − z(1−Φ(z)) | — | derived (D5), tested |

## Decision layer (E5–E7)

| Symbol | Meaning | Units | Provenance |
|---|---|---|---|
| θ | full parameter set of one version of the operation | — | definition |
| m | margin per shipped order | $/order | measured or interview |
| c_w | cost of one order waiting one hour | $/order·hr | interview or assumed → sensitivity |
| K | staffing + equipment overhead | $/hr | measured |
| ρ_max | sustainable utilization cap in X | — | assumed (0.95) → sensitivity |
| X | throughput, min(demand, bottleneck capacity at ρ_max) | orders/hr | derived (D8/D9) |
| Π(θ) | profit rate: mX − c_wΣL − Σ inv − K | $/hr | derived (D9), tested |
| T | operating hours per year | hr/yr | measured |
| I(S) | annualized cost of change set S | $/yr | quotes/estimates |
| V(S) | value: T(Π_after − Π_before) − I(S); do S iff V > 0 and sign survives sensitivity | $/yr | derived (D9), tested |
| 𝓘_ab | interaction V({a,b}) − V({a}) − V({b}) | $/yr | derived (D9), tested |

## Standing assumptions (each one is tested or swept)

1. Poisson external arrivals (tested: it held in D1's data checks; re-test per dataset).
2. Service times exponential unless measured cv says otherwise, then Kingman-corrected (C-001).
3. FIFO discipline, infinite buffers.
4. Open network: all work eventually leaves (guardrail rejects trapping routing).
5. Steady state: every station ρ < 1 (guardrail; unstable inputs raise, never return numbers).
6. Demand per cycle approximately normal; lumpy/intermittent SKUs go to the D6 treatment instead.
7. Cost inputs are the weakest layer: every assumed or interviewed cost gets a sensitivity sweep and the report states the flip points.
