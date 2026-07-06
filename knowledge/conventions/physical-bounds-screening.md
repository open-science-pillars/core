---
type: convention
title: "Physical-bounds screening table for geophysical QC"
description: "Hard and plausible screening ranges for common geophysical variables; the QC bounds check reads these, they are screening thresholds not truth."
tags: [qc, physical-bounds, screening, geophysical]
timestamp: 2026-07-05
status: verified
verified: 2026-07-06
verified_by: OSP steward review
evidence:
  - "internal: climatological screening ranges compiled by the OSP quality-control skill; regional analyses tighten them"
---

# Physical-bounds screening table for geophysical QC

Screening thresholds for the physical-bounds check (QC step 4). Hard
bounds are physically impossible to exceed; plausible ranges catch
suspect-but-legal values. Both are screening thresholds, not truth: a
value inside the bounds is not thereby correct, and a value outside the
plausible range is listed for review, not auto-rejected.

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
