"""Unit test: the effective-agent sweep against a hand calculation,
including a waiting interval that crosses an hour boundary."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "analysis"), str(ROOT / "model")]

import pandas as pd  # noqa: E402

import bank_validation as B  # noqa: E402


def main() -> int:
    T = lambda s: pd.Timestamp("1999-03-01 10:00:00") + pd.Timedelta(seconds=s)  # noqa: E731
    rows = [
        # Agent A busy 0-1800, B 600-3000, C 1200-1500.
        dict(outcome="served", wait_s=0, arrived_at=T(0), left_queue_at=T(0), started_at=T(0), finished_at=T(1800)),
        dict(outcome="served", wait_s=0, arrived_at=T(600), left_queue_at=T(600), started_at=T(600), finished_at=T(3000)),
        dict(outcome="served", wait_s=0, arrived_at=T(1200), left_queue_at=T(1200), started_at=T(1200), finished_at=T(1500)),
        # Caller X waits 900-1300; caller Y waits 3500-3700 (crosses 11:00).
        dict(outcome="abandoned", wait_s=400, arrived_at=T(900), left_queue_at=T(1300), started_at=pd.NaT, finished_at=pd.NaT),
        dict(outcome="abandoned", wait_s=200, arrived_at=T(3500), left_queue_at=T(3700), started_at=pd.NaT, finished_at=pd.NaT),
    ]
    ce = B.effective_agents(pd.DataFrame(rows))
    # Hour 10: line exists 900-1300 (busy 2 for 300 s, 3 for 100 s) and
    # 3500-3600 (busy 0): (600 + 300 + 0) / 500 = 1.8. Hour 11: 0.0.
    assert abs(ce[pd.Timestamp("1999-03-01 10:00")] - 1.8) < 1e-12
    assert abs(ce[pd.Timestamp("1999-03-01 11:00")] - 0.0) < 1e-12
    print("effective-agent sweep: matches hand calculation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
