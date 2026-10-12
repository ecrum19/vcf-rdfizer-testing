#!/usr/bin/env python3
"""Build the query catalog that the results site shows: every query with its oracle.

benchmarks/query-catalog/notes.json is written by hand. For each query it gives a
one-line summary, the oracle as pseudo-code, and where the exact query text and
oracle code live: a VCF-RDFizer release tag (source "tool") or a commit of this
repository (source "testing"), with line ranges for the oracle code. This script
copies that exact text into benchmarks/query-catalog/catalog.json, so the site shows
what ran, and refuses to write if a cited file or line range does not exist.

The site build (build_site_data.py) only reads catalog.json, because CI has no copy
of the VCF-RDFizer repository. Rerun this script after editing notes.json:

    python3 scripts/build_query_catalog.py --tool-repo ../vcf-rdfizer
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "benchmarks" / "query-catalog"


def git_show(repo: Path, rev: str, path: str) -> str:
    """The file at a tag or commit, read with git show, never from a checkout."""
    try:
        return subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{path}"],
                              check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"cannot read {path} at {rev} in {repo}: {error.stderr.strip()}") from None


def rev_commit(repo: Path, rev: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", f"{rev}^{{commit}}"],
                          check=True, capture_output=True, text=True).stdout.strip()


def repo_for(source: str, tool_repo: Path) -> Path:
    if source == "tool":
        return tool_repo
    if source == "testing":
        return ROOT
    raise SystemExit(f"unknown source {source!r}")


def provenance(source: str, rev: str, path: str, tool_repo: Path, lines: tuple[int, int] | None = None) -> dict:
    where = {"source": "VCF-RDFizer" if source == "tool" else "vcf-rdfizer-testing",
             "rev": rev, "commit": rev_commit(repo_for(source, tool_repo), rev), "path": path}
    if lines:
        where["lines"] = list(lines)
    return where


def sparql_entries(item: dict, tool_repo: Path) -> list[dict]:
    """One entry per query file and release; identical text at several tags is shown once."""
    out = []
    for entry in item["sparql"]:
        source = entry.get("source", "tool")
        revs = entry.get("tags") or [entry["tag_or_commit"]]
        text = git_show(repo_for(source, tool_repo), revs[0], entry["path"])
        for rev in revs[1:]:
            if git_show(repo_for(source, tool_repo), rev, entry["path"]) != text:
                raise SystemExit(f"{item['id']}: {entry['path']} differs between {revs[0]} and {rev}; list them separately")
        out.append({"label": entry["label"], "text": text.rstrip() + "\n",
                    "from": [provenance(source, rev, entry["path"], tool_repo) for rev in revs]})
    return out


def code_entries(item: dict, tool_repo: Path) -> list[dict]:
    out = []
    for entry in item.get("oracle_code", []):
        source = entry.get("source", "tool")
        rev = entry.get("tag") or entry["tag_or_commit"]
        lines = git_show(repo_for(source, tool_repo), rev, entry["path"]).splitlines()
        start, end = int(entry["start"]), int(entry["end"])
        if not 1 <= start <= end <= len(lines):
            raise SystemExit(f"{item['id']}: lines {start}-{end} are outside {entry['path']} at {rev} ({len(lines)} lines)")
        out.append({"note": entry.get("note", ""), "text": "\n".join(lines[start - 1:end]) + "\n",
                    "from": provenance(source, rev, entry["path"], tool_repo, (start, end))})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tool-repo", type=Path, required=True, help="a clone of VCF-RDFizer with its release tags")
    args = parser.parse_args()
    notes = json.loads((CATALOG / "notes.json").read_text())
    groups = []
    for group in notes["groups"]:
        items = []
        for item in group["items"]:
            built = {key: item[key] for key in ("id", "label", "summary") }
            built["pseudo"] = item["oracle_pseudo"].rstrip() + "\n"
            for key in ("notes", "differences", "not_represented"):
                if item.get(key):
                    built[key] = item[key]
            built["sparql"] = sparql_entries(item, args.tool_repo)
            built["oracleCode"] = code_entries(item, args.tool_repo)
            items.append(built)
        groups.append({key: group[key] for key in ("id", "rq", "title", "intro", "oracleLabel")} | {"items": items})
    out = {"groups": groups, "builtFrom": {"notes": "benchmarks/query-catalog/notes.json",
                                           "testingCommit": rev_commit(ROOT, "HEAD")}}
    (CATALOG / "catalog.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {CATALOG / 'catalog.json'}: {sum(len(g['items']) for g in groups)} queries in {len(groups)} groups")


if __name__ == "__main__":
    main()
