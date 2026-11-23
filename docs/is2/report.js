// report.js — Independent Study 2 Product Report (technical record of the product).
const { P, H1, H2, H3, bullet, num, note, table, pageBreak, rule, gap, build, Paragraph, TextRun } = require("./lib");

const W = (...f) => { const t = f.reduce((a, b) => a + b, 0); return f.map((x) => Math.round((x / t) * 9360)); };
const fix = (w) => { const d = 9360 - w.reduce((a, b) => a + b, 0); w[w.length - 1] += d; return w; };
const cols = (...f) => fix(W(...f));

const c = [];
c.push(new Paragraph({ style: "Title", children: [new TextRun("Operations Decision Model")] }));
c.push(P("**Independent Study 2 Product Report**", { size: 28, after: 60 }));
c.push(P("Jacob Fine  ·  Mathematics Research, Ms. Badalian  ·  Jericho High School  ·  November 2026", { color: "52514E", after: 60 }));
c.push(note("This report is the technical record of the Independent Study 2 product: the software, its tests, and its results. The code was built with Claude under the permission given for the coding portion of the project. It is not the research paper. Every number below comes from a result file in the repository and can be regenerated."));
c.push(rule());

// ---------------------------------------------------------------- 1
c.push(H1("1. Summary"));
c.push(P("Independent Study 2 had to find out whether the equations from Independent Study 1 are correct, work out what their outputs mean as a decision, and deliver an interactive portal where the simulations run, plus a written log of every change to the formulas. All of it was delivered. The headline results:"));
c.push(table(["What had to be shown", "Result", "Verdict"], [
  ["The equations match an independent simulation", "87 of 87 verification checks pass; every exact formula proven within ±5% by an equivalence test (TOST)", "Shown"],
  ["The model makes good decisions across many operations", "160 made-up companies, 2 to 250 workers. Sealed sets, run once: 27 of 28 criteria passed; exact best plan chosen in 78 of 80", "Shown"],
  ["The model says how sure it is, honestly", "On 80 fresh companies, 90% ranges contained the truth 89% of the time (after a recorded first failure at 73%)", "Shown"],
  ["The model works on real data", "Call center: failed 1 of 6. Real warehouse inventory: 90.6% delivered at a 90% target. Real factory: correct bottleneck. 4 of 11 real-data criteria passed in total", "Partly"],
  ["It runs outside the development workspace", "Fresh clone of the GitHub repository, fresh environment: every test passes", "Shown"],
], cols(30, 55, 15)));
c.push(gap());
c.push(P("**The honest bottom line.** On operations that follow its assumptions, the model is accurate and its advice is nearly perfect at every size tested. Real data showed where those assumptions break: work released in waves, skewed demand, and effective capacity that differs from headcount. Those findings define Independent Study 3."));

// ---------------------------------------------------------------- 2
c.push(H1("2. Research question and what Independent Study 2 promised"));
c.push(P("**Research question.** How can a general mathematical model decide whether a change to a small distribution or production operation is worth making, and when is a change in inventory or logistics strategy a better choice than automation?"));
c.push(table(["Promised in the proposal", "Delivered", "Status"], [
  ["Learn statistical significance testing and choose the tests", "TOST equivalence testing chosen and defended; chi-square and bootstrap KS for input checks; the tests validated before use", "Done"],
  ["Build a program that runs the equations on any data, including large data", "Model engine plus data pipeline with a validation gate; 5,000,000 rows processed in about 5 seconds", "Done"],
  ["Test on real public data, predicting held-back data blind", "Three real datasets, each pre-registered and run once", "Done (4 of 11 criteria)"],
  ["Build a warehouse simulation with random arrivals, random work, absent workers, lumpy demand", "Independent simulators for crews, give-ups, lines of stations, absent workers, order-by-order histories", "Done"],
  ["Compare equations to simulation with statistical tests; investigate gaps", "87 of 87 checks; every gap fixed with a mechanism or recorded as a limit", "Done"],
  ["Define how a change is valued in $/yr and test it", "Value of a change set V(S); tested against re-simulation of every plan in 80 sealed companies", "Done"],
  ["Run everything at different scales", "Two size bands, 2 to 100 and 100 to 250 workers; 5,000,000-row data test", "Done"],
  ["Product: interactive portal", "12-page program; every page and work button tested", "Done"],
  ["Product: written log of formula changes", "13 changelog entries with mechanism and evidence", "Done"],
], cols(34, 50, 16)));

// ---------------------------------------------------------------- 3
c.push(H1("3. The product"));
c.push(H2("3.1 Where it lives"));
c.push(bullet("**Source of truth:** private GitHub repository jacobafine11-bot/operations-decision-model, with the full commit history."));
c.push(bullet("**Interface:** the portal, a Streamlit program (portal/app.py). Run with: pip install -r requirements.txt, then streamlit run portal/app.py. Deployable on Streamlit Community Cloud from the repository."));
c.push(bullet("**Notebook:** notebooks/colab_quickstart.ipynb runs the full test suite in Google Colab with no setup."));
c.push(H2("3.2 The portal, page by page"));
c.push(table(["Page", "What it does"], [
  ["Overview", "What the model is; an honest status table; where to go"],
  ["Independent Study 2", "Each proposal promise, what was delivered, and the evidence"],
  ["Model workbench", "Describe an operation; see utilization, the bottleneck, profit, 90% ranges; rank changes with interactions and flip points; size one crew"],
  ["Mock company walkthrough", "A fictional distributor with a known answer key, from raw history to a checked decision"],
  ["Simulation lab", "Run the independent simulator live; watch it converge; equivalence verdict; sample-size estimate"],
  ["Statistics lab", "TOST step by step; why a plain t-test would pass a wrong model; input checks on real data"],
  ["Benchmark (160 companies)", "Sealed scorecards, model vs a rule of thumb, uncertainty coverage, company explorer"],
  ["Fine-tuning journal", "Every formula change with mechanism, evidence, and a live demonstration"],
  ["Real-data tests", "Call center, warehouse, factory: pre-registered, run once, diagnosed"],
  ["Verification suite", "Run all 87 checks from the page; run history; the full report"],
  ["Data pipeline", "Upload an order history; validation gate; estimates; scale proof"],
  ["Documents", "Every document in the repository"],
], cols(28, 72)));
c.push(gap());
c.push(H2("3.3 It works outside the development workspace"));
c.push(P("On 23 November 2026 the repository was cloned fresh from GitHub into a new Python environment with only the packages in requirements.txt. Results: 87 of 87 verification checks, both unit tests, 12 of 12 portal pages and both work buttons, the 5,000,000-row pipeline test (4.7 s), and an identical reproduction of the C-009 held-out check. Record: docs/CLEAN_ROOM_RUN.md."));

// ---------------------------------------------------------------- 4
c.push(H1("4. The model"));
c.push(P("The model turns a description of an operation into one number, dollars per year, so that any change can be judged on the same scale."));
c.push(table(["Part", "What it computes", "Type"], [
  ["E1 Traffic equations", "Real load on each station: λ = (I − Pᵀ)⁻¹γ", "Exact"],
  ["E2 Station queues", "Utilization, chance of waiting, line length, wait: M/M/1 and Erlang C crews", "Exact"],
  ["E2 Work variability (C-004)", "Wait scaled by (Ca² + Cs²)/2", "Exact at 1 worker; approximation for crews"],
  ["E2b Customers who give up (C-006)", "Erlang A: wait and share who abandon, valid even when overloaded", "Exact"],
  ["Variability down a line (C-009)", "QNA linking equation passes each station's variability to the next", "Approximation"],
  ["E3 Inventory", "Best stock level S* = mean + sd · Φ⁻¹(p/(p+h)); expected shortage and excess", "Exact for normal demand"],
  ["E5 Profit rate", "Π = mX − c_wΣL − inventory cost − overhead, in $/hour", "Definition"],
  ["E6 Value of a change set", "V(S) = hours/yr × (Π after − Π before) − annualized cost", "Definition"],
  ["E7 Best plan", "Every affordable set of changes compared; \"do nothing\" always included", "Exact search"],
  ["Uncertainty ranges (C-011, C-012)", "90% range for each prediction from sampling error and the formula's measured error", "Tested by coverage"],
], cols(28, 52, 20)));
c.push(gap());
c.push(P("**The decision rule.** Make a set of changes only if its value V(S) is positive and stays positive when the uncertain cost inputs move within believable ranges. The model reports the flip point, for example \"re-slotting beats automation unless a waiting order costs more than $5.76 per hour\", so the weakest input is named rather than hidden."));
c.push(P("**Guardrails.** The model refuses rather than guesses: an overloaded station with no one giving up has no steady state, so the model stops with an explanation instead of returning a number."));

// ---------------------------------------------------------------- 5
c.push(H1("5. How it was verified"));
c.push(H2("5.1 Four layers"));
c.push(num("**The tests themselves.** Before any test judged the model, it was judged: TOST agrees with its independent confidence-interval form in 400 of 400 random cases and fires at the designed 5% rate; the input-check tests pass data built to pass and reject data built to fail.", "numbers"));
c.push(num("**Textbook values.** Every closed form reproduces known answers exactly (for example, Erlang C with 3 servers and load 2 equals 4/9, worked by hand).", "numbers"));
c.push(num("**A second algorithm.** Every result is recomputed a different way: matrix solve vs iteration, Erlang B recursion vs direct sum, the best stock level vs a 1,000,000-draw brute force.", "numbers"));
c.push(num("**Independent simulation.** Simulators that share no code with the model build the operation customer by customer. Exact formulas must pass an equivalence test; approximations are held to stated tolerances and labeled as approximations.", "numbers"));
c.push(H2("5.2 Why an equivalence test (TOST) and not a t-test"));
c.push(P("A t-test asks whether a difference can be proven, so a model passes by failing to find one, which is easiest when evidence is weakest. TOST reverses the burden: its null hypothesis is that the difference is at least a margin fixed in advance (±5%), so a small p-value is positive evidence that the model is within the margin. Waits of nearby customers are correlated, so every comparison uses batch means (20 batches, 19 degrees of freedom). Full study and defense: docs/STATS_STUDY.md."));
c.push(H2("5.3 Rules first, results second"));
c.push(bullet("Every test on new data or new companies was written down and committed to git before any result existed."));
c.push(bullet("Fixes were made only on development data and proven on sealed or fresh data the fix never saw."));
c.push(bullet("A formula changed only for a reason explained from how the operation works, never to make a number match."));
c.push(bullet("Failed tests stay on the record and are never re-run on the same data as if still blind."));

// ---------------------------------------------------------------- 6
c.push(H1("6. Results"));
c.push(H2("6.1 Against simulation"));
c.push(P("87 of 87 checks pass. Examples of what is proven equivalent within ±5%: single-station and crew waits, the chance of waiting, a three-station line, single-worker waits with non-random work times (Pollaczek-Khinchine), and Erlang A waits and abandonment including an overloaded case. Approximations measured against simulation: crew waits with non-random work (within 12%) and lines of crews with variability passed down the line (within 20%). Report: docs/VERIFICATION_REPORT.md."));
c.push(H2("6.2 Benchmark: 160 made-up companies"));
c.push(P("Each company went through exactly what a real engagement would: a 30,000-order history, the validation gate, estimates, predictions, and a recommended plan. The true operation was then re-simulated under every affordable plan so the model's advice could be graded against perfect knowledge. Two size bands; development and sealed sets; an original and a \"hard decisions\" generator in which hiring, automation, and doing nothing can each win. Rules: docs/PREREGISTRATION_BENCHMARK.md (two amendments, both committed before the sealed runs, both fixing the test, not the model)."));
c.push(table(["Sealed set (run once)", "2 to 100 workers", "100 to 250 workers"], [
  ["Original: criteria passed", "7 of 7", "7 of 7"],
  ["Hard decisions: criteria passed", "7 of 7", "6 of 7"],
  ["Median error, time through the line (original / hard)", "1.3% / 0.8%", "0.4% / 0.4%"],
  ["Promised vs delivered savings, median error (original / hard)", "4.8% / 7.3%", "3.0% / 2.6%"],
  ["Exact best plan chosen (original / hard)", "20 / 18 of 20", "20 / 20 of 20"],
  ["Rule of thumb near-best (original / hard)", "5 / 7 of 20", "11 / 8 of 20"],
], cols(46, 27, 27)));
c.push(gap());
c.push(P("**The one failure:** hard decisions, 100 to 250 workers, station waits 23.8% median error (criterion: 15% or less). Four stations at 88% to 95% busy. With the true inputs the formula's error was 5.7%; with inputs estimated from history it was 23.8%. Near capacity a small error in measured work speed is amplified many times, because every waiting-time formula contains 1/(1 − utilization). Decisions were unaffected: errors largely cancel when comparing before with after."));
c.push(H2("6.3 Uncertainty ranges"));
c.push(table(["Coverage of 90% ranges (80 fresh companies each)", "Round 1", "Round 2", "Pass zone"], [
  ["Station waits", "73.4% (fail)", "89.1%", "82% to 97%"],
  ["Time through the line", "85.0%", "88.8%", "82% to 97%"],
  ["Stations near capacity", "82.6%", "86.5%", "75% or more"],
], cols(46, 18, 18, 18)));
c.push(gap());
c.push(P("Round 1 covered estimation error only and was too narrow at quiet stations, where the formula's own small error mattered more. That error was measured only on development companies (5.5% at first stations, 11.5% downstream, unbiased) and added; round 2, on new companies, passed all three criteria."));
c.push(H2("6.4 Real data"));
c.push(H3("Round 1: call center (failed 1 of 6)"));
c.push(P("417,149 real calls (Anonymous Bank, Technion SEE Center). The calibration half showed that headcount is not capacity: agents were available for incoming calls about 38% of the time, and counting heads put the model off by a factor of about 18. An effective-capacity measure, added by a dated amendment before the blind half, cut that to about 2. The blind half then failed: predicted waits and abandonment about twice the real values, rank correlation 0.24 (needed 0.70); coverage passed (97.3%). Lesson recorded: the score used to choose a model must penalize bias, not only error size. A call center is also not the project's target, which led to round 2."));
c.push(H3("Round 2: real warehouse and real factory (3 of 5)"));
c.push(table(["Test", "Result", "Verdict"], [
  ["Warehouse: 90% service target (140 products, 19 unseen weeks)", "90.6% delivered", "Pass"],
  ["Warehouse: 95% service target", "92.9% delivered", "Pass"],
  ["Warehouse: 80% service target", "86.3% delivered (overstocks)", "Fail"],
  ["Factory: predicted bottleneck among the 2 busiest", "Quality Check 1, the actual busiest", "Pass"],
  ["Factory: workload per machine within 20%", "36.9% median error", "Fail"],
], cols(52, 33, 15)));
c.push(gap());
c.push(P("Diagnoses (exploratory, after the results): the 80% miss comes from skewed demand (products with symmetric demand delivered 80.3%; skewed ones 88.5%). The factory workload miss is a test-design flaw: the data ends mid-route for orders started in March (7.1 recorded steps each against 13.8). The warehouse also revealed that orders arrive in waves: 32,634 orders created in only 768 distinct minutes, up to 594 at once."));
c.push(H2("6.5 Scale"));
c.push(P("A synthetic year of 5,000,000 order events and 91,250 demand rows was generated, validated, and estimated in about 5 seconds; rates were recovered within 0.12% of the truth, and the estimator matched an independent engine to 1.4 × 10⁻¹⁵."));

// ---------------------------------------------------------------- 7
c.push(H1("7. Changes made to the formulas"));
c.push(P("Each change records what was seen, the mechanism, what changed, and the evidence (docs/CHANGELOG.md; Fine-tuning journal in the portal)."));
c.push(table(["Entry", "What was seen", "What changed", "Evidence"], [
  ["C-001/C-004", "Waits 35% too high when work is steady", "Wait scaled by measured work variability", "Exact at 1 worker; crews within 12%"],
  ["C-002", "Rounded timestamps made speeds look 4% to 9% faster", "Data policy for second-level timestamps", "Recovery error 9% → 0.12%"],
  ["C-003", "One year of demand leaves up to 15% error in spread", "Fed into sensitivity ranges", "Quantified"],
  ["C-005", "Need a validation standard", "TOST at a pre-registered ±5%", "Tests validated first"],
  ["C-006", "Real callers give up; overloaded hours", "Erlang A added", "Equivalent to simulation"],
  ["C-007", "Headcount is not capacity", "Effective-capacity measure", "Error factor 18 → 2"],
  ["C-008", "Real call-center test failed", "Lessons recorded; no tuning", "Holdout retired"],
  ["C-009", "Downstream stations 24% to 43% too high", "Variability passed down the line", "Held-out: 24.3% → 5.9%"],
  ["C-010", "Benchmark: estimation amplified near capacity", "Led to C-011", "Sealed 27 of 28"],
  ["C-011", "Predictions need honest error bars", "90% ranges from sampling error", "Coverage round 1: 2 of 3"],
  ["C-012", "Ranges too narrow at quiet stations", "Formula's own error added", "Coverage round 2: 3 of 3"],
  ["C-013", "Real warehouse and factory", "No model change yet; next steps named", "3 of 5"],
], cols(12, 33, 30, 25)));

// ---------------------------------------------------------------- 8
c.push(H1("8. Limits, stated plainly"));
c.push(bullet("**No real distributor's waiting times have been tested yet.** The only real waiting-time test, a call center, failed, and it was not the target kind of operation."));
c.push(bullet("**Random arrivals are assumed.** A real warehouse released work in batches; the model does not yet represent batch (wave) arrivals."));
c.push(bullet("**Demand is assumed roughly symmetric.** Real demand was skewed, which made the stock rule overstock at an 80% target."));
c.push(bullet("**Near capacity, predictions depend heavily on measurement precision.** The 90% ranges show this and the model flags such stations as sensitive."));
c.push(bullet("**Variability is passed down only single lines of stations.** Other layouts (splits, merges, job shops) fall back to random arrivals. One known miss: a very steady crew far down a line was under-predicted by about 31% even with true inputs."));
c.push(bullet("**The benchmark companies follow the model's assumptions** (first-come first-served lines, random arrivals). The benchmark proves the pipeline and the decision logic, not that real operations fit those assumptions; real data is the test of that."));
c.push(bullet("**Factory waiting times are out of scope:** they are driven by scheduling and setups, which the model does not represent."));

// ---------------------------------------------------------------- 9
c.push(H1("9. What Independent Study 3 does next"));
c.push(num("Add batch (wave) arrivals and a skewed demand model, each derived from its mechanism and proven on data it was not built on.", "numbers2"));
c.push(num("Fix the factory test design (compare only completed work) and re-test on fresh data.", "numbers2"));
c.push(num("Take the model to the Syosset distributor: a stopwatch sample of arrivals, picking, packing, and loading; a pre-registered test of its predictions there; then a decision the owner can use.", "numbers2"));

// ---------------------------------------------------------------- 10
c.push(H1("10. Evidence index: the commit record"));
c.push(P("Each pre-registration and amendment was committed before the result it governs. All commits are on GitHub (times in UTC)."));
c.push(table(["Commit", "Time", "What"], [
  ["c4f978b", "17 Nov 17:04", "Pre-registration: call-center blind test"],
  ["b88300d", "17 Nov 17:08", "Amendment 1: effective capacity, before any holdout scoring"],
  ["4c8d4bd", "17 Nov 17:09", "Frozen model choice (calibration half only)"],
  ["380587b", "17 Nov 17:11", "Call-center holdout result: failed 1 of 6"],
  ["acbc157", "19 Nov 17:04", "Pre-registration: C-009 held-out check"],
  ["69d2dd7", "19 Nov 17:05", "C-009 result: passed (24.3% → 5.9%)"],
  ["f20b009", "19 Nov 17:26", "Pre-registration: 160-company benchmark"],
  ["d8cd624", "19 Nov 17:28", "Development results; Amendment 1 (hard set)"],
  ["49a043b", "19 Nov 17:30", "Amendment 2 (precise truth); model unchanged"],
  ["1456b6d", "19 Nov 17:30", "Model frozen for sealed runs"],
  ["12f0dde", "19 Nov 17:33", "Sealed benchmark results: 27 of 28"],
  ["fea57d4", "19 Nov 17:35", "Pre-registration: coverage round 1"],
  ["a4cdb65", "19 Nov 17:36", "Coverage round 1 result: 2 of 3"],
  ["40f264a", "19 Nov 17:38", "C-012 and pre-registration: coverage round 2"],
  ["9d67298", "19 Nov 17:40", "Coverage round 2 result: 3 of 3"],
  ["319b60f", "19 Nov 17:43", "Pre-registration: real-data round 2"],
  ["d0bb844", "19 Nov 17:44", "Real-data round 2 result: 3 of 5"],
  ["bb208b5", "23 Nov 17:01", "Clean-room run from a fresh clone"],
], cols(14, 18, 68)));
c.push(gap());
c.push(H2("How to reproduce"));
c.push(table(["Command", "What it shows"], [
  ["python tests/run_verification.py", "All 87 checks; writes docs/VERIFICATION_REPORT.md and a run record"],
  ["python tests/test_portal_pages.py", "Every portal page and work button"],
  ["python pipeline/scale_test.py", "5,000,000-row pipeline test"],
  ["python analysis/qna_heldout.py", "C-009 held-out check (reproduces the recorded result)"],
  ["python analysis/benchmark.py dev", "Benchmark development set (sealed sets run once and refuse a rerun)"],
  ["streamlit run portal/app.py", "The portal"],
], cols(42, 58)));

build("IS2_Product_Report.docx", "IS2 Product Report", c).then(() => console.log("report written"));
