---
name: analysis-review
description: "Post-computation sanity checks: area weighting, autocorrelation in trends, baselines, projections, budget grid, uncertainty reported, smell-test ranges."
---

# analysis-review

The post-computation review: invocable directly ("review this analysis")
and run before results are reported. Review what
was computed (the code and outputs), not what the prose claims.

## Consult the bundle (standing step)

This review carries NO expected numbers, dataset facts, or gotcha rules
of its own; they live in the knowledge bundle and are read per analysis.
Before flagging anything numeric or product-specific, DISCOVER and
consult the applicable concepts: glob and grep the installed
`knowledge/` directories (core's and the domain plugin's) by quantity,
product, variable, and topic, read the matches, and restate what each
one constrains, citing it by path. In particular: the cross-cutting
sanity anchors live in `conventions/smell-test-ranges.md`; a product's
native uncertainty or quality layer lives in its dataset concept's
`## Uncertainty` section; a quantity's expected range lives in its
domain recipe concept; a trap's rule lives in its gotcha or convention
concept. A concept added or corrected since you last ran is found this
way and changes this review without editing this skill. Never work from
a remembered number where a concept exists.

## Verdict format

Each check gets an inline flag and one line of evidence:

- 🔴 wrong result likely; must be fixed before reporting
- 🟡 suspicious or incomplete; investigate or justify explicitly
- 🟢 clean

The review ends with an overall verdict; any unresolved 🔴 blocks the
report. The review proposes fixes; it never silently applies them.

## Methodology checklist

1. **Area weighting.** Any spatial mean over a lat-lon grid without
   cos-lat or cell-area weights is 🔴 (xarray-fundamentals has the rule
   and the fix).
2. **Autocorrelation in trends.** Original Mann-Kendall or uncorrected
   OLS significance on monthly or daily series is 🔴; check the method
   against basic-statistics' decision tree, and per-cell map claims
   against its FDR rule.
3. **Baselines.** Climatology, anomaly, or percentile results without a
   stated baseline are 🔴; two compared series on different baselines
   without comment is 🔴; a trended record used as its own full-record
   baseline earns 🟡 unless the midpoint-centering is acknowledged.
4. **Projections and figures.** Per cartography: jet or rainbow 🔴;
   diverging colormap without a pinned physical center 🔴; missing
   `transform=` 🔴 (misplaced data); polar fields on PlateCarree 🟡;
   stippling, hatching, or bands undefined in the caption 🟡; comparable
   panels without a shared colorbar 🟡.
5. **Budget grid (hard refusal: invariant, universal).** Property
   budgets computed on regridded fields are 🔴, full stop; budgets close
   only on the native grid. This flag fires without consulting anything;
   the domain plugin's budget skills and gotcha concepts carry the
   formulation details, cited when present.
6. **Calendar and seasonal handling.** DJF spanning the year boundary
   via `groupby("time.season")` is 🔴 for cross-year seasons; annual
   means of monthly data without month-length weighting 🟡. The rule and
   the fix live in the calendars convention concept
   (`conventions/calendars.md`); read and cite it, do not restate it.
7. **QC lineage.** Statistics computed before a fill-value audit are 🔴
   if sentinels were present; no QC run at all on a new dataset is 🟡.
   The sentinel list and detection recipe live in the fill-values
   concept (`conventions/common-fill-values.md`), consulted per the
   standing step, not carried here.

## The three UQ checks

1. **Is uncertainty reported alongside the headline number?** Every
   headline quantity carries an interval, a spread, or a native product
   uncertainty, or an explicit one-line waiver. Absent: 🔴.
2. **Is an ensemble mean shown without spread?** 🔴; with fewer than
   about 10 members the spread must also be called a likely
   underestimate (uncertainty-quantification has the caveat).
3. **Does the product carry a native uncertainty or quality layer that
   the analysis ignored?** Consult the dataset concept's Uncertainty
   section to know what exists. Ignored and material to the conclusion:
   🔴; ignored and plausibly immaterial: 🟡 with a justification asked.

## Smell-test ranges

The procedure: a headline value outside its anchor is 🔴 until
explained, inside but odd is 🟡. Do NOT carry or remember the anchor
values here. Read the cross-cutting anchors from the smell-test concept
(`conventions/smell-test-ranges.md`) per the standing step, and read a
domain quantity's expected range from its own domain recipe concept
(never hardcode a number that a recipe or the anchors concept states,
and never invent one when a concept exists). Restate and cite the anchor
you used.

Unit smells resolve most out-of-anchor values (invariant unit method,
not a dataset fact): a 273-ish offset is K vs C; a factor ~30 on
precipitation is mm/day vs mm/month; a factor 100 on fractions is
percent vs fraction; a factor 1000 on transport is TW vs PW.

## Must NOT (hard refusals and gates)

- Never pass an analysis with an unresolved 🔴.
- Never soften a missing-uncertainty finding to stylistic advice; it is
  🔴 by the house rule.
- Never invent an expected range, or remember one, when a concept states
  it; read it from the recipe or the smell-test anchors concept and cite
  it.
- Never review prose alone when code and outputs are available.
- Never silently fix what the review found; propose, with the flag and
  the evidence.
