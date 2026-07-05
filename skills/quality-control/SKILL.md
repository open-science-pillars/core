---
name: quality-control
description: QC for geophysical data: completeness, physical-bounds checks, fill-value audit, satellite QA flag decoding, discontinuity detection.
---

# quality-control

Quality control for geophysical datasets: invocable directly ("run QC on
this dataset") and consulted automatically before analysis. Authored in
Session 4 per SPECIFICATION.md v0.5.1 §3.3. The six-check structure
reconstructs the v0.1 enumeration referenced by SPEC §9 (the v0.1 text is
not in this workspace; flagged, not silently improvised).

## The six checks, in order

Order matters: a bounds check on unmasked sentinels reports garbage, so
the fill audit precedes bounds.

1. **Coordinates and time axis.** Latitude within [-90, 90], longitude
   convention identified, coordinates monotonic after sorting; time axis
   monotonic, no duplicates, cadence as documented; calendar identified.
2. **Fill-value audit.** `_FillValue`/`missing_value` attributes present
   and applied; scan minima/maxima for unmasked sentinels (-9999,
   -32767, -999, 1e20, 9.96921e36 and kin); check `encoding` for packing
   applied twice or not at all. The `conventions/common-fill-values.md`
   concept carries the sentinel list and detection recipe.
3. **Completeness.** Missing fraction per variable, overall and per time
   step; the longest gap, reported in time units, with its dates; spatial
   holes distinguished from temporal gaps.
4. **Physical bounds.** Every value inside the hard bounds of its
   variable (table below); values outside plausible-but-legal ranges
   listed for review rather than auto-rejected.
5. **QA flag decoding.** Satellite products: decode the bit-packed QA
   layer and mask accordingly (section below); never threshold a packed
   QA integer numerically.
6. **Discontinuity detection.** Spikes (rolling-median deviation test),
   steps (change in mean across a break, instrument or version
   transitions), and suspicious exact repeats (stuck sensor, duplicated
   granule).

Report each check with a verdict and one line of evidence. Flagged data
is masked and reported, never silently deleted; interpolation across a
reported gap happens only when stated in the methods.

## Physical bounds table

Hard bounds are physically impossible to exceed; plausible ranges catch
suspect-but-legal values. Both are screening thresholds, not truth.

| Variable | Units | Plausible | Hard bounds |
|---|---|---|---|
| 2 m air temperature | K | 210 to 330 | 180 to 340 |
| land surface temperature | K | 210 to 340 | 180 to 360 |
| sea surface temperature | degC | -2 to 34 | -2.5 to 38 |
| ocean temperature (interior) | degC | -2 to 30 | -2.5 to 35 |
| sea level pressure | hPa | 920 to 1070 | 850 to 1090 |
| precipitation rate | mm/day | 0 to 300 | 0 to 500 |
| relative humidity | % | 0 to 100 | 0 to 102 |
| specific humidity | kg/kg | 0 to 0.03 | 0 to 0.04 |
| wind speed (10 m) | m/s | 0 to 60 | 0 to 115 |
| wind components u, v | m/s | -60 to 60 | -115 to 115 |
| 500 hPa geopotential height | m | 4900 to 6000 | 4700 to 6100 |
| sea surface salinity | psu | 2 to 41 | 0 to 42 |
| sea surface height anomaly | m | -1.5 to 1.5 | -2.5 to 2.5 |
| significant wave height | m | 0 to 20 | 0 to 26 |
| sea ice concentration | fraction | 0 to 1 | 0 to 1 |
| snow depth | m | 0 to 10 | 0 to 15 |
| soil moisture (volumetric) | m3/m3 | 0 to 0.55 | 0 to 0.6 |
| NDVI | unitless | -0.2 to 1 | -1 to 1 |
| chlorophyll-a | mg/m3 | 0.01 to 70 | 0 to 100 |
| aerosol optical depth (550 nm) | unitless | -0.05 to 3 | -0.1 to 5 |
| total column ozone | DU | 150 to 500 | 90 to 600 |
| cloud fraction | fraction | 0 to 1 | 0 to 1 |
| TOA shortwave flux | W/m2 | 0 to 1400 | 0 to 1450 |
| evaporation | mm/day | -2 to 15 | -5 to 20 |

Bounds are climatological screening values; regional analyses tighten
them (a 45 degC 2 m temperature is plausible in the Lut Desert and a
finding in Finland). State which bounds were applied.

## Satellite QA flag decoding

QA layers are bit-packed integers; decode with bitwise operations, never
arithmetic comparisons on the packed value.

- **MODIS** (for example MOD13 VI Quality, 16-bit): bits 0-1 overall
  quality (00 good, 01 usable-check-others), bits 2-5 aerosol and
  adjacency conditions, bit 8 shadow, bits 10 and 15 clouds; many
  products also ship a simpler pixel-reliability layer, use it for
  first-pass masking and the bit field for the reasons.
- **Landsat Collection 2 QA_PIXEL** (16-bit): bit 0 fill, bit 1 dilated
  cloud, bit 3 cloud, bit 4 cloud shadow, bit 5 snow, bit 6 clear, bit 7
  water; confidence pairs sit in bits 8-15. Mask with
  `(qa & (1 << bit)) != 0`.
- **Sentinel-2 SCL** (scene classification, integer classes, not bits):
  0 no-data, 1 saturated/defective, 3 cloud shadow, 8 cloud medium
  probability, 9 cloud high probability, 10 thin cirrus, 11 snow;
  typical mask keeps classes 4, 5, 6, 7 (vegetation, bare, water,
  unclassified-usable).

Always state which bits or classes were masked and what fraction of
pixels that removed. QA flags are categorical: they are never a
quantitative uncertainty (uncertainty-quantification carries that rule).

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

## Must NOT

- Never run bounds checks before the fill-value audit.
- Never threshold or average a packed QA integer as if it were data.
- Never treat QA flags as quantitative uncertainty.
- Never silently delete or interpolate flagged data; mask, report, and
  state any infilling in the methods.
- Never pass a dataset as "QC clean" without reporting all six checks
  with evidence.
