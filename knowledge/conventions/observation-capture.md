---
type: convention
title: "Observation capture: freezing live data into citable records"
description: "Live observation APIs revise, replace, and reprocess; a receipt cannot hash a moving target. A capture freezes one query with two hashes (raw evidence, canonical identity), the retrieval time as part of the record, and the rule that revision means a new capture, never an overwrite."
tags: [observations, capture, provenance, reproducibility, receipts]
generated: { by: knowledge-seeder/claude, at: 2026-09-01T00:00:00Z }
status: draft
---

# Observation capture: freezing live data into citable records

Observation sources of record are live and mutable by design:
agencies revise provisional values, replace real-time profiles with
delayed-mode science versions, reissue annual releases, and reprocess
series under new algorithm versions. That is a feature of the
sources. It is fatal to a receipt, which must hash exactly what a
computation consumed, and it breaks a methods section, which must say
exactly what was fetched and when. The capture is the bridge.

## The contract

A capture freezes ONE deterministic query: the source, the full
request URL and parameters, and a fixed time window ("latest" is
refused, because an unreproducible query cannot be a citable record).
The store holds two payloads per capture, and the manifest records a
hash of each:

- **raw_sha256** covers the body exactly as received: the evidence.
- **content_sha256** covers a canonical extraction (parsed rows,
  deterministic ordering and serialization) with the volatile
  envelope stripped: the identity. Live envelopes carry per-request
  fields such as query timestamps, so raw bytes differ while the
  data stands still; measured on the first live demonstration, two
  captures of the same closed window agreed in content and differed
  in raw, which is the two-hash argument in one line.

The retrieval timestamp is part of the record, not decoration: for a
mutable source, "the data as retrieved on this date" is the only
honest citation, and the access date a methods section needs comes
from here. A revision at the source is a NEW capture beside the old
one, never an overwrite; a content hash that changes between captures
of the same window is information about the source, not an error in
the store. VERIFY re-hashes stored payloads against the manifest and
fails loudly on any mismatch.

## What cites what

A receipt cites the capture id and content_sha256; an attested
computation consumes the frozen canonical payload from the store,
never the live wire, which keeps the standing rule intact that
nothing attested calls a connector. Captures live outside the
repositories. The capture tool itself records its own version and
hash in every manifest record, so the chain from claim to evidence
has no anonymous link.
