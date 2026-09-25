#!/usr/bin/env python3
"""Integrate every run record from every host into one summary file.

combine_benchmark_metrics.py answers "what did this run measure". It knows
nothing about which host ran it, which experiment and cell it belongs to, which
tool commit produced it, or whether it was later superseded -- and this campaign
has all four, because it ran split across two VMs, moved experiments between
them mid-flight, changed tool commit twice, and re-ran two experiments after
fixing bugs the first runs exposed.

So this walks the archived tree, attaches that context to each cell, and keeps
the branches apart:

  live        the dataset the paper reports
  superseded  a run replaced by a later one (kept: it is why the later one exists)
  stalled     a run killed because it could not finish
  offsplit    started on the host that turned out not to own that experiment
  partial     interrupted before bench.json was written
  calibration the identical cell each host ran so the two can be compared
  archive     an older tool's data, kept separate because its labels collide
  prerelease  the first campaign, on development commits, set aside when the
              whole suite was re-run on the v3.1.0 release ("__campaign1__")
  supplementary  a targeted run added after a campaign to measure what it did
              not ("__supplement_"), e.g. the sample ladder's COTTAS bytes;
              reported where it is used, never counted as campaign cells

Only `live` feeds the reported numbers. Everything else is carried so a reader
can see what was excluded and why, rather than having to take it on trust.

Usage:
  python3 scripts/build_run_summary.py BioMedSem_2026/benchmark-results \
      --output BioMedSem_2026/benchmark-results/summary.json
"""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from combine_benchmark_metrics import build_combined_metrics_for_run  # noqa: E402

SCHEMA_VERSION = "biomedsem-1.0"

#: Which branch of the campaign a tree belongs to. Order matters: the first
#: matching marker wins, and "benchmarks_outputs" alone must be tested last
#: because every other name starts with it.
TREE_KINDS = (
    # Tested first: "benchmarks_outputs_calibration__campaign1__..." is the
    # pre-release calibration, and must not be read as the current one.
    ("__campaign1", "prerelease"),
    ("__superseded", "superseded"),
    ("__stalled", "stalled"),
    ("__offsplit", "offsplit"),
    ("__partial", "partial"),
    ("__tool", "archive"),
    ("__supplement", "supplementary"),
    ("_calibration", "calibration"),
    ("benchmarks_outputs", "live"),
)


def tree_kind(tree_name: str) -> str:
    for marker, kind in TREE_KINDS:
        if marker in tree_name:
            return kind
    return "unknown"


#: Cells recorded before bm_record_assertion existed carry no marker, so their
#: assertion is recovered from what the experiment script demonstrably does.
#: Both rules are transcriptions of the scripts, not guesses:
#:   06_equivalence asserts its refusal__* cells with bm_expect_refusal, and
#:   09_awkward_inputs states "a refusal is a valid, recorded outcome" and
#:   asserts nothing for its awkward_* fixtures.
#: Anything else keeps the strict reading -- silence means a non-zero exit is a
#: failure, which is what caught 13_query_cost's three real cottas mismatches.
def _legacy_assertion(record: dict[str, Any]) -> str | None:
    cell = record.get("cell") or ""
    if cell.startswith("refusal__"):
        return "refusal"
    if record.get("experiment") == "09_awkward_inputs" and cell.startswith("awkward_"):
        return "recorded"
    return None


def classify(record: dict[str, Any]) -> str:
    """OK / FAILED / REFUSED / RECORDED / SKIPPED for one cell.

    REFUSED  the experiment demanded this run fail, and it did
    RECORDED the experiment asserted nothing: the exit code is an observation
    """
    if record.get("skipped"):
        return "SKIPPED"
    assertion = record.get("assertion")
    nonzero = bool(record.get("exit_code"))
    if assertion == "refusal":
        # A refusal cell that SUCCEEDED is a failure of the assertion itself.
        return "REFUSED" if nonzero else "FAILED"
    if not nonzero:
        # A zero exit is success whatever was asserted. The assertion only
        # disambiguates a non-zero one, so reporting an unasserted success as
        # anything other than OK would lose information rather than add it --
        # 09 has eight awkward inputs that convert cleanly and three that are
        # refused, and those are different results.
        return "OK"
    return "RECORDED" if assertion == "recorded" else "FAILED"


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def git_describe(repo: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "log", "--oneline", "-1"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip() or None
    except Exception:
        return None


def collect_cells(root: Path) -> list[dict[str, Any]]:
    """One record per cell, wherever it lives, with its branch recorded."""
    cells: list[dict[str, Any]] = []
    # rglob rather than a fixed depth: the stalled archives nest an extra level
    # (<tree>/<archive>/<experiment>/<cell>), and a fixed glob silently skipped
    # exactly those -- the cottas hang evidence -- which is the one thing this
    # summary must not do.
    for bench_path in sorted(root.rglob("bench.json")):
        cell_dir = bench_path.parent
        parts = bench_path.relative_to(root).parts
        if len(parts) < 4:
            continue
        host, tree = parts[0], parts[1]
        bench = read_json(bench_path) or {}

        record: dict[str, Any] = {
            "host": host,
            "tree": tree,
            "branch": tree_kind(tree),
            "experiment": bench.get("experiment") or cell_dir.parent.name,
            "cell": bench.get("cell") or cell_dir.name,
            "skipped": bool(bench.get("skipped")),
            "exit_code": bench.get("exit_code"),
            "wrapper_wall_seconds": bench.get("wrapper_wall_seconds"),
            "tool_commit": bench.get("tool_commit"),
            "image_ref": bench.get("image_ref"),
            "image_digest_recorded": bench.get("image_digest"),
            "command": bench.get("command"),
            "path": str(cell_dir.relative_to(root)),
        }
        if record["skipped"]:
            record["skip_reason"] = bench.get("skip_reason") or bench.get("reason")
        record["assertion"] = bench.get("assertion") or _legacy_assertion(record)
        if bench.get("assertion_note"):
            record["assertion_note"] = bench["assertion_note"]
        record["status"] = classify(record)

        runs = []
        for run_dir in sorted((cell_dir / "out" / "run_metrics").glob("*__*")):
            if not run_dir.is_dir():
                continue
            summary = read_json(run_dir / "summary.json") or {}
            entry = {
                "run_id": summary.get("run_id"),
                "timestamp": summary.get("timestamp"),
                "mode": summary.get("mode"),
                "status": summary.get("status"),
                "exit_code": summary.get("exit_code"),
                "run_directory": str(run_dir.relative_to(root)),
            }
            validation = summary.get("validation")
            if isinstance(validation, dict):
                entry["validation"] = {
                    k: validation.get(k)
                    for k in ("status", "engines", "targets", "queries")
                    if k in validation
                }
            try:
                combined = build_combined_metrics_for_run(run_dir)
                entry["datasets"] = combined.get("datasets") or []
                entry["compression_by_method"] = combined.get("compression_by_method") or []
            except Exception as error:  # a bad run must not sink the summary
                entry["combine_error"] = str(error)
            runs.append(entry)
        record["runs"] = runs
        cells.append(record)
    return cells


def attach_image_digests(cells: list[dict[str, Any]], table: dict[str, dict[str, str]]) -> None:
    for cell in cells:
        tag = cell.get("image_ref")
        if not tag:
            # Legitimate for a host-side cell such as 08_robustness/mutation_score,
            # which runs no container at all. Recorded rather than left blank so
            # it cannot be mistaken for a missing record.
            cell["image_digest"] = None
            cell["image_note"] = "no container image (host-side cell)"
            continue
        # A cell that pulled a published image records the registry's own
        # digest ("repo@sha256:..."), which names the exact bits it ran; prefer
        # it. Locally built tags carry no such record and are resolved against
        # the host's image inventory instead, because the same tag names
        # different bits on two hosts that each built it.
        recorded = cell.get("image_digest_recorded") or ""
        if "@sha256:" in recorded:
            cell["image_digest"] = recorded.split("@", 1)[1]
            cell["image_note"] = "registry digest recorded by the cell"
            continue
        cell["image_digest"] = (table.get(cell["host"]) or {}).get(tag)
        if cell["image_digest"] is None:
            cell["image_note"] = "tag not found in this host's image inventory"


def roll_up(cells: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    by_exp = collections.defaultdict(list)
    for c in cells:
        by_exp[(c["branch"], c["experiment"])].append(c)
    for (branch, exp), rows in sorted(by_exp.items()):
        out.setdefault(branch, {})[exp] = {
            "cells": len(rows),
            "ok": sum(1 for r in rows if r["status"] == "OK"),
            "failed": sum(1 for r in rows if r["status"] == "FAILED"),
            "skipped": sum(1 for r in rows if r["status"] == "SKIPPED"),
            "refused": sum(1 for r in rows if r["status"] == "REFUSED"),
            "recorded": sum(1 for r in rows if r["status"] == "RECORDED"),
            "wall_hours": round(
                sum(float(r.get("wrapper_wall_seconds") or 0) for r in rows) / 3600, 3
            ),
            "hosts": sorted({r["host"] for r in rows}),
            "tool_commits": sorted(
                {(r.get("tool_commit") or "?")[:8] for r in rows if not r["skipped"]}
            ),
            "images": sorted(
                {r.get("image_ref") or "?" for r in rows if not r["skipped"]}
            ),
        }
    return out


def integrity(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """The checks a reader would otherwise have to trust rather than verify."""
    live = [c for c in cells if c["branch"] == "live" and not c["skipped"]]
    by_exp_hosts = collections.defaultdict(set)
    for c in live:
        by_exp_hosts[c["experiment"]].add(c["host"])
    split = {e: sorted(h) for e, h in by_exp_hosts.items() if len(h) > 1}
    return {
        "live_cells": len(live),
        "experiments_spanning_two_hosts": split,
        "experiments_spanning_two_hosts_ok": not split,
        "cells_without_host": [c["path"] for c in live if not c.get("host")],
        "cells_without_tool_commit": [c["path"] for c in live if not c.get("tool_commit")],
        "tool_commits": sorted({(c.get("tool_commit") or "?")[:8] for c in live}),
        "image_refs": sorted({c.get("image_ref") or "?" for c in live}),
        "cells_with_unresolved_image": [
            c["path"] for c in live
            if c.get("image_ref") and not c.get("image_digest")
        ],
        "refused_as_designed": [
            c["path"] for c in live if c["status"] == "REFUSED"
        ],
        "recorded_not_asserted": [
            c["path"] for c in live if c["status"] == "RECORDED"
        ],
        "failed_live_cells": [
            {"path": c["path"], "exit_code": c["exit_code"]}
            for c in live if c["status"] == "FAILED"
        ],
    }


def image_digests(root: Path) -> dict[str, dict[str, str]]:
    """host -> {image tag: image id}, from every provenance file on that host.

    A cell records the image *tag* it ran, and a tag is not unique: each host
    built vcf-rdfizer:local-025fb7d independently, so the same tag names
    different bits on the two machines. Resolving tag -> id per host is what
    turns "image_ref" into provenance a reader can check.
    """
    out: dict[str, dict[str, str]] = {}
    for path in sorted(root.glob("*/*/00_environment/provenance.*.json")):
        payload = read_json(path) or {}
        host = payload.get("host") or path.relative_to(root).parts[0]
        table = out.setdefault(host, {})
        for entry in payload.get("images_present") or []:
            if isinstance(entry, (list, tuple)) and len(entry) == 2:
                table.setdefault(entry[0].strip(), entry[1].strip())
        image = payload.get("image") or {}
        if image.get("tag") and image.get("id"):
            table.setdefault(image["tag"], image["id"])
    return out


def provenance(root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path in sorted(root.glob("*/*/00_environment/provenance.*.json")):
        payload = read_json(path)
        if not payload:
            continue
        host = payload.get("host") or path.relative_to(root).parts[0]
        commit = (payload.get("tool_repo") or {}).get("head_short") or "unknown"
        out.setdefault(host, {})[commit] = {
            "image": (payload.get("image") or {}).get("id"),
            "image_created": (payload.get("image") or {}).get("created"),
            "tool": (payload.get("tool_repo") or {}).get("subject"),
            "harness": (payload.get("harness_repo") or {}).get("subject"),
            "platform": payload.get("platform"),
            "source": str(path.relative_to(root)),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path, help="benchmark-results directory")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    cells = collect_cells(root)
    digests = image_digests(root)
    attach_image_digests(cells, digests)
    live_runs = [
        r for c in cells if c["branch"] == "live" for r in c["runs"]
    ]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_commit": git_describe(Path(__file__).resolve().parents[1]),
        "root": str(root.name),
        "hosts": sorted({c["host"] for c in cells}),
        "provenance": provenance(root),
        "image_digests_by_host": digests,
        "counts": {
            "cells_total": len(cells),
            "cells_by_branch": dict(
                collections.Counter(c["branch"] for c in cells)
            ),
            "runs_live": len(live_runs),
        },
        "trees_seen": {
            host: {
                tree.name: {
                    "branch": tree_kind(tree.name),
                    "complete_cells": sum(
                        1 for c in cells if c["host"] == host and c["tree"] == tree.name
                    ),
                    "files": sum(1 for _ in tree.rglob("*") if _.is_file()),
                }
                for tree in sorted((root / host).iterdir()) if tree.is_dir()
            }
            for host in sorted({c["host"] for c in cells})
        },
        "experiments": roll_up(cells),
        "integrity": integrity(cells),
        "cells": cells,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=False) + "\n",
                           encoding="utf-8")
    counts = summary["counts"]
    print("Wrote %s" % args.output)
    print("  cells: %d  (%s)" % (
        counts["cells_total"],
        ", ".join("%s=%d" % kv for kv in sorted(counts["cells_by_branch"].items())),
    ))
    ok = summary["integrity"]["experiments_spanning_two_hosts_ok"]
    print("  live cells: %d   no experiment spans two hosts: %s"
          % (summary["integrity"]["live_cells"], ok))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
