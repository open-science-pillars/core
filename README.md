# core

The Open Science Pillars foundation capability: earth science data formats,
statistics, uncertainty quantification, cartography, quality control,
reproducibility, analysis review, and the start / discover-data / report
workflows. The domain capabilities (ocean-science, hydrology) build on it.

In the organization's terms (`.osp/repository.yaml`) this is a foundation
repository serving every Earth science sphere; its knowledge bundle is
cross-cutting conventions. Its canonical behavior is the skills under
`skills/`, one `SKILL.md` per workflow, which every runtime's package
projects unchanged; the agents under `agents/` orchestrate them and hold
no behavior of their own. The Claude package files are that projection
(`.osp/package.yaml` is the source they must agree with).

## Install

```bash
claude plugin marketplace add open-science-pillars/marketplace
claude plugin install core@open-science-pillars
```

The domain plugins (ocean-science, hydrology) declare core as a
dependency, so installing one of them installs core with it; the command
above is for core on its own. An install stays at the release it was
installed from: `claude plugin update core@open-science-pillars` moves
it to the current one, and `claude plugin list` shows what you have.
Which runtimes this release is qualified on is the table below, rendered
from the qualification records; what each word asserts is in the
marketplace repository's docs/runtime-distribution.md.

<!-- osp-runtimes:start -->
Runtime support for core 0.5.0 (release lock `sha256:da7c20ab55ba`), rendered by build-kit's `osp.py advertise` from `.osp/surfaces.yaml` and the qualification records; edit those, not this block.

| Runtime | Role | Declared status | Qualification |
|---|---|---|---|
| Claude Code | development and runtime, required | supported | Qualified on 2026-09-12 |
| Claude Cowork | runtime, required | tested | Not qualified |
| OpenAI Codex | runtime, required | planned | Not qualified |
| Claude Science | future runtime | limited-release | Outside the required matrix |

A runtime is advertised as supported only on a qualified record for this exact release; a release stays valid when a runtime is not qualified, and that runtime is simply not advertised.
<!-- osp-runtimes:end -->

## Your first run

New here? Do the 10-minute [Getting Started tutorial](https://github.com/open-science-pillars/tutorials/blob/main/tutorial-1-getting-started.qmd):
it installs the plugin, orients you, and walks a real quality-control and
mapping task end to end. Unfamiliar with a term below? See the
[glossary](https://github.com/open-science-pillars/marketplace/blob/main/GLOSSARY.md).

## What's inside

- **Skills** for the everyday science stack: data formats, statistics and
  trends, uncertainty quantification, cartography, quality control,
  reproducibility, and a review pass, plus three workflows you invoke by
  name: *start* (orient in a project), *discover-data* (find a dataset), and
  *report* (write it up). Report enforces the house rule: no headline number
  without an uncertainty statement or an explicit reason there isn't one.
  One more skill, *consult-knowledge*, states once how every skill and
  agent reads the installed knowledge bundles before acting on a dataset:
  how every installed bundle is found (through the installer's record of
  plugins, so a bundle that arrives as a dependency is read the moment it
  lands), how to cite a match and voice its status, which concept wins
  when two disagree. The *start* screen reports each installed plugin's
  version and its knowledge in numbers, read from disk.
- **Agents**: a linter that checks the knowledge bundle for problems and a
  seeder that drafts new evidence-linked concepts. Both propose; neither
  merges on its own.
- **A knowledge bundle** of cross-cutting conventions (CF metadata, calendar
  traps, the sentinel fill-values that silently poison a mean).
- **Verification**: automated notebooks that re-check each workflow on small
  test data, so a broken change fails loudly; and one attested reference
  computation (`verification/trend_computation.py`, verified by
  `verification/trend_attester.py`) whose receipt names the capability
  release and the runtime that ran it, so a result from any runtime is
  checked by the same deterministic attester.

Data discovery uses the NASA Earthdata connector when available and falls
back to knowledge-based discovery otherwise (see CONNECTORS.md).

License: Apache-2.0. Cite via CITATION.cff.
