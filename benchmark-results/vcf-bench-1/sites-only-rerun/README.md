# Experiment 09's sites-only cell, rerun with a conformant fixture (2026-10-10)

The reported `awkward_sites_only` cell,
[`../benchmarks_outputs/09_awkward_inputs/awkward_sites_only/`](../benchmarks_outputs/09_awkward_inputs/awkward_sites_only/),
comes from this rerun rather than from the base campaign's run of 2026-09-24.
[`rerun_sites_only.sh`](rerun_sites_only.sh) is the driver and [`run.log`](run.log) its log.

## Why

The fixture is meant to be an ordinary sites-only VCF: "No FORMAT or sample columns at all; Q5/Q6 are not
applicable" ([`FIXTURES.json`](../../../benchmarks/fixtures/FIXTURES.json)). The campaign's copy was not one.
`lib/make_fixtures.py` always ended the `#CHROM` line with `FORMAT`, and this was the only fixture built
without samples, so the file declared a `FORMAT` column with no samples after it. The specification has
no such column, and bcftools, which supplies the paired validation's reference values, rejected the
header. The tool converted the file (245 triples), but neither paired validation ran a query.

The generator now writes `FORMAT` only when samples follow it, and the sites-only fixture declares no
FORMAT keys, like a real sites-only file. Regenerating changed no other fixture.

## How

Same host, harness checkout (`3b36985d`), image (`ecrum19/vcf-rdfizer@sha256:1904e96d…`, v3.1.0) and
arguments as the campaign, through the harness's own `bm_run`. The host's tool checkout had moved past the
release, so the cell ran the release commit `d3b34d5` from a worktree; its wrapper and data files are
identical to the checkout's. The experiment's `tidy.csv` was rebuilt with the host's collector, and only
the sites-only row changed.

## Result

- Exit 0: 183 triples and an HDT artifact.
- Both paired validations (N-Triples and HDT) PASS: 11 query comparisons equal, and Q5 and Q6 verified not
  applicable, as the fixture's expectation says. Both still ran and agreed: neither the source nor the graph
  has a genotype.
- SHACL: no violations; four advisory warnings (VCF 4.5 recommends Source and Version on INFO declarations).

What the base campaign's totals gain: 78 of 78 validations complete, rather than 76; 1,006 equal query
comparisons, rather than 984; and 8 verified not applicable, rather than 4 (four on the zero-record fixture,
four here).

The first run is on the `legacy` branch, at
`benchmark-results/vcf-bench-1/benchmarks_outputs__superseded/09_awkward_inputs__malformed_sites_only__20260924T161103/`.

## Reproduce

Running `09_awkward_inputs.sh` into a fresh `BM_RESULTS` with the fixtures on `main` reproduces this cell
with the rest of the experiment; the driver here only reran the one cell in place.

That was checked on 2026-10-10. On vcf-bench-1, with the same image and release commit, the harness of this
change ran `09` into an empty results root, generating the fixtures itself. For all eleven fixtures, the exit
code, triple count, validation status and per-query outcome matched the records here. `make_fixtures.py`
regenerates all eighteen fixtures byte-identically on Python 3.12 and 3.14.
