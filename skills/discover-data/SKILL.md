---
name: discover-data
description: Find earth science datasets for a research need: parse to parameters, search Earthdata, compare candidates, surface knowledge-bundle gotchas.
---

# discover-data

Turn a research need into a shortlist of concrete datasets with honest
caveats. Authored in Session 5 per SPECIFICATION.md v0.5.1 §3.4. Works
by slash command or conversationally ("what SST data should I use for
the North Atlantic?"). Recommends only; loading data is a separate,
gated step owned by the loader workflows.

## Behavior, in order

1. **Parse the need into structured parameters** and show them back:
   variable, region, period, temporal and spatial resolution, level or
   depth if applicable, latency needs (NRT vs research quality).
   Unstated parameters are recorded as open, not silently defaulted.
2. **Consult installed knowledge bundles first.** Check dataset concepts
   for products matching the parameters, and collect their gotchas and
   Uncertainty notes; these travel with the results.
3. **Search.** When the Earthdata MCP connector is available, query it
   (CMR collection search) with the parsed parameters. When it is not,
   use the knowledge-based fallback: candidate products from the
   bundles and standing domain knowledge, each with its archive URL,
   and **name the fallback explicitly** ("Earthdata connector
   unavailable; candidates from installed knowledge, archive links
   below"). No silent degradation in either direction.
4. **Output a comparison table.** One row per candidate: product and
   version, variable match, spatial and temporal resolution, period of
   record, access path (ShortName, archive URL), and a notes column
   carrying the load-bearing caveat for each.
5. **Surface relevant gotchas alongside the results, unprompted.** A
   recommendation that omits a known trap for the recommended product
   is wrong even when the table is right; cite the concept (bundle
   path) with each gotcha so provenance survives.
6. **At most one clarifying question**, and only when the answer
   actually changes the recommendation (a missing region rarely does;
   a missing period often does). Ask it after showing what can already
   be answered, never as a gate before doing any work.

## Rules

- Knowledge first: bundle concepts outrank generic recollection; when a
  bundle concept and general knowledge disagree, the concept wins and
  the disagreement is worth reporting.
- State versions with a verification date when quoting them from a
  dataset concept; never hardcode a processing baseline from memory.
- Candidates the parameters rule out are dropped silently; near-misses
  (right variable, wrong resolution) earn one line saying why they
  missed.

## Must NOT

- Never download anything or trigger a loader.
- Never present results without checking installed bundles for gotchas
  on the recommended products.
- Never ask more than one clarifying question.
- Never degrade to the fallback, or to the connector, without naming
  which path produced the results.
