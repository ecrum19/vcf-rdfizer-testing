#!/usr/bin/env python3
"""Combine conversion, TSV, and compression metrics into a single JSON file.

The output JSON intentionally contains two views:
1) datasets: one row per dataset (convenient for paper tables)
2) compression_by_method: one row per dataset+method (tidy form for plotting)

Metric JSON files are the primary evidence. The combiner retains their source
paths, reads both current and legacy `raw_metrics` locations, and never
creates rows for compression methods that a run did not select.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


METHOD_SPECS: Dict[str, Dict[str, str]] = {
    "gzip": {
        "section_key": "gzip_raw_rdf",
        "size_key": "output_gz_size_bytes",
        "path_key": "output_gz_path",
    },
    "brotli": {
        "section_key": "brotli_raw_rdf",
        "size_key": "output_brotli_size_bytes",
        "path_key": "output_brotli_path",
    },
    "hdt": {
        "section_key": "hdt_conversion",
        "size_key": "output_hdt_size_bytes",
        "path_key": "output_hdt_path",
    },
    "hdt_gzip": {
        "section_key": "gzip_on_hdt",
        "size_key": "output_hdt_gz_size_bytes",
        "path_key": "output_hdt_gz_path",
    },
    "hdt_brotli": {
        "section_key": "brotli_on_hdt",
        "size_key": "output_hdt_br_size_bytes",
        "path_key": "output_hdt_br_path",
    },
    "cottas": {
        "section_key": "cottas_conversion",
        "size_key": "output_cottas_size_bytes",
        "path_key": "output_cottas_path",
    },
    "cottas_gzip": {
        "section_key": "gzip_on_cottas",
        "size_key": "output_cottas_gz_size_bytes",
        "path_key": "output_cottas_gz_path",
    },
    "cottas_brotli": {
        "section_key": "brotli_on_cottas",
        "size_key": "output_cottas_br_size_bytes",
        "path_key": "output_cottas_br_path",
    },
}


def _safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _strip_known_suffixes(name: str) -> str:
    known_suffixes = (
        ".vcf.gz",
        ".nt.gz",
        ".nt.br",
        ".tsv.gz",
        ".vcf",
        ".nt",
        ".tsv",
        ".gz",
        ".br",
    )
    stripped = name
    while stripped:
        for suffix in known_suffixes:
            if stripped.endswith(suffix):
                stripped = stripped[: -len(suffix)]
                break
        else:
            break
    return stripped or Path(name).stem


def _select_latest(
    current: Optional[Dict[str, Any]], candidate: Dict[str, Any]
) -> Dict[str, Any]:
    if current is None:
        return candidate
    current_priority = int(current.get("_source_priority") or 0)
    candidate_priority = int(candidate.get("_source_priority") or 0)
    if candidate_priority > current_priority:
        return candidate
    if candidate_priority < current_priority:
        return current
    current_ts = str(current.get("timestamp") or "")
    candidate_ts = str(candidate.get("timestamp") or "")
    if candidate_ts > current_ts:
        return candidate
    return current


def _dataset_from_conversion_path(payload: Dict[str, Any], path: Path) -> str:
    output_path = (payload.get("artifacts") or {}).get("output_path")
    if output_path:
        name = _strip_known_suffixes(Path(str(output_path)).name)
        if name:
            return name
    return path.parent.name


def _dataset_from_compression_path(payload: Dict[str, Any], path: Path) -> str:
    output_name = payload.get("output_name")
    if output_name:
        return _strip_known_suffixes(Path(str(output_name)).name)
    return path.parent.name


def _dataset_from_prefixed_input_path(payload: Dict[str, Any], path: Path) -> str:
    prefix = payload.get("prefix")
    if prefix:
        return _strip_known_suffixes(Path(str(prefix)).name)

    input_path = payload.get("input_path")
    if input_path:
        return _strip_known_suffixes(Path(str(input_path)).name)

    return path.parent.name


def _extract_conversion(payload: Dict[str, Any], source_file: Path) -> Dict[str, Any]:
    artifacts = payload.get("artifacts") or {}
    timing = payload.get("timing") or {}
    rdf_storage = payload.get("rdf_storage") or {}
    triples_payload = artifacts.get("output_triples") or {}
    total_triples = triples_payload.get("TOTAL")

    if total_triples is None and isinstance(triples_payload, dict):
        values = [value for value in triples_payload.values() if isinstance(value, int)]
        total_triples = sum(values) if values else None

    rdf_size_bytes = artifacts.get("output_size_bytes")
    input_vcf_size_bytes = artifacts.get("input_vcf_size_bytes")

    return {
        "run_id": payload.get("run_id"),
        "timestamp": payload.get("timestamp"),
        "conversion_exit_code": payload.get("exit_code"),
        "conversion_wall_seconds": timing.get("wall_seconds"),
        "conversion_user_seconds": timing.get("user_seconds"),
        "conversion_sys_seconds": timing.get("sys_seconds"),
        "conversion_max_rss_kb": timing.get("max_rss_kb"),
        "mapping_file": artifacts.get("input_path"),
        "mapping_size_bytes": artifacts.get("input_size_bytes"),
        "input_vcf_size_bytes": input_vcf_size_bytes,
        "rdf_size_bytes": rdf_size_bytes,
        "total_triples": total_triples,
        "rdf_expansion_ratio_vs_vcf": _safe_div(rdf_size_bytes, input_vcf_size_bytes),
        "rdf_bytes_per_triple": _safe_div(rdf_size_bytes, total_triples),
        "rdf_storage_mode": rdf_storage.get("mode"),
        "rdf_storage_compressed": rdf_storage.get("compressed"),
        "rdf_storage_serialization": rdf_storage.get("serialization"),
        "conversion_command": payload.get("command"),
        "conversion_metrics_file": str(source_file),
    }


def _extract_tsv(payload: Dict[str, Any], source_file: Path) -> Dict[str, Any]:
    artifacts = payload.get("artifacts") or {}
    timing = payload.get("timing") or {}
    output_paths = artifacts.get("output_paths") or []

    return {
        "run_id": payload.get("run_id"),
        "timestamp": payload.get("timestamp"),
        "tsv_exit_code": payload.get("exit_code"),
        "tsv_wall_seconds": timing.get("wall_seconds"),
        "tsv_user_seconds": timing.get("user_seconds"),
        "tsv_sys_seconds": timing.get("sys_seconds"),
        "tsv_max_rss_kb": timing.get("max_rss_kb"),
        "tsv_input_path": payload.get("input_path"),
        "tsv_output_paths": output_paths,
        "tsv_output_file_count": len(output_paths),
        "tsv_size_bytes": artifacts.get("output_size_bytes"),
        "tsv_metrics_file": str(source_file),
    }


def _extract_method(payload: Dict[str, Any], method: str) -> Dict[str, Any]:
    spec = METHOD_SPECS[method]
    section = payload.get(spec["section_key"]) or {}
    timing = section.get("timing") or {}
    validation = section.get("validation") or {}
    validation_timing = validation.get("timing") or {}

    return {
        "method": method,
        "output_path": section.get(spec["path_key"]),
        "size_bytes": section.get(spec["size_key"]),
        "exit_code": section.get("exit_code"),
        "wall_seconds": timing.get("wall_seconds"),
        "user_seconds": timing.get("user_seconds"),
        "sys_seconds": timing.get("sys_seconds"),
        "max_rss_kb": timing.get("max_rss_kb"),
        "validation_present": bool(validation),
        "validation_valid": validation.get("valid"),
        "validation_count_match": validation.get("count_match"),
        "validation_source_triples": validation.get("source_triples"),
        "validation_decoded_triples": validation.get("decoded_triples"),
        "validation_expected_triples": validation.get("expected_triples"),
        "validation_validator": validation.get("validator"),
        "validation_wall_seconds": validation_timing.get("wall_seconds"),
        "validation_user_seconds": validation_timing.get("user_seconds"),
        "validation_sys_seconds": validation_timing.get("sys_seconds"),
        "validation_max_rss_kb": validation_timing.get("max_rss_kb"),
    }


def _selected_compression_methods(payload: Dict[str, Any]) -> List[str]:
    raw_methods = payload.get("compression_methods")
    if not isinstance(raw_methods, str):
        return []

    selected: List[str] = []
    for value in raw_methods.replace("|", ",").split(","):
        method = value.strip()
        if method in METHOD_SPECS and method not in selected:
            selected.append(method)
    return selected


def _extract_compression(
    payload: Dict[str, Any], source_file: Path
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    methods: Dict[str, Dict[str, Any]] = {}
    selected_methods = _selected_compression_methods(payload)
    for method in selected_methods:
        methods[method] = _extract_method(payload, method)

    summary = {
        "run_id": payload.get("run_id"),
        "timestamp": payload.get("timestamp"),
        "compression_methods": payload.get("compression_methods"),
        "compression_output_dir": payload.get("output_dir"),
        "combined_rdf_size_bytes": payload.get("combined_rdf_size_bytes"),
        "hdt_source": payload.get("hdt_source"),
        "combined_rdf_path": payload.get("combined_rdf_path"),
        "compression_metrics_file": str(source_file),
        "compression_selected_methods": selected_methods,
    }
    return summary, methods


def _iter_metric_files(run_dir: Path, section: str) -> Iterable[Path]:
    """Yield current metric files first, followed by legacy raw metric files."""

    paths: List[Path] = []
    seen: set[Path] = set()
    for base in (run_dir / section, run_dir / "raw_metrics" / section):
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.json")):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                paths.append(resolved)
    return paths


def _source_priority(run_dir: Path, metric_file: Path) -> int:
    try:
        relative = metric_file.resolve().relative_to(run_dir.resolve())
    except ValueError:
        return 0
    return 1 if relative.parts and relative.parts[0] == "raw_metrics" else 2


def _mark_source_priority(record: Dict[str, Any], run_dir: Path, metric_file: Path) -> Dict[str, Any]:
    record["_source_priority"] = _source_priority(run_dir, metric_file)
    return record


def _without_internal_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in record.items() if not key.startswith("_")}


def _parse_timing_value(value: str) -> Any:
    stripped = value.strip()
    if stripped == "":
        return None
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    try:
        return int(stripped)
    except ValueError:
        try:
            return float(stripped)
        except ValueError:
            return stripped


def _extract_timing_text(path: Path, method: str) -> Dict[str, Any]:
    raw_values: Dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            raw_values[key] = _parse_timing_value(value)

    return {
        "method": method,
        "output_path": raw_values.get("output_path"),
        "size_bytes": raw_values.get("output_size_bytes"),
        "exit_code": raw_values.get("exit_code"),
        "wall_seconds": raw_values.get("wall_seconds"),
        "user_seconds": raw_values.get("user_seconds"),
        "sys_seconds": raw_values.get("sys_seconds"),
        "max_rss_kb": raw_values.get("max_rss_kb"),
        "validation_present": any(key.startswith("validation_") for key in raw_values),
        "validation_valid": raw_values.get("validation_valid"),
        "validation_count_match": raw_values.get("validation_count_match"),
        "validation_source_triples": raw_values.get("source_triples"),
        "validation_decoded_triples": raw_values.get("decoded_triples"),
        "validation_expected_triples": raw_values.get("expected_triples"),
        "validation_validator": raw_values.get("validation_validator"),
        "compression_timing_file": str(path),
    }


def _compression_timing_by_dataset(run_dir: Path) -> Dict[str, Dict[str, Dict[str, Any]]]:
    timing_root = run_dir / "compression_time"
    if not timing_root.exists():
        return {}

    timings: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for method_dir in sorted(timing_root.iterdir()):
        method = method_dir.name
        if method not in METHOD_SPECS or not method_dir.is_dir():
            continue
        for timing_file in sorted(method_dir.glob("*/*.txt")):
            dataset = _strip_known_suffixes(timing_file.parent.name)
            candidate = _extract_timing_text(timing_file, method)
            existing = timings.setdefault(dataset, {}).get(method)
            if existing is None or str(timing_file) > str(existing["compression_timing_file"]):
                timings[dataset][method] = candidate
    return timings


def _fill_missing_method_values(
    method_values: Dict[str, Any], timing_values: Dict[str, Any]
) -> Dict[str, Any]:
    merged = dict(method_values)
    for key, value in timing_values.items():
        if key == "compression_timing_file":
            merged[key] = value
        elif merged.get(key) in (None, "") and value is not None:
            merged[key] = value
    return merged


def _missing_compression_wall_times(
    methods_by_dataset: Dict[str, Dict[str, Dict[str, Any]]]
) -> List[Dict[str, str]]:
    missing: List[Dict[str, str]] = []
    for dataset, methods in methods_by_dataset.items():
        for method, values in methods.items():
            exit_code = values.get("exit_code")
            wall_seconds = values.get("wall_seconds")
            if exit_code is None:
                missing.append(
                    {
                        "dataset": dataset,
                        "method": method,
                        "reason": "selected method has no recorded result",
                    }
                )
            elif exit_code == 0 and not isinstance(wall_seconds, (int, float)):
                missing.append(
                    {
                        "dataset": dataset,
                        "method": method,
                        "reason": "successful method has no recorded wall_seconds",
                    }
                )
    return missing


def _run_completion(run_dir: Path) -> Dict[str, Any]:
    timing_file = run_dir / "wrapper_execution_times.csv"
    if timing_file.exists():
        with timing_file.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if rows:
            last_row = rows[-1]
            status = str(last_row.get("status") or "")
            return {
                "completion_state": "completed" if status == "success" else "not_completed",
                "completion_mode": last_row.get("mode"),
                "completion_status": status or None,
                "completion_evidence_file": str(timing_file),
            }

    progress_file = run_dir / "progress.log"
    if progress_file.exists():
        progress_text = progress_file.read_text(encoding="utf-8")
        if "Full pipeline finished successfully" in progress_text:
            return {
                "completion_state": "completed",
                "completion_mode": "full",
                "completion_status": "success",
                "completion_evidence_file": str(progress_file),
            }

    return {
        "completion_state": "unverified",
        "completion_mode": None,
        "completion_status": None,
        "completion_evidence_file": None,
    }


def build_combined_metrics_for_run(run_dir: Path) -> Dict[str, Any]:
    conversion_by_dataset: Dict[str, Dict[str, Any]] = {}
    tsv_by_dataset: Dict[str, Dict[str, Any]] = {}
    compression_by_dataset: Dict[str, Dict[str, Any]] = {}
    methods_by_dataset: Dict[str, Dict[str, Dict[str, Any]]] = {}
    run_directory = str(run_dir.resolve())
    run_name = run_dir.name
    completion = _run_completion(run_dir)

    for conv_file in _iter_metric_files(run_dir, "conversion_metrics"):
        payload = _load_json(conv_file)
        dataset = _dataset_from_conversion_path(payload, conv_file)
        candidate = _mark_source_priority(
            _extract_conversion(payload, conv_file), run_dir, conv_file
        )
        existing = conversion_by_dataset.get(dataset)
        conversion_by_dataset[dataset] = _select_latest(existing, candidate)

    for tsv_file in _iter_metric_files(run_dir, "tsv_metrics"):
        payload = _load_json(tsv_file)
        dataset = _dataset_from_prefixed_input_path(payload, tsv_file)
        candidate = _mark_source_priority(_extract_tsv(payload, tsv_file), run_dir, tsv_file)
        existing = tsv_by_dataset.get(dataset)
        tsv_by_dataset[dataset] = _select_latest(existing, candidate)

    for comp_file in _iter_metric_files(run_dir, "compression_metrics"):
        payload = _load_json(comp_file)
        dataset = _dataset_from_compression_path(payload, comp_file)
        summary, methods = _extract_compression(payload, comp_file)
        summary = _mark_source_priority(summary, run_dir, comp_file)
        existing = compression_by_dataset.get(dataset)

        if _select_latest(existing, summary) is summary:
            compression_by_dataset[dataset] = summary
            methods_by_dataset[dataset] = methods

    for dataset, timing_methods in _compression_timing_by_dataset(run_dir).items():
        compression = compression_by_dataset.get(dataset)
        if compression is None:
            compression_by_dataset[dataset] = {
                "compression_methods": ",".join(sorted(timing_methods)),
                "compression_selected_methods": sorted(timing_methods),
                "compression_metrics_file": None,
                "compression_timing_files": {
                    method: values["compression_timing_file"]
                    for method, values in timing_methods.items()
                },
            }
            methods_by_dataset[dataset] = timing_methods
            continue

        selected_methods = compression.get("compression_selected_methods") or []
        methods = methods_by_dataset.setdefault(dataset, {})
        timing_files: Dict[str, str] = {}
        for method in selected_methods:
            timing_values = timing_methods.get(method)
            if timing_values is None:
                continue
            methods[method] = _fill_missing_method_values(
                methods.get(method, {"method": method}), timing_values
            )
            timing_files[method] = str(timing_values["compression_timing_file"])
        if timing_files:
            compression["compression_timing_files"] = timing_files

    all_datasets = sorted(
        set(conversion_by_dataset)
        | set(tsv_by_dataset)
        | set(compression_by_dataset)
        | set(methods_by_dataset)
    )

    dataset_rows: List[Dict[str, Any]] = []
    method_rows: List[Dict[str, Any]] = []

    for dataset in all_datasets:
        conversion = _without_internal_fields(conversion_by_dataset.get(dataset, {}))
        tsv = _without_internal_fields(tsv_by_dataset.get(dataset, {}))
        compression = _without_internal_fields(compression_by_dataset.get(dataset, {}))
        methods = methods_by_dataset.get(dataset, {})

        row: Dict[str, Any] = {
            "dataset": dataset,
            "run_directory": run_directory,
            "run_name": run_name,
            **completion,
            "run_id": conversion.get("run_id") or tsv.get("run_id") or compression.get("run_id"),
            "timestamp": conversion.get("timestamp") or tsv.get("timestamp") or compression.get("timestamp"),
            "conversion_present": bool(conversion),
            "tsv_present": bool(tsv),
            "compression_present": bool(compression) or bool(methods),
        }
        row.update(conversion)
        row.update(tsv)
        row.update(compression)

        rdf_size_bytes = row.get("rdf_size_bytes") or row.get("combined_rdf_size_bytes")
        input_vcf_size_bytes = row.get("input_vcf_size_bytes")
        tsv_size_bytes = row.get("tsv_size_bytes")
        row["rdf_size_bytes_for_ratios"] = rdf_size_bytes
        row["tsv_size_ratio_vs_vcf"] = _safe_div(tsv_size_bytes, input_vcf_size_bytes)
        row["tsv_size_ratio_vs_rdf"] = _safe_div(tsv_size_bytes, rdf_size_bytes)

        successful_for_size: List[Dict[str, Any]] = []
        successful_for_time: List[Dict[str, Any]] = []

        for method in METHOD_SPECS:
            if method not in methods:
                continue
            values = methods[method]
            size_bytes = values.get("size_bytes")
            wall_seconds = values.get("wall_seconds")
            exit_code = values.get("exit_code")

            ratio_vs_rdf = _safe_div(size_bytes, rdf_size_bytes)
            ratio_vs_vcf = _safe_div(size_bytes, input_vcf_size_bytes)
            reduction_pct_vs_rdf = None if ratio_vs_rdf is None else (1.0 - ratio_vs_rdf) * 100.0

            row[f"{method}_size_bytes"] = size_bytes
            row[f"{method}_exit_code"] = exit_code
            row[f"{method}_output_path"] = values.get("output_path")
            row[f"{method}_wall_seconds"] = wall_seconds
            row[f"{method}_user_seconds"] = values.get("user_seconds")
            row[f"{method}_sys_seconds"] = values.get("sys_seconds")
            row[f"{method}_max_rss_kb"] = values.get("max_rss_kb")
            row[f"{method}_validation_present"] = values.get("validation_present")
            row[f"{method}_validation_valid"] = values.get("validation_valid")
            row[f"{method}_validation_count_match"] = values.get(
                "validation_count_match"
            )
            row[f"{method}_validation_source_triples"] = values.get(
                "validation_source_triples"
            )
            row[f"{method}_validation_decoded_triples"] = values.get(
                "validation_decoded_triples"
            )
            row[f"{method}_validation_expected_triples"] = values.get(
                "validation_expected_triples"
            )
            row[f"{method}_validation_validator"] = values.get(
                "validation_validator"
            )
            row[f"{method}_validation_wall_seconds"] = values.get(
                "validation_wall_seconds"
            )
            row[f"{method}_validation_user_seconds"] = values.get(
                "validation_user_seconds"
            )
            row[f"{method}_validation_sys_seconds"] = values.get(
                "validation_sys_seconds"
            )
            row[f"{method}_validation_max_rss_kb"] = values.get(
                "validation_max_rss_kb"
            )
            row[f"{method}_size_ratio_vs_rdf"] = ratio_vs_rdf
            row[f"{method}_size_ratio_vs_vcf"] = ratio_vs_vcf
            row[f"{method}_size_reduction_pct_vs_rdf"] = reduction_pct_vs_rdf

            if exit_code == 0 and size_bytes is not None:
                successful_for_size.append(
                    {
                        "method": method,
                        "size_bytes": size_bytes,
                        "ratio_vs_rdf": ratio_vs_rdf,
                    }
                )
            if exit_code == 0 and wall_seconds is not None:
                successful_for_time.append(
                    {
                        "method": method,
                        "wall_seconds": wall_seconds,
                    }
                )

            method_rows.append(
                {
                    "dataset": dataset,
                    "run_directory": run_directory,
                    "run_name": run_name,
                    "run_id": row.get("run_id"),
                    "timestamp": row.get("timestamp"),
                    "method": method,
                    "compression_exit_code": exit_code,
                    "compression_output_path": values.get("output_path"),
                    "compression_wall_seconds": wall_seconds,
                    "compression_user_seconds": values.get("user_seconds"),
                    "compression_sys_seconds": values.get("sys_seconds"),
                    "compression_max_rss_kb": values.get("max_rss_kb"),
                    "compression_metrics_file": compression.get(
                        "compression_metrics_file"
                    ),
                    "compression_timing_file": values.get("compression_timing_file"),
                    "compressed_size_bytes": size_bytes,
                    "compressed_size_ratio_vs_rdf": ratio_vs_rdf,
                    "compressed_size_ratio_vs_vcf": ratio_vs_vcf,
                    "compressed_size_reduction_pct_vs_rdf": reduction_pct_vs_rdf,
                    "rdf_size_bytes": rdf_size_bytes,
                    "input_vcf_size_bytes": input_vcf_size_bytes,
                    "total_triples": row.get("total_triples"),
                    "validation_present": values.get("validation_present"),
                    "validation_valid": values.get("validation_valid"),
                    "validation_count_match": values.get("validation_count_match"),
                    "validation_source_triples": values.get(
                        "validation_source_triples"
                    ),
                    "validation_decoded_triples": values.get(
                        "validation_decoded_triples"
                    ),
                    "validation_expected_triples": values.get(
                        "validation_expected_triples"
                    ),
                    "validation_validator": values.get("validation_validator"),
                    "validation_wall_seconds": values.get(
                        "validation_wall_seconds"
                    ),
                }
            )

        if successful_for_size:
            best_size = min(successful_for_size, key=lambda x: x["size_bytes"])
            row["best_method_by_size"] = best_size["method"]
            row["best_size_bytes"] = best_size["size_bytes"]
            row["best_size_ratio_vs_rdf"] = best_size["ratio_vs_rdf"]
        else:
            row["best_method_by_size"] = None
            row["best_size_bytes"] = None
            row["best_size_ratio_vs_rdf"] = None

        if successful_for_time:
            best_time = min(successful_for_time, key=lambda x: x["wall_seconds"])
            row["best_method_by_wall_time"] = best_time["method"]
            row["best_wall_seconds"] = best_time["wall_seconds"]
        else:
            row["best_method_by_wall_time"] = None
            row["best_wall_seconds"] = None

        dataset_rows.append(row)

    return {
        "schema_version": "1.2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_directory": run_directory,
        "run_name": run_name,
        "completion": completion,
        "dataset_count": len(dataset_rows),
        "tsv_record_count": sum(1 for row in dataset_rows if row.get("tsv_present")),
        "compression_record_count": len(method_rows),
        "integrity": {
            "missing_compression_wall_times": _missing_compression_wall_times(
                methods_by_dataset
            ),
        },
        "datasets": dataset_rows,
        "compression_by_method": method_rows,
    }


def build_combined_metrics(run_dirs: Sequence[Path]) -> Dict[str, Any]:
    run_results: List[Dict[str, Any]] = []
    dataset_rows: List[Dict[str, Any]] = []
    method_rows: List[Dict[str, Any]] = []
    missing_compression_wall_times: List[Dict[str, str]] = []
    unverified_runs: List[Dict[str, Any]] = []

    for run_dir in run_dirs:
        result = build_combined_metrics_for_run(run_dir)
        run_name = str(result["run_name"])
        completion = result["completion"]
        if completion["completion_state"] != "completed":
            unverified_runs.append({"run_name": run_name, **completion})
        for issue in result["integrity"]["missing_compression_wall_times"]:
            missing_compression_wall_times.append({"run_name": run_name, **issue})
        run_results.append(
            {
                "run_directory": result["run_directory"],
                "run_name": run_name,
                **completion,
                "dataset_count": result["dataset_count"],
                "tsv_record_count": result["tsv_record_count"],
                "compression_record_count": result["compression_record_count"],
                "missing_compression_wall_time_count": len(
                    result["integrity"]["missing_compression_wall_times"]
                ),
            }
        )
        dataset_rows.extend(result["datasets"])
        method_rows.extend(result["compression_by_method"])

    return {
        "schema_version": "1.2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_count": len(run_results),
        "run_directories": [entry["run_directory"] for entry in run_results],
        "runs": run_results,
        "dataset_count": len(dataset_rows),
        "tsv_record_count": sum(1 for row in dataset_rows if row.get("tsv_present")),
        "compression_record_count": len(method_rows),
        "integrity": {
            "all_runs_completed": not bool(unverified_runs),
            "unverified_or_incomplete_runs": unverified_runs,
            "all_successful_compression_wall_times_present": not bool(
                missing_compression_wall_times
            ),
            "missing_compression_wall_times": missing_compression_wall_times,
        },
        "datasets": dataset_rows,
        "compression_by_method": method_rows,
    }


def _require_compression_wall_times(combined: Dict[str, Any]) -> None:
    issues = (combined.get("integrity") or {}).get(
        "missing_compression_wall_times", []
    )
    if not issues:
        return

    details = "; ".join(
        f"{issue['run_name']}:{issue['dataset']}:{issue['method']} "
        f"({issue['reason']})"
        for issue in issues
    )
    raise SystemExit(
        "Refusing to write an aggregate with missing compression wall times. "
        f"Repair or investigate the source metrics first: {details}"
    )


def _dedupe_paths(paths: Sequence[Path]) -> List[Path]:
    unique_paths: List[Path] = []
    seen: set[str] = set()
    for path in paths:
        resolved = path.resolve()
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            unique_paths.append(resolved)
    return unique_paths


def _default_output_path(run_dirs: Sequence[Path]) -> Path:
    if len(run_dirs) == 1:
        return run_dirs[0] / "combined_metrics.json"

    parent_paths = {str(run_dir.parent.resolve()) for run_dir in run_dirs}
    if len(parent_paths) == 1:
        parent = Path(next(iter(parent_paths)))
        return parent / "combined_metrics_multi_run.json"

    return Path("combined_metrics_multi_run.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine conversion/compression benchmark metrics into one JSON file."
    )
    parser.add_argument(
        "run_dirs",
        nargs="+",
        type=Path,
        help=(
            "One or more benchmark run directories "
            "(e.g., benchmark-results/20260305T102641 benchmark-results/20260306T090000)"
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Output JSON file path "
            "(default: single run -> <run_dir>/combined_metrics.json, "
            "multiple runs -> sibling combined_metrics_multi_run.json)"
        ),
    )
    parser.add_argument(
        "--require-compression-wall-times",
        action="store_true",
        help=(
            "Fail instead of writing output when a selected compression method "
            "is missing its result or a successful method is missing wall_seconds."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dirs = _dedupe_paths(args.run_dirs)
    for run_dir in run_dirs:
        if not run_dir.exists() or not run_dir.is_dir():
            raise SystemExit(f"Run directory not found or not a directory: {run_dir}")

    combined = build_combined_metrics(run_dirs)
    if args.require_compression_wall_times:
        _require_compression_wall_times(combined)

    output_file = args.output or _default_output_path(run_dirs)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as handle:
        json.dump(combined, handle, indent=2)
        handle.write("\n")

    print(f"Wrote {output_file}")
    print(
        f"Runs: {combined['run_count']}, "
        f"datasets: {combined['dataset_count']}, "
        f"compression records: {combined['compression_record_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
