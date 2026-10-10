# VCF-RDFizer evaluation: harness and run records

The evaluation of [VCF-RDFizer](https://github.com/ecrum19/VCF-RDFizer) reported in
*VCF-RDFizer: From a VCF File to Explicit, Verifiable, and Policy-aware Semantic
Genomic Data* (BioMedSem 2026). The repository holds:
- the benchmark harness that ran every experiment;
- the run records of every reported result;
- the scripts that compute every reported value from those records;
- an interactive results site.

The GitHub repository also holds the manuscript, its figures and figure scripts
(`BioMedSem_2026/`) and the authors' working notes (`tool-docs/`). Those two are
not part of the [Zenodo archive](#zenodo-archive).

Every number, table and figure in the manuscript can be traced to a run record
here and regenerated from it. Only the runs whose results the manuscript reports
are on this branch. Pre-release, superseded, stalled and failed runs, including
those the supplement cites as evidence of the defects the reported runs
corrected, are on the
[`legacy` branch](https://github.com/ecrum19/vcf-rdfizer-testing/tree/legacy/benchmark-results)
(see [`LEGACY.md`](LEGACY.md)).

The input VCFs are downloaded from their providers (see [Datasets](#datasets)),
and the generated RDF is not stored. Every run records the command, tool
commit and image digest that rebuild it.

## Contents

| Path | Contents |
| --- | --- |
| [`benchmarks/`](benchmarks/README.md) | The harness: experiments `00`–`18`, the linked workflow ([`use_case/acmg/`](benchmarks/use_case/acmg/README.md)), the converter comparison ([`converters/`](benchmarks/converters/README.md)), fixtures, and analysis scripts. Its README gives each script, what it measures, the result it produced and where its records are; [`DESIGN.md`](benchmarks/DESIGN.md) gives each experiment's design as run, by the paper's research questions |
| [`benchmark-results/`](benchmark-results/README.md) | The run records of every reported result, per benchmark host. Its README maps each result to its records |
| [`plugin-tests/`](plugin-tests/README.md) | Tests of VCF-RDFizer's SPDI, gene and policy plug-ins on real data |
| [`scripts/`](#support-scripts) | Input download, host setup, the archive summary, and the code that computes every reported value (`figure_data.py`, `build_site_data.py`) |
| [`site/`](site/) | The [results site](https://ecrum19.github.io/vcf-rdfizer-testing/) |
| [`BioMedSem_2026/`](BioMedSem_2026/README.md) | *Repository only.* The manuscript and supplement (`paper/`), and every figure with the script or TikZ source that draws it (`paper-assets/`) |
| [`tool-docs/`](tool-docs/README.md) | *Repository only.* Working notes for the authors; no result depends on them |
| [`LEGACY.md`](LEGACY.md) | Material moved off this branch over time, and how to retrieve it |

## Software versions

The base campaign (experiments `00`–`13`) ran VCF-RDFizer **v3.1.0**: image
`ecrum19/vcf-rdfizer@sha256:1904e96dde12ab2e2e70d8ee1267765c293ab100a8bd1b14d5b009b2bf8e34aa`,
commit `d3b34d5`.

The later experiments ran **v3.3.1**: image
`ecrum19/vcf-rdfizer@sha256:3ad71b1a54612142e3be43b24e7e4a38551949cb641f4421bcae9bf051102993`,
commit `b25fb7b`, [doi:10.5281/zenodo.23237636](https://doi.org/10.5281/zenodo.23237636).
They are:
- the linked workflow;
- regional and large-graph retrieval;
- the converter comparison;
- the consumer WGS validation run.

On the same 100,000 HG005 records, the two releases write identical sorted
triples, so the v3.1.0 graphs that the retrieval experiments query stand for
v3.3.1's.

## Reproducing the results

**Recompute every reported value from the run records alone, and check it
against the paper** (Python 3.12, standard library only):

```bash
python3 -m unittest scripts/test_build_site_data.py      # every pinned number matches the paper
python3 scripts/build_site_data.py --out site/data       # every value the site and figures show
```

In the GitHub repository, the figures and the manuscript can be rebuilt too
(Matplotlib and LaTeX):

```bash
python3 BioMedSem_2026/paper-assets/figures/make_figures.py
make -C BioMedSem_2026/paper
```

**Rerun an experiment.** You need Docker, Python 3, and a VCF-RDFizer checkout at
the release the experiment used. Start with
[`benchmarks/README.md`](benchmarks/README.md), which gives each experiment's
script, release, host, configuration and records. In outline:

```bash
bash scripts/download_test_data.sh                       # the ten input VCFs
BM_IMAGE_VERSION=3.1.0 bash benchmarks/00_environment.sh
BM_IMAGE_VERSION=3.1.0 bash benchmarks/run_all.sh biomedsem      # the base campaign
BM_IMAGE_VERSION=3.3.1 bash benchmarks/17_use_case_acmg.sh       # e.g. the linked workflow
bash benchmarks/18_converter_comparison.sh                       # the converter comparison
```

Compare a download against `benchmark-results/input-checksums.tsv`
before trusting any comparison. `run_all.sh smoke` checks the pipeline on small
inputs; its timings are not measurements. The plug-in tests run
separately; see [`plugin-tests/README.md`](plugin-tests/README.md).

The linked workflow's MyVariant.info tier replays the service responses recorded
on 2026-09-28, which are published in
[`benchmarks/use_case/acmg/myvariant-cache/`](benchmarks/use_case/acmg/myvariant-cache/README.md).
Use them, not the live service, whose data change.

## Zenodo archive

The Zenodo record holds this repository without `BioMedSem_2026/` and `tool-docs/`.
[`.gitattributes`](.gitattributes) marks both `export-ignore`, so every archive git
or GitHub makes leaves them out: `git archive`, a release's source zip, and
Zenodo's GitHub import. To make the archive of a tagged release:

```bash
git archive --format=zip --prefix=vcf-rdfizer-testing/ -o vcf-rdfizer-testing.zip <tag>
```

## Results site

<https://ecrum19.github.io/vcf-rdfizer-testing/> presents the evidence as
interactive charts. `.github/workflows/pages.yml` builds it from the archive on
every push to `main`. The page types no numbers of its own:
- charts read the data files;
- every number in its prose is filled from `facts.json`, which
  `scripts/build_site_data.py` computes from the run records;
- the tests fail if a digit is typed into the page.

To view it locally:

```bash
python3 scripts/build_site_data.py --out site/data
python3 -m http.server 8765 --directory site
```

## Support scripts

| Script | Use |
| --- | --- |
| `scripts/download_test_data.sh` | Downloads the ten public VCF inputs and normalizes their names |
| `scripts/install_vcf_rdfizer_ubuntu.sh` | Installs Docker and, optionally, the VCF-RDFizer CLI on Ubuntu (`--docker-only`; `VCF_RDFIZER_VERSION=3.1.0` selects a release) |
| `scripts/report_system_conditions.py` | Records host and software details; called by `benchmarks/00_environment.sh` |
| `scripts/build_run_summary.py` | Integrates the base campaign's run records into `summary.json` |
| `scripts/combine_benchmark_metrics.py` | Extracts per-run measurements; imported by `build_run_summary.py` |
| `scripts/build_site_data.py` | Builds the results site's data from the run records (standard library only) |
| `scripts/test_build_site_data.py` | Pins the site's numbers to the paper's |

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

The script rejects `index.html*` artifacts during mirroring.

Before downloading each dataset, the script checks for its canonical filename in `vcf_data/`. If that file, or the original downloaded filename/archive, is already present, `wget` is skipped and only the required normalization or extraction step is performed.

The Sequencing.com collection is downloaded as `SequencingdotcomVCFs.zip`. After the download succeeds, the script extracts the archive in a temporary directory, keeps the member `KatSuricata-NG1N86S6FC-30x-WGS-Sequencing_com-03-18-24.snp-indel.genome.vcf.gz`, renames it to `NG1N86S6FC.vcf.gz`, and removes the other extracted files and archive. The other downloaded files are likewise normalized to the ten canonical names shown in the table above.

The four additional datasets are direct downloads from the public IGSR and NIST FTP servers. The 1000 Genomes Phase 3 chromosome-20 file is a phased GRCh37 batch VCF with 2,504 samples. The HGSVC2 `freeze3.sv.alt.vcf.gz` file is a GRCh38 structural-variant batch VCF with 32 samples; it uses sequence alleles in the `REF`/`ALT` columns rather than the symbolic-allele representation. The HG004 and HG005 files are single-sample GRCh38 Genome in a Bottle benchmark VCFs covering chromosomes 1–22. Their canonical names and download URLs are listed in the table above and are also used directly by `scripts/download_test_data.sh`.

## Licences

- **Code:** MIT License ([`LICENSE`](LICENSE)). This covers shell, Python,
  JavaScript, HTML and CSS sources, Makefiles, and the LaTeX/TikZ sources of
  figures.
- **Data and documents:** CC BY 4.0 ([`LICENSE-DATA`](LICENSE-DATA)). This covers
  the run records, the figures, the manuscript, and the documentation.
- **Exception:** the recorded MyVariant.info responses in
  `benchmarks/use_case/acmg/myvariant-cache/` remain under MyVariant.info's
  terms; see the README there.
- **Not redistributed:** the source VCFs stay under their providers' terms.

## Citation

Please cite the manuscript, and this archive by its Zenodo record (metadata in
[`.zenodo.json`](.zenodo.json), citation in [`CITATION.cff`](CITATION.cff)).
VCF-RDFizer itself is cited as
[doi:10.5281/zenodo.23237635](https://doi.org/10.5281/zenodo.23237635) (all
versions) or by the version used.
