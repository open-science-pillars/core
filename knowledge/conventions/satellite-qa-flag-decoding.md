---
type: convention
title: "Satellite QA flag decoding: MODIS, Landsat Collection 2, Sentinel-2"
description: "Bit and class layouts for decoding satellite QA layers: MODIS VI Quality, Landsat C2 QA_PIXEL, Sentinel-2 SCL; used by the QC QA-flag check."
tags: [qc, qa-flags, modis, landsat, sentinel-2, bitfield]
timestamp: 2026-07-05
status: verified
verified: 2026-07-06
verified_by: OSP steward review
evidence:
  - https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands
---

# Satellite QA flag decoding

Product-specific bit and class layouts for the QC QA-flag check (step 5).
QA layers are bit-packed integers decoded with bitwise operations, never
arithmetic comparisons on the packed value (that refusal lives in the
quality-control skill); these are the layouts it reads.

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
pixels that removed.
