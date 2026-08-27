# VCF-RDFizer semantic-equivalence testing guide

**Purpose:** define six bioinformatically meaningful tests that can be evaluated independently over (1) VCF-RDFizer N-Triples with SPARQL/Comunica and (2) the source VCF with an established VCF parser, then compared exactly.

**Prepared:** 2026-08-26  
**Vocabulary namespace:** `https://w3id.org/vcf-rdfizer/vocab#`  
**Primary VCF oracle proposed here:** `cyvcf2`, with `bcftools query` as the exact lexical oracle for FILTER when needed.

---

## 1. Executive recommendation

Use the following six-query suite, running each query **separately for each source VCF and its corresponding RDF output**:

| ID | Test | Main VCF/RDF fields exercised | Established analogue |
|---|---|---|---|
| Q1 | Record density by contig and 1 Mb window | `CHROM`, `POS` / `vcfr:chrom`, `vcfr:pos` | VCFtools `--SNPdensity`, generalized here from SNPs to all records [R3] |
| Q2 | Record-level allele-shape distribution | `REF`, `ALT` / `vcfr:ref`, `vcfr:alt` | Variant-class summaries, indel filtering, and indel-length summaries in VCFtools; GATK `CountVariants` [R3, R4] |
| Q3 | Biallelic SNV transition/transversion counts | `REF`, `ALT` | VCFtools `--TsTv-summary`; GATK VariantEval Ti/Tv [R3, R4] |
| Q4 | FILTER status and exact FILTER-code distribution | `FILTER` / `vcfr:filter` | VCFtools `--FILTER-summary`; raw/filtered count QC in GATK [R3, R4] |
| Q5 | Per-sample genotype classes and call rate | sample IDs and `GT` / `vcfr:sampleId`, GT `vcfr:fieldValue` | VCFtools `--missing-indv`; cyvcf2 genotype and `call_rate` facilities [R3, R5, R6] |
| Q6 | Genotype-derived alternate allele count/number distribution | biallelic `ALT`, sample `GT` | VCFtools allele counts/frequencies and bcftools `AC`/`AN`/`AF` calculation [R3, R8] |

These tests were selected because together they exercise:

1. record identity and genomic location;
2. exact REF/ALT lexical preservation;
3. a standard mutation-spectrum QC statistic;
4. VCF FILTER semantics;
5. sample linkage, FORMAT/GT extraction, phase normalization, and missingness; and
6. aggregation across all genotypes at a site.

The comparison contract should be **exact equality of integer counts**, not approximate biological plausibility. Compute ratios such as Ti/Tv and call rate only after the underlying integer counts match.

---

## 2. What this test can and cannot establish

### It can establish

- The converted RDF contains the same record locations, allele strings, FILTER values, sample identifiers, and GT values as the source VCF for the scopes explicitly defined below.
- RDF links such as `VCFRecord -> VariantCall -> SampleCall -> FormatFieldValue` are complete enough to reproduce standard VCF summaries.
- A SPARQL engine and a conventional VCF parser reach the same deterministic results from two representations of the same source.

### It cannot establish by itself

- That the source VCF calls are biologically correct relative to a reference genome or truth set.
- That variants are normalized, left-aligned, decomposed, or represented at a unique biological locus.
- Cross-file concordance among samples, because the ten inputs include different callers, assemblies, cohorts, and purposes.
- Clinical significance or functional effect, because the current core mapping does not expose an annotation model sufficient for those questions.

GIAB files can later support truth-concordance experiments, but that is a second validation layer requiring reference-aware normalization and interval handling.

---

## 3. Test corpus and applicability

The supplied project README identifies ten inputs [R14]:

| # | Canonical file | Profile relevant to this test |
|---:|---|---|
| 1 | `NG1N86S6FC.vcf.gz` | Personal WGS VCF; Sequencing.com provenance |
| 2 | `NG131FQA1I.vcf.gz` | Personal WGS VCF; Dante Labs provenance |
| 3 | `NB72462M.vcf.gz` | Personal WGS VCF; Nebula Genomics provenance |
| 4 | `60820188475559.vcf.gz` | Filtered-SNP profile |
| 5 | `60820188474283.vcf.gz` | Dante Labs WGS profile |
| 6 | `0GOOR_HG002.vcf.gz` | GIAB Truth Challenge submission |
| 7 | `1000G_phase3_chr20.vcf.gz` | GRCh37, chromosome 20, phased, 2,504 samples; principal multi-sample stress case |
| 8 | `HGSVC2_freeze3_sv_alt.vcf.gz` | GRCh38 structural variants, 32 samples; sequence REF/ALT alleles rather than only symbolic ALT values |
| 9 | `HG004_GRCh38_1_22_v4.2.1_benchmark.vcf.gz` | GIAB, single sample, GRCh38 chromosomes 1–22 |
| 10 | `HG005_GRCh38_1_22_v4.2.1_benchmark.vcf.gz` | GIAB, single sample, GRCh38 chromosomes 1–22 |

### Applicability rules

- **Q1–Q4 are required for every file.** They use mandatory fixed VCF fields represented by the current default mapping.
- **Q5–Q6 are required when the file has sample columns and a GT FORMAT field.** A query returning no rows must not automatically be called a pass; first inspect the VCF header and RDF preflight results to determine whether GT was genuinely absent or lost.
- Execute one dataset at a time. Do not combine GRCh37 and GRCh38 RDF into one correctness result.
- If one conversion produces multiple `.nt` partitions, treat all partitions belonging to that one VCF as the source set for a single Comunica query.

The first five inputs are described only at a profile/provider level in the supplied README. Their exact sample count, assembly, GT availability, and header conventions must therefore be discovered during preflight rather than assumed.

---

## 4. Audit of the current default RDF mapping

This plan targets the current default rules, not merely the vocabulary's intended model.

### Present in the default mapping

The current `VCFRecord` map emits:

- `vcfr:chrom` from `CHROM`;
- `vcfr:pos` as `xsd:integer` from `POS`;
- `vcfr:recordId` from `ID`;
- `vcfr:ref` from `REF`;
- `vcfr:alt` from the complete ALT field; and
- `vcfr:hasCall` to a `VariantCall` resource. [R11]

The current `VariantCall` map emits:

- `vcfr:filter` from `FILTER`;
- `vcfr:infoRaw` from the complete INFO field; and
- `vcfr:formatRaw` from the complete FORMAT field. [R11]

Sample data are represented as:

- `VariantCall -> vcfr:hasSampleCall -> SampleCall`;
- `SampleCall -> vcfr:sampleId`;
- `SampleCall -> vcfr:hasFormatValue -> .../fmt/{FORMAT_KEY}`; and
- the FORMAT value node has `vcfr:fieldValue`. [R11]

### Important current limitations

1. **QUAL is preserved in the intermediate `records.tsv`, but is not emitted by the current default RML mapping.** The TSV splitter writes a `QUAL` column and its values [R13], while the default `VariantCall` map currently maps FILTER, raw INFO, and raw FORMAT only [R11]. Therefore, a QUAL distribution or threshold query would test a known mapping omission rather than the generated RDF as currently designed.
2. **INFO keys are not emitted as structured value nodes by the default rules.** The ontology defines `InfoFieldValue` and `vcfr:hasInfoValue`, but the current default map exposes only `vcfr:infoRaw` [R11, R12].
3. **A FORMAT value's key is encoded in its IRI suffix, for example `/fmt/GT`, rather than emitted as an explicit predicate.** Q5 and Q6 consequently identify GT with `STRENDS(STR(?node), "/fmt/GT")`. This is workable but brittle.
4. **ALT is currently one literal containing the source ALT field.** Multi-allelic ALT is therefore a comma-separated lexical value, even though the vocabulary also permits repeated assertions or an ordered list [R11, R12]. The core tests deliberately do not try to split an arbitrary ALT list in SPARQL 1.1.
5. **The vocabulary recommends representing VCF's missing token as `"."^^vcfr:Null`; the current direct RML references normally emit the dot as a plain literal.** The queries below use `STR(...)`, so they work with either representation, but a separate conformance check should expose this difference [R12].

### Consequence for the test suite

The six core queries use only fields that the current mapping actually emits. QUAL-, DP-, GQ-, and structured INFO-based tests are deferred to the mapping-improvement section.

---

## 5. Exact comparison contract

A result is comparable only when the SPARQL and parser paths implement the same scope.

### Shared lexical rules

- Convert `REF` and `ALT` to uppercase only for classification; preserve their source lexical values for debugging.
- Reconstruct the parser-side ALT lexical field as the comma-joined `variant.ALT` list, using `.` for a missing ALT.
- Normalize phased and unphased GT separators to `/` only for genotype classification and allele counting. Preserve phase separately if a later test needs it.
- A GT containing any missing allele is `MISSING`, including `./.`, `.`, `0/.`, `./1`, and phased equivalents.
- `PASS`, `.`, and failed FILTER codes remain distinct. Under VCF semantics, `PASS` means all filters passed; `.` means filtering was not applied; any other nonempty value is one or more failed filter identifiers [R1].

### Numeric rules

- Compare integer counts exactly.
- Derive `Ti/Tv = transitions / transversions` only after both counts match. Represent division by zero as `null`, not infinity.
- Derive per-sample `callRate = called / total` only after class counts match.
- For Q6, compare exact `(AN, AC, siteCount)` tuples. Derive `AF = AC / AN` only for display; do not compare rounded floating-point AF bins as the primary assertion.

### Duplicate protection

The SPARQL uses `DISTINCT` at record or sample-call level where practical. This makes aggregate results robust to accidental duplicate triples across partitioned inputs, while still allowing preflight to report duplicates as a structural defect.

---

## 6. Recommended repository layout

```text
tests/semantic_equivalence/
├── README.md                         # operational notes for the test code
├── queries/
│   ├── q01_record_density_1mb.rq
│   ├── q02_variant_shape_counts.rq
│   ├── q03_titv.rq
│   ├── q04_filter_distribution.rq
│   ├── q05_sample_genotype_counts.rq
│   ├── q06_ac_an_distribution.rq
│   └── preflight_record_cardinality.rq
├── parser_oracle.py                  # cyvcf2 implementation
├── run_comunica.sh                   # executes all .rq files
├── normalize_sparql_json.py          # SPARQL JSON -> canonical rows
├── compare_results.py                # exact comparison + invariants
├── fixtures/
│   ├── edge_cases.vcf
│   └── edge_cases.expected.json
└── results/
    └── <dataset-id>/
        ├── manifest.json
        ├── parser.json
        ├── q01.sparql.json
        ├── ...
        └── comparison.json
```

Keep query files versioned. Record the SHA-256 of each query, the VCF, every RDF partition, the converter version/commit, vocabulary version/commit, Comunica version, parser version, and command line in `manifest.json`.

---

## 7. Environment and execution tools

### Comunica for local N-Triples

Comunica provides a separate local-file package, `@comunica/query-sparql-file`, and the `comunica-sparql-file` command [R9]. Query files can be supplied with `-f`, and SPARQL Results JSON can be requested with `-t application/sparql-results+json` [R10].

```bash
npm install --save-dev @comunica/query-sparql-file
npx comunica-sparql-file --version
```

### VCF oracle

`cyvcf2` is an HTSlib-backed Python VCF/BCF parser designed for fast variant and sample-level analysis. Its paper evaluates it on a large 1000 Genomes chromosome VCF, making it an appropriate primary oracle for the 2,504-sample input [R5]. Its API exposes REF, ALT, CHROM, POS, FILTER, FORMAT, genotypes, call rate, variant type helpers, and transition status [R6].

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install cyvcf2
python - <<'PY'
import cyvcf2
print(cyvcf2.__version__)
PY
```

Install `bcftools` as a second, established HTSlib-based oracle. It is particularly useful for an exact FILTER-field extraction and for optional `AC`/`AN` cross-checks [R7, R8].

```bash
bcftools --version
```

Pin tested versions in the actual implementation rather than relying indefinitely on unbounded package ranges.

---

## 8. Preflight checks

Run preflight before interpreting any of the six biological summaries.

### 8.1 VCF-side inventory

For every source VCF, record:

- VCF format version;
- sample count and sample IDs;
- contig declarations;
- reference/assembly metadata if present;
- presence of `GT`, `DP`, `GQ`, and relevant INFO declarations;
- record count; and
- SHA-256.

A minimal shell inventory can include:

```bash
bcftools view -h input.vcf.gz > header.txt
bcftools query -l input.vcf.gz > samples.txt
sha256sum input.vcf.gz
```

### 8.2 N-Triples syntax validation

Use an RDF parser independent of Comunica, for example Apache Jena RIOT:

```bash
riot --validate path/to/part-*.nt
```

A syntax failure is a conversion failure and should stop the semantic comparison for that dataset.

### 8.3 Record cardinality diagnostic

A valid current-model record should have exactly one CHROM, POS, REF, ALT, and `hasCall` value. The query below returns only anomalous records.

```sparql
PREFIX vcfr: <https://w3id.org/vcf-rdfizer/vocab#>

SELECT ?record
       (COUNT(DISTINCT ?chrom) AS ?chromCount)
       (COUNT(DISTINCT ?pos) AS ?posCount)
       (COUNT(DISTINCT ?ref) AS ?refCount)
       (COUNT(DISTINCT ?alt) AS ?altCount)
       (COUNT(DISTINCT ?call) AS ?callCount)
WHERE {
  ?record a vcfr:VCFRecord .
  OPTIONAL { ?record vcfr:chrom ?chrom }
  OPTIONAL { ?record vcfr:pos ?pos }
  OPTIONAL { ?record vcfr:ref ?ref }
  OPTIONAL { ?record vcfr:alt ?alt }
  OPTIONAL { ?record vcfr:hasCall ?call }
}
GROUP BY ?record
HAVING(
  COUNT(DISTINCT ?chrom) != 1 ||
  COUNT(DISTINCT ?pos) != 1 ||
  COUNT(DISTINCT ?ref) != 1 ||
  COUNT(DISTINCT ?alt) != 1 ||
  COUNT(DISTINCT ?call) != 1
)
LIMIT 100
```

Expected result: zero rows.

### 8.4 Position datatype diagnostic

```sparql
PREFIX vcfr: <https://w3id.org/vcf-rdfizer/vocab#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

SELECT ?record ?pos
WHERE {
  ?record a vcfr:VCFRecord ; vcfr:pos ?pos .
  FILTER(DATATYPE(?pos) != xsd:integer)
}
LIMIT 100
```

Expected result: zero rows under the current default mapping.

### 8.5 Missing-token conformance diagnostic

This is expected to reveal plain `"."` literals until the mapping implements the vocabulary's `vcfr:Null` policy.

```sparql
PREFIX vcfr: <https://w3id.org/vcf-rdfizer/vocab#>

SELECT ?s ?p ?o (DATATYPE(?o) AS ?datatype)
WHERE {
  ?s ?p ?o .
  FILTER(ISLITERAL(?o) && STR(?o) = ".")
  FILTER(DATATYPE(?o) != vcfr:Null)
}
LIMIT 100
```

Do not silently treat an expected known limitation as a pass. Record it explicitly as an expected conformance failure until fixed.

---

# 9. Core query specifications

## Q1. Record density by contig and 1 Mb window

### Bioinformatic rationale

Windowed variant density is a standard way to summarize the genomic distribution of calls. VCFtools exposes `--SNPdensity`; this query generalizes the same windowing pattern to **all VCF records** so it remains meaningful for indels and the HGSVC2 structural-variant file [R3]. It tests both `CHROM` and the integer interpretation of `POS`.

`windowIndex` is zero-based:

- `0` represents positions 1–1,000,000;
- `1` represents positions 1,000,001–2,000,000; and so on.

A rare VCF telomere position of `0`, allowed by the specification, produces `windowIndex = -1`; the parser uses the identical formula [R1].

### SPARQL

```sparql
PREFIX vcfr: <https://w3id.org/vcf-rdfizer/vocab#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

SELECT ?chrom ?windowIndex (COUNT(DISTINCT ?record) AS ?recordCount)
WHERE {
  ?record a vcfr:VCFRecord ;
          vcfr:chrom ?chrom ;
          vcfr:pos ?pos .

  BIND(FLOOR((xsd:integer(?pos) - 1) / 1000000) AS ?windowIndex)
}
GROUP BY ?chrom ?windowIndex
ORDER BY ?chrom ?windowIndex
```

### Parser-side operation

For each variant:

```python
window_index = (int(variant.POS) - 1) // 1_000_000
window_counts[(variant.CHROM, window_index)] += 1
```

### Expected output schema

```json
{"chrom": "20", "windowIndex": 0, "recordCount": 12345}
```

### Pass criterion

The sorted set of `(chrom, windowIndex, recordCount)` rows must be exactly equal.

### Useful invariant

The sum of `recordCount` across Q1 must equal the total number of VCF records and the total counts in Q2 and Q4.

---

## Q2. Record-level allele-shape distribution

### Bioinformatic rationale

Variant-class counts are common VCF QC outputs. VCFtools distinguishes SNPs/indels, supports indel filtering, and reports indel-length histograms; GATK VariantEval includes variant-count summaries [R3, R4]. The current RDF mapping stores the complete ALT column as one literal, so this test uses a deliberately explicit **record-shape classification** rather than pretending to perform allele-level decomposition.

Classification order matters:

1. `NO_ALT`: ALT is `.`.
2. `MULTIALLELIC`: raw ALT contains a comma.
3. `SYMBOLIC_OR_BREAKEND`: `*`, `<ID>`, or breakend bracket syntax.
4. `OTHER`: REF/ALT contains symbols outside `A/C/G/T/N` after the previous rules.
5. `SNV`: one-base REF and one-base ALT.
6. `MNV_OR_EQUAL_LENGTH_SUBSTITUTION`: equal lengths greater than one.
7. `INSERTION_SHAPE`: ALT is longer than REF.
8. `DELETION_SHAPE`: REF is longer than ALT.

The labels `INSERTION_SHAPE` and `DELETION_SHAPE` avoid overclaiming: non-normalized complex alleles can have the same length relationship without being a minimal normalized indel.

### SPARQL

```sparql
PREFIX vcfr: <https://w3id.org/vcf-rdfizer/vocab#>

SELECT ?variantClass (COUNT(DISTINCT ?record) AS ?recordCount)
WHERE {
  ?record a vcfr:VCFRecord ;
          vcfr:ref ?refLiteral ;
          vcfr:alt ?altLiteral .

  BIND(UCASE(STR(?refLiteral)) AS ?ref)
  BIND(UCASE(STR(?altLiteral)) AS ?alt)

  BIND(
    IF(?alt = ".", "NO_ALT",
      IF(CONTAINS(?alt, ","), "MULTIALLELIC",
        IF(
          ?alt = "*" ||
          CONTAINS(?alt, "[") ||
          CONTAINS(?alt, "]") ||
          (STRSTARTS(?alt, "<") && STRENDS(?alt, ">")),
          "SYMBOLIC_OR_BREAKEND",
          IF(
            !REGEX(?ref, "^[ACGTN]+$") || !REGEX(?alt, "^[ACGTN]+$"),
            "OTHER",
            IF(
              STRLEN(?ref) = 1 && STRLEN(?alt) = 1,
              "SNV",
              IF(
                STRLEN(?ref) = STRLEN(?alt),
                "MNV_OR_EQUAL_LENGTH_SUBSTITUTION",
                IF(
                  STRLEN(?ref) < STRLEN(?alt),
                  "INSERTION_SHAPE",
                  "DELETION_SHAPE"
                )
              )
            )
          )
        )
      )
    ) AS ?variantClass
  )
}
GROUP BY ?variantClass
ORDER BY ?variantClass
```

### Parser-side operation

Reconstruct raw ALT before classification:

```python
alt_lexical = ",".join(
    "." if allele is None else str(allele)
    for allele in (variant.ALT or [None])
)
variant_class = classify_variant_shape(variant.REF, alt_lexical)
variant_shape_counts[variant_class] += 1
```

The parser function must implement the same ordered rules as the SPARQL, not rely on a library's potentially different `is_indel` or `var_type` definition.

### Pass criterion

Every `(variantClass, recordCount)` row must match exactly.

### Dataset-specific value

Q2 is especially important for `HGSVC2_freeze3_sv_alt.vcf.gz`, whose structural variants are described as sequence alleles. A test that recognizes only `<DEL>`-style symbolic ALT would miss this stress case.

---

## Q3. Biallelic SNV transition/transversion counts

### Bioinformatic rationale

Ti/Tv is a standard call-set QC statistic in VCFtools and GATK VariantEval [R3, R4]. The test is restricted to records where REF and ALT are each exactly one of `A`, `C`, `G`, or `T`, and REF differs from ALT. Multi-allelic records are excluded automatically because their raw ALT contains more than one character.

Transitions are `A<->G` and `C<->T`; all other valid single-base substitutions are transversions.

### SPARQL

```sparql
PREFIX vcfr: <https://w3id.org/vcf-rdfizer/vocab#>

SELECT
  (COUNT(DISTINCT ?record) AS ?biallelicSnvCount)
  (SUM(IF(
    (?ref = "A" && ?alt = "G") ||
    (?ref = "G" && ?alt = "A") ||
    (?ref = "C" && ?alt = "T") ||
    (?ref = "T" && ?alt = "C"),
    1, 0
  )) AS ?transitionCount)
  (SUM(IF(
    (?ref = "A" && ?alt = "G") ||
    (?ref = "G" && ?alt = "A") ||
    (?ref = "C" && ?alt = "T") ||
    (?ref = "T" && ?alt = "C"),
    0, 1
  )) AS ?transversionCount)
WHERE {
  ?record a vcfr:VCFRecord ;
          vcfr:ref ?refLiteral ;
          vcfr:alt ?altLiteral .

  BIND(UCASE(STR(?refLiteral)) AS ?ref)
  BIND(UCASE(STR(?altLiteral)) AS ?alt)

  FILTER(
    REGEX(?ref, "^[ACGT]$") &&
    REGEX(?alt, "^[ACGT]$") &&
    ?ref != ?alt
  )
}
```

### Parser-side operation

```python
ref = variant.REF.upper()
alt = alt_lexical.upper()

if re.fullmatch(r"[ACGT]", ref) and re.fullmatch(r"[ACGT]", alt) and ref != alt:
    biallelic_snv_count += 1
    if (ref, alt) in {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}:
        transition_count += 1
    else:
        transversion_count += 1
```

### Pass criterion

All three integer counts must match exactly. Then compute:

```python
ti_tv_ratio = transition_count / transversion_count if transversion_count else None
```

### Invariants

- `transitionCount + transversionCount = biallelicSnvCount`.
- `biallelicSnvCount <= Q2["SNV"]` because Q2 permits `N` and does not independently require REF != ALT.

---

## Q4. FILTER status and exact code distribution

### Bioinformatic rationale

The VCF specification distinguishes `PASS`, `.`, and failed filter identifiers [R1]. Filtered-versus-passing counts are common QC metrics, and VCFtools supplies `--FILTER-summary` [R3]. Grouping by both broad status and exact lexical value tests that the full semicolon-separated FILTER field survived conversion.

### SPARQL

```sparql
PREFIX vcfr: <https://w3id.org/vcf-rdfizer/vocab#>

SELECT ?filterStatus ?filterLexical (COUNT(DISTINCT ?record) AS ?recordCount)
WHERE {
  ?record a vcfr:VCFRecord ;
          vcfr:hasCall ?call .
  ?call vcfr:filter ?filterLiteral .

  BIND(STR(?filterLiteral) AS ?filterLexical)
  BIND(
    IF(
      ?filterLexical = "PASS",
      "PASS",
      IF(?filterLexical = ".", "NOT_APPLIED", "FAILED")
    ) AS ?filterStatus
  )
}
GROUP BY ?filterStatus ?filterLexical
ORDER BY ?filterStatus ?filterLexical
```

### Parser-side operation

Do **not** use only `cyvcf2.Variant.FILTER`: its documented API returns `None` for both `PASS` and `.`, so it intentionally conflates two VCF meanings [R6]. Use one of these exact approaches:

**Preferred command-line lexical oracle:**

```bash
bcftools query -f '%FILTER\n' input.vcf.gz
```

Count the returned raw strings and classify them with the same three rules.

**Single-process cyvcf2 fallback:**

```python
def exact_filter_lexical(variant) -> str:
    values = list(variant.FILTERS or [])
    if values:
        return ";".join(values)

    # FILTERS is documented to be empty for '.', while FILTER itself conflates
    # PASS and '.'. Inspect the serialized VCF row to preserve the exact token.
    fields = str(variant).rstrip("\r\n").split("\t", 8)
    if len(fields) < 7:
        raise ValueError("Could not recover the VCF FILTER column")
    return fields[6]
```

For the 2,504-sample file, `bcftools query` is preferable because serializing a complete record merely to recover FILTER can be unnecessarily expensive.

### Pass criterion

Every `(filterStatus, filterLexical, recordCount)` row must match exactly.

### Invariant

The sum of all Q4 counts must equal the total record count from Q1 and Q2.

---

## Q5. Per-sample genotype classes and call rate

### Bioinformatic rationale

Per-sample genotype composition and missingness are standard VCF summaries. VCFtools reports per-individual missingness, while cyvcf2 exposes genotypes, genotype classes, called/unknown counts, and call rate [R3, R6]. This test exercises the deepest routinely useful path in the current RDF:

```text
VCFRecord -> VariantCall -> SampleCall -> FormatFieldValue(GT)
```

### Classification contract

After replacing `|` with `/`:

| Class | Rule |
|---|---|
| `NO_GT_FIELD` | The sample call has no `/fmt/GT` value node |
| `MISSING` | GT contains any `.` |
| `HAPLOID_REF` | Complete haploid GT `0` |
| `HAPLOID_ALT` | Complete haploid GT with any positive allele index |
| `HOM_REF` | Complete diploid `0/0` |
| `HOM_ALT` | Complete diploid with equal positive allele indices, e.g. `1/1` or `2/2` |
| `HET` | Complete diploid with unequal allele indices, e.g. `0/1` or `1/2` |
| `OTHER_PLOIDY` | Complete GT not matching haploid or diploid syntax |

Phased and unphased calls belong to the same class in this query. Phase preservation should be tested separately if it is a project requirement.

### SPARQL

```sparql
PREFIX vcfr: <https://w3id.org/vcf-rdfizer/vocab#>

SELECT ?sampleId ?genotypeClass (COUNT(DISTINCT ?sampleCall) AS ?callCount)
WHERE {
  ?sampleCall a vcfr:SampleCall ;
              vcfr:sampleId ?sampleId .

  OPTIONAL {
    ?sampleCall vcfr:hasFormatValue ?gtValueNode .
    FILTER(STRENDS(STR(?gtValueNode), "/fmt/GT"))
    ?gtValueNode vcfr:fieldValue ?gtLiteral .
  }

  BIND(
    IF(BOUND(?gtLiteral), REPLACE(STR(?gtLiteral), "[|]", "/"), "")
    AS ?gt
  )

  BIND(
    IF(
      !BOUND(?gtLiteral),
      "NO_GT_FIELD",
      IF(
        CONTAINS(?gt, "."),
        "MISSING",
        IF(
          REGEX(?gt, "^[0-9]+$"),
          IF(?gt = "0", "HAPLOID_REF", "HAPLOID_ALT"),
          IF(
            REGEX(?gt, "^[0-9]+/[0-9]+$"),
            IF(
              STRBEFORE(?gt, "/") = STRAFTER(?gt, "/"),
              IF(STRBEFORE(?gt, "/") = "0", "HOM_REF", "HOM_ALT"),
              "HET"
            ),
            "OTHER_PLOIDY"
          )
        )
      )
    ) AS ?genotypeClass
  )
}
GROUP BY ?sampleId ?genotypeClass
ORDER BY ?sampleId ?genotypeClass
```

### Parser-side operation

Use the raw allele indices from `variant.genotypes`. In cyvcf2 the final element of each genotype list is the phasing boolean [R6]. Convert negative/missing allele values to `None`.

```python
def genotype_alleles(raw_gt):
    if raw_gt is None:
        return None
    return tuple(
        None if allele is None or int(allele) < 0 else int(allele)
        for allele in raw_gt[:-1]  # final item is phased/unphased boolean
    )


def classify_genotype(alleles, has_gt_field: bool) -> str:
    if not has_gt_field:
        return "NO_GT_FIELD"
    if alleles is None or not alleles or any(a is None for a in alleles):
        return "MISSING"
    if len(alleles) == 1:
        return "HAPLOID_REF" if alleles[0] == 0 else "HAPLOID_ALT"
    if len(alleles) == 2:
        if alleles[0] == alleles[1]:
            return "HOM_REF" if alleles[0] == 0 else "HOM_ALT"
        return "HET"
    return "OTHER_PLOIDY"
```

### Call-rate derivation

For each sample:

```text
total  = sum(all genotype-class counts)
missing = MISSING + NO_GT_FIELD
called = total - missing
callRate = called / total, when total > 0
```

A complete polyploid call in `OTHER_PLOIDY` is considered called. This is separate from Q6, which deliberately restricts allele counting to supported haploid/diploid biallelic calls.

### Pass criterion

Every `(sampleId, genotypeClass, callCount)` row must match exactly. Derive call rate only after that equality is established.

### Performance note

This is likely the most expensive query for the 2,504-sample 1000 Genomes file. First validate it on the edge-case fixture and smaller/single-sample files, then run the complete source. Record wall time and maximum RSS, but do not turn a performance threshold into a semantic correctness criterion.

---

## Q6. Genotype-derived biallelic AC/AN distribution

### Bioinformatic rationale

Allele count and frequency are central population-genetics summaries. VCFtools reports per-site allele counts and frequencies; bcftools `fill-tags` can calculate `AC`, `AN`, and `AF` [R3, R8]. This query calculates AC and AN independently from GT rather than trusting possibly stale INFO tags. It therefore tests whether all relevant sample links and allele indices were preserved.

### Deliberate scope

A site is included only when:

- raw ALT is neither `.` nor comma-separated, so the site has exactly one ALT lexical value;
- at least one GT contributes to AN; and
- a contributing GT is complete haploid or diploid and contains only allele indices `0` and `1`.

The following do not contribute to AC or AN:

- missing or partially missing calls;
- polyploid calls;
- calls containing allele index `2` or higher; and
- records with multiple ALT values.

This restricted contract makes the SPARQL and parser calculation explicit and exactly reproducible across all inputs. It is a correctness test, not a claim that other genotypes are biologically unimportant.

### SPARQL

```sparql
PREFIX vcfr: <https://w3id.org/vcf-rdfizer/vocab#>

SELECT ?an ?ac (COUNT(DISTINCT ?record) AS ?siteCount)
WHERE {
  {
    SELECT ?record
           (SUM(?anContribution) AS ?an)
           (SUM(?acContribution) AS ?ac)
    WHERE {
      {
        SELECT DISTINCT ?record ?sampleCall ?gt
        WHERE {
          ?record a vcfr:VCFRecord ;
                  vcfr:alt ?altLiteral ;
                  vcfr:hasCall ?call .

          FILTER(
            STR(?altLiteral) != "." &&
            !CONTAINS(STR(?altLiteral), ",")
          )

          ?call vcfr:hasSampleCall ?sampleCall .
          ?sampleCall vcfr:hasFormatValue ?gtValueNode .
          FILTER(STRENDS(STR(?gtValueNode), "/fmt/GT"))
          ?gtValueNode vcfr:fieldValue ?gtLiteral .

          BIND(REPLACE(STR(?gtLiteral), "[|]", "/") AS ?gt)
        }
      }

      BIND(
        IF(
          REGEX(?gt, "^[01]$"),
          1,
          IF(REGEX(?gt, "^[01]/[01]$"), 2, 0)
        ) AS ?anContribution
      )

      BIND(
        IF(
          ?gt = "1",
          1,
          IF(
            ?gt = "0/1" || ?gt = "1/0",
            1,
            IF(?gt = "1/1", 2, 0)
          )
        ) AS ?acContribution
      )
    }
    GROUP BY ?record
  }

  FILTER(?an > 0)
}
GROUP BY ?an ?ac
ORDER BY ?an ?ac
```

### Parser-side operation

For each single-ALT site:

```python
an = 0
ac = 0

for alleles in complete_sample_alleles:
    if len(alleles) not in (1, 2):
        continue
    if any(a not in (0, 1) for a in alleles):
        continue
    an += len(alleles)
    ac += sum(alleles)

if an > 0:
    ac_an_site_counts[(an, ac)] += 1
```

### Expected output schema

```json
{"an": 5008, "ac": 1, "siteCount": 12345, "af": 0.0001996805}
```

`af` is optional display metadata and is not part of the exact primary key/value assertion.

### Pass criterion

Every `(AN, AC, siteCount)` tuple must match exactly.

### Optional third-oracle check

On a biallelic, haploid/diploid subset equivalent to the rules above, compare against values generated by bcftools:

```bash
bcftools +fill-tags input.vcf.gz -Ou -- -t AC,AN,AF \
  | bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t%AN\t%AC\t%AF\n'
```

Do not use this command as a substitute for matching the explicit scope. bcftools may support additional ploidies and multiallelic cases that the core SPARQL intentionally excludes.

---

## 10. Reference parser-oracle skeleton

The following skeleton implements the same six scopes in one sequential `cyvcf2` pass. It is intended as implementation guidance; add argument validation, logging, a manifest, and tests before production use.

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from cyvcf2 import VCF

TRANSITIONS = {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}


def alt_lexical(variant: Any) -> str:
    alleles = variant.ALT or [None]
    return ",".join("." if allele is None else str(allele) for allele in alleles)


def classify_variant_shape(ref_value: str, alt_value: str) -> str:
    ref = str(ref_value).upper()
    alt = str(alt_value).upper()

    if alt == ".":
        return "NO_ALT"
    if "," in alt:
        return "MULTIALLELIC"
    if (
        alt == "*"
        or "[" in alt
        or "]" in alt
        or (alt.startswith("<") and alt.endswith(">"))
    ):
        return "SYMBOLIC_OR_BREAKEND"
    if not re.fullmatch(r"[ACGTN]+", ref) or not re.fullmatch(r"[ACGTN]+", alt):
        return "OTHER"
    if len(ref) == 1 and len(alt) == 1:
        return "SNV"
    if len(ref) == len(alt):
        return "MNV_OR_EQUAL_LENGTH_SUBSTITUTION"
    if len(ref) < len(alt):
        return "INSERTION_SHAPE"
    return "DELETION_SHAPE"


def exact_filter_lexical(variant: Any) -> str:
    values = list(variant.FILTERS or [])
    if values:
        return ";".join(str(v) for v in values)

    # Exact fallback because cyvcf2 Variant.FILTER maps both PASS and '.' to None.
    fields = str(variant).rstrip("\r\n").split("\t", 8)
    if len(fields) < 7:
        raise ValueError("Could not recover FILTER from serialized VCF record")
    return fields[6]


def genotype_alleles(raw_gt: Any) -> tuple[int | None, ...] | None:
    if raw_gt is None:
        return None
    return tuple(
        None if allele is None or int(allele) < 0 else int(allele)
        for allele in raw_gt[:-1]  # final element is the phasing boolean
    )


def classify_genotype(
    alleles: tuple[int | None, ...] | None,
    *,
    has_gt_field: bool,
) -> str:
    if not has_gt_field:
        return "NO_GT_FIELD"
    if alleles is None or not alleles or any(a is None for a in alleles):
        return "MISSING"
    complete = tuple(int(a) for a in alleles if a is not None)
    if len(complete) == 1:
        return "HAPLOID_REF" if complete[0] == 0 else "HAPLOID_ALT"
    if len(complete) == 2:
        if complete[0] == complete[1]:
            return "HOM_REF" if complete[0] == 0 else "HOM_ALT"
        return "HET"
    return "OTHER_PLOIDY"


def sorted_rows(counter: Counter, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, count in sorted(counter.items()):
        key_tuple = key if isinstance(key, tuple) else (key,)
        row = dict(zip(keys, key_tuple, strict=True))
        row["count"] = int(count)
        rows.append(row)
    return rows


def run(vcf_path: Path) -> dict[str, Any]:
    reader = VCF(str(vcf_path), strict_gt=True)
    samples = list(reader.samples)

    density: Counter[tuple[str, int]] = Counter()
    variant_shapes: Counter[str] = Counter()
    filters: Counter[tuple[str, str]] = Counter()
    genotype_classes: Counter[tuple[str, str]] = Counter()
    ac_an: Counter[tuple[int, int]] = Counter()

    biallelic_snv_count = 0
    transition_count = 0
    transversion_count = 0
    total_records = 0

    for variant in reader:
        total_records += 1

        # Q1
        window_index = (int(variant.POS) - 1) // 1_000_000
        density[(str(variant.CHROM), window_index)] += 1

        # Q2
        raw_alt = alt_lexical(variant)
        variant_shapes[classify_variant_shape(variant.REF, raw_alt)] += 1

        # Q3
        ref = str(variant.REF).upper()
        alt = raw_alt.upper()
        if (
            re.fullmatch(r"[ACGT]", ref)
            and re.fullmatch(r"[ACGT]", alt)
            and ref != alt
        ):
            biallelic_snv_count += 1
            if (ref, alt) in TRANSITIONS:
                transition_count += 1
            else:
                transversion_count += 1

        # Q4
        raw_filter = exact_filter_lexical(variant)
        filter_status = (
            "PASS"
            if raw_filter == "PASS"
            else "NOT_APPLIED"
            if raw_filter == "."
            else "FAILED"
        )
        filters[(filter_status, raw_filter)] += 1

        # Q5 and Q6
        format_keys = [] if not variant.FORMAT else str(variant.FORMAT).split(":")
        has_gt = "GT" in format_keys

        allele_calls: list[tuple[int | None, ...] | None] = []
        if samples:
            if has_gt:
                raw_genotypes = list(variant.genotypes)
                if len(raw_genotypes) != len(samples):
                    raise ValueError(
                        f"Sample/genotype length mismatch at "
                        f"{variant.CHROM}:{variant.POS}"
                    )
                allele_calls = [genotype_alleles(gt) for gt in raw_genotypes]
            else:
                allele_calls = [None] * len(samples)

            for sample_id, alleles in zip(samples, allele_calls, strict=True):
                gt_class = classify_genotype(alleles, has_gt_field=has_gt)
                genotype_classes[(sample_id, gt_class)] += 1

        # Q6: one ALT; only complete haploid/diploid GT with allele indices 0/1.
        if raw_alt != "." and "," not in raw_alt and has_gt:
            an = 0
            ac = 0
            for alleles in allele_calls:
                if alleles is None or any(a is None for a in alleles):
                    continue
                complete = tuple(int(a) for a in alleles if a is not None)
                if len(complete) not in (1, 2):
                    continue
                if any(a not in (0, 1) for a in complete):
                    continue
                an += len(complete)
                ac += sum(complete)
            if an > 0:
                ac_an[(an, ac)] += 1

    reader.close()

    q1 = [
        {
            "chrom": chrom,
            "windowIndex": int(window),
            "recordCount": int(count),
        }
        for (chrom, window), count in sorted(density.items())
    ]

    q2 = [
        {"variantClass": cls, "recordCount": int(count)}
        for cls, count in sorted(variant_shapes.items())
    ]

    q3 = {
        "biallelicSnvCount": biallelic_snv_count,
        "transitionCount": transition_count,
        "transversionCount": transversion_count,
        "tiTvRatio": (
            transition_count / transversion_count if transversion_count else None
        ),
    }

    q4 = [
        {
            "filterStatus": status,
            "filterLexical": lexical,
            "recordCount": int(count),
        }
        for (status, lexical), count in sorted(filters.items())
    ]

    q5_rows = [
        {
            "sampleId": sample,
            "genotypeClass": gt_class,
            "callCount": int(count),
        }
        for (sample, gt_class), count in sorted(genotype_classes.items())
    ]

    per_sample: dict[str, Counter[str]] = {}
    for (sample, gt_class), count in genotype_classes.items():
        per_sample.setdefault(sample, Counter())[gt_class] += count

    q5_call_rates = []
    for sample, counts in sorted(per_sample.items()):
        total = sum(counts.values())
        missing = counts["MISSING"] + counts["NO_GT_FIELD"]
        called = total - missing
        q5_call_rates.append(
            {
                "sampleId": sample,
                "total": total,
                "called": called,
                "missing": missing,
                "callRate": called / total if total else None,
            }
        )

    q6 = [
        {
            "an": int(an),
            "ac": int(ac),
            "siteCount": int(count),
            "af": ac / an,
        }
        for (an, ac), count in sorted(ac_an.items())
    ]

    return {
        "source": str(vcf_path),
        "sampleCount": len(samples),
        "samples": samples,
        "totalRecords": total_records,
        "q01_record_density_1mb": q1,
        "q02_variant_shape_counts": q2,
        "q03_titv": q3,
        "q04_filter_distribution": q4,
        "q05_sample_genotype_counts": q5_rows,
        "q05_call_rates_derived": q5_call_rates,
        "q06_ac_an_distribution": q6,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("vcf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = run(args.vcf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
```

### Recommended adjustment for Q4 at scale

For the full 1000 Genomes file, run `bcftools query -f '%FILTER\n'` as a separate Q4 oracle instead of calling `str(variant)` for records whose FILTER list is empty. Keep the same JSON schema so the comparator is unchanged.

---

## 11. Running the SPARQL queries with Comunica

### One `.nt` file

```bash
npx comunica-sparql-file \
  path/to/dataset.nt \
  -f tests/semantic_equivalence/queries/q01_record_density_1mb.rq \
  -t application/sparql-results+json \
  > results/dataset/q01.sparql.json
```

### Multiple `.nt` partitions for one VCF

```bash
#!/usr/bin/env bash
set -euo pipefail

rdf_dir="$1"
query_file="$2"
output_file="$3"

mapfile -d '' sources < <(
  find "$rdf_dir" -type f -name '*.nt' -print0 | sort -z
)

if ((${#sources[@]} == 0)); then
  echo "No .nt files found under $rdf_dir" >&2
  exit 1
fi

npx comunica-sparql-file \
  "${sources[@]}" \
  -f "$query_file" \
  -t application/sparql-results+json \
  > "$output_file"
```

Only pass partitions belonging to one converted VCF. Comunica accepts multiple sources, but cross-dataset union is not the desired correctness unit [R9, R10].

### Capture execution conditions

```bash
/usr/bin/time -v \
  npx comunica-sparql-file "${sources[@]}" \
    -f "$query_file" \
    -t application/sparql-results+json \
    > "$output_file" \
    2> "${output_file%.json}.time.txt"
```

Save stdout and stderr separately. A timeout or out-of-memory failure is an execution result, not evidence that the RDF values differ.

---

## 12. Normalizing Comunica SPARQL JSON

SPARQL Results JSON represents integer values as strings plus datatypes. Normalize before comparison:

- Q1: `windowIndex`, `recordCount` -> integer.
- Q2: `recordCount` -> integer.
- Q3: all three values -> integer.
- Q4: `recordCount` -> integer.
- Q5: `callCount` -> integer.
- Q6: `an`, `ac`, `siteCount` -> integer.

Ignore binding order. Sort rows by these keys:

| Query | Sort key |
|---|---|
| Q1 | `(chrom, windowIndex)` |
| Q2 | `(variantClass)` |
| Q3 | single object |
| Q4 | `(filterStatus, filterLexical)` |
| Q5 | `(sampleId, genotypeClass)` |
| Q6 | `(an, ac)` |

Do not strip leading `chr` from contig names, coerce sample identifiers, split FILTER codes, or normalize allele strings differently on one path. Lexical differences are exactly what this test is meant to find.

---

## 13. Exact comparison and invariants

### Primary assertions

For every dataset:

```text
canonical(parser Qn) == canonical(SPARQL Qn)
```

Use a deep equality check and emit a structured diff containing missing rows, extra rows, and rows with differing counts.

### Cross-query invariants

Let `N` be the record count.

1. `sum(Q1.recordCount) = N`.
2. `sum(Q2.recordCount) = N`.
3. `sum(Q4.recordCount) = N`.
4. `Q3.transitionCount + Q3.transversionCount = Q3.biallelicSnvCount`.
5. For each sample, `sum(Q5.callCount across classes)` equals the number of RDF sample calls expected for that sample under the current conversion.
6. `sum(Q6.siteCount)` cannot exceed the count of single-ALT records with at least one supported complete GT.

Invariants do not replace parser/SPARQL equality; they catch internally inconsistent implementations on either side.

### Mismatch localization

When an aggregate differs, rerun a record-level query scoped to the affected contig/window. Preserve the RDF record IRI because its `/record/{ROW_ID}` suffix can be compared to the VCF stream ordinal used by the converter.

```sparql
PREFIX vcfr: <https://w3id.org/vcf-rdfizer/vocab#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

SELECT ?record ?chrom ?pos ?ref ?alt ?filter ?sampleId ?gt
WHERE {
  ?record a vcfr:VCFRecord ;
          vcfr:chrom ?chrom ;
          vcfr:pos ?pos ;
          vcfr:ref ?ref ;
          vcfr:alt ?alt ;
          vcfr:hasCall ?call .
  ?call vcfr:filter ?filter .

  OPTIONAL {
    ?call vcfr:hasSampleCall ?sampleCall .
    ?sampleCall vcfr:sampleId ?sampleId .
    OPTIONAL {
      ?sampleCall vcfr:hasFormatValue ?gtNode .
      FILTER(STRENDS(STR(?gtNode), "/fmt/GT"))
      ?gtNode vcfr:fieldValue ?gt .
    }
  }

  FILTER(?chrom = "20")
  FILTER(FLOOR((xsd:integer(?pos) - 1) / 1000000) = 10)
}
ORDER BY ?pos ?record ?sampleId
```

Prefer a small window or explicit position filter; a full record-level export from the 1000 Genomes RDF can be enormous.

---

## 14. Edge-case fixture required before full data

Create and version a compact VCF containing at least:

- PASS, `.`, one failed FILTER, and multiple failed FILTER codes;
- A>G transition and A>C transversion;
- one insertion-shape and one deletion-shape allele;
- an MNV;
- multi-allelic ALT;
- symbolic ALT, spanning-deletion `*`, and a breakend ALT;
- no ALT (`.`);
- phased and unphased diploid GT;
- haploid GT;
- `0/0`, `0/1`, `1/0`, `1/1`, and `1/2`;
- fully and partially missing GT;
- polyploid GT; and
- one record whose FORMAT lacks GT.

Convert this fixture through exactly the same VCF-RDFizer path used for the ten datasets. Hand-calculate expected Q1–Q6 output and make it a unit-test oracle. This catches disagreements in category definitions before a multi-hour full-data run.

---

## 15. Suggested execution order

1. Pin and record converter, mapping, vocabulary, Comunica, Node.js, cyvcf2, HTSlib/bcftools, and OS versions.
2. Build and pass the edge-case fixture.
3. Run VCF and RDF preflight for all ten inputs.
4. Run Q1–Q4 on every input.
5. Run Q5–Q6 on single-sample/smaller inputs.
6. Run Q5–Q6 on HGSVC2 (32 samples).
7. Run Q5–Q6 on 1000 Genomes (2,504 samples), capturing resource use.
8. Normalize, compare, and check invariants.
9. Investigate every mismatch at record level.
10. Publish result manifests and machine-readable diffs with the benchmark output.

Q1–Q4 are expected to be substantially lighter than Q5–Q6. This order provides useful failures early without weakening the requirement to run the complete suite.

---

## 16. Acceptance criteria

A dataset passes semantic-equivalence validation when:

- the VCF and every `.nt` partition have recorded hashes;
- N-Triples syntax validation passes;
- record cardinality and POS datatype preflight return no anomalies;
- Q1–Q4 exactly match the VCF oracle;
- Q5–Q6 exactly match when GT is present;
- an empty Q5/Q6 result is explained by verified source structure rather than assumed;
- all cross-query invariants hold;
- no mismatch is dismissed because a result “looks biologically plausible”; and
- known vocabulary/mapping conformance deviations, such as plain-dot missing values, are reported separately.

A query execution failure should be reported as `EXECUTION_FAILED`, not `MISMATCH` or `PASS`.

---

## 17. Recommended mapping improvements

These are not required to run the six core tests, but they would enable stronger future validation.

### 17.1 Emit QUAL

The intermediate TSV already contains `QUAL` [R13]. Add a predicate-object map under `VariantCallMap`:

```turtle
rr:predicateObjectMap [
  rr:predicate vcfr:qual ;
  rr:objectMap [ rml:reference "QUAL" ]
] ;
```

A production mapping should preserve `.` as `vcfr:Null` while typing valid numeric QUAL values appropriately. A direct unconditional numeric datatype would fail on `.`.

This enables:

- QUAL missingness;
- QUAL threshold counts;
- quality distributions; and
- Ti/Tv by QUAL, analogous to VCFtools `--TsTv-by-qual` [R3].

### 17.2 Emit an explicit FORMAT key

Add a property such as `vcfr:fieldKey "GT"` to `FormatFieldValue`. Then Q5/Q6 can match a semantic field identifier rather than parse an IRI suffix.

### 17.3 Structure INFO values

Use `vcfr:hasInfoValue`, `InfoFieldValue`, an explicit key, and typed values. Prioritize common reserved tags such as `AC`, `AN`, `AF`, `DP`, and structural-variant fields. Then compare:

- source INFO AC/AN/AF;
- genotype-derived AC/AN/AF; and
- RDF structured values.

This three-way test can detect both conversion errors and stale/inconsistent source INFO annotations.

### 17.4 Represent ALT alleles individually and preserve order

Emit one allele node/assertion per ALT item with an explicit index. That would permit allele-level classification and correct handling of Number=A, Number=R, and genotype allele indexes without nonportable string splitting.

### 17.5 Implement the vocabulary missing-value policy

Serialize the VCF missing token as `"."^^vcfr:Null` where appropriate [R12]. Add SHACL tests to ensure numeric properties never receive a fabricated zero for missing values.

### 17.6 Link values to header definitions

Use `vcfr:declaredBy` for INFO, FORMAT, FILTER, and symbolic ALT usages. This would allow tests that every used key/code has a matching header declaration.

---

## 18. Strong optional follow-up queries after mapping improvements

1. **QUAL distribution and missingness**: compare exact lexical/missing counts and numeric bins.
2. **DP and GQ distributions per sample**: test typed FORMAT values and sample linkage.
3. **INFO-versus-GT AC/AN consistency**: verify source annotations and conversion independently.
4. **Header declaration coverage**: every INFO/FORMAT/FILTER/ALT usage resolves through `vcfr:declaredBy`.
5. **Ordered multiallelic allele counts**: calculate AC for allele indexes 1..N.
6. **GIAB concordance**: after normalization, compare calls to an appropriate truth set and confident regions. This is biological validation, not merely representation equivalence.

---

## 19. Why these queries are defensible in a methods paper

The suite is not a collection of arbitrary demonstration queries:

- windowed density, variant counts, Ti/Tv, FILTER summaries, missingness, and allele frequencies/counts are established VCF analysis/QC operations [R2–R4];
- the parser is a published, HTSlib-backed VCF analysis library evaluated on large multi-sample VCF data [R5, R6];
- the query scopes are stated precisely enough to reproduce independently;
- all primary assertions compare integers exactly;
- difficult VCF semantics—multi-allelic ALT, symbolic/breakend alleles, missing genotypes, phasing, ploidy, PASS versus `.`, and sequence-encoded SV alleles—are handled explicitly rather than hidden behind tool-specific shorthand; and
- the suite covers both shallow record fields and deep sample-level graph paths.

The result can therefore be reported as a **representation-equivalence validation workload**. It should not be described as proof of variant-call accuracy unless a separate truth-concordance analysis is performed.

---

# References

**[R1]** Global Alliance for Genomics and Health / SAMtools-HTS specifications. *The Variant Call Format Specification, VCF v4.5 and BCF v2.2*, 25 February 2026. https://samtools.github.io/hts-specs/VCFv4.5.pdf

**[R2]** Danecek P, Auton A, Abecasis G, et al. *The variant call format and VCFtools*. Bioinformatics. 2011;27(15):2156–2158. https://doi.org/10.1093/bioinformatics/btr330

**[R3]** VCFtools documentation, v0.1.16. Relevant operations include `--SNPdensity`, `--TsTv-summary`, `--FILTER-summary`, `--missing-indv`, `--freq`, and `--counts`. https://vcftools.github.io/man_latest.html

**[R4]** Broad Institute GATK. *VariantEval*: general-purpose variant evaluation including raw/filtered SNP counts and transition/transversion ratio. https://gatk.broadinstitute.org/hc/en-us/articles/9570243836187-VariantEval-BETA

**[R5]** Pedersen BS, Quinlan AR. *cyvcf2: fast, flexible variant analysis with Python*. Bioinformatics. 2017;33(12):1867–1869. https://doi.org/10.1093/bioinformatics/btx057

**[R6]** cyvcf2 API documentation. Relevant fields include CHROM, POS, REF, ALT, FILTER/FILTERS, FORMAT, genotypes, call rate, and transition/type helpers. https://brentp.github.io/cyvcf2/docstrings.html

**[R7]** SAMtools project. *bcftools manual*. https://samtools.github.io/bcftools/bcftools.html

**[R8]** SAMtools project. *bcftools `fill-tags` plugin*, including AC, AF, AN, missingness, and type calculations. https://samtools.github.io/bcftools/howtos/plugin.fill-tags.html

**[R9]** Comunica. *Querying local files from the command line*. https://comunica.dev/docs/query/getting_started/query_cli_file/

**[R10]** Comunica. *Querying from the command line*, including `-f`, multiple sources, and SPARQL Results JSON output. https://comunica.dev/docs/query/getting_started/query_cli/

**[R11]** VCF-RDFizer default RML mapping. Relevant sections: `VCFRecordMap`, `VariantCallMap`, `SampleCallMap`, and `FormatFieldValueMap`. https://github.com/ecrum19/VCF-RDFizer/blob/main/rules/default_rules.ttl

**[R12]** VCF-RDFizer vocabulary ontology. Relevant terms include `VCFRecord`, `VariantCall`, `SampleCall`, `chrom`, `pos`, `ref`, `alt`, `qual`, `filter`, `infoRaw`, `formatRaw`, `hasFormatValue`, `fieldValue`, and `vcfr:Null`. https://github.com/ecrum19/VCF-RDFizer-vocabulary/blob/main/ontology/vcf-rdfizer-vocabulary.ttl

**[R13]** VCF-RDFizer VCF-to-TSV splitter. The records TSV includes CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO, FORMAT, and sample columns. https://github.com/ecrum19/VCF-RDFizer/blob/main/src/vcf_as_tsv.sh

**[R14]** Supplied project `README.md`, section **Test Data (VCF Inputs)**, especially the dataset table and the notes describing the 1000 Genomes, HGSVC2, HG004, and HG005 profiles.

---

## Appendix A. Minimal result manifest example

```json
{
  "datasetId": "1000G_phase3_chr20",
  "sourceVcf": {
    "path": "vcf_data/1000G_phase3_chr20.vcf.gz",
    "sha256": "..."
  },
  "rdfSources": [
    {"path": "rdf/part-00000.nt", "sha256": "..."},
    {"path": "rdf/part-00001.nt", "sha256": "..."}
  ],
  "converter": {"version": "...", "gitCommit": "..."},
  "mapping": {"path": "rules/default_rules.ttl", "sha256": "..."},
  "vocabulary": {"versionIri": "...", "gitCommit": "..."},
  "tools": {
    "node": "...",
    "comunicaQuerySparqlFile": "...",
    "python": "...",
    "cyvcf2": "...",
    "bcftools": "..."
  },
  "queries": {
    "q01": {"path": "queries/q01_record_density_1mb.rq", "sha256": "..."},
    "q02": {"path": "queries/q02_variant_shape_counts.rq", "sha256": "..."},
    "q03": {"path": "queries/q03_titv.rq", "sha256": "..."},
    "q04": {"path": "queries/q04_filter_distribution.rq", "sha256": "..."},
    "q05": {"path": "queries/q05_sample_genotype_counts.rq", "sha256": "..."},
    "q06": {"path": "queries/q06_ac_an_distribution.rq", "sha256": "..."}
  }
}
```

## Appendix B. Reporting table template

| Dataset | Preflight | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Notes |
|---|---|---|---|---|---|---|---|---|
| `NG1N86S6FC` |  |  |  |  |  |  |  |  |
| `NG131FQA1I` |  |  |  |  |  |  |  |  |
| `NB72462M` |  |  |  |  |  |  |  |  |
| `60820188475559` |  |  |  |  |  |  |  |  |
| `60820188474283` |  |  |  |  |  |  |  |  |
| `0GOOR_HG002` |  |  |  |  |  |  |  |  |
| `1000G_phase3_chr20` |  |  |  |  |  |  |  |  |
| `HGSVC2_freeze3_sv_alt` |  |  |  |  |  |  |  |  |
| `HG004_GRCh38_1_22_v4.2.1_benchmark` |  |  |  |  |  |  |  |  |
| `HG005_GRCh38_1_22_v4.2.1_benchmark` |  |  |  |  |  |  |  |  |

Suggested status values: `PASS`, `MISMATCH`, `NOT_APPLICABLE_VERIFIED`, `EXECUTION_FAILED`, and `BLOCKED_BY_PREFLIGHT`.
