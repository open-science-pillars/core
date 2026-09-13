# core quickstart

About five minutes from installed to a defensible number, plus one
attested one. Assumes the plugin is installed
(`claude plugin install core@open-science-pillars`) and, for step 5,
that `uv` is on your path (the README's install section). The timed,
fresh-install-tested walkthrough is
[Tutorial 1](https://github.com/open-science-pillars/tutorials/blob/main/tutorial-1-getting-started.qmd)
in the tutorials repository (measured at 4.6 minutes).

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
uncertainty statement is a blocking finding, not a style note). "Write this
up as a report" gates on filename and sections BEFORE writing, then
cites the knowledge concepts it relied on in Provenance.

## 5. Prove a number

The attested reference computation is the smallest thing this plugin
can prove: a global-mean trend on a synthetic fixture, run by an
executor that writes a receipt, then checked by a deterministic attester
that never trusts the executor. Run both from a checkout of this
repository (or from the install path `claude plugin list` shows), in a
terminal with `uv`:

```bash
uv run verification/trend_computation.py --runtime claude-code --out /tmp/receipt.json
uv run verification/trend_attester.py /tmp/receipt.json --out /tmp/attestation.json
```

The first command prints the headline (about 0.20 K per decade) and
writes a receipt that names the capability release and the runtime that
ran it (`--runtime` is whatever ran it: `claude-code` here). The second
recomputes the trend from the fixture, checks the receipt's code hash
and values against the sanctioned computation, and writes the verdict;
a nonzero exit is a failed attestation. The same attester checks a
receipt from any runtime, which is what a qualification record is made
of.

That loop (orient, discover, compute under rules, review, gated
report, prove) is the whole plugin. Everything else is depth on one of
those verbs.
