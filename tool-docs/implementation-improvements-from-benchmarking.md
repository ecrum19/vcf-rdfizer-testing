# VCF-RDFizer implementation improvements surfaced from benchmarking

**Date:** 2026-09-18
**Evidence:** `BioMedSem_2026/benchmark-results/` (134 live cells, 92.4 h, two hosts, tool commits `025fb7d`, `be658a2`, `a3679e1`, `20d2cbb`)
**Reported in:** `BioMedSem_2026/paper/current.tex` §3.1–3.9

Every claim below is traceable to an archived run. Where a number is quoted, the
cell that produced it is named so the fix can be re-measured against the same
cell rather than against a fresh, incomparable run.

This document is deliberately split into two halves that need different kinds of
work:

- **Part A — performance and correctness of the tool itself.** The benchmark
  found a small number of very concentrated costs. Most of the runtime, most of
  the disk, and most of the validation time each sit in one or two places.
- **Part B — the linked-data demonstration.** Nothing here is a bug. The
  linking architecture works; the *demonstration* of it does not yet support any
  claim a reviewer would accept, and fixing that is a data and experiment-design
  problem, not a code problem.

A priority ordering across both halves is in §12.

---

## Part A — Performance

## 1. Representation building is 90% of end-to-end cost, and the chunking pass runs once per representation

**What the data shows.** Across the corpus-breadth cells, stage timings account
for ~90% of end-to-end wall time, and essentially all of it is HDT and COTTAS
construction. The declarative half of the pipeline — TSV extraction plus
RMLStreamer mapping — is under 0.3%.

| cell | end-to-end | TSV | RMLStreamer | HDT | COTTAS |
|---|---|---|---|---|---|
| `giab_single__HG005_GRCh38` (whole file) | 53,384 s | 58.0 s | 127.9 s | 19,480 s | 28,502 s |
| `sv_batch__HGSVC2__first250000` | 6,860 s | 6.0 s | 20.5 s | 1,910 s | 4,190 s |
| `consumer_wgs__60820188474283__first250000` | 5,959 s | 3.3 s | 22.7 s | 1,422 s | 3,946 s |

The practical consequence is that **mapping-level optimization is not worth
doing**. Making RMLStreamer twice as fast on the whole HG005 file would save
64 seconds out of 14.8 hours. Every performance improvement worth the effort is
downstream of the `.nt.gz` aggregate.

**The specific finding.** In `stages/compression_operations/*/partitioned_compression.json`
for the whole-file HG005 cell, the `hdt` and `cottas` entries report the *same*
`chunk_count` (186) and the *same* `chunk_input_bytes` (99,325,167,164 — 99.33 GB),
with identical chunk boundaries. The same holds on `r1000000__rep1` (52 chunks,
27.78 GB). Both representations are built from the same source `.nt.gz` by the
same record-safe chunker, and each one runs that chunker itself.

That means when `--representations hdt,cottas` is requested, the pipeline
decompresses and re-materializes ~99 GB of N-Triples **twice**, once per
representation, and writes 186 chunk files twice.

**What to do.**

1. **Chunk once, feed both.** Hoist the record-safe chunking pass out of the
   per-representation loop. Chunk boundaries are already deterministic and fully
   recorded (`start_record`/`end_record`/`start_uncompressed_byte`), so the
   second consumer can reuse the manifest verbatim. Expected saving is the
   decompress-and-write half of one representation's cost; it cannot be quantified
   more precisely from the current records because chunking is not separately
   timed (see §6).
2. **Stream chunks to both converters concurrently** rather than sequentially,
   once (1) is in place. The workspace trace in §2 shows the two builds running
   strictly one after the other — HDT from 0.86 h to 10.23 h, COTTAS from 10.35 h
   to 14.65 h — and they are independent given a chunk. How much of the 8 cores is
   already used *within* each build is not recorded (§6); the process snapshot
   taken during the COTTAS hang showed ~190% CPU, which suggests headroom but is
   one observation of one stalled query, not a measurement.
3. **If (1) and (2) are too invasive, at minimum add a `--reuse-chunks` flag** so
   a second representation can be built against an existing chunk directory. This
   is also what makes it possible to *measure* the saving before committing to the
   refactor.

**How to verify.** Re-run `05_corpus_breadth.sh` with `BM_CORPUS_WHOLE=HG005_GRCh38.vcf.gz`
and compare `wall_seconds_hdt + wall_seconds_cottas` against 47,982 s, on the same
host. A single-representation control (`--representations hdt` alone) should be
unchanged; if it moves, the refactor changed more than intended.

---

## 2. Peak disk is held by artifacts that are no longer needed, not by a transient merge spike

**What the data shows.** `--rdf-storage-mode space-optimized` already works and
works well: paired against `plain`, it emits identical triple counts
(17,098,746 and 269,272,677) and identical final bytes, while peak host workspace
falls **7.83×** (3.047 GB → 0.389 GB) and **7.32×** (43.73 GB → 5.98 GB), for
+4.0% and +3.1% wall time. That is not the problem.

The problem is what remains. The 5-second-interval workspace trace for the
whole-file HG005 cell (`workspace_bytes.tsv`, 10,660 samples) gives an exact
shape:

| elapsed | workspace | what is on disk |
|---|---|---|
| 0.00–0.05 h | spikes to 6.76 GB, falls to 2.63 GB | TSV intermediates written, then compacted |
| 0.07–0.86 h | grows to 5.35 GB | `.nt.gz` aggregate (2.89 GB) lands beside the TSVs |
| **0.86–10.23 h** | **flat at 5.35 GB** | HDT building; its chunk scratch is in the Docker volume, not here |
| 10.23–10.35 h | 5.35 → 9.98 → **14.73 GB** | HDT output (4.63 GB) lands, plus ~4.75 GB more |
| **10.35–14.65 h** | **flat at 14.73 GB** | COTTAS building |
| 14.65 h | **16.23 GB (peak)** | COTTAS output (1.50 GB) lands |

Peak is reached at the very end and is **not transient**: the run sits within 90%
of peak for 4.47 h, 30% of its duration. The final tree is 10.88 GB, so roughly
5.35 GB of material is still present at peak that is cleaned up afterwards.

Two components stand out:

- **TSV intermediates, 2.63 GB, held for all 14.8 hours.** They are consumed by
  RMLStreamer within the first three minutes (`RDF conversion completed` at
  00:03:51 in `progress.log`) and then never touched again.
- **~4.75 GB appearing alongside the HDT output and held for the remaining
  4.3 hours.** The HDT file itself is 4.63 GB and is accounted for separately in
  the 9.98 GB step, so this is an additional artifact — an index sidecar, a
  temporary copy, or both. It is not identified by any current metric.

**What to do.**

1. **Delete the TSV intermediates as soon as the mapping stage exits 0**, or make
   retention opt-in (`--keep-intermediates`). On this cell that alone takes peak
   from 16.23 GB to ~13.6 GB, a 16% reduction, for no functional loss.
2. **Identify and free the ~4.75 GB HDT-adjacent artifact.** First step is
   instrumentation, not code: record the out-tree composition (per-file sizes) at
   each stage boundary so this becomes a named artifact rather than a delta in a
   byte trace. If it is a temporary copy, freeing it takes peak to ~8.9 GB — a
   further 1.8× on top of the 7.3–7.8× that space-optimized mode already buys.
3. **Free each representation's chunk scratch as its converter finishes**, rather
   than at the end of the run. This is invisible in the host trace because the
   scratch lives in a Docker volume, which brings us to §6.

**How to verify.** `01_storage_mode.sh` is the right harness — it already samples
`workspace_bytes.tsv` at 5 s. The claim to demonstrate is a lower peak at
*unchanged* final bytes and unchanged triple count; a change in either means the
cleanup removed something it should not have.

---

## 3. Validation cost is three queries out of twenty-seven

**What the data shows.** On the 17.1M-triple graph (`13_query_cost/large__*`,
QLever, mean of three replicates), the thirteen semantic questions cost 17.11 s
in total. The fourteen graph-integrity preflight queries cost 298.11 s — and
three of them account for 294.13 s of that, 98.7%:

| preflight query | mean wall |
|---|---|
| `preflight_missing_token_conformance` | 102.50 s |
| `preflight_empty_values` | 97.01 s |
| `preflight_empty_values_count` | 94.62 s |
| remaining 11 preflight queries, combined | 3.98 s |

So validation costs ~18× more than the science it is protecting, and the
overwhelming majority of that is three full-graph anomaly scans.

Worse, the pattern is internally inconsistent. Each sample query has a `_count`
companion. For `blank_nodes`, both cost 0.61 s. For `missing_token_conformance`,
the sample query costs 102.50 s but its count companion costs 0.30 s. For
`empty_values`, **both** cost ~95 s — the count variant re-scans the entire graph
to produce a number the sample query already computed. The summary JSON for that
check reports both `anomalyCount` and `anomalyCountReturned`, so the value is
already available.

**What to do.**

1. **Delete `preflight_empty_values_count` and derive it from
   `preflight_empty_values`.** This is ~95 s, a third of all preflight cost, for a
   value the first query already has. It is the single cheapest win in this
   document.
2. **Make the two remaining full-graph scans bounded by default.** Both already
   accept `limitedTo: 100`; the limit governs how many anomaly rows are
   *returned*, not how much of the graph is scanned. Either push the limit into
   the query as a `LIMIT` on the scan, or run these two under an explicit
   `--deep-validation` flag and keep the cheap eleven in the default path. A
   default validation pass that costs 17 s instead of 315 s is the difference
   between validation being routine and being skipped.
3. **Report the two cost halves separately in the run summary.** `benchmark.csv`
   already carries `query_id`, so the split is a reporting change: "semantic
   checks 17.1 s, integrity scans 298.1 s" tells a user what to turn off; one
   aggregate number does not.

**How to verify.** `13_query_cost.sh` at both scales. Correctness must not move:
all 780 paired comparisons in the campaign passed except the four discussed in
§5, and that has to stay true.

---

## 4. Engine selection dominates query cost by three orders of magnitude, and the default does not reflect it

**What the data shows.** The same thirteen questions, same graph, same machine
(`13_query_cost/small__*`, 0.96M triples):

| engine | Q1–Q13 total | setup |
|---|---|---|
| QLever | 1.09 s | 2.07 s |
| Comunica | 23.30 s | 12.36 s |
| HDT-backed | 44.83 s | 10.80 s |
| native pycottas | 1,402.37 s | 29.52 s |

Meanwhile the *artifact* barely matters: on the 17.1M-triple graph, QLever takes
17.11 s against N-Triples, 17.16 s against HDT and 16.97 s against COTTAS — under
5% spread, because each engine materializes what it needs.

This inverts the intuition the tool's interface encourages. Users choose a
representation and accept whatever engine follows; the measurement says the
representation is a *storage* decision and the engine is the *performance*
decision.

**What to do.**

1. **Make QLever the default validation engine** where it is available.
   `06_equivalence` already showed cross-engine agreement, so this costs no
   correctness. The campaign's own `13_query_cost/large__*` cells already use
   `--validation-engine qlever` for exactly this reason; the default should match
   what the benchmark had to do by hand.
2. **Document native pycottas querying as a conformance path, not a query path.**
   It is 1,286× slower than QLever on identical work and, per §5, does not
   terminate at all on one encoding. It has value as an independent
   implementation for cross-checking; presenting it as a way to query a COTTAS
   file is misleading.
3. **State the artifact/engine separation in the CLI help and README.** One
   sentence — "the representation determines size and build time; the engine
   determines query time" — would prevent the most likely misconfiguration.

---

## 5. Native COTTAS querying does not terminate on the condensed encoding, and the timeout does not bound it

**What the data shows.** This is the one hard failure in the campaign, and it
was reproduced twice. Archived under
`benchmark-results/vcf-bench-2/benchmarks_outputs__stalled/`:

- **Run 1** (`06_equivalence__cottas_condensed_hang__20260917T202754`): native
  pycottas answered the 14 preflight queries and Q1–Q4 against the **condensed**
  encoding of a 10,000-record fixture, then ran **41 hours** on
  `q05_sample_genotype_counts` at ~190% CPU without completing.
- **Run 2** (`06_equivalence__cottas_hang_2__timeout_ineffective__20260918T094006`):
  same fixture, same query, ~10 hours before it was killed. The progress log
  stops at `completed: 18` of 27 with `q05_sample_genotype_counts` in flight.

The scope is specific and worth stating precisely, because it is narrower than
"COTTAS is broken":

- QLever answered all thirteen questions on **that same cell**.
- The sibling **expanded** encoding completed every engine, including native
  pycottas, in 185–194 min, with all four engines agreeing and all three
  artifacts passing.

So the defect is *native pycottas × condensed genotype encoding × genotype-level
query*.

**The second, more serious half.** Run 2 was launched with
`--validation-query-timeout 1800` and `--validation-time-budget 14400` on the
command line. The process snapshot in `diagnostics/snapshot.txt` confirms both
flags were live on the running invocation. **Neither fired.** A documented bound
that is not enforced is worse than no bound, because it invites exactly the
unattended overnight run that lost 41 hours here.

**What to do, in this order.**

1. **Fix the timeout first.** It is independent of the COTTAS bug and it protects
   every future run from every future hang. The bound has to be enforced where
   the query is actually executed — inside the container, per engine, per query —
   not only in the wrapper that spawned it. A timeout that fires must record the
   query as `EXECUTION_FAILED` and let the remaining queries run, so a bound costs
   one query's evidence rather than the whole cell.
2. **Then diagnose the condensed-encoding hang.** The narrowness of the
   reproduction is a gift: one query, one encoding, one engine, a 10,000-record
   fixture that fits anywhere. Start by profiling `q05_sample_genotype_counts`
   against the condensed COTTAS artifact outside the harness. The likely shape —
   the condensed encoding stores genotypes as `S + (V × F)` rather than `V × S`,
   so a per-sample genotype query has to join across the sample block — suggests a
   missing or unusable index on the join column rather than sheer data volume.
3. **Until it is fixed, refuse the combination explicitly.** The wrapper already
   structurally refuses three option pairs (`--hdt-strategy single` beside
   space-optimized, beside COTTAS, beside `hdt,cottas`); a fourth refusal with a
   clear message is honest and costs a user nothing they can currently get.

**How to verify.** `06_equivalence.sh` is the cell that failed and is the cell
that has to pass. The bar is: the condensed arm completes all 27 queries under
all four engines, or the combination is refused with a diagnostic and the
experiment records that refusal as a result.

---

## 6. Instrumentation gaps that block further optimization

Three quantities that the campaign needed are not recorded, and each one blocks a
specific decision above.

**Per-chunk and per-merge-round timing.** `partitioned_compression.json` records
186 chunks with exact byte and record boundaries but **no wall time per chunk**
and no record of the pairwise merge rounds at all. So of HDT's 19,480 s on the
whole HG005 file, the split between (a) decompressing and writing chunks,
(b) converting each chunk, and (c) ~8 rounds of HDTCat merging is unknown. §1's
recommendation cannot be sized until this exists, and the saving cannot be
attributed after the fact either.

**Memory of the dominant stage.** In the same record, `max_rss_kb` is `null` for
both `hdt` and `cottas`. The pipeline's own summary reports `max_rss_kb_java`
(1.3–1.8 GB, the mapping stage) and `max_rss_kb_tsv` (7.5 MB) — but the stage that
takes 90% of the wall time reports no memory at all. This directly undermines the
feasibility experiment: `10_feasibility` shows all nine cells completing at 8, 16
and 31 GB ceilings with peak RSS of 1.37–1.85 GB, but that figure is the *mapping*
stage's memory, not the build stage's.

**Container-volume workspace.** `stages/partitioned/*.json` records
`runtime_environment: docker-volume` and nothing about how large that volume got.
The host-side `workspace_bytes.tsv` cannot see it. Since the 99.33 GB of chunk
material lives there, the peak disk figure in §2 is only half the story — and the
`analysis/collect_metrics.py` docstring is explicit that these are different
numbers that must never be added.

**What to do.** All three are recording changes rather than algorithmic ones:
time each chunk and each merge round into the existing `chunks` array; wrap the
build stage in the same `/usr/bin/time -v` treatment the Java stage already gets;
and sample the container volume the way the host tree is already sampled, writing
it as a clearly distinct `peak_volume_workspace_bytes`. Do these **before** §1 and
§2, not after — they are how you will know whether those fixes worked.

---

## 7. Fixed per-run overhead is material for small inputs

**What the data shows.** On the records ladder (`04_scaling_records`), stage
timings do not account for the whole run, and the unexplained remainder is large
at the small end:

| rung | end-to-end | TSV + mapping + HDT | unaccounted |
|---|---|---|---|
| `r10000` | 41.3 s | 26.9 s | 14.4 s (35%) |
| `r100000` | 424.0 s | 310.0 s | 114.0 s (27%) |
| `r1000000` | 5,479.3 s | 4,333.8 s | 1,145.5 s (21%) |

Some of this is container start and JVM warm-up, which is genuinely fixed —
`12_modes_smoke`'s `mode_tsv` and `mode_index_hdt` cells complete in 1 s each, and
`phaseA_convert` takes 26–29 s for a 1,000-record file. But the remainder *grows*
with input size, so it is not all fixed cost: something proportional to the data
is happening outside the timed stages, most likely aggregation and file movement
between the container volume and the host tree.

**What to do.** Close the accounting before optimizing it. Once §6's stage
timings exist, this gap should shrink to genuine process overhead; whatever is
left is a real, unmeasured, data-proportional stage that deserves its own timer.
For interactive use on small files, a warm-container mode (reuse one container
across inputs in a batch) would remove the fixed component, which is ~35% of a
10,000-record run.

---

## 8. The expanded sample representation needs a cost estimate, not just a guard

**What the data shows.** The 1→2504 sample ladder (`03_sample_representation`,
10,000 variant records held fixed) separates the two representations by three
orders of magnitude:

| samples | condensed triples | expanded triples | ratio | expanded wall |
|---|---|---|---|---|
| 1 | 1,439,503 | 1,609,503 | 1.1× | 38 s |
| 64 | 1,439,818 | 17,359,818 | 12.1× | 360 s |
| 1,024 | 1,444,618 | 257,364,618 | 178.2× | 5,825 s |
| 2,504 | 1,452,018 | 627,372,018 | 432.1× | 14,527 s |

Fitted exponents: condensed **+0.001** (95% CI [+0.000, +0.002]), expanded
**+0.795** (95% CI [+0.649, +0.940]). Extrapolated to the full 1,812,841-record
chromosome-20 call set, the expanded representation needs roughly **2 TB** against
a 189 GB volume.

The harness handles this with `bm_skip_if_cohort_scale`, which refuses the
expanded cell above `BM_CORPUS_MAX_SAMPLES` (default 1000) — and that guard is
the right behaviour. But it lives in the *benchmark*, not in the tool. A user
running VCF-RDFizer directly on a 2,504-sample cohort in expanded mode gets no
warning and fills their disk.

**What to do.**

1. **Move the guard into the tool.** Header preflight already reads the sample
   count. Estimate output size from `records × samples × format_keys` before
   starting, compare it against free space on the target volume, and refuse with
   the estimate and the `condensed` alternative named in the message.
2. **Make `condensed` the default for multi-sample inputs.** The benchmark's own
   framing is that condensed is the tractable setting at cohort scale, not a
   space-saving option. The default should match.
3. **Publish the estimator coefficients.** The ladder gives them directly; a user
   deciding whether a cohort is feasible should not have to run it to find out.

---

## 9. Two correctness defects the validation stage caught

These are small, specific, and already localized by the archived reports.

**Zero-record VCFs drop header-declared samples.** On the `awkward_no_records`
fixture — a header-only VCF that declares a sample column and contains no data
records — the graph omits the `vcfc:SampleSet` and `vcfc:VCFSample` resources the
header declares. Q9 flagged six missing predicates
(`hasGenotypeColumns`, `hasSample`, `hasSampleSet`, `representationProfile`,
`sampleIndex`, `sampleName`) and an `rdf:type` count of 40 against an expected 42;
Q10 flagged two missing classes (`SampleSet`, `VCFSample`). The run exited non-zero rather than reporting success, which
is the validator behaving correctly. The fix is in the mapping: sample resources
should derive from the header declaration, not from the presence of data records.

**Missing values survive as literal `"."` on real data.** On the real
100,000-record `HG005_GRCh38` input, `preflight_missing_token_conformance` found
**20 surviving literal `"."` tokens** — missing values emitted as the VCF
placeholder instead of being omitted from the graph. This is recorded as
`EXPECTED_CONFORMANCE_FAILURE` rather than `FAIL` only because
`strictConformance` was `false` for that run. It should be fixed in the
extraction, not configured away; twenty bad literals in a real file is the kind
of thing that propagates into every downstream query that filters on absence.

A third case is **not** a tool defect and should not be treated as one. The
`awkward_sites_only` fixture returns `EXECUTION_FAILED` because the VCF-side
oracle cannot read it: `bcftools` rejects a `FORMAT` column declared with no
sample columns, which is itself outside the specification. The conversion
produced 245 triples and a valid HDT artifact. **Fix the fixture**, by removing
the `FORMAT` column from the `#CHROM` line, and the case becomes testable.

---

## 10. Validation coverage: the cheapest improvement is already written

**What the data shows.** The mutation-score experiment injected 113 targeted
corruptions and the validation suite detected 96 — a score of **0.850**. The 17
undetected instances fall into ten classes, and the report names the remedy for
each:

| undetected class | instances | stated remedy |
|---|---|---|
| `corrupt_allele_value` | 2 | **the vocabulary's consistency SHACL profile already checks this** |
| `corrupt_record_index` | 2 | **the SPARQL SHACL profile checks uniqueness and ordering** |
| `corrupt_value_item_allele` | 2 | **the consistency profile checks item/raw agreement** |
| `corrupt_sample_index_expanded` | 1 | **the SPARQL SHACL profile rejects duplicate `sampleIndex`** |
| `corrupt_allele_kind` | 2 | cross-check `alleleKind` against Q2's REF/ALT classification |
| `corrupt_attribute_value` | 2 | digest over structured header attributes, as Q11 does for records |
| `corrupt_contig_count` | 2 | read the derived scalar's value, not just its existence |
| `wrong_declaration_owner` | 2 | tie field IDs to their header line |
| `corrupt_called_allele` | 1 | check the `calledAllele` join, not just its count |
| `flip_phasing_status` | 1 | compare `vcfc:phasingStatus` against the raw genotype string |

**The headline.** Four of those ten classes — **7 of the 17 undetected instances**
— are covered by a SHACL shape profile that **already exists and was enabled in
zero of the 62 validation runs in this campaign** (`shacl: null` in every
`summary.json`). Turning it on raises the mutation score from **0.850 to 0.912**
with no new oracle, no new query, and no new code.

**What to do.**

1. **Wire the existing SHACL profile into the validation stage and enable it by
   default on small inputs.** Then re-run `08_robustness.sh` and report the new
   score. This is the highest-value-per-hour item in this entire document.
2. **Close the remaining six classes with aggregate queries**, in the order the
   table gives — `corrupt_allele_kind` first, since the report notes Q2 already
   computes the comparison value and only the cross-check is missing.
3. **Re-run the mutation score after each change** and report the trajectory.
   A score that moves 0.850 → 0.912 → higher is a far stronger claim than a single
   number, because it demonstrates that the gap list is actionable rather than
   decorative.

---

## Part B — Demonstrating the linked-data capability

## 11. What the linking evidence currently supports, and what it needs to support

**What the data shows.** All three linker tiers were exercised as far as an
offline campaign allows (`09_awkward_inputs/link__*`), against the same
86-record graph:

| tier | linker | keys | links | time | outcome |
|---|---|---|---|---|---|
| 1 | `rsid-dbsnp` | 86 | 86 | 0.0022 s | works, offline, manifest digest recorded |
| 2 | `gene-demo` | 86 | **0** | 0.0019 s | executes cleanly, produces nothing |
| 3 | `rsid-ensembl` | — | — | — | **never run** |

The architecture is genuinely good and the instrumentation is better than most:
each linker records its tier, version, manifest SHA-256, reference digest,
assembly, unique key count, skipped records, request count, cache hits, bytes
transferred and wall time. Tier 1 emitted 86 `linking:sameVariantAs` triples to
`identifiers.org` dbSNP IRIs with zero network access.

**Why none of that is yet a demonstration.**

- **Tier 1 proves plumbing, not entity resolution.** It rewrites an identifier
  that is already in the VCF's ID column into an IRI. It cannot fail to link a
  record that has an rsID, and it cannot link one that does not. The preview
  triples make this plain: `rs0000001`, `rs0000002`, `rs0000003` — the fixture's
  identifiers are synthetic and sequential. A reviewer will read 86/86 as 100%
  recall and then notice that the denominator was constructed.
- **Tier 2 produced zero links.** The run is well-formed — it records the
  reference digest `c343c83f…` and assembly GRCh38, 86 unique keys, no skipped
  records — but the bundled demonstration gene interval set does not overlap the
  fixture's coordinates. "Executes correctly" and "links nothing" are the same
  row in the output, which is the worst possible outcome to show someone.
- **Tier 3 was never exercised at all**, because the campaign deliberately
  withheld network access so every reported number would be reproducible offline.
  That was the right call for the benchmark and leaves the live resolver with
  zero evidence behind it.

The fair current claim is: *the linking architecture is implemented, offline-
capable and provenance-instrumented; its real-world yield is untested.* That is
what §3.7 of the manuscript says, and it is as far as the data goes.

### 11.1 What a credible demonstration requires

**Use a real cohort with real identifiers.** The 86-record synthetic fixture has
to go. The corpus already contains the right input: `HG005_GRCh38` or
`HG004_GRCh38` (GIAB, GRCh38, real rsIDs where dbSNP has them), or the 1000
Genomes chromosome-20 call set if a population-scale example is wanted. Convert
in condensed mode — §8 — so the cohort case stays tractable.

**Report yield against a known denominator.** The metric that matters is not
"86 links" but the pair:

- **coverage** — of records that *carry* an rsID, what fraction resolved;
- **recall against an independent overlap** — of records that dbSNP *would*
  match on position and alleles, what fraction the linker found.

The second is the one that distinguishes tier 1 from a `sed` command. Compute the
independent overlap with `bcftools isec` against a released dbSNP VCF, then
compare. Anything less and tier 1's 100% remains uninterpretable.

**Report precision, which currently has no mechanism at all.** Tier 1 trusts the
ID column. If a VCF carries a stale or wrong rsID — which is common in
re-annotated call sets — tier 1 will emit a confidently wrong
`linking:sameVariantAs`. A position-and-allele cross-check against the dbSNP
record the IRI points at would turn that from an unmeasured risk into a reported
number. This is the single most important gap in the linking story, because
`sameVariantAs` is a strong assertion and nothing currently validates it.

**Pin the reference release.** Every link claim is relative to a dbSNP or Ensembl
build. The linker already records a `manifest_sha256` and a `reference_digest`,
which is most of the work; what is missing is the human-readable release
identifier (`dbSNP b156`, `Ensembl 112`) in the output graph itself, so a graph
consumed a year later still says what it was linked against.

**Fix or replace the tier-2 reference bundle.** Either ship a demonstration
reference whose intervals actually overlap the demonstration input, or — better —
point tier 2 at a real GENCODE or Ensembl gene annotation for the assembly and
report gene-overlap yield on a real cohort. A demo that produces zero links is
worse than no demo, and the fix is a data-packaging decision, not code.

**Run tier 3 at least once, deliberately and reproducibly.** It needs network, so
it cannot live in the offline campaign — but it can live in a separate, clearly
labelled experiment with `BM_ALLOW_NETWORK=1` and `BM_CONTACT_EMAIL` set, run
once, with the response cache archived so the *result* is reproducible even
though the *run* is not. Record request count, cache hits, bytes transferred,
final service status and per-request latency; the linker already emits all five
fields and they are all zero today.

### 11.2 What the demonstration should show a reader

A useful linked-data demo answers a question that neither VCF nor RDF alone
answers. The current output — 86 `sameVariantAs` triples — answers none, which is
why it reads as plumbing. Concretely, the assets already in this repository
support at least these:

1. **A cross-file join.** Two GIAB genomes (HG004 and HG005) are both in the
   corpus, both converted, both GRCh38. One SPARQL query over both graphs —
   variants called in one and not the other, within a gene of interest — is a
   query neither `bcftools` nor `cyvcf2` answers without writing a script, and it
   uses only assets that exist.
2. **A gene-level aggregation via tier-2 links.** Variant counts per gene across
   a cohort, once tier 2 links to a real annotation, is a recognizable
   bioinformatic operation and is the natural extension of Q1's density windows.
3. **A provenance-aware retrieval.** The link graph already carries per-linker
   manifest and reference digests. A query that returns only links produced
   against a named dbSNP build demonstrates the governance angle the Discussion
   claims, using metadata the tool already emits.

Each of these should be measured the way §3.6 measures the thirteen questions —
with a parser-side comparator where one is even possible, and an honest note
where it is not, because "the parser cannot do this at all" is the strongest
result the linking work can produce and it should be stated as a measurement
rather than an assertion.

### 11.3 What to add to the benchmark harness

`09_awkward_inputs.sh` currently runs linking as an afterthought in the
awkward-inputs experiment, against whatever `.nt` the smoke conversion produced.
Linking deserves its own experiment — call it `14_linking.sh` — with:

- a real corpus input rather than a fixture;
- tiers 1 and 2 offline, tier 3 gated behind `BM_ALLOW_NETWORK=1`;
- an independent overlap oracle (`bcftools isec` against a pinned dbSNP release),
  in the same spirit as the cyvcf2 oracle that makes §3.5 credible;
- `analysis/datasets.py linking` emitting coverage, recall, precision and
  per-tier cost, so the result lands in a table the same way every other
  experiment does.

The pattern that makes the rest of this benchmark trustworthy — compute the
answer twice, independently, and compare — is exactly what the linking evidence
lacks. Adding it is what turns tier 1's 86/86 from a tautology into a result.

---

## 12. Priority

Ordered by value per unit of effort, not by section number.

| # | Change | §  | Effort | Why this rank |
|---|---|---|---|---|
| 1 | Enable the existing SHACL profile in validation | 10 | hours | Mutation score 0.850 → 0.912 with no new code |
| 2 | Enforce `--validation-query-timeout` where queries execute | 5 | hours | Already cost 51 h of unattended runtime; protects everything downstream |
| 3 | Drop `preflight_empty_values_count`; derive it | 3 | hours | ~95 s, a third of preflight cost, for a value already computed |
| 4 | Add per-chunk, per-merge and build-stage RSS timing | 6 | days | Blocks #5 and #6; without it no build-stage claim is measurable |
| 5 | Delete TSV intermediates after mapping succeeds | 2 | days | −16% peak disk, no functional loss |
| 6 | Chunk once, feed both representations | 1 | weeks | The largest single runtime saving available |
| 7 | Move the cohort-scale guard into the tool | 8 | days | Prevents a user filling their disk with no warning |
| 8 | Build the real linking demonstration (`14_linking.sh`) | 11 | weeks | Turns the weakest claim in the paper into a measured one |
| 9 | Fix zero-record sample emission; fix surviving `"."` literals | 9 | days | Small, localized, already diagnosed |
| 10 | Default to QLever; document artifact-vs-engine | 4 | hours | Free 20× on the default path |
| 11 | Diagnose the condensed-COTTAS hang, or refuse the combination | 5 | weeks | Narrow reproduction exists; the refusal is an acceptable interim |

Items 1–3 and 10 are a single afternoon between them and move four separate
numbers in the manuscript. They should not wait for anything else in this list.

---

## 13. Implementation notes (2026-09-19)

Implemented on `dev` in the tool repo (`ecrum19/VCF-RDFizer`), 10 commits,
`f830078..79e5408`. Suite: 716 tests before, **817 after, all passing**.

### Two corrections to this document

**§1 was wrong. Chunking is already shared.** `stream_chunks` is called once in
`src/partitioned_compression.py` and the loop builds HDT *and* COTTAS from each
chunk before unlinking it. The identical `chunk_count` and `chunk_input_bytes`
under both methods is one shared plan recorded twice, not two passes. Nothing
was reimplemented. The archived records could not distinguish the two cases,
which is precisely the gap §6 describes — so §6 was done first, and
`chunk_stream_seconds` now makes it visible. What remains of §1 is real but
smaller: the two builds are serial *within* each chunk iteration.

**§9's `"."` literals were a false positive, not a graph defect.** The published
shapes permit a bare dot on exactly two predicates: `vcfc:fieldNumber` (pattern
`^([0-9]+|A|R|G|LA|LR|LG|P|M|[.])$` — `Number=.` is VCF's variable-cardinality
token, a declared arity) and `vcfc:genotypeString` (a fully-missing call is
literally `"."`). Neither is typed `vcfc:Null` because neither is missing. The
check flagged conformant values; both queries now exclude those predicates.
**The manuscript's claim that the HG005 graph retains 20 bad literals does not
hold and needs correcting.**

### What landed

| # | Status | Notes |
|---|---|---|
| 1 | done | Shapes + ontology bundle vendored to `vcf_rdfizer_data/`, digest-pinned in `VOCABULARY_PROVENANCE.json`; on by default ≤512 MiB (pyshacl is in-memory); `--no-shacl` opts out |
| 2 | done | Already fixed on `fix/cottas-query-timeout` (`53412a7`); merged to `dev` |
| 3 | done | Generalised: *any* anomaly preflight whose sample returns under its LIMIT derives the count instead of re-scanning. `derived`/`derivedFrom`/`derivedReason` in the record, `derived` column in `benchmark.csv` |
| 4 | done | Per-chunk `write_seconds`, shared `chunk_stream_seconds`, merge rounds per representation, `getrusage(RUSAGE_CHILDREN)` RSS fallback, container-volume peak. The stage detail existed all along and was dropped at the wrapper boundary |
| 5 | done | Freed after the last TSV reader, before the build. Source-order tests pin the sequencing, since "gone by the end" was already true |
| 6 | n/a | See correction above |
| 7 | done | Estimator fitted on the ladder (25 triples/sample-call, 20 peak bytes/triple) vs actual free space, refuses above 75%; `--allow-cohort-expansion` overrides. Expanded only |
| 8 | half | Tool side done: `eligible_records`, `linked_subjects`, coverage, and an `assertion_basis` per tier carried into the linkset node. The other half is an experiment, not code |
| 9 | done | Zero-record fix + conformance-check scope (above) |
| 10 | done | QLever is the default; artifact-vs-engine separation documented in CLI help and `docs/validation.md` |
| 11 | interim | Explicit `cottas` + condensed is refused with the measurement quoted; `--validation-engine all` drops cottas with a warning and validates on the other three. Upstream diagnosis still open |

### Verification

**Not run on the VM.** No Docker daemon on this machine and `vcf-bench-1/2` do
not resolve from it, so nothing container-backed — RMLStreamer, HDT/COTTAS
builds, a full pipeline — was exercised. The container-side changes (§4) are
covered by unit tests only and still need one real run on a host that has
Docker.

Run for real, without a container:

- **SHACL assets** — all 8 vendored shape files parse (46–894 triples each), the
  2,665-triple ontology bundle carries `AltAllele rdfs:subClassOf Allele`, and
  pyshacl 0.30.1 validates with RDFS inference in 0.37 s.
- **Zero-record fix** — `awkward_no_records` through the real `vcf_as_tsv.sh`
  and the real emitters: **0 triples before, 8 after**, and every predicate and
  class the oracle reported missing is present.
- **Chunker** — a real 4.34 MB / 120,000-triple graph, 9 chunks:
  `chunk_stream_seconds` 0.060 s against 0.135 s of held-out consumer time, so
  build time is not charged to the stream; every chunk carries `write_seconds`.
- **Cohort guard** — a real 121 MB stand-in TSV, 12,000 × 2,504: estimate
  15.0 GB against 16.4 GB free → **refused**; condensed → allowed;
  `--allow-cohort-expansion` → allowed. The estimator gives **2.27 TB** for the
  full 1000G chr20 expanded shape, against the ~2.1 TB the run plan
  extrapolated independently.

### Correction to the SHACL claim (§10, item 1)

**The 0.850 -> 0.912 figure does not belong to the default.** Measured on
bench-1, on a 2,000-triple graph:

| profile | cost | catches the four classes? |
|---|---|---|
| `vcf-core-vocabulary.shacl.ttl` | **1.7 s** | **no** — cardinality and datatype only |
| `vcf-core-consistency.shacl.ttl` | 33.7 s | yes — `alleleValue` vs `REF`/`ALT` |
| `vcf-core-vocabulary-sparql.shacl.ttl` | 73.2 s | yes — index uniqueness |

The core profile constrains `vcfc:sampleIndex` to exist once as an integer >= 1
and says nothing about whether two samples share a value. Uniqueness is a
`sh:sparql` rule in the SPARQL profile; value agreement is in the consistency
profile. So the four classes need the profiles that cost 63x the core one, and
whose constraints self-join the graph.

Resolved by splitting rather than by picking one: `--shacl-profile core` is the
default, cheap, gated at 512 MiB; `--shacl-profile full` adds both, gated at
16 MiB. Section 10's recommendation stands, but the score improvement requires
`full` on a fixture-sized graph, not the default, and the manuscript should say
so if it cites the figure.

**What is and is not established.** That the uniqueness and agreement rules live
only in the non-default profiles is definitive — it is read from the vendored
shapes, where `sh:message "Record indices must be unique within a VCF file"`
appears in `vcf-core-vocabulary-sparql.shacl.ttl` and nowhere else. The costs
are measured. **End-to-end detection was not confirmed.** An ad-hoc probe that
injected a duplicate `recordIndex` into a 2,000-line slice of a graph reported
1 violation under `full` both before and after the injection — but that slice
is a truncated N-Triples file, so it carries a baseline violation of its own and
may not even contain both records the self-join needs. The probe was the wrong
instrument. The right one already exists: run the repository's own
mutation-score harness (`08_robustness.sh`, `test/validation_mutations.py`) with
`--shacl-profile full` and read the score.

> **Settled in section 15 (2026-09-21).** That harness was run. The score is
> **113/113 = 1.000**, not 0.912: the full profile closed all ten undetected
> classes, not the four predicted here. The reasoning above — which classes map
> to which constraint — was too literal, because a corruption that does not
> violate its own class's constraint frequently violates a neighbouring one.

---

## 14. VM verification (2026-09-19, bench-1)

Run on `vcf-bench-1` via the SLICES jump host, in `~/vrdev-test/` so neither
the pinned `~/VCF-RDFizer` checkout nor the archived `benchmarks_outputs/` was
touched. Image built from `dev` as `vcf-rdfizer:dev-test`. Unit suite on the
VM: **841 tests, OK**.

**Five defects the local Docker-less checks could not have found**, all fixed
and committed:

1. **SHACL blocked on warnings.** The first real pipeline run failed `test-1k`
   with `violationCount 0` and `violationPaths [vcfc:fieldSource,
   vcfc:fieldVersion]`. Those carry `sh:severity sh:Warning` because VCF 4.5
   *recommends* Source and Version on INFO declarations. pyshacl sets
   `conforms=False` for any severity, so the new default failed a conformant
   graph — and would have failed almost every real VCF.
2. **The violation matcher never fired.** pyshacl 0.30.1 writes
   `Validation Result in <Component>` with an indented `Severity:` line, not
   `Constraint Violation`. The existing parser matched nothing, so the layer
   could not have reported a real violation either. Now parsed by severity,
   with the pre-0.30 spelling still handled and an unclassifiable block
   treated as blocking.
3. **`peak_volume_workspace_bytes` measured the host disk.** It reported
   126,956,531,712 bytes — 127 GB — for a build whose scratch was one 11.9 MB
   chunk, because `shutil.disk_usage` describes the backing device. Now the
   scratch tree is sized directly: **12.6 MB** for that same build.
4. **The zero-record fix was half a fix.** With the sample set restored, q09
   and q10 passed but `preflight_sample_gt_inventory` still failed, expecting
   `sampleIdCount` 1 and finding 0. `vcfc:sampleId` lives on `SampleCall`, one
   per sample *per record*, so a header-only VCF has none. Expectation
   corrected.
5. **The default profile caught none of the four classes** — see the
   correction above.

**Verified working on real runs:**

| Change | Evidence |
|---|---|
| Derived anomaly counts (§3) | 6 of 6 `*_count` companions derived at 0.0 s; `preflight_distinct_triple_count`, which has no sample pair, still executed |
| QLever default (§10) | `engines=['qlever']` with no flag passed |
| Build profile (§4) | `chunk_stream_seconds` 0.098 s, per-chunk `write_seconds`, `max_rss_kb` 367,196 (was null), `by_stage_kind` splitting hdt-chunk-build 0.33 s from cottas-chunk-build 11.5 s |
| Shared chunking (§1 correction) | One `chunk_stream_seconds` scalar beside per-method totals, confirming empirically that the 99 GB read happens **once** |
| Zero-record fix (§9) | `awkward_no_records`: 181 triples and exit 1 in the campaign, now **189 triples, exit 0, comparisonStatus PASS**, no failing preflight |
| COTTAS guard (§11) | Explicit `cottas`+condensed → exit 2 with the measurement quoted, no output directory created; `--validation-engine all`+condensed → warns and validates on comunica, qlever, hdt; `cottas`+expanded → allowed |
| SHACL default (§1) | Runs on every pipeline, `status=PASS` with `conforms=False` and 6 advisories — the severity distinction working as intended. (The 34–38 s quoted here is the cell's whole validation wall, not SHACL's share; section 15 measures the added cost at +1.5–2.5 s on these fixtures.) |
| Cohort guard (§7) | On the real `test-larger-multisample.vcf.gz` (10,000 x 2,504) the estimator gives **12.5 GB** against the campaign's **measured 11.48 GB** peak for that same shape — within 9% |

**Not verified at the time:** the mutation score under `--shacl-profile full`
(measured since — see section 15 — at 113/113), and a full-scale run. Everything above is fixture-scale
(test-1k, test-100, 2,000-triple graphs). The peak-workspace and TSV-cleanup
savings in sections 2 and 5 are argued from where the code now frees things,
not measured on a 14.8-hour whole-file run; `05_corpus_breadth.sh` with
`BM_CORPUS_WHOLE=HG005_GRCh38.vcf.gz` is still the test that would settle them.

### Still open

§1's remaining half (build HDT and COTTAS concurrently per chunk); the upstream
pycottas diagnosis behind §5/#11; and the `14_linking.sh` experiment in §11.3,
which belongs in this repo, not the tool. Section 15 adds one more: the perfect
mutation score costs roughly sixty times the default profile, because its
constraints self-join the graph, so it is confined to inputs small enough to
afford it. Expressing the same uniqueness checks as streaming comparisons over
the oracle would carry that coverage to cohort scale.

---

## 15. Tier 1 re-run on the fixed tool (2026-09-21, bench-1)

The changes in sections 13 and 14 were verified per-change but never through
the harness end to end. This is that run: `08_robustness`, `09_awkward_inputs`,
`11_covering_set` and `12_modes_smoke`, executed by
`run_all.sh biomedsem 08 09 11 12` against an image built from the `dev` tree,
with `BM_RESULTS` pointed at a scratch tree so the archived
`benchmarks_outputs/` was untouched.

### Why only these four

The other experiments were not re-run, and the determinism cell is the reason.
`08_robustness/determinism__{a,b}` reproduces digest
`661578e7…94194ed` — 17,098,746 triples, zero duplicates, `identical: true` —
which is byte-for-byte the campaign's result on the same 100,000-record input.
Since none of the changes altered a single emitted triple, the conversion-scale
results (experiments 01, 03, 04, 05, 07, 13) remain valid as archived, and the
49 hours a Tier 3 re-run would cost buys only a slightly better peak-disk
column. The round-trip cell likewise reproduces `identical: true`.

That is the general rule worth keeping: **re-run the experiments whose verdicts
the change could flip, and use the determinism digest to certify the rest.**

### Results against the campaign

| Experiment | Campaign | Re-run | Change |
|---|---|---|---|
| `08_robustness` | 8 cells, 8 ok | 9 cells, 9 ok | new `mutation_score__shacl_full` cell |
| `09_awkward_inputs` | 12 ok, 2 non-zero, 2 skipped | 13 ok, 2 non-zero, 2 skipped | `awkward_no_records` 1 → 0 |
| `11_covering_set` | 10 ok | 7 ok, 3 non-zero | `row3`, `row9`, `row10` 0 → 1 |
| `12_modes_smoke` | 7 ok | 7 ok | unchanged |

`awkward_sites_only` (validation) and `awkward_truncated` (TSV conversion on a
truncated gzip, which refusing is the correct behaviour) fail exactly as they
did in the campaign; neither was touched.

### The mutation score is 113/113, not the 0.912 predicted in §14

| | Campaign | Re-run |
|---|---|---|
| score | 96/113 = 0.850 | **113/113 = 1.000** |
| caught by comparison queries | 96 | 96 |
| caught by shapes | — | 17 |
| undetected classes | 10 | none |
| wall | — | 1,548 s |

Section 14 predicted the full profile would close four of the ten classes, on
the reasoning that only four map to a constraint the consistency and SPARQL
profiles express. It closed all ten. The mapping from mutation class to
constraint was too literal: a corruption that does not violate its own class's
constraint frequently violates a neighbouring one — `corrupt_allele_kind`, for
instance, is caught not by a kind constraint but by the class shape that
requires the kind to be one of the enumerated individuals. Both unmutated
controls PASS in both sample representations and `corrupt_record_index` returns
`SHACL_VIOLATION` in both, so the perfect score is not a shape layer rejecting
conformant graphs.

### SHACL's cost by default is small, and I overstated it mid-run

Measured from the re-run, not estimated:

| Cell | Campaign validation wall | Re-run | Delta |
|---|---|---|---|
| `09` awkward cells (each) | 18.8–20.0 s | 20.3–22.5 s | +1.5 to +2.5 s |
| `12` `phaseB_validate_aggregate` | 46.3 s | 61.3 s | +15.0 s |
| `11` row3 (56,462 triples) | — | 24.2 s SHACL wall | — |

So the default profile costs roughly 10% on fixture-scale cells and 32% on a
1,000-record graph, scaling with triple count rather than being a fixed
overhead. The `--no-shacl` treatment given to `13_query_cost` is still right
for any experiment whose timings feed a table, but it is not urgent for the
small cells. One design consequence is worth recording: **SHACL runs as a
preflight gate**, so a shape failure costs the whole query layer for that cell
(the three failing covering-set rows report `0 queries`).

### The covering set found a real conversion defect

Three rows went from exit 0 to exit 1 — precisely the three combining
`--info-representation raw` with `--sample-representation expanded`:

| | expanded + structured | expanded + raw |
|---|---|---|
| rows | row1, row7 | row3, row9, row10 |
| triples | 94,919 | 56,462 |
| `calledAllele` | 1,972 | 1,972 |
| `alleleIndex` | 1,972 | **0** |

`emit_record_detail` gated the allele layer on `info_representation ==
"structured"`, reasoning that the Number=A/R/G value items are what join to the
allele resources. The expanded sample layer joins to them too:
`vcf_rdfizer.py:2595` emits `vcfc:calledAllele` on every
`vcfc:GenotypeAlleleCall` pointing at `<record>/allele/<index>`, regardless of
the INFO setting. Those configurations therefore produced **1,972 dangling
object references per 1,000 records**, with no `vcfc:alleleIndex` triple
anywhere in the file.

**This is the most useful single result in the re-run.** The defect was present
throughout the campaign and all ten rows exited 0 for its entire duration,
because the comparison queries count `calledAllele` edges without following the
join. The shape layer reported it as 5,916 violations the first time it ran.
Nothing else in the study demonstrates as directly why the two validation
layers are not redundant.

### What was changed

**1. `allele_layer_required(info_representation, sample_representation)`**
(`vcf_rdfizer.py`) replaces the gate with a disjunction over both axes. The
allele layer is minted when structured INFO **or** expanded samples ask for it,
and omitted only for `raw` + `condensed`, where nothing references it —
condensed emits no `calledAllele` at all. The sample representation is passed
down from `run_full_mode` through `emit_record_detail`.

**2. The census oracle had the identical defect, mirrored.** Fixing the emitter
alone turned the three failures from a shape violation into a census
`MISMATCH`: the graph now carried the allele triples, and `expected_census` —
which still merged the allele layer only under structured INFO — reported them
as six extra predicate rows, two extra class rows and a 1,972-triple `rdf:type`
discrepancy. The allele counters are now split out of `emitted_record_counters`
the way the genotype counters already were, and merged under the same
disjunction. Everything the emitter writes inside its `emit_alleles` branch
moves with them — the contig and assembly links included — or the two sides
would disagree again on the next raw-INFO run.

This is worth noting as a pattern: **the oracle re-derives the expectation from
the same representation flags the emitter reads, so a rule expressed in two
places can be wrong in two places.** Both now call the one predicate.

**3. `validation_fixtures.build_graph`** replicated the old rule as
`emit_alleles=include_info`; it now calls `allele_layer_required` so the
fixture harness cannot drift from the wrapper.

**4. `test/test_allele_reference_integrity_unit.py`** (new, 10 tests) pins the
truth table, asserts across all four representation combinations that no graph
references an allele it does not describe, asserts that the fix describes the
targets rather than silencing the references, asserts that raw INFO still
withholds the structured INFO layer, and checks the oracle's census expectation
on the same four combinations. Reverting either half of the fix fails it: the
pre-fix emitter rule reproduces exactly 4 dangling references on the test
fixture.

Unit suite: **851 tests, OK** (was 841).

### Verification of the fix

`11_covering_set` re-run on `vcf-rdfizer:local-d33d3af`: **10 cells — 10 ok, 0
non-zero.** Only the three affected rows changed, and each by exactly the same
amount:

| row | sample | INFO | triples before | after | delta |
|---|---|---|---|---|---|
| row3 | expanded | raw | 56,462 | 67,308 | +10,846 |
| row9 | expanded | raw | 56,462 | 67,308 | +10,846 |
| row10 | expanded | raw | 56,462 | 67,308 | +10,846 |
| all seven others | — | — | unchanged | unchanged | 0 |

The delta reconciles exactly against the fixture's 986 records and 1,972
alleles: 3 x 1,972 for `alleleIndex`/`alleleValue`/`alleleKind`, 986
`hasReferenceAllele`, 986 `hasAltAllele`, 986 `chromosome`, and 1,972 `rdf:type`
for the `ReferenceAllele` and `AltAllele` resources. Row3 reports
`status: PASS`, `comparisonStatus: PASS`, `shacl: PASS` with `violationCount 0`.

The intermediate state is worth recording, because it is what the second fix
was for. With only the emitter fixed, row3 went from `BLOCKED_BY_PREFLIGHT`
(5,916 shape violations) to `MISMATCH` — SHACL passing with 0 violations while
`q09_predicate_census` reported six extra predicate rows and a 12,878-vs-10,906
`rdf:type` discrepancy, and `q10_class_census` two extra class rows. The graph
was right and the expectation was wrong. Only after both halves read
`allele_layer_required` does the row pass.

### Ordering, for the next time this happens

1. Run `08_robustness` first. Its determinism cell is the cheapest possible
   answer to "does anything need re-running at scale?", and a matching digest
   retires the 49-hour tier outright.
2. Re-run the experiments whose *verdicts* the change could flip, not the ones
   whose *timings* it could shift — timings can be restated from the archive
   with a caveat; verdicts cannot.
3. Expect a stronger validator to fail things that used to pass, and read those
   failures as findings before reading them as regressions. Three of the four
   cell-level changes in this re-run were the new checks working.
