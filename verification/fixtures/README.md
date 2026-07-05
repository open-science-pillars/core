# Fixture provenance

Required by SPECIFICATION.md v0.5.1 §6: every fixture is recorded here with
source, version, and license. All fixtures in this directory are synthetic,
generated deterministically by `make_fixtures.py` (seed 20260704), and the
generated `.nc` files are never committed (see `.gitignore`); run
`python make_fixtures.py` to produce them.

| File | Source | Structure | License |
|---|---|---|---|
| era5like_t2m.nc | make_fixtures.py (Session 2) | monthly t2m, 5 degree global grid, 1985-2024; zonal 302-40*sin^2(lat) K; seasonal amplitude 1-14 K by latitude, opposite phase per hemisphere; trend 0.20 K/decade; AR(1) noise phi=0.5, sigma=0.6 K | public domain (synthetic) |

Reference numbers (printed by the generator, asserted by golden notebooks):
area-weighted global mean about 289.1 K over the record; unweighted mean
biased about 6.7 K cold (this gap is the weighting-mistake detector);
fitted global-mean trend 0.20 K/decade.

Session 4 adds the bad-data variant (unmasked -9999 sentinels, an
impossible value, a 6-month gap) to make_fixtures.py for the QC tests.
