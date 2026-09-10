#!/usr/bin/env python3
"""Decide an equivalence claim from paired runs.

Plan §1 and §2.3 both make a partly NEGATIVE claim ("does not differ much").
A significance test that fails to reject is not evidence of equivalence — with
n=3 it is evidence of nothing. This script does it properly: a bootstrap CI on
the paired ratio, compared against a stated margin, with equivalence declared
only when the WHOLE CI sits inside the corridor.

Pairing: runs are grouped by ``--group-by`` (default: the input file), and
within each group the two arms are paired by repetition index parsed from the
cell name (``__r3``, ``__rep3``). If no index is present, runs are paired in the
order they executed, which is why the experiment scripts interleave the arms
rather than blocking them.

Usage:
    python3 equivalence.py 01_storage_mode --margin 0.10
    python3 equivalence.py 01_storage_mode --factor rdf_storage_mode \\
        --treatment space-optimized --baseline plain --metric wall_seconds_java
    python3 equivalence.py 03_sample_representation --cell-filter s1__ --margin 0.10
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import stats  # noqa: E402

CANDIDATE_FACTORS = [
    "rdf_storage_mode",
    "sample_representation",
    "info_representation",
    "header_representation",
    "hdt_strategy",
]

# Preference order: the tool's own conversion timing first, the wrapper's
# end-to-end time as a fallback. They differ — the wrapper includes host-side
# staging — so which one was used is reported alongside the verdict.
METRIC_PREFERENCE = ["wall_seconds_java", "wrapper_wall_seconds"]

REP_PATTERN = re.compile(r"__(?:r|rep)(\d+)\b")


def load(experiment: str, results: pathlib.Path) -> list[dict]:
    tidy = results / experiment / "tidy.json"
    if not tidy.is_file():
        raise SystemExit(
            f"{tidy} not found. Run first:\n"
            f"  python3 collect_metrics.py {experiment}"
        )
    return json.loads(tidy.read_text())


def usable(rows: list[dict]) -> list[dict]:
    return [r for r in rows if not r.get("skipped") and r.get("exit_code") == 0]


def pick_factor(rows: list[dict], explicit: str | None) -> str:
    if explicit:
        return explicit
    for column in CANDIDATE_FACTORS:
        values = {r.get(column) for r in rows if r.get(column) is not None}
        if len(values) == 2:
            return column
    raise SystemExit(
        "could not identify the varying factor automatically.\n"
        "Pass --factor with one of: " + ", ".join(CANDIDATE_FACTORS)
    )


def pick_metric(rows: list[dict], explicit: str | None) -> str:
    if explicit:
        return explicit
    for column in METRIC_PREFERENCE:
        if any(r.get(column) not in (None, "") for r in rows):
            return column
    raise SystemExit("no timing metric present; pass --metric")


def rep_index(cell: str) -> int | None:
    match = REP_PATTERN.search(cell)
    return int(match.group(1)) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment")
    parser.add_argument("--results", default=None)
    parser.add_argument("--margin", type=float, default=0.10,
                        help="symmetric equivalence margin as a fraction (default 0.10)")
    parser.add_argument("--factor", default=None, help="column that varies between the arms")
    parser.add_argument("--treatment", default=None)
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--metric", default=None, help="numeric column to compare")
    parser.add_argument("--group-by", default="input",
                        help="comma-separated columns identifying a pairing group")
    parser.add_argument("--cell-filter", default=None,
                        help="only cells whose name contains this substring")
    parser.add_argument("--confidence", type=float, default=0.90)
    parser.add_argument("--out", default=None, help="write the verdicts as JSON here")
    args = parser.parse_args()

    results = pathlib.Path(args.results) if args.results \
        else pathlib.Path(__file__).resolve().parent.parent / "results"

    rows = usable(load(args.experiment, results))
    if args.cell_filter:
        rows = [r for r in rows if args.cell_filter in (r.get("cell") or "")]
    if not rows:
        raise SystemExit("no successful cells match the filter")

    factor = pick_factor(rows, args.factor)
    metric = pick_metric(rows, args.metric)
    values = sorted({r.get(factor) for r in rows if r.get(factor) is not None})
    if len(values) != 2:
        raise SystemExit(f"factor {factor!r} has {len(values)} values ({values}); need exactly 2")

    if args.treatment and args.baseline:
        treatment_value, baseline_value = args.treatment, args.baseline
    else:
        # Default orientation: the space-saving / cohort-scaling arm is the
        # treatment, so a positive relative difference reads as "costs more".
        preferred = {"space-optimized", "condensed", "structured", "partitioned"}
        treatment_value = next((v for v in values if v in preferred), values[0])
        baseline_value = next(v for v in values if v != treatment_value)

    group_columns = [c.strip() for c in args.group_by.split(",") if c.strip()]

    groups: dict[tuple, dict[str, list[dict]]] = {}
    for row in rows:
        value = row.get(factor)
        if value not in (treatment_value, baseline_value):
            continue
        if row.get(metric) in (None, ""):
            continue
        key = tuple(row.get(c) for c in group_columns)
        groups.setdefault(key, {treatment_value: [], baseline_value: []})[value].append(row)

    verdicts = []
    for key, arms in sorted(groups.items(), key=lambda kv: [str(x) for x in kv[0]]):
        treat_rows, base_rows = arms[treatment_value], arms[baseline_value]
        if not treat_rows or not base_rows:
            print(f"  {key}: only one arm present — skipped")
            continue

        # Pair by repetition index where present, else by execution order.
        def ordered(rs: list[dict]) -> list[dict]:
            if all(rep_index(r.get("cell") or "") is not None for r in rs):
                return sorted(rs, key=lambda r: rep_index(r["cell"]))
            return sorted(rs, key=lambda r: r.get("started_epoch") or 0)

        treat_rows, base_rows = ordered(treat_rows), ordered(base_rows)
        n = min(len(treat_rows), len(base_rows))
        if len(treat_rows) != len(base_rows):
            print(f"  {key}: arms are unequal ({len(treat_rows)} vs {len(base_rows)}); "
                  f"using the first {n} of each")
        treat = [float(r[metric]) for r in treat_rows[:n]]
        base = [float(r[metric]) for r in base_rows[:n]]

        result = stats.paired_ratio_ci(treat, base, confidence=args.confidence)
        verdict = stats.equivalence_verdict(result, args.margin)
        verdict.update({
            "group": dict(zip(group_columns, key)),
            "factor": factor,
            "treatment": treatment_value,
            "baseline": baseline_value,
            "metric": metric,
            "treatment_values": treat,
            "baseline_values": base,
        })
        verdicts.append(verdict)

    if not verdicts:
        raise SystemExit("no pairable groups found")

    label = ", ".join(group_columns)
    print(f"\nEquivalence: {treatment_value} vs {baseline_value}  ({factor})")
    print(f"Metric: {metric}    Margin: +/-{args.margin:.0%}    "
          f"CI: {args.confidence:.0%} bootstrap on paired ratios\n")
    width = max(len(str(v["group"])) for v in verdicts)
    for v in verdicts:
        ci = ("      n/a      " if v["ci_low"] != v["ci_low"]
              else f"[{v['ci_low']:+6.1%},{v['ci_high']:+6.1%}]")
        print(f"  {str(v['group']):<{width}}  n={v['n_pairs']}  "
              f"{v['relative_difference']:+7.1%}  CI {ci}  {v['verdict']}")

    print("\nReport this as an equivalence result, and state WHEN the margin was")
    print("fixed. A margin chosen after seeing the data is not pre-registration;")
    print("say which it was rather than implying the stronger one.")

    out_path = pathlib.Path(args.out) if args.out \
        else results / args.experiment / f"equivalence__{factor}__{metric}.json"
    out_path.write_text(json.dumps({
        "experiment": args.experiment,
        "factor": factor,
        "metric": metric,
        "margin": args.margin,
        "confidence": args.confidence,
        "treatment": treatment_value,
        "baseline": baseline_value,
        "verdicts": verdicts,
    }, indent=2) + "\n")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
