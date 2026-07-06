---
type: dataset-gotcha
title: "Hamed-Rao modified Mann-Kendall can return NaN; detect it and fall back to the original test"
description: "The Hamed-Rao autocorrelation correction occasionally yields a NaN p-value; undetected, those cells read as non-significant and silently blank a trend map."
tags: [mann-kendall, hamed-rao, autocorrelation, trend, pymannkendall, nan]
timestamp: 2026-07-05
severity: medium
scope: cross-cutting
# Cross-cutting method gotcha: a numerical failure mode of the Hamed-Rao
# variance correction (pymannkendall), independent of any one dataset, so
# it states its scope instead of linking a dataset concept (the SPEC §3.6
# cross-cutting exception, as in common-fill-values.md).
evidence:
  - ../../verification/fixtures/make_fixtures.py
  - "internal: relocated from core/skills/basic-statistics/SKILL.md during the knowledge-coupling migration, needs a steward evidence link"
status: draft
---

# Hamed-Rao modified Mann-Kendall can return NaN; detect it and fall back

**Applicability: cross-cutting.** This is a numerical property of the
Hamed-Rao variance correction (`pymannkendall.hamed_rao_modification_test`),
not of any one dataset. It surfaces most often in per-cell trend maps,
where thousands of independent series are tested.

**Mechanism.** The Hamed-Rao modification rescales the Mann-Kendall
variance by the series' autocorrelation structure. On some series that
rescaling is undefined and the test returns a NaN p-value. Observed on
about 1.5% of grid cells in per-cell map use (core map-mode run,
2026-07-04); the rate depends on the series length and autocorrelation.

**Wrong-result mode.** A NaN p-value that is not caught reads downstream
as "not significant," so affected cells silently drop out of a
significance mask or stipple layer. The map looks complete while a
fraction of it is quietly blank, and the blanking correlates with
autocorrelation structure rather than with the signal.

**Fix (for the analyst).** Detect NaN p-values explicitly and fall back
to the uncorrected `pymannkendall.original_test` on those series only,
stating the fallback in the methods rather than letting NaN read as
non-significant. The fallback trades the autocorrelation correction for a
verdict, so record which cells took it.

**Verification.** On the core verification fixture
([make_fixtures.py](../../verification/fixtures/make_fixtures.py),
era5like_t2m.nc), the Hamed-Rao path recovers the constructed trend
(0.199 vs the imposed 0.20 K/decade, verified 2026-07-04). The fixture's
AR(1) noise (phi = 0.5 by construction, documented in make_fixtures.py)
is why the autocorrelation-aware test is the right default there. The
imposed trend is strong enough that the uncorrected original test happens
to agree on this fixture, which is exactly the situation where the
uncorrected test would build false confidence for weaker real-world
trends. A dedicated eval for the NaN fallback path is not yet in core's
evals/; the existing trend-method case checks autocorrelation-awareness
generally, not this failure mode.
