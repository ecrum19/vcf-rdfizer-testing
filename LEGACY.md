# Legacy archive

The [`legacy` branch](https://github.com/ecrum19/vcf-rdfizer-testing/tree/legacy)
preserves the complete repository at the October 1, 2026 cleanup boundary
(`71ec037e`), plus the previously untracked ECCB LaTeX template files, and the
run records moved off `main` on 2026-10-10. Files retain their original paths.
`main` contains the harness and the run records of every reported result.

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
| `benchmarks/RUN_PLAN.md`, `benchmarks/AGGREGATION.md` | The pre-release campaign's host plan and the steps for pulling results off the hosts. Their lasting content, which host ran each experiment and how its records were archived, is in `benchmarks/README.md` and `benchmark-results/README.md`. |
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

## Moved to the legacy branch (2026-10-10)

`main` now holds only the runs whose results the manuscript reports. Every other
run record moved to `legacy`, at the path it had on `main` and byte-identical to
`main` at `66f53577`; the supplement cites some of them as evidence of the
defects the reported runs corrected.
[`benchmark-results/README.md` on `legacy`](https://github.com/ecrum19/vcf-rdfizer-testing/tree/legacy/benchmark-results) lists each one,
what it is, and which statement in the supplement cites it.

| Moved from `benchmark-results/` | What it is |
| --- | --- |
| `vcf-bench-{1,2}/benchmarks_outputs__campaign1__*/`, `benchmarks_outputs_calibration*/` | The pre-release campaign, and the host calibrations |
| `vcf-bench-1/benchmarks_outputs__superseded/`, `vcf-bench-2/benchmarks_outputs__stalled/`, `vcf-bench-{1,2}/benchmarks_outputs__partial/`, `vcf-bench-2/benchmarks_outputs__offsplit/`, `vcf-bench-1/benchmarks_outputs__tool8b1b4a8/` | Superseded, stopped, interrupted and off-host base-campaign runs, and an older tool's storage data |
| `vcf-bench-1/benchmarks_outputs/14_regional_access/`, `vcf-bench-3/benchmarks_outputs/16_scale_retrieval*/`, `vcf-bench-{1,2,3}/use-case/` | The pre-release regional, large-graph and use-case runs, rerun with v3.3.1 |
| `vcf-bench-2/review-runs/validate__*`, `shacl-mem/`, `diag_q11*`, `e2e_*`, `validate_noshacl.sh` | The v3.1.0 consumer WGS validation runs, their diagnostics, and the validator-fix runs, rerun with v3.3.1 |
| `vcf-bench-2/v331-rerun/attempt{1,2}-*`, `vcf-bench-3/v331-rerun/attempt1-exit126/` | Failed attempts within the v3.3.1 rerun |
| `_manifests/` | The 2026-09 host pulls' file counts and tarball checksums, which count the moved trees |

`summary.json` was rebuilt from what remains, the 143 base-campaign cells; those
records are unchanged. `main`'s earlier `summary.json`, which classifies all 382
cells, moved with the runs. The results site's consumer WGS panel now shows only
the v3.3.1 run.

## Sites-only cell replaced by its rerun (2026-10-10)

The base campaign's `09_awkward_inputs/awkward_sites_only` cell ran on a
malformed fixture: `benchmarks/lib/make_fixtures.py` wrote a FORMAT column with no
samples after it, which bcftools rejects, so neither paired validation ran. The
generator is fixed, and the cell was rerun on the same host with the same release
and arguments ([`benchmark-results/vcf-bench-1/sites-only-rerun/`](benchmark-results/vcf-bench-1/sites-only-rerun/README.md)).

| Moved from `benchmark-results/` | Now on `legacy` at |
| --- | --- |
| `vcf-bench-1/benchmarks_outputs/09_awkward_inputs/awkward_sites_only/` (the 2026-09-24 run), byte-identical to `main` at `66f53577` | `vcf-bench-1/benchmarks_outputs__superseded/09_awkward_inputs__malformed_sites_only__20260924T161103/awkward_sites_only/`, with a README and the experiment's tidy table as it stood |

`summary.json` was rebuilt; only that cell's record and experiment 09's roll-up
changed. The site's validation totals became 78 of 78 completed validations, 1,006
equal query comparisons, and 8 verified not applicable.

## Material retained on main

The benchmark harness, fixtures, plug-in tests, linked-workflow definitions,
results site, paper and supplement remain on `main`, with the run records of every
reported result. Every script in `benchmarks/` and `scripts/` produced, computes or
checks a reported result; `benchmarks/README.md` and the README's support-script
table say which. `benchmarks/DESIGN.md` gives each experiment's design as run,
by the paper's research questions; the plan written before the campaign is in its
history (`git show 66f53577:benchmarks/DESIGN.md`).

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

No cleanup rewrote Git history. Historical files remain available through
`legacy`, `efd5f22d`, `66f53577`, and the existing commits.
