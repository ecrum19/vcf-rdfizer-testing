# VCF-RDFizer manuscript revision notes

**Revision date:** 2026-08-31  
**Primary manuscript:** `current_revised_marked.tex`  
**Bibliography:** `reference_revised.bib`  
**Machine-readable change record:** `manuscript_and_bibliography_revisions.patch`

## 1. Revision policy

The manuscript was revised conservatively against the supplied draft, bibliography, compression change log, testing README, semantic-equivalence query plan, and the author's newer one-chunk-at-a-time correction. No unfinished conversion, compression, query, or parser-comparison result was invented.

The marked manuscript uses:

- **blue text** for additions and substantively revised passages;
- **orange `[AUTHOR QUERY: ...]` statements** for facts, versions, run statuses, or measurements not established by the supplied artifacts;
- dated LaTeX comments such as `% [REVISED 2026-08-31: ...]` for source-level navigation; and
- a unified patch for exact line-by-line inspection.

The original six-file numbers are retained only as a clearly labeled **legacy baseline**. The current HDT/COTTAS pipeline, the four newly added VCFs, and the query workload have separate placeholder tables so old and new measurements cannot be silently combined.

## 2. Major manuscript changes

### A. COTTAS as a queryable compressed representation

The abstract, Introduction, Study Aims, workflow description, capability table, compression discussion, query-impact discussion, keywords, and bibliography now state that VCF-RDFizer offers both **HDT** and **COTTAS** as queryable compressed RDF representations.

The revision distinguishes:

- raw N-Triples;
- gzip/Brotli archival or transport artifacts;
- unwrapped HDT/COTTAS artifacts used for direct queries; and
- optionally gzip/Brotli-packaged HDT/COTTAS artifacts, which must be unpacked before querying.

The COTTAS citation was corrected to the formal paper:

> Arenas-Guerrero, J. and Ferrada, S. *COTTAS: Columnar Triple Table Storage for Efficient and Compressed RDF Management*. The Semantic Web — ISWC 2025, LNCS 16141, 313–331 (published 2026). DOI: `10.1007/978-3-032-09530-5_18`.

A separate `pycottas_2026` software/documentation entry was added. The earlier draft's sentence that cited COTTAS while calling it “Jelly” was replaced; Jelly is now identified separately as an RDF streaming serialization.

### B. Current HDT/COTTAS construction and storage optimization

The old whole-/batch-oriented HDT account was replaced by the current storage-aware design:

```text
.nt.gz aggregate -> make one raw chunk -> HDT/COTTAS conversion -> delete chunk -> repeat
```

The manuscript now documents that:

1. a plain or concatenated-gzip logical N-Triples aggregate is read incrementally;
2. chunk boundaries occur only after complete newline-terminated N-Triples records;
3. only one uncompressed RDF chunk exists at a time;
4. each selected representation consumes the chunk before it is deleted;
5. HDT parts are merged in a balanced HDTCat tree and the final HDT sidecar index is generated;
6. COTTAS parts are produced with `pycottas.rdf2cottas(..., disk=True)`, pairwise merged with `pycottas.cat(..., remove_input_files=True)`, and indexed on the final merged representation;
7. pycottas operations use isolated DuckDB scratch directories;
8. HDT/COTTAS outputs are validated by native streamed decoding and source-versus-decoded triple-count comparison without writing a full decoded RDF copy; and
9. representation parts, merge intermediates, indexes, and scratch data still consume workspace even though the full decompressed aggregate duplicate is removed.

The supplied lower-peak fallback values are included explicitly as fallback settings, not assumed benchmark defaults:

```text
--chunk-min-bytes 67108864
--chunk-target-bytes 134217728
--chunk-max-bytes 268435456
```

An author query requests the exact commit/release, dependency versions, default and actual chunk sizes, confirmation that `--build` was used, and the resulting Docker image digest.

### C. Six real-world bioinformatic and representation-equivalence queries

A new Methods subsection, query table, Results placeholder, and Discussion subsection were added for six paired operations:

| ID | Operation | Main purpose |
|---|---|---|
| Q1 | Record density by contig and 1-Mb window | Genomic distribution/QC and preservation of `CHROM`/`POS` |
| Q2 | Record-level allele-shape distribution | SNV/indel/MNV/multiallelic/SV-shape summaries and preservation of `REF`/`ALT` |
| Q3 | Biallelic SNV transition/transversion counts | Standard Ti/Tv QC and allele preservation |
| Q4 | FILTER state and exact FILTER-value distribution | Distinguishes `PASS`, `.`, and failed filters |
| Q5 | Per-sample genotype classes and call rate | Missingness/genotype composition and deep sample-call linkage |
| Q6 | GT-derived AC/AN distribution | Allele-count aggregation across sample genotypes without trusting INFO tags |

The manuscript now explains that:

- the same explicit scope must be implemented in SPARQL and the VCF-side oracle;
- raw N-Triples can be queried with Comunica's local-file package;
- HDT can be queried with Comunica's HDT package;
- COTTAS can be queried through pycottas' triple-pattern or RDFLib-compatible SPARQL path;
- cyvcf2 is the primary programmatic VCF oracle, with `bcftools query` used for exact FILTER lexical values and an optional `fill-tags` cross-check;
- primary assertions are exact equality of normalized integer counts;
- ratios are derived only after their counts match;
- query execution failure is not a semantic mismatch; and
- the workload tests **representation equivalence**, not variant-call truth, normalization, or clinical validity.

The text deliberately says that the study **defines** or **plans** these tests until versioned query result manifests are available.

### D. Expanded ten-file VCF corpus

A new ten-file corpus table documents the original six baseline inputs plus:

- `1000G_phase3_chr20.vcf.gz`: phased GRCh37 chromosome-20 VCF, 2,504 samples;
- `HGSVC2_freeze3_sv_alt.vcf.gz`: GRCh38 structural-variant VCF, 32 samples, sequence-resolved REF/ALT alleles;
- `HG004_GRCh38_1_22_v4.2.1_benchmark.vcf.gz`: single-sample GIAB benchmark VCF; and
- `HG005_GRCh38_1_22_v4.2.1_benchmark.vcf.gz`: single-sample GIAB benchmark VCF.

The first five provider/profile files retain `TBD` sample-count and assembly cells until their actual headers are inventoried. An author query also flags the major size discrepancy between the testing README's approximate compressed sizes and the older conversion table; the manuscript does not guess whether the old values are uncompressed sizes, different source files, or mislabeled units.

### E. SPARQL impact and parser-comparison plan

The Discussion now positions RDF/SPARQL as a **complementary access layer**, not an unconditional replacement for VCF/BCF tooling. It identifies potential uses including:

- cohort-level QC across independently produced VCF-derived graphs;
- combined variant/genotype and linked gene/phenotype/pharmacogenomic queries;
- knowledge-graph enrichment;
- multi-source querying through a common RDF model; and
- provenance- or governance-aware retrieval.

A fair comparison protocol is outlined. It must separate one-time conversion/index construction from repeated query cost, use identical biological scopes, distinguish indexed regional access from full scans, define cache/repetition/timeout conditions, record wall/CPU/RSS/result cardinality, and establish exact result equality before comparing speed.

No performance ranking between Comunica/N-Triples, Comunica/HDT, COTTAS, cyvcf2, or bcftools is asserted. The manuscript contains a `TBD` table for these data.

## 3. Author-query register

The manuscript contains **13 explicit author queries**:

1. **Line 162 — completed ten-file status:** confirm whether all ten inputs have completed current-`dev` conversion and whether the abstract can report measured ranges.
2. **Line 303 — pipeline figure:** regenerate `vcf2rdf.pdf` to show COTTAS, storage modes, balanced merges, validation, and packaging.
3. **Line 364 — reproducible current build:** provide the exact release/commit, HDT and pycottas versions, default/actual chunk sizes, `--build` confirmation, and Docker image digest.
4. **Line 408 — source-header inventory and size discrepancy:** provide exact assemblies, sample counts, VCF versions, and explain the old/new input-size discrepancy.
5. **Line 413 — four added files:** state which have completed RDF, HDT, COTTAS, and paired-query runs, with finished run names.
6. **Line 425 — current test environment:** confirm the workstation or provide complete current hardware/software details.
7. **Line 460 — active mapping:** verify whether QUAL and structured INFO/FORMAT representations exist in the exact `dev` mapping used.
8. **Line 461 — query implementation state:** confirm whether the six `.rq` files, cyvcf2 oracle, normalizer, and comparator are committed and executed or remain a specification.
9. **Line 504 — results strategy:** choose a complete current rerun or a clearly separated legacy/current presentation.
10. **Line 640 — query benchmark protocol:** define commands, indexes, engines, versions, cache conditions, repetitions, timeouts, concurrency, materialization, and build/query accounting.
11. **Line 687 — capability table:** resolve QUAL support and whether COTTAS indexes are fixed to `spo` or configurable.
12. **Line 744 — parser/performance comparator:** select cyvcf2/bcftools scope, index state, end-to-end versus repeated-query focus, and COTTAS-table placement.
13. **Line 780 — immutable availability reference:** replace the development branch with the final release/commit and container digest.

Line numbers refer to the delivered `current_revised_marked.tex` and may shift after editing.

## 4. Bibliography changes

Added or corrected citation keys include:

- `cottas_2025` — corrected COTTAS paper metadata;
- `pycottas_2026` — pycottas implementation/query interface;
- `cyvcf2_2017` — programmatic VCF oracle;
- `thousand_genomes_2015` — 1000 Genomes Phase 3 cohort;
- `hgsvc_2021` — HGSVC structural-variation resource;
- `giab_v421_2022` — GIAB v4.2.1 benchmark methodology;
- `comunica_file_docs_2026` — Comunica local-file package; and
- `comunica_hdt_docs_2026` — Comunica HDT package.

The manuscript now uses `\bibliography{reference_revised}`.

## 5. Validation performed

- All manuscript citation keys resolve to bibliography entries.
- No duplicate bibliography keys were found.
- No duplicate LaTeX labels were found.
- Braces and `\begin{...}`/`\end{...}` environments are balanced.
- The marked manuscript contains 20 revision environments and 13 author queries.
- A syntax-only article-class harness compiled successfully to a 16-page PDF with no fatal LaTeX errors.
- `biber --tool --validate-datamodel` parsed the revised bibliography successfully with exit status 0.

## 6. Remaining technical limitations

- The actual Springer Nature class file `sn-jnl.cls` was not available in the runtime, so the exact journal-class manuscript could not be compiled here.
- The original figure files `vcf2rdf.pdf` and `class-hierarchy-paper.png` were not attached, so visual figure verification and figure editing were not possible.
- The public GitHub `dev` branch could not be fetched from this runtime. Current implementation statements therefore rely on the supplied change log and, where they conflict, the author's newer one-chunk-at-a-time correction. The manuscript asks for an immutable final commit and image digest.
- Bibliography validation reports 30 pre-existing data-model warnings in older entries (for example, nonstandard fields, missing `booktitle`/journal fields, and malformed ISSN/ISBN values). The newly added entries parse, but a separate bibliography-cleanup pass is advisable before final submission.
- No current HDT/COTTAS measurements or paired-query outputs were supplied, so all such numerical cells remain explicitly `TBD`.
