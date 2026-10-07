# Reproducible, isolated build for the Springer Nature manuscript.
# All LaTeX intermediates are written below .build/$(PAPER)/.
# A distributed source bundle carries its figures inside this directory.

# The main text's source name; package.py reads it from here.
PAPER     = current_revised
BUILD_DIR = .build/$(PAPER)
LATEXMK   = latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error
FIGURE_DIR = $(if $(wildcard figures),figures,../paper-assets)
# Main text: vcf2rdf-v3 (Figure 1), vcf-core-minimal (Figure 2), fig-validation, fig-usecase-matches, fig-usecase-costs, fig-samples,
# and fig-retrieval; the rest are the supplement's.
FIGURES = $(addprefix $(FIGURE_DIR)/,vcf2rdf-v3.pdf vcf-core-minimal.pdf fig-validation.pdf fig-usecase-matches.pdf \
	fig-usecase-costs.pdf fig-samples.pdf fig-retrieval.pdf \
	vcf-core-classes.pdf fig-linking-framework.pdf fig-scaling.pdf fig-representations.pdf)
SOURCES   = $(PAPER).tex supplementary.tex reference.bib template/sn-jnl.cls \
	template/bst/sn-mathphys-num.bst $(FIGURES) Makefile .latexmkrc

.PHONY: all manuscript $(PAPER).pdf paper.pdf supplementary.pdf bundle clean distclean

all: paper.pdf supplementary.pdf

manuscript: paper.pdf

# Each document reads the other's labels from its .aux (xr), so the main text
# is compiled again once the supplement exists; latexmk reruns only if needed.
$(PAPER).pdf: $(SOURCES)
	mkdir -p "$(BUILD_DIR)"
	cp $(PAPER).tex supplementary.tex reference.bib "$(BUILD_DIR)/"
	cp template/sn-jnl.cls template/bst/sn-mathphys-num.bst "$(BUILD_DIR)/"
	cp $(FIGURES) "$(BUILD_DIR)/"
	cd "$(BUILD_DIR)" && $(LATEXMK) $(PAPER).tex && $(LATEXMK) supplementary.tex \
		&& $(LATEXMK) $(PAPER).tex
	cp "$(BUILD_DIR)/$(PAPER).pdf" "$@"

# Keep the source filename stable while exporting the requested shareable name.
paper.pdf: $(PAPER).pdf
	cp "$(PAPER).pdf" "$@"

# Built together with the main text, above.
supplementary.pdf: $(PAPER).pdf
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
