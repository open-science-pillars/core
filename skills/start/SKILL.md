---
name: start
description: "Session orientation: list installed science plugins, connector status, local config, available workflow skills, one suggested next step."
---

# start

Orient the scientist in one screen: what is installed, what is connected,
what is configured, and what to do next. Works identically invoked by slash command
or by asking conversationally ("what science tools do I have here?").

## Behavior

Produce exactly one screen with these five parts, in order:

1. **Installed OSP plugins and their knowledge.** Which Open Science
   Pillars plugins are present (core; ocean-science and other domain
   plugins; the provider bundle plugin they depend on, such as
   nasa-daac-knowledge), with one clause each on what they cover, read
   from the installer's record (`claude plugin list --json` where a shell
   exists; see consult-knowledge for how bundle roots are found from
   it). One line per plugin: version, the date it was installed or last
   updated, and its knowledge in numbers: concepts by status (stable,
   draft, deprecated) and how many stable concepts are past their
   `stale_after` date today, counted from the concept frontmatter under
   each bundle root. A plugin whose record carries `errors` is reported
   as disabled with the error's own words. All of this is read from
   disk; nothing is fetched, and no comparison with the catalog is
   made. The part closes with one line: installs stay at the release
   they were installed from, and
   `claude plugin update <name>@open-science-pillars` moves one.
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
   above: a plugin disabled by a dependency error suggests the install
   command the error names; no data touched yet suggests discover-data;
   an analysis in progress suggests finishing it and running report; a
   domain plugin installed but unconfigured suggests filling its local
   config.

## Rules

- One screen. No scrolling walls, no exhaustive option lists.
- Read-only: start never loads data, writes files, or asks questions.
- Never invent status: check what is actually loaded and configured;
  when something cannot be checked from this surface (the installer's
  record on a surface without a shell), say so rather than guessing.
- Knowledge counts come from the files under the bundle roots, never
  from an index line or a remembered figure.

## Must NOT

- Never list knowledge skills in the menu of things to invoke.
- Never suggest more than one next step.
- Never trigger a download, a file write, or a connector call that
  costs more than a status check.
