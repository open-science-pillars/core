# Legacy USGS captures (waterservices.usgs.gov, before the migration)

Six captures taken with `connectors/obs_capture.py` at tool version
0.1.0 on 2026-09-06T03:39Z against the legacy WaterServices JSON
endpoints, frozen here as evidence for the move of the USGS tools to
the USGS Water Data API (api.waterdata.usgs.gov). `SHA256SUMS` covers
every file; `manifest.jsonl` is the capture manifest as written. Their
content hashes are legacy identities (rows of time and value only, as
the old tool produced them) and are comparable only with other legacy
captures; see `knowledge/conventions/observation-capture.md`.

| Capture id | Query | Rows |
|---|---|---|
| 20260906T033925Z-18da4ef3 | usgs-dv 09380000 00060, 2022-10-01 to 2023-09-30 | 365 |
| 20260906T033926Z-51a6b2bd | usgs-dv 09380000 00060, 2023-01-01 to 2023-12-31 | 365 |
| 20260906T033926Z-b42ec496 | usgs-dv 09379900 62614, 2022-10-01 to 2023-09-30 | 365 |
| 20260906T033927Z-4c13d76c | usgs-dv 09085000 00060, 2021-01-01 to 2021-12-31 | 365 |
| 20260906T033927Z-99399976 | usgs-dv 09085000 00060, 2023-01-01 to 2023-12-31 | 365 |
| 20260906T033927Z-3c2c08aa | usgs-iv 09380000 00060, period P14D ending 2026-09-05T20:00 site local, all provisional | 1342 |

## Parity with the Water Data API

Compared value by value on 2026-09-06 against the `daily` and
`continuous` collections over the same windows (legacy instantaneous
times converted from site-local offsets to UTC; legacy daily midnights
taken as dates):

| Capture | Legacy rows | API rows | Times matched | Value differences | Legacy qualifiers to API fields |
|---|---|---|---|---|---|
| 18da4ef3 | 365 | 365 | 365 | 0 | A to Approved, no qualifier (365) |
| 51a6b2bd | 365 | 365 | 365 | 0 | A to Approved, no qualifier (365) |
| b42ec496 | 365 | 365 | 365 | 0 | A to Approved, no qualifier (365) |
| 4c13d76c | 365 | 365 | 365 | 0 | A to Approved (357); A,e to Approved + ESTIMATED (8) |
| 99399976 | 365 | 365 | 365 | 0 | A to Approved (345); A,e to Approved + ESTIMATED (20) |
| 3c2c08aa | 1342 | 1342 | 1342 | 0 | P to Provisional, no qualifier (1342) |

3167 of 3167 values identical. The differences are of shape, not of
data: the daily statistic keeps code 00003 while the continuous code
changes from 00000 to 00011; the unit spelling changes from `ft3/s`
to `ft^3/s`; continuous times are UTC instants where the legacy
service gave site-local times with an offset; daily times are dates
where the legacy service gave a midnight without a zone; the legacy
qualifier column (A, P, e) splits into `approval_status` and a
`qualifier` list; the site name is no longer on the observation.
