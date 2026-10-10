# Experiment 17, Arm 4 with VCF-RDFizer v3.3.0 (vcf-bench-3, 2026-10-06 to 2026-10-08)

The layered-consent arm (one complete WGS VCF, NB72462M, under layered consent; four requesters)
of [`benchmarks/17_use_case_acmg.sh`](../../../../benchmarks/17_use_case_acmg.sh), run with the
published v3.3.0 release. The paper reports Arm 4 from a rerun with v3.3.1 on vcf-bench-2 instead.
This run is kept because its record-level comparison shows the gap that v3.3.1 closed.

| | |
|---|---|
| VCF-RDFizer | v3.3.0, commit `7ab2300` (every cell's `bench.json`, `tool_commit`) |
| Image | `ecrum19/vcf-rdfizer@sha256:1838720dc0c23d9df760be661d028e5227f32371c765af48f7af2f3759d06432` |
| Host | vcf-bench-3 |
| Cells | 16, all exit 0: derive, convert, and link for NB72462M and ClinVar; baseline; governed views for four requesters; queries; the comparison |

## Result

`comparison.json`: the carrier lists of every requester agree with the bcftools baseline. The
counts of records each release view keeps do not agree for two requesters:

| Requester | Baseline | RDF route | Agree |
|---|---|---|---|
| own physician | 5,063,417 | 5,063,417 | yes |
| clinical | 5,063,411 | 5,063,411 | yes |
| cardio (panel of cardiac genes) | 6,397 | 6,380 | no, 17 fewer |
| biobank (research) | 5,060,897 | 5,060,910 | no, 13 more |

Both gaps are NB72462M's spanning-deletion (`*`) records. v3.3.0's gene linkers keyed no record
with a `*` allele, so those records had no gene links:
- 13 records in cancer-predisposition genes escaped the prohibition that withholds those genes
  from research, and were released to the biobank view.
- 17 records in cardiac genes were withheld from the view limited to those genes.

VCF-RDFizer v3.3.1 links `*` records by their REF span (VCF-RDFizer commit `2022d61`, "Link
spanning-deletion `*` records to the genes their REF span overlaps").

## Not included

The converted graphs, link sets, and release views, which the archived commands regenerate. The
run's working tree on vcf-bench-3 was removed after this archive was taken (logged in
`~/vrdev-test/deleted-2026-10-08.txt` on that host).
