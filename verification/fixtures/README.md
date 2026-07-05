# Fixture provenance

Required by SPEC §6: every fixture is recorded here with
source, version, and license. All fixtures in this directory are synthetic,
generated deterministically by `make_fixtures.py` (seed 20260704), and the
generated `.nc` files are never committed (see `.gitignore`); run
`python make_fixtures.py` to produce them.

| File | Source | Structure | License |
|---|---|---|---|
| era5like_t2m.nc | make_fixtures.py  | monthly t2m, 5 degree global grid, 1985-2024; zonal 302-40*sin^2(lat) K; seasonal amplitude 1-14 K by latitude, opposite phase per hemisphere; trend 0.20 K/decade; AR(1) noise phi=0.5, sigma=0.6 K | public domain (synthetic) |
| era5like_t2m_bad.nc | make_fixtures.py  | the era5like field plus three injected defects for the six QC checks: 300 unmasked -9999.0 cell-months in 1995-1999 (no advertising attribute), one impossible 400 K value at 2005-01 near the equator, and an all-NaN gap 2003-03 through 2003-08; the file's own attributes deliberately do not mention the defects | public domain (synthetic) |

Reference numbers (printed by the generator, asserted by golden notebooks):
area-weighted global mean about 289.1 K over the record; unweighted mean
biased about 6.7 K cold (this gap is the weighting-mistake detector);
fitted global-mean trend 0.20 K/decade.

QC behavior tests copy era5like_t2m_bad.nc to a neutral filename outside
this directory before testing, so the tested agent cannot read the
defect list from this README or the generator source.
