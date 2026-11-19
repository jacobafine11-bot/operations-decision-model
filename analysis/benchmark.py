"""
benchmark.py — the multi-company benchmark, exactly as pre-registered in
docs/PREREGISTRATION_BENCHMARK.md.

  python analysis/benchmark.py dev       # development set (may inspect, may fix)
  python analysis/benchmark.py freeze    # record the frozen model (git revision)
  python analysis/benchmark.py sealed    # sealed set, once, after the freeze commit
  python analysis/benchmark.py report    # write docs/BENCHMARK_REPORT.md

For every company the model goes through the real pipeline (history →
validation gate → DuckDB estimates → evaluate → best_plan) and is graded
against brute-force re-simulation of the TRUE operation under every plan.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from itertools import combinations
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("model", "simulation", "schema", "pipeline"):
    sys.path.insert(0, str(ROOT / sub))

import numpy as np  # noqa: E402

import opsmodel as M  # noqa: E402
from estimate import estimate_stations  # noqa: E402
from eventlog import StationTruth, generate_orders, line_times  # noqa: E402
from guardrails import ModelError  # noqa: E402
from schema import validate_orders  # noqa: E402

BANDS = {"S": (2, 100, 2, 6), "L": (100, 250, 3, 7)}
SETS = {"dev": range(0, 20), "sealed": range(20, 40)}
N_HISTORY, N_TRUTH, N_PLAN, REPS = 30_000, 100_000, 20_000, 4
RESULTS = ROOT / "results"


@dataclass(frozen=True)
class Cand:
    name: str
    station: int
    kind: str        # "speed" (multiply rate) or "hire" (add workers)
    amount: float
    install: float
    annual: float
    years: float

    @property
    def annualized(self) -> float:
        return self.install / self.years + self.annual


@dataclass(frozen=True)
class Company:
    band: str
    idx: int
    seed: int
    lam: float
    stations: tuple
    waiting_cost: float
    wage: float
    hours: float
    cands: tuple
    budget: float

    @property
    def workers(self) -> int:
        return sum(s.workers for s in self.stations)


def make_company(band: str, idx: int) -> Company:
    lo, hi, kmin, kmax = BANDS[band]
    seed = (1_000_000 if band == "L" else 0) + 7919 * (idx + 1)
    rng = np.random.default_rng(seed)
    W = int(rng.integers(lo, hi + 1))
    k = min(int(rng.integers(kmin, kmax + 1)), W)
    workers = 1 + rng.multinomial(W - k, rng.dirichlet(np.ones(k)))
    b = int(rng.integers(k))
    rho = rng.uniform(0.50, 0.90, k)
    rho[b] = rng.uniform(0.80, 0.93)
    lam = W * rng.uniform(1.5, 4.0)
    cv = rng.uniform(0.3, 1.5, k)
    stations = tuple(StationTruth(f"S{j + 1}", lam / (workers[j] * rho[j]), int(workers[j]), float(cv[j]))
                     for j in range(k))
    cw, wage = rng.uniform(2, 15), rng.uniform(22, 38)
    hours = float(rng.choice([2000.0, 4000.0, 6000.0]))
    scale = W / 20.0
    others = [j for j in range(k) if j != b]
    second = max(others, key=lambda j: rho[j]) if others else b
    hire_b = max(1, round(0.1 * workers[b]))
    auto_install = rng.uniform(40_000, 250_000) * scale
    c4 = (Cand("Speed up second station", second, "speed", rng.uniform(1.1, 1.4),
               rng.uniform(3_000, 30_000) * scale, 0.0, 5.0)
          if rng.random() < 0.5 else
          Cand("Hire at second station", second, "hire", max(1, round(0.1 * workers[second])),
               0.0, max(1, round(0.1 * workers[second])) * wage * hours, 1.0))
    cands = (
        Cand("Process change at bottleneck", b, "speed", rng.uniform(1.1, 1.3),
             rng.uniform(2_000, 15_000) * scale, 0.0, 5.0),
        Cand("Automate bottleneck", b, "speed", rng.uniform(1.4, 1.9),
             auto_install, 0.05 * auto_install, 7.0),
        Cand("Hire at bottleneck", b, "hire", hire_b, 0.0, hire_b * wage * hours, 1.0),
        c4,
    )
    return Company(band, idx, seed, float(lam), stations, float(cw), float(wage), hours,
                   cands, float(rng.uniform(0.5, 1.5) * auto_install))


def apply_truth(stations, plan) -> list:
    out = list(stations)
    for c in plan:
        s = out[c.station]
        out[c.station] = (replace(s, service_rate=s.service_rate * c.amount) if c.kind == "speed"
                          else replace(s, workers=s.workers + int(c.amount)))
    return out


def affordable_plans(co: Company):
    plans = []
    for r in range(0, len(co.cands) + 1):
        for p in combinations(co.cands, r):
            if sum(c.install for c in p) <= co.budget + 1e-9:
                plans.append(p)
    return plans


def key(plan) -> str:
    return " + ".join(sorted(c.name for c in plan)) or "Do nothing"


# ---------------------------------------------------------------- one company

def assess(co: Company) -> dict:
    t0 = time.time()
    # 1. History through the real pipeline.
    orders = generate_orders(co.lam, list(co.stations), N_HISTORY, co.seed + 1)
    gate = validate_orders(orders)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "o.parquet"
        orders.to_parquet(p, index=False)
        est = {e.station: e for e in estimate_stations(str(p))}
    k = len(co.stations)
    lam_hat = est[co.stations[0].name].arrival_rate
    op = M.Operation(
        stations=tuple(M.Station(s.name, est[s.name].service_rate, s.workers, est[s.name].service_cv)
                       for s in co.stations),
        external_arrivals=tuple(lam_hat if j == 0 else 0.0 for j in range(k)),
        routing=tuple(tuple(1.0 if q == j + 1 else 0.0 for q in range(k)) for j in range(k)),
        waiting_cost=co.waiting_cost, hours_per_year=co.hours)

    out = {"band": co.band, "idx": co.idx, "workers": co.workers, "stations": k,
           "lam": co.lam, "gate_fatal": gate.fatal}
    # 2. Truth for predictions.
    true_waits, true_total = line_times(co.lam, list(co.stations), N_TRUTH, co.seed + 2)
    out.update(true_total_h=true_total, true_waits_h=true_waits)
    try:
        b = M.evaluate(op)
        out.update(pred_total_h=float(sum(r.W for r in b.station_results)),
                   pred_waits_h=[float(r.Wq) for r in b.station_results], refused=False)
    except ModelError as e:
        out.update(refused=True, refusal=str(e))
        return out

    # 3. Model's decision.
    def to_change(c: Cand) -> M.Change:
        def ap(o, c=c):
            sts = list(o.stations)
            s = sts[c.station]
            sts[c.station] = (replace(s, service_rate=s.service_rate * c.amount) if c.kind == "speed"
                              else replace(s, servers=s.servers + int(c.amount)))
            return o.with_changes(stations=tuple(sts))
        return M.Change(c.name, ap, c.install, c.annual, c.years)

    best, ranked = M.best_plan(op, [to_change(c) for c in co.cands], budget=co.budget)
    model_vals = {(" + ".join(sorted(cv.names)) or "Do nothing"): cv for cv in ranked}
    pick = " + ".join(sorted(best.names)) or "Do nothing"

    # 4. Truth for every affordable plan (common random numbers).
    befores = [line_times(co.lam, list(co.stations), N_PLAN, co.seed + 100 + r)[1] for r in range(REPS)]
    true_vals, true_gross = {}, {}
    for plan in affordable_plans(co):
        kk = key(plan)
        if not plan:
            true_vals[kk], true_gross[kk] = 0.0, 0.0
            continue
        after = apply_truth(co.stations, plan)
        g = [co.waiting_cost * co.lam * (befores[r] - line_times(co.lam, after, N_PLAN, co.seed + 100 + r)[1])
             * co.hours for r in range(REPS)]
        true_gross[kk] = float(np.mean(g))
        true_vals[kk] = true_gross[kk] - sum(c.annualized for c in plan)
    best_true_key = max(true_vals, key=true_vals.get)
    out.update(
        pick=pick, best_true=best_true_key, best_true_value=true_vals[best_true_key],
        pick_true_value=true_vals[pick], pick_true_gross=true_gross[pick],
        pick_promised_gross=float(model_vals[pick].gross_savings_per_year) if pick != "Do nothing" else 0.0,
        pick_model_value=float(best.value_per_year),
        n_plans=len(true_vals), plans_true={k_: round(v, 2) for k_, v in true_vals.items()},
        plans_model={k_: round(float(v.value_per_year), 2) for k_, v in model_vals.items()},
        seconds=round(time.time() - t0, 1))
    return out


# ---------------------------------------------------------------- scoring

def score(rows: list[dict], band: str) -> dict:
    rs = [r for r in rows if r["band"] == band]
    ok = [r for r in rs if not r.get("refused")]
    tot_err = [r["pred_total_h"] / r["true_total_h"] - 1 for r in ok]
    st_err = [pw / tw - 1 for r in ok for pw, tw in zip(r["pred_waits_h"], r["true_waits_h"]) if tw * 60 >= 1.0]
    near, regret_rel, no_loss, prom_err = [], [], [], []
    for r in ok:
        bt, pt = r["best_true_value"], r["pick_true_value"]
        reg = bt - pt
        near.append(reg <= max(0.10 * max(bt, 0.0), 2_000.0))
        regret_rel.append(reg / bt if bt > 0 else (0.0 if reg <= 2_000 else 1.0))
        no_loss.append(pt >= -2_000.0)
        if r["pick"] != "Do nothing" and r["pick_true_gross"] > 0:
            prom_err.append(r["pick_promised_gross"] / r["pick_true_gross"] - 1)
    med = lambda x: float(np.median(np.abs(x))) if len(x) else float("nan")  # noqa: E731
    share = lambda x: float(np.mean(x)) if len(x) else float("nan")  # noqa: E731
    n = len(rs)
    card = [
        ("P1", "Median abs error, total time through the line", med(tot_err), "≤ 10%", med(tot_err) <= 0.10),
        ("P2", "Companies with total-time error within ±20%",
         share([abs(e) <= 0.20 for e in tot_err]) * len(ok) / max(n, 1), "≥ 90%",
         share([abs(e) <= 0.20 for e in tot_err]) * len(ok) / max(n, 1) >= 0.90),
        ("P3", "Median abs error, station waits (true wait ≥ 1 min)", med(st_err), "≤ 15%", med(st_err) <= 0.15),
        ("D1", "Companies where the model's plan is near-best", share(near) * len(ok) / max(n, 1), "≥ 80%",
         share(near) * len(ok) / max(n, 1) >= 0.80),
        ("D2", "Median regret, share of the best plan's value", float(np.median(regret_rel)) if regret_rel else float("nan"),
         "≤ 5%", (float(np.median(regret_rel)) if regret_rel else 1) <= 0.05),
        ("D3", "Companies where the model's plan doesn't lose money", share(no_loss) * len(ok) / max(n, 1), "≥ 95%",
         share(no_loss) * len(ok) / max(n, 1) >= 0.95),
        ("D4", "Median abs error, promised vs delivered savings", med(prom_err), "≤ 15%", med(prom_err) <= 0.15),
    ]
    return {"band": band, "companies": n, "refused": n - len(ok),
            "card": [{"id": c[0], "criterion": c[1], "value": c[2], "pass_if": c[3], "pass": bool(c[4])}
                     for c in card],
            "total_time_errors": tot_err, "station_wait_errors": st_err}


def _run(args):
    return assess(make_company(*args))


def run_set(which: str) -> int:
    if which == "sealed":
        frz = RESULTS / "benchmark_frozen.json"
        if not frz.exists():
            print("Refusing: no freeze record. Run `benchmark.py freeze` and commit first.")
            return 2
    jobs = [(b, i) for b in BANDS for i in SETS[which]]
    t0 = time.time()
    with Pool(2) as pool:
        rows = []
        for r in pool.imap_unordered(_run, jobs):
            rows.append(r)
            print(f"  {r['band']}{r['idx']:02d}: {r['workers']:>3} workers, {r['stations']} stations, "
                  f"{'REFUSED' if r.get('refused') else 'total err %+.1f%%, pick %s' % (100 * (r['pred_total_h'] / r['true_total_h'] - 1), 'near-best' if r['best_true_value'] - r['pick_true_value'] <= max(0.1 * max(r['best_true_value'], 0), 2000) else 'MISS')}",
                  flush=True)
    rows.sort(key=lambda r: (r["band"], r["idx"]))
    scores = {b: score(rows, b) for b in BANDS}
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                         text=True).stdout.strip()
    (RESULTS / f"benchmark_{which}.json").write_text(json.dumps(
        {"set": which, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "code_revision": rev, "seconds": round(time.time() - t0), "rows": rows, "scores": scores},
        indent=1, default=float))
    for b, s in scores.items():
        print(f"\nBand {b} ({which}, {s['companies']} companies, {s['refused']} refused): "
              f"{sum(c['pass'] for c in s['card'])}/{len(s['card'])} criteria")
        for c in s["card"]:
            v = c["value"]
            print(f"  {c['id']} {'PASS' if c['pass'] else 'FAIL'}  {c['criterion']}: {v:.1%} (need {c['pass_if']})")
    print(f"\n{which}: {len(rows)} companies in {time.time() - t0:.0f}s")
    return 0


def freeze() -> int:
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                         text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "model"], cwd=ROOT, capture_output=True,
                           text=True).stdout.strip()
    if dirty:
        print("Refusing to freeze: model/ has uncommitted changes.")
        return 2
    (RESULTS / "benchmark_frozen.json").write_text(json.dumps(
        {"frozen_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model_revision": rev}, indent=2))
    print(f"Frozen at model revision {rev}. Commit results/benchmark_frozen.json before running sealed.")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd in ("dev", "sealed"):
        raise SystemExit(run_set(cmd))
    if cmd == "freeze":
        raise SystemExit(freeze())
    print(__doc__)
    raise SystemExit(2)
