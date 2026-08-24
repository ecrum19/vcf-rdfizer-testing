# Experimental plan for benchmarking VCF-RDFizer

## 1. Aim and scope

This benchmark evaluates the trade-off between compute cost and storage cost in
VCF-RDFizer. The design is staged so that expensive full-corpus runs are only
performed after the two implementation choices that affect the pipeline most
directly have been evaluated on a representative test fixture.

The study has three questions:

1. Does `--rdf-storage-mode space-optimized` reduce RDF storage substantially
   without materially changing conversion time or memory use relative to
   `plain`?
2. Is HDT generation more efficient with
   `--hdt-strategy partitioned` than with `single`, and how does the automatic
   `auto` choice compare?
3. Given the better storage mode and HDT strategy, which combinations of RDF
   representation and artifact compression provide the best time/space
   trade-off across the ten benchmark VCFs?

The spelling used by the current repository scripts is
`space-optimized`. If the pinned VCF-RDFizer release exposes the equivalent
mode as `space-efficient`, record that spelling in the run manifest and use it
consistently; do not treat the two spellings as separate experimental levels.

The option discussed as `----hdt-strategy` in the request is written correctly
in the commands below as `--hdt-strategy`.

## 2. Inputs

### 2.1 Ten benchmark VCFs

These are the ten corpus inputs. They are downloaded into `vcf_data/` using
[`scripts/download_test_data.sh`](scripts/download_test_data.sh) and are not
stored in Git because of their size.

| # | Canonical file | Approx. compressed size | Dataset/profile description |
|---:|---|---:|---|
| 1 | `NG1N86S6FC.vcf.gz` | 379 MB | Sequencing.com whole-genome VCF |
| 2 | `NG131FQA1I.vcf.gz` | 224 MB | Dante Labs VCF |
| 3 | `NB72462M.vcf.gz` | 341 MB | Nebula Genomics VCF |
| 4 | `60820188475559.vcf.gz` | 325 MB | Filtered SNP VCF |
| 5 | `60820188474283.vcf.gz` | 222 MB | Dante Labs whole-genome VCF |
| 6 | `0GOOR_HG002.vcf.gz` | 69 MB | Genome in a Bottle HG002 truth-challenge VCF |
| 7 | `1000G_phase3_chr20.vcf.gz` | 327 MB | 1000 Genomes Phase 3 chromosome 20; 2,504 samples; GRCh37 |
| 8 | `HGSVC2_freeze3_sv_alt.vcf.gz` | 31.5 MB | HGSVC2 structural-variant batch; 32 samples; GRCh38 |
| 9 | `HG004_GRCh38_1_22_v4.2.1_benchmark.vcf.gz` | 149 MB | Genome in a Bottle HG004 benchmark; single sample; GRCh38 |
| 10 | `HG005_GRCh38_1_22_v4.2.1_benchmark.vcf.gz` | 139 MB | Genome in a Bottle HG005 benchmark; single sample; GRCh38 |

The approximate sizes are descriptive metadata, not measured benchmark
results. Before running, record the exact byte size and SHA-256 checksum of
every input. The input file order must be fixed in the manifest, even though
run order may be randomized.

### 2.2 Auxiliary pilot fixture

Phases 1 and 2 use one additional, smaller fixture:

```text
VCF-RDFizer/test/test_vcf_files/test-larger.vcf
```

This fixture is used to make the storage-mode and HDT-strategy comparisons
efficient. It is not one of the ten corpus files and must be reported
separately in all tables and figures. If the checkout contains the compressed
variant `test-larger.vcf.gz` instead, use that file, record the substitution,
and report its checksum.

## 3. Experimental controls

Every run must record the following in a machine-readable manifest:

- VCF-RDFizer Git commit or package/container digest, including the exact
  command line;
- VCF-RDFizer and dependency versions, Docker image, Python, Java, and Spark
  versions;
- host CPU model and core count, RAM, operating system, filesystem, and
  available disk space;
- input path, input checksum, compressed and uncompressed input sizes, and
  VCF record count if available;
- Spark/RDF parallelism, including `--spark-partitions` and
  `--rdf-layout` values;
- run repetition number, start/end timestamps, exit status, and any failure or
  retry;
- whether the filesystem and operating-system page cache were cold or warm.

Use one otherwise idle machine, one pinned software environment, one storage
device, and one fixed parallelism setting for all comparisons. Do not run
different configurations concurrently. Use a fresh output directory for every
run so that an earlier artifact cannot be reused accidentally. Randomize the
order of paired configurations within each repetition to reduce bias from
thermal throttling, background load, and filesystem state. A warm-up run may be
performed, but it must be excluded from the reported statistics.

The suggested common controls, matching the repository's existing benchmark
commands, are:

```text
--mode full
--rdf-compression none
--spark-partitions 8
--rdf-layout batch
```

If a release does not support one of these flags, document the supported
equivalent and keep it unchanged for every treatment. `--rdf-compression`
should remain `none` in this study so that the effects of
`--representations` and `--artifact-compression` are not mixed with RDF
intermediate-file compression.

## 4. Measurements and derived quantities

Collect metrics separately for conversion and for every generated artifact.
At minimum, collect:

- wall-clock time in seconds;
- user CPU time and system CPU time;
- peak resident memory;
- exit code and success/failure reason;
- number of emitted RDF triples or records;
- final bytes for each output artifact;
- peak working-directory bytes, if the runner can observe temporary files.

For each artifact, calculate:

```text
size_ratio_input  = artifact_bytes / compressed_input_bytes
size_ratio_triples = artifact_bytes / emitted_triples
throughput        = emitted_triples / wall_seconds
```

For a complete pipeline, also report total wall time and total CPU time. Do
not add stage times if the tool's metrics indicate that stages overlap; use the
runner's measured end-to-end time in that case. Report both absolute values and
values normalized by input bytes, input records, or emitted triples.

The primary summary statistic is the median across successful repetitions,
with interquartile range (IQR). Report every individual repetition in an
appendix or machine-readable result file. Across the heterogeneous ten-file
corpus, report both:

- a macro summary: median of per-file normalized metrics; and
- a micro summary: total bytes and total seconds over all files.

This prevents the largest VCF from dominating the only summary while retaining
the practical cost of processing the full corpus.

## 5. Phase 1 — RDF storage mode

### Question and hypothesis

Compare `plain` with `space-optimized` on the same pilot VCF. The hypothesis is
that space-optimized storage materially reduces disk usage, while the median
conversion wall time, CPU time, and peak memory remain close to the plain-mode
baseline.

### Treatments

| Factor | Levels |
|---|---|
| Input | `test-larger.vcf` only |
| `--rdf-storage-mode` | `plain`, `space-optimized` |
| `--hdt-strategy` | `partitioned` (held fixed) |
| `--representations` | `hdt,cottas` (held fixed) |
| `--artifact-compression` | `none` (held fixed) |
| `--rdf-compression` | `none` (held fixed) |

Run each level at least three times (five is preferred if runtime permits),
with the two modes interleaved or randomized within each repetition. This is a
paired comparison: the input and all non-storage settings are identical.

A representative command is:

```bash
python3 VCF-RDFizer/vcf_rdfizer.py \
  --mode full \
  --input VCF-RDFizer/test/test_vcf_files/test-larger.vcf \
  --rdf-storage-mode plain \
  --rdf-compression none \
  --representations hdt,cottas \
  --artifact-compression none \
  --hdt-strategy partitioned \
  --out experiments/phase1/plain-r1 \
  --build
```

Repeat the command with `--rdf-storage-mode space-optimized` and a distinct
output directory for every repetition.

### Analysis and decision rule

Report the paired percentage change from plain mode to space-optimized mode for
wall time, CPU time, peak memory, final output bytes, and peak working bytes.
Use the storage mode for Phase 3 that is Pareto-preferred: select
space-optimized if it has lower median storage and no practically important
time penalty. A pre-specified operational rule is a storage reduction of at
least 10% with no more than a 5% increase in median wall time; otherwise select
the mode with the better observed time/space trade-off and explain the choice.

The conclusion must distinguish “no detectable/practically important compute
penalty” from “the two modes are exactly equal.”

## 6. Phase 2 — HDT strategy

### Question and hypothesis

Compare the three values of `--hdt-strategy` on the same pilot VCF. The
hypothesis is that `partitioned` is substantially more efficient than `single`
for HDT generation, with `auto` documenting the tool's default decision.

### Treatments

| Factor | Levels |
|---|---|
| Input | `test-larger.vcf` only |
| `--hdt-strategy` | `auto`, `partitioned`, `single` |
| `--rdf-storage-mode` | the Phase 1 selected mode |
| `--representations` | `hdt` only, so the HDT strategy is exercised directly |
| `--artifact-compression` | `none` |
| `--rdf-compression` | `none` |

Run each strategy at least three times, with strategy order randomized within
each repetition. Use `hdt` alone here to avoid COTTAS work obscuring the HDT
strategy effect. The common RDF conversion settings, input, software, and
parallelism must remain unchanged.

Example for the partitioned treatment:

```bash
python3 VCF-RDFizer/vcf_rdfizer.py \
  --mode full \
  --input VCF-RDFizer/test/test_vcf_files/test-larger.vcf \
  --rdf-storage-mode space-optimized \
  --rdf-compression none \
  --representations hdt \
  --artifact-compression none \
  --hdt-strategy partitioned \
  --spark-partitions 8 \
  --rdf-layout batch \
  --out experiments/phase2/partitioned-r1 \
  --build
```

Substitute `auto` and `single` for the strategy and use the Phase 1 selected
storage mode. For `auto`, record the strategy actually selected in the logs if
the tool exposes it; `auto` is a policy level, not necessarily a fourth HDT
algorithm.

### Analysis and decision rule

The primary comparison is partitioned versus single median HDT wall time. Also
compare CPU time, peak memory, temporary disk usage, final HDT size, and
success/failure rate. Report:

```text
speedup_single_over_partitioned = median_time_single / median_time_partitioned
memory_reduction                 = 1 - median_peak_rss_partitioned / median_peak_rss_single
```

Select the strategy with the lowest median total compute time among successful
runs. If two strategies are within 5% in time, select the one with lower peak
memory and storage. The expected Phase 3 setting is `partitioned`, but the
measured result—not the expectation—determines the selected setting.

If `single` fails, times out, or exhausts memory, retain the failure as a
result; do not silently replace it with `auto` or `partitioned`. This is part
of the efficiency comparison.

## 7. Phase 3 — Representation and artifact-compression benchmark

### Purpose

Run the full ten-file corpus only after the Phase 1 storage mode and Phase 2
HDT strategy have been selected. This phase estimates the practical time/space
frontier of the compression choices.

### Configuration matrix

The current repository commands request the two representations `hdt,cottas`
and the artifact compressors `none`, `gzip`, and `brotli`. Use the comma-
separated options in one invocation when supported. This shares the expensive
VCF-to-RDF conversion and is more efficient than reconverting each input once
per artifact. Treat each emitted representation/compressor pair as a separate
result cell:

| Representation | Artifact compression levels |
|---|---|
| HDT | `none`, `gzip`, `brotli` |
| COTTAS | `none`, `gzip`, `brotli` |

Thus, the planned output comparison contains six representation/compressor
cells per input. The uncompressed cells are the baselines for measuring the
additional time and space effect of gzip or Brotli. If the pinned tool also
emits the raw RDF artifact under these settings, retain it as a separate raw-
RDF baseline and report its `none`, `gzip`, and `brotli` artifacts separately;
do not merge raw RDF and HDT/COTTAS sizes.

Use:

```bash
python3 VCF-RDFizer/vcf_rdfizer.py \
  --mode full \
  --input vcf_data/ \
  --rdf-storage-mode <phase-1-selected-mode> \
  --rdf-compression none \
  --representations hdt,cottas \
  --artifact-compression none,gzip,brotli \
  --hdt-strategy <phase-2-selected-strategy> \
  --spark-partitions 8 \
  --rdf-layout batch \
  --out experiments/phase3/<run-id> \
  --build
```

If the CLI requires one VCF path rather than a directory, run the same command
once per canonical file, preserving the file name in `<run-id>`. Do not run
the ten inputs as one opaque aggregate if that prevents per-file timings and
sizes from being recorded.

Run the full corpus at least three times if feasible. A practical minimum is
one successful run for every file/configuration cell plus repeated runs for
the largest or most variable files; any reduced-repetition design must be
labelled exploratory. Keep the configuration bundle constant across all ten
inputs. Randomize the input order between repetitions, but never change the
configuration or software environment mid-run.

### Phase 3 outputs

For every VCF and every emitted artifact, store:

- representation (`hdt`, `cottas`, and raw RDF if emitted);
- artifact compression (`none`, `gzip`, `brotli`);
- output path and exact byte size;
- artifact-generation wall/CPU time and peak memory;
- total pipeline wall/CPU time and conversion metrics;
- emitted triple/record count;
- exit code, logs, and checksum of the final artifact.

Summarize each cell with per-file size, time, normalized ratios, and IQR. Plot
at least:

1. output bytes versus wall time, with one point per artifact and color by
   representation/compressor;
2. per-input bars or a heatmap of size ratio;
3. per-input and aggregate speedups relative to each representation's
   uncompressed baseline.

The preferred configuration is a Pareto result: a configuration is dominated
if another configuration is no larger and no slower, with at least one strict
improvement. Report the complete Pareto frontier rather than declaring a
single universal winner, because the best choice depends on whether storage
or conversion time is the limiting resource.

## 8. Empirical complexity analysis

“Size complexity” here means the observed scaling of output bytes and runtime
with input size and RDF cardinality; these experiments do not prove an
algorithmic big-O bound. For each representation/compressor, fit and report
the slope of:

```text
log(output_bytes) ~ log(input_bytes)
log(wall_seconds) ~ log(input_bytes)
log(wall_seconds) ~ log(emitted_triples)
```

Use the ten files as observations, show confidence intervals for slopes, and
inspect residuals. Because the inputs differ in sample count, genome build,
variant type, and record structure, also report results stratified by dataset
family where possible. A slope near 1 indicates approximately linear empirical
scaling over this corpus; it should not be generalized beyond the measured
range without additional datasets.

## 9. Validity checks and reporting rules

Before accepting a run:

- require exit code 0 and verify that expected artifacts exist;
- verify final artifact checksums and record byte counts;
- verify that all configurations emit the same logical RDF content, or record
  why a representation is intentionally not byte-identical;
- compare triple counts across equivalent configurations;
- flag retries, timeouts, OOM events, missing metrics, and partial outputs;
- exclude failed runs from timing medians but report their count and causes;
- never silently discard an outlier—investigate it and report the decision.

The final report should include the exact configuration matrix, all ten input
names, software/system conditions, per-run raw metrics, medians and IQRs,
paired percentage changes for Phases 1–2, and the Phase 3 Pareto frontier.
The conclusion should answer the three research questions explicitly and
separate observations from hypotheses that were not supported.

## 10. Recommended execution order

1. Pin the VCF-RDFizer version and capture the environment manifest.
2. Download and checksum the ten corpus VCFs.
3. Run the pilot warm-up, then Phase 1 storage-mode comparisons.
4. Select the storage mode using the pre-specified time/space rule.
5. Run Phase 2 with `auto`, `partitioned`, and `single`.
6. Select the HDT strategy using the pre-specified compute/memory rule.
7. Run the Phase 3 representation/compressor bundle over all ten VCFs.
8. Validate artifacts, aggregate raw metrics, compute normalized metrics, and
   generate tables/figures.

This ordering minimizes repeated conversion work while preserving a controlled
comparison for each research question.
