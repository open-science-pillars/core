#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "xarray", "netcdf4", "pymannkendall", "pyyaml"]
# ///
"""Deterministic attester for the foundation capability's reference
computation (trend_computation.py). No language model, consumer side.

A receipt from any runtime attests PASS (exit 0) only when ALL hold,
else FAIL (exit 1) naming the check:

  1. fields      every declared receipt field is present;
  2. code        the receipt's code_sha256 is the sanctioned executor
                 beside this file, so an edited computation invalidates
                 every earlier receipt by construction;
  3. release     the receipt names the capability release: the name and
                 version of the package beside this file, and the
                 digest of its release lock (or null where the tree
                 carries none); a receipt from another release is not
                 this release's evidence;
  4. runtime     the receipt names the runtime that produced it;
  5. data        the fixture regenerated here by the generator at the
                 receipt's seed hashes to the receipt's digest, and so
                 does the generator;
  6. series      the anomaly series in the receipt is the one the
                 regenerated fixture yields (1e-6 K);
  7. recompute   Sen's slope, the Hamed-Rao p value and the bootstrap
                 interval recomputed from the series equal the
                 receipt's (1e-9 relative);
  8. evidence    the weighting detector was tripped (unweighted mean
                 more than 5 K cold) and the receipt says it was caught;
  9. plausible   the trend lies in the fixture's imposed band (0.15 to
                 0.25 K/decade), the interval contains it, and its half
                 width is between 0 and 0.05 K/decade.

The attestation written by --out names the receipt's capability release
and runtime, the receipt's and this file's digests, and every check,
so a qualification record can cite it.

  trend_attester.py RECEIPT.json [--out ATTESTATION.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("trend_computation", HERE / "trend_computation.py")
tc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tc)

FIELDS = ["run_id", "computation", "code_sha256", "capability", "runtime", "generated_utc", "data",
          "bound_parameters", "results", "mutation_evidence", "caveats"]
REL = 1e-9
SERIES_TOL = 1e-6


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=REL, abs_tol=1e-12)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("receipt")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    receipt_path = Path(args.receipt)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    checks = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    missing = [f for f in FIELDS if f not in receipt]
    check("fields", not missing, "all present" if not missing else f"missing {missing}")
    sanctioned = tc.sha256_file(HERE / "trend_computation.py")
    check("code", receipt.get("code_sha256") == sanctioned,
          f"receipt {receipt.get('code_sha256')} vs sanctioned {sanctioned}")
    identity = tc.capability_identity(tc.PACKAGE_ROOT)
    cap = receipt.get("capability") or {}
    check("release", cap == identity, f"receipt names {cap}; this tree is {identity}")
    rt = receipt.get("runtime") or {}
    check("runtime", bool(rt.get("name")), f"runtime {rt.get('name')!r} {rt.get('version') or ''}".strip())

    data = receipt.get("data") or {}
    seed_ok = data.get("seed") == tc.SEED
    generator = tc.FIXTURES / "make_fixtures.py"
    with tempfile.TemporaryDirectory() as tmp:
        fx = tc.fixture(Path(tmp) / "era5like_t2m.nc")
        fixture_digest = tc.sha256_file(fx)
        check("data", seed_ok and data.get("sha256") == fixture_digest and data.get("generator_sha256") == tc.sha256_file(generator),
              f"regenerated fixture {fixture_digest}, receipt {data.get('sha256')}; generator match "
              f"{data.get('generator_sha256') == tc.sha256_file(generator)}; seed {data.get('seed')}")
        ds = xr.open_dataset(fx)
        fresh = tc.analysis(ds)
    results = receipt.get("results") or {}
    series = np.asarray(results.get("anomaly_k") or [], dtype=float)
    fresh_series = np.asarray(fresh["anomaly_k"], dtype=float)
    series_ok = series.size == fresh_series.size and series.size > 0 and bool(np.max(np.abs(series - fresh_series)) <= SERIES_TOL)
    check("series", series_ok, f"{series.size} months; max deviation from the regenerated fixture "
                               f"{float(np.max(np.abs(series - fresh_series))) if series.size == fresh_series.size and series.size else 'n/a'}")
    if series.size:
        re = tc.trend(series)
        rec_ci = results.get("ci95_k_per_decade") or [float('nan'), float('nan')]
        recompute_ok = (close(re["sen_k_per_decade"], float(results.get("sen_k_per_decade", float('nan'))))
                        and close(re["mk_p"], float(results.get("mk_p", float('nan'))))
                        and close(re["ci95_k_per_decade"][0], float(rec_ci[0])) and close(re["ci95_k_per_decade"][1], float(rec_ci[1])))
        check("recompute", recompute_ok, f"sen {re['sen_k_per_decade']:.9f} vs {results.get('sen_k_per_decade')}, "
                                         f"p {re['mk_p']:.3e} vs {results.get('mk_p')}, ci {re['ci95_k_per_decade']} vs {rec_ci}")
    else:
        check("recompute", False, "no series to recompute from")
    ev = receipt.get("mutation_evidence") or {}
    bias = float(ev.get("unweighted_bias_k", 0.0))
    check("evidence", bias < tc.WEIGHTING_BIAS_BAR_K and ev.get("caught") is True
          and close(bias, float(results.get("unweighted_mean_k", 0.0)) - float(results.get("weighted_mean_k", 0.0))),
          f"unweighted bias {bias:.3f} K (bar {tc.WEIGHTING_BIAS_BAR_K}), caught {ev.get('caught')}")
    sen = float(results.get("sen_k_per_decade", float('nan')))
    ci = results.get("ci95_k_per_decade") or [float('nan'), float('nan')]
    half = (float(ci[1]) - float(ci[0])) / 2
    check("plausible", 0.15 < sen < 0.25 and float(ci[0]) < sen < float(ci[1]) and 0 < half < 0.05,
          f"sen {sen:.4f} K/decade, ci [{float(ci[0]):.4f}, {float(ci[1]):.4f}], half width {half:.4f}")

    verdict = "PASS" if all(c["ok"] for c in checks) else "FAIL"
    attestation = {
        "verdict": verdict,
        "attester": "skills/basic-statistics/scripts/trend_attester.py",
        "attester_sha256": tc.sha256_file(Path(__file__).resolve()),
        "computation_sha256": sanctioned,
        "receipt": receipt_path.name,
        "receipt_sha256": tc.sha256_file(receipt_path),
        "run_id": receipt.get("run_id"),
        "capability": cap,
        "runtime": rt,
        "attested_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "checks": checks,
    }
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(attestation, indent=2) + "\n", encoding="utf-8")
    for c in checks:
        print(f"  {'ok  ' if c['ok'] else 'FAIL'} {c['name']}: {c['detail']}")
    print(f"{verdict}: {cap.get('name')} {cap.get('version')} on {rt.get('name')}, receipt {receipt.get('run_id')}"
          + (f", attestation {args.out}" if args.out else ""))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
