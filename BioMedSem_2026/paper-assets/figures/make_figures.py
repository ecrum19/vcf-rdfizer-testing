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
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
RESULTS = HERE.parent.parent / "benchmark-results"
B1 = RESULTS / "vcf-bench-1" / "benchmarks_outputs"
B2 = RESULTS / "vcf-bench-2" / "benchmarks_outputs"

# Records in the whole HG005_GRCh38 file (the archive does not record it;
# counted with `zcat | grep -vc '^#'` on vcf-bench-1).
HG005_WHOLE_RECORDS = 3_856_856

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


def tidy(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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
    records = defaultdict(lambda: defaultdict(list))
    for row in tidy(B1 / "04_scaling_records" / "tidy.csv"):
        rung = row["cell"].split("__")[0]
        n = HG005_WHOLE_RECORDS if rung == "rfull" else int(rung[1:])
        records[n]["triples"].append(float(row["output_triples"]))
        records[n]["wall"].append(float(row["wrapper_wall_seconds"]))
        records[n]["disk"].append(float(row["peak_host_out_tree_bytes"]))
        records[n]["rss"].append(float(row["max_rss_kb_java"]))
    rungs = sorted(records)
    med = {k: [st.median(records[n][k]) for n in rungs] for k in ("triples", "wall", "disk", "rss")}
    idx = {k: [v / med[k][0] for v in med[k]] for k in med}

    storage = defaultdict(lambda: defaultdict(list))
    for row in tidy(B1 / "01_storage_mode" / "tidy.csv"):
        key = "slice" if row["cell"].startswith("HG005") else "larger"
        storage[key][row["rdf_storage_mode"]].append(
            (float(row["peak_host_out_tree_bytes"]), float(row["wrapper_wall_seconds"]),
             float(row["output_triples"])))

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
def sample_ladder() -> dict:
    """Median triples and stored bytes per (profile, sample count)."""
    summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    raw = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for cell in summary["cells"]:
        if cell["experiment"] != "03_sample_representation" or cell["branch"] != "live":
            continue
        if not cell["cell"].startswith("s") or not cell.get("runs"):
            continue
        n = int(cell["cell"].split("__")[0][1:])
        profile = cell["cell"].split("__")[1]
        d = cell["runs"][0]["datasets"][0]
        for key, field in (("triples", "total_triples"), ("nt", "rdf_size_bytes"),
                           ("hdt", "hdt_size_bytes"), ("cottas", "cottas_size_bytes"),
                           ("vcf", "input_vcf_size_bytes")):
            if d.get(field) is not None:  # COTTAS only where the cell built it
                raw[profile][key][n].append(float(d[field]))
    ladder = {}
    for profile, keys in raw.items():
        xs = sorted(keys["triples"])
        ladder[profile] = {"x": xs, **{k: [st.median(keys[k][n]) for n in xs]
                                       for k in keys if all(keys[k][n] for n in xs)}}
    return ladder


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
# Dataset name as the run records it -> the paper's short label.
SHORT_NAMES = {
    "0GOOR_HG002_first250000": "HG002",
    "HG004_GRCh38_first250000": "HG004",
    "HG005_GRCh38": "HG005 (whole)",
    "HGSVC2_first250000": "HGSVC2",
}


def corpus_rows() -> list[dict]:
    summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    rows = []
    for cell in summary["cells"]:
        if cell["experiment"] != "05_corpus_breadth" or cell["branch"] != "live":
            continue
        if not cell.get("runs"):
            continue
        d = cell["runs"][0]["datasets"][0]
        name = SHORT_NAMES.get(d["dataset"], d["dataset"].replace("_first250000", ""))
        rows.append({
            "name": name,
            "triples": d["hdt_validation_source_triples"],
            "nt": d["rdf_size_bytes"], "hdt": d["hdt_size_bytes"], "cottas": d["cottas_size_bytes"],
            "hdt_s": d["hdt_wall_seconds"], "cottas_s": d["cottas_wall_seconds"],
        })
    return sorted(rows, key=lambda r: r["triples"])


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
QUERIES = [
    ("q01_record_density_1mb", "Q1 Record density"),
    ("q02_variant_shape_counts", "Q2 Allele shapes"),
    ("q03_titv", "Q3 Ti/Tv"),
    ("q04_filter_distribution", "Q4 FILTER states"),
    ("q05_sample_genotype_counts", "Q5 Genotype classes"),
    ("q06_ac_an_distribution", "Q6 AC/AN"),
    ("q07_file_metadata", "Q7 File metadata"),
    ("q08_header_line_census", "Q8 Header census"),
    ("q09_predicate_census", "Q9 Predicate census"),
    ("q10_class_census", "Q10 Class census"),
    ("q11_record_digest", "Q11 Record digest"),
    ("q12_info_value_digest", "Q12 INFO digest"),
    ("q13_format_value_digest", "Q13 FORMAT digest"),
]
QIDS = {q for q, _ in QUERIES}


def benchmark_rows(scale: str):
    """Yield (replicate, target, row) for every benchmark.csv of one scale."""
    for rep_dir in sorted((B1 / "13_query_cost").glob(f"{scale}__r*")):
        for path in rep_dir.glob("out/run_metrics/*/reports/validation/*/benchmark.csv"):
            target = path.parent.name.rsplit("__", 1)[-1] if "__" in path.parent.name else "nt"
            for row in tidy(path):
                yield rep_dir.name, target, row


def fig_retrieval() -> None:
    engine_q = defaultdict(list)
    oracle_q = defaultdict(list)
    batch = defaultdict(lambda: defaultdict(float))  # (rep, target) -> engine -> seconds
    setup = defaultdict(list)
    oracle_wall = []
    seen = set()
    for rep, target, row in benchmark_rows("large"):
        if row["query_id"] not in QIDS or row["status"] != "PASS":
            continue
        key = (rep, target, row["engine"], row["query_id"])
        if key in seen:
            continue
        seen.add(key)
        if target == "nt":
            engine_q[row["query_id"]].append(float(row["wall_seconds"]))
        # The parser does not depend on which artifact is being validated, so
        # every validation of a replicate is a replicate of the same scan.
        oracle_q[row["query_id"]].append(float(row["oracle_query_seconds"]))
        oracle_wall.append(float(row["oracle_wall_seconds"]))
        batch[(rep, target)][row["engine"]] += float(row["wall_seconds"])
        setup[(target, row["engine"])].append(float(row["engine_setup_seconds"]))
    per_target = defaultdict(list)
    for (rep, target), engines in batch.items():
        per_target[target].append(engines["qlever"])
    ql_batch = st.mean(per_target["nt"])
    ql_setup = st.mean(setup[("nt", "qlever")])
    parser_batch = st.mean(oracle_wall)

    small = defaultdict(lambda: defaultdict(float))
    small_setup = defaultdict(list)
    seen = set()
    for rep, target, row in benchmark_rows("small"):
        if row["query_id"] not in QIDS or row["status"] != "PASS":
            continue
        key = (rep, target, row["engine"], row["query_id"])
        if key in seen:
            continue
        seen.add(key)
        small[(rep, target)][row["engine"]] += float(row["wall_seconds"])
        small_setup[row["engine"]].append(float(row["engine_setup_seconds"]))
    engine_runs = defaultdict(list)
    for engines in small.values():
        for engine, seconds in engines.items():
            engine_runs[engine].append(seconds)

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
# Figure: the policy demonstrator's decision grid
# ---------------------------------------------------------------------------
POLICY_DEMO = HERE / "data" / "policy-demo"
REQUESTERS = [("gru", "General research", "GRU"), ("alz", "Alzheimer's study", "DS"),
              ("clinical", "Clinical genetics", "CC")]
BRCA1_WINDOW = ("chr17", 43044295, 43125483)
APOE_E4 = ("chr19", 44908684, "T", "C")


def policy_rows(key):
    """(label, released?, cell text) per row of the grid, for one requester's view."""
    view = POLICY_DEMO / key
    counts = json.loads((view / "summary.json").read_text(encoding="utf-8"))
    decisions = list(csv.DictReader((view / "decisions.csv").open(encoding="utf-8")))
    rows = []
    for file_iri, info in counts["files"].items():
        name = file_iri.split("//")[1].replace(".vcf", "")
        if info["released"]:
            rows.append((name, True, f"{info['records_released']} records"))
        else:
            rows.append((name, False, "withdrawn" if "prohibition" in info["reason"] else "no consent"))

    def selected(test):
        # Records the rule decides: those in files this requester may otherwise see.
        hits = [d for d in decisions if test(d) and counts["files"][d["file"]]["released"]]
        released = sum(d["released"] == "True" for d in hits)
        return released == len(hits), f"{released} of {len(hits)}"

    chrom, start, end = BRCA1_WINDOW
    rows.append(("BRCA1", *selected(lambda d: d["chrom"] == chrom and start <= int(d["pos"]) <= end)))
    rows.append(("rs429358", *selected(lambda d: (d["chrom"], int(d["pos"]), d["ref"], d["alts"]) ==
                                       (APOE_E4[0], APOE_E4[1], APOE_E4[2], APOE_E4[3]))))
    return rows, counts


def fig_policy() -> None:
    views = {key: policy_rows(key) for key, _, _ in REQUESTERS}
    labels = [label for label, _, _ in views["gru"][0]]
    rule_text = {"P001": "GRU + CC", "P002": "GRU + CC", "P003": "HMB", "P004": "withdrew",
                 "P005": "DS", "BRCA1": "region: CC only", "rs429358": "variant: DS only"}
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.7))
    fig.subplots_adjust(left=0.25, right=0.99, top=0.85, bottom=0.16)
    n_rows = len(labels)
    for col, (key, _, _) in enumerate(REQUESTERS):
        rows, _ = views[key]
        for row, (label, released, text) in enumerate(rows):
            y = n_rows - 1 - row
            ax.add_patch(plt.Rectangle((col + 0.04, y + 0.08), 0.92, 0.84, linewidth=0,
                                       facecolor=BLUE if released else "#e7e6e2"))
            ax.text(col + 0.5, y + 0.5, text, ha="center", va="center", fontsize=6.5,
                    color="white" if released else INK_2)
    ax.axhline(2.0, color=AXIS, linewidth=0.6)            # consents above, cohort rules below
    ax.set_xlim(0, len(REQUESTERS))
    ax.set_ylim(0, n_rows)
    ax.set_yticks([n_rows - 0.5 - i for i in range(n_rows)])
    ax.set_yticklabels([f"{label}  ({rule_text[label]})" for label in labels])
    ax.set_xticks([i + 0.5 for i in range(len(REQUESTERS))])
    ax.set_xticklabels([f"{name}\npurpose {code}" for _, name, code in REQUESTERS])
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    for col, (key, _, _) in enumerate(REQUESTERS):
        s = views[key][1]
        ax.text(col + 0.5, -0.25, f"{s['records_released']} of {s['records_released'] + s['records_withheld']} "
                "records released\n"
                f"{views[key][1]['triples_withheld']:,} triples withheld",
                ha="center", va="top", fontsize=6.2, color=INK_2)
    fig.savefig(OUT / "fig-policy-grid.pdf", metadata=PDF_METADATA)
    plt.close(fig)


if __name__ == "__main__":
    fig_scaling()
    fig_samples()
    fig_representations()
    fig_retrieval()
    fig_policy()
    for name in ("fig-scaling", "fig-samples", "fig-representations", "fig-retrieval", "fig-policy-grid"):
        print("wrote", OUT / f"{name}.pdf")
