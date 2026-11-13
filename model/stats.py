"""
stats.py — the statistical tests this project uses, and nothing else.

The study behind these choices is docs/STATS_STUDY.md. Summary of the
decisions it defends:

  * VALIDATION (is the model's prediction right?) uses TOST equivalence
    testing on batch means, pre-registered margin ±5% relative for exact
    theory, alpha = 0.05. A plain t-test has the wrong shape for
    validation: failing to reject "model == simulation" is weak evidence
    (low power makes it easy to pass), while with enough data it flags
    meaninglessly tiny differences. TOST flips the burden of proof: the
    null hypothesis is "the difference is AT LEAST the margin", so a
    small p-value is positive evidence the model is within the margin.
  * INPUT CHECKS on real data (are arrivals Poisson? are gaps
    exponential?) use a chi-square goodness-of-fit test for counts and a
    parametric-bootstrap Kolmogorov-Smirnov test for gaps. The bootstrap
    (Lilliefors-style) is required because fitting the rate from the
    same data makes the textbook KS p-value too forgiving.

Every routine here is cross-checked in tests/run_verification.py against
an independent formulation (TOST vs. the 90%-confidence-interval
criterion, which is mathematically the same decision; scipy's t
quantiles vs. the hard-coded table in simulation/des.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as sp


# ---------------------------------------------------------------- TOST

@dataclass(frozen=True)
class TostResult:
    diff: float          # estimate - target
    rel_diff: float      # diff / target (0 if target == 0)
    margin: float        # absolute equivalence margin used
    se: float
    df: int
    p_value: float       # max of the two one-sided p-values
    equivalent: bool     # p_value < alpha
    alpha: float


def tost_one_sample(mean: float, se: float, df: int, target: float,
                    margin: float, alpha: float = 0.05) -> TostResult:
    """Two One-Sided Tests for equivalence of a single estimated mean
    against a fixed theoretical target.

    H0: |mean_true - target| >= margin   (not equivalent)
    HA: |mean_true - target| <  margin   (equivalent)

    Test 1: H0a: d <= -margin  vs  d > -margin  ->  t1 = (d + m)/se,
            p1 = P(T_df >= t1)
    Test 2: H0b: d >= +margin  vs  d < +margin  ->  t2 = (d - m)/se,
            p2 = P(T_df <= t2)
    TOST p = max(p1, p2); equivalence is claimed iff p < alpha, which is
    identical to the (1 - 2*alpha) CI lying entirely inside ±margin.
    """
    if se <= 0 or df < 1 or margin <= 0:
        raise ValueError("se and margin must be > 0, df >= 1")
    d = mean - target
    t1 = (d + margin) / se
    t2 = (d - margin) / se
    p1 = float(sp.t.sf(t1, df))
    p2 = float(sp.t.cdf(t2, df))
    p = max(p1, p2)
    return TostResult(
        diff=d,
        rel_diff=d / target if target != 0 else 0.0,
        margin=margin,
        se=se,
        df=df,
        p_value=p,
        equivalent=p < alpha,
        alpha=alpha,
    )


def tost_ci_criterion(mean: float, se: float, df: int, target: float,
                      margin: float, alpha: float = 0.05) -> bool:
    """Independent formulation of the same decision: equivalence holds
    iff the (1 - 2 alpha) two-sided CI for the mean lies inside
    [target - margin, target + margin]. Exists for cross-checking."""
    t = float(sp.t.ppf(1 - alpha, df))
    lo, hi = mean - t * se, mean + t * se
    return (target - margin) < lo and hi < (target + margin)


# ---------------------------------------------------------------- KS (gaps)

@dataclass(frozen=True)
class KsResult:
    statistic: float
    p_value: float
    n: int
    n_boot: int


def ks_exponential(gaps: np.ndarray, n_boot: int = 499, seed: int = 0) -> KsResult:
    """Are these inter-arrival gaps exponential? Parametric-bootstrap KS.

    The rate is estimated from the data (1/mean), which shrinks the KS
    statistic and makes the textbook p-value too forgiving. Remedy:
    simulate n_boot datasets from the FITTED exponential, refit on each,
    and use the bootstrap distribution of the KS statistic for the
    p-value (Lilliefors' approach, by simulation).
    """
    gaps = np.asarray(gaps, dtype=float)
    gaps = gaps[gaps >= 0]
    n = len(gaps)
    if n < 20:
        raise ValueError("need at least 20 gaps")
    rate = 1.0 / gaps.mean()
    d_obs = float(sp.kstest(gaps, "expon", args=(0, 1.0 / rate)).statistic)
    rng = np.random.default_rng(seed)
    d_boot = np.empty(n_boot)
    for b in range(n_boot):
        x = rng.exponential(1.0 / rate, n)
        d_boot[b] = sp.kstest(x, "expon", args=(0, x.mean())).statistic
    p = float((np.sum(d_boot >= d_obs) + 1) / (n_boot + 1))
    return KsResult(statistic=d_obs, p_value=p, n=n, n_boot=n_boot)


# ---------------------------------------------------------------- chi2 (counts)

@dataclass(frozen=True)
class Chi2Result:
    statistic: float
    df: int
    p_value: float
    n_bins: int


def chi2_poisson(counts: np.ndarray, min_expected: float = 5.0) -> Chi2Result:
    """Are these per-period counts Poisson? Chi-square goodness of fit.

    Expected frequencies come from a Poisson with the sample mean; tail
    bins are merged until every expected frequency is at least
    min_expected (the standard validity condition); degrees of freedom
    lose one for the total and one for the estimated mean.
    """
    counts = np.asarray(counts, dtype=int)
    n = len(counts)
    if n < 30:
        raise ValueError("need at least 30 periods")
    mean = counts.mean()
    kmax = int(counts.max())
    ks = np.arange(0, kmax + 1)
    probs = sp.poisson.pmf(ks, mean)
    probs = np.append(probs, max(1.0 - probs.sum(), 0.0))  # tail bin k > kmax
    observed = np.bincount(counts, minlength=kmax + 1).astype(float)
    observed = np.append(observed, 0.0)

    # Merge from the right until every expected count clears the floor.
    exp = probs * n
    obs_m, exp_m = [], []
    acc_o = acc_e = 0.0
    for o, e in zip(observed, exp):
        acc_o += o
        acc_e += e
        if acc_e >= min_expected:
            obs_m.append(acc_o)
            exp_m.append(acc_e)
            acc_o = acc_e = 0.0
    if acc_e > 0 and exp_m:
        obs_m[-1] += acc_o
        exp_m[-1] += acc_e
    obs_a, exp_a = np.array(obs_m), np.array(exp_m)
    exp_a *= obs_a.sum() / exp_a.sum()  # renormalize to observed total
    stat = float(((obs_a - exp_a) ** 2 / exp_a).sum())
    dof = len(obs_a) - 1 - 1
    if dof < 1:
        raise ValueError("too few bins after merging; collect more data")
    return Chi2Result(statistic=stat, df=dof,
                      p_value=float(sp.chi2.sf(stat, dof)), n_bins=len(obs_a))
