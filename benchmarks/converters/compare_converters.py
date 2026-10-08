#!/usr/bin/env python3
"""Answer the validator's content questions from one converter's graph.

Runs INSIDE the pinned VCF-RDFizer image (ecrum19/vcf-rdfizer:3.3.1) and
imports that image's validator, so every graph -- VCF-RDFizer's own and each
other converter's -- is held to the same oracle (cyvcf2 + bcftools over the
source VCF), the same QLever build, the same result normalisation, and the
same comparator. Only the SPARQL text differs: each converter's questions are
ported to its vocabulary and live in queries/<tool>/.

The questions in scope are the validator's content questions, Q01-Q08. The
other five are not comparable across vocabularies by construction: Q09 and
Q10 census the VCF Core predicates and classes, and Q11-Q13 hash VCF-RDFizer's
own record IRIs into their digests.

A question a converter's graph cannot answer has no query file. Its reason is
recorded in queries/<tool>/not_represented.json and reported as
NOT_REPRESENTED. Every question in scope must have one or the other; a gap in
both is an error, so a missing port cannot pass for a missing capability.

A query may contain {{NAME}} placeholders for facts that are not in the graph but in the
conversion's own configuration -- TogoVar, for one, replaces CHROM with the reference IRI its
config assigns, so its Q01 maps the IRI back through that config. Each is filled from a file
given as --bind NAME=FILE, and the rendered query that actually ran is kept in queries/ next to
the results.

Usage (inside the image; see 18_converter_comparison.sh):
  python3 compare_converters.py --tool jvarkit --vcf in.vcf.gz \
      --graph graph.nt.gz --queries queries/jvarkit --out results/
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

VALIDATOR_DIR = Path("/opt/vcf-rdfizer/validation")
sys.path.insert(0, str(VALIDATOR_DIR))
import validation_runner as vr  # noqa: E402  (the image's validator, unchanged)

CONTENT_QUESTIONS = (
    "q01_record_density_1mb",
    "q02_variant_shape_counts",
    "q03_titv",
    "q04_filter_distribution",
    "q05_sample_genotype_counts",
    "q06_ac_an_distribution",
    "q07_file_metadata",
    "q08_header_line_census",
)
#: How many differing rows of each kind to keep in comparison.json. The full
#: answer is always in raw/<question>.sparql.json.
EXAMPLE_ROWS = 5


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def materialize(graph: Path, scratch: Path) -> tuple[Path, int]:
    """Return an uncompressed N-Triples copy for QLever, and its triple count."""
    target = scratch / "graph.nt"
    opener = gzip.open if graph.name.endswith(".gz") else open
    triples = 0
    with opener(graph, "rb") as source, target.open("wb") as sink:
        for line in source:
            sink.write(line)
            stripped = line.strip()
            if stripped and not stripped.startswith(b"#"):
                triples += 1
    return target, triples


def summarize(comparison: dict[str, Any]) -> dict[str, Any]:
    """Counts plus a few example rows; single-row questions keep both values."""
    if "expected" in comparison:
        return {"expected": comparison["expected"], "actual": comparison["actual"]}
    return {
        "missingRows": len(comparison["missingRows"]),
        "extraRows": len(comparison["extraRows"]),
        "differingRows": len(comparison["differingRows"]),
        "examples": {
            kind: comparison[kind][:EXAMPLE_ROWS]
            for kind in ("missingRows", "extraRows", "differingRows")
            if comparison[kind]
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tool", required=True)
    parser.add_argument("--vcf", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True, help="N-Triples (.nt or .nt.gz)")
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, default=Path("/work/scratch"))
    parser.add_argument("--qlever-memory-gb", type=int, default=8)
    parser.add_argument("--filter-oracle", default="auto", choices=("auto", "bcftools", "cyvcf2"))
    parser.add_argument("--bind", action="append", default=[], metavar="NAME=FILE",
                        help="fill {{NAME}} in the queries with the contents of FILE")
    args = parser.parse_args()
    bindings = {}
    for item in args.bind:
        name, _, path = item.partition("=")
        bindings[name] = Path(path).read_text(encoding="utf-8").strip()

    not_represented_path = args.queries / "not_represented.json"
    not_represented = (
        json.loads(not_represented_path.read_text(encoding="utf-8"))
        if not_represented_path.is_file() else {}
    )
    plan: dict[str, Path | None] = {}
    for question in CONTENT_QUESTIONS:
        query = args.queries / f"{question}.rq"
        has_query, has_reason = query.is_file(), question in not_represented
        if has_query == has_reason:
            raise SystemExit(
                f"{args.tool}: {question} needs exactly one of {query.name} or a "
                f"not_represented.json entry (has query: {has_query}, has reason: {has_reason})"
            )
        plan[question] = query if has_query else None

    args.out.mkdir(parents=True, exist_ok=True)
    raw_dir = args.out / "raw"
    raw_dir.mkdir(exist_ok=True)
    rendered_dir = args.out / "queries"
    rendered_dir.mkdir(exist_ok=True)
    args.scratch.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    oracle = vr.parse_vcf(args.vcf, filter_oracle=args.filter_oracle)
    oracle_seconds = time.monotonic() - started

    graph_nt, triples = materialize(args.graph, args.scratch)
    engine = vr.build_engine(
        "qlever", graph_nt, raw_dir=raw_dir, scratch=args.scratch,
        options={"memory_gb": args.qlever_memory_gb},
    )
    questions: dict[str, dict[str, Any]] = {}
    with engine:
        for question, query in plan.items():
            if query is None:
                questions[question] = {
                    "status": "NOT_REPRESENTED",
                    "reason": not_represented[question],
                }
                continue
            record: dict[str, Any] = {"query": query.name, "querySha256": sha256_file(query)}
            text = query.read_text(encoding="utf-8")
            for name, value in bindings.items():
                text = text.replace("{{" + name + "}}", value)
            unbound = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", text)))
            if unbound:
                raise SystemExit(f"{query.name}: no --bind for {', '.join(unbound)}")
            rendered = rendered_dir / query.name
            rendered.write_text(text, encoding="utf-8")
            record["renderedSha256"] = sha256_file(rendered)
            execution = engine.execute(question, rendered)
            record["wallSeconds"] = execution["wallSeconds"]
            if execution["status"] != "PASS":
                record.update(status="EXECUTION_FAILED", error=execution.get("error"))
                questions[question] = record
                continue
            try:
                actual = vr.normalize(question, Path(execution["rawResult"]))
                comparison = vr.compare_rows(question, oracle[question], actual)
            except (ValueError, KeyError) as error:
                record.update(status="RESULT_UNREADABLE", error=str(error))
                questions[question] = record
                continue
            record["status"] = comparison["status"]
            record.update(summarize(comparison))
            questions[question] = record
        engine_description = engine.describe()

    report = {
        "tool": args.tool,
        "vcf": {"path": str(args.vcf), "sha256": sha256_file(args.vcf),
                "records": oracle["totalRecords"], "samples": oracle["sampleCount"]},
        "graph": {"path": str(args.graph), "sha256": sha256_file(args.graph),
                  "triples": triples,
                  "triplesPerRecord": triples / oracle["totalRecords"] if oracle["totalRecords"] else None},
        "oracleSeconds": oracle_seconds,
        "engine": engine_description,
        "questions": questions,
    }
    (args.out / "comparison.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    with (args.out / "comparison.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tool", "question", "status", "wall_seconds",
                         "missing_rows", "extra_rows", "differing_rows"])
        for question, record in questions.items():
            writer.writerow([args.tool, question, record["status"], record.get("wallSeconds", ""),
                             record.get("missingRows", ""), record.get("extraRows", ""),
                             record.get("differingRows", "")])
    shutil.rmtree(args.scratch, ignore_errors=True)
    for question, record in questions.items():
        print(f"{args.tool:<12} {question:<28} {record['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
