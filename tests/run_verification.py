"""
run_verification.py — the full verification suite.

Layer 1: closed form vs. known textbook values (exact arithmetic).
Layer 2: each result vs. a second, independent computation
         (matrix solve vs. iteration; Erlang B recursion vs. direct sum;
          critical ratio vs. brute-force cost minimization).
Layer 3: model vs. discrete-event simulation. Exact formulas are judged
         by TOST equivalence tests (pre-registered margin ±5% relative,
         alpha = 0.05; see docs/STATS_STUDY.md). Approximations are
         judged against their stated tolerance and labeled as
         approximations. Assumption-breaking runs measure where the
         model's assumptions bend; gaps are findings, not failures.
Layer 0 (new): the statistical machinery itself is validated — TOST
         against its independent CI formulation, scipy's t quantiles
         against the hard-coded table, KS and chi-square against data
         that should pass and data that should fail.

Plus unit-invariance tests (hours vs. minutes must agree) and guardrail
tests (invalid inputs must raise, not return numbers).

Writes docs/VERIFICATION_REPORT.md and results/run_record_<date>.json;
exits nonzero on any failure.
"""

from __future__ import annotations

import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "model"))
sys.path.insert(0, str(ROOT / "simulation"))

import numpy as np  # noqa: E402
from scipy import stats as sp  # noqa: E402

import des as D  # noqa: E402
import opsmodel as M  # noqa: E402
import stats as ST  # noqa: E402
from guardrails import ModelError  # noqa: E402

T0 = time.time()
REPORT: list[str] = []
FAILURES: list[str] = []
N_CHECKS = 0

EXACT_MARGIN = 0.05   # pre-registered relative equivalence margin
ALPHA = 0.05
BATCHES = 20          # batch-means batches -> df = 19


def check(name: str, ok: bool, detail: str) -> None:
    global N_CHECKS
    N_CHECKS += 1
    status = "PASS" if ok else "FAIL"
    REPORT.append(f"| {name} | {status} | {detail} |")
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def section(title: str, note: str = "") -> None:
    REPORT.append("")
    REPORT.append(f"### {title}")
    if note:
        REPORT.append("")
        REPORT.append(note)
    REPORT.append("")
    REPORT.append("| Check | Result | Detail |")
    REPORT.append("|---|---|---|")


# =====================================================================
# Layer 0 — validate the statistical machinery itself
# =====================================================================
section("Layer 0: the statistical tests, tested",
        "Before any test is trusted to judge the model, it is judged itself: "
        "against an independent formulation of the same decision, and against "
        "data constructed to pass and data constructed to fail.")

# scipy t quantiles vs. the hard-coded table used by the simulator's CIs.
worst = max(abs(float(sp.t.ppf(0.975, df)) - D.t975(df)) for df in range(1, 31))
check("scipy t(0.975) vs. hard-coded table (df 1-30)", worst < 5e-4,
      f"worst abs diff {worst:.1e}")

# TOST decision vs. the 90%-CI criterion (mathematically identical).
rng = np.random.default_rng(3)
agree = 0
trials = 400
for _ in range(trials):
    mean = rng.normal(1.0, 0.05)
    se = rng.uniform(0.005, 0.05)
    m = rng.uniform(0.01, 0.10)
    t1 = ST.tost_one_sample(mean, se, 19, 1.0, m)
    agree += (t1.equivalent == ST.tost_ci_criterion(mean, se, 19, 1.0, m))
check("TOST decision == 90% CI criterion (400 random cases)", agree == trials,
      f"{agree}/{trials} agreements")

# TOST calibration: when the true difference EQUALS the margin, the
# equivalence claim should fire at ~alpha (here, with known-variance-ish
# large df, close to 5%).
rng = np.random.default_rng(11)
fires = 0
reps = 4000
for _ in range(reps):
    x = rng.normal(1.05, 0.10, 400)          # true diff exactly at margin 0.05
    se = x.std(ddof=1) / math.sqrt(len(x))
    fires += ST.tost_one_sample(x.mean(), se, len(x) - 1, 1.0, 0.05).equivalent
rate = fires / reps
check("TOST type-I rate at the margin ~ alpha", 0.03 < rate < 0.07,
      f"fired {rate:.3f} (target 0.05)")

# KS: true exponential gaps must pass; uniform gaps must fail.
rng = np.random.default_rng(5)
ks_good = ST.ks_exponential(rng.exponential(0.25, 2500), seed=1)
ks_bad = ST.ks_exponential(rng.uniform(0, 0.5, 2500), seed=2)
check("KS passes true exponential gaps", ks_good.p_value > ALPHA,
      f"D={ks_good.statistic:.4f}, p={ks_good.p_value:.3f}")
check("KS rejects uniform gaps", ks_bad.p_value < ALPHA,
      f"D={ks_bad.statistic:.4f}, p={ks_bad.p_value:.3f}")

# Chi-square: Poisson counts must pass; constant counts must fail.
chi_good = ST.chi2_poisson(rng.poisson(6.0, 400))
chi_bad = ST.chi2_poisson(np.full(400, 6))
check("Chi-square passes Poisson counts", chi_good.p_value > ALPHA,
      f"chi2={chi_good.statistic:.2f}, df={chi_good.df}, p={chi_good.p_value:.3f}")
check("Chi-square rejects constant counts", chi_bad.p_value < ALPHA,
      f"chi2={chi_bad.statistic:.2f}, df={chi_bad.df}, p={chi_bad.p_value:.4f}")

# =====================================================================
# Layer 1 — textbook reductions (exact)
# =====================================================================
section("Layer 1: closed form vs. textbook values")

r = M.mm1(2.0, 3.0)
check("M/M/1 rho (lam=2, mu=3)", abs(r.rho - 2 / 3) < 1e-12, f"rho={r.rho:.6f}, expect 0.666667")
check("M/M/1 L", abs(r.L - 2.0) < 1e-12, f"L={r.L:.6f}, expect 2")
check("M/M/1 W", abs(r.W - 1.0) < 1e-12, f"W={r.W:.6f}, expect 1")
check("M/M/1 Lq", abs(r.Lq - 4 / 3) < 1e-12, f"Lq={r.Lq:.6f}, expect 1.333333")
check("M/M/1 Wq", abs(r.Wq - 2 / 3) < 1e-12, f"Wq={r.Wq:.6f}, expect 0.666667")
check("Little's law L = lam W", abs(r.L - 2.0 * r.W) < 1e-12, "internal consistency")
check("Little's law Lq = lam Wq", abs(r.Lq - 2.0 * r.Wq) < 1e-12, "internal consistency")

c_hand = M.erlang_c(3, 2.0)
check("Erlang C (c=3, a=2) = 4/9 (worked by hand in D4)",
      abs(c_hand - 4 / 9) < 1e-12, f"C={c_hand:.9f}")

r1, rc = M.mm1(2.0, 3.0), M.mmc(2.0, 3.0, 1)
ok = all(abs(getattr(r1, f) - getattr(rc, f)) < 1e-12
         for f in ("rho", "p_wait", "Lq", "Wq", "L", "W"))
check("M/M/c (c=1) == M/M/1", ok, "all six outputs identical")

# C-004 reduction: cv = 1 must reproduce plain M/M/c exactly.
ra, rb = M.mmc(10.0, 4.0, 3), M.mmc(10.0, 4.0, 3, service_cv=1.0)
ok = all(abs(getattr(ra, f) - getattr(rb, f)) < 1e-15
         for f in ("rho", "p_wait", "Lq", "Wq", "L", "W"))
check("Kingman factor at cv=1 changes nothing (C-004 reduction)", ok,
      "corrected model collapses to M/M/c exactly")

# C-004 exactness at c=1: the correction equals Pollaczek-Khinchine.
lam_, mu_, cv_ = 4.0, 6.0, 1.5
pk = (lam_ / mu_) / (mu_ - lam_) * (1 + cv_ ** 2) / 2
got = M.mmc(lam_, mu_, 1, service_cv=cv_).Wq
check("M/G/1 correction == Pollaczek-Khinchine (algebra)",
      abs(got - pk) < 1e-12, f"Wq={got:.6f}, PK={pk:.6f}")

# C-009 QNA linking equation: exact limiting cases.
check("QNA: Poisson in + exponential service -> Poisson out (Burke)",
      abs(M.departure_scv(1.0, 1.0, 0.85, 3) - 1.0) < 1e-12,
      f"Cd^2 = {M.departure_scv(1.0, 1.0, 0.85, 3):.12f}")
check("QNA: idle single server passes arrivals through (rho -> 0)",
      abs(M.departure_scv(0.37, 0.5, 0.0, 1) - 0.37) < 1e-12,
      f"Cd^2 = {M.departure_scv(0.37, 0.5, 0.0, 1):.12f}")
check("QNA: saturated single server passes service through (rho -> 1)",
      abs(M.departure_scv(1.9, 0.6, 1.0, 1) - 0.36) < 1e-12,
      f"Cd^2 = {M.departure_scv(1.9, 0.6, 1.0, 1):.12f}")
ra, rb = M.mmc(10.0, 4.0, 3, 0.7), M.mmc(10.0, 4.0, 3, 0.7, arrival_cv=1.0)
check("arrival_cv = 1 changes nothing (C-009 reduction)",
      abs(ra.Wq - rb.Wq) < 1e-15, "identical to the C-004 model")
_net = M.Operation(stations=(M.Station("a", 5.0, 2), M.Station("b", 9.0, 1)),
                   external_arrivals=(4.0, 1.0), routing=((0.0, 1.0), (0.0, 0.0)))
check("Non-serial network keeps random arrivals (documented limit)",
      M.arrival_variability(_net, M.traffic(_net.external_arrivals, _net.routing)) == [1.0, 1.0],
      "outside orders enter two stations, so no propagation is attempted")

# C-006 Erlang A exact identities.
ea, ec = M.erlang_a(10.0, 4.0, 3, 1e-9), M.mmc(10.0, 4.0, 3)
check("Erlang A with theta -> 0 equals Erlang C (C-006)",
      abs(ea.Wq_all - ec.Wq) / ec.Wq < 1e-6,
      f"Wq {ea.Wq_all:.9f} vs {ec.Wq:.9f}")
ea = M.erlang_a(12.0, 3.0, 3, 3.0)   # theta == mu -> N ~ Poisson(lam/mu)
pois = sp.poisson(4.0)
lq_pois = float(sum((k - 3) * pois.pmf(k) for k in range(4, 200)))
check("Erlang A with theta == mu matches Poisson identity (C-006)",
      abs(ea.Lq - lq_pois) < 1e-10, f"Lq {ea.Lq:.12f} vs {lq_pois:.12f}")
check("Erlang A flow balance: busy servers == throughput / mu",
      abs(ea.L_busy - ea.throughput / 3.0) < 1e-10,
      f"{ea.L_busy:.10f} vs {ea.throughput/3.0:.10f}")
ea = M.erlang_a(14.0, 4.0, 3, 3.0)   # overloaded: lam > c mu
check("Erlang A answers an overloaded system (lam > c mu)",
      0 < ea.p_abandon < 1 and math.isfinite(ea.Wq_all),
      f"P(abandon)={ea.p_abandon:.4f}; Erlang C would refuse")

lam = M.traffic([2.0, 0.0], [[0.0, 1.0], [0.0, 0.0]])
L_each = [M.mm1(l, mu).L for l, mu in zip(lam, (3.0, 4.0))]
check("Jackson tandem L_total (2;3,4)", abs(sum(L_each) - 3.0) < 1e-12,
      f"L={sum(L_each):.6f}, expect 3")

inv = M.newsvendor_normal(100.0, 20.0, 5.0, 5.0)
check("Newsvendor symmetric S* = mean", abs(inv.S_star - 100.0) < 1e-6,
      f"S*={inv.S_star:.4f}, expect 100")
check("Normal loss G(0) = 0.398942",
      abs(M.normal_loss(0.0) - 1 / math.sqrt(2 * math.pi)) < 1e-12,
      f"G(0)={M.normal_loss(0.0):.6f}")

# =====================================================================
# Layer 2 — independent second computations
# =====================================================================
section("Layer 2: independent second computations")

gamma = [10.0, 0.0, 2.0]
P = [[0.0, 0.8, 0.0], [0.1, 0.0, 0.7], [0.0, 0.05, 0.0]]
lam_solve = M.traffic(gamma, P)
lam_iter = M.traffic_by_iteration(gamma, P)
diff = float(np.max(np.abs(lam_solve - lam_iter)))
check("E1 solve vs. iteration (rework loop)", diff < 1e-9,
      f"max diff {diff:.2e}; lambda={np.round(lam_solve, 4).tolist()}")

out_flow = float(sum(l * (1 - sum(row)) for l, row in zip(lam_solve, P)))
check("E1 flow conservation", abs(out_flow - sum(gamma)) < 1e-9,
      f"out={out_flow:.6f}, in={sum(gamma):.6f}")

worst = 0.0
for c in (1, 2, 3, 5, 8, 15, 40, 100):
    for rho in (0.3, 0.6, 0.85, 0.95, 0.99):
        a = rho * c
        worst = max(worst, abs(M.erlang_c(c, a) - M.erlang_c_direct(c, a)))
check("Erlang C recursion vs. direct sum (40 cases)", worst < 1e-10,
      f"worst abs diff {worst:.2e}")

worst = max(abs(M._Phi(M._Phi_inv(p)) - p) for p in
            (0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 0.999))
check("Normal inverse cdf round trip", worst < 1e-10, f"worst {worst:.2e}")
worst = max(abs(M._Phi_inv(p) - float(sp.norm.ppf(p))) for p in
            (0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99))
check("Normal inverse cdf vs. scipy", worst < 1e-8, f"worst {worst:.2e}")

t0 = time.time()
S_bf, S_grid, costs = D.newsvendor_brute_force(100.0, 20.0, 9.0, 3.0)
inv = M.newsvendor_normal(100.0, 20.0, 9.0, 3.0)
grid_step = S_grid[1] - S_grid[0]
check("Newsvendor S* vs. brute force (1M draws)",
      abs(S_bf - inv.S_star) <= 3 * grid_step,
      f"closed form {inv.S_star:.2f}, brute force {S_bf:.2f} "
      f"(grid step {grid_step:.2f}, {time.time()-t0:.1f}s)")

i_near = int(np.argmin(np.abs(S_grid - inv.S_star)))
inv_at = M.newsvendor_normal(100.0, 20.0, 9.0, 3.0, S=float(S_grid[i_near]))
rel = abs(costs[i_near] - inv_at.cost_per_cycle) / inv_at.cost_per_cycle
check("Newsvendor expected cost vs. simulated cost", rel < 0.01,
      f"closed form ${inv_at.cost_per_cycle:.2f}, simulated ${costs[i_near]:.2f} "
      f"(rel diff {rel:.3%})")

# =====================================================================
# Layer 3 — model vs. discrete-event simulation
# =====================================================================
SIM_ROWS: list[str] = []      # exact theory: TOST table
APPROX_ROWS: list[str] = []   # approximations: tolerance table


def equiv_check(name: str, theory: float, est: D.Estimate) -> None:
    """Exact theory vs. simulation, judged by TOST at the pre-registered
    ±5% relative margin."""
    se = est.half_width / D.t975(BATCHES - 1)
    res = ST.tost_one_sample(est.mean, se, BATCHES - 1, theory,
                             margin=EXACT_MARGIN * abs(theory), alpha=ALPHA)
    verdict = "equivalent" if res.equivalent else "NOT shown equivalent"
    SIM_ROWS.append(
        f"| {name} | {theory:.5f} | {est.mean:.5f} ± {est.half_width:.5f} "
        f"| ±{EXACT_MARGIN:.0%} | {res.p_value:.2e} | {verdict} |")
    check(f"[sim] {name}", res.equivalent,
          f"theory {theory:.5f}, sim {est.mean:.5f} ± {est.half_width:.5f}, "
          f"rel diff {res.rel_diff:+.2%}, TOST p={res.p_value:.2e}")


def approx_check(name: str, predicted: float, est: D.Estimate,
                 tol: float, basis: str) -> None:
    """Approximation vs. simulation: judged against its stated tolerance
    and labeled as an approximation, never as proven equivalence."""
    rel = abs(est.mean - predicted) / predicted
    ok = rel < tol
    APPROX_ROWS.append(
        f"| {name} | {predicted:.5f} | {est.mean:.5f} ± {est.half_width:.5f} "
        f"| {rel:.1%} | {tol:.0%} | {basis} |")
    check(f"[approx] {name}", ok,
          f"predicted {predicted:.5f}, sim {est.mean:.5f}, rel {rel:.2%} "
          f"(tolerance {tol:.0%})")


# Exact cases: M/M/1, M/M/c, tandem Jackson, and M/G/1 via P-K (C-004).
# Sample sizes scale with utilization: high-rho queues are strongly
# autocorrelated, and TOST needs the 90% CI inside ±5%, which sets a
# power requirement (se below ~2.9% relative). See SIMULATION_METHODS.
for lam_, mu_, n_ in ((2.0, 3.0, 400_000), (9.0, 10.0, 2_500_000)):
    th = M.mm1(lam_, mu_)
    s = D.simulate_mmc(lam_, mu_, 1, seed=int(lam_ * 10),
                       n_customers=n_, warmup=n_ // 10)
    equiv_check(f"M/M/1 Wq (lam={lam_}, mu={mu_})", th.Wq, s.Wq)
    equiv_check(f"M/M/1 L (lam={lam_}, mu={mu_})", th.L, s.L_little)

for lam_, mu_, c_, n_ in ((10.0, 4.0, 3, 400_000), (20.0, 4.0, 6, 1_600_000),
                          (3.0, 4.0, 2, 400_000)):
    th = M.mmc(lam_, mu_, c_)
    s = D.simulate_mmc(lam_, mu_, c_, seed=c_, n_customers=n_, warmup=n_ // 10)
    equiv_check(f"M/M/{c_} Wq (lam={lam_}, mu={mu_})", th.Wq, s.Wq)
    equiv_check(f"M/M/{c_} P(wait)", th.p_wait, s.p_wait)

lam_t, mus = 2.0, (3.0, 4.0, 5.0)
th_W = sum(M.mm1(lam_t, mu).W for mu in mus)
s = D.simulate_tandem(lam_t, mus, seed=5)
equiv_check("Tandem 3-station W_total (Jackson)", th_W, s.W_total)

# M/G/1 with the C-004 correction is EXACT (Pollaczek-Khinchine): test
# it against simulation at high and low variability.
for cv_ in (1.5, 0.5):
    th = M.mmc(4.0, 6.0, 1, service_cv=cv_)
    s = D.simulate_mmc(4.0, 6.0, 1, cv_service=cv_, seed=int(cv_ * 100),
                       n_customers=600_000, warmup=60_000)
    equiv_check(f"M/G/1 Wq, cv={cv_} (P-K exact, C-004)", th.Wq, s.Wq)

# Erlang A (C-006) vs. the independent abandonment simulator, including
# an overloaded system Erlang C cannot describe.
for lam_, mu_, c_, th_ in ((10.0, 4.0, 3, 6.0), (14.0, 4.0, 3, 3.0),
                           (20.0, 3.0, 8, 2.0)):
    th = M.erlang_a(lam_, mu_, c_, th_)
    s = D.simulate_mmc_abandon(lam_, mu_, c_, th_, seed=int(lam_ * 7),
                               n_customers=1_000_000, warmup=100_000)
    equiv_check(f"Erlang A Wq_all (lam={lam_}, mu={mu_}, c={c_}, theta={th_})",
                th.Wq_all, s.Wq_all)
    equiv_check(f"Erlang A P(abandon) (lam={lam_}, c={c_}, theta={th_})",
                th.p_abandon, s.p_abandon)

# Approximations: the multi-server Kingman factor, now the model default.
th = M.mmc(10.0, 4.0, 3, service_cv=0.5)
s_lowvar = D.simulate_mmc(10.0, 4.0, 3, cv_service=0.5, seed=99)
approx_check("M/G/3 Wq, cv=0.5 (Kingman, C-004)", th.Wq, s_lowvar.Wq,
             tol=0.12, basis="Allen-Cunneen/Kingman factor; raw M/M/c was 35% off")
th = M.mmc(10.0, 4.0, 3, service_cv=1.4)
s_hivar = D.simulate_mmc(10.0, 4.0, 3, cv_service=1.4, seed=101,
                         n_customers=600_000, warmup=60_000)
approx_check("M/G/3 Wq, cv=1.4 (Kingman, C-004)", th.Wq, s_hivar.Wq,
             tol=0.12, basis="Allen-Cunneen/Kingman factor, high variability")

# C-009: serial line with non-exponential crews, QNA-corrected model vs.
# event-log simulation (approximation: labeled, held to tolerance).
from eventlog import StationTruth, generate_orders, observed_station_times  # noqa: E402
_sts = [StationTruth("P", 8.0, 3, 0.8), StationTruth("K", 13.0, 2, 0.6),
        StationTruth("L", 30.0, 1, 1.0)]
_op = M.Operation(stations=tuple(M.Station(s.name, s.service_rate, s.workers, s.cv) for s in _sts),
                  external_arrivals=(22.0, 0.0, 0.0),
                  routing=((0, 1, 0), (0, 0, 1), (0, 0, 0)))
_obs = observed_station_times(generate_orders(22.0, _sts, 200_000, 77)).set_index("station")
for _s, _r in zip(_sts, M.evaluate(_op).station_results):
    _o = float(_obs.loc[_s.name, "obs_wait_h"])
    approx_check(f"Serial line wait at {_s.name} (QNA, C-009)", _r.Wq,
                 D.Estimate(_o, 0.0), tol=0.20,
                 basis="QNA linking equation + Kingman; event-log simulation, 200k orders")

# Absenteeism: binomial mixture of Erlang C as the model's approximation.
lam_, mu_, c_, p_abs = 10.0, 4.0, 3, 0.08
mix_th, mass = 0.0, 0.0
for k in range(1, c_ + 1):
    pk_ = math.comb(c_, k) * (1 - p_abs) ** k * p_abs ** (c_ - k)
    try:
        mix_th += pk_ * M.mmc(lam_, mu_, k).Wq
        mass += pk_
    except ModelError:
        pass
s_abs = D.simulate_mmc_absenteeism(lam_, mu_, c_, p_abs, seed=47)
APPROX_ROWS.append(
    f"| Absenteeism 8%, crew of 3 | {mix_th:.5f} (mixture, stable crews = {mass:.0%} of days) "
    f"| {s_abs.mean:.5f} ± {s_abs.half_width:.5f} | {(s_abs.mean-mix_th)/mix_th:+.1%} | finding | "
    f"Mixture understates: short-crew days have no steady state; use simulation for staffing under absence |")

section("Layer 3a: exact theory vs. simulation (TOST equivalence)",
        f"Pre-registered margin ±{EXACT_MARGIN:.0%} relative, alpha = {ALPHA}. "
        "'Equivalent' means the TOST null (difference at least the margin) is "
        "rejected: positive evidence the model is within ±5% of the simulation. "
        "docs/STATS_STUDY.md defends this choice; docs/SIMULATION_METHODS.md "
        "documents how each simulation ran.")
REPORT.pop()  # replace the default check-table header for this section
REPORT.pop()
REPORT.append("| Scenario | Theory | Simulation (95% CI) | Margin | TOST p | Verdict |")
REPORT.append("|---|---|---|---|---|---|")
REPORT.extend(SIM_ROWS)

REPORT.append("")
REPORT.append("**Layer 3b: approximations and findings** (judged against stated "
              "tolerance; never claimed as proven equivalence):")
REPORT.append("")
REPORT.append("| Scenario | Model prediction | Simulation (95% CI) | Gap | Tolerance | Basis |")
REPORT.append("|---|---|---|---|---|---|")
REPORT.extend(APPROX_ROWS)

# =====================================================================
# Unit invariance
# =====================================================================
section("Unit invariance: hours vs. minutes")

th_hr = M.mmc(20.0, 8.0, 3, service_cv=0.7)
th_min = M.mmc(20.0 / 60, 8.0 / 60, 3, service_cv=0.7)
check("rho identical", abs(th_hr.rho - th_min.rho) < 1e-12,
      f"{th_hr.rho:.6f} vs {th_min.rho:.6f}")
check("P(wait) identical", abs(th_hr.p_wait - th_min.p_wait) < 1e-12,
      f"{th_hr.p_wait:.6f} vs {th_min.p_wait:.6f}")
check("L identical (counts are unitless)", abs(th_hr.L - th_min.L) < 1e-9,
      f"{th_hr.L:.6f} vs {th_min.L:.6f}")
check("W converts by exactly 60", abs(th_hr.W * 60 - th_min.W) < 1e-9,
      f"{th_hr.W*60:.6f} min vs {th_min.W:.6f} min")
check("cv is dimensionless (same correction in both unit systems)",
      abs(th_hr.Wq * 60 - th_min.Wq) < 1e-9,
      f"Wq {th_hr.Wq*60:.6f} min vs {th_min.Wq:.6f} min")


def _op(unit_scale: float, hours_per_year: float) -> M.Operation:
    return M.Operation(
        stations=(M.Station("pick", 8.0 * unit_scale, 3, service_cv=0.8),
                  M.Station("pack", 13.0 * unit_scale, 2, service_cv=0.6),
                  M.Station("load", 25.0 * unit_scale, 1, service_cv=1.0)),
        external_arrivals=(20.0 * unit_scale, 0.0, 0.0),
        routing=((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
        products=(M.Product("liners", 500, 120, 6.0, 1.5),),
        margin=9.0,
        waiting_cost=4.0 * unit_scale,
        hourly_overhead=120.0 * unit_scale,
        hours_per_year=hours_per_year,
    )


op_hr = _op(1.0, 2000.0)
op_min = _op(1.0 / 60, 2000.0 * 60)
pi_hr = M.evaluate(op_hr)
pi_min = M.evaluate(op_min)
check("E5 profit: $/hr == 60 x $/min",
      abs(pi_hr.profit_per_hour - 60 * pi_min.profit_per_hour) < 1e-6,
      f"${pi_hr.profit_per_hour:.4f}/hr vs ${60*pi_min.profit_per_hour:.4f}/hr")
check("E5 bottleneck named identically", pi_hr.bottleneck == pi_min.bottleneck,
      f"'{pi_hr.bottleneck}' vs '{pi_min.bottleneck}'")


def _faster_pick(factor: float):
    def apply(op: M.Operation) -> M.Operation:
        from dataclasses import replace as _rep
        sts = list(op.stations)
        sts[0] = _rep(sts[0], service_rate=sts[0].service_rate * factor)
        return op.with_changes(stations=tuple(sts))
    return apply


ch_hr = M.Change("re-slot", _faster_pick(1.25), install_cost=3000.0)
v_hr = M.value_of_changes(op_hr, [ch_hr]).value_per_year
v_min = M.value_of_changes(op_min, [ch_hr]).value_per_year
check("E6 value identical across units", abs(v_hr - v_min) < 1e-4,
      f"${v_hr:,.2f}/yr vs ${v_min:,.2f}/yr")

# =====================================================================
# Decision layer (E5–E7) behavior
# =====================================================================
section("Decision layer: E5–E7 behavior")

base = M.evaluate(op_hr)
check("Bottleneck is picking (highest rho)", base.bottleneck == "pick",
      f"loads {['%.2f' % r.rho for r in base.station_results]}")


def _faster_pack(op: M.Operation) -> M.Operation:
    from dataclasses import replace as _rep
    sts = list(op.stations)
    sts[1] = _rep(sts[1], service_rate=sts[1].service_rate * 1.3)
    return op.with_changes(stations=tuple(sts))


ch_pack = M.Change("faster packing", _faster_pack, install_cost=5000.0)
v_pick = M.value_of_changes(op_hr, [ch_hr])
v_pack = M.value_of_changes(op_hr, [ch_pack])
check("Bottleneck fix beats non-bottleneck fix",
      v_pick.value_per_year > v_pack.value_per_year,
      f"pick ${v_pick.value_per_year:,.0f}/yr vs pack ${v_pack.value_per_year:,.0f}/yr")

best, ranked = M.best_plan(op_hr, [ch_hr, ch_pack], budget=10_000)
check("E7 never ranks below 'do nothing'", best.value_per_year >= 0,
      f"best = {list(best.names) or 'do nothing'} at ${best.value_per_year:,.0f}/yr")

inter = M.interaction(op_hr, ch_hr, ch_pack)
check("Interaction term computed and finite", math.isfinite(inter),
      f"I(pick,pack) = ${inter:,.0f}/yr "
      f"({'complements' if inter > 0 else 'substitutes' if inter < 0 else 'independent'})")

pi_more = M.evaluate(M.apply_changes(op_hr, [ch_hr])).profit_per_hour
check("More bottleneck capacity never lowers Pi",
      pi_more >= base.profit_per_hour - 1e-9,
      f"{base.profit_per_hour:.2f} -> {pi_more:.2f} $/hr")

flip = M.sensitivity(op_hr, [ch_hr], [ch_pack], "waiting_cost", 0.5, 40.0)
check("Sensitivity sweep runs", flip is None or 0.5 <= flip <= 40.0,
      f"flip point: {'none in range' if flip is None else f'${flip:.2f}/order-hr'}")

# =====================================================================
# Guardrails: invalid inputs must raise
# =====================================================================
section("Guardrails: invalid inputs must raise")


def must_raise(name: str, fn):
    try:
        fn()
    except ModelError as e:
        check(name, True, f"raised: {str(e)[:70]}")
    except Exception as e:
        check(name, False, f"raised wrong type {type(e).__name__}: {e}")
    else:
        check(name, False, "returned a number instead of raising")


must_raise("Unstable M/M/1 (lam >= mu)", lambda: M.mm1(5.0, 4.0))
must_raise("Unstable crew (rho >= 1)", lambda: M.mmc(13.0, 4.0, 3))
must_raise("Negative arrival rate", lambda: M.mm1(-1.0, 4.0))
must_raise("Zero or negative service cv", lambda: M.mmc(2.0, 4.0, 1, service_cv=0.0))
must_raise("Routing rows sum > 1", lambda: M.traffic([1.0, 0.0], [[0.6, 0.6], [0.0, 0.0]]))
must_raise("Flow-trapping routing", lambda: M.traffic([1.0, 1.0], [[0.0, 1.0], [1.0, 0.0]]))
must_raise("Zero service rate", lambda: M.mm1(1.0, 0.0))
must_raise("Negative abandonment rate", lambda: M.erlang_a(2.0, 4.0, 1, -1.0))
must_raise("Network with overloaded station",
           lambda: M.evaluate(op_hr.with_changes(external_arrivals=(30.0, 0.0, 0.0))))

# =====================================================================
# Report + run record
# =====================================================================
n_fail = len(FAILURES)
elapsed = time.time() - T0

try:
    git_rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=ROOT, capture_output=True, text=True,
                             timeout=10).stdout.strip() or "no-git"
except Exception:
    git_rev = "no-git"

now = datetime.now(timezone.utc)
header = [
    "# Verification Report",
    "",
    f"Generated by `tests/run_verification.py` on {now:%Y-%m-%d %H:%M UTC} "
    f"(code revision `{git_rev}`, {elapsed:.0f}s wall time). "
    f"**{N_CHECKS - n_fail} / {N_CHECKS} checks passed.**",
    "",
    "Verification layers: (0) the statistical tests themselves are validated "
    "against independent formulations and against data built to pass and to "
    "fail; (1) closed forms against textbook values, exactly; (2) every result "
    "against a second, algorithmically independent computation; (3) the model "
    "against a discrete-event simulation that shares no code with it — exact "
    "formulas judged by TOST equivalence at a pre-registered ±5% margin, "
    "approximations judged against stated tolerances and labeled as such. "
    "Unit invariance and guardrail behavior are enforced throughout. "
    "Methods: docs/SIMULATION_METHODS.md. Test choice: docs/STATS_STUDY.md. "
    "Changes: docs/CHANGELOG.md.",
]
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "VERIFICATION_REPORT.md").write_text("\n".join(header + REPORT) + "\n")

(ROOT / "results").mkdir(exist_ok=True)
record = {
    "generated_utc": now.isoformat(timespec="seconds"),
    "code_revision": git_rev,
    "python": platform.python_version(),
    "platform": platform.platform(),
    "packages": {"numpy": np.__version__,
                 "scipy": __import__("scipy").__version__},
    "checks_total": N_CHECKS,
    "checks_failed": n_fail,
    "failures": FAILURES,
    "equivalence_margin_relative": EXACT_MARGIN,
    "alpha": ALPHA,
    "batch_means_batches": BATCHES,
    "wall_time_s": round(elapsed, 1),
}
(ROOT / "results" / f"run_record_{now:%Y%m%d_%H%M%S}.json").write_text(
    json.dumps(record, indent=2))

print(f"{N_CHECKS - n_fail}/{N_CHECKS} checks passed in {elapsed:.0f}s "
      f"(rev {git_rev})")
if FAILURES:
    print("FAILURES:")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
