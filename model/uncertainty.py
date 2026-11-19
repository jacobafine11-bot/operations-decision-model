"""
uncertainty.py — changelog C-011: how sure is each prediction, given how
much data its inputs were estimated from?

Why this exists (benchmark, CHANGELOG C-010): near capacity a 1% error in
an estimated work speed becomes a 15% to 40% error in predicted wait. The
point formula was right (5.7% median error with true inputs); the inputs
were uncertain. A trustworthy model must say so.

Method: parametric Monte Carlo over the sampling error of the estimates.
  * Arrival rate from n arrivals over a span: relative SE 1/sqrt(n)
    (Poisson count).
  * Mean work time at a station from n jobs with variability cv: relative
    SE cv/sqrt(n) (standard error of a mean).
Draw both many times, re-run the model on each draw, and report the
percentile interval. A draw that pushes a station past capacity has no
steady state; it counts as an infinite wait, so the interval's upper end
can honestly be "unbounded". Work-time variability (cv) is held at its
estimate (second-order effect; documented limit).

The interval covers ESTIMATION uncertainty only. It does not cover the
formula's own approximation error (e.g. the known C-010 miss at a steady
downstream crew). The coverage test (analysis/coverage.py) checks
whether that omission matters in practice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

try:
    from . import opsmodel as M
    from .guardrails import ModelError
except ImportError:  # pragma: no cover
    import opsmodel as M  # type: ignore
    from guardrails import ModelError  # type: ignore


# C-012: the formula's own approximation error, as the spread of
# log(predicted / true) station waits with TRUE inputs, measured ONLY on the
# benchmark's development companies (analysis/approx_error.py,
# results/approx_error.json: 60 companies, 147 stations). Mean error was
# about 0 (unbiased); these are the spreads.
APPROX_SD_FIRST = 0.055        # first station: random outside arrivals
APPROX_SD_DOWNSTREAM = 0.115   # later stations: line-variability approximation too


@dataclass(frozen=True)
class Interval:
    point: float
    lo: float
    hi: float          # math.inf when some plausible draws are past capacity
    p_unstable: float  # share of draws where some station is past capacity


@dataclass(frozen=True)
class OperationIntervals:
    waits: tuple       # Interval per station, hours
    total: Interval    # time through the whole operation, hours
    sensitive: tuple   # station names where the 90% range is more than ±25% of the point


def intervals(op: M.Operation, n_jobs: list[int], n_arrivals: int, level: float = 0.90,
              draws: int = 600, seed: int = 0, include_approx: bool = True) -> OperationIntervals:
    """op: the operation built from ESTIMATED inputs.
    n_jobs: jobs observed per station (sample size behind each work speed).
    n_arrivals: arrivals observed (sample size behind the arrival rate).
    include_approx: also include the formula's approximation error (C-012).
    For networks that are not a single line, every station uses the larger
    downstream spread (conservative)."""
    if len(n_jobs) != len(op.stations):
        raise ModelError("need one job count per station")
    if n_arrivals < 2 or min(n_jobs) < 2:
        raise ModelError("need at least 2 observations per estimate")
    base = M.evaluate(op)
    rng = np.random.default_rng(seed)
    k = len(op.stations)
    waits = np.empty((draws, k))
    totals = np.empty(draws)
    unstable = np.zeros(draws, dtype=bool)
    lam_rel = 1.0 / math.sqrt(n_arrivals)
    serial = M.is_serial_line(op)
    approx_sd = np.array([(APPROX_SD_FIRST if (serial and j == 0) else APPROX_SD_DOWNSTREAM)
                          if include_approx else 0.0 for j in range(k)])
    for d in range(draws):
        f_lam = max(1.0 + rng.normal() * lam_rel, 1e-6)
        sts = []
        for st, n in zip(op.stations, n_jobs):
            f_mean = max(1.0 + rng.normal() * st.service_cv / math.sqrt(n), 1e-6)
            sts.append(replace(st, service_rate=st.service_rate / f_mean))
        trial = op.with_changes(stations=tuple(sts),
                                external_arrivals=tuple(g * f_lam for g in op.external_arrivals))
        try:
            b = M.evaluate(trial)
            noise = np.exp(rng.normal(size=k) * approx_sd)
            wq = np.array([r.Wq for r in b.station_results]) * noise
            waits[d] = wq
            totals[d] = float(wq.sum() + sum(r.W - r.Wq for r in b.station_results))
        except ModelError:
            waits[d] = np.inf
            totals[d] = np.inf
            unstable[d] = True
    a = (1 - level) / 2
    q = lambda x: (float(np.quantile(x, a)), float(np.quantile(x, 1 - a)))  # noqa: E731
    w_int = []
    sensitive = []
    for j, (st, r) in enumerate(zip(op.stations, base.station_results)):
        lo, hi = q(waits[:, j])
        w_int.append(Interval(r.Wq, lo, hi, float(unstable.mean())))
        if r.Wq > 0 and (hi == math.inf or max(r.Wq - lo, hi - r.Wq) / r.Wq > 0.25):
            sensitive.append(st.name)
    tlo, thi = q(totals)
    return OperationIntervals(tuple(w_int), Interval(float(sum(r.W for r in base.station_results)),
                                                     tlo, thi, float(unstable.mean())),
                              tuple(sensitive))
