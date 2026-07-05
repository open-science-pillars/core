# Eval seed results (core)

The "seed" set is the hand-graded baseline: one manual run per case on
Claude Code, N=1, rubric-graded by hand, distinct from the automated
N=20 runner (with binomial confidence intervals) that supersedes it.
Grader: OSP steward review. Model: claude-fable-5 for all runs.
Convention per SCHEMA.md; transcripts referenced live in
marketplace/docs/prompts/behavior/.

| Case | Date | Model | Grade | Evidence line |
|---|---|---|---|---|
| area-weighting | 2026-07-04 | claude-fable-5 | pass | cos-lat weighted 289.06 K reported; unweighted 282.40 named as the trap (behavior/weighted-global-mean.md, verbatim prompt) |
| uncertainty-statement | 2026-07-04 | claude-fable-5 | FAIL | headline +0.28 K carried no interval, method/level, or waiver; nearby annual-means std was descriptive context, not an attached uncertainty statement |
| trend-method | 2026-07-04 | claude-fable-5 | pass (note) | Hamed-Rao chosen with autocorrelation reasoning, Sen's slope per decade; note: no CI on the slope magnitude, consistent with the uncertainty-statement failure mode |

## Seed findings

The uncertainty-statement failure is the seed pass's substantive
result: outside the report workflow (where the gate enforces it), an
uncoached computation prompt did not trigger the house uncertainty
rule. Phase 2 should treat this as the first tuning target and re-run
at N=20 to estimate the true rate.
