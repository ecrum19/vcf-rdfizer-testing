# Benchmark harness

The experiments behind the BioMedSem 2026 manuscript, one script per experiment.
Each script writes one directory per *cell* (one configuration of one
experiment), and every cell records its command, host, tool commit, image
digest, exit status and timings. The cells the manuscript reports are archived,
without the generated RDF, in [`../benchmark-results/`](../benchmark-results/README.md).

- [Experiments](#experiments): what each script measures, the result it produced, and where its records are
- [Runs made outside these scripts](#runs-made-outside-these-scripts)
- [Supporting code](#supporting-code)
- [Running the harness](#running-the-harness)
- [Reading the outputs](#reading-the-outputs)

[`DESIGN.md`](DESIGN.md) is the plan written before the campaign. The scripts'
comments cite its sections as "Plan §". It explains why each experiment is
shaped as it is; this file describes what ran.

## Experiments

Figure and table numbers are the manuscript's (main text) and the supplement's
(prefix S). Records are under `benchmark-results/`; `b1`, `b2` and `b3` are the
hosts `vcf-bench-1`, `-2` and `-3`.

### Base campaign: `00`–`13`, VCF-RDFizer v3.1.0

143 cells in 12 experiment families (Table S12). `00` and `02` prepare the
others and are not counted. Every family ran whole on one host.

| Script | What it measures | Reported in | Records |
| --- | --- | --- | --- |
| `00_environment.sh` | Host, Docker and image manifest; resolves the image tag to its digest | Sections S6.2–S6.3 | `b1`, `b2`: `benchmarks_outputs/00_environment/` |
| `02_derive_ladders.sh` | Builds the derived inputs with awk: the sample ladder (10,000 records of the 1000 Genomes chr20 call set at 1–2,504 samples) and the record ladder (HG005 prefixes of 10,000, 100,000 and 1,000,000 records) | Inputs to `01`, `03`, `04`, `10`, `13` | (inputs, not cells) |
| `01_storage_mode.sh` | Plain against space-optimized storage: peak workspace and time, on 100,000 HG005 records (3 replicates) and a 269M-triple test file (once each) | Section 3.3; Figure S4f | `b1/benchmarks_outputs/01_storage_mode/` |
| `03_sample_representation.sh` | Condensed against expanded samples across the sample ladder, with timing replicates and a single- and a multi-sample anchor | Section 3.3; Figure S5 | `b2/benchmarks_outputs/03_sample_representation/` |
| `04_scaling_records.sh` | Cost against record count on the record ladder (3 replicates) and the complete HG005 VCF (once); the only place record-scaling exponents are fitted | Section 3.3; Figure S4a–e; Section S9.1 | `b1/benchmarks_outputs/04_scaling_records/` |
| `05_corpus_breadth.sh` | HDT and COTTAS construction on the first 250,000 records of eight public VCFs and on the complete HG005 VCF | Section 3.3; Figure S6; Table S14 | `b2/benchmarks_outputs/05_corpus_breadth/` |
| `06_equivalence.sh` | The thirteen source-comparison queries on a 10,000-line fixture, in both storage modes and sample profiles, on four SPARQL engines over three RDF artifacts and two HDT strategies, plus two required refusals | Section 3.1; Section S10 | `b2/benchmarks_outputs/06_equivalence/` |
| `07_representation_axes.sh` | Raw against structured INFO, basic against structured headers, and fixtures declaring VCF 4.1–4.5 or no version | Sections S7, S10 | `b1/benchmarks_outputs/07_representation_axes/` |
| `08_robustness.sh` | Determinism (two identical conversions), a compress–decompress round trip, index idempotence, and the 113-fault mutation score with the default and all shape profiles | Section 3.1; Figure 3b; Table S6 | `b1/benchmarks_outputs/08_robustness/` |
| `09_awkward_inputs.sh` | Eleven difficult fixtures, a conversion with the three demonstration linkers, and a custom-mapping cell. The sites-only cell is a rerun with the corrected fixture (below) | Section S7; Table S15 | `b1/benchmarks_outputs/09_awkward_inputs/` |
| `10_feasibility.sh` | One million HG005 records under three configurations, each with memory ceilings of 8, 16 and 31 GB | Section S10 | `b1/benchmarks_outputs/10_feasibility/` |
| `11_covering_set.sh` | Ten configuration rows on a 1,000-line fixture covering every value and every pair of values of seven options, each validated with shapes | Section S10 | `b1/benchmarks_outputs/11_covering_set/` |
| `12_modes_smoke.sh` | Each operating mode on its own: TSV, conversion, validation, compression, decompression, HDT and COTTAS indexing | Section S10 | `b1/benchmarks_outputs/12_modes_smoke/` |
| `13_query_cost.sh` | SPARQL against the cyvcf2 parser on identical work: the thirteen queries on the fixture (0.96M triples) and on 100,000 HG005 records (17.1M triples), 3 replicates | Section 3.3; Figures 6a, 6d, S7, S8c; Section S9.4 | `b1/benchmarks_outputs/13_query_cost/` |

`scripts/build_run_summary.py` integrates these cells into
`benchmark-results/summary.json`, and refuses an archive in which a family spans
two hosts.

### Later experiments: `14`–`18`, VCF-RDFizer v3.3.1

These are outside `run_all.sh` and its profiles; each is run by name. The
reported runs of `14`, `16` and `17` come from one rerun with v3.3.1, driven by
`run_v331.sh`, whose copy, logs and results are in each host's `v331-rerun/`.

| Script | What it measures | Reported in | Records |
| --- | --- | --- | --- |
| `14_regional_access.sh` | Region-restricted questions from 1 kb to 10 Mb: QLever on `13_query_cost`'s graphs, against tabix-indexed cyvcf2 and bcftools; 11,160 executions | Section 3.3; Figures 6c, S8a–b; Table S18 | `b1/v331-rerun/results/14_regional_access/` |
| `15_scale_prepare.sh` | Builds the large graphs once, with the published v3.1.0 image: 1,000,000 HG005 records (170.9M triples) and the complete VCF (657.4M), each with a manifest of every artifact's size and SHA-256 | The graphs that `16` queries | `b3/benchmarks_outputs/15_scale_prepare/`, `b3/scale-store-manifests/` |
| `16_scale_retrieval.sh` | The thirteen questions on those graphs: QLever from N-Triples, HDT and COTTAS, and the native HDT and COTTAS engines | Figure 3a; Table S17 | `b3/v331-rerun/results/16_scale_retrieval/` |
| `17_use_case_acmg.sh` | The linked workflow: carriers of ClinVar-classified variants in the 81 ACMG SF v3.2 genes, with simulated consent, by an RDF route and a bcftools baseline that must agree. Arm 1: five gene-span slices; Arm 2: 104 1000 Genomes participants; Arm 3: the complete HG005 VCF; Arm 4: the complete NB72462M VCF under layered consent. See [`use_case/acmg/README.md`](use_case/acmg/README.md) | Section 3.2; Figures 4, S3; Tables S7–S11 | `b1/v331-rerun/results/17_use_case_acmg/` (Arm 1, with the MyVariant.info tier) and `…__cohort/` (Arm 2); `b2/v331-rerun/results/17_use_case_acmg__wgs/` (Arm 3) and `…__layered/` (Arm 4) |
| `18_converter_comparison.sh` | JVarkit, TogoVar, SPARQLing Genomics, BioInterchange and VCF-RDFizer on two shared inputs, in pinned containers, with questions Q1–Q8 ported to each vocabulary and compared with the same source-derived oracle. See [`converters/README.md`](converters/README.md) | Section 3.3; Figure 5; Section S2; Tables S2–S3 | `b1/18_converter_comparison/` |

`15` and `16` are two halves of one experiment. `13` reconverts its input on
every replicate, which is affordable at 17.1M triples but not at 657M: three
replicates would spend about 48 h rebuilding the same graph. So `15` builds each
graph once into a store outside the results tree, and `16` only reads it,
refusing a scale that has not been built. Generation pins the published image so
that a stored graph traces to a release; querying may use a newer image, which
changes retrieval cost but not the graph.

## Runs made outside these scripts

Five reported results came from small drivers that call the tool, or one cell of
an experiment, directly. Each driver is archived with its records.

| Result | Driver | Records |
| --- | --- | --- |
| Default-profile mutation rerun (Figure 3b) | `review_runs.sh` | `b2/review-runs/` |
| Minimal RDF setup and the repeated-question crossover: `13_query_cost`'s large input converted to N-Triples only (Figure 6a) | `run_nt_only.sh` | `b2/nt-only/` |
| Consumer WGS validation run: the first 250,000 NG131FQA1I records, validated on QLever with batched default shapes (Figure 3a; Section S4.2) | `run_v331.sh`, job `consumer_wgs` | `b2/v331-rerun/results/consumer_wgs__NG131FQA1I__first250000/` |
| Release conversion check: v3.3.1 and v3.1.0 write the same sorted triples for 100,000 HG005 records (Section S6.2) | `run_v331.sh`, job `bridge` | `b2/v331-rerun/bridge/` |
| `09`'s sites-only cell, rerun on 2026-10-10 because the campaign's fixture declared a FORMAT column without samples and its paired validation could not run (Section S7; Table S15) | `rerun_sites_only.sh`: `bm_run` with `09`'s arguments, v3.1.0 | `b1/benchmarks_outputs/09_awkward_inputs/awkward_sites_only/`; driver and log in `b1/sites-only-rerun/` |

## Supporting code

| Path | What it does |
| --- | --- |
| `run_all.sh` | Runs `00`–`13` in order, one at a time, under a profile (below) |
| `lib/common.sh` | Shared shell helpers: resolving the tool and image, running a cell into a fresh directory with its `bench.json`, sampling workspace bytes, recording assertions, finding inputs, and the cohort-scale guard |
| `lib/scale.sh` | The scale store's layout and manifests, shared by `15` and `16` |
| `lib/make_fixtures.py` | Builds the small fixtures in `fixtures/` |
| `fixtures/` | The difficult-input and VCF-version fixtures of `07` and `09`; [`FIXTURES.json`](fixtures/FIXTURES.json) records how each was made |
| `analysis/collect_metrics.py` | Collects one experiment's cells into `tidy.csv` and `tidy.json` |
| `analysis/datasets.py` | Joins collected cells into one dataset per question: corpus, equivalence, awkward inputs, feasibility, coverage, query cost, regional access |
| `analysis/compare_graphs.py` | Compares two graphs by their sorted triple set, not their bytes (used by `08`) |
| `analysis/describe_inputs.py` | Structural descriptors of the input VCFs: records, samples, variant classes |
| `analysis/equivalence.py` | Decides an equivalence claim from paired runs against a stated margin (`01`, `03`) |
| `analysis/fit_scaling.py` | Fits scaling exponents on a log-log axis, only on the derived ladders (`03`, `04`) |
| `analysis/stats.py` | The shared statistics, numpy only: a bootstrap interval on a paired ratio, and a log-log slope with its interval |
| `analysis/provenance.py` | Resolves each host's image tags to digests (`02`, `14`, `15`) |
| `analysis/scale_store.py` | Lists the scale store and re-hashes it against its manifests |
| `analysis/scale_retrieval.py` | Turns `16`'s cells into `retrieval.csv` and `retrieval-raw.json` |
| `use_case/acmg/` | Experiment 17's definitions, policies, queries, baseline, comparison and tests; [README](use_case/acmg/README.md) |
| `converters/` | Experiment 18's containers, query ports, normalization and summary; [README](converters/README.md) |

The figures and the results site do not use `analysis/`. They read the cells
directly, through `scripts/figure_data.py` and `scripts/build_site_data.py`.

## Running the harness

### Setup

```bash
bash ../scripts/download_test_data.sh        # the input VCFs (about 2.3 GB)
export VCF_RDFIZER=/path/to/vcf_rdfizer.py   # only if the tool is not a sibling checkout
python3 -m pip install numpy rdflib          # rdflib: linking and the mutation score
```

Docker is required; `bcftools` is not, because the derived inputs are built with
awk. By default the harness builds an image from the tool checkout, tags it
`vcf-rdfizer:local-<commit>`, and runs every cell with `--no-build`. To use the
published releases instead, as the reported runs did:

```bash
export BM_IMAGE_VERSION=3.1.0     # the base campaign (00-13), and 15
export BM_IMAGE_VERSION=3.3.1     # 14, 16, 17 and 18
```

A dirty checkout gets a `-dirty` tag and a warning. Commit before a run you
intend to report.

### Run

```bash
./run_all.sh biomedsem              # the manuscript configuration of 00-13
./run_all.sh biomedsem 03 05 06     # part of it, e.g. one host's share
./run_all.sh smoke                  # does everything still run? (not measurements)
./run_all.sh 03 06                  # selected experiments at their defaults
BM_IMAGE_VERSION=3.3.1 BM_ACMG_ARM=arm1 ./17_use_case_acmg.sh
```

Run `00_environment.sh` first, once per session, and run one experiment at a
time: two concurrent runs invalidate every timing and memory number. Detach long
runs (`systemd-run --user --scope`, or `nohup`); Ctrl-C on the wrapper leaves its
container running.

**The `biomedsem` profile** sets the defaults the base campaign used; an
explicit environment variable still wins. It:
- runs three replicates at the cheapest size and the larger sizes once
  (`BM_REPS=3`, `BM_REPS_AT_SCALE=1`);
- truncates each corpus file to its first 250,000 records, keeping the header
  (`BM_CORPUS_MAX_RECORDS`), with one file converted whole (`BM_CORPUS_WHOLE`; the
  campaign set `HG005_GRCh38.vcf.gz`);
- uses the 1,000,000-record HG005 rung for feasibility, and the 100,000-record rung
  for robustness, INFO and header costs, and query cost;
- validates on all four SPARQL engines in `06` (`BM_EQUIV_ENGINES=all`) and on
  Comunica in `09`, `11` and `12` (`BM_VALIDATION_ENGINES=comunica`). `13` runs
  every engine on the fixture and QLever on the 100,000-record input
  (`BM_QUERY_ENGINES`, `BM_QUERY_LARGE_ENGINES`).

**The `smoke` profile** shrinks every input to a fixture and runs one replicate on
one engine. It checks that the scripts and the analysis still run; its timings are
not measurements.

**The cohort-scale guard.** The expanded sample profile emits a resource per sample
per record. The 1000 Genomes chr20 call set (1,812,841 records, 2,504 samples)
reached 23 GB after 1.1% of its records, about 2.1 TB in full.
`bm_skip_if_cohort_scale` therefore skips an expanded cell whose input has more
than `BM_CORPUS_MAX_SAMPLES` (default 1,000) sample columns, and records the skip
as a result. It applies in `03` and `05`; condensed cells still run.

### The large-graph store

```bash
BM_IMAGE_VERSION=3.1.0 ./15_scale_prepare.sh r1000000   # build once: about 4 h (the complete VCF: about 14 h)
./16_scale_retrieval.sh r1000000                        # query as often as needed
python3 analysis/scale_store.py verify                  # re-hash the store against its manifests
python3 analysis/scale_retrieval.py                     # -> results/16_*/retrieval.csv
```

Every axis of `16` is selectable; for example, one engine reading all three artifacts:

```bash
BM_SCALE_CELLS="qlever:nt.gz qlever:hdt qlever:cottas" ./16_scale_retrieval.sh whole
```

### Collect

```bash
python3 analysis/collect_metrics.py --all          # -> results/<experiment>/tidy.{csv,json}
python3 analysis/datasets.py querycost 13_query_cost
python3 analysis/fit_scaling.py 03_sample_representation \
        --x samples --y triples --group mode --cell-filter __structure
```

### Layout

```
results/<experiment>/<cell>/    bench.json, command.txt, command.json, stdout.log, stderr.log,
                                workspace_bytes.tsv, out/ (the tool's own output tree)
results/<experiment>/tidy.csv   one row per cell
```

Each cell gets a fresh `--out`; rerunning a cell fails rather than overwrite it.
Move the cell, or set `BM_RESULTS` to a new root.

### Environment variables

`BM_RESULTS` results root · `BM_REPS` replicates · `BM_SIZES` storage-mode inputs ·
`BM_SAMPLE_RUNGS` / `BM_RECORD_RUNGS` ladder rungs · `BM_SAMPLE_REPRESENTATIONS` and
`BM_SAMPLE_PARTS` for `03` · `BM_VALIDATION_ENGINES` · `BM_SPARK_PARTITIONS` (default 8) ·
`BM_CEILINGS` memory ceilings for `10` · `BM_IMAGE_VERSION` a published release ·
`BM_REBUILD=1` force a rebuild · `BM_REGIONAL_SCALES`, `BM_REGIONAL_ARMS`,
`BM_REGIONAL_RDF_SMALL` / `_SLICE` / `_WHOLE` and `BM_REGIONAL_IMAGE` for `14` ·
`BM_WINDOW_SEED` · `BM_SCALE_STORE` (default `../scale_store`), `BM_SCALE_SET`,
`BM_SCALE_REPRS`, `BM_SCALE_CELLS`, `BM_SCALE_QUERIES` (`core`, `preflight` or `all`),
`BM_SCALE_NODE_HEAP_MB` and `BM_SCALE_ALLOW_LOCAL_IMAGE=1` for `15` and `16` ·
`BM_ACMG_ARM` (`arm1`, `cohort`, `wgs`, `layered`), `BM_ACMG_STAGES` and
`BM_MYVARIANT_CACHE` for `17` · `BM_ALLOW_NETWORK=1` with `BM_CONTACT_EMAIL` for a
live linker · `BM_CUSTOM_RULES` custom mapping · `BM_DRY_RUN=1` print commands
without running

## Reading the outputs

1. **Peak workspace, not final bytes.** Both storage modes write the same triples,
   so their final sizes match. `peak_host_out_tree_bytes` is the storage-mode
   result. The partitioned stage's Docker volume is a separate number
   (`peak_volume_workspace_bytes`); never add them.
2. **Never compare `.nt.gz` checksums.** Space-optimized storage writes a
   concatenated gzip stream; plain storage gzips one merged file. Compare sorted
   triple sets with `analysis/compare_graphs.py`.
3. **`--hdt-strategy single` works only with plain storage and HDT without
   COTTAS.** Anything else exits 2, and `06` asserts both refusals.
4. **The derived ladder files are not valid VCFs.** Sample columns are cut without
   recomputing INFO, so AC and AN disagree with the retained genotypes. INFO is a
   held-fixed control.
5. **A non-zero exit is not always a failure.** `bench.json` records an
   `assertion` (`ok`, `refusal` or `recorded`): `06`'s refusal cells must fail, and
   `09` records the refusal of an awkward input as a valid outcome.
6. **In `benchmark.csv`, compare with `oracle_query_seconds`, not
   `oracle_wall_seconds`.** The first is the parser's cost for that query; the
   second is its total for all queries, repeated on each row.
7. **A regional window means POS, not overlap.** A tabix seek returns every record
   whose span overlaps the region. Every VCF arm of `14` drops out-of-window POS
   after the seek, which makes it comparable with a SPARQL `?pos` filter.
8. **`16`'s default query set is the thirteen core queries.** A subset makes the
   tool report `TIMING_ONLY` instead of a validation verdict. Each selected query
   is still compared with the cyvcf2 oracle, and `answersAgree` in the cell's
   `summary.json` is the flag to check.
9. **Cite the image digest, not the tag.** Two hosts that build the same local tag
   independently get different images. Each host's
   `00_environment/provenance.*.json` records the digest, and `summary.json`
   resolves every cell's tag to it.
