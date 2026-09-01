# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp", "httpx"]
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

WHAT LEAVES YOUR MACHINE. Query parameters only (station and float
identifiers, bounding boxes, time ranges), sent over HTTPS to the
agency endpoints named per tool. Every source here is anonymous; no
credential exists in this process. No file, no local path, and no
data you hold is ever sent.

Run: uv run observations_mcp.py            (stdio MCP server)
     uv run observations_mcp.py --selftest (live probe of every group)
"""
from __future__ import annotations

import sys
from urllib.parse import quote

import httpx
from mcp.server.mcpserver import MCPServer

VERSION = "0.1.0"
UA = {"User-Agent": f"osp-observations-mcp/{VERSION}"}
MAX_ROWS = 500
mcp = MCPServer("observations")


def _get(url: str, params: dict | None = None) -> httpx.Response:
    r = httpx.get(url, params=params, headers=UA, timeout=30.0,
                  follow_redirects=True)
    r.raise_for_status()
    return r


def _cap(rows: list) -> dict:
    if len(rows) > MAX_ROWS:
        return {"rows": rows[:MAX_ROWS], "truncated": True,
                "total_rows": len(rows)}
    return {"rows": rows, "truncated": False, "total_rows": len(rows)}


# ---------------------------------------------------------------- USGS
@mcp.tool()
def usgs_instantaneous(sites: str, parameter_cd: str = "00060",
                       period: str = "P7D") -> dict:
    """Instantaneous values from USGS NWIS stream gauges.

    sites: comma-separated USGS site numbers (e.g. '01646500').
    parameter_cd: USGS parameter code; 00060 discharge cfs, 00065 gage
    height ft, 00010 water temperature C.
    period: ISO 8601 duration back from now (e.g. 'P7D').
    Source of record: waterservices.usgs.gov (anonymous)."""
    r = _get("https://waterservices.usgs.gov/nwis/iv/",
             {"format": "json", "sites": sites,
              "parameterCd": parameter_cd, "period": period,
              "siteStatus": "all"})
    out = []
    for ts in r.json()["value"]["timeSeries"]:
        vals = [{"t": v["dateTime"], "v": v["value"]}
                for v in ts["values"][0]["value"]]
        out.append({"site": ts["sourceInfo"]["siteCode"][0]["value"],
                    "name": ts["sourceInfo"]["siteName"],
                    "parameter": ts["variable"]["variableName"],
                    **_cap(vals)})
    return {"series": out}


@mcp.tool()
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
    r = _get("https://waterservices.usgs.gov/nwis/dv/", p)
    out = []
    for ts in r.json()["value"]["timeSeries"]:
        vals = [{"t": v["dateTime"][:10], "v": v["value"]}
                for v in ts["values"][0]["value"]]
        out.append({"site": ts["sourceInfo"]["siteCode"][0]["value"],
                    "name": ts["sourceInfo"]["siteName"],
                    "parameter": ts["variable"]["variableName"],
                    **_cap(vals)})
    return {"series": out}


# --------------------------------------------------------------- CO-OPS
@mcp.tool()
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
    r = _get("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter", p)
    j = r.json()
    if "error" in j:
        return {"error": j["error"].get("message", str(j["error"]))}
    key = "predictions" if product == "predictions" else "data"
    rows = [{"t": d.get("t"), "v": d.get("v")} for d in j.get(key, [])]
    return {"station": station, "product": product, "datum": datum,
            "units": "metric", **_cap(rows),
            "metadata": j.get("metadata", {})}


# ----------------------------------------------------------------- Argo
_ERDDAP = "https://erddap.ifremer.fr/erddap/tabledap/ArgoFloats.json"


def _erddap(variables: str, constraints: list[str]) -> dict:
    q = quote(variables, safe="") + "".join(
        "&" + quote(c, safe="=") for c in constraints)
    r = _get(f"{_ERDDAP}?{q}")
    t = r.json()["table"]
    return {"columns": t["columnNames"], **_cap(t["rows"])}


@mcp.tool()
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
    return _erddap("platform_number,cycle_number,latitude,longitude,time",
                   cons)


@mcp.tool()
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
    return _erddap("cycle_number,time,pres,temp,psal", cons)


# ---------------------------------------------------------------- PSMSL
@mcp.tool()
def psmsl_monthly(station_id: int) -> dict:
    """Monthly mean sea level from PSMSL, Revised Local Reference.

    station_id: PSMSL id (e.g. 1 Brest, 12 New York; catalogue at
    psmsl.org). Values are millimetres on the station's RLR datum,
    defined roughly 7000 mm below mean sea level, so ABSOLUTE numbers
    are meaningless; use differences and trends. Missing value -99999
    rows are dropped and counted."""
    r = _get("https://psmsl.org/data/obtaining/rlr.monthly.data/"
             f"{station_id}.rlrdata")
    rows, missing = [], 0
    for line in r.text.strip().splitlines():
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 2:
            continue
        yr, v = float(parts[0]), int(parts[1])
        if v == -99999:
            missing += 1
            continue
        rows.append({"decimal_year": yr, "rlr_mm": v})
    return {"station_id": station_id, "datum": "RLR",
            "missing_months": missing, **_cap(rows)}


# ------------------------------------------------------------ Hydrocron
@mcp.tool()
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
    r = _get("https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/"
             "timeseries",
             {"feature": feature, "feature_id": feature_id,
              "start_time": start_time, "end_time": end_time,
              "fields": fields})
    feats = r.json()["results"]["geojson"]["features"]
    return {"feature": feature, "feature_id": feature_id,
            **_cap([f["properties"] for f in feats])}


# -------------------------------------------------------------- selftest
def selftest() -> int:
    checks = [
        ("usgs_instantaneous", lambda: usgs_instantaneous(
            "01646500", period="P1D")["series"][0]["total_rows"] > 0),
        ("coops_data", lambda: coops_data(
            "8443970", latest=True)["total_rows"] == 1),
        ("argo_search", lambda: argo_search(
            25, 35, -75, -55, "2026-08-20T00:00:00Z")["total_rows"] > 0),
        ("psmsl_monthly", lambda: psmsl_monthly(1)["total_rows"] > 2000),
        ("hydrocron_timeseries", lambda: hydrocron_timeseries(
            "63470800171", start_time="2024-01-25T00:00:00Z",
            end_time="2024-03-29T00:00:00Z")["total_rows"] > 0),
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
    print(f"selftest: {len(checks) - failures}/{len(checks)} groups live")
    return failures


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    mcp.run()
