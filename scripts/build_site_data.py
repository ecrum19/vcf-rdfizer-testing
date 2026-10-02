#!/usr/bin/env python3
"""Build the results site's data files from the benchmark archive.

    python3 scripts/build_site_data.py --out site/data

Standard library only, and no network: everything is read from
BioMedSem_2026/benchmark-results and benchmarks/use_case/acmg. Only the reported
results are included -- the live v3.1.0 campaign trees and the unsuffixed
use-case cells; superseded, stalled and failed attempts are left out. The
values behind the paper's figures come from the same module make_figures.py
uses (paper-assets/figures/figure_data.py), so the site and the paper cannot
compute them differently.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import statistics as st
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "BioMedSem_2026" / "paper-assets" / "figures"))
import figure_data as fd  # noqa: E402

RESULTS = fd.RESULTS
USE_CASE = RESULTS / "vcf-bench-1" / "use-case"
USE_CASE_WGS = RESULTS / "vcf-bench-2" / "use-case"
REVIEW = RESULTS / "vcf-bench-2" / "review-runs"
REPO_URL = "https://github.com/ecrum19/vcf-rdfizer-testing"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path | str) -> str:
    return str(Path(path).resolve().relative_to(ROOT))


def live_report_dirs() -> list[Path]:
    """Every validation report in the live campaign trees of both hosts."""
    dirs = []
    for host in ("vcf-bench-1", "vcf-bench-2"):
        pattern = RESULTS / host / "benchmarks_outputs" / "**" / "reports" / "validation" / "*" / "summary.json"
        dirs += [Path(p).parent for p in glob.glob(str(pattern), recursive=True)]
    return sorted(dirs)


# ---------------------------------------------------------------------------
# Campaign
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
            "url": f"{REPO_URL}/tree/main/BioMedSem_2026/benchmark-results/{c['path']}",
        }
        for c in summary["cells"] if c["branch"] == "live"
    ]
    hosts = {}
    for host, by_commit in summary["provenance"].items():
        platform = by_commit.get("d3b34d5", {}).get("platform")
        if platform:
            hosts[host] = platform
    return {
        "harnessCommit": summary["harness_commit"],
        "experiments": [{"experiment": name, **row} for name, row in sorted(experiments.items())],
        "cells": cells,
        "hosts": hosts,
        "totals": {
            "cells": len(cells),
            "hours": round(sum(row["wall_hours"] for row in experiments.values()), 2),
            "byStatus": dict(Counter(c["status"] for c in cells)),
        },
    }


# ---------------------------------------------------------------------------
# Fidelity
# ---------------------------------------------------------------------------
def validation_counts() -> dict:
    """Pass/total for every layer of the campaign's validation evidence."""
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
            shacl.append(summary["shacl"])
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
    """The paired validation of NG131FQA1I's first 250,000 records (review run)."""
    run = REVIEW / "validate__NG131FQA1I__first250000__noshacl"
    report = Path(glob.glob(str(run / "out" / "run_metrics" / "*" / "reports" / "validation"
                                / "NG131FQA1I_first250000"))[0])
    comparison = load(report / "comparison.json")
    rapper = load(report / "rdf-validation.json")
    diagnosis = (REVIEW / "diag_q11b.out").read_text(encoding="utf-8")
    return {
        "triples": rapper["tripleCount"],
        "queries": [{"query": q, "status": r["status"]} for q, r in sorted(comparison["queries"].items())],
        "qualDiagnosis": diagnosis.strip().splitlines(),
        "source": rel(report),
    }


# ---------------------------------------------------------------------------
# Conversion cost
# ---------------------------------------------------------------------------
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
                    "wholeFileRecords": fd.HG005_WHOLE_RECORDS},
        "storage": storage,
        "samples": fd.sample_ladder(),
        "corpus": fd.corpus_rows(),
    }


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
def regional() -> dict:
    """Median over questions of each question's median per arm and window size."""
    out = {}
    for graph in ("small", "slice"):
        path = RESULTS / "vcf-bench-1" / "benchmarks_outputs" / "14_regional_access" / graph / "out" / "regional.csv"
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
        setup = load(path.with_name("regional.json")).get("setup") or {}
        out[graph] = {
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
    path = RESULTS / "vcf-bench-3" / "benchmarks_outputs" / "16_scale_retrieval" / "retrieval.csv"
    rows = []
    for row in fd.tidy(path):
        rows.append({
            "scale": row["scale"], "engine": row["engine"], "artifact": row["artifact"],
            "query": row["query_id"], "status": row["statuses"],
            "seconds": float(row["median_query_seconds"]) if row["median_query_seconds"] else None,
            "setup": float(row["median_setup_seconds"]) if row["median_setup_seconds"] else None,
        })
    return {"rows": rows, "source": rel(path)}


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
        "costBySize": qlever_cost_by_size(),
    }


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------
ARMS = {
    "arm1": USE_CASE / "17_use_case_acmg",
    "arm2": USE_CASE / "17_use_case_acmg__cohort",
    "arm3": USE_CASE_WGS / "17_use_case_acmg__wgs",
}


def reported_cells(arm: Path, prefix: str) -> list[Path]:
    """The cells the paper reports: unsuffixed, so not __phase1, __failed_* or __before_*."""
    return [p for p in sorted(arm.glob(f"{prefix}__*")) if p.is_dir() and "__" not in p.name[len(prefix) + 2:]]


def wall(cells: list[Path]) -> float:
    return sum(load(c / "bench.json")["wrapper_wall_seconds"] for c in cells if (c / "bench.json").exists())


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
            "source": rel(arm),
        }
    effort = ROOT / "benchmarks" / "use_case" / "acmg" / "effort.json"
    return {"arms": arms, "effort": load(effort)}


# ---------------------------------------------------------------------------
def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build(out: Path) -> dict[str, dict]:
    datasets = {
        "campaign": campaign(),
        "fidelity": {"validation": validation_counts(), "mutation": mutation_profiles(),
                     "realGenome": real_genome()},
        "scaling": scaling(),
        "retrieval": retrieval(),
        "usecase": usecase(),
    }
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
