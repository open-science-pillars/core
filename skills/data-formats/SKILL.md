---
name: data-formats
description: Open and inspect NetCDF, HDF4/5, GeoTIFF, Zarr, GRIB, CSV earth science files with xarray, rioxarray, cfgrib; fill values, time decoding, CRS, chunking.
user-invocable: false
---

# data-formats

Background expertise for opening earth science data files correctly on the
first try, and for diagnosing the openings that fail.

## Identify the format first: magic bytes, not extensions

Extensions lie. A `.nc` file can be classic NetCDF-3 or HDF5-based
NetCDF-4 (different engines); a `.hdf` file can be HDF4 or HDF5 (different
libraries entirely). Check the leading bytes before choosing an opener:

```python
with open(path, "rb") as f:
    head = f.read(8)
```

| Leading bytes | Format |
|---|---|
| `CDF\x01` or `CDF\x02` | NetCDF-3 classic / 64-bit offset |
| `\x89HDF\r\n\x1a\n` | HDF5 (includes NetCDF-4) |
| `\x0e\x03\x13\x01` | HDF4 (MODIS-era products) |
| `II*\x00` or `MM\x00*` | TIFF / GeoTIFF (little / big endian) |
| `GRIB` | GRIB (byte 8 gives the edition) |
| no magic; a directory (or object store) containing `.zgroup`, `.zarray`, or `zarr.json` | Zarr (v2 / v3) |
| printable text, delimiter-separated | CSV or similar; sniff, do not assume |

A wrong-looking magic number on a downloaded file usually means a
truncated or HTML-error-page download; compare file size against the
archive listing before debugging anything else.

## Openers

| Format | Opener | Notes |
|---|---|---|
| NetCDF-3/4 | `xr.open_dataset(path)` | engine `netcdf4` or `h5netcdf`; both read NetCDF-4, only `netcdf4` reads classic directly |
| HDF5 (non-NetCDF layout) | `xr.open_dataset(path, engine="h5netcdf")` or `h5py` | satellite L1/L2 products often need group selection: `group="..."` |
| HDF4 | `xr.open_dataset(path, engine="netcdf4")` if libnetcdf has HDF4 support; else `pyhdf` or `rioxarray` | conda-forge libnetcdf carries HDF4 support; pip wheels usually do not |
| GeoTIFF | `rioxarray.open_rasterio(path)` | preserves CRS and transform; plain xarray does not |
| Zarr | `xr.open_zarr(store)` | try `consolidated=True` first; fall back explicitly |
| GRIB | `xr.open_dataset(path, engine="cfgrib")` | heterogeneous files need `backend_kwargs={"filter_by_keys": {...}}` |
| CSV | `pandas.read_csv(...)` then `.to_xarray()` | `parse_dates=`, explicit `na_values=`; never trust dtype inference on station data |

Open lazily by default (`chunks={}` engages Dask with on-disk chunking).
Declare the compute scale rather than assuming a machine: small (laptop),
medium (Dask cluster), large (HPC or burst) per SPEC §0.4.

## Fill values and packing

`mask_and_scale=True` (the default) applies `_FillValue`,
`missing_value`, `scale_factor`, and `add_offset` from attributes. Two
traps:

1. **Unmasked sentinels.** Files that omit the `_FillValue` attribute but
   use sentinel values anyway (-9999, -32767, 1e20 and kin) decode as real
   data and silently bias every statistic. After opening, check
   `float(var.min())` and `float(var.max())` against physical plausibility
   before computing anything. The core knowledge bundle's
   `conventions/common-fill-values.md` concept carries the sentinel list
   and detection recipe.
2. **Packed integers.** If a variable that should be continuous arrives as
   int16, packing attributes were probably lost or ignored; check
   `var.encoding` for `scale_factor` before trusting values.

## Time decoding

CF time units (`days since 1850-01-01`) decode automatically. Non-standard
calendars (`360_day`, `noleap`, `all_leap`) need cftime objects: pass
`use_cftime=True` and expect cftime datetimes downstream (resampling works;
direct numpy datetime comparisons do not). When decoding fails, open with
`decode_times=False`, inspect `time.attrs["units"]` and
`time.attrs["calendar"]`, repair, then `xr.decode_cf(ds)`. The
`conventions/calendars.md` concept records the DJF year-boundary trap.

## CRS and coordinates

- GeoTIFF via rioxarray: CRS lives at `da.rio.crs`; reproject with
  `da.rio.reproject(...)`. Never assume EPSG:4326.
- NetCDF: CF encodes projection in a `grid_mapping` variable; projected
  data has `x`/`y` coordinates in meters, not degrees. Check before
  treating coordinates as lat/lon.
- Longitude arrives as either 0..360 or -180..180; normalize deliberately
  (`ds.assign_coords(lon=(ds.lon + 180) % 360 - 180).sortby("lon")`) and
  say which convention the output uses.
- Latitude may be descending; `sortby("lat")` before slicing with ranges.

## Per-format failure guidance

| Symptom | Likely cause | Fix |
|---|---|---|
| `[Errno -51] NetCDF: Unknown file format` | file is not what the extension claims, or truncated download | check magic bytes and file size against the archive |
| `unable to decode time units` | non-CF units string or exotic calendar | `decode_times=False`, inspect attrs, `use_cftime=True`, then `xr.decode_cf` |
| cfgrib: `multiple values for unique key` | GRIB file mixes levels or steps | `backend_kwargs={"filter_by_keys": {"typeOfLevel": "isobaricInhPa"}}` (or the relevant key) |
| Zarr: `KeyError: '.zgroup'` or metadata not found | unconsolidated v2 store, v3 store, or wrong path/prefix | `consolidated=False`; confirm store layout and zarr-python version |
| GeoTIFF opens with row/col integer coords | opened without rioxarray, or georeferencing absent | reopen with `rioxarray.open_rasterio`; if CRS is still None the file lacks it, ask the producer |
| HDF4 open fails with netcdf4 engine | libnetcdf built without HDF4 | conda-forge `libnetcdf`, or read via `pyhdf` |
| variable is all NaN after open | bad `_FillValue`/`valid_range` attrs masking everything | `mask_and_scale=False`, inspect raw values and attrs, mask manually |
| times are `object` dtype strings (CSV) | dates not parsed | `parse_dates=` in `read_csv`, then `.to_xarray()` |

## Must NOT

- Never trust a file extension over magic bytes.
- Never report a statistic before confirming fill values are masked.
- Never assume EPSG:4326, a longitude convention, or an ascending latitude
  axis without checking.
- Never load a multi-GB dataset eagerly; open lazily and state the compute
  scale.
- Never paper over a time-decoding failure by dropping the time axis.

## What "open and summarize" means here

A complete summary of an opened dataset states: dimensions and sizes;
coordinate ranges (with longitude convention and latitude order); variables
with units and dtypes; time span, cadence, and calendar; CRS or grid
mapping if any; fill-value status (masked, or sentinels detected); and
in-memory vs on-disk size with the chunking in effect.
