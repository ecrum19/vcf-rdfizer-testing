# Default-profile mutation rerun (vcf-bench-2, 2026-10-01)

The mutation score of `08_robustness`, rerun outside the 143-cell campaign with
the default (`core`) shape profile, on the campaign's own release: VCF-RDFizer
v3.1.0 (commit `d3b34d5`, image `ecrum19/vcf-rdfizer:3.1.0`, `sha256:1904e96d…34aa`).
It is the middle bar of Figure 3b; the other two come from `08_robustness` in
`vcf-bench-1/benchmarks_outputs/`.

| Directory | What | Result |
| --- | --- | --- |
| `mutation__none/` | The mutation score with queries only, as a control | 96/113, as in the campaign |
| `mutation__core/` | The mutation score with the default shape profile | 96/113; `detectedByShacl` 0 |

Each directory holds `mutation-score.json` (every mutation, its class, and which
layer detected it) and the test run's `stdout.log` and `stderr.log`.

[`review_runs.sh`](review_runs.sh) is the driver; [`review-runs.log`](review-runs.log)
is its log. The directory keeps its name from the host (`~/vrdev-test/review-runs`).
The driver's second half, and the later lines of the log, belong to the v3.1.0
validation runs of the consumer WGS VCF (NG131FQA1I). The manuscript reports that
run's v3.3.1 rerun instead
([`../v331-rerun/`](../v331-rerun/README.md)), so the v3.1.0 runs, their
diagnostics and the validator-fix runs are on the
[`legacy` branch](https://github.com/ecrum19/vcf-rdfizer-testing/tree/legacy/benchmark-results/vcf-bench-2/review-runs).
