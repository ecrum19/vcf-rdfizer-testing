# Indexed regional access: an added arm for the retrieval comparison

Status: **implemented and smoke-tested on vcf-bench-1; the full sweep has not
been run.** The harness, the runner, the queries and the analysis are in place,
and a reduced run of both scales passed with every arm agreeing (see "What is
verified"). No reportable measurement has been taken yet.

**Scope: a standalone investigation.** `14_regional_access.sh` is not in
`run_all.sh` or any profile, and the runner's tests are outside VCF-RDFizer's
CI suite. It is run by hand when wanted. The
manuscript still keeps its placeholder in §4.2 (the `\authorquery` after
"Queryable Genomic RDF as a Complementary Access Layer") until it has.

## What it is

A VCF-side comparator that uses a coordinate index, and a set of
region-restricted questions that give that index something to do.

The existing VCF side of the retrieval comparison (§3.6, `13_query_cost`) is
cyvcf2 streaming the whole file, with `bcftools query` for exact FILTER text.
This adds a third VCF-side arm:

- the source VCF compressed with `bgzip` and indexed with `tabix`, or with a
  CSI index where a contig exceeds 2^29 bp;
- the same questions answered by seeking to the region through that index —
  `bcftools query -r`, and cyvcf2's `VCF(path)(region)`.

## Why it matters

The paper's retrieval result is conditional, and one half of it rests on an
unindexed baseline.

1. **The current VCF baseline cannot be selective.** Every one of the thirteen
   questions costs cyvcf2 about 11.5 s on the 100,000-record `HG005_GRCh38`
   slice, because it must scan the file whichever question it is. QLever answers
   in 0.005–4.66 s, so the paper reports SPARQL as 2.5–2300× faster *per
   question*.
2. **That comparison is fair for whole-file questions and unfair for regional
   ones.** None of Q1–Q13 is region-restricted, so the existing design is
   internally consistent. But the Discussion's conclusion — the RDF path "wins
   on selective, repeated and ad hoc interrogation" — generalizes to exactly the
   kind of question where the VCF world does not scan.
3. **A reviewer familiar with VCF will ask for it.** Indexed regional access is
   how VCFs are queried in practice. Without this arm, the claim that SPARQL is
   faster on selective questions is demonstrated only against the one VCF access
   mode nobody uses for selective questions.
4. **It tests a real weakness of the graph side too.** HDT and COTTAS answer
   triple patterns, not numeric ranges, so a `FILTER` on `vcfc:pos` has no
   positional index to use and those engines will scan every `vcfc:pos` triple.
   QLever may do better because it orders numeric values in its index. The arm
   therefore also extends the "engine selection is the performance decision"
   finding to a new query shape.

Either outcome improves the paper. If SPARQL still wins on repeated regional
questions, the claim becomes stronger than it is now. If tabix wins, the paper
states plainly that indexed VCF remains the fastest route for coordinate-bounded
retrieval and that the RDF path's advantage is in joins, cross-file and
cross-resource questions — which is what the Discussion argues its value is
anyway.

---

## What was built

| Piece | Location |
| --- | --- |
| Runner | `vcf-rdfizer/src/validation/regional_runner.py` |
| Queries | `vcf-rdfizer/src/validation/queries/regional/{common,expanded}/r0*.rq` |
| Tests | `vcf-rdfizer/test/test_regional_runner.py` and `test_regional_runner_driver.py` (75 tests; not in CI) |
| Image | `tabix` added to the Dockerfile — it ships `bgzip` and `tabix`, which `bcftools` alone does not |
| Harness | `vcf-rdfizer-testing/benchmarks/14_regional_access.sh` |
| Analysis | `collect_metrics.py`, and `datasets.py regional` |
| Docs | `vcf-rdfizer/docs/validation.md`, "Indexed regional access" |

The runner lives with the validation code rather than in the benchmark repo
because it reuses that module's engine abstraction (`build_engine`) and its
classification helpers. Reusing `classify_variant_shape`, `classify_genotype`
and `filter_status` rather than reimplementing them is what makes a regional
answer comparable to a whole-file one: the two are classified by the same code.

`14_regional_access.sh` is the only experiment that does not drive the wrapper
CLI — the wrapper has no mode for this — so it runs the runner inside the pinned
image directly through a new `bm_run_raw`. Image digest, host, timings and the
`bench.json` record are identical to every other cell, so both kinds land in the
same dataset.

### Questions

| ID | Question | Query file |
|---|---|---|
| R1 | Record count in a window | `r01_region_record_count.rq` |
| R2 | Allele-shape distribution in a window | `r02_region_variant_shape_counts.rq` |
| R3 | Ti/Tv in a window | `r03_region_titv.rq` |
| R4 | FILTER distribution in a window | `r04_region_filter_distribution.rq` |
| R5 | Per-sample genotype classes in a window | `r05_region_sample_genotype_counts.rq` |

Each is the whole-file query plus a contig and POS restriction; the
classification logic is character-for-character the original. `{{CHROM}}`,
`{{START}}` and `{{END}}` are substituted per window. R5 is provided for the
`expanded` representation only, matching `13_query_cost`; a condensed variant
would need its own template because the sample layer is reached differently.

### Arms

| Arm | Access path |
| --- | --- |
| `cyvcf2-scan` | whole-file iteration with a POS filter (baseline) |
| `cyvcf2-indexed` | `VCF(path)(region)` over the bgzipped, indexed copy |
| `bcftools-indexed` | `bcftools query -r` |
| `comunica`, `hdt`, `cottas`, `qlever` | the same question as SPARQL |

---

## Three design decisions the original sketch did not anticipate

### A window means POS, not overlap

This is the one that would have silently invalidated the comparison. A tabix or
CSI seek returns every record whose **span overlaps** the region, so a deletion
beginning before the window and reaching into it comes back from htslib, while a
SPARQL `?pos` filter excludes it. Left alone, the arms would disagree on any
window whose left edge cuts an indel — and it would read as a graph defect
rather than a coordinate convention.

Every VCF arm therefore keeps the index seek and then drops records whose POS
falls outside the window. The seek still does the work being measured; the
post-filter costs one integer comparison per returned record and is applied by
every VCF arm alike. `REGION_SEMANTICS` in the runner states this, and the tests
pin it.

### The scan arm is timed on fewer windows than the others

The scan arm's cost does not depend on the window, because it reads the file
whichever region is asked for. Measured on vcf-bench-1 it is 0.64 s a question
on the slice, far below the ~11.5 s first assumed from `13_query_cost`'s
whole-file questions. So timing it on every window would not be expensive, only
1,200 measurements of the same number. It is timed on 3 windows per size
(`--scan-windows-per-size`, configurable) and reported as a flat baseline
rather than a curve. `--thin-arms` can give any other arm the same treatment. Correctness is unaffected: the equality
reference is a single whole-file pass that fills every window at once, and that
pass is deliberately **not** timed, because answering eighty windows in one pass
is not what a one-question user pays for.

Measured cost: a region-restricted question takes Comunica, HDT and COTTAS
about 1 s on the small input (against 23–45 s for the whole-file questions), so
the **small scale is roughly an hour** with every engine on every window. The
slice, with the VCF arms and QLever only, is a few minutes.

### Windows are anchored on real records

A GIAB benchmark VCF covers a few percent of the genome. Uniformly drawn 1 kb
windows would be almost all empty, and the experiment would measure the cost of
returning nothing — four window sizes would be a sparsity ladder, not a
selectivity ladder. Each window therefore starts at a randomly chosen record
position, from a fixed seed, so every window holds at least one record and every
arm sees identical regions. The realised record count per window is recorded, so
results can be plotted against actual selectivity rather than against nominal
window size.

---

## Protocol

Unchanged from §3.6 in substance: identical scope on both sides, exact equality
verified before any timing is compared, replicates, and one-time costs reported
separately. Specifics:

- **Windows.** 1 kb, 100 kb, 1 Mb, 10 Mb; 20 per size; seed `20260923`; written
  to `windows.json` so a rerun measures the same regions.
- **Replicates.** 3, medians reported, raw rows kept.
- **One-time costs.** `bgzip` and index time on the VCF side, engine setup on
  the SPARQL side, in `data_regional_setup`. Neither is folded into a
  per-question number. Conversion cost is in neither and belongs to the
  conversion experiments — quote it, do not hide it and do not omit it.
- **Equality.** Every arm's answer is compared against a cyvcf2 reference. The
  runner exits non-zero and writes `mismatches.json` when any arm disagrees, and
  the dataset refuses to present those rows as a result.
- **Warm/cold.** Engine setup happens once per arm; per-query executions are
  warm for QLever's server and cold for Comunica, which spawns a process per
  query. That is inherent to the engines and is the same condition `13_query_cost`
  reports under.

## Inputs

The scales mirror `13_query_cost` and read its variables:

| Scale | Input | Arms |
| --- | --- | --- |
| `small` | 13's small input (`test-10k.vcf` in the biomedsem profile) | all seven |
| `slice` | the 100,000-record `HG005_GRCh38` slice | VCF arms + QLever |
| `whole` (opt-in) | the whole `HG005_GRCh38` file | VCF arms + QLever |

Both default scales **reuse 13's RDF artifact rather than rebuilding it**. The
harness finds it under `results/13_query_cost/` by the input's stem, and uses
the first of 13's replicate conversions. The heavy engines stay off the slice,
as they do in 13. There HDT spent over ten minutes rebuilding its index,
Comunica's endpoint crashed at start-up (a `validation_runner` bind-probe bug),
and 13 has no numbers for them to compare against. The whole file matters most,
because an index seek is independent of file size and a scan is not. But it
needs a whole-file graph that 13 does not build.

## How to run it

```bash
# small and slice scales (after 13_query_cost, on the same host)
BM_REGIONAL_IMAGE=<image built from VCF-RDFizer PR #23> \
  bash benchmarks/14_regional_access.sh

# whole-file scale, qlever only among the engines
BM_REGIONAL_SCALES=whole bash benchmarks/14_regional_access.sh

python3 benchmarks/analysis/collect_metrics.py 14_regional_access
python3 benchmarks/analysis/datasets.py regional 14_regional_access
```

`BM_DRY_RUN=1` prints the command without running anything. If the harness
cannot find the `13_query_cost` artifact, name it with
`BM_REGIONAL_RDF_SLICE` / `BM_REGIONAL_RDF_WHOLE`.

**The v3.1.0 image cannot run this.** It has neither the runner nor `tabix`.
The harness checks the image first and records a stated skip rather than
failing. Until a release includes PR #23, point `BM_REGIONAL_IMAGE` at an image
built from it. Those cells are then marked `experiment-override` and carry that
image's digest.

## Outputs

| File | Contents |
| --- | --- |
| `regional.csv` | one row per arm, question, window, replicate |
| `regional.json` | medians per arm/question/window size, plus setup |
| `windows.json` | the regions, the seed, and the realised record counts |
| `mismatches.json` | any disagreement; non-empty invalidates that arm |
| `data_regional.csv` | per-question cost by access path, with the ratio against the fastest indexed VCF arm |
| `data_regional_setup.csv` | each side's one-time cost |

## What is verified, and what is not

Verified on vcf-bench-1, with an image built from PR #23 (htslib/tabix 1.22.1,
bcftools 1.22, cyvcf2 0.34.0), through the harness, against the live
`13_query_cost` results, at 2 windows per size and 1 replicate:

| Scale | Arms | Executions | Failed | Disagreed |
| --- | --- | --- | --- | --- |
| small (`test-10k`) | all seven | 200 | 0 | 0 |
| slice (`HG005_GRCh38_r100000`) | VCF arms + QLever | 140 | 0 | 0 |

`collect_metrics.py` and `datasets.py regional` both build from that output.
The runner's 75 unit tests pass, and inside the image none are skipped.

Getting there found four runner defects, all fixed in PR #23:

- an unsorted VCF could not be indexed;
- a plain-gzip slice was compressed twice;
- three of four engines rejected the reused `.nt.gz`;
- engine options were silently ignored.

The `%GT` caveat did not arise: every file tested carries GT.

Not yet done: the full sweep (20 windows per size, 3 replicates), and the
whole-file scale.

## What would change in the paper

- §3.6 gains a regional table or figure and one paragraph.
- The Discussion's retrieval paragraph states the regional result explicitly
  instead of generalizing from whole-file questions.
- The placeholder `\authorquery` in §4.2 is removed.

## Decision needed

Whether to run it before submission. Implementation is no longer the cost — the
slice scale is well under an hour. If it is still not run, the recommended
alternative is one sentence in the Discussion stating that coordinate-bounded
retrieval against an indexed VCF was not measured, and that the per-question
speed-ups are relative to an unindexed scan.
