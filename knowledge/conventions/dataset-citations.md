---
type: convention
title: "Dataset DOIs and citations by archive"
description: "Where the citable DOI lives per archive and what a complete data citation names: version or processing baseline, DOI, and an access date for records that update in place."
tags: [citation, doi, provenance, fair, reproducibility]
timestamp: 2026-07-05
status: draft
evidence:
  - "internal: relocated from core/skills/reproducibility/SKILL.md during the knowledge-coupling migration, needs a steward evidence link"
---

# Dataset DOIs and citations by archive

Cite the data itself, with version and DOI, not just the paper about it.
The archive determines where the citable identifier lives and what a
complete citation names.

| Archive | Where the DOI lives, what to cite |
|---|---|
| PO.DAAC (NASA ocean) | dataset landing page; cite ShortName + version + DOI |
| NSIDC DAAC (cryosphere) | dataset landing page; DOI per dataset and version |
| GES DISC / LP DAAC / ORNL DAAC | landing page DOI; product name + collection/version |
| Copernicus CDS (ERA5 and kin) | dataset DOI on the CDS record, plus the required C3S attribution line |
| ESGF (CMIP6) | per-dataset citation via the WDC Climate citation service; cite model, experiment, variant label, version |
| NOAA NCEI | dataset landing page DOI; include access date for evolving records |
| USGS (Landsat) | collection-level DOI plus product identifier |
| Zenodo (software, community data) | version DOI for exact reuse; concept DOI for the project as a whole; cite the version DOI in methods |

Two rules cut across the table:

- **Name the exact version everywhere.** "ERA5" without a version,
  period, and DOI is not a citation; a data DOI carried without its
  version string is ambiguous.
- **State the access date when a record updates in place.** Near-real-time
  products and evolving records (many NOAA NCEI series) change under a
  fixed identifier, so the citation pins when it was read.

**Zenodo, concept vs version DOI.** Zenodo mints two DOIs: a *concept*
DOI that always resolves to the newest version (cite it for the project
as a whole) and a *version* DOI that resolves to one exact deposit.
Exact reuse (the case a methods section documents) cites the version
DOI; confusing the two lets a "reproducible" citation drift to whatever
was uploaded last.
