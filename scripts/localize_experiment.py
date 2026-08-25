#!/usr/bin/env python3
"""Copy a completed run into a named archive and rebuild its aggregate metrics.

VCF-RDFizer stores a run below ``experiments/run_metrics/<run-id>`` where the
run ID is normally a timestamp.  This script gives that run a stable,
human-readable directory name below ``experiments/finished_experiments`` and
then invokes ``combine_benchmark_metrics.py`` for every named run in that
directory.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = REPOSITORY_ROOT / "experiments" / "run_metrics"
DEFAULT_FINISHED_ROOT = REPOSITORY_ROOT / "experiments" / "finished_experiments"
COMBINER_SCRIPT = Path(__file__).resolve().with_name("combine_benchmark_metrics.py")


def _resolve_path(path: Path) -> Path:
    """Resolve a user-supplied path relative to the current working directory."""

    return path.expanduser().resolve()


def _resolve_run_directory(run: str, source_root: Path) -> Path:
    """Resolve either a run ID below ``source_root`` or an explicit path."""

    candidate = Path(run).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()

    from_current_directory = (Path.cwd() / candidate).resolve()
    if from_current_directory.is_dir():
        return from_current_directory

    return (source_root / candidate).resolve()


def _validate_run_name(name: str) -> str:
    """Ensure ``name`` can only address one child directory."""

    if not name or name in {".", ".."} or name.startswith("."):
        raise ValueError("the experiment name must not be empty or hidden")

    name_path = Path(name)
    if name_path.name != name or name_path.is_absolute():
        raise ValueError("the experiment name must be a single directory name")

    return name


def _localized_run_directories(finished_root: Path) -> list[Path]:
    """Return all named run directories, excluding files such as the aggregate."""

    return sorted(
        (
            path
            for path in finished_root.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        ),
        key=lambda path: path.name,
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy a timestamped VCF-RDFizer run into a named directory and "
            "rebuild the aggregate metrics JSON."
        )
    )
    parser.add_argument(
        "run",
        help=(
            "Run ID below experiments/run_metrics, or a path to a run "
            "directory (for example, 20260824T173012)."
        ),
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Human-readable name for this run, used as its archive directory name.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help=f"Root containing timestamped runs (default: {DEFAULT_SOURCE_ROOT}).",
    )
    parser.add_argument(
        "--finished-root",
        type=Path,
        default=DEFAULT_FINISHED_ROOT,
        help=(
            "Directory containing named runs and the aggregate output "
            f"(default: {DEFAULT_FINISHED_ROOT})."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Aggregate JSON output path "
            "(default: <finished-root>/combined_metrics_multi_run.json)."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing localized run with the same name.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        experiment_name = _validate_run_name(args.name)
    except ValueError as error:
        raise SystemExit(f"Invalid experiment name: {error}") from error

    source_root = _resolve_path(args.source_root)
    finished_root = _resolve_path(args.finished_root)
    source_run = _resolve_run_directory(args.run, source_root)
    destination_run = finished_root / experiment_name
    output_file = (
        _resolve_path(args.output)
        if args.output
        else finished_root / "combined_metrics_multi_run.json"
    )

    if not source_run.is_dir():
        raise SystemExit(f"Run directory not found or not a directory: {source_run}")
    if source_run.resolve() == destination_run.resolve():
        raise SystemExit("The source run and destination run are the same directory.")
    if not COMBINER_SCRIPT.is_file():
        raise SystemExit(f"Combiner script not found: {COMBINER_SCRIPT}")

    finished_root.mkdir(parents=True, exist_ok=True)

    if destination_run.exists():
        if not args.overwrite:
            raise SystemExit(
                f"Localized run already exists: {destination_run}\n"
                "Choose another --name or pass --overwrite to replace it."
            )
        if not destination_run.is_dir():
            raise SystemExit(f"Destination exists but is not a directory: {destination_run}")
        shutil.rmtree(destination_run)

    print(f"Copying {source_run} -> {destination_run}", flush=True)
    shutil.copytree(source_run, destination_run)

    run_directories = _localized_run_directories(finished_root)
    if not run_directories:
        raise SystemExit(f"No localized experiment directories found in {finished_root}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(COMBINER_SCRIPT),
        *(str(run_directory) for run_directory in run_directories),
        "--output",
        str(output_file),
    ]
    print(
        "Rebuilding aggregate metrics for: "
        + ", ".join(path.name for path in run_directories),
        flush=True,
    )
    subprocess.run(command, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
