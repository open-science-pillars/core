---
type: Attested Computation
spheres: []
title: "Global-mean temperature trend of the synthetic fixture (attested)"
description: "The foundation capability's reference computation: the area-weighted global mean of the synthetic fixture, anomalies against 1991-2020, Sen's slope under the Hamed-Rao test and a moving-block bootstrap interval, written as a receipt that names the capability release and the runtime that ran it; the attester regenerates the fixture and recomputes every number."
tags: [trend, mann-kendall, hamed-rao, bootstrap, area-weighting, attested, receipt, runtime]
runtime: python
parameters:
  - { name: runtime, type: "the runtime that ran the executor (claude-code, claude-cowork, openai-codex, ...)", required: true }
computation: ../../skills/basic-statistics/scripts/trend_computation.py
executor:
  resource: ../../skills/basic-statistics/scripts/trend_computation.py
  receipt: [run_id, computation, code_sha256, capability, runtime, generated_utc, data, bound_parameters, results, mutation_evidence, caveats]
attester:
  resource: ../../skills/basic-statistics/scripts/trend_attester.py
generated: { by: claude-code/fable-5.1, at: 2026-09-12T06:30:00Z }
status: draft
sources:
  - id: make-fixtures
    resource: ../../verification/fixtures/make_fixtures.py
    title: "make_fixtures.py: the deterministic generator of era5like_t2m.nc (seed 20260704, imposed trend 0.20 K/decade, AR(1) noise), which the attester regenerates rather than trusts"
  - id: golden
    resource: ../../verification/analysis_pipeline.py
    title: "The golden notebook whose chain (load, QC, weighted mean, anomaly, trend, interval) this executor states as numbers"
  - id: pymannkendall
    resource: https://github.com/mmhs013/pymannkendall
    title: "pymannkendall: hamed_rao_modification_test, the trend test and Sen's slope the executor and the attester both call"
  - id: mk-nan
    resource: ../gotchas/hamed-rao-mk-nan.md
    title: "The Hamed-Rao NaN gotcha the plausibility check would surface as a failed interval"
---

# Global-mean temperature trend of the synthetic fixture (attested)

The one computation the foundation capability attests, so that a
runtime's result can be verified by something other than a runtime.
The executor regenerates the synthetic fixture (public domain, seed
20260704), applies the chain the golden notebook asserts, and writes a
receipt; the attester, on any machine and with no language model in
the path, regenerates the fixture again, checks the receipt's series is
the one that fixture yields, recomputes the trend, the p value and the
bootstrap interval from the series, and checks the weighting detector
was tripped.[^make-fixtures][^golden][^pymannkendall]

**What the receipt names.** Beyond the sanctioned code's digest and
the data digests, every receipt carries `capability` (the package's
name, version and release-lock digest, read from the package the
executor ships in) and `runtime` (the name and version the caller
declares). The attester refuses a receipt whose capability is not the
package beside it, so a result from another release, or from a copy of
the script outside its package, is not this release's evidence. That
is what lets a result produced on Claude Code, Claude Cowork or Codex
be verified under one attester and shown to belong to one governed
release.

**The chain.** Area-weighted global mean (cos latitude), anomalies
against the 1991-2020 monthly climatology, Sen's slope per decade under
the Hamed-Rao modified Mann-Kendall test, and a 95 percent interval
from a moving-block bootstrap on the OLS slope (block length 12 months,
500 resamples, seed 20260704). The Hamed-Rao test can return NaN on
some series; the attester's plausibility check would then fail the
interval rather than pass a blank.[^mk-nan]

**Mutation evidence.** The unweighted mean must read more than 5 K
colder than the weighted one (the fixture's poles are cold and
over-represented on a regular grid); a run in which the detector is not
tripped aborts receiptless, and the attester checks the bias in the
receipt against the receipt's own means.

**Reference run.** On the fixture the trend is about 0.20 K/decade with
a half width near 0.02 K/decade; the attester holds any run to the
fixture's imposed band (0.15 to 0.25) and to an interval that contains
the estimate with a half width between 0 and 0.05.

**Where the code is.** The executor and the attester are the scripts of
the skill that runs them, `skills/basic-statistics/scripts/`, and this
concept names them from here (a computation is a skill, ADR E in the
marketplace repository). The generator the attester regenerates the
fixture from stays under `verification/fixtures/`, where the golden
that proves the chain reaches it too, and no fixture is committed.

**Status.** Draft until a steward signs it; the executor and attester
run in the capability's gate and in the qualification harness today.
The code moved out of `verification/` into the skill on 2026-09-20 and
the paths above followed it; nothing about the computation changed but
the paths it resolves. The reference run reproduced at the new path on
claude-code under core 0.5.0: Sen's slope 0.198695697 K/decade, the 95
percent interval 0.1968368596519823 to 0.20047346345435277, Hamed-Rao
p 0.0, receipt run sha256:ab6dc5b7706c0dd2, attested PASS on all nine
checks. The receipt's `computation` and `code_sha256` name the new path
and the moved file, so the run identifier changed with them, as the
contract requires; no value did.
