#!/usr/bin/env python3
"""Turn 16_scale_retrieval cells into a per-query retrieval dataset.

One row per (scale, engine, artifact, query), aggregated over replicates.

What this reads, and why it is not collect_metrics.py:

* ``benchmark.csv``  the per-query timings the validation runner writes. This
  is the measurement. collect_metrics.py aggregates a cell to ONE row, which
  is right for a conversion experiment and wrong here -- the whole point of
  this experiment is the per-query shape.
* ``summary.json``   status, the selected query list, and ``answersAgree``.
* the scale manifest, for the identity of the graph that was queried.

THE TWO COLUMNS THAT ARE NOT THE SAME MEASUREMENT
-------------------------------------------------
``wall_seconds`` is one query on one engine. ``oracle_wall_seconds`` is the
parser's total for ALL queries in the run, repeated on every row so the CSV
needs no join. Dividing them row-wise divides one query by thirteen. The
per-query oracle column here is ``oracle_query_seconds``, which the runner
attributes from measured phases; where it is absent the field is left empty
rather than filled with the batch total.

ANSWER EQUALITY COMES FIRST
---------------------------
A row whose query disagreed with the oracle is reported with ``status`` other
than PASS and is excluded from the medians. A timing whose answer was never
checked is not a measurement, so a scale whose ``answersAgree`` is false is
reported loudly at the end and its rows are marked.

Usage:
    python3 scale_retrieval.py [experiment] [--results DIR] [--csv PATH]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import statistics
import sys

DEFAULT_EXPERIMENT = "16_scale_retrieval"


def default_results_root() -> pathlib.Path:
    env = os.environ.get("BM_RESULTS")
    if env:
        return pathlib.Path(env)
    return pathlib.Path(__file__).resolve().parent.parent / "results"


def read_json(path: pathlib.Path | None):
    # find_one() returns None when nothing matched, and a cell that failed
    # before writing its reports is exactly the case this has to survive --
    # crashing there would lose the analysis of every cell that did succeed.
    if path is None:
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def find_one(root: pathlib.Path, name: str) -> pathlib.Path | None:
    matches = sorted(root.rglob(name))
    return matches[0] if matches else None


def cell_rows(cell: pathlib.Path) -> list[dict]:
    """Every per-query timing this cell recorded, with its provenance attached."""
    bench = read_json(cell / "bench.json") or {}
    if bench.get("skipped"):
        return [{
            "cell": cell.name, "skipped": True,
            "skip_reason": bench.get("reason", ""),
        }]

    summary_path = find_one(cell / "out", "summary.json")
    summary = read_json(summary_path) if summary_path else None
    # The runner decodes the artifact to N-Triples before any engine runs, for
    # the syntax and cardinality check, and that cost is paid once per cell
    # whatever the engine. At whole-genome scale it is roughly 99 GB of text,
    # so it dominates cell wall time while belonging to neither side of the
    # retrieval comparison. Report it separately rather than letting it hide
    # inside the cell total.
    materialization = read_json(find_one(cell / "out", "materialization.json")) or {}
    benchmark_csv = find_one(cell / "out", "benchmark.csv")
    if benchmark_csv is None:
        return [{
            "cell": cell.name, "skipped": True,
            "skip_reason": "no benchmark.csv -- the run produced no timings",
            "exit_code": bench.get("exit_code"),
        }]

    # scale__engine__artifact__rN
    parts = cell.name.split("__")
    scale = parts[0] if parts else ""
    engine_label = parts[1] if len(parts) > 1 else ""
    artifact = parts[2].replace("_", ".") if len(parts) > 2 else ""
    rep = parts[3] if len(parts) > 3 else ""

    rows = []
    with open(benchmark_csv) as handle:
        for row in csv.DictReader(handle):
            rows.append({
                "cell": cell.name,
                "skipped": False,
                "scale": scale,
                "engine": row.get("engine") or engine_label,
                "artifact": artifact,
                "replicate": rep,
                "query_id": row.get("query_id", ""),
                "status": row.get("status", ""),
                "wall_seconds": row.get("wall_seconds", ""),
                # Per-query oracle cost where the runner attributed one. NOT
                # oracle_wall_seconds, which is the batch total.
                "oracle_query_seconds": row.get("oracle_query_seconds", ""),
                "oracle_batch_seconds": row.get("oracle_wall_seconds", ""),
                "engine_setup_seconds": row.get("engine_setup_seconds", ""),
                "exit_code": bench.get("exit_code"),
                "run_status": (summary or {}).get("status", ""),
                "answers_agree": (summary or {}).get("answersAgree", ""),
                "tool_commit": bench.get("tool_commit", ""),
                "image_digest": bench.get("image_digest", ""),
                "host": bench.get("host", ""),
                "materialize_seconds": materialization.get("wallSeconds", ""),
                "materialized": materialization.get("materialized", ""),
            })
    return rows


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def aggregate(rows: list[dict]) -> list[dict]:
    """Median over replicates, per (scale, engine, artifact, query)."""
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        if row.get("skipped"):
            continue
        key = (row["scale"], row["engine"], row["artifact"], row["query_id"])
        groups.setdefault(key, []).append(row)

    out = []
    for (scale, engine, artifact, query_id), items in sorted(groups.items()):
        # Only rows whose answer was verified equal contribute a timing.
        passing = [r for r in items if r["status"] == "PASS"]
        seconds = [s for s in (to_float(r["wall_seconds"]) for r in passing) if s is not None]
        setups = [s for s in (to_float(r["engine_setup_seconds"]) for r in passing) if s is not None]
        oracle = [s for s in (to_float(r["oracle_query_seconds"]) for r in passing) if s is not None]
        out.append({
            "scale": scale,
            "engine": engine,
            "artifact": artifact,
            "query_id": query_id,
            "replicates": len(items),
            "replicates_passing": len(passing),
            "statuses": "|".join(sorted({r["status"] for r in items})),
            "median_query_seconds": round(statistics.median(seconds), 6) if seconds else "",
            "min_query_seconds": round(min(seconds), 6) if seconds else "",
            "max_query_seconds": round(max(seconds), 6) if seconds else "",
            "median_setup_seconds": round(statistics.median(setups), 6) if setups else "",
            "median_oracle_query_seconds": round(statistics.median(oracle), 6) if oracle else "",
            "speedup_vs_oracle": (
                round(statistics.median(oracle) / statistics.median(seconds), 3)
                if oracle and seconds and statistics.median(seconds) > 0 else ""
            ),
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment", nargs="?", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--results", type=pathlib.Path, default=None)
    parser.add_argument("--csv", type=pathlib.Path, default=None)
    args = parser.parse_args()

    root = (args.results or default_results_root()) / args.experiment
    if not root.is_dir():
        print(f"no such experiment directory: {root}", file=sys.stderr)
        return 1

    raw: list[dict] = []
    for cell in sorted(p for p in root.iterdir() if p.is_dir()):
        raw.extend(cell_rows(cell))

    measured = [r for r in raw if not r.get("skipped")]
    skipped = [r for r in raw if r.get("skipped")]
    if not measured:
        print(f"{root}: no timings recorded", file=sys.stderr)
        for row in skipped:
            print(f"  skipped {row['cell']}: {row.get('skip_reason','')}", file=sys.stderr)
        return 1

    summary_rows = aggregate(measured)

    out_csv = args.csv or (root / "retrieval.csv")
    with open(out_csv, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    (root / "retrieval-raw.json").write_text(json.dumps(measured, indent=2) + "\n")

    print(f"{len(measured)} timings from {len({r['cell'] for r in measured})} cells")
    print(f"wrote {out_csv}")
    print(f"wrote {root / 'retrieval-raw.json'}")

    # Per scale/engine/artifact totals, which is the number the figure uses.
    print()
    print(f"{'scale':<12}{'engine':<10}{'artifact':<10}{'queries':>8}{'total s':>12}{'setup s':>10}")
    totals: dict[tuple, list[float]] = {}
    setups: dict[tuple, float] = {}
    for row in summary_rows:
        if row["median_query_seconds"] == "":
            continue
        key = (row["scale"], row["engine"], row["artifact"])
        totals.setdefault(key, []).append(row["median_query_seconds"])
        if row["median_setup_seconds"] != "":
            setups[key] = row["median_setup_seconds"]
    for key in sorted(totals):
        scale, engine, artifact = key
        values = totals[key]
        print(f"{scale:<12}{engine:<10}{artifact:<10}{len(values):>8}"
              f"{sum(values):>12.3f}{setups.get(key, 0):>10.3f}")

    disagreed = sorted({
        (r["scale"], r["engine"], r["artifact"])
        for r in measured if r["answers_agree"] is False
    })
    if disagreed:
        print()
        print("ANSWERS DISAGREED -- do not quote these timings:", file=sys.stderr)
        for item in disagreed:
            print(f"  {item}", file=sys.stderr)
        return 1

    if skipped:
        print()
        print(f"{len(skipped)} cells recorded no timings:")
        for row in skipped:
            print(f"  {row['cell']}: {row.get('skip_reason','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
