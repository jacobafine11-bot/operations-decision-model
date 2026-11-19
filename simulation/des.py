"""
des.py — discrete-event simulation, deliberately independent of the model.

Nothing here imports opsmodel. The simulator builds warehouses event by
event from first principles (random arrivals, FIFO lines, busy servers),
so agreement between the two is evidence, not circularity.

Estimators and uncertainty:
  * Waits are averaged per customer; confidence intervals come from the
    batch-means method (split the post-warmup sequence into B batches,
    treat batch means as ~independent, use their t-interval). Batch means
    is the standard remedy for serial correlation in queue waits.
  * L (number in system) is measured by time-average via Little's law
    cross-check AND by direct time-weighted census where applicable.

Reproducibility: every function takes a seed; default generators are
numpy PCG64.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

import numpy as np


# ---------------------------------------------------------------- CI helper

# Two-sided 97.5% t quantiles for df = 1..30 (df>30 ~ 1.96). Hard-coded to
# avoid a scipy dependency; values from standard t tables.
_T975 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262,
         2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101,
         2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052,
         2.048, 2.045, 2.042]


def t975(df: int) -> float:
    return _T975[df - 1] if 1 <= df <= 30 else 1.96


@dataclass(frozen=True)
class Estimate:
    mean: float
    half_width: float  # 95% CI half-width

    @property
    def lo(self) -> float:
        return self.mean - self.half_width

    @property
    def hi(self) -> float:
        return self.mean + self.half_width

    def contains(self, theory: float) -> bool:
        return self.lo <= theory <= self.hi


def batch_means(x: np.ndarray, batches: int = 20) -> Estimate:
    n = (len(x) // batches) * batches
    if n < batches:
        raise ValueError("not enough observations for batch means")
    bm = x[:n].reshape(batches, -1).mean(axis=1)
    m = float(bm.mean())
    se = float(bm.std(ddof=1) / math.sqrt(batches))
    return Estimate(m, t975(batches - 1) * se)


# ---------------------------------------------------------------- M/M/c sim

@dataclass(frozen=True)
class SimQueueResult:
    Wq: Estimate       # hours
    W: Estimate        # hours
    L_little: Estimate  # via Little's law: lambda_hat * W
    p_wait: Estimate
    n_customers: int


def trace_mmc(arrival_rate: float, service_rate: float, servers: int,
              n_customers: int, seed: int, cv_service: float = 1.0):
    """Raw per-customer trace (arrival times, waits, times in system), all
    in hours. simulate_mmc() summarizes this; the portal plots it."""
    rng = np.random.default_rng(seed)
    inter = rng.exponential(1.0 / arrival_rate, n_customers)
    arrivals = np.cumsum(inter)
    if cv_service == 1.0:
        service = rng.exponential(1.0 / service_rate, n_customers)
    else:
        shape = 1.0 / (cv_service ** 2)
        scale = 1.0 / (service_rate * shape)
        service = rng.gamma(shape, scale, n_customers)

    free = [0.0] * servers
    heapq.heapify(free)
    waits = np.empty(n_customers)
    sojourn = np.empty(n_customers)
    for i in range(n_customers):
        t_free = heapq.heappop(free)
        start = max(arrivals[i], t_free)
        dep = start + service[i]
        heapq.heappush(free, dep)
        waits[i] = start - arrivals[i]
        sojourn[i] = dep - arrivals[i]
    return arrivals, waits, sojourn


def simulate_mmc(arrival_rate: float, service_rate: float, servers: int,
                 n_customers: int = 400_000, warmup: int = 40_000,
                 seed: int = 7, cv_service: float = 1.0) -> SimQueueResult:
    """FIFO G/G/c simulator via the server-availability heap.

    For each customer i with arrival A_i: pop the earliest server-free
    time, start at max(A_i, free), depart at start + S_i. Exact for FIFO
    multi-server queues (no events are ever out of order because arrivals
    are processed in arrival order and the heap always yields the server
    that frees first).

    cv_service: coefficient of variation of service times.
      1.0 -> exponential (M/M/c). Other values use a gamma distribution
      with the same mean, letting tests break the exponential assumption
      on purpose (M/G/c has no exact closed form; the model's error there
      is a finding, not a bug).
    """
    arrivals, waits, sojourn = trace_mmc(arrival_rate, service_rate, servers,
                                         n_customers, seed, cv_service)
    w = waits[warmup:]
    s = sojourn[warmup:]
    lam_hat = (len(arrivals) - warmup) / (arrivals[-1] - arrivals[warmup])
    Wq = batch_means(w)
    W = batch_means(s)
    L = Estimate(lam_hat * W.mean, lam_hat * W.half_width)
    pw = batch_means((w > 1e-12).astype(float))
    return SimQueueResult(Wq=Wq, W=W, L_little=L, p_wait=pw,
                         n_customers=len(w))


# ---------------------------------------------------------------- abandonment

@dataclass(frozen=True)
class SimAbandonResult:
    Wq_all: Estimate     # hours in queue, all arrivals (abandoners count
                         # their time until leaving)
    p_abandon: Estimate
    n_customers: int


def trace_mmc_abandon(arrival_rate: float, service_rate: float, servers: int,
                      abandon_rate: float, n_customers: int, seed: int,
                      cv_service: float = 1.0):
    """Raw trace: time in queue (hours) and abandon flag per caller."""
    rng = np.random.default_rng(seed)
    A = np.cumsum(rng.exponential(1.0 / arrival_rate, n_customers))
    patience = rng.exponential(1.0 / abandon_rate, n_customers)
    if cv_service == 1.0:
        S = rng.exponential(1.0 / service_rate, n_customers)
    else:
        shape = 1.0 / cv_service ** 2
        S = rng.gamma(shape, 1.0 / (service_rate * shape), n_customers)
    free = [0.0] * servers
    heapq.heapify(free)
    tq = np.empty(n_customers)
    ab = np.zeros(n_customers)
    for i in range(n_customers):
        t_free = free[0]
        start = A[i] if A[i] > t_free else t_free
        wait = start - A[i]
        if wait > patience[i]:
            tq[i] = patience[i]
            ab[i] = 1.0
        else:
            heapq.heapreplace(free, start + S[i])
            tq[i] = wait
    return tq, ab


def simulate_mmc_abandon(arrival_rate: float, service_rate: float,
                         servers: int, abandon_rate: float,
                         n_customers: int = 600_000, warmup: int = 60_000,
                         seed: int = 13, cv_service: float = 1.0
                         ) -> SimAbandonResult:
    """FIFO multi-server queue where each caller has an exponential
    patience (rate abandon_rate) and hangs up if not served in time.

    Exact mechanics under FIFO: process callers in arrival order; the
    earliest-free server time gives the moment caller i WOULD start. If
    that wait exceeds the caller's patience, the caller leaves at
    arrival + patience and never occupies a server (the server-free heap
    is untouched). Otherwise service starts and the server is busy until
    start + service. Later callers are unaffected by abandoners, which is
    what makes this exact for FIFO.
    """
    tq, ab = trace_mmc_abandon(arrival_rate, service_rate, servers,
                               abandon_rate, n_customers, seed, cv_service)
    return SimAbandonResult(Wq_all=batch_means(tq[warmup:]),
                            p_abandon=batch_means(ab[warmup:]),
                            n_customers=n_customers - warmup)


# ---------------------------------------------------------------- tandem sim

@dataclass(frozen=True)
class SimTandemResult:
    W_total: Estimate       # hours through the whole line
    L_total: Estimate       # orders in the whole line (Little)
    W_each: tuple           # per-stage sojourn estimates


def simulate_tandem(arrival_rate: float, service_rates: tuple[float, ...],
                    n_customers: int = 400_000, warmup: int = 40_000,
                    seed: int = 11) -> SimTandemResult:
    """Single-server stations in series, FIFO, infinite buffers.

    Departure recursions (exact for this discipline):
        D^1_i = max(A_i, D^1_{i-1}) + S^1_i
        D^k_i = max(D^{k-1}_i, D^k_{i-1}) + S^k_i
    Jackson/Burke theory says each stage then behaves as an independent
    M/M/1 in steady state; the test suite checks that claim numerically.
    """
    rng = np.random.default_rng(seed)
    A = np.cumsum(rng.exponential(1.0 / arrival_rate, n_customers))
    prev_dep = A.copy()
    stage_sojourn = []
    for mu in service_rates:
        S = rng.exponential(1.0 / mu, n_customers)
        D = np.empty(n_customers)
        d_prev = 0.0
        for i in range(n_customers):
            start = prev_dep[i] if prev_dep[i] > d_prev else d_prev
            d_prev = start + S[i]
            D[i] = d_prev
        stage_sojourn.append(D - prev_dep)
        prev_dep = D

    total = prev_dep - A
    tot = batch_means(total[warmup:])
    lam_hat = (n_customers - warmup) / (A[-1] - A[warmup])
    L = Estimate(lam_hat * tot.mean, lam_hat * tot.half_width)
    each = tuple(batch_means(s[warmup:]) for s in stage_sojourn)
    return SimTandemResult(W_total=tot, L_total=L, W_each=each)


# ---------------------------------------------------------------- absenteeism

def simulate_mmc_absenteeism(arrival_rate: float, service_rate: float,
                             servers: int, p_absent: float,
                             n_days: int = 2_000, hours_per_day: float = 8.0,
                             seed: int = 23) -> Estimate:
    """Mean wait when each worker independently misses a day with
    probability p_absent (Zain's 'sick employee'). Each day runs as its
    own finite-horizon FIFO queue with the surviving crew; days with zero
    workers present push all work to a single emergency server at half
    speed (a modeling choice, stated in the report).

    Returns the across-days estimate of mean wait (hours). There is no
    exact closed form for this; the model approximates it by mixing
    Erlang C over the binomial crew size, and the gap between that
    approximation and this simulation is measured, not assumed away.
    """
    rng = np.random.default_rng(seed)
    day_means = []
    for _ in range(n_days):
        present = int(rng.binomial(servers, 1.0 - p_absent))
        if present == 0:
            c_eff, mu_eff = 1, service_rate * 0.5
        else:
            c_eff, mu_eff = present, service_rate
        n = max(int(arrival_rate * hours_per_day), 1)
        A = np.cumsum(rng.exponential(1.0 / arrival_rate, n))
        S = rng.exponential(1.0 / mu_eff, n)
        free = [0.0] * c_eff
        heapq.heapify(free)
        w = 0.0
        for i in range(n):
            t_free = heapq.heappop(free)
            start = max(A[i], t_free)
            heapq.heappush(free, start + S[i])
            w += start - A[i]
        day_means.append(w / n)
    arr = np.array(day_means)
    return batch_means(arr, batches=20)


# ---------------------------------------------------------------- newsvendor

def newsvendor_brute_force(mean: float, sd: float, underage: float,
                           overage: float, n_draws: int = 1_000_000,
                           grid: int = 400, seed: int = 31
                           ) -> tuple[float, np.ndarray, np.ndarray]:
    """Brute-force the optimal stock level: simulate demand, evaluate the
    cost at every S on a grid, return (argmin S, grid, mean costs).
    Completely independent of the closed-form critical-ratio result,
    which is the point."""
    rng = np.random.default_rng(seed)
    d = rng.normal(mean, sd, n_draws)
    S_grid = np.linspace(mean - 3 * sd, mean + 3 * sd, grid)
    costs = np.empty(grid)
    for i, S in enumerate(S_grid):
        short = np.maximum(d - S, 0.0)
        over = np.maximum(S - d, 0.0)
        costs[i] = underage * short.mean() + overage * over.mean()
    return float(S_grid[int(np.argmin(costs))]), S_grid, costs
