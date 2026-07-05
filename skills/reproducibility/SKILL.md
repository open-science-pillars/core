---
name: reproducibility
description: CF-compliant metadata, dataset DOIs and citations, provenance history attributes, FAIR outputs, package version capture.
user-invocable: false
---

# reproducibility

Background expertise for outputs a stranger can trust, cite, and rerun.
Authored in Session 4 per SPECIFICATION.md v0.5.1 §3.3. The report
skill's Reproducibility section consumes what this skill prescribes.

## CF-compliant metadata on every output

Every saved dataset carries:

- Per variable: `units` (UDUNITS-parseable), `long_name`, and
  `standard_name` where one exists in the CF standard-name table; fill
  values declared, not implied.
- Per coordinate: `units`, `standard_name`, `axis` where applicable;
  time with proper CF units string and `calendar`.
- Global: `title`, `institution`, `source`, `history`, `references`,
  `Conventions` (the CF version targeted), and `license`.

The `conventions/cf-conventions.md` concept carries the details; the
short version is that an output whose variables lack units is not a
result file, it is a puzzle.

## The history attribute: provenance that travels with the file

Append one timestamped line per processing step to the global `history`
attribute, newest first, stating tool, version, and operation:

```
2026-07-04T19:40:12Z: anomalies vs 1991-2020 monthly climatology;
cos-lat weighted global mean; osp-core analysis_pipeline (xarray 2026.6)
```

Name the exact inputs somewhere durable (history line or a
`source_files` attribute): file names, dataset versions or processing
baselines, and DOIs. If an input has a checksum or granule ID, record
it; "the SST file" is not an input specification.

## Dataset DOIs and citations: the quick table

Cite the data itself, with version and DOI, not just the paper about it.

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

Two rules: name the exact version everywhere ("ERA5" without a version,
period, and DOI is not a citation), and when a record updates in place
(NRT products, evolving records), state the access date.

## FAIR outputs, practically

- **Findable:** an identifier (DOI when published, stable path
  otherwise) and metadata rich enough to be discovered without opening
  the file.
- **Accessible:** open formats (NetCDF, Zarr, GeoTIFF, CSV), no bespoke
  binary blobs.
- **Interoperable:** CF names, standard units, documented grids.
- **Reusable:** an explicit license, the provenance chain above, and
  stated caveats (including the uncertainty statement the house rule
  requires).

## Package version capture

- Record the versions that produced a result: Python plus the
  load-bearing packages (xarray, dask, numpy, and the domain libraries
  used), in the output's global attributes and in the report's
  Reproducibility section.
- Ship the environment: a pinned `environment.yml` or lock file beside
  published analyses; "latest" is not a version.
- Record random seeds wherever stochastic methods run (bootstrap,
  Monte Carlo propagation, ML training), and the fixture or subset
  identity for any published test result.

## Must NOT

- Never save an output without units, history, and Conventions
  attributes.
- Never cite a dataset without its version (or processing baseline) and
  DOI; never cite only the descriptor paper when a data DOI exists.
- Never publish an analysis against an unpinned environment.
- Never confuse Zenodo concept and version DOIs: exact reuse cites the
  version.
- Never leave a stochastic result without its recorded seed.
