"""The values behind the manuscript's data figures, read from the archive.

Standard library only, so both make_figures.py (the paper's PDFs) and the
results site (scripts/build_site_data.py) compute every plotted value the same
way. Every number is read from BioMedSem_2026/benchmark-results, never typed in.
"""

from __future__ import annotations

import csv
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent.parent / "benchmark-results"
B1 = RESULTS / "vcf-bench-1" / "benchmarks_outputs"
B2 = RESULTS / "vcf-bench-2" / "benchmarks_outputs"

# Records in the whole HG005_GRCh38 file (the archive does not record it;
# counted with `zcat | grep -vc '^#'` on vcf-bench-1).
HG005_WHOLE_RECORDS = 3_856_856

QUERIES = [
    ("q01_record_density_1mb", "Q1 Record density"),
    ("q02_variant_shape_counts", "Q2 Allele shapes"),
    ("q03_titv", "Q3 Ti/Tv"),
    ("q04_filter_distribution", "Q4 FILTER states"),
    ("q05_sample_genotype_counts", "Q5 Genotype classes"),
    ("q06_ac_an_distribution", "Q6 AC/AN"),
    ("q07_file_metadata", "Q7 File metadata"),
    ("q08_header_line_census", "Q8 Header census"),
    ("q09_predicate_census", "Q9 Predicate census"),
    ("q10_class_census", "Q10 Class census"),
    ("q11_record_digest", "Q11 Record digest"),
    ("q12_info_value_digest", "Q12 INFO digest"),
    ("q13_format_value_digest", "Q13 FORMAT digest"),
]
QIDS = {q for q, _ in QUERIES}

# Dataset name as the run records it -> the paper's short label.
SHORT_NAMES = {
    "0GOOR_HG002_first250000": "HG002",
    "HG004_GRCh38_first250000": "HG004",
    "HG005_GRCh38": "HG005 (whole)",
    "HGSVC2_first250000": "HGSVC2",
}


def tidy(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summary() -> dict:
    return json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))


def records_ladder() -> dict:
    """Per-rung replicate values and medians for the HG005 records ladder."""
    records = defaultdict(lambda: defaultdict(list))
    for row in tidy(B1 / "04_scaling_records" / "tidy.csv"):
        rung = row["cell"].split("__")[0]
        n = HG005_WHOLE_RECORDS if rung == "rfull" else int(rung[1:])
        records[n]["triples"].append(float(row["output_triples"]))
        records[n]["wall"].append(float(row["wrapper_wall_seconds"]))
        records[n]["disk"].append(float(row["peak_host_out_tree_bytes"]))
        records[n]["rss"].append(float(row["max_rss_kb_java"]))
    rungs = sorted(records)
    med = {k: [st.median(records[n][k]) for n in rungs] for k in ("triples", "wall", "disk", "rss")}
    return {"rungs": rungs, "median": med, "runs": {n: dict(records[n]) for n in rungs}}


def storage_modes() -> dict:
    """(peak bytes, wall seconds, triples) per input and storage mode."""
    storage = defaultdict(lambda: defaultdict(list))
    for row in tidy(B1 / "01_storage_mode" / "tidy.csv"):
        key = "slice" if row["cell"].startswith("HG005") else "larger"
        storage[key][row["rdf_storage_mode"]].append(
            (float(row["peak_host_out_tree_bytes"]), float(row["wrapper_wall_seconds"]),
             float(row["output_triples"])))
    return {key: dict(modes) for key, modes in storage.items()}


def sample_ladder() -> dict:
    """Median triples and stored bytes per (profile, sample count)."""
    raw = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for cell in summary()["cells"]:
        if cell["experiment"] != "03_sample_representation" or cell["branch"] != "live":
            continue
        if not cell["cell"].startswith("s") or not cell.get("runs"):
            continue
        n = int(cell["cell"].split("__")[0][1:])
        profile = cell["cell"].split("__")[1]
        d = cell["runs"][0]["datasets"][0]
        for key, field in (("triples", "total_triples"), ("nt", "rdf_size_bytes"),
                           ("hdt", "hdt_size_bytes"), ("cottas", "cottas_size_bytes"),
                           ("vcf", "input_vcf_size_bytes")):
            if d.get(field) is not None:  # COTTAS only where the cell built it
                raw[profile][key][n].append(float(d[field]))
    ladder = {}
    for profile, keys in raw.items():
        xs = sorted(keys["triples"])
        ladder[profile] = {"x": xs, **{k: [st.median(keys[k][n]) for n in xs]
                                       for k in keys if all(keys[k][n] for n in xs)}}
    return ladder


def corpus_rows() -> list[dict]:
    rows = []
    for cell in summary()["cells"]:
        if cell["experiment"] != "05_corpus_breadth" or cell["branch"] != "live":
            continue
        if not cell.get("runs"):
            continue
        d = cell["runs"][0]["datasets"][0]
        name = SHORT_NAMES.get(d["dataset"], d["dataset"].replace("_first250000", ""))
        rows.append({
            "name": name,
            "triples": d["hdt_validation_source_triples"],
            "nt": d["rdf_size_bytes"], "hdt": d["hdt_size_bytes"], "cottas": d["cottas_size_bytes"],
            "hdt_s": d["hdt_wall_seconds"], "cottas_s": d["cottas_wall_seconds"],
            "wall_s": cell["wrapper_wall_seconds"],
        })
    return sorted(rows, key=lambda r: r["triples"])


def benchmark_rows(scale: str):
    """Yield (replicate, target, row) for every benchmark.csv of one scale."""
    for rep_dir in sorted((B1 / "13_query_cost").glob(f"{scale}__r*")):
        for path in rep_dir.glob("out/run_metrics/*/reports/validation/*/benchmark.csv"):
            target = path.parent.name.rsplit("__", 1)[-1] if "__" in path.parent.name else "nt"
            for row in tidy(path):
                yield rep_dir.name, target, row


def retrieval() -> dict:
    """Per-question, batch and per-engine timings of 13_query_cost."""
    engine_q = defaultdict(list)
    oracle_q = defaultdict(list)
    batch = defaultdict(lambda: defaultdict(float))  # (rep, target) -> engine -> seconds
    setup = defaultdict(list)
    oracle_wall = []
    seen = set()
    for rep, target, row in benchmark_rows("large"):
        if row["query_id"] not in QIDS or row["status"] != "PASS":
            continue
        key = (rep, target, row["engine"], row["query_id"])
        if key in seen:
            continue
        seen.add(key)
        if target == "nt":
            engine_q[row["query_id"]].append(float(row["wall_seconds"]))
        # The parser does not depend on which artifact is being validated, so
        # every validation of a replicate is a replicate of the same scan.
        oracle_q[row["query_id"]].append(float(row["oracle_query_seconds"]))
        oracle_wall.append(float(row["oracle_wall_seconds"]))
        batch[(rep, target)][row["engine"]] += float(row["wall_seconds"])
        setup[(target, row["engine"])].append(float(row["engine_setup_seconds"]))
    per_target = defaultdict(list)
    for (rep, target), engines in batch.items():
        per_target[target].append(engines["qlever"])

    small = defaultdict(lambda: defaultdict(float))
    small_setup = defaultdict(list)
    seen = set()
    for rep, target, row in benchmark_rows("small"):
        if row["query_id"] not in QIDS or row["status"] != "PASS":
            continue
        key = (rep, target, row["engine"], row["query_id"])
        if key in seen:
            continue
        seen.add(key)
        small[(rep, target)][row["engine"]] += float(row["wall_seconds"])
        small_setup[row["engine"]].append(float(row["engine_setup_seconds"]))
    engine_runs = defaultdict(list)
    for engines in small.values():
        for engine, seconds in engines.items():
            engine_runs[engine].append(seconds)

    return {
        "engine_q": dict(engine_q), "oracle_q": dict(oracle_q),
        "ql_batch": st.mean(per_target["nt"]),
        "ql_setup": st.mean(setup[("nt", "qlever")]),
        "parser_batch": st.mean(oracle_wall),
        "per_target": dict(per_target), "setup": dict(setup),
        "engine_runs": dict(engine_runs), "small_setup": dict(small_setup),
    }
