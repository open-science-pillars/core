# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6,<7"]
# ///
"""obs_cite: emit the citation an observation source requires, with
the access date taken from a capture record, never invented.

Reads the citation block of a source's connector concept (the dated,
steward-reviewed statement of what the authority requires) plus,
optionally, a capture record from the obs-capture store, and prints
the citation with the access date filled from retrieved_at. A source
whose concept carries no citation block is REFUSED, so the gap can
never again go silent: the fix is to add verified citation facts to
the concept, not to guess.

Usage:
  obs_cite.py --source psmsl [--capture-id ID] [--store DIR]
  obs_cite.py --concept PATH [--access-date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

CONCEPTS = {
    "coops": "ocean-science/knowledge/connectors/coops-tides.md",
    "argo": "ocean-science/knowledge/connectors/argo-floats.md",
    "psmsl": "ocean-science/knowledge/connectors/psmsl-gauges.md",
    "usgs": "hydrology/knowledge/connectors/usgs-water.md",
    "hydrocron": "hydrology/knowledge/connectors/hydrocron-swot.md",
}


def find_concept(source: str) -> Path:
    rel = CONCEPTS[source]
    here = Path(__file__).resolve()
    candidates = [here.parents[2] / rel]           # sibling checkouts
    cache = Path.home() / ".claude/plugins/cache/open-science-pillars"
    repo, _, inner = rel.partition("/")
    if cache.exists():
        candidates += sorted(cache.glob(f"{repo}/*/{inner}"), reverse=True)
    for c in candidates:
        if c.exists():
            return c
    raise SystemExit(f"connector concept for {source!r} not found "
                     f"(looked for {rel} beside this checkout and in "
                     "the plugin cache)")


def frontmatter(path: Path) -> dict:
    t = path.read_text()
    if not t.startswith("---"):
        raise SystemExit(f"{path} has no frontmatter")
    return yaml.safe_load(t.split("---", 2)[1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=sorted(CONCEPTS))
    ap.add_argument("--concept", type=Path)
    ap.add_argument("--capture-id")
    ap.add_argument("--store", type=Path,
                    default=Path.home() / "obs-captures")
    ap.add_argument("--access-date")
    ap.add_argument("--station", default="<station>")
    a = ap.parse_args()
    path = a.concept or find_concept(a.source)
    fm = frontmatter(path)
    cit = fm.get("citation")
    if not cit:
        print(f"REFUSED: cannot cite from {path.name}: its connector "
              "concept carries no citation block; add verified citation "
              "facts to the concept rather than guessing", file=sys.stderr)
        return 2

    access, capture_line = a.access_date, None
    if a.capture_id:
        mf = a.store / "manifest.jsonl"
        recs = [json.loads(x) for x in mf.read_text().splitlines()
                if x.strip()] if mf.exists() else []
        match = [r for r in recs if r["capture_id"] == a.capture_id]
        if not match:
            raise SystemExit(f"no capture record {a.capture_id} in {mf}")
        r = match[-1]
        access = r["retrieved_at"][:10]
        capture_line = (f"Data as captured: id {r['capture_id']}, "
                        f"content sha256 {r['content_sha256']}")
    if cit.get("access_date_required") and not access:
        print(f"REFUSED: {path.name} declares the access date mandatory; "
              "pass --capture-id (preferred: the date then comes from the "
              "frozen record) or --access-date", file=sys.stderr)
        return 2

    text = cit["data"].replace("{access_date}", access or "<access date>")
    text = text.replace("{station}", a.station)
    print(text)
    if cit.get("doi"):
        print(f"DOI: https://doi.org/{cit['doi']}")
    if cit.get("paper"):
        print(f"Cite alongside: {cit['paper']}")
    if cit.get("software"):
        print(f"Software: {cit['software']}")
    if cit.get("program"):
        print(f"Acknowledgment: {cit['program']}")
    if capture_line:
        print(capture_line)
    if cit.get("note"):
        print(f"Note: {cit['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
