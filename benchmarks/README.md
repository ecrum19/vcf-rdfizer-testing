# Benchmark suite

Runnable version of [`benchmarking_suggestions.md`](../benchmarking_suggestions.md).
One script per plan section; output is CSV + JSON only.

## Setup

```bash
bash ../scripts/download_test_data.sh        # corpus VCFs (~2.3 GB)
export VCF_RDFIZER=/path/to/vcf_rdfizer.py   # only if not a sibling checkout
python3 -m pip install numpy rdflib          # rdflib: linking + mutation score
```

Needs Docker. `bcftools` is **not** required — derived inputs are built with awk.

**Docker image.** By default the suite builds the image once from the tool
checkout and tags it `vcf-rdfizer:local-<commit>`, so the tag records which
source produced a result. Cells then run with `--image <that ref> --no-build`,
so nothing rebuilds mid-sweep. To reproduce against a published release
instead:

```bash
export BM_IMAGE_VERSION=1.1.0     # pulls and pins ecrum19/vcf-rdfizer:1.1.0
```

`BM_REBUILD=1` forces a rebuild. A dirty checkout gets a `-dirty` tag and is
rebuilt every session, with a warning — commit before a publishable run.

## Run

```bash
./run_all.sh              # everything, in order
./run_all.sh cheap        # skips the large-input experiments (01, 04, 05, 10)
./run_all.sh smoke        # fast end-to-end pass — see below
./run_all.sh 03 06        # selected only
```

**`biomedsem` is the manuscript configuration.** Every claim in the plan is
still supported; what changes is *where* the evidence is allowed to be
expensive. Unlike `smoke`, these are measurements and are meant to be reported.

The full plan runs for multiple weeks, and the measured reason is that a
handful of cells dominate while most of the evidence sits in cheap ones:

| measured | |
| --- | --- |
| `01` at default sizes/reps | 57.8 h for 11 of its 30 cells |
| one HG005 cell | 12.3 h |
| `03`'s three real-file anchors | 17.7 h — vs 3.6 min for the same contrast on a fixture |
| `06` on a 10k fixture, one engine | 92 min — validation is overhead-bound, not data-bound |

Those are two different cost regimes and they need different cuts:

- **C1** — replicates bound the CI, and run-to-run variance is a property of the
  machine, not the input (sd was ~1 % of the mean). So the corridor is bought on
  the cheapest size and larger sizes run once each as a size check
  (`BM_REPS_AT_SCALE`). The 397 MB third size is dropped: §3's ladder covers the
  size trend far more cheaply than a third paired arm. **The peak-disk half needs
  no replicates at all** — it was identical across every replicate in each arm.
- **C2** — the ladder is the evidence; §2.4 says so itself ("anchors, not the
  evidence"). The anchors move to `test-larger-multisample.vcf.gz`, which makes
  the same 2,504-vs-1 sample contrast.
- **C3** — unchanged. The ladders were always the cheap part.
- **C4 breadth** — becomes a *feature*-coverage claim. `BM_CORPUS_MAX_RECORDS`
  truncates each corpus file to its first 250k records, keeping the header and so
  the declared INFO/FORMAT/FILTER fields; `BM_CORPUS_WHOLE` exempts one file so a
  real VCF is still converted end to end. Truncated cells carry a `__firstN`
  label. This is the one change that genuinely weakens a claim — from "converted
  ten whole cohorts" to "handled the features of ten cohorts, one of them whole"
  — and the manuscript should say so rather than gloss it.
- **C4 feasibility** — the claim is that it *completes* under a memory cap, which
  a 1M-record ladder input demonstrates as well as a 397 MB file does.
- **C4/C5 validation** — cross-engine agreement is bought once in §4.1, where it
  *is* the claim (`BM_EQUIV_ENGINES`), and one engine runs everywhere else.

Every value is a default, so an explicit env var still wins. `00` and `02` must
run first: the profile draws on the derived ladders.

**`smoke` is for "does this still work", never for numbers.** It selects the
same scripts as `cheap` and shrinks everything they read: one replicate, a
two-rung samples ladder, 2,000-record derived bases, fixtures in place of every
corpus file, and a single SPARQL engine. `cheap` on its own is *not* fast —
several of its experiments default to a 1.16M-record or 139 MB input.

Two classes of cell had to be parameterised for this to work, because they
ignore the ladder rungs by design and run whole real files: §2.4's real-cohort
anchors (`BM_ANCHOR_PAIRS`) and §4.2's INFO inputs (`BM_INFO_INPUTS`). Measured
on one smoke pass before they were overridable, §2.4 alone took **17.7 h of
`03`'s 17.8 h**, while the eight cells the rungs *did* shrink took **2.7
minutes** — so shrinking rungs without shrinking those is close to no saving at
all. `BM_VALIDATION_ENGINES` and `BM_QUERY_ENGINES` drop to one engine for the
same reason: validation setup is per engine per artifact, so `all` multiplies a
cheap graph by twelve engine startups.

The smoke anchors use `test-larger-multisample.vcf.gz` (2,504 samples) against
`test-10k.vcf` (1 sample), which keeps the cohort-vs-single contrast the
section is about and still exercises the cohort guard, since the multisample
expanded cell is skipped by it.

Every value the profile sets is a default, so an explicit env var still wins.
Results from a smoke run are not measurements; do not report them.

**Cohort-scale inputs are guarded out of the `expanded` cells.** The expanded
representation emits per sample per record, so cost is records x samples. A
cohort file is small on disk and enormous once expanded:
`1000G_phase3_chr20.vcf.gz` is 327 MB gzipped, but at 1,812,841 records x 2,504
samples it reached **23 GB after 20,000 variants (1.1%)** — about **2.1 TB** for
the whole file, against a 189 GB volume. Unguarded it fills the disk and dies,
and because every experiment loop is serial, everything after it waits behind a
cell that cannot finish.

`bm_skip_if_cohort_scale` (in `lib/common.sh`) skips such a cell when the input
has more than `BM_CORPUS_MAX_SAMPLES` (default 1000) sample columns. It is used
in two places, which are the two that run full cohort files:

- `05_corpus_breadth.sh` — §3.2 runs everything at expanded
- `03_sample_representation.sh` — the §2.4 real-cohort anchors

**Only `expanded` is affected.** `condensed` is ~S + (V x F) and stays
tractable, so the cohort file still gets its condensed cell — which is the
comparison §2 is actually making. The skip is recorded as a real result with
its reason, so the table shows the case was considered rather than quietly
absent; "expanded does not scale to a 2,504-sample cohort" is a finding, not a
gap. Raise the variable if you have the disk.

`00_environment.sh` must run first and once per session. Run **one experiment at
a time** — two concurrent runs invalidate every timing and memory number.

| Script | Plan | What it answers |
|---|---|---|
| `00_environment.sh` | §5.4 | Environment manifest. Numbers are meaningless without it. |
| `02_derive_ladders.sh` | §2.1, §3.1 | Builds the samples and records ladders (awk, no bcftools). |
| `01_storage_mode.sh` | §1 | plain vs space-optimized, paired, 3 sizes × 5 reps. |
| `03_sample_representation.sh` | §2 | condensed vs expanded across a 1→2504 sample ladder. |
| `04_scaling_records.sh` | §3.1 | Records ladder. The only place records-slopes are fitted. |
| `05_corpus_breadth.sh` | §3.2 | Ten real files, one config. Deliberately not a curve. |
| `06_equivalence.sh` | §4.1 | Q1–Q13 vs oracle across every encoding, + the mechanism check. |
| `07_representation_axes.sh` | §4.2 | info/header representation cost; VCF 4.1–4.5 conformance. |
| `08_robustness.sh` | §4.3 | Mutation score, round-trip, determinism, index idempotence. |
| `09_awkward_inputs.sh` | §4.4 | 11 difficult VCFs + extensibility smoke runs. |
| `10_feasibility.sh` | §4.4 | Memory ceiling × configuration → completed / OOM. |
| `11_covering_set.sh` | §5.1 | Six runs covering every option value and pair. |
| `12_modes_smoke.sh` | §5.2–5.3 | Phase A/B separation; every mode exercised once. |
| `13_query_cost.sh` | §4.5 | SPARQL retrieval vs the cyvcf2 parser, on identical work. |

### Investigations outside the suite

Not in `run_all.sh`, and not part of any profile. Run directly when wanted.

| Script | What it investigates |
|---|---|
| `14_regional_access.sh` | Indexed regional access: SPARQL against bgzip+tabix seeks, on five region-restricted questions. It reuses `13_query_cost`'s graphs, so run it after 13 on the same host. It needs an image with VCF-RDFizer's regional runner and tabix (`BM_REGIONAL_IMAGE`); v3.1.0 has neither and records a skip. |

## Get the data out

```bash
python3 analysis/collect_metrics.py --all          # -> results/<exp>/tidy.{csv,json}
```

Then whichever apply:

```bash
python3 analysis/equivalence.py 01_storage_mode --margin 0.10
python3 analysis/fit_scaling.py 03_sample_representation \
        --x samples --y triples --group mode --cell-filter __structure
python3 analysis/describe_inputs.py --corpus       # structural descriptors
python3 analysis/datasets.py corpus 05_corpus_breadth
python3 analysis/datasets.py equivalence 06_equivalence
python3 analysis/datasets.py awkward 09_awkward_inputs
python3 analysis/datasets.py feasibility 10_feasibility
python3 analysis/datasets.py coverage 11_covering_set
python3 analysis/datasets.py querycost 13_query_cost   # aggregate + per-query
python3 analysis/datasets.py regional 14_regional_access
```

`tidy.csv` is the schema everything else joins on. Values stay numeric; missing
is empty, not `—`.

## Layout

```
results/<experiment>/<cell>/    bench.json, command.txt, stdout.log, stderr.log,
                               workspace_bytes.tsv, out/  (the tool's own tree)
results/<experiment>/tidy.csv   one row per cell
results/descriptors.json        per-input structural descriptors
```

Each cell gets a fresh `--out`; re-running a cell fails rather than overwriting.
Move or delete the cell, or set `BM_RESULTS` to a new root.

## Eight things that will bite you

1. **Peak workspace, not final bytes.** Both storage modes emit the same
   triples, so a final-size table shows ~0% and looks like it refutes §1.
   `peak_host_out_tree_bytes` is the number. The partitioned stage's Docker
   volume is a *separate* number (`peak_volume_workspace_bytes`) — never add them.
2. **Never compare `.nt.gz` checksums.** space-optimized writes a concatenated
   gzip stream, plain gzips one merged `.nt`. Same triples, different bytes. Use
   `analysis/compare_graphs.py`, which digests the sorted triple set.
3. **`--hdt-strategy single` only works with `plain` + `hdt` (no cottas).**
   Anything else exits 2. It is a verification path, not a faster one.
4. **Derived ladder files are not valid VCFs.** Sample columns are cut without
   recomputing INFO, so AC/AN disagree with the retained genotypes. That is
   intentional (INFO is a held-fixed control) — say so in the manuscript.
5. **`--validation-engine all` only on small inputs.** At scale use `qlever` or
   `--validate-artifacts hdt`.
6. **In `benchmark.csv`, compare against `oracle_query_seconds`, not
   `oracle_wall_seconds`.** The first is the parser's cost for *that* query and
   is row-wise comparable; the second is its total for *all* queries, repeated
   on each row for join convenience, so a row-wise ratio against it is wrong by
   ~27×. `datasets.py querycost` writes both an aggregate and a per-query file
   and uses the right column in each.
7. **A window means POS, not overlap.** A tabix seek returns every record whose
   span overlaps the region, so an indel starting before the window comes back
   from htslib but not from a SPARQL `?pos` filter. Every VCF arm in
   `14_regional_access` keeps the seek and then drops out-of-window POS, which
   is what makes the arms comparable; if you add an arm, it must do the same.
8. **Detach long runs** (`systemd-run --user --scope`, or `nohup`). Ctrl-C on the
   wrapper leaves its container running.

## Environment variables

`BM_RESULTS` results root · `BM_REPS` repetitions · `BM_SIZES` §1 inputs ·
`BM_SAMPLE_RUNGS` / `BM_RECORD_RUNGS` ladder rungs · `BM_VALIDATION_ENGINES` ·
`BM_SPARK_PARTITIONS` (default 8) · `BM_CEILINGS` §10 ceilings ·
`BM_IMAGE_VERSION` pin a published release · `BM_REBUILD=1` force a rebuild ·
`BM_REGIONAL_SCALES` small/slice/whole (default `small slice`, mirroring 13) · `BM_REGIONAL_ARMS` (or `_SMALL`/`_SLICE`/`_WHOLE`) · `BM_REGIONAL_THIN_ARMS` arms timed on `BM_SCAN_WINDOWS_PER_SIZE` windows only (default: the scan arm) · `BM_WINDOW_SEED` ·
`BM_REGIONAL_RDF_SMALL` / `_SLICE` / `_WHOLE` reuse a specific graph · `BM_REGIONAL_IMAGE` run 14 on its own image (v3.1.0 lacks the regional runner) ·
`BM_DRY_RUN=1` print commands without running · `BM_ALLOW_NETWORK=1` +
`BM_CONTACT_EMAIL` tier-3 linker · `BM_CUSTOM_RULES` custom mapping
