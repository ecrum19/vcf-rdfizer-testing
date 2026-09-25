#!/usr/bin/env python3
"""Collect one experiment's runs into a tidy table.

Reads, per cell directory under ``results/<experiment>/``:

* ``bench.json``     — the wrapper record written by ``bm_run`` (exit code,
  wall time, peak host workspace, tool commit, exact argv)
* ``out/run_metrics/*/metrics.csv``  — the tool's own per-output metrics
* ``out/run_metrics/*/summary.json`` — final status and the validation index
* ``out/run_metrics/*/stages/partitioned/*.json`` — the partitioned stage's own
  workspace samples, which are the Docker-volume footprint and a DIFFERENT
  number from the host peak in ``bench.json``. Never add them.

Configuration factors come from the recorded argv rather than from the cell
label, so a renamed cell cannot silently change what a row claims to be.

Writes ``results/<experiment>/tidy.csv`` and ``tidy.json``.

Usage:
    python3 collect_metrics.py <experiment> [--results DIR] [--quiet]
    python3 collect_metrics.py --all
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys

def default_results_root() -> pathlib.Path:
    """Results root: $BM_RESULTS if set, else ../results.

    The shell side honours BM_RESULTS everywhere; without this the analysis
    looked only in benchmarks/results, so a run directed elsewhere ended with
    run_all.sh's closing collect_metrics step failing and no tidy dataset.
    """
    env = os.environ.get("BM_RESULTS")
    if env:
        return pathlib.Path(env)
    return pathlib.Path(__file__).resolve().parent.parent / "results"


# Factors we lift out of the recorded command line. Anything absent is None,
# which for a defaulted flag means "not pinned in this run" — worth seeing.
FACTOR_FLAGS = {
    "--mode": "mode",
    "--sample-representation": "sample_representation",
    "--info-representation": "info_representation",
    "--header-representation": "header_representation",
    "--rdf-storage-mode": "rdf_storage_mode",
    "--hdt-strategy": "hdt_strategy",
    "--representations": "representations",
    "--rdf-compression": "rdf_compression",
    "--artifact-compression": "artifact_compression",
    "--vcf-version": "vcf_version_requested",
    "--spark-partitions": "spark_partitions",
    "--validation-engine": "validation_engine",
    "--chunk-target-bytes": "chunk_target_bytes",
    "--chunk-min-bytes": "chunk_min_bytes",
    "--chunk-max-bytes": "chunk_max_bytes",
}

# Numeric columns lifted from the tool's metrics.csv.
METRIC_COLUMNS = [
    "output_triples",
    "wall_seconds_java",
    "user_seconds_java",
    "sys_seconds_java",
    "max_rss_kb_java",
    "input_vcf_size_bytes",
    "output_dir_size_bytes",
    "exit_code_java",
    "vcf_version",
    "vcf_version_source",
    "combined_rdf_size_bytes",
]


def factors_from_argv(argv: list[str]) -> dict:
    """Lift configuration factors out of the exact recorded command line."""
    out = {name: None for name in FACTOR_FLAGS.values()}
    out["input"] = None
    for index, token in enumerate(argv):
        if token in FACTOR_FLAGS and index + 1 < len(argv):
            out[FACTOR_FLAGS[token]] = argv[index + 1]
        elif token in ("--input", "--rdf", "--compressed-input", "--hdt", "--cottas") \
                and index + 1 < len(argv):
            if out["input"] is None:
                out["input"] = pathlib.Path(argv[index + 1]).name
    out["validate_requested"] = "--validate" in argv
    return out


def newest_metrics_dir(out_dir: pathlib.Path) -> pathlib.Path | None:
    """The run_metrics directory for this cell. One cell is one run."""
    root = out_dir / "run_metrics"
    if not root.is_dir():
        return None
    candidates = [p for p in root.iterdir() if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_tool_metrics(metrics_dir: pathlib.Path) -> dict:
    """One row per cell. Multi-output runs are summed for triples and sizes."""
    path = metrics_dir / "metrics.csv"
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {}
    merged: dict = {}
    for column in METRIC_COLUMNS:
        values = [r.get(column) for r in rows if r.get(column) not in (None, "")]
        if not values:
            continue
        # Sum the additive ones, take the max of the peaks, keep strings as-is.
        if column in ("output_triples", "input_vcf_size_bytes",
                      "output_dir_size_bytes", "combined_rdf_size_bytes"):
            merged[column] = sum(int(float(v)) for v in values)
        elif column in ("wall_seconds_java", "user_seconds_java", "sys_seconds_java"):
            merged[column] = sum(float(v) for v in values)
        elif column == "max_rss_kb_java":
            merged[column] = max(int(float(v)) for v in values)
        elif column == "exit_code_java":
            merged[column] = max(int(float(v)) for v in values)
        else:
            merged[column] = values[0]
    merged["metrics_rows"] = len(rows)
    return merged


def read_summary(metrics_dir: pathlib.Path) -> dict:
    path = metrics_dir / "summary.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"summary_unreadable": True}
    out: dict = {"tool_status": data.get("status")}
    validation = data.get("validation") or []
    if validation:
        out["validation_targets"] = len(validation)
        statuses = [v.get("status") for v in validation]
        out["validation_status"] = (
            "PASS" if statuses and all(s == "PASS" for s in statuses)
            else ",".join(sorted({s or "?" for s in statuses}))
        )
        engines = sorted({e for v in validation for e in (v.get("engines") or [])})
        out["validation_engines"] = ",".join(engines)
        out["validation_wall_seconds"] = sum(
            float(v.get("wall_seconds") or 0) for v in validation
        )
    return out


def read_query_cost(metrics_dir: pathlib.Path) -> dict:
    """Lift the SPARQL-vs-parser timings out of each validation benchmark.json.

    The validation suite computes every expected value twice — once by parsing
    the VCF with cyvcf2, once by querying the graph — so every validated run is
    already a like-for-like measurement of a SPARQL engine against a
    purpose-built parser on identical work.

    ONE THING TO GET RIGHT: the oracle timing is a WHOLE-RUN TOTAL, split into
    parse and census. There is no per-query oracle number. benchmark.csv repeats
    that total on every row purely so the file needs no join, so comparing a
    row's ``wall_seconds`` against its ``oracle_wall_seconds`` compares one
    query against ALL queries. The only valid comparison is aggregate against
    aggregate, which is what is collected here.
    """
    summary_path = metrics_dir / "summary.json"
    if not summary_path.is_file():
        return {}
    try:
        summary = json.loads(summary_path.read_text())
    except json.JSONDecodeError:
        return {}

    out: dict = {}
    engine_query: dict[str, float] = {}
    engine_setup: dict[str, float] = {}
    oracle_total = oracle_parse = oracle_census = None
    query_count = None
    benchmark_csvs: list[str] = []

    for entry in summary.get("validation") or []:
        # The summary indexes the reports; the docs say to start here rather
        # than globbing, because a non-aggregate target is suffixed.
        rel = entry.get("benchmark_csv")
        if not rel:
            continue
        benchmark_path = (metrics_dir / rel).with_name("benchmark.json")
        if not benchmark_path.is_file():
            continue
        try:
            benchmark = json.loads(benchmark_path.read_text())
        except json.JSONDecodeError:
            continue

        oracle = benchmark.get("oracle") or {}
        if oracle.get("totalSeconds") is not None:
            oracle_total = float(oracle["totalSeconds"])
            oracle_parse = oracle.get("vcfParseSeconds")
            oracle_census = oracle.get("censusSeconds")
        query_count = len(benchmark.get("queryIds") or []) or query_count

        phases = oracle.get("phases") or {}
        for name, value in phases.items():
            if value is not None:
                out[f"oracle_phase__{name}"] = value
        if oracle.get("perQuerySeconds"):
            # The per-query CSV is the join target for the per-query view; note
            # its path rather than flattening 27 columns into this row.
            benchmark_csvs.append(str(benchmark_path.with_name("benchmark.csv")))
            out["oracle_per_query_available"] = True

        for name, engine in (benchmark.get("engines") or {}).items():
            if engine.get("querySeconds") is not None:
                engine_query[name] = engine_query.get(name, 0.0) + float(engine["querySeconds"])
            if engine.get("setupSeconds") is not None:
                engine_setup[name] = max(engine_setup.get(name, 0.0),
                                         float(engine["setupSeconds"]))

    if oracle_total is None and not engine_query:
        return {}

    out["query_count"] = query_count
    out["benchmark_csvs"] = ";".join(benchmark_csvs) or None
    out["oracle_total_seconds"] = oracle_total
    out["oracle_parse_seconds"] = oracle_parse
    out["oracle_census_seconds"] = oracle_census
    for name, value in engine_query.items():
        out[f"engine_query_seconds__{name}"] = value
    for name, value in engine_setup.items():
        out[f"engine_setup_seconds__{name}"] = value
    return out


def read_regional(cell_dir: pathlib.Path) -> dict:
    """Lift the regional-access run's own report out of the cell.

    14_regional_access does not drive the wrapper, so there is no run_metrics
    tree to read: the regional runner writes regional.json / regional.csv
    straight into the cell's out/ directory. The per-execution rows stay in the
    CSV -- there are thousands of them -- and this records the path plus the
    headline facts a cell-level row can carry.
    """
    report = cell_dir / "out" / "regional.json"
    if not report.is_file():
        return {}
    try:
        data = json.loads(report.read_text())
    except json.JSONDecodeError:
        return {"regional_report_unreadable": True}

    out: dict = {
        "regional_csv": str(cell_dir / "out" / "regional.csv"),
        "regional_report": str(report),
        "regional_windows": str(cell_dir / "out" / "windows.json"),
        "regional_executions": data.get("executions"),
        "regional_failures": data.get("failures"),
        "regional_disagreements": data.get("disagreements"),
        "regional_arms": ",".join(data.get("arms") or []),
        "regional_window_count": data.get("windowCount"),
        "regional_replicates": data.get("replicates"),
        "input": pathlib.Path(data.get("vcf") or "").name or None,
    }
    setup = data.get("setup") or {}
    index = setup.get("vcfIndex") or {}
    if index:
        out["vcf_bgzip_seconds"] = index.get("bgzipSeconds")
        out["vcf_index_seconds"] = index.get("indexSeconds")
        out["vcf_index_kind"] = index.get("indexKind")
        out["vcf_index_bytes"] = index.get("indexBytes")
        out["vcf_indexed_bytes"] = index.get("bgzipBytes")
    for engine, seconds in (setup.get("engineSetupSeconds") or {}).items():
        out[f"engine_setup_seconds__{engine}"] = seconds
    if setup.get("engineErrors"):
        out["regional_engine_errors"] = ";".join(
            f"{name}: {message}" for name, message in setup["engineErrors"].items()
        )
    return out


def read_partitioned_workspace(metrics_dir: pathlib.Path) -> dict:
    """Peak Docker-VOLUME workspace, and the build breakdown beside it.

    This is not the host peak in bench.json. The partitioned stage runs in an
    ephemeral Docker volume that `du` on the output tree cannot see, so the two
    numbers measure different things and are reported in separate columns. They
    must never be added.

    Read from `build_profile` in the compression-operations record, which sizes
    the /work TREE. The older free-space path below computed `total - free` on
    the volume's backing device, which is the whole host disk: on a build whose
    scratch was one 11.9 MB chunk it read 126,956,531,712 bytes. That figure
    never reached a dataset only because the sample arrays it wanted were never
    written. It is kept solely as a fallback for archives that do carry them,
    and flagged when used, because it is not a measurement of this build.
    """
    operations_dir = metrics_dir / "stages" / "compression_operations"
    if operations_dir.is_dir():
        for path in sorted(operations_dir.rglob("partitioned_compression.json")):
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
            profile = data.get("build_profile") or {}
            if not profile:
                continue
            out = {
                "peak_volume_workspace_bytes": profile.get("peak_volume_workspace_bytes"),
                "peak_volume_workspace_source": "build_profile_tree",
                # The shared pass: one decompress-and-chunk feeds every
                # representation, so this is charged to neither method's total.
                "chunk_stream_seconds": profile.get("chunk_stream_seconds"),
                "chunk_count": profile.get("chunk_count"),
                "chunk_input_bytes": profile.get("chunk_input_bytes"),
                "build_max_rss_kb": profile.get("max_rss_kb"),
            }
            for kind, bucket in (profile.get("by_stage_kind") or {}).items():
                key = kind.replace("-", "_")
                out[f"build_seconds__{key}"] = bucket.get("wall_seconds")
                out[f"build_stages__{key}"] = bucket.get("stage_count")
            for prefix, rounds in (profile.get("merge_rounds") or {}).items():
                out[f"merge_rounds__{prefix}"] = rounds
            return {key: value for key, value in out.items() if value is not None}

    stage_dir = metrics_dir / "stages" / "partitioned"
    if not stage_dir.is_dir():
        return {}
    peak_used = None
    for path in sorted(stage_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        samples = data.get("workspace_free_space_samples") or data.get("workspace_samples") or []
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            used = sample.get("used_bytes")
            if used is None:
                total, free = sample.get("total_bytes"), sample.get("free_bytes")
                if total is not None and free is not None:
                    used = total - free
            if used is not None:
                peak_used = used if peak_used is None else max(peak_used, used)
    if peak_used is None:
        return {}
    return {
        "peak_volume_workspace_bytes": peak_used,
        # Device-level, not this build's footprint. Do not report it as one.
        "peak_volume_workspace_source": "device_free_space_legacy",
    }


def collect_cell(cell_dir: pathlib.Path) -> dict | None:
    bench_path = cell_dir / "bench.json"
    if not bench_path.is_file():
        return None
    try:
        bench = json.loads(bench_path.read_text())
    except json.JSONDecodeError:
        return {"cell": cell_dir.name, "error": "bench.json unreadable"}

    row: dict = {
        "cell": bench.get("cell", cell_dir.name),
        "experiment": bench.get("experiment"),
        "skipped": bool(bench.get("skipped")),
        "skip_reason": bench.get("reason"),
        "exit_code": bench.get("exit_code"),
        "wrapper_wall_seconds": bench.get("wrapper_wall_seconds"),
        "peak_host_out_tree_bytes": bench.get("peak_out_tree_bytes"),
        "final_out_tree_bytes": bench.get("final_out_tree_bytes"),
        "tool_commit": bench.get("tool_commit"),
        "memory_ceiling_requested": bench.get("memory_ceiling_requested"),
        "config": bench.get("config"),
    }
    if row["skipped"]:
        return row

    row.update(factors_from_argv(bench.get("command") or []))

    # 14_regional_access writes its own report instead of a run_metrics tree.
    row.update(read_regional(cell_dir))

    metrics_dir = newest_metrics_dir(cell_dir / "out")
    if metrics_dir is not None:
        row["run_metrics_dir"] = str(metrics_dir.relative_to(cell_dir))
        row.update(read_tool_metrics(metrics_dir))
        row.update(read_summary(metrics_dir))
        row.update(read_partitioned_workspace(metrics_dir))
        row.update(read_query_cost(metrics_dir))

    # Derived quantities. Guarded so a failed run does not produce a ratio.
    triples = row.get("output_triples")
    wall = row.get("wall_seconds_java") or row.get("wrapper_wall_seconds")
    if triples and wall:
        row["triples_per_second"] = triples / wall
        row["seconds_per_mtriple"] = (wall / triples) * 1e6
    input_bytes = row.get("input_vcf_size_bytes")
    if triples and input_bytes:
        row["triples_per_input_byte"] = triples / input_bytes
    if row.get("peak_host_out_tree_bytes") and input_bytes:
        row["peak_host_workspace_ratio"] = row["peak_host_out_tree_bytes"] / input_bytes
    if row.get("final_out_tree_bytes") and triples:
        row["bytes_per_triple"] = row["final_out_tree_bytes"] / triples
    return row


def collect_experiment(results: pathlib.Path, experiment: str, quiet: bool = False) -> list[dict]:
    exp_dir = results / experiment
    if not exp_dir.is_dir():
        raise SystemExit(f"no such experiment directory: {exp_dir}")
    rows = []
    for cell_dir in sorted(p for p in exp_dir.iterdir() if p.is_dir()):
        row = collect_cell(cell_dir)
        if row is not None:
            rows.append(row)
    if not rows:
        raise SystemExit(f"no cells with a bench.json under {exp_dir}")

    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)

    csv_path = exp_dir / "tidy.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    (exp_dir / "tidy.json").write_text(json.dumps(rows, indent=2) + "\n")

    if not quiet:
        ok = sum(1 for r in rows if r.get("exit_code") == 0)
        skipped = sum(1 for r in rows if r.get("skipped"))
        failed = len(rows) - ok - skipped
        print(f"{experiment}: {len(rows)} cells — {ok} ok, {failed} non-zero, {skipped} skipped")
        print(f"  {csv_path}")
        if failed:
            for row in rows:
                if not row.get("skipped") and row.get("exit_code") != 0:
                    print(f"  exit {row.get('exit_code')}: {row['cell']}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment", nargs="?", help="experiment directory name")
    parser.add_argument("--all", action="store_true", help="collect every experiment present")
    parser.add_argument("--results", default=None, help="results root (default: ../results)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    results = pathlib.Path(args.results) if args.results \
        else default_results_root()
    if not results.is_dir():
        raise SystemExit(f"results root not found: {results}\nRun an experiment script first.")

    if args.all:
        names = sorted(p.name for p in results.iterdir()
                       if p.is_dir() and p.name != "00_environment")
        if not names:
            raise SystemExit(f"no experiments under {results}")
        for name in names:
            try:
                collect_experiment(results, name, args.quiet)
            except SystemExit as exc:
                print(f"{name}: {exc}", file=sys.stderr)
        return 0

    if not args.experiment:
        parser.error("give an experiment name, or --all")
    collect_experiment(results, args.experiment, args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
