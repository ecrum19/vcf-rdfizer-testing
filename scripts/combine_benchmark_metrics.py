#!/usr/bin/env python3
"""Combine conversion, TSV, and compression metrics into a single JSON file.

The output JSON intentionally contains two views:
1) datasets: one row per dataset (convenient for paper tables)
2) compression_by_method: one row per dataset+method (tidy form for plotting)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


METHOD_SPECS: Dict[str, Dict[str, str]] = {
    "gzip": {
        "section_key": "gzip_raw_rdf",
        "size_key": "output_gz_size_bytes",
    },
    "brotli": {
        "section_key": "brotli_raw_rdf",
        "size_key": "output_brotli_size_bytes",
    },
    "hdt": {
        "section_key": "hdt_conversion",
        "size_key": "output_hdt_size_bytes",
    },
    "hdt_gzip": {
        "section_key": "gzip_on_hdt",
        "size_key": "output_hdt_gz_size_bytes",
    },
    "hdt_brotli": {
        "section_key": "brotli_on_hdt",
        "size_key": "output_hdt_br_size_bytes",
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
    for suffix in (".vcf.gz", ".vcf", ".gz", ".tsv"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return Path(name).stem


def _select_latest(
    current: Optional[Dict[str, Any]], candidate: Dict[str, Any]
) -> Dict[str, Any]:
    if current is None:
        return candidate
    current_ts = str(current.get("timestamp") or "")
    candidate_ts = str(candidate.get("timestamp") or "")
    if candidate_ts > current_ts:
        return candidate
    return current


def _dataset_from_conversion_path(payload: Dict[str, Any], path: Path) -> str:
    output_path = (payload.get("artifacts") or {}).get("output_path")
    if output_path:
        name = Path(str(output_path)).name
        if name:
            return name
    return path.parent.name


def _dataset_from_compression_path(payload: Dict[str, Any], path: Path) -> str:
    output_name = payload.get("output_name")
    if output_name:
        return str(output_name)
    return path.parent.name


def _dataset_from_prefixed_input_path(payload: Dict[str, Any], path: Path) -> str:
    prefix = payload.get("prefix")
    if prefix:
        return str(prefix)

    input_path = payload.get("input_path")
    if input_path:
        return _strip_known_suffixes(Path(str(input_path)).name)

    return path.parent.name


def _extract_conversion(payload: Dict[str, Any], source_file: Path) -> Dict[str, Any]:
    artifacts = payload.get("artifacts") or {}
    timing = payload.get("timing") or {}
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

    return {
        "method": method,
        "size_bytes": section.get(spec["size_key"]),
        "exit_code": section.get("exit_code"),
        "wall_seconds": timing.get("wall_seconds"),
        "user_seconds": timing.get("user_seconds"),
        "sys_seconds": timing.get("sys_seconds"),
        "max_rss_kb": timing.get("max_rss_kb"),
    }


def _extract_compression(
    payload: Dict[str, Any], source_file: Path
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    methods: Dict[str, Dict[str, Any]] = {}
    for method in METHOD_SPECS:
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
    }
    return summary, methods


def _iter_metric_files(run_dir: Path, section: str) -> Iterable[Path]:
    base = run_dir / section
    if not base.exists():
        return []
    return sorted(base.glob("*/*.json"))


def build_combined_metrics_for_run(run_dir: Path) -> Dict[str, Any]:
    conversion_by_dataset: Dict[str, Dict[str, Any]] = {}
    tsv_by_dataset: Dict[str, Dict[str, Any]] = {}
    compression_by_dataset: Dict[str, Dict[str, Any]] = {}
    methods_by_dataset: Dict[str, Dict[str, Dict[str, Any]]] = {}
    run_directory = str(run_dir.resolve())
    run_name = run_dir.name

    for conv_file in _iter_metric_files(run_dir, "conversion_metrics"):
        payload = _load_json(conv_file)
        dataset = _dataset_from_conversion_path(payload, conv_file)
        candidate = _extract_conversion(payload, conv_file)
        existing = conversion_by_dataset.get(dataset)
        conversion_by_dataset[dataset] = _select_latest(existing, candidate)

    for tsv_file in _iter_metric_files(run_dir, "tsv_metrics"):
        payload = _load_json(tsv_file)
        dataset = _dataset_from_prefixed_input_path(payload, tsv_file)
        candidate = _extract_tsv(payload, tsv_file)
        existing = tsv_by_dataset.get(dataset)
        tsv_by_dataset[dataset] = _select_latest(existing, candidate)

    for comp_file in _iter_metric_files(run_dir, "compression_metrics"):
        payload = _load_json(comp_file)
        dataset = _dataset_from_compression_path(payload, comp_file)
        summary, methods = _extract_compression(payload, comp_file)
        existing = compression_by_dataset.get(dataset)

        if _select_latest(existing, summary) is summary:
            compression_by_dataset[dataset] = summary
            methods_by_dataset[dataset] = methods

    all_datasets = sorted(
        set(conversion_by_dataset) | set(tsv_by_dataset) | set(compression_by_dataset)
    )

    dataset_rows: List[Dict[str, Any]] = []
    method_rows: List[Dict[str, Any]] = []

    for dataset in all_datasets:
        conversion = conversion_by_dataset.get(dataset, {})
        tsv = tsv_by_dataset.get(dataset, {})
        compression = compression_by_dataset.get(dataset, {})
        methods = methods_by_dataset.get(dataset, {})

        row: Dict[str, Any] = {
            "dataset": dataset,
            "run_directory": run_directory,
            "run_name": run_name,
            "run_id": conversion.get("run_id") or tsv.get("run_id") or compression.get("run_id"),
            "timestamp": conversion.get("timestamp") or tsv.get("timestamp") or compression.get("timestamp"),
            "conversion_present": bool(conversion),
            "tsv_present": bool(tsv),
            "compression_present": bool(compression),
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
            values = methods.get(method, {})
            size_bytes = values.get("size_bytes")
            wall_seconds = values.get("wall_seconds")
            exit_code = values.get("exit_code")

            ratio_vs_rdf = _safe_div(size_bytes, rdf_size_bytes)
            ratio_vs_vcf = _safe_div(size_bytes, input_vcf_size_bytes)
            reduction_pct_vs_rdf = None if ratio_vs_rdf is None else (1.0 - ratio_vs_rdf) * 100.0

            row[f"{method}_size_bytes"] = size_bytes
            row[f"{method}_exit_code"] = exit_code
            row[f"{method}_wall_seconds"] = wall_seconds
            row[f"{method}_user_seconds"] = values.get("user_seconds")
            row[f"{method}_sys_seconds"] = values.get("sys_seconds")
            row[f"{method}_max_rss_kb"] = values.get("max_rss_kb")
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
                    "compression_wall_seconds": wall_seconds,
                    "compression_user_seconds": values.get("user_seconds"),
                    "compression_sys_seconds": values.get("sys_seconds"),
                    "compression_max_rss_kb": values.get("max_rss_kb"),
                    "compressed_size_bytes": size_bytes,
                    "compressed_size_ratio_vs_rdf": ratio_vs_rdf,
                    "compressed_size_ratio_vs_vcf": ratio_vs_vcf,
                    "compressed_size_reduction_pct_vs_rdf": reduction_pct_vs_rdf,
                    "rdf_size_bytes": rdf_size_bytes,
                    "input_vcf_size_bytes": input_vcf_size_bytes,
                    "total_triples": row.get("total_triples"),
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
        "schema_version": "1.1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_directory": run_directory,
        "run_name": run_name,
        "dataset_count": len(dataset_rows),
        "tsv_record_count": sum(1 for row in dataset_rows if row.get("tsv_present")),
        "compression_record_count": len(method_rows),
        "datasets": dataset_rows,
        "compression_by_method": method_rows,
    }


def build_combined_metrics(run_dirs: Sequence[Path]) -> Dict[str, Any]:
    run_results: List[Dict[str, Any]] = []
    dataset_rows: List[Dict[str, Any]] = []
    method_rows: List[Dict[str, Any]] = []

    for run_dir in run_dirs:
        result = build_combined_metrics_for_run(run_dir)
        run_results.append(
            {
                "run_directory": result["run_directory"],
                "run_name": result["run_name"],
                "dataset_count": result["dataset_count"],
                "tsv_record_count": result["tsv_record_count"],
                "compression_record_count": result["compression_record_count"],
            }
        )
        dataset_rows.extend(result["datasets"])
        method_rows.extend(result["compression_by_method"])

    return {
        "schema_version": "1.1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_count": len(run_results),
        "run_directories": [entry["run_directory"] for entry in run_results],
        "runs": run_results,
        "dataset_count": len(dataset_rows),
        "tsv_record_count": sum(1 for row in dataset_rows if row.get("tsv_present")),
        "compression_record_count": len(method_rows),
        "datasets": dataset_rows,
        "compression_by_method": method_rows,
    }


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dirs = _dedupe_paths(args.run_dirs)
    for run_dir in run_dirs:
        if not run_dir.exists() or not run_dir.is_dir():
            raise SystemExit(f"Run directory not found or not a directory: {run_dir}")

    output_file = args.output or _default_output_path(run_dirs)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    combined = build_combined_metrics(run_dirs)
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
