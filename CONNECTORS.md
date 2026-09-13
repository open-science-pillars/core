# Connectors: core

What this plugin talks to over the network, what leaves your machine
when it does, and what happens when it cannot. This file is the
disclosure; `.mcp.json` is the wire.

## NASA Earthdata MCP (`earthdata`)

**What it is.** `.mcp.json` registers NASA's Earthdata MCP server
(github.com/nasa/earthdata-mcp), a streamable-http server in front of
NASA's Common Metadata Repository.

**What leaves your machine.** Search terms only: collection names,
keywords, and the spatial or temporal bounds of a query, sent over
HTTPS to NASA's CMR. No credential is sent, because CMR search is a
public API and this connector needs none. No file, no local path, and
no data you hold ever passes through it.

**What does not go through it.** Downloads. Data retrieval happens
directly between your machine and the archive through earthaccess,
never through this connector, which is why an unreachable connector
cannot block a download.

**When it is unavailable.** Nothing breaks. discover-data falls back to
knowledge-based discovery with archive URLs and says which path it
used; loading proceeds from local files or direct library access.

**Where the facts about this service are maintained.** Endpoint,
transport, tool surface, auth boundary and deprecation status are
recorded as a dated concept with a staleness date in the PO.DAAC
knowledge bundle (`connectors/earthdata-mcp.md` in
github.com/open-science-pillars/nasa-daac-knowledge), re-verified on a
schedule. This file deliberately does not restate them, so there is
one place to correct when they change.

**Per runtime.** Claude Code and Cowork read `.mcp.json` from the
installed plugin; on Cowork the stdio observations server runs on your
computer with your permissions, so `uv` must be reachable from the app.
What each runtime consumes, and what a qualified record asserts, is in
the marketplace repository's docs/runtime-distribution.md.

## Credentials

An Earthdata Login is needed only to retrieve data, never to search.
It is read by earthaccess at download time and is never handled by
this plugin, never sent to the connector above, and never stored in
this repository in any form.

The USGS Water Data API key (`API_USGS_PAT`) is optional and
recommended: it is read from the environment by the observations
server and the capture tool at request time, sent only as a header to
api.waterdata.usgs.gov, and never written anywhere. The observations
section below says exactly what happens with and without it.

## Observations MCP (`observations`)

**What it is.** `.mcp.json` runs `connectors/observations_mcp.py` from
this plugin over stdio: one thin server exposing five authoritative
observation sources as tools. USGS Water Data API stream gauges, NOAA CO-OPS
tide stations, Argo profiling floats (Ifremer ERDDAP), PSMSL
long-record tide gauges, and PO.DAAC Hydrocron SWOT river series.
Every tool is a paper-thin translation from parameters to one
official HTTPS request; no science lives in the server.

**What leaves your machine.** Query parameters only: station, gauge,
float, and reach identifiers, bounding boxes, and time ranges, sent
over HTTPS to the agency endpoint named in each tool. One optional
credential exists. If you set `API_USGS_PAT` in your environment (a
key from https://api.waterdata.usgs.gov/signup/), the server sends
its value as an `X-Api-Key` header to api.waterdata.usgs.gov and to
no other host; the request URL that every response, capture manifest
and receipt copies never carries it, and the offline and live
selftests assert that a sentinel key appears in none of them. Unset,
the USGS requests share the per-address bucket with everything else
on your machine that calls the same API, and a 429 comes back as a
structured error naming the variable and the reset window; the server
never retries against that host. No file, no local path, and no data
you hold is ever sent.

**What does not go through it.** Archive holdings. ECCO, SWOT, and
GRACE retrieval happens through earthaccess as always; this server
fetches point observations only, and nothing attested ever calls it.

**When it is unavailable.** Nothing breaks. Gates and attesters never
depend on connectors; the knowledge concepts carry archive URLs for
every source.

**Where the facts are maintained.** Endpoint, tool surface, and the
correctness knowledge (datum conventions, quality flags, reference
offsets) are dated concepts with staleness dates: CO-OPS, Argo, and
PSMSL in `knowledge/connectors/` of
github.com/open-science-pillars/ocean-science; USGS and Hydrocron in
`knowledge/connectors/` of github.com/open-science-pillars/hydrology.
This file deliberately does not restate them.

**Running from a checkout.** `uv run connectors/observations_mcp.py`
from the repo root; `--selftest` probes all five sources live.

**Version and pin propagation (the runbook).** The server file is the
unit of review. Its PEP 723 block pins dependency majors, so a launch
resolves within reviewed bounds; the file's own VERSION constant names
the contract version and travels in every response as server_version.
Repositories that run the server from a commit-pinned URL (hydrology,
ocean-science) update in exactly one way: after a change merges here,
each repo repoints its `.mcp.json` pin to the new commit in a reviewed
edit of its own. Nothing else moves a pin. The offline contract tests
(`--test`, recorded fixtures, run in CI) are the drift alarm: an
upstream schema change fails the parser contract before it reaches a
user as a wrong answer.
