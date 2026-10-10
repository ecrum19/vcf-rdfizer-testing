#!/usr/bin/env python3
"""Build the results site's data files from the benchmark archive.

    python3 scripts/build_site_data.py --out site/data

Standard library only, and no network: everything is read from
benchmark-results/ and benchmarks/use_case/acmg. Only the reported
results are included -- the live v3.1.0 campaign trees and the v3.3.1 rerun's
unsuffixed cells; superseded, stalled and failed attempts are left out. The
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import figure_data as fd  # noqa: E402

RESULTS = fd.RESULTS
REVIEW = RESULTS / "vcf-bench-2" / "review-runs"
#: The rerun with the published v3.3.1 of every result a pre-release build first produced, per host.
#: The use-case arms, regional and large-graph retrieval, and the consumer WGS validation run are
#: read from here; the v3.1.0 campaign and the v3.1.0 review run are not rerun.
V331 = {host: RESULTS / host / "v331-rerun" / "results" for host in ("vcf-bench-1", "vcf-bench-2", "vcf-bench-3")}
ACMG = ROOT / "benchmarks" / "use_case" / "acmg"
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
            "url": f"{REPO_URL}/tree/main/benchmark-results/{c['path']}",
        }
        for c in summary["cells"] if c["branch"] == "live"
    ]
    hosts = {}
    for host, by_commit in summary["provenance"].items():
        platform = by_commit.get("d3b34d5", {}).get("platform")
        if platform:
            hosts[host] = platform
    return {
        "image": next(ref for ref in summary["integrity"]["image_refs"] if ref != "?"),
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


def review_report(run: str, root: Path = REVIEW) -> Path:
    """The validation report directory of one run on NG131FQA1I's first 250,000 records."""
    return Path(glob.glob(str(root / run / "out" / "run_metrics" / "*" / "reports" / "validation"
                              / "NG131FQA1I_first250000"))[0])


def real_genome() -> dict:
    """The paired validation of NG131FQA1I's first 250,000 records.

    The v3.1.0 review run (no shapes) is the diagnosis; the published v3.3.1's
    run, default shapes batched, is the current result.
    """
    report = review_report("validate__NG131FQA1I__first250000__noshacl")
    rerun = review_report("consumer_wgs__NG131FQA1I__first250000", V331["vcf-bench-2"])
    comparison = load(report / "comparison.json")
    shacl = load(rerun / "shacl.json")
    rapper = load(report / "rdf-validation.json")
    diagnosis = (REVIEW / "diag_q11b.out").read_text(encoding="utf-8")
    # One line per QUAL rendering: how many values it changes, and how many
    # digest buckets then still differ from QLever's.
    qual = {line.split("QUAL")[0].strip(): [int(n) for n in re.findall(r":\s+(\d+)", line)]
            for line in diagnosis.splitlines() if "QUAL" in line}
    sample, records = re.fullmatch(r"(.+)_first(\d+)", report.name).groups()
    phase_sets = sum(row["resourceCount"] for row in comparison["queries"]["q10_class_census"]["extraRows"]
                     if row["class"].endswith("#PhaseSet"))
    return {
        "sample": sample, "records": int(records),
        "triples": rapper["tripleCount"],
        "phaseSets": phase_sets,
        "qual": {"changed": qual["trailing zeros stripped"][0],
                 "differAsWritten": qual["as written"][1],
                 "differStripped": qual["trailing zeros stripped"][1]},
        "queries": [{"query": q, "status": r["status"]} for q, r in sorted(comparison["queries"].items())],
        "qualDiagnosis": diagnosis.strip().splitlines(),
        "source": rel(report),
        "rerun": {
            "triples": load(rerun / "rdf-validation.json")["tripleCount"],
            "queries": [{"query": q, "status": r["status"]}
                        for q, r in sorted(load(rerun / "comparison.json")["queries"].items())],
            "shacl": {"status": shacl["status"], "violations": shacl["violationCount"],
                      "advisories": shacl["advisoryCount"], "batches": shacl["batches"],
                      "workers": shacl["workers"], "minutes": round(shacl["wallSeconds"] / 60)},
            "source": rel(rerun),
        },
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
    "arm1": V331["vcf-bench-1"] / "17_use_case_acmg",
    "arm2": V331["vcf-bench-1"] / "17_use_case_acmg__cohort",
    "arm3": V331["vcf-bench-2"] / "17_use_case_acmg__wgs",
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
    campaign, fidelity, scaling, retrieval, usecase = (
        d[k] for k in ("campaign", "fidelity", "scaling", "retrieval", "usecase"))
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
    out["phaseSets"] = f"{real['phaseSets']:,}"
    out["qualChanged"] = f"{real['qual']['changed']:,}"
    out["qualDiffer"] = f"{real['qual']['differAsWritten']:,}"

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


def build(out: Path) -> dict[str, dict]:
    datasets = {
        "campaign": campaign(),
        "fidelity": {"validation": validation_counts(), "mutation": mutation_profiles(),
                     "realGenome": real_genome()},
        "scaling": scaling(),
        "retrieval": retrieval(),
        "usecase": usecase(),
    }
    datasets["facts"] = facts(datasets)
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
