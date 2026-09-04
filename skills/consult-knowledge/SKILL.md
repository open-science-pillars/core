---
name: consult-knowledge
description: "Consult installed knowledge bundles before acting on a dataset: which concept directories to search, how to cite a match and voice its status, which concept wins on conflict."
user-invocable: false
---

# consult-knowledge

The one consult convention every Open Science Pillars skill and agent
follows before it acts on a dataset, a quantity, or a method. Skills
carry procedure and hard refusals; facts about data live in knowledge
concepts and are read fresh per run. A concept added or corrected since
the last run is found this way and changes behavior with no skill edit.

A skill that cannot load this file carries the five-word form instead,
verbatim: "Consult installed knowledge concepts first."

## Where to look

Every installed plugin ships a bundle at `knowledge/` (root index.md and
log.md, concepts in typed directories). Search all of them: the domain
plugin's own bundle, core's, and any bundle a project's local config
names. A plugin that pins a copy of a provider bundle declares the copy
directory in `knowledge/snapshot.yaml` (`copy_dir`); the copies are
ordinary concepts and are searched like the rest.

Under each bundle root, and under each copy directory, glob the
directories that exist:

| directory | what it answers |
|---|---|
| `datasets/` | product identity, access, versions, native grid, the Uncertainty section |
| `fields/` | per-variable facts: names, units, sign, staggering, DOIs |
| `gotchas/` | traps: mechanism, wrong-result mode, the correct approach |
| `recipes/` | validated analysis patterns with expected ranges |
| `computations/` | attested computations: sanctioned code, inputs, receipts, the reference numbers recipes and findings quote |
| `conventions/` | cross-cutting practice: calendars, fill values, CF, sanity ranges |
| `validity-domains/` | where a product's claims hold and where they do not |
| `findings/` | scientific claims with receipts, signed or draft |
| `connectors/` | endpoint facts for interactive services |

`references/` holds files concepts cite (code, receipts, masks); it is
reached through the citing concept, not searched on its own.

Grep by product name and ShortName, variable, quantity, method, region,
and the check in play. Read every match in full. Where a concept exists,
never work from a remembered number, list, or rule.

## What to do with a match

Restate what each concept changes about the plan, at the step it
constrains, and cite it by bundle path
(`knowledge/gotchas/ecco-native-vs-regridded.md`) with its status.
Numbers come from the concept, or from the computation receipt it cites,
at the precision written there. A concept that shaped a choice is cited;
a concept that is cited was read.

## Voicing status

Concept status is `stable` unless the frontmatter says otherwise.

- `stable`: state it plainly. For a high-severity claim (a wrong-result
  mode, a number a conclusion rests on) say how it was verified: a
  `human:` verified event is human-reviewed; a process-only event is
  machine-confirmed; none is unverified.
- `draft`: consultable, voiced as unverified ("a draft concept, not yet
  reviewed, says ..."). Never presented as settled.
- `deprecated`: never cited as current; follow `superseded_by`.
- `disputed:` present: state the dispute and its link beside the claim.
- past `stale_after`: say the sweep is due and the fact may be outdated.

## Precedence

When two concepts disagree, the canonical provider bundle wins over a
plugin-local concept (a snapshot copy is the provider's text and ranks
with it); stable wins over draft; within a tier the later verified event
wins. Say that they disagree. A concept wins over anything a skill or an
agent remembers, including this file.

## When nothing matches

Say so ("no installed concept covers X"), proceed on general method
labeled as such, and never invent a concept, a path, a number, or a
citation. The gap is ingest material: name it in the Provenance note so
the steward can open a concept issue.

## Must NOT

- Never carry a concept's fact into a skill body; the skill points here.
- Never resolve a disagreement between concepts silently.
- Never treat an unread concept as consulted.
