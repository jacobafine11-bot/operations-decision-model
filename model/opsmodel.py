"""
opsmodel.py — the Operations Decision Model engine.

Implements the equation stack E1–E7:

  E1  Traffic equations        lambda = (I - P^T)^{-1} gamma
  E2  Station queueing         M/M/1 and M/M/c (Erlang C)
  E3  Inventory (newsvendor)   S* at critical ratio p/(p+h), expected costs
  E4  Coupling                 changes edit theta (service rates, costs, stock)
  E5  Profit rate              Pi(theta) = m X - c_w sum L - sum C_i* - K   [$/hr]
  E6  Value of a change set    V(S) = T (Pi_after - Pi_before) - I(S)      [$/yr]
  E7  Best plan                argmax V(S) subject to install cost <= budget

Conventions (see docs/NOTATION.md):
  * Base time unit is the HOUR unless a name says otherwise. All formulas are
    written so that dimensionless outputs (rho, probabilities, counts in
    system) are identical under any consistent change of time unit; the test
    suite enforces this (tests/test_invariance.py).
  * All money is in dollars. E5 is $/hour; E6 is $/year.
  * Every function validates its inputs and its outputs via guardrails.

Verification: every result in this file is checked three independent ways —
closed form vs. textbook value, vs. a second independent computation
(e.g. Erlang B recursion vs. direct summation; matrix solve vs. fixed-point
iteration), and vs. discrete-event simulation (simulation/des.py) with
confidence intervals. See tests/ and docs/VERIFICATION_REPORT.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from itertools import combinations
from typing import Callable, Sequence

import numpy as np

try:  # package-style import first, script-style fallback
    from .guardrails import (
        ModelError,
        check_finite_nonnegative,
        check_probability,
        check_throughput,
        require_positive,
        require_stable,
    )
except ImportError:  # pragma: no cover
    from guardrails import (  # type: ignore
        ModelError,
        check_finite_nonnegative,
        check_probability,
        check_throughput,
        require_positive,
        require_stable,
    )


# =====================================================================
# E1 — Traffic equations: the real load on each station
# =====================================================================

def traffic(gamma: Sequence[float], routing: Sequence[Sequence[float]]) -> np.ndarray:
    """Solve lambda = gamma + P^T lambda for the effective arrival rate
    at each station of an open network (orders/hr).

    gamma[j]      external arrivals straight into station j (orders/hr)
    routing[j][k] probability an order leaving station j goes next to k
                  (rows may sum to < 1; the remainder leaves the system)

    Returns lambda as a numpy array. Raises ModelError if the routing
    matrix traps flow (spectral radius >= 1) or produces negative rates.

    Derivation: D3 (queueing networks). Verified against fixed-point
    iteration in tests/test_reduction.py.
    """
    g = np.asarray(gamma, dtype=float)
    P = np.asarray(routing, dtype=float)
    n = g.shape[0]
    if P.shape != (n, n):
        raise ModelError(f"routing must be {n}x{n}, got {P.shape}")
    if (g < 0).any():
        raise ModelError("external arrival rates must be >= 0")
    if (P < 0).any() or (P.sum(axis=1) > 1 + 1e-12).any():
        raise ModelError("routing rows must be >= 0 and sum to <= 1")

    # Spectral radius < 1 guarantees (I - P^T) is invertible and the
    # network is open (all work eventually leaves).
    if n and np.max(np.abs(np.linalg.eigvals(P))) >= 1 - 1e-12:
        raise ModelError("routing matrix traps flow (spectral radius >= 1)")

    lam = np.linalg.solve(np.eye(n) - P.T, g)
    if (lam < -1e-9).any():
        raise ModelError("traffic solution produced a negative rate: check inputs")
    return np.maximum(lam, 0.0)


def traffic_by_iteration(gamma, routing, iters: int = 10_000, tol: float = 1e-12):
    """Second, independent computation of E1 by fixed-point iteration
    lambda_{t+1} = gamma + P^T lambda_t. Exists purely so the test suite
    can cross-check the matrix solve against a different algorithm."""
    g = np.asarray(gamma, dtype=float)
    P = np.asarray(routing, dtype=float)
    lam = g.copy()
    for _ in range(iters):
        nxt = g + P.T @ lam
        if np.max(np.abs(nxt - lam)) < tol:
            return nxt
        lam = nxt
    return lam


# =====================================================================
# E2 — Station queueing: M/M/1 and M/M/c (Erlang C)
# =====================================================================

@dataclass(frozen=True)
class QueueResult:
    rho: float      # utilization (dimensionless)
    p_wait: float   # probability an arriving order must wait
    Lq: float       # average orders waiting in line
    Wq: float       # average wait in line (hours)
    L: float        # average orders at the station (line + in service)
    W: float        # average time at the station (hours)


def mm1(arrival_rate: float, service_rate: float) -> QueueResult:
    """Single-server queue with Poisson arrivals and exponential service.

    Closed forms (derivation D2, from the birth-death balance equations):
        rho = lam/mu,  L = rho/(1-rho),  W = 1/(mu-lam),
        Lq = rho^2/(1-rho),  Wq = rho/(mu-lam),  P(wait) = rho.
    """
    require_positive("arrival_rate", arrival_rate)
    require_positive("service_rate", service_rate)
    rho = arrival_rate / service_rate
    require_stable(rho, "M/M/1 station")
    L = rho / (1 - rho)
    W = 1.0 / (service_rate - arrival_rate)
    Lq = rho * rho / (1 - rho)
    Wq = rho / (service_rate - arrival_rate)
    return QueueResult(
        rho=rho,
        p_wait=check_probability("P(wait)", rho),
        Lq=check_finite_nonnegative("Lq", Lq),
        Wq=check_finite_nonnegative("Wq", Wq),
        L=check_finite_nonnegative("L", L),
        W=check_finite_nonnegative("W", W),
    )


def erlang_b(servers: int, offered_load: float) -> float:
    """Erlang B blocking probability via the numerically stable recursion
        B(0) = 1,  B(k) = a B(k-1) / (k + a B(k-1)).
    Used as the stepping stone to Erlang C, and as the second independent
    route to P(wait) (the first being the direct summation below).
    """
    if servers < 0:
        raise ModelError("servers must be >= 0")
    require_positive("offered_load", offered_load)
    b = 1.0
    for k in range(1, servers + 1):
        b = offered_load * b / (k + offered_load * b)
    return check_probability("ErlangB", b)


def erlang_c_direct(servers: int, offered_load: float) -> float:
    """Erlang C by direct summation of the defining formula:
        C = [a^c / (c! (1-rho))] / [ sum_{k<c} a^k/k! + a^c/(c!(1-rho)) ].
    Terms are built multiplicatively to avoid factorial overflow.
    Independent of erlang_c() below on purpose, for cross-checking.
    """
    a = offered_load
    c = servers
    rho = a / c
    require_stable(rho, "M/M/c station")
    term = 1.0           # a^k / k!, starting at k=0
    s = 0.0
    for k in range(c):
        s += term
        term *= a / (k + 1)
    tail = term / (1 - rho)   # a^c/c! / (1-rho)
    return check_probability("ErlangC", tail / (s + tail))


def erlang_c(servers: int, offered_load: float) -> float:
    """Erlang C probability of waiting, computed from Erlang B:
        C = B / (1 - rho (1 - B)),  rho = a/c.
    Numerically stable for large c. Cross-checked against
    erlang_c_direct() in the test suite.
    """
    if servers < 1:
        raise ModelError("servers must be >= 1")
    a = offered_load
    c = servers
    rho = a / c
    require_stable(rho, "M/M/c station")
    b = erlang_b(c, a)
    return check_probability("ErlangC", b / (1 - rho * (1 - b)))


def mmc(arrival_rate: float, service_rate: float, servers: int,
        service_cv: float = 1.0) -> QueueResult:
    """Multi-server queue: a crew of `servers` workers, each working at
    `service_rate` (orders/hr), shared FIFO line, Poisson arrivals.

    service_cv is the coefficient of variation of service times,
    measured from data by pipeline/estimate.py. The waiting time carries
    the variability factor (Ca^2 + Cs^2)/2 with Ca = 1 (Poisson):

        Wq = [C / (c mu - lam)] * (1 + Cs^2) / 2

    Status of that factor (changelog C-001/C-004):
      * servers == 1: EXACT. It is the Pollaczek-Khinchine formula for
        M/G/1, since lam E[S^2]/(2(1-rho)) = Wq_MM1 * (1 + Cs^2)/2.
      * servers > 1: the Allen-Cunneen/Kingman approximation; verified
        against simulation within ~5-12% in the suite, labeled as an
        approximation in every report.
      * service_cv == 1 reduces exactly to M/M/c (asserted in tests).
    p_wait stays the Erlang C value: exact at cv = 1, an approximation
    otherwise. Derivations: D2, D4, C-001.
    """
    require_positive("arrival_rate", arrival_rate)
    require_positive("service_rate", service_rate)
    require_positive("service_cv", service_cv)
    if servers < 1:
        raise ModelError("servers must be >= 1")
    a = arrival_rate / service_rate            # offered load (dimensionless)
    rho = a / servers
    require_stable(rho, f"M/M/{servers} station")
    C = erlang_c(servers, a)
    variability = (1.0 + service_cv ** 2) / 2.0
    Wq = C / (servers * service_rate - arrival_rate) * variability
    Lq = arrival_rate * Wq
    W = Wq + 1.0 / service_rate
    L = arrival_rate * W
    return QueueResult(
        rho=rho,
        p_wait=C,
        Lq=check_finite_nonnegative("Lq", Lq),
        Wq=check_finite_nonnegative("Wq", Wq),
        L=check_finite_nonnegative("L", L),
        W=check_finite_nonnegative("W", W),
    )


# ---------------------------------------------------------------------
# E2b — Erlang A (M/M/c+M): customers who give up while waiting
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class AbandonResult:
    p_wait: float        # probability an arrival finds all servers busy
    p_abandon: float     # probability an arrival gives up before service
    Lq: float            # average number waiting
    Wq_all: float        # average time in queue over ALL arrivals (hours),
                         # counting abandoners' time until they leave
    L_busy: float        # average number of busy servers
    throughput: float    # served per hour = lam (1 - p_abandon)


def erlang_a(arrival_rate: float, service_rate: float, servers: int,
             abandon_rate: float) -> AbandonResult:
    """M/M/c+M (Palm's model, 'Erlang A'). Each waiting customer gives up
    after an exponential patience with rate theta = abandon_rate (/hr).

    State k = number in system. Birth rate lam; death rate
        k mu                    for k <= c
        c mu + (k - c) theta    for k >  c
    so the chain is stable for ANY load when theta > 0 (impatient
    customers keep the line finite). Stationary probabilities follow from
    detailed balance pi_{k+1} = pi_k lam / death(k+1); the infinite tail is
    summed until terms fall below 1e-16 of the running total (truncation
    error is bounded by the geometric tail and is far below test tolerance).

    Outputs via Little's law: Wq_all = Lq / lam; and since each waiting
    customer abandons at rate theta, the abandonment flow is theta Lq,
    giving P(abandon) = theta Lq / lam.

    theta == 0 is exactly Erlang C (delegated to mmc, which enforces
    rho < 1). Derivation: changelog C-006; verified against Erlang C
    (theta -> 0), the theta == mu Poisson identity, and an independent
    abandonment simulation (tests/run_verification.py).
    """
    require_positive("arrival_rate", arrival_rate)
    require_positive("service_rate", service_rate)
    if servers < 1:
        raise ModelError("servers must be >= 1")
    if abandon_rate < 0:
        raise ModelError("abandon_rate must be >= 0")
    if abandon_rate == 0:
        r = mmc(arrival_rate, service_rate, servers)
        return AbandonResult(r.p_wait, 0.0, r.Lq, r.Wq,
                             arrival_rate / service_rate, arrival_rate)

    lam, mu, c, th = arrival_rate, service_rate, servers, abandon_rate
    # Work in log space to avoid overflow at large loads.
    logs = [0.0]
    k = 0
    while True:
        k += 1
        death = k * mu if k <= c else c * mu + (k - c) * th
        logs.append(logs[-1] + math.log(lam) - math.log(death))
        # Past the mode (ratio < 1) and negligible: stop.
        if k > c and lam < death and logs[-1] - max(logs) < math.log(1e-16):
            break
        if k > 10_000_000:  # pragma: no cover - would need absurd inputs
            raise ModelError("Erlang A tail did not converge")
    m = max(logs)
    w = np.exp(np.array(logs) - m)
    pi = w / w.sum()
    ks = np.arange(len(pi))
    p_wait = float(pi[ks >= c].sum())
    Lq = float(((ks - c).clip(min=0) * pi).sum())
    busy = float((np.minimum(ks, c) * pi).sum())
    p_ab = th * Lq / lam
    return AbandonResult(
        p_wait=check_probability("P(wait)", p_wait),
        p_abandon=check_probability("P(abandon)", p_ab),
        Lq=check_finite_nonnegative("Lq", Lq),
        Wq_all=check_finite_nonnegative("Wq_all", Lq / lam),
        L_busy=check_finite_nonnegative("busy servers", busy),
        throughput=lam * (1 - p_ab),
    )


# =====================================================================
# E3 — Inventory: newsvendor with normal demand
# =====================================================================

_SQRT2 = math.sqrt(2.0)
_SQRT2PI = math.sqrt(2.0 * math.pi)


def _phi(z: float) -> float:
    """Standard normal pdf."""
    return math.exp(-0.5 * z * z) / _SQRT2PI


def _Phi(z: float) -> float:
    """Standard normal cdf via erf (no external dependency)."""
    return 0.5 * (1.0 + math.erf(z / _SQRT2))


def _Phi_inv(p: float, tol: float = 1e-12) -> float:
    """Inverse standard normal cdf by bisection on [-12, 12].

    Bisection is deliberately chosen over a rational approximation:
    it is slower but transparently correct, and inverse-cdf calls are
    not on any hot path. Verified against scipy in development and
    against round-tripping _Phi in the test suite.
    """
    p = check_probability("Phi_inv argument", p)
    if p <= 0.0:
        return -12.0
    if p >= 1.0:
        return 12.0
    lo, hi = -12.0, 12.0
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if _Phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def normal_loss(z: float) -> float:
    """Standard normal loss function  G(z) = phi(z) - z (1 - Phi(z)) =
    E[(Z - z)^+].  Building block for expected shortage. Derivation: D5."""
    return _phi(z) - z * (1.0 - _Phi(z))


@dataclass(frozen=True)
class InventoryResult:
    S_star: float          # optimal order-up-to level (units)
    critical_ratio: float  # p/(p+h)
    expected_shortage: float  # E[(D - S)^+] per cycle (units)
    expected_excess: float    # E[(S - D)^+] per cycle (units)
    cost_per_cycle: float     # h*excess + p*shortage ($)
    fill_rate: float          # fraction of demand met from stock


def newsvendor_normal(mean: float, sd: float, underage_cost: float,
                      overage_cost: float, S: float | None = None) -> InventoryResult:
    """Newsvendor with Normal(mean, sd) demand per cycle.

    underage_cost p: $ lost per unit short (stockout)
    overage_cost  h: $ per unit left over (holding)
    S: evaluate at this stock level; default is the optimum
       S* = mean + sd * Phi^{-1}(p / (p + h))     (derivation D5)

    Expected shortage = sd * G(z),  z = (S - mean)/sd.
    Expected excess   = S - mean + expected shortage   (identity
      E[(S-D)^+] = S - E[D] + E[(D-S)^+], exact for any distribution).
    """
    require_positive("sd", sd)
    require_positive("underage_cost", underage_cost)
    require_positive("overage_cost", overage_cost)
    cr = underage_cost / (underage_cost + overage_cost)
    if S is None:
        S = mean + sd * _Phi_inv(cr)
    z = (S - mean) / sd
    shortage = sd * normal_loss(z)
    excess = S - mean + shortage
    cost = overage_cost * excess + underage_cost * shortage
    fill = 1.0 - shortage / mean if mean > 0 else 1.0
    return InventoryResult(
        S_star=S,
        critical_ratio=check_probability("critical ratio", cr),
        expected_shortage=check_finite_nonnegative("E[shortage]", shortage),
        expected_excess=check_finite_nonnegative("E[excess]", excess),
        cost_per_cycle=check_finite_nonnegative("inventory cost", cost),
        fill_rate=check_probability("fill rate", max(fill, 0.0)),
    )


# =====================================================================
# E4/E5 — The operation and its profit rate
# =====================================================================

@dataclass(frozen=True)
class Station:
    name: str
    service_rate: float   # orders/hr per worker (mu)
    servers: int = 1      # crew size (c)
    service_cv: float = 1.0  # coefficient of variation of service times
                             # (measured by pipeline/estimate.py; 1.0 =
                             # exponential; C-004 correction applies it)


@dataclass(frozen=True)
class Product:
    name: str
    demand_mean: float    # units per replenishment cycle
    demand_sd: float
    underage_cost: float  # $/unit short per cycle
    overage_cost: float   # $/unit held per cycle
    cycles_per_year: float = 52.0


@dataclass(frozen=True)
class Operation:
    """theta: the full parameter set describing one version of the operation."""
    stations: tuple[Station, ...]
    external_arrivals: tuple[float, ...]        # gamma (orders/hr)
    routing: tuple[tuple[float, ...], ...]      # P
    products: tuple[Product, ...] = ()
    margin: float = 0.0        # m, $ earned per shipped order
    waiting_cost: float = 0.0  # c_w, $ per order-hour spent in the system
    hourly_overhead: float = 0.0   # K, $/hr staff + equipment in theta
    demand_rate: float | None = None  # customer demand (orders/hr); default: total external arrivals
    rho_max: float = 0.95      # sustainable utilization cap used in X
    hours_per_year: float = 2000.0

    def with_changes(self, **kw) -> "Operation":
        return replace(self, **kw)


@dataclass(frozen=True)
class ProfitBreakdown:
    profit_per_hour: float
    throughput: float            # X, orders/hr
    revenue_per_hour: float
    waiting_cost_per_hour: float
    inventory_cost_per_hour: float
    overhead_per_hour: float
    station_results: tuple      # QueueResult per station
    loads: tuple                # lambda_j per station
    bottleneck: str             # name of the highest-utilization station


def evaluate(op: Operation) -> ProfitBreakdown:
    """E5. Price the whole operation in $/hour.

        Pi(theta) = m X - c_w sum_j L_j - sum_i C_i*/hours_per_cycle - K

        X = min(demand, rho_max * min_j c_j mu_j_effective_capacity)

    Inventory cost per cycle is converted to $/hr through cycles_per_year
    and hours_per_year so every term shares the unit $/hr.

    Guardrails: every station must be stable at its routed load; X may
    exceed neither demand nor bottleneck capacity.
    """
    lam = traffic(op.external_arrivals, op.routing)
    results = []
    for st, l in zip(op.stations, lam):
        if l <= 0:
            # Station sees no load: contributes nothing, trivially stable.
            results.append(QueueResult(0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
            continue
        results.append(mmc(l, st.service_rate, st.servers, st.service_cv))

    demand = op.demand_rate if op.demand_rate is not None else float(np.sum(op.external_arrivals))
    capacity = min(
        (op.rho_max * st.servers * st.service_rate / max(l_rel, 1e-15)
         for st, l_rel in zip(op.stations, _relative_load(lam, op))),
        default=float("inf"),
    )
    X = check_throughput(min(demand, capacity), demand, capacity)

    revenue = op.margin * X
    waiting = op.waiting_cost * sum(r.L for r in results)
    inv_hr = 0.0
    for p in op.products:
        r = newsvendor_normal(p.demand_mean, p.demand_sd, p.underage_cost, p.overage_cost)
        inv_hr += r.cost_per_cycle * p.cycles_per_year / op.hours_per_year
    pi = revenue - waiting - inv_hr - op.hourly_overhead

    utils = [r.rho for r in results]
    bottleneck = op.stations[int(np.argmax(utils))].name if utils else ""
    return ProfitBreakdown(
        profit_per_hour=pi,
        throughput=X,
        revenue_per_hour=revenue,
        waiting_cost_per_hour=waiting,
        inventory_cost_per_hour=inv_hr,
        overhead_per_hour=op.hourly_overhead,
        station_results=tuple(results),
        loads=tuple(float(x) for x in lam),
        bottleneck=bottleneck,
    )


def _relative_load(lam: np.ndarray, op: Operation) -> np.ndarray:
    """Load per unit of total external input, used to scale bottleneck
    capacity back to the external-order rate (visit ratios)."""
    total_in = float(np.sum(op.external_arrivals))
    if total_in <= 0:
        raise ModelError("operation has no external arrivals")
    return lam / total_in


# =====================================================================
# E6/E7 — Valuing changes and choosing the best affordable set
# =====================================================================

@dataclass(frozen=True)
class Change:
    """A named edit to theta, with its cost to put in place.

    apply: Operation -> Operation (pure function, never mutates)
    install_cost: one-time $ cost
    annual_cost: recurring $/yr (maintenance, subscription)
    amortize_years: years over which install_cost is spread in V(S)
    """
    name: str
    apply: Callable[[Operation], Operation]
    install_cost: float = 0.0
    annual_cost: float = 0.0
    amortize_years: float = 5.0

    @property
    def annualized_cost(self) -> float:
        yrs = max(self.amortize_years, 1e-9)
        return self.install_cost / yrs + self.annual_cost


@dataclass(frozen=True)
class ChangeValue:
    names: tuple[str, ...]
    value_per_year: float       # V(S), $/yr, net of annualized change costs
    gross_savings_per_year: float
    annualized_cost: float
    benefit_cost_ratio: float   # gross savings / annualized cost (inf if free)
    payback_years: float        # install cost / gross annual savings (inf if none)
    pi_before: float
    pi_after: float


def apply_changes(op: Operation, changes: Sequence[Change]) -> Operation:
    out = op
    for ch in changes:
        out = ch.apply(out)
    return out


def value_of_changes(op: Operation, changes: Sequence[Change]) -> ChangeValue:
    """E6. V(S) = T (Pi(theta_S) - Pi(theta)) - annualized cost of S.

    T is hours_per_year, converting $/hr to $/yr. The decision rule:
    do the set S only if V(S) > 0 and the sign survives sensitivity
    analysis on the cost inputs (see sensitivity())."""
    before = evaluate(op)
    after = evaluate(apply_changes(op, changes))
    T = op.hours_per_year
    gross = T * (after.profit_per_hour - before.profit_per_hour)
    cost = sum(ch.annualized_cost for ch in changes)
    install_total = sum(ch.install_cost for ch in changes)
    ratio = gross / cost if cost > 0 else math.inf
    payback = install_total / gross if gross > 0 else math.inf
    return ChangeValue(
        names=tuple(ch.name for ch in changes),
        value_per_year=gross - cost,
        gross_savings_per_year=gross,
        annualized_cost=cost,
        benefit_cost_ratio=ratio,
        payback_years=payback,
        pi_before=before.profit_per_hour,
        pi_after=after.profit_per_hour,
    )


def interaction(op: Operation, a: Change, b: Change) -> float:
    """I_ab = V({a,b}) - V({a}) - V({b}).
    Positive: complements (worth more together).
    Negative: substitutes (they overlap; buying both wastes money)."""
    vab = value_of_changes(op, [a, b]).value_per_year
    va = value_of_changes(op, [a]).value_per_year
    vb = value_of_changes(op, [b]).value_per_year
    return vab - va - vb


def best_plan(op: Operation, candidates: Sequence[Change],
              budget: float = math.inf, max_set_size: int | None = None
              ) -> tuple[ChangeValue, list[ChangeValue]]:
    """E7. Enumerate every subset of candidates whose total install cost
    fits the budget; return the subset with the highest V(S), plus the
    full ranked list (descending V). The empty set ("do nothing",
    V = 0) is always a candidate, so a negative-value plan never wins.

    Exhaustive enumeration is exact and fine for the small-operation
    scale this model targets (<= ~15 candidate changes)."""
    k_max = len(candidates) if max_set_size is None else max_set_size
    ranked: list[ChangeValue] = []
    empty = ChangeValue((), 0.0, 0.0, 0.0, math.inf, math.inf,
                        evaluate(op).profit_per_hour, evaluate(op).profit_per_hour)
    ranked.append(empty)
    for k in range(1, k_max + 1):
        for subset in combinations(candidates, k):
            if sum(c.install_cost for c in subset) > budget:
                continue
            try:
                ranked.append(value_of_changes(op, subset))
            except ModelError:
                # A subset that destabilizes the network is not a valid plan.
                continue
    ranked.sort(key=lambda cv: cv.value_per_year, reverse=True)
    return ranked[0], ranked


def sensitivity(op: Operation, changes_a: Sequence[Change],
                changes_b: Sequence[Change], param: str,
                lo: float, hi: float, steps: int = 200) -> float | None:
    """Find where the ranking between two plans flips as one Operation
    parameter (e.g. 'waiting_cost') sweeps [lo, hi]. Returns the flip
    point, or None if one plan wins over the whole range.

    This is the honest-reporting tool: 'A beats B unless waiting cost
    exceeds $X per order-hour'."""
    prev_sign = None
    prev_x = None
    for i in range(steps + 1):
        x = lo + (hi - lo) * i / steps
        trial = op.with_changes(**{param: x})
        diff = (value_of_changes(trial, changes_a).value_per_year
                - value_of_changes(trial, changes_b).value_per_year)
        sign = diff > 0
        if prev_sign is not None and sign != prev_sign:
            # Bisect between prev_x and x for a tighter answer.
            a, b = prev_x, x
            for _ in range(60):
                mid = 0.5 * (a + b)
                t = op.with_changes(**{param: mid})
                d = (value_of_changes(t, changes_a).value_per_year
                     - value_of_changes(t, changes_b).value_per_year)
                if (d > 0) == prev_sign:
                    a = mid
                else:
                    b = mid
            return 0.5 * (a + b)
        prev_sign, prev_x = sign, x
    return None
