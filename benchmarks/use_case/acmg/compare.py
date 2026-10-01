#!/usr/bin/env python3
"""Compare the RDF route's carriers with the baseline's, requester by requester.

    compare.py <results-dir> <use_case.json>

Reads <results-dir>/baseline/carriers.<requester>.tsv and
<results-dir>/query/<requester>/carriers.tsv, and writes
<results-dir>/comparison.json and grid.tsv (carriers released per requester and
participant). A requester whose RDF query has not run yet is listed as not
run, never counted as agreeing. Where both routes also wrote rare.tsv (arm 2's
panel), those lists are compared too, under "rare". Exits 1 unless at least one
requester ran and every comparison made agrees: a disagreement is a bug in one route, and no timing
or line count from the experiment is reportable until it is explained.
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys


def key(participant: str, gene: str, chrom: str, pos: str, ref: str, alt: str) -> tuple:
    return (participant, gene, chrom.removeprefix("chr"), int(pos), ref, alt)


def read_tsv(path: pathlib.Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def baseline_keys(path: pathlib.Path) -> set[tuple]:
    return {key(r["participant"], r["gene"], r["chrom"], r["pos"], r["ref"], r["alt"])
            for r in read_tsv(path)}


def rdf_keys(path: pathlib.Path) -> set[tuple]:
    # ?file is file://<participant>.acmg.vcf, the IRI VCF-RDFizer gave the input.
    return {key(r["file"].removeprefix("file://").removesuffix(".acmg.vcf"), r["gene"],
                r["chrom"], r["pos"], r["ref"], r["alt"])
            for r in read_tsv(path)}


def main(argv: list[str]) -> int:
    results, case_json = pathlib.Path(argv[0]), pathlib.Path(argv[1])
    case = json.loads(case_json.read_text(encoding="utf-8"))
    everyone = ["unrestricted", *case["policy"]["requesters"]]
    ran = [n for n in everyone if (results / "query" / n / "carriers.tsv").is_file()]
    participants = [p["id"] for p in case["participants"]]

    def compared(query: str, name: str) -> dict:
        expected = baseline_keys(results / "baseline" / f"{query}.{name}.tsv")
        found = rdf_keys(results / "query" / name / f"{query}.tsv")
        return {"baseline": len(expected), "rdf": len(found), "agree": expected == found,
                "only_baseline": sorted(map(list, expected - found)),
                "only_rdf": sorted(map(list, found - expected)), "keys": found}

    comparison, grid = {"not_run": [n for n in everyone if n not in ran]}, []
    for name in ran:
        comparison[name] = compared("carriers", name)
        found = comparison[name].pop("keys")
        grid.append([name] + [str(sum(1 for k in found if k[0] == p)) for p in participants])
    rare = [n for n in ran if (results / "query" / n / "rare.tsv").is_file()
            and (results / "baseline" / f"rare.{n}.tsv").is_file()]
    if rare:
        comparison["rare"] = {n: compared("rare", n) for n in rare}
        for entry in comparison["rare"].values():
            entry.pop("keys")

    (results / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    with (results / "grid.tsv").open("w", encoding="utf-8") as handle:
        handle.write("\t".join(["requester", *participants]) + "\n")
        handle.writelines("\t".join(row) + "\n" for row in grid)
    agree = bool(ran) and all(comparison[n]["agree"] for n in ran) \
        and all(c["agree"] for c in comparison.get("rare", {}).values())
    print(("AGREE" if agree else "DISAGREE") + ": " +
          ", ".join(f"{n} {comparison[n]['rdf']}/{comparison[n]['baseline']}" for n in ran) +
          ("; rare: " + ", ".join(f"{n} {c['rdf']}/{c['baseline']}" for n, c in comparison["rare"].items())
           if rare else "") +
          (f"; not run: {', '.join(comparison['not_run'])}" if comparison["not_run"] else ""))
    return 0 if agree else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
