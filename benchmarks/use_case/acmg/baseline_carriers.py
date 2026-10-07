#!/usr/bin/env python3
"""Step 5 of the baseline: apply the use case's rules to bcftools' carrier rows.

Input is one row per carrier genotype, as baseline.sh queries it:

    participant  chrom  pos  ref  alt  CLNSIG  CLNREVSTAT  GENEINFO  GT

Output, in <out-dir>:

    carriers.unrestricted.tsv   every carrier, as if there were no policy
    carriers.<requester>.tsv    what each requester may see
    summary.json                counts per requester, the classification spread,
                                and how many carriers are ACMG-reportable
    rare.<requester>.tsv        with a panel file: the carriers of variants whose
                                panel frequency is below the case's threshold

With <out-dir>/records.tsv (participant, CHROM, POS, REF, ALT for every record,
which baseline.sh writes), summary.json also counts the records each requester
may see, so arm 4's views are compared record for record, not only on carriers.

This file is the consent logic a pipeline author would write by hand. It
reads use_case.json and nothing from the RDF route, and it encodes the DUO
purpose hierarchy itself (DS is a kind of HMB, which is a kind of GRU), as a
script would, instead of reading the ontology.

Usage:
    baseline_carriers.py <use_case.json> <genes.txt> <genotypes.tsv> <out-dir> [panel.tsv]

panel.tsv is bcftools' CHROM, POS, REF, ALT and frequency for each panel site.
"""

from __future__ import annotations

import collections
import csv
import json
import pathlib
import sys

# DUO: disease-specific research (DS) is health/medical research (HMB), which is
# general research use (GRU). Clinical care (CC) is outside that hierarchy. A
# case may add narrower purposes of its own ("purposes"), which main() adds.
BROADER = {"DUO:0000007": "DUO:0000006", "DUO:0000006": "DUO:0000042"}
CLINICAL = "DUO:0000043"
COLUMNS = ["participant", "gene", "chrom", "pos", "ref", "alt", "classification", "clnsig", "gt", "restricted"]


def within(purpose: str, permitted: str) -> bool:
    """True when a request for `purpose` falls under a consent for `permitted`."""
    while purpose:
        if purpose == permitted:
            return True
        purpose = BROADER.get(purpose, "")
    return False


def classification(clnsig: str) -> str:
    """The first '|'-separated term: ClinVar's own classification of the variant.

    "Pathogenic|risk_factor" classifies as Pathogenic;
    "Conflicting_classifications_of_pathogenicity" classifies as itself.
    """
    return clnsig.split("|")[0]


def is_reportable(clnsig: str, reportable: list[str]) -> bool:
    """A classification an ACMG secondary-findings report would act on."""
    return classification(clnsig) in reportable


def acmg_genes(geneinfo: str, genes: set[str]) -> list[str]:
    # GENEINFO is "SYMBOL:GeneID|SYMBOL:GeneID".
    symbols = (item.split(":")[0] for item in geneinfo.split("|") if item and item != ".")
    return sorted(set(symbols) & genes)


def restricted_spans(regions: list[dict], genes: list[str]) -> dict[str, list[tuple[int, int]]]:
    """The restricted genes' spans by contig name without 'chr', 1-based and inclusive."""
    spans = collections.defaultdict(list)
    for region in regions:
        if region["symbol"] in genes:
            spans[region["chrom"].removeprefix("chr")].append((region["start"], region["end"]))
    return spans


def overlaps(chrom: str, pos: int, ref: str, spans: dict) -> bool:
    """Does the record's REF extent, [POS, POS + len(REF) - 1], touch a span?"""
    end = pos + len(ref) - 1
    return any(start <= end and pos <= stop for start, stop in spans.get(chrom.removeprefix("chr"), ()))


def carriers(rows, definition: dict, genes: set[str], spans: dict) -> list[dict]:
    found = []
    for participant, chrom, pos, ref, alt, clnsig, revstat, geneinfo, gt in rows:
        if revstat in definition["excluded_review_status"]:
            continue
        for gene in acmg_genes(geneinfo, genes):
            found.append({"participant": participant, "gene": gene, "chrom": chrom.removeprefix("chr"),
                          "pos": int(pos), "ref": ref, "alt": alt,
                          "classification": classification(clnsig), "clnsig": clnsig, "gt": gt,
                          "restricted": overlaps(chrom, int(pos), ref, spans)})
    return sorted(found, key=lambda c: (c["participant"], c["gene"], c["pos"], c["alt"]))


def gene_spans(genes: list[str]) -> dict[str, list[tuple[int, int]]]:
    regions = json.loads((pathlib.Path(__file__).resolve().parent / "regions.json")
                         .read_text(encoding="utf-8"))["regions"]
    return restricted_spans(regions, genes)


def released(carrier: dict, purpose: str, policy: dict, assignee: str | None = None,
             panels: list[tuple[str, dict]] = ()) -> bool:
    """May a requester with this purpose (and assignee) see this record?

    `carrier` needs participant and restricted; arm 4's rules also read chrom,
    pos, ref and alt. `panels` pairs each purpose panel with its genes' spans.
    """
    consent = policy["consents"][carrier["participant"]]
    if consent.get("withdrawn"):
        return False
    if not any(within(purpose, permitted) for permitted in consent["permits"]):
        return False
    # The secondary-findings rule is about the record, not ClinVar's gene label.
    if carrier["restricted"] and not within(purpose, CLINICAL):
        return False
    # Arm 4: a purpose limited to a gene panel sees nothing outside it.
    for panel_purpose, spans in panels:
        if within(purpose, panel_purpose) and not overlaps(carrier["chrom"], carrier["pos"], carrier["ref"], spans):
            return False
    # A region is coordinates on a contig. The plug-in's RegionSelector compares
    # the contig name as the file writes it, so the two routes agree only for
    # files written in the rule's naming style, which arm 4's genome is.
    for region in policy.get("regions", ()):
        if (carrier["chrom"].removeprefix("chr") == region["chrom"].removeprefix("chr")
                and region["start"] <= carrier["pos"] <= region["end"]
                and not any(within(purpose, p) for p in region["purposes"])):
            return False
    # A named variant, by identity, withheld from named requesters.
    for variant in policy.get("variants", ()):
        named = {policy["requesters"][who]["assignee"] for who in variant["withheld_from"]}
        if assignee in named and (carrier["chrom"].removeprefix("chr"), carrier["pos"], carrier["ref"],
                                  carrier["alt"]) == (variant["chrom"].removeprefix("chr"), variant["pos"],
                                                      variant["ref"], variant["alt"]):
            return False
    return True


def released_records(records_tsv: pathlib.Path, policy: dict, cancer: dict,
                     panels: list[tuple[str, dict]]) -> dict[str, int]:
    """Records each requester may see, over every record of every participant."""
    counts = collections.Counter()
    requesters = policy["requesters"]
    with records_tsv.open(encoding="utf-8") as handle:
        for line in handle:
            participant, chrom, pos, ref, alt = line.rstrip("\n").split("\t")[:5]
            record = {"participant": participant, "chrom": chrom.removeprefix("chr"),
                      "pos": int(pos), "ref": ref, "alt": alt,
                      "restricted": overlaps(chrom, int(pos), ref, cancer)}
            counts["unrestricted"] += 1
            for name, requester in requesters.items():
                counts[name] += released(record, requester["purpose"], policy, requester["assignee"], panels)
    return dict(counts)


def rare_sites(panel_tsv: pathlib.Path, below: float) -> set[tuple]:
    """(chrom without 'chr', pos, ref, alt) of every panel site with a frequency below `below`."""
    rare = set()
    with panel_tsv.open(encoding="utf-8") as handle:
        for line in handle:
            chrom, pos, ref, alt, frequency = line.rstrip("\n").split("\t")
            if frequency != "." and float(frequency) < below:
                rare.add((chrom.removeprefix("chr"), int(pos), ref, alt))
    return rare


def write(path: pathlib.Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str]) -> int:
    case_json, genes_txt, genotypes_tsv, out_dir, *panel_tsv = map(pathlib.Path, argv)
    case = json.loads(case_json.read_text(encoding="utf-8"))
    genes = {g.strip() for g in genes_txt.read_text(encoding="utf-8").splitlines()
             if g.strip() and not g.startswith("#")}
    with genotypes_tsv.open(encoding="utf-8") as handle:
        rows = [line.rstrip("\n").split("\t")[:9] for line in handle if line.strip()]

    definition = case["definition"]
    for term in case.get("purposes", ()):
        BROADER[term["iri"]] = term["broader"]
    policy = case["policy"]
    spans = gene_spans(policy["secondary_findings"]["genes"])
    panels = [(panel["purpose"], gene_spans(panel["genes"])) for panel in policy.get("purpose_panels", ())]
    everyone = carriers(rows, definition, genes, spans)
    write(out_dir / "carriers.unrestricted.tsv", everyone)
    reportable = definition["reportable_significance"]
    summary = {
        "unrestricted": len(everyone),
        # Reported, not filtered on: an empty subset here is this cohort's
        # answer to the ACMG secondary-findings question, and saying so is the
        # point. See definition.reportable_note.
        "reportable": {"total": sum(1 for c in everyone if is_reportable(c["clnsig"], reportable)),
                       "definition": reportable},
        "classifications": dict(collections.Counter(c["classification"] for c in everyone).most_common()),
    }
    rare = panel_tsv and rare_sites(panel_tsv[0], case["panel"]["rare"]["below"])
    visible = {"unrestricted": everyone}
    for name, requester in policy["requesters"].items():
        visible[name] = [c for c in everyone if released(c, requester["purpose"], policy,
                                                         requester["assignee"], panels)]
        write(out_dir / f"carriers.{name}.tsv", visible[name])
        summary[name] = len(visible[name])
    if panel_tsv:
        summary["rare"] = {}
        for name, rows in visible.items():
            rows = [c for c in rows if (c["chrom"], c["pos"], c["ref"], c["alt"]) in rare]
            write(out_dir / f"rare.{name}.tsv", rows)
            summary["rare"][name] = len(rows)
    if (out_dir / "records.tsv").is_file():
        summary["records"] = released_records(out_dir / "records.tsv", policy, spans, panels)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
