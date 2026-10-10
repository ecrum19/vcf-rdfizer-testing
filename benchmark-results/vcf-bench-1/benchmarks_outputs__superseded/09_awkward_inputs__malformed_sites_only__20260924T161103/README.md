# Experiment 09's first sites-only cell (2026-09-24, v3.1.0)

The base campaign's `awkward_sites_only` cell, retired because its fixture was not the file the experiment
meant to test. Until 2026-10-10 it was `main`'s
`benchmark-results/vcf-bench-1/benchmarks_outputs/09_awkward_inputs/awkward_sites_only/`, where its rerun
now is; `awkward_sites_only/` here is byte-identical to that cell at `66f53577`, and `tidy.before_rerun.*`
to the experiment's tidy table then.

**What the fixture should have been.** Its expectation in `benchmarks/fixtures/FIXTURES.json`: "Convert. No
FORMAT or sample columns at all; Q5/Q6 are not applicable."

**What it was.** `benchmarks/lib/make_fixtures.py` always ended the `#CHROM` line with `FORMAT` and added
samples after it, and this was the only fixture built without samples. The file therefore declared a
`FORMAT` column with no samples, which the specification does not allow, and kept two `##FORMAT` lines
(fixture SHA-256 `3b10e5a1…`).

**What happened.**
- VCF-RDFizer converted it without a warning: 245 triples and an HDT artifact.
- Both paired validations (N-Triples and HDT) stopped with `EXECUTION_FAILED` before any query: bcftools,
  which supplies the reference values, rejected the header (`[E::bcf_hdr_parse_sample_line] Could not
  parse the "#CHROM.." line`; `awkward_sites_only/out/run_metrics/*/logs/wrapper.log`).

No pass or semantic failure follows from this cell. It accounts for the base campaign's 76 of 78 completed
validations, and for the supplement's "malformed sites-only fixture", as first reported.

**The correction, on `main`.** The generator writes `FORMAT` only when samples follow it, and the
sites-only fixture declares no FORMAT keys (SHA-256 `6e872d68…`); no other fixture changed. The cell was
rerun on 2026-10-10 on vcf-bench-1 with the same image, release commit and arguments: 183 triples, both
paired validations PASS (11 equal query comparisons each, Q5 and Q6 verified not applicable), no SHACL
violations. The campaign's totals became 78 of 78 validations and 1,006 equal comparisons. `main`'s
`benchmark-results/vcf-bench-1/sites-only-rerun/` holds the driver and its log.
