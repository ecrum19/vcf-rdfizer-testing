# Reproducible, isolated build for the Springer Nature manuscript.
# All LaTeX intermediates are written below .build/current/.

PAPER     = current
BUILD_DIR = .build/$(PAPER)
LATEXMK   = latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error
SOURCES   = current.tex reference.bib template/sn-jnl.cls \
	template/bst/sn-mathphys-num.bst ../paper-assets/vcf2rdf-v3.pdf \
	../paper-assets/vcf-core-classes.pdf ../paper-assets/fig-scaling.pdf ../paper-assets/fig-samples.pdf \
	../paper-assets/fig-representations.pdf ../paper-assets/fig-retrieval.pdf \
	../paper-assets/fig-usecase.pdf Makefile

.PHONY: all manuscript $(PAPER).pdf supplementary.pdf clean distclean

all: $(PAPER).pdf supplementary.pdf

manuscript: $(PAPER).pdf

$(PAPER).pdf: $(SOURCES)
	mkdir -p "$(BUILD_DIR)"
	cp current.tex reference.bib "$(BUILD_DIR)/"
	cp template/sn-jnl.cls template/bst/sn-mathphys-num.bst "$(BUILD_DIR)/"
	cp ../paper-assets/vcf2rdf-v3.pdf ../paper-assets/vcf-core-classes.pdf "$(BUILD_DIR)/"
	cp ../paper-assets/fig-scaling.pdf ../paper-assets/fig-samples.pdf \
		../paper-assets/fig-representations.pdf \
		../paper-assets/fig-retrieval.pdf ../paper-assets/fig-usecase.pdf "$(BUILD_DIR)/"
	cd "$(BUILD_DIR)" && $(LATEXMK) $(PAPER).tex
	cp "$(BUILD_DIR)/$(PAPER).pdf" "$@"

# The supplement reads the main text's section numbers from its .aux (xr).
supplementary.pdf: supplementary.tex reference.bib $(PAPER).pdf
	cp supplementary.tex "$(BUILD_DIR)/"
	cd "$(BUILD_DIR)" && $(LATEXMK) supplementary.tex
	cp "$(BUILD_DIR)/supplementary.pdf" "$@"

# Remove intermediates while preserving the exported PDF.
clean:
	rm -rf .build

# Remove intermediates and the exported PDF.
distclean: clean
	rm -f $(PAPER).pdf supplementary.pdf
