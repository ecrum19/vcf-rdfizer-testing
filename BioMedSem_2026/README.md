# BioMedSem 2026: manuscript and evidence

| Directory | Contents |
| --- | --- |
| [`paper/`](paper/README.md) | The manuscript (`current_short.tex`, also built as `paper.pdf`), its supplementary material (`supplementary.tex`), the compiled PDFs, and the portable source-ZIP builder |
| [`paper-assets/`](paper-assets/) | Every figure the two documents include, with its source |
| [`benchmark-results/`](benchmark-results/README.md) | The run records behind every reported number: commands, logs, timings, comparisons, validation reports and provenance |

## Figures

The data figures are drawn from `benchmark-results/` by
[`paper-assets/figures/make_figures.py`](paper-assets/figures/make_figures.py),
which reads every value through
[`figure_data.py`](paper-assets/figures/figure_data.py) and
[`scripts/build_site_data.py`](../scripts/build_site_data.py), the results site's
builder. The paper and the site therefore cannot compute a value differently.
The diagrams are standalone TikZ sources beside their PDFs.

| Figure | File | Source |
| --- | --- | --- |
| 1 | `vcf-core-minimal.pdf` | `vcf-core-minimal.tex` |
| 2 | `fig-validation.pdf` | `make_figures.py` |
| 3 | `fig-usecase-matches.pdf` | `make_figures.py` |
| 4 | `fig-converters.pdf` | `make_figures.py` |
| 5 | `fig-regional.pdf` | `make_figures.py` |
| S1 | `vcf-core-classes.pdf` | `vcf-core-classes.tex` |
| S2 | `vcf2rdf-v3.pdf` | `vcf2rdf-v3.tex` |
| S3 | `fig-linking-framework.pdf` | `fig-linking-framework.tex` |
| S4 | `fig-usecase-costs.pdf` | `make_figures.py` |
| S5 | `fig-scaling.pdf` | `make_figures.py` |
| S6 | `fig-samples.pdf` | `make_figures.py` |
| S7 | `fig-representations.pdf` | `make_figures.py` |
| S8 | `fig-retrieval.pdf` | `make_figures.py` |
| S9 | `fig-retrieval-detail.pdf` | `make_figures.py` |

To redraw the data figures (Python 3 with Matplotlib), from the repository root:

```bash
python3 BioMedSem_2026/paper-assets/figures/make_figures.py
```

The figures carry no creation timestamp, so an unchanged figure is redrawn
byte for byte. To rebuild a diagram, run `pdflatex <name>.tex` in `paper-assets/`.

## Building the documents

```bash
make -C BioMedSem_2026/paper          # manuscript and supplement
make -C BioMedSem_2026/paper bundle   # also a self-contained LaTeX source ZIP
```

Recipients of the ZIP need only a LaTeX installation, not this archive; see
[`paper/README.md`](paper/README.md).

Earlier manuscripts (the ECCB submission and the full-length BioMedSem draft) and
superseded figures are listed in [`LEGACY.md`](../LEGACY.md), with how to
retrieve them.
