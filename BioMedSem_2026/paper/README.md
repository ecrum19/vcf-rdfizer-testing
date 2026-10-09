# BioMedSem 2026 manuscript

The main source is `current_short.tex`, the condensed manuscript (set by `PAPER`
in the `Makefile`); `supplementary.tex` contains its supplementary material. The
compiled main text is supplied as both `paper.pdf` and `current_short.pdf`
(identical files). The supplement is `supplementary.pdf`.

`current_long.tex` and `supplementary_long.tex` are the previous full-length
pair, kept for reference and not built by `make`. Each refers to the other, so
compile them with the three commands below, using their names.

## Compile the downloaded ZIP

1. Unzip `BioMedSem_2026-paper.zip` and open the extracted directory.
2. Use a full TeX Live, MacTeX, or MiKTeX installation with pdfLaTeX, BibTeX and
   `latexmk`. A minimal installation may need additional standard LaTeX packages.
3. Run these commands in that directory, in this order:

   ```sh
   latexmk -pdf -interaction=nonstopmode -halt-on-error current_short.tex
   latexmk -pdf -interaction=nonstopmode -halt-on-error supplementary.tex
   latexmk -pdf -interaction=nonstopmode -halt-on-error current_short.tex
   ```

Each document reads the other's cross-references from its `.aux`, so the main
text is compiled again after the supplement. These commands regenerate
`current_short.pdf` and `supplementary.pdf`. To update the `paper.pdf` copy
without Make, copy `current_short.pdf` to `paper.pdf` (`cp current_short.pdf
paper.pdf` on macOS/Linux, or `copy current_short.pdf paper.pdf` in Windows
Command Prompt).

Alternatively, with Make installed, simply run `make`. It builds both documents
in the correct order, refreshes all three PDF filenames, and keeps intermediates
under `.build/current_short/`. Run `make manuscript` for the main text only, `make clean`
to remove intermediates, or `make distclean` to remove the exported PDFs too.

The ZIP includes all figures in `figures/`, the bibliography, and the official
Springer Nature December 2024 class and selected bibliography style in
`template/`. The included `.latexmkrc` supplies their search paths. No benchmark
data, Python packages, Docker image, or neighboring repository is needed to
compile the paper. Existing author queries are retained for the authors to resolve.

## Build and package from the repository

From `BioMedSem_2026/paper`, run `make` to compile or `make bundle` to compile and
create a new `BioMedSem_2026-paper.zip`. Packaging additionally needs Python 3
(standard library only). In the repository, figures are read from
`../paper-assets/`; the packager copies only the figures used by the two documents.
Build caches, editor settings, and benchmark archives are excluded from the ZIP.
