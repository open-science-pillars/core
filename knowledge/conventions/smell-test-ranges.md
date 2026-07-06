---
type: convention
title: "Smell-test anchors: order-of-magnitude sanity ranges for headline earth-science quantities"
description: "Cross-cutting order-of-magnitude anchors used by the post-computation review: the expected range a headline global quantity should sit near, so an out-of-anchor value is flagged instead of reported."
tags: [smell-test, sanity-check, expected-range, climatology, review]
timestamp: 2026-07-05
status: draft
evidence:
  - "internal: relocated from core/skills/analysis-review/SKILL.md during the knowledge-coupling migration, needs a steward evidence link"
---

# Smell-test anchors: order-of-magnitude sanity ranges for headline earth-science quantities

Order-of-magnitude anchors for the post-computation review. A headline
value outside its anchor is suspect until explained; inside but odd
warrants a second look. These are cross-cutting reference ranges,
consulted at review time and cited, never carried inside a skill.

**These drift, which is why they are knowledge and not hardcoded.** The
warming trend, the sea-level rate, and the Arctic sea-ice extent all
change with the observing era; the salinity and temperature climatology
shift with the region and reference period. Read the current anchor from
here (and update this concept when the science moves), rather than
freezing a number into a procedure.

## The anchors

| Quantity | Anchor |
|---|---|
| global mean 2 m temperature | about 288 K (15 C) |
| recent global warming trend | 0.1 to 0.3 K/decade |
| global mean precipitation | about 2.7 mm/day |
| global mean sea level rise | 3 to 4.5 mm/yr recent decades |
| ENSO Nino3.4 anomaly | within about +/-3 K |
| Arctic September sea ice extent | order 4 to 5 million km2 recent years |
| surface salinity, open ocean | 32 to 38 psu |

## Domain quantities defer to their domain recipe concepts

A quantity that has its own domain recipe concept reads its expected
range from that recipe, not from this table. For example, meridional
heat transport at 26.5N in the Atlantic (order 1 PW) is stated with its
comparison spread by the ocean-science bundle's recipe concept
(`recipes/ecco-mht-26n.md`); consult that, and never invent a number
when a recipe exists.

## Unit smells (the diagnostic, not a fact)

Most out-of-anchor values are unit mismatches, resolved by the
invariant unit conversions the analyst already knows: a 273-ish offset
is K vs C; a factor about 30 on precipitation is mm/day vs mm/month; a
factor 100 on fractions is percent vs fraction; a factor 1000 on
transport is TW vs PW. This is a diagnostic technique (invariant,
universal), recorded here beside the anchors it resolves.
