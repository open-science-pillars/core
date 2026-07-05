# core quickstart

Five minutes from installed to a defensible number. Assumes the plugin
is installed (`claude plugin install core@open-science-pillars`); the
timed, fresh-install-tested walkthrough lives in the
[tutorials book](https://github.com/open-science-pillars/tutorials)
(Tutorial 1, measured at 4.6 minutes).

## 1. Orient

Ask: "What science tools do I have set up here, and what should I do
next?" The start skill answers in one screen: skills, connectors,
credentials, knowledge bundles, one suggested next step.

## 2. Get data honestly

Ask for data conversationally ("what SST data should I use for the
North Atlantic?"): discover-data parses the need, searches or falls
back to its knowledge bundle BY NAME, and surfaces the gotchas that
come with each candidate.

## 3. Compute with the house rules on

Open any NetCDF/Zarr you have (data-formats identifies and summarizes
it; quality-control runs its six checks before analysis touches it).
Compute a spatial mean and a trend: area weighting, autocorrelation
handling, and a baseline statement happen by default
(xarray-fundamentals, basic-statistics), and every headline number
arrives with an uncertainty statement or an explicit waiver
(uncertainty-quantification: the house rule).

## 4. Check and report

"Review this analysis" runs analysis-review's checklist (a missing
uncertainty statement is a blocking 🔴, not a style note). "Write this
up as a report" gates on filename and sections BEFORE writing, then
cites the knowledge concepts it relied on in Provenance.

That loop (orient, discover, compute under rules, review, gated
report) is the whole plugin. Everything else is depth on one of those
five verbs.
