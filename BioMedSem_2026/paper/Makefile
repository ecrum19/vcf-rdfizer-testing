# Reproducible, isolated build for the Springer Nature manuscript.
# All LaTeX intermediates are written below .build/current/.

PAPER     = current
BUILD_DIR = .build/$(PAPER)
LATEXMK   = latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error
SOURCES   = current.tex reference_revised.bib template/sn-jnl.cls \
	template/bst/sn-mathphys-num.bst ../paper-assets/vcf2rdf.pdf \
	../paper-assets/class-hierarchy-paper.png Makefile

.PHONY: all manuscript $(PAPER).pdf clean distclean

all manuscript: $(PAPER).pdf

$(PAPER).pdf: $(SOURCES)
	mkdir -p "$(BUILD_DIR)"
	cp current.tex reference_revised.bib "$(BUILD_DIR)/"
	cp template/sn-jnl.cls template/bst/sn-mathphys-num.bst "$(BUILD_DIR)/"
	cp ../paper-assets/vcf2rdf.pdf ../paper-assets/class-hierarchy-paper.png "$(BUILD_DIR)/"
	cd "$(BUILD_DIR)" && $(LATEXMK) $(PAPER).tex
	cp "$(BUILD_DIR)/$(PAPER).pdf" "$@"

# Remove intermediates while preserving the exported PDF.
clean:
	rm -rf .build

# Remove intermediates and the exported PDF.
distclean: clean
	rm -f $(PAPER).pdf
