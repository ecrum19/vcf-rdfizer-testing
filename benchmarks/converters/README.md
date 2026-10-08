# Converter comparison on a shared input (experiment 18)

The paper's converter table (Table 1) was built from public documentation. This experiment runs
the converters that can still be installed on the same inputs as VCF-RDFizer, and measures their
output with **the measurements the paper already applies to VCF-RDFizer**. It adds no new metric.

| Measurement | The same as in the paper's |
|---|---|
| Answers to the validator's content questions Q01–Q08, compared with the oracle computed from the source VCF | Semantic validation (RQ1) |
| Conversion wall time and peak resident memory (GNU `time -v`) | Conversion benchmark |
| Triples, triples per record, and gzipped N-Triples size relative to the gzipped VCF | Conversion benchmark; the size panel of the retrieval figure (`fig:regional`b) |
| QLever index build time | Retrieval experiments |

## What is compared, and how

Every converter's graph goes through one script, [`compare_converters.py`](compare_converters.py),
which runs inside the pinned VCF-RDFizer image and imports that image's validator unchanged:
the same oracle (cyvcf2 and bcftools over the source VCF), the same QLever build, the same result
normalisation, and the same comparator. Only the SPARQL differs. Each converter's questions are
ported to its own vocabulary and kept in `queries/<tool>/`. VCF-RDFizer's are copied verbatim from
the v3.3.1 tag, and the driver checks them against the copies in the image.

Each question gets one of these outcomes:

| Outcome | Meaning |
|---|---|
| `PASS` | The graph's answer equals the oracle's |
| `MISMATCH` | The graph holds the information, but its answer differs from the oracle's. `comparison.json` gives the differing rows. |
| `NOT_REPRESENTED` | The graph does not hold the information the question needs. The reason, with evidence from the converter's source, is in `queries/<tool>/not_represented.json`. |
| `EXECUTION_FAILED`, `RESULT_UNREADABLE` | The query did not run, or its result could not be read. |

The script refuses to run when a question in scope has neither a query nor a recorded reason, so a
missing port cannot be reported as a missing capability.

**Why Q01–Q08 only.** The validator asks 13 questions. Q09 and Q10 count the VCF Core predicates
and classes, and Q11–Q13 hash VCF-RDFizer's own record IRIs into their digests. None of the five has
a counterpart in another vocabulary. Q01–Q08 ask about the VCF's content: record density, variant
shape, Ti/Tv, FILTER values, genotype classes, AC/AN from genotypes, file metadata, and header lines.

**Each converter is run with the options that make its output most complete,** not with its
defaults, and the options are recorded per tool below. A question a converter leaves out by design,
such as TogoVar's omission of genotypes, is reported as `NOT_REPRESENTED`, not as a failure.

## Inputs

| Input | Records × samples | Why |
|---|---|---|
| `HG005_GRCh38_r100000.vcf.gz` | 100,000 × 1 | The slice used by the query-cost and regional-retrieval experiments |
| `1000G_10000r_s16.vcf.gz` | 10,000 × 16 | Multi-sample, phased, with multiallelic records, so Q05–Q06 are tested on more than one sample |

Both are derived by `02_derive_ladders.sh`. Their SHA-256 values are in
`BioMedSem_2026/benchmark-results/vcf-input-sizes.json`.

## Reproducing

```bash
BM_IMAGE_VERSION=3.3.1 ./benchmarks/18_converter_comparison.sh
```

Requires Docker on an x86_64 host. Every image is built from a pinned base image digest, with
packages taken from `snapshot.debian.org` at a fixed date, and every upstream artifact is verified
against the checksum in [`pins.env`](pins.env). Results land in
`$BM_RESULTS/18_converter_comparison/`, one cell per conversion and per comparison, recorded like
every other experiment (`bench.json`, command line, logs).

## Converters

Each converter runs in its upstream image, unmodified, wherever upstream publishes one. The
measuring binary is mounted into the container rather than built into it. Ports read only what the
graph states. Where a converter writes two VCF values the same way, the port maps that one state to
the value the converter's source code derives it from, and the conflation is listed below. The
comparison then shows whether it costs anything on these inputs.

### VCF-RDFizer v3.3.1 (the baseline)

- **Obtained:** release source archive `v3.3.1` (SHA-256 in `pins.env`) and image
  `ecrum19/vcf-rdfizer@sha256:3ad71b1a…2993`.
- **Command:** the release CLI, run from the runner exactly as in every other experiment, with the
  options of the paper's N-Triples-only rerun: `--mode full --sample-representation expanded
  --rdf-storage-mode space-optimized --representations none --rdf-compression gzip`.
- **Questions:** the validator's own Q01–Q08, copied verbatim. The driver checks them against the
  copies in the image.

### JVarkit `vcf2rdf` (commit `fc2356a3`)

- **Obtained:** built from source. Upstream publishes no jar, and its Dockerfile builds an older
  commit from another branch.
  - The pin is the commit, because the `v2026.04.30` tag was moved after its release was published.
  - The Gradle wrapper lacks a distribution checksum, so one is added.
  - The build fetches its library jars from Maven Central without checksums, so the image records
    the SHA-256 of every jar it used (`/opt/jvarkit/build-sha256.txt`).
- **Command:** `java -jar jvarkit.jar vcf2rdf --hide '' <vcf>`. The default `--hide
  FILTER,ALT,VEP,GT` would omit ALT, FILTER, and genotypes.
- **Graph:**
  - Turtle in its own `http://github.com/lindenb/jvarkit/` namespace. Classes are written as IRIs
    with the scheme `vcf` (`<vcf:Variant>`), not as prefixed names.
  - A record is `<urn:variant/CHROM:POS:REF>`, so lines sharing CHROM, POS, and REF merge.
  - ALT: one literal per allele, with symbolic alleles and breakends written as `""`.
  - FILTER: one IRI per failed filter.
  - One genotype node per record and sample, typed by htsjdk's call class.
  - No INFO. Header: contigs, FILTER IDs, and samples only.
- **Conflations:**
  - FILTER `PASS` and `.` both write nothing; the port reads nothing as PASS.
  - No ploidy is written, so haploid calls read as homozygous.
  - A no-call and a record without GT both carry no class; the port reads either as MISSING.
- **Not in the graph:** Q07, Q08 (see `queries/jvarkit/not_represented.json`).

### TogoVar `vcf2rdf` v1.0.0-beta.12 (commit `f17835a6`)

- **Obtained:** the upstream Docker Hub image, by digest.
- **Command:**
  - `vcf2rdf generate config --assembly <GRCh38|GRCh37> <vcf>`, then
    `vcf2rdf convert --no-normalize --config <config> <vcf>`.
  - `--no-normalize` keeps POS, REF, and ALT as written; the default trims them.
  - The input must be bgzipped with a `.tbi` index.
- **Graph:**
  - Turtle with FALDO locations and the `gvo:` namespace.
  - One blank node per ALT allele and none for the record, so records are regrouped on (reference,
    POS, REF, ID).
  - CHROM is replaced by the reference IRI its configuration assigns. The Q01 port maps it back
    through that configuration (`{{CHROM_VALUES}}`).
  - REF and ALT alleles outside `[ACGTURYKMSWBDHVN]` are dropped (symbolic, `*`, breakends), and so
    are records with no allele left.
  - INFO is written. Samples, genotypes, and header lines are not, by design.
- **Conflation:** multiple FILTER values lose their order.
- **Not in the graph:** Q05–Q08.

### SPARQLing Genomics `vcf2rdf` 0.99.11 (commit `1859f6f8`)

- **Obtained:** the upstream release image (a Guix pack), loaded from its release tarball after the
  checksum is verified.
- **Command:** `vcf2rdf -i <vcf>`. The defaults already write INFO, FORMAT, and the header.
- **Graph:**
  - N-Triples.
  - One call node per record and sample, and only for calls with a non-reference allele. Records in
    which no sample carries one are absent.
  - Call IRIs are `origin://<md5>@<k>`, with k = record index × samples + sample index (documented
    upstream), so records are regrouped on floor(k / samples).
  - Only the first ALT allele is written.
  - Number=A/R/G INFO values are divided by the sample count, so on the 16-sample input AC and AF
    are dropped.
  - Header lines are typed items.
- **Conflations:**
  - A multiallelic record is recognised only when a written call carries an allele index ≥ 2.
  - Multiple FILTER values lose their order.

### BioInterchange 2.0.5 (commit `49d57012`)

- **Obtained:** upstream published neither a binary nor an image, and its source build no longer
  works, because it clones a LibDocument repository that is gone.
  - The one remaining binary is the x86_64 Linux bottle of the brewsci/bio Homebrew formula
    (removed from that tap on 2025-10-25). GHCR still serves it, addressed by its SHA-256.
  - It runs on Debian bullseye, because it links Python 3.9 and OpenSSL 1.1.
  - The JSON-LD contexts its output names now return 404. `bi_jsonld_to_nquads.py` therefore
    inlines the context file from the pinned commit and refuses any other remote document. It uses
    PyLD from the same snapshot; rdflib would read FILTER `.` as PASS.
  - Time-boxed: if the image cannot be built, or the tool fails on an input, that is recorded as the
    result (`environment/unavailable.tsv`, or the cell's exit code).
- **Command:** `biointerchange -o <out.ldj> <in.vcf>`, on an uncompressed copy of the input. No option
  changes what is written for VCF.
- **Graph:**
  - GFVO-squared JSON-LD, one document per line. Records, alleles, and samples are blank nodes; the
    header is on a `gc:Meta` node.
  - ALT alleles are `g:alleleB`, `g:alleleC`, … in file order.
  - FILTER is an ordered list, with PASS as the empty list.
  - Genotypes are letter strings (`AB`), with hom-ref calls kept.
- **Conflations:**
  - A missing allele `.` is written as REF, so MISSING reads as HOM_REF or HET.
  - `*` is written as `""`, and the port restores it.
  - `##fileformat` loses its `VCFv` prefix, and the port restores it.
  - INFO and ALT definitions share one property and are told apart by whether they have a type.
  - Definitions whose IDs the tool renames to the same term (AD and DP both become `depth`) collapse
    into one.
