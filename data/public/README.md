# Public data included in this repository

## Tyler's Grill (University of Richmond), one day in 2005
- `tylers_grill_arrivals.csv`: 1,434 customer arrival times, seconds after opening (07:30; open until 21:00).
- `tylers_grill_service.csv`: 110 measured service times, seconds.
- Source: R package simEd (Lawson & Leemis), dataset `tylersGrill`, collected for CMSC 326 Simulation, University of Richmond, 2005. CRAN: https://CRAN.R-project.org/package=simEd (GPL). Used in the portal's Statistics lab for real input checks (are arrivals Poisson? are gaps exponential?).

## Not included: Anonymous Bank call center (1999)
Free for research with acknowledgment, but not redistributed here. Download from the Technion SEE Center and convert with `adapters/anonymous_bank.py` (see that file). Window-level results derived from it are in `results/`.
