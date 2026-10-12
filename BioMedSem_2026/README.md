# BioMedSem 2026: manuscript and figures

| Directory | Contents |
| --- | --- |
| [`paper/`](paper/README.md) | The manuscript (`submitted.tex`, also built as `paper.pdf`), its supplementary material (`supplementary.tex`), the compiled PDFs, and the portable source-ZIP builder |
| [`paper-assets/`](paper-assets/) | Every figure the two documents include, with its source |

The run records behind every number are in [`benchmark-results/`](../benchmark-results/README.md)
at the repository root. This directory and `tool-docs/` are marked `export-ignore` in
[`.gitattributes`](../.gitattributes): they are in the GitHub repository, but not in the
Zenodo archive or any other archive git makes.

## Figures

The data figures are drawn from `benchmark-results/` by
[`paper-assets/figures/make_figures.py`](paper-assets/figures/make_figures.py),
which reads every value through
[`scripts/figure_data.py`](../scripts/figure_data.py) and
[`scripts/build_site_data.py`](../scripts/build_site_data.py), the results site's
builder. The paper and the site therefore cannot compute a value differently.
The diagrams are standalone TikZ sources beside their PDFs.
Figure 4, RQ1, Supplementary Section S4, and the results site share five labels:
A, Core benchmark validation; B, Artifact decoding; C, Consumer WGS validation;
D, Large-graph query agreement; E, Fault-injection sensitivity.
The titles are defined in `FIDELITY_GROUPS` in `build_site_data.py`.
Group D compares the archived normalized parser and SPARQL answers in every
replicate; execution status alone is insufficient. Group B checks decoded triple
counts, not the identity of every triple.
Figure 5 focuses on the Scenario 2 shared-frequency join and Scenario 4 policy views;
Figure S3 expands the comparison to all four scenarios and every requester. Both
read the v3.3.1 reruns through the same reader as the results site. Input records
and triples come from final conversion-stage reports; link counts, exact match-set
comparisons, released-record counts, and timing replicates come from the corresponding
link, comparison, policy, and query records. Figure 5 shows selected stage costs;
Figure S4 and Table S11 report the full breakdown. No repeated-INFO counterfactual
is used.

| Figure | File | Source |
| --- | --- | --- |
| 1 | `vcf-core-minimal.pdf` | `vcf-core-minimal.tex` |
| 2 | `vcf2rdf-v3.pdf` | `vcf2rdf-v3.tex` |
| 3 | `fig-query-oracle.pdf` | `fig-query-oracle.tex` |
| 4 | `fig-validation.pdf` | `make_figures.py` |
| 5 | `fig-usecase-matches.pdf` | `make_figures.py` |
| 6 | `fig-converters.pdf` | `make_figures.py` |
| 7 | `fig-regional.pdf` | `make_figures.py` |
| S1 | `vcf-core-classes.pdf` | `vcf-core-classes.tex` |
| S2 | `fig-linking-framework.pdf` | `fig-linking-framework.tex` |
| S3 | `fig-usecase-overview.pdf` | `make_figures.py` |
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

For a publisher that wants raster files, `make -C BioMedSem_2026/paper figures-tiff` writes
every figure as an LZW-compressed TIFF, 4,016 px wide (600 dpi across a 170 mm page), to
`paper/figures-tiff/`. The files are named by figure number (`Fig1.tif`, …, `FigS9.tif`),
and `figures.tsv` maps each one to its source. The export needs Ghostscript
(`paper-assets/figures/export_tiff.py`).

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
