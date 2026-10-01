# COTTAS index forms

Branch: `codex/cottas-multiple-indexes` · Commit: `0dc836a`

`--cottas-indexes all` selects all six `spo` permutations; `all-quads` selects
all 24 `spog` permutations. Comma-separated selections such as `spog,gspo,pgos`
are supported. Default remains SPO. The first order keeps `name.cottas`;
additional copies use `name.<order>.cottas`.

Dataset compression accepts `.nq`/`.nq.gz` and requires graph-aware orders.
VCF/triple input can also use graph-aware indexes, with the default graph.
Named-graph exports require `--decompress-out <out>/dataset.nq`.

Each chunk is parsed/deduplicated once; additional orders sort its Parquet data.
Sequential bounded merges preserve graph identity without multiplying merge
memory. Streaming N-Quads parsing preserves shared blank nodes and literal
lexical forms. Reindexing, validation, gzip/Brotli packaging and JSON metrics
support every order. Default graphs and legacy `DEFAULT` values are handled.

Validation:

- **258 focused tests passed; 311/312 changed executable lines covered (99.7%).**
  COTTAS adapter and selection-module branches: **100%**.
- **fed-expt / realfed:** all 24 dataset orders across four chunks, 384 native
  quad-query patterns, packaging/decompression and all 24 reindexes passed.
  All six triple orders and VCF→`gspo,spog` passed on 8,519 statements.
- Wheel built. Broad regression: **902 tests; 900 passed, one skipped**, one
  pre-existing vocabulary mismatch (bundled 2.1.2 versus sibling checkout 2.1.3).

VM evidence: `/tmp/vcf-cottas-indexes.BnWxCX/verify-*.json`.
