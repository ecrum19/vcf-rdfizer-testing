#!/usr/bin/env python3
"""Generate a comparison figure from combined_metrics.json."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def _to_scaled(values: List[Dict[str, Any]], key: str, scale: float) -> List[float]:
    scaled: List[float] = []
    for row in values:
        raw = row.get(key)
        if isinstance(raw, (int, float)):
            scaled.append(raw * scale)
        else:
            scaled.append(float("nan"))
    return scaled


def _row_label(row: Dict[str, Any], duplicate_datasets: Set[str], multi_run: bool) -> str:
    dataset = str(row.get("dataset", "unknown"))
    run_name = str(row.get("run_name") or row.get("run_id") or "")
    if multi_run and dataset in duplicate_datasets and run_name:
        return f"{run_name}:{dataset}"
    return dataset


def _load_rows(metrics_path: Path) -> Tuple[List[Dict[str, Any]], bool, Set[str]]:
    with metrics_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    rows = payload.get("datasets")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No dataset rows found in {metrics_path}")

    rows = sorted(
        rows,
        key=lambda row: (
            float(row.get("input_vcf_size_bytes") or float("inf")),
            str(row.get("dataset") or ""),
        ),
    )
    run_count = int(payload.get("run_count") or 1)
    seen: Set[str] = set()
    duplicate_datasets: Set[str] = set()
    for row in rows:
        dataset = str(row.get("dataset", "unknown"))
        if dataset in seen:
            duplicate_datasets.add(dataset)
        seen.add(dataset)
    return rows, run_count > 1, duplicate_datasets


def _bar_offsets(num_series: int, width: float) -> List[float]:
    center = (num_series - 1) / 2
    return [(idx - center) * width for idx in range(num_series)]


def make_figure(metrics_path: Path, output_path: Path, title: str, show: bool) -> None:
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "matplotlib is required to generate figures. Install it with: "
            "python3 -m pip install matplotlib"
        ) from exc

    rows, multi_run, duplicate_datasets = _load_rows(metrics_path)
    labels = [_row_label(row, duplicate_datasets, multi_run) for row in rows]
    x = list(range(len(rows)))

    fig, axes = plt.subplots(3, 1, figsize=(13, 14), sharex=True)
    fig.suptitle(title, fontsize=16)

    # 1) Size comparison (GB)
    size_series = [
        ("input_vcf_size_bytes", "VCF input"),
        ("rdf_size_bytes", "RDF output"),
        ("gzip_size_bytes", "RDF + gzip"),
        ("brotli_size_bytes", "RDF + brotli"),
        ("hdt_size_bytes", "HDT"),
        ("hdt_gzip_size_bytes", "HDT + gzip"),
        ("hdt_brotli_size_bytes", "HDT + brotli"),
    ]
    size_width = 0.11
    size_offsets = _bar_offsets(len(size_series), size_width)
    for offset, (key, legend_label) in zip(size_offsets, size_series):
        vals = _to_scaled(rows, key, 1 / 1e9)
        axes[0].bar([xi + offset for xi in x], vals, width=size_width, label=legend_label)
    axes[0].set_ylabel("Size (GB)")
    axes[0].set_title("Dataset Sizes by Representation")
    axes[0].grid(axis="y", linestyle="--", alpha=0.4)
    axes[0].legend(ncols=2, fontsize=9)

    # 2) Wall-clock time comparison (seconds)
    time_series = [
        ("conversion_wall_seconds", "Conversion"),
        ("gzip_wall_seconds", "gzip"),
        ("brotli_wall_seconds", "brotli"),
        ("hdt_wall_seconds", "HDT"),
        ("hdt_gzip_wall_seconds", "HDT + gzip"),
        ("hdt_brotli_wall_seconds", "HDT + brotli"),
    ]
    time_width = 0.13
    time_offsets = _bar_offsets(len(time_series), time_width)
    for offset, (key, legend_label) in zip(time_offsets, time_series):
        vals = _to_scaled(rows, key, 1.0)
        axes[1].bar([xi + offset for xi in x], vals, width=time_width, label=legend_label)
    axes[1].set_ylabel("Wall time (s)")
    axes[1].set_title("Computation Cost by Step")
    axes[1].grid(axis="y", linestyle="--", alpha=0.4)
    axes[1].legend(ncols=3, fontsize=9)

    # 3) Peak memory comparison (GB)
    memory_series = [
        ("conversion_max_rss_kb", "Conversion"),
        ("gzip_max_rss_kb", "gzip"),
        ("brotli_max_rss_kb", "brotli"),
        ("hdt_max_rss_kb", "HDT"),
        ("hdt_gzip_max_rss_kb", "HDT + gzip"),
        ("hdt_brotli_max_rss_kb", "HDT + brotli"),
    ]
    mem_width = 0.13
    mem_offsets = _bar_offsets(len(memory_series), mem_width)
    for offset, (key, legend_label) in zip(mem_offsets, memory_series):
        vals = _to_scaled(rows, key, 1 / (1024 * 1024))
        axes[2].bar([xi + offset for xi in x], vals, width=mem_width, label=legend_label)
    axes[2].set_ylabel("Peak RSS (GB)")
    axes[2].set_title("Peak Memory by Step")
    axes[2].grid(axis="y", linestyle="--", alpha=0.4)
    axes[2].legend(ncols=3, fontsize=9)

    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels, rotation=25, ha="right")

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220)

    if show:
        plt.show()
    else:
        plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a multi-panel benchmark figure from combined_metrics.json."
    )
    parser.add_argument(
        "combined_metrics_json",
        type=Path,
        help="Path to combined_metrics.json",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output image path (default: <input_dir>/combined_metrics_figure.png)",
    )
    parser.add_argument(
        "--title",
        default="VCF-RDF Benchmark: Size, Time, and Memory",
        help="Figure title.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the figure interactively in addition to saving it.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metrics_path = args.combined_metrics_json
    if not metrics_path.exists():
        raise SystemExit(f"Metrics file not found: {metrics_path}")

    if args.output is None:
        output_path = metrics_path.with_name("combined_metrics_figure.png")
    else:
        output_path = args.output

    make_figure(metrics_path, output_path, args.title, args.show)

    if output_path.exists() and output_path.stat().st_size > 0:
        size_kb = int(math.ceil(output_path.stat().st_size / 1024))
        print(f"Wrote {output_path} ({size_kb} KB)")
    else:
        raise SystemExit(f"Failed to create figure at {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
