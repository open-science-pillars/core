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

## What's inside

- `skills/`: eight knowledge skills (background expertise, auto-loading)
  and three workflow skills (start, discover-data, report). Report enforces
  the house rule: no headline result without an uncertainty statement or an
  explicit one-line waiver.
- `agents/`: knowledge-linter (bundle health checks, proposes only) and
  knowledge-seeder (drafts evidence-linked concepts, never merges).
- `knowledge/`: OKF bundle of cross-cutting conventions (CF metadata,
  calendar traps, unmasked fill values).
- `verification/`: marimo golden notebooks; `analysis_pipeline.py` runs the
  fixture pipeline end to end, headless, exit nonzero on failure.
- `evals/`: seed methodology cases (area weighting, uncertainty statement,
  trend method).
- `.mcp.json`: NASA Earthdata MCP connector with graceful degradation to
  knowledge-based discovery; see CONNECTORS.md.

Build status per surface: marketplace repo, docs/PROGRESS.md. Spec:
SPECIFICATION.md §3. License: Apache-2.0. Cite via CITATION.cff.
