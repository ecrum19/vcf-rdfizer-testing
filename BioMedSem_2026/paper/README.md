# BioMedSem 2026 manuscript

The main source is `submitted.tex`, the submitted manuscript (set by `PAPER`
in the `Makefile`); `supplementary.tex` contains its supplementary material. The
compiled main text is supplied as both `paper.pdf` and `submitted.pdf`
(identical files). The supplement is `supplementary.pdf`.

## Compile the downloaded ZIP

1. Unzip `BioMedSem_2026-paper.zip` and open the extracted directory.
2. Use a full TeX Live, MacTeX, or MiKTeX installation with pdfLaTeX, BibTeX and
   `latexmk`. A minimal installation may need additional standard LaTeX packages.
3. Run these commands in that directory, in this order:

   ```sh
   latexmk -pdf -interaction=nonstopmode -halt-on-error submitted.tex
   latexmk -pdf -interaction=nonstopmode -halt-on-error supplementary.tex
   latexmk -pdf -interaction=nonstopmode -halt-on-error submitted.tex
   ```

Each document reads the other's cross-references from its `.aux`, so the main
text is compiled again after the supplement. These commands regenerate
`submitted.pdf` and `supplementary.pdf`. To update the `paper.pdf` copy
without Make, copy `submitted.pdf` to `paper.pdf` (`cp submitted.pdf
paper.pdf` on macOS/Linux, or `copy submitted.pdf paper.pdf` in Windows
Command Prompt).

Alternatively, with Make installed, simply run `make`. It builds both documents
in the correct order, refreshes all three PDF filenames, and keeps intermediates
under `.build/submitted/`. Run `make manuscript` for the main text only, `make clean`
to remove intermediates, or `make distclean` to remove the exported PDFs too.

The ZIP includes all figures in `figures/`, the bibliography, the cover letter
(`VCF-RDFizer_JBS_Cover_Letter.pdf`, kept out of Git and added only when present),
and the official Springer Nature December 2024 class and selected bibliography
style in `template/`. The style carries one documented patch that keeps letters in
page and article numbers. The included `.latexmkrc` supplies their search paths.
No benchmark data, Python packages, Docker image, or neighboring repository is
needed to compile the paper.

## Build and package from the repository

From `BioMedSem_2026/paper`, run `make` to compile or `make bundle` to compile and
create a new `BioMedSem_2026-paper.zip`. Packaging additionally needs Python 3
(standard library only). In the repository, figures are read from
`../paper-assets/`; the packager copies only the figures used by the two documents.
Build caches, editor settings, and benchmark archives are excluded from the ZIP.
