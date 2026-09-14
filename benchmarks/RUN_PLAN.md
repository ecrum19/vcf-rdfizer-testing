# BioMedSem run plan — two hosts in parallel

The `biomedsem` profile split across `vcf-bench-1` and `vcf-bench-2`, one
experiment at a time per host. Target ~1.5 days instead of multiple weeks.

## The one rule

**Split whole experiments, never cells within an experiment.** §1's paired
comparison, §2's ladder and §3's slopes all compare cells *to each other*; put
those on two machines and every comparison is confounded by hardware. Across
experiments it matters far less, and `bench.json` now records `host` per cell
so any residual cross-host comparison is at least visible.

These are separate physical hosts that merely share a flavour name, so each
host runs `12_modes_smoke` under identical settings as a calibration cell
before its share. Compare `phaseA_convert` wall time between them and report
it; if they disagree by more than a few percent, cross-experiment comparisons
need a caveat.

## Shared configuration

Both hosts, identical:

```
tool      025fb7d, then be658a2 from each host's handover (see below)
image     vcf-rdfizer:local-025fb7d  -- tag only; digests differ per host
profile   biomedsem
BM_RESULTS  ~/vcf-rdfizer-testing/benchmarks_outputs
BM_CORPUS_WHOLE=HG005_GRCh38.vcf.gz
```

### The tool commit changes mid-run, on purpose

bench-2's checkout moved from `025fb7d` to `be658a2` partway through `03`. Rather
than revert it, bench-1 is aligned onto `be658a2` at its `04 -> 07` handover, so
the two hosts converge instead of diverging.

The commits differ in `vcf_rdfizer.py` by one docstring hunk and no executable
line, and substantively only in `src/validation/validation_runner.py`
(`ad4c6c6`, the comunica warm-up retry). The alignment is chosen so that **every
experiment that runs validation — `06 09 11 12 13` — lands on `be658a2`**. `03`
is the only experiment straddling the boundary and it runs no validation.

### The image tag is not a digest

Both hosts tagged `vcf-rdfizer:local-025fb7d`, but built it independently about
five hours apart, so the image IDs differ (`b645120b…` on bench-1,
`0082fe2c…` on bench-2). `bench.json`'s `image_ref` is therefore not provenance.
Each host writes `00_environment/provenance.<host>.<commit>.json` with the real
digest, layer list and platform record; cite that.

### Nothing is deleted

Both handover watchers move rather than delete. Experiments belonging to the
other host go to `benchmarks_outputs__offsplit/`, interrupted cells to
`benchmarks_outputs__partial/`, and the pre-handover calibration is copied to
`benchmarks_outputs_calibration__*` before the restart can overwrite it. All of
it ships with the dataset; none of it enters `merged/`.

`BM_CORPUS_WHOLE` is deliberately **not** the 397 MB `NG1N86S6FC`: whole-file
conversion of that one is ~35 h, more than everything else in the profile put
together. `HG005_GRCh38.vcf.gz` (139 MB) is still a real single-sample WGS file
converted end to end, at ~12 h.

The tool is an unmerged branch. Every cell records its commit, so this is
honest rather than hidden — but the manuscript should say which commit, and
why it is not a release tag.

## The split

Invoke as `run_all.sh biomedsem <prefixes>` — the profile sets the
configuration, the prefixes select this host's share. A profile name alone runs
everything.

| host | experiments | why there | est. |
| --- | --- | --- | --- |
| **bench-2** | `00 02 01 03`, then `05 06 09 10 13` | has the truncated corpus and its own ladders | ~28 h |
| **bench-1** | `00 04 07 08 11 12` | has the full derived ladders | ~20 h |

`01` and `03` sit on bench-2 rather than bench-1 because an early launch ran
the whole suite there: the profile branches set `SELECTED` without shifting, so
the experiment list after the profile name was discarded (fixed in `ecc8eb2`).
Those cells are valid `biomedsem` cells on the manuscript tool, so they were
kept and the split rebalanced around them rather than repeated.

Dependencies, checked:

- `01 03 04 07 08 13` need derived ladder inputs → bench-1 has them; bench-2
  gets them from `02`, which is first in its list.
- `05` needs the truncated corpus (`*_first250000.vcf.gz`) → built on bench-2.
- `10` needs `HG005_GRCh38_r1000000.vcf.gz` → from `02` on bench-2.
- `06 09 11 12` need only fixtures → either host.

## Merging

Full step-by-step: [`AGGREGATION.md`](AGGREGATION.md).

Each host writes to its own `benchmarks_outputs`. To combine:

```bash
# from a machine that can reach both
rsync -a bench-2:~/vcf-rdfizer-testing/benchmarks_outputs/ ./merged/
rsync -a bench-1:~/vcf-rdfizer-testing/benchmarks_outputs/ ./merged/
BM_RESULTS=./merged python3 benchmarks/analysis/collect_metrics.py --all
```

No experiment appears on both hosts, so no cell collides — the watchers
enforce it, and `AGGREGATION.md` Step 3 asserts it. Keep **both**
`00_environment/manifest.json` files — they are per host, and the second copy
will overwrite the first. Rename them before merging:

```bash
mv merged/00_environment/manifest.json merged/00_environment/manifest.<host>.json
```

## What to check before launching

- `docker images | grep 025fb7d` on both hosts
- `git -C ~/VCF-RDFizer log --oneline -1` matches on both
- nothing else running: `pgrep -f 'vcf_rdfizer.py|run_all'`
- disk: the profile's peak is `05`'s whole-file cell; keep >60 GB free

## Known gaps

- `rules__custom` skips unless `BM_CUSTOM_RULES=/path/to/rules.ttl` is set. C4
  claims configurability and the custom-mapping path is otherwise untested.
- `02` ignores `BM_DRY_RUN` and builds derived inputs for real, so a dry run of
  the profile does real work.
- §1's earlier data (n=5 on `test-larger`, plus an HG005 pair) was produced on
  tool `8b1b4a8`, before the VCF 4.5 accessor work. It is kept as a separate
  archive. The claim is a *ratio* and a tool change moves both arms together,
  so it remains usable — but the profile re-runs §1 on the current tool so the
  reported dataset can be one commit throughout.
