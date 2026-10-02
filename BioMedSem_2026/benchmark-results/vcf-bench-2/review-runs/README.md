# Review runs (vcf-bench-2, 2026-10-01/02)

Two runs on the campaign's own release, VCF-RDFizer v3.1.0 (commit `d3b34d5`, image
`ecrum19/vcf-rdfizer:3.1.0`, `sha256:1904e96d…34aa`), outside the 143-cell campaign.
Small result files only; the generated graphs are not kept here.

| Directory | What | Result |
| --- | --- | --- |
| `mutation__none/` | mutation score, queries only (control) | 96/113, reproduces the campaign |
| `mutation__core/` | mutation score with the default (`core`) shape profile | 96/113, `detectedByShacl` 0 |
| `validate__NG131FQA1I__first250000/` | paired QLever validation with the default shapes | host ran out of memory; no report |
| `validate__NG131FQA1I__first250000__noshacl/` | the same with `--no-shacl` and a memory watchdog | 58,231,176 triples; 10/13 exact; MISMATCH on Q9/Q10 (phase sets the oracle does not model) and Q11 (QLever's canonical QUAL) |
| `diag_q11.out`, `diag_q11b.out` | graph literals against the VCF text; canonical-QUAL bucket check | 0 fields differ; 0 bucket differences with canonical QUAL (788 as written) |

`review_runs.sh`, `validate_noshacl.sh`, `diag_q11.py` and `diag_q11b.py` are the
scripts that produced them; `review-runs.log` is the run log.
