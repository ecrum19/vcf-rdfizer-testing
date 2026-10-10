# Run records retired from main (2026-10-10)

These run records were on `main` under the same paths until 2026-10-10, when
`main` was reduced to the runs whose results the BioMedSem 2026 manuscript
reports. Every file here is byte-identical to the one `main` had at commit
`66f53577`; nothing was edited or removed when it moved. (`BioMedSem_2026/benchmark-results/`
on this branch is a separate, older copy: the repository as it stood on 2026-10-01.)

Each directory is one of four kinds:
- **pre-release**: produced by a development build. The paper reports a later
  run with a published release.
- **superseded**: replaced by a later run of the same experiment, after a fix.
- **failed or stopped**: did not finish. Kept as evidence of the defect that
  stopped it.
- **not reported**: completed, but the paper does not use it.

Some are still cited in the supplement as evidence of the defects that the
reported runs corrected. That use is in the last column. The reported runs
are on [`main`](https://github.com/ecrum19/vcf-rdfizer-testing/tree/main/benchmark-results).

## Base campaign (experiments 00-13)

The paper reports the v3.1.0 campaign in `vcf-bench-{1,2}/benchmarks_outputs/` on `main`.

| Path | Kind | What it is | Cited in the supplement for |
| --- | --- | --- | --- |
| `vcf-bench-1/benchmarks_outputs__campaign1__20260922T172925/`, `vcf-bench-2/benchmarks_outputs__campaign1__20260922T173002/` | pre-release | The first campaign, on development commit `a3679e1` (local image tags), set aside when the whole suite was rerun on v3.1.0 | "An earlier pre-release campaign ... archived" (Reproducibility) |
| `vcf-bench-*/benchmarks_outputs_calibration/` | not reported as a cell | The v3.1.0 calibration: `12_modes_smoke` under identical settings on both campaign hosts | Calibration: identical triples, conversion 26 vs 37 s and validation 156 vs 208 s, so timings are compared within a host (Hosts, measurements) |
| `vcf-bench-1/benchmarks_outputs_calibration__025fb7d_20260914T155155/`, `vcf-bench-2/benchmarks_outputs_calibration__pre_rebalance_20260914T154843/`, `vcf-bench-*/benchmarks_outputs_calibration__campaign1__*/` | pre-release | Earlier calibrations, before the hosts were rebalanced and for the pre-release campaign | |
| `vcf-bench-1/benchmarks_outputs__superseded/11_covering_set__6row__20260915T144211/` | superseded | A six-row covering set on a pre-release build | Dangling allele references: 1,972 genotype references to absent alleles and 5,916 shape violations in a 1,000-record test (defects table) |
| `vcf-bench-1/benchmarks_outputs__superseded/11_covering_set__buggy_oracle__20260915T135234/` | superseded | The covering set with a defect in the preflight oracle | |
| `vcf-bench-1/benchmarks_outputs__superseded/13_query_cost__format_item_bug__20260916T104331/` | superseded | Query cost on a build with a FORMAT-item defect, which produced three COTTAS mismatches | |
| `vcf-bench-1/benchmarks_outputs__superseded/08_robustness__no_shacl_host__20260924T132739/` | superseded | v3.1.0 robustness run on a host without pyshacl; rerun as `rerun08.log` on `main` | |
| `vcf-bench-1/benchmarks_outputs__superseded/09_awkward_inputs__no_network__20260924T160616/` | superseded | v3.1.0 difficult-inputs run without network for the demonstration linkers; rerun as `rerun09_network.log` on `main` | |
| `vcf-bench-2/benchmarks_outputs__stalled/` | stopped | Two `06_equivalence` runs in which pycottas' rdflib Store did not finish `q05_sample_genotype_counts` on the condensed encoding, after 41 h and then 10 h; in-process timeouts did not stop it | COTTAS query execution (defects table). The reported `06_equivalence` uses the DuckDB-backed endpoint instead |
| `vcf-bench-1/benchmarks_outputs__partial/`, `vcf-bench-2/benchmarks_outputs__partial/` | failed | Cells of `07` and `06` interrupted before `bench.json` was written | |
| `vcf-bench-2/benchmarks_outputs__offsplit/` | not reported | `04_scaling_records` started on the host that did not own it | |
| `vcf-bench-1/benchmarks_outputs__tool8b1b4a8/` | not reported | Storage-mode data from an older tool commit (`8b1b4a8`), kept apart because its labels collide with the campaign's | |
| `_manifests/vcf-bench-{1,2}_manifest__campaign1.json` | pre-release | File counts, byte totals and tarball SHA-256 of the pre-release campaign's pull from each host | |
| `_manifests/vcf-bench-{1,2}_manifest.json` | | The same for the pulls of 2026-09-24 and 2026-09-25, which brought the v3.1.0 campaign together with every other tree above; their totals count both | |
| `summary.json` | | `main`'s integration of every tree above and the campaign, before the move: 382 cells, each classified by branch (`live`, `prerelease`, `superseded`, `stalled`, `calibration`, `archive`) | |

## Experiments outside the base campaign (14-17)

The paper reports these from the v3.3.1 rerun, in `vcf-bench-*/v331-rerun/` on `main`.

| Path | Kind | What it is | Cited in the supplement for |
| --- | --- | --- | --- |
| `vcf-bench-1/benchmarks_outputs/14_regional_access/` | pre-release | Regional retrieval on development commit `3da1a5a` | |
| `vcf-bench-3/benchmarks_outputs/16_scale_retrieval/` | pre-release | Large-graph retrieval on the pre-release runners `245fe1f` and `5ed75c8`, on the same v3.1.0 graphs. QLever: 634.6 s after an 868.0 s index build on the complete VCF | |
| `vcf-bench-3/benchmarks_outputs/16_scale_retrieval__failed_before_memory_fixes/` | failed | The COTTAS cell, SIGKILLed at 32.2 GB RSS because the shape gate measured the packaged artifact, not the graph; and the HDT cell, whose endpoint ran out of JavaScript heap with about 25 GB free | Shape memory guards; Comunica heap limits (defects table) |
| `vcf-bench-1/use-case/17_use_case_acmg/` | pre-release | Arm 1, five gene-span slices, image `ecrum19/vcf-rdfizer:3.2.0` with a development linker tree; includes the live MyVariant.info run of 2026-09-28 | The 21 MyVariant.info responses recorded on 2026-09-28, which the v3.3.1 rerun replays (Builds). The responses themselves are published on `main` in `benchmarks/use_case/acmg/myvariant-cache/` |
| `vcf-bench-1/use-case/17_use_case_acmg__v3.3.1/` | pre-release | Arm 1's link-to-compare stages again on the v3.3.1 checkout, after Arm 4 exposed the spanning-deletion gap ([README](vcf-bench-1/use-case/17_use_case_acmg__v3.3.1/README.md)) | |
| `vcf-bench-1/use-case/17_use_case_acmg__cohort/` | pre-release | Arm 2, 104 participants | Pre-release release views took 20-27 min per requester, against 59-81 s in v3.3.1 (Stage costs) |
| `vcf-bench-1/use-case/17_use_case_acmg__cohort__failed_panel_info_disk/` | failed | An earlier Arm 2 attempt from an uncommitted development tree (`tool_source.txt`), set aside before the run above | |
| `vcf-bench-2/use-case/17_use_case_acmg__wgs/` | pre-release | Arm 3, the complete HG005 VCF | |
| `vcf-bench-3/use-case/17_use_case_acmg__layered/` | pre-release | Arm 4 on a v3.3.1 pre-release tree; the same counts as the reported rerun ([README](vcf-bench-3/use-case/17_use_case_acmg__layered/README.md)) | |
| `vcf-bench-3/use-case/17_use_case_acmg__layered__v3.3.0/`, `__layered__smoke_v3.3.0/` | superseded | Arm 4 on v3.3.0, whose gene linker skipped spanning-deletion (`*`) records ([README](vcf-bench-3/use-case/17_use_case_acmg__layered__v3.3.0/README.md)) | Gene links for non-explicit alleles: v3.3.0 skipped spanning-deletion records (defects table) |

## Validation runs on vcf-bench-2 (`review-runs/`)

`main` keeps `review-runs/mutation__{none,core}/` (the default-profile mutation
rerun), its driver `review_runs.sh` and the run log `review-runs.log`. The
driver and log are copied here as well, because they also cover the first
validation run below. The README beside them is `main`'s, as it stood before the move.

| Path | Kind | What it is | Cited in the supplement for |
| --- | --- | --- | --- |
| `review-runs/validate__NG131FQA1I__first250000/` | failed | The consumer WGS validation run on v3.1.0 with the default shapes: the host ran out of memory | Shape memory guards: a 58.2M-triple graph admitted by its 63.8 MB VCF size (defects table) |
| `review-runs/validate__NG131FQA1I__first250000__noshacl/` | superseded | The same on v3.1.0 without shapes: 10 of 13 answers equal; Q9 and Q10 differ on phase sets and Q11 on QUAL's lexical form | "A v3.1.0 run first reported three discrepancies" (Validation); Consumer WGS oracle (defects table) |
| `review-runs/diag_q11*.py`, `diag_q11*.out` | | Direct comparison of graph literals with the VCF text, and the canonical-QUAL digest check | "Direct field comparison found no conversion differences, and canonicalizing QUAL reproduced the graph-side digest" (Validation) |
| `review-runs/validate__NG131FQA1I__first250000__fixes/`, `__fixes_b500k/`, `e2e_*`, `validate_noshacl.sh`, `*driver.log` | pre-release | The validator fixes on development builds; `__fixes_b500k` is the first pass, before v3.3.1 was published | |
| `review-runs/shacl-mem/` | not reported | pyshacl peak memory and time for one and four shape batches (about 2.4 GB and 300 s per million triples), the basis of the batch default | |

## Failed attempts within the v3.3.1 rerun

| Path | What it is |
| --- | --- |
| `vcf-bench-2/v331-rerun/attempt1-arm4-resume-diskfull/` | Arm 4's first resume, which filled the disk while indexing the first view |
| `vcf-bench-2/v331-rerun/attempt2-arm4-resume-stopped/` | Arm 4's second resume, stopped at the start of govern to clear more space |
| `vcf-bench-3/v331-rerun/attempt1-exit126/` | The first start of large-graph retrieval, which exited because the script was not executable |

`main`'s `v331-rerun/README.md` on each host describes how each job ran.

## Reading a file

Browse this branch on GitHub, or, without changing a checkout:

```bash
git fetch origin legacy
git show origin/legacy:benchmark-results/vcf-bench-2/benchmarks_outputs__stalled/<path>
```
