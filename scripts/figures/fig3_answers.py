"""Figure 3: answers state their level, or abstain (the Manuscript page's
#answer-levels). The level of each answer on the simulated RNA suite by kind
of upload, and how often the answer set holds the true type, on RNA and on
protein, type by type.

summary.json gives the suite's coverage overall and per kind of upload, not
per type; the per-type RNA values are computed here from the suite's per-cell
table beside it (eval_cells.csv.gz, the cells summary.json was computed from),
grouping reference types into the protein data's author types with the
protocol's mapping (COARSE in benchmark/fulcher2026_score.py). On RNA a cell
counts as covered when its set holds its own reference type; on Fulcher 2026
when its set holds any type of its author label (research/notebooks/
protein_coverage.py).
"""
from __future__ import annotations

import ast
import csv
import gzip

from . import common, style

NAME = "fig3-answers"
TITLE = "Figure 3"
SECTION = "answer-levels"
WIDTH = "double"

SUMMARY = "research/notebook-outputs/v41_phase3/summary.json"
CELLS = "research/notebook-outputs/v41_phase3/eval_cells.csv.gz"
COVERAGE = "research/notebook-outputs/protein_coverage/coverage.json"
MAPPING = "benchmark/fulcher2026_score.py"
SOURCES = (SUMMARY, CELLS, COVERAGE, MAPPING)

ALT = ("Two panels. a, stacked horizontal bars, one per kind of simulated RNA upload and one for all uploads, "
       "each split into the share of cells answered with one type, with a family, with a branch, or not "
       "answered: most answers name a branch, and uploads of one type alone go unanswered most often. "
       "b, a dumbbell per cell type comparing how often the answer set holds the true type on simulated RNA "
       "and on protein, against the target: on RNA most types are near the target; on Fulcher protein CD eight "
       "T and dendritic cells fall far below it, and on the macrophage and monocyte protein set almost no "
       "cell is covered.")
CAPTION = ("Answers state their level, or abstain. a, The level of the served model's answer for each cell of "
           "the simulated RNA evaluation suite, by kind of upload: one type, a family of types, a branch "
           "(lineage), or no answer; each bar gives its number of cells. b, Coverage: the share of cells whose "
           "answer set holds the true type, on the simulated RNA suite (orange) and on development protein data "
           "(green), for Fulcher's author types and the two types of the macrophage and monocyte protein set, "
           "against the target the sets were fitted to on simulated RNA (grey line). On RNA a cell counts when "
           "its set holds its own reference type, grouped into Fulcher's types; on Fulcher when its set holds "
           "a type of its author label. A type without a cell in the suite has a protein value only.")

KINDS = (("single", "One type alone"), ("narrow", "A few types"), ("mixed", "Many types"),
         ("lineage", "One lineage"), ("pbmc", "PBMC-like"), ("scope2", "SCoPE2-like"))
ALL = "All uploads"
LEVELS = (("class", "One type"), ("group", "A family"), ("lineage", "A branch"), ("abstain", "No answer"))
LEVEL_COLOUR = {"class": style.LEVELS["class"], "group": style.LEVELS["group"],
                "lineage": style.LEVELS["lineage"], "abstain": style.LEVELS["none"]}
CELLS_SERIES = "cells"

# Panel b: the protein data sets, the types each labels, as the page names them.
FULCHER_TYPES = (("CD4T", "CD4 T"), ("CD8T", "CD8 T"), ("NK", "NK"), ("B", "B"), ("monocyte", "Monocyte"),
                 ("DC", "Dendritic cell"))
SCOPE2_TYPES = (("macrophage", "Macrophage"), ("monocyte", "Monocyte"))
GROUPS = (("fulcher2026", "Fulcher 2026"), ("scope2", "SCoPE2"))
EVERY = "All cells"
RNA, PROTEIN, TARGET = "RNA", "Protein", "target"


def coarse() -> dict:
    """The protocol's reference-type to author-type mapping, read from the scoring script."""
    tree = ast.parse((common.REPO / MAPPING).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "COARSE" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"{MAPPING} has no COARSE")


def rna_coverage(method: str = "v4.1") -> dict:
    """Per reference type: [cells, covered] on the simulated suite."""
    counts = {}
    with gzip.open(common.REPO / CELLS, "rt", encoding="utf-8", newline="") as handle:
        for cell in csv.DictReader(handle):
            if cell["method"] == method:
                n = counts.setdefault(cell["true"], [0, 0])
                n[0] += 1
                n[1] += cell["covered"] == "True"
    return counts


def data() -> list[dict]:
    summary = common.read_json(SUMMARY)
    coverage = common.read_json(COVERAGE)
    rows = []
    for key, label in (("all", ALL),) + KINDS:
        record, field = ((summary["result"]["v4.1"], "result.v4.1") if key == "all"
                         else (summary["by_scenario"]["v4.1"][key], f"by_scenario.v4.1.{key}"))
        for level, name in LEVELS:
            rows.append(common.row("a", label, record["levels"][level], series=name, unit="% of cells",
                                   source=SUMMARY, field=f"{field}.levels.{level}"))
        rows.append(common.row("a", label, record["cells"], series=CELLS_SERIES, unit="cells", source=SUMMARY,
                               field=f"{field}.cells"))

    mapping = coarse()
    cells = rna_coverage()
    overall = summary["result"]["v4.1"]["coverage"]
    for group, group_name in GROUPS:
        protein = coverage["v41"][group]
        rows.append(common.row("b", f"{group_name}: {EVERY}", overall, series=RNA, unit="%", source=SUMMARY,
                               field="result.v4.1.coverage"))
        rows.append(common.row("b", f"{group_name}: {EVERY}", protein["coverage_pct"], series=PROTEIN, unit="%",
                               source=COVERAGE, field=f"v41.{group}.coverage_pct"))
        for key, label in (FULCHER_TYPES if group == "fulcher2026" else SCOPE2_TYPES):
            members = sorted(c for c in cells if (mapping.get(c) == key if group == "fulcher2026" else c == key))
            n = sum(cells[c][0] for c in members)
            if n:
                hit = sum(cells[c][1] for c in members)
                where = (f"COARSE {key}: {', '.join(members)}" if group == "fulcher2026" else key)
                rows.append(common.row("b", f"{group_name}: {label}", round(100 * hit / n, 2), series=RNA,
                                       unit="%", source=CELLS,
                                       field=f"method v4.1, true in ({where}): share covered of {n} cells"))
            rows.append(common.row("b", f"{group_name}: {label}", protein["by_class"][key]["coverage_pct"],
                                   series=PROTEIN, unit="%", source=COVERAGE,
                                   field=f"v41.{group}.by_class.{key}.coverage_pct"))
    rows.append(common.row("b", TARGET, coverage["target_pct"], unit="%", source=COVERAGE, field="target_pct"))
    return rows


def _head(fig, ax, letter, title, left_mm):
    """The panel letter (left_mm left of the plot) and a short title on one line, a fixed height above it."""
    box = ax.get_position()
    y = 1 + (7 / 72) / (box.height * fig.get_figheight())
    common.panel_letter(ax, letter, x=-left_mm * style.MM / (box.width * fig.get_figwidth()), y=y)
    ax.text(0, y, title, transform=ax.transAxes, ha="left", va="bottom", fontsize=style.SIZE_TITLE,
            color=style.INK)


def _levels(fig, ax, rows):
    kinds = list(dict.fromkeys(r["label"] for r in rows))
    ys = [0] + [i + 0.5 for i in range(1, len(kinds))]          # all uploads, a gap, then each kind
    height = 0.62
    for y, kind in zip(ys, kinds):
        left = 0.0
        for level, name in LEVELS:
            value = next(r["value"] for r in rows if r["label"] == kind and r["series"] == name)
            ax.barh(y, value, left=left, height=height, color=LEVEL_COLOUR[level], edgecolor=style.PAPER,
                    linewidth=0.8, zorder=2)
            if value >= 6:
                ax.text(left + value / 2, y, f"{value:.0f}", ha="center", va="center", fontsize=style.SIZE,
                        color=style.PAPER if level == "class" else style.INK, zorder=3)
            left += value
        count = next(r["value"] for r in rows if r["label"] == kind and r["series"] == CELLS_SERIES)
        ax.text(101.5, y, f"{count:,} cells", ha="left", va="center", fontsize=style.SIZE, color=style.INK_SOFT,
                clip_on=False)
    ax.set_xlim(0, 100)
    ax.set_ylim(ys[-1] + 0.6, -0.6)
    ax.set_yticks(ys, kinds)
    ax.set_xticks(range(0, 101, 25))
    ax.tick_params(axis="y", length=0, labelcolor=style.INK, pad=4)
    ax.tick_params(axis="x", length=2.5, width=style.LINE_WIDTH)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Share of cells (%)")
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=LEVEL_COLOUR[level], edgecolor="none", label=name) for level, name in LEVELS]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(ax.get_position().x0, 0.995), ncol=len(handles),
               borderaxespad=0, handlelength=1.2, handleheight=0.9, handletextpad=0.4, columnspacing=1.2)


def _coverage(fig, ax, rows):
    pairs = [r for r in rows if r["label"] != TARGET]
    target = next(r for r in rows if r["label"] == TARGET)
    labels = list(dict.fromkeys(r["label"] for r in pairs))
    groups = list(dict.fromkeys(lab.split(": ", 1)[0] for lab in labels))
    ticks, names, positions, y = [], [], {}, 0.0
    for group in groups:
        ticks.append(y)
        names.append(group)
        y += 1
        for lab in (x for x in labels if x.split(": ", 1)[0] == group):
            positions[lab] = y
            ticks.append(y)
            names.append(lab.split(": ", 1)[1])
            y += 1
        y += 0.3
    ax.axvline(target["value"], color=style.NEUTRAL, linewidth=style.LINE_WIDTH, linestyle=(0, (3, 2)), zorder=1)
    ax.text(target["value"] - 1.5, -0.55, "target", ha="right", va="center", fontsize=style.SIZE,
            color=style.INK_SOFT)
    for lab, yy in positions.items():
        got = {r["series"]: r["value"] for r in pairs if r["label"] == lab}
        if len(got) == 2:
            ax.plot([got[RNA], got[PROTEIN]], [yy, yy], color=style.NEUTRAL, linewidth=style.MARK_WIDTH, zorder=2)
        for series, colour, marker in ((RNA, style.RNA, "o"), (PROTEIN, style.PROT, "s")):
            if series in got:
                ax.plot([got[series]], [yy], linestyle="none", marker=marker, markersize=style.MARKER + 0.4,
                        color=colour, markeredgecolor=style.PAPER, markeredgewidth=0.5, zorder=3, clip_on=False,
                        label=series if lab == labels[0] else None)
    ax.set_xlim(0, 100)
    ax.set_ylim(y - 0.3 - 0.4, -0.9)
    ax.set_yticks(ticks, names)
    for text, name in zip(ax.get_yticklabels(), names):
        if name in groups:
            text.set_fontweight("bold")
            text.set_color(style.INK)
    ax.set_xticks(range(0, 101, 25))
    ax.tick_params(axis="y", length=0, labelcolor=style.INK, pad=4)
    ax.tick_params(axis="x", length=2.5, width=style.LINE_WIDTH)
    ax.spines["left"].set_visible(False)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_xlabel("Coverage of the true type (%)")
    handles, labs = ax.get_legend_handles_labels()
    labs = ["RNA, simulated suite" if lab == RNA else "Protein" for lab in labs]
    fig.legend(handles, labs, loc="upper left", bbox_to_anchor=(ax.get_position().x0, 0.995), ncol=2,
               borderaxespad=0, handletextpad=0.3, columnspacing=1.2)


def draw(rows, plt):
    fig = common.new_figure(plt, WIDTH, 78)
    grid = fig.add_gridspec(1, 2, width_ratios=(1.4, 1), left=0.115, right=0.985, bottom=0.12, top=0.84,
                            wspace=0.74)
    ax_a = fig.add_subplot(grid[0, 0])
    ax_b = fig.add_subplot(grid[0, 1])
    _levels(fig, ax_a, [r for r in rows if r["panel"] == "a"])
    _coverage(fig, ax_b, [r for r in rows if r["panel"] == "b"])
    _head(fig, ax_a, "a", "Answer level by kind of upload", 21.5)
    _head(fig, ax_b, "b", "Coverage by type", 25)
    return fig
