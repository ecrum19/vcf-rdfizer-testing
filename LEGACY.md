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

## Removed from main before the Zenodo release (2026-10-09)

These files were unused by the manuscript, the harness or the results site, or
were internal working notes. Each can be read at commit `efd5f22d`, the last
commit that has all of them, for example
`git show efd5f22d:benchmarks/RUN_PLAN.md`.

| Original path | What it was |
| --- | --- |
| `BioMedSem_2026/paper/current_long.tex`, `supplementary_long.tex` and their PDFs | The full-length manuscript and supplement, superseded by the condensed pair. Their numbers predate the v3.3.1 rerun. |
| `BioMedSem_2026/paper-assets/fig-workflow.*`, `fig-usecase.*` | A workflow diagram no document included, and the use-case diagram that only the first co-author brief used. |
| `BioMedSem_2026/paper-assets/figures/count_validation.py` | A tally of the validation evidence, superseded by `validation_counts()` in `scripts/build_site_data.py`, which the figures and the site tests use. |
| `BioMedSem_2026/paper-assets/vcf2rdf-v3.fls`, `vcf2rdf-v3.fdb_latexmk` | LaTeX build files. |
| `benchmarks/RUN_PLAN.md`, `benchmarks/AGGREGATION.md` | The pre-release campaign's host plan and the steps for pulling results off the hosts. Their lasting content is in `benchmarks/README.md`, under "How the manuscript's results were produced". |
| `tool-docs/jbms-review-vcf-rdfizer.md`, `jbms-revision-plan.md`, `workstream-a-implementation.md`, `proposal-indexed-regional-access-arm.md`, `results-site-plan.md`, `cottas-multiple-indexes.md` | A simulated journal review and the plans and notes written while acting on it. |
| `tool-docs/coauthor-report/report.tex`, and the figure copies only it used | The first co-author brief, superseded by `report_revised.tex`. |

`benchmarking_suggestions.md` moved to [`benchmarks/DESIGN.md`](benchmarks/DESIGN.md).

## Moved before the Zenodo release (2026-10-10)

| Old path | New path |
| --- | --- |
| `BioMedSem_2026/benchmark-results/` | `benchmark-results/` |
| `BioMedSem_2026/paper-assets/figures/figure_data.py` | `scripts/figure_data.py` |

Both were moved with `git mv`, so `git log --follow <new path>` shows each file's
full history. `BioMedSem_2026/` and `tool-docs/` stay in the repository but are
left out of the Zenodo archive (see `.gitattributes`).

## Material retained on main

The current benchmark harness, fixtures, plug-in tests, ACMG use case, paper and
supplement remain on `main`. So do the run records used to substantiate the
supplement's testing issues, even when those records describe failed or
superseded runs. Removing them would break the paper's evidence trail.

`scripts/combine_benchmark_metrics.py` remains because the current
`build_run_summary.py` imports it. The download, Ubuntu setup and host-reporting
scripts are also active dependencies. The benchmark design rationale is
`benchmarks/DESIGN.md`.

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

Neither cleanup rewrote Git history. Historical files remain available through
`legacy`, `efd5f22d`, and the existing commits.
