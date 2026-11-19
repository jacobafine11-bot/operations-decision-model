# Public data included in this repository

## Tyler's Grill (University of Richmond), one day in 2005
- `tylers_grill_arrivals.csv`: 1,434 customer arrival times, seconds after opening (07:30; open until 21:00).
- `tylers_grill_service.csv`: 110 measured service times, seconds.
- Source: R package simEd (Lawson & Leemis), dataset `tylersGrill`, collected for CMSC 326 Simulation, University of Richmond, 2005. CRAN: https://CRAN.R-project.org/package=simEd (GPL). Used in the portal's Statistics lab for real input checks (are arrivals Poisson? are gaps exponential?).

## Warehouse orders, footwear manufacturer (2023)
- `warehouse_weekly_demand.csv`: units per product reference per week (weeks with zero demand omitted).
- `warehouse_orders.csv`: one row per order with its creation time.
- Source: "Order Picking Dataset from a Warehouse of a Footwear Manufacturing Company", Mendeley Data, https://data.mendeley.com/datasets/pf2w725pw3/1, CC BY 4.0. Converted by `adapters/mendeley_warehouse.py`.

## Factory job shop, machining (2012)
- `factory_operations.csv`: one row per operation (work order, sequence, activity, resource, start, end).
- Source: Levy, D. (2014). Production Analysis with Process Mining Technology. 4TU.ResearchData, https://data.4tu.nl/datasets/12697997. Converted by `adapters/factory_4tu.py`.

## Not included: Anonymous Bank call center (1999)
Free for research with acknowledgment, but not redistributed here. Download from the Technion SEE Center and convert with `adapters/anonymous_bank.py` (see that file). Window-level results derived from it are in `results/`.
