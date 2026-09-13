#!/usr/bin/env python3
"""Fit empirical scaling exponents on a log-log axis.

Plan §2.2 and §3.1. Slopes are fitted ONLY on derived ladders, where exactly
one thing varies and everything else is held constant by construction. Running
this across the ten-file corpus would estimate a mixture of genomic content
differences rather than the tool's scaling — see §3.2, and do not do it.

The headline §2 result is two slopes on one axis from the same variant content:

    expanded   log(triples) ~ log(samples)   slope ~1
    condensed  log(triples) ~ log(samples)   slope ~0

Usage:
    python3 fit_scaling.py 03_sample_representation --x samples --y triples --group mode
    python3 fit_scaling.py 04_scaling_records --x records --y triples
    python3 fit_scaling.py 04_scaling_records --x triples --y wall_seconds
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
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


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import stats  # noqa: E402

# Named axes, so a command line reads as the question being asked rather than
# as a column name. Each entry resolves a row to a number.
X_AXES = {
    "samples": lambda r: _from_cell(r, r"__s(\d+)\b") or _from_cell(r, r"\bs(\d+)__"),
    "records": lambda r: _from_cell(r, r"__r(\d+)\b") or _from_cell(r, r"\br(\d+)__"),
    "triples": lambda r: _number(r.get("output_triples")),
    "input_bytes": lambda r: _number(r.get("input_vcf_size_bytes")),
}
Y_AXES = {
    "triples": lambda r: _number(r.get("output_triples")),
    "wall_seconds": lambda r: _number(r.get("wall_seconds_java")
                                      or r.get("wrapper_wall_seconds")),
    "peak_rss_kb": lambda r: _number(r.get("max_rss_kb_java")),
    "artifact_bytes": lambda r: _number(r.get("final_out_tree_bytes")),
    "peak_host_workspace": lambda r: _number(r.get("peak_host_out_tree_bytes")),
}
GROUPS = {
    "mode": "sample_representation",
    "storage": "rdf_storage_mode",
    "info": "info_representation",
    "strategy": "hdt_strategy",
    "none": None,
}


def _number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _from_cell(row: dict, pattern: str):
    """Read a ladder rung out of the cell name.

    The rung is part of the cell's identity — s256, r100000 — and the derived
    inputs carry the real counts in their .provenance.json. Where the requested
    and actual counts differ (a rung larger than the source), prefer the
    provenance value; see --provenance.
    """
    match = re.search(pattern, row.get("cell") or "")
    return float(match.group(1)) if match else None


def load(experiment: str, results: pathlib.Path) -> list[dict]:
    tidy = results / experiment / "tidy.json"
    if not tidy.is_file():
        raise SystemExit(f"{tidy} not found. Run:\n  python3 collect_metrics.py {experiment}")
    rows = json.loads(tidy.read_text())
    return [r for r in rows if not r.get("skipped") and r.get("exit_code") == 0]


def apply_provenance(rows: list[dict], derived_dir: pathlib.Path) -> None:
    """Replace requested rung counts with the counts actually in the file."""
    if not derived_dir.is_dir():
        return
    provenance = {}
    for path in derived_dir.glob("*.provenance.json"):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        provenance[data.get("derived_file")] = data
    for row in rows:
        entry = provenance.get(row.get("input"))
        if entry:
            row["_records_actual"] = entry.get("data_records")
            row["_samples_actual"] = entry.get("sample_columns")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment")
    parser.add_argument("--x", default="records", choices=sorted(X_AXES))
    parser.add_argument("--y", default="triples", choices=sorted(Y_AXES))
    parser.add_argument("--group", default="none", choices=sorted(GROUPS))
    parser.add_argument("--results", default=None)
    parser.add_argument("--derived", default=None,
                        help="derived-input directory, for real rung counts")
    parser.add_argument("--cell-filter", default=None,
                        help="only cells whose name contains this substring. Use it to "
                             "keep one cell KIND in the fit: an experiment that also ran "
                             "timing repetitions at some rungs would otherwise collapse "
                             "both kinds together at those rungs")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    results = pathlib.Path(args.results) if args.results \
        else default_results_root()
    rows = load(args.experiment, results)
    if args.cell_filter:
        rows = [r for r in rows if args.cell_filter in (r.get("cell") or "")]
        if not rows:
            raise SystemExit(f"no successful cells contain {args.cell_filter!r}")

    derived = pathlib.Path(args.derived) if args.derived \
        else pathlib.Path(__file__).resolve().parent.parent.parent / "vcf_data" / "derived"
    apply_provenance(rows, derived)

    x_of, y_of = X_AXES[args.x], Y_AXES[args.y]
    group_column = GROUPS[args.group]

    # Prefer provenance counts where the axis is a ladder rung.
    def x_value(row):
        if args.x == "records" and row.get("_records_actual"):
            return float(row["_records_actual"])
        if args.x == "samples" and row.get("_samples_actual"):
            return float(row["_samples_actual"])
        return x_of(row)

    buckets: dict[str, list[tuple[float, float]]] = {}
    for row in rows:
        xv, yv = x_value(row), y_of(row)
        if xv is None or yv is None or xv <= 0 or yv <= 0:
            continue
        key = str(row.get(group_column)) if group_column else "all"
        buckets.setdefault(key, []).append((xv, yv))

    if not buckets:
        raise SystemExit(
            f"no usable points for x={args.x}, y={args.y}.\n"
            "Check that the cells carry the rung in their name (e.g. __s256, __r100000)\n"
            "and that the runs recorded the metric."
        )

    print(f"\nlog({args.y}) ~ log({args.x})   [{args.experiment}]\n")
    fits = {}
    for key in sorted(buckets):
        points = sorted(buckets[key])
        # Median-collapse repeated runs at the same rung so repetitions do not
        # inflate n and shrink the CI dishonestly.
        collapsed: dict[float, list[float]] = {}
        for xv, yv in points:
            collapsed.setdefault(xv, []).append(yv)
        xs = sorted(collapsed)
        ys = [stats.median(collapsed[x]) for x in xs]

        if args.y == "triples":
            for x in xs:
                values = set(collapsed[x])
                if len(values) > 1:
                    print(f"  warning: rung x={x:,.0f} has {len(values)} different "
                          f"triple counts {sorted(values)}.\n"
                          f"           Triples are deterministic, so this means the fit is "
                          f"mixing cell kinds.\n"
                          f"           Restrict it, e.g. --cell-filter __structure",
                          file=sys.stderr)

        fit = stats.loglog_slope(xs, ys)
        fit["group"] = key
        fit["points"] = [{"x": x, "y": y, "reps": len(collapsed[x])} for x, y in zip(xs, ys)]
        fits[key] = fit

        ci = ""
        if "slope_ci_low" in fit:
            ci = f"  95% CI [{fit['slope_ci_low']:+.3f}, {fit['slope_ci_high']:+.3f}]"
        r2 = f"  R^2={fit['r_squared']:.4f}" if fit.get("r_squared") == fit.get("r_squared") else ""
        print(f"  {key:<16} n={fit['n']}  slope={fit['slope']:+.3f}{ci}{r2}")
        for point in fit["points"]:
            print(f"      x={point['x']:>12,.0f}  y={point['y']:>16,.0f}  "
                  f"({point['reps']} rep{'s' if point['reps'] != 1 else ''})")

    if args.group == "mode" and {"expanded", "condensed"} <= set(fits):
        e, c = fits["expanded"]["slope"], fits["condensed"]["slope"]
        print(f"\n  expanded slope {e:+.3f} vs condensed slope {c:+.3f}")
        print("  The §2 prediction is ~1 against ~0: expanded structure grows as")
        print("  V x S x F, condensed as S + (V x F). Two slopes on one axis from")
        print("  the same variant content is the strongest form of that claim.")

    print("\nThese are EMPIRICAL scaling exponents over the measured range, not")
    print("algorithmic bounds. Do not generalize beyond the rungs actually run.")

    out_path = pathlib.Path(args.out) if args.out \
        else results / args.experiment / f"scaling__{args.y}_vs_{args.x}__{args.group}.json"
    out_path.write_text(json.dumps({
        "experiment": args.experiment, "x": args.x, "y": args.y,
        "group": args.group, "fits": fits,
    }, indent=2) + "\n")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
