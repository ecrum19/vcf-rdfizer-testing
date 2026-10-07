# Arm 4 smoke run on VCF-RDFizer v3.3.0: the `*` gap

NB72462M restricted to the ACMG gene spans, APOE, and chr17:1,000,000-1,100,000
(10,260 records), on vcf-bench-3, 2026-10-06, with the v3.3.0 tool and image.

Carriers agreed for every requester, but released records did not:

| Requester | RDF view | Baseline |
| --- | ---: | ---: |
| cardio | 6,380 | 6,397 |
| biobank | 7,753 | 7,740 |

The v3.3.0 gene linker skipped every record whose ALT is `*` (34 here), so they
had no gene links. The cancer-gene prohibition never matched the 13 in cancer
genes (released to the biobank), and the cardiac-panel rule withheld the 17 in
cardiac genes from cardio. v3.3.1 links `*` records by their REF span; see
`../17_use_case_acmg__layered` for the whole genome on v3.3.1.

`link__NB72462M__failed_cold_reference_cache` is a first link attempt that
failed because the Ensembl reference bundle had not been fetched on this host;
the cell after it ran with the warmed cache. Small files only.
