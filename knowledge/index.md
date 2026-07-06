# core knowledge bundle

Cross-cutting conventions for earth science analysis; the concepts every
OSP plugin builds on. OKF v0.1 conformant per SPEC §5.

- Snapshot source repository: (none; this is an original bundle)
- Snapshot source commit: (n/a)
- Snapshot date: (n/a)

## conventions

- [CF conventions for analysis outputs](conventions/cf-conventions.md), type: convention, status: verified
- [Calendar handling, and the DJF year-boundary trap](conventions/calendars.md), type: convention, status: verified
- [Unmasked fill values: the sentinel list and detection recipe](conventions/common-fill-values.md), type: dataset-gotcha, severity high, cross-cutting, status: verified (standing 🟡: eval case pending)
- [Smell-test anchors: order-of-magnitude sanity ranges](conventions/smell-test-ranges.md), type: convention, status: draft
- [Physical-bounds screening table](conventions/physical-bounds-screening.md), type: convention, status: draft
- [Satellite QA flag decoding (MODIS, Landsat, Sentinel-2)](conventions/satellite-qa-flag-decoding.md), type: convention, status: draft
- [Dataset citation and DOI conventions](conventions/dataset-citations.md), type: convention, status: draft
- [Hamed-Rao modified Mann-Kendall can return NaN](gotchas/hamed-rao-mk-nan.md), type: dataset-gotcha, severity medium, status: draft
