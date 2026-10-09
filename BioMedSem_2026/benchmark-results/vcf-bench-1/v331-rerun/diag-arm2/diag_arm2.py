#!/usr/bin/env python3
"""Arm 2 record-count disagreement: which records do the two routes decide differently, and why?

Read-only. Re-applies the harness's own baseline rule (baseline_carriers.released) to every record
in the RDF route's decision log, and characterises each record the two routes decide differently.

    diag_arm2.py <harness benchmarks dir> <cohort.json> <arm-2 results dir>
"""
import collections
import csv
import json
import pathlib
import sys

bench, case_path, results = map(pathlib.Path, sys.argv[1:4])
sys.path.insert(0, str(bench / "use_case" / "acmg"))
import baseline_carriers as bc  # noqa: E402

case = json.loads(case_path.read_text())
for term in case.get("purposes", ()):
    bc.BROADER[term["iri"]] = term["broader"]
policy = case["policy"]
spans = bc.gene_spans(policy["secondary_findings"]["genes"])
panels = [(p["purpose"], bc.gene_spans(p["genes"])) for p in policy.get("purpose_panels", ())]
regions = json.loads((bench / "use_case" / "acmg" / "regions.json").read_text())["regions"]
restricted_genes = set(policy["secondary_findings"]["genes"])


def genes_hit(chrom, pos, ref):
    end = pos + len(ref) - 1
    hits = []
    for region in regions:
        if region["symbol"] in restricted_genes and region["chrom"].removeprefix("chr") == chrom.removeprefix("chr") \
                and region["start"] <= end and pos <= region["end"]:
            hits.append(f'{region["symbol"]}[{region["start"]}-{region["end"]}]'
                        f'{" starts-before" if pos < region["start"] else ""}{" ends-after" if end > region["end"] else ""}')
    return hits


for name in ("clinical", "cardio", "biobank"):
    requester = policy["requesters"][name]
    differing = []
    total = 0
    with (results / f"govern__{name}" / "out" / "decisions.csv").open() as handle:
        for row in csv.DictReader(handle):
            total += 1
            participant = row["group"].split("//", 1)[1].split(".", 1)[0]
            record = {"participant": participant, "chrom": row["chrom"].removeprefix("chr"),
                      "pos": int(row["pos"]), "ref": row["ref"], "alt": row["alt"],
                      "restricted": bc.overlaps(row["chrom"], int(row["pos"]), row["ref"], spans)}
            baseline = bc.released(record, requester["purpose"], policy, requester["assignee"], panels)
            rdf = row["released"] == "True"
            if baseline != rdf:
                differing.append((row, baseline, record))
    print(f"\n== {name}: {total} records, {len(differing)} decided differently")
    if not differing:
        continue
    kinds = collections.Counter()
    for row, baseline, record in differing:
        alt_kind = "*" if row["alt"] == "*" else ("del" if len(row["ref"]) > len(row["alt"]) else
                   "ins" if len(row["ref"]) < len(row["alt"]) else "snv/mnv")
        hits = genes_hit(row["chrom"], int(row["pos"]), row["ref"])
        boundary = "starts-before-gene" if any("starts-before" in h for h in hits) else \
                   "ends-after-gene" if any("ends-after" in h for h in hits) else \
                   "inside-gene" if hits else "no-restricted-gene"
        kinds[(f"rdf={'release' if not baseline else 'withhold'}", alt_kind, boundary, row["reason"][:60])] += 1
    for key, count in kinds.most_common():
        print(f"  {count:5d}  {key}")
    print("  examples:")
    seen = set()
    for row, baseline, record in differing:
        key = (row["chrom"], row["pos"], row["ref"], row["alt"])
        if key in seen:
            continue
        seen.add(key)
        print(f"    {row['group'].split('//')[1]} {row['chrom']}:{row['pos']} {row['ref'][:20]}>{row['alt'][:20]} "
              f"rdf_released={row['released']} baseline_released={baseline} "
              f"genes={genes_hit(row['chrom'], int(row['pos']), row['ref'])} | {row['reason'][:80]}")
        if len(seen) >= 12:
            break
