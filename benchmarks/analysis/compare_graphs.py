#!/usr/bin/env python3
"""Compare two RDF graphs by canonical content, not by bytes.

Used by the round-trip, determinism and index-idempotence checks in plan §4.3.

Why canonical rather than byte comparison: N-Triples has no canonical
serialization order, and the pipeline does not promise one. Two runs of the same
conversion can emit the same triples in a different order, and the two storage
modes deliberately produce different gzip framing (space-optimized assembles a
concatenated stream; plain gzips one merged file). Comparing raw checksums would
report all of that as a difference, which is exactly the false alarm §1 warns
about.

So for N-Triples the digest is over the SORTED SET of triple lines, and the
triple count is reported beside it. For any other file (a .hdt, say) there is
nothing to canonicalize, so the digest is over the bytes and that is stated in
the output.

Usage:
    python3 compare_graphs.py a.nt b.nt --label roundtrip --out verdict.json
    python3 compare_graphs.py --digest-only path.hdt
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import pathlib
import sys

NT_SUFFIXES = (".nt", ".nt.gz")


def open_text(path: pathlib.Path) -> io.TextIOBase:
    if path.name.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def is_ntriples(path: pathlib.Path) -> bool:
    return any(path.name.endswith(suffix) for suffix in NT_SUFFIXES)


def canonical_digest(path: pathlib.Path) -> dict:
    """Digest over the sorted set of triple lines, plus counts.

    Both the multiset (total lines) and the set (distinct lines) are reported:
    a conversion that duplicates a triple is a real difference that a set-only
    digest would hide.
    """
    if not is_ntriples(path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "path": str(path),
            "kind": "opaque",
            "digest": digest,
            "note": "not N-Triples; digest is over raw bytes, so serialization "
                    "differences cannot be distinguished from content differences",
        }

    total = 0
    seen: set[str] = set()
    hasher = hashlib.sha256()
    with open_text(path) as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            total += 1
            seen.add(line)
    for line in sorted(seen):
        hasher.update(line.encode("utf-8"))
        hasher.update(b"\n")

    return {
        "path": str(path),
        "kind": "ntriples",
        "digest": hasher.hexdigest(),
        "triples_total": total,
        "triples_distinct": len(seen),
        "duplicate_lines": total - len(seen),
    }


def compare(a: pathlib.Path, b: pathlib.Path, label: str) -> dict:
    left, right = canonical_digest(a), canonical_digest(b)
    identical = left["digest"] == right["digest"]

    verdict = {
        "label": label,
        "identical": identical,
        "left": left,
        "right": right,
    }
    if left["kind"] == right["kind"] == "ntriples":
        verdict["triples_match"] = left["triples_distinct"] == right["triples_distinct"]
        verdict["triple_delta"] = right["triples_distinct"] - left["triples_distinct"]
        if not identical and verdict["triples_match"]:
            verdict["diagnosis"] = (
                "same triple COUNT but different content — a substitution, not a "
                "loss. Diff the sorted files to find it."
            )
        elif not identical:
            verdict["diagnosis"] = (
                f"triple count differs by {verdict['triple_delta']:+d}; "
                "content was lost or added"
            )
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", type=pathlib.Path)
    parser.add_argument("--label", default="comparison")
    parser.add_argument("--out", default=None, type=pathlib.Path)
    parser.add_argument("--digest-only", action="store_true",
                        help="print one file's canonical digest and exit")
    args = parser.parse_args()

    for path in args.paths:
        if not path.is_file():
            raise SystemExit(f"not a file: {path}")

    if args.digest_only:
        print(canonical_digest(args.paths[0])["digest"])
        return 0

    if len(args.paths) != 2:
        raise SystemExit("give exactly two files to compare, or use --digest-only")

    verdict = compare(args.paths[0], args.paths[1], args.label)

    status = "IDENTICAL" if verdict["identical"] else "DIFFERENT"
    print(f"  {args.label}: {status}")
    for side in ("left", "right"):
        entry = verdict[side]
        if entry["kind"] == "ntriples":
            print(f"    {side:<5} {entry['triples_distinct']:,} distinct "
                  f"({entry['triples_total']:,} lines) {pathlib.Path(entry['path']).name}")
        else:
            print(f"    {side:<5} opaque {entry['digest'][:16]}… "
                  f"{pathlib.Path(entry['path']).name}")
    if verdict.get("diagnosis"):
        print(f"    {verdict['diagnosis']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(verdict, indent=2) + "\n")
        print(f"    wrote {args.out}")

    # Non-zero on a mismatch so a driver script can notice.
    return 0 if verdict["identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
