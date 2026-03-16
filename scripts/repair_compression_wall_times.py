#!/usr/bin/env python3
"""Repair batch compression wall times from wrapper logs.

Some historical benchmark runs recorded incorrect wall-clock totals for
partitioned compression stages. This utility reconstructs per-method wall time
totals from the wrapper command log and patches the per-run timing artifacts.

The repair updates:
- compression_time/<method>/<dataset>/*.txt
- compression_metrics/<dataset>/*.json
- metrics.csv rows whose output_name matches the dataset
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple


METHOD_COLUMN_MAP = {
    "gzip": "wall_seconds_gzip",
    "brotli": "wall_seconds_brotli",
    "hdt": "wall_seconds_hdt",
    "hdt_gzip": "wall_seconds_gzip_on_hdt",
    "hdt_brotli": "wall_seconds_brotli_on_hdt",
}

METHOD_JSON_PATH_MAP = {
    "gzip": ("gzip_raw_rdf", "timing", "wall_seconds"),
    "brotli": ("brotli_raw_rdf", "timing", "wall_seconds"),
    "hdt": ("hdt_conversion", "timing", "wall_seconds"),
    "hdt_gzip": ("gzip_on_hdt", "timing", "wall_seconds"),
    "hdt_brotli": ("brotli_on_hdt", "timing", "wall_seconds"),
}

LOG_COMMAND_RE = re.compile(r"^\[(?P<timestamp>[^\]]+)\] \$ (?P<command>.*)$")
TIME_FILE_RE = re.compile(
    r"/data/out/\.(?P<part>\d+)\.(?P<method>hdt_brotli|hdt_gzip|brotli|gzip|hdt)\.time"
)
DATASET_RE = re.compile(r"/benchmark-results/[^/]+/(?P<dataset>[^:/\s]+):/data/in:ro")


def _format_seconds(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _read_run_end(run_dir: Path) -> datetime:
    timing_file = run_dir / "wrapper_execution_times.csv"
    if not timing_file.exists():
        raise FileNotFoundError(f"Missing wrapper_execution_times.csv: {timing_file}")

    with timing_file.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError(f"No rows found in {timing_file}")

    row = rows[-1]
    start = datetime.fromisoformat(row["timestamp"])
    elapsed = float(row["elapsed_seconds"])
    return start + timedelta(seconds=elapsed)


def _read_wrapper_log(run_dir: Path) -> Path:
    log_dir = run_dir / "wrapper_logs"
    logs = sorted(log_dir.glob("*.log"))
    if not logs:
        raise FileNotFoundError(f"No wrapper log found in {log_dir}")
    return logs[-1]


def _recover_wall_seconds(run_dir: Path) -> Dict[Tuple[str, str], float]:
    run_end = _read_run_end(run_dir)
    log_path = _read_wrapper_log(run_dir)
    commands: List[Tuple[datetime, str]] = []

    for line in log_path.read_text(encoding="utf-8").splitlines():
        match = LOG_COMMAND_RE.match(line)
        if not match:
            continue
        commands.append((datetime.fromisoformat(match.group("timestamp")), match.group("command")))

    recovered: Dict[Tuple[str, str], float] = {}
    for index, (started_at, command) in enumerate(commands):
        time_match = TIME_FILE_RE.search(command)
        if not time_match:
            continue
        dataset_match = DATASET_RE.search(command)
        if not dataset_match:
            continue

        next_started_at = commands[index + 1][0] if index + 1 < len(commands) else run_end
        wall_seconds = (next_started_at - started_at).total_seconds()
        if wall_seconds < 0:
            raise ValueError(
                f"Negative duration recovered for {run_dir.name} {dataset_match.group('dataset')} "
                f"{time_match.group('method')}"
            )

        key = (dataset_match.group("dataset"), time_match.group("method"))
        recovered[key] = recovered.get(key, 0.0) + wall_seconds

    return recovered


def _update_timing_text(path: Path, wall_seconds: float) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines: List[str] = []

    for line in lines:
        if line.startswith("wall_seconds="):
            new_lines.append(f"wall_seconds={_format_seconds(wall_seconds)}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"wall_seconds={_format_seconds(wall_seconds)}")

    old_text = path.read_text(encoding="utf-8")
    new_text = "\n".join(new_lines) + "\n"
    if new_text == old_text:
        return False

    path.write_text(new_text, encoding="utf-8")
    return True


def _set_nested(mapping: MutableMapping[str, object], path: Iterable[str], value: float) -> bool:
    current: MutableMapping[str, object] = mapping
    keys = list(path)
    for key in keys[:-1]:
        nested = current.get(key)
        if not isinstance(nested, MutableMapping):
            return False
        current = nested

    leaf = keys[-1]
    if current.get(leaf) == value:
        return False
    current[leaf] = value
    return True


def _update_metrics_json(path: Path, wall_by_method: Mapping[str, float]) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    for method, seconds in wall_by_method.items():
        json_path = METHOD_JSON_PATH_MAP.get(method)
        if not json_path:
            continue
        changed = _set_nested(payload, json_path, seconds) or changed

    if not changed:
        return False

    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return True


def _update_metrics_csv(path: Path, recovered: Mapping[Tuple[str, str], float]) -> bool:
    if not path.exists():
        return False

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames

    if not fieldnames:
        return False

    changed = False
    for row in rows:
        dataset = row.get("output_name")
        if not dataset:
            continue
        for method, column in METHOD_COLUMN_MAP.items():
            seconds = recovered.get((dataset, method))
            if seconds is None or column not in row:
                continue
            formatted = f"{seconds:.6f}"
            if row[column] != formatted:
                row[column] = formatted
                changed = True

    if not changed:
        return False

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return True


def repair_run(run_dir: Path) -> Dict[str, int]:
    recovered = _recover_wall_seconds(run_dir)
    changed_counts = {
        "compression_time_files": 0,
        "compression_metrics_files": 0,
        "metrics_csv_files": 0,
    }

    grouped_by_dataset: Dict[str, Dict[str, float]] = {}
    for (dataset, method), seconds in recovered.items():
        grouped_by_dataset.setdefault(dataset, {})[method] = seconds

    for dataset, wall_by_method in grouped_by_dataset.items():
        for method, seconds in wall_by_method.items():
            timing_dir = run_dir / "compression_time" / method / dataset
            for timing_file in sorted(timing_dir.glob("*.txt")):
                if _update_timing_text(timing_file, seconds):
                    changed_counts["compression_time_files"] += 1

        metrics_dir = run_dir / "compression_metrics" / dataset
        for metrics_file in sorted(metrics_dir.glob("*.json")):
            if _update_metrics_json(metrics_file, wall_by_method):
                changed_counts["compression_metrics_files"] += 1

    if _update_metrics_csv(run_dir / "metrics.csv", recovered):
        changed_counts["metrics_csv_files"] += 1

    return changed_counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair batch compression wall times using wrapper log timestamps."
    )
    parser.add_argument(
        "run_dirs",
        nargs="+",
        type=Path,
        help="One or more benchmark run directories to repair.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for run_dir in args.run_dirs:
        if not run_dir.exists() or not run_dir.is_dir():
            raise SystemExit(f"Run directory not found or not a directory: {run_dir}")

    for run_dir in args.run_dirs:
        changed_counts = repair_run(run_dir.resolve())
        print(
            f"Repaired {run_dir}: "
            f"{changed_counts['compression_time_files']} timing files, "
            f"{changed_counts['compression_metrics_files']} compression metrics files, "
            f"{changed_counts['metrics_csv_files']} metrics.csv files"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
