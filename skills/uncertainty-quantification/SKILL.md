---
name: uncertainty-quantification
description: Uncertainty for results: error propagation, bootstrap and block-bootstrap CIs, ensemble spread, conformal prediction, native product uncertainty fields, reporting rules.
---

# uncertainty-quantification

How results earn their error bars: invocable directly ("put a confidence
interval on this") and consulted automatically whenever a quantitative
result heads for a report. Authored in Session 4 per SPECIFICATION.md
v0.5.1 §3.3 (full scope).

## The house reporting rule

**No headline quantitative result without an uncertainty statement (an
interval, a spread, or the product's native uncertainty), or an explicit
one-line reason why none is available.** Every stated interval carries
its method and level: "0.85 +/- 0.12 PW (95% CI, moving-block bootstrap,
block length 12 months)" is a result; "0.85 PW" is not. The report skill
enforces this in its Results section; analysis-review checks for it after
the fact.

## Choosing a method

- Arithmetic on inputs with known errors: error propagation.
- A statistic of a sample or series, effectively independent samples:
  bootstrap.
- A statistic of an autocorrelated series (most geophysical series):
  block bootstrap.
- Multiple models or ensemble members: spread, with the small-ensemble
  caveat.
- The product ships uncertainty fields: use them, starting from the
  dataset concept's Uncertainty section.
- An ML or statistical prediction that needs guaranteed coverage:
  conformal prediction.

## Error propagation basics

Independent errors add in quadrature: sums and differences combine
absolute sigmas, products and ratios combine relative sigmas; correlated
inputs need the covariance term, and ignoring positive covariance
understates the total. For nonlinear functions, linearization is only as
good as the local derivative; when in doubt, propagate by Monte Carlo
(sample the inputs, run the computation per sample, quote percentiles of
the output). Monte Carlo propagation is the honest default for anything
beyond simple arithmetic.

## Bootstrap and block bootstrap

Plain bootstrap: resample the data with replacement, recompute the
statistic, at least 1000 resamples, quote percentile bounds with the
level. Valid when samples are effectively independent.

**Block bootstrap** is the default for time series, because geophysical
series are autocorrelated and plain bootstrap destroys that structure,
producing intervals that are too narrow (the classic way honest-looking
error bars go wrong). Resample contiguous blocks (moving-block or
circular), statistic per resample, percentile CI.

Block-length guidance: the block must exceed the decorrelation scale.
Estimate lag-1 autocorrelation r1; the decorrelation time is roughly
(1 + r1) / (1 - r1) samples. Choose the block at or above that, and for
monthly data prefer 12 months so blocks also respect the seasonal cycle.
State the block length with the interval. Two pitfalls: a trended series
is not exchangeable, so detrend and bootstrap the residuals (or bootstrap
the trend estimator itself); and n^(1/3)-style defaults are a floor, not
a justification, when r1 is large.

## Native product uncertainty fields

Before analyzing any dataset, read its dataset concept's
`## Uncertainty` section (knowledge-first): it names the product's error
fields and their caveats. Examples in this org's bundles: GHRSST MUR's
analysis-error field, SWOT's ssha uncertainty variables, GRACE-FO mascon
error grids; ECCO ships no formal error fields (dynamical consistency
stands in, and that must be said plainly when quoting ECCO numbers).
Use the fields, do not just map them: propagate them into the derived
quantity. Spatially correlated errors do not average down like white
noise; a basin mean of a field with correlated errors keeps most of the
error unless the product documents its error correlation scale. State
the assumption used.

## Ensemble spread

Spread across members (standard deviation or a percentile range) is a
legitimate uncertainty statement, with a mandatory caveat: **small
ensembles underestimate uncertainty**, both statistically (a sample
spread from N members is biased low and noisy for small N) and
structurally (members often share model assumptions, so the true
uncertainty exceeds the spread). With fewer than about 10 members,
report the range, call it a lower bound on the uncertainty, and say why.
An ensemble mean is never presented without its spread.

## Conformal prediction

Distribution-free prediction intervals with finite-sample coverage
guarantees: model-agnostic, wraps any trained predictor, no retraining.
Split conformal in one breath: hold out a calibration set, compute
nonconformity scores (residuals) on it, take the appropriate quantile,
and widen every prediction by that amount; coverage then holds by
construction under exchangeability.

When to reach for it: ML-derived surfaces and predictions (downscaling,
gap-filling, biomass and yield estimation) that must state coverage to be
usable; heteroscedastic cases want conformalized quantile regression so
intervals vary with the predictors. Caveat: exchangeability strains under
spatial and temporal correlation; calibrate on spatially or temporally
blocked splits and say so. GEE-native implementations exist for Earth
observation workflows, so "we could not compute intervals at scale" is
rarely a valid waiver for EO ML products. Remember cartography's pairing
rule: an ML surface for stakeholders ships with its uncertainty map.

## The applied framing: the carbon-credit lower bound

Carbon-credit protocols allocate credits from the **lower bound of a
prediction interval**, not from the point estimate. An estimator with
great point accuracy and no honest interval earns nothing defensible; a
slightly worse estimator with tight, valid intervals is worth more
credits. The general lesson prices uncertainty directly: decisions
consume bounds, not points, so tightening honest intervals is scientific
work with direct value, and overstating a point estimate without an
interval is not a shortcut, it is an unverifiable claim.

## Must NOT

- Never present an ensemble mean without its spread.
- Never treat quality flags as quantitative uncertainty (they are
  categorical; quality-control carries the decoding rules).
- Never report an interval without stating method and level (and block
  length, for block bootstrap).
- Never run a plain bootstrap on an autocorrelated series.
- Never claim conformal coverage where exchangeability is plainly broken
  and unblocked.
- Never average a spatially correlated error field down as if it were
  white noise without stating the correlation assumption.
