---
name: start
description: "Session orientation: list installed science plugins, connector status, local config, available workflow skills, one suggested next step."
---

# start

Orient the scientist in one screen: what is installed, what is connected,
what is configured, and what to do next. Authored in Session 5 per
SPECIFICATION.md v0.5.1 §3.4. Works identically invoked by slash command
or by asking conversationally ("what science tools do I have here?").

## Behavior

Produce exactly one screen with these five parts, in order:

1. **Installed OSP plugins.** Which Open Science Pillars plugins are
   present (core; ocean-science and other domain plugins when installed),
   with one clause each on what they cover.
2. **Connector status.** Whether the Earthdata MCP connector is
   configured and reachable this session; when it is not, say so plainly
   and note that discovery falls back to knowledge-based search
   (discover-data names the fallback when it fires). On surfaces with
   per-session connectors, "not configured this session" is a normal
   state, not an error.
3. **Local config summary.** If a project local config exists (for
   example `ocean-science.local.md`), summarize the filled blocks (data
   paths, compute, region defaults) in a line or two; if none exists,
   say none is configured and which template creates one.
4. **Available workflow skills, grouped by plugin.** Core's workflows
   (discover-data, report), then each installed domain plugin's
   workflows. Knowledge skills are not listed; they load themselves as
   background expertise.
5. **One suggested next step.** Exactly one, chosen from the state
   above: no data touched yet suggests discover-data; an analysis in
   progress suggests finishing it and running report; a domain plugin
   installed but unconfigured suggests filling its local config.

## Rules

- One screen. No scrolling walls, no exhaustive option lists.
- Read-only: start never loads data, writes files, or asks questions.
- Never invent status: check what is actually loaded and configured;
  when something cannot be checked from this surface, say so rather
  than guessing.

## Must NOT

- Never list knowledge skills in the menu of things to invoke.
- Never suggest more than one next step.
- Never trigger a download, a file write, or a connector call that
  costs more than a status check.
