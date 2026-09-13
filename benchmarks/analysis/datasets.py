#!/usr/bin/env python3
"""Join collected results into structured per-question datasets.

One script, one subcommand per question the plan asks. Each writes a CSV and a
JSON beside the results and prints a compact view to stdout; the files are the
deliverable, the stdout view is only there so you can see it worked.

  corpus       §3.2  stratified breadth rows, normalized by emitted TRIPLES
  equivalence  §4.1  encodings x validation outcome, incl. the mechanism check
  awkward      §4.4  observed behaviour against each fixture's expectation
  feasibility  §4.4  memory ceiling x configuration -> completed / OOM
  coverage     §5.1  re-derive that the covering set actually covers
  querycost    §4.5  SPARQL retrieval vs the cyvcf2 parser, on identical work

Nothing here formats for print. Figures and typeset tables come later, off the
CSV/JSON these produce.

Usage:
    python3 datasets.py corpus 05_corpus_breadth
    python3 datasets.py equivalence 06_equivalence
    python3 datasets.py awkward 09_awkward_inputs
    python3 datasets.py feasibility 10_feasibility
    python3 datasets.py coverage 11_covering_set
"""

from __future__ import annotations

import argparse
import csv
import itertools
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


RESULTS_DEFAULT = default_results_root()


def load_tidy(results: pathlib.Path, experiment: str) -> list[dict]:
    path = results / experiment / "tidy.json"
    if not path.is_file():
        raise SystemExit(f"{path} not found. Run:\n  python3 collect_metrics.py {experiment}")
    return json.loads(path.read_text())


def load_descriptors(results: pathlib.Path) -> dict:
    path = results / "descriptors.json"
    if not path.is_file():
        return {}
    try:
        return {e["file"]: e for e in json.loads(path.read_text())}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def emit(records: list[dict], caption: str, out_stem: pathlib.Path | None,
         *, note: str | None = None) -> None:
    """Write records as CSV + JSON, and print a compact view.

    Records are dicts with stable keys, so the CSV header is the schema and
    downstream code can rely on it. Numbers stay numbers — no thousands
    separators, no units glued on, no em-dashes for missing values. A missing
    value is an empty CSV field and a JSON null, which is what a reader can
    actually filter on.
    """
    if not records:
        print(f"\n{caption}\n  (no rows)")
        return

    columns: list[str] = []
    for record in records:
        for key in record:
            if key not in columns:
                columns.append(key)

    print(f"\n{caption}\n")
    # Compact stdout view: every column, values as-is, aligned.
    def cell(value) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.4g}"
        return str(value)

    widths = {c: max(len(c), *(len(cell(r.get(c))) for r in records)) for c in columns}
    print("  " + "  ".join(c.ljust(widths[c]) for c in columns))
    print("  " + "  ".join("-" * widths[c] for c in columns))
    for record in records:
        print("  " + "  ".join(cell(record.get(c)).ljust(widths[c]) for c in columns))

    if note:
        print(f"\n{note}")

    if out_stem is None:
        return

    csv_path = out_stem.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({c: record.get(c) for c in columns})

    json_path = out_stem.with_suffix(".json")
    json_path.write_text(json.dumps(
        {"caption": caption, "columns": columns, "rows": records}, indent=2) + "\n")

    print(f"\nwrote {csv_path}")
    print(f"wrote {json_path}")


# ---------------------------------------------------------------------------
def cmd_corpus(args, results: pathlib.Path) -> int:
    rows_in = [r for r in load_tidy(results, args.experiment)
               if not r.get("skipped") and r.get("exit_code") == 0]
    descriptors = load_descriptors(results)
    if not descriptors:
        print("note: no descriptors.json — run describe_inputs.py --corpus for the\n"
              "      structural columns. Without them an off-trend cost reads as\n"
              "      noise instead of as explained.", file=sys.stderr)

    records = []
    for row in sorted(rows_in, key=lambda r: (r.get("cell") or "")):
        name = row.get("input")
        desc = descriptors.get(name, {})
        records.append({
            "family": desc.get("family") or (row.get("cell") or "").split("__")[0],
            "file": name,
            "records": desc.get("records_counted"),
            "records_sampled": desc.get("records_truncated_at_limit"),
            "samples": desc.get("samples"),
            "sample_calls": desc.get("sample_calls"),
            "dominant_allele_shape": desc.get("dominant_allele_shape"),
            "multiallelic_records": desc.get("multiallelic_records"),
            "info_keys_used": desc.get("info_keys_used"),
            "format_keys_used": desc.get("format_keys_used"),
            "vcf_version": row.get("vcf_version") or desc.get("fileformat"),
            "vcf_version_source": row.get("vcf_version_source"),
            "triples": row.get("output_triples"),
            "wall_seconds": row.get("wall_seconds_java") or row.get("wrapper_wall_seconds"),
            "seconds_per_mtriple": row.get("seconds_per_mtriple"),
            "bytes_per_triple": row.get("bytes_per_triple"),
            "peak_host_workspace_bytes": row.get("peak_host_out_tree_bytes"),
            "peak_volume_workspace_bytes": row.get("peak_volume_workspace_bytes"),
            "input_vcf_size_bytes": row.get("input_vcf_size_bytes"),
            "max_rss_kb": row.get("max_rss_kb_java"),
        })

    emit(records, "Corpus breadth (§3.2)",
         results / args.experiment / "data_corpus" if not args.no_files else None,
         note=("Cost is normalized by emitted triples, not input bytes: input bytes\n"
               "is exactly what makes a structural-variant callset incomparable.\n"
               "NO cross-family regression is fitted from these rows."))
    return 0


# ---------------------------------------------------------------------------
def cmd_equivalence(args, results: pathlib.Path) -> int:
    rows_in = [r for r in load_tidy(results, args.experiment) if not r.get("skipped")]

    records = []
    for row in sorted(rows_in, key=lambda r: (r.get("cell") or "")):
        cell = row.get("cell") or ""
        records.append({
            "cell": cell,
            "kind": cell.split("__")[0] if "__" in cell else "other",
            "storage": row.get("rdf_storage_mode"),
            "sample_representation": row.get("sample_representation"),
            "hdt_strategy": row.get("hdt_strategy"),
            "representations": row.get("representations"),
            "exit_code": row.get("exit_code"),
            "expected_nonzero": cell.startswith("refusal__"),
            "validation_status": row.get("validation_status"),
            "validation_targets": row.get("validation_targets"),
            "validation_engines": row.get("validation_engines"),
            "validation_wall_seconds": row.get("validation_wall_seconds"),
            "triples": row.get("output_triples"),
        })

    emit(records, "Representation equivalence (§4.1)",
         results / args.experiment / "data_equivalence" if not args.no_files else None,
         note=("Every encoding is validated against a VCF-side oracle computed from\n"
               "the same input (Q1-Q13). Q5 and Q6 traverse the sample layer and are\n"
               "where condensed could have broken."))

    # Two derived verdicts, written as their own small structured file: they are
    # the claims, and they should not have to be re-derived by eye.
    verdicts = {}

    refusals = [r for r in records if r["expected_nonzero"]]
    if refusals:
        verdicts["refusals"] = [{
            "cell": r["cell"], "exit_code": r["exit_code"],
            "as_expected": r["exit_code"] != 0,
        } for r in refusals]
        print("\nRefusal cells (non-zero is the expected result here):")
        for entry in verdicts["refusals"]:
            state = "as expected" if entry["as_expected"] else "UNEXPECTED SUCCESS"
            print(f"  {entry['cell']}: exit {entry['exit_code']} — {state}")

    mechanism = {r["hdt_strategy"]: r for r in records if r["kind"] == "mechanism"}
    if {"single", "partitioned"} <= set(mechanism):
        single, part = mechanism["single"], mechanism["partitioned"]
        identical = single["triples"] == part["triples"]
        verdicts["mechanism_check"] = {
            "single_triples": single["triples"],
            "partitioned_triples": part["triples"],
            "identical": identical,
            "single_validation": single["validation_status"],
            "partitioned_validation": part["validation_status"],
        }
        print(f"\nMechanism check: single {single['triples']} triples vs "
              f"partitioned {part['triples']} — "
              f"{'IDENTICAL' if identical else 'DIFFERENT'}")
        print("  This is what justifies partitioned generation being the default,")
        print("  rather than it merely being convenient.")

    if verdicts and not args.no_files:
        path = results / args.experiment / "data_equivalence_verdicts.json"
        path.write_text(json.dumps(verdicts, indent=2) + "\n")
        print(f"\nwrote {path}")
    return 0


# ---------------------------------------------------------------------------
def cmd_awkward(args, results: pathlib.Path) -> int:
    rows_in = load_tidy(results, args.experiment)
    fixtures_path = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "FIXTURES.json"
    expectations = {}
    if fixtures_path.is_file():
        data = json.loads(fixtures_path.read_text())
        for entry in data.get("fixtures", []):
            if entry.get("expectation"):
                expectations[entry["file"].split(".")[0]] = entry["expectation"]

    records = []
    for row in sorted(rows_in, key=lambda r: (r.get("cell") or "")):
        cell = row.get("cell") or ""
        if not cell.startswith("awkward_"):
            continue
        if row.get("skipped"):
            outcome = "skipped"
        elif row.get("exit_code") == 0:
            outcome = "converted"
        else:
            outcome = "refused"
        records.append({
            "fixture": cell,
            "outcome": outcome,
            "exit_code": row.get("exit_code"),
            "validation_status": row.get("validation_status"),
            "triples": row.get("output_triples"),
            "converted_but_validation_failed": (
                outcome == "converted"
                and row.get("validation_status") not in (None, "PASS")
            ),
            "expectation": expectations.get(cell),
        })

    emit(records, "Awkward inputs (§4.4)",
         results / args.experiment / "data_awkward" if not args.no_files else None,
         note=("Converted and refused-with-a-clear-diagnostic are BOTH acceptable;\n"
               "a crash or a silently wrong graph is not. The column to watch is\n"
               "converted_but_validation_failed — that is the failure mode this\n"
               "experiment exists to catch, and a bare exit code would hide it."))

    flagged = [r for r in records if r["converted_but_validation_failed"]]
    if flagged:
        print("\nFLAGGED — converted but validation did not pass:")
        for record in flagged:
            print(f"  {record['fixture']}: validation={record['validation_status']}")
    return 0


# ---------------------------------------------------------------------------
def cmd_feasibility(args, results: pathlib.Path) -> int:
    rows_in = [r for r in load_tidy(results, args.experiment) if not r.get("skipped")]

    records = []
    for row in sorted(rows_in, key=lambda r: (r.get("cell") or "")):
        code = row.get("exit_code")
        if code == 0:
            outcome = "completed"
        elif code in (-9, 137):
            outcome = "oom_killed"
        else:
            outcome = "failed"
        records.append({
            "config": row.get("config") or (row.get("cell") or "").split("__")[0],
            "memory_ceiling_requested": row.get("memory_ceiling_requested"),
            "ceiling_applied": row.get("ceiling_applied"),
            "outcome": outcome,
            "exit_code": code,
            "wall_seconds": row.get("wall_seconds_java") or row.get("wrapper_wall_seconds"),
            "max_rss_kb": row.get("max_rss_kb_java"),
            "peak_host_workspace_bytes": row.get("peak_host_out_tree_bytes"),
            "peak_volume_workspace_bytes": row.get("peak_volume_workspace_bytes"),
            "triples": row.get("output_triples"),
            "chunk_target_bytes": row.get("chunk_target_bytes"),
            "sample_representation": row.get("sample_representation"),
            "cell": row.get("cell"),
        })

    emit(records, "Feasibility under a memory ceiling (§4.4)",
         results / args.experiment / "data_feasibility" if not args.no_files else None,
         note=("oom_killed (exit -9 / 137) means the OOM-killer intervened — NOT that\n"
               "the RDF is invalid. Check stderr_tail, max_rss_kb and the workspace\n"
               "samples in stages/partitioned/<sample>.json before suspecting the data."))

    unverified = [r for r in records if r["ceiling_applied"] is None]
    if unverified:
        print("\nWARNING: ceiling_applied is unverified on every cell. The ceiling was")
        print("requested via DOCKER_MEMORY/DOCKER_MEMORY_SWAP; confirm the pinned")
        print("release forwards those to its container invocations before reporting")
        print("any of these as a constrained run. An unenforced ceiling makes this")
        print("dataset say nothing.")
    return 0


# ---------------------------------------------------------------------------
COVERING_FACTORS = [
    "sample_representation", "info_representation", "rdf_storage_mode",
    "rdf_compression", "representations", "artifact_compression", "hdt_strategy",
]


def cmd_coverage(args, results: pathlib.Path) -> int:
    """Re-derive coverage from the recorded command lines.

    The point of a covering set is a property, not a claim. Checking it from
    what actually ran means an edit to the table that breaks coverage is caught
    rather than assumed.
    """
    rows_in = [r for r in load_tidy(results, args.experiment)
               if not r.get("skipped") and r.get("exit_code") == 0]
    if not rows_in:
        raise SystemExit("no successful cells to check")

    records = [{"cell": row.get("cell"),
                **{f: row.get(f) for f in COVERING_FACTORS}}
               for row in sorted(rows_in, key=lambda r: r.get("cell") or "")]

    emit(records, "Functional covering set as executed (§5.1)",
         results / args.experiment / "data_coverage" if not args.no_files else None)

    value_coverage = {}
    for factor in COVERING_FACTORS:
        values = sorted({str(r.get(factor)) for r in rows_in if r.get(factor) is not None})
        value_coverage[factor] = values

    pair_gaps = []
    for left, right in itertools.combinations(COVERING_FACTORS, 2):
        seen = {(str(r.get(left)), str(r.get(right))) for r in rows_in}
        wanted = {(a, b) for a in value_coverage[left] for b in value_coverage[right]}
        missing = sorted(wanted - seen)
        if missing:
            pair_gaps.append({"left": left, "right": right,
                              "missing": [{"left": a, "right": b} for a, b in missing]})

    report = {
        "experiment": args.experiment,
        "cells": len(rows_in),
        "value_coverage": value_coverage,
        "untested_factors": [f for f, v in value_coverage.items() if len(v) < 2],
        "pair_gaps": pair_gaps,
        "note": ("Some gaps are REQUIRED, not defects: --hdt-strategy single is "
                 "refused beside space-optimized and beside cottas, so those pairs "
                 "cannot exist. Check each gap against plan §1.2 before adding a row."),
    }

    print("\nValue coverage:")
    for factor, values in value_coverage.items():
        print(f"  {factor:<24} {len(values)} value(s): {', '.join(values)}")
    if report["untested_factors"]:
        print(f"\n  factors with only one value: {', '.join(report['untested_factors'])}"
              " — these are not being tested")
    print(f"\nPair coverage: {len(pair_gaps)} pair(s) not fully covered")
    for gap in pair_gaps:
        shown = ", ".join(f"{m['left']}/{m['right']}" for m in gap["missing"][:4])
        more = f" (+{len(gap['missing']) - 4} more)" if len(gap["missing"]) > 4 else ""
        print(f"  {gap['left']} x {gap['right']}: missing {shown}{more}")
    if pair_gaps:
        print("\n  " + report["note"])

    if not args.no_files:
        path = results / args.experiment / "data_coverage_report.json"
        path.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {path}")
    return 0


# ---------------------------------------------------------------------------
def cmd_querycost(args, results: pathlib.Path) -> int:
    """SPARQL retrieval against the cyvcf2 oracle, on identical work.

    Aggregate against aggregate only. The oracle timing is a whole-run total,
    so a per-query ratio would divide one query by all of them; benchmark.csv
    repeats the total on each row for join convenience and that is the trap.

    Two cost shapes, which is the actual finding: the parser pays parse+census
    on every invocation and has no index, while an engine pays setup once and
    then queries. So the headline is not a speed factor but a break-even — how
    many repeated queries before the graph's setup has paid for itself.
    """
    rows_in = [r for r in load_tidy(results, args.experiment)
               if not r.get("skipped") and r.get("exit_code") == 0]
    if not rows_in:
        raise SystemExit("no successful cells")

    engines: list[str] = []
    for row in rows_in:
        for key in row:
            if key.startswith("engine_query_seconds__"):
                name = key.split("__", 1)[1]
                if name not in engines:
                    engines.append(name)
    if not engines:
        raise SystemExit(
            "no engine query timings found.\n"
            "This dataset needs runs made with --validate; the SPARQL-vs-parser\n"
            "timings come from each validation report's benchmark.json."
        )

    def scale_of(row: dict) -> str:
        cell = row.get("cell") or ""
        return cell.split("__")[0] if "__" in cell else "all"

    def median(values: list[float]) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2.0

    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows_in:
        for engine in engines:
            if row.get(f"engine_query_seconds__{engine}") is not None:
                groups.setdefault((scale_of(row), engine), []).append(row)

    records = []
    for (scale, engine), cells in sorted(groups.items()):
        query_seconds = median([float(c[f"engine_query_seconds__{engine}"]) for c in cells])
        setup_values = [float(c[f"engine_setup_seconds__{engine}"]) for c in cells
                        if c.get(f"engine_setup_seconds__{engine}") is not None]
        setup_seconds = median(setup_values)
        oracle_seconds = median([float(c["oracle_total_seconds"]) for c in cells
                                 if c.get("oracle_total_seconds") is not None])
        oracle_parse = median([float(c["oracle_parse_seconds"]) for c in cells
                               if c.get("oracle_parse_seconds") is not None])

        ratio = break_even = None
        if oracle_seconds and query_seconds is not None:
            ratio = query_seconds / oracle_seconds
            # Break-even: n * query + setup <= n * oracle  =>  n >= setup / (oracle - query).
            # Only defined when querying is actually cheaper than parsing;
            # otherwise the graph never pays for itself on this workload.
            if query_seconds < oracle_seconds:
                gap = oracle_seconds - query_seconds
                break_even = (setup_seconds or 0.0) / gap
            else:
                break_even = None

        statuses = {c.get("validation_status") for c in cells}
        records.append({
            "scale": scale,
            "engine": engine,
            "reps": len(cells),
            "queries": cells[0].get("query_count"),
            "triples": cells[0].get("output_triples"),
            "engine_query_seconds": query_seconds,
            "engine_setup_seconds": setup_seconds,
            "oracle_total_seconds": oracle_seconds,
            "oracle_parse_seconds": oracle_parse,
            "query_vs_oracle_ratio": ratio,
            "break_even_repetitions": break_even,
            "answers_equal": "PASS" if statuses == {"PASS"} else ",".join(
                sorted(str(s) for s in statuses)),
        })

    emit(records, "SPARQL retrieval vs cyvcf2 parser, identical work (§4.5)",
         results / args.experiment / "data_querycost" if not args.no_files else None,
         note=("engine_query_seconds and oracle_total_seconds both cover the SAME full\n"
               "query set, so this ratio is like-for-like. For the per-question view see\n"
               "data_querycost_per_query, written alongside this file.\n"
               "\n"
               "Note that benchmark.csv's oracle_wall_seconds column is the whole-run\n"
               "total repeated on every row, so a row-wise ratio against it is invalid;\n"
               "the per-question column is oracle_query_seconds.\n"
               "\n"
               "break_even_repetitions is the number of repeated queries after which\n"
               "the engine's one-time setup has paid for itself against re-parsing the\n"
               "VCF each time. Empty means querying was not cheaper than parsing at\n"
               "this scale, so there is no crossover to report.\n"
               "\n"
               "Conversion cost is in NEITHER column — the graph has to exist first.\n"
               "Quote it from §3; do not fold it in here, and do not omit it."))

    unequal = [r for r in records if r["answers_equal"] != "PASS"]
    if unequal:
        print("\nDO NOT QUOTE SPEED FOR THESE — the answers were not proven equal:")
        for record in unequal:
            print(f"  {record['scale']}/{record['engine']}: "
                  f"validation={record['answers_equal']}")
        print("Result equality is the precondition for a timing comparison.")

    _emit_per_query(rows_in, results, args, scale_of)
    return 0


def _emit_per_query(rows_in, results, args, scale_of) -> None:
    """Per-query rows, joining each engine's query time to the parser's.

    This IS row-wise comparable: `oracle_query_seconds` is the cost of the
    parser answering THAT query, composed from directly measured phases
    (reader open, record scan, per-sample block, assembly). The whole-run
    `oracle_wall_seconds` column in the same file is not — it is the total for
    all queries, repeated for join convenience.
    """
    per_query: list[dict] = []
    seen_paths: set[str] = set()
    for row in rows_in:
        paths = (row.get("benchmark_csvs") or "").split(";")
        for path_str in paths:
            if not path_str or path_str in seen_paths:
                continue
            seen_paths.add(path_str)
            path = pathlib.Path(path_str)
            if not path.is_file():
                continue
            with path.open(newline="", encoding="utf-8") as handle:
                for entry in csv.DictReader(handle):
                    def number(key):
                        value = entry.get(key)
                        try:
                            return float(value) if value not in (None, "") else None
                        except ValueError:
                            return None

                    engine_seconds = number("wall_seconds")
                    oracle_seconds = number("oracle_query_seconds")
                    ratio = None
                    if engine_seconds is not None and oracle_seconds:
                        ratio = engine_seconds / oracle_seconds
                    per_query.append({
                        "scale": scale_of(row),
                        "cell": row.get("cell"),
                        "engine": entry.get("engine"),
                        "query_id": entry.get("query_id"),
                        "status": entry.get("status"),
                        "engine_wall_seconds": engine_seconds,
                        "oracle_query_seconds": oracle_seconds,
                        "engine_vs_oracle_ratio": ratio,
                        "engine_setup_seconds": number("engine_setup_seconds"),
                        "artifact_origin": entry.get("artifact_origin") or None,
                    })

    if not per_query:
        print("\nNo per-query oracle timings found. They come from the validation\n"
              "report's benchmark.csv `oracle_query_seconds` column, which needs a\n"
              "tool build that records the oracle's phase breakdown.")
        return

    emit(per_query, "Per-query: SPARQL vs parser, same question (§4.5)",
         results / args.experiment / "data_querycost_per_query" if not args.no_files else None,
         note=("engine_wall_seconds and oracle_query_seconds are the same question on\n"
               "both sides, so this ratio IS valid row-wise.\n"
               "\n"
               "oracle_query_seconds is attributed from measured phases, not measured in\n"
               "isolation: the oracle is one pass filling every query's counters at once,\n"
               "so there is no per-query slice of it to time. Every query pays reader\n"
               "open + record scan + assembly; only q05/q06/q13 additionally pay for the\n"
               "per-sample genotype block, which is what makes them diverge on a cohort\n"
               "file and not on a single-sample one. benchmark.json's\n"
               "oracle.sampleLevelQueries names them, so the attribution is auditable."))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("table", choices=["corpus", "equivalence", "awkward",
                                          "feasibility", "coverage", "querycost"])
    parser.add_argument("experiment")
    parser.add_argument("--results", default=None)
    parser.add_argument("--no-files", action="store_true",
                        help="print only; do not write CSV/JSON")
    args = parser.parse_args()

    results = pathlib.Path(args.results) if args.results else RESULTS_DEFAULT
    handler = {
        "corpus": cmd_corpus, "equivalence": cmd_equivalence, "awkward": cmd_awkward,
        "feasibility": cmd_feasibility, "coverage": cmd_coverage,
        "querycost": cmd_querycost,
    }[args.table]
    return handler(args, results)


if __name__ == "__main__":
    raise SystemExit(main())
