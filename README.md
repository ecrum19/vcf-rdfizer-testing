# Test Data (VCF Inputs)

This repository contains automated tests for a tool that converts genomic **VCF** files into **RDF**.
Because the VCF inputs are large, they are **not stored in Git**. The experiment pipeline downloads them from their original hosting sources.

## Datasets

The table below lists the datasets used in the experiments, including file name, provenance/profile page, approximate size, source/provider label, and the exact `wget` command used to retrieve the file(s).

> Note: the `wget --mirror ... '/_/'` URLs point to collection roots. Depending on what is hosted there, one or more files may be downloaded.

| # | File name | Profile / provenance | Size | Provider / label | Download command |
|---:|---|---|---:|---|---|
| 1 | `NG1N86S6FC.vcf.gz` | https://my.pgp-hms.org/profile/hu416394 | 379 MB | Sequencing.com | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://f26290bdbc3bf08190edec227f21635c-291.collections.ac2it.arvadosapi.com/_/'` |
| 2 | `NG131FQA1I.vcf.gz` | https://my.pgp-hms.org/profile/huFFFE77 | 224 MB | Dante Labs | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://5aa905ff32eca70008e6d6d8aca1f238-200.collections.ac2it.arvadosapi.com/_/'` |
| 3 | `NB72462M.vcf.gz` | https://my.pgp-hms.org/profile/huF7A4DE | 341 MB | Nebula Genomics | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://531155966bc06bca5de62439c00ce64b-282.collections.ac2it.arvadosapi.com/_/'` |
| 4 | `60820188475559.vcf.gz` | https://my.pgp-hms.org/profile/hu1C1368 | 325 MB | Filtered SNPs | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://e17abc964664035c2efe6041b954e4f1-300.collections.ac2it.arvadosapi.com/_/'` |
| 5 | `60820188474283.vcf.gz` | https://my.pgp-hms.org/profile/hu6ABACE | 222 MB | Dante Labs WGS | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://b42c5de31c35c2184a7119ddee4b049d-208.collections.ac2it.arvadosapi.com/_/'` |
| 6 | `0GOOR_HG002.vcf.gz` | https://precision.fda.gov/challenges/10/results | 69 MB | Genome in a Bottle Truth Challenge v2 | `wget https://data.nist.gov/od/ds/ark:/88434/mds2-2336/submission_vcfs/0GOOR/0GOOR_HG002.vcf.gz` |
| 7 | `1000G_phase3_chr20.vcf.gz` | https://www.internationalgenome.org/data-portal/data-collections/phase3/ | 327 MB | 1000 Genomes Phase 3 batch; 2,504 samples; GRCh37 | `wget 'https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr20.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz' -O 1000G_phase3_chr20.vcf.gz` |
| 8 | `HGSVC2.vcf.gz` | https://internationalgenome.org/data-portal/data-collections/hgsvc2/ | 31.5 MB | HGSVC2 structural-variant batch; 32 samples; GRCh38 | `wget 'https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/HGSVC2/release/v1.0/integrated_callset/freeze3.sv.alt.vcf.gz' -O HGSVC2.vcf.gz` |
| 9 | `HG004_GRCh38.vcf.gz` | https://www.nist.gov/programs-projects/genome-bottle | 149 MB | Genome in a Bottle HG004 benchmark; single sample; GRCh38 | `wget 'https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/AshkenazimTrio/HG004_NA24143_mother/NISTv4.2.1/GRCh38/HG004_GRCh38_1_22_v4.2.1_benchmark.vcf.gz' -O HG004_GRCh38.vcf.gz` |
| 10 | `HG005_GRCh38.vcf.gz` | https://www.nist.gov/programs-projects/genome-bottle | 139 MB | Genome in a Bottle HG005 benchmark; single sample; GRCh38 | `wget 'https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/ChineseTrio/HG005_NA24631_son/NISTv4.2.1/GRCh38/HG005_GRCh38_1_22_v4.2.1_benchmark.vcf.gz' -O HG005_GRCh38.vcf.gz` |

## Downloading the Datasets

Helper script:

```bash
bash scripts/download_test_data.sh
```

Optional output directory:

```bash
DATA_DIR=vcf_data bash scripts/download_test_data.sh
```

The script now rejects `index.html*` artifacts during mirroring.

Before downloading each dataset, the script checks for its canonical filename in `vcf_data/`. If that file, or the original downloaded filename/archive, is already present, `wget` is skipped and only the required normalization or extraction step is performed.

The Sequencing.com collection is downloaded as `SequencingdotcomVCFs.zip`. After the download succeeds, the script extracts the archive in a temporary directory, keeps the member `KatSuricata-NG1N86S6FC-30x-WGS-Sequencing_com-03-18-24.snp-indel.genome.vcf.gz`, renames it to `NG1N86S6FC.vcf.gz`, and removes the other extracted files and archive. The other downloaded files are likewise normalized to the ten canonical names shown in the table above.

The four additional datasets are direct downloads from the public IGSR and NIST FTP servers. The 1000 Genomes Phase 3 chromosome-20 file is a phased GRCh37 batch VCF with 2,504 samples. The HGSVC2 `freeze3.sv.alt.vcf.gz` file is a GRCh38 structural-variant batch VCF with 32 samples; it uses sequence alleles in the `REF`/`ALT` columns rather than the symbolic-allele representation. The HG004 and HG005 files are single-sample GRCh38 Genome in a Bottle benchmark VCFs covering chromosomes 1–22. Their canonical names and download URLs are listed in the table above and are also used directly by `scripts/download_test_data.sh`.

## Scripts

| Script | Description |
|---|---|
| `scripts/combine_benchmark_metrics.py` | Combines conversion, TSV, and compression metrics from one or more benchmark runs into a consolidated JSON file. |
| `scripts/localize_experiment.py` | Copies a timestamped run into a named `experiments/finished_experiments/` directory and rebuilds the aggregate metrics JSON for all named runs. |
| `scripts/download_test_data.sh` | Downloads the public VCF inputs, extracts the Sequencing.com archive member, and normalizes all files to the canonical names used by the benchmarks. |
| `scripts/export_latex_tables.py` | Converts consolidated benchmark metrics into LaTeX-ready conversion and compression tables. |
| `scripts/install_vcf_rdfizer_ubuntu.sh` | Installs Docker and the VCF-RDFizer Python CLI on Ubuntu; supports a `--docker-only` mode. |
| `scripts/plot_combined_metrics.py` | Generates a comparison figure from consolidated benchmark metrics. |
| `scripts/repair_compression_wall_times.py` | Reconstructs incorrect historical compression wall times from wrapper logs and updates the affected benchmark artifacts. |
| `scripts/report_system_conditions.py` | Collects host and software details and emits paper-ready system-condition text or JSON. |


## Automated Ubuntu Setup

On Ubuntu, the setup script ensures `unzip` is installed, installs Docker Engine from Docker's official apt repository, enables the Docker service, and adds the current user to the `docker` group. By default it also installs the VCF-RDFizer Python CLI in a dedicated virtual environment and adds `~/.local/bin` to the user's `PATH`:

```bash
bash scripts/install_vcf_rdfizer_ubuntu.sh
```

Open a new login shell after the script completes so the Docker group membership takes effect. A specific VCF-RDFizer release can be installed with:

```bash
VCF_RDFIZER_VERSION=1.0.0 bash scripts/install_vcf_rdfizer_ubuntu.sh
```

The installer is safe to rerun: it installs only missing apt packages, downloads
Docker's signing key and repository configuration only when absent, and skips
the VCF-RDFizer package download when the requested package is already present.
If `VCF_RDFIZER_VERSION` is set, it reinstalls only when that exact version is
not already available.

To install and activate Docker only, while running VCF-RDFizer from an existing git checkout:

```bash
bash scripts/install_vcf_rdfizer_ubuntu.sh --docker-only
```

This mode does not install Python packages or modify the user's `PATH`.

## Replicating Conversion & Compression Tests

TSV Benchmarks only:
```bash
vcf_rdfizer --mode tsv --input vcf-rdfizer-testing/vcf_data/ --out vcf-rdfizer-testing/benchmark-results/v1.1 --build
```

Full Run Benchmarks (including all compression types):
```bash
vcf_rdfizer --mode full --input vcf-rdfizer-testing/vcf_data/ --spark-partitions 8 --rdf-layout batch --out vcf-rdfizer-testing/benchmark-results/v1.1 --compression gzip,brotli,hdt,hdt_gzip,hdt_brotli --build
```

Full space-optimized run for one VCF with all supported raw-RDF and artifact
compression options:

```bash
bash test_full_spaceopt_all_compressions.sh test-larger.vcf.gz
```

The argument may be a basename in `VCF-RDFizer/test/test_vcf_files/`, a path
relative to the current directory/repository, or an absolute path. The script
selects raw RDF `gzip,brotli`, both `hdt,cottas` representations, and gzip plus
Brotli packaging for each representation. (`space-optimized` is the
VCF-RDFizer CLI spelling of the space-efficient mode.)

## Semantic VCF Query Equivalence Tests

The Dockerized suite in [`tests/test-queries`](tests/test-queries/README.md)
compares six bioinformatic summaries computed independently from a source VCF
and its converted N-Triples: genomic density, allele shape, Ti/Tv, exact FILTER
distribution, per-sample genotype classes/call rate, and genotype-derived
AC/AN. Run its edge-case fixture with:

```bash
tests/test-queries/run_in_docker.sh
```

For a real conversion, provide one VCF and its corresponding `.nt` file or
partition directory:

```bash
tests/test-queries/run_in_docker.sh \
  --vcf vcf_data/HG004_GRCh38.vcf.gz \
  --rdf path/to/HG004/rdf \
  --dataset-id HG004_GRCh38
```

The query runner consumes `.nt` only; decode generated `.hdt`/`.cottas` output
with VCF-RDFizer first (details in the [test-specific README](tests/test-queries/README.md)).

See the [test-specific README](tests/test-queries/README.md) for exact query
semantics, multiple-partition usage, provenance options, result files, status
interpretation, and large-dataset memory guidance.


## Metrics and Reporting Scripts

### 1) Combine Conversion + Compression Metrics

Script: `scripts/combine_benchmark_metrics.py`

Single run directory:

```bash
python3 scripts/combine_benchmark_metrics.py benchmark-results/20260305T102641
```

This writes:

- `benchmark-results/20260305T102641/combined_metrics.json`

Multiple run directories:

```bash
python3 scripts/combine_benchmark_metrics.py \
  benchmark-results/20260305T102641 \
  benchmark-results/20260308T120000 \
  -o benchmark-results/combined_metrics_all_runs.json
```

### 2) Localize a Finished Experiment

After a VCF-RDFizer run has written metrics to
`experiments/run_metrics/<run-id>`, give it a human-readable name and add it
to the aggregate archive:

```bash
python3 scripts/localize_experiment.py \
  20260824T173012 \
  --name plain-hdt-cottas
```

This copies the run to
`experiments/finished_experiments/plain-hdt-cottas/` and writes or refreshes
`experiments/finished_experiments/combined_metrics_multi_run.json` using every
named run already in `finished_experiments`. Before aggregation, it repairs
recoverable compression wall times across all named runs and verifies that every
successful compression method has a recorded wall-clock time. It refuses to
publish an aggregate if a successful operation still lacks that measurement,
rather than inventing a value. A method that was selected but has no recorded
result is kept in the aggregate's integrity audit and is not emitted as a
null-valued compression measurement, so an older incomplete archive does not
block a later completed run. The original run ID and timestamp remain available
in the copied metric files, while the aggregate uses the chosen directory name
as `run_name`.

Use `--source-root`, `--finished-root`, or `--output` when working with a
different layout. An existing name is protected by default; pass
`--overwrite` only when replacing that localized copy is intentional.

### 3) Generate Comparison Figure

Script: `scripts/plot_combined_metrics.py`

Requirements:

```bash
python3 -m pip install matplotlib
```

Generate figure PNG from combined metrics:

```bash
python3 scripts/plot_combined_metrics.py \
  benchmark-results/20260305T102641/combined_metrics.json \
  -o benchmark-results/20260305T102641/combined_metrics_figure.png
```

### 4) Export LaTeX Tables (Conversion + Compression)

Script: `scripts/export_latex_tables.py`

```bash
python3 scripts/export_latex_tables.py \
  benchmark-results/20260305T102641/combined_metrics.json
```

This writes two LaTeX-ready files beside the JSON:

- `conversion_stats_table.tex`
- `compression_stats_table.tex`

Custom output directory:

```bash
python3 scripts/export_latex_tables.py \
  benchmark-results/20260305T102641/combined_metrics.json \
  --output-dir benchmark-results/latex
```

### 5) Report System/Test Conditions

Script: `scripts/report_system_conditions.py`

Generate a paper-ready sentence:

```bash
python3 scripts/report_system_conditions.py --format sentence
```

Generate machine-readable JSON:

```bash
python3 scripts/report_system_conditions.py --format json
```

Generate both sentence + JSON:

```bash
python3 scripts/report_system_conditions.py --format both
```

Write output to a file:

```bash
python3 scripts/report_system_conditions.py \
  --format both \
  -o benchmark-results/system_conditions.txt
```
