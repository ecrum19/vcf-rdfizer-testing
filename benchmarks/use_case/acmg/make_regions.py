#!/usr/bin/env python3
"""Pin the GRCh38 regions of the ACMG SF v3.2 genes, once, from Ensembl.

The use case restricts every input to these genes, so the region file is an
input and is committed rather than fetched at run time. This script records
where it came from: the gene list's source, the Ensembl release, and each
gene's stable ID. Re-running it against a later Ensembl release may move a
gene's span, which is why the output is pinned and this is not run by
``17_use_case_acmg.sh``.

Each region is the gene's full span (UTRs and introns included), with no
padding. A ClinVar variant in a promoter outside that span is therefore out
of scope for both routes alike.

Usage:
    python3 make_regions.py            # writes acmg_sf_v3.2.GRCh38.bed + regions.json
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
GENES = HERE / "acmg_sf_v3.2.genes.txt"
ENSEMBL = "https://rest.ensembl.org"


def ensembl(path: str, body: dict | None = None) -> object:
    # System curl rather than urllib: it uses the OS trust store, which some
    # Python installs (python.org's on macOS) do not.
    argv = ["curl", "-sSf", "--retry", "3", "-H", "Accept: application/json", ENSEMBL + path]
    if body is not None:
        argv += ["-H", "Content-Type: application/json", "--data", json.dumps(body)]
    return json.loads(subprocess.run(argv, check=True, capture_output=True, text=True).stdout)


def read_genes() -> list[str]:
    lines = GENES.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def main() -> int:
    genes = read_genes()
    if len(genes) != 81 or len(set(genes)) != 81:
        sys.exit(f"expected 81 distinct ACMG SF v3.2 genes, found {len(set(genes))}")

    release = ensembl("/info/data")["releases"]
    assembly = ensembl("/info/assembly/homo_sapiens")["assembly_name"]
    # A patch release (GRCh38.p14) keeps the primary-assembly coordinates.
    if assembly.split(".")[0] != "GRCh38":
        sys.exit(f"Ensembl serves {assembly}, not GRCh38")
    found = ensembl("/lookup/symbol/homo_sapiens", {"symbols": genes})

    regions = []
    for symbol in genes:
        gene = found.get(symbol)
        if not gene:
            sys.exit(f"Ensembl has no gene for symbol {symbol}")
        if gene.get("assembly_name") != "GRCh38":
            sys.exit(f"{symbol}: assembly {gene.get('assembly_name')}")
        regions.append({
            "symbol": symbol,
            "ensembl_id": gene["id"],
            "chrom": "chr" + gene["seq_region_name"],
            "start": gene["start"],  # 1-based, inclusive (Ensembl)
            "end": gene["end"],
        })

    regions.sort(key=lambda r: (chrom_order(r["chrom"]), r["start"]))
    # BED is 0-based half-open: start - 1, end unchanged.
    bed = "".join(f"{r['chrom']}\t{r['start'] - 1}\t{r['end']}\t{r['symbol']}\n" for r in regions)
    (HERE / "acmg_sf_v3.2.GRCh38.bed").write_text(bed, encoding="utf-8")
    (HERE / "regions.json").write_text(json.dumps({
        "gene_list": "ACMG SF v3.2 (Miller et al. 2023, Genet Med 25:100866), "
                     "as tabulated at https://www.ncbi.nlm.nih.gov/clinvar/docs/acmg/",
        "coordinates": f"Ensembl release {release[0]} ({assembly}), gene span, no padding",
        "genes": len(regions),
        "bases": sum(r["end"] - r["start"] + 1 for r in regions),
        "regions": regions,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"{len(regions)} genes, Ensembl {release[0]}")
    return 0


def chrom_order(chrom: str) -> int:
    name = chrom.removeprefix("chr")
    return int(name) if name.isdigit() else {"X": 23, "Y": 24}.get(name, 25)


if __name__ == "__main__":
    raise SystemExit(main())
