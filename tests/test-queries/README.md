# Semantic VCF query equivalence tests

This directory implements the semantic-query validation workload described in
[`vcf_rdfizer_testing_queries_plan.md`](../../vcf_rdfizer_testing_queries_plan.md).
It independently summarizes one source VCF with `cyvcf2`/`bcftools`, evaluates
the equivalent SPARQL over that VCF's N-Triples with Comunica, canonicalizes
both result sets, and requires exact integer equality.

The suite validates representation equivalence for the fields and graph paths
used by the six queries. It does not establish that the source variants are
biologically correct, normalized, or concordant with a truth set.

## Quick start: bundled fixture

Docker is the only host prerequisite. From the repository root, run:

```bash
tests/test-queries/run_in_docker.sh
```

The first run builds `vcf-rdfizer-query-tests:local`; later builds reuse
Docker's cache. The command then validates the bundled 15-record edge-case VCF
and its representative RDF. A successful run prints `"status": "PASS"` and
returns exit code 0. Generated reports are written to:

```text
tests/test-queries/results/edge_cases/
```

Use `--no-build` when the image already exists and no dependency definition
changed:

```bash
tests/test-queries/run_in_docker.sh --no-build
```

## Run against a converted dataset

Supply exactly one source VCF and the RDF produced from that same VCF:

```bash
tests/test-queries/run_in_docker.sh \
  --vcf vcf_data/HG004_GRCh38.vcf.gz \
  --rdf benchmark-results/HG004_GRCh38/rdf \
  --dataset-id HG004_GRCh38 \
  --converter-version 2.1.0 \
  --converter-commit COMMIT_SHA \
  --mapping path/to/default_rules.ttl \
  --vocabulary-version VERSION_OR_IRI \
  --vocabulary-commit COMMIT_SHA
```

`--rdf` accepts either an `.nt` file or a directory, which is searched
recursively for `.nt` partitions. Repeat it if a single conversion's partitions
live in multiple locations:

```bash
tests/test-queries/run_in_docker.sh \
  --vcf vcf_data/example.vcf.gz \
  --rdf experiments/example/rdf-batch-1 \
  --rdf experiments/example/rdf-batch-2 \
  --dataset-id example
```

Never pass partitions from different VCFs in one invocation. Contig labels,
sample IDs, FILTER strings, and allele strings are intentionally not rewritten
or harmonized.

The Docker wrapper mounts this repository at its original absolute path, so VCF,
RDF, mapping, and result paths must be inside the repository. To use external
paths, either copy the input under the repository or invoke
`run_suite.py` in an environment where the dependencies are installed.

### Conversion provenance

The semantic comparisons can run without the optional converter, mapping, and
vocabulary arguments, but the manifest will set `provenanceComplete` to false.
A publishable validation run should provide them. The mapping file itself is
hashed; version and commit strings are recorded verbatim.

The bundled `fixtures/edge_cases.nt` is a small representative graph used to
test the harness independently of a converter installation. To validate an
actual VCF-RDFizer build, convert `fixtures/edge_cases.vcf` through the same
mapping and command path as the production datasets, then pass the resulting
`.nt` file or partition directory with `--rdf`. The hand-checked result in
`fixtures/edge_cases.expected.json` remains the independent oracle:

```bash
tests/test-queries/run_in_docker.sh \
  --vcf tests/test-queries/fixtures/edge_cases.vcf \
  --rdf path/to/converter-output \
  --expected tests/test-queries/fixtures/edge_cases.expected.json \
  --dataset-id edge_cases_converter_build \
  --converter-version VERSION \
  --converter-commit COMMIT_SHA \
  --mapping path/to/default_rules.ttl \
  --vocabulary-version VERSION_OR_IRI
```

## What each query proves

All comparisons use exact integer counts. Ratios are display-only derivatives
computed after their underlying counts match.

| Query | Result and exact scope | Main graph path tested |
|---|---|---|
| Q1 `q01_record_density_1mb.rq` | Record counts by source contig and zero-based 1 Mb window, using `(POS - 1) // 1,000,000`. | `VCFRecord -> chrom, pos` |
| Q2 `q02_variant_shape_counts.rq` | Record-level ALT shape: no ALT, multiallelic, symbolic/breakend, other, SNV, equal-length substitution, insertion-shape, or deletion-shape. The complete ALT column remains one lexical value. | `VCFRecord -> ref, alt` |
| Q3 `q03_titv.rq` | Transition and transversion counts for biallelic A/C/G/T SNVs with `REF != ALT`. | `VCFRecord -> ref, alt` |
| Q4 `q04_filter_distribution.rq` | Counts by broad status and exact FILTER lexical value. `PASS`, `.`, and failed codes are distinct; semicolon-separated failures are not split. | `VCFRecord -> VariantCall -> filter` |
| Q5 `q05_sample_genotype_counts.rq` | Per-sample genotype class counts after normalizing `|` to `/` for classification. | `VariantCall -> SampleCall -> FormatFieldValue(GT)` |
| Q6 `q06_ac_an_distribution.rq` | Site distribution by genotype-derived `(AN, AC)` for single-ALT records with at least one complete haploid/diploid call containing only allele indexes 0/1. | All record, call, sample, and GT links |

### Q2 classification order

The order is part of the contract: `NO_ALT`, `MULTIALLELIC`,
`SYMBOLIC_OR_BREAKEND`, `OTHER`, `SNV`,
`MNV_OR_EQUAL_LENGTH_SUBSTITUTION`, `INSERTION_SHAPE`, then
`DELETION_SHAPE`. This is a record-shape classification, not an allele-level
decomposition and not a claim that every longer ALT is a normalized insertion.

### Q5 genotype classes

After phase-separator normalization, genotypes are classified as:

| Class | Rule |
|---|---|
| `NO_GT_FIELD` | The sample call has no `/fmt/GT` value. |
| `MISSING` | Any allele is `.`; partial calls such as `0/.` are missing. |
| `HAPLOID_REF` / `HAPLOID_ALT` | One complete allele index, respectively 0 or positive. |
| `HOM_REF` | Complete diploid `0/0`. |
| `HOM_ALT` | Complete diploid with equal positive indexes, such as `1/1`. |
| `HET` | Complete diploid with unequal indexes, including `1/2`. |
| `OTHER_PLOIDY` | Any other complete ploidy. |

Call rate is derived per sample as `(total - MISSING - NO_GT_FIELD) / total`.
Complete `OTHER_PLOIDY` calls count as called for Q5, but do not contribute to
Q6.

### Q6 exclusions

Q6 excludes multi-ALT records, no-ALT records, missing or partially missing GT,
polyploid GT, and any GT containing allele index 2 or higher. It derives AC and
AN from GT rather than trusting INFO tags. The comparison key is the exact
`(AN, AC, siteCount)` tuple; floating-point AF is never a primary assertion.

## Preflight and failure semantics

Before comparing biological summaries, the runner performs four RDF checks:

1. Raptor `rapper` parses every `.nt` source independently. A syntax error
   blocks semantic comparison.
2. `preflight_record_cardinality.rq` requires each typed VCF record to have
   exactly one CHROM, POS, REF, ALT, and call link.
3. `preflight_position_datatype.rq` requires `vcfr:pos` to use `xsd:integer`.
4. Sample/GT inventory counts must equal the VCF-derived number of sample calls,
   sample IDs, and GT value nodes.

`preflight_missing_token_conformance.rq` is also run. Plain `"."` literals are
reported as `EXPECTED_CONFORMANCE_FAILURE` because the current mapping does not
yet consistently emit `"."^^vcfr:Null`. This diagnostic is visible but does not
make otherwise equivalent results fail.

Statuses and applicability labels have distinct meanings:

| Status | Meaning |
|---|---|
| `PASS` | All required query rows and invariants match exactly. |
| `MISMATCH` | Both paths executed, but RDF-derived values or structural sample/GT counts differ. |
| `BLOCKED_BY_PREFLIGHT` | RDF syntax or a blocking record/POS structural check failed. |
| `EXECUTION_FAILED` | A parser or query engine invocation did not produce a result. |
| `NOT_APPLICABLE_VERIFIED_NO_SAMPLES_OR_GT` | Q5/Q6 applicability was ruled out from source structure, rather than inferred from an empty RDF result. |

The runner exits nonzero for every top-level status except `PASS`.

## Result files

Each run writes `tests/test-queries/results/<dataset-id>/` unless
`--results-dir` is supplied.

| File or directory | Contents |
|---|---|
| `manifest.json` | SHA-256 hashes for VCF, all RDF partitions, all queries, tool versions, platform, command line, and supplied converter/mapping/vocabulary provenance. |
| `parser.json` | Canonical VCF-oracle results, header inventory, record/sample counts, and derived call rates. |
| `rdf-validation.json` | Per-partition N-Triples syntax status and validator logs. |
| `preflight.json` | Structural and missing-token diagnostics. |
| `raw/` | Unmodified Comunica SPARQL Results JSON plus separate stderr and GNU `time -v` resource files. |
| `normalized/` | Typed and deterministically sorted canonical results for Q1-Q6. |
| `sparql.json` | Combined normalized RDF-derived result set. |
| `comparison.json` | Per-query missing rows, extra rows, differing counts, fixture checks, and cross-query invariants. |
| `summary.json` | Concise top-level status, applicability, preflight, provenance warnings, and report paths. |

Reusing a dataset ID overwrites the known generated report files for that ID.
Choose a distinct `--dataset-id` when runs must be retained side by side.

## Cross-query invariants

The comparator checks both result paths independently:

- Q1, Q2, and Q4 totals equal the source record count;
- Q3 transitions plus transversions equal its biallelic SNV count;
- Q3's biallelic A/C/G/T subset does not exceed Q2's broader SNV class;
- every represented sample has one Q5 class per source record; and
- every Q6 row has `AN > 0`, `0 <= AC <= AN`, and positive `siteCount`.

These checks complement, but never replace, parser-versus-SPARQL equality.

## Large and partitioned datasets

Q5 and Q6 traverse every sample call and are expected to dominate runtime and
memory for multi-sample VCFs such as 1000 Genomes. Run the fixture and smaller
datasets first. The wrapper gives Node an 8 GiB heap by default; adjust it when
needed:

```bash
VCF_QUERY_NODE_MEMORY_MB=16384 \
  tests/test-queries/run_in_docker.sh --no-build \
  --vcf vcf_data/1000G_phase3_chr20.vcf.gz \
  --rdf path/to/1000G/rdf \
  --dataset-id 1000G_phase3_chr20
```

Resource exhaustion or timeout is an execution failure, not a semantic
mismatch. Raw query stderr is retained to aid diagnosis.

## Run without Docker

The tested container pins Node 22.19.0, Comunica file query 5.3.0, cyvcf2
0.34.0, and its Python dependencies. For a local run, install:

- Python 3.11+ and `python -m pip install -r tests/test-queries/requirements.txt`;
- Node.js and `npm install -g @comunica/query-sparql-file@5.3.0`;
- `bcftools`; and
- Raptor's `rapper` command (`raptor2-utils` on Debian/Ubuntu).

Then run:

```bash
python3 tests/test-queries/run_suite.py \
  --vcf path/to/input.vcf.gz \
  --rdf path/to/rdf-or-partition-directory \
  --dataset-id dataset_name
```

For query-engine-only debugging, `run_comunica.sh` executes every versioned
`.rq` file and preserves raw results and stderr/timing output:

```bash
tests/test-queries/run_comunica.sh \
  --output-dir /tmp/query-results \
  path/to/part-00000.nt path/to/part-00001.nt
```

The smaller command-line tools can also be invoked independently:

```bash
python3 tests/test-queries/parser_oracle.py input.vcf.gz --output parser.json

python3 tests/test-queries/normalize_sparql_json.py \
  q01 raw/q01_record_density_1mb.sparql.json \
  --output normalized/q01_record_density_1mb.json

python3 tests/test-queries/compare_results.py \
  --parser parser.json \
  --sparql sparql.json \
  --output comparison.json
```

## Current model boundaries

The queries intentionally use only fields emitted by the current default
mapping. QUAL is not queried, INFO remains a raw string, ALT remains one lexical
literal, and GT is identified by the `/fmt/GT` IRI suffix because an explicit
FORMAT key is not yet emitted. Changes to those model decisions should update
the queries, fixture RDF, oracle contract, and hand-checked expected JSON in one
reviewed change.
