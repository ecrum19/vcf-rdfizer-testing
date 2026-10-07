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

import glob
import re
import statistics as st
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402

from figure_data import (  # noqa: E402 - stdlib-only data layer shared with the site
    QUERIES, corpus_rows, records_ladder, retrieval, sample_ladder, storage_modes,
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
# Figure: scaling with records, samples, and storage mode
# ---------------------------------------------------------------------------
def fig_scaling() -> None:
    ladder = records_ladder()
    rungs, med = ladder["rungs"], ladder["median"]
    idx = {k: [v / med[k][0] for v in med[k]] for k in med}
    storage = storage_modes()

    fig = plt.figure(figsize=(WIDTH_IN, 2.75))
    left = GridSpec(1, 1, figure=fig, left=0.105, right=0.5, top=0.9, bottom=0.2)
    right = GridSpec(1, 1, figure=fig, left=0.69, right=0.985, top=0.78, bottom=0.2)

    # (a) records ------------------------------------------------------------
    ax = fig.add_subplot(left[0, 0])
    style_axes(ax, "both")
    for key in ("triples", "wall", "disk"):
        ax.plot(rungs, idx[key], color=GRAY, linewidth=1.4, solid_capstyle="round", zorder=2)
        for x, y in zip(rungs, idx[key]):
            dot(ax, x, y, GRAY, size=4.5)
    ax.plot(rungs, idx["rss"], color=BLUE, linewidth=1.6, solid_capstyle="round", zorder=3)
    for x, y in zip(rungs, idx["rss"]):
        dot(ax, x, y, BLUE)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(7e3, 6.5e6)
    ax.set_ylim(0.6, 1500)
    ax.xaxis.set_major_locator(FixedLocator(rungs))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels(["10k", "100k", "1M", "3.86M\n(whole)"])
    ax.yaxis.set_major_locator(FixedLocator([1, 10, 100, 1000]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}×"))
    ax.set_xlabel("Records (HG005_GRCh38)")
    ax.set_ylabel("Growth relative to 10k records")
    lo = min(idx[k][-1] for k in ("triples", "wall", "disk"))
    hi = max(idx[k][-1] for k in ("triples", "wall", "disk"))
    ax.annotate(f"Triples, wall time and\npeak disk: ×{lo:.0f}–{hi:.0f}",
                xy=(rungs[2], idx["disk"][2]), xytext=(1.3e4, 180),
                color=INK_2, fontsize=6.5, ha="left", va="center",
                arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.5))
    rss_gb = [v * 1024 / 1e9 for v in med["rss"]]  # max RSS is reported in kB
    ax.text(rungs[-1], idx["rss"][-1] * 2.1,
            f"Peak memory: {min(rss_gb):.1f}–{max(rss_gb):.1f} GB\n(×{max(idx['rss']):.1f} at most)",
            color=INK_2, fontsize=6.5, ha="right", va="bottom")
    ax.set_title("(a) Memory stays flat as records grow")

    # (b) storage mode --------------------------------------------------------
    ax = fig.add_subplot(right[0, 0])
    style_axes(ax, "x")
    rows = [("larger", "test-larger\n269M triples"), ("slice", "HG005 slice\n17.1M triples")]
    for y, (key, label) in enumerate(rows):
        plain = st.mean(v[0] for v in storage[key]["plain"]) / 1e9
        spo = st.mean(v[0] for v in storage[key]["space-optimized"]) / 1e9
        t_plain = st.mean(v[1] for v in storage[key]["plain"])
        t_spo = st.mean(v[1] for v in storage[key]["space-optimized"])
        ax.plot([spo, plain], [y, y], color=GRAY, linewidth=1.2, zorder=1)
        dot(ax, plain, y, GRAY)
        dot(ax, spo, y, BLUE)
        ax.text((plain * spo) ** 0.5, y + 0.2,
                f"{plain / spo:.1f}× less disk, {100 * (t_spo / t_plain - 1):+.1f}% time",
                color=INK_2, fontsize=6.3, va="bottom", ha="center")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([label for _, label in rows])
    ax.set_ylim(-0.5, len(rows) - 0.2)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xscale("log")
    ax.set_xlim(0.15, 160)
    ax.xaxis.set_major_locator(FixedLocator([0.3, 1, 3, 10, 30, 100]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xlabel("Peak disk workspace (GB)")
    ax.plot([], [], "o", color=BLUE, markersize=5, label="Space-optimized")
    ax.plot([], [], "o", color=GRAY, markersize=5, label="Plain")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=2, handletextpad=0.3,
              columnspacing=1.0, borderaxespad=0.1)
    ax.set_title("(b) Space-optimized storage cuts peak\n     disk for a few percent more time",
                 x=-0.62, pad=20)

    fig.savefig(OUT / "fig-scaling.pdf", metadata=PDF_METADATA)
    plt.close(fig)


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
    bottom = GridSpec(1, 1, figure=fig, left=0.2, right=0.93, top=0.235, bottom=0.09)

    def sample_axis(ax):
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(0.6, 5000)
        ax.xaxis.set_major_locator(FixedLocator(s_x))
        ax.xaxis.set_minor_locator(NullLocator())
        # 1,024 and 2,504 sit too close on a log axis for two labels.
        ax.set_xticklabels(["" if n == 1024 else f"{n:,}" for n in s_x])
        ax.set_xlabel("Sample columns (10,000 records held fixed)")

    # (a) triples --------------------------------------------------------------
    ax = fig.add_subplot(top[0, 0])
    style_axes(ax, "both")
    for series, color, label in ((e, ORANGE, "Expanded"), (c, BLUE, "Condensed")):
        ys = [v / 1e6 for v in series["triples"]]
        ax.plot(s_x, ys, color=color, linewidth=1.6, solid_capstyle="round", label=label)
        for x, y in zip(s_x, ys):
            dot(ax, x, y, color)
    sample_axis(ax)
    ax.set_ylim(0.6, 2500)
    ax.yaxis.set_major_locator(FixedLocator([1, 10, 100, 1000]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}M"))
    ax.set_ylabel("Triples")
    ax.legend(loc="upper left", handlelength=1.6, borderaxespad=0.2)
    g_c = c["triples"][-1] / c["triples"][0]
    g_e = e["triples"][-1] / e["triples"][0]
    ax.text(s_x[-1], e["triples"][-1] / 1e6 * 1.35, f"×{g_e:.0f}", color=INK_2,
            fontsize=6.5, ha="center", va="bottom")
    ax.text(s_x[-1], c["triples"][-1] / 1e6 * 0.7, f"+{100 * (g_c - 1):.1f}%", color=INK_2,
            fontsize=6.5, ha="center", va="top")
    ax.set_title("(a) Triples: condensed barely grows")

    # (b) stored bytes -----------------------------------------------------------
    ax = fig.add_subplot(top[0, 1])
    style_axes(ax, "both")
    has_cottas = "cottas" in c and "cottas" in e
    vcf = [v / 1e6 for v in c["vcf"]]
    ax.plot(s_x, vcf, color=GRAY, linewidth=1.2, solid_capstyle="round", zorder=1)
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
    ax.set_ylim(0.8, 12000)
    ax.yaxis.set_major_locator(FixedLocator([1, 10, 100, 1000, 10000]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{v / 1000:g} GB" if v >= 1000 else f"{v:g} MB"))
    ax.set_ylabel("Size on disk")
    handles = [
        plt.Line2D([], [], color=INK_2, linewidth=1.6, marker="o", markersize=4.5,
                   label="HDT"),
        plt.Line2D([], [], color=INK_2, linewidth=0.9, marker="o", markersize=4,
                   markerfacecolor="white", markeredgecolor=INK_2, label="gzip N-Triples"),
        plt.Line2D([], [], color=GRAY, linewidth=1.2, label="Input VCF (uncompressed)"),
    ]
    if has_cottas:
        handles.insert(1, plt.Line2D([], [], color=INK_2, linewidth=1.2, marker="s",
                                     markersize=4, label="COTTAS"))
    ax.legend(handles=handles, loc="upper left", handlelength=1.8, borderaxespad=0.2)
    ax.text(64, e["hdt"][3] / 1e6 * 2.2, "Expanded", color=INK_2, fontsize=6.5, ha="right",
            va="bottom")
    ax.text(4, c["nt"][1] / 1e6 * 0.62, "Condensed", color=INK_2, fontsize=6.5, ha="center",
            va="top")
    ax.set_title("(b) Bytes: condensed still grows")

    # (c) the gap, measured three ways ----------------------------------------
    ax = fig.add_subplot(bottom[0, 0])
    style_axes(ax, "x")
    gaps = [("Triples", e["triples"][-1] / c["triples"][-1]),
            ("gzip N-Triples", e["nt"][-1] / c["nt"][-1]),
            ("HDT", e["hdt"][-1] / c["hdt"][-1])]
    if "cottas" in c and "cottas" in e:
        gaps.append(("COTTAS", e["cottas"][-1] / c["cottas"][-1]))
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
    ax.set_xlabel(f"Expanded ÷ condensed at {s_x[-1]:,} samples")
    ax.set_title("(c) Counting triples overstates the size gap")

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
                  left=0.19, right=0.9, top=0.93, bottom=0.085)

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
    ax.text((ql_batch * (ql_batch + ql_setup)) ** 0.5, 0.4, f"+ {ql_setup:.1f} s setup",
            color=INK_2, fontsize=6, ha="center", va="bottom")
    ax.text(1.015, 0, f"{parser_batch / ql_batch:.1f}×", transform=ax.get_yaxis_transform(),
            color=INK_2, fontsize=6.5, ha="left", va="center")
    ax.axhline(1, color=AXIS, linewidth=0.6)
    ax.set_yticks([0] + ys)
    ax.set_yticklabels(["All 13, one batch"] + [label for _, label in QUERIES])
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_ylim(-0.7, n + 2.6)
    ax.set_xscale("log")
    ax.set_xlim(0.003, 60)
    ax.xaxis.set_major_locator(FixedLocator([0.01, 0.1, 1, 10]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(seconds_label))
    ax.set_xlabel("Seconds (17.1M-triple HG005 graph, mean of three replicates)")
    ax.text(1.015, n + 1, "Speed-up", transform=ax.get_yaxis_transform(), color=INK,
            fontsize=6.5, fontweight="bold", ha="left", va="bottom")
    ax.texts[-1].set_position((1.015, n + 1.6))
    handles = [plt.Line2D([], [], marker="o", linestyle="", color=BLUE, markersize=5,
                          label="SPARQL (QLever)"),
               plt.Line2D([], [], marker="o", linestyle="", color=GRAY, markersize=5,
                          label="VCF scan (cyvcf2)")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.005, 1.0), ncol=2,
              handletextpad=0.3, columnspacing=1.2, borderaxespad=0.2)
    ax.set_title("(a) Per question, SPARQL beats a VCF scan; for the whole batch, one scan wins")

    # (b) engines --------------------------------------------------------------
    order = ["qlever", "comunica", "cottas", "hdt"]
    names = {"qlever": "QLever", "comunica": "Comunica", "cottas": "COTTAS", "hdt": "HDT"}
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
    ax.set_xlabel("Q1–Q13 total (s), 0.96M triples")
    ax.set_title("(b) The engine sets the cost")

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
    ax.set_xlabel("QLever, Q1–Q13 total (s), 17.1M triples")
    ax.set_title("(c) The artifact does not")

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
    real_equal = sum(q["status"] == "PASS" for q in real["queries"])
    valid = [
        ("Base campaign, paired comparisons", "fixtures and slices up to 17.1M triples",
         v["comparisons"]["PASS"],
         sum(n for status, n in v["comparisons"].items() if not status.startswith("NOT_APPLICABLE"))),
        ("Native HDT/COTTAS decoding", "triple count of every artifact", decoded, decode_total),
        ("Whole-genome retrieval", f"HG005, {millions(whole_triples)} triples",
         sum(r["status"] == "PASS" for r in whole), len(whole)),
        ("Consumer-genome follow-up", f"NG131FQA1I, {millions(real['triples'])} triples",
         real_equal, len(real["queries"])),
    ]
    faults = [
        ("Queries only", scores["queries"]),
        ("Queries + default shapes", scores["core"]),
        ("Queries + all shape profiles", scores["full"]),
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
            ax.text(1.02, y, f"{hit:,} / {total:,}", transform=ax.get_yaxis_transform(),
                    color=INK, fontsize=6.6, ha="left", va="center")
            if miss:
                ax.text(hit / total + 0.01, y, label_miss.format(miss), color=INK_2,
                        fontsize=6.2, ha="left", va="center", zorder=3)
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
    track(ax, valid, BLUE, "{} differ")
    ax.set_title("(a) Valid inputs: every answer should equal the VCF's", x=-0.47)
    ax.set_xlabel("Equal to the source, share of expected")

    ax = fig.add_subplot(gs[1])
    track(ax, [(name, "", s["detected"], s["total"]) for name, s in faults], ORANGE, "{} missed")
    ax.set_title(f"(b) Injected faults: all {faults[0][1]['total']} should be detected", x=-0.47)
    ax.set_xlabel("Detected, share of injected")

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
#: Arm 4 (layered rules on one complete genome) ran on vcf-bench-3, outside the site's arms.
ARM4 = site.RESULTS / "vcf-bench-3" / "use-case" / "17_use_case_acmg__layered"


def arm_genome_triples(arm: Path) -> int:
    """Triples converted from the arm's genomes, before links (ClinVar and the panel excluded)."""
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
    """Matches each requester may see, per arm; the RDF and conventional workflows side by side."""
    arms = site.usecase()["arms"]
    panels = [
        ("Arm 1: five genome slices", arms["arm1"]["carriers"], arm_genome_triples(site.ARMS["arm1"])),
        ("Arm 2: cohort of 104", arms["arm2"]["carriers"], arm_genome_triples(site.ARMS["arm2"])),
        ("Arm 2: cohort, panel AF < 0.01", arms["arm2"]["rare"], None),
        ("Arm 3: HG005 genome", arms["arm3"]["carriers"], arm_genome_triples(site.ARMS["arm3"])),
        ("Arm 4: NB72462M genome", carriers(site.load(ARM4 / "comparison.json")), arm_genome_triples(ARM4)),
    ]
    fig, axes = plt.subplots(3, 2, figsize=(WIDTH_IN, 4.35))
    fig.subplots_adjust(left=0.27, right=0.95, top=0.94, bottom=0.05, wspace=0.18, hspace=0.62)
    for i, (ax, (name, counts, triples)) in enumerate(zip(axes.flat, panels)):
        style_axes(ax, "x")
        rows = [(key, label) for key, label in REQUESTERS if key in counts]
        top = max(counts[key]["rdf"] for key, _ in rows)
        for y, (key, _label) in zip(range(len(rows) - 1, -1, -1), rows):
            c = counts[key]
            ax.barh(y, c["rdf"], height=0.56, color=GRAY if key == "unrestricted" else BLUE, zorder=2)
            dot(ax, c["baseline"], y, ORANGE, size=4.6, zorder=4)
            ax.text(c["rdf"] + top * 0.06, y, f"{c['rdf']:,}", color=INK_2, fontsize=6.3,
                    va="center")
        ax.set_xlim(0, top * 1.38)
        ax.set_ylim(-0.6, len(rows) - 0.4)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([label for _, label in reversed(rows)] if i % 2 == 0 else [])
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _p: f"{x:,.0f}"))
        ax.xaxis.set_major_locator(FixedLocator([0, top / 2, top]) if top < 10 else
                                   matplotlib.ticker.MaxNLocator(3))
        subtitle = f", {triples_label(triples)} triples" if triples else ""
        ax.set_title(f"({'abcde'[i]}) {name}{subtitle}", fontsize=7)
    # The sixth cell holds the legend.
    key_ax = axes.flat[len(panels)]
    key_ax.axis("off")
    handles = [plt.Rectangle((0, 0), 1, 1, color=GRAY, label="RDF workflow, no policy"),
               plt.Rectangle((0, 0), 1, 1, color=BLUE, label="RDF workflow, release view"),
               plt.Line2D([], [], marker="o", linestyle="", color=ORANGE, markeredgecolor="white",
                          markersize=5, label="Conventional workflow")]
    key_ax.legend(handles=handles, loc="center left", handletextpad=0.5, labelspacing=0.9,
                  borderaxespad=0.0)
    fig.savefig(OUT / "fig-usecase-matches.pdf", metadata=PDF_METADATA)
    plt.close(fig)
    for name, counts, triples in panels:
        print(f"usecase {name}: {triples}", {k: (counts[k]['rdf'], counts[k]['baseline']) for k, _ in REQUESTERS if k in counts})


def millions(n: float) -> str:
    return f"{n / 1e6:.1f}M"


# ---------------------------------------------------------------------------
# Figure: stage costs of the linked workflow
# ---------------------------------------------------------------------------
#: The four arms in order of graph size; arm 4 (layered rules) ran on vcf-bench-3.
COST_ARMS = [
    ("Arm 1: five genome slices", site.ARMS["arm1"]),
    ("Arm 2: cohort of 104", site.ARMS["arm2"]),
    ("Arm 3: complete HG005", site.ARMS["arm3"]),
    ("Arm 4: complete NB72462M", ARM4),
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

if __name__ == "__main__":
    fig_scaling()
    fig_samples()
    fig_representations()
    fig_retrieval()
    fig_validation()
    fig_usecase_matches()
    fig_usecase_costs()
    for name in ("fig-scaling", "fig-samples", "fig-representations", "fig-retrieval",
                 "fig-validation", "fig-usecase-matches", "fig-usecase-costs"):
        print("wrote", OUT / f"{name}.pdf")
