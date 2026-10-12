#!/usr/bin/env python3
"""Build the results site's data files from the benchmark archive.

    python3 scripts/build_site_data.py --out site/data

Standard library only, and no network: everything is read from
benchmark-results/ and benchmarks/use_case/acmg, which hold only the reported
runs: the v3.1.0 core benchmark, the additional v3.1.0 runs, and the v3.3.1 rerun.
Superseded attempts are on the repository's legacy branch; reported execution
failures remain alongside the successful runs. The
values behind the paper's figures come from the same module make_figures.py
uses (scripts/figure_data.py), so the site and the paper cannot
compute them differently.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import statistics as st
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import figure_data as fd  # noqa: E402
from turtle_text import statement_text, turtle_statements  # noqa: E402

RESULTS = fd.RESULTS
REVIEW = RESULTS / "vcf-bench-2" / "review-runs"
#: The rerun with the published v3.3.1 of every result a pre-release build first produced, per host.
#: The use-case arms, regional and large-graph retrieval, and the consumer WGS validation run are
#: read from here; the v3.1.0 core benchmark and the v3.1.0 mutation rerun are not rerun.
V331 = {host: RESULTS / host / "v331-rerun" / "results" for host in ("vcf-bench-1", "vcf-bench-2", "vcf-bench-3")}
ACMG = ROOT / "benchmarks" / "use_case" / "acmg"
REPO_URL = "https://github.com/ecrum19/vcf-rdfizer-testing"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path | str) -> str:
    return str(Path(path).resolve().relative_to(ROOT))


def live_report_dirs() -> list[Path]:
    """Every validation report in the core benchmark's live trees on both hosts."""
    dirs = []
    for host in ("vcf-bench-1", "vcf-bench-2"):
        pattern = RESULTS / host / "benchmarks_outputs" / "**" / "reports" / "validation" / "*" / "summary.json"
        dirs += [Path(p).parent for p in glob.glob(str(pattern), recursive=True)]
    return sorted(dirs)


# ---------------------------------------------------------------------------
# Core benchmark
# ---------------------------------------------------------------------------
def campaign() -> dict:
    summary = fd.summary()
    experiments = summary["experiments"]["live"]
    cells = [
        {
            "cell": c["cell"], "experiment": c["experiment"], "host": c["host"],
            "status": c["status"], "wallSeconds": c.get("wrapper_wall_seconds"),
            "toolCommit": (c.get("tool_commit") or "")[:7] or None,
            "imageDigest": c.get("image_digest"),
            "url": f"{REPO_URL}/tree/main/benchmark-results/{c['path']}",
        }
        for c in summary["cells"] if c["branch"] == "live"
    ]
    hosts = {}
    for host, by_commit in summary["provenance"].items():
        platform = by_commit.get("d3b34d5", {}).get("platform")
        if platform:
            hosts[host] = platform
    # Every host behind a reported result, each with the record its details come from:
    # the core benchmark's provenance capture or, for a host whose harness wrote none,
    # a platform record captured afterwards that says why it applies to the runs.
    host_records = [
        {"host": host, **platform, "recorded": "At the core benchmark",
         "record": f"{REPO_URL}/blob/main/{rel(RESULTS / host / 'benchmarks_outputs' / '00_environment' / f'provenance.{host}.d3b34d5.json')}"}
        for host, platform in sorted(hosts.items())
    ]
    for path in sorted(RESULTS.glob("*/00_environment/platform.json")):
        record = load(path)
        host_records.append({"host": record["host"], **record["platform"],
                             "recorded": f"After its runs ({record['captured_utc'][:10]}), unchanged since before them",
                             "record": f"{REPO_URL}/blob/main/{rel(path)}"})
    return {
        "image": next(ref for ref in summary["integrity"]["image_refs"] if ref != "?"),
        "harnessCommit": summary["harness_commit"],
        "experiments": [{"experiment": name, **row} for name, row in sorted(experiments.items())],
        "cells": cells,
        "hosts": hosts,
        "hostRecords": host_records,
        "totals": {
            "cells": len(cells),
            "hours": round(sum(row["wall_hours"] for row in experiments.values()), 2),
            "byStatus": dict(Counter(c["status"] for c in cells)),
        },
    }


# ---------------------------------------------------------------------------
# Fidelity
# ---------------------------------------------------------------------------
FIDELITY_GROUPS = {
    "A": "Core benchmark validation",
    "B": "Artifact decoding",
    "C": "Consumer WGS validation",
    "D": "Large-graph query agreement",
    "E": "Fault-injection sensitivity",
}


def large_graph_agreement() -> dict:
    """RQ1 D: compare saved normalized answers, not execution PASS alone.

    These retrieval runs are TIMING_ONLY: Q1--Q13 were compared with the VCF,
    but preflight and SHACL were omitted. Count a question once per input path
    only if it agrees in every recorded replicate; retain failures explicitly.
    """
    root = V331["vcf-bench-3"] / "16_scale_retrieval"
    groups = defaultdict(list)
    for cell in sorted(root.glob("*__qlever__*")):
        reports = list(cell.glob("out/run_metrics/*/reports/validation/*/summary.json"))
        if len(reports) != 1:
            raise ValueError(f"Expected one retrieval report in {cell}, got {len(reports)}")
        report = reports[0].parent
        summary = load(reports[0])
        parser, sparql = load(report / "parser.json"), load(report / "sparql.json")
        queries = {q: q in parser and q in sparql and parser[q] == sparql[q] for q in fd.QIDS}
        groups[(cell.name.split("__")[0], summary["sourceFormat"])].append({
            "source": rel(report), "records": summary["recordCount"],
            "status": summary["status"], "answersAgree": summary["answersAgree"],
            "queries": queries,
        })
    rows = []
    for (scale_id, artifact), runs in sorted(groups.items()):
        manifest = load(RESULTS / "vcf-bench-3" / "scale-store-manifests" / f"{scale_id}.manifest.json")
        questions = [{"query": q, "status": "PASS" if all(r["queries"][q] for r in runs) else "FAIL"}
                     for q in fd.QIDS]
        rows.append({"scale": scale_id, "artifact": artifact, "records": runs[0]["records"],
                     "triples": manifest["triples"], "replicates": len(runs), "queries": questions,
                     "passed": sum(q["status"] == "PASS" for q in questions),
                     "total": len(questions), "runs": runs})
    return {"rows": rows, "source": rel(root)}


def validation_counts() -> dict:
    """Pass/total for every layer of the core benchmark's validation evidence."""
    comparisons, invariants, rapper, engines = Counter(), Counter(), Counter(), Counter()
    shacl = []
    reports = live_report_dirs()
    for report in reports:
        summary = load(report / "summary.json")
        engines[len(summary.get("engineStatuses") or {})] += 1
        if (report / "comparison.json").exists():
            comparison = load(report / "comparison.json")
            for result in (comparison.get("queries") or {}).values():
                comparisons[result.get("status")] += 1
            for items in (comparison.get("invariants") or {}).values():
                for item in items:
                    invariants[item["status"]] += 1
        if (report / "rdf-validation.json").exists():
            rapper[load(report / "rdf-validation.json").get("status")] += 1
        if isinstance(summary.get("shacl"), dict) and "wallSeconds" in summary["shacl"]:
            triples = load(report / "rdf-validation.json").get("tripleCount")
            shacl.append({**summary["shacl"], "triples": triples})
    decode = Counter()
    for host in ("vcf-bench-1", "vcf-bench-2"):
        pattern = RESULTS / host / "benchmarks_outputs" / "**" / "stages" / "compression" / "*.json"
        for path in glob.glob(str(pattern), recursive=True):
            stage = load(Path(path))
            for key, label in (("hdt_conversion", "hdt"), ("cottas_conversion", "cottas")):
                check = (stage.get(key) or {}).get("validation")
                if check:
                    ok = check.get("valid") and check.get("count_match")
                    decode[(label, bool(ok))] += 1
    return {
        "validations": len(reports),
        "comparisons": dict(comparisons),
        "invariants": dict(invariants),
        "rapper": dict(rapper),
        "enginesAnswering": {str(k): v for k, v in sorted(engines.items())},
        "decode": {f"{label}:{'pass' if ok else 'fail'}": n for (label, ok), n in decode.items()},
        "shacl": {
            "validations": len(shacl),
            "violations": sum(s.get("violationCount") or 0 for s in shacl),
            "seconds": [min(s["wallSeconds"] for s in shacl), max(s["wallSeconds"] for s in shacl)]
            if shacl else None,
            "maxTriples": max((s["triples"] or 0 for s in shacl), default=None),
        },
        "maxValidatedTriples": max(
            (load(r / "rdf-validation.json").get("tripleCount") or 0)
            for r in reports if (r / "rdf-validation.json").exists()),
    }


def mutation_profiles() -> dict:
    """Detection of each mutation under queries only, the core and the full shapes."""
    robustness = RESULTS / "vcf-bench-1" / "benchmarks_outputs" / "08_robustness"
    runs = {
        "queries": robustness / "mutation_score" / "mutation-score.json",
        "core": REVIEW / "mutation__core" / "mutation-score.json",
        "full": robustness / "mutation_score__shacl_full" / "mutation-score.json",
    }
    scores, detected = {}, defaultdict(dict)
    for profile, path in runs.items():
        data = load(path)
        scores[profile] = {"detected": data["detected"], "total": data["total"], "source": rel(path)}
        for mutation in data["mutations"]:
            key = f"{mutation['id']}|{mutation['representation']}"
            detected[key][profile] = mutation["detected"]
            detected[key]["element"] = mutation["vcfElement"]
    classes = defaultdict(lambda: Counter())
    for key, row in detected.items():
        if not row["queries"]:  # only the classes the queries miss
            mutation_class = key.split("|")[0]
            classes[mutation_class]["total"] += 1
            for profile in ("core", "full"):
                classes[mutation_class][profile] += int(row[profile])
    return {
        "scores": scores,
        "missedByQueries": [
            {"class": name, "mutations": c["total"], "core": c["core"], "full": c["full"]}
            for name, c in sorted(classes.items())
        ],
    }


def real_genome() -> dict:
    """The consumer WGS validation run: NG131FQA1I's first 250,000 records, validated by v3.3.1.

    The paired comparison on QLever, with the default shapes checked in record batches. The
    v3.1.0 runs on the same slice, which the supplement cites for the oracle's corrections,
    are on the legacy branch.
    """
    report = Path(glob.glob(str(V331["vcf-bench-2"] / "consumer_wgs__NG131FQA1I__first250000" / "out"
                                / "run_metrics" / "*" / "reports" / "validation" / "NG131FQA1I_first250000"))[0])
    shacl = load(report / "shacl.json")
    sample, records = re.fullmatch(r"(.+)_first(\d+)", report.name).groups()
    return {
        "sample": sample, "records": int(records),
        "triples": load(report / "rdf-validation.json")["tripleCount"],
        "queries": [{"query": q, "status": r["status"]}
                    for q, r in sorted(load(report / "comparison.json")["queries"].items())],
        "shacl": {"status": shacl["status"], "violations": shacl["violationCount"],
                  "advisories": shacl["advisoryCount"], "batches": shacl["batches"],
                  "workers": shacl["workers"], "minutes": round(shacl["wallSeconds"] / 60)},
        "source": rel(report),
    }


# ---------------------------------------------------------------------------
# Conversion cost
# ---------------------------------------------------------------------------
def sample_ladder_records() -> int:
    """The sample ladder's record count, from its derived inputs' names (1000G_<n>r_s<k>)."""
    counts = {int(m.group(1)) for c in fd.summary()["cells"]
              if c["experiment"] == "03_sample_representation" and c["branch"] == "live"
              for m in [re.search(r"_(\d+)r_s\d+\.vcf", " ".join(c.get("command") or []))] if m}
    assert len(counts) == 1, counts
    return counts.pop()


def scaling() -> dict:
    ladder = fd.records_ladder()
    storage = {
        key: {mode: {"peakBytes": st.mean(v[0] for v in runs),
                     "wallSeconds": st.mean(v[1] for v in runs),
                     "triples": runs[0][2]}
              for mode, runs in modes.items()}
        for key, modes in fd.storage_modes().items()
    }
    return {
        "records": {"rungs": ladder["rungs"], "median": ladder["median"],
                    "meanWall": [st.mean(ladder["runs"][n]["wall"]) for n in ladder["rungs"]],
                    "replicates": len(ladder["runs"][ladder["rungs"][0]]["wall"]),
                    "wholeFileRecords": fd.HG005_WHOLE_RECORDS},
        "storage": storage,
        "samples": {**fd.sample_ladder(), "records": sample_ladder_records()},
        "corpus": fd.corpus_rows(),
    }


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
REGIONAL = V331["vcf-bench-1"] / "14_regional_access"


def regional() -> dict:
    """Median over questions of each question's median per arm and window size."""
    out = {}
    for graph in ("small", "slice"):
        path = REGIONAL / graph / "out" / "regional.csv"
        times = defaultdict(list)
        executions = failures = disagreements = 0
        for row in fd.tidy(path):
            executions += 1
            failures += row["status"] != "OK"
            disagreements += row["agrees_with_reference"] != "True"
            if row["status"] == "OK":
                times[(row["arm"], int(row["window_size"]), row["query_id"])].append(
                    float(row["wall_seconds"]))
        per_arm = defaultdict(lambda: defaultdict(list))
        for (arm, size, _query), values in times.items():
            per_arm[arm][size].append(st.median(values))
        meta = load(path.with_name("regional.json"))
        setup = meta.get("setup") or {}
        windows = load(path.with_name("windows.json"))
        out[graph] = {
            "records": windows["totalRecords"], "questions": len(meta["queries"]),
            "windowsPerSize": windows["windowsPerSize"], "scanWindowsPerSize": meta["scanWindowsPerSize"],
            "replicates": meta["replicates"],
            "ms": {arm: {str(size): round(1000 * st.median(v), 2) for size, v in sorted(sizes.items())}
                   for arm, sizes in per_arm.items()},
            "executions": executions, "failures": failures, "disagreements": disagreements,
            "setupSeconds": {
                "qlever": setup.get("engineSetupSeconds", {}).get("qlever"),
                "bgzipAndTabix": (setup.get("vcfIndex") or {}).get("totalSetupSeconds"),
            },
        }
    return out


def scale() -> dict:
    path = V331["vcf-bench-3"] / "16_scale_retrieval" / "retrieval.csv"
    rows = []
    for row in fd.tidy(path):
        status = row["statuses"]
        # A successful wrapper exit need not be a completed query response.
        # In particular, native HDT Q5 left a truncated !TIMEDOUT! response.
        if row["engine"] != "qlever" and status == "PASS":
            responses = list(path.parent.glob(
                f"{row['scale']}__{row['engine']}__*/out/run_metrics/*/reports/validation/*/raw/"
                f"{row['engine']}/{row['query_id']}.sparql.json"))
            if len(responses) != int(row["replicates"]):
                raise ValueError(f"Missing native query response: {row['engine']} {row['query_id']}")
            for response in responses:
                raw = response.read_text(encoding="utf-8")
                try:
                    json.loads(raw)["results"]["bindings"]
                except (json.JSONDecodeError, KeyError):
                    status = "TIMEOUT" if "!TIMEDOUT!" in raw else "INVALID_RESULT"
        rows.append({
            "scale": row["scale"], "engine": row["engine"], "artifact": row["artifact"],
            "query": row["query_id"], "status": status, "reportedStatus": row["statuses"],
            "seconds": float(row["median_query_seconds"]) if row["median_query_seconds"] and status == "PASS" else None,
            "setup": float(row["median_setup_seconds"]) if row["median_setup_seconds"] else None,
        })
    return {"rows": rows, "source": rel(path)}


def sparql_binding_multiset(result: dict) -> Counter:
    """Compare raw answers without row-order or numeric datatype differences.

    Native runs that stop early have no consolidated sparql.json. Their complete
    raw answers can still be compared with a QLever run whose normalized answers
    were checked against the source VCF. Preserve duplicate rows and RDF terms.
    """
    numeric = {"integer", "int", "long", "decimal", "double", "float", "nonNegativeInteger",
               "positiveInteger", "unsignedInt", "unsignedLong", "short", "byte"}

    def term(value):
        datatype = value.get("datatype", "")
        if datatype.startswith("http://www.w3.org/2001/XMLSchema#") and datatype.split("#")[-1] in numeric:
            return ("number", Decimal(value["value"]))
        return (value["type"], value["value"], value.get("xml:lang", ""), datatype)

    return Counter(tuple(sorted((key, term(value)) for key, value in row.items()))
                   for row in result["results"]["bindings"])


def scale_comparison() -> dict:
    """Per-query completion and stage costs, directly from the scale run reports.

    Missing engine/scale combinations are explicitly unmeasured, never zero-time
    successes or failures. Query totals follow the paper's sum-of-medians rule;
    decoding and indexing use separate replicate medians (not a single timed run).
    """
    root = V331["vcf-bench-3"] / "16_scale_retrieval"
    groups = defaultdict(list)
    references = {}
    for cell in sorted(root.glob("*__qlever__nt_gz__*")):
        report = next(cell.glob("out/run_metrics/*/reports/validation/*/summary.json")).parent
        references.setdefault(cell.name.split("__")[0], report)
    for cell in sorted(root.glob("*__*__core__r*")):
        scale_id, engine, artifact_id, _, _ = cell.name.split("__")
        artifact = {"nt_gz": "nt.gz"}.get(artifact_id, artifact_id)
        report = next(cell.glob("out/run_metrics/*/reports/validation/*/summary.json")).parent
        summary = load(report / "summary.json")
        bench = load(cell / "bench.json")
        command = bench["command"]
        timings = {r["query_id"]: r for r in fd.tidy(report / "benchmark.csv") if r["engine"] == engine}
        parser = load(report / "parser.json")
        normalized = load(report / "sparql.json") if engine == "qlever" else None
        reference = references[scale_id]
        reference_parser = load(reference / "parser.json")
        reference_answers = load(reference / "sparql.json")
        queries = []
        for q, label in fd.QUERIES:
            execution = summary.get("queryExecutions", {}).get(q, {})
            timing = timings[q]
            error = execution.get("error", "")
            response = report / "raw" / engine / f"{q}.sparql.json"
            raw = response.read_text(encoding="utf-8")
            agrees = None
            if "!TIMEDOUT!" in raw:
                status = "TIMEOUT"
            elif "Connection refused" in error or "Connection reset by peer" in error:
                status = "ENDPOINT_UNAVAILABLE"
            elif timing["status"] != "PASS":
                status = "EXECUTION_FAILED"
            else:
                # Parsing must succeed even when the wrapper reports PASS.
                answer = sparql_binding_multiset(json.loads(raw))
                if engine == "qlever":
                    agrees = q in normalized and q in parser and normalized[q] == parser[q]
                else:
                    reference_raw = load(reference / "raw" / "qlever" / f"{q}.sparql.json")
                    agrees = (answer == sparql_binding_multiset(reference_raw)
                              and parser[q] == reference_parser[q] == reference_answers[q])
                status = "PASS" if agrees else "MISMATCH"
            queries.append({"query": q, "label": label, "status": status,
                            "reportedStatus": timing["status"], "answerAgrees": agrees,
                            "seconds": float(timing["wall_seconds"]), "error": error,
                            "source": rel(response)})
        groups[(scale_id, engine, artifact)].append({
            "source": rel(report), "status": summary["status"],
            "host": bench["host"], "image": bench["image_ref"],
            "nodeHeapMb": int(command[command.index("--node-heap-mb") + 1]) if "--node-heap-mb" in command else None,
            "records": parser["totalRecords"], "queries": queries,
            "decodeSeconds": load(report / "materialization.json")["wallSeconds"],
            "indexSeconds": summary["benchmark"]["engineSetupSeconds"][engine],
        })

    paths = [("qlever", "nt.gz"), ("qlever", "hdt"), ("qlever", "cottas"),
             ("hdt", "hdt"), ("cottas", "cottas")]
    cells, stages, graphs = [], [], []
    for scale_id in ("r1000000", "whole"):
        manifest = load(RESULTS / "vcf-bench-3" / "scale-store-manifests" / f"{scale_id}.manifest.json")
        records = groups[(scale_id, "qlever", "nt.gz")][0]["records"]
        graphs.append({"scale": scale_id, "records": records, "triples": manifest["triples"]})
        for engine, artifact in paths:
            runs = groups[(scale_id, engine, artifact)]
            questions = []
            for i, (q, label) in enumerate(fd.QUERIES):
                measured = [r["queries"][i] for r in runs]
                statuses = {m["status"] for m in measured}
                status = next(iter(statuses)) if len(statuses) == 1 else "MIXED" if statuses else "NOT_RUN"
                values = [m["seconds"] for m in measured]
                questions.append({"query": q, "label": label, "status": status,
                                  "seconds": st.median(values) if values else None,
                                  "minSeconds": min(values) if values else None,
                                  "maxSeconds": max(values) if values else None,
                                  "sources": [m["source"] for m in measured]})
            cells.append({"scale": scale_id, "engine": engine, "artifact": artifact,
                          "records": records, "triples": manifest["triples"], "replicates": len(runs),
                          "completed": sum(q["status"] == "PASS" for q in questions) if runs else None,
                          "total": len(questions), "queries": questions, "runs": runs})
            if scale_id == "whole" and engine == "qlever":
                for stage, values in (("Decode to N-Triples", [r["decodeSeconds"] for r in runs]),
                                      ("Build QLever index", [r["indexSeconds"] for r in runs]),
                                      ("Run all queries", [sum(q["seconds"] for q in r["queries"]) for r in runs])):
                    if not all(q["status"] == "PASS" for q in questions):
                        raise ValueError(f"Incomplete QLever workload: {scale_id} {artifact}")
                    seconds = (sum(q["seconds"] for q in questions) if stage == "Run all queries"
                               else st.median(values))
                    stages.append({"artifact": artifact, "stage": stage, "seconds": seconds,
                                   "minSeconds": min(values), "maxSeconds": max(values),
                                   "replicates": len(runs), "sources": [r["source"] for r in runs]})
    return {"cells": cells, "graphs": graphs, "wholeStages": stages, "source": rel(root)}


def qlever_cost_by_size() -> list[dict]:
    """The thirteen questions' QLever time per graph size, as the sum of per-question medians.

    The two smaller graphs ran on vcf-bench-1 (13_query_cost, N-Triples), the two
    larger on vcf-bench-3 (16_scale_retrieval, gzip N-Triples).
    """
    series = []
    for size in ("small", "large"):
        times, triples = defaultdict(list), None
        for rep_dir in sorted((fd.B1 / "13_query_cost").glob(f"{size}__r*")):
            for report in rep_dir.glob("out/run_metrics/*/reports/validation/*"):
                if "__" in report.name:  # the HDT and COTTAS validations
                    continue
                triples = load(report / "rdf-validation.json")["tripleCount"]
                for row in fd.tidy(report / "benchmark.csv"):
                    if row["engine"] == "qlever" and row["query_id"] in fd.QIDS and row["status"] == "PASS":
                        times[row["query_id"]].append(float(row["wall_seconds"]))
        series.append({"graph": size, "host": "vcf-bench-1", "triples": triples,
                       "seconds": sum(st.median(v) for v in times.values())})
    manifests = RESULTS / "vcf-bench-3" / "scale-store-manifests"
    rows = scale()["rows"]
    for name, manifest in (("r1000000", "r1000000"), ("whole", "whole")):
        seconds = [r["seconds"] for r in rows
                   if r["scale"] == name and r["engine"] == "qlever" and r["artifact"] == "nt.gz"]
        series.append({"graph": name, "host": "vcf-bench-3",
                       "triples": load(manifests / f"{manifest}.manifest.json")["triples"],
                       "seconds": sum(seconds)})
    for row in series:
        row["perMillion"] = row["seconds"] / (row["triples"] / 1e6)
    return series


def retrieval() -> dict:
    data = fd.retrieval()
    return {
        "perQuestion": [
            {"query": qid, "label": label,
             "sparql": st.mean(data["engine_q"][qid]), "parser": st.mean(data["oracle_q"][qid])}
            for qid, label in fd.QUERIES
        ],
        "batch": {"sparql": data["ql_batch"], "setup": data["ql_setup"], "parser": data["parser_batch"]},
        "engines": {e: {"mean": st.mean(r), "min": min(r), "max": max(r), "runs": len(r),
                        "setup": [min(data["small_setup"][e]), max(data["small_setup"][e])]}
                    for e, r in data["engine_runs"].items()},
        "artifacts": {t: st.mean(v) for t, v in data["per_target"].items()},
        "regional": regional(),
        "scale": scale(),
        "scaleComparison": scale_comparison(),
        "costBySize": qlever_cost_by_size(),
        "breakEven": {k: v for k, v in fd.breakeven().items() if k != "conversion_runs"},
    }


# ---------------------------------------------------------------------------
# Shared-input converter comparison (experiment 18; Figure 6, Section S2)
# ---------------------------------------------------------------------------
CONVERTERS = RESULTS / "vcf-bench-1" / "18_converter_comparison"
CONVERTER_NAMES = {"vcf-rdfizer": "VCF-RDFizer", "jvarkit": "JVarkit", "togovar": "TogoVar",
                   "sparqling-genomics": "SPARQLing Genomics", "biointerchange": "BioInterchange"}


def converters() -> dict:
    """Which content questions each converter's graph answers as the oracle does, and its conversion cost."""
    summary = CONVERTERS / "summary"
    outcomes = [{"tool": r["tool"], "input": r["input"], "question": r["question"], "status": r["status"]}
                for r in fd.tidy(summary / "outcomes.csv")]
    runs = defaultdict(list)
    for r in fd.tidy(summary / "conversions.csv"):
        runs[(r["tool"], r["input"])].append(r)
    conversions = [{"tool": tool, "input": data, "replicates": len(rs),
                    "wallSeconds": st.median(float(r["wall_seconds"]) for r in rs),
                    "peakRssGb": max(int(r["peak_rss_kb"]) for r in rs) * 1024 / 1e9,
                    "outputBytes": st.median(int(r["native_output_bytes"]) for r in rs)}
                   for (tool, data), rs in sorted(runs.items())]
    labels = dict(fd.QUERIES)
    questions = sorted({o["question"] for o in outcomes})
    inputs = {"HG005_GRCh38_r100000": "HG005, 100,000 records, one sample",
              "1000G_10000r_s16": "1000 Genomes, 10,000 records, 16 samples"}
    return {"tools": [{"id": k, "name": v} for k, v in CONVERTER_NAMES.items()],
            "inputs": [{"id": k, "label": v} for k, v in inputs.items()],
            "questions": [{"id": q, "label": labels[q]} for q in questions],
            "outcomes": outcomes, "conversions": conversions, "source": rel(CONVERTERS)}


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------
ARMS = {
    "arm1": V331["vcf-bench-1"] / "17_use_case_acmg",
    "arm2": V331["vcf-bench-1"] / "17_use_case_acmg__cohort",
    "arm3": V331["vcf-bench-2"] / "17_use_case_acmg__wgs",
    "arm4": V331["vcf-bench-2"] / "17_use_case_acmg__layered",
}


def reported_cells(arm: Path, prefix: str) -> list[Path]:
    """The cells the paper reports: unsuffixed, so not __phase1, __failed_* or __before_*."""
    return [p for p in sorted(arm.glob(f"{prefix}__*")) if p.is_dir() and "__" not in p.name[len(prefix) + 2:]]


def wall(cells: list[Path]) -> float:
    return sum(load(c / "bench.json")["wrapper_wall_seconds"] for c in cells if (c / "bench.json").exists())


def usecase_inputs(arm: Path) -> dict:
    """Converted files, records and triples, with public annotations counted separately.

    Use the final conversion-stage report, not a counterfactual conversion or
    a sum of intermediate metrics. These are the same v3.3.1 cells as the
    match comparisons and stage-cost reader below; links are excluded.
    """
    groups = defaultdict(Counter)
    for cell in reported_cells(arm, "convert"):
        source = cell.name.split("__", 1)[1]
        group = source if source in ("clinvar", "panel") else "genomes"
        reports = list((cell / "out" / "run_metrics").glob("*/stages/conversion/*.json"))
        if len(reports) != 1:
            raise ValueError(f"Expected one conversion report in {cell}, got {len(reports)}")
        report = load(reports[0])
        if report["exit_code"] != 0:
            raise ValueError(f"Unsuccessful conversion: {reports[0]}")
        groups[group].update(files=1, records=report["sample_representation"]["records"],
                             triples=report["artifacts"]["output_triples"]["TOTAL"])
    return {group: dict(counts) for group, counts in groups.items()}


def stage_costs(arm: Path) -> dict:
    """Seconds per stage: one value for the once-per-arm stages, one per requester otherwise.

    The view is the govern cell. The harness checks a view between that cell and
    the next requester's, so a check is the gap between consecutive govern cells;
    the last requester's gap also holds other work and is not used. Index and
    query are the query cell's setup and median replicate.
    """
    def bench(cell):
        return load(cell / "bench.json")

    def cells(prefix):
        return [c for c in reported_cells(arm, prefix) if (c / "bench.json").exists()]

    govern = sorted(cells("govern"), key=lambda c: bench(c)["started_epoch"])
    out = {"convert": [wall(cells("convert"))], "link": [wall(cells("link"))],
           "view": [], "check": [], "index": [], "query": [], "empty": set()}
    for i, cell in enumerate(govern):
        requester = cell.name.split("__", 1)[1]
        out["view"].append((requester, bench(cell)["wrapper_wall_seconds"]))
        if i + 1 < len(govern):
            out["check"].append((requester, bench(govern[i + 1])["started_epoch"] - bench(cell)["ended_epoch"]))
        summary = load(cell / "out" / "summary.json")
        out.setdefault("released", {})[requester] = (summary["records_released"], summary["triples_released"])
        if summary["records_released"] == 0:
            out["empty"].add(requester)
    for timing in sorted(arm.glob("query/*/timing.json")):
        requester = timing.parent.name
        data = load(timing)
        replicates = data["replicates"]
        replicates = replicates["carriers"] if isinstance(replicates, dict) else replicates
        if requester == "unrestricted":
            out["unrestricted"] = (data["setup_seconds"], st.median(replicates))
            continue
        out["index"].append((requester, data["setup_seconds"]))
        out["query"].append((requester, st.median(replicates)))
    out["triples"] = load(arm / "query" / "unrestricted" / "timing.json")["triples"]
    return out


def stage_cost_table(arm: Path) -> dict:
    """stage_costs() for the site: once-per-arm stages, then one row per requester (Figure S4, Table S11)."""
    costs = stage_costs(arm)
    per = defaultdict(dict)
    for stage in ("view", "check", "index", "query"):
        for requester, seconds in costs[stage]:
            per[requester][stage] = seconds
    for requester, (records, triples) in costs["released"].items():
        per[requester].update(records=records, triples=triples, empty=requester in costs["empty"])
    # The conventional workflow is one cell for all requesters, after the same derived inputs.
    conventional = load(arm / "baseline" / "bench.json")["wrapper_wall_seconds"]
    return {"convert": costs["convert"][0], "link": costs["link"][0], "triples": costs["triples"],
            "conventional": conventional, "requesters": dict(per)}


def usecase() -> dict:
    arms = {}
    for name, arm in ARMS.items():
        comparison = load(arm / "comparison.json")
        # Genomes, ClinVar and the cohort's panel file are reported apart.
        linkers = defaultdict(lambda: defaultdict(Counter))
        for cell in reported_cells(arm, "link"):
            source = cell.name.split("__", 1)[1]
            group = source if source in ("clinvar", "panel") else "genomes"
            for path in cell.glob("out/*.links.json"):
                for linker in load(path).get("linkers", []):
                    linkers[group][linker["id"]]["linked"] += linker.get("linked_subjects") or 0
                    linkers[group][linker["id"]]["eligible"] += linker.get("eligible_records") or 0
        queries = {}
        for timing in sorted(arm.glob("query/*/timing.json")):
            data = load(timing)
            # Arm 1 records one query's replicates; later arms record them per query.
            replicates = data["replicates"]
            if isinstance(replicates, list):
                replicates = {"carriers": replicates}
            queries[timing.parent.name] = {"replicates": replicates, "setup": data["setup_seconds"]}
        with (arm / "grid.tsv").open(encoding="utf-8") as handle:
            grid = list(csv.reader(handle, delimiter="\t"))
        arms[name] = {
            "inputs": usecase_inputs(arm),
            "carriers": {r: {k: v for k, v in c.items() if k in ("baseline", "rdf", "agree")}
                         for r, c in comparison.items() if isinstance(c, dict) and "agree" in c},
            "rare": {r: {k: v for k, v in c.items() if k in ("baseline", "rdf", "agree")}
                     for r, c in (comparison.get("rare") or {}).items() if isinstance(c, dict)},
            "grid": {"participants": grid[0][1:], "rows": {row[0]: [int(x) for x in row[1:]] for row in grid[1:]}},
            "linking": {g: {k: dict(v) for k, v in by.items()} for g, by in linkers.items()},
            "stageSeconds": {
                "convert": wall(reported_cells(arm, "convert")),
                "link": wall(reported_cells(arm, "link")),
                "view": {c.name.split("__")[1]: wall([c]) for c in reported_cells(arm, "govern")},
            },
            "queries": queries,
            "records": {r: {k: v for k, v in c.items() if k in ("baseline", "rdf", "agree")}
                        for r, c in (comparison.get("records") or {}).items() if isinstance(c, dict)},
            "costs": stage_cost_table(arm),
            "source": rel(arm),
        }
    images = {load(c / "bench.json").get("image_ref") for arm in ARMS.values()
              for c in reported_cells(arm, "convert") if (c / "bench.json").exists()}
    return {"arms": arms, "effort": load(ACMG / "effort.json"), "study": study(),
            "convertImages": sorted(images - {None}), "myvariant": myvariant()}


def study() -> dict:
    """The question's fixed inputs: genes, participants, consents and requesters."""
    spec = load(ACMG / "use_case.json")
    regions = load(ACMG / "regions.json")
    return {
        "geneList": regions["gene_list"].split(" (")[0],
        "genes": regions["genes"],
        "coordinates": regions["coordinates"].split(" (")[0],
        "participants": [{"id": p["id"], "source": p["source"]} for p in spec["participants"]],
        "consents": spec["policy"]["consents"],
        "requesters": spec["policy"]["requesters"],
        "restrictedGenes": len(spec["policy"]["secondary_findings"]["genes"]),
        "cohort": len(load(ACMG / "cohort" / "cohort.json")["participants"]),
        "wholeGenome": spec["whole_genome"]["participant"],
    }


def myvariant() -> dict:
    """The live tier: how many rsID links MyVariant.info confirmed, and in how many service responses.

    The v3.3.1 run replays the responses recorded on 2026-09-28 rather than
    requesting them again, so its linker reports 0 requests: count the
    responses it used, live or recorded.
    """
    arm = ARMS["arm1"]
    confirmed = load(arm / "tier1_vs_tier3_myvariant.json")
    requests = sum(len(linker.get("responses") or [])
                   for path in arm.glob("link_myvariant__*/out/*.links.json")
                   for linker in load(path).get("linkers", []))
    return {"genomes": {g: {"rsid": c["tier1_links"], "confirmed": c["tier3_links"]} for g, c in confirmed.items()},
            "requests": requests}


# ---------------------------------------------------------------------------
# Release policies (RQ2): how each scenario's ODRL rules decided each release
# ---------------------------------------------------------------------------
#: Each scenario's case file. generate.py writes policy.ttl beside it (arm 1's into acmg/),
#: and test_use_case.py fails if a committed policy.ttl is not what its case generates.
POLICY_CASES = {
    "arm1": ACMG / "use_case.json",
    "arm2": ACMG / "cohort" / "cohort.json",
    "arm3": ACMG / "wgs" / "case.json",
    "arm4": ACMG / "layered" / "case.json",
}
SCENARIO_TITLES = {
    "arm1": "Gene-span slices of {n} single-sample VCFs",
    "arm2": "{n} 1000 Genomes participants",
    "arm3": "The complete {first} VCF",
    "arm4": "The complete {first} VCF under layered consent",
}
OBO = "http://purl.obolibrary.org/obo/"
POLICY_NS = "https://example.org/policy/acmg-use-case/"
CLINICAL_CARE = OBO + "DUO_0000043"  # generate.py's cohort_rule("DUO:0000043")
NO_PERMISSION = "no-permission"      # the engine's default deny


def acmg_generate():
    """benchmarks/use_case/acmg/generate.py (standard library only), for its DUO terms."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("acmg_generate", ACMG / "generate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def purpose_iri(term: str) -> str:
    return OBO + "DUO_" + term.split(":")[1] if term.startswith("DUO:") else term


def purpose_vocabulary(case: dict) -> dict[str, dict]:
    """The purposes a scenario's evaluation knew, each with its broader term.

    generate.py's DUO_TERMS are the plug-in's bundled DUO subset, term for term
    (arms 1-3 ran with that default); a case's own purposes extend it (arm 4's
    purposes.ttl)."""
    terms = {OBO + term: {"label": label, "broader": OBO + broader} for term, label, broader in re.findall(
        r'obo:(DUO_\d+) rdfs:label "([^"]+)" ; rdfs:subClassOf obo:(DUO_\d+)', acmg_generate().DUO_TERMS)}
    for term in case.get("purposes", []):
        terms[term["iri"]] = {"label": term["label"], "broader": purpose_iri(term["broader"])}
    return terms


def within(purpose: str, term: str, vocabulary: dict) -> bool:
    """The engine's rule: a purpose satisfies a term when it is that term or narrower."""
    while purpose:
        if purpose == term:
            return True
        purpose = vocabulary.get(purpose, {}).get("broader")
    return False


def rule_applies(rule: dict, assignee: str, purpose: str, vocabulary: dict) -> bool:
    """vcf_rdfizer_policies.engine.applies(): the assignee matches, and every constraint holds."""
    if rule["assignees"] and assignee not in rule["assignees"]:
        return False
    if rule["operator"]:
        inside = any(within(purpose, term, vocabulary) for term in rule["purposes"])
        return inside == (rule["operator"] == "isAnyOf")
    return True


def policy_rules(case: dict) -> list[dict]:
    """The rules generate.py writes from a case file, in the order it writes them."""
    policy, requesters = case["policy"], case["policy"]["requesters"]
    findings = policy["secondary_findings"]
    rules = [{"id": "cohort", "kind": "prohibition", "subjects": ["ex:cancer-predisposition", "ex:cohort"],
              "asset": POLICY_NS + "cancer-predisposition", "target": {"kind": "genes", "genes": findings["genes"]},
              "assignees": [], "operator": "isNoneOf", "purposes": [CLINICAL_CARE], "rule": findings["rule"]}]
    for participant, consent in policy["consents"].items():
        rules.append({"id": f"consent-{participant}", "kind": "consent", "subjects": [f"ex:consent-{participant}"],
                      "asset": f"file://{participant}.acmg.vcf", "target": {"kind": "file", "participant": participant},
                      "assignees": [], "operator": "isAnyOf", "purposes": [purpose_iri(t) for t in consent["permits"]],
                      "withdrawn": bool(consent.get("withdrawn"))})
    for i, panel in enumerate(policy.get("purpose_panels", []), 1):
        rules.append({"id": f"outside_panel_{i}", "kind": "prohibition",
                      "subjects": [f"ex:OutsidePanel{i}", f"ex:outside-panel-{i}", f"ex:outside_panel_{i}"],
                      "asset": POLICY_NS + f"outside-panel-{i}", "target": {"kind": "outside-panel", "genes": panel["genes"]},
                      "assignees": [], "operator": "isAnyOf", "purposes": [purpose_iri(panel["purpose"])], "rule": panel["rule"]})
    for region in policy.get("regions", []):
        name = f"region-{region['name'].lower()}"
        rules.append({"id": name.replace("-", "_"), "kind": "prohibition", "subjects": [f"ex:{name}", f"ex:{name.replace('-', '_')}"],
                      "asset": POLICY_NS + name,
                      "target": {"kind": "region", **{k: region[k] for k in ("name", "chrom", "start", "end", "source")}},
                      "assignees": [], "operator": "isNoneOf", "purposes": [purpose_iri(t) for t in region["purposes"]],
                      "rule": region["rule"]})
    for i, variant in enumerate(policy.get("variants", []), 1):
        rules.append({"id": f"variant_{i}", "kind": "prohibition", "subjects": [f"ex:variant-{i}", f"ex:variant_{i}"],
                      "asset": POLICY_NS + f"variant-{i}",
                      "target": {"kind": "variant", **{k: variant[k] for k in ("name", "spdi")}},
                      "assignees": [requesters[who]["assignee"] for who in variant["withheld_from"]],
                      "operator": None, "purposes": [], "rule": variant["rule"]})
    return rules


def policy_statements(path: Path) -> dict[str, dict]:
    """Every top-level statement of a policy file, by its subject, as written (with its comment)."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = {}
    for first, last in turtle_statements(text):
        subject = lines[first - 1].split()[0]
        if subject.startswith("@"):
            continue
        start, written = statement_text(lines, first, last)
        out[subject] = {"lines": [start, last], "text": written}
    return out


def release_outcome(cell: Path, rules: list[dict], digest: str) -> dict:
    """One requester's release view: what was released, and which rule decided each withheld record.

    The engine names one reason per record (the first prohibition that covers
    it, else the permission that releases it), so the counts per rule add up to
    the records of the file."""
    summary = load(cell / "out" / "summary.json")
    recorded = re.search(r'vcfp:policyDigest "sha256:([0-9a-f]+)"', (cell / "out" / "manifest.ttl").read_text(encoding="utf-8"))
    if not recorded or recorded.group(1) != digest:
        raise ValueError(f"{cell}: the release used a different policy than the committed one")
    by_asset = {rule["asset"]: rule["id"] for rule in rules}
    effects = defaultdict(lambda: {"released": 0, "withheld": 0})
    for reason, records in summary["reasons"].items():
        verdict, _, why = reason.partition(": ")
        rule = NO_PERMISSION if why == "no permission covers it for this purpose" else by_asset[why.split(" on ", 1)[1].strip("<>")]
        effects[rule][verdict] += records
    if sum(e["released"] for e in effects.values()) != summary["records_released"] or \
            sum(e["withheld"] for e in effects.values()) != summary["records_withheld"]:
        raise ValueError(f"{cell}: the reasons do not add up to the released and withheld records")
    files = [{"participant": group.removeprefix("file://").removesuffix(".acmg.vcf"), "released": g["released"],
              "rule": NO_PERMISSION if g["reason"].endswith("no permission covers it for this purpose")
              else by_asset[g["reason"].split(" on ", 1)[1].strip("<>")],
              "recordsReleased": g["records_released"], "recordsWithheld": g["records_withheld"]}
             for group, g in sorted(summary["groups"].items())]
    return {"released": summary["records_released"], "withheld": summary["records_withheld"],
            "triplesReleased": summary["triples_released"], "triplesWithheld": summary["triples_withheld"],
            "effects": dict(effects), "files": files, "source": rel(cell / "out")}


#: The conventional workflow's version of each piece of the policy, as blocks of
#: baseline_carriers.py found by their own comments and definitions (start, end exclusive),
#: so a shifted line cannot misplace them.
CONVENTIONAL_BLOCKS = {
    "purposes": ("# DUO: disease-specific research (DS)", "COLUMNS = ["),
    "within": ("def within(", "def classification("),
    "overlaps": ("def overlaps(", "def carriers("),
    "consent": ('    consent = policy["consents"][carrier["participant"]]', "    # The secondary-findings rule"),
    "cohort": ("    # The secondary-findings rule", "    # Arm 4: a purpose limited to a gene panel"),
    "outside-panel": ("    # Arm 4: a purpose limited to a gene panel", "    # A region is coordinates"),
    "region": ("    # A region is coordinates", "    # A named variant"),
    "variant": ("    # A named variant", "    return True"),
}


def conventional_code() -> dict:
    """Each rule as the conventional workflow's hand-written Python applies it (baseline_carriers.py's
    released()), with the lines the page links to. The script reads the same case file as
    generate.py, never the RDF or the policy."""
    path = ACMG / "baseline_carriers.py"
    lines = path.read_text(encoding="utf-8").splitlines()

    def find(marker: str, after: int = 0) -> int:
        found = [i for i, line in enumerate(lines) if i >= after and line.startswith(marker)]
        if not found:
            raise ValueError(f"{rel(path)}: no line starts with {marker!r}")
        return found[0]

    code = {}
    for name, (start_marker, end_marker) in CONVENTIONAL_BLOCKS.items():
        start = find(start_marker)
        end = find(end_marker, start + 1)
        while not lines[end - 1].strip():
            end -= 1
        code[name] = {"lines": [start + 1, end], "text": "\n".join(lines[start:end]) + "\n"}
    return {"script": rel(path), "driver": rel(ACMG / "baseline.sh"), "derive": rel(ACMG / "derive.sh"), "code": code}


def policies() -> dict:
    """For each scenario: its purposes, its rules (as data and as the Turtle that ran), and for
    each requester which rules applied and what each one withheld, through to the ClinVar
    matches the requester's query returned. Checked against the engine's own records.
    Alongside: the conventional workflow's version of each rule, and both routes' stage times."""
    import hashlib
    scenarios = []
    for arm_id, case_path in POLICY_CASES.items():
        arm, case = ARMS[arm_id], load(case_path)
        policy_path = case_path.parent / "policy.ttl"
        digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
        vocabulary = purpose_vocabulary(case)
        statements = policy_statements(policy_path)
        rules = policy_rules(case)
        for rule in rules:
            parts = sorted((statements[s] for s in rule.pop("subjects")), key=lambda s: s["lines"][0])
            rule["turtle"] = "\n".join(p["text"].rstrip("\n") for p in parts) + "\n"
            rule["lines"] = [p["lines"] for p in parts]
        comparison = load(arm / "comparison.json")
        requesters = []
        for requester, request in case["policy"]["requesters"].items():
            assignee, purpose = request["assignee"], purpose_iri(request["purpose"])
            outcome = release_outcome(arm / f"govern__{requester}", rules, digest)
            applies = {rule["id"]: rule_applies(rule, assignee, purpose, vocabulary) for rule in rules}
            # The site's reading of the policy must agree with the engine's decisions.
            for rule in rules:
                effect = outcome["effects"].get(rule["id"], {})
                if (effect.get("withheld") and rule["kind"] == "prohibition" or effect.get("released")) and not applies[rule["id"]]:
                    raise ValueError(f"{arm_id} {requester}: {rule['id']} decided records but does not apply")
            for f in outcome["files"]:
                consent = next(r for r in rules if r["id"] == f"consent-{f['participant']}")
                if f["released"] != (applies[consent["id"]] and not consent["withdrawn"]):
                    raise ValueError(f"{arm_id} {requester}: {f['participant']}'s file decision disagrees with its consent")
            requesters.append({
                "id": requester, "assignee": assignee, "purpose": purpose,
                "label": assignee.rstrip("/").rsplit("/", 1)[1].replace("-", " ").capitalize(),
                "applies": applies, **outcome,
                "matches": {k: comparison[requester][k] for k in ("rdf", "baseline", "agree")},
                "records": {k: comparison["records"][requester][k] for k in ("rdf", "baseline", "agree")},
            })
        if {f"govern__{r['id']}" for r in requesters} != {c.name for c in reported_cells(arm, "govern")}:
            raise ValueError(f"{arm_id}: the case's requesters are not the released views")
        participants = [p["id"] for p in case["participants"]]
        scenarios.append({
            "id": arm_id, "number": int(arm_id[-1]),
            "title": SCENARIO_TITLES[arm_id].format(n=words(len(participants)) if len(participants) < 10 else len(participants),
                                                    first=participants[0]),
            "question": case["question"], "participants": participants,
            "policyFile": rel(policy_path), "policyDigest": digest,
            "purposes": [{"iri": iri, **term} for iri, term in vocabulary.items()],
            "purposeFile": rel(case_path.parent / "purposes.ttl") if case.get("purposes") else None,
            "rules": rules, "requesters": requesters,
            "withoutPolicy": {k: comparison["unrestricted"][k] for k in ("rdf", "baseline", "agree")},
            "costs": stage_cost_table(arm),
        })
    return {"scenarios": scenarios, "conventional": conventional_code(), "source": rel(ACMG)}


# ---------------------------------------------------------------------------
# Facts: every number the page's prose quotes, formatted once, here
# ---------------------------------------------------------------------------
WORDS = ("no one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen twenty").split()
# Names of the Data Use Ontology terms the simulated consents use.
DUO = {"DUO:0000006": "health research", "DUO:0000007": "disease-specific research",
       "DUO:0000042": "general research", "DUO:0000043": "clinical care"}


def words(n: int) -> str:
    return WORDS[n] if 0 <= n < len(WORDS) else f"{n:,}"


def millions(x: float) -> str:
    return f"{x / 1e6:.{2 if x < 1e6 else 1 if x < 1e8 else 0}f}M"


def short(n: int) -> str:
    """10000 -> 10k, 1000000 -> 1M."""
    return f"{n // 10**6}M" if n % 10**6 == 0 else f"{n // 1000}k" if n % 1000 == 0 else f"{n:,}"


def span(values, digits: int = 1) -> str:
    lo, hi = (f"{x:.{digits}f}" for x in (min(values), max(values)))
    return lo if lo == hi else f"{lo}–{hi}"


def listing(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def facts(d: dict) -> dict[str, str]:
    campaign, fidelity, scaling, retrieval, usecase, conv = (
        d[k] for k in ("campaign", "fidelity", "scaling", "retrieval", "usecase", "converters"))
    v, mutation, real = fidelity["validation"], fidelity["mutation"], fidelity["realGenome"]
    records, samples, storage = scaling["records"], scaling["samples"], scaling["storage"]
    arms, effort, study = usecase["arms"], usecase["effort"], usecase["study"]
    out = {}

    version = lambda image: "v" + image.rsplit(":", 1)[1]  # noqa: E731
    out["campaignImage"] = campaign["image"]
    out["campaignVersion"] = version(campaign["image"])
    out["cells"] = f"{campaign['totals']['cells']:,}"
    out["campaignHosts"] = words(len(campaign["hosts"]))
    out["useCaseVersion"] = listing([version(i) for i in usecase["convertImages"]])

    # Fidelity
    total = sum(v["comparisons"].values())
    out["questions"] = words(len(retrieval["perQuestion"]))
    out["qRange"] = f"Q1–Q{len(retrieval['perQuestion'])}"
    out["comparisonsEqual"] = f"{v['comparisons']['PASS']:,}"
    out["comparisons"] = f"{total:,}"
    out["comparisonsOther"] = words(total - v["comparisons"]["PASS"])
    scores = mutation["scores"]
    out["faults"] = f"{scores['queries']['total']:,}"
    out["faultsMissed"] = f"{scores['queries']['total'] - scores['queries']['detected']:,}"
    out["faultClasses"] = words(len(mutation["missedByQueries"]))
    out["shaclMaxTriples"] = millions(v["shacl"]["maxTriples"])
    out["realSample"] = real["sample"]
    out["realRecords"] = f"{real['records']:,}"
    out["realTriples"] = millions(real["triples"])
    out["validations"] = words(v["validations"]) if v["validations"] < len(WORDS) else str(v["validations"])
    out["invariants"] = f"{v['invariants'].get('PASS', 0):,}"
    for label, title in FIDELITY_GROUPS.items():
        out[f"fidelity{label}"] = f"{label}. {title}"

    # Use case
    sources = Counter(p["source"].split()[0] for p in study["participants"])
    out["geneList"] = study["geneList"]
    out["genes"] = str(study["genes"])
    out["ensembl"] = study["coordinates"]
    out["requesters"] = words(len(study["requesters"]))
    out["arm1Genomes"] = words(len(study["participants"]))
    out["arm1Sources"] = listing([f"{words(n)} {name}" for name, n in sources.most_common()])
    out["cohort"] = str(study["cohort"])
    out["wholeGenome"] = study["wholeGenome"]
    out["restrictedGenes"] = str(study["restrictedGenes"])
    out["consents"] = "; ".join(
        f"{pid} " + ("withdrew" if c.get("withdrawn") else
                     "consents to " + listing([DUO.get(term, term) for term in c["permits"]]))
        for pid, c in study["consents"].items())
    # The whole genome against the same participant's arm-1 file, by linked records.
    linked = {arm: sum(load(path)["records"] for path in
                       (ROOT / arms[arm]["source"]).glob(f"link__{study['wholeGenome']}/out/*.links.json"))
              for arm in ("arm1", "arm3")}
    fold = linked["arm3"] / linked["arm1"]
    out["wholeGenomeFold"] = f"{float(f'{fold:.2g}'):,.0f}"
    grid = arms["arm1"]["grid"]
    column = grid["participants"].index(study["wholeGenome"])
    same = all(grid["rows"][r][column] == c["rdf"] for r, c in arms["arm3"]["carriers"].items())
    out["wholeGenomeAgreement"] = "equals" if same else "differs from"
    queries = {arm: a["queries"]["unrestricted"] for arm, a in arms.items()}
    out["queryReplicates"] = words(len(queries["arm1"]["replicates"]["carriers"]))
    out["queryMinutes"] = span([st.median(q["replicates"]["carriers"]) / 60 for q in queries.values()])
    out["wholeGenomeIndexMinutes"] = f"{queries['arm3']['setup'] / 60:.0f}"
    code_only = [s for s in effort["scenarios"]
                 if not any(e["added"] or e["removed"] for f, e in s["edits"]["baseline"].items() if "(data)" not in f)]
    out["dataEdits"] = f"{words(len(code_only))} of {words(len(effort['scenarios']))}"
    for route in ("rdf", "baseline"):
        # "of which ... (data)" lines belong to the file listed before them.
        lines, last = {}, None
        for name, n in effort["inventory"][route].items():
            if name.startswith("of which"):
                lines[last] -= n
            elif "(data)" not in name and n:
                lines[last := name] = n
        out[f"{route}Rules"] = (f"{sum(lines.values())} lines ("
                                + ", ".join(f"{f} {n}" for f, n in lines.items()) + ")")
    mv = usecase["myvariant"]
    out["myvariantGenomes"] = words(len(mv["genomes"]))
    out["myvariantShare"] = span([100 * g["confirmed"] / g["rsid"] for g in mv["genomes"].values()], 0) + "%"
    out["myvariantRequests"] = str(mv["requests"])
    # All four scenarios (Scenario 4 adds the participant's own physician as a requester); the data
    # keys keep the harness's name for a scenario, "arm".
    out["scenarios"] = words(len(arms))
    out["armsAgree"] = words(sum(all(c["agree"] for c in a["carriers"].values()) for a in arms.values()))
    out["arm4Participant"] = arms["arm4"]["grid"]["participants"][0]
    out["arm4Requesters"] = words(sum(r != "unrestricted" for r in arms["arm4"]["carriers"]))
    agree = [name for name, a in arms.items() if all(c["agree"] for c in a["records"].values())]
    differ = {name: a["records"] for name, a in arms.items() if name not in agree}
    out["recordArmsAgree"] = "Scenarios " + listing([n[3:] for n in agree])
    out["recordArmsDiffer"] = listing([f"Scenario {n[3:]}" for n in differ])
    out["recordExtra"] = listing([f"{c['rdf'] - c['baseline']:,}" for a in differ.values() for c in a.values()
                                  if not c["agree"]])
    # Query time of every non-empty release view, over all arms (Section S5.4).
    seconds = [r["query"] for a in arms.values() for r in a["costs"]["requesters"].values()
               if r.get("query") and not r.get("empty")]
    out["querySeconds"] = f"{min(seconds):.0f}–{max(seconds):.0f}"
    # The conventional workflow's one run per scenario, against the RDF workflow's conversion and linking.
    conventional = [a["costs"]["conventional"] for a in arms.values()]
    convert_link = [(a["costs"]["convert"] + a["costs"]["link"]) / 60 for a in arms.values()]
    out["conventionalSeconds"] = f"{min(conventional)}–{max(conventional)}"
    out["convertLinkMinutes"] = f"{min(convert_link):.1f}–{max(convert_link):.0f}"
    # Run records hold whole seconds, so the ratio allows the conventional run one more second.
    fold = min(60 * m / (s + 1) for m, s in zip(convert_link, conventional))
    out["conventionalFold"] = f"{int(fold // 10 * 10)}"

    # Conversion
    rss_gb = [kb * 1024 / 1e9 for kb in records["median"]["rss"]]
    out["recordsFold"] = f"{records['rungs'][-1] / records['rungs'][0]:,.0f}"
    out["ladder"] = listing([short(n) for n in records["rungs"][:-1]])
    out["ladderReplicates"] = words(records["replicates"])
    out["wholeRecords"] = f"{records['wholeFileRecords'] / 1e6:.2f}M"
    out["rssLow"], out["rssHigh"] = f"{min(rss_gb):.1f}", f"{max(rss_gb):.1f}"
    out["diskCut"] = span([m["plain"]["peakBytes"] / m["space-optimized"]["peakBytes"] for m in storage.values()])
    out["spaceTimeCost"] = span([100 * (m["space-optimized"]["wallSeconds"] / m["plain"]["wallSeconds"] - 1)
                                 for m in storage.values()], 0) + "%"
    out["sampleRecords"] = f"{samples['records']:,}"
    out["samplesMin"], out["samplesMax"] = (f"{n:,}" for n in (samples["expanded"]["x"][0], samples["expanded"]["x"][-1]))
    out["tripleRatio"] = f"{samples['expanded']['triples'][-1] / samples['condensed']['triples'][-1]:.0f}"
    out["hdtRatio"] = f"{samples['expanded']['hdt'][-1] / samples['condensed']['hdt'][-1]:.0f}"
    sliced = {int(m.group(1)) for c in campaign["cells"] if c["experiment"] == "05_corpus_breadth"
              for m in [re.search(r"__first(\d+)$", c["cell"])] if m}
    out["corpusRecords"] = listing([f"{n:,}" for n in sorted(sliced)])
    whole = max(scaling["corpus"], key=lambda r: r["triples"])
    out["representationHours"] = f"{(whole['hdt_s'] + whole['cottas_s']) / 3600:.1f}"
    out["wholeHours"] = f"{whole['wall_s'] / 3600:.2f}"

    # Shared-input converter comparison
    outcomes = defaultdict(list)
    for o in conv["outcomes"]:
        outcomes[o["tool"]].append(o["status"] == "PASS")
    names = {t["id"]: t["name"] for t in conv["tools"]}
    out["converters"] = words(len(conv["tools"]) - 1)
    out["converterQuestions"] = words(len(conv["questions"]))
    out["converterRange"] = f"Q1–Q{len(conv['questions'])}"
    out["converterInputs"] = words(len(conv["inputs"]))
    out["converterAllPass"] = listing([names[t] for t, ok in outcomes.items() if all(ok)])

    # Setup amortization: the minimal RDF setup, and the core benchmark's HDT-inclusive one
    be = retrieval["breakEven"]
    out["breakEven"] = f"{be['n_star']:.0f}"
    out["breakEvenWithHdt"] = f"{be['n_star_with_hdt']:.0f}"
    out["breakEvenRange"] = span(list(be["per_question"].values()), 0)
    out["minimalSetup"] = f"{be['setup']:.0f} s"

    # Retrieval
    by_graph = {r["graph"]: r for r in retrieval["costBySize"]}
    engines = retrieval["engines"]
    out["sliceRecords"] = f"{records['rungs'][1]:,}"
    out["sliceTriples"] = millions(by_graph["large"]["triples"])
    out["fixtureTriples"] = millions(by_graph["small"]["triples"])
    out["midTriples"] = millions(by_graph["r1000000"]["triples"])
    out["maxTriples"] = millions(by_graph["whole"]["triples"])
    out["perMillion"] = span([r["perMillion"] for r in retrieval["costBySize"]], 2)
    out["qleverIndex"] = f"{retrieval['batch']['setup']:.1f} s"
    out["engineRuns"] = words(engines["qlever"]["runs"])
    out["engineArtifacts"] = words(len(retrieval["artifacts"]))
    out["engineReplicates"] = words(engines["qlever"]["runs"] // len(retrieval["artifacts"]))
    out["engineFold"] = span([e["mean"] / engines["qlever"]["mean"] for k, e in engines.items() if k != "qlever"], 0)
    scale_cells = retrieval["scaleComparison"]["cells"]
    out["scaleQleverRuns"] = listing(sorted({words(c["replicates"]) for c in scale_cells if c["engine"] == "qlever" and c["replicates"]}))
    out["scaleNativeRuns"] = listing(sorted({words(c["replicates"]) for c in scale_cells if c["engine"] != "qlever" and c["replicates"]}))
    out["scaleNativeHeapMb"] = listing(sorted({f"{r['nodeHeapMb']:,}" for c in scale_cells if c["engine"] != "qlever" for r in c["runs"]}))
    rows = retrieval["scale"]["rows"]
    per_artifact = defaultdict(float)
    for r in rows:
        if r["scale"] == "whole" and r["engine"] == "qlever":
            per_artifact[r["artifact"]] += r["seconds"]
    out["artifactSpread"] = f"{100 * (max(per_artifact.values()) / min(per_artifact.values()) - 1):.1f}%"
    in_place = Counter((r["engine"], r["status"] == "PASS") for r in rows
                       if r["scale"] == "r1000000" and r["engine"] != "qlever")
    failed = {n for (_, ok), n in in_place.items() if not ok}
    out["inPlaceFailed"] = listing([words(n) for n in sorted(failed)])
    answered = {n for (_, ok), n in in_place.items() if ok}
    out["nativeAnswered"] = listing([words(n) for n in sorted(answered)])
    out["nativeHdtAnswered"] = words(in_place[("hdt", True)])
    out["nativeCottasAnswered"] = words(in_place[("cottas", True)])
    regional = retrieval["regional"]
    first = next(iter(regional.values()))
    out["regionalQuestions"] = words(first["questions"])
    out["regionalWindows"] = words(first["windowsPerSize"])
    out["regionalScanWindows"] = words(first["scanWindowsPerSize"])
    out["regionalReplicates"] = words(first["replicates"])
    out["regionalExecutions"] = f"{sum(g['executions'] for g in regional.values()):,}"
    out["regionalFailures"] = words(sum(g["failures"] for g in regional.values()))
    out["regionalDisagreements"] = words(sum(g["disagreements"] for g in regional.values()))
    return out


# ---------------------------------------------------------------------------
def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def queries() -> dict:
    """Every query with its oracle, as scripts/build_query_catalog.py copied them from the
    pinned VCF-RDFizer tags and this repository; CI has no VCF-RDFizer clone to read."""
    catalog = load(ROOT / "benchmarks" / "query-catalog" / "catalog.json")
    return {"groups": catalog["groups"], "source": rel(ROOT / "benchmarks" / "query-catalog")}


def build(out: Path) -> dict[str, dict]:
    datasets = {
        "campaign": campaign(),
        "fidelity": {"groups": FIDELITY_GROUPS, "validation": validation_counts(),
                     "mutation": mutation_profiles(), "realGenome": real_genome(),
                     "largeGraphs": large_graph_agreement()},
        "scaling": scaling(),
        "retrieval": retrieval(),
        "usecase": usecase(),
        "converters": converters(),
    }
    datasets["facts"] = facts(datasets)
    datasets["queries"] = queries()
    datasets["policies"] = policies()  # fetched when RQ2's policy section opens, like queries.json
    meta = {"builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "repoCommit": git_commit()}
    out.mkdir(parents=True, exist_ok=True)
    for name, data in datasets.items():
        (out / f"{name}.json").write_text(json.dumps({"meta": meta, **data}, indent=1, default=str),
                                          encoding="utf-8")
    return datasets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "site" / "data")
    args = parser.parse_args()
    for name in build(args.out):
        print("wrote", args.out / f"{name}.json")


if __name__ == "__main__":
    main()
