# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=2,<3", "httpx>=0.27,<1", "zstandard>=0.22,<1"]
# ///
"""observations: one thin MCP server over seven authoritative
observation sources that compose with the ocean and hydrology
knowledge work.

  usgs_*       USGS Water Data API: stream gauges of record
  nwis_*       USGS Water Data API: discrete groundwater levels
  coops_*      NOAA CO-OPS: tide and water-level stations of record
  argo_*       Argo profiling floats via the Ifremer ERDDAP
  psmsl_*      PSMSL: the long-record tide-gauge authority
  hydrocron_*  PO.DAAC Hydrocron: SWOT river and lake series, with
               the product collection named rather than defaulted
  gnss_*       Nevada Geodetic Laboratory: MIDAS station velocities
  nwm_*        NOAA National Water Model retrospective on AWS

DESIGN. Every tool is a paper-thin translation from parameters to one
official HTTPS request and a trimmed response. No science lives here:
correctness knowledge (datums, offsets, quality flags, parameter
codes) lives in the connector concepts that cite this file, and
anything attested happens in sanctioned executors that never call
this server. Gates never depend on connectors.

RESPONSE CONTRACT (v0.5). Every successful response carries
retrieval provenance: retrieved_at (UTC), request_url (the resolved
request, never a credential), server_version. Where a source serves
more than one product collection, the response also carries the
collection that answered and who named it, because a series whose
version is not recorded cannot be joined to another one safely. Truncation keeps the
TAIL of a series (the recent record), states the total, and names the
time span actually returned, so a truncated answer can never silently
masquerade as the whole record; narrow the time window to reach
earlier rows. Failures return a structured {"error", "source",
"status", "detail"} with the agency's own message in detail, never a
bare exception, so "no data for that parameter" is never misreported
as "the agency is down". One bounded retry with backoff on 429 and
5xx, except on api.waterdata.usgs.gov, where a retry would spend a
second request against an hourly bucket; a minimum interval per host
keeps the client polite.

USGS PAGING. The Water Data API serves pages (limit 50000 at most)
with a cursor next link and no matched-row count, and a sorted
request cannot be paged. The usgs tools therefore fetch unsorted at
the page limit without geometry, follow next links under a request
budget, sort locally, and count what they walked: total_rows is a
walked count, never an estimate. When a next link remains after the
budget the tool returns a structured error naming the budget rather
than a silent head.

NWM CHUNKS. The National Water Model retrospective is a zarr store
on a public bucket, not an API: a reach's series lives one column
deep in chunks of 672 hours by 30000 reaches, so one tool call reads
the store metadata once, the reach and gauge index arrays once (2.9
MB and 68 KB), and then one streamflow chunk (4 to 9 MB measured)
and one time chunk per 28-day block of the window, under a budget of
14 chunks: at most 28 chunk requests and roughly 50 to 130 MB for one
call. The tool states the budget when a window exceeds it. Only the
CONUS and Alaska stores are served: the Hawaii and PR stores are
blosc/lz4 compressed (and Hawaii's time axis is in minutes), which
this server does not decode, so those domains are refused before any
request.

WHAT LEAVES YOUR MACHINE. Query parameters only (station, well,
float, lake and reach identifiers, coordinates, bounding boxes, time
ranges), sent over HTTPS to the agency endpoints named per tool. One
optional credential exists: if API_USGS_PAT is set in the
environment, its value is sent as an X-Api-Key header to
api.waterdata.usgs.gov only, and to no other host; it never appears
in a request URL, a response, or an error. No other tool sends any
credential: the geodesy tables, the Hydrocron service and the
National Water Model bucket are read anonymously. No file, no local
path, and no data you hold is ever sent.

Run: uv run observations_mcp.py            (stdio MCP server)
     uv run observations_mcp.py --selftest (live probes + regressions)
     uv run observations_mcp.py --test     (offline: parsers vs fixtures)
     uv run observations_mcp.py --record-fixtures (refresh fixtures, live)
"""
from __future__ import annotations

import array
import base64
import datetime as dt
import json
import math
import os
import re
import sys
import time
from functools import wraps
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
import zstandard
from mcp.server.mcpserver import MCPServer

VERSION = "0.5.0"
UA = {"User-Agent": f"osp-observations-mcp/{VERSION}"}
MAX_ROWS = 500
MIN_INTERVAL_S = 0.5
USGS_API = "https://api.waterdata.usgs.gov/ogcapi/v0/collections"
USGS_HOST = "api.waterdata.usgs.gov"
USGS_KEY_VAR = "API_USGS_PAT"
USGS_PAGE_LIMIT = 50000   # the API's maximum page size
USGS_PAGE_BUDGET = 4      # requests one tool call may spend on next links
# The Nevada Geodetic Laboratory's MIDAS velocity tables, one per
# reference frame. IGS20 is the current table (rebuilt weekly under
# gps_timeseries/IGS20); IGS14 is the superseded table the laboratory
# keeps under velocities/, dated by its Last-Modified header.
NGL_MIDAS = {
    "IGS20": "https://geodesy.unr.edu/gps_timeseries/IGS20/midas/midas.IGS.txt",
    "IGS14": "https://geodesy.unr.edu/velocities/midas.IGS14.txt",
}
NWM_BUCKET = "https://noaa-nwm-retrospective-3-0-pds.s3.amazonaws.com"
NWM_RETROSPECTIVE = "NWM Retrospective v3.0"
# The domains whose chrtout stores this server decodes (zstd, hours
# since an instant). Hawaii and PR are blosc/lz4 stores, Hawaii's time
# axis in minutes, read 2026-09-15; they are refused by name.
NWM_DOMAINS = ("CONUS", "Alaska")
NWM_UNSERVED_DOMAINS = {
    "Hawaii": "its chrtout store is blosc/lz4 compressed and its time axis "
              "is in minutes since 1994-01-01T00:15",
    "PR": "its chrtout store is blosc/lz4 compressed",
}
NWM_CHUNK_BUDGET = 14     # 28-day streamflow chunks one tool call may read
FIXTURES = Path(__file__).parent / "fixtures"
mcp = MCPServer("observations")
_last_call: dict[str, float] = {}


class SourceError(Exception):
    def __init__(self, source: str, status: int | None, detail: str):
        self.source, self.status, self.detail = source, status, detail
        super().__init__(detail)


def _headers(url: str) -> dict:
    """The user agent, plus the USGS key as a header on the USGS host
    only; the key is read from the environment at request time."""
    h = dict(UA)
    key = os.environ.get(USGS_KEY_VAR)
    if key and urlparse(url).netloc == USGS_HOST:
        h["X-Api-Key"] = key
    return h


def _fetch(source: str, url: str, params: dict | None = None) -> httpx.Response:
    host = urlparse(url).netloc
    wait = MIN_INTERVAL_S - (time.monotonic() - _last_call.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    last: SourceError | None = None
    for attempt in (1, 2):
        _last_call[host] = time.monotonic()
        try:
            r = httpx.get(url, params=params, headers=_headers(url),
                          timeout=60.0, follow_redirects=True)
        except httpx.HTTPError as e:
            last = SourceError(source, None, f"transport failure: {e!r}")
            time.sleep(2.0)
            continue
        if r.status_code < 400:
            return r
        if r.status_code == 429 and host == USGS_HOST:
            raise SourceError(source, 429, _usgs_429_detail(r))
        last = SourceError(source, r.status_code, r.text[:500])
        if r.status_code in (429, 500, 502, 503, 504) and attempt == 1:
            time.sleep(2.0)
            continue
        break
    raise last


def _usgs_429_detail(r: httpx.Response) -> str:
    """No retry on this host: name the variable and the reset window."""
    reset = r.headers.get("Retry-After") or r.headers.get("X-RateLimit-Reset")
    limits = {k: v for k, v in r.headers.items()
              if "ratelimit" in k.lower() or k.lower() == "retry-after"}
    keyed = USGS_KEY_VAR in os.environ
    return (f"rate limited by {USGS_HOST} ({'keyed' if keyed else 'unkeyed'} "
            f"bucket); not retried because a retry spends a second request "
            f"against an hourly bucket. Reset: "
            f"{reset + ' seconds' if reset else 'the current hour'}. "
            + ("" if keyed else
               f"Set {USGS_KEY_VAR} to a key from https://{USGS_HOST}/signup/ "
               "to use a per-key bucket; it is sent only as an X-Api-Key "
               "header. ")
            + f"Headers: {json.dumps(limits)}. Body: {r.text[:300]}")


def _meta(r: httpx.Response) -> dict:
    return {"retrieved_at":
            dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "request_url": str(r.request.url),
            "server_version": VERSION}


def guarded(source: str):
    """Failures become structured data the agent can reason about,
    never bare exceptions and never misdiagnoses."""
    def deco(fn):
        @wraps(fn)
        def inner(*a, **kw):
            try:
                return fn(*a, **kw)
            except SourceError as e:
                return {"error": f"{source} request failed",
                        "source": source, "status": e.status,
                        "detail": e.detail}
            except (KeyError, IndexError, ValueError, TypeError) as e:
                return {"error": f"unexpected response shape from {source}; "
                                 "the upstream schema may have changed",
                        "source": source, "status": None,
                        "detail": repr(e)[:500]}
        return inner
    return deco


def _cap(rows: list, tkey=None) -> dict:
    """Keep the TAIL (the recent record) and name what was returned."""
    total = len(rows)
    kept = rows[-MAX_ROWS:] if total > MAX_ROWS else rows
    out = {"rows": kept, "truncated": total > MAX_ROWS, "total_rows": total}
    if kept and tkey is not None:
        try:
            out["returned_span"] = [str(tkey(kept[0])), str(tkey(kept[-1]))]
        except Exception:
            pass
    if out["truncated"]:
        out["omitted"] = (f"{total - MAX_ROWS} earlier rows omitted; "
                          "narrow the time window to retrieve them")
    return out


# ------------------------------------------------------------- parsers
def parse_usgs(pages: list[dict]) -> dict:
    """Group Water Data API features (daily or continuous) into one
    series per location, parameter and statistic; rows carry the
    approval status and the qualifier list the API splits the legacy
    qualifier column into."""
    groups: dict[tuple, dict] = {}
    for page in pages:
        for f in page["features"]:
            p = f["properties"]
            k = (p["monitoring_location_id"], p["parameter_code"],
                 p["statistic_id"], p["time_series_id"])
            g = groups.setdefault(k, {
                "site": p["monitoring_location_id"].split("-", 1)[-1],
                "location_id": p["monitoring_location_id"],
                "parameter": p["parameter_code"],
                "statistic_id": p["statistic_id"],
                "unit": p.get("unit_of_measure"),
                "time_series_id": p["time_series_id"], "rows": []})
            g["rows"].append({"t": p["time"], "v": p["value"],
                              "approval": p.get("approval_status"),
                              "qualifiers": sorted(p.get("qualifier") or [])})
    out = []
    for k in sorted(groups):
        g = groups[k]
        rows = sorted(g.pop("rows"), key=lambda r: r["t"])
        out.append({**g, **_cap(rows, tkey=lambda r: r["t"])})
    if not out:
        raise SourceError("usgs", 200, "no observations returned for that "
                          "location, parameter and window (the API answers "
                          "an unknown site or parameter with an empty "
                          "collection, not an error); check the site "
                          "number and parameter code")
    return {"series": out}


def parse_coops(j: dict, product: str) -> dict:
    if "error" in j:
        raise SourceError("coops", 200, j["error"].get("message", str(j["error"])))
    key = "predictions" if product == "predictions" else "data"
    rows = [{"t": d.get("t"), "v": d.get("v")} for d in j.get(key, [])]
    return {**_cap(rows, tkey=lambda r: r["t"]),
            "metadata": j.get("metadata", {})}


def parse_erddap(j: dict) -> dict:
    t = j["table"]
    cols = t["columnNames"]
    tidx = cols.index("time") if "time" in cols else None
    tkey = (lambda r: r[tidx]) if tidx is not None else None
    return {"columns": cols, **_cap(t["rows"], tkey=tkey)}


def parse_psmsl(text: str) -> dict:
    rows, missing = [], 0
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 2:
            continue
        yr, v = float(parts[0]), int(parts[1])
        if v == -99999:
            missing += 1
            continue
        rows.append({"decimal_year": yr, "rlr_mm": v})
    if not rows:
        raise ValueError("no data rows parsed; check the station id")
    return {"datum": "RLR", "missing_months": missing,
            **_cap(rows, tkey=lambda r: r["decimal_year"])}


def parse_hydrocron(j: dict) -> dict:
    feats = j["results"]["geojson"]["features"]
    rows = [f["properties"] for f in feats]
    return _cap(rows, tkey=lambda r: r.get("time_str"))


def parse_usgs_field(pages: list[dict]) -> dict:
    """Group Water Data API field-measurements features (discrete
    readings taken on a site visit: groundwater levels, and the
    discharge and gage height measurements the same collection
    holds) into one series per location, parameter and series id.
    Rows carry the value, the approval status, the qualifier list,
    the vertical datum the reading is referenced to and the observing
    procedure, because a depth to water and an elevation above a
    datum are different numbers for the same well."""
    groups: dict[tuple, dict] = {}
    for page in pages:
        for f in page["features"]:
            p = f["properties"]
            k = (p["monitoring_location_id"], p["parameter_code"],
                 p["field_measurements_series_id"])
            g = groups.setdefault(k, {
                "site": p["monitoring_location_id"].split("-", 1)[-1],
                "location_id": p["monitoring_location_id"],
                "parameter": p["parameter_code"],
                "reading_type": p.get("reading_type"),
                "unit": p.get("unit_of_measure"),
                "series_id": p["field_measurements_series_id"], "rows": []})
            g["rows"].append({"t": p["time"], "v": p["value"],
                              "approval": p.get("approval_status"),
                              "qualifiers": sorted(p.get("qualifier") or []),
                              "vertical_datum": p.get("vertical_datum"),
                              "procedure": p.get("observing_procedure")})
    out = []
    for k in sorted(groups):
        g = groups[k]
        rows = sorted(g.pop("rows"), key=lambda r: r["t"])
        out.append({**g, **_cap(rows, tkey=lambda r: r["t"])})
    if not out:
        raise SourceError("usgs", 200, "no field measurements returned for "
                          "that site, parameter and window (the API answers "
                          "an unknown site or parameter with an empty "
                          "collection, not an error); check the site number "
                          "and parameter code, and note that a continuously "
                          "recorded well is served by the daily collection "
                          "through usgs_daily, not by field-measurements")
    return {"series": out}


MIDAS_COLUMNS = 27   # per the laboratory's midas.readme.txt


def parse_midas(text: str) -> dict[str, dict]:
    """One record per station from a MIDAS velocity table. The columns
    are the laboratory's (midas.readme.txt): station, version, first
    and last epoch (decimal years), duration, epoch counts, velocity
    pairs, east north up velocities and their uncertainties (metres
    per year in the file, millimetres per year here), offsets, outlier
    fractions, pair standard deviations, assumed steps, then latitude,
    longitude and height. Longitudes in the file run below -180 for
    eastern stations and are normalised to -180..180 here."""
    out: dict[str, dict] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < MIDAS_COLUMNS:
            continue
        lon = ((float(parts[25]) + 180.0) % 360.0) - 180.0
        mm = lambda i: round(float(parts[i]) * 1000.0, 3)
        out[parts[0]] = {
            "station": parts[0], "midas_version": parts[1],
            "first_epoch": float(parts[2]), "last_epoch": float(parts[3]),
            "duration_years": float(parts[4]),
            "n_epochs": int(parts[5]), "n_good_epochs": int(parts[6]),
            "n_velocity_pairs": int(parts[7]),
            "east_mm_yr": mm(8), "north_mm_yr": mm(9), "up_mm_yr": mm(10),
            "east_u_mm_yr": mm(11), "north_u_mm_yr": mm(12),
            "up_u_mm_yr": mm(13), "steps_assumed": int(parts[23]),
            "lat": float(parts[24]), "lon": round(lon, 10),
            "height_m": float(parts[26])}
    if not out:
        raise ValueError("no MIDAS rows parsed; the table format may have "
                         "changed")
    return out


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def nearest_stations(table: dict[str, dict], lat: float, lon: float,
                     n: int = 3) -> list[dict]:
    """The n stations of a MIDAS table nearest a point, each with its
    great-circle distance in kilometres."""
    ranked = sorted(
        ({"station": k, "distance_km": round(
            _haversine_km(lat, lon, v["lat"], v["lon"]), 3)}
         for k, v in table.items()),
        key=lambda d: d["distance_km"])
    return ranked[:n]


_ZARR_TYPECODES = {"<i2": "h", "<i4": "i", "<i8": "q", "<f4": "f", "<f8": "d"}


def zarr_decode(raw: bytes, zarray: dict):
    """Decode one zarr v2 chunk the way the retrospective stores write
    them: a zstd frame (or none), C order, little-endian numbers as an
    array, or fixed-width bytes as a list. Anything else is refused
    rather than guessed."""
    comp = (zarray.get("compressor") or {}).get("id")
    if comp == "zstd":
        try:
            buf = zstandard.ZstdDecompressor().decompressobj().decompress(raw)
        except zstandard.ZstdError as e:
            raise ValueError(f"zstd decompression failed: {e}")
    elif comp is None:
        buf = raw
    else:
        raise ValueError(f"unsupported zarr compressor {comp!r}")
    if zarray.get("filters") or zarray.get("order", "C") != "C":
        raise ValueError("unsupported zarr filters or array order")
    dtype = zarray["dtype"]
    if dtype.startswith("|S"):
        w = int(dtype[2:])
        return [buf[i:i + w] for i in range(0, len(buf), w)]
    a = array.array(_ZARR_TYPECODES[dtype])
    if a.itemsize != int(dtype[2:]):
        raise ValueError(f"array typecode width mismatch for {dtype}")
    a.frombytes(buf)
    if sys.byteorder != "little":
        a.byteswap()
    return a


def nwm_time_epoch(meta: dict) -> dt.datetime:
    """The instant hour zero of the store's time axis stands for, from
    the axis's own units attribute."""
    units = meta["time/.zattrs"]["units"]
    m = re.match(r"hours since (\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})", units)
    if not m:
        raise ValueError(f"time units {units!r} are not hours since an instant")
    return dt.datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}").replace(
        tzinfo=dt.timezone.utc)


def nwm_chunk_plan(meta: dict, index: int, start_date: str,
                   end_date: str) -> dict:
    """Which chunks hold one reach's hours in a window: the time chunk
    ids, the reach's chunk column and offset within it, and the hour
    range, from the store metadata alone. A window wider than the
    chunk budget is refused here, before any chunk is read."""
    za = meta["streamflow/.zarray"]
    t_len, f_len = za["chunks"]
    n_hours = za["shape"][0]
    epoch = nwm_time_epoch(meta)
    try:
        s = dt.datetime.fromisoformat(start_date).replace(tzinfo=dt.timezone.utc)
        e = dt.datetime.fromisoformat(end_date).replace(tzinfo=dt.timezone.utc)
    except ValueError as err:
        raise SourceError("nwm", None, f"dates must be YYYY-MM-DD: {err}")
    if e < s:
        raise SourceError("nwm", None, "end_date is before start_date")
    h0 = max(0, math.floor((s - epoch).total_seconds() / 3600))
    h1 = min(n_hours - 1, math.ceil(
        (e + dt.timedelta(days=1) - epoch).total_seconds() / 3600) - 1)
    if h1 < h0:
        last = epoch + dt.timedelta(hours=n_hours - 1)
        raise SourceError("nwm", None, f"the window lies outside the "
                          f"retrospective's time axis ({epoch.date()} to "
                          f"{last.date()})")
    k0, k1 = h0 // t_len, h1 // t_len
    if k1 - k0 + 1 > NWM_CHUNK_BUDGET:
        raise SourceError(
            "nwm", None,
            f"the window spans {k1 - k0 + 1} chunks of {t_len} hours; the "
            f"budget for one call is {NWM_CHUNK_BUDGET} chunks (about "
            f"{NWM_CHUNK_BUDGET * t_len // 24} days); narrow the window")
    return {"time_chunks": list(range(k0, k1 + 1)),
            "column": index // f_len, "offset": index % f_len,
            "chunk_hours": t_len, "chunk_features": f_len,
            "hour_range": [h0, h1], "epoch": epoch}


def nwm_daily_means(hours, values, epoch: dt.datetime, zattrs: dict,
                    hour_range: list[int], fill=None) -> list[dict]:
    """Mean of the hourly values within each UTC calendar day, the
    fill value excluded and the hours counted, with the store's own
    scale_factor and add_offset applied. The fill is the array's
    fill_value, and the attributes' missing_value stands in when the
    array declares none."""
    if fill is None:
        fill = zattrs.get("missing_value", zattrs.get("_FillValue"))
    scale = float(zattrs.get("scale_factor", 1.0))
    offset = float(zattrs.get("add_offset", 0.0))
    days: dict[str, list[float]] = {}
    for h, v in zip(hours, values):
        if h < hour_range[0] or h > hour_range[1] or v == fill:
            continue
        day = (epoch + dt.timedelta(hours=int(h))).date().isoformat()
        days.setdefault(day, []).append(v * scale + offset)
    return [{"date": d, "mean": round(sum(vs) / len(vs), 3),
             "n_hours": len(vs)} for d, vs in sorted(days.items())]


# ---------------------------------------------------------------- USGS
def _usgs_locations(sites: str) -> str:
    """Bare site numbers become the API's prefixed location ids."""
    ids = []
    for s in sites.split(","):
        s = s.strip()
        if s:
            ids.append(s if "-" in s else f"USGS-{s}")
    if not ids:
        raise SourceError("usgs", None, "sites is empty")
    return ",".join(ids)


_DURATION = re.compile(r"^P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$")


def _period_start(period: str, now: dt.datetime | None = None) -> str:
    """ISO 8601 duration (PnW, PnD, PTnH, PTnM and combinations) back
    from now, as a UTC instant for the datetime filter."""
    m = _DURATION.match(period.strip().upper())
    if not m or not any(m.groups()):
        raise SourceError("usgs", None, f"period {period!r} is not an ISO "
                          "8601 duration such as P7D, P2W or PT12H")
    w, d, h, mi = (int(x or 0) for x in m.groups())
    now = now or dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(weeks=w, days=d, hours=h, minutes=mi)
    return start.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _usgs_walk(collection: str, params: dict, fetch=_fetch) -> tuple[list[dict], httpx.Response]:
    """Fetch every page of one items query under the request budget.
    Returns the pages and the first response (whose URL is the
    request of record)."""
    url = f"{USGS_API}/{collection}/items"
    q = {**params, "limit": USGS_PAGE_LIMIT, "skipGeometry": "true"}
    pages, first = [], None
    for n in range(USGS_PAGE_BUDGET):
        r = fetch("usgs", url, q)
        first = first or r
        page = r.json()
        pages.append(page)
        nxt = next((l.get("href") for l in page.get("links", [])
                    if l.get("rel") == "next"), None)
        if not nxt:
            return pages, first
        if urlparse(nxt).netloc != USGS_HOST:
            raise SourceError("usgs", None, f"refusing a next link off "
                              f"{USGS_HOST}: {nxt}")
        url, q = nxt, None
    raise SourceError(
        "usgs", None,
        f"the window holds more than {USGS_PAGE_BUDGET * USGS_PAGE_LIMIT} "
        f"rows ({USGS_PAGE_BUDGET} pages of {USGS_PAGE_LIMIT}, the request "
        "budget for one call); narrow the time window or ask for fewer "
        "sites")


@mcp.tool()
@guarded("usgs")
def usgs_instantaneous(sites: str, parameter_cd: str = "00060",
                       period: str = "P7D") -> dict:
    """Continuous (instantaneous) values from USGS stream gauges.

    sites: comma-separated USGS site numbers (e.g. '01646500').
    parameter_cd: USGS parameter code; 00060 discharge cfs, 00065 gage
    height ft, 00010 water temperature C.
    period: ISO 8601 duration back from now (e.g. 'P7D'). Times are
    UTC; each row carries approval (Approved or Provisional) and the
    qualifier list (e.g. ESTIMATED, ICE). The continuous collection
    serves roughly the most recent year; the connector concept in the
    hydrology bundle keeps that fact dated.
    Source of record: api.waterdata.usgs.gov, collection continuous."""
    pages, r = _usgs_walk("continuous", {
        "monitoring_location_id": _usgs_locations(sites),
        "parameter_code": parameter_cd,
        "datetime": f"{_period_start(period)}/.."})
    return {**parse_usgs(pages), **_meta(r)}


@mcp.tool()
@guarded("usgs")
def usgs_daily(sites: str, parameter_cd: str = "00060",
               start_date: str = "", end_date: str = "") -> dict:
    """Daily values from USGS stream gauges (daily statistics,
    typically the mean, statistic_id 00003).

    start_date, end_date: YYYY-MM-DD, either side open when empty
    (both empty fetches the whole daily record and returns its tail).
    Same site and parameter codes as usgs_instantaneous; rows carry
    approval and qualifiers the same way.
    Source of record: api.waterdata.usgs.gov, collection daily."""
    p = {"monitoring_location_id": _usgs_locations(sites),
         "parameter_code": parameter_cd}
    if start_date or end_date:
        p["datetime"] = f"{start_date or '..'}/{end_date or '..'}"
    pages, r = _usgs_walk("daily", p)
    return {**parse_usgs(pages), **_meta(r)}


# --------------------------------------------------------------- CO-OPS
@mcp.tool()
@guarded("coops")
def coops_data(station: str, product: str = "water_level",
               datum: str = "MLLW", begin_date: str = "",
               end_date: str = "", latest: bool = False) -> dict:
    """NOAA CO-OPS tide and water-level station data.

    station: 7-digit CO-OPS id (e.g. '8443970' Boston).
    product: water_level, predictions, hourly_height, air_temperature,
    water_temperature, wind, currents.
    datum: MLLW, MSL, NAVD, STND. DATUMS DIFFER BY FEET; never compare
    series across datums without conversion.
    begin_date, end_date: yyyymmdd; or latest=True for the newest
    observation. Source of record: api.tidesandcurrents.noaa.gov."""
    p = {"station": station, "product": product, "datum": datum,
         "units": "metric", "time_zone": "gmt", "format": "json",
         "application": "osp-observations"}
    if latest:
        p["date"] = "latest"
    else:
        p["begin_date"], p["end_date"] = begin_date, end_date
    r = _fetch("coops",
               "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter", p)
    return {"station": station, "product": product, "datum": datum,
            "units": "metric", **parse_coops(r.json(), product), **_meta(r)}


# ----------------------------------------------------------------- Argo
_ERDDAP = "https://erddap.ifremer.fr/erddap/tabledap/ArgoFloats.json"


def _erddap_fetch(variables: str, constraints: list[str]) -> tuple[dict, dict]:
    q = quote(variables, safe="") + "".join(
        "&" + quote(c, safe="=") for c in constraints)
    r = _fetch("argo", f"{_ERDDAP}?{q}")
    return parse_erddap(r.json()), _meta(r)


@mcp.tool()
@guarded("argo")
def argo_search(lat_min: float, lat_max: float, lon_min: float,
                lon_max: float, time_min: str, time_max: str = "") -> dict:
    """Argo float profile positions in a box and time window.

    time_min, time_max: ISO 8601 (e.g. '2026-08-20T00:00:00Z').
    Returns float ids with profile positions and times, from the
    Ifremer ERDDAP serving the Argo GDAC; no credential is sent."""
    cons = [f"time>={time_min}", f"latitude>={lat_min}",
            f"latitude<={lat_max}", f"longitude>={lon_min}",
            f"longitude<={lon_max}"]
    if time_max:
        cons.append(f"time<={time_max}")
    data, meta = _erddap_fetch(
        "platform_number,cycle_number,latitude,longitude,time", cons)
    return {**data, **meta}


@mcp.tool()
@guarded("argo")
def argo_profile(platform_number: str, time_min: str,
                 time_max: str = "") -> dict:
    """Temperature and salinity profile rows for one Argo float.

    platform_number: WMO id as a string (e.g. '1902324').
    Rows are (cycle, time, pressure dbar, temp C, psal PSU); apply
    quality control before science use, which this tool does NOT do;
    the knowledge concepts carry the QC discipline."""
    cons = [f'platform_number="{platform_number}"', f"time>={time_min}"]
    if time_max:
        cons.append(f"time<={time_max}")
    data, meta = _erddap_fetch("cycle_number,time,pres,temp,psal", cons)
    return {**data, **meta}


# ---------------------------------------------------------------- PSMSL
@mcp.tool()
@guarded("psmsl")
def psmsl_monthly(station_id: int) -> dict:
    """Monthly mean sea level from PSMSL, Revised Local Reference.

    station_id: PSMSL id (e.g. 1 Brest, 12 New York; catalogue at
    psmsl.org). Values are millimetres on the station's RLR datum,
    defined roughly 7000 mm below mean sea level, so ABSOLUTE numbers
    are meaningless; use differences and trends. Missing value -99999
    rows are dropped and counted. Long records truncate to the RECENT
    tail; the returned_span field names what came back."""
    r = _fetch("psmsl", "https://psmsl.org/data/obtaining/rlr.monthly.data/"
               f"{station_id}.rlrdata")
    return {"station_id": station_id, **parse_psmsl(r.text), **_meta(r)}


# ------------------------------------------------------------ Hydrocron
# The collections Hydrocron serves, and the one this tool names for each
# feature when the caller does not choose. Naming one is not a style
# preference: the service picks a collection when the request omits it,
# that default has moved between product versions, and the versions
# differ by metres on the same reach while sharing no timestamps, so a
# series assembled across a change of default carries a step that cannot
# be found by joining on time. The list is the service's own, from the
# error it returns for a name it does not know.
HYDROCRON_COLLECTIONS = (
    "SWOT_L2_HR_RiverSP_2.0", "SWOT_L2_HR_RiverSP_reach_2.0",
    "SWOT_L2_HR_RiverSP_node_2.0", "SWOT_L2_HR_LakeSP_2.0",
    "SWOT_L2_HR_LakeSP_prior_2.0", "SWOT_L2_HR_RiverSP_D",
    "SWOT_L2_HR_RiverSP_reach_D", "SWOT_L2_HR_RiverSP_node_D",
    "SWOT_L2_HR_LakeSP_D", "SWOT_L2_HR_LakeSP_prior_D",
)
HYDROCRON_DEFAULT_COLLECTION = {
    "Reach": "SWOT_L2_HR_RiverSP_reach_D",
    "Node": "SWOT_L2_HR_RiverSP_node_D",
    "PriorLake": "SWOT_L2_HR_LakeSP_prior_D",
}


@mcp.tool()
@guarded("hydrocron")
def hydrocron_timeseries(feature_id: str, feature: str = "Reach",
                         start_time: str = "2023-01-01T00:00:00Z",
                         end_time: str = "2026-12-31T00:00:00Z",
                         fields: str = "reach_id,time_str,wse,width",
                         collection_name: str = "") -> dict:
    """SWOT river and lake time series from PO.DAAC Hydrocron.

    feature: 'Reach', 'Node' or 'PriorLake'; feature_id: SWORD id (e.g.
    '63470800171'). fields: comma list; wse is water surface elevation
    in metres (EGM2008 geoid), width in metres. Fill values are large
    negatives; filter before use.

    collection_name: the product collection to read. Left empty, this
    tool names the current D-family collection for the feature rather
    than letting the service choose, and the name it used is returned
    so a receipt can record it. Pass one of HYDROCRON_COLLECTIONS to
    read another; an unknown name is refused here rather than sent.
    Source: PO.DAAC Hydrocron; no credential is sent."""
    if collection_name and collection_name not in HYDROCRON_COLLECTIONS:
        raise ValueError(
            f"unknown collection {collection_name!r}; Hydrocron serves "
            f"{', '.join(HYDROCRON_COLLECTIONS)}")
    chosen = collection_name or HYDROCRON_DEFAULT_COLLECTION.get(feature)
    if not chosen:
        raise ValueError(
            f"no default collection for feature {feature!r}; pass collection_name, "
            f"or use one of {', '.join(sorted(HYDROCRON_DEFAULT_COLLECTION))}")
    q = {"feature": feature, "feature_id": feature_id,
         "start_time": start_time, "end_time": end_time,
         "fields": fields, "collection_name": chosen}
    r = _fetch("hydrocron",
               "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/"
               "timeseries", q)
    return {"feature": feature, "feature_id": feature_id,
            "collection_name": chosen,
            "collection_was_named_by": "caller" if collection_name else "this tool",
            **parse_hydrocron(r.json()), **_meta(r)}


@mcp.tool()
@guarded("usgs")
def nwis_groundwater_levels(sites: str, parameter_cd: str = "72019",
                            start_date: str = "", end_date: str = "") -> dict:
    """Discrete groundwater levels from USGS wells: the readings taken
    on site visits, from the Water Data API field-measurements
    collection (the API has no separate groundwater collection; the
    discrete levels live there beside discharge measurements).

    sites: comma-separated USGS site numbers (a well's 15-digit
    number, e.g. '255854080085601').
    parameter_cd: 72019 depth to water below land surface in FEET
    (the default); 62610 groundwater elevation above NGVD29 in feet;
    62611 above NAVD88 in feet; 72150 above local mean sea level;
    72229 above GUVD04. Depth and elevation are different numbers for
    the same well; each row carries the vertical datum it is
    referenced to.
    start_date, end_date: YYYY-MM-DD, either side open when empty.
    Rows carry approval and qualifiers (e.g. Static). Paging, the
    optional API_USGS_PAT key as a header on this host only, and the
    no-retry rule on 429 are the usgs_daily ones. A well recorded
    continuously is served by the daily collection through usgs_daily
    with the same parameter code.
    Source of record: api.waterdata.usgs.gov, collection
    field-measurements. Terms: USGS data are public domain; provisional
    values are subject to revision, so cite the access date."""
    p = {"monitoring_location_id": _usgs_locations(sites),
         "parameter_code": parameter_cd}
    if start_date or end_date:
        p["datetime"] = f"{start_date or '..'}/{end_date or '..'}"
    pages, r = _usgs_walk("field-measurements", p)
    return {**parse_usgs_field(pages), **_meta(r)}


@mcp.tool()
@guarded("hydrocron")
def hydrocron_lake_timeseries(lake_id: str,
                              start_time: str = "2023-01-01T00:00:00Z",
                              end_time: str = "2026-12-31T00:00:00Z",
                              fields: str = "lake_id,time_str,wse,wse_u,"
                                            "area_total,area_tot_u,quality_f,"
                                            "partial_f,dark_frac,ice_clim_f",
                              collection_name: str = "") -> dict:
    """SWOT lake time series from PO.DAAC Hydrocron: the PriorLake
    feature, one series per lake of the prior lake database.

    lake_id: the prior lake database id (e.g. '6350036102'), the id
    the LakeSP prior product carries as lake_id. fields: comma list of
    LakeSP prior fields; wse is water surface elevation in metres on
    the EGM2008 geoid, area_total in square kilometres, quality_f the
    summary quality flag (0 good), partial_f whether the lake was only
    partly observed, dark_frac the dark-water fraction, ice_clim_f the
    climatological ice flag. Fill values are large negatives; filter
    before use. Each row also carries the units the service returns.

    collection_name: the product collection to read. Left empty, this
    tool names the current D-family prior-lake collection rather than
    letting the service choose, and returns the name it used; pass one
    of HYDROCRON_COLLECTIONS to read another; an unknown name is
    refused here rather than sent.
    Source: PO.DAAC Hydrocron; no credential is sent (the service is
    anonymous; the Earthdata Login token is not used). Terms: NASA
    data are open; cite the product version and the access date."""
    if collection_name and collection_name not in HYDROCRON_COLLECTIONS:
        raise ValueError(
            f"unknown collection {collection_name!r}; Hydrocron serves "
            f"{', '.join(HYDROCRON_COLLECTIONS)}")
    chosen = collection_name or HYDROCRON_DEFAULT_COLLECTION["PriorLake"]
    q = {"feature": "PriorLake", "feature_id": lake_id,
         "start_time": start_time, "end_time": end_time,
         "fields": fields, "collection_name": chosen}
    r = _fetch("hydrocron",
               "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/"
               "timeseries", q)
    return {"feature": "PriorLake", "lake_id": lake_id,
            "collection_name": chosen,
            "collection_was_named_by": "caller" if collection_name else "this tool",
            **parse_hydrocron(r.json()), **_meta(r)}


# ------------------------------------------------------------------ NGL
_midas_cache: dict[str, dict] = {}


def _midas_table(frame: str, fetch=_fetch) -> dict:
    """The parsed MIDAS table for a frame, fetched once per process
    (the table is a few megabytes and rebuilt weekly); the fetch's
    provenance travels with it."""
    if frame not in NGL_MIDAS:
        raise SourceError("ngl", None, f"frame {frame!r} is not one of "
                          f"{', '.join(NGL_MIDAS)}")
    if frame not in _midas_cache:
        r = fetch("ngl", NGL_MIDAS[frame])
        _midas_cache[frame] = {
            "table": parse_midas(r.text), **_meta(r),
            "table_last_modified": r.headers.get("Last-Modified")}
    return _midas_cache[frame]


@mcp.tool()
@guarded("ngl")
def gnss_vertical_velocity(station: str = "", lat: float | None = None,
                           lon: float | None = None,
                           frame: str = "IGS20") -> dict:
    """A GNSS station's vertical velocity, its uncertainty and its
    reference frame from the Nevada Geodetic Laboratory's MIDAS
    velocity table, by station id or by the station nearest a point.

    station: the laboratory's 4-character id (e.g. 'P224'); or leave
    it empty and pass lat, lon (degrees) for the nearest station, in
    which case the three nearest are listed with their distances.
    frame: 'IGS20' (the current table, rebuilt weekly) or 'IGS14' (the
    superseded table the laboratory keeps). Velocities are MIDAS
    trends in millimetres per year with the MIDAS uncertainty; up is
    the vertical land motion a tide gauge series carries. A velocity
    in a plate-fixed frame is a different number; this tool serves the
    IGS frames only. The table is one request of about 5.4 MB (IGS20,
    measured 2026-09-15), read once per process; the response names
    when it was fetched and the file's last modification.
    Source: geodesy.unr.edu; no credential is sent. Terms: the
    laboratory asks that Blewitt, Hammond and Kreemer (2018, Eos,
    doi:10.1029/2018EO104623) be cited for its data products and
    Blewitt et al. (2016, JGR Solid Earth, doi:10.1002/2015JB012552)
    for MIDAS, and notes that many stations carry an original data
    citation of their own."""
    t = _midas_table(frame)
    table = t["table"]
    if station:
        rec = table.get(station.strip().upper())
        if rec is None:
            raise SourceError("ngl", 200, f"station {station!r} is not in "
                              f"the {frame} MIDAS table ({len(table)} "
                              "stations); check the id at geodesy.unr.edu")
        lookup, near = "station id", []
    elif lat is not None and lon is not None:
        near = nearest_stations(table, lat, lon, 3)
        rec = table[near[0]["station"]]
        lookup = f"nearest station to {lat}, {lon}"
    else:
        raise SourceError("ngl", None, "pass a station id, or lat and lon")
    return {"frame": frame, "lookup": lookup, **rec,
            "nearest": near, "units": "mm/yr, MIDAS trend and uncertainty",
            "table_url": NGL_MIDAS[frame], "table_stations": len(table),
            "table_last_modified": t["table_last_modified"],
            "retrieved_at": t["retrieved_at"], "request_url": t["request_url"],
            "server_version": VERSION}


# ------------------------------------------------------------------ NWM
_nwm_cache: dict[tuple, object] = {}


def _nwm_store(domain: str) -> str:
    """The store URL for a served domain; an unserved or unknown domain
    is refused here, before any request."""
    if domain in NWM_UNSERVED_DOMAINS:
        raise SourceError("nwm", None, f"domain {domain} is not served: "
                          f"{NWM_UNSERVED_DOMAINS[domain]}, which this "
                          f"server does not decode; served domains are "
                          f"{' and '.join(NWM_DOMAINS)}")
    if domain not in NWM_DOMAINS:
        raise SourceError("nwm", None, f"domain {domain!r} is not one of "
                          f"{', '.join(NWM_DOMAINS)}")
    return f"{NWM_BUCKET}/{domain}/zarr/chrtout.zarr"


def _nwm_array(domain: str, name: str, fetch=_fetch):
    """A one-chunk coordinate array of the store (feature_id, gage_id),
    decoded once per process."""
    key = (domain, name)
    if key not in _nwm_cache:
        meta = _nwm_metadata(domain, fetch)
        r = fetch("nwm", f"{_nwm_store(domain)}/{name}/0")
        _nwm_cache[key] = zarr_decode(r.content, meta[f"{name}/.zarray"])
    return _nwm_cache[key]


def _nwm_metadata(domain: str, fetch=_fetch) -> dict:
    key = (domain, ".zmetadata")
    if key not in _nwm_cache:
        r = fetch("nwm", f"{_nwm_store(domain)}/.zmetadata")
        _nwm_cache[key] = r.json()["metadata"]
    return _nwm_cache[key]


def _nwm_reach_index(domain: str, feature_id: int, usgs_site: str,
                     fetch=_fetch) -> tuple[int, int, str]:
    """(index, feature_id, gage_id) of the reach, by NHDPlus feature id
    or by the USGS gauge the store's gage_id axis assigns to it."""
    fids = _nwm_array(domain, "feature_id", fetch)
    gages = _nwm_array(domain, "gage_id", fetch)
    if usgs_site:
        want = usgs_site.strip().encode()
        hits = [i for i, g in enumerate(gages) if g.strip(b"\x00 ") == want]
        if not hits:
            raise SourceError("nwm", 200, f"no reach in the {domain} "
                              f"retrospective carries USGS gauge {usgs_site}; "
                              "pass the NHDPlus feature_id instead")
        idx = hits[0]
        return idx, int(fids[idx]), want.decode()
    try:
        idx = fids.index(feature_id)
    except ValueError:
        raise SourceError("nwm", 200, f"feature_id {feature_id} is not on "
                          f"the {domain} retrospective's feature axis "
                          f"({len(fids)} reaches)")
    return idx, int(feature_id), gages[idx].strip(b"\x00 ").decode()


@mcp.tool()
@guarded("nwm")
def nwm_retrospective_streamflow(feature_id: int = 0, usgs_site: str = "",
                                 start_date: str = "", end_date: str = "",
                                 domain: str = "CONUS") -> dict:
    """Daily mean streamflow at one reach from the NOAA National Water
    Model retrospective, version 3.0, read anonymously from the public
    bucket noaa-nwm-retrospective-3-0-pds (the CHRTOUT zarr store,
    hourly, 1979-02-01 to 2023-01-31 on the CONUS domain).

    feature_id: the NHDPlus v2 ComID of the reach (the store's
    feature_id axis); or usgs_site: a USGS gauge number, resolved to
    the reach the store's gage_id axis assigns it. start_date,
    end_date: YYYY-MM-DD, inclusive, UTC, both required (there is no
    default window, because the widest window the budget allows is
    also the most expensive call). domain: CONUS or Alaska; Hawaii and
    PR are refused by name, because their stores are blosc/lz4
    compressed (Hawaii's time axis in minutes) and this server does
    not decode them.
    Returns one row per UTC calendar day: the mean of the hourly
    values in cubic metres per second, and the hours that were not
    fill. This is MODEL OUTPUT, not an observation: the retrospective
    is one simulation with one forcing and one channel routing, and
    reaches below dams carry the model's reservoir treatment; the
    hydrology concepts carry that discipline.
    Cost: the store metadata, the 2.9 MB feature index and the 68 KB
    gauge index once per process, then per 28-day chunk in the window
    one streamflow chunk (4 to 9 MB measured) and one time chunk,
    under a budget of NWM_CHUNK_BUDGET chunks: at most 28 chunk
    requests and roughly 50 to 130 MB in one call; a wider window is
    refused with the budget named. Source: NOAA Open Data
    Dissemination on AWS; no credential is sent. Terms: NOAA data are
    public domain; cite the retrospective version and the access
    date."""
    if not usgs_site and not feature_id:
        raise SourceError("nwm", None, "pass feature_id or usgs_site")
    if not start_date or not end_date:
        raise SourceError("nwm", None, "pass start_date and end_date "
                          "(YYYY-MM-DD); there is no default window")
    store = _nwm_store(domain)
    meta = _nwm_metadata(domain)
    idx, fid, gage = _nwm_reach_index(domain, feature_id, usgs_site)
    plan = nwm_chunk_plan(meta, idx, start_date, end_date)
    zattrs = meta["streamflow/.zattrs"]
    hours, values, keys, first = [], [], [], None
    for k in plan["time_chunks"]:
        key = f"streamflow/{k}.{plan['column']}"
        r = _fetch("nwm", f"{store}/{key}")
        first = first or r
        chunk = zarr_decode(r.content, meta["streamflow/.zarray"])
        values.extend(chunk[plan["offset"]::plan["chunk_features"]])
        t = zarr_decode(_fetch("nwm", f"{store}/time/{k}").content,
                        meta["time/.zarray"])
        hours.extend(t)
        keys.append(key)
    rows = nwm_daily_means(hours, values, plan["epoch"], zattrs,
                           plan["hour_range"],
                           fill=meta["streamflow/.zarray"].get("fill_value"))
    if not rows:
        raise SourceError("nwm", 200, "every hour in the window is fill "
                          "for that reach")
    return {"retrospective": NWM_RETROSPECTIVE, "domain": domain,
            "store": store, "model": meta[".zattrs"].get("TITLE"),
            "model_code_version": meta[".zattrs"].get("code_version"),
            "feature_id": fid, "feature_index": idx, "gage_id": gage,
            "units": zattrs.get("units"),
            "aggregation": "mean of the hourly values within each UTC "
                           "calendar day, fill excluded, hours counted",
            "chunks_read": keys,
            **_cap(rows, tkey=lambda r: r["date"]), **_meta(first)}


# ---------------------------------------------------------- test modes
_USGS_FIXTURE_Q = {"monitoring_location_id": "USGS-09380000",
                   "parameter_code": "00060",
                   "datetime": "2023-01-01/2023-12-31",
                   "limit": 200, "skipGeometry": "true"}


def record_fixtures() -> int:
    FIXTURES.mkdir(exist_ok=True)

    def usgs_pages() -> str:
        # Two real pages of one daily year at a small page size, so the
        # offline test walks a genuine cursor next link.
        pages = []
        r = _fetch("usgs", f"{USGS_API}/daily/items", _USGS_FIXTURE_Q)
        pages.append(r.json())
        nxt = next(l["href"] for l in pages[0]["links"] if l["rel"] == "next")
        pages.append(_fetch("usgs", nxt).json())
        return json.dumps({"first_url": str(r.request.url), "pages": pages})

    def midas_excerpt() -> str:
        # The live IGS20 table is several megabytes; the fixture keeps
        # its first three lines (eastern stations, whose longitudes the
        # file writes below -180) and every station within 1.5 degrees
        # of the San Francisco Bay, so the parser and the nearest
        # lookup are exercised on real rows. The request is named.
        r = _fetch("ngl", NGL_MIDAS["IGS20"])
        lines = r.text.splitlines()
        keep = lines[:3] + [
            l for l in lines[3:]
            if len(l.split()) >= MIDAS_COLUMNS
            and abs(float(l.split()[24]) - 37.8) <= 1.5
            and abs(((float(l.split()[25]) + 180) % 360 - 180) + 122.3) <= 1.5]
        return json.dumps({
            "request_url": str(r.request.url),
            "recorded_at": _meta(r)["retrieved_at"],
            "table_last_modified": r.headers.get("Last-Modified"),
            "table_lines": len(lines), "kept_lines": len(keep),
            "kept": "the first three lines, then every station within 1.5 "
                    "degrees of 37.8N 122.3W",
            "lines": keep}, indent=1)

    def nwm_pieces() -> str:
        # The store metadata, the first time chunk and the gage_id axis
        # are small and recorded whole; a streamflow chunk is several
        # megabytes, so the fixture keeps the one column zarr_decode
        # extracts from the live chunk for the reach that carries USGS
        # gauge 09380000, with the chunk key named.
        store = _nwm_store("CONUS")
        rm = _fetch("nwm", f"{store}/.zmetadata")
        meta = rm.json()["metadata"]
        rt = _fetch("nwm", f"{store}/time/0")
        rg = _fetch("nwm", f"{store}/gage_id/0")
        gages = zarr_decode(rg.content, meta["gage_id/.zarray"])
        idx = next(i for i, g in enumerate(gages)
                   if g.strip(b"\x00 ") == b"09380000")
        fids = zarr_decode(_fetch("nwm", f"{store}/feature_id/0").content,
                           meta["feature_id/.zarray"])
        plan = nwm_chunk_plan(meta, idx, "1979-02-01", "1979-02-28")
        key = f"streamflow/0.{plan['column']}"
        rs = _fetch("nwm", f"{store}/{key}")
        col = zarr_decode(rs.content, meta["streamflow/.zarray"])[
            plan["offset"]::plan["chunk_features"]]
        return json.dumps({
            "store": store, "recorded_at": _meta(rm)["retrieved_at"],
            "zmetadata": meta,
            "time_0": {"request_url": str(rt.request.url),
                       "b64": base64.b64encode(rt.content).decode()},
            "gage_id_0": {"request_url": str(rg.request.url),
                          "b64": base64.b64encode(rg.content).decode()},
            "streamflow_column": {
                "request_url": str(rs.request.url), "chunk": key,
                "gage_id": "09380000", "feature_index": idx,
                "feature_id": int(fids[idx]), "offset": plan["offset"],
                "values": list(col)}}, indent=1)

    jobs = {
        "usgs_daily_pages.json": usgs_pages,
        "usgs_continuous.json": lambda: _fetch(
            "usgs", f"{USGS_API}/continuous/items",
            {"monitoring_location_id": "USGS-09380000",
             "parameter_code": "00060", "limit": 20,
             "skipGeometry": "true"}).text,
        "coops_latest.json": lambda: _fetch(
            "coops", "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter",
            {"station": "8443970", "product": "water_level", "datum": "MLLW",
             "units": "metric", "time_zone": "gmt", "format": "json",
             "date": "latest", "application": "osp-observations"}).text,
        "argo_search.json": lambda: _fetch(
            "argo", _ERDDAP + "?" + quote(
                "platform_number,cycle_number,latitude,longitude,time",
                safe="") + "&" + quote("time>=2026-08-20T00:00:00Z", safe="=")
            + "&" + quote("latitude>=25", safe="=")
            + "&" + quote("latitude<=35", safe="=")
            + "&" + quote("longitude>=-75", safe="=")
            + "&" + quote("longitude<=-55", safe="=")).text,
        "psmsl_1.txt": lambda: _fetch(
            "psmsl",
            "https://psmsl.org/data/obtaining/rlr.monthly.data/1.rlrdata").text,
        "hydrocron_reach.json": lambda: _fetch(
            "hydrocron",
            "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries",
            {"feature": "Reach", "feature_id": "63470800171",
             "start_time": "2024-01-25T00:00:00Z",
             "end_time": "2024-03-29T00:00:00Z",
             "fields": "reach_id,time_str,wse,width",
             # Named, like every other request this server makes: a
             # fixture recorded from whatever the service defaulted to
             # would change meaning under the maintainers' feet.
             "collection_name": HYDROCRON_DEFAULT_COLLECTION["Reach"]}).text,
        "nwis_groundwater.json": lambda: _fetch(
            "usgs", f"{USGS_API}/field-measurements/items",
            {"monitoring_location_id": "USGS-255854080085601",
             "parameter_code": "72019",
             "datetime": "1988-01-01/1989-12-31",
             "limit": 200, "skipGeometry": "true"}).text,
        "hydrocron_lake.json": lambda: _fetch(
            "hydrocron",
            "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries",
            {"feature": "PriorLake", "feature_id": "6350036102",
             "start_time": "2024-01-01T00:00:00Z",
             "end_time": "2024-06-30T00:00:00Z",
             "fields": "lake_id,time_str,wse,wse_u,area_total,area_tot_u,"
                       "quality_f,partial_f,dark_frac,ice_clim_f",
             "collection_name": HYDROCRON_DEFAULT_COLLECTION["PriorLake"]}).text,
        "midas_igs20_excerpt.json": midas_excerpt,
        "nwm_retrospective.json": nwm_pieces,
    }
    only = [a for a in sys.argv[2:] if not a.startswith("-")]
    for name, fn in jobs.items():
        if only and name not in only:
            continue
        (FIXTURES / name).write_text(fn())
        print(f"recorded {name}")
    return 0


class _FixtureFetch:
    """Serves the recorded pages by URL and records what was sent, so
    the walker and the key handling are tested without the network."""

    def __init__(self, fx: dict):
        self.pages = {fx["first_url"]: fx["pages"][0]}
        nxt = next(l["href"] for l in fx["pages"][0]["links"] if l["rel"] == "next")
        self.pages[nxt] = fx["pages"][1]
        self.first_url = fx["first_url"]
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, source, url, params=None):
        self.calls.append((url, _headers(url)))
        key = self.first_url if params else url
        req = httpx.Request("GET", key)
        return httpx.Response(200, json=self.pages[key], request=req)


def offline_test() -> int:
    """Contract tests: every parser against its recorded fixture, the
    truncation regression that keeps the tail, the two-page USGS walk,
    the rule that the USGS key travels only as a header, the MIDAS
    lookup on a recorded excerpt, and the zarr decode, chunk plan and
    daily aggregation of the National Water Model store."""
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"{'PASS' if cond else 'FAIL'} {name}")
        fails += 0 if cond else 1

    fx = json.loads((FIXTURES / "usgs_daily_pages.json").read_text())
    u = parse_usgs(fx["pages"])
    s = u["series"][0]
    check("usgs parser groups, sorts and caps",
          s["site"] == "09380000" and s["location_id"] == "USGS-09380000"
          and s["statistic_id"] == "00003" and s["total_rows"] == 365
          and s["rows"][0]["t"] == "2023-01-01"
          and s["rows"][-1]["t"] == "2023-12-31"
          and s["rows"][0]["approval"] == "Approved"
          and isinstance(s["rows"][0]["qualifiers"], list)
          and s["returned_span"] == ["2023-01-01", "2023-12-31"])
    ff = _FixtureFetch(fx)
    pages, first = _usgs_walk("daily", dict(_USGS_FIXTURE_Q), fetch=ff)
    check("usgs walker follows the cursor next link to the last page",
          len(pages) == 2 and len(ff.calls) == 2
          and sum(len(p["features"]) for p in pages) == 365
          and first.request.url == httpx.URL(fx["first_url"]))
    saved = os.environ.get(USGS_KEY_VAR)
    os.environ[USGS_KEY_VAR] = "SENTINEL-not-a-key-0000"
    try:
        ff2 = _FixtureFetch(fx)
        pages, first = _usgs_walk("daily", dict(_USGS_FIXTURE_Q), fetch=ff2)
        out = json.dumps({**parse_usgs(pages), **_meta(first)})
        check("usgs key is a header on the USGS host only, never in a "
              "URL or response",
              all(h.get("X-Api-Key") == "SENTINEL-not-a-key-0000"
                  for _, h in ff2.calls)
              and "SENTINEL" not in out
              and "X-Api-Key" not in _headers("https://psmsl.org/x"))
    finally:
        if saved is None:
            del os.environ[USGS_KEY_VAR]
        else:
            os.environ[USGS_KEY_VAR] = saved
    c = json.loads((FIXTURES / "usgs_continuous.json").read_text())
    s = parse_usgs([c])["series"][0]
    check("usgs continuous rows are UTC instants with approval",
          s["statistic_id"] == "00011" and s["rows"][0]["t"].endswith("+00:00")
          and s["rows"][0]["approval"] in ("Approved", "Provisional"))
    check("usgs empty collection is a structured source error",
          "error" in guarded("usgs")(lambda: parse_usgs(
              [{"features": []}]))()
          and "no observations" in guarded("usgs")(lambda: parse_usgs(
              [{"features": []}]))()["detail"])
    check("usgs period parses to a UTC start",
          _period_start("P7D", dt.datetime(2026, 1, 8, tzinfo=dt.timezone.utc))
          == "2026-01-01T00:00:00Z"
          and "error" in guarded("usgs")(lambda: _period_start("7 days"))())
    j = json.loads((FIXTURES / "coops_latest.json").read_text())
    c = parse_coops(j, "water_level")
    check("coops parser", c["total_rows"] == 1 and c["metadata"]["id"] == "8443970")
    j = json.loads((FIXTURES / "argo_search.json").read_text())
    a = parse_erddap(j)
    check("argo parser", "platform_number" in a["columns"] and a["total_rows"] > 0)
    p = parse_psmsl((FIXTURES / "psmsl_1.txt").read_text())
    check("psmsl parser keeps the TAIL",
          p["truncated"] and p["total_rows"] > 2000
          and p["rows"][-1]["decimal_year"] > 2000.0
          and "omitted" in p and "returned_span" in p)
    j = json.loads((FIXTURES / "hydrocron_reach.json").read_text())
    h = parse_hydrocron(j)
    check("hydrocron parser", h["total_rows"] > 0 and "wse" in h["rows"][0])
    check("cap keeps tail on synthetic",
          _cap(list(range(1000)))["rows"][-1] == 999
          and _cap(list(range(1000)))["rows"][0] == 500)
    check("guarded returns structure, never raises",
          "error" in guarded("t")(lambda: (_ for _ in ()).throw(KeyError("x")))())
    j = json.loads((FIXTURES / "nwis_groundwater.json").read_text())
    s = parse_usgs_field([j])["series"][0]
    check("nwis groundwater parser keeps datum, procedure and approval",
          s["site"] == "255854080085601" and s["parameter"] == "72019"
          and s["unit"] == "ft" and s["reading_type"] == "ReferencePrimary"
          and s["total_rows"] >= 20 and s["rows"][0]["t"] < s["rows"][-1]["t"]
          and s["rows"][0]["vertical_datum"] and s["rows"][0]["procedure"]
          and s["rows"][0]["approval"] in ("Approved", "Provisional")
          and isinstance(s["rows"][0]["qualifiers"], list))
    check("nwis groundwater empty collection is a structured source error",
          "no field measurements" in guarded("usgs")(lambda: parse_usgs_field(
              [{"features": []}]))()["detail"])
    j = json.loads((FIXTURES / "hydrocron_lake.json").read_text())
    h = parse_hydrocron(j)
    check("hydrocron lake parser", h["total_rows"] > 0
          and h["rows"][0]["lake_id"] == "6350036102"
          and "wse" in h["rows"][0] and "area_total" in h["rows"][0]
          and h["rows"][0]["wse_units"] == "m")
    fx = json.loads((FIXTURES / "midas_igs20_excerpt.json").read_text())
    tab = parse_midas("\n".join(fx["lines"]))
    p224 = tab.get("P224")
    check("midas parser reads the README columns in mm/yr and normalises "
          "longitude",
          p224 is not None and p224["up_u_mm_yr"] > 0
          and abs(p224["up_mm_yr"]) < 5 and p224["lat"] > 37
          and -123 < p224["lon"] < -122 and p224["midas_version"] == "MIDAS5"
          and p224["last_epoch"] > p224["first_epoch"]
          and 130 < tab["00NA"]["lon"] < 131 and tab["00NA"]["lat"] < 0)
    near = nearest_stations(tab, 37.8639, -122.2191, 3)
    check("midas nearest station lookup",
          near[0]["station"] == "P224" and near[0]["distance_km"] < 0.5
          and len(near) == 3 and near[1]["distance_km"] >= near[0]["distance_km"])
    _midas_cache["IGS20"] = {"table": tab, "retrieved_at": "x",
                             "request_url": fx["request_url"],
                             "table_last_modified": fx["table_last_modified"]}
    try:
        g = gnss_vertical_velocity("p224")
        g2 = gnss_vertical_velocity(lat=37.8639, lon=-122.2191)
        g3 = gnss_vertical_velocity("ZZZZ")
        check("gnss tool by id and by coordinates, structured error on an "
              "unknown id",
              g["station"] == "P224" and g["frame"] == "IGS20"
              and g["up_mm_yr"] == p224["up_mm_yr"]
              and g2["station"] == "P224" and g2["nearest"][0]["station"] == "P224"
              and "error" in g3 and g3["source"] == "ngl")
    finally:
        _midas_cache.clear()
    fx = json.loads((FIXTURES / "nwm_retrospective.json").read_text())
    meta = fx["zmetadata"]
    col = fx["streamflow_column"]
    t0 = zarr_decode(base64.b64decode(fx["time_0"]["b64"]), meta["time/.zarray"])
    gages = zarr_decode(base64.b64decode(fx["gage_id_0"]["b64"]),
                        meta["gage_id/.zarray"])
    check("nwm zarr decode: zstd, int64 time axis, fixed-width gage ids",
          len(t0) == meta["time/.zarray"]["chunks"][0] and t0[0] == 0
          and t0[1] == 1 and len(gages) == meta["gage_id/.zarray"]["shape"][0]
          and gages[col["feature_index"]].strip(b"\x00 ") == b"09380000")
    plan = nwm_chunk_plan(meta, col["feature_index"], "1979-02-01", "1979-02-28")
    check("nwm chunk plan: column and offset from the index, time chunks "
          "from the axis units",
          plan["time_chunks"] == [0] and f"streamflow/0.{plan['column']}" == col["chunk"]
          and plan["offset"] == col["offset"]
          and nwm_time_epoch(meta).isoformat() == "1979-02-01T01:00:00+00:00"
          and plan["hour_range"][0] == 0)
    rows = nwm_daily_means(t0, col["values"], plan["epoch"],
                           meta["streamflow/.zattrs"], plan["hour_range"],
                           fill=meta["streamflow/.zarray"].get("fill_value"))
    check("nwm daily means: UTC days, fill excluded, scale applied, hours "
          "counted",
          rows[0]["date"] == "1979-02-01" and rows[0]["n_hours"] == 23
          and rows[1]["n_hours"] == 24 and 100 < rows[1]["mean"] < 2000
          and rows[-1]["date"] == "1979-02-28")
    check("nwm unserved domain, non-zstd chunk and missing window are "
          "structured errors",
          "not served" in guarded("nwm")(lambda: _nwm_store("Hawaii"))()["detail"]
          and "not one of" in guarded("nwm")(lambda: _nwm_store("Mars"))()["detail"]
          and "zstd" in guarded("nwm")(lambda: zarr_decode(
              b"not a zstd frame", meta["time/.zarray"]))()["detail"]
          and "no default window" in nwm_retrospective_streamflow(
              usgs_site="09380000")["detail"])
    check("nwm window over the chunk budget is a structured error naming it",
          "budget" in guarded("nwm")(lambda: nwm_chunk_plan(
              meta, 0, "1990-01-01", "1992-12-31"))()["detail"]
          and "outside" in guarded("nwm")(lambda: nwm_chunk_plan(
              meta, 0, "1950-01-01", "1950-12-31"))()["detail"])
    n = 24
    print(f"offline test: {n - fails}/{n} PASS")
    return fails


def selftest() -> int:
    global USGS_PAGE_LIMIT

    def usgs_multipage():
        # A real two-page walk at a small page size (the live cursor
        # link), then the page size goes back to the API maximum.
        global USGS_PAGE_LIMIT
        USGS_PAGE_LIMIT = 200
        try:
            d = usgs_daily("09380000", start_date="2023-01-01",
                           end_date="2023-12-31")
        finally:
            USGS_PAGE_LIMIT = 50000
        s = d["series"][0]
        return (s["total_rows"] == 365 and s["rows"][-1]["t"] == "2023-12-31"
                and "limit=200" in d["request_url"])

    def usgs_sentinel():
        # A sentinel key is refused by the API; the refusal is a
        # structured error and the sentinel appears nowhere in it.
        saved = os.environ.get(USGS_KEY_VAR)
        os.environ[USGS_KEY_VAR] = "SENTINEL-not-a-key-0000"
        try:
            d = usgs_daily("09380000", start_date="2023-01-01",
                           end_date="2023-01-02")
        finally:
            if saved is None:
                del os.environ[USGS_KEY_VAR]
            else:
                os.environ[USGS_KEY_VAR] = saved
        return ("error" in d and d["status"] == 403
                and "SENTINEL" not in json.dumps(d))

    def usgs_real_key_absent():
        # With the user's real key set, its value is in no response.
        key = os.environ.get(USGS_KEY_VAR)
        if not key:
            print(f"     ({USGS_KEY_VAR} not set; keyed path not exercised)")
            return True
        d = usgs_instantaneous("09380000", period="P1D")
        return "series" in d and key not in json.dumps(d)

    checks = [
        ("usgs_instantaneous", lambda: (
            lambda d: d["series"][0]["total_rows"] > 0
            and d["series"][0]["rows"][-1]["approval"] in ("Approved", "Provisional")
            and d["series"][0]["rows"][-1]["t"].endswith("+00:00"))(
                usgs_instantaneous("01646500", period="P1D"))),
        ("usgs_daily multi-page walk", usgs_multipage),
        ("usgs sentinel key: refused, never echoed", usgs_sentinel),
        ("usgs real key never in a response", usgs_real_key_absent),
        ("coops_data", lambda: coops_data(
            "8443970", latest=True)["total_rows"] == 1),
        ("argo_search", lambda: argo_search(
            25, 35, -75, -55, "2026-08-20T00:00:00Z")["total_rows"] > 0),
        ("psmsl_monthly TAIL regression", lambda: (
            lambda d: d["truncated"] and d["rows"][-1]["decimal_year"] > 2000
            and d["retrieved_at"] and d["request_url"])(psmsl_monthly(1))),
        ("hydrocron_timeseries", lambda: hydrocron_timeseries(
            "63470800171", start_time="2024-01-25T00:00:00Z",
            end_time="2024-03-29T00:00:00Z")["total_rows"] > 0),
        ("nwis_groundwater_levels", lambda: (
            lambda d: d["series"][0]["total_rows"] > 0
            and d["series"][0]["rows"][-1]["vertical_datum"])(
                nwis_groundwater_levels("255854080085601",
                                        start_date="1988-01-01",
                                        end_date="1989-12-31"))),
        ("hydrocron_lake_timeseries", lambda: hydrocron_lake_timeseries(
            "6350036102", start_time="2024-01-01T00:00:00Z",
            end_time="2024-06-30T00:00:00Z")["total_rows"] > 0),
        ("gnss_vertical_velocity by id and by coordinates", lambda: (
            lambda a, b: a["station"] == "P224" and a["up_u_mm_yr"] > 0
            and b["nearest"][0]["distance_km"] < 1.0
            and a["table_last_modified"])(
                gnss_vertical_velocity("P224"),
                gnss_vertical_velocity(lat=37.8639, lon=-122.2191))),
        ("nwm_retrospective_streamflow at the Lees Ferry gauge", lambda: (
            lambda d: d["gage_id"] == "09380000" and d["total_rows"] == 28
            and 100 < d["rows"][0]["mean"] < 2000
            and d["retrospective"] == NWM_RETROSPECTIVE)(
                nwm_retrospective_streamflow(usgs_site="09380000",
                                             start_date="1979-02-01",
                                             end_date="1979-02-28"))),
        ("structured error, no misdiagnosis", lambda: (
            lambda d: "error" in d and d["source"] == "usgs"
            and "no observations" in d["detail"])(
                usgs_instantaneous("01646500", parameter_cd="99999"))),
    ]
    failures = 0
    for name, fn in checks:
        try:
            ok = fn()
            print(f"{'PASS' if ok else 'FAIL'} {name}")
            failures += 0 if ok else 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            failures += 1
    print(f"selftest: {len(checks) - failures}/{len(checks)} live")
    return failures


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    if "--test" in sys.argv:
        raise SystemExit(offline_test())
    if "--record-fixtures" in sys.argv:
        raise SystemExit(record_fixtures())
    mcp.run()
