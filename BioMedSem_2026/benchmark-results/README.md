# BioMedSem benchmark results

Every non-regenerable file from the two benchmark VMs, plus `summary.json`,
which integrates all of it into one file.

## Layout

```
vcf-bench-1/ vcf-bench-2/     one directory per host, mirroring its disk
  benchmarks_outputs/           the live run -- what the paper reports
  benchmarks_outputs_calibration/        the identical cell both hosts ran
  benchmarks_outputs__superseded/        runs replaced by a later re-run
  benchmarks_outputs__stalled/           runs killed because they could not finish
  benchmarks_outputs__offsplit/          started on the host that did not own it
  benchmarks_outputs__partial/           interrupted before bench.json was written
  benchmarks_outputs__tool8b1b4a8/       an older tool's data, labels collide
_manifests/                   file counts, byte totals and sha256 per host
summary.json                  the integrated record (see below)
```

Only `benchmarks_outputs/` feeds the reported numbers. The other trees are kept
because they are the reason the live numbers look the way they do — a superseded
run explains why a re-run exists, and the two stalled trees are the only
evidence for the COTTAS non-termination claim.

## What is not here

The generated RDF: 137 GB of `.nt`, `.hdt` and `.cottas` under
`out/<dataset>/`. Every cell records the argv, `tool_commit` and image digest
that produced it, so any artifact can be rebuilt. Nothing was deleted from the
hosts to produce this directory.

## summary.json

Built by `scripts/build_run_summary.py`. One record per cell (192 of them),
each tagged with its host, branch, experiment, tool commit and resolved image
digest, plus per-experiment roll-ups, host provenance, and an integrity block.

Regenerate with:

```bash
python3 scripts/build_run_summary.py BioMedSem_2026/benchmark-results \
    --output BioMedSem_2026/benchmark-results/summary.json
```

It exits non-zero if any experiment spans two hosts, which would confound that
experiment's internal comparison.

## Three things to know before citing these numbers

**Four tool commits.** `025fb7d`, `be658a2`, `a3679e1`, `20d2cbb`. The split is
in `summary.json` under `experiments.live`. Two experiments were re-run on a
later commit after their first run exposed a bug in the validation oracle; the
originals are under `__superseded/`.

**An image tag is not a digest.** Both hosts tagged an image
`vcf-rdfizer:local-025fb7d`, but each built it independently, so the tag names
different bits on the two machines — `b645120b…` on bench-1, `0082fe2c…` on
bench-2. `summary.json` resolves every cell's tag to the digest for *its* host.
Cite the digest.

**`06_equivalence` is absent.** It was killed twice without completing: COTTAS
does not terminate on `q05_sample_genotype_counts` against the condensed
encoding (41 h, then 10 h). The evidence is under `__stalled/`, including the
container logs. It is a limitation to report, not a gap to hide.
