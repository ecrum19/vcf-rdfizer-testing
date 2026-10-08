#!/usr/bin/env python3
"""Summarise experiment 18 from its cells: conversions, sizes, and question outcomes.

    python3 summarize.py $BM_RESULTS/18_converter_comparison

Writes summary/conversions.csv (one row per conversion replicate), summary/outcomes.csv (one
row per converter, input, and question), and summary/summary.md. Reads only what the cells
recorded; computes nothing that is not already a measurement in the paper.

Wall time and peak resident set size come from different places, deliberately the same
quantities. For the other converters they are BusyBox `time -v` inside the converter's
container (measure.sh); for VCF-RDFizer, its own run summary, whose wall time spans all its
stages (including starting its stage containers) and whose peak is the largest per-stage
`time -v` maximum.
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from pathlib import Path

QUESTIONS = (
    "q01_record_density_1mb", "q02_variant_shape_counts", "q03_titv",
    "q04_filter_distribution", "q05_sample_genotype_counts", "q06_ac_an_distribution",
    "q07_file_metadata", "q08_header_line_census",
)
SHORT = {"PASS": "pass", "MISMATCH": "differs", "NOT_REPRESENTED": "not in graph",
         "EXECUTION_FAILED": "failed", "RESULT_UNREADABLE": "unreadable"}


def parse_time_v(path: Path) -> tuple[float | None, int | None]:
    """Wall seconds and peak RSS (kB) from `time -v` output."""
    if not path.is_file():
        return None, None
    text = path.read_text(errors="replace")
    wall = rss = None
    match = re.search(r"Elapsed \(wall clock\) time[^:]*:\s*([0-9:.]+)", text)
    if match:
        seconds = 0.0
        for part in match.group(1).split(":"):
            seconds = seconds * 60 + float(part)
        wall = seconds
    match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", text)
    if match:
        rss = int(match.group(1))
    return wall, rss


def vcfrdfizer_metrics(cell: Path) -> tuple[float | None, int | None]:
    summaries = sorted((cell / "out" / "run_metrics").glob("*/summary.json"))
    if not summaries:
        return None, None
    summary = json.loads(summaries[-1].read_text())
    wall = summary.get("execution", {}).get("wall_seconds")
    peaks = [int(value) for table in summary.get("summary_tables", {}).values()
             for row in table for key, value in row.items()
             if key.startswith("max_rss_kb") and str(value).isdigit()]
    return wall, max(peaks) if peaks else None


def read_tsv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return dict(line.split("\t", 1) for line in path.read_text().splitlines() if "\t" in line)


def main() -> int:
    root = Path(sys.argv[1])
    out = root / "summary"
    out.mkdir(exist_ok=True)

    conversions = []
    for cell in sorted(root.glob("convert__*")):
        _, tool, name, rep = cell.name.split("__")
        bench = json.loads((cell / "bench.json").read_text())
        if tool == "vcf-rdfizer":
            wall, rss = vcfrdfizer_metrics(cell)
        else:
            wall, rss = parse_time_v(cell / "out" / "time.txt")
        native = (cell / "native.tsv").read_text().split() if (cell / "native.tsv").is_file() else ["", ""]
        conversions.append({
            "tool": tool, "input": name, "replicate": rep.lstrip("r"),
            "exit_code": bench.get("exit_code"), "wall_seconds": wall, "peak_rss_kb": rss,
            "native_output_sha256": native[0], "native_output_bytes": native[1],
        })
    with (out / "conversions.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(conversions[0]))
        writer.writeheader()
        writer.writerows(conversions)

    outcomes, rows = [], []
    for cell in sorted(root.glob("compare__*")):
        _, tool, name = cell.name.split("__")
        report_path = cell / "out" / "comparison.json"
        report = json.loads(report_path.read_text()) if report_path.is_file() else {}
        sizes = read_tsv(root / f"normalise__{tool}__{name}" / "sizes.tsv")
        for question in QUESTIONS:
            record = report.get("questions", {}).get(question, {"status": "NO_RESULT"})
            outcomes.append({"tool": tool, "input": name, "question": question,
                             "status": record["status"],
                             "missing_rows": record.get("missingRows", ""),
                             "extra_rows": record.get("extraRows", ""),
                             "differing_rows": record.get("differingRows", "")})
        reps = [c for c in conversions if c["tool"] == tool and c["input"] == name
                and c["exit_code"] == 0 and c["wall_seconds"] is not None]
        records = report.get("vcf", {}).get("records")
        triples = int(sizes["triples"]) if "triples" in sizes else None
        rows.append({
            "tool": tool, "input": name,
            "wall_s_median": statistics.median(c["wall_seconds"] for c in reps) if reps else None,
            "peak_rss_gb_max": max(c["peak_rss_kb"] for c in reps if c["peak_rss_kb"]) / 1024 ** 2
                if any(c["peak_rss_kb"] for c in reps) else None,
            "deterministic": len({c["native_output_sha256"] for c in reps}) == 1 if reps else None,
            "triples": triples,
            "triples_per_record": triples / records if triples and records else None,
            "nt_gz_over_vcf_gz": int(sizes["nt_gz_bytes"]) / int(sizes["vcf_gz_bytes"])
                if "nt_gz_bytes" in sizes else None,
            "qlever_index_s": report.get("engine", {}).get("indexBuildSeconds"),
            **{question[:3]: SHORT.get(next(o["status"] for o in outcomes if o["tool"] == tool
                                            and o["input"] == name and o["question"] == question),
                                       "no result")
               for question in QUESTIONS},
        })
    with (out / "outcomes.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(outcomes[0]))
        writer.writeheader()
        writer.writerows(outcomes)

    def fmt(value, spec):
        return "–" if value is None else format(value, spec)

    lines = ["# Experiment 18 summary", "",
             "| Converter | Input | Wall (s, median) | Peak RSS (GB) | Same output every replicate "
             "| Triples | Triples/record | N-Triples.gz ÷ VCF.gz | QLever index (s) | "
             + " | ".join(q[:3].upper() for q in QUESTIONS) + " |",
             "|" + "---|" * (9 + len(QUESTIONS))]
    for row in rows:
        lines.append("| " + " | ".join([
            row["tool"], row["input"], fmt(row["wall_s_median"], ".1f"),
            fmt(row["peak_rss_gb_max"], ".2f"),
            {True: "yes", False: "no", None: "–"}[row["deterministic"]],
            fmt(row["triples"], ","), fmt(row["triples_per_record"], ".1f"),
            fmt(row["nt_gz_over_vcf_gz"], ".1f"), fmt(row["qlever_index_s"], ".1f"),
            *[row[q[:3]] for q in QUESTIONS]]) + " |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
