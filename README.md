# Test Data (VCF Inputs)

This repository contains automated tests for a tool that converts genomic **VCF** files into **RDF**.
Because the VCF inputs are large, they are **not stored in Git**. The experiment pipeline downloads them from their original hosting sources.

## Datasets

The table below lists the datasets used in the experiments, including file name, provenance/profile page, approximate size, source/provider label, and the exact `wget` command used to retrieve the file(s).

> Note: the `wget --mirror ... '/_/'` URLs point to collection roots. Depending on what is hosted there, one or more files may be downloaded.

| # | File name | Profile / provenance | Size | Provider / label | Download command |
|---:|---|---|---:|---|---|
| 1 | `KatSuricata-NG1N86S6FC-30x-WGS-Sequencing_com-03-18-24.sv.vcf.gz` | https://my.pgp-hms.org/profile/hu416394 | 379 MB | Sequencing.com | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://f26290bdbc3bf08190edec227f21635c-291.collections.ac2it.arvadosapi.com/_/'` |
| 2 | `68484e35b07b48cd9eed01d1a0110ff0.vcf` | https://my.pgp-hms.org/profile/huF85C76 | 2.91 GB | Nebula Genomics | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://362f852df716087509351bc471a93b83-2026.collections.ac2it.arvadosapi.com/_/'` |
| 3 | `YP3ZQ.snpeff.vep.vcf` | https://my.pgp-hms.org/profile/huF85C76 | 6.49 GB | 30x WGS | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://e2050a5a973b05c215ce43af953062c0-4404.collections.ac2it.arvadosapi.com/_/'` |
| 4 | `NG131FQA1I.vcf.gz` | https://my.pgp-hms.org/profile/huFFFE77 | 224 MB | Dante Labs | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://5aa905ff32eca70008e6d6d8aca1f238-200.collections.ac2it.arvadosapi.com/_/'` |
| 5 | `NB72462M.vcf.gz` | https://my.pgp-hms.org/profile/huF7A4DE | 341 MB | Nebula Genomics | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://531155966bc06bca5de62439c00ce64b-282.collections.ac2it.arvadosapi.com/_/'` |
| 6 | `60820188475559.filtered.snp.vcf.gz` | https://my.pgp-hms.org/profile/hu1C1368 | 325 MB | Filtered SNPs | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://e17abc964664035c2efe6041b954e4f1-300.collections.ac2it.arvadosapi.com/_/'` |
| 7 | `60820188475559_SA_L001_R1_001.fastq.gz.10009.g.vcf.gz` | https://my.pgp-hms.org/profile/hu1C1368 | 1.86 GB | 30x WGS | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://4db2692220447fa6aeb6b949efde90e5-1329.collections.ac2it.arvadosapi.com/_/'` |
| 8 | `60820188474283.snp.vcf.gz` | https://my.pgp-hms.org/profile/hu6ABACE | 222 MB | Dante Labs WGS | `wget --mirror --no-parent --no-host --cut-dirs=1 'https://b42c5de31c35c2184a7119ddee4b049d-208.collections.ac2it.arvadosapi.com/_/'` |

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

### 2) Generate Comparison Figure

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

### 3) Export LaTeX Tables (Conversion + Compression)

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

### 4) Report System/Test Conditions for Paper Methods

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
