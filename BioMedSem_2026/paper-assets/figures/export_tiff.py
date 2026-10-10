#!/usr/bin/env python3
"""Export every figure of the manuscript and supplement as a high-resolution TIFF.

    export_tiff.py --aux-dir <build dir> --figures-dir <dir of figure PDFs> --out <dir> \\
        current_short.tex supplementary.tex

Each figure is named by the number LaTeX gave it (Fig1.tif, ..., FigS1.tif, ...),
read from the documents' .aux files, so a renumbering renames the files with it.
Run it after a build: `make -C BioMedSem_2026/paper figures-tiff` does both.

The publisher (BMC) asks for about 300 dpi at the final size and recommends
LZW-compressed TIFF. These figures are line art with small text, so each is
rendered to --width-px pixels (default 4016: 600 dpi across BMC's 170 mm
full-page width), anti-aliased, 24-bit RGB, LZW-compressed. Needs Ghostscript.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

FIGURE = re.compile(r"\\begin\{figure\}.*?\\end\{figure\}", re.S)
GRAPHIC = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
LABEL = re.compile(r"\\label\{(fig:[^}]+)\}")


def figures(tex: Path) -> list[tuple[str, str]]:
    """(label, graphic file) for every figure environment in a LaTeX source."""
    out = []
    for block in FIGURE.findall(tex.read_text(encoding="utf-8")):
        graphic, label = GRAPHIC.search(block), LABEL.search(block)
        if graphic and label:
            out.append((label.group(1), graphic.group(1)))
    return out


def numbers(aux: Path) -> dict[str, str]:
    """Figure label -> the number LaTeX printed (e.g. 2, S4)."""
    return dict(re.findall(r"\\newlabel\{(fig:[^}]+)\}\{\{([^}]*)\}", aux.read_text(encoding="utf-8")))


def width_points(pdf: Path) -> float:
    """The width of a PDF's first page, in points."""
    box = subprocess.run(
        ["gs", "-q", "-dNODISPLAY", "-dNOSAFER", "-dBATCH", "-c",
         f"({pdf}) (r) file runpdfbegin 1 pdfgetpage /MediaBox pget pop == quit"],
        capture_output=True, text=True, check=True).stdout
    x0, _y0, x1, _y1 = (float(v) for v in re.findall(r"-?[\d.]+", box)[:4])
    return x1 - x0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sources", nargs="+", type=Path, help="LaTeX sources, in the build's directory or not")
    parser.add_argument("--aux-dir", type=Path, required=True, help="where the build wrote the .aux files")
    parser.add_argument("--figures-dir", type=Path, required=True, help="where the figure PDFs are")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--width-px", type=int, default=4016)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for tex in args.sources:
        printed = numbers(args.aux_dir / (tex.stem + ".aux"))
        for label, graphic in figures(tex):
            pdf = args.figures_dir / graphic
            dpi = args.width_px / (width_points(pdf) / 72)
            name = f"Fig{printed[label]}.tif"
            subprocess.run(
                ["gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=tiff24nc", "-sCompression=lzw",
                 f"-r{dpi:.2f}", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
                 f"-sOutputFile={args.out / name}", str(pdf)],
                check=True)
            rows.append((name, graphic))
            print(f"{name:12} {graphic}")
    with (args.out / "figures.tsv").open("w", encoding="utf-8") as handle:
        handle.write("file\tsource\n" + "".join(f"{n}\t{g}\n" for n, g in rows))
    print(f"wrote {len(rows)} TIFFs ({args.width_px} px wide) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
