"""Figure 6: where the model fails. (a) Cells of one type uploaded alone,
against the same cells in their whole upload and beside one other type. (b)
Foreign cells: what the served model says to cell lines and microglia outside
the blood reference, and how few it refuses as outside. (c, d, e) CD8 against
CD4 T cells on Khoury: what its CD8 T cluster is called, what tells its two
T-cell clusters apart, and where the reference files naive CD8-like cells.
"""
from __future__ import annotations

from . import common, style

NAME = "fig6-limits"
TITLE = "Figure 6"
SECTION = "failure-modes"
WIDTH = "double"

SINGLE = "research/notebook-outputs/single_type_uploads/summary.json"
FOREIGN = "research/notebook-outputs/ood_candidates/summary.json"
CD8_CD4 = "research/notebook-outputs/cd8_cd4_diagnosis/diagnosis.json"
SPEC = "service/model/v4_1/spec_v41.json"          # the served answer levels (which name is a type, a family, a lineage)
SOURCES = (SINGLE, FOREIGN, CD8_CD4, SPEC)

ALT = ("Five panels. (a) Two dot plots sharing one list of six cell types: on the left the share of "
       "committed answers that are right, on the right recall, each for the cells in their whole upload, "
       "uploaded alone, and uploaded with one other type. Alone, most types fall far below their level "
       "in the whole upload. (b) One horizontal bar per foreign cell set, split into the reasons for no "
       "answer in greys and the answers given in blues by level, with the number answered at the right; "
       "almost none are refused as outside the reference, most get no answer because they fall between "
       "types, and some get a blood answer. (c) Bars of what the served model calls Khoury's cytotoxic "
       "T-cell cluster: mostly naive helper and helper T cells, rarely its own type. (d) For two memory "
       "markers and the cytotoxic marker, how well each tells Khoury's two T-cell clusters apart, against "
       "chance; the memory markers separate them far better. (e) Bars of where the reference files its "
       "naive cytotoxic-like T cells: mostly under helper T cells.")
CAPTION = ("Where the model fails. (a) Cells of one type uploaded alone, against the same cells in their "
           "whole upload and uploaded with one other type: the share of committed answers that are right, "
           "and recall (the pairs are named below the panel). Scaling within the upload is the cause. "
           "(b) Foreign cells: what the served model gives each cell line and the microglia, as a share of "
           "the set's cells, split into the reasons for no answer (greys) and the answers it commits to "
           "by level (blues), with the cells answered at the right. (c) The cells of Khoury's cytotoxic "
           "T-cell cluster, by the fine type the served model calls them. (d) How well single markers tell "
           "Khoury's cytotoxic T-cell cluster from its helper T-cell cluster (area under the ROC curve, "
           "oriented to the cluster where the marker is higher; the grey line is chance). (e) The "
           "reference's naive cytotoxic-like T cells, by the type the reference files them under. All on "
           "development or post hoc data.")

# ---- a: one type alone ----
TYPES = ("CD4T", "CD8T", "NK", "B", "monocyte", "DC")
TYPE_NAMES = {"CD4T": "CD4 T", "CD8T": "CD8 T", "NK": "NK", "B": "B", "monocyte": "Monocyte", "DC": "DC"}
METRICS = (("correct_when_committed_pct", "right when committed, %"), ("recall_pct", "recall, %"))
WHOLE, ALONE, PAIRED = "in its whole upload", "alone", "paired: "

# ---- b: foreign cells ----
NO_ANSWER = (("outside_supported_region", "outside the reference"), ("ambiguous_between_classes", "between types"),
             ("no_confident_label", "no confident label"), ("coverage_too_low", "too little measured"))
LEVEL_WORDS = {"class": "type", "group": "family", "lineage": "lineage"}
SET_NAMES = {"293T": "HEK293T"}

# ---- d: markers ----
CHANCE = 0.5     # the area under the ROC curve of a marker that does not tell the clusters apart (a definition)


def _single() -> list[dict]:
    summary = common.read_json(SINGLE)["v4.1"]
    rows = []
    for metric, unit in METRICS:
        for t in TYPES:
            for series, path in ((WHOLE, ("mixed", t)), (ALONE, ("alone", t))):
                rows.append(common.row("a", TYPE_NAMES[t], summary[path[0]][t][metric], series=series, unit=unit,
                                       source=SINGLE, field=f"v4.1 > {path[0]} > {t} > {metric}"))
            for pair, members in summary["paired"].items():
                if t in members:
                    rows.append(common.row("a", TYPE_NAMES[t], members[t][metric], series=PAIRED + pair, unit=unit,
                                           source=SINGLE, field=f"v4.1 > paired > {pair} > {t} > {metric}"))
    return rows


def _level(name: str, hierarchy: dict) -> str:
    if name in hierarchy:
        return "class"
    if name in {v["group"] for v in hierarchy.values()}:
        return "group"
    if name in {v["lineage"] for v in hierarchy.values()}:
        return "lineage"
    raise KeyError(f"{name!r} is not a type, family or lineage in {SPEC}")


def _foreign() -> list[dict]:
    hierarchy = common.read_json(SPEC)["hierarchy"]
    sets = common.read_json(FOREIGN)["foreign_development"]
    reasons = dict(NO_ANSWER)
    rows = []
    for key, record in sets.items():
        tail = key.split(" ", 1)[1]
        name = SET_NAMES.get(tail, tail)
        base = f"foreign_development > {key}"
        rows.append(common.row("b", "cells", record["cells"], series=name, unit="cells", source=FOREIGN,
                               field=f"{base} > cells"))
        served = record["v41_served"]
        unknown = [k for k in served if not k.startswith("answer: ") and k not in reasons]
        if unknown:
            raise KeyError(f"{FOREIGN}: {key}: outcomes not in NO_ANSWER: {unknown}")
        for outcome, words in NO_ANSWER:
            if outcome in served:
                rows.append(common.row("b", f"no answer: {words}", served[outcome], series=name, unit="cells",
                                       source=FOREIGN, field=f"{base} > v41_served > {outcome}"))
        answers = [(k, n) for k, n in served.items() if k.startswith("answer: ")]
        order = ("lineage", "group", "class")
        answers.sort(key=lambda kn: (order.index(_level(kn[0][len("answer: "):], hierarchy)), kn[0]))
        for outcome, n in answers:
            answer = outcome[len("answer: "):]
            level = LEVEL_WORDS[_level(answer, hierarchy)]
            rows.append(common.row("b", f"answer, {level}: {answer}", n, series=name, unit="cells", source=FOREIGN,
                                   field=f"{base} > v41_served > {outcome} (its level from {SPEC} > hierarchy)"))
    return rows


def _cd8() -> list[dict]:
    record = common.read_json(CD8_CD4)
    posthoc = record["khoury_posthoc"]
    rows = []
    called = posthoc["fine_classes_called"]["v4.1"]["CD8T"]
    for label, pct in called.items():
        rows.append(common.row("c", label, pct, series="Khoury's CD8 T cluster", unit="% of the cluster's cells",
                               source=CD8_CD4, field=f"khoury_posthoc > fine_classes_called > v4.1 > CD8T > {label}"))
    aucs = posthoc["auc_cd8_cluster_vs_cd4_cluster"]
    base = "khoury_posthoc > auc_cd8_cluster_vs_cd4_cluster"
    for marker, entry in aucs.items():
        auc = entry["auc_cd8_cluster"]
        if auc < CHANCE:
            rows.append(common.row("d", marker, round(1 - auc, 4), series="higher in the CD4 T cluster", unit="AUROC",
                                   source=CD8_CD4, field=f"{base} > {marker} > 1 - auc_cd8_cluster"))
        else:
            rows.append(common.row("d", marker, auc, series="higher in the CD8 T cluster", unit="AUROC",
                                   source=CD8_CD4, field=f"{base} > {marker} > auc_cd8_cluster"))
    reference = record["reference"]
    rows.append(common.row("e", "naive CD8-like cells", reference["naive_cd8_like_cells"], series="all", unit="cells",
                           source=CD8_CD4, field="reference > naive_cd8_like_cells"))
    for label, n in reference["naive_cd8_like_by_class"].items():
        rows.append(common.row("e", label, n, series="filed under", unit="cells", source=CD8_CD4,
                               field=f"reference > naive_cd8_like_by_class > {label}"))
    return rows


def data() -> list[dict]:
    return _single() + _foreign() + _cd8()


# ---- drawing (lengths in mm) ----

DISPLAY = {"mature nk t cell": "mature NK T cell"}      # a few names as the page writes them
ROW1_TOP, ROW1_H = 124.0, 40.0
ROW2_TOP, ROW2_H = 48.0, 32.0


def _axes(fig, W, H, left, bottom, w, h):
    return fig.add_axes((left / W, bottom / H, w / W, h / H))


def _title(ax, letter, title, dx_mm, w_mm, h_mm, dy_mm=3.5):
    ax.text(-dx_mm / w_mm, 1 + dy_mm / h_mm, letter, transform=ax.transAxes, fontsize=style.SIZE_LETTER,
            fontweight="bold", ha="left", va="baseline", color=style.INK)
    ax.text((4.0 - dx_mm) / w_mm, 1 + dy_mm / h_mm, title, transform=ax.transAxes, fontsize=style.SIZE_TITLE,
            ha="left", va="baseline", color=style.INK)


def _tint(colour: str, share: float) -> str:
    """colour mixed with the paper by share (0 keeps it, 1 is paper)."""
    rgb = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    paper = [int(style.PAPER[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(c + (p - c) * share):02X}" for c, p in zip(rgb, paper))


def _hbars(ax, labels, values, colour, fmt):
    ys = list(range(len(labels)))
    ax.barh(ys, values, height=0.62, color=colour, linewidth=0)
    for y, v in zip(ys, values):
        ax.text(v, y, " " + fmt(v), ha="left", va="center", fontsize=style.SIZE, color=style.INK_SOFT)
    ax.set_yticks(ys)
    ax.set_yticklabels([DISPLAY.get(x, x) for x in labels], fontsize=style.SIZE, color=style.INK_SOFT)
    ax.set_ylim(len(labels) - 0.5, -0.5)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.spines["left"].set_visible(False)


def _dot_handle(**kwargs):
    from matplotlib.lines import Line2D
    return Line2D([], [], marker="o", linestyle="none", markersize=style.MARKER, markeredgecolor=style.PAPER,
                  markeredgewidth=0.3, **kwargs)


def _panel_a(fig, rows, W, H):
    names = [TYPE_NAMES[t] for t in TYPES]
    colours = {WHOLE: style.CATEGORICAL[0], ALONE: style.CATEGORICAL[1], PAIRED: style.CATEGORICAL[2]}
    offsets = {WHOLE: -0.17, PAIRED: 0.0, ALONE: 0.17}
    top, h, w = ROW1_TOP, ROW1_H, 33.0
    lefts = (16.0, 16.0 + w + 5.0)
    for k, ((_, unit), left) in enumerate(zip(METRICS, lefts)):
        ax = _axes(fig, W, H, left, top - h, w, h)
        mine = [r for r in rows if r["unit"] == unit]
        ax.set_xlim(0, 100)
        ax.set_ylim(len(names) - 0.5, -0.5)
        ax.grid(axis="x", color=style.LINE, linewidth=0.5)
        ax.set_axisbelow(True)
        for y, name in enumerate(names):
            here = {(PAIRED if r["series"].startswith(PAIRED) else r["series"]): r["value"]
                    for r in mine if r["label"] == name}
            ax.plot([min(here.values()), max(here.values())], [y, y], color=style.LINE, linewidth=style.MARK_WIDTH,
                    zorder=1)
            for series in (WHOLE, PAIRED, ALONE):
                if series in here:
                    ax.plot([here[series]], [y + offsets[series]], "o", color=colours[series], markersize=style.MARKER,
                            markeredgecolor=style.PAPER, markeredgewidth=0.3, zorder=3)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names if k == 0 else [], fontsize=style.SIZE, color=style.INK_SOFT)
        ax.tick_params(axis="y", length=0, pad=2)
        ax.spines["left"].set_visible(False)
        ax.set_xlabel(unit[0].upper() + unit[1:], fontsize=style.SIZE_LABEL, labelpad=2)
        if k == 0:
            _title(ax, "a", "One type uploaded alone", 15.0, w, h, dy_mm=9.0)
    fig.legend(handles=[_dot_handle(color=colours[WHOLE], label=WHOLE), _dot_handle(color=colours[ALONE], label=ALONE),
                        _dot_handle(color=colours[PAIRED], label="with one other type")],
               loc="lower left", bbox_to_anchor=(lefts[0] / W - 0.012, (top + 1.0) / H), ncol=3, fontsize=style.SIZE,
               frameon=False, handletextpad=0.2, columnspacing=0.9, borderaxespad=0)
    pairs = sorted({r["series"][len(PAIRED):] for r in rows if r["series"].startswith(PAIRED)})
    words = "; ".join(" with ".join(TYPE_NAMES.get(t, t).lower() if t == "monocyte" else TYPE_NAMES.get(t, t)
                                    for t in pair.split("+")) for pair in pairs)
    fig.text(lefts[0] / W, (top - h - 10.5) / H, f"Pairs uploaded together: {words}", ha="left", va="top",
             fontsize=style.SIZE, color=style.INK_FAINT)


def _panel_b(fig, rows, W, H):
    from matplotlib.patches import Patch

    sets = []
    for r in rows:
        if r["series"] not in sets:
            sets.append(r["series"])
    greys = dict(zip([words for _, words in NO_ANSWER],
                     (style.INK_FAINT, style.NEUTRAL, _tint(style.NEUTRAL, 0.45), _tint(style.NEUTRAL, 0.75))))
    levels = ("lineage", "family", "type")
    blues = {LEVEL_WORDS[k]: style.LEVELS[k] for k in ("class", "group", "lineage")}
    dark = {style.INK_FAINT, style.NEUTRAL, style.LEVELS["class"], style.LEVELS["group"]}
    top, h, left, w = ROW1_TOP, ROW1_H, 112.0, 52.0
    ax = _axes(fig, W, H, left, top - h, w, h)
    ax.set_xlim(0, 100)
    ax.set_ylim(len(sets) - 0.5, -0.5)
    seen_grey, seen_blue = set(), set()
    for y, name in enumerate(sets):
        mine = [r for r in rows if r["series"] == name]
        cells = next(r["value"] for r in mine if r["label"] == "cells")
        x, answered = 0.0, 0
        for r in mine:
            if r["label"] == "cells":
                continue
            kind, what = r["label"].split(": ", 1)
            if kind == "no answer":
                colour = greys[what]
                seen_grey.add(what)
            else:
                level = kind.split(", ")[1]
                colour = blues[level]
                seen_blue.add(level)
                answered += r["value"]
            share = 100.0 * r["value"] / cells
            ax.barh([y], [share], left=[x], height=0.62, color=colour, edgecolor=style.PAPER, linewidth=0.6)
            if share >= 7.0:
                ax.text(x + share / 2, y, f"{r['value']:g}", ha="center", va="center", fontsize=style.SIZE,
                        color=style.PAPER if colour in dark else style.INK)
            x += share
        ax.text(1.0 + 1.5 / w, y, f"{answered:g} of {cells:g} answered", transform=ax.get_yaxis_transform(),
                ha="left", va="center", fontsize=style.SIZE, color=style.INK_SOFT)
    ax.set_yticks(range(len(sets)))
    ax.set_yticklabels(sets, fontsize=style.SIZE, color=style.INK_SOFT)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Share of the set's cells (%)", fontsize=style.SIZE_LABEL, labelpad=2)
    _title(ax, "b", "Foreign cells: what the served model says", 18.0, w, h, dy_mm=9.0)
    patch = dict(edgecolor="none")
    common_kw = dict(fontsize=style.SIZE, title_fontsize=style.SIZE, frameon=False, handlelength=1.0, handleheight=0.8,
                     handletextpad=0.4, columnspacing=1.0, borderaxespad=0, alignment="left")
    first = ax.legend(handles=[Patch(facecolor=greys[words], label=words, **patch)
                               for _, words in NO_ANSWER if words in seen_grey],
                      title="No answer", loc="upper left", bbox_to_anchor=(-18.0 / w, -11.0 / h), ncol=2, **common_kw)
    ax.add_artist(first)
    ax.legend(handles=[Patch(facecolor=blues[level], label=f"a {level}", **patch) for level in levels
                       if level in seen_blue],
              title="Answered with", loc="upper left", bbox_to_anchor=(1.0 + 1.5 / w, -11.0 / h), ncol=1, **common_kw)


def _panel_c(fig, rows, W, H):
    left, w = 25.0, 30.0
    ax = _axes(fig, W, H, left, ROW2_TOP - ROW2_H, w, ROW2_H)
    _hbars(ax, [r["label"] for r in rows], [r["value"] for r in rows], style.ACCENT, lambda v: f"{v:g}%")
    ax.set_xlim(0, max(r["value"] for r in rows) * 1.3)
    ax.set_xlabel("Share of the cluster's cells (%)", fontsize=style.SIZE_LABEL, labelpad=2)
    _title(ax, "c", "Khoury's CD8 T cluster, called as", 24.0, w, ROW2_H)


def _panel_d(fig, rows, W, H):
    left, w = 86.0, 34.0
    ax = _axes(fig, W, H, left, ROW2_TOP - ROW2_H, w, ROW2_H)
    rows = sorted(rows, key=lambda r: -r["value"])
    ys = list(range(len(rows)))
    ax.set_xlim(CHANCE - 0.02, 1.0)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.grid(axis="x", color=style.LINE, linewidth=0.5)
    ax.set_axisbelow(True)
    ax.axvline(CHANCE, color=style.NEUTRAL, linewidth=style.LINE_WIDTH)
    for y, r in zip(ys, rows):
        ax.plot([CHANCE, r["value"]], [y, y], color=style.INK_SOFT, linewidth=style.MARK_WIDTH, zorder=2)
        ax.plot([r["value"]], [y], "o", color=style.INK, markersize=style.MARKER, markeredgecolor=style.PAPER,
                markeredgewidth=0.3, zorder=3)
        ax.annotate(f"{r['value']:.2f}, {r['series']}", (CHANCE, y), xytext=(3, -6.0), textcoords="offset points",
                    ha="left", va="center", fontsize=style.SIZE, color=style.INK_SOFT)
    ax.set_yticks(ys)
    ax.set_yticklabels([r["label"] for r in rows], fontsize=style.SIZE, color=style.INK_SOFT)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("AUROC between the two clusters", fontsize=style.SIZE_LABEL, labelpad=2)
    _title(ax, "d", "What tells its T-cell clusters apart", 13.0, w, ROW2_H)


def _panel_e(fig, rows, W, H):
    left, w = 148.0, 32.0
    total = next(r for r in rows if r["series"] == "all")
    parts = [r for r in rows if r["series"] == "filed under"]
    ax = _axes(fig, W, H, left, ROW2_TOP - ROW2_H, w, ROW2_H)
    _hbars(ax, [r["label"] for r in parts], [r["value"] for r in parts], style.NEUTRAL, lambda v: f"{v:g}")
    ax.set_xlim(0, max(r["value"] for r in parts) * 1.22)
    ax.set_xlabel(f"Cells, of {total['value']:g} naive CD8-like", fontsize=style.SIZE_LABEL, labelpad=2)
    _title(ax, "e", "Reference's naive CD8-like cells, filed as", 16.0, w, ROW2_H)


def draw(rows, plt):
    W, H = style.WIDTHS_MM[WIDTH], 134.0
    fig = common.new_figure(plt, WIDTH, H)
    _panel_a(fig, [r for r in rows if r["panel"] == "a"], W, H)
    _panel_b(fig, [r for r in rows if r["panel"] == "b"], W, H)
    _panel_c(fig, [r for r in rows if r["panel"] == "c"], W, H)
    _panel_d(fig, [r for r in rows if r["panel"] == "d"], W, H)
    _panel_e(fig, [r for r in rows if r["panel"] == "e"], W, H)
    return fig
