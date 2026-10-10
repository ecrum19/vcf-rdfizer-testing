# Benchmark results

The run records behind every number in the BioMedSem 2026 manuscript and its
supplement, from the three benchmark hosts. A run record is everything a run
writes except the data it generates:
- its command, tool commit and image digest;
- its exit status, timings and resource samples;
- its logs, comparisons and validation reports.

The generated RDF and the input VCFs are not here; see [What is not here](#what-is-not-here).

## Where each reported result comes from

| Manuscript result | Release | Records |
| --- | --- | --- |
| Base campaign: fidelity and validation (RQ1), record and sample scaling, storage, corpus breadth, configuration coverage, query cost (Figures 3, 6, S4–S7) | v3.1.0 | `vcf-bench-1/benchmarks_outputs/`, `vcf-bench-2/benchmarks_outputs/`; integrated in `summary.json` |
| Default-profile mutation rerun (Figure 3b) | v3.1.0 | `vcf-bench-2/review-runs/mutation__*` ([README](vcf-bench-2/review-runs/README.md)) |
| Consumer WGS validation run (Figure 3a) | v3.3.1 | `vcf-bench-2/v331-rerun/results/consumer_wgs__NG131FQA1I__first250000/` |
| Minimal RDF setup and the repeated-question crossover (Figure 6a) | v3.1.0 | `vcf-bench-2/nt-only/` ([README](vcf-bench-2/nt-only/README.md)) |
| Linked workflow, Arms 1–3, record comparison, stage costs (Figures 4, S3) | v3.3.1 | `vcf-bench-1/v331-rerun/results/17_use_case_acmg/`, `…__cohort/`; `vcf-bench-2/v331-rerun/results/17_use_case_acmg__wgs/` |
| Linked workflow, Arm 4 (Figures 4, S3) | v3.3.1 | `vcf-bench-2/v331-rerun/results/17_use_case_acmg__layered/` ([README](vcf-bench-2/v331-rerun/README.md)) |
| MyVariant.info tier | v3.3.1 | `vcf-bench-1/v331-rerun/results/17_use_case_acmg/link_myvariant__*`, `tier1_vs_tier3_myvariant.json` |
| Regional retrieval (Figures 6c, S8; Table S18) | v3.3.1 | `vcf-bench-1/v331-rerun/results/14_regional_access/` |
| Large-graph retrieval (Figure 3a; Table S17) | v3.3.1 on v3.1.0 graphs | `vcf-bench-3/v331-rerun/results/16_scale_retrieval/`; the graphs' manifests in `vcf-bench-3/scale-store-manifests/` ([README](vcf-bench-3/README.md)) |
| Release conversion check (both releases write the same graph) | v3.1.0, v3.3.1 | `vcf-bench-2/v331-rerun/bridge/` |
| Shared-input converter comparison (Figure 5, Section S2) | v3.3.1 | `vcf-bench-1/18_converter_comparison/` ([README](vcf-bench-1/18_converter_comparison/README.md)) |

Images:
- v3.1.0 is `ecrum19/vcf-rdfizer@sha256:1904e96dde12ab2e2e70d8ee1267765c293ab100a8bd1b14d5b009b2bf8e34aa`
  (commit `d3b34d5`).
- v3.3.1 is `ecrum19/vcf-rdfizer@sha256:3ad71b1a54612142e3be43b24e7e4a38551949cb641f4421bcae9bf051102993`
  (commit `b25fb7b`).

Every v3.3.1 result outside the converter comparison comes from one rerun of
whatever a pre-release build first produced. Each host's `v331-rerun/README.md`
gives that host's jobs and results.

## Layout

```
vcf-bench-1/ vcf-bench-2/ vcf-bench-3/   one directory per host
  benchmarks_outputs/                    the v3.1.0 base campaign (bench-1, bench-2); large-graph
                                         retrieval's first runs (bench-3)
  benchmarks_outputs_calibration/        the calibration cell both campaign hosts ran
  v331-rerun/                            the v3.3.1 rerun: driver, logs, results/
  use-case/                              the linked workflow's pre-release runs
  review-runs/, nt-only/ (bench-2)       the additional validation runs, and the N-Triples-only rerun
  18_converter_comparison/ (bench-1)     experiment 18
  scale-store-manifests/ (bench-3)       the large graphs' manifests
  benchmarks_outputs__campaign1__<ts>/   the pre-release campaign, set aside when the suite
                                         was rerun on v3.1.0 (with its calibration)
  benchmarks_outputs__superseded/        runs replaced by a later rerun
  benchmarks_outputs__stalled/           runs stopped because they could not finish
  benchmarks_outputs__offsplit/          experiments started on the host that did not own them
  benchmarks_outputs__partial/           cells interrupted before bench.json was written
  benchmarks_outputs__tool8b1b4a8/       an older tool's storage-mode data
_manifests/                              file counts, byte totals and SHA-256 per host
summary.json                             the base campaign, integrated (below)
input-checksums.tsv, vcf-input-sizes.json   the source VCFs' SHA-256 and sizes
```

Every cell holds:
- `bench.json`: experiment, cell, exit status, wall time, host, tool commit and
  image digest;
- `command.txt` and `command.json`;
- `stdout.log`, `stderr.log`, and `workspace_bytes.tsv`;
- its own `out/` tree, without the generated RDF.

**Superseded and failed runs are kept** beside the reported ones. Their names say
what they are (`__superseded`, `__stalled`, `__failed_*`, `__before_*`, the
pre-release `use-case/` arms and `v3.3.0` Arm 4). They are the evidence for the
supplement's account of defects and corrections, so removing them would break
the paper's evidence trail. Each such directory's README, or the README beside
it, says why it exists.

## summary.json

[`scripts/build_run_summary.py`](../scripts/build_run_summary.py) integrates
the base campaign hosts' trees into one record:
- one record per cell (382), each tagged with its host, branch, experiment, tool
  commit and resolved image digest;
- per-experiment roll-ups;
- host provenance;
- an integrity block.

Its live branch is the 143 cells the paper reports: 136 OK, 2 recorded,
2 refused as required, and 3 skipped by a stated guard.

```bash
python3 scripts/build_run_summary.py benchmark-results \
    --output benchmark-results/summary.json
```

It exits non-zero if any experiment spans two hosts, which would confound that
experiment's internal comparison.

## Before citing a number

**Cite the image digest, not the tag.** In the pre-release campaign, both hosts
tagged an image `vcf-rdfizer:local-025fb7d` but built it independently, so the
tag names different bits on each: `b645120b…` on bench-1, `0082fe2c…` on bench-2.
`summary.json` resolves every cell's tag to the digest for its host.

**A non-zero exit is not always a failure.**
- `06` asserts that two configurations are refused: `--hdt-strategy single`
  beside COTTAS, and beside a gzip aggregate.
- `09` runs awkward fixtures, where a refusal is a valid outcome.
- `bench.json` carries an `assertion` field (`ok`, `refusal` or `recorded`), and
  `summary.json` classifies on it.
- For cells recorded before that field existed, `build_run_summary.py` recovers
  the assertion from the scripts' documented behaviour.

**`06_equivalence` was hard-won.**
- **Two runs were stopped.** COTTAS, queried through pycottas' rdflib Store, did
  not finish `q05_sample_genotype_counts` on the condensed encoding, after 41 h and
  then 10 h. Both runs are kept under `__stalled/` with their container logs,
  because the contrast is the result.
- **The DuckDB endpoint finished it.** Querying through
  `@elias.crum/query-sparql-cottas` instead (DuckDB over the Parquet, behind the
  same endpoint the other engines use) finishes that cell in 99.8 min.
- **All engines agree.** The whole experiment takes 8.98 h, with all four
  engines agreeing on every artifact.

## What is not here

- **The generated RDF:** about 196 GB of `.nt`, `.hdt` and `.cottas` from the
  campaign, plus the later experiments' graphs and release views. Every cell
  records the command, commit and image digest that produced it, so any artifact
  can be rebuilt; the large-graph manifests record the SHA-256 of every artifact.
- **Large files of the v3.3.1 rerun:** its graphs, derived VCFs, per-record
  decision logs and any file over 5 MB. Each host's `v331-rerun/excluded-files.tsv`
  lists them with size and SHA-256.
- **The source VCFs.** They are downloaded from their providers (repository
  README, Datasets), and `input-checksums.tsv` gives their SHA-256.
