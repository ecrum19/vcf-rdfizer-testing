#!/usr/bin/env python3
"""Describe VCF inputs structurally, for the plan §3.2 breadth table.

The ten corpus files are not a scaling curve — HGSVC2 is structural variants,
1000G is a phased SNV cohort, HG004/5 are single-sample benchmarks, the five
provider files are consumer WGS. What makes the breadth table honest is putting
each file's STRUCTURAL DESCRIPTORS next to its cost in the same row: a reader
who sees "sequence-resolved SV, 32 samples" beside an off-trend cost reads it
as explained rather than as noise.

Everything here is computed by streaming the file once, with no bcftools and no
index. On a 400 MB gzip that is a few minutes; results are cached in
``descriptors.json`` beside the output and reused unless --refresh is given.

Usage:
    python3 describe_inputs.py --corpus
    python3 describe_inputs.py path/to/one.vcf.gz [more ...]
    python3 describe_inputs.py --corpus --limit-records 200000   # fast sample
"""

from __future__ import annotations

import argparse
import collections
import gzip
import io
import json
import pathlib
import re
import sys
import time

CORPUS = [
    ("sv_batch", "HGSVC2.vcf.gz"),
    ("cohort", "1000G_phase3_chr20.vcf.gz"),
    ("giab_single", "HG004_GRCh38.vcf.gz"),
    ("giab_single", "HG005_GRCh38.vcf.gz"),
    ("giab_single", "0GOOR_HG002.vcf.gz"),
    ("consumer_wgs", "NG1N86S6FC.vcf.gz"),
    ("consumer_wgs", "NG131FQA1I.vcf.gz"),
    ("consumer_wgs", "NB72462M.vcf.gz"),
    ("consumer_wgs", "60820188475559.vcf.gz"),
    ("consumer_wgs", "60820188474283.vcf.gz"),
]

SYMBOLIC = re.compile(r"^<[^>]+>$")
BREAKEND = re.compile(r"[\[\]]")
BASES = set("ACGTNacgtn")


def open_text(path: pathlib.Path) -> io.TextIOBase:
    if path.name.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def allele_shape(ref: str, alt: str) -> str:
    """Classify one ALT allele against its REF. Record-level, not normalized."""
    if alt in (".", ""):
        return "no_alt"
    if SYMBOLIC.match(alt):
        return "symbolic"
    if BREAKEND.search(alt):
        return "breakend"
    if not set(ref) <= BASES or not set(alt) <= BASES:
        return "other"
    if len(ref) == 1 and len(alt) == 1:
        return "snv"
    if len(ref) == len(alt):
        return "mnv"
    if len(ref) > len(alt):
        return "deletion"
    return "insertion"


def describe(path: pathlib.Path, limit_records: int | None = None) -> dict:
    meta_keys: collections.Counter = collections.Counter()
    info_keys_declared: set[str] = set()
    format_keys_declared: set[str] = set()
    info_keys_seen: set[str] = set()
    format_keys_seen: set[str] = set()
    shapes: collections.Counter = collections.Counter()
    filters: collections.Counter = collections.Counter()
    contigs: set[str] = set()
    samples: list[str] = []
    records = 0
    multiallelic = 0
    fileformat = None
    reference = None
    truncated = False

    with open_text(path) as handle:
        for line in handle:
            if line.startswith("##"):
                body = line[2:].rstrip("\r\n")
                key = body.split("=", 1)[0]
                meta_keys[key] += 1
                if key == "fileformat":
                    fileformat = body.split("=", 1)[1] if "=" in body else None
                elif key == "reference":
                    reference = body.split("=", 1)[1] if "=" in body else None
                elif key == "INFO":
                    match = re.search(r"ID=([^,>]+)", body)
                    if match:
                        info_keys_declared.add(match.group(1))
                elif key == "FORMAT":
                    match = re.search(r"ID=([^,>]+)", body)
                    if match:
                        format_keys_declared.add(match.group(1))
                continue
            if line.startswith("#CHROM"):
                fields = line.rstrip("\r\n").split("\t")
                samples = fields[9:] if len(fields) > 9 else []
                continue
            if not line.strip():
                continue

            fields = line.rstrip("\r\n").split("\t")
            if len(fields) < 8:
                continue
            records += 1
            contigs.add(fields[0])
            ref, alt, filt, info = fields[3], fields[4], fields[6], fields[7]

            alts = alt.split(",")
            if len(alts) > 1:
                multiallelic += 1
            for one in alts:
                shapes[allele_shape(ref, one)] += 1

            filters[filt] += 1
            if info not in (".", ""):
                for entry in info.split(";"):
                    info_keys_seen.add(entry.split("=", 1)[0])
            if len(fields) > 8 and fields[8] not in (".", ""):
                for key in fields[8].split(":"):
                    format_keys_seen.add(key)

            if limit_records is not None and records >= limit_records:
                truncated = True
                break

    return {
        "file": path.name,
        "bytes_on_disk": path.stat().st_size,
        "fileformat": fileformat,
        "reference": reference,
        "records_counted": records,
        "records_truncated_at_limit": truncated,
        "contigs": len(contigs),
        "samples": len(samples),
        "sample_calls": records * len(samples),
        "multiallelic_records": multiallelic,
        "allele_shapes": dict(shapes.most_common()),
        "dominant_allele_shape": shapes.most_common(1)[0][0] if shapes else None,
        "filter_values_distinct": len(filters),
        "filter_top": dict(filters.most_common(5)),
        "info_keys_declared": len(info_keys_declared),
        "info_keys_used": len(info_keys_seen),
        "format_keys_declared": len(format_keys_declared),
        "format_keys_used": len(format_keys_seen),
        "info_keys_used_undeclared": sorted(info_keys_seen - info_keys_declared)[:10],
        "format_keys_used_undeclared": sorted(format_keys_seen - format_keys_declared)[:10],
        "meta_line_keys": dict(meta_keys.most_common()),
        "described_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", type=pathlib.Path)
    parser.add_argument("--corpus", action="store_true", help="describe the ten corpus files")
    parser.add_argument("--vcf-data", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--limit-records", type=int, default=None,
                        help="stop after N records per file (a fast, clearly-labelled sample)")
    parser.add_argument("--refresh", action="store_true", help="ignore the cache")
    args = parser.parse_args()

    root = pathlib.Path(__file__).resolve().parent.parent
    vcf_data = pathlib.Path(args.vcf_data) if args.vcf_data else root.parent / "vcf_data"
    out_path = pathlib.Path(args.out) if args.out else root / "results" / "descriptors.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cache = {}
    if out_path.is_file() and not args.refresh:
        try:
            cache = {e["file"]: e for e in json.loads(out_path.read_text())}
        except (json.JSONDecodeError, KeyError, TypeError):
            cache = {}

    targets: list[tuple[str | None, pathlib.Path]] = []
    if args.corpus:
        for family, name in CORPUS:
            path = vcf_data / name
            if path.is_file():
                targets.append((family, path))
            else:
                print(f"  not present, skipped: {name}", file=sys.stderr)
    for path in args.paths:
        if not path.is_file():
            raise SystemExit(f"not a file: {path}")
        targets.append((None, path))

    if not targets:
        raise SystemExit(
            "nothing to describe.\n"
            f"Corpus files were expected in {vcf_data}; download them with\n"
            "  bash scripts/download_test_data.sh"
        )

    entries = []
    for family, path in targets:
        if path.name in cache and not args.refresh:
            print(f"  cached: {path.name}")
            entry = cache[path.name]
        else:
            print(f"  reading: {path.name}")
            entry = describe(path, args.limit_records)
        if family:
            entry["family"] = family
        entries.append(entry)

    out_path.write_text(json.dumps(entries, indent=2) + "\n")
    print(f"\nwrote {out_path}")

    header = f"{'file':<32} {'family':<14} {'records':>12} {'samples':>8} {'shape':<12} {'ver':<10}"
    print("\n" + header)
    print("-" * len(header))
    for entry in entries:
        print(f"{entry['file']:<32} {entry.get('family', '-'):<14} "
              f"{entry['records_counted']:>12,} {entry['samples']:>8,} "
              f"{str(entry.get('dominant_allele_shape')):<12} "
              f"{str(entry.get('fileformat')):<10}"
              + ("  (sampled)" if entry.get("records_truncated_at_limit") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
