#!/usr/bin/env python3
"""Package the manuscript and its dependencies after `make all`."""

import hashlib
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    root = Path(__file__).resolve().parent
    bundle_name = "BioMedSem_2026-paper"
    figure_dir = root / "figures"
    if not figure_dir.is_dir():
        figure_dir = root.parent / "paper-assets"
    # The main text's name is set once, by PAPER in the Makefile.
    paper = re.search(r"^PAPER\s*=\s*(\S+)", (root / "Makefile").read_text(encoding="utf-8"), re.M)[1]

    names = [
        f"{paper}.tex", "supplementary.tex", "reference.bib",
        f"{paper}.pdf", "paper.pdf", "supplementary.pdf",
        "Makefile", ".latexmkrc", "README.md", "package.py",
        "template/sn-jnl.cls", "template/bst/sn-mathphys-num.bst",
    ]
    files = {name: root / name for name in names}
    for source in (f"{paper}.tex", "supplementary.tex"):
        figures = re.findall(
            r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}",
            (root / source).read_text(encoding="utf-8"),
        )
        for name in figures:
            files[f"figures/{name}"] = figure_dir / name

    missing = [str(path) for path in files.values() if not path.is_file()]
    if missing:
        raise SystemExit("Run make first; missing bundle inputs:\n" + "\n".join(missing))
    if (root / "paper.pdf").read_bytes() != (root / f"{paper}.pdf").read_bytes():
        raise SystemExit("paper.pdf is stale; run make first")

    output = root / f"{bundle_name}.zip"
    temporary = output.with_suffix(".zip.tmp")
    checksums = []
    with ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            data = path.read_bytes()
            archive.writestr(f"{bundle_name}/{name}", data)
            checksums.append(f"{hashlib.sha256(data).hexdigest()}  {name}\n")
        archive.writestr(f"{bundle_name}/SHA256SUMS.txt", "".join(checksums))
    temporary.replace(output)
    print(f"Created {output.name} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
