# Arm 4: layered governance on one whole genome (VCF-RDFizer v3.3.1)

NB72462M's whole genome (5,063,417 records, 1.22B triples with links) under
layered, simulated consent, on vcf-bench-3, 2026-10-06/07. Linking and
governance ran from the tool checkout at `29a81f6` (VCF-RDFizer PR #32,
release v3.3.1); conversion and queries used image `ecrum19/vcf-rdfizer:3.3.0`.
Derive and convert cells come from the v3.3.0 run on the same host (hard links,
not re-run). The policy is `benchmarks/use_case/acmg/layered/`.

| Requester (purpose) | Records released | Withheld, by rule | Matches |
| --- | ---: | --- | ---: |
| own physician (own-physician care) | 5,063,417 | none | 1,382 |
| clinical (CC) | 5,063,411 | 6 APOE region | 1,382 |
| cardio (DS) | 6,397 | 5,054,507 outside the cardiac panel; 2,513 cancer genes | 722 |
| biobank (GRU) | 5,060,897 | 2,513 cancer genes; 6 APOE; 1 named variant (DSP) | 983 |

Matches (participant-variant-gene, unrestricted 1,382) and released records
agree with the bcftools baseline for every requester (`comparison.json`); every
view passed its policy and source checks (`govern__*/check.txt`). Govern took
55-74 min per requester; queries 10-93 min. MemAvailable stayed above 17.3 GB
(`resources.tsv`).

The record-level comparison is why v3.3.1 exists: on v3.3.0 the gene linker
skipped the 34 `*` (spanning-deletion) records, so 13 in cancer genes were
released to the biobank and 17 in cardiac genes were withheld from cardio. See
`../17_use_case_acmg__layered__smoke_v3.3.0` (gene-region slice, 3.3.0) and
`../../vcf-bench-1/use-case/17_use_case_acmg__v3.3.1` (arm 1 on 3.3.1).

Small files only, as for the other use-case directories.
