#!/usr/bin/env python3
"""Build the query catalog that the results site shows: every query with its oracle.

benchmarks/query-catalog/notes.json is written by hand. For each query it gives a
one-line summary, the oracle as pseudo-code, and where the exact query text and
oracle code live: a VCF-RDFizer release tag (source "tool") or a commit of this
repository (source "testing"), with line ranges for the oracle code. This script
copies that exact text into benchmarks/query-catalog/catalog.json, so the site shows
what ran, and refuses to write if a cited file or line range does not exist.

A group of kind "shacl" names one SHACL shapes file instead of listing items: every
node shape in it becomes an item, with its exact Turtle text (by line range) and a
list of its constraints read from the parsed graph. The script refuses to write if
the statements it cut out do not add up to the file's graph.

The site build (build_site_data.py) only reads catalog.json, because CI has no copy
of the VCF-RDFizer repository. Rerun this script after editing notes.json (it needs
rdflib):

    python3 scripts/build_query_catalog.py --tool-repo ../vcf-rdfizer
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import rdflib
from rdflib.collection import Collection
from rdflib.compare import isomorphic
from rdflib.namespace import RDF

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "benchmarks" / "query-catalog"
SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")

from turtle_text import statement_text, turtle_statements  # noqa: E402  (scripts/ is on sys.path when run as a script)


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


# ---------- SHACL shapes ----------

def term(g: rdflib.Graph, node) -> str:
    if isinstance(node, rdflib.Literal):
        return f'"{node}"' if node.datatype is None or node.datatype == rdflib.XSD.string else str(node)
    if isinstance(node, rdflib.BNode) and (node, RDF.first, None) in g:
        return ", ".join(term(g, x) for x in Collection(g, node))
    return node.n3(g.namespace_manager)


def path_text(g: rdflib.Graph, path) -> str:
    if isinstance(path, rdflib.BNode):
        if (path, RDF.first, None) in g:
            return "/".join(path_text(g, p) for p in Collection(g, path))
        if (inverse := g.value(path, SH.inversePath)) is not None:
            return f"^{path_text(g, inverse)}"
    return term(g, path)


# The SHACL terms that structure a shape rather than constrain a value.
STRUCTURE = {RDF.type, SH.path, SH.minCount, SH.maxCount, SH.message, SH.severity, SH.flags, SH.property,
             SH.sparql, SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf,
             SH.qualifiedMinCount, SH.qualifiedMaxCount, SH.name, SH.description}
RANGE = {SH.minInclusive: "≥", SH.maxInclusive: "≤", SH.minExclusive: ">", SH.maxExclusive: "<"}


def value_checks(g: rdflib.Graph, node) -> list[str]:
    """What a shape or property shape requires of each value, in words."""
    out = []
    for p, o in sorted(g.predicate_objects(node), key=lambda po: str(po[0])):
        if p in STRUCTURE:
            continue
        name = g.namespace_manager.compute_qname(p)[2]
        if p in RANGE:
            out.append(f"{RANGE[p]} {o}")
        elif p == SH.pattern:
            flags = g.value(node, SH.flags)
            out.append(f"pattern {o}" + (f" (flags {flags})" if flags else ""))
        elif p == SH.node:
            out.append(f"conforms to {term(g, o)}")
        elif p in (SH.datatype, SH["class"], SH.nodeKind):
            out.append(f"{name} {term(g, o)}")
        elif p == SH["in"]:
            out.append(f"one of {term(g, o)}")
        elif p == SH.hasValue:
            out.append(f"value {term(g, o)}")
        elif p in (SH["or"], SH.xone):
            members = [describe(g, m) for m in Collection(g, o)]
            out.append(("one of: " if p == SH["or"] else "exactly one of: ") + " | ".join(members))
        elif p == SH["not"]:
            out.append("not: " + describe(g, o))
        elif p == SH.qualifiedValueShape:
            low, high = g.value(node, SH.qualifiedMinCount), g.value(node, SH.qualifiedMaxCount)
            out.append(f"{count_text(low, high)} value(s) with " + "; ".join(value_checks(g, o)))
        else:
            out.append(f"{name} {term(g, o)}")
    return out


def describe(g: rdflib.Graph, node) -> str:
    """A nested shape in words: its own value checks, then each of its property shapes."""
    properties = []
    for prop in g.objects(node, SH.property):
        count = count_text(g.value(prop, SH.minCount), g.value(prop, SH.maxCount))
        checks = ([] if count == "any number" else [count]) + value_checks(g, prop)
        properties.append(f"{path_text(g, g.value(prop, SH.path))}: {', '.join(checks)}")
    return "; ".join(value_checks(g, node) + sorted(properties)) or term(g, node)


def count_text(low, high) -> str:
    low, high = int(low or 0), (None if high is None else int(high))
    word = {0: "zero", 1: "one"}
    if high is not None and low == high:
        return f"exactly {word.get(low, low)}"
    if high is None:
        return f"at least {word.get(low, low)}" if low else "any number"
    return f"at most {word.get(high, high)}" if not low else f"{low} to {high}"


def constraint_rows(g: rdflib.Graph, shape, text: str) -> list[dict]:
    """One row per property shape, SPARQL constraint, and the shape's own value checks,
    in the order they appear in the shape's text."""
    shape_severity = g.value(shape, SH.severity)
    rows = []
    if checks := value_checks(g, shape):
        rows.append({"kind": "node", "path": "", "count": "", "checks": checks, "at": len(text) + 1})
    for prop in g.objects(shape, SH.property):
        path = path_text(g, g.value(prop, SH.path))
        found = re.search(r"sh:path\s+" + re.escape(path) + r"(?![\w-])", text)
        low, high, checks = g.value(prop, SH.minCount), g.value(prop, SH.maxCount), value_checks(g, prop)
        qualified = g.value(prop, SH.qualifiedValueShape)
        if qualified is not None and low is None and high is None:
            # Only the qualified count applies: "exactly one hasHeaderLine with class X".
            low, high = g.value(prop, SH.qualifiedMinCount), g.value(prop, SH.qualifiedMaxCount)
            path = f"{path} with {describe(g, qualified)}"
            checks = [c for c in checks if " value(s) with " not in c]
        rows.append({"kind": "property", "path": path, "count": count_text(low, high), "checks": checks,
                     "message": str(g.value(prop, SH.message) or ""),
                     "severity": g.value(prop, SH.severity), "at": found.start() if found else len(text)})
    for constraint in g.objects(shape, SH.sparql):
        message = str(g.value(constraint, SH.message) or "")
        rows.append({"kind": "sparql", "path": "", "count": "", "checks": [], "message": message,
                     "severity": shape_severity, "at": text.find(message) if message else len(text)})
    for row in rows:
        severity = row.pop("severity", None) or SH.Violation
        row["severity"] = severity.n3(g.namespace_manager).removeprefix("sh:")
        if not row.get("message"):
            row.pop("message", None)
    # rdflib does not keep the file's order; ties are broken by content, so a rebuild is stable.
    rows.sort(key=lambda r: (r["at"], r["kind"], r["path"], r["checks"], r.get("message", "")))
    for row in rows:
        del row["at"]
    return rows


def shape_summary(g: rdflib.Graph, shape, rows: list[dict]) -> str:
    target = g.value(shape, SH.targetClass)
    subject = (f"Each {term(g, target)}" if target else
               f"Each object of {term(g, o)}" if (o := g.value(shape, SH.targetObjectsOf)) else
               f"Each subject of {term(g, s)}" if (s := g.value(shape, SH.targetSubjectsOf)) else
               "Used by other shapes through sh:node; each value")
    by_count: dict[str, list[str]] = {}
    for row in rows:
        if row["kind"] == "property" and not row.get("message"):
            by_count.setdefault(row["count"], []).append(row["path"].removeprefix("vcfc:"))
    phrases = [f"{count}{' of' if count == 'any number' else ''} "
               f"{' and '.join(paths) if len(paths) < 3 else ', '.join(paths[:-1]) + ' and ' + paths[-1]}"
               for count, paths in by_count.items()]
    node = next((r for r in rows if r["kind"] == "node"), None)
    if node:
        phrases.append("plus a condition across properties" if phrases else "; ".join(node["checks"]))
    messages = [r["message"] for r in rows if r.get("message")]
    summary = f"{subject}: {'; '.join(phrases)}" if phrases else f"{subject}:"
    if messages:
        summary += (". " if phrases else " ") + " ".join(m if m.endswith(".") else m + "." for m in messages)
    if all(r["severity"] == "Warning" for r in rows):
        summary += " (warning only)"
    return summary


def shacl_group(group: dict, tool_repo: Path) -> dict:
    """Every node shape in one shapes file, with its exact text and its constraints."""
    tags, path = group["tags"], group["path"]
    text = git_show(tool_repo, tags[0], path)
    for rev in tags[1:]:
        if git_show(tool_repo, rev, path) != text:
            raise SystemExit(f"{group['id']}: {path} differs between {tags[0]} and {rev}")
    lines = text.splitlines()
    g = rdflib.Graph().parse(data=text, format="turtle")
    prefixes = "\n".join(l for l in lines if l.lstrip().startswith("@prefix")) + "\n"
    rebuilt, items = rdflib.Graph(), []
    for first, last in turtle_statements(text):
        statement = "\n".join(lines[first - 1:last])
        part = rdflib.Graph().parse(data=prefixes + statement, format="turtle")
        rebuilt += part
        shapes = [s for s in part.subjects(RDF.type, SH.NodeShape) if isinstance(s, rdflib.URIRef)]
        if not shapes:
            continue
        if len(shapes) > 1:
            raise SystemExit(f"{group['id']}: lines {first}-{last} declare {len(shapes)} shapes")
        shape = shapes[0]
        first, text_with_comment = statement_text(lines, first, last)
        rows = constraint_rows(g, shape, statement)
        name = g.namespace_manager.compute_qname(shape)[2]
        items.append({"id": f"{group['id']}-{name}", "label": name, "summary": shape_summary(g, shape, rows),
                      "constraints": rows, "text": text_with_comment,
                      "from": [provenance("tool", rev, path, tool_repo, (first, last)) for rev in tags]})
    if not isomorphic(rebuilt, g):
        raise SystemExit(f"{group['id']}: the statements cut from {path} do not add up to its graph")
    if len(items) != len(set(g.subjects(RDF.type, SH.NodeShape))):
        raise SystemExit(f"{group['id']}: found {len(items)} of {len(set(g.subjects(RDF.type, SH.NodeShape)))} shapes")
    return {key: group[key] for key in ("id", "rq", "title", "intro", "kind", "paper") if key in group} | {
        "file": [provenance("tool", rev, path, tool_repo) for rev in tags], "items": items}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tool-repo", type=Path, required=True, help="a clone of VCF-RDFizer with its release tags")
    args = parser.parse_args()
    notes = json.loads((CATALOG / "notes.json").read_text())
    groups = []
    for group in notes["groups"]:
        if group.get("kind") == "shacl":
            groups.append(shacl_group(group, args.tool_repo))
            continue
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
        groups.append({key: group[key] for key in ("id", "rq", "title", "intro", "oracleLabel", "paper") if key in group}
                      | {"items": items})
    out = {"groups": groups, "builtFrom": {"notes": "benchmarks/query-catalog/notes.json",
                                           "testingCommit": rev_commit(ROOT, "HEAD")}}
    (CATALOG / "catalog.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {CATALOG / 'catalog.json'}: {sum(len(g['items']) for g in groups)} queries and shapes in {len(groups)} groups")


if __name__ == "__main__":
    main()
