#!/usr/bin/env python3
"""Build the manuscript's data figures from the archived benchmark results.

    python3 make_figures.py            # writes ../fig-*.pdf

Every number is read from BioMedSem_2026/benchmark-results, never typed in,
so the figures can be regenerated when a campaign is replaced. All of them are
the v3.1.0 campaign (the live trees on both hosts).

Colour: two categorical hues (blue, orange) plus gray for context, validated
together on the white page with the dataviz palette validator. Figures are
for print, so there is one (light) mode and no hover layer; every plotted
value is also stated in the text or in the archived tidy datasets.
"""

from __future__ import annotations

import csv
import glob
import os
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402

from figure_data import (  # noqa: E402 - stdlib-only data layer shared with the site
    B1, HG005_WHOLE_RECORDS, QUERIES, corpus_rows, records_ladder, retrieval, sample_ladder, storage_modes,
    tidy,
)

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
# The validation and use-case readers live with the results site's builder.
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
import build_site_data as site  # noqa: E402

# ---------------------------------------------------------------------------
# Style: the reference palette's light-mode roles
# ---------------------------------------------------------------------------
BLUE = "#2a78d6"      # categorical slot 1
ORANGE = "#eb6834"    # categorical slot 2
BLUE_LIGHT = "#86b6ef"
GRAY = "#a8a69f"      # context marks
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
WIDTH_IN = 372 / 72.27  # sn-jnl \textwidth
#: No creation timestamp, so regenerating an unchanged figure rewrites identical bytes.
PDF_METADATA = {"CreationDate": None}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 7,
    "axes.titlesize": 7.5,
    "axes.labelsize": 7,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 0.6,
    "axes.labelcolor": INK_2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": INK_2,
    "ytick.labelcolor": INK_2,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "axes.titlecolor": INK,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlepad": 6,
    "legend.frameon": False,
    "legend.fontsize": 6.5,
    "pdf.fonttype": 42,
    "savefig.dpi": 300,
})


def style_axes(ax, grid_axis: str = "x") -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def dot(ax, x, y, color, size=5.5, zorder=3, **kw):
    """A filled marker with a white ring, so it reads where it crosses a line."""
    ax.plot(x, y, "o", color=color, markersize=size, markeredgecolor="white",
            markeredgewidth=0.9, zorder=zorder, **kw)


def seconds_label(v: float, _pos=None) -> str:
    if v >= 1:
        return f"{v:g}"
    return f"{v:.3f}".rstrip("0")


# ---------------------------------------------------------------------------
# Figure: the record ladder, and storage mode (supplement)
# ---------------------------------------------------------------------------
#: The supplement's text width (a4, 2.4 cm margins), so its figures print unscaled.
SUPP_WIDTH_IN = 459.5 / 72.27
AQUA = "#1baf7a"      # categorical slot 3 (validated with slots 1-2; sub-3:1, so always labelled)
B1_LADDER = B1 / "04_scaling_records" / "tidy.csv"
RUNG_LABELS = ["10k", "100k", "1M", "3.86M\n(complete)"]


def loglog_slope(ladder: dict, key: str) -> float:
    """Least-squares exponent over every replicate: value ~ records ** slope."""
    import math
    xs, ys = [], []
    for n, run in ladder["runs"].items():
        for v in run[key]:
            xs.append(math.log10(n)); ys.append(math.log10(v))
    mx, my = st.mean(xs), st.mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)


def duration(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3600:.1f} h"


def stage_shares() -> list[tuple[int, float, dict]]:
    """Median seconds per stage at each rung of the ladder; 'other' is the remainder of the wall time."""
    by_rung = {}
    for row in tidy(B1_LADDER):
        rung = row["cell"].split("__")[0]
        n = HG005_WHOLE_RECORDS if rung == "rfull" else int(rung[1:])
        g = lambda k: float(row[k]) if row.get(k) else 0.0  # noqa: E731
        parts = {
            "rml": g("wall_seconds_java"),
            "hdt": sum(g(k) for k in ("chunk_stream_seconds", "build_seconds__hdt_chunk_build",
                                      "build_seconds__hdt_merge", "build_seconds__hdt_index")),
            "decode": g("build_seconds__hdt_validate"),
        }
        parts["other"] = g("wrapper_wall_seconds") - sum(parts.values())
        by_rung.setdefault(n, []).append((g("wrapper_wall_seconds"), parts))
    out = []
    for n in sorted(by_rung):
        runs = by_rung[n]
        total = st.median(w for w, _ in runs)
        parts = {k: st.median(p[k] for _, p in runs) for k in runs[0][1]}
        out.append((n, total, parts))
    return out


def fig_scaling() -> None:
    """Record ladder: absolute triples, time, disk, and memory, where the time goes, and storage mode."""
    ladder = records_ladder()
    rungs, med, runs = ladder["rungs"], ladder["median"], ladder["runs"]
    fig = plt.figure(figsize=(SUPP_WIDTH_IN, 4.55))
    top = GridSpec(1, 4, figure=fig, left=0.075, right=0.985, top=0.9, bottom=0.6, wspace=0.55)
    low_l = GridSpec(1, 1, figure=fig, left=0.135, right=0.58, top=0.4, bottom=0.08)
    low_r = GridSpec(1, 1, figure=fig, left=0.79, right=0.985, top=0.36, bottom=0.08)

    # (a)-(d): one measure each, absolute, against records -----------------------
    panels = [
        ("triples", "Triples", lambda v: f"{v / 1e6:,.1f}M" if v < 1e9 else f"{v / 1e9:.2f}B",
         {1e6: "1M", 1e7: "10M", 1e8: "100M", 1e9: "1B"}),
        ("wall", "End-to-end time", duration, {60: "1 min", 600: "10 min", 3600: "1 h", 36000: "10 h"}),
        ("disk", "Peak disk", lambda v: f"{v / 1e6:.0f} MB" if v < 1e9 else f"{v / 1e9:.1f} GB",
         {1e7: "10 MB", 1e8: "100 MB", 1e9: "1 GB", 1e10: "10 GB"}),
        ("rss", "Mapping memory", None, None),
    ]
    for i, (key, title, fmt, ticks) in enumerate(panels):
        log_y = ticks is not None
        ax = fig.add_subplot(top[0, i])
        style_axes(ax, "y")
        ax.set_xscale("log")
        values = med[key]
        if log_y:
            ax.set_yscale("log")
        ax.plot(rungs, values, color=BLUE, linewidth=1.6, solid_capstyle="round", zorder=2)
        for n in rungs:
            for v in runs[n][key]:
                ax.plot(n, v, "o", color=BLUE_LIGHT, markersize=2.6, zorder=3, markeredgewidth=0)
        for x, y in zip(rungs, values):
            dot(ax, x, y, BLUE, size=4.6, zorder=4)
        ax.set_xlim(6e3, 6e6)
        ax.xaxis.set_major_locator(FixedLocator(rungs))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xticklabels(["10k", "100k", "1M", "3.9M"], fontsize=6)
        ax.tick_params(axis="x", length=2)
        if log_y:
            lo, hi = min(ticks), max(ticks)
            ax.set_ylim(lo / 2.5, hi * 2.5)
            ax.yaxis.set_major_locator(FixedLocator(list(ticks)))
            ax.yaxis.set_minor_locator(NullLocator())
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p, d=ticks: d.get(v, "")))
            slope = loglog_slope(ladder, key)
            ax.text(0.96, 0.05, f"$\\propto$ records$^{{{slope:.2f}}}$", transform=ax.transAxes, color=INK_2,
                    fontsize=6.5, va="bottom", ha="right")
        else:
            ax.set_ylim(0, 2.0e9 / 1024)
            ax.yaxis.set_major_locator(FixedLocator([0, 0.5e9 / 1024, 1e9 / 1024, 1.5e9 / 1024, 2e9 / 1024]))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v * 1024 / 1e9:g} GB"))
            ax.text(0.04, 0.96, "flat", transform=ax.transAxes, color=INK_2, fontsize=6.5, va="top")
        ax.tick_params(axis="y", labelsize=6)
        # Label the end points only, so the line carries the trend.
        if log_y:
            ax.annotate(fmt(values[0]), (rungs[0], values[0]), textcoords="offset points",
                        xytext=(5, -2), ha="left", va="top", color=INK_2, fontsize=6)
            ax.annotate(fmt(values[-1]), (rungs[-1], values[-1]), textcoords="offset points",
                        xytext=(-5, 2), ha="right", va="bottom", color=INK_2, fontsize=6)
        else:
            gb = [v * 1024 / 1e9 for v in values]
            ax.text(0.96, 0.06, f"{min(gb):.1f}\u2013{max(gb):.1f} GB at every size", transform=ax.transAxes,
                    ha="right", va="bottom", color=INK_2, fontsize=6)
        ax.set_title(f"({'abcd'[i]}) {title}", fontsize=7)
        if i == 0:
            ax.set_xlabel("HG005 records", fontsize=6.5)

    # (e) where the time goes ----------------------------------------------------
    ax = fig.add_subplot(low_l[0, 0])
    stages = [("rml", "RML mapping", BLUE), ("hdt", "HDT construction", ORANGE),
              ("decode", "HDT decode check", AQUA), ("other", "Other", GRAY)]
    shares = stage_shares()
    for y, (n, total, parts) in zip(range(len(shares) - 1, -1, -1), shares):
        left = 0.0
        for key, _label, color in stages:
            frac = parts[key] / total
            ax.barh(y, frac, left=left, height=0.62, color=color, edgecolor="white", linewidth=1.0, zorder=2)
            if frac >= 0.06:
                ax.text(left + frac / 2, y, f"{100 * frac:.0f}%", ha="center", va="center",
                        color="white" if key in ("rml", "hdt") else INK, fontsize=6.2, zorder=3)
            left += frac
        ax.text(1.02, y, duration(total), va="center", ha="left", color=INK_2, fontsize=6.5)
    ax.set_yticks(range(len(shares)))
    ax.set_yticklabels(list(reversed(["10k records", "100k records", "1M records", "3.86M records\n(complete VCF)"])))
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{100 * v:.0f}%"))
    ax.set_xlabel("Share of end-to-end time (total at right)")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, label=l) for _k, l, c in stages]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.02, 1.02), ncol=4,
              handlelength=1.0, handletextpad=0.35, columnspacing=0.9, fontsize=6.2, borderaxespad=0)
    ax.set_title("(e) HDT construction, not RDF mapping, sets the time", pad=17)

    # (f) storage mode -----------------------------------------------------------
    storage = storage_modes()
    ax = fig.add_subplot(low_r[0, 0])
    style_axes(ax, "x")
    rows = [("larger", "test-larger\n269M triples"), ("slice", "100k HG005 records\n17.1M triples")]
    for y, (key, label) in enumerate(rows):
        plain = st.mean(v[0] for v in storage[key]["plain"]) / 1e9
        spo = st.mean(v[0] for v in storage[key]["space-optimized"]) / 1e9
        t_plain = st.mean(v[1] for v in storage[key]["plain"])
        t_spo = st.mean(v[1] for v in storage[key]["space-optimized"])
        ax.plot([spo, plain], [y, y], color=GRAY, linewidth=1.2, zorder=1)
        dot(ax, plain, y, GRAY)
        dot(ax, spo, y, BLUE)
        ax.text((plain * spo) ** 0.5, y + 0.22,
                f"{plain / spo:.1f}× less disk\n{100 * (t_spo / t_plain - 1):+.1f}% time",
                color=INK_2, fontsize=6, va="bottom", ha="center")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([label for _, label in rows], fontsize=6.2)
    ax.set_ylim(-0.5, len(rows) - 0.15)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xscale("log")
    ax.set_xlim(0.15, 160)
    ax.xaxis.set_major_locator(FixedLocator([0.3, 3, 30]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xlabel("Peak disk (GB)")
    ax.plot([], [], "o", color=BLUE, markersize=4.5, label="Space-optimized")
    ax.plot([], [], "o", color=GRAY, markersize=4.5, label="Plain")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.05, 1.0), ncol=2, handletextpad=0.2,
              columnspacing=0.8, borderaxespad=0.1, fontsize=6.2)
    ax.set_title("(f) Space-optimized storage", x=-0.62, y=1.12, pad=12)

    fig.savefig(OUT / "fig-scaling.pdf", metadata=PDF_METADATA)
    plt.close(fig)
    for key in ("triples", "wall", "disk", "rss"):
        print(f"ladder {key}: slope {loglog_slope(ladder, key):.3f}", [round(v) for v in med[key]])
    for n, total, parts in shares:
        print(f"ladder time {n}: {total:.0f} s", {k: f"{100 * v / total:.1f}%" for k, v in parts.items()})


# ---------------------------------------------------------------------------
# Figure: when converting pays off (supplement)
# ---------------------------------------------------------------------------
#: The N-Triples-only rerun on vcf-bench-2: conversion alone (convert__repN), and the query-cost
#: run without HDT or COTTAS (validate__repN), both with v3.1.0 on the 100,000-record slice.
NT_ONLY = site.RESULTS / "vcf-bench-2" / "nt-only"


def nt_only_rerun() -> dict:
    """Conversion wall times, QLever setup, and per-question query and parse times of the rerun."""
    conversion = [float((d / "wall_seconds.txt").read_text()) for d in sorted(NT_ONLY.glob("convert__rep*"))]
    sparql, parser, setup, seen = defaultdict(list), defaultdict(list), {}, set()
    for rep in sorted(NT_ONLY.glob("validate__rep*")):
        for path in rep.glob("out/run_metrics/*/reports/validation/*/benchmark.csv"):
            for row in tidy(path):
                if row["query_id"] not in dict(QUERIES) or row["status"] != "PASS" or row["engine"] != "qlever":
                    continue
                if (rep.name, row["query_id"]) in seen:
                    continue
                seen.add((rep.name, row["query_id"]))
                sparql[row["query_id"]].append(float(row["wall_seconds"]))
                parser[row["query_id"]].append(float(row["oracle_query_seconds"]))
                setup.setdefault(rep.name, float(row["engine_setup_seconds"]))
    return {"conversion": conversion, "index": list(setup.values()),
            "sparql": dict(sparql), "parser": dict(parser)}


def breakeven() -> dict:
    """Setup, per-question parse and query times, and the break-even, on 100,000 HG005 records.

    Everything comes from the N-Triples-only rerun: conversion to the gzip-framed N-Triples
    that QLever indexes, QLever indexing, and the query-cost validation on them. The base
    campaign's conversions also built HDT; that setup is kept only for comparison.
    """
    rerun = nt_only_rerun()
    parser = {q: st.median(v) for q, v in rerun["parser"].items()}
    sparql = {q: st.mean(v) for q, v in rerun["sparql"].items()}
    conversion, index = st.mean(rerun["conversion"]), st.mean(rerun["index"])
    setup = conversion + index
    scan, query = st.median(parser.values()), st.mean(sparql.values())
    # Base campaign, for comparison: the record ladder's conversion with HDT, the query-cost index.
    campaign = retrieval()
    with_hdt = st.mean(float(row["wrapper_wall_seconds"]) for row in tidy(B1_LADDER)
                       if row["cell"].startswith("r100000__")) + campaign["ql_setup"]
    c_scan = st.median(st.median(v) for v in campaign["oracle_q"].values())
    c_query = st.mean(st.mean(v) for v in campaign["engine_q"].values())
    return {"conversion": conversion, "conversion_runs": rerun["conversion"], "index": index,
            "setup": setup, "scan": scan, "query": query, "n_star": setup / (scan - query),
            "per_question": {q: setup / (parser[q] - sparql[q]) for q, _ in QUERIES},
            "setup_with_hdt": with_hdt, "n_star_with_hdt": with_hdt / (c_scan - c_query)}


#: Gzipped VCF inputs, measured on the hosts; the run records hold uncompressed sizes only.
VCF_INPUT_SIZES = site.RESULTS / "vcf-input-sizes.json"


def ingest_sizes() -> list[tuple[str, int, int]]:
    """(label, gzipped VCF bytes, gzip-framed N-Triples bytes that QLever ingested)."""
    vcf = site.load(VCF_INPUT_SIZES)["files"]
    slice_nt = st.median(int(row["combined_rdf_size_bytes"]) for row in tidy(B1 / "13_query_cost" / "tidy.csv")
                         if row["cell"].startswith("large"))
    whole_nt = site.load(site.RESULTS / "vcf-bench-3" / "scale-store-manifests"
                         / "whole.manifest.json")["artifacts"]["nt.gz"]["bytes"]
    return [("100,000\nHG005 records", vcf["HG005_GRCh38_r100000.vcf.gz"]["bytes"], slice_nt),
            ("Complete\nHG005 VCF", vcf["HG005_GRCh38.vcf.gz"]["bytes"], whole_nt)]


# ---------------------------------------------------------------------------
# Figure: sample profiles -- triples against stored bytes
# ---------------------------------------------------------------------------
def fig_samples() -> None:
    lad = sample_ladder()
    c, e = lad["condensed"], lad["expanded"]
    s_x = c["x"]
    assert s_x == e["x"]

    fig = plt.figure(figsize=(WIDTH_IN, 3.95))
    top = GridSpec(1, 2, figure=fig, wspace=0.36, left=0.1, right=0.955, top=0.935,
                   bottom=0.43)
    bottom = GridSpec(1, 1, figure=fig, left=0.27, right=0.93, top=0.235, bottom=0.09)

    def sample_axis(ax):
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(0.6, 5000)
        ax.xaxis.set_major_locator(FixedLocator(s_x))
        ax.xaxis.set_minor_locator(NullLocator())
        # 1,024 and 2,504 sit too close on a log axis for two labels.
        ax.set_xticklabels(["" if n == 1024 else f"{n:,}" for n in s_x])
        ax.set_xlabel("Samples in the VCF (10,000 records, fixed)")

    # (a) triples --------------------------------------------------------------
    ax = fig.add_subplot(top[0, 0])
    style_axes(ax, "both")
    for series, color, label in ((e, ORANGE, "Expanded profile"), (c, BLUE, "Condensed profile")):
        ys = [v / 1e6 for v in series["triples"]]
        ax.plot(s_x, ys, color=color, linewidth=1.6, solid_capstyle="round", label=label)
        for x, y in zip(s_x, ys):
            dot(ax, x, y, color)
    sample_axis(ax)
    ax.set_ylim(0.6, 2500)
    ax.yaxis.set_major_locator(FixedLocator([1, 10, 100, 1000]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}M"))
    ax.set_ylabel("RDF triples")
    ax.legend(loc="upper left", handlelength=1.6, borderaxespad=0.2)
    g_c = c["triples"][-1] / c["triples"][0]
    g_e = e["triples"][-1] / e["triples"][0]
    ax.text(s_x[-1], e["triples"][-1] / 1e6 * 1.35, f"{g_e:.0f}×", color=INK_2,
            fontsize=6.5, ha="center", va="bottom")
    ax.text(s_x[-1], c["triples"][-1] / 1e6 * 0.7, f"+{100 * (g_c - 1):.1f}%", color=INK_2,
            fontsize=6.5, ha="center", va="top")
    ax.set_title("(a) Triples by number of samples")

    # (b) stored bytes -----------------------------------------------------------
    ax = fig.add_subplot(top[0, 1])
    style_axes(ax, "both")
    has_cottas = "cottas" in c and "cottas" in e
    vcf = [v / 1e6 for v in c["vcf"]]
    ax.plot(s_x, vcf, color=GRAY, linewidth=1.2, solid_capstyle="round", zorder=1)
    # The gzipped inputs, measured on the host: the run records hold uncompressed sizes only.
    gz = site.load(VCF_INPUT_SIZES)["files"]
    vcf_gz = [gz[f"1000G_10000r_s{n}.vcf.gz"]["bytes"] / 1e6 for n in s_x]
    ax.plot(s_x, vcf_gz, color=GRAY, linewidth=1.2, linestyle=(0, (3, 2)), solid_capstyle="round", zorder=1)
    for series, color in ((e, ORANGE), (c, BLUE)):
        hdt = [v / 1e6 for v in series["hdt"]]
        nt = [v / 1e6 for v in series["nt"]]
        ax.plot(s_x, hdt, color=color, linewidth=1.6, solid_capstyle="round", zorder=2)
        ax.plot(s_x, nt, color=color, linewidth=0.9, solid_capstyle="round", zorder=2)
        for x, y in zip(s_x, hdt):
            dot(ax, x, y, color, size=5)
        for x, y in zip(s_x, nt):
            ax.plot(x, y, "o", markersize=4.2, markerfacecolor="white", markeredgecolor=color,
                    markeredgewidth=1.0, zorder=3)
        if has_cottas:
            cot = [v / 1e6 for v in series["cottas"]]
            ax.plot(s_x, cot, color=color, linewidth=1.2, solid_capstyle="round", zorder=2)
            for x, y in zip(s_x, cot):
                ax.plot(x, y, "s", markersize=4.2, color=color, markeredgecolor="white",
                        markeredgewidth=0.8, zorder=3)
    sample_axis(ax)
    ax.set_ylim(0.1, 2.5e5)
    ax.yaxis.set_major_locator(FixedLocator([0.1, 1, 10, 100, 1000, 10000]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{v / 1000:g} GB" if v >= 1000 else f"{v:g} MB"))
    ax.set_ylabel("Size on disk")
    handles = [
        plt.Line2D([], [], color=INK_2, linewidth=1.6, marker="o", markersize=4.5,
                   label="HDT"),
        plt.Line2D([], [], color=INK_2, linewidth=0.9, marker="o", markersize=4,
                   markerfacecolor="white", markeredgecolor=INK_2, label="gzip-framed N-Triples"),
        plt.Line2D([], [], color=GRAY, linewidth=1.2, label="Source VCF"),
        plt.Line2D([], [], color=GRAY, linewidth=1.2, linestyle=(0, (3, 2)), label="Source VCF, gzip"),
    ]
    if has_cottas:
        handles.insert(1, plt.Line2D([], [], color=INK_2, linewidth=1.2, marker="s",
                                     markersize=4, label="COTTAS"))
    ax.legend(handles=handles, loc="upper left", handlelength=1.8, borderaxespad=0.2, ncol=2,
              columnspacing=0.8, fontsize=5.9)
    ax.text(64, e["hdt"][3] / 1e6 * 2.2, "Expanded profile", color=INK_2, fontsize=6.5, ha="right",
            va="bottom")
    ax.text(4, c["nt"][1] / 1e6 * 0.62, "Condensed profile", color=INK_2, fontsize=6.5, ha="center",
            va="top")
    ax.set_title("(b) Stored size by number of samples")

    # (c) the gap, measured three ways ----------------------------------------
    ax = fig.add_subplot(bottom[0, 0])
    style_axes(ax, "x")
    gaps = [("Triple count", e["triples"][-1] / c["triples"][-1]),
            ("gzip-framed N-Triples size", e["nt"][-1] / c["nt"][-1]),
            ("HDT size", e["hdt"][-1] / c["hdt"][-1])]
    if "cottas" in c and "cottas" in e:
        gaps.append(("COTTAS size", e["cottas"][-1] / c["cottas"][-1]))
    for y, (label, gap) in zip(range(len(gaps) - 1, -1, -1), gaps):
        # Neutral: blue and orange name the profiles in this figure.
        ax.barh(y, gap, height=0.55, color=GRAY, zorder=2)
        ax.text(gap * 1.08, y, f"{gap:.0f}×", color=INK_2, fontsize=6.5, va="center")
    ax.set_yticks(range(len(gaps)))
    ax.set_yticklabels([label for label, _ in reversed(gaps)])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xscale("log")
    ax.set_xlim(1, 1500)
    ax.xaxis.set_major_locator(FixedLocator([1, 10, 100, 1000]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}×"))
    ax.set_xlabel("Expanded ÷ condensed (log scale)")
    ax.set_title(f"(c) Expanded-to-condensed ratio at {s_x[-1]:,} samples, by measure")

    fig.savefig(OUT / "fig-samples.pdf", metadata=PDF_METADATA)
    plt.close(fig)

    print("samples: S, triples c/e, nt MB c/e, hdt MB c/e, vcf MB")
    for i, n in enumerate(s_x):
        print(f"  {n:5d} {c['triples'][i]:12,.0f} {e['triples'][i]:13,.0f} "
              f"{c['nt'][i]/1e6:8.2f} {e['nt'][i]/1e6:9.1f} {c['hdt'][i]/1e6:8.2f} "
              f"{e['hdt'][i]/1e6:9.1f} {c['vcf'][i]/1e6:7.1f}")
    print("  gaps:", [(k, round(v, 1)) for k, v in gaps])


# ---------------------------------------------------------------------------
# Figure: queryable representations in the corpus experiment
# ---------------------------------------------------------------------------
def fig_representations() -> None:
    rows = corpus_rows()
    labels = [f"{r['name']} · {r['triples'] / 1e6:.0f}M" for r in rows]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(WIDTH_IN, 2.75), sharey=True,
                                   gridspec_kw=dict(wspace=0.12, left=0.215, right=0.985,
                                                    top=0.80, bottom=0.15))
    y = range(len(rows))

    style_axes(ax1, "x")
    ax1.plot([1.0, 1.0], [-0.6, len(rows) - 0.45], color=INK_2, linewidth=0.7, zorder=1)
    ax1.text(1.0, len(rows) - 0.05, "stored gzip N-Triples", color=INK_2, fontsize=6,
             ha="center", va="bottom", zorder=4,
             bbox=dict(facecolor="white", edgecolor="none", pad=1.0))
    for i, r in enumerate(rows):
        h, c = r["hdt"] / r["nt"], r["cottas"] / r["nt"]
        ax1.plot([c, h], [i, i], color=GRID, linewidth=1.2, zorder=1)
        dot(ax1, h, i, ORANGE)
        dot(ax1, c, i, BLUE)
    ax1.set_xlim(0, 2.0)
    ax1.set_xticks([0, 0.5, 1.0, 1.5, 2.0])
    ax1.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}×"))
    ax1.set_xlabel("Artifact size relative to the stored N-Triples")
    ax1.set_yticks(list(y))
    ax1.set_yticklabels(labels)
    ax1.tick_params(axis="y", length=0)
    ax1.spines["left"].set_visible(False)
    ax1.set_ylim(-0.6, len(rows) + 0.25)
    c_lo = min(r["cottas"] / r["nt"] for r in rows); c_hi = max(r["cottas"] / r["nt"] for r in rows)
    h_lo = min(r["hdt"] / r["nt"] for r in rows); h_hi = max(r["hdt"] / r["nt"] for r in rows)
    ax1.set_title(f"(a) COTTAS {c_lo:.2f}–{c_hi:.2f}×, always smallest;\n"
                  f"     HDT {h_lo:.2f}–{h_hi:.2f}×, larger than N-Triples")

    style_axes(ax2, "x")
    for i, r in enumerate(rows):
        h, c = r["hdt_s"] / 60, r["cottas_s"] / 60
        ax2.plot([h, c], [i, i], color=GRID, linewidth=1.2, zorder=1)
        dot(ax2, h, i, ORANGE)
        dot(ax2, c, i, BLUE)
    ax2.set_xscale("log")
    ax2.set_xlim(5, 900)
    ax2.xaxis.set_major_locator(FixedLocator([10, 30, 100, 300]))
    ax2.xaxis.set_minor_locator(NullLocator())
    ax2.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax2.set_xlabel("Build time (minutes)")
    ax2.tick_params(axis="y", length=0)
    ax2.spines["left"].set_visible(False)
    ratios = [r["cottas_s"] / r["hdt_s"] for r in rows]
    ax2.set_title(f"(b) COTTAS takes {min(ratios):.1f}–{max(ratios):.1f}× longer\n"
                  f"     to build than HDT")

    handles = [plt.Line2D([], [], marker="o", linestyle="", color=BLUE, markersize=5,
                          label="COTTAS"),
               plt.Line2D([], [], marker="o", linestyle="", color=ORANGE, markersize=5,
                          label="HDT")]
    fig.legend(handles=handles, loc="upper right", ncol=2, bbox_to_anchor=(0.985, 1.0),
               handletextpad=0.3, columnspacing=1.2)
    fig.savefig(OUT / "fig-representations.pdf", metadata=PDF_METADATA)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure: retrieval cost
# ---------------------------------------------------------------------------
def fig_retrieval() -> None:
    data = retrieval()
    engine_q, oracle_q = data["engine_q"], data["oracle_q"]
    ql_batch, ql_setup, parser_batch = data["ql_batch"], data["ql_setup"], data["parser_batch"]
    per_target, setup = data["per_target"], data["setup"]
    engine_runs, small_setup = data["engine_runs"], data["small_setup"]

    fig = plt.figure(figsize=(WIDTH_IN, 4.35))
    gs = GridSpec(2, 2, figure=fig, height_ratios=[2.6, 1.0], hspace=0.5, wspace=0.55,
                  left=0.19, right=0.9, top=0.93, bottom=0.11)

    # (a) per question --------------------------------------------------------
    ax = fig.add_subplot(gs[0, :])
    style_axes(ax, "x")
    n = len(QUERIES)
    ys = list(range(n + 1, 1, -1))  # Q1 at the top; row 0 is the batch
    for y, (qid, _) in zip(ys, QUERIES):
        ql, cv = st.mean(engine_q[qid]), st.mean(oracle_q[qid])
        ax.plot([ql, cv], [y, y], color=GRID, linewidth=1.2, zorder=1)
        dot(ax, cv, y, GRAY)
        dot(ax, ql, y, BLUE)
        speed = cv / ql
        ax.text(1.015, y, f"{speed:,.0f}×" if speed >= 10 else f"{speed:.1f}×",
                transform=ax.get_yaxis_transform(), color=INK_2, fontsize=6.5,
                ha="left", va="center")
    # The whole batch: one parser pass against QLever's query time plus setup.
    ax.plot([ql_batch, ql_batch + ql_setup], [0, 0], color=BLUE_LIGHT, linewidth=2.2,
            solid_capstyle="butt", zorder=2)
    ax.plot([parser_batch, ql_batch], [0, 0], color=GRID, linewidth=1.2, zorder=1)
    dot(ax, parser_batch, 0, GRAY)
    dot(ax, ql_batch, 0, BLUE)
    ax.text((ql_batch * (ql_batch + ql_setup)) ** 0.5, 0.3, f"+ {ql_setup:.1f} s indexing",
            color=INK_2, fontsize=6, ha="center", va="bottom")
    ax.text(1.015, 0, f"{parser_batch / ql_batch:.1f}×", transform=ax.get_yaxis_transform(),
            color=INK_2, fontsize=6.5, ha="left", va="center")
    ax.axhline(1, color=AXIS, linewidth=0.6)
    ax.set_yticks([0] + ys)
    ax.set_yticklabels(["Q1–Q13 as one batch"] + [label for _, label in QUERIES])
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_ylim(-0.7, n + 2.6)
    ax.set_xscale("log")
    ax.set_xlim(0.003, 60)
    ax.xaxis.set_major_locator(FixedLocator([0.01, 0.1, 1, 10]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(seconds_label))
    ax.set_xlabel("Seconds (log scale), mean of three replicates")
    ax.text(1.015, n + 1, "Speed-up", transform=ax.get_yaxis_transform(), color=INK,
            fontsize=6.5, fontweight="bold", ha="left", va="bottom")
    ax.texts[-1].set_position((1.015, n + 1.6))
    handles = [plt.Line2D([], [], marker="o", linestyle="", color=BLUE, markersize=5,
                          label="Indexed SPARQL (QLever)"),
               plt.Line2D([], [], marker="o", linestyle="", color=GRAY, markersize=5,
                          label="VCF parsing (cyvcf2)")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.005, 1.0), ncol=2,
              handletextpad=0.3, columnspacing=1.2, borderaxespad=0.2)
    ax.set_title("(a) Time per question on 100,000 HG005 records (17.1M triples)")

    # (b) engines --------------------------------------------------------------
    order = ["qlever", "comunica", "cottas", "hdt"]
    names = {"qlever": "QLever", "comunica": "Comunica, N-Triples", "cottas": "Comunica, COTTAS",
             "hdt": "Comunica, HDT"}
    ax = fig.add_subplot(gs[1, 0])
    style_axes(ax, "x")
    for y, engine in zip(range(len(order) - 1, -1, -1), order):
        runs = engine_runs[engine]
        mean = st.mean(runs)
        color = BLUE if engine == "qlever" else GRAY
        ax.barh(y, mean, height=0.55, color=color, zorder=2)
        ax.plot([min(runs), max(runs)], [y, y], color=INK_2, linewidth=0.7, zorder=3)
        ax.text(max(runs) + 1.2, y, f"{mean:.1f} s", color=INK_2, fontsize=6.5, va="center")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([names[e] for e in reversed(order)])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 60)
    ax.set_xlabel("Total for Q1–Q13 (s)\n10,000-line fixture, 0.96M triples")
    ax.set_title("(b) Total by SPARQL engine")

    # (c) artifacts -----------------------------------------------------------
    arts = [("nt", "N-Triples"), ("hdt", "HDT"), ("cottas", "COTTAS")]
    ax = fig.add_subplot(gs[1, 1])
    style_axes(ax, "x")
    for y, (target, label) in zip(range(len(arts) - 1, -1, -1), arts):
        mean = st.mean(per_target[target])
        ax.barh(y, mean, height=0.55, color=BLUE, zorder=2)
        ax.text(mean + 0.6, y, f"{mean:.2f} s", color=INK_2, fontsize=6.5, va="center")
    ax.set_yticks(range(len(arts)))
    ax.set_yticklabels([label for _, label in reversed(arts)])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 24)
    ax.set_xlabel("Total for Q1–Q13 (s)\n100,000 HG005 records, 17.1M triples")
    ax.set_title("(c) QLever total by input artifact")

    fig.savefig(OUT / "fig-retrieval.pdf", metadata=PDF_METADATA)
    plt.close(fig)

    print("retrieval: per-question QLever/cyvcf2 (mean):")
    for qid, label in QUERIES:
        print(f"  {label:22s} {st.mean(engine_q[qid]):8.3f} {st.mean(oracle_q[qid]):7.2f}")
    print(f"  batch: qlever {ql_batch:.2f} + setup {ql_setup:.2f}; parser {parser_batch:.2f}")
    for e in order:
        r = engine_runs[e]
        print(f"  {e:9s} {st.mean(r):6.1f} [{min(r):.1f}-{max(r):.1f}] n={len(r)} "
              f"setup {min(small_setup[e]):.1f}-{max(small_setup[e]):.1f}")
    for t, _ in arts:
        print(f"  qlever on {t}: {st.mean(per_target[t]):.2f} setup {st.mean(setup[(t, 'qlever')]):.2f}")


# ---------------------------------------------------------------------------
# Figure: regional and whole-file retrieval, RDF against tabular parsing
# ---------------------------------------------------------------------------
#: Regional execution paths: RDF first, then the indexed readers, then the
#: unindexed scan as the dashed context baseline (gray, as in Figure 6).
REGIONAL_PATHS = [("qlever", "QLever (RDF)", BLUE, "o", "-"),
                  ("bcftools-indexed", "bcftools + tabix", ORANGE, "s", "-"),
                  ("cyvcf2-indexed", "cyvcf2 + tabix", AQUA, "D", "-"),
                  ("cyvcf2-scan", "cyvcf2, full parse", GRAY, "^", "--")]
REGIONAL_SIZES = [1_000, 100_000, 1_000_000, 10_000_000]


def regional_window_records() -> dict[int, float]:
    """Median records per window, per window size, on the 100,000-record HG005 slice."""
    path = site.REGIONAL / "slice" / "out" / "regional.csv"
    seen, per_size = set(), defaultdict(list)
    for row in tidy(path):
        key = (row["window_size"], row["window_id"])
        if row["arm"] == "qlever" and key not in seen:
            seen.add(key)
            per_size[int(row["window_size"])].append(int(row["records_in_window"]))
    return {size: st.median(counts) for size, counts in per_size.items()}


def regional_axis(ax, ticks: bool = True) -> None:
    """Log window-size axis with the four sizes as ticks."""
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.xaxis.set_major_locator(FixedLocator(REGIONAL_SIZES))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels(["1 kb", "100 kb", "1 Mb", "10 Mb"] if ticks else [])
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:,.0f}" if v >= 1 else f"{v:g}"))


def path_legend(fig, paths, y=1.0, ncol=4, x=0.53) -> None:
    handles = [plt.Line2D([], [], color=color, linestyle=style, marker=marker, markersize=4,
                          markeredgecolor="white", label=label)
               for _arm, label, color, marker, style in paths]
    fig.legend(handles=handles, loc="upper center", ncol=ncol, bbox_to_anchor=(x, y),
               frameon=False, fontsize=6.3, handlelength=2.2, columnspacing=1.4)


def fig_regional() -> None:
    """Setup and break-even, ingested file sizes, regional queries, and every comparison as a ratio."""
    slice_ = site.regional()["slice"]
    ms = {arm: {int(size): v for size, v in sizes.items()} for arm, sizes in slice_["ms"].items()}
    records = regional_window_records()
    data = retrieval()
    per_question = [st.mean(data["oracle_q"][q]) / st.mean(data["engine_q"][q]) for q, _ in QUERIES]
    batch = data["parser_batch"] / data["ql_batch"]
    b = breakeven()
    sizes = ingest_sizes()

    fig = plt.figure(figsize=(WIDTH_IN, 5.0))
    top = GridSpec(1, 2, figure=fig, width_ratios=[1.0, 1.0], wspace=0.42,
                   left=0.1, right=0.975, top=0.875, bottom=0.6)
    low = GridSpec(1, 2, figure=fig, width_ratios=[1.0, 1.0], wspace=0.62,
                   left=0.1, right=0.975, top=0.44, bottom=0.085)

    # (a) repeated whole-file questions, setup included ------------------------
    ax = fig.add_subplot(top[0, 0])
    style_axes(ax, "y")
    n_max, n_star = 30, b["n_star"]
    top_min = n_max * b["scan"] / 60 * 1.12
    ax.axvspan(n_star, n_max, color=BLUE_LIGHT, alpha=0.18, lw=0, zorder=0)
    ax.plot([0, n_max], [0, n_max * b["scan"] / 60], color=GRAY, linestyle="--", linewidth=1.5, zorder=2)
    ax.plot([0, n_max], [b["setup"] / 60, (b["setup"] + n_max * b["query"]) / 60], color=BLUE,
            linewidth=1.5, zorder=2)
    dot(ax, n_star, n_star * b["scan"] / 60, INK, size=5, zorder=4)
    ax.annotate(f"{n_star:.0f} questions", (n_star, n_star * b["scan"] / 60), textcoords="offset points",
                xytext=(6, -10), color=INK, fontsize=6.2, ha="left")
    ax.text(0.6, b["setup"] / 60 + 0.95, f"Convert + index {b['setup'] / 60:.1f} min,\nthen {b['query']:.2f} s each",
            color=INK_2, fontsize=5.9, va="bottom", ha="left")
    ax.text(n_max - 0.5, n_max * b["scan"] / 60 * 0.62, f"Full parse\n{b['scan']:.1f} s each", color=INK_2,
            fontsize=5.9, va="top", ha="right")
    ax.text((n_star + n_max) / 2, top_min * 0.97, "RDF cheaper", color=INK_2, fontsize=5.9, ha="center", va="top")
    ax.set_xlim(0, n_max)
    ax.set_ylim(0, top_min)
    ax.set_xlabel("Separate whole-file questions")
    ax.set_ylabel("Cumulative time (min)")
    ax.set_title("(a) Repeated questions, setup included")

    # (b) what QLever ingests against the gzipped VCF ------------------------
    ax = fig.add_subplot(top[0, 1])
    style_axes(ax, "y")
    fmt = lambda v: f"{v / 1e9:.2f} GB" if v >= 1e9 else f"{v / 1e6:.1f} MB"  # noqa: E731
    for x, (label, vcf_bytes, nt_bytes) in enumerate(sizes):
        for dx, value, color in ((-0.19, vcf_bytes, GRAY), (0.19, nt_bytes, BLUE)):
            ax.bar(x + dx, value / 1e6, width=0.34, color=color, zorder=2)
            ax.text(x + dx, value / 1e6 * 1.18, fmt(value), color=INK_2, fontsize=5.7, ha="center", va="bottom")
        ax.text(x, nt_bytes / 1e6 * 5.2, f"{nt_bytes / vcf_bytes:.1f}×", color=INK, fontsize=6.6,
                ha="center", va="bottom", fontweight="bold")
    ax.set_yscale("log")
    ax.set_ylim(0.6, 3e5)
    ax.yaxis.set_major_locator(FixedLocator([1, 10, 100, 1000, 10000]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v / 1000:g} GB" if v >= 1000 else f"{v:g} MB"))
    ax.set_xticks(range(len(sizes)))
    ax.set_xticklabels([label for label, *_ in sizes], fontsize=6.2)
    ax.set_xlim(-0.6, len(sizes) - 0.4)
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("Size, gzip-compressed")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=GRAY, label="VCF"),
                       plt.Rectangle((0, 0), 1, 1, color=BLUE, label="N-Triples for QLever")],
              loc="upper left", fontsize=5.9, handlelength=1.0, borderaxespad=0.3, frameon=False)
    ax.set_title("(b) Gzipped VCF and N-Triples sizes")

    # (c) regional time by window size --------------------------------------
    ax = fig.add_subplot(low[0, 0])
    style_axes(ax, "y")
    ax.axvspan(10_000_000 / 2.2, 10_000_000 * 2.2, color=BLUE_LIGHT, alpha=0.18, lw=0, zorder=0)
    ax.text(10_000_000, 2.1, "QLever\nfastest", color=INK_2, fontsize=5.8, ha="center", va="bottom")
    for arm, _label, color, marker, style in REGIONAL_PATHS:
        ys = [ms[arm][s] for s in REGIONAL_SIZES]
        ax.plot(REGIONAL_SIZES, ys, color=color, linestyle=style, linewidth=1.4, zorder=2)
        ax.plot(REGIONAL_SIZES, ys, marker, color=color, markersize=3.6, markeredgecolor="white",
                markeredgewidth=0.6, zorder=3)
        end = ys[-1]
        ax.annotate(f"{end:,.1f}" if end < 100 else f"{end:,.0f}", (REGIONAL_SIZES[-1], end),
                    xytext=(9, 0), textcoords="offset points", color=INK_2, fontsize=5.8, va="center")
    regional_axis(ax, ticks=False)
    ax.set_xticklabels([f"{name}\n({int(records[s] + 0.5):,})" for s, name in
                        zip(REGIONAL_SIZES, ["1 kb", "100 kb", "1 Mb", "10 Mb"])], fontsize=6)
    ax.set_xlim(400, 3.2e7)
    ax.set_ylim(1.8, 2500)
    ax.yaxis.set_major_locator(FixedLocator([3, 10, 30, 100, 300, 1000]))
    ax.set_xlabel("Window size (median records per window)")
    ax.set_ylabel("Median time per query (ms)")
    ax.set_title("(c) Regional queries by window size")

    # (d) every comparison as VCF parsing time / RDF time, setup excluded ------
    ax = fig.add_subplot(low[0, 1])
    style_axes(ax, "x")
    rows = [f"{name} windows" for name in ["1 kb", "100 kb", "1 Mb", "10 Mb"]] + [
        "Whole file,\nper question", "Whole file,\none-pass batch"]
    ys = list(range(len(rows) - 1, -1, -1))
    ax.axvspan(1, 6000, color=BLUE_LIGHT, alpha=0.18, lw=0, zorder=0)
    ax.axvline(1, color=AXIS, linewidth=0.8, zorder=1)
    ax.text(0.8, len(rows) - 0.3, "VCF parsing\nfaster", color=INK_2, fontsize=5.8, ha="right", va="bottom")
    ax.text(1.3, len(rows) - 0.3, "RDF querying\nfaster", color=INK_2, fontsize=5.8, ha="left", va="bottom")
    # The two indexed readers sit just above and below their row, so equal ratios stay visible.
    offset = {"bcftools-indexed": 0.15, "cyvcf2-indexed": -0.15, "cyvcf2-scan": 0.0}
    for y, size in zip(ys, REGIONAL_SIZES):
        for arm, _label, color, marker, _style in REGIONAL_PATHS[1:]:
            ax.plot(ms[arm][size] / ms["qlever"][size], y + offset[arm], marker, color=color, markersize=4,
                    markeredgecolor="white", markeredgewidth=0.6, zorder=3)
    y = ys[4]
    ax.plot([min(per_question), max(per_question)], [y, y], color=GRAY, linewidth=1.0, zorder=2)
    for r in per_question:
        ax.plot(r, y, "^", color=GRAY, markersize=3.6, markeredgecolor="white", markeredgewidth=0.5, zorder=3)
    ax.annotate(f"{min(per_question):.1f}–{max(per_question):,.0f}×", ((min(per_question) * max(per_question)) ** 0.5, y),
                xytext=(0, 4), textcoords="offset points", color=INK_2, fontsize=5.8, ha="center", va="bottom")
    y = ys[5]
    ax.plot(batch, y, "^", color=GRAY, markersize=5.2, markeredgecolor="white", markeredgewidth=0.6, zorder=3)
    ax.annotate(f"{batch:.1f}×", (batch, y), xytext=(-6, 0), textcoords="offset points",
                color=INK_2, fontsize=5.8, ha="right", va="center")
    ax.set_xscale("log")
    ax.set_xlim(0.1, 6000)
    ax.xaxis.set_major_locator(FixedLocator([0.1, 1, 10, 100, 1000]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:g}×"))
    ax.set_yticks(ys)
    ax.set_yticklabels(rows, fontsize=6.2)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_ylim(-0.6, len(rows) + 0.75)
    ax.set_xlabel("VCF parsing time ÷ QLever time")
    ax.set_title("(d) Parsing relative to querying, no setup", loc="left", x=-0.42)

    path_legend(fig, REGIONAL_PATHS)
    fig.savefig(OUT / "fig-regional.pdf", metadata=PDF_METADATA)
    plt.close(fig)
    print("regional ms:", {a: ms[a] for a, *_ in REGIONAL_PATHS}, "records/window:", records)
    print(f"  N-Triples conversion {b['conversion']:.1f} s (runs {[round(x, 1) for x in b['conversion_runs']]}) + index "
          f"{b['index']:.1f} s = {b['setup']:.1f} s; break-even {b['n_star']:.1f} "
          f"(with HDT: {b['setup_with_hdt']:.1f} s, {b['n_star_with_hdt']:.1f}); scan {b['scan']:.2f} s, query {b['query']:.3f} s")
    print("  sizes:", [(l.replace(chr(10), ' '), v, n, round(n / v, 1)) for l, v, n in sizes])
    print(f"  whole file per question {min(per_question):.1f}-{max(per_question):.0f}x; batch {batch:.2f}x")


#: The five regional questions, as the supplement names them.
REGIONAL_QUESTIONS = [("r01_region_record_count", "Record count"),
                      ("r02_region_variant_shape_counts", "Variant shapes"),
                      ("r03_region_titv", "Ti/Tv"),
                      ("r04_region_filter_distribution", "FILTER values"),
                      ("r05_region_sample_genotype_counts", "Sample genotypes")]
#: The three Comunica engines run only on the fixture; one light-blue family, told apart by marker.
COMUNICA_PATHS = [("comunica", "Comunica, N-Triples", BLUE_LIGHT, "v", "-"),
                  ("hdt", "Comunica, HDT", BLUE_LIGHT, "<", "-"),
                  ("cottas", "Comunica, COTTAS", BLUE_LIGHT, ">", "-")]


def fig_retrieval_detail() -> None:
    """Supplementary detail: each regional question, the fixture's seven paths, and per-question break-even."""
    summary = site.load(site.REGIONAL / "slice" / "out" / "regional.json")["summary"]
    fixture = {arm: {int(s): v for s, v in sizes.items()}
               for arm, sizes in site.regional()["small"]["ms"].items()}
    b = breakeven()

    fig = plt.figure(figsize=(SUPP_WIDTH_IN, 5.0))
    top = GridSpec(1, 5, figure=fig, wspace=0.12, left=0.075, right=0.985, top=0.79, bottom=0.6)
    low_l = GridSpec(1, 1, figure=fig, left=0.075, right=0.5, top=0.4, bottom=0.08)
    low_r = GridSpec(1, 1, figure=fig, left=0.735, right=0.965, top=0.4, bottom=0.08)

    # (a) each regional question on the 100,000-record slice ----------------
    axes = [fig.add_subplot(top[0, i]) for i in range(5)]
    for i, (ax, (qid, name)) in enumerate(zip(axes, REGIONAL_QUESTIONS)):
        style_axes(ax, "y")
        for arm, _label, color, marker, style in REGIONAL_PATHS:
            ys = [1000 * summary[arm][qid][str(s)]["medianSeconds"] for s in REGIONAL_SIZES]
            ax.plot(REGIONAL_SIZES, ys, color=color, linestyle=style, linewidth=1.2, zorder=2)
            ax.plot(REGIONAL_SIZES, ys, marker, color=color, markersize=3.2, markeredgecolor="white",
                    markeredgewidth=0.5, zorder=3)
        regional_axis(ax)
        ax.set_xlim(400, 3.2e7)
        ax.set_ylim(1.8, 2500)
        ax.yaxis.set_major_locator(FixedLocator([3, 10, 30, 100, 300, 1000]))
        ax.set_xticklabels(["1k", "100k", "1M", "10M"], fontsize=5.8)
        if i:
            ax.set_yticklabels([])
        else:
            ax.set_ylabel("Median time per query (ms)")
        ax.set_title(name, fontsize=6.6, loc="center")
    fig.text(0.075, 0.855, "(a) Each regional question on 100,000 HG005 records (17.1M triples)",
             fontsize=7.5, ha="left", va="bottom")
    fig.text(0.53, 0.555, "Window size (bp)", fontsize=6.6, ha="center", va="top", color=INK)

    # (b) the 10,000-line fixture, all seven paths ---------------------------
    ax = fig.add_subplot(low_l[0, 0])
    style_axes(ax, "y")
    for arm, _label, color, marker, style in REGIONAL_PATHS + COMUNICA_PATHS:
        ys = [fixture[arm][s] for s in REGIONAL_SIZES]
        ax.plot(REGIONAL_SIZES, ys, color=color, linestyle=style, linewidth=1.2, zorder=2)
        ax.plot(REGIONAL_SIZES, ys, marker, color=color, markersize=3.4, markeredgecolor="white",
                markeredgewidth=0.5, zorder=3)
    regional_axis(ax)
    ax.set_xlim(400, 3.2e7)
    ax.set_ylim(0.3, 3000)
    ax.yaxis.set_major_locator(FixedLocator([1, 10, 100, 1000]))
    ax.text(10_000_000 * 1.25, fixture["comunica"][10_000_000], "Comunica\nengines", color=INK_2,
            fontsize=5.8, va="center", ha="left")
    ax.set_xlabel("Window size")
    ax.set_ylabel("Median time per query (ms)")
    ax.set_title("(b) All paths on the 10,000-line fixture (0.96M triples)")

    # (c) break-even per repeated question ----------------------------------
    ax = fig.add_subplot(low_r[0, 0])
    style_axes(ax, "x")
    names = dict(QUERIES)
    qids = [q for q, _ in QUERIES]
    for y, q in zip(range(len(qids) - 1, -1, -1), qids):
        n = b["per_question"][q]
        ax.barh(y, n, height=0.62, color=BLUE, zorder=2)
        ax.text(0.5, y, f"{n:.0f}", va="center", ha="left", color="white", fontsize=5.8, zorder=4)
    ax.axvline(b["n_star"], color=INK, linewidth=0.8, linestyle=(0, (2, 2)), zorder=3)
    ax.text(b["n_star"] + 0.4, len(qids) - 0.35, f"all: {b['n_star']:.0f}", color=INK_2, fontsize=5.8,
            va="bottom")
    ax.set_yticks(range(len(qids)))
    ax.set_yticklabels([names[q] for q in reversed(qids)], fontsize=6.0)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 20)
    ax.set_xlabel("Questions to break even")
    ax.set_title("(c) Break-even per repeated question", loc="left", x=-0.62)

    path_legend(fig, REGIONAL_PATHS + COMUNICA_PATHS, y=0.995, ncol=4)
    fig.savefig(OUT / "fig-retrieval-detail.pdf", metadata=PDF_METADATA)
    plt.close(fig)
    print("retrieval detail: per-question break-even",
          {q[:3]: round(n) for q, n in b["per_question"].items()})


# ---------------------------------------------------------------------------
# Figure: validation evidence, expected against observed
# ---------------------------------------------------------------------------
def fig_validation() -> None:
    """What each validation layer should report on its inputs, and what it did.

    Valid inputs should agree everywhere; injected faults should all be found.
    Each bar is the expected outcome, filled to the observed one.
    """
    v = site.validation_counts()
    scores = site.mutation_profiles()["scores"]
    real = site.real_genome()
    whole = [r for r in site.scale()["rows"]
             if r["scale"] == "whole" and r["engine"] == "qlever" and r["artifact"] == "nt.gz"]
    whole_triples = site.load(site.RESULTS / "vcf-bench-3" / "scale-store-manifests"
                              / "whole.manifest.json")["triples"]
    decoded = sum(n for k, n in v["decode"].items() if k.endswith(":pass"))
    decode_total = sum(v["decode"].values())
    # The consumer WGS validation run as validated by v3.3.1; the v3.1.0 diagnosis is in the supplement.
    real_equal = sum(q["status"] == "PASS" for q in real["rerun"]["queries"])
    valid = [
        ("Base campaign: query comparisons", f"{v['validations'] - 2} validation runs, up to 17.1M triples",
         v["comparisons"]["PASS"],
         sum(n for status, n in v["comparisons"].items() if not status.startswith("NOT_APPLICABLE"))),
        ("HDT and COTTAS decoding", "decoded triple count of each artifact", decoded, decode_total),
        ("Complete HG005 VCF retrieval", f"3.86M records, {millions(whole_triples)} triples",
         sum(r["status"] == "PASS" for r in whole), len(whole)),
        ("Consumer WGS VCF validation", f"NG131FQA1I, 250k records, {millions(real['triples'])} triples",
         real_equal, len(real["rerun"]["queries"])),
    ]
    faults = [
        ("Source-comparison queries", scores["queries"]),
        ("Queries and default SHACL shapes", scores["core"]),
        ("Queries and all SHACL profiles", scores["full"]),
    ]

    fig = plt.figure(figsize=(WIDTH_IN, 3.05))
    gs = GridSpec(2, 1, figure=fig, height_ratios=[len(valid), len(faults)], hspace=0.75,
                  left=0.33, right=0.86, top=0.91, bottom=0.12)

    def track(ax, rows, colour_hit, label_miss):
        style_axes(ax, "x")
        n = len(rows)
        for y, (name, note, hit, total) in zip(range(n - 1, -1, -1), rows):
            ax.barh(y, 1, height=0.56, color=GRID, zorder=1)
            ax.barh(y, hit / total, height=0.56, color=colour_hit, zorder=2)
            miss = total - hit
            # Count on the right, with what is short of it beneath, as name and note are on the left.
            ax.text(1.02, y + (0.13 if miss else 0), f"{hit:,} / {total:,}", transform=ax.get_yaxis_transform(),
                    color=INK, fontsize=6.6, ha="left", va="center")
            if miss:
                ax.text(1.02, y - 0.22, label_miss.format(miss), transform=ax.get_yaxis_transform(),
                        color=MUTED, fontsize=5.8, ha="left", va="center")
            ax.text(-0.02, y + 0.13, name, transform=ax.get_yaxis_transform(), color=INK,
                    fontsize=6.6, ha="right", va="center")
            if note:
                ax.text(-0.02, y - 0.22, note, transform=ax.get_yaxis_transform(),
                        color=MUTED, fontsize=5.8, ha="right", va="center")
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.6, n - 0.4)
        ax.xaxis.set_major_locator(FixedLocator([0, 0.25, 0.5, 0.75, 1]))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _p: f"{x:.0%}"))

    ax = fig.add_subplot(gs[0])
    track(ax, valid, BLUE, "{} mismatches")
    ax.set_title("(a) Agreement with the source VCF on valid inputs", x=-0.47)
    ax.set_xlabel("Results equal to the source-derived result")

    ax = fig.add_subplot(gs[1])
    track(ax, [(name, "", s["detected"], s["total"]) for name, s in faults], ORANGE, "{} undetected")
    ax.set_title(f"(b) Detection of {faults[0][1]['total']} injected faults", x=-0.47)
    ax.set_xlabel("Injected faults detected")

    fig.savefig(OUT / "fig-validation.pdf", metadata=PDF_METADATA)
    plt.close(fig)
    print("validation:", [(r[0], r[2], r[3]) for r in valid],
          [(n, s["detected"], s["total"]) for n, s in faults])


# ---------------------------------------------------------------------------
# Figure: use-case matches per requester, both workflows
# ---------------------------------------------------------------------------
#: Requesters in display order; arm 4 adds care by the participant's physician.
REQUESTERS = [("unrestricted", "All (no policy)"), ("own_physician", "Participant's physician"),
              ("clinical", "Clinical care (CC)"), ("cardio", "Cardiovascular research (DS)"),
              ("biobank", "General research (GRU)")]
#: Arm 4 (layered rules on one complete VCF), outside the site's arms: its v3.3.1 rerun on vcf-bench-2.
ARM4 = site.V331["vcf-bench-2"] / "17_use_case_acmg__layered"


def arm_genome_triples(arm: Path) -> int:
    """Triples converted from the arm's VCFs, before links (ClinVar and the panel excluded)."""
    total = 0
    for cell in site.reported_cells(arm, "convert"):
        if cell.name.split("__", 1)[1] in ("clinvar", "panel"):
            continue
        counts = [int(m.group(1))
                  for path in glob.glob(str(cell / "out" / "**" / "*.json"), recursive=True)
                  for m in re.finditer(r'"total_triples":\s*"?(\d+)', Path(path).read_text())]
        total += max(counts)
    return total


def carriers(comparison: dict) -> dict:
    """The per-requester match comparisons of a comparison.json, as the site reads them."""
    return {r: c for r, c in comparison.items() if isinstance(c, dict) and "agree" in c}


def fig_usecase_matches() -> None:
    """Matches each requester may see, per arm; the RDF and conventional workflows side by side.

    One row of panels on a shared requester axis, so each requester is named once.
    """
    arms = site.usecase()["arms"]
    panels = [
        ("Arm 1", "five gene-span slices", arms["arm1"]["carriers"], arm_genome_triples(site.ARMS["arm1"])),
        ("Arm 2", "cohort of 104", arms["arm2"]["carriers"], arm_genome_triples(site.ARMS["arm2"])),
        ("Arm 2", "panel AF < 0.01", arms["arm2"]["rare"], None),
        ("Arm 3: HG005", "complete VCF", arms["arm3"]["carriers"], arm_genome_triples(site.ARMS["arm3"])),
        ("Arm 4: NB72462M", "complete VCF", carriers(site.load(ARM4 / "comparison.json")), arm_genome_triples(ARM4)),
    ]
    short = {"unrestricted": "All", "own_physician": "OP", "clinical": "CC",
             "cardio": "DS", "biobank": "GRU"}
    ys = {key: len(REQUESTERS) - 1 - i for i, (key, _) in enumerate(REQUESTERS)}
    fig, axes = plt.subplots(1, len(panels), figsize=(WIDTH_IN, 2.0), sharey=True)
    fig.subplots_adjust(left=0.07, right=0.96, top=0.66, bottom=0.12, wspace=0.34)
    for i, (ax, (arm, what, counts, triples)) in enumerate(zip(axes, panels)):
        style_axes(ax, "x")
        top = max(counts[key]["rdf"] for key, _ in REQUESTERS if key in counts)
        for key, _label in REQUESTERS:
            y = ys[key]
            if key not in counts:  # the participant's physician requests only in Arm 4
                ax.text(top * 0.04, y, "\u2013", color=MUTED, fontsize=6, va="center")
                continue
            c = counts[key]
            ax.barh(y, c["rdf"], height=0.58, color=GRAY if key == "unrestricted" else BLUE, zorder=2)
            dot(ax, c["baseline"], y, ORANGE, size=4.2, zorder=4)
            # Offset in points, not data, so the label clears the dot in a narrow panel.
            ax.annotate(f"{c['rdf']:,}", (c["rdf"], y), xytext=(4.5, 0), textcoords="offset points",
                        color=INK_2, fontsize=5.8, va="center")
        ax.set_xlim(0, top * 1.7)
        ax.set_ylim(-0.6, len(REQUESTERS) - 0.4)
        ax.set_yticks(sorted(ys.values()))
        ax.set_yticklabels([short[key] for key, _ in reversed(REQUESTERS)], fontsize=6.3)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", labelsize=5.8)
        ax.spines["left"].set_visible(False)
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(2, integer=True))
        ax.xaxis.set_major_formatter(FuncFormatter(
            lambda x, _p, big=top >= 10_000: f"{x / 1000:.0f}k" if big and x else f"{x:,.0f}"))
        size = f"\n{triples_label(triples)} triples" if triples else "\n"
        ax.set_title(f"({'abcde'[i]}) {arm}\n{what}{size}", fontsize=6.0, linespacing=1.15, loc="center")
    handles = [plt.Rectangle((0, 0), 1, 1, color=GRAY, label="RDF workflow, no policy"),
               plt.Rectangle((0, 0), 1, 1, color=BLUE, label="RDF workflow, release view"),
               plt.Line2D([], [], marker="o", linestyle="", color=ORANGE, markeredgecolor="white",
                          markersize=5, label="Conventional workflow")]
    fig.legend(handles=handles, loc="upper center", ncol=3, bbox_to_anchor=(0.55, 1.0),
               frameon=False, fontsize=6.5, handletextpad=0.5, columnspacing=1.6)
    fig.savefig(OUT / "fig-usecase-matches.pdf", metadata=PDF_METADATA)
    plt.close(fig)
    for arm, what, counts, triples in panels:
        print(f"usecase {arm} {what}: {triples}", {k: (counts[k]['rdf'], counts[k]['baseline']) for k, _ in REQUESTERS if k in counts})


def millions(n: float) -> str:
    return f"{n / 1e6:.1f}M"


# ---------------------------------------------------------------------------
# Figure: stage costs of the linked workflow
# ---------------------------------------------------------------------------
#: The four arms in order of graph size.
COST_ARMS = [
    ("Arm 1: five gene-span slices", site.ARMS["arm1"]),
    ("Arm 2: cohort of 104", site.ARMS["arm2"]),
    ("Arm 3: complete HG005 VCF", site.ARMS["arm3"]),
    ("Arm 4: complete NB72462M VCF", ARM4),
]
STAGES = [("convert", "Convert"), ("link", "Link"),
          ("view", "Write view"), ("check", "Check view"), ("index", "Index view"), ("query", "Query")]
#: The requester followed to the first answer: present in every arm, and its check is recorded in each.
FIRST_ANSWER = "clinical"


def triples_label(n: float) -> str:
    return f"{n / 1e9:.2f}B" if n >= 1e9 else millions(n)


def stage_costs(arm: Path) -> dict:
    """Seconds per stage: one value for the once-per-arm stages, one per requester otherwise.

    The view is the govern cell. The harness checks a view between that cell and
    the next requester's, so a check is the gap between consecutive govern cells;
    the last requester's gap also holds other work and is not used. Index and
    query are the query cell's setup and median replicate.
    """
    def bench(cell):
        return site.load(cell / "bench.json")

    def cells(prefix):
        return [c for c in site.reported_cells(arm, prefix) if (c / "bench.json").exists()]

    govern = sorted(cells("govern"), key=lambda c: bench(c)["started_epoch"])
    out = {"convert": [site.wall(cells("convert"))], "link": [site.wall(cells("link"))],
           "view": [], "check": [], "index": [], "query": [], "empty": set()}
    for i, cell in enumerate(govern):
        requester = cell.name.split("__", 1)[1]
        out["view"].append((requester, bench(cell)["wrapper_wall_seconds"]))
        if i + 1 < len(govern):
            out["check"].append((requester, bench(govern[i + 1])["started_epoch"] - bench(cell)["ended_epoch"]))
        summary = site.load(cell / "out" / "summary.json")
        out.setdefault("released", {})[requester] = (summary["records_released"], summary["triples_released"])
        if summary["records_released"] == 0:
            out["empty"].add(requester)
    for timing in sorted(arm.glob("query/*/timing.json")):
        requester = timing.parent.name
        data = site.load(timing)
        replicates = data["replicates"]
        replicates = replicates["carriers"] if isinstance(replicates, dict) else replicates
        if requester == "unrestricted":
            out["unrestricted"] = (data["setup_seconds"], st.median(replicates))
            continue
        out["index"].append((requester, data["setup_seconds"]))
        out["query"].append((requester, st.median(replicates)))
    out["triples"] = site.load(arm / "query" / "unrestricted" / "timing.json")["triples"]
    return out


def fig_usecase_costs() -> None:
    """Time before the first answer, and each query, against the size of the arm's graph."""
    arms = [(name, stage_costs(path)) for name, path in COST_ARMS]
    sizes, setup, query = [], [], []
    for _name, costs in arms:
        pick = lambda key: dict(costs[key])[FIRST_ANSWER]  # noqa: E731
        sizes.append(costs["triples"])
        setup.append(costs["convert"][0] + costs["link"][0] + pick("view") + pick("check") + pick("index"))
        query.append(pick("query"))
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.35))
    fig.subplots_adjust(left=0.1, right=0.97, top=0.9, bottom=0.2)
    style_axes(ax, "y")
    ax.set_yscale("log")
    xs = list(range(len(arms)))  # arms in order of graph size, evenly spaced
    ax.plot(xs, setup, color=BLUE, linewidth=1.6, zorder=2, label="Before the first answer")
    ax.plot(xs, query, color=ORANGE, linewidth=1.6, zorder=2, label="Each query")
    for x, y in zip(xs, setup):
        dot(ax, x, y, BLUE, size=5.5)
        text = f"{y / 3600:.1f} h" if y >= 3600 else f"{y / 60:.0f} min"
        ax.annotate(text, (x, y), textcoords="offset points", xytext=(0, 7), ha="center",
                    color=INK_2, fontsize=6.5)
    for x, y in zip(xs, query):
        dot(ax, x, y, ORANGE, size=5.5)
    ax.annotate(f"{min(query) / 60:.1f}--{max(query) / 60:.1f} min in every arm".replace("--", "\u2013"),
                (1.5, st.mean(query[1:3])), textcoords="offset points", xytext=(0, -12), ha="center",
                color=INK_2, fontsize=6.5)
    ax.set_xticks(xs)
    labels = []
    for name, costs in arms:
        what = name.split(": ")[1]
        labels.append(f"{what[0].upper()}{what[1:]}\n{triples_label(costs['triples'])} triples")
    ax.set_xticklabels(labels)
    ax.tick_params(axis="x", length=0)
    ax.set_xlim(-0.45, len(arms) - 0.55)
    names = {60: "1 min", 600: "10 min", 3600: "1 h", 36000: "10 h"}
    ax.yaxis.set_major_locator(FixedLocator(list(names)))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: names.get(v, "")))
    ax.set_ylim(60, 15 * 3600)
    ax.set_ylabel("Time (log scale)")
    ax.legend(loc="upper left", handlelength=1.6, borderaxespad=0.2)
    fig.savefig(OUT / "fig-usecase-costs.pdf", metadata=PDF_METADATA)
    plt.close(fig)
    for (name, _c), x, a, b in zip(arms, sizes, setup, query):
        print(f"costs {name}: {x} triples, first answer {a / 60:.1f} min, query {b:.1f} s")

# ---------------------------------------------------------------------------
# Figure: the shared-input converter comparison (main text)
# ---------------------------------------------------------------------------
#: Experiment 18's reported run. EXP18_RESULTS reads it from elsewhere, e.g. a checkout of the
#: branch that archives it, before that archive is merged here.
CONVERTERS = Path(os.environ.get("EXP18_RESULTS", site.RESULTS / "vcf-bench-1" / "18_converter_comparison"))
CONVERTER_ROWS = (("vcf-rdfizer", "VCF-RDFizer"), ("jvarkit", "JVarkit"), ("togovar", "TogoVar"),
                  ("sparqling-genomics", "SPARQLing Genomics"), ("biointerchange", "BioInterchange"))
CONVERTER_INPUTS = (("HG005_GRCh38_r100000", "HG005", "100k records, 1 sample"),
                    ("1000G_10000r_s16", "1000 Genomes", "10k records, 16 samples"))
#: Outcome colours used by no other figure, so this grid's blue or orange is never read as another
#: figure's series: the palette's violet slot, and a raspberry stepped clear of the orange.
#: Validated with the dataviz palette validator against every colour the other figures use
#: (blue, orange, aqua): CVD Delta E >= 9.2 and normal-vision Delta E >= 15.8 for every pair that
#: involves them; white marks reach 8.6:1 on violet and 6.0:1 on raspberry.
VIOLET = "#4a3aa7"
RASPBERRY = "#b0306f"
#: Outcome -> (fill, mark, mark colour, label). The mark carries the outcome too, so it is never
#: colour alone.
CONVERTER_OUTCOMES = {
    "PASS": (VIOLET, "\u2713", "white", "Answers as the oracle does"),
    "MISMATCH": (RASPBERRY, "\u00d7", "white", "Answers differently"),
    "NOT_REPRESENTED": (GRID, "\u2013", INK_2, "Not in the graph"),
}


def converter_outcomes() -> dict[tuple[str, str, str], str]:
    with (CONVERTERS / "summary" / "outcomes.csv").open(encoding="utf-8") as handle:
        return {(row["tool"], row["input"], row["question"]): row["status"] for row in csv.DictReader(handle)}


def fig_converters() -> None:
    """Which of the content questions Q1-Q8 each converter's graph answers as the oracle does.

    One grid per input: converters down, questions across, one cell per answer.
    """
    outcomes = converter_outcomes()
    questions = sorted({question for (_tool, _input, question) in outcomes})
    unknown = {status for status in outcomes.values()} - set(CONVERTER_OUTCOMES)
    if unknown:
        raise SystemExit(f"fig-converters: no style for {sorted(unknown)}")
    rows = len(CONVERTER_ROWS)
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH_IN, 1.85), sharey=True)
    fig.subplots_adjust(left=0.205, right=0.995, top=0.69, bottom=0.03, wspace=0.07)
    for i, (ax, (key, name, what)) in enumerate(zip(axes, CONVERTER_INPUTS)):
        for row, (tool, _label) in enumerate(CONVERTER_ROWS):
            y = rows - 1 - row
            for x, question in enumerate(questions):
                fill, mark, ink, _ = CONVERTER_OUTCOMES[outcomes[(tool, key, question)]]
                ax.add_patch(plt.Rectangle((x - 0.45, y - 0.41), 0.9, 0.82, facecolor=fill, linewidth=0))
                # DejaVu Sans, bundled with matplotlib, has the check mark that Helvetica lacks.
                ax.text(x, y, mark, ha="center", va="center", color=ink, fontsize=6.6, fontweight="bold",
                        fontfamily="DejaVu Sans")
        ax.set_xlim(-0.55, len(questions) - 0.45)
        ax.set_ylim(-0.55, rows - 0.45)
        ax.set_xticks(range(len(questions)))
        ax.set_xticklabels([f"Q{int(question[1:3])}" for question in questions], fontsize=6.2)
        ax.xaxis.tick_top()
        ax.set_yticks(range(rows))
        ax.set_yticklabels([label for _tool, label in reversed(CONVERTER_ROWS)], fontsize=6.5)
        ax.tick_params(length=0, pad=2)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(f"({'ab'[i]}) {name}: {what}", fontsize=6.6, pad=13)
    # The keys are the fills; every cell also carries its mark, which the caption names.
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=fill, linewidth=0, label=label)
               for fill, _mark, _ink, label in CONVERTER_OUTCOMES.values()]
    fig.legend(handles=handles, loc="upper center", ncol=3, bbox_to_anchor=(0.6, 1.0), frameon=False,
               fontsize=6.5, handlelength=1.0, handletextpad=0.5, columnspacing=1.8)
    fig.savefig(OUT / "fig-converters.pdf", metadata=PDF_METADATA)
    plt.close(fig)
    for tool, label in CONVERTER_ROWS:
        for key, name, _what in CONVERTER_INPUTS:
            passed = sum(outcomes[(tool, key, q)] == "PASS" for q in questions)
            print(f"converters {label} / {name}: {passed} of {len(questions)} as the oracle")


if __name__ == "__main__":
    fig_scaling()
    fig_samples()
    fig_representations()
    fig_retrieval()
    fig_regional()
    fig_validation()
    fig_usecase_matches()
    fig_usecase_costs()
    fig_retrieval_detail()
    fig_converters()
    for name in ("fig-converters", "fig-scaling", "fig-samples", "fig-representations", "fig-retrieval", "fig-regional",
                 "fig-validation", "fig-usecase-matches", "fig-usecase-costs", "fig-retrieval-detail"):
        print("wrote", OUT / f"{name}.pdf")
