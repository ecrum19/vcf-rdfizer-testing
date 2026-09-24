# Indexed regional access: an added arm for the retrieval comparison

Status: **implemented, not yet run.** The harness, the runner, the queries and
the analysis are in place and tested; no measurement has been taken. The
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
| Tests | `vcf-rdfizer/test/test_regional_runner_unit.py` (23 tests) |
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

The original cost estimate — 7,200 executions, "most of them sub-second",
2–4 h — does not survive contact with the scan arm. It costs ~11.5 s per
execution on the slice regardless of the window, because it reads the file
whichever region is asked for. At 5 questions × 4 sizes × 20 windows × 3
replicates that arm alone is 1,200 executions ≈ **3.8 h**, and on the whole file
it is not runnable at all.

It is also 1,200 measurements of the same number. So the scan arm is timed on 3
windows per size (`--scan-windows-per-size`, configurable) and reported as a
flat baseline rather than a curve. Correctness is unaffected: the equality
reference is a single whole-file pass that fills every window at once, and that
pass is deliberately **not** timed, because answering eighty windows in one pass
is not what a one-question user pays for.

Revised cost: roughly **1,900 timed executions per scale**, of which 60 are the
slow ones. Estimated well under an hour for the slice; the whole-file cells are
dominated by the engines' setup, not by the queries.

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

The 100,000-record `HG005_GRCh38` slice already used by `13_query_cost`, whose
RDF artifact is **reused rather than rebuilt** — the harness locates it under
`results/13_query_cost/` and refuses to guess when more than one candidate
exists. The whole `HG005_GRCh38` file is the second scale, and matters most: an
index seek is independent of file size, a scan is not.

## How to run it

```bash
# slice scale, every arm
bash benchmarks/14_regional_access.sh

# whole-file scale, qlever only among the engines
BM_REGIONAL_SCALES=whole bash benchmarks/14_regional_access.sh

python3 benchmarks/analysis/collect_metrics.py 14_regional_access
python3 benchmarks/analysis/datasets.py regional 14_regional_access
```

`BM_DRY_RUN=1` prints the command without running anything. If the harness
cannot find the `13_query_cost` artifact, name it with
`BM_REGIONAL_RDF_SLICE` / `BM_REGIONAL_RDF_WHOLE`.

**The image must be rebuilt before this runs.** `tabix` is a new package, and
without it the indexed arms fall back to `bcftools index`, which produces an
equivalent index but means the run is not testing the documented path.

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

Verified locally: the runner end to end on the scan arm (40 executions, zero
disagreements); window drawing, anchoring and seed reproducibility; the bcftools
folder against the cyvcf2 arm on every question and window; the SPARQL
normalizer; template rendering and its injection guard; the POS convention;
`datasets.py regional` including its disagreement path. 23 unit tests, and the
tool suite passes at 889 tests.

Not verified, because the binaries are not on this machine and no run has been
made: the `bcftools query -r` and `tabix` paths against a real index, and the
SPARQL arms against a real graph. The first run should be the slice at
`--windows-per-size 2 --replicates 1` as a smoke test before the full sweep.

One caveat to check on that first run: `_classify_bcftools_gt` maps `%GT` text
onto the same classes the allele-index oracle produces, but a record with no GT
field prints `.`, which is indistinguishable from a missing call. A file whose
records lack GT entirely would make the bcftools arm disagree with the cyvcf2
arms — the comparator will catch it, and the fix would be to read FORMAT
explicitly rather than infer from `%GT`.

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
