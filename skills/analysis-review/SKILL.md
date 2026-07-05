---
name: analysis-review
description: Post-computation sanity checks: area weighting, autocorrelation in trends, baselines, projections, budget grid, uncertainty reported, smell-test ranges.
---

# analysis-review

The post-computation review: invocable directly ("review this analysis")
and run before results are reported. Authored in Session 4 per
SPECIFICATION.md v0.5.1 §3.3, including the three UQ checks. Review what
was computed (the code and outputs), not what the prose claims.

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
5. **Budget grid.** Property budgets computed on regridded fields are
   🔴, full stop; budgets close only on the native grid (the domain
   plugin's budget skills and gotcha concepts carry the details).
6. **Calendar and seasonal handling.** DJF spanning the year boundary
   via `groupby("time.season")` is 🔴 for cross-year seasons; annual
   means of monthly data without month-length weighting 🟡.
7. **QC lineage.** Statistics computed before a fill-value audit are 🔴
   if sentinels were present; no QC run at all on a new dataset is 🟡.

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

Order-of-magnitude anchors; a value outside its anchor is 🔴 until
explained, inside but odd is 🟡. Domain quantities read their expected
ranges from recipe concepts (never hardcode a number that a recipe
states, and never invent one when a recipe exists).

| Quantity | Anchor |
|---|---|
| global mean 2 m temperature | about 288 K (15 C) |
| recent global warming trend | 0.1 to 0.3 K/decade |
| global mean precipitation | about 2.7 mm/day |
| global mean sea level rise | 3 to 4.5 mm/yr recent decades |
| ENSO Nino3.4 anomaly | within about +/-3 K |
| meridional heat transport, 26.5N Atlantic | recipe concept (order 1 PW) |
| Arctic September sea ice extent | order 4 to 5 million km2 recent years |
| surface salinity, open ocean | 32 to 38 psu |

Unit smells resolve most 🔴 anchors: a 273-ish offset is K vs C; a
factor ~30 on precipitation is mm/day vs mm/month; a factor 100 on
fractions is percent vs fraction; a factor 1000 on transport is TW vs PW.

## Must NOT

- Never pass an analysis with an unresolved 🔴.
- Never soften a missing-uncertainty finding to stylistic advice; it is
  🔴 by the house rule.
- Never invent an expected range when a recipe concept states one; read
  the recipe and cite it.
- Never review prose alone when code and outputs are available.
- Never silently fix what the review found; propose, with the flag and
  the evidence.
