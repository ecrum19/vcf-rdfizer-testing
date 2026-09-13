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
tool      fix/vcf45-structured-accessors @ 025fb7d
image     vcf-rdfizer:local-025fb7d
profile   biomedsem
BM_RESULTS  ~/vcf-rdfizer-testing/benchmarks_outputs
BM_CORPUS_WHOLE=HG005_GRCh38.vcf.gz
```

`BM_CORPUS_WHOLE` is deliberately **not** the 397 MB `NG1N86S6FC`: whole-file
conversion of that one is ~35 h, more than everything else in the profile put
together. `HG005_GRCh38.vcf.gz` (139 MB) is still a real single-sample WGS file
converted end to end, at ~12 h.

The tool is an unmerged branch. Every cell records its commit, so this is
honest rather than hidden — but the manuscript should say which commit, and
why it is not a release tag.

## The split

| host | experiments | why there | est. |
| --- | --- | --- | --- |
| **bench-1** | `00 01 03 04 07 08 11 12` | has the full derived ladders already | ~33 h |
| **bench-2** | `00 02 05 06 09 10 13` | `05`'s truncated corpus is already built there; `02` builds its ladders | ~28 h |

`02` runs on bench-2 only — bench-1's ladders already exist and rebuilding them
would waste an hour and change nothing.

Dependencies, checked:

- `01 03 04 07 08 13` need derived ladder inputs → bench-1 has them; bench-2
  gets them from `02`, which is first in its list.
- `05` needs the truncated corpus (`*_first250000.vcf.gz`) → built on bench-2.
- `10` needs `HG005_GRCh38_r1000000.vcf.gz` → from `02` on bench-2.
- `06 09 11 12` need only fixtures → either host.

## Merging

Each host writes to its own `benchmarks_outputs`. To combine:

```bash
# from a machine that can reach both
rsync -a bench-2:~/vcf-rdfizer-testing/benchmarks_outputs/ ./merged/
rsync -a bench-1:~/vcf-rdfizer-testing/benchmarks_outputs/ ./merged/
BM_RESULTS=./merged python3 benchmarks/analysis/collect_metrics.py --all
```

No experiment appears on both hosts, so no cell collides. Keep **both**
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
