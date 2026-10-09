# VCF-RDFizer v3.3.1 rerun on vcf-bench-1 (2026-10-08)

Part of the rerun that gives every reported result a published release: VCF-RDFizer v3.3.1 (tag commit
`b25fb7b`, image `ecrum19/vcf-rdfizer@sha256:3ad71b1a54612142e3be43b24e7e4a38551949cb641f4421bcae9bf051102993`),
harness `vcf-rdfizer-testing` `6f2239ff`. The driver is [`run_v331.sh`](run_v331.sh) (role `bench1`);
[`run.log`](run.log) is its log. The jobs ran one at a time, each under a memory watchdog
(`resources.<job>.tsv`).

| Job | What | Wall | Result |
|---|---|---|---|
| `arm1` | Experiment 17, Arm 1: five gene-span slices | 53 min | Both routes agree on every carrier list and record count (`results/17_use_case_acmg/comparison.json`) |
| `regional` | Experiment 14, regional retrieval on the v3.1.0 graphs that `13_query_cost` built | 85 min | Completed (`results/14_regional_access/`) |
| `arm2` | Experiment 17, Arm 2: 104 1000 Genomes participants | 3.0 h | Carrier lists agree. The record-level check does not: see below. Exit 1 is the comparison's verdict, not a failure. |

## Arm 2's record-level disagreement

The release views released 110 more records to the disease-specific requester (cardio, DUO:0000007) and
58 more to the general-research requester (biobank, DUO:0000042) than the bcftools baseline.
[`diag-arm2/`](diag-arm2/) re-applies the baseline's rule to every record in the RDF route's decision log:
- Every differing record is a symbolic structural variant: `<INS:ME:...>`, `<DUP>`, or `<INS>`.
- Each lies inside a cancer-predisposition gene, such as BRCA2, WT1, NF2, STK11, or TSC2.

v3.3.1's gene linkers key no record with a symbolic or breakend ALT, so those records have no gene link, and the
prohibition on those genes cannot reach them. The paper keeps v3.3.1 and states this as a limitation;
ecrum19/VCF-RDFizer#34 links such records by their REF span.

## Not included

The 251 files listed in [`excluded-files.tsv`](excluded-files.tsv), with size and SHA-256:
- graphs, link sets, and release views (`.nt.gz`);
- the derived VCFs;
- the per-record `decisions.csv` and `records.tsv`;
- anything else over 5 MB.

They stay on the host under `~/vrdev-test/v331/`. [`pack_v331.sh`](pack_v331.sh) made the selection on
every host.
