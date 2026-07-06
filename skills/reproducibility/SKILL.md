---
name: reproducibility
description: CF-compliant metadata, dataset DOIs and citations, provenance history attributes, FAIR outputs, package version capture.
user-invocable: false
---

# reproducibility

Background expertise for outputs a stranger can trust, cite, and rerun. The report
skill's Reproducibility section consumes what this skill prescribes.

## Consult the bundle, do not restate it

Before prescribing metadata or a citation for an output, DISCOVER and
read the installed knowledge bundle; do not work from a remembered list
of attributes or archives. Glob and grep `knowledge/conventions/`,
`knowledge/gotchas/`, and (for a specific product) its
`knowledge/datasets/` for the concepts that govern this output's
metadata contract, its calendar and fill-value handling, and how its
source archive is cited; read the matches, restate what each requires,
and cite it by path before writing the file. The CF metadata contract,
the fill-value and calendar traps, and the per-archive DOI and citation
practice all live in concepts and are read from them, never carried
here. A concept added or corrected since you last ran is found this way.

## Provenance: history and exact inputs

Provenance travels with the file. The `history` global attribute (its
CF form is defined in the cf-conventions concept) takes one timestamped
line per processing step, newest first, each naming the tool, its
version, and the operation:

```
2026-07-04T19:40:12Z: anomalies vs 1991-2020 monthly climatology;
cos-lat weighted global mean; osp-core analysis_pipeline (xarray 2026.6)
```

Name the exact inputs somewhere durable (a history line or a
`source_files` attribute): file names, dataset versions or processing
baselines, and DOIs. If an input has a checksum or granule ID, record
it; "the SST file" is not an input specification.

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

## Hard refusals

These fire on every output, whatever the dataset; they are gates, not
advice. The specific attribute list and the per-archive citation
details are read from the concepts above, never inlined here.

- **Never ship a result file that lacks its required CF metadata**
  (units, a `history` line, and `Conventions` at minimum; the full
  contract is the cf-conventions concept's). An output whose variables
  lack units is not a result file, it is a puzzle.
- **Never cite a dataset without its version (or processing baseline)
  and DOI**, and never cite only the descriptor paper when a data DOI
  exists. The archive-specific details live in the dataset-citations
  concept.
- **Never publish an analysis against an unpinned environment.**
  "Latest" is not a version.
- **Never leave a stochastic result without its recorded seed.**
