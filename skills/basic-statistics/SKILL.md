---
name: basic-statistics
description: Climatology, anomalies, Mann-Kendall and Sen's slope trends, composites, percentile extremes, calendar handling for climate data.
user-invocable: false
---

# basic-statistics

Background expertise for the statistics that climate and geophysical
analyses actually run on, with the traps that make them silently wrong. Mechanics of
groupby, resample, and weighting live in xarray-fundamentals; uncertainty
methods (bootstrap variants, intervals) live in uncertainty-quantification.

## Consult the bundle

Before running these methods on a real product, DISCOVER and consult the
installed knowledge bundle rather than working from remembered numbers.
Glob and grep `knowledge/datasets/`, `knowledge/gotchas/`,
`knowledge/recipes/`, and `knowledge/conventions/` for concepts touching
the product, quantity, and method in play (the dataset's own gotchas, the
calendar conventions, the method failure modes), read the matches, and
restate and cite what each changes about the plan before computing. This
file carries the procedure and the refusals only; dataset facts, expected
numbers, observed failure rates, and gotcha rules live in concepts and are
read from them per analysis, so a concept added or corrected since you last
ran changes the behavior without editing this skill.

## Climatology and anomalies

The canonical pattern and the two house rules:

1. **State the baseline period with every climatology or anomaly** (for
   example 1991-2020). An anomaly without its baseline is not a result.
2. Spatial aggregation is area-weighted, always (cos-lat or true cell
   areas; see xarray-fundamentals).

Deseasonalize by removing the monthly climatology before trend or
variability analysis; a seasonal cycle left in dominates variance and
corrupts autocorrelation estimates. If the record carries a trend, note
that a full-record baseline centers anomalies at the record midpoint and
anomalies inherit the trend; that is usually intended, but say it.

## Trends: the decision tree

Work down until a branch fits; never start at OLS.

1. **Question is "is there a monotonic trend, and how big?"** (the common
   case): Mann-Kendall for presence, Sen's slope for magnitude.
   - Residuals effectively independent (annual means, short-memory data):
     original MK, `pymannkendall.original_test`.
   - Autocorrelated series (monthly anomalies, most geophysical series):
     **Hamed-Rao modified MK**, `pymannkendall.hamed_rao_modification_test`;
     positive autocorrelation inflates false positives in original MK.
   - Seasonal cycle present and not removed: `pymannkendall.seasonal_test`
     (or deseasonalize first, then Hamed-Rao).
2. **Question is "what is the linear rate with a physical model in
   mind":** OLS is acceptable when residuals are near-normal and serial
   correlation is handled: inflate the standard error by the lag-1
   effective-sample-size factor, or block-bootstrap the slope CI
   (uncertainty-quantification has the recipe).
3. **Gridded trend maps:** apply the chosen test per grid cell, show
   Sen's slope (or OLS slope) as the field, and mark statistical
   significance by stippling (see cartography); consider false-discovery
   control when claiming field-wide significance.
4. **Never:** OLS p-values on an autocorrelated series without
   correction; trends from first-minus-last differences; extrapolating a
   fitted trend beyond the record.

Report every trend with: magnitude in physical units per decade, the test
used, the p-value or CI, and the record period. A trend without
uncertainty and method is not a result (the house reporting rule).

## Mann-Kendall worked example (pymannkendall)

Monthly global-mean series from a lat-lon dataset:

```python
import numpy as np, xarray as xr, pymannkendall as pmk

ds = xr.open_dataset("era5like_t2m.nc")
w = np.cos(np.deg2rad(ds.lat))
gm = ds.t2m.weighted(w).mean(["lat", "lon"])
base = gm.sel(time=slice("1991-01-01", "2020-12-31"))
anom = gm.groupby("time.month") - base.groupby("time.month").mean()

res = pmk.hamed_rao_modification_test(anom.values)
trend_per_decade = res.slope * 120   # slope is per time step; 120 months/decade
```

Read the result carefully: `res.slope` is **per time step** (per month
here), so scale by 120 for K/decade; `res.trend` is the categorical call;
`res.p` reflects the autocorrelation correction. Method note: the
Hamed-Rao variance correction can return a NaN p-value on some series;
detect it and fall back to `original_test` deliberately, stating the
fallback, rather than letting NaN cells silently read as non-significant.
The observed failure rate, the fallback rationale, and the fixture
verification numbers are not carried here: glob `knowledge/gotchas/` for
the Hamed-Rao NaN failure-mode concept and cite it. The reasoning that
stays is method, not a dataset fact: when a trend is strong relative to
its autocorrelated noise the uncorrected original test can happen to agree
with the corrected one, which is exactly the case where the uncorrected
test builds false confidence for weaker real-world trends, so the
autocorrelation-aware test is the default.

## Composites

Composite means over event categories (El Niño months, post-eruption
years) are differences of means: test them (permutation test or Welch's
t), respect serial correlation when events span consecutive time steps
(block permutation by event, not by month), and beware multiple
comparisons on maps: report field significance or control the false
discovery rate rather than celebrating scattered stippling.

## Percentile extremes

- Empirical percentiles per grid cell or station; for day-of-year
  thresholds use a centered window (commonly 5 days) across the baseline
  years.
- **In-base bias trap:** exceedance rates of a percentile threshold are
  biased inside vs outside the baseline period used to define it; either
  interpret only out-of-base exceedances or apply the standard
  bootstrap-resampling correction when comparing across the boundary.
- Count-based indices (days above the 90th percentile) change meaning
  with the baseline; state the baseline and window with the index.
- Sample size matters at the tails: a 99th percentile from 30 values is
  noise; say how many samples stand behind a quoted extreme.

## Calendar-aware statistics

Month-length weighting of annual and seasonal means, the DJF year-boundary
(QS-DEC) trap, and taking day counts from the dataset's own calendar
(360_day, noleap, and the rest) rather than a hardcoded table are calendar
facts, not statistics: consult and cite `conventions/calendars.md` instead
of carrying them here. The statistics-specific application to remember:
day-of-year percentile windows are sized in calendar days too, so a model
calendar reshapes the window just as it reshapes month-length weights;
take both from the actual calendar.

## Must NOT (hard refusals)

These are hard refusals: statistical-validity gates that hold regardless
of the dataset (invariant, universal, refusal-shaped), so they stay in the
skill and fire without consulting anything.

- Never run original Mann-Kendall or plain OLS significance on an
  autocorrelated series without the appropriate correction.
- Never report a trend without method, period, significance, and
  physical-units magnitude per decade.
- Never compute a climatology, anomaly, or percentile index without
  stating the baseline (and window, for percentiles).
- Never aggregate spatially without area weights.
- Never claim map-wide significance from per-cell tests without
  field-significance or FDR control.
- Never compare percentile exceedances across the in-base/out-of-base
  boundary without the correction.
