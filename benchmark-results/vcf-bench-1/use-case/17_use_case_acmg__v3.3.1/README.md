# Arm 1 again, on VCF-RDFizer v3.3.1

Arm 1's link, govern, query, baseline and compare stages, re-run on 2026-10-06
with the tool checkout at `29a81f6` (VCF-RDFizer PR #32, release v3.3.1) and
image `ecrum19/vcf-rdfizer:3.2.0`, as in arm 1. Derive and convert were not
re-run: they are arm 1's cells (`../17_use_case_acmg/`), hard-linked on the VM.

Why: arm 4's record-level comparison found that up to v3.3.0 the gene linker
skipped records whose ALT is `*`, so the rule withholding the 28
cancer-predisposition genes did not reach them. Arm 1's first run compared
carriers only, which those records do not change.

| | first run (`../17_use_case_acmg`) | this run |
| --- | --- | --- |
| gene-linker skipped records, NB72462M / NG131FQA1I | 33 / 32 | 0 / 0 |
| records released, clinical | 19,625 | 19,625 |
| records released, cardio | 23,957 | 23,933 (−13 NB72462M, −11 NG131FQA1I) |
| records released, biobank | 16,118 | 16,105 (−13 NB72462M) |
| carriers, every requester | agree | agree, identical counts |
| records vs. baseline | not compared | agree for every requester |

Every removed record is a `*` record inside a cancer-predisposition gene.
Small files only, as for the other use-case directories.
