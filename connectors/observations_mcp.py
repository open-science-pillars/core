# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=2,<3", "httpx>=0.27,<1"]
# ///
"""observations: one thin MCP server over five authoritative
observation sources that compose with the ocean and hydrology
knowledge work.

  usgs_*       USGS Water Data (NWIS): stream gauges of record
  coops_*      NOAA CO-OPS: tide and water-level stations of record
  argo_*       Argo profiling floats via the Ifremer ERDDAP
  psmsl_*      PSMSL: the long-record tide-gauge authority
  hydrocron_*  PO.DAAC Hydrocron: SWOT river reach and node series

DESIGN. Every tool is a paper-thin translation from parameters to one
official HTTPS request and a trimmed response. No science lives here:
correctness knowledge (datums, offsets, quality flags, parameter
codes) lives in the connector concepts that cite this file, and
anything attested happens in sanctioned executors that never call
this server. Gates never depend on connectors.

RESPONSE CONTRACT (v0.2). Every successful response carries
retrieval provenance: retrieved_at (UTC), request_url (the resolved
request), server_version. Truncation keeps the TAIL of a series (the
recent record), states the total, and names the time span actually
returned, so a truncated answer can never silently masquerade as the
whole record; narrow the window or use offset to reach earlier rows.
Failures return a structured {"error", "source", "status", "detail"}
with the agency's own message in detail, never a bare exception, so
"no data for that parameter" is never misreported as "the agency is
down". One bounded retry with backoff on 429 and 5xx; a minimum
interval per host keeps the client polite.

WHAT LEAVES YOUR MACHINE. Query parameters only (station and float
identifiers, bounding boxes, time ranges), sent over HTTPS to the
agency endpoints named per tool. Every source here is anonymous; no
credential exists in this process. No file, no local path, and no
data you hold is ever sent.

Run: uv run observations_mcp.py            (stdio MCP server)
     uv run observations_mcp.py --selftest (live probes + regressions)
     uv run observations_mcp.py --test     (offline: parsers vs fixtures)
     uv run observations_mcp.py --record-fixtures (refresh fixtures, live)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from functools import wraps
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
from mcp.server.mcpserver import MCPServer

VERSION = "0.2.0"
UA = {"User-Agent": f"osp-observations-mcp/{VERSION}"}
MAX_ROWS = 500
MIN_INTERVAL_S = 0.5
FIXTURES = Path(__file__).parent / "fixtures"
mcp = MCPServer("observations")
_last_call: dict[str, float] = {}


class SourceError(Exception):
    def __init__(self, source: str, status: int | None, detail: str):
        self.source, self.status, self.detail = source, status, detail
        super().__init__(detail)


def _fetch(source: str, url: str, params: dict | None = None) -> httpx.Response:
    host = urlparse(url).netloc
    wait = MIN_INTERVAL_S - (time.monotonic() - _last_call.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    last: SourceError | None = None
    for attempt in (1, 2):
        _last_call[host] = time.monotonic()
        try:
            r = httpx.get(url, params=params, headers=UA, timeout=30.0,
                          follow_redirects=True)
        except httpx.HTTPError as e:
            last = SourceError(source, None, f"transport failure: {e!r}")
            time.sleep(2.0)
            continue
        if r.status_code < 400:
            return r
        last = SourceError(source, r.status_code, r.text[:500])
        if r.status_code in (429, 500, 502, 503, 504) and attempt == 1:
            time.sleep(2.0)
            continue
        break
    raise last


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
def parse_usgs(j: dict) -> dict:
    out = []
    for ts in j["value"]["timeSeries"]:
        vals = [{"t": v["dateTime"], "v": v["value"]}
                for v in ts["values"][0]["value"]]
        out.append({"site": ts["sourceInfo"]["siteCode"][0]["value"],
                    "name": ts["sourceInfo"]["siteName"],
                    "parameter": ts["variable"]["variableName"],
                    **_cap(vals, tkey=lambda r: r["t"])})
    if not out:
        raise ValueError("no time series in response; check the site "
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
@mcp.tool()
@guarded("usgs")
def usgs_instantaneous(sites: str, parameter_cd: str = "00060",
                       period: str = "P7D") -> dict:
    """Instantaneous values from USGS NWIS stream gauges.

    sites: comma-separated USGS site numbers (e.g. '01646500').
    parameter_cd: USGS parameter code; 00060 discharge cfs, 00065 gage
    height ft, 00010 water temperature C.
    period: ISO 8601 duration back from now (e.g. 'P7D').
    Source of record: waterservices.usgs.gov (anonymous)."""
    r = _fetch("usgs", "https://waterservices.usgs.gov/nwis/iv/",
               {"format": "json", "sites": sites,
                "parameterCd": parameter_cd, "period": period,
                "siteStatus": "all"})
    return {**parse_usgs(r.json()), **_meta(r)}


@mcp.tool()
@guarded("usgs")
def usgs_daily(sites: str, parameter_cd: str = "00060",
               start_date: str = "", end_date: str = "") -> dict:
    """Daily values from USGS NWIS (statistics, typically the mean).

    start_date, end_date: YYYY-MM-DD. Same site and parameter codes as
    usgs_instantaneous. Source of record: waterservices.usgs.gov."""
    p = {"format": "json", "sites": sites, "parameterCd": parameter_cd}
    if start_date:
        p["startDT"] = start_date
    if end_date:
        p["endDT"] = end_date
    r = _fetch("usgs", "https://waterservices.usgs.gov/nwis/dv/", p)
    return {**parse_usgs(r.json()), **_meta(r)}


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
    Ifremer ERDDAP serving the Argo GDAC (anonymous)."""
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
@mcp.tool()
@guarded("hydrocron")
def hydrocron_timeseries(feature_id: str, feature: str = "Reach",
                         start_time: str = "2023-01-01T00:00:00Z",
                         end_time: str = "2026-12-31T00:00:00Z",
                         fields: str = "reach_id,time_str,wse,width") -> dict:
    """SWOT river time series from PO.DAAC Hydrocron.

    feature: 'Reach' or 'Node'; feature_id: SWORD id (e.g.
    '63470800171'). fields: comma list; wse is water surface elevation
    in metres (EGM2008 geoid), width in metres. Fill values are large
    negatives; filter before use. Source: PO.DAAC Hydrocron
    (anonymous)."""
    r = _fetch("hydrocron",
               "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/"
               "timeseries",
               {"feature": feature, "feature_id": feature_id,
                "start_time": start_time, "end_time": end_time,
                "fields": fields})
    return {"feature": feature, "feature_id": feature_id,
            **parse_hydrocron(r.json()), **_meta(r)}


# ---------------------------------------------------------- test modes
def record_fixtures() -> int:
    FIXTURES.mkdir(exist_ok=True)
    jobs = {
        "usgs_iv.json": lambda: _fetch(
            "usgs", "https://waterservices.usgs.gov/nwis/iv/",
            {"format": "json", "sites": "01646500", "parameterCd": "00060",
             "period": "P1D", "siteStatus": "all"}).text,
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
             "fields": "reach_id,time_str,wse,width"}).text,
    }
    for name, fn in jobs.items():
        (FIXTURES / name).write_text(fn())
        print(f"recorded {name}")
    return 0


def offline_test() -> int:
    """Contract tests: every parser against its recorded fixture, plus
    the truncation regression that keeps the tail."""
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"{'PASS' if cond else 'FAIL'} {name}")
        fails += 0 if cond else 1

    j = json.loads((FIXTURES / "usgs_iv.json").read_text())
    u = parse_usgs(j)
    check("usgs parser", u["series"][0]["site"] == "01646500"
          and u["series"][0]["total_rows"] > 0
          and "returned_span" in u["series"][0])
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
    print(f"offline test: {7 - fails}/7 PASS")
    return fails


def selftest() -> int:
    checks = [
        ("usgs_instantaneous", lambda: usgs_instantaneous(
            "01646500", period="P1D")["series"][0]["total_rows"] > 0),
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
            and "detail" in d)(usgs_instantaneous("01646500",
                                                  parameter_cd="99999"))),
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
