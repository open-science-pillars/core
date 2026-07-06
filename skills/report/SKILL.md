---
name: report
description: "Assemble an analysis report: Data Description, Methods, Results with uncertainty statements, Quality Notes, Provenance citing knowledge concepts, Reproducibility."
---

# report

Assemble the session's analysis into a report a colleague can trust and
rerun. Works by
slash command or conversationally ("write this up"). The report renders
what was actually computed this session; it never invents numbers,
methods, or citations.

## Knowledge coupling (standing rule)

This skill is a procedure, not a store of dataset facts. Every dataset
detail the report states (product version, verification date, expected
range, uncertainty framing, release caveat, convention, or gotcha) is
discovered in the installed knowledge bundles, not remembered here:
glob and grep `knowledge/` (core and any domain bundle in play) for the
concepts touching the datasets, methods, and quantities reported, read
the matches, restate what each says in the report's own words, and cite
it by bundle path. A concept added or corrected since you last ran is
picked up this way. The report carries none of these facts inline; when
a stated fact has no owning concept, that gap is itself a Quality or
Provenance note.

## The confirmation gate (hard gate, before anything is written)

Before writing any file, present:

- the proposed filename (and format),
- the section list with one line on what each will contain,

and wait for explicit confirmation. The gate lives here in the skill
body so it fires on every surface, conversational included. On surfaces
where file writing is unavailable, the same gate confirms scope, then
the report renders in-session with a note saying so.

Format: markdown by default; docx only when asked.

## The six sections

1. **Data Description.** Each dataset used: product and version (with
   verification date when it came from a dataset concept), period,
   region, resolution, access path.
2. **Methods.** What was computed and how: weighting, baselines, trend
   method and its autocorrelation handling, calendar choices, block
   lengths and seeds for resampling methods. Specific enough to
   reimplement.
3. **Results.** The findings, and **the house rule is enforced here
   (hard refusal): every headline quantity carries an uncertainty
   statement (interval,
   spread, or native product uncertainty) with method and level, or an
   explicit one-line reason why none is available.** A result that
   arrives without uncertainty goes back for one (or gets its waiver)
   before the report is assembled.
4. **Quality Notes.** QC findings on the inputs: what was flagged,
   masked, or gap-ridden, and what that means for the conclusions;
   "QC not run" is itself a note when true.
5. **Provenance.** The knowledge concepts consulted, cited by bundle
   path (for example `core/knowledge/conventions/calendars.md`, or a
   domain bundle's dataset and gotcha concepts), with concept status
   noted when it is anything other than verified. Connector and search
   paths used (Earthdata MCP vs knowledge fallback) are recorded here
   too.
6. **Reproducibility.** Package versions that produced the results,
   the environment file when one exists, random seeds, input file
   identity (names, versions, DOIs), and the provenance history line
   written into any saved outputs (per the reproducibility skill).

## Rules

- Content comes from the session's actual computations and their
  outputs; a section with nothing real to say says so briefly rather
  than padding.
- Figures included in the report follow cartography's rules (defined
  captions, uncertainty visualization where results carry intervals).
- Saved report files carry CF-style provenance where applicable: at
  minimum a generation timestamp, tool identity, and input list in the
  document header.

## Must NOT (hard refusals: invariant, universal, gate-shaped)

- Never write a file before the gate is confirmed.
- Never assemble a Results section containing a headline quantity with
  neither an uncertainty statement nor a waiver.
- Never cite a concept that was not actually consulted, and never
  consult one without citing it.
- Never fabricate a Methods detail that cannot be traced to what ran;
  a gap in the record is reported as a gap.
