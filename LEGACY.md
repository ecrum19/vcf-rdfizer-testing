# Legacy archive

The [`legacy` branch](https://github.com/ecrum19/vcf-rdfizer-testing/tree/legacy)
preserves the complete repository at the October 1, 2026 cleanup boundary
(`71ec037e`), plus the previously untracked ECCB LaTeX template files.
Files retain their original paths. `main` contains the current tests and reports.

## Material removed from main

| Original path | Archived material |
| --- | --- |
| `experiments/finished_experiments/` | Earlier named conversion/compression runs and their aggregate metrics. The directory uses an underscore, not a hyphen. |
| `ECCB_2026/` | Previous paper, bibliography, figures, result tables, benchmark records and OUP template files. |
| Root `test_*.sh` files | Seven earlier single-configuration conversion, compression, indexing and validation runners, replaced by `benchmarks/`. |
| `scripts/export_latex_tables.py`, `localize_experiment.py`, `plot_combined_metrics.py`, `repair_compression_wall_times.py` | The earlier experiment-localization, reporting and historical timing-repair workflow. |
| `tool-docs/benchmark-experimental-plan.md`, `implementation-improvements-from-benchmarking.md`, `vcf_rdfizer_testing_queries_plan.md` | Superseded benchmark design, pre-release findings and the original six-query proposal. |
| `tool-docs/vcf2rdf*.drawio.xml` and the accompanying `Zone.Identifier` file | Earlier workflow diagrams, replaced by the current TikZ figure sources. |
| `BioMedSem_2026/paper-assets/class-hierarchy-paper.png`, `combined_metrics_figure.png`, `vcf2rdf.pdf`, `vcf2rdf.svg` | Figures no longer included by the current manuscript or supplement. |
| `BioMedSem_2026/paper-assets/fig-policy-*` and `figures/data/policy-demo/` | The synthetic policy demonstrator's figures and captured results, superseded in the paper by the real-genome use case. Its plotting code is preserved in the archived `make_figures.py`. |

## Material retained on main

The current benchmark harness, fixtures, plug-in tests, ACMG use case, paper and
supplement remain on `main`. So do the run records used to substantiate the
supplement's testing issues, even when those records describe failed or
superseded runs. Removing them would break the paper's evidence trail.

`scripts/combine_benchmark_metrics.py` remains because the current
`build_run_summary.py` imports it. The download, Ubuntu setup and host-reporting
scripts are also active dependencies. The benchmark design rationale and the
current review/implementation documents remain with the workflows they support.

## Retrieve archived files

Browse the branch on GitHub, or create a separate checkout:

```bash
git fetch origin legacy
git worktree add --detach ../vcf-rdfizer-testing-legacy origin/legacy
```

For a single file, without changing the current checkout:

```bash
git show origin/legacy:scripts/export_latex_tables.py
```

This is a normal branch archive; no Git history was rewritten. Historical files
remain available through `legacy` and the existing commits.
