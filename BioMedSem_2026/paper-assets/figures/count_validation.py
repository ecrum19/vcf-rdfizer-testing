#!/usr/bin/env python3
"""Count the validation evidence the paper's Section 3.5 and its table report.

    python3 count_validation.py <tree> [<tree> ...]

Walks every reports/validation/<target>/ directory under the given trees and
tallies paired comparisons, invariants, engine agreement, rapper syntax
checks, SHACL verdicts and preflight checks; native decode checks come from
each run's compression metrics.
"""
import collections
import json
import sys
from pathlib import Path


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main(trees):
    t = collections.Counter()
    status = collections.Counter()
    for tree in map(Path, trees):
        for summary in tree.glob("*/*/out/run_metrics/*/reports/validation/*/summary.json"):
            d = summary.parent
            s = load(summary) or {}
            t["validations"] += 1
            status[s.get("status")] += 1
            comp = load(d / "comparison.json")
            if comp:
                t["validations_with_comparison"] += 1
                for q in comp.get("queries", {}).values():
                    t[f"comparison_{q.get('status')}"] += 1
                for side in comp.get("invariants", {}).values():
                    for inv in side:
                        t[f"invariant_{inv.get('status')}"] += 1
            agree = load(d / "engine-agreement.json")
            if agree:
                t["agreement_recorded"] += 1
                t["agreement_true"] += bool(agree.get("agree"))
                n = len(agree.get("comparedEngines") or [])
                t[f"engines_{n}"] += 1
            rv = load(d / "rdf-validation.json")
            if rv:
                t[f"rapper_{rv.get('status')}"] += 1
            sh = load(d / "shacl.json")
            if sh:
                t[f"shacl_{sh.get('status')}"] += 1
                t["shacl_violations"] += sh.get("violationCount") or 0
            pf = load(d / "preflight.json")
            if pf:
                # preflight_distinct_triple_count reports a row count and asserts
                # nothing, so it is not a check.
                pf.pop("preflight_distinct_triple_count", None)
                for v in pf.values():
                    st = v.get("status") if isinstance(v, dict) else v
                    t[f"preflight_{st}"] += 1
        for metrics in tree.glob("*/*/out/run_metrics/*/stages/compression/*.json"):
            m = load(metrics) or {}
            for name, method in (m.get("methods") or {}).items():
                v = (method.get("details") or {}).get("validation") or method.get("validation")
                if isinstance(v, dict) and "valid" in v:
                    t[f"decode_{name}_{'PASS' if v.get('valid') and v.get('count_match', True) else 'FAIL'}"] += 1
    for k in sorted(t):
        print(f"{k:32s} {t[k]}")
    print("validation status:", dict(status))


if __name__ == "__main__":
    main(sys.argv[1:])
