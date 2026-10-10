# Index storage on vcf-bench-3 (2026-10-10)

What each route keeps on disk to answer queries, for the two inputs of main Figure 6b: the VCF compressed
with bgzip plus its tabix index, against the QLever index built from the tool's N-Triples. Experiment
[`19_index_storage.sh`](../../../benchmarks/19_index_storage.sh) (design §3.11) ran both cells in
the v3.3.1 image (`sha256:3ad71b1a…2993`), whose QLever is the build (`bfd5741`) the reported runs used.
[`run_index_storage.sh`](run_index_storage.sh) is the driver, at harness `a32b5304`, and
[`run.log`](run.log) its log. Each cell's numbers are in `out/index_storage.json`.

| Input | VCF route: bgzipped VCF + `.tbi` | RDF route: QLever index | Ratio |
| --- | --- | --- | --- |
| 100,000 HG005 records (`slice/`) | 3,498,705 + 46,386 = 3,545,091 bytes (3.5 MB) | 214,472,461 bytes (214.5 MB) | 60.5× |
| Complete HG005 VCF (`whole/`) | 139,334,496 + 1,607,258 = 140,941,754 bytes (140.9 MB) | 8,107,236,139 bytes (8.1 GB) | 57.5× |

- **Inputs.** Both VCFs match the SHA-256 in [`vcf-input-sizes.json`](../../vcf-input-sizes.json). The
  slice's N-Triples are `13_query_cost/large__r1`'s, copied from vcf-bench-1 and checked by SHA-256; the
  complete VCF's are the scale store's, matching
  [`whole.manifest.json`](../scale-store-manifests/whole.manifest.json). QLever parsed 17,098,746 and
  657,425,805 triples, as those graphs record.
- **The VCF route.** The complete VCF is already BGZF and was indexed as it is (tabix 3.2 s). The slice is
  plain gzip, so it was recompressed with bgzip first. That is why its VCF route stores 3.5 MB, not the
  3.07 MB of the gzipped input; regional retrieval did the same.
- **The RDF route.** QLever was built with the validator's arguments (`-F nt -m 4G`), with the N-Triples
  streamed into it. The slice took 23 s and peaked at 5.5 GB of memory; the complete VCF took 14.4 min and
  9.2 GB.
- **Reproducibility.** The slice was also built on vcf-bench-1, once from the decompressed N-Triples
  file and once streamed. All three builds wrote the same 24 files, and every data file had the same size
  each time. Only the total differs, by a few dozen bytes, because it includes QLever's own build log
  (`index.index.resource-usage-log.tsv`), which records timings.

Both indexes were deleted after measuring. To reproduce, on a host with the two graphs:

```bash
BM_IMAGE_VERSION=3.3.1 ./benchmarks/19_index_storage.sh
```
