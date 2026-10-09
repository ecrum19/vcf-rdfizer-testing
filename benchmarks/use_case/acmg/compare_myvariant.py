#!/usr/bin/env python3
"""Compare the unchecked rsID links (tier 1) with the service-confirmed ones (tier 3).

    compare_myvariant.py <results-dir> <participant>...

rsid-dbsnp, in <results-dir>/link__<participant>, rewrites every rsID of the ID
column into a dbSNP IRI without checking it. rsid-myvariant, in
<results-dir>/link_myvariant__<participant>, links only the rsIDs that a
MyVariant.info dbSNP record carries. Writes <results-dir>/tier1_vs_tier3_myvariant.json:
per participant, both link counts, whether tier 3 is a subset of tier 1, the
tier-1 links and distinct rsIDs that tier 3 did not confirm, and the first five
of those rsIDs as examples. Exits 1 if tier 3 holds a link tier 1 does not: the
service may confirm fewer identifiers than the file declares, never others.
"""

from __future__ import annotations

import gzip
import json
import pathlib
import re
import sys

# Both linkers emit <call> vcfl:sameVariantAs <https://identifiers.org/dbsnp:rs...>.
# The cell's spdi and gene links share the file, with other objects or predicates.
RSID_LINK = re.compile(r"^(<[^>]+>) <https://w3id\.org/vcf-rdfizer/linking#sameVariantAs> "
                       r"<https://identifiers\.org/dbsnp:([^>]+)> \.$")


def rsid_links(cell: pathlib.Path) -> set[tuple[str, str]]:
    """(call IRI, rsID) for every rsID link in the cell's link set, plain or gzipped."""
    paths = sorted(cell.glob("out/*.links.nt")) + sorted(cell.glob("out/*.links.nt.gz"))
    if len(paths) != 1:
        raise SystemExit(f"expected one link set in {cell}/out, found {len(paths)}")
    opener = gzip.open if paths[0].suffix == ".gz" else open
    with opener(paths[0], "rt", encoding="utf-8") as handle:
        return {m.groups() for line in handle for m in [RSID_LINK.match(line.rstrip("\n"))] if m}


def main(argv: list[str]) -> int:
    results, participants = pathlib.Path(argv[0]), argv[1:]
    report, ok = {}, True
    for participant in participants:
        tier1 = rsid_links(results / f"link__{participant}")
        tier3 = rsid_links(results / f"link_myvariant__{participant}")
        unconfirmed = tier1 - tier3
        report[participant] = {
            "tier1_links": len(tier1),
            "tier3_links": len(tier3),
            "tier3_subset_of_tier1": tier3 <= tier1,
            "unconfirmed_links": len(unconfirmed),
            "unconfirmed_rsids": len({rsid for _, rsid in unconfirmed}),
            "examples": sorted({rsid for _, rsid in unconfirmed})[:5],
        }
        ok &= tier3 <= tier1
        print(f"{participant}: tier 3 confirmed {len(tier3):,} of {len(tier1):,} tier-1 links")
    (results / "tier1_vs_tier3_myvariant.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
