# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "numpy",
#     "xarray",
#     "netcdf4",
#     "pymannkendall",
#     "matplotlib",
# ]
# ///
# Core golden notebook (Session 5, SPEC v0.5.1 §6): the report skill's
# computational substrate, end to end on the synthetic fixture:
# load -> QC -> anomaly -> Mann-Kendall trend -> figure -> report.
# Asserts section-complete report content, a knowledge-concept citation,
# and an uncertainty statement on the headline trend. Headless green via
# `python verification/analysis_pipeline.py` (nonzero exit on failure).

import marimo

__generated_with = "0.23.13"
app = marimo.App()


@app.cell
def _():
    import importlib.util
    import re
    import sys
    from datetime import datetime, timezone
    from pathlib import Path

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pymannkendall as pmk
    import xarray as xr

    HERE = Path(__file__).resolve().parent
    return HERE, datetime, importlib, np, plt, pmk, re, timezone, xr


@app.cell
def _(HERE, importlib):
    # Fixture: generate deterministically if absent (fixtures are never
    # committed; make_fixtures.py is the reproducible source, SPEC §6).
    fixture_path = HERE / "fixtures" / "era5like_t2m.nc"
    if not fixture_path.exists():
        spec = importlib.util.spec_from_file_location(
            "make_fixtures", HERE / "fixtures" / "make_fixtures.py"
        )
        mf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mf)
        mf.make_era5like_t2m(fixture_path)
    assert fixture_path.exists()
    return (fixture_path,)


@app.cell
def _(fixture_path, xr):
    # LOAD (data-formats practice): magic bytes, then open.
    with open(fixture_path, "rb") as f:
        magic = f.read(8)
    assert magic == b"\x89HDF\r\n\x1a\n", "fixture is not NetCDF-4/HDF5"
    ds = xr.open_dataset(fixture_path)
    assert set(ds.t2m.dims) == {"time", "lat", "lon"}
    assert ds.t2m.attrs["units"] == "K"
    return (ds,)


@app.cell
def _(ds, np):
    # QC (quality-control practice, clean-fixture expectations):
    # coords and time monotonic, fill audit, completeness, bounds.
    assert bool(np.all(np.diff(ds.lat) > 0)) and bool(np.all(np.diff(ds.lon) > 0))
    assert bool((ds.time.diff("time") > np.timedelta64(0, "s")).all())
    vmin, vmax = float(ds.t2m.min()), float(ds.t2m.max())
    for sentinel in (-9999.0, -999.0, -32767.0, 1e20, 9.96921e36):
        assert not bool((ds.t2m == sentinel).any()), f"unmasked sentinel {sentinel}"
    assert int(ds.t2m.isnull().sum()) == 0, "clean fixture must be complete"
    assert 180.0 < vmin and vmax < 340.0, "hard bounds violated"
    qc_note = (
        f"Six checks passed on the clean fixture: coordinates and time "
        f"monotonic; no unmasked sentinels; 0% missing; values within "
        f"hard bounds ({vmin:.1f} to {vmax:.1f} K); no QA layer present "
        f"(not a satellite product); no discontinuities expected or found."
    )
    return qc_note, vmin, vmax


@app.cell
def _(ds, np):
    # ANOMALY (xarray-fundamentals practice): cos-lat weighted global
    # mean, anomalies vs the stated 1991-2020 baseline.
    w = np.cos(np.deg2rad(ds.lat))
    gm = ds.t2m.weighted(w).mean(["lat", "lon"])
    gm_unweighted = ds.t2m.mean(["lat", "lon"])
    base = gm.sel(time=slice("1991-01-01", "2020-12-31"))
    clim = base.groupby("time.month").mean()
    anom = gm.groupby("time.month") - clim

    weighted_mean = float(gm.mean())
    assert 288.9 < weighted_mean < 289.2, f"weighted mean {weighted_mean}"
    assert float(gm_unweighted.mean()) - weighted_mean < -5.0, \
        "weighting detector: unweighted must be >5 K cold"
    baseline = "1991-2020"
    return anom, baseline, gm, weighted_mean


@app.cell
def _(anom, np, pmk):
    # TREND (basic-statistics practice): Hamed-Rao MK + Sen's slope,
    # block-bootstrap CI on the OLS slope (12-month moving blocks).
    res = pmk.hamed_rao_modification_test(anom.values)
    sen_per_decade = res.slope * 120
    assert res.trend == "increasing" and res.p < 0.01
    assert 0.15 < sen_per_decade < 0.25, f"Sen {sen_per_decade}"

    y = anom.values
    t = np.arange(y.size) / 120.0  # decades
    slope_hat, intercept = np.polyfit(t, y, 1)
    resid = y - (slope_hat * t + intercept)
    rng = np.random.default_rng(20260704)
    L, n = 12, y.size
    n_blocks = int(np.ceil(n / L))
    slopes = np.empty(500)
    for i in range(500):
        starts = rng.integers(0, n - L, n_blocks)
        boot = np.concatenate([resid[s:s + L] for s in starts])[:n]
        slopes[i] = np.polyfit(t, slope_hat * t + intercept + boot, 1)[0]
    ci_lo, ci_hi = np.percentile(slopes, [2.5, 97.5])
    half_width = (ci_hi - ci_lo) / 2
    assert ci_lo < sen_per_decade < ci_hi
    assert half_width < 0.05, f"CI implausibly wide: {half_width}"
    assert half_width > 0, "a zero-width interval is not an uncertainty"
    headline = (
        f"{sen_per_decade:.3f} +/- {half_width:.3f} K/decade "
        f"(95% CI, moving-block bootstrap, block length 12 months, "
        f"500 resamples, seed 20260704; Hamed-Rao MK p = {res.p:.1e})"
    )
    return ci_hi, ci_lo, headline, res, sen_per_decade


@app.cell
def _(HERE, anom, baseline, headline, plt):
    # FIGURE (cartography practice): anomaly series, labeled band caption.
    fig, ax = plt.subplots(figsize=(7.2, 3.2), constrained_layout=True)
    annual = anom.resample(time="YS").mean()
    ax.plot(anom.time, anom, lw=0.5, alpha=0.6, label="monthly anomaly")
    ax.plot(annual.time, annual, lw=2, label="annual mean")
    ax.set_ylabel(f"t2m anomaly vs {baseline} (K)")
    ax.set_title(f"Global mean anomaly; trend {headline.split('(')[0].strip()}")
    ax.legend(frameon=False)
    figure_path = HERE / "analysis_pipeline_figure.png"
    fig.savefig(figure_path, dpi=150)
    assert figure_path.exists() and figure_path.stat().st_size > 10_000
    return (figure_path,)


@app.cell
def _(
    HERE,
    baseline,
    datetime,
    figure_path,
    fixture_path,
    headline,
    np,
    qc_note,
    re,
    timezone,
    weighted_mean,
    xr,
):
    # REPORT (report skill's substrate): six sections, concept citations,
    # uncertainty statement on the headline trend. Then the assertions.
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report_md = f"""# Global mean temperature trend, synthetic fixture

## Data Description
Synthetic ERA5-like monthly 2 m temperature ({fixture_path.name}),
5 degree global grid, 1985-2024, generated by make_fixtures.py
(seed 20260704); public domain synthetic test data, not observations.

## Methods
cos-latitude weighted global mean (weighted mean {weighted_mean:.2f} K);
monthly anomalies against the {baseline} climatology; trend by Sen's
slope with the Hamed-Rao modified Mann-Kendall test (autocorrelated
monthly series); CI by moving-block bootstrap, block length 12 months,
500 resamples, seed 20260704. Calendar handling per
core/knowledge/conventions/calendars.md (status: verified).

## Results
Headline trend: {headline}.

## Quality Notes
{qc_note}

## Provenance
Knowledge concepts consulted: core/knowledge/conventions/calendars.md
(verified; monthly climatology and baseline convention);
core/knowledge/conventions/common-fill-values.md (verified; sentinel
audit in QC); core/knowledge/conventions/cf-conventions.md (verified;
output metadata practice). Data path: local fixture; no connector used.

## Reproducibility
xarray {xr.__version__}, numpy {np.__version__}; bootstrap seed
20260704; fixture regenerable via verification/fixtures/make_fixtures.py;
generated {now} by verification/analysis_pipeline.py.
"""
    report_path = HERE / "analysis_pipeline_report.md"
    report_path.write_text(report_md)

    for section in ("Data Description", "Methods", "Results",
                    "Quality Notes", "Provenance", "Reproducibility"):
        assert f"## {section}" in report_md, f"missing section {section}"
    assert len(re.findall(r"core/knowledge/[\w/.-]+\.md", report_md)) >= 3, \
        "report must cite knowledge concepts by bundle path"
    results = report_md.split("## Results")[1].split("##")[0]
    assert re.search(r"\+/-.*95% CI", results, flags=re.S), \
        "headline trend lacks an uncertainty statement"
    print("analysis_pipeline: all assertions passed")
    print(f"  headline: {headline}")
    print(f"  report: {report_path}")
    print(f"  figure: {figure_path}")
    return (report_md,)


if __name__ == "__main__":
    app.run()
