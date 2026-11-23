// guide.js — Defense guide: study material for defending Independent Study 2.
const { P, H1, H2, H3, bullet, num, note, table, rule, gap, build, Paragraph, TextRun } = require("./lib");
const W = (...f) => { const t = f.reduce((a, b) => a + b, 0); const w = f.map((x) => Math.round((x / t) * 9360));
  w[w.length - 1] += 9360 - w.reduce((a, b) => a + b, 0); return w; };

const c = [];
c.push(new Paragraph({ style: "Title", children: [new TextRun("Defending Independent Study 2")] }));
c.push(P("**Study guide for Jacob: questions, derivations, and weak points**", { size: 26, after: 60 }));
c.push(P("Operations Decision Model  ·  Mathematics Research, Ms. Badalian  ·  November 2026", { color: "52514E", after: 60 }));
c.push(note("This is study material, not a script. The answers below are points and evidence to know; say them in your own words. Anything marked as a derivation you should be able to do on a whiteboard without notes."));
c.push(rule());

// ---------------------------------------------------------------- A
c.push(H1("A. The core claim in four sentences"));
c.push(P("Know these four points cold; everything else supports one of them."));
c.push(num("The model turns how work flows through a small operation into one number, dollars per year, so every possible change (a process change, a hire, automation, or doing nothing) is judged on the same scale.", "numbers"));
c.push(num("Every equation was checked three independent ways, and the model's decisions were graded on 80 sealed made-up companies against perfect knowledge: it chose the exact best plan 78 times and a near-best plan every time.", "numbers"));
c.push(num("Every prediction comes with a 90% range, and on 80 fresh companies those ranges held 89% of the time.", "numbers"));
c.push(num("Real data showed where the model's assumptions hold (warehouse stock levels at 90% to 95% service, factory bottleneck) and where they break (work released in waves, skewed demand, headcount vs real capacity). Those breaks are Independent Study 3.", "numbers"));

// ---------------------------------------------------------------- B
c.push(H1("B. Derivations you must be able to do by hand"));
c.push(P("Each one names where it lives in the program, so you can show it running after you derive it."));
c.push(table(["#", "Derive", "Key steps", "Where in the program"], [
  ["1", "Average line at one station: L = ρ/(1 − ρ)", "Balance: λπₙ = μπₙ₊₁, so πₙ = ρⁿ(1 − ρ); L = Σ nπₙ = ρ/(1 − ρ)", "Verification Layer 1; Simulation lab"],
  ["2", "Little's law use: W = L/λ", "Average number in system = arrival rate × average time in system", "Every station result"],
  ["3", "Erlang C, 3 workers, load a = 2: P(wait) = 4/9", "Numerator a³/(3!(1 − ρ)) = (8/6)/(1/3) = 4; denominator 1 + 2 + 2 + 4 = 9", "Verification Layer 1"],
  ["4", "Why waits explode near capacity", "Time in system W = 1/(μ − λ), so a 1% error in speed moves W by about 1/(1 − ρ) percent: about 2% at 50% busy, about 14% at 93%, about 33% at 97%", "Journal C-011; workbench ranges"],
  ["5", "Best stock level S* = F⁻¹(p/(p + h))", "Add one unit: gain p·P(D > S), lose h·P(D ≤ S); stop when they balance: P(D ≤ S) = p/(p + h)", "Real-data test R-A"],
  ["6", "Value of a change V(S)", "hours/yr × (profit rate after − before) − annualized cost; \"do nothing\" is exactly 0, so a losing plan can never win", "Workbench; Benchmark"],
  ["7", "Work-variability factor (1 + cv²)/2", "Exponential work has cv = 1 (factor 1). Steadier work, smaller factor. Exact for one worker (Pollaczek-Khinchine)", "Journal C-001/C-004"],
  ["8", "TOST and why the p-value is the larger of two", "Test 1: difference above −margin; test 2: below +margin; equivalence needs both, so the weaker decides", "Statistics lab tab 1"],
  ["9", "Standard error of a mean; why batch means", "SE = sd/√n for independent data; nearby waits are correlated, so average long batches and use the spread of the batch averages", "Simulation lab"],
  ["10", "Give-up rate estimate θ = abandonments / total waiting time", "Exponential patience with some waits cut short by service (censoring): the maximum-likelihood estimate", "Real-data round 1"],
], W(5, 25, 44, 26)));

// ---------------------------------------------------------------- C
c.push(H1("C. Questions you will likely get"));
const qa = [
  ["Why should anyone trust results from simulations you wrote yourself?",
   ["The simulators share no code with the model; they build the operation customer by customer, while the model uses equations. Agreement between two independent methods is evidence, not circularity.",
    "Exact formulas had to pass an equivalence test at a margin set before the test (±5%), not just \"look close\".",
    "And the model was also tested on three real datasets, including failures, which is the check simulations can't give."],
   "Simulation lab; Verification Layer 3; docs/SIMULATION_METHODS.md"],
  ["Why TOST instead of a regular t-test? Why ±5%?",
   ["A t-test passes a model by failing to find a difference, which is easiest with weak evidence. TOST makes the model prove it is inside the margin.",
    "±5% because the decisions don't change below that: the cost inputs themselves are uncertain by up to 15%.",
    "Show the Statistics lab tab 2: with small samples a t-test passes a 10%-wrong model most of the time; TOST almost never does."],
   "Statistics lab tabs 1 and 2; docs/STATS_STUDY.md"],
  ["Your first real-data test failed. Doesn't that sink the project?",
   ["It was recorded as a failure and never re-run, which is what makes the passing results believable.",
    "It found something real: counting agents put the model off by a factor of about 18, because agents were available only about 38% of the time. That is the small-business problem the project is about: planning by headcount.",
    "It was also the wrong kind of operation (callers hang up; warehouse orders don't), so round 2 tested a real warehouse and a real factory."],
   "Real-data tests, round 1; Journal C-007, C-008"],
  ["How do you know you didn't tune the model to the tests?",
   ["Every test's rules were committed to git before any result existed; the timestamps are public on GitHub.",
    "Fixes were made on development data and proven on sealed or fresh data the fix never saw.",
    "Sealed sets refuse to run twice; the code enforces it."],
   "IS2 page commit record; report section 10"],
  ["You changed the benchmark after seeing development results. Isn't that cheating?",
   ["Both amendments fixed the test, not the model, and were committed before either sealed set ran.",
    "Amendment 1 made the test harder (the decisions were too easy), and the original sealed set was still run unchanged.",
    "Amendment 2 made the truth more precise; the model was frozen and unchanged."],
   "docs/PREREGISTRATION_BENCHMARK.md"],
  ["78 of 80 sounds too good to be true.",
   ["Compare it with a rule of thumb (always fix the bottleneck cheaply): near-best in only 31 of 80. The hard set was built so hiring, automation, and doing nothing each win sometimes.",
    "There were close calls (runner-up within 10% of the best) in 26 of 80 companies, and the model still found the best.",
    "The honest limit: the made-up companies follow the model's assumptions. The benchmark proves the decision logic and the pipeline; real data tests the assumptions."],
   "Benchmark page; report section 8"],
  ["What is original here? Erlang C and the newsvendor are textbook.",
   ["The individual formulas are textbook, and you should say so.",
    "What is new: one decision layer that prices sets of changes together (including interactions and flip points) for small operations; a validation protocol (pre-registered, sealed, coverage-tested ranges); and the findings, such as headcount vs effective capacity and wave arrivals in a real warehouse.",
    "The literature gap: existing tools are built for large firms with data teams; this targets operations that plan by headcount."],
   "Report sections 4 and 6"],
  ["What would make it wrong at the Syosset distributor?",
   ["Work released in waves instead of one order at a time (found in the real warehouse).",
    "Skewed demand for stock levels below 90% service.",
    "Workers' real availability below headcount.",
    "Stations above about 90% busy, where a small sample gives wide ranges: the program flags these as sensitive."],
   "Report section 8; workbench ranges"],
  ["How much data would you need from Syosset?",
   ["Use the workbench: set orders of history and watch the 90% ranges. At about 2,000 orders a busy picking station's wait range is very wide; at 30,000 it is tight.",
    "Plan the stopwatch sample around the busiest station."],
   "Model workbench"],
  ["What are exact vs approximate formulas in your model?",
   ["Exact: single queues, crews with exponential work, one worker with any work variability, callers who give up, stock levels for normal demand.",
    "Approximate: crews with non-exponential work, and variability passed down a line. Approximations are never given an equivalence claim; their measured error is part of the 90% ranges."],
   "Report section 4"],
  ["Where does the $ value come from, and isn't waiting cost a guess?",
   ["Yes: waiting cost is usually the weakest input. That is why the model reports the flip point: the waiting cost at which the ranking of two plans changes. If the real value is near it, measure it before deciding."],
   "Model workbench, decisions tab"],
  ["What did you learn from your failures?",
   ["Choose models with a score that punishes bias, not only error size (call center).",
    "A one-run simulation truth can be too noisy near capacity (benchmark).",
    "Ranges must include the formula's own error, not only data error (coverage).",
    "Check whether data is cut off before judging a prediction (factory)."],
   "Fine-tuning journal C-008, C-010, C-012, C-013"],
  ["Where did you use AI, and what did you do yourself?",
   ["Be exact and honest here; this is the question where overclaiming costs the most.",
    "Say what you were permitted (AI for the coding portion), what Claude built (the code, simulations, tests), and what you did yourself (the decisions, the derivations you can reproduce, the direction of the research). Only claim what you can demonstrate on the spot."],
   "Have your derivation notebook ready"],
];
qa.forEach(([q, pts, ev], i) => {
  c.push(H3(`${i + 1}. ${q}`));
  pts.forEach((t) => c.push(bullet(t)));
  c.push(P(`**Show:** ${ev}`, { size: 20, color: "52514E", after: 140 }));
});

// ---------------------------------------------------------------- D
c.push(H1("D. Weak points to raise yourself, before someone else does"));
c.push(P("Saying these first is stronger than being caught by them."));
c.push(table(["Weak point", "How to say it honestly"], [
  ["No real distributor's waiting times tested yet", "\"The only real waiting-time test was a call center and it failed; the distributor test is Independent Study 3.\""],
  ["Benchmark companies follow the model's assumptions", "\"The benchmark proves the decision logic and pipeline; real data is where the assumptions get tested.\""],
  ["Random arrivals assumed; a real warehouse released work in waves", "\"I found this in real data and it's the next model change.\""],
  ["Near capacity, predictions are sensitive", "\"The model shows a range and flags those stations instead of hiding it.\""],
  ["Factory workload test failed by design error", "\"I didn't account for the data ending mid-route; I recorded it as a failure and a lesson.\""],
  ["Formulas are textbook", "\"The originality is the decision layer, the validation protocol, and the findings.\""],
], W(38, 62)));

// ---------------------------------------------------------------- E
c.push(H1("E. A five-minute live demonstration"));
c.push(num("**Overview** (30 s): the status table, including the failures.", "numbers2"));
c.push(num("**Mock company walkthrough** (90 s): history, gate, estimates, prediction vs history with 90% ranges, ranked plans; press \"Run the check\" to show the decision delivered.", "numbers2"));
c.push(num("**Simulation lab** (60 s): run one station; the running average settles on the blue line; TOST verdict.", "numbers2"));
c.push(num("**Benchmark** (60 s): 78 of 80 vs a rule of thumb at 31 of 80; the one failure and why.", "numbers2"));
c.push(num("**Real-data tests** (60 s): the call-center failure and the warehouse 90.6%; end on wave arrivals as the next step.", "numbers2"));
c.push(gap());
c.push(P("**Before presenting:** run the Verification page's \"Run all checks now\" so the result shown is from that day."));

build("IS2_Defense_Guide.docx", "IS2 Defense Guide", c).then(() => console.log("guide written"));
