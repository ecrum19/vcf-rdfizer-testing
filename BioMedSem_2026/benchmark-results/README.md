# BioMedSem benchmark results

Every non-regenerable file from the two benchmark VMs, plus `summary.json`,
which integrates all of it into one file.

## Layout

```
vcf-bench-1/ vcf-bench-2/     one directory per host, mirroring its disk
  benchmarks_outputs/           the live run -- VCF-RDFizer v3.1.0, what the paper reports
  benchmarks_outputs_calibration/        the identical cell both hosts ran
  benchmarks_outputs__campaign1__<ts>/   the pre-release campaign on development
                                         commits, set aside when the suite was
                                         re-run on v3.1.0 (and its calibration)
  benchmarks_outputs__superseded/        runs replaced by a later re-run
  benchmarks_outputs__stalled/           runs killed because they could not finish
  benchmarks_outputs__offsplit/          started on the host that did not own it
  benchmarks_outputs__partial/           interrupted before bench.json was written
  benchmarks_outputs__tool8b1b4a8/       an older tool's data, labels collide
_manifests/                   file counts, byte totals and sha256 per host
summary.json                  the integrated record (see below)
```

Only `benchmarks_outputs/` feeds the reported numbers.

**Current state (2026-09-24).** The whole suite is being re-run on the published
image `ecrum19/vcf-rdfizer:3.1.0` (`sha256:1904e96d…34aa`, commit `d3b34d5`).
vcf-bench-1's share (01, 04, 07–13) is finished and is its `benchmarks_outputs/`;
09 was re-run once more with network access so the tier-3 linker has a result,
and the first 09 run is under `__superseded/`. vcf-bench-2's share (03, 05, 06) is
still running and is not mirrored yet, so bench-2 currently has no live tree
here. Both hosts' first campaigns are kept under `__campaign1__<ts>/` with the
names the VMs gave them; they are byte-identical to what this directory held as
`benchmarks_outputs/` before the re-run. The other trees are kept
because they are the reason the live numbers look the way they do — a superseded
run explains why a re-run exists, and the two stalled trees are the only
evidence for the COTTAS non-termination claim.

## What is not here

The generated RDF: 137 GB of `.nt`, `.hdt` and `.cottas` under
`out/<dataset>/`. Every cell records the argv, `tool_commit` and image digest
that produced it, so any artifact can be rebuilt. Nothing was deleted from the
hosts to produce this directory.

## summary.json

Built by `scripts/build_run_summary.py`. One record per cell (327 of them),
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

**One tool commit in the live run; several in the pre-release one.** Every live
cell ran the published v3.1.0 image, and `summary.json` takes its digest from the
`repo@sha256:` that `bench.json` records. The pre-release campaign used
`025fb7d`, `be658a2`, `a3679e1`, `20d2cbb`; that split is
in `summary.json` under `experiments.prerelease`. Two experiments were re-run on a
later commit after their first run exposed a bug in the validation oracle; the
originals are under `__superseded/`.

**An image tag is not a digest.** Both hosts tagged an image
`vcf-rdfizer:local-025fb7d`, but each built it independently, so the tag names
different bits on the two machines — `b645120b…` on bench-1, `0082fe2c…` on
bench-2. `summary.json` resolves every cell's tag to the digest for *its* host.
Cite the digest.

**`06_equivalence` is present, and was hard-won.** It was killed twice without
completing: COTTAS, queried through pycottas' rdflib Store, did not terminate on
`q05_sample_genotype_counts` against the condensed encoding (41 h, then 10 h).
Querying it through `@elias.crum/query-sparql-cottas` instead — DuckDB over the
Parquet, behind the same endpoint the other engines use — finishes that cell in
99.8 minutes, and the whole experiment in 8.98 h with all four engines agreeing
on every artifact. The two killed runs are kept under `__stalled/` with their
container logs, because the contrast is the result.

**A non-zero exit is not always a failure.** `06` asserts that two
configurations are *refused* (`--hdt-strategy single` beside cottas, and beside
a gzip aggregate), and `09` runs awkward fixtures where a refusal is a valid
outcome. Both were previously counted as failures. `bench.json` now carries an
`assertion` field — `ok`, `refusal` or `recorded` — and `summary.json`
classifies on it: `REFUSED` where the refusal was demanded and delivered,
`RECORDED` where nothing was asserted and the exit code is an observation.
Cells recorded before that field existed are recovered from the scripts'
documented behaviour; the rule is in `build_run_summary.py`.
