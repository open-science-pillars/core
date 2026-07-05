---
type: convention
title: Calendar handling, and the DJF year-boundary trap
description: "CF calendars, cftime, month-length weighting, and the DJF season trap: December belongs to the following winter, not its own calendar year's."
tags: [calendar, cftime, seasons, djf, time]
timestamp: 2026-07-04
status: verified
verified: 2026-07-04
verified_by: OSP steward review
---

# Calendar handling, and the DJF year-boundary trap

## The DJF trap

A DJF (December-January-February) seasonal mean spans the year
boundary: December 1999 belongs to winter 1999/2000, together with
January and February 2000. Grouping by `time.season` labels months
correctly as DJF but aggregates December with its own calendar year's
January and February, months eleven and ten earlier, which is almost
never the intended winter. Quarterly resampling anchored at December
(`QS-DEC` frequency) assigns December to the following January and
February and is the correct grouping for cross-year seasons. Edge
seasons are incomplete (the first DJF lacks its December's year
predecessor; the last may lack January and February) and are dropped or
flagged, not silently averaged from two months.

## CF calendars and cftime

Model and reanalysis output uses CF calendars beyond the real one:
`standard`/`proleptic_gregorian`, `noleap` (365-day), `all_leap`,
`360_day`. Non-standard calendars decode to cftime objects, which
support label selection, resampling, and groupby, but not direct
comparison or arithmetic with numpy datetime64 values, and datasets on
different calendars do not concatenate. Calendar alignment
(`convert_calendar`) drops or duplicates days (February 29, day 361 to
365), which shifts annual statistics slightly; converted data says so
in its methods.

## Month-length weighting

An annual mean of twelve monthly means over-weights February unless
weighted by days per month, and the day counts come from the data's own
calendar (30 for every month of `360_day`, never a hardcoded table).
The same applies to seasonal means (DJF is 90 or 91 days by calendar
and leap status) and to any aggregation of unequal periods.

References: CF conventions, the calendar attribute section (numbered
§4.4.3 in the CF-1.14 draft; section numbers drift between versions),
https://cfconventions.org/cf-conventions/cf-conventions.html#calendar;
xarray time-series documentation for cftime behavior,
https://docs.xarray.dev/en/stable/user-guide/weather-climate.html.
