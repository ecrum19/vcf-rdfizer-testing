# Benchmarking plan

> **Runnable version: [`benchmarks/`](benchmarks/).** One script per section
> below, `benchmarks/run_all.sh` to drive them, and `benchmarks/analysis/` to
> turn the runs into CSV/JSON. [`benchmarks/README.md`](benchmarks/README.md) is
> the operator's guide; this document is the reasoning behind what the scripts
> do. Section numbers match.


The suite today (`test_full_spaceopt_all_compressions.sh`) runs one monolithic
job per input at `--validate-artifacts all --validation-engine all`. Everything
is coupled, validation dominates the cost, and a failure anywhere loses the
whole run. Worse for the paper: it produces numbers, not *claims*. Nothing in
that design isolates a single factor, so no sentence in the Results section can
be attributed to it.

This plan is organized the other way round — around the four things the paper
argues, with one experiment per argument.

| # | Claim | Type of claim | Experiment |
|---|---|---|---|
| C1 | `space-optimized` costs the same time as `plain` but far less disk | **equivalence** (time) + difference (disk) | §1 |
| C2 | `condensed` vs `expanded` is irrelevant at 1 sample, decisive at 1000s | **interaction** | §2 |
| C3 | Cost scales predictably with records and samples | **scaling** | §3 |
| C4 | The tool is robust, broadly capable, and configurable to a user's setup | **coverage / breadth** | §4 |
| C5 | Retrieval via SPARQL is worth the conversion, for repeated questions | **cost comparison** | §4.5 |

C1 and C2 are the two claims most likely to be attacked by a reviewer, because
both are partly *negative* ("does not differ much"). Sections 1 and 2 are
written to make those negatives defensible rather than assumed.

---

## 1. Storage mode: same compute, much less disk — **run, claim supported**

**The claim.** `--rdf-storage-mode space-optimized` produces the same triples
as `plain`, at a peak transient disk footprint several times smaller, with no
practically important change in wall time, CPU time, or peak memory.

> **Status: this experiment has been run and the claim holds.** The result was
> strong enough to change the tool: `--rdf-storage-mode` now **defaults to
> `space-optimized`** rather than being required in full mode
> (`DEFAULT_RDF_STORAGE_MODE`, changelog 2026-09-10). Fill the measured values
> into §1.4's table before drafting the Results paragraph; the rest of this
> section is the reporting scaffold and the list of things a reviewer will
> check, not work still outstanding.
>
> Two consequences for the manuscript. First, the paper can now state the
> default *and* the evidence for it in the same breath, which is a stronger
> configurability argument than describing a flag: the tool ships the setting
> its own benchmark selected. Second, every command in the paper that passes
> `--rdf-storage-mode space-optimized` explicitly is now passing a default —
> keep it explicit in the run manifests anyway (§5.4), but the prose should say
> it is the default so a reader reproducing the work does not think the flag is
> load-bearing.

Say *triples*, not *files*. Two artifacts genuinely differ in framing rather
than content: in space-optimized mode the aggregate is a **concatenated** gzip
stream assembled from the RMLStreamer parts, and when `gzip` is also a selected
`--rdf-compression` method that aggregate *is* the delivered `.nt.gz` artifact.
In plain mode the same deliverable is produced by gzipping one merged `.nt`, so
it is a single-member gzip. Both decompress to the same N-Triples; neither is
byte-identical to the other. Compare decoded triples or a canonicalized digest,
never the raw `.nt.gz` checksum, or a reviewer will be handed what looks like a
reproducibility failure.

### 1.1 Two things the reporting has to get right

The claim is established; these are the two ways writing it up can still go
wrong, and both are worth checking against the runs already completed.

**Check first whether the completed runs sampled peak workspace.** If they
recorded only final artifact bytes, that is the one thing worth re-running for
— see immediately below. It is cheap (a `du -sb` loop, no reconversion needed
for the small and medium sizes) and it is the metric the whole disk argument
rests on.

**Final artifact bytes are the wrong disk metric.** Both modes emit the same
triples, so `.hdt`, `.cottas`, and `.nt.gz` come out the same size. A table of
final output bytes will show ~0% difference and *appear to refute* the claim.
The quantity that differs is the **peak workspace footprint** during the run:
`plain` holds one uncompressed `.nt` aggregate; `space-optimized` holds a
`.nt.gz` aggregate plus one uncompressed chunk at a time. That is the number
that decides whether a 400 MB VCF fits on the volume you have, and it is not in
the metrics list today.

Measure it directly. Sample the run workspace on a fixed interval and keep the
maximum:

```bash
# alongside each run
( while :; do du -sb "$WORKDIR" 2>/dev/null | cut -f1; sleep 5; done ) \
  > "$RUNDIR/workspace_bytes.tsv" &
```

Report `max(workspace_bytes)`, and report it **normalized by uncompressed input
bytes** — a ratio like `3.1x` vs `0.6x` travels; raw gigabytes on your host do
not.

**"No difference" is not the same as "failed to find a difference."** A t-test
that does not reach significance is not evidence of equivalence — with n=3 it is
evidence of nothing at all. The manuscript needs an explicit margin:

> space-optimized is declared to have no practically important compute penalty
> if the 90% CI of the paired relative difference in median wall time lies
> entirely within ±10%.

Report the paired relative difference with its CI (TOST, or a bootstrap CI on
the paired ratios — either is fine) and state the margin alongside it. That
turns "we saw no difference" into a testable, and passable, claim.

Since the runs are already done, be precise about *when* the margin was fixed.
If it was set before the runs, say so — pre-registration is the strongest
version. If it was chosen after seeing the data, do not imply otherwise; state
it as a decision rule applied post hoc and let the CI carry the argument. A
±10% margin on a result that comfortably clears it is convincing either way,
and a reviewer who catches an implied pre-registration that did not happen will
discount the whole section.

### 1.2 A confound that must be held fixed

`--hdt-strategy single` cannot consume a gzip aggregate: a single `rdf2hdt`
pass would have to expand a second full uncompressed copy, which is the exact
cost `space-optimized` exists to avoid. Since `space-optimized` is now the
default, `single` requires an explicit `--rdf-storage-mode plain`. The
combination is refused, in every path that can reach it:

```text
--hdt-strategy single cannot read a gzip aggregate: one rdf2hdt pass would have
to materialize a second full uncompressed copy. Use --hdt-strategy partitioned,
or --rdf-storage-mode plain if you specifically need a single-pass HDT for
verification.
```

So storage mode × HDT strategy is *not* a full cross product. The paired
comparison in §1.3 holds `--hdt-strategy partitioned`. Do not put
`single` + `space-optimized` in any matrix; it is a documented refusal, not a
data point.

**`single` + COTTAS was silently ignored before 2026-09-10, and is now
refused.** COTTAS always needs bounded chunks, and both dispatch sites gate
partitioning on one boolean, so `--representations hdt,cottas --hdt-strategy
single` ran the partitioned path for both representations with the strategy
having no effect:

```python
compression_uses_partitioning(methods) and (
    any(method in COTTAS_COMPRESSION_METHODS for method in methods)
    or should_use_partitioned_hdt(...)
)
```

This matters retrospectively. **Any historical run in
`experiments/finished_experiments/` that combined `--representations hdt,cottas`
with `--hdt-strategy single` recorded partitioned HDT under a `single` label.**
The old suite passed `hdt,cottas`, so check before reusing any such run: the
numbers are valid measurements of partitioned generation and mislabelled as
anything else. On the current tool the same command exits 2, so no new cell can
be mislabelled this way.

`single` therefore changes observable behaviour only when all three hold: HDT
selected, COTTAS **not** selected, and `--rdf-storage-mode plain`.

**Do not run an HDT-strategy performance comparison at all.** Below
`--chunk-min-bytes` (128 MiB uncompressed RDF, the default) the partitioned
path emits one chunk and its merge is trivial, so the two strategies converge;
above it, partitioned is the only one that survives cohort scale. There is no
regime where `single` meaningfully wins on time, so a timing table comparing
them has no result to report. What `single` *is* good for is an equivalence
oracle — see §4.1.

### 1.3 Design

Paired, one input at a time, everything but the storage mode fixed:

| Factor | Value |
|---|---|
| `--rdf-storage-mode` | `plain` / `space-optimized` ← **the only variable** (pass both explicitly; `space-optimized` is now the default) |
| `--hdt-strategy` | `partitioned` (forced, see §1.2) |
| `--representations` | `hdt,cottas` |
| `--rdf-compression`, `--artifact-compression` | `none` |
| `--sample-representation` | `expanded` |
| Validation | off (`--mode validation` separately, §5) |
| Repetitions | 5, order interleaved |

Run this on **three input sizes**, not one. The interesting shape is that the
disk saving *grows* with input size while the time penalty stays flat — that is
the whole "essential for large genome files" argument, and it needs at least
three points to be visible. Suggested: the small fixture, `HG005` (139 MB), and
`NG1N86S6FC` (397 MB).

### 1.4 The figure that makes the point

One plot, two y-axes or two stacked panels, x = input size:

- **top:** peak workspace / input bytes — two diverging curves;
- **bottom:** wall time ratio (space-optimized ÷ plain) with CI band, and a
  shaded ±10% equivalence corridor the points sit inside.

That single figure says "free in time, cheaper in space, increasingly so" more
compactly than any table.

### 1.5 Optional, and the sharpest version of the claim

Run the largest input on a volume with a hard quota sized between the two peak
footprints, and show `plain` failing on disk exhaustion where
`space-optimized` completes. A demonstrated capability boundary is stronger
evidence than a percentage, and it is one command:

```bash
# e.g. a loopback fs or a container with a bounded volume
truncate -s 120G /tmp/quota.img && mkfs.ext4 -q /tmp/quota.img
```

Report it as a capability result, not a benchmark, and keep it out of the
timing medians.

---

## 2. Sample representation: negligible at one sample, decisive at a cohort

**The claim.** `condensed` and `expanded` are near-indistinguishable on
single-sample VCFs, and differ by orders of magnitude on multi-sample VCFs.

That is an **interaction** between `--sample-representation` and sample count,
and it must be measured as one. Two bars (a single-sample file and a cohort
file) technically show it, but they show it at exactly two points, and the two
points are different files — a reviewer will ask whether the effect is the
sample count or the file. The fix is a ladder in sample count with everything
else held constant.

### 2.1 Build the ladder by subsetting one source file

Derive every rung from `1000G_phase3_chr20.vcf.gz` (2,504 samples), fixing the
record count so *only* sample count varies:

```bash
SRC=vcf_data/1000G_phase3_chr20.vcf.gz

# sample list, straight from the #CHROM line
bcftools view -h "$SRC" | tail -1 | cut -f10- | tr '\t' '\n' > /tmp/all_samples.txt

# fix the record set ONCE, so every rung has byte-identical variant content
bcftools view --no-version -Oz -o /tmp/base10k.vcf.gz \
  <(bcftools view "$SRC" | awk '/^#/{print;next} c++<10000{print}')
bcftools index -t /tmp/base10k.vcf.gz

for S in 1 4 16 64 256 1024 2504; do
  head -n "$S" /tmp/all_samples.txt > /tmp/s_$S.txt
  bcftools view -S /tmp/s_$S.txt -I --no-version \
    -Oz -o "vcf_data/derived/1000G_10k_s${S}.vcf.gz" /tmp/base10k.vcf.gz
done
```

`-I` matters: it suppresses INFO recomputation, so `AC`/`AN` and the rest of the
INFO column are byte-identical across rungs. Without it, the INFO layer changes
with S and contaminates the triple counts you are attributing to the sample
layer. Record the exact `bcftools` version and commands in the manifest — these
are derived inputs and must be reproducible.

### 2.2 The primary metric is deterministic, so n=1 is enough for it

**Emitted triples** is the primary outcome here, and conversion is
deterministic: one run per cell gives the exact number, with no repetitions and
no error bars needed. Only the *secondary* metrics (wall time, peak RSS, peak
workspace, artifact bytes) need 3 repetitions. This makes the whole ladder cheap
— 7 rungs × 2 modes = 14 conversions, on 10k-record inputs.

The theory predicts, per the
[sample-representation guide](../vcf-rdfizer/docs/sample-representation-guide.md):

```text
expanded  sample-layer structure  ~  V x S x F        slope ~1 in S
condensed sample-layer structure  ~  S + (V x F)      slope ~0 in S
```

So plot log(triples) against log(S) and fit both slopes. **A fitted slope of
~1.0 versus ~0.0 on the same axes, from the same variant content, is the
strongest form this claim can take**, and it contains the single-sample result
as its left endpoint rather than as a separate assertion.

### 2.3 Report the crossover explicitly

At S=1 the two modes should be within a few percent — quantify it and use the
same pre-registered ±10% equivalence framing as §1.1, because "does not impact
single-sample files much" is again a negative claim. At S=2504 report the ratio
as a multiple (expected: large; the guide's worked example gives ~1,070× on
*structure*, though final artifact bytes shrink far less because the scalar
values persist inside vector literals — say so plainly, or a reviewer will read
the structural ratio as a compression claim and find it unsupported).

Report both, side by side, and label them differently:

| S | triples (exp) | triples (cond) | structure ratio | `.hdt` bytes (exp) | `.hdt` bytes (cond) | byte ratio |
|---|---|---|---|---|---|---|

The gap between the two ratio columns is an honest and interesting result: the
saving is in graph structure, not in information content, and HDT's dictionary
already recovers part of it. Owning that distinction is more convincing than a
single headline number.

### 2.4 Confirm on a real cohort, then stop

Two anchor runs on unsubsetted real files — `1000G_phase3_chr20.vcf.gz`
(2,504 samples) and one single-sample GIAB file (`HG004`) — confirm the ladder's
prediction at full scale. These are anchors, not the evidence; the ladder is
the evidence.

---

## 3. Scaling: controlled ladders, not a regression across the corpus

You are right that the corpus cannot carry a scaling curve. `HGSVC2` is a
structural-variant callset with sequence-resolved `REF`/`ALT` alleles;
`1000G_phase3_chr20` is a phased 2,504-sample SNV cohort; `HG004`/`HG005` are
single-sample small-variant benchmarks; the five provider files are consumer
WGS. Fitting `log(wall) ~ log(input_bytes)` across those ten points does not
estimate the tool's scaling — it estimates a mixture of genomic content
differences, and the residuals will be large and uninterpretable. Any reviewer
who knows the datasets will say so.

Split the question in two.

### 3.1 Cost model — from derived ladders (this is where slopes are fitted)

Two one-factor ladders, each derived by subsetting a **single** source file, so
variant class, caller, assembly, and header stay fixed:

| Ladder | Source | Varies | Held fixed |
|---|---|---|---|
| **Records** | `HG005_GRCh38.vcf.gz` | ~10k → 100k → 1M → all records | 1 sample, same caller/assembly |
| **Samples** | `1000G_phase3_chr20.vcf.gz` | 1 → 2504 samples (§2.1) | 10k records, same variant content |

```bash
# records ladder, by leading-record count (same awk idiom as above)
SRC=vcf_data/HG005_GRCh38.vcf.gz
for N in 10000 100000 1000000; do
  bcftools view --no-version -Oz -o "vcf_data/derived/HG005_r${N}.vcf.gz" \
    <(bcftools view "$SRC" | awk -v n="$N" '/^#/{print;next} c++<n{print}')
done
```

Fit and report, with CIs, on these ladders only:

```text
log(triples)      ~ log(records)     # at fixed S
log(wall_seconds) ~ log(triples)
log(triples)      ~ log(samples)     # at fixed V, per mode  -> the §2 slopes
```

State explicitly that these are *empirical* scaling exponents over the measured
range, not algorithmic bounds — the existing plan already says this, and it is
worth keeping.

### 3.2 Corpus breadth — a stratified table, deliberately not a curve

The ten real files answer a different question: does the tool handle real,
heterogeneous VCFs? Present them as a table stratified by dataset family, with
per-file **structural descriptors** next to the cost, and normalize by emitted
triples rather than by input bytes:

| Family | File | Records | Samples | Sample calls | Allele shape | INFO/FORMAT keys | VCF ver | Triples | s / Mtriple | bytes / triple |
|---|---|---|---|---|---|---|---|---|---|---|
| SV batch | `HGSVC2` | | 32 | | sequence-resolved SV | | 4.2 | | | |
| Cohort | `1000G_phase3_chr20` | | 2504 | | biallelic SNV, phased | | 4.1 | | | |
| GIAB single | `HG004`, `HG005`, `0GOOR_HG002` | | 1 | | SNV/indel | | 4.2 | | | |
| Consumer WGS | the five provider files | | 1 | | SNV/indel | | 4.2 | | | |

Two reasons this works better than a regression:

- **Normalizing by input bytes is exactly what makes `HGSVC2` incomparable.**
  Its long sequence alleles mean many bytes per record. Normalizing by *emitted
  triples* removes that: cost per triple should be roughly stable across
  families, and if it is, **that stability is itself the robustness result** —
  a much better finding than a slope. Where it is *not* stable, the descriptor
  columns explain why, in the same row.
- The descriptors pre-empt the objection instead of absorbing it. A reader who
  sees "sequence-resolved SV, 32 samples" next to an off-trend cost does not
  read it as noise.

Say in the text that no cross-family regression is fitted, and why. Declining to
fit a model you cannot justify reads as rigor, not as a missing result.

---

## 4. Robustness, capability, and configurability

This is the argument the current plan supports least, and where the most is
available cheaply. Four sub-arguments; the first is the load-bearing one.

### 4.1 Configurability does not cost correctness ← the keystone experiment

Every option in §1 and §2 is a *different physical encoding of the same
information*. That is the claim that makes configurability a feature rather
than a menu of ways to get different answers — and it is directly testable with
the six queries already specified in
[`vcf_rdfizer_testing_queries_plan.md`](vcf_rdfizer_testing_queries_plan.md)
(Q1 density, Q2 allele shape, Q3 Ti/Tv, Q4 FILTER, Q5 per-sample genotype
classes, Q6 GT-derived AC/AN).

Run all six against a VCF-side oracle (cyvcf2 / `bcftools`) and against every
representation of the same input:

| Encoding | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 |
|---|---|---|---|---|---|---|
| VCF oracle (cyvcf2) | — | — | — | — | — | — |
| `.nt`, expanded | | | | | | |
| `.nt`, condensed | | | | | | |
| HDT, expanded | | | | | | |
| HDT, condensed | | | | | | |
| COTTAS, expanded | | | | | | |
| COTTAS, condensed | | | | | | |
| `.nt` from `plain` vs `space-optimized` | | | | | | |

Add one more row that is not a representation but a *mechanism* check:

| Mechanism | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 |
|---|---|---|---|---|---|---|
| HDT via `--hdt-strategy single` (one `rdf2hdt` pass) | | | | | | |
| HDT via `--hdt-strategy partitioned` (chunk + `hdtc` merge) | | | | | | |

This is the only experiment `single` is still worth running, and it is worth
running: it demonstrates that chunked generation plus an `hdtc` merge is
equivalent to a single-pass conversion of the same graph. Without this row you
have no evidence that the merge path is lossless; with it,
partitioned-by-default is justified rather than merely convenient — and since
`space-optimized` is now the default, that justification is load-bearing for
the tool's out-of-the-box behaviour, not just for a benchmark table.

The configuration is now enforced rather than merely recommended — anything
else exits 2 (§1.2):

```bash
vcf_rdfizer.py --mode full --input <small.vcf.gz> \
  --rdf-storage-mode plain --representations hdt \
  --rdf-compression none --hdt-strategy single --out ./experiments
```

Assert identical triple counts and identical query answers, not identical
bytes.

All cells equal to the oracle is a single, quotable sentence: *every
configuration answers all six biological queries identically to the source
VCF.* Note that Q5 and Q6 are the ones that must traverse the sample layer, so
they are precisely where condensed could have broken and did not — call that
out rather than burying it in a uniform table.

Run this on a small input where `--validation-engine all` is affordable.
Cross-engine agreement at small scale is the deliverable; at large scale it is
just expense.

### 4.2 Three configurability axes the plan is missing

The option space is larger than the "96 configurations" this document
previously claimed, because it omitted three axes that trade triples for
queryability in exactly the same way `--sample-representation` does:

| Option | Values | Trade-off |
|---|---|---|
| `--info-representation` | `structured` / `raw` | `structured` emits one `vcfc:InfoFieldValue` per record per key plus the per-allele layer, making INFO queryable; `raw` keeps only `vcfc:infoRaw` |
| `--header-representation` | `structured` / `basic` | `structured` types each `##` line with its vocabulary subclass and lifts FILTER/ALT/contig attributes into properties; `basic` keeps untyped header lines |
| `--vcf-version` | `auto`, `4.1`–`4.5` | selects the conformance overlay: which INFO keys flatten a tuple, whether tuples repeat per ALT, whether local-allele (`LA`/`LR`/`LG`) and base-modification FORMAT families exist |

`--info-representation` deserves the §2 treatment in miniature: INFO is
per-record, so its cost scales with V rather than V×S, and structuring it is
plausibly *more* expensive than expanded samples on single-sample WGS files —
which is a genuinely useful result for a user choosing settings, and it
completes the "pay triples for queryability" story on a second axis. One
paired run per mode on `HG005` plus one on `HGSVC2` (SV records carry heavy
INFO) is enough.

`--vcf-version` is a robustness axis rather than a cost axis. The corpus already
spans 4.1 (`1000G`) and 4.2 (everything else); add small fixtures declaring
4.3, 4.4, and 4.5 and show the version-dependent emitter behaviour actually
changes — per-ALT tuple repetition, `LA`/`LR`/`LG`, base modifications. Include
one file with a missing or malformed `##fileformat` and show it converts under
the 4.5 fallback **without emitting a `vcfc:VCF4xFile` class**, i.e. it does not
claim a version gate it cannot verify. That "degrades honestly" behaviour is a
robustness result worth a sentence.

### 4.3 Robustness evidence that already exists and is not being used

Two things in the repo are stronger evidence than any timing table, and neither
appears in the plan:

- **The mutation score.** `docs/vcf-coverage.md` records 96/113 (85%) across 60
  mutations, with every gap enumerated and named in
  `test/validation_mutations.py`. This is a *quantified* statement that the
  validation suite would detect corruption of specific VCF elements — far
  beyond "we ran it and it exited 0." Regenerate it against the pinned commit,
  cite the number, and cite the remaining-gaps list as the limitation. A
  reviewer trusts a paper that reports 85% with the gaps listed considerably
  more than one that reports nothing.
- **Round-trip identity.** `--mode compress` → `--mode decompress`, then assert
  the triple count (and a canonicalized checksum) matches the original. Cheap,
  strong, and it exercises two modes the suite never touches.

Add two more that cost almost nothing:

- **Determinism.** The same input and configuration twice → identical triple
  count and identical canonicalized artifact digest. One extra repetition,
  already being run.
- **`--mode index` idempotence.** Re-indexing an existing `.hdt`/`.cottas`
  leaves query results unchanged.

### 4.4 Awkward-input handling, and configurability under a real constraint

**Awkward inputs.** A small table of deliberately difficult real-VCF situations,
each with a one-line fixture and the observed behaviour — converted, or refused
with a clear diagnostic. Both outcomes are acceptable results; a crash or a
silently wrong graph is not. Candidates: sites-only VCF (no FORMAT/sample
columns), symbolic alleles (`<DEL>`, `<INS>`), breakend notation, ploidy > 2,
haploid and half-called genotypes (`./1`), missing values throughout, an empty
FILTER (`.`) vs `PASS`, a truncated `.gz`, CRLF line endings, and a header
declaring a FORMAT key absent from the records. This directly supports "does
MANY useful VCF things," and it is honest about the edges.

**Configurability under constraint — the strongest form of the claim.** "It is
configurable for your technical setup" is proven by *running under a
constraint*, not by listing flags. Take the largest input and a fixed memory
ceiling well below what the default settings need, then show which
configurations complete:

```bash
docker run --memory=8g --memory-swap=8g ... \
  vcf_rdfizer.py --mode full -i NG1N86S6FC.vcf.gz \
    --rdf-storage-mode space-optimized --hdt-strategy partitioned \
    --chunk-min-bytes 67108864 \
    --chunk-target-bytes 134217728 \
    --chunk-max-bytes 268435456 \
    ...
```

Report a small feasibility matrix: memory ceiling (8/16/31 GB) × configuration
(defaults / low-peak chunk settings / condensed) → completed or OOM, with wall
time where it completed. A table showing that a file which fails at defaults on
8 GB succeeds with documented flag changes is the single most convincing piece
of evidence for the configurability claim, because it shows the flags *matter*
rather than merely existing.

**Extensibility.** One smoke run each for `--rules` with a custom mapping and
for `--mode link` across its three linker tiers (`rsid-dbsnp` declarative,
`gene-demo` reference bundle, `rsid-ensembl` live resolver). Document the honest
interaction while you are there: custom rules consuming `sample_calls.tsv` or
`sample_format_values.tsv` are **rejected** in condensed mode, by design, since
running them would emit both graph shapes and reintroduce the expansion
condensed exists to avoid. A documented, deliberate refusal is a design result,
not a gap.

---

### 4.5 SPARQL retrieval against a VCF parser ← what a biologist actually asks

The question a bioinformatician asks first is not whether the graph is correct;
it is *what does it cost me to get an answer out of it, compared with parsing
the VCF?* Nothing in §1–§4.4 answers that, and the manuscript already carries a
`TBD` table for it.

**Almost none of this needs building.** The validation suite computes every
expected value **twice** — once by parsing the VCF with cyvcf2, once by querying
the graph — so every validated run is already a like-for-like measurement of a
SPARQL engine against a purpose-built parser on identical work, with the
answers proven equal first. The tool writes it to
`reports/validation/<id>/benchmark.json` and `benchmark.csv`, and `metrics.csv`
carries `validation_oracle_seconds` and `validation_engine_query_seconds`
summary columns. It was simply never collected.

So §4.5 is a reporting exercise plus repetitions, not a new harness.

#### The trap in the data

`benchmark.csv` has one row per engine per query with `wall_seconds` and
`oracle_wall_seconds` side by side. **They are not two measurements of the same
thing:**

| Column | Covers |
|---|---|
| `wall_seconds` | this **one** query, on this engine |
| `oracle_wall_seconds` | the parser's total for **all** queries, repeated on every row so the file needs no join |

A row-wise ratio against `oracle_wall_seconds` divides one query by twenty-seven.
Anyone who plots that column naively publishes a number wrong by that factor.

**`oracle_query_seconds` is the per-question column**, added 2026-09-10, and it
*is* row-wise comparable against `wall_seconds`. It is attributed from four
directly measured phases of the oracle's single pass:

| Phase | Measured |
|---|---|
| `readerOpenSeconds` | open the file, parse the header |
| `scanSeconds` | the record loop, in total |
| `sampleBlockSeconds` | the per-sample genotype/AC-AN portion inside that loop |
| `assemblySeconds` | building the per-query expected structures |

Every query pays open + scan + assembly. Only the **sample-level** queries — Q5,
Q6 and Q13 — additionally pay for the per-sample block, and `benchmark.json`'s
`oracle.sampleLevelQueries` names them so the attribution is auditable rather
than implicit.

That split is the reason per-query oracle numbers are worth having. Measured on
the shipped fixtures:

| Fixture | Samples | Scan | Sample block | Assembly |
|---|---:|---:|---:|---:|
| `test-1k.vcf` | 1 | 0.037 s | 0.006 s (15.5%) | 0.018 s |
| `test-larger-multisample.vcf.gz` | 2,504 | 180.7 s | 132.8 s (**73.5%**) | 149.2 s |

So on a cohort file a genotype question costs the parser substantially more than
a record-level one, and an aggregate-only comparison averages that away.

**One known coarseness, in the conservative direction.** `assemblySeconds` is
charged to every query equally, and on a cohort file it is not small — 149 s
against a 181 s scan above — because it sorts the per-sample counters. Most of
that work really belongs to the sample-level queries, so the attribution
*over-charges* record-level queries on multi-sample inputs and therefore
understates the very gap it is measuring. Splitting it means restructuring the
post-loop assembly into per-query builders. Until then the bias is stated rather
than hidden, and it errs against the paper's own argument.

**Why attributed and not measured in isolation.** The oracle is deliberately
one pass that fills every query's counters together — the right design for an
oracle, and the reason it is affordable at all. There is therefore no per-query
slice of it to time. Gating the pass per query was considered and rejected: the
accumulators in the sample block feed the expected values, so a gate left on in
a correctness run would corrupt the oracle that every equality claim in the
paper rests on. Measuring phases and stating the attribution rule is the honest
alternative, and the rule is one sentence long.

Both views are emitted: `data_querycost.csv` for the aggregate (engine total vs
oracle total over the same full set) and `data_querycost_per_query.csv` for the
per-question comparison.

#### The two sides have different cost shapes, and that is the result

```text
parser   parse + census, paid in full on every invocation. No index.
SPARQL   setup once (index/load), then query. Setup amortizes; queries do not.
```

A one-question workload therefore favours the parser and a repeated-question
workload favours the graph. So the headline is not a speed factor but a
**break-even**: how many repeated queries before the graph's setup has paid for
itself, `n >= setup / (oracle - query)`. Quoting "Nx faster" without naming the
regime it came from is exactly the overclaim the Discussion says it is avoiding.

Two further honesty requirements:

- **Conversion cost is in neither column.** The graph has to exist first. Quote
  it from §3 alongside the retrieval numbers — not folded in, and not omitted.
- **Scale changes the answer, and the tool's own docs say so.** On a 312-triple
  fixture the engine ordering is dominated by per-process startup: Comunica and
  HDT spawn one process per query and take ~25 s for 27 queries where cyvcf2
  takes 0.003 s. That says nothing about a cohort-sized graph. Run at least two
  scales, and report the small one as a startup artefact rather than a
  retrieval result.

#### Design

| Factor | Value |
|---|---|
| Scales | one small fixture, one real single-sample file (≥100 MB) |
| Engines | all four at the small scale; `qlever` only at the large one |
| Repetitions | 3, medians reported |
| Query set | the suite's full set — not selectable, and a fairer basis than a hand-picked subset. Per-query rows come out regardless |
| Precondition | validation status `PASS` in the same row; equality before speed |

`--validation-engine all` at the large scale would spend hours measuring
Comunica's process startup. Don't.

#### What to report

Per engine and scale: median engine query seconds, median oracle seconds for the
same work, their ratio, setup seconds, break-even repetitions, and the
validation status that licenses the comparison. State the regime, name the
conversion cost, and assert no ranking the data does not carry.

The honest summary this supports is the one the Discussion already wants: RDF is
a *complementary access layer*. It loses on a single ad-hoc question against a
purpose-built parser, and wins where the parser has nothing to offer — repeated
querying, cross-file joins over a common model, and links to gene/phenotype
resources. A break-even number makes that concrete instead of rhetorical.

---

## 5. Execution mechanics

The claim-driven design above replaces the old cross-product framing, but three
mechanical points from the earlier draft still hold and are what make it
affordable.

### 5.1 Coverage is a covering set, not a cross product

For *functional* coverage — every option value exercised, plus every option
pair covered at least once — six small-input runs suffice:

| # | sample-rep | info-rep | storage | rdf-comp | reprs | artifact-comp | hdt-strategy |
|---|---|---|---|---|---|---|---|
| 1 | expanded | structured | space-optimized | gzip | hdt,cottas | gzip | partitioned |
| 2 | condensed | raw | plain | brotli | hdt | brotli | single |
| 3 | expanded | raw | plain | brotli | hdt | gzip | auto |
| 4 | condensed | structured | space-optimized | gzip | cottas | brotli | auto |
| 5 | expanded | structured | space-optimized | brotli | hdt,cottas | brotli | partitioned |
| 6 | condensed | raw | plain | gzip | cottas | gzip | partitioned |

This is the correctness sweep and belongs on **small** inputs only.

Two placement constraints from §1.2 shape this table, and both are easy to get
wrong:

- **Row 2 is the only legal home for `single`.** It needs `plain` storage
  *and* `hdt` without `cottas`. Both other placements now exit 2 rather than
  running: `single` beside `space-optimized` was always refused, and `single`
  beside `cottas` is refused as of 2026-09-10 (it used to be silently ignored).
  The table cannot be got wrong quietly any more, but it can still fail a whole
  sweep at cell 2, so keep the covering set in this shape.
- **Row 3 is where `auto`'s HDT decision is actually exercised**, because it
  selects `hdt`. In rows without HDT (row 4) `auto` is a no-op, so a covering
  set that only ever pairs `auto` with `cottas` does not test the policy at all.

### 5.2 Separate conversion from validation

Conversion is minutes; validation is hours. Never let them share a run.

```bash
# Phase A - conversion + compression, no validation. Cheap, all configs.
vcf_rdfizer.py --mode full -i "$VCF" ... -o ./experiments

# Phase B - validation against the artifacts Phase A already produced.
vcf_rdfizer.py --mode validation --rdf ./experiments/<name>/<name>.nt.gz ... -o ./experiments
```

A re-runnable Phase B means a validation bug costs you Phase B, not the six
hours of conversion in front of it. It also exercises `--mode validation`,
which the current suite never does. At scale, prefer
`--validation-engine qlever` or `--validate-artifacts hdt`; reserve
`--validation-engine all` for §4.1's small-input cross-engine table, where
agreement is the actual deliverable.

### 5.3 Modes the current suite never touches

`--mode tsv`, `--mode compress`, `--mode decompress`, `--mode index`,
`--mode link`, `--mode validation`, and `--rules`. Each needs one small-input
smoke run; §4.3 and §4.4 give most of them a purpose beyond smoke.

### 5.4 Operational notes

- **Run one experiment at a time.** 8 cores / 31 GB / no swap. Two concurrent
  runs is how the `HG004` job ended up holding 17 GB while `HGSVC2` needed it.
  The §4.4 feasibility matrix is the *only* place a memory ceiling is
  deliberately imposed; everywhere else a constrained run is a contaminated
  measurement.
- **Detach properly** (`systemd-run --user --scope`, or `nohup`). Ctrl-C on the
  wrapper leaves its Docker container running: that is exactly how the `HG004`
  validation kept going for three days after the run "ended", and how its
  `.nt.gz` got deleted out from under a live reader.
- **Check `.progress/*.jsonl` first** when a run looks stuck. A progress file
  with an old mtime tells you which stage hung and when, in one command.
- **Pin `--rdf-storage-mode` explicitly in every manifest, even though it now
  has a default.** Same reasoning as `--hdt-strategy auto` (§3.1, §5.4): a
  default is a policy that can change between releases, and a manifest has to
  record the mechanism that ran. The prose can say "the default"; the manifest
  should say `space-optimized`.
- **Record the tool commit** in every run directory, plus the `bcftools`
  version and exact subsetting commands for the §2.1 and §3.1 derived inputs.
  Comparing numbers across runs is meaningless without the first; the derived
  ladders are irreproducible without the second.
- **Sample workspace size** (§1.1) alongside every run, not just the §1 ones —
  it is nearly free and it is the metric that makes the disk argument.
- **Pre-register the §2.3 equivalence margin** in the manifest before the first
  run of that ladder, and cite the manifest in the manuscript. §1's margin can
  no longer be pre-registered — report it honestly as §1.1 describes. Margins
  that appear to have been chosen after the fact are the easiest thing for a
  reviewer to reject, so getting §2's right matters more now, not less.

---

## 6. What each section yields in the manuscript

| Section | Deliverable | Cost |
|---|---|---|
| §1 | Fig: workspace ratio + time-equivalence corridor vs input size | **done** — 30 runs (3 sizes × 2 modes × 5 reps) |
| §2 | Fig: log(triples) vs log(samples), two slopes; crossover table | 14 conversions + 3 reps on 3 rungs |
| §3.1 | Table: empirical scaling exponents with CIs | 2 ladders, ~8 runs |
| §3.2 | Table: stratified corpus with structural descriptors | 10 runs, 1 config |
| §4.1 | Table: 6 queries × 7 encodings, all equal to oracle | small input, 1 sweep |
| §4.2 | Table: INFO/header representation cost; version-conformance results | ~8 small runs |
| §4.3 | Mutation score 96/113 + round-trip + determinism results | already exists / near-free |
| §4.4 | Table: awkward inputs; feasibility matrix under memory ceilings | ~15 small + 9 large runs |
| §4.5 | Dataset: SPARQL vs cyvcf2 per engine/scale, with break-even | 6 runs (already-collected timings) |

§1 is already complete. Of what remains, §4.4's large-input cells are the only
expensive part: §2, the claim most likely to be attacked, runs entirely on
small derived inputs, which is the point of deriving them.

Recommended order from here: §2 (the other headline claim, cheap), then §4.1
(the keystone, and it now also validates the partitioned default the §1 result
introduced), then §3, then §4.2–§4.4.
