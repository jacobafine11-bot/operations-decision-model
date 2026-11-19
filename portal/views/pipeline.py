import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

import core
from estimate import estimate_stations
from schema import ORDERS_COLUMNS, validate_orders

st.title("Data pipeline")
st.markdown("How a company's records become model inputs. The equations never see raw "
            "rows: data is converted to a standard format, checked by the validation gate, "
            "then turned into rates.")

st.markdown("""
```
raw export  →  adapter  →  standard tables  →  validation gate  →  estimation  →  model
(any shape)    (one per     (fixed columns     (reports, never      (rows → rates,
               source)       and units)         fixes silently)      with variability)
```
""")

t1, t2, t3 = st.tabs(["1 · Check your own data", "2 · The standard format", "3 · Scale proof"])

with t1:
    st.markdown("Upload an order history as CSV with these columns: "
                f"`{', '.join(ORDERS_COLUMNS)}` (one row per order per station; timestamps "
                "like `2026-09-01 08:15:03`).")
    up = st.file_uploader("Order history CSV", type="csv")
    use_sample = st.toggle("Use the mock company's history instead", value=up is None)
    df = None
    if up is not None and not use_sample:
        df = pd.read_csv(up)
        for c in ("arrived_at", "started_at", "finished_at"):
            if c in df:
                df[c] = pd.to_datetime(df[c], errors="coerce")
    elif use_sample:
        import mock_company as MC
        df = MC.history(10_000, 3)
    if df is not None:
        rep = validate_orders(df)
        (st.error if rep.fatal else st.success)(rep.summary().split("\n")[0])
        for f in rep.findings:
            st.markdown(f"- {f}")
        if not rep.fatal:
            with tempfile.TemporaryDirectory() as td:
                p = Path(td) / "o.parquet"
                df.to_parquet(p, index=False)
                est = estimate_stations(str(p))
            out = pd.DataFrame([{"Station": e.station, "Arrivals/hr": e.arrival_rate,
                                 "Speed/hr per worker": e.service_rate,
                                 "Variability (cv)": e.service_cv, "Orders": e.n_orders} for e in est])
            st.subheader("Estimated inputs")
            st.dataframe(out.style.format(precision=3), hide_index=True, width="stretch")
            st.caption("These go straight into the Model workbench. Crew sizes come from the "
                       "owner, and should be checked against effective capacity (C-007).")

with t2:
    st.markdown("""
| Table | One row per | Columns |
|---|---|---|
| `orders` | order per station | order_id, station, arrived_at, started_at, finished_at |
| `queue_events` | customer, where customers can give up | event_id, station, arrived_at, left_queue_at, outcome (served / abandoned), wait_s, started_at, finished_at, service_s, server |
| `demand` | product per day | product_id, date, units |
| `inventory` | product per count | product_id, date, on_hand |
| `costs` | cost input | name, value, unit, source (measured / interview / assumed / public) |

**What the gate checks:** required columns, timestamp types, missing values, duplicates,
impossible timestamp order (work finishing before it starts), suspicious durations (time-zone
or unit errors), coverage, and the provenance of every cost input. Small problems are reported;
large ones reject the data.

**A real catch:** the bank data had 11,098 call ID numbers used twice. The gate rejected it.
Diagnosis showed zero identical rows: the IDs repeat across phone lines, so the correct key
is line + ID + date. The adapter was fixed, not the gate (`adapters/anonymous_bank.py`).
""")

with t3:
    st.markdown("""
Before any real export arrives, the pipeline was tested on a synthetic year with known true
values: **5,000,000 order events + 91,250 demand rows**.

| Stage | Time |
|---|---|
| Generate and write to Parquet (44 MB) | about 3 s |
| Validation gate | about 1.5 s |
| Estimation over the full files (DuckDB) | about 0.3 s |

Rates were recovered within **0.12%** of the truth, and the estimator matched an independent
engine to **1.4 × 10⁻¹⁵**. The first run of this test caught a real problem: rounding
timestamps to whole seconds made speeds look 4 to 9% faster (changelog C-002).
""")
    st.code("python pipeline/scale_test.py", language="bash")
