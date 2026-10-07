# VCF-RDFizer testing

This repository contains the current benchmark harness, plug-in tests, archived
measurement evidence, and the BioMedSem manuscript for VCF-RDFizer.
Large VCF inputs are downloaded from their original providers and are not stored
in Git.

| Directory or file | Purpose |
| --- | --- |
| [`benchmarks/`](benchmarks/README.md) | Experiment runners, fixtures and analysis; includes the separate regional retrieval, large-graph retrieval (up to the complete HG005 VCF) and ACMG use-case experiments. |
| [`benchmarks/RUN_PLAN.md`](benchmarks/RUN_PLAN.md) | Configuration and host allocation for the manuscript campaign. |
| [`benchmarking_suggestions.md`](benchmarking_suggestions.md) | Design rationale behind the numbered benchmark experiments. |
| [`plugin-tests/`](plugin-tests/README.md) | Policy, SPDI and gene-linker verification. |
| [`BioMedSem_2026/paper/`](BioMedSem_2026/paper/README.md) | Current manuscript, supplement, compiled PDFs and portable source ZIP builder. |
| [`BioMedSem_2026/benchmark-results/`](BioMedSem_2026/benchmark-results/README.md) | Measurement records and provenance used by the paper, including evidence for its testing-issues supplement. |
| [`tool-docs/`](tool-docs/) | Current review, revision and implementation work, plus the advisor report. |

The ECCB manuscript, finished experiments and superseded runners, reports and
figures are preserved on the [`legacy` branch](https://github.com/ecrum19/vcf-rdfizer-testing/tree/legacy).
See [the archive inventory](LEGACY.md) for what moved and how to retrieve it.

## Running the current tests

Start with the [benchmark operator's guide](benchmarks/README.md) for the tool
checkout, Docker and Python dependencies. From this repository's root:

```bash
export BM_IMAGE_VERSION=3.1.0
bash benchmarks/00_environment.sh
bash benchmarks/run_all.sh smoke
python3 benchmarks/analysis/collect_metrics.py --all
```

The smoke profile checks the pipeline with small inputs; its timings are not
benchmark measurements. Follow [the run plan](benchmarks/RUN_PLAN.md) to reproduce
the manuscript campaign. Regional retrieval, scale retrieval and the ACMG use
case are separate experiments; see the operator's guide and
[the ACMG instructions](benchmarks/use_case/acmg/README.md).

Run plug-in checks using [their separate instructions](plugin-tests/README.md).
The paired Q1–Q13 validation workload is exercised by
`benchmarks/06_equivalence.sh` through VCF-RDFizer's validation runner.

## Building the paper and reports

```bash
make -C BioMedSem_2026/paper
make -C BioMedSem_2026/paper bundle
```

These build the main paper and supplement; `bundle` also produces a self-contained
LaTeX source ZIP. See [the paper README](BioMedSem_2026/paper/README.md) for
compilation requirements and instructions for recipients.

The integrated archive summary is rebuilt with:

```bash
python3 scripts/build_run_summary.py BioMedSem_2026/benchmark-results \
  --output BioMedSem_2026/benchmark-results/summary.json
```

## Results site

An interactive version of the evidence is published at
<https://ecrum19.github.io/vcf-rdfizer-testing/>, built from the archive by
`.github/workflows/pages.yml` on every push to `main`. To build and view it locally:

```bash
python3 -m unittest scripts/test_build_site_data.py   # the data must match the paper
python3 scripts/build_site_data.py --out site/data
python3 -m http.server 8765 --directory site
```

The page types no numbers of its own: charts read the data files, and every
number in its prose is a `{placeholder}` or `data-fill` span filled from
`facts.json`, which the builder computes from `BioMedSem_2026/benchmark-results`
and `benchmarks/use_case/acmg`. The tests fail if a digit is typed into the page.

| Support script | Current use |
| --- | --- |
| `scripts/download_test_data.sh` | Downloads and normalizes the ten public VCF inputs. |
| `scripts/install_vcf_rdfizer_ubuntu.sh` | Installs Docker and, optionally, the VCF-RDFizer CLI on Ubuntu. |
| `scripts/report_system_conditions.py` | Captures host/software details; called by `00_environment.sh`. |
| `scripts/build_run_summary.py` | Integrates archived cells, provenance and validation outcomes. |
| `scripts/combine_benchmark_metrics.py` | Extracts per-run measurements; imported by the archive summary builder. |
| `scripts/build_site_data.py` | Builds the results site's data files from the archive (stdlib only). |

## Ubuntu setup

```bash
bash scripts/install_vcf_rdfizer_ubuntu.sh --docker-only
```

Open a new login shell afterwards for Docker group membership to take effect.
To install the CLI as well, omit `--docker-only`; use
`VCF_RDFIZER_VERSION=3.1.0` to select the base benchmark release. The installer
skips dependencies already installed.

## Datasets

The table below lists the datasets used in the experiments, including file name, provenance/profile page, approximate size, source/provider label, and the exact `wget` command used to retrieve the file(s).

> Note: the `wget --mirror ... '/_/'` URLs point to collection roots. Depending on what is hosted there, one or more files may be downloaded.

| # | File name | VCF version | Profile / provenance | Size | Provider / label | Download command |
|---:|---|---|---|---:|---|---|
| 1 | `NG1N86S6FC.vcf.gz` | VCFv4.2 | https://my.pgp-hms.org/profile/hu416394 | 379 MB | Sequencing.com | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://f26290bdbc3bf08190edec227f21635c-291.collections.ac2it.arvadosapi.com/_/'` |
| 2 | `NG131FQA1I.vcf.gz` | VCFv4.2 | https://my.pgp-hms.org/profile/huFFFE77 | 224 MB | Dante Labs | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://5aa905ff32eca70008e6d6d8aca1f238-200.collections.ac2it.arvadosapi.com/_/'` |
| 3 | `NB72462M.vcf.gz` | VCFv4.2 | https://my.pgp-hms.org/profile/huF7A4DE | 341 MB | Nebula Genomics | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://531155966bc06bca5de62439c00ce64b-282.collections.ac2it.arvadosapi.com/_/'` |
| 4 | `60820188475559.vcf.gz` | VCFv4.2 | https://my.pgp-hms.org/profile/hu1C1368 | 325 MB | Filtered SNPs | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://e17abc964664035c2efe6041b954e4f1-300.collections.ac2it.arvadosapi.com/_/'` |
| 5 | `60820188474283.vcf.gz` | VCFv4.2 | https://my.pgp-hms.org/profile/hu6ABACE | 222 MB | Dante Labs WGS | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://b42c5de31c35c2184a7119ddee4b049d-208.collections.ac2it.arvadosapi.com/_/'` |
| 6 | `0GOOR_HG002.vcf.gz` | VCFv4.2 | https://precision.fda.gov/challenges/10/results | 69 MB | Genome in a Bottle Truth Challenge v2 | `wget https://data.nist.gov/od/ds/ark:/88434/mds2-2336/submission_vcfs/0GOOR/0GOOR_HG002.vcf.gz` |
| 7 | `1000G_phase3_chr20.vcf.gz` | VCFv4.1 | https://www.internationalgenome.org/data-portal/data-collections/phase3/ | 327 MB | 1000 Genomes Phase 3 batch; 2,504 samples; GRCh37 | `wget 'https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr20.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz' -O 1000G_phase3_chr20.vcf.gz` |
| 8 | `HGSVC2.vcf.gz` | VCFv4.2 | https://internationalgenome.org/data-portal/data-collections/hgsvc2/ | 31.5 MB | HGSVC2 structural-variant batch; 32 samples; GRCh38 | `wget 'https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/HGSVC2/release/v1.0/integrated_callset/freeze3.sv.alt.vcf.gz' -O HGSVC2.vcf.gz` |
| 9 | `HG004_GRCh38.vcf.gz` | VCFv4.2 | https://www.nist.gov/programs-projects/genome-bottle | 149 MB | Genome in a Bottle HG004 benchmark; single sample; GRCh38 | `wget 'https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/AshkenazimTrio/HG004_NA24143_mother/NISTv4.2.1/GRCh38/HG004_GRCh38_1_22_v4.2.1_benchmark.vcf.gz' -O HG004_GRCh38.vcf.gz` |
| 10 | `HG005_GRCh38.vcf.gz` | VCFv4.2 | https://www.nist.gov/programs-projects/genome-bottle | 139 MB | Genome in a Bottle HG005 benchmark; single sample; GRCh38 | `wget 'https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/ChineseTrio/HG005_NA24631_son/NISTv4.2.1/GRCh38/HG005_GRCh38_1_22_v4.2.1_benchmark.vcf.gz' -O HG005_GRCh38.vcf.gz` |

The `VCF version` column is the value of the `##fileformat` declaration on the
first line of each file. It was read without downloading the full datasets, by
requesting only the first 128 KB of each file over HTTP and decompressing that
prefix:

```bash
curl -sL -r 0-131071 '<url>' | gzip -dc 2>/dev/null | head -1
```

For an already-downloaded copy, the equivalent local check is:

```bash
for f in vcf_data/*.vcf.gz; do printf '%s\t' "$f"; gzip -dc "$f" 2>/dev/null | head -1; done
```

Dataset 1 is distributed inside `SequencingdotcomVCFs.zip`; the version shown is
that of the archive member `KatSuricata-NG1N86S6FC-30x-WGS-Sequencing_com-03-18-24.snp-indel.genome.vcf.gz`.
Dataset 6 was verified from a local copy with the command above, because the
NIST distribution endpoint did not serve the file over HTTP during the check.

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
