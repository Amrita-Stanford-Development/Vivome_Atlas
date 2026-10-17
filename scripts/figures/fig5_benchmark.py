"""Figure 5: the benchmark as a forest plot. Each row is one outside method's
run (a rule, and a seed where the method is stochastic): VivOME v4.1's
balanced accuracy minus that run's, with the paired bootstrap's 95% interval,
on Khoury (post hoc) and on Fulcher (development, in sample for the model's
one weight). Rows against older VivOME models are left out (the owner's
decision): v4.1 is compared with outside methods only.
"""
from __future__ import annotations

import re

from . import common, style

NAME = "fig5-benchmark"
TITLE = "Figure 5"
SECTION = "benchmark"
WIDTH = "double"

KHOURY = "research/benchmark/khoury2026_posthoc_v41_check/paired_bootstrap.csv"
FULCHER = "research/benchmark/v41_development/paired_bootstrap_v41.csv"
SOURCES = (KHOURY, FULCHER)

ALT = ("Two forest plots side by side, Khoury on the left and Fulcher on the right, on one horizontal "
       "scale of balanced accuracy points. Each row is one run of an outside method, grouped by method "
       "and named by its rule and seed; a dot marks the served model minus that run, a whisker its 95% "
       "interval, and a vertical line marks zero. Rows right of zero favour VivOME. On Fulcher every "
       "interval lies right of zero. On Khoury most do; the intervals for PCA with neighbours and for "
       "some scANVI runs with neighbours include zero.")
CAPTION = ("The benchmark, the served VivOME model against each outside method. Each row is one run: a method, its "
           "rule for turning its output into a cell type, and its seed where the method is stochastic. "
           "The dot is the served model's balanced accuracy minus the run's, in points; the whisker is the "
           "paired bootstrap's 95% interval. Right of the zero line favours VivOME, left favours the "
           "method; blue marks an interval wholly right of zero, grey one that includes zero. (a) Khoury, "
           "scored post hoc. (b) Fulcher, development data, in sample for the model's one tuned weight. "
           "Every method gets the same RNA reference, its labels and the same query cells; comparisons "
           "with earlier VivOME models are left out.")

# The methods, in the page's order, and how their names are written.
METHODS = (("correlation", "Correlation"), ("pca", "PCA"), ("harmony", "Harmony"), ("scanvi", "scANVI"),
           ("maxfuse", "MaxFuse"), ("scglue", "scGLUE"), ("seurat", "Seurat"))
# Each rule in plain words, in the order rows are listed within a method.
RULES = {
    "shared_knn": "nearest neighbours", "shared kNN": "nearest neighbours",
    "nearest centroid": "nearest centroid",
    "scANVI classifier": "its own classifier",
    "Seurat native transfer": "its own transfer",
    "MaxFuse matching": "its own matching", "matching": "its own matching",
    "correlation": "correlation to type means", "correlation to class mean": "correlation to type means",
}
NATIVE = {"scanvi": "its own classifier", "seurat": "its own transfer"}   # Khoury's "native" rule, by method
RULE_ORDER = ("nearest neighbours", "nearest centroid", "its own classifier", "its own transfer",
              "its own matching", "correlation to type means")
OLDER_VIVOME = re.compile(r"^v\d")       # model_b of a VivOME version (v4, v3.1): left out


def _runs(panel: str, source: str, entries: list[tuple]) -> list[dict]:
    """entries: (method, rule words, seed, value, lo, hi, field), any order; returns rows grouped by method."""
    order = {key: i for i, (key, _) in enumerate(METHODS)}
    names = dict(METHODS)
    rows = []
    for key, _ in METHODS:
        mine = sorted((e for e in entries if e[0] == key), key=lambda e: (RULE_ORDER.index(e[1]), int(e[2])))
        seeds = {e[2] for e in mine}
        for method, rule, seed, value, lo, hi, field in mine:
            label = rule if len(seeds) == 1 else f"{rule}, seed {seed}"
            rows.append(common.row(panel, label, value, series=names[method], lo=lo, hi=hi,
                                   unit="balanced accuracy points", source=source, field=field))
    unknown = {e[0] for e in entries} - set(order)
    if unknown:
        raise KeyError(f"{source}: methods not in METHODS: {sorted(unknown)}")
    return rows


def data() -> list[dict]:
    khoury = []
    for i, r in enumerate(common.read_csv(KHOURY)):
        if OLDER_VIVOME.match(r["model_b"]):
            continue
        method, seed = re.fullmatch(r"([a-z]+)_seed(\d+)", r["model_b"]).groups()
        rule = NATIVE[method] if r["rule_b"] == "native" else RULES[r["rule_b"]]
        khoury.append((method, rule, seed, float(r["diff_bal_acc_pct"]), float(r["ci_lo"]), float(r["ci_hi"]),
                       f"row {i + 1} ({r['comparison']}, {r['model_b']}, {r['rule_b']}): diff_bal_acc_pct, ci_lo, ci_hi"))
    fulcher = []
    for i, r in enumerate(common.read_csv(FULCHER)):
        if r["dataset"] != "Fulcher 2026":
            continue
        fulcher.append((r["baseline"], RULES[r["baseline_rule"]], r["seed"], float(r["point_estimate_pct"]),
                        float(r["ci_lo"]), float(r["ci_hi"]),
                        f"row {i + 1} (Fulcher 2026, {r['baseline']}, seed {r['seed']}, {r['baseline_rule']}): "
                        "point_estimate_pct, ci_lo, ci_hi"))
    return _runs("a", KHOURY, khoury) + _runs("b", FULCHER, fulcher)


# ---- drawing (lengths in mm) ----

ROW_MM = 2.85          # one run
HEAD_MM = 3.3          # a method's name
TOP_MM = 12.0          # letter, title and the words for each side, above the rows
AXIS_MM = 11.0         # tick labels and the axis label, below the rows
LABEL_MM, PLOT_MM, GAP_MM = 33.0, 56.0, 13.0


def _layout(rows: list[dict]):
    """y positions (mm from the top of the rows) of each method's name and each run."""
    y, heads, runs, last = 0.0, [], [], None
    for r in rows:
        if r["series"] != last:
            if last is not None:
                y += 1.2
            heads.append((y + HEAD_MM * 0.55, r["series"]))
            y += HEAD_MM
            last = r["series"]
        runs.append(y + ROW_MM / 2)
        y += ROW_MM
    return heads, runs, y + 0.6


def _colour(r: dict) -> str:
    """Blue when the interval is wholly on VivOME's side, grey when it includes zero."""
    if r["lo"] > 0:
        return style.ACCENT
    return style.RNA if r["hi"] < 0 else style.NEUTRAL


def draw(rows, plt):
    from matplotlib.lines import Line2D

    panels = [("a", "Khoury 2026, scored post hoc"), ("b", "Fulcher 2026, development data, in sample")]
    groups = {p: [r for r in rows if r["panel"] == p] for p, _ in panels}
    layouts = {p: _layout(groups[p]) for p, _ in panels}
    tallest = max(layout[2] for layout in layouts.values())
    height = TOP_MM + tallest + AXIS_MM
    width = style.WIDTHS_MM[WIDTH]
    fig = common.new_figure(plt, WIDTH, height)

    lo = min(min(r["lo"] for r in rows), 0.0)
    hi = max(r["hi"] for r in rows)
    pad = 0.04 * (hi - lo)
    xlim = (lo - pad, hi + pad)

    for k, (p, title) in enumerate(panels):
        heads, runs, body = layouts[p]
        left = LABEL_MM + k * (LABEL_MM + PLOT_MM + GAP_MM)
        bottom = height - TOP_MM - body
        ax = fig.add_axes((left / width, bottom / height, PLOT_MM / width, body / height))
        ax.set_xlim(*xlim)
        ax.set_ylim(body, 0)
        ax.grid(axis="x", color=style.LINE, linewidth=0.5)
        ax.set_axisbelow(True)
        ax.axvline(0, color=style.NEUTRAL, linewidth=style.LINE_WIDTH, zorder=1)
        for r, y in zip(groups[p], runs):
            colour = _colour(r)
            ax.plot([r["lo"], r["hi"]], [y, y], color=colour, linewidth=style.MARK_WIDTH, solid_capstyle="butt",
                    zorder=2)
            ax.plot([r["value"]], [y], "o", color=colour, markersize=style.MARKER * 0.85,
                    markeredgecolor=style.PAPER, markeredgewidth=0.3, zorder=3)
        ax.set_yticks(runs)
        ax.set_yticklabels([r["label"] for r in groups[p]], fontsize=style.SIZE, color=style.INK_SOFT)
        ax.tick_params(axis="y", length=0, pad=2)
        ax.spines["left"].set_visible(False)
        for yh, name in heads:
            ax.text(-0.8 / PLOT_MM, yh, name, transform=ax.get_yaxis_transform(), ha="right", va="center",
                    fontsize=style.SIZE_LABEL, fontweight="bold", color=style.INK)
        for yh, _ in heads[1:]:          # a thin rule between methods
            ax.axhline(yh - HEAD_MM * 0.55 - 0.6, color=style.LINE, linewidth=0.5, zorder=0)
        ax.set_xlabel("VivOME v4.1 minus the method, balanced accuracy points", fontsize=style.SIZE_LABEL,
                      color=style.INK, labelpad=2)
        # The letter and the title on one line; under them, which side favours whom.
        x0 = -LABEL_MM / PLOT_MM
        ax.text(x0, 1 + 9.0 / body, p, transform=ax.transAxes, fontsize=style.SIZE_LETTER, fontweight="bold",
                ha="left", va="baseline", color=style.INK)
        ax.text(x0 + 4.0 / PLOT_MM, 1 + 9.0 / body, title, transform=ax.transAxes, fontsize=style.SIZE_TITLE,
                ha="left", va="baseline", color=style.INK)
        for text, sign, ha in (("favours VivOME v4.1 →", 1, "left"), ("← favours the method", -1, "right")):
            ax.annotate(text, xy=(0, 1), xycoords=("data", "axes fraction"), xytext=(sign * 3, 3),
                        textcoords="offset points", ha=ha, va="bottom", fontsize=style.SIZE, color=style.INK_SOFT,
                        annotation_clip=False)
    # One legend for both panels, in the room under the shorter one.
    marker = dict(marker="o", linewidth=style.MARK_WIDTH, markersize=style.MARKER * 0.85, markeredgecolor=style.PAPER,
                  markeredgewidth=0.3)
    handles = [Line2D([], [], color=style.ACCENT, label="95% interval right of zero", **marker),
               Line2D([], [], color=style.NEUTRAL, label="95% interval includes zero", **marker)]
    if any(r["hi"] < 0 for r in rows):
        handles.append(Line2D([], [], color=style.RNA, label="95% interval left of zero", **marker))
    short = min(panels, key=lambda pt: layouts[pt[0]][2])[0]
    k = [p for p, _ in panels].index(short)
    room_top = height - TOP_MM - layouts[short][2] - AXIS_MM - 2.0
    fig.legend(handles=handles, loc="upper left", fontsize=style.SIZE, frameon=False, handlelength=1.8,
               bbox_to_anchor=((LABEL_MM + k * (LABEL_MM + PLOT_MM + GAP_MM) - 2.0) / width, room_top / height))
    return fig
