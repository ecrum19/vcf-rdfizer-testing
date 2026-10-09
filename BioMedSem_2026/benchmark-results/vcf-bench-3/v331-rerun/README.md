# VCF-RDFizer v3.3.1 rerun on vcf-bench-3 (2026-10-08)

The same release and harness as vcf-bench-1 (see [its README](../../vcf-bench-1/v331-rerun/README.md)),
driver role `bench3`: experiment 16, large-graph retrieval, run with the v3.3.1 image on the existing
v3.1.0 graphs in `scale_store/`. The two releases write the same graph: see vcf-bench-2's `bridge` job.

| Cells | Replicates | Wall each | Result |
|---|---|---|---|
| Complete HG005 VCF, QLever on N-Triples, HDT, COTTAS | 3 each | 52-66 min | All completed |
| 1,000,000 HG005 records, QLever on N-Triples | 3 | 13.5 min | All completed |
| 1,000,000 HG005 records, native HDT (24 GB heap) | 1 | 3.6 h | Did not complete (exit 1) |
| 1,000,000 HG005 records, native COTTAS (24 GB heap) | 1 | 29 min | Did not complete (exit 1) |

The native paths' failures match the base campaign's, which the paper reports. Per-cell records are in
`results/16_scale_retrieval/`. Its `retrieval.csv` and `retrieval-raw.json`, which the figures and the paper
read, were built from those cells with
`python3 benchmarks/analysis/scale_retrieval.py 16_scale_retrieval --results BioMedSem_2026/benchmark-results/vcf-bench-3/v331-rerun/results`.
On the complete HG005 VCF, QLever answered the thirteen questions in 646.4 s after an 880.8 s index build
(the earlier pre-release runners `245fe1f` and `5ed75c8`: 634.6 s and 868.0 s).

`attempt1-exit126/` is the first start, which exited after 60 s because `16_scale_retrieval.sh` is not
executable in the harness tree. The driver now runs it with `bash`; nothing else changed. No file was left
out of this archive ([`excluded-files.tsv`](excluded-files.tsv) is empty).
