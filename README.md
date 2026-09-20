# core

The foundation capability of Open Science Pillars: the skills a scientist
uses in every analysis (opening NetCDF, Zarr, GeoTIFF and GRIB files;
statistics and trends; uncertainty on every headline number; maps; quality
control; reproducible outputs; a review pass) and three workflows you
invoke by name: `start` orients you in a project, `discover-data` finds a
dataset, `report` writes the analysis up. The domain capabilities
(ocean-science, hydrology) build on it and install it for you. It is a
foundation repository serving every Earth science sphere (`kind:
foundation` in `.osp/repository.yaml`); the words used on this page
(capability, plugin, sphere, knowledge bundle, runtime) are defined in the
[glossary](https://github.com/open-science-pillars/marketplace/blob/main/GLOSSARY.md).

## Install

On Claude Code:

```bash
claude plugin marketplace add open-science-pillars/marketplace
claude plugin install core@open-science-pillars
```

What comes with it: nothing else. core declares no dependencies; it is the
dependency every domain capability declares, so installing ocean-science
or hydrology installs core alongside. An install stays at the release it
was installed from: `claude plugin update core@open-science-pillars` moves
it to the current one, and `claude plugin list` shows what you have.

On Claude Cowork: add the marketplace by repository
(`open-science-pillars/marketplace`) under Customize > Plugins > Add
marketplace, then install the same capability from it; the shell commands
on this page are for Claude Code.

Local requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/).
The observations connector and every script here (the golden notebook,
the reference computation and its attester) declare their dependencies in
a PEP 723 header and run as `uv run <script>`; uv builds the environment
on first run, so nothing is installed by hand. Never `python script.py`:
it skips the header and fails at the first import. No account is needed
for anything in core (an optional USGS key raises a rate limit; see
[CONNECTORS.md](CONNECTORS.md)); an Earthdata Login matters only when a
domain capability downloads NASA data.

## Runtimes

Which runtimes this release is qualified on is the table below, rendered
from the qualification records; what each word asserts is in the
marketplace repository's
[docs/runtime-distribution.md](https://github.com/open-science-pillars/marketplace/blob/main/docs/runtime-distribution.md).

<!-- osp-runtimes:start -->
Runtime support for core 0.6.0 (release lock `sha256:123d1b1ca25a`), rendered by build-kit's `osp.py advertise` from `.osp/surfaces.yaml` and the qualification records; edit those, not this block.

| Runtime | Role | Declared status | Qualification |
|---|---|---|---|
| Claude Code | development and runtime, required | supported | Qualified on 2026-09-20 |
| Claude Cowork | runtime, required | tested | Not qualified, waived for this release (Claude Cowork is not qualified for this release. A Cowork record is a run by a person with Cowork in front of them, installing from the catalog, and no such run has been made for 0.6.0; the runtime cannot be driven headlessly, so the coordinator carrying this release on the maintainer's behalf cannot make one either. This repeats the decision recorded for land-ice 0.1.0 on 2026-09-19 for the same reason. Nothing about the capability is known to fail there: its projection renders and validates in the gate, and the Claude Code run for this release passed every required test. The surface is not advertised until a run exists.; human:PaulMRamirez, 2026-09-20) |
| OpenAI Codex | runtime, required | planned | Not qualified, waived for this release (OpenAI Codex is not qualified for this release. No release in this organization has been qualified on Codex: the Agent Plugins projection renders and passes plugin-check in the gate, but the Codex leg has never been exercised, so there is no procedure to run and nothing to record. This repeats the decision recorded for land-ice 0.1.0 on 2026-09-19 for the same reason. The surface is not advertised, and the projection is published as conformant rather than as tested.; human:PaulMRamirez, 2026-09-20) |
| Claude Science | future runtime | limited-release | Outside the required matrix |

A runtime is advertised as supported only on a qualified record for this exact release; a release stays valid when a runtime is not qualified, and that runtime is simply not advertised.
<!-- osp-runtimes:end -->

## First result

[tutorials/quickstart.md](tutorials/quickstart.md) in this repository
takes about five minutes and assumes only that the plugin is installed
and `uv` is on your path: orient, find data, compute under the house
rules, review, report, then run the attested reference computation whose
receipt names this release and the runtime that ran it. The long form is
[Tutorial 1, Getting Started](https://github.com/open-science-pillars/tutorials/blob/main/tutorial-1-getting-started.qmd)
in the tutorials repository (measured at 4.6 minutes on a fresh install):
it installs the plugin and walks a quality-control and mapping task end
to end.

## What's inside

- **Skills** (`skills/`, one `SKILL.md` each): `data-formats`,
  `xarray-fundamentals`, `basic-statistics`, `uncertainty-quantification`,
  `cartography`, `quality-control`, `reproducibility`, `analysis-review`,
  `consult-knowledge`, and the three workflows `start`, `discover-data`
  and `report`. The report workflow enforces the house rule: no headline
  number without an uncertainty statement or an explicit reason there is
  none. A computation is a skill, so `basic-statistics` also carries the
  scripts of the attested reference computation in its `scripts/`
  directory: `trend_computation.py`, the sanctioned executor, and
  `trend_attester.py`, the deterministic attester that checks its
  receipt.
- **Agents** (`agents/`): `knowledge-linter` checks a knowledge bundle for
  problems; `knowledge-seeder` drafts new evidence-linked concepts. Both
  propose; neither merges on its own.
- **Knowledge** (`knowledge/`): core's own bundle of cross-cutting
  conventions (CF metadata, calendars, the sentinel fill values that
  silently poison a mean, smell-test ranges), one gotcha and one attested
  computation. The provider bundles (PO.DAAC, ESDIS) live in
  [nasa-daac-knowledge](https://github.com/open-science-pillars/nasa-daac-knowledge)
  and arrive with the domain capabilities; `consult-knowledge` states how
  every installed bundle is found and cited.
- **Verification** (`verification/`): `analysis_pipeline.py`, the golden
  notebook that re-checks the workflows on a synthetic fixture and then
  proves the two scripts of the attested reference computation, and
  `fixtures/make_fixtures.py`, the deterministic generator the golden,
  the executor and the attester each regenerate that fixture from. No
  fixture is committed.
- **Evals** (`evals/`): four hand-graded judgment cases (`area-weighting`,
  `fill-value-detection`, `trend-method`, `uncertainty-statement`) and
  their seed results.

## Connectors and credentials

Data discovery uses the NASA Earthdata connector when it is reachable and
falls back to knowledge-based discovery otherwise; the observations
connector fetches point observations from five public agency sources.
What leaves your machine, which credential is read where, and what
happens when a connector is unavailable is in [CONNECTORS.md](CONNECTORS.md).

## Contributing

Start with the marketplace repository's
[CONTRIBUTING.md](https://github.com/open-science-pillars/marketplace/blob/main/CONTRIBUTING.md)
and the guides under its `docs/` (contributing a skill, contributing
knowledge, testing, the package authoring guide).

## License and citation

Apache-2.0. Cite via [CITATION.cff](CITATION.cff).
