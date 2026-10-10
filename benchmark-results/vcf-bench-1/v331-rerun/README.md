# VCF-RDFizer v3.3.1 rerun on vcf-bench-1 (2026-10-08)

Part of the rerun that gives every reported result a published release: VCF-RDFizer v3.3.1 (tag commit
`b25fb7b`, image `ecrum19/vcf-rdfizer@sha256:3ad71b1a54612142e3be43b24e7e4a38551949cb641f4421bcae9bf051102993`),
harness `vcf-rdfizer-testing` `6f2239ff`. The driver is [`run_v331.sh`](run_v331.sh) (role `bench1`);
[`run.log`](run.log) is its log. The jobs ran one at a time, each under a memory watchdog
(`resources.<job>.tsv`).

| Job | What | Wall | Result |
|---|---|---|---|
| `arm1` | Experiment 17, Scenario 1: five gene-span slices | 53 min | Both routes agree on every carrier list and record count (`results/17_use_case_acmg/comparison.json`) |
| `regional` | Experiment 14, regional retrieval on the v3.1.0 graphs that `13_query_cost` built | 85 min | Completed (`results/14_regional_access/`) |
| `arm2` | Experiment 17, Scenario 2: 104 1000 Genomes participants | 3.0 h | Carrier lists agree. The record-level check does not: see below. Exit 1 is the comparison's verdict, not a failure. |
| `myvariant` | Experiment 17, Scenario 1's MyVariant.info tier (2026-10-09; role `bench1-myvariant`, harness `4ea07cc7`) | 1 min | Same links as the 2026-09-28 run, from its recorded responses: see below |

## Scenario 2's record-level disagreement

The release views released 110 more records to the disease-specific requester (cardio, DUO:0000007) and
58 more to the general-research requester (biobank, DUO:0000042) than the bcftools baseline.
[`diag-arm2/`](diag-arm2/) re-applies the baseline's rule to every record in the RDF route's decision log:
- Every differing record is a symbolic structural variant: `<INS:ME:...>`, `<DUP>`, or `<INS>`.
- Each lies inside a cancer-predisposition gene, such as BRCA2, WT1, NF2, STK11, or TSC2.

v3.3.1's gene linkers key no record with a symbolic or breakend ALT, so those records have no gene link, and the
prohibition on those genes cannot reach them. The paper keeps v3.3.1 and states this as a limitation;
ecrum19/VCF-RDFizer#34 links such records by their REF span.

## Scenario 1's MyVariant.info tier

The live tier (`rsid-myvariant` on the two PGP files) first ran on 2026-09-28 from a pre-release tree, outside
the harness, and made 21 requests to MyVariant.info. That run's records are on the legacy branch, in
[`vcf-bench-1/use-case/17_use_case_acmg/link_myvariant__*`](https://github.com/ecrum19/vcf-rdfizer-testing/tree/legacy/benchmark-results/vcf-bench-1/use-case/17_use_case_acmg). Harness `4ea07cc7` adds it to experiment 17 as the
`link_myvariant` stage, which replays recorded responses offline. This job ran that stage with v3.3.1 on the
21 responses of 2026-09-28, copied from this host's linker cache to `~/vrdev-test/v331/myvariant-cache/`
(their SHA-256 in [`inputs.bench1-myvariant.sha256`](inputs.bench1-myvariant.sha256)). The same 21 files,
byte for byte, are published as the stage's default recording in
[`benchmarks/use_case/acmg/myvariant-cache/`](../../../benchmarks/use_case/acmg/myvariant-cache/);
reproduce the result from them, not from the live service, whose data change.
- **No request reached the service.** Each `link_myvariant__*/out/*.links.json` records 0 requests, 0 bytes
  transferred, and 10 and 11 cache hits; their response digests are the 2026-09-28 run's.
- **Identical result.** The linker confirmed 9,223 of 9,951 (NB72462M) and 9,479 of 10,316 (NG131FQA1I) rsID
  links, and `results/17_use_case_acmg/tier1_vs_tier3_myvariant.json` is byte-identical to that run's.
- **Why the replay answers every request.** v3.3.1's `rsid-myvariant` manifest and resolver are byte-identical to
  the ones the first run recorded, and the derived VCFs' records are identical (only two `##bcftools_viewCommand`
  header lines differ), so v3.3.1 builds the same 21 requests.

[`run_v331.sh`](run_v331.sh) is the driver with the added role; `run.log` continues with this job.

## Not included

The 253 files listed in [`excluded-files.tsv`](excluded-files.tsv), with size and SHA-256:
- graphs, link sets (`.nt`, `.nt.gz`), and release views;
- the derived VCFs;
- the per-record `decisions.csv` and `records.tsv`;
- anything else over 5 MB.

They stay on the host under `~/vrdev-test/v331/`. [`pack_v331.sh`](pack_v331.sh) made the selection on
every host.
