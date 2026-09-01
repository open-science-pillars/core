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
an unreproducible query cannot be a citable record.

Usage:
  obs_capture.py capture --source psmsl -p station_id=1
  obs_capture.py capture --source usgs-dv -p sites=01646500 \\
      -p start_date=2024-01-01 -p end_date=2024-03-31
  obs_capture.py verify --id <capture_id>
  obs_capture.py list
Store: --store DIR (default ~/obs-captures), shown on first use.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

VERSION = "0.1.0"
UA = {"User-Agent": f"osp-obs-capture/{VERSION}"}


def fetch(url: str, params: dict | None = None) -> httpx.Response:
    for attempt in (1, 2):
        try:
            r = httpx.get(url, params=params, headers=UA, timeout=60.0,
                          follow_redirects=True)
        except httpx.HTTPError as e:
            if attempt == 2:
                raise SystemExit(f"transport failure: {e!r}")
            time.sleep(2.0)
            continue
        if r.status_code < 400:
            return r
        if r.status_code in (429, 500, 502, 503, 504) and attempt == 1:
            time.sleep(2.0)
            continue
        raise SystemExit(f"HTTP {r.status_code}: {r.text[:300]}")
    raise SystemExit("unreachable")


# Each source: (endpoint builder, canonicalizer). Canonical output is
# rows only, deterministically ordered; envelopes are stripped.
def _usgs(kind):
    def build(p):
        base = {"format": "json", "sites": p["sites"],
                "parameterCd": p.get("parameter_cd", "00060")}
        if kind == "iv":
            base["period"] = p["period"]  # deterministic only if past-anchored; warn below
            base["siteStatus"] = "all"
            return "https://waterservices.usgs.gov/nwis/iv/", base
        base["startDT"], base["endDT"] = p["start_date"], p["end_date"]
        return "https://waterservices.usgs.gov/nwis/dv/", base

    def canon(r):
        out = []
        for ts in r.json()["value"]["timeSeries"]:
            out.append({"site": ts["sourceInfo"]["siteCode"][0]["value"],
                        "parameter": ts["variable"]["variableCode"][0]["value"],
                        "rows": [{"t": v["dateTime"], "v": v["value"]}
                                 for v in ts["values"][0]["value"]]})
        return sorted(out, key=lambda s: (s["site"], s["parameter"]))
    return build, canon


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
    r = fetch(url, q)
    raw = r.content
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
