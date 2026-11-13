"""Smoke tests for the portal's compute layer (no UI needed)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portal"))

import pandas as pd  # noqa: E402

import logic as L  # noqa: E402


def main() -> int:
    op = L.build_operation(L.DEFAULTS["stations"], L.DEFAULTS["arrival_rate"],
                           L.DEFAULTS["margin"], L.DEFAULTS["waiting_cost"],
                           L.DEFAULTS["overhead"], L.DEFAULTS["hours_per_year"])
    table, bottleneck = L.station_table(op)
    assert len(table) == 4 and bottleneck == "Picking", (len(table), bottleneck)
    prof = L.profit_table(op)
    assert list(prof["Line"])[-1] == "Operating profit"

    changes_df = pd.DataFrame({
        "Name": ["Re-slot", "Hire packer"],
        "Station": ["Picking", "Packing"],
        "Type": ["Speed up station by %", "Add workers"],
        "Amount": [25.0, 1.0],
        "One-time cost $": [3000.0, 0.0],
        "Yearly upkeep $": [0.0, 38000.0],
        "Spread cost over (years)": [5.0, 1.0],
    })
    changes = L.build_changes(changes_df, [s.name for s in op.stations])
    plans = L.plan_table(op, changes, budget=100_000)
    assert "Do nothing" in set(plans["Plan"]), "do-nothing baseline missing"
    assert (plans["Value $/year"] >= plans["Value $/year"].shift(-1).fillna(-1e18)).all(), \
        "plans not sorted by value"
    flip = L.waiting_cost_flip(op, [changes[0]], [changes[1]])
    assert flip is None or flip > 0

    # The guardrail must surface as ModelError on evaluation, which is
    # the call the UI makes right after building (station_table).
    try:
        bad_op = L.build_operation(L.DEFAULTS["stations"], 1e6, 9.0, 4.0,
                                   120.0, 2000.0)
        L.station_table(bad_op)
    except L.ModelError:
        pass
    else:
        raise AssertionError("overload did not raise ModelError")

    print("portal logic: all smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
