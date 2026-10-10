# Benchmark results

The run records behind every number in the BioMedSem 2026 manuscript and its
supplement, from the three benchmark hosts. A run record is everything a run
writes except the data it generates:
- its command, tool commit and image digest;
- its exit status, timings and resource samples;
- its logs, comparisons and validation reports.

**Only the runs whose results the manuscript reports are here.** Pre-release,
superseded, stalled and failed runs are on the repository's
[`legacy` branch](https://github.com/ecrum19/vcf-rdfizer-testing/tree/legacy/benchmark-results),
at the same paths. That includes those the supplement cites as evidence of the defects the reported
runs corrected. Its README says what each one is and which statement cites it.

The generated RDF and the input VCFs are not here either; see [What is not here](#what-is-not-here).

## Where each reported result comes from

Figure and table numbers are the manuscript's (main text) and the supplement's
(prefix S). [`benchmarks/README.md`](../benchmarks/README.md) describes the
script behind each.

| Manuscript result | Release | Records |
| --- | --- | --- |
| Base campaign: fidelity and validation, record and sample scaling, storage, corpus breadth, configuration coverage, query cost (Figures 3, 6, S4–S7; Tables S6, S12, S14–S15) | v3.1.0 | `vcf-bench-1/benchmarks_outputs/`, `vcf-bench-2/benchmarks_outputs/`; integrated in `summary.json` |
| Default-profile mutation rerun (Figure 3b) | v3.1.0 | `vcf-bench-2/review-runs/` ([README](vcf-bench-2/review-runs/README.md)) |
| Minimal RDF setup and the repeated-question crossover (Figure 6a) | v3.1.0 | `vcf-bench-2/nt-only/` ([README](vcf-bench-2/nt-only/README.md)) |
| Consumer WGS validation run (Figure 3a; Section S4.2) | v3.3.1 | `vcf-bench-2/v331-rerun/results/consumer_wgs__NG131FQA1I__first250000/` |
| Linked workflow, Scenarios 1–2, with the MyVariant.info tier (Figures 4, S3; Tables S7–S11) | v3.3.1 | `vcf-bench-1/v331-rerun/results/17_use_case_acmg/`, `…__cohort/` ([README](vcf-bench-1/v331-rerun/README.md)) |
| Linked workflow, Scenarios 3–4 (Figures 4, S3; Tables S7–S11) | v3.3.1 | `vcf-bench-2/v331-rerun/results/17_use_case_acmg__wgs/`, `…__layered/` ([README](vcf-bench-2/v331-rerun/README.md)) |
| Regional retrieval (Figures 6c, S8a–b; Table S18) | v3.3.1 | `vcf-bench-1/v331-rerun/results/14_regional_access/` |
| Large-graph retrieval (Figure 3a; Table S17) | v3.3.1 on v3.1.0 graphs | `vcf-bench-3/v331-rerun/results/16_scale_retrieval/`; the graphs' builds in `vcf-bench-3/benchmarks_outputs/15_scale_prepare/` and their manifests in `vcf-bench-3/scale-store-manifests/` ([README](vcf-bench-3/README.md)) |
| Release conversion check: both releases write the same graph (Section S6.2) | v3.1.0, v3.3.1 | `vcf-bench-2/v331-rerun/bridge/` |
| Shared-input converter comparison (Figure 5; Section S2; Tables S2–S3) | v3.3.1 | `vcf-bench-1/18_converter_comparison/` ([README](vcf-bench-1/18_converter_comparison/README.md)) |

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
vcf-bench-1/                       the base campaign's first host
  benchmarks_outputs/              experiments 00, 01, 04, 07-13 of the v3.1.0 campaign
  sites-only-rerun/                the driver and log of 09's sites-only cell, rerun with a conformant fixture (v3.1.0)
  v331-rerun/                      the v3.3.1 rerun: Scenarios 1-2, the MyVariant.info tier, regional retrieval
  18_converter_comparison/         experiment 18
vcf-bench-2/                       the base campaign's second host
  benchmarks_outputs/              experiments 00, 03, 05, 06 of the v3.1.0 campaign
  review-runs/                     the default-profile mutation rerun (v3.1.0)
  nt-only/                         the N-Triples-only rerun (v3.1.0)
  v331-rerun/                      the v3.3.1 rerun: Scenarios 3-4, the consumer WGS validation run, the release check
vcf-bench-3/                       the large-graph host
  benchmarks_outputs/              experiment 15: the two large graphs, built with v3.1.0
  scale-store-manifests/           those graphs' manifests
  v331-rerun/                      the v3.3.1 rerun: large-graph retrieval
summary.json                       the base campaign, integrated (below)
input-checksums.tsv                the source VCFs' SHA-256
vcf-input-sizes.json               the source VCFs' sizes
```

A directory is named after the one it was copied from on its host, so each
record can be matched with the host's logs.

Every cell holds:
- `bench.json`: experiment, cell, exit status, wall time, host, tool commit and
  image digest;
- `command.txt` and `command.json`;
- `stdout.log`, `stderr.log`, and `workspace_bytes.tsv`;
- its own `out/` tree, without the generated RDF.

## summary.json

[`scripts/build_run_summary.py`](../scripts/build_run_summary.py) integrates the
base campaign's cells (experiments 00–13 in the `benchmarks_outputs` trees) into
one record:
- one record per cell (143), each tagged with its host, experiment, tool commit
  and resolved image digest;
- per-experiment roll-ups;
- host provenance;
- an integrity block.

Of the 143 cells, 137 are OK, 1 recorded (the truncated gzip's intended refusal),
2 refused as required, and 3 skipped by a stated guard (Table S12).

```bash
python3 scripts/build_run_summary.py benchmark-results \
    --output benchmark-results/summary.json
```

It exits non-zero if any experiment spans two hosts, which would confound that
experiment's internal comparison.

## Before citing a number

**Cite the image digest, not the tag.** Two hosts that build the same local tag
independently get different images. `summary.json` resolves every cell's tag to
the digest its host recorded.

**One base-campaign cell is a later rerun.** `09_awkward_inputs/awkward_sites_only`
ran again on 2026-10-10, on the same host with the same image and arguments,
because the campaign's sites-only fixture was malformed and its paired
validation could not run. It now converts and passes, which brings the campaign to
78 of 78 completed validations and 1,006 equal query comparisons
([`vcf-bench-1/sites-only-rerun/`](vcf-bench-1/sites-only-rerun/README.md)). The
first run is on `legacy`.

**A non-zero exit is not always a failure.**
- `06` asserts two refusals: `--hdt-strategy single` beside COTTAS, and beside a
  gzip aggregate.
- `09` runs awkward fixtures, where a refusal is a valid outcome.
- `bench.json` carries an `assertion` field (`ok`, `refusal` or `recorded`), and
  `summary.json` classifies on it.
- For cells recorded before that field existed, `build_run_summary.py` recovers
  the assertion from the scripts' documented behaviour.

**`06_equivalence` queries COTTAS through DuckDB.** It uses the
`@elias.crum/query-sparql-cottas` endpoint (DuckDB over the Parquet, behind the
same endpoint the other engines use). It finishes the condensed encoding's
`q05_sample_genotype_counts` in 99.8 min; the experiment takes 8.98 h, and all four
engines agree on every artifact. The two earlier runs through pycottas' rdflib
Store did not finish that query (supplement, defects table) and are on `legacy`.

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
- **Runs the manuscript does not report:** on the
  [`legacy` branch](https://github.com/ecrum19/vcf-rdfizer-testing/tree/legacy/benchmark-results)
  (see above and [`LEGACY.md`](../LEGACY.md)).
