# Review runs (vcf-bench-2, 2026-10-01/02)

The first runs used the campaign's own release, VCF-RDFizer v3.1.0 (commit `d3b34d5`, image
`ecrum19/vcf-rdfizer:3.1.0`, `sha256:1904e96d…34aa`), outside the 143-cell campaign.
Small result files only; the generated graphs are not kept here.

| Directory | What | Result |
| --- | --- | --- |
| `mutation__none/` | mutation score, queries only (control) | 96/113, reproduces the campaign |
| `mutation__core/` | mutation score with the default (`core`) shape profile | 96/113, `detectedByShacl` 0 |
| `validate__NG131FQA1I__first250000/` | paired QLever validation with the default shapes | host ran out of memory; no report |
| `validate__NG131FQA1I__first250000__noshacl/` | the same with `--no-shacl` and a memory watchdog | 58,231,176 triples; 10/13 exact; MISMATCH on Q9/Q10 (phase sets the oracle does not model) and Q11 (QLever's canonical QUAL) |
| `diag_q11.out`, `diag_q11b.out` | graph literals against the VCF text; canonical-QUAL bucket check | 0 fields differ; 0 bucket differences with canonical QUAL (788 as written) |
| `validate__NG131FQA1I__first250000__fixes/` | the same slice on an earlier build of the fixes, before the 500k-triple shape-batch default | stopped by the memory watchdog during validation (MemAvailable 0.6 GB); no report |
| `validate__NG131FQA1I__first250000__fixes_b500k/` | the same with 500k-triple shape batches, the v3.3.1 default | **PASS**: 13/13 exact; default shapes 0 violations, 46 warnings, 117 batches, 89 min; MemAvailable never below 19.9 GB |
| `shacl-mem/` | pyshacl peak memory and time for one and four shape batches of that graph | 0.51M triples: 1.26 GB, 155 s; 2.0M triples: 4.72 GB, 607 s (about 2.4 GB and 300 s per million triples) |

The `__fixes` runs and `shacl-mem/` used the scratch image tag `vcf-rdfizer:dev-validation-fixes`,
built on the VM from the fix tree. The passing `__fixes_b500k` run used image ID
`sha256:29c371ada059d0755df464a4e9bab434ac326daf3e8a464395118a16921c5317` (built 09:57 UTC, run
started 10:07 UTC), built from the tree committed as VCF-RDFizer `3994e94`, whose message reports
this run. The stopped attempt and `shacl-mem/` ran on earlier builds of that tag (`shacl-mem/` sets
its batches explicitly). Between `3994e94` and release v3.3.1 (`29a81f6`) the validation code changes
only by naming a constant (`c373492`); the rest is linking and docs. The fixes in `3994e94`:
the census oracle counts phase sets, SV events, confidence intervals and gVCF blocks; Q11 drops a
decimal QUAL's trailing zeros on both sides; node-local shapes are validated in record batches.
The graph is the same 58,231,176 triples as the v3.1.0 runs. `shacl-report.txt` is gzipped here.

`review_runs.sh`, `validate_noshacl.sh`, `e2e_fixes.sh`, `e2e_fixes_b500k.sh`, `diag_q11*.py` and
`shacl-mem/shacl_*.py` are the scripts that produced them; `review-runs.log` is the run log.
