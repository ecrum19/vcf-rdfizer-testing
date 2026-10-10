# Benchmark design

How the evaluation reported in the BioMedSem 2026 manuscript was designed and
run, organized by the paper's three research questions. Each section names the
script that implements it, what was varied and held fixed, the cells that ran,
how the runs are analyzed, and where the paper reports the result. The scripts'
comments cite these sections as "Plan §".

| RQ | Question | Sections | Scripts |
| --- | --- | --- | --- |
| RQ1 | Which aspects of VCF information are preserved and verifiable? | §1 | `06`, `08`, `09`, `07` (versions), `11`, `12`; the consumer WGS validation run |
| RQ2 | What does the explicit representation in RDF enable in a linked, policy-aware workflow? | §2 | `17` |
| RQ3 | Under which workloads and representation choices are the costs practical? | §3 | `18`, `04`, `03`, `01`, `05`, `07` (INFO, header), `10`, `13`, `14`, `15`, `16` |
| | Shared by all three | §4 | `00`, `02`, `run_all.sh` |

Figure and table numbers are the manuscript's (main text) and the supplement's
(prefix S). [`README.md`](README.md) lists every script with its records, and
the run records are in [`../benchmark-results/`](../benchmark-results/README.md).
Numbers belong to the paper; this document gives the design that produced
them. The plan written before the campaign, which used a different section
numbering, can be read with `git show 66f53577:benchmarks/DESIGN.md`. The table at the end maps
its section numbers, which archived run logs print, to these.

**The base campaign** is experiments `00`–`13`: 143 cells in 12 families
(`00` and `02` prepare the others and are not counted), all with the published
VCF-RDFizer v3.1.0 image (Table S12). Experiments `14`–`18`, and four results
made by small drivers (listed in `README.md`), are reported separately
(Table S13). They used v3.3.1, except the default-profile mutation rerun and the
N-Triples-only rerun, which used v3.1.0.

---

## 1. RQ1: Which aspects of VCF information are preserved and verifiable?

The evidence is VCF-RDFizer's validation layer, run against graphs whose
correct content is known from the source VCF:
- **Source comparison.** Thirteen SPARQL queries (Q1–Q13) are answered from the
  graph and again, independently, from the VCF with cyvcf2 (and bcftools for
  exact FILTER text). Answers must be equal after normalization. Fourteen
  preflight checks run first. Table S5 defines the queries.
- **Structural validation.** SHACL shapes check structure the queries do not
  observe: the default profile (cardinality, datatypes) and two deeper profiles
  (uniqueness, value agreement).
- **Engines.** QLever, which builds its own index from the decoded graph, and
  three Comunica engines: over N-Triples, over HDT, and over COTTAS through a
  DuckDB-backed engine.

In the base campaign, 78 validation runs come from five families: difficult
inputs (20), covering set (23), equivalence (16), query cost (18) and modes (1).
Each artifact a run validates (gzip-framed N-Triples, HDT, COTTAS) is decoded and
its triple count compared with the source graph's.

### 1.1 Equivalence across encodings, artifacts and engines (`06`)

**Question.** Does every encoding the options produce answer the same
questions identically to the source VCF?

**Design.** One small input, so that every engine can run on every artifact:
`test-10k.vcf`, a 10,000-line, 9,986-record single-sample fixture.
- Four encoding cells: `plain` and `space-optimized` storage, each with
  `expanded` and `condensed` samples. Each converts to gzip-framed N-Triples,
  partitioned HDT and COTTAS, and validates all three
  (`--validate-artifacts all`) on all four engines (`--validation-engine all`).
  The graphs hold 0.96M triples expanded and 0.79M condensed.
- Two mechanism cells and two refusal cells (§1.2).

Q5 and Q6 traverse the sample layer, so they are where the condensed profile
could have failed. COTTAS is queried through the DuckDB-backed Comunica
engine; the earlier pycottas/rdflib path stalled on Q5 (Table S16).

**Reported in** Section 3.1 and Section S10.

### 1.2 The HDT-strategy constraints, and the mechanism check (`06`; shapes `01` and `11`)

`--hdt-strategy single` builds HDT in one `rdf2hdt` pass. It cannot read the
gzip aggregate that space-optimized storage writes, and COTTAS always needs
bounded chunks, so the tool refuses `single` beside `space-optimized` storage
and beside COTTAS (exit 2). `single` is therefore legal only with `plain`
storage and HDT without COTTAS. This shapes three experiments:
- **`06` asserts both refusals** (`refusal__single_with_space_optimized`,
  `refusal__single_with_cottas`). A refusal that succeeded would fail the cell.
- **`06` runs the mechanism check.** HDT built by `single` and by `partitioned`
  (chunks merged with `hdtc`) from the same graph, in `plain` storage, both
  validated on all four engines. Equal answers show that the partitioned merge,
  the default, loses nothing.
- **`01` pins `partitioned`,** so storage mode is the only factor (§3.4).
  **`11`'s rows place `single`** only where it is legal (§1.6).

No HDT-strategy timing comparison was run. Below the chunk threshold
(128 MiB of uncompressed RDF) the two strategies converge, and above it only
`partitioned` scales.

### 1.3 Fault sensitivity: the mutation score (`08`; the default-profile rerun)

**Question.** Would the validation layer notice a corrupted graph?

**Design.** The tool's mutation test (`test/validation_mutations.py` in
VCF-RDFizer) applies 113 deliberate corruptions to a small converted graph:
coordinates, alleles, filters, metadata, phasing, sample indexes and
relationships. Two controls must still pass. It counts which corruptions each
layer detects:
- **Queries only:** `08`'s `mutation_score` cell.
- **Queries and all three shape profiles:** `08`'s `mutation_score__shacl_full`.
- **Queries and the default profile:** a rerun outside the campaign on
  vcf-bench-2, with the same release (`review-runs/mutation__core`, with a
  queries-only control, `mutation__none`).

These cells run the tool's test suite on the host, not in the conversion
container, so they record the harness commit rather than an image.

**Reported in** Figure 3b, Table S6 and Section S4.3.

### 1.4 Determinism, round trip, index idempotence (`08`)

All three on the 100,000-record HG005 slice, compared by sorted triple set
(`analysis/compare_graphs.py`), never by file checksum (§3.4 explains why the
bytes differ):
- **Determinism:** two identical conversions to N-Triples must give identical
  sorted triples.
- **Round trip:** convert, compress (gzip-framed N-Triples and HDT), decompress;
  the triples must be unchanged.
- **Index idempotence:** build HDT, re-index it with `--mode index`; the artifact
  must be unchanged.

**Reported in** Table S6.

### 1.5 Difficult inputs and declared VCF versions (`09`; `07`'s version cells)

**Difficult inputs (`09`).** Eleven fixtures, each a legal or deliberately broken
VCF that a converter can plausibly get wrong:
- a breakend, symbolic alleles, high ploidy, half and haploid calls;
- missing values, FILTER variants, a declared FORMAT key absent from the
  records, CRLF line endings;
- a file with no records, a sites-only file that declares FORMAT, and a
  truncated gzip.

Each is converted to HDT and validated on Comunica. Converting it and being
refused with a diagnostic are both acceptable; a crash or a silently wrong graph
is not. [`fixtures/FIXTURES.json`](fixtures/FIXTURES.json) records each fixture's
expectation, and `analysis/datasets.py awkward` pairs observed with expected.

The same experiment converts a 100-record fixture and links it with the three
demonstration linkers (`gene-demo`, `rsid-dbsnp`, `rsid-ensembl`). A
custom-mapping cell records a skip, because no rules file was supplied.

**Declared versions (`07`).** Six fixtures declaring VCF 4.1–4.5, or no version,
are converted with `--vcf-version` set to match (`auto` for the undeclared
file). The version selects a conformance overlay: per-ALT tuple repetition,
local-allele and base-modification FORMAT fields. The undeclared file must
convert without claiming a version class it cannot verify.

**Reported in** Section S7 and Table S15.

### 1.6 Every option value and every mode (`11`, `12`)

**Covering set (`11`).** Ten rows on `test-1k.vcf` cover every value of seven
options and every legal pair of values. Each row validates every artifact,
with the default shapes, on Comunica:

| Row | Samples | INFO | Storage | RDF compression | Representations | Artifact compression | HDT strategy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | expanded | structured | space-optimized | gzip | hdt,cottas | gzip | partitioned |
| 2 | condensed | raw | plain | brotli | hdt | brotli | single |
| 3 | expanded | raw | plain | brotli | hdt | gzip | auto |
| 4 | condensed | structured | space-optimized | gzip | cottas | brotli | auto |
| 5 | expanded | structured | space-optimized | brotli | hdt,cottas | brotli | partitioned |
| 6 | condensed | raw | plain | gzip | cottas | gzip | partitioned |
| 7 | expanded | structured | plain | gzip | hdt | gzip | single |
| 8 | condensed | raw | plain | gzip | hdt,cottas | gzip | auto |
| 9 | expanded | raw | space-optimized | gzip | hdt | gzip | partitioned |
| 10 | expanded | raw | plain | brotli | cottas | gzip | partitioned |

- **Pair coverage is checked, not asserted.** `analysis/datasets.py coverage`
  re-derives it from the cells. The only uncovered pairs are the prohibited ones
  (§1.2): `single` with space-optimized storage, with COTTAS, or with
  `hdt,cottas`.
- **Row 3 exercises `auto`'s HDT decision.** `auto` is a no-op in a row
  without HDT.
- **Not a codec comparison.** Gzip and Brotli are exercised in both compression
  roles, but their ratios and throughput are not compared.

**Modes (`12`).** Each operating mode runs once on its own on `test-1k.vcf` and
its artifacts:
- `tsv`;
- conversion with validation off (Phase A, §4.3);
- `--mode validation` on Phase A's N-Triples (Phase B);
- `compress`, `decompress`;
- HDT and COTTAS indexing.

**Reported in** Section S10.

### 1.7 Validation beyond the base campaign

- **Consumer WGS validation run.** The first 250,000 records of the
  `NG131FQA1I` consumer WGS VCF (58,231,176 triples, expanded profile), validated
  with v3.3.1 on QLever. Default shapes are checked in record batches, 117
  batches on four workers. It is the driver `run_v331.sh`'s job `consumer_wgs`.
  The v3.1.0 runs on the same slice, which the supplement cites for the oracle's
  corrections, are on the repository's `legacy` branch. Reported in Figure 3a
  and Section S4.2.
- **Large graphs.** Large-graph retrieval (§3.10) compares the thirteen answers
  with cyvcf2, without SHACL, on graphs of 170.9M and 657.4M triples. Reported in
  Figure 3a.

---

## 2. RQ2: What does the explicit representation in RDF enable in a linked, policy-aware workflow?

One workflow, experiment `17`, built and run as specified in
[`use_case/acmg/README.md`](use_case/acmg/README.md). Every stage used
VCF-RDFizer v3.3.1. Arms 1–2 ran on vcf-bench-1 and Arms 3–4 on vcf-bench-2.

### 2.1 The question, and two routes that must agree

Which participant–variant–gene matches connect an observed allele to a ClinVar
classification in the 81 genes of ACMG SF v3.2, and which matches may each
requester receive? ClinVar (release 2026-09-13) records need at least one
review star. Pathogenic and likely pathogenic matches are reported separately,
but not used as a filter.

| | RDF route | Conventional route |
| --- | --- | --- |
| Identity | Converted VCFs and ClinVar linked by SPDI identifier | Contigs renamed to ClinVar's, then `bcftools annotate` |
| Release | One checked release view per requester, from ODRL rules | The same rules, hand-written in Python |
| Question | One SPARQL query per requester on QLever | `bcftools view` and `query`, then the script |

Both routes read the same derived inputs and the same case definition
(`use_case.json`); linking, policy evaluation and querying are implemented
separately. **The gate:** the sorted participant, gene, contig, position and
allele tuples must agree for every requester before any timing is compared
(`compare.py`).

### 2.2 Four arms

| Arm | Input | Tests |
| --- | --- | --- |
| 1 | Gene-span slices (the ACMG regions) of five single-sample VCFs | Heterogeneous inputs |
| 2 | 104 unrelated high-coverage 1000 Genomes participants, with population frequencies stored once in a sites-only graph | Cohort breadth, and joining a third resource |
| 3 | The complete HG005 VCF | Complete-VCF scale; its matches must equal its Arm 1 matches |
| 4 | The complete NB72462M VCF, four requesters | Fine-grained release |

The simulated consents combine file permissions, withdrawals, gene panels, a
region and one named variant. Arm 4's rules each target a different kind of
selection, so every one of its four requesters receives a different, non-empty
view.

### 2.3 Linking

- **SPDI linker:** gives each normalized record a global variant identifier,
  shared with ClinVar.
- **Gene linker** (`ensembl-genes-grch38`): links records to Ensembl genes by
  locus. The gene-panel rules select on these links.
- **MyVariant.info tier** (Arm 1's two PGP files): confirms rsIDs against the
  live service. It replays the 21 responses recorded on 2026-09-28
  (`use_case/acmg/myvariant-cache/`), and `compare_myvariant.py` compares its
  links with `rsid-dbsnp`'s.

Reported in Table S7.

### 2.4 Release views, their checks, and where they run

The policy plug-in streams one release view per requester and checks it before
use: against the policy, and against an oracle graph written directly from the
VCF text beside the same link graphs. Every arm also compares the records each
view releases with the count the conventional route releases to that requester.

Release and querying run on QLever, never on an in-memory graph. Arm 4's graph
alone holds 1.2 billion triples, so an in-memory graph could not hold every arm.

**Reported in** Section 3.2, Figure 4 and Tables S8–S9.

### 2.5 Authoring effort (`use_case/acmg/effort.py`)

`effort.py` counts the non-blank, non-comment lines each route asks its author
to write for Arm 1, with rules and data counted apart. It then applies four
changes to both routes as real edits:
- a withdrawal;
- a requester with a new purpose;
- a cardiac panel in place of the cancer one;
- a rule on one variant.

After each edit, both routes must still release the same records to every
requester on a fixture. The result is committed as `effort.json`. Reported in
Table S10.

### 2.6 Stage costs

Conversion and linking are paid once per arm. View writing, view checking,
indexing and querying are paid per requester; the query time is the median of
three runs. Each job ran under a memory watchdog that also recorded free disk.
Reported in Figure S3 and Table S11.

---

## 3. RQ3: Under which workloads and representation choices are the costs practical?

Four questions, in the paper's order:
1. **Semantic coverage against other converters** (§3.1).
2. **Conversion cost on controlled ladders** that vary one dimension at a time
   (§3.2–§3.3), with the storage and representation options that trade disk or
   triples for queryability (§3.4–§3.7).
3. **Retrieval cost against VCF access** (§3.8–§3.9).
4. **Retrieval on large graphs** (§3.10).

Stage timings, resident memory, transient workspace and retained artifact sizes
are measured separately. Replicated measurements are kept apart from
single-run measurements.

### 3.1 Semantic coverage: the shared-input converter comparison (`18`)

Four other executable converters (JVarkit, TogoVar, SPARQLing Genomics,
BioInterchange) and VCF-RDFizer v3.3.1 convert two shared inputs:
- the 100,000-record HG005 slice;
- the 10,000-record, 16-sample rung of the sample ladder.

Each converter runs with its most complete available options, in a pinned
container under Docker Compose. Content questions Q1–Q8 are ported to
each vocabulary and compared with the same source-derived oracle, normalization,
comparator and QLever build. A question is reported as not represented when the
graph lacks the information. Conversion time, peak memory and output size use
three replicates. [`converters/README.md`](converters/README.md) gives the
versions, commands and ports.

**Reported in** Figure 5, Section S2 and Tables S2–S3.

### 3.2 Record scaling (`04`)

**Design.** The record ladder (§4.2): HG005 prefixes of 10,000, 100,000 and
1,000,000 records with three replicates each, and the complete VCF (3,856,856
records) once. One configuration throughout: expanded samples,
space-optimized storage, partitioned HDT, no compression.

**Analysis.** Records vary with everything else held constant, so this is the
only place record-scaling exponents are fitted (`analysis/fit_scaling.py`, an
OLS slope on log-log axes with a 95% interval). It fits triples, artifact bytes,
peak workspace and end-to-end time against records. These are empirical
exponents over the measured range, not algorithmic bounds. Stage shares and
mapping-stage memory come from the same cells. Conversion cost for the retrieval
comparisons (§3.8) is quoted from here, never folded into query time.

**Reported in** Section 3.3, Figure S4a–e and Section S9.1.

### 3.3 Sample representation (`03`)

**Question.** How do the expanded and condensed sample profiles grow with
sample count?

**Design.** The sample ladder (§4.2): 10,000 records of the 1000 Genomes chr20
call set at 1, 4, 16, 64, 256, 1,024 and 2,504 samples, with INFO byte-identical
across rungs. Conversions use space-optimized storage and partitioned HDT. Three
parts:
- **Structure,** one cell per rung and profile (14 cells). The triple count is
  deterministic, so one run gives the exact number.
- **Timing,** three interleaved replicates per profile at 1 and at 2,504 samples
  (12 cells).
- **Anchors:** both profiles on a 2,504-sample fixture
  (`test-larger-multisample.vcf.gz`) and a single-sample one (`test-10k.vcf`).
  The expanded cohort anchor is skipped by the cohort-scale guard (§4.4), and the
  skip is recorded.

**Analysis.** Triple counts are fitted against samples per profile: expanded
grows with records × samples, condensed with records plus samples. The
structure ratio (triples) and the byte ratios (gzip-framed N-Triples, HDT) are
reported separately, because condensed vectors keep the values and still grow in
bytes.

**Reported in** Section 3.3, Figure S5 and Section S9.1.

### 3.4 Storage mode (`01`)

**Question.** Does space-optimized storage cut the disk a conversion needs,
without a practically important cost in time?

**Design.** A paired comparison of `plain` against `space-optimized`, with
everything else held fixed: partitioned HDT (§1.2), HDT and COTTAS, no
compression, expanded samples.
- The 100,000-record HG005 slice, three replicates per mode, interleaved
  (plain, space-optimized, plain, ...) so drift cannot favour one mode.
- `test-larger.vcf.gz` (1,155,741 records, 269M triples), once per mode
  (`BM_REPS_AT_SCALE=1`).

**Analysis.**
- **The disk metric is peak workspace,** sampled from the output tree during
  the run (`workspace_bytes.tsv`), not final artifact bytes. Both modes write
  the same triples, so final sizes match.
- **Time is judged against a ±10% equivalence margin** on mapping time for the
  replicated input (`analysis/equivalence.py`: a bootstrap interval on the
  paired ratio).
- **Compare triples, not files.** The space-optimized aggregate is a
  concatenated gzip stream, and plain storage gzips one merged file. The
  triples are the same but the bytes are not.

**Reported in** Section 3.3, Figure S4f and Section S9.2.

### 3.5 Corpus breadth and optional artifacts (`05`)

**Question.** Does the converter handle real, heterogeneous VCFs, and what do
HDT and COTTAS cost on them?

**Design.** One configuration (expanded samples, space-optimized storage, HDT
and COTTAS), one run per file:
- the first 250,000 records of eight public VCFs, keeping their headers
  (`BM_CORPUS_MAX_RECORDS`);
- the complete HG005 VCF (`BM_CORPUS_WHOLE`).

The 2,504-sample 1000 Genomes call set is skipped by the cohort-scale guard
(§4.4), so it has a recorded cell but no measurement.

**Analysis.**
- **A stratified table, not a curve.** The files differ in variant class, sample
  count, caller and VCF version, so no cross-family regression is fitted.
- **Costs are normalized by emitted triples,** not input bytes: sequence-resolved
  structural variants make input bytes incomparable. Structural descriptors
  (`analysis/describe_inputs.py`) explain differences row by row.

**Reported in** Section 3.3, Figure S6, Table S14 and Section S9.2.

### 3.6 INFO and header representation (`07`)

- **INFO:** `raw` against `structured` on the 100,000-record HG005 slice and on
  the complete HGSVC2 structural-variant VCF (32 samples), three paired
  replicates each. INFO grows with records, not records × samples, so its cost is
  a second "triples for queryability" axis.
- **Header:** `basic` against `structured` on the HG005 slice, once each.

Reported in Section S10.

### 3.7 Memory ceilings (`10`)

**Design.** One million HG005 records under three configurations:
- the defaults;
- smaller chunks (64, 128 and 256 MiB minimum, target and maximum);
- smaller chunks with condensed samples.

Each runs with requested Docker memory ceilings of 8, 16 and 31 GB (9 cells).
This is the only experiment that imposes a ceiling; everywhere else a
constrained run would contaminate the measurement.

**Caveat.** The ceiling is passed through `DOCKER_MEMORY`, and each cell records
whether it was applied (`ceiling_applied`). The harness could not confirm that
it reached every container the tool starts. The result is therefore the memory
the runs used, not survival under verified limits.

**Reported in** Section S10.

### 3.8 Query cost: SPARQL against the VCF parser (`13`; the N-Triples-only rerun)

**Question.** What does it cost to answer the same questions from the graph and
from the VCF?

**Design.** The validation layer already answers every question twice, from the
graph and from the VCF with cyvcf2, and proves the answers equal first. `13`
turns that into the experiment, with three replicates at two scales and no SHACL
(the shapes are a fixed cost of neither side):
- **Fixture:** `test-10k.vcf` (0.96M triples), all four engines over all three
  artifacts.
- **Slice:** the 100,000-record HG005 slice (17.1M triples), QLever loading each
  of the three artifacts.

**Analysis.**
- **Compare the right columns.** In `benchmark.csv`, `wall_seconds` is one query
  on one engine. `oracle_wall_seconds` is the parser's total for all queries,
  repeated on each row; `oracle_query_seconds` is the per-question figure.
- **How a question's parser time is attributed.** The oracle is one pass, so the
  per-question time is built from measured phases. Every question pays file
  opening, the record scan and assembly; the sample-level questions (Q5, Q6, Q13)
  also pay the per-sample block. Charging assembly to every question
  over-charges record-level questions on multi-sample inputs, which works
  against the RDF side. `analysis/datasets.py querycost` writes both an aggregate
  and a per-question dataset.
- **Break-even, not a speed factor.** The two sides have different cost shapes.
  The parser pays the whole parse on every question; the graph pays setup once
  and then a query per question. The result is a break-even count: additional
  RDF setup divided by the per-question saving (Section S9.4). Conversion is in
  neither column and is quoted from §3.2.
- **Minimal setup.** The campaign's conversions also built HDT and COTTAS, which
  QLever does not need, so their setup overstates the RDF route. The
  N-Triples-only rerun (`benchmark-results/vcf-bench-2/nt-only/`, v3.1.0, three
  replicates) converts the same slice to gzip-framed N-Triples only, then indexes
  and queries it on QLever. That gives the minimal setup in the crossover.

**Reported in** Section 3.3, Figures 6a, 6d, S7 and S8c, and Sections S9.3–S9.4.

### 3.9 Regional access (`14`)

**Question.** Against a coordinate-indexed VCF, which is the strongest
conventional route for a region-restricted question, how does SPARQL compare?

**Design.** Five region-restricted questions, asked of every access path on
windows of 1 kb, 100 kb, 1 Mb and 10 Mb (seeded by `BM_WINDOW_SEED`):
- **Indexed paths:** QLever on `13`'s graphs, bcftools with tabix, and cyvcf2
  with tabix, each timed on 20 windows per size.
- **Full parse:** cyvcf2 on the unindexed VCF, timed on 3 windows per size,
  because its cost does not depend on the window.
- **Scales:** on the fixture, the Comunica, HDT and COTTAS engines run too
  (seven paths); on the HG005 slice, the VCF paths and QLever.

Every VCF path drops records whose POS is outside the window after the seek,
which gives the same selection as a SPARQL `?pos` filter. One whole-file pass is
the equality reference for every window. Setup (bgzip and tabix; the QLever
index) is reported separately from the per-question time.

The cells run the regional runner inside the v3.3.1 image directly, since the
tool's command line has no mode for it. They ran from the v3.3.1 rerun:
11,160 executions in all, every answer compared.

**Reported in** Section 3.3, Figures 6c and S8a–b, and Table S18.

### 3.10 Large-graph retrieval (`15`, `16`)

**Design.** Two halves, so the expensive half runs once:
- **`15`** builds each graph once with the published v3.1.0 image into a store
  outside the results tree, with a manifest of every artifact's size and SHA-256:
  - one million HG005 records (170.9M triples), 3.98 h;
  - the complete VCF (657.4M triples), 14.25 h.
- **`16`** only reads the store, and refuses a scale that has not been built.
  The reported run used v3.3.1's runner, which writes the same graph as v3.1.0
  (the release conversion check, Section S6.2). It ran three sets of cells:
  - complete VCF: QLever from N-Triples, HDT and COTTAS, three replicates each;
  - one million records: QLever from N-Triples, three replicates;
  - one million records: the native HDT and COTTAS engines with a 24 GB heap,
    once each, under a one-hour ceiling per query.

**Analysis.**
- **The thirteen core queries, without SHACL.** Each cell reports
  `TIMING_ONLY` instead of a validation verdict, but every answer is still
  compared with cyvcf2 (`answersAgree`).
- **Query time and setup are reported separately.** Setup is index build and
  artifact decoding.
- **The in-memory Comunica engine is refused above 50M triples**
  (`BM_SCALE_MEMORY_ENGINE_MAX_TRIPLES`), and the refusal is recorded. The
  reported run did not request it.

**Reported in** Figure 3a and Table S17.

---

## 4. Execution, shared by every experiment

### 4.1 Environment and provenance (`00`)

`00_environment.sh` runs first in every session. It records the host, kernel,
CPU, memory, Docker version, tool commit, and the image's tag and digest in
`00_environment/provenance.<host>.<commit>.json`. A local tag is not unique:
two hosts that build the same tag independently get different images. So
`scripts/build_run_summary.py` resolves every cell's tag to the digest its
host recorded. Every cell's `bench.json` carries the tool commit and image.

### 4.2 Derived inputs (`02`)

The ladders are derived from one source file each, so a fitted slope measures
the tool rather than differences between files:

| Ladder | Source | Varies | Held fixed |
| --- | --- | --- | --- |
| Records | `HG005_GRCh38.vcf.gz` | 10,000, 100,000, 1,000,000 leading records | One sample, caller, assembly, header |
| Samples | `1000G_phase3_chr20.vcf.gz` | 1–2,504 samples | The same 10,000 records and INFO |

- **Built with awk, not bcftools.** Cutting sample columns cannot recompute
  INFO, so INFO is byte-identical across rungs by construction. AC and AN then
  disagree with the remaining genotypes, so the rungs are benchmark fixtures,
  not biologically valid VCFs. Validation is unaffected: Q6 derives AC and AN
  from GT, and the oracle reads the same file.
- **Provenance beside each file.** Each derived file has a provenance record
  with its source and command.
- **Other slices** follow the same idea: the corpus files' first 250,000 records
  (§3.5), and `NG131FQA1I`'s first 250,000 records for the consumer WGS
  validation run (§1.7).

### 4.3 Conversion apart from validation

Conversion takes minutes and validation hours, so validation runs only where a
section needs it. Its engines follow the question:

| Experiment | Validation engines |
| --- | --- |
| `06` | All four, on every artifact; cross-engine agreement is the result (§1.1) |
| `09`, `11`, `12` | Comunica over N-Triples |
| `13` | All four on the fixture; QLever on the HG005 slice (§3.8) |
| `16` | QLever from three artifacts, and the native HDT and COTTAS engines (§3.10) |

`12` demonstrates the separation: Phase A converts with validation off, and
Phase B validates Phase A's artifacts with `--mode validation`. SHACL runs with
the default profile unless a section turns it off (`13`, `16`). Conversions use
eight Spark partitions throughout.

### 4.4 Hosts, profile, and operation

- **Two identical hosts, whole families on each.** The base campaign ran on
  vcf-bench-1 (`01 04 07 08 09 10 11 12 13`) and vcf-bench-2 (`03 05 06`). Each
  family's cells are compared with each other, so no family was split, and
  `build_run_summary.py` refuses an archive in which one is.
- **Calibration.** Before the campaign, each host ran `12` under identical
  settings. The triples were identical and the timings differed, so timings are
  compared only within a host. The calibration records are on the `legacy`
  branch.
- **One experiment at a time.** Each host (8 cores, 33.6 GB RAM, no swap) ran
  one experiment at a time; only `10` imposes a memory ceiling.
- **Published images, never rebuilt mid-run.** Every cell used `--no-build`:
  v3.1.0 for `00`–`13` and `15`, v3.3.1 for `14` and `16`–`18`.
- **The `biomedsem` profile** of `run_all.sh` set the campaign's sizes,
  replicates and engines (`README.md` lists them). Corpus files were truncated to
  250,000 records with HG005 converted whole, and the cohort-scale guard skipped
  expanded cells on inputs with more than 1,000 sample columns.
- **Later experiments.** `15` and `16` ran on vcf-bench-3. The v3.3.1 rerun of
  `14`, `16`, `17` and the consumer WGS validation run used one driver
  (`run_v331.sh`) on each experiment's original host, except Arm 4, which moved
  to vcf-bench-2. Each job ran under a memory watchdog. `18` ran on vcf-bench-1.

### 4.5 What every run records

Each cell writes into a fresh output directory and fails rather than overwrite
one. It records:
- `bench.json`: experiment, cell, exit status, wall time, host, tool commit,
  image, and an `assertion` (`ok`, `refusal` or `recorded`) that says how a
  non-zero exit is read;
- `command.txt` and `command.json`;
- `stdout.log`, `stderr.log`, and `workspace_bytes.tsv`;
- the tool's own `out/` tree.

The archive keeps all of it except the generated RDF.
`scripts/build_run_summary.py` integrates the base campaign's cells into
`benchmark-results/summary.json`.

---

## Section numbers before 2026-10-10

The plan written before the campaign used a different numbering, which run
logs archived before this date print in their banners. Read it with
`git show 66f53577:benchmarks/DESIGN.md`.

| Earlier | Topic | Now |
| --- | --- | --- |
| §1, §1.1 | Storage mode | §3.4 |
| §1.2 | HDT-strategy constraints | §1.2 |
| §2, §2.2–§2.4 | Sample representation | §3.3 |
| §2.1 | Building the sample ladder | §4.2 |
| §3, §3.1 | Record scaling (ladder building: §4.2) | §3.2 |
| §3.2 | Corpus breadth | §3.5 |
| §4.1 | Equivalence (the mechanism check: §1.2) | §1.1 |
| §4.2 | INFO and header representation; VCF versions | §3.6; §1.5 |
| §4.3 | Mutation score; determinism, round trip, idempotence | §1.3; §1.4 |
| §4.4 | Awkward inputs and linkers; memory feasibility | §1.5; §3.7 |
| §4.5 | Query cost | §3.8 |
| §4.6 | Regional access | §3.9 |
| §5.1 | Covering set | §1.6 |
| §5.2 | Conversion apart from validation | §4.3 |
| §5.3 | Modes | §1.6 |
| §5.4 | Environment; operation | §4.1; §4.4 |
| §5.5 | Authoring effort | §2.5 |
| "§scale" | Large-graph generation and retrieval | §3.10 |
