# BioMedSem 2026 manuscript

Open this directory in VS Code and run the LaTeX Workshop recipe **make current manuscript**, or build from a terminal with `make`.

Build products are isolated in `.build/current/`; `current.pdf` is the exported manuscript. Use `make clean` to remove intermediates or `make distclean` to remove the PDF as well.

The local `template/` directory contains the official Springer Nature December 2024 `sn-jnl.cls` and the bibliography style selected by `current.tex`, so the project does not depend on a Downloads-folder copy of the template.
