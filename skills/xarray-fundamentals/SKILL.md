---
name: xarray-fundamentals
description: xarray selection, resampling, groupby, area-weighted means, Dask chunking, cftime calendars for gridded earth science data.
user-invocable: false
---

# xarray-fundamentals

Background expertise for manipulating gridded earth science data with
xarray without the classic silent errors.

## Selection

- Label-based `sel` for coordinates, positional `isel` for indices; never
  index a physical axis by position when a labeled coordinate exists.
- Point extraction uses `method="nearest"` (optionally `tolerance=`);
  bare `sel(lat=41.9)` on float coordinates raises or silently misses.
- Range slices require monotonic coordinates: `sortby("lat")` first when
  latitude descends, and mind the longitude convention (0..360 vs
  -180..180) before slicing a region that crosses the seam.
- Conditional selection is `where(cond)` (keeps shape, inserts NaN) or
  `where(cond, drop=True)`; boolean masks combine with `&`/`|`, not
  `and`/`or`.

## Resampling and groupby

Two different operations, commonly confused:

- `resample(time="MS").mean()` aggregates along contiguous time bins
  (monthly means from daily data). Frequency aliases: `MS` month start,
  `QS-DEC` quarters anchored at December, `YS` year start.
- `groupby("time.month").mean()` composites across years (a 12-value
  climatology), collapsing time.

The canonical climatology-and-anomaly pattern:

```python
base = ds.sel(time=slice("1991-01-01", "2020-12-31"))
clim = base.groupby("time.month").mean("time")
anom = ds.groupby("time.month") - clim
```

**A climatology or anomaly is meaningless without its baseline; state the
baseline period (for example 1991-2020) in the output, every time.**

Seasonal means: `resample(time="QS-DEC").mean()` puts December with the
following January and February. `groupby("time.season")` labels months
DJF/MAM/JJA/SON but groups December with its own calendar year's January
and February, which is almost never what a DJF mean intends; the
`conventions/calendars.md` concept records this trap.

## Area-weighted means: never unweighted

Grid cells shrink toward the poles on regular lat-lon grids. An unweighted
`.mean(["lat", "lon"])` over-weights high latitudes and silently biases
every global or regional statistic; for global mean surface temperature
the bias is on the order of tenths of a degree, comparable to the signals
being studied. The rule: **spatial means over a lat-lon grid are
cos(latitude)-weighted, always.**

```python
weights = np.cos(np.deg2rad(ds.lat))
gm = ds.weighted(weights).mean(["lat", "lon"])
```

- `ds.weighted(w)` handles NaN correctly (weights of missing cells are
  excluded from the normalization); a hand-rolled
  `(ds * w).mean() / w.mean()` does not, and disagrees wherever data has
  gaps.
- When the product provides true cell areas or bounds (curvilinear and
  model grids), weight by the cell-area field instead of cos(lat);
  cos(lat) is exact only for regular lat-lon spacing.
- Zonal means (`mean("lon")`) need no latitude weighting; meridional and
  regional means do.

## Dask and chunking

- `open_dataset(path, chunks={})` opens lazily with on-disk chunking;
  explicit dicts (`chunks={"time": 120}`) override. Aim for chunks of
  roughly 100 MB; thousands of tiny chunks cost more scheduling than
  compute.
- Chunk along dimensions you slice, keep dimensions you reduce over
  contiguous where possible; rechunk deliberately with
  `.chunk({"time": -1})` before operations that need whole axes
  (quantiles, some groupbys).
- Nothing computes until `.compute()` (returns in-memory result),
  `.persist()` (keeps it on the cluster), or plotting forces it. Check
  `ds.nbytes / 1e9` before computing and state the compute scale: small
  (laptop), medium (Dask cluster), large (HPC), per SPEC §0.4.
- `xr.open_mfdataset` parallelizes multi-file opens but silently aligns
  coordinates; pass `combine="by_coords"` and check the result's time
  axis is monotonic with no duplicates.

## cftime calendars

Model and reanalysis output on `360_day`, `noleap`, or `all_leap`
calendars decodes to cftime objects (`use_cftime=True` forces this).
What works: `sel` with date strings, `resample`, `groupby("time.month")`.
What breaks: direct comparison or arithmetic against numpy `datetime64`,
and concatenating datasets on different calendars. Align calendars
explicitly with `ds.convert_calendar("standard", align_on="date")` (or
keep everything in cftime), and say so in the methods, since dropping
February 29 or day-361 changes annual statistics slightly. The
`conventions/calendars.md` concept carries the details.

## Must NOT

- Never compute an unweighted spatial mean over a lat-lon grid.
- Never report a climatology or anomaly without stating the baseline
  period.
- Never use `groupby("time.season")` for DJF means across the year
  boundary; use `resample(time="QS-DEC")`.
- Never compare cftime and numpy datetime values directly.
- Never trigger eager computation on data larger than memory; check
  `nbytes`, chunk, and state the compute scale.
- Never assume `open_mfdataset` produced a clean time axis; verify
  monotonicity and duplicates.
