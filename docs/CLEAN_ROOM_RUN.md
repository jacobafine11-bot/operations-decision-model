# Clean-Room Run

Proof that the program works from the public repository alone, not from the
development workspace. Run on 2026-11-23 (UTC).

## Procedure

1. Fresh clone of `jacobafine11-bot/operations-decision-model` at commit `7c45d45`.
2. New Python virtual environment (Python 3.13.18), packages installed only from
   `requirements.txt` (numpy 2.5.5, scipy 1.18.1, pandas 3.1.1, duckdb 2.0.1,
   streamlit 1.67.0).
3. Every test and two reproductions run inside that clone.

## Results

| What | Command | Result |
|---|---|---|
| Verification suite | `python tests/run_verification.py` | **87/87 passed** (9 s) |
| Portal compute layer | `python tests/test_portal_logic.py` | passed |
| Effective-agent sweep | `python tests/test_bank_analysis.py` | passed (matches hand calculation) |
| Every portal page and work button | `python tests/test_portal_pages.py` | **11/11 pages, 2/2 buttons** |
| 5-million-row pipeline | `python pipeline/scale_test.py` | passed, 4.7 s |
| C-009 held-out check (reproduction) | `python analysis/qna_heldout.py` | identical result, PASS |
| Benchmark development set (reproduction) | `python analysis/benchmark.py dev` | band S 7/7; band L 6/7 defined (see note) |

**Note on the development-set reproduction.** The recorded development run
(before Amendment 2) used a one-run truth; the final code uses the more precise
4 × 200,000-order truth. With it, one big-company development station's true wait
is 1.02 minutes (previously under 1 minute), so criterion P3 is now judged on that
single station (predicted 0.84 minutes, −17.7%) instead of being undefined. All
decision criteria (D1 to D4) reproduce exactly. The sealed sets were run with the
final code, so their recorded results stand unchanged.

## Not re-run here, by design

The sealed benchmark sets, the coverage tests, and both real-data rounds refuse to
run a second time: each was a one-time test and its result file is final. The bank
analysis needs the Technion data, which is not redistributed (see
`adapters/anonymous_bank.py`).
