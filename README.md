# core

The Open Science Pillars foundation plugin: earth science data formats,
statistics, uncertainty quantification, cartography, quality control,
reproducibility, analysis review, and the start / discover-data / report
workflows. Domain plugins (ocean-science first) build on it.

## Install

```bash
claude plugin marketplace add open-science-pillars/marketplace
claude plugin install core@open-science-pillars
```

Cowork and Claude Science: add the marketplace and install from it.

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
- **Agents**: a linter that checks the knowledge bundle for problems and a
  seeder that drafts new evidence-linked concepts. Both propose; neither
  merges on its own.
- **A knowledge bundle** of cross-cutting conventions (CF metadata, calendar
  traps, the sentinel fill-values that silently poison a mean).
- **Verification**: automated notebooks that re-check each workflow on small
  test data, so a broken change fails loudly.

Data discovery uses the NASA Earthdata connector when available and falls
back to knowledge-based discovery otherwise (see CONNECTORS.md).

License: Apache-2.0. Cite via CITATION.cff.
