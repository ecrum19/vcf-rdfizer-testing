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
./run_all.sh cheap        # skips the large-input experiments (01, 05, 10)
./run_all.sh 03 06        # selected only
```

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

## Seven things that will bite you

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
7. **Detach long runs** (`systemd-run --user --scope`, or `nohup`). Ctrl-C on the
   wrapper leaves its container running.

## Environment variables

`BM_RESULTS` results root · `BM_REPS` repetitions · `BM_SIZES` §1 inputs ·
`BM_SAMPLE_RUNGS` / `BM_RECORD_RUNGS` ladder rungs · `BM_VALIDATION_ENGINES` ·
`BM_SPARK_PARTITIONS` (default 8) · `BM_CEILINGS` §10 ceilings ·
`BM_IMAGE_VERSION` pin a published release · `BM_REBUILD=1` force a rebuild ·
`BM_DRY_RUN=1` print commands without running · `BM_ALLOW_NETWORK=1` +
`BM_CONTACT_EMAIL` tier-3 linker · `BM_CUSTOM_RULES` custom mapping
