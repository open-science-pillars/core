---
okf_version: "0.2"
---

# core knowledge bundle

Cross-cutting conventions for earth science analysis; the concepts every
OSP plugin builds on. OKF v0.2 conformant (okf_version "0.2" above;
the exact spec text is vendored in marketplace docs/upstream): every
verified concept carries its steward's verified event with the original
review date, status stable.

## conventions

- [CF conventions for analysis outputs](conventions/cf-conventions.md), type: convention, status: stable, verified
- [Calendar handling, and the DJF year-boundary trap](conventions/calendars.md), type: convention, status: stable, verified
- [Unmasked fill values: the sentinel list and detection recipe](conventions/common-fill-values.md), type: dataset-gotcha, severity high, cross-cutting, status: stable, verified (standing 🟡: eval case pending)
- [Smell-test anchors: order-of-magnitude sanity ranges](conventions/smell-test-ranges.md), type: convention, status: stable, verified
- [Observation capture: freezing live data into citable records](conventions/observation-capture.md), type: convention, status: draft
- [Physical-bounds screening table](conventions/physical-bounds-screening.md), type: convention, status: stable, verified
- [Satellite QA flag decoding (MODIS, Landsat, Sentinel-2)](conventions/satellite-qa-flag-decoding.md), type: convention, status: stable, verified
- [Dataset citation and DOI conventions](conventions/dataset-citations.md), type: convention, status: stable, verified
- [Hamed-Rao modified Mann-Kendall can return NaN](gotchas/hamed-rao-mk-nan.md), type: dataset-gotcha, severity medium, status: stable, verified
