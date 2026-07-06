---
name: quality-control
description: "QC for geophysical data: completeness, physical-bounds checks, fill-value audit, satellite QA flag decoding, discontinuity detection."
---

# quality-control

Quality control for geophysical datasets: invocable directly ("run QC on
this dataset") and consulted automatically before analysis. The six-check structure
reconstructs the v0.1 enumeration referenced by SPEC §9.

## Consult the bundle for this dataset

Before reporting any check, DISCOVER and read the applicable knowledge
concepts; do not carry dataset facts, sentinel lists, screening numbers,
or QA bit layouts in this skill. Glob and grep `knowledge/` (its
`conventions/`, `gotchas/`, `datasets/`, and `recipes/`) by the dataset,
variable, and check in play, read the matches, then restate what each
changes about the check and cite it by path. The concepts this skill
leans on:

- the sentinel list and detection recipe: `conventions/common-fill-values.md`;
- the physical-bounds screening table: `conventions/physical-bounds-screening.md`;
- the satellite QA bit and class layouts: `conventions/satellite-qa-flag-decoding.md`;
- calendar and time-axis rules: `conventions/calendars.md`;
- the dataset's own known-issues / gotcha concepts, for named instrument
  or version transitions.

A concept added or corrected since you last ran is found this way, and
that is how it changes this skill's behavior without editing the skill.
Numbers, sentinel values, and bit layouts are read from the concepts,
never from this file.

## The six checks, in order

Order matters: a bounds check on unmasked sentinels reports garbage, so
the fill audit precedes bounds.

1. **Coordinates and time axis.** Latitude within [-90, 90], longitude
   convention identified, coordinates monotonic after sorting; time axis
   monotonic, no duplicates, cadence as documented; calendar identified.
2. **Fill-value audit.** `_FillValue`/`missing_value` attributes present
   and applied; scan minima/maxima for unmasked sentinels and check
   `encoding` for packing applied twice or not at all. The sentinel list
   and the detection recipe are read from
   `conventions/common-fill-values.md`, not carried here.
3. **Completeness.** Missing fraction per variable, overall and per time
   step; the longest gap, reported in time units, with its dates; spatial
   holes distinguished from temporal gaps.
4. **Physical bounds.** Every value inside the hard bounds of its
   variable; values outside the plausible-but-legal range listed for
   review rather than auto-rejected. Hard versus plausible is the method;
   the screening numbers per variable are read from
   `conventions/physical-bounds-screening.md`, and regional analyses
   tighten them. State which bounds were applied.
5. **QA flag decoding.** Satellite products: decode the bit-packed QA
   layer with bitwise operations and mask accordingly; never threshold a
   packed QA integer numerically. The product bit and class layouts
   (MODIS, Landsat C2, Sentinel-2, and kin) are read from
   `conventions/satellite-qa-flag-decoding.md`, not carried here; state
   which bits or classes were masked and what fraction that removed.
6. **Discontinuity detection.** Spikes (rolling-median deviation test),
   steps (change in mean across a break, instrument or version
   transitions), and suspicious exact repeats (stuck sensor, duplicated
   granule).

Report each check with a verdict and one line of evidence. Flagged data
is masked and reported, never silently deleted; interpolation across a
reported gap happens only when stated in the methods.

QA flags are categorical: they are never a quantitative uncertainty
(uncertainty-quantification carries that rule). The screening numbers
(the physical-bounds table) and the product QA layouts (MODIS, Landsat
C2, Sentinel-2) are dataset facts and live in the concepts named in
"Consult the bundle for this dataset", read and cited per run, never
inlined here.

## Discontinuity detection

- Spikes: deviation from a centered rolling median beyond k robust
  standard deviations (k around 5 for geophysical series); report count
  and worst offenders with dates.
- Steps: compare means across candidate break dates (known instrument
  or version transitions first; the dataset concept's known-issues
  section names them); a persistent shift after a transition date is a
  finding for the provider, not something to quietly detrend.
- Exact repeats: identical consecutive values or identical granules
  beyond chance suggest a stuck sensor or duplicated file.

## Must NOT (hard refusals and gates: invariant, universal, fire without consulting anything)

- Never run bounds checks before the fill-value audit. (Ordering gate: a
  bounds check on unmasked sentinels reports garbage.)
- Never threshold or average a packed QA integer as if it were data.
- Never treat QA flags as quantitative uncertainty.
- Never silently delete or interpolate flagged data; mask, report, and
  state any infilling in the methods.
- Never pass a dataset as "QC clean" without reporting all six checks
  with evidence.
- Never inline a screening bound, a sentinel value, or a QA bit layout
  in this skill; read them from the concepts and cite them per run.
