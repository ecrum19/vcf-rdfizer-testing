# ECCB 2026 Assets

## Compression Timing Transparency Note

Some older batch-mode benchmark runs in this repository under-reported
compression `wall_seconds`, especially for partitioned `hdt` runs. The
underlying issue was fixed upstream in VCF-RDFizer commit
[fb48e503341400c412f2fe1de73e1b53f894377f](https://github.com/ecrum19/VCF-RDFizer/commit/fb48e503341400c412f2fe1de73e1b53f894377f).

For transparency, the manuscript assets in this directory were rebuilt after a
local repair of the affected historical run artifacts. The repair:

- reconstructed per-dataset, per-method batch compression wall times from
  `wrapper_logs/*.log`
- used `wrapper_execution_times.csv` to anchor the end time of the final
  compression step in each run
- updated only the compression wall-time fields in:
  - `benchmark-results/*/compression_time/*/*/*.txt`
  - `benchmark-results/*/compression_metrics/*/*.json`
  - `benchmark-results/*/metrics.csv` when a matching row was present

After that repair, the aggregate outputs used by the paper were regenerated:

```bash
python3 scripts/repair_compression_wall_times.py \
  benchmark-results/20260305T102641 \
  benchmark-results/20260306T092411

python3 scripts/combine_benchmark_metrics.py benchmark-results/20260305T102641
python3 scripts/combine_benchmark_metrics.py benchmark-results/20260306T092411
python3 scripts/combine_benchmark_metrics.py \
  benchmark-results/20260305T102641 \
  benchmark-results/20260306T092411

python3 scripts/export_latex_tables.py \
  benchmark-results/combined_metrics_multi_run.json \
  --output-dir benchmark-results

MPLBACKEND=Agg python3 scripts/plot_combined_metrics.py \
  benchmark-results/combined_metrics_multi_run.json \
  --output benchmark-results/combined_metrics_figure.png
```

As a result, the aggregated `combined_metrics*.json` files, LaTeX tables, and
figure copies in `ECCB_2026/` reflect corrected compression wall times.
