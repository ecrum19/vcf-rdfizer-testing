#!/usr/bin/env python3
"""Run VCF/RDF semantic-equivalence preflight and all six query comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import cyvcf2

from compare_results import QUERY_SPECS, compare_payloads
from normalize_sparql_json import normalize_file
from parser_oracle import run as run_parser_oracle


SCRIPT_DIR = Path(__file__).resolve().parent
QUERY_DIR = SCRIPT_DIR / "queries"
FIXTURE_VCF = SCRIPT_DIR / "fixtures" / "edge_cases.vcf"
FIXTURE_RDF = SCRIPT_DIR / "fixtures" / "edge_cases.nt"
FIXTURE_EXPECTED = SCRIPT_DIR / "fixtures" / "edge_cases.expected.json"
CORE_QUERIES = tuple(QUERY_SPECS)
PREFLIGHT_QUERIES = (
    "preflight_record_cardinality",
    "preflight_position_datatype",
    "preflight_missing_token_conformance",
    "preflight_sample_gt_inventory",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def json_load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def tool_version(command: list[str], *, table_label: str | None = None) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    output = result.stdout.strip()
    if table_label:
        for line in output.splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[0] == table_label:
                return cells[1]
    return output.splitlines()[0] if output else None


def resolve_rdf_sources(paths: list[Path]) -> list[Path]:
    sources: set[Path] = set()
    for source in paths:
        source = source.resolve()
        if source.is_file():
            if source.suffix != ".nt":
                raise ValueError(f"RDF file must use the .nt extension: {source}")
            sources.add(source)
        elif source.is_dir():
            sources.update(path.resolve() for path in source.rglob("*.nt"))
        else:
            raise FileNotFoundError(f"RDF source does not exist: {source}")
    if not sources:
        raise ValueError("No N-Triples (*.nt) sources were found")
    return sorted(sources, key=lambda path: str(path))


def validate_ntriples(sources: list[Path], results_dir: Path) -> dict[str, Any]:
    validator = shutil.which("rapper")
    if validator is None:
        return {
            "status": "EXECUTION_FAILED",
            "error": "rapper is not installed; use the Docker runner",
            "files": [],
        }

    validations = []
    all_valid = True
    log_dir = results_dir / "rdf-validation"
    log_dir.mkdir(parents=True, exist_ok=True)
    for index, source in enumerate(sources, start=1):
        result = subprocess.run(
            [validator, "-i", "ntriples", "-c", str(source)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        log_path = log_dir / f"{index:04d}-{source.name}.txt"
        log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
        valid = result.returncode == 0
        all_valid = all_valid and valid
        validations.append(
            {
                "path": str(source),
                "sha256": sha256_file(source),
                "status": "PASS" if valid else "FAIL",
                "exitCode": result.returncode,
                "log": str(log_path),
            }
        )
    return {
        "status": "PASS" if all_valid else "FAIL",
        "validator": tool_version([validator, "--version"]),
        "files": validations,
    }


def execute_query(
    query_id: str,
    sources: list[Path],
    raw_dir: Path,
) -> dict[str, Any]:
    executable = shutil.which("comunica-sparql-file")
    if executable is None:
        return {
            "status": "EXECUTION_FAILED",
            "error": "comunica-sparql-file is not installed; use the Docker runner",
        }

    query_path = QUERY_DIR / f"{query_id}.rq"
    raw_path = raw_dir / f"{query_id}.sparql.json"
    stderr_path = raw_dir / f"{query_id}.stderr.txt"
    metrics_path = raw_dir / f"{query_id}.time.txt"
    raw_path.unlink(missing_ok=True)
    stderr_path.unlink(missing_ok=True)
    metrics_path.unlink(missing_ok=True)

    comunica_command = [
        executable,
        *(str(source) for source in sources),
        "-f",
        str(query_path),
        "-t",
        "application/sparql-results+json",
    ]
    time_version = tool_version(["/usr/bin/time", "--version"])
    if time_version and "gnu time" in time_version.lower():
        command = [
            "/usr/bin/time",
            "-v",
            "-o",
            str(metrics_path),
            *comunica_command,
        ]
    else:
        command = comunica_command
    started = time.monotonic()
    with raw_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
        result = subprocess.run(
            command,
            check=False,
            stdout=stdout_handle,
            stderr=stderr_handle,
        )
    elapsed = time.monotonic() - started

    return {
        "status": "PASS" if result.returncode == 0 else "EXECUTION_FAILED",
        "exitCode": result.returncode,
        "wallSeconds": elapsed,
        "query": str(query_path),
        "command": command,
        "rawResult": str(raw_path),
        "stderr": str(stderr_path),
        "resourceMetrics": str(metrics_path) if metrics_path.exists() else None,
    }


def sparql_bindings(path: Path) -> list[dict[str, Any]]:
    document = json_load(path)
    try:
        bindings = document["results"]["bindings"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"Invalid SPARQL Results JSON: {path}") from error
    if not isinstance(bindings, list):
        raise ValueError(f"SPARQL bindings are not a list: {path}")
    return bindings


def binding_integer(binding: dict[str, Any], field: str) -> int:
    return int(binding[field]["value"])


def preflight_report(
    executions: dict[str, dict[str, Any]],
    parser_payload: dict[str, Any],
) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for query_id in PREFLIGHT_QUERIES:
        execution = executions[query_id]
        if execution["status"] != "PASS":
            report[query_id] = {
                "status": "EXECUTION_FAILED",
                "execution": execution,
            }
            continue
        bindings = sparql_bindings(Path(execution["rawResult"]))

        if query_id == "preflight_record_cardinality":
            report[query_id] = {
                "status": "PASS" if not bindings else "FAIL",
                "anomalyCountReturned": len(bindings),
                "limitedTo": 100,
            }
        elif query_id == "preflight_position_datatype":
            report[query_id] = {
                "status": "PASS" if not bindings else "FAIL",
                "anomalyCountReturned": len(bindings),
                "limitedTo": 100,
            }
        elif query_id == "preflight_missing_token_conformance":
            report[query_id] = {
                "status": "PASS" if not bindings else "EXPECTED_CONFORMANCE_FAILURE",
                "plainDotCountReturned": len(bindings),
                "limitedTo": 100,
                "note": (
                    "Plain dot literals remain a documented mapping limitation."
                    if bindings
                    else "No plain dot literals were observed."
                ),
            }
        else:
            if len(bindings) != 1:
                report[query_id] = {
                    "status": "FAIL",
                    "error": f"Expected one aggregate row, got {len(bindings)}",
                }
                continue
            actual = {
                "sampleCallCount": binding_integer(bindings[0], "sampleCallCount"),
                "sampleIdCount": binding_integer(bindings[0], "sampleIdCount"),
                "gtValueNodeCount": binding_integer(bindings[0], "gtValueNodeCount"),
            }
            expected = {
                "sampleCallCount": parser_payload["sampleCount"]
                * parser_payload["totalRecords"],
                "sampleIdCount": parser_payload["sampleCount"],
                "gtValueNodeCount": parser_payload["sampleCount"]
                * parser_payload["gtRecordCount"],
            }
            report[query_id] = {
                "status": "PASS" if actual == expected else "FAIL",
                "expected": expected,
                "actual": actual,
            }
    return report


def write_manifest(
    args: argparse.Namespace,
    vcf_path: Path,
    rdf_sources: list[Path],
    results_dir: Path,
    *,
    source_sha256: str,
    rdf_sha256: dict[Path, str],
) -> dict[str, Any]:
    query_paths = sorted(QUERY_DIR.glob("*.rq"))
    provenance_warnings = []
    if not args.converter_version:
        provenance_warnings.append("converter version was not supplied")
    if not args.mapping:
        provenance_warnings.append("mapping file was not supplied")
    if not args.vocabulary_version:
        provenance_warnings.append("vocabulary version was not supplied")

    manifest: dict[str, Any] = {
        "datasetId": args.dataset_id,
        "commandLine": sys.argv,
        "sourceVcf": {
            "path": str(vcf_path),
            "sha256": source_sha256,
        },
        "rdfSources": [
            {
                "path": str(source),
                "sha256": (
                    rdf_sha256[source]
                    if source in rdf_sha256
                    else sha256_file(source)
                ),
            }
            for source in rdf_sources
        ],
        "converter": {
            "version": args.converter_version,
            "gitCommit": args.converter_commit,
        },
        "mapping": (
            {
                "path": str(args.mapping.resolve()),
                "sha256": sha256_file(args.mapping.resolve()),
            }
            if args.mapping
            else None
        ),
        "vocabulary": {
            "version": args.vocabulary_version,
            "gitCommit": args.vocabulary_commit,
        },
        "tools": {
            "python": platform.python_version(),
            "cyvcf2": cyvcf2.__version__,
            "bcftools": tool_version(["bcftools", "--version"]),
            "node": tool_version(["node", "--version"]),
            "comunicaQuerySparqlFile": tool_version(
                ["comunica-sparql-file", "--version"],
                table_label="Comunica Engine",
            ),
            "rapper": tool_version(["rapper", "--version"]),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "queries": {
            path.stem: {"path": str(path), "sha256": sha256_file(path)}
            for path in query_paths
        },
        "provenanceComplete": not provenance_warnings,
        "provenanceWarnings": provenance_warnings,
        "resultsDirectory": str(results_dir),
    }
    json_write(results_dir / "manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vcf", type=Path, default=FIXTURE_VCF)
    parser.add_argument(
        "--rdf",
        type=Path,
        action="append",
        help="N-Triples file or directory; repeat for multiple partitions",
    )
    parser.add_argument("--dataset-id", help="Result directory identifier")
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--expected", type=Path, help="Optional hand-checked query JSON")
    parser.add_argument(
        "--filter-oracle",
        choices=("auto", "bcftools", "cyvcf2"),
        default="auto",
    )
    parser.add_argument("--converter-version")
    parser.add_argument("--converter-commit")
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--vocabulary-version")
    parser.add_argument("--vocabulary-commit")
    args = parser.parse_args()

    args.vcf = args.vcf.resolve()
    args.rdf = args.rdf or [FIXTURE_RDF]
    if args.dataset_id is None:
        args.dataset_id = args.vcf.name
        for suffix in (".vcf.gz", ".vcf", ".bcf"):
            if args.dataset_id.endswith(suffix):
                args.dataset_id = args.dataset_id[: -len(suffix)]
                break
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.dataset_id):
        parser.error("--dataset-id may contain only letters, digits, dot, underscore, hyphen")
    args.results_dir = (
        args.results_dir.resolve()
        if args.results_dir
        else (SCRIPT_DIR / "results" / args.dataset_id).resolve()
    )
    using_fixture = args.vcf == FIXTURE_VCF.resolve() and {
        path.resolve() for path in args.rdf
    } == {FIXTURE_RDF.resolve()}
    if args.expected is None and using_fixture:
        args.expected = FIXTURE_EXPECTED
    if using_fixture:
        args.converter_version = args.converter_version or "bundled-fixture-rdf"
        args.vocabulary_version = args.vocabulary_version or "fixture-vocabulary-contract"
    return args


def main() -> None:
    args = parse_args()
    if not args.vcf.is_file():
        raise SystemExit(f"VCF does not exist: {args.vcf}")
    if args.mapping and not args.mapping.resolve().is_file():
        raise SystemExit(f"Mapping does not exist: {args.mapping.resolve()}")
    if args.expected and not args.expected.resolve().is_file():
        raise SystemExit(f"Expected-result JSON does not exist: {args.expected.resolve()}")

    rdf_sources = resolve_rdf_sources(args.rdf)
    results_dir: Path = args.results_dir
    raw_dir = results_dir / "raw"
    normalized_dir = results_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{args.dataset_id}] computing VCF oracle", flush=True)
    parser_payload = run_parser_oracle(
        args.vcf,
        filter_oracle=args.filter_oracle,
    )
    json_write(results_dir / "parser.json", parser_payload)

    print(f"[{args.dataset_id}] validating {len(rdf_sources)} RDF source(s)", flush=True)
    rdf_validation = validate_ntriples(rdf_sources, results_dir)
    json_write(results_dir / "rdf-validation.json", rdf_validation)
    rdf_hashes = {
        Path(item["path"]): item["sha256"]
        for item in rdf_validation.get("files", [])
        if item.get("sha256")
    }
    manifest = write_manifest(
        args,
        args.vcf,
        rdf_sources,
        results_dir,
        source_sha256=parser_payload["sourceSha256"],
        rdf_sha256=rdf_hashes,
    )
    if rdf_validation["status"] != "PASS":
        summary = {
            "datasetId": args.dataset_id,
            "status": "BLOCKED_BY_PREFLIGHT",
            "rdfValidation": rdf_validation,
            "manifest": str(results_dir / "manifest.json"),
        }
        json_write(results_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2), file=sys.stderr)
        raise SystemExit(1)

    executions: dict[str, dict[str, Any]] = {}
    for query_id in PREFLIGHT_QUERIES + CORE_QUERIES:
        print(f"[{args.dataset_id}] running {query_id}", flush=True)
        execution = execute_query(query_id, rdf_sources, raw_dir)
        executions[query_id] = execution
        if execution["status"] != "PASS":
            print(f"[{args.dataset_id}] {query_id} failed", file=sys.stderr, flush=True)
    json_write(results_dir / "query-executions.json", executions)

    try:
        preflight = preflight_report(executions, parser_payload)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        summary = {
            "datasetId": args.dataset_id,
            "status": "EXECUTION_FAILED",
            "error": f"Could not interpret preflight results: {error}",
            "manifest": str(results_dir / "manifest.json"),
        }
        json_write(results_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2), file=sys.stderr)
        raise SystemExit(1) from error
    json_write(results_dir / "preflight.json", preflight)

    failed_queries = [
        query_id
        for query_id in CORE_QUERIES
        if executions[query_id]["status"] != "PASS"
    ]
    failed_preflight_execution = [
        query_id
        for query_id in PREFLIGHT_QUERIES
        if executions[query_id]["status"] != "PASS"
    ]
    if failed_queries or failed_preflight_execution:
        summary = {
            "datasetId": args.dataset_id,
            "status": "EXECUTION_FAILED",
            "failedQueries": failed_queries,
            "failedPreflightQueries": failed_preflight_execution,
            "preflight": preflight,
            "manifest": str(results_dir / "manifest.json"),
        }
        json_write(results_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2), file=sys.stderr)
        raise SystemExit(1)

    sparql_payload: dict[str, Any] = {"totalRecords": parser_payload["totalRecords"]}
    normalization_failures: dict[str, str] = {}
    for query_id in CORE_QUERIES:
        try:
            normalized = normalize_file(
                query_id,
                Path(executions[query_id]["rawResult"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            normalization_failures[query_id] = str(error)
            continue
        sparql_payload[query_id] = normalized
        json_write(normalized_dir / f"{query_id}.json", normalized)
    if normalization_failures:
        summary = {
            "datasetId": args.dataset_id,
            "status": "EXECUTION_FAILED",
            "normalizationFailures": normalization_failures,
            "preflight": preflight,
            "manifest": str(results_dir / "manifest.json"),
        }
        json_write(results_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2), file=sys.stderr)
        raise SystemExit(1)
    json_write(results_dir / "sparql.json", sparql_payload)

    expected = json_load(args.expected.resolve()) if args.expected else None
    comparison = compare_payloads(
        parser_payload,
        sparql_payload,
        fixture_expected=expected,
    )
    json_write(results_dir / "comparison.json", comparison)

    blocking_preflight = [
        query_id
        for query_id in (
            "preflight_record_cardinality",
            "preflight_position_datatype",
        )
        if preflight[query_id]["status"] != "PASS"
    ]
    sample_gt_preflight_failed = (
        preflight["preflight_sample_gt_inventory"]["status"] != "PASS"
    )
    q5_q6_required = bool(
        parser_payload["sampleCount"] and parser_payload["gtRecordCount"]
    )
    if blocking_preflight:
        status = "BLOCKED_BY_PREFLIGHT"
    elif comparison["status"] != "PASS" or sample_gt_preflight_failed:
        status = "MISMATCH"
    else:
        status = "PASS"

    summary = {
        "datasetId": args.dataset_id,
        "status": status,
        "recordCount": parser_payload["totalRecords"],
        "sampleCount": parser_payload["sampleCount"],
        "gtRecordCount": parser_payload["gtRecordCount"],
        "applicability": {
            "q01-q04": "REQUIRED",
            "q05-q06": (
                "REQUIRED"
                if q5_q6_required
                else "NOT_APPLICABLE_VERIFIED_NO_SAMPLES_OR_GT"
            ),
        },
        "preflight": preflight,
        "comparisonStatus": comparison["status"],
        "provenanceComplete": manifest["provenanceComplete"],
        "provenanceWarnings": manifest["provenanceWarnings"],
        "results": {
            "manifest": str(results_dir / "manifest.json"),
            "parser": str(results_dir / "parser.json"),
            "sparql": str(results_dir / "sparql.json"),
            "comparison": str(results_dir / "comparison.json"),
        },
    }
    json_write(results_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
