# Test Data (VCF inputs)

This repository contains automated tests for a tool that converts genomic **VCF** files into **RDF**.  
Because the VCF inputs are large, they are **not stored in the Git repository**. Instead, the experiment pipeline **downloads them from the original hosting sources**.

## Datasets

The table below lists the datasets used in the experiments, including file name, provenance/profile page, approximate size, source/provider label, and the exact `wget` command used to retrieve the file(s).

> Note: The `wget --mirror ... '/_/'` URLs point to collection roots; `wget` may download one or more files from that collection depending on what is hosted there.

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

## Downloading the datasets

A helper script is provided to download all datasets in a reproducible manner:

```bash
bash scripts/download_test_data.sh