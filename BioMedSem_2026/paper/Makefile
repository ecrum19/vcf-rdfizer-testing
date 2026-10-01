# Reproducible, isolated build for the Springer Nature manuscript.
# All LaTeX intermediates are written below .build/current/.
# A distributed source bundle carries its figures inside this directory.

PAPER     = current
BUILD_DIR = .build/$(PAPER)
LATEXMK   = latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error
FIGURE_DIR = $(if $(wildcard figures),figures,../paper-assets)
FIGURES = $(addprefix $(FIGURE_DIR)/,vcf2rdf-v3.pdf vcf-core-classes.pdf \
	fig-scaling.pdf fig-samples.pdf fig-representations.pdf fig-retrieval.pdf \
	fig-usecase.pdf)
SOURCES   = current.tex reference.bib template/sn-jnl.cls \
	template/bst/sn-mathphys-num.bst $(FIGURES) Makefile .latexmkrc

.PHONY: all manuscript $(PAPER).pdf paper.pdf supplementary.pdf bundle clean distclean

all: paper.pdf supplementary.pdf

manuscript: paper.pdf

$(PAPER).pdf: $(SOURCES)
	mkdir -p "$(BUILD_DIR)"
	cp current.tex reference.bib "$(BUILD_DIR)/"
	cp template/sn-jnl.cls template/bst/sn-mathphys-num.bst "$(BUILD_DIR)/"
	cp $(FIGURES) "$(BUILD_DIR)/"
	cd "$(BUILD_DIR)" && $(LATEXMK) $(PAPER).tex
	cp "$(BUILD_DIR)/$(PAPER).pdf" "$@"

# Keep the source filename stable while exporting the requested shareable name.
paper.pdf: $(PAPER).pdf
	cp "$(PAPER).pdf" "$@"

# The supplement reads the main text's section numbers from its .aux (xr).
supplementary.pdf: supplementary.tex reference.bib $(PAPER).pdf
	cp supplementary.tex "$(BUILD_DIR)/"
	cd "$(BUILD_DIR)" && $(LATEXMK) supplementary.tex
	cp "$(BUILD_DIR)/supplementary.pdf" "$@"

# Python is needed only to package the sources, not to compile them.
bundle: all
	python3 package.py

# Remove intermediates while preserving the exported PDF.
clean:
	rm -rf .build

# Remove intermediates and the exported PDF.
distclean: clean
	rm -f $(PAPER).pdf paper.pdf supplementary.pdf
