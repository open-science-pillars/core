# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.27,<1"]
# ///
"""obs_capture: freeze one observation query into a citable record.

The five adopted observation sources are live and mutable: agencies
revise provisional values, replace real-time profiles with
delayed-mode, reissue releases, reprocess on new versions. A receipt
cannot hash a moving target, and by standing doctrine no sanctioned
executor calls a connector. This tool is the bridge: it fetches once
from the OFFICIAL endpoint, stores the evidence, and gives the data a
citable identity.

TWO HASHES, by design. raw_sha256 covers the body exactly as
received: the evidence. content_sha256 covers a canonical extraction
(parsed rows, deterministic serialization) with the volatile envelope
stripped, because live envelopes carry per-request fields (query
timestamps) that change while the data stands still: the identity.
Two captures of unchanged data differ in raw and agree in content,
and that agreement is the reproducibility statement a methods section
needs beside the retrieval date.

A revision at the source is a NEW capture beside the old one, never
an overwrite. VERIFY re-hashes stored payloads against the manifest
and fails loudly on any mismatch. Captures live OUTSIDE the
repositories; receipts cite capture_id and content_sha256.

Deterministic windows only: a capture of "latest" is refused, because
an unreproducible query cannot be a citable record. A usgs-iv capture
given a period (a duration back from now) is resolved to an explicit
UTC window at capture time and that window is what the manifest
records; the period form is a convenience, not a reproducible query.

CANONICAL ROWS ARE API INDEPENDENT. For the USGS sources a canonical
row is the time as an ISO 8601 UTC instant or a date, the value as
the decimal string the agency served, the approval status and the
sorted qualifier list, and the site as its bare number; the source
endpoint, its envelope and its geometry are not part of the identity,
so a content hash survives a change of endpoint when the data stands
still. Captures taken before this tool moved to the USGS Water Data
API (manifest tool_version 0.1.0, a waterservices.usgs.gov request
URL, rows of t and v only) remain legacy evidence: their raw hash
still verifies and their content hash is a legacy identity, comparable
only with other legacy captures.

The USGS key: if API_USGS_PAT is set, it is sent as an X-Api-Key
header to api.waterdata.usgs.gov only; the request URL the manifest
records never carries it. Pages (limit 50000, cursor next links) are
walked under a request budget; a multi-page capture stores the page
bodies joined by newlines as its raw payload and records the count.
No retry on a 429 from that host, since a retry spends a second
request against an hourly bucket.

Usage:
  obs_capture.py capture --source psmsl -p station_id=1
  obs_capture.py capture --source usgs-dv -p sites=01646500 \\
      -p start_date=2024-01-01 -p end_date=2024-03-31
  obs_capture.py capture --source usgs-iv -p sites=01646500 \\
      -p start_time=2026-08-01T00:00:00Z -p end_time=2026-08-08T00:00:00Z
  obs_capture.py verify --id <capture_id>
  obs_capture.py list
Store: --store DIR (default ~/obs-captures), shown on first use.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

VERSION = "0.2.0"
UA = {"User-Agent": f"osp-obs-capture/{VERSION}"}
USGS_API = "https://api.waterdata.usgs.gov/ogcapi/v0/collections"
USGS_HOST = "api.waterdata.usgs.gov"
USGS_KEY_VAR = "API_USGS_PAT"
USGS_PAGE_LIMIT = 50000
USGS_PAGE_BUDGET = 4


def _headers(url: str) -> dict:
    h = dict(UA)
    key = os.environ.get(USGS_KEY_VAR)
    if key and urlparse(url).netloc == USGS_HOST:
        h["X-Api-Key"] = key
    return h


def fetch(url: str, params: dict | None = None) -> httpx.Response:
    host = urlparse(url).netloc
    for attempt in (1, 2):
        try:
            r = httpx.get(url, params=params, headers=_headers(url),
                          timeout=120.0, follow_redirects=True)
        except httpx.HTTPError as e:
            if attempt == 2:
                raise SystemExit(f"transport failure: {e!r}")
            time.sleep(2.0)
            continue
        if r.status_code < 400:
            return r
        if r.status_code == 429 and host == USGS_HOST:
            reset = r.headers.get("Retry-After") or r.headers.get("X-RateLimit-Reset")
            raise SystemExit(
                f"HTTP 429 from {USGS_HOST}, not retried (a retry spends a "
                f"second request against an hourly bucket); reset "
                f"{reset + ' seconds' if reset else 'within the hour'}; "
                + ("" if USGS_KEY_VAR in os.environ else
                   f"set {USGS_KEY_VAR} (a key from https://{USGS_HOST}/signup/, "
                   "sent only as an X-Api-Key header) for a per-key bucket; ")
                + f"body: {r.text[:300]}")
        if r.status_code in (429, 500, 502, 503, 504) and attempt == 1:
            time.sleep(2.0)
            continue
        raise SystemExit(f"HTTP {r.status_code}: {r.text[:300]}")
    raise SystemExit("unreachable")


def fetch_pages(url: str, params: dict) -> list[httpx.Response]:
    """Every page of one Water Data API items query, under the budget."""
    q = {**params, "limit": USGS_PAGE_LIMIT, "skipGeometry": "true"}
    out = []
    for _ in range(USGS_PAGE_BUDGET):
        r = fetch(url, q)
        out.append(r)
        nxt = next((l.get("href") for l in r.json().get("links", [])
                    if l.get("rel") == "next"), None)
        if not nxt:
            return out
        if urlparse(nxt).netloc != USGS_HOST:
            raise SystemExit(f"refusing a next link off {USGS_HOST}: {nxt}")
        url, q = nxt, None
    raise SystemExit(f"the window holds more than "
                     f"{USGS_PAGE_BUDGET * USGS_PAGE_LIMIT} rows (the request "
                     "budget for one capture); narrow the window")


_DURATION = re.compile(r"^P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$")


def _resolve_period(period: str) -> tuple[str, str]:
    m = _DURATION.match(period.strip().upper())
    if not m or not any(m.groups()):
        raise SystemExit(f"period {period!r} is not an ISO 8601 duration "
                         "such as P7D or PT12H")
    w, d, h, mi = (int(x or 0) for x in m.groups())
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    start = now - dt.timedelta(weeks=w, days=d, hours=h, minutes=mi)
    iso = lambda t: t.isoformat().replace("+00:00", "Z")
    return iso(start), iso(now)


# Each source: (endpoint builder, canonicalizer). Canonical output is
# rows only, deterministically ordered; envelopes are stripped. A
# builder returns (url, params); the USGS builders page.
def _usgs(kind):
    def build(p):
        ids = ",".join(x if "-" in x else f"USGS-{x}"
                       for x in (y.strip() for y in p["sites"].split(","))
                       if x)
        q = {"monitoring_location_id": ids,
             "parameter_code": p.get("parameter_cd", "00060")}
        if kind == "iv":
            if "period" in p and "start_time" not in p:
                p["start_time"], p["end_time"] = _resolve_period(p["period"])
                print(f"note: period {p['period']} resolved to "
                      f"{p['start_time']}/{p['end_time']} (anchored to now; "
                      "the resolved window is the reproducible query)")
            q["datetime"] = f"{p['start_time']}/{p['end_time']}"
            return f"{USGS_API}/continuous/items", q
        q["datetime"] = f"{p['start_date']}/{p['end_date']}"
        return f"{USGS_API}/daily/items", q

    def canon(pages):
        groups = {}
        for r in pages:
            for f in r.json()["features"]:
                pr = f["properties"]
                k = (pr["monitoring_location_id"].split("-", 1)[-1],
                     pr["parameter_code"], pr["statistic_id"])
                groups.setdefault(k, []).append(
                    {"t": _utc(pr["time"]), "v": pr["value"],
                     "approval": pr.get("approval_status"),
                     "qualifiers": sorted(pr.get("qualifier") or [])})
        if not groups:
            raise SystemExit("no observations returned for that location, "
                             "parameter and window (the API answers an "
                             "unknown site or parameter with an empty "
                             "collection); nothing captured")
        return [{"site": k[0], "parameter": k[1], "statistic": k[2],
                 "rows": sorted(v, key=lambda row: row["t"])}
                for k, v in sorted(groups.items())]
    return build, canon


def _utc(t: str) -> str:
    """A date stays a date; an instant becomes ISO 8601 UTC with Z."""
    if "T" not in t:
        return t
    return (dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
            .astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"))


def _coops():
    def build(p):
        if "latest" in p or p.get("date") == "latest":
            raise SystemExit("captures need deterministic windows; "
                             "'latest' is refused (use begin_date and "
                             "end_date)")
        q = {"station": p["station"],
             "product": p.get("product", "water_level"),
             "datum": p.get("datum", "MLLW"), "units": "metric",
             "time_zone": "gmt", "format": "json",
             "application": "osp-obs-capture",
             "begin_date": p["begin_date"], "end_date": p["end_date"]}
        return "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter", q

    def canon(r):
        j = r.json()
        if "error" in j:
            raise SystemExit(f"agency error: {j['error']}")
        key = "predictions" if "predictions" in j else "data"
        return {"metadata": j.get("metadata", {}),
                "rows": [{"t": d.get("t"), "v": d.get("v")}
                         for d in j.get(key, [])]}
    return build, canon


def _psmsl():
    def build(p):
        return ("https://psmsl.org/data/obtaining/rlr.monthly.data/"
                f"{int(p['station_id'])}.rlrdata", None)

    def canon(r):
        rows, missing = [], 0
        for line in r.text.strip().splitlines():
            parts = [x.strip() for x in line.split(";")]
            if len(parts) < 2:
                continue
            v = int(parts[1])
            if v == -99999:
                missing += 1
                continue
            rows.append({"decimal_year": float(parts[0]), "rlr_mm": v})
        return {"datum": "RLR", "missing_months": missing, "rows": rows}
    return build, canon


def _hydrocron():
    def build(p):
        return ("https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/"
                "timeseries",
                {"feature": p.get("feature", "Reach"),
                 "feature_id": p["feature_id"],
                 "start_time": p["start_time"], "end_time": p["end_time"],
                 "fields": p.get("fields", "reach_id,time_str,wse,width")})

    def canon(r):
        feats = r.json()["results"]["geojson"]["features"]
        rows = [f["properties"] for f in feats]
        return {"rows": sorted(rows, key=lambda x: str(x.get("time_str")))}
    return build, canon


def _argo(kind):
    from urllib.parse import quote
    base = "https://erddap.ifremer.fr/erddap/tabledap/ArgoFloats.json"

    def build(p):
        if kind == "search":
            vars = "platform_number,cycle_number,latitude,longitude,time"
            cons = [f"time>={p['time_min']}", f"time<={p['time_max']}",
                    f"latitude>={p['lat_min']}", f"latitude<={p['lat_max']}",
                    f"longitude>={p['lon_min']}",
                    f"longitude<={p['lon_max']}"]
        else:
            vars = "cycle_number,time,pres,temp,psal"
            cons = [f'platform_number="{p["platform_number"]}"',
                    f"time>={p['time_min']}", f"time<={p['time_max']}"]
        q = quote(vars, safe="") + "".join(
            "&" + quote(c, safe="=") for c in cons)
        return f"{base}?{q}", None

    def canon(r):
        t = r.json()["table"]
        return {"columns": t["columnNames"],
                "rows": sorted(t["rows"], key=lambda row: json.dumps(
                    row, default=str))}
    return build, canon


SOURCES = {
    "usgs-iv": _usgs("iv"), "usgs-dv": _usgs("dv"), "coops": _coops(),
    "psmsl": _psmsl(), "hydrocron": _hydrocron(),
    "argo-search": _argo("search"), "argo-profile": _argo("profile"),
}


def do_capture(store: Path, source: str, params: dict) -> dict:
    build, canon = SOURCES[source]
    url, q = build(params)
    if source.startswith("usgs-"):
        pages = fetch_pages(url, q)
        r, raw = pages[0], b"\n".join(pg.content for pg in pages)
        canonical = canon(pages)
    else:
        r = fetch(url, q)
        pages, raw = [r], r.content
        canonical = canon(r)
    cbytes = json.dumps(canonical, sort_keys=True,
                        separators=(",", ":")).encode()
    retrieved = dt.datetime.now(dt.timezone.utc)
    content_sha = hashlib.sha256(cbytes).hexdigest()
    cid = retrieved.strftime("%Y%m%dT%H%M%SZ") + "-" + content_sha[:8]
    store.mkdir(parents=True, exist_ok=True)
    (store / f"{cid}.raw").write_bytes(raw)
    (store / f"{cid}.canonical.json").write_bytes(cbytes)
    nrows = canonical if isinstance(canonical, list) else canonical.get("rows", [])
    rec = {"capture_id": cid, "source": source,
           "request_url": str(r.request.url), "params": params,
           "retrieved_at": retrieved.isoformat(timespec="seconds"),
           "pages": len(pages),
           "raw_sha256": hashlib.sha256(raw).hexdigest(),
           "content_sha256": content_sha,
           "rows": sum(len(s["rows"]) for s in nrows) if isinstance(nrows, list)
                   and nrows and isinstance(nrows[0], dict) and "rows" in nrows[0]
                   else len(nrows),
           "tool_version": VERSION,
           "tool_sha256": hashlib.sha256(
               Path(__file__).read_bytes()).hexdigest(),
           "note": ("recapture may legitimately differ if the source "
                    "revises this window; a difference is information, "
                    "not an error")}
    with open(store / "manifest.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def records(store: Path) -> list[dict]:
    p = store / "manifest.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def do_verify(store: Path, cid: str) -> int:
    recs = [r for r in records(store) if r["capture_id"] == cid]
    if not recs:
        print(f"FAIL: no manifest record for {cid}")
        return 1
    rec = recs[-1]
    ok = True
    for suffix, key in ((".raw", "raw_sha256"),
                        (".canonical.json", "content_sha256")):
        f = store / f"{cid}{suffix}"
        if not f.exists():
            print(f"FAIL: missing payload {f.name}")
            ok = False
            continue
        got = hashlib.sha256(f.read_bytes()).hexdigest()
        if got != rec[key]:
            print(f"FAIL: {f.name} hash mismatch (stored payload does "
                  f"not match the manifest record)")
            ok = False
    if ok:
        print(f"PASS {cid}: payloads match the manifest "
              f"(content {rec['content_sha256'][:12]}, retrieved "
              f"{rec['retrieved_at']})")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["capture", "verify", "list"])
    ap.add_argument("--source", choices=sorted(SOURCES))
    ap.add_argument("-p", "--param", action="append", default=[],
                    metavar="KEY=VALUE")
    ap.add_argument("--id", dest="cid")
    ap.add_argument("--store", type=Path,
                    default=Path.home() / "obs-captures")
    a = ap.parse_args()
    print(f"store: {a.store}")
    if a.mode == "capture":
        if not a.source:
            raise SystemExit("--source required")
        params = dict(kv.split("=", 1) for kv in a.param)
        rec = do_capture(a.store, a.source, params)
        print(f"captured {rec['capture_id']}: {rec['source']}, "
              f"{rec['rows']} rows, content {rec['content_sha256'][:12]}, "
              f"raw {rec['raw_sha256'][:12]}, at {rec['retrieved_at']}")
        return 0
    if a.mode == "verify":
        if not a.cid:
            raise SystemExit("--id required")
        return do_verify(a.store, a.cid)
    for r in reversed(records(a.store)):
        print(f"{r['capture_id']}  {r['source']:12s} {r['rows']:7d} rows  "
              f"content {r['content_sha256'][:12]}  {r['retrieved_at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
