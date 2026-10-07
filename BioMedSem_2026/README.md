# BioMedSem 2026 paper and evidence

- [`paper/`](paper/README.md): current manuscript, supplementary material,
  compiled PDFs, and the portable LaTeX source ZIP builder.
- [`paper-assets/`](paper-assets/): figures used by those documents and their
  TikZ/Python sources.
- [`benchmark-results/`](benchmark-results/README.md): recorded measurements,
  provenance and validation evidence. The large-graph retrieval extension, up to the
  complete HG005 VCF, is documented under [`vcf-bench-3`](benchmark-results/vcf-bench-3/README.md).

Build both documents from the repository root:

```bash
make -C BioMedSem_2026/paper
```

Create the shareable source ZIP with `make -C BioMedSem_2026/paper bundle`.
Recipients need a LaTeX installation; they do not need the benchmark archive.

To regenerate the four data plots from the recorded results:

```bash
python3 BioMedSem_2026/paper-assets/figures/make_figures.py
```

Plot generation needs Python and Matplotlib. The workflow, vocabulary and use-case
figures have standalone `.tex` sources beside their PDFs. The benchmark archive's
README documents how to rebuild its integrated summary.

The previous ECCB manuscript, old reporting pipeline and superseded figures are
preserved on the [`legacy` branch](https://github.com/ecrum19/vcf-rdfizer-testing/tree/legacy);
see [the archive inventory](../LEGACY.md).
