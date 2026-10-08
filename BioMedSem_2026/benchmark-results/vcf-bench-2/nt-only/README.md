# N-Triples-only rerun (vcf-bench-2, 2026-10-08)

The break-even of main Figure 8a, measured directly. The base campaign's conversions of the
100,000-record HG005 slice also built HDT, which QLever does not need, so its setup overstated the
RDF route. This rerun converts the same input with the same release, VCF-RDFizer v3.1.0
(`d3b34d5`, image `ecrum19/vcf-rdfizer:3.1.0`, `sha256:1904e96d…34aa`), to gzip-framed N-Triples
only, on vcf-bench-2 (same CPU and image digest as vcf-bench-1, which ran the original cells).

| Cells | What | Result |
| --- | --- | --- |
| `convert__rep1..3` | `13_query_cost/large` without HDT, COTTAS, or validation (`--representations none`) | wall 96.6, 95.5, 95.1 s (`wall_seconds.txt`) |
| `validate__rep1..3` | `13_query_cost/large` without HDT or COTTAS: QLever validation, no SHACL | 13/13 equal in each; QLever index 25.1, 24.9, 24.9 s |

Break-even: (95.7 s conversion + 25.0 s index) / (12.28 s median cyvcf2 parse − 1.43 s mean
QLever query per question) ≈ 11 questions. With the base campaign's HDT-inclusive setup it was 44.

`run_nt_only.sh` is the driver (cells run one at a time, wall time taken around each command) and
`run.log` its log. The 76 MB N-Triples outputs stay on the VM under `~/vrdev-test/nt-only/`; the
v3.1.0 source was extracted there with `git archive d3b34d5`.
