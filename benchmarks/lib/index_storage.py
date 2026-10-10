#!/usr/bin/env python3
"""Measure what each route keeps on disk to answer queries: one input.

Runs inside a VCF-RDFizer image (it needs bgzip, tabix and QLever's index
builder; v3.3.1 has all three), called by 19_index_storage.sh. Standard library
only, so it runs on the image's own python3.

    index_storage.py --vcf IN.vcf.gz --nt IN.nt.gz --scratch DIR --out DIR

The VCF route: the VCF compressed with bgzip, which tabix requires, and its
tabix index. A VCF that is already BGZF is indexed as it is; a plain-gzip one
is recompressed with bgzip at its default level first.

The RDF route: the QLever index built from the tool's gzip-framed N-Triples,
with the arguments VCF-RDFizer's validator uses (`-F nt -m 4G`). The index
answers queries without the N-Triples or the VCF, so it is the whole of what
the route keeps. The N-Triples are streamed into the builder rather than
decompressed to disk first: for the complete HG005 VCF they would take about
100 GB, and where the input comes from does not change the index.

Writes OUT/index_storage.json, and keeps QLever's log as OUT/qlever-index.log
and /usr/bin/time's report as OUT/qlever-index.time.txt. Both indexes are
built under SCRATCH and deleted afterwards unless --keep is given.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

QLEVER_INDEX = os.environ.get("QLEVER_INDEX_BUILDER_BIN", "/opt/qlever/bin/qlever-index")
QLEVER_LIB = "/opt/qlever/lib"  # the binary's Boost, ICU and jemalloc, as the validator sets them


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_bgzf(path: Path) -> bool:
    """BGZF is gzip with a 'BC' extra subfield in the first member's header."""
    with path.open("rb") as handle:
        head = handle.read(18)
    return len(head) == 18 and head[:4] == b"\x1f\x8b\x08\x04" and head[12:14] == b"BC"


def run(argv: list[str], **kwargs) -> float:
    started = time.monotonic()
    subprocess.run(argv, check=True, **kwargs)
    return time.monotonic() - started


def first_line(argv: list[str]) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    return (result.stdout or result.stderr).splitlines()[0].strip()


def vcf_route(vcf: Path, scratch: Path) -> dict:
    work = scratch / "tabix"
    work.mkdir(parents=True)
    bgzf = is_bgzf(vcf)
    indexed = work / "input.vcf.gz"
    bgzip_seconds = 0.0
    if bgzf:
        indexed.symlink_to(vcf)
    else:
        with indexed.open("wb") as sink:
            started = time.monotonic()
            gunzip = subprocess.Popen(["gunzip", "-c", str(vcf)], stdout=subprocess.PIPE)
            subprocess.run(["bgzip", "-c"], stdin=gunzip.stdout, stdout=sink, check=True)
            gunzip.stdout.close()
            if gunzip.wait() != 0:
                raise SystemExit(f"gunzip failed on {vcf}")
            bgzip_seconds = time.monotonic() - started
    tabix_seconds = run(["tabix", "-p", "vcf", str(indexed)])
    tbi = Path(f"{indexed}.tbi")
    bgzip_bytes = indexed.resolve().stat().st_size
    return {
        "inputWasBgzf": bgzf,
        "bgzipBytes": bgzip_bytes,
        "bgzipSeconds": round(bgzip_seconds, 3),
        "tbiBytes": tbi.stat().st_size,
        "tabixSeconds": round(tabix_seconds, 3),
        "tabixVersion": first_line(["tabix", "--version"]),
        "storedBytes": bgzip_bytes + tbi.stat().st_size,
    }


def rdf_route(nt: Path, scratch: Path, out: Path, memory: str) -> dict:
    work = scratch / "qlever"
    work.mkdir(parents=True)
    base = work / "index"
    argv = [QLEVER_INDEX, "-i", str(base), "-f", "-", "-F", "nt", "-m", memory]
    environment = dict(os.environ)
    environment["LD_LIBRARY_PATH"] = ":".join(
        part for part in (QLEVER_LIB, environment.get("LD_LIBRARY_PATH", "")) if part)
    log, timing = out / "qlever-index.log", out / "qlever-index.time.txt"
    started = time.monotonic()
    with log.open("wb") as sink:
        gunzip = subprocess.Popen(["gunzip", "-c", str(nt)], stdout=subprocess.PIPE)
        subprocess.run(["/usr/bin/time", "-v", "-o", str(timing), *argv], stdin=gunzip.stdout,
                       stdout=sink, stderr=subprocess.STDOUT, env=environment, cwd=work, check=True)
        gunzip.stdout.close()
        if gunzip.wait() != 0:
            raise SystemExit(f"gunzip failed on {nt}")
    seconds = time.monotonic() - started
    text = log.read_text(errors="replace")
    if "Index build completed" not in text:
        raise SystemExit(f"QLever did not report a completed index; see {log}")
    files = {p.name: p.stat().st_size for p in sorted(work.iterdir()) if p.is_file()}
    parsed = re.findall(r"Triples parsed: ([\d,]+)", text)
    version = re.search(r"QLever index builder (\w+)", text)
    rss = re.search(r"Maximum resident set size \(kbytes\): (\d+)", timing.read_text())
    return {
        "qleverVersion": version.group(1) if version else None,
        "command": [*argv[:4], "<N-Triples on stdin>", *argv[5:]],
        "triplesParsed": int(parsed[-1].replace(",", "")) if parsed else None,
        "indexBytes": sum(files.values()),
        "indexFiles": files,
        "buildSeconds": round(seconds, 1),
        "peakRssKb": int(rss.group(1)) if rss else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vcf", type=Path, required=True)
    parser.add_argument("--nt", type=Path, required=True, help="the tool's gzip-framed N-Triples")
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--memory", default="4G", help="QLever's -m, as the validator passes it")
    parser.add_argument("--keep", action="store_true", help="keep both indexes under --scratch")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    scratch = args.scratch / f"index-storage-{args.dataset}"
    if scratch.exists():
        shutil.rmtree(scratch)
    try:
        vcf = {"name": args.vcf.name, "bytes": args.vcf.stat().st_size, "sha256": sha256(args.vcf)}
        nt = {"name": args.nt.name, "bytes": args.nt.stat().st_size, "sha256": sha256(args.nt)}
        tabix = vcf_route(args.vcf, scratch)
        qlever = rdf_route(args.nt, scratch, args.out, args.memory)
    finally:
        if not args.keep:
            shutil.rmtree(scratch, ignore_errors=True)
    record = {
        "dataset": args.dataset,
        "vcf": vcf,
        "ntriples": nt,
        "vcfRoute": tabix,
        "rdfRoute": qlever,
        "queryReady": {
            "vcfBytes": tabix["storedBytes"],
            "rdfBytes": qlever["indexBytes"],
            "ratio": round(qlever["indexBytes"] / tabix["storedBytes"], 1),
        },
    }
    (args.out / "index_storage.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record["queryReady"]))


if __name__ == "__main__":
    main()
