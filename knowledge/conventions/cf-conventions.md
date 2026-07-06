---
type: convention
title: CF conventions for analysis outputs
description: "The CF metadata practice this org's outputs follow: standard names, units, coordinate attributes, grid mappings, history provenance."
tags: [cf, metadata, netcdf, provenance]
timestamp: 2026-07-04
status: verified
verified: 2026-07-04
verified_by: OSP steward review
---

# CF conventions for analysis outputs

The Climate and Forecast (CF) conventions
(https://cfconventions.org/cf-conventions/cf-conventions.html) are the
metadata contract for gridded earth science data. The parts that carry
the most weight in practice:

- **Variables** carry `units` (UDUNITS-parseable) and, where the CF
  standard-name table defines one, `standard_name`; `long_name` covers
  the rest. Tools match on standard names, humans read long names.
- **Coordinates** carry `units`, `standard_name`, and `axis` where
  applicable. Time is encoded as a number with a units string ("days
  since 1850-01-01") plus a `calendar` attribute; the calendar is part
  of the data, not a display preference (see
  [calendars](calendars.md)).
- **Projected data** names a `grid_mapping` variable holding the CRS
  parameters; latitude-longitude cannot be assumed from coordinate
  names alone.
- **Cell semantics**: `cell_methods` states what a value represents
  ("time: mean"), and `bounds` arrays define cell edges. Exact area
  weights come from bounds when present; cos-latitude weighting is the
  approximation for regular grids without them.
- **Missing data** is declared with `_FillValue` (CF §2.5.1); sentinel
  conventions that skip the attribute are the trap recorded in
  [common-fill-values](common-fill-values.md).
- **Packed data**: integer variables carrying `scale_factor` and/or
  `add_offset` reconstruct physical values as
  `packed * scale_factor + add_offset` (CF §8.1); xarray applies this
  when `mask_and_scale=True` (the default). Compute on the unpacked
  values, and note that `_FillValue` is matched against the packed
  integer before scaling.
- **Global attributes**: `title`, `institution`, `source`,
  `references`, `Conventions` (the CF version), `license`, and a
  `history` that appends one timestamped line per processing step,
  newest first. The history attribute is the provenance that travels
  with the file.

Compliance checkers exist (the CF-checker, `cfchecks`) and catch most
omissions mechanically; the items above are the ones that change
analysis outcomes rather than just tidiness.
