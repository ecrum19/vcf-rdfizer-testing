# vcf-bench-3 — the optional scale-retrieval experiment

Not part of the base campaign (Supplementary Table S12). This host ran the
two-phase scale experiment (`15_scale_prepare.sh`, `16_scale_retrieval.sh`),
which is optional and in no profile. **The manuscript reports its rerun with
v3.3.1** on the same graphs, in [`v331-rerun/`](v331-rerun/README.md);
`benchmarks_outputs/` holds the first runs, on pre-release runners.

## What is here, and what is not

| path | what |
|---|---|
| `benchmarks_outputs/15_scale_prepare/` | the two graph builds, with their wrapper records |
| `benchmarks_outputs/16_scale_retrieval/` | every retrieval cell, including per-query raw results |
| `benchmarks_outputs/16_scale_retrieval__failed_before_memory_fixes/` | the two cells that failed before the memory fixes, kept as evidence |
| `scale-store-manifests/` | the store's manifests |

**The built graphs themselves are deliberately absent.** They are 17 GB and
live on the host in `scale_store/`. The manifests are what make them
reproducible: each records the source VCF and its digest, the triple count,
every artifact's size and sha256, and the tool commit and image digest that
produced it. Rebuilding from that record costs 4 h at 171M triples and 14 h at
657M.

## The two graphs

| scale | triples | source | build | artifacts |
|---|---:|---|---:|---|
| `r1000000` | 170,935,101 | `HG005_GRCh38_r1000000.vcf.gz` | 3.98 h | nt.gz 721.5 MB, hdt 1.1 GB, cottas 372.6 MB |
| `whole` | 657,425,805 | `HG005_GRCh38.vcf.gz` | 14.25 h | nt.gz 2.7 GB, hdt 4.3 GB, cottas 1.4 GB |

Both were converted by the **published** `ecrum19/vcf-rdfizer:3.1.0`
(`sha256:1904e96d…`), the same image that produced the base campaign,
so a retrieval number taken here measures the same pipeline. The whole-file
triple count reproduces `vcf-bench-2`'s independent v3.1.0 run exactly.

## Reading the retrieval cells

Every cell is `TIMING_ONLY` by construction: they answer the thirteen core
queries rather than the whole suite, so they carry **no validation verdict**.
Each selected query is still compared against the cyvcf2 oracle, and
`answersAgree` in `summary.json` is the flag to check before quoting any
timing.

Build the dataset with:

```bash
python3 benchmarks/analysis/scale_retrieval.py 16_scale_retrieval
```

## The two failed cells

`16_scale_retrieval__failed_before_memory_fixes/` holds the COTTAS and HDT
cells as they failed before the fixes, and they are kept because they are the
evidence for two defects:

* the COTTAS cell was SIGKILLed at 32.2 GB RSS on a 31 GB machine because the
  shape layer's size gate measured the packaged artifact rather than the graph,
  so the best-compressing format was the one most likely to exhaust memory;
* the HDT cell's endpoint aborted with a JavaScript heap-out-of-memory while
  ~25 GB was free, because Node does not size its heap from the machine.

Both are fixed upstream (VCF-RDFizer #29). The retried cells sit in
`16_scale_retrieval/` and fail differently; see Supplementary Section S9.3
and Table S17.
