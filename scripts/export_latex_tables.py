#!/usr/bin/env python3
"""Export LaTeX-ready conversion/compression tables from combined_metrics.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))


def _bytes_to_mb(value: Any) -> Optional[float]:
    if not _is_number(value):
        return None
    return float(value) / 1_000_000.0


def _kb_to_mb(value: Any) -> Optional[float]:
    if not _is_number(value):
        return None
    return float(value) / 1024.0


def _fmt(value: Optional[float], decimals: int = 1) -> str:
    if value is None:
        return "{}"
    return f"{value:.{decimals}f}"


def _fmt_int(value: Any) -> str:
    if not _is_number(value):
        return "{}"
    return str(int(round(float(value))))


def _escape_latex(text: str) -> str:
    escaped = text
    escaped = escaped.replace("\\", "\\textbackslash{}")
    escaped = escaped.replace("_", "\\_")
    escaped = escaped.replace("%", "\\%")
    escaped = escaped.replace("&", "\\&")
    escaped = escaped.replace("#", "\\#")
    escaped = escaped.replace("{", "\\{")
    escaped = escaped.replace("}", "\\}")
    return escaped


def _load_dataset_rows(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("datasets")
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"No dataset rows found in {path}")
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("input_vcf_size_bytes") or float("inf")),
            str(row.get("dataset") or ""),
        ),
    )


def _conversion_table(rows: List[Dict[str, Any]]) -> str:
    body_lines: List[str] = []
    for row in rows:
        name = _escape_latex(str(row.get("dataset", "unknown")))
        line = (
            f"\\texttt{{{name}}} & "
            f"{_fmt(_bytes_to_mb(row.get('input_vcf_size_bytes')))} & "
            f"{_fmt(row.get('conversion_wall_seconds'))} & "
            f"{_fmt(_kb_to_mb(row.get('conversion_max_rss_kb')))} & "
            f"{_fmt(_bytes_to_mb(row.get('rdf_size_bytes')))} & "
            f"{_fmt_int(row.get('total_triples'))} \\\\"
        )
        body_lines.append(line)

    body = "\n".join(body_lines)
    return f"""% Requires: \\usepackage{{booktabs}}, \\usepackage{{siunitx}}
\\begin{{table*}}[t]
\\centering
\\small
\\setlength{{\\tabcolsep}}{{0pt}}
\\begin{{tabular*}}{{\\textwidth}}{{@{{\\extracolsep{{\\fill}}}}p{{0.28\\textwidth}}
S[table-format=6.1]
S[table-format=6.1]
S[table-format=7.1]
S[table-format=7.1]
S[table-format=10.0]@{{}}}}
\\toprule
\\textbf{{Input VCF}} &
{{\\textbf{{Input \\texttt{{.vcf.gz}} size (MB)}}}} &
{{\\textbf{{Wall time (s)}}}} &
{{\\textbf{{Max RSS (MB)}}}} &
{{\\textbf{{Output raw RDF size (MB)}}}} &
{{\\textbf{{\\# triples}}}} \\\\
\\midrule
{body}
\\bottomrule
\\end{{tabular*}}
\\caption{{Conversion statistics per input file. Sizes are decimal MB.}}
\\label{{tab:conversion-stats}}
\\end{{table*}}
"""


def _compression_table(rows: List[Dict[str, Any]]) -> str:
    body_lines: List[str] = []
    for row in rows:
        name = _escape_latex(str(row.get("dataset", "unknown")))
        line = (
            f"\\texttt{{{name}}} & "
            f"{_fmt(row.get('hdt_wall_seconds'))} & "
            f"{_fmt(row.get('gzip_wall_seconds'))} & "
            f"{_fmt(row.get('brotli_wall_seconds'))} & "
            f"{_fmt(row.get('hdt_gzip_wall_seconds'))} & "
            f"{_fmt(row.get('hdt_brotli_wall_seconds'))} & "
            f"{_fmt(_bytes_to_mb(row.get('hdt_size_bytes')))} & "
            f"{_fmt(_bytes_to_mb(row.get('gzip_size_bytes')))} & "
            f"{_fmt(_bytes_to_mb(row.get('brotli_size_bytes')))} & "
            f"{_fmt(_bytes_to_mb(row.get('hdt_gzip_size_bytes')))} & "
            f"{_fmt(_bytes_to_mb(row.get('hdt_brotli_size_bytes')))} \\\\"
        )
        body_lines.append(line)

    body = "\n".join(body_lines)
    return f"""% Requires: \\usepackage{{booktabs}}, \\usepackage{{tabularx}}, \\usepackage{{siunitx}}, \\usepackage{{array}}
\\begin{{table*}}[t]
\\centering
\\small
\\setlength{{\\tabcolsep}}{{4pt}}
\\begin{{tabularx}}{{\\linewidth}}{{@{{}}>{{\\raggedright\\arraybackslash}}X
S[table-format=6.1] S[table-format=6.1] S[table-format=6.1] S[table-format=6.1] S[table-format=6.1]
S[table-format=6.1] S[table-format=6.1] S[table-format=6.1] S[table-format=6.1] S[table-format=6.1]@{{}}}}
\\toprule
\\textbf{{Input file}} &
\\multicolumn{{5}}{{c}}{{\\textbf{{Time (s)}}}} &
\\multicolumn{{5}}{{c}}{{\\textbf{{Size (MB)}}}} \\\\
\\cmidrule(lr){{2-6}}\\cmidrule(lr){{7-11}}
&
\\textbf{{HDT}} &
\\textbf{{Gzip}} &
\\textbf{{Brotli}} &
\\textbf{{HDT+Gz}} &
\\textbf{{HDT+Br}} &
\\textbf{{HDT}} &
\\textbf{{Gzip}} &
\\textbf{{Brotli}} &
\\textbf{{HDT+Gz}} &
\\textbf{{HDT+Br}} \\\\
\\midrule
{body}
\\bottomrule
\\end{{tabularx}}
\\caption{{Compression statistics per input file. Times are wall-clock seconds; sizes are decimal MB.}}
\\label{{tab:compression-sizes}}
\\end{{table*}}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export LaTeX conversion/compression tables from combined_metrics.json."
    )
    parser.add_argument("combined_metrics_json", type=Path, help="Path to combined_metrics.json")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for generated .tex files (default: same directory as input JSON)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.combined_metrics_json
    if not source.exists():
        raise SystemExit(f"Metrics file not found: {source}")

    output_dir = args.output_dir or source.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_dataset_rows(source)
    conversion_tex = _conversion_table(rows)
    compression_tex = _compression_table(rows)

    conversion_path = output_dir / "conversion_stats_table.tex"
    compression_path = output_dir / "compression_stats_table.tex"

    conversion_path.write_text(conversion_tex, encoding="utf-8")
    compression_path.write_text(compression_tex, encoding="utf-8")

    print(f"Wrote {conversion_path}")
    print(f"Wrote {compression_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
