# vcf-bench-3: large-graph retrieval

Not part of the base campaign (Supplementary Table S12). This host ran the
two-phase large-graph experiment: `15_scale_prepare.sh` built two graphs once,
and `16_scale_retrieval.sh` queried them. The manuscript reports the retrieval
from the v3.3.1 rerun on those graphs (Figure 3a, Table S17).

| Path | What |
| --- | --- |
| `benchmarks_outputs/15_scale_prepare/` | The two graph builds, with their wrapper records |
| `scale-store-manifests/` | The graphs' manifests |
| [`v331-rerun/`](v331-rerun/README.md) | The reported retrieval, with VCF-RDFizer v3.3.1: driver, logs, and per-cell records in `results/16_scale_retrieval/` |

The first retrieval runs, on pre-release runners, and the two cells that
failed before the memory fixes are on the
[`legacy` branch](https://github.com/ecrum19/vcf-rdfizer-testing/tree/legacy/benchmark-results/vcf-bench-3).

## The two graphs

| Scale | Triples | Source | Build | Artifacts |
| --- | ---: | --- | ---: | --- |
| `r1000000` | 170,935,101 | `HG005_GRCh38_r1000000.vcf.gz` | 3.98 h | nt.gz 721.5 MB, hdt 1.1 GB, cottas 372.6 MB |
| `whole` | 657,425,805 | `HG005_GRCh38.vcf.gz` | 14.25 h | nt.gz 2.7 GB, hdt 4.3 GB, cottas 1.4 GB |

Both were converted by the published `ecrum19/vcf-rdfizer:3.1.0`
(`sha256:1904e96d…`), the image that produced the base campaign, so retrieval
here measures the same pipeline. The complete VCF's triple count reproduces
vcf-bench-2's independent v3.1.0 run exactly. v3.3.1 writes the same graph
(vcf-bench-2's `bridge` job), so the v3.1.0 graphs stand for v3.3.1's.

**The graphs themselves are not archived.** They are 17 GB and stay on the host
in `scale_store/`. The manifests make them reproducible: each records the source
VCF and its digest, the triple count, every artifact's size and SHA-256, and the
tool commit and image digest that produced it.

## Reading the retrieval cells

Every cell is `TIMING_ONLY` by construction: it answers the thirteen core
queries rather than the whole validation suite, so it carries no validation
verdict. Each query is still compared with the cyvcf2 oracle, and
`answersAgree` in the cell's `summary.json` is the flag to check before quoting a
timing. The dataset the figures read is built with:

```bash
python3 benchmarks/analysis/scale_retrieval.py 16_scale_retrieval \
    --results benchmark-results/vcf-bench-3/v331-rerun/results
```
