# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=2,<3", "httpx>=0.27,<1"]
# ///
"""observations: one thin MCP server over five authoritative
observation sources that compose with the ocean and hydrology
knowledge work.

  usgs_*       USGS Water Data API: stream gauges of record
  coops_*      NOAA CO-OPS: tide and water-level stations of record
  argo_*       Argo profiling floats via the Ifremer ERDDAP
  psmsl_*      PSMSL: the long-record tide-gauge authority
  hydrocron_*  PO.DAAC Hydrocron: SWOT river and lake series, with
               the product collection named rather than defaulted

DESIGN. Every tool is a paper-thin translation from parameters to one
official HTTPS request and a trimmed response. No science lives here:
correctness knowledge (datums, offsets, quality flags, parameter
codes) lives in the connector concepts that cite this file, and
anything attested happens in sanctioned executors that never call
this server. Gates never depend on connectors.

RESPONSE CONTRACT (v0.4). Every successful response carries
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

WHAT LEAVES YOUR MACHINE. Query parameters only (station and float
identifiers, bounding boxes, time ranges), sent over HTTPS to the
agency endpoints named per tool. One optional credential exists: if
API_USGS_PAT is set in the environment, its value is sent as an
X-Api-Key header to api.waterdata.usgs.gov only, and to no other host;
it never appears in a request URL, a response, or an error. No file,
no local path, and no data you hold is ever sent.

Run: uv run observations_mcp.py            (stdio MCP server)
     uv run observations_mcp.py --selftest (live probes + regressions)
     uv run observations_mcp.py --test     (offline: parsers vs fixtures)
     uv run observations_mcp.py --record-fixtures (refresh fixtures, live)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
from functools import wraps
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
from mcp.server.mcpserver import MCPServer

VERSION = "0.4.0"
UA = {"User-Agent": f"osp-observations-mcp/{VERSION}"}
MAX_ROWS = 500
MIN_INTERVAL_S = 0.5
USGS_API = "https://api.waterdata.usgs.gov/ogcapi/v0/collections"
USGS_HOST = "api.waterdata.usgs.gov"
USGS_KEY_VAR = "API_USGS_PAT"
USGS_PAGE_LIMIT = 50000   # the API's maximum page size
USGS_PAGE_BUDGET = 4      # requests one tool call may spend on next links
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
    and the rule that the USGS key travels only as a header."""
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
    n = 12
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
