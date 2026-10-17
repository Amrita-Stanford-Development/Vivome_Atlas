"""Methods illustration: the answer layer. From the members' views of one cell
to its answer: the checks in the order the service makes them, the set and
the level it supports (a), and the bar each type must clear to join a set,
with the families and lineages that set an answer's level (b).

The order and the rules are service/pipeline/abstention.py's (score_abstention:
coverage floor, then out of distribution, then an empty set),
service/pipeline/calibration.py's (MondrianCalibrator: a type joins a set when
its probability is at least one minus its qhat; a non-empty set also takes the
answer path's top type and the fused best guess) and
service/pipeline/ensemble.py's (resolve: one type, one family, one lineage, or
ambiguous), as the page's procedures section (#answers) and
docs/service/projection-api.md (v3.1) state them. The answer looks are the
Atlas page's (style.LEVELS; web/js/atlas/atlas-panels.js, the key), with the
page's words: a type, a family, a lineage (the Atlas page's branch).

Numbers: the thresholds per type and the hierarchy from web/data/workflow.json
(the served model's trace), the floor, the out-of-distribution threshold, the
target coverage and the marginal threshold from web/data/manuscript.json.
Type names are the site's plain names (web/js/workflow-data.js, PLAIN_NAMES).
"""
from __future__ import annotations

import re

from . import common, style

NAME = "methods-answers"
TITLE = "Methods illustration: the answer layer"
SECTION = "answers"
WIDTH = "double"
ALT = ("Two panels. a: a flow from one cell, read by the members, to its answer. Three checks in order: enough "
       "observed genes, else no answer because too little was measured; enough similarity to the reference "
       "cells, else no answer because the cell is outside the supported region; at least one type clearing its "
       "bar, else no answer because no type stands out. The set then also takes the answer path's top type and "
       "the fused best guess, and its types decide the level: one type, a family, a lineage, or no answer because "
       "several types fit. Each outcome is drawn in the Atlas page's answer look. b: every reference type, "
       "grouped by lineage and family, with a dot at the probability it needs to join a set, and a grey line at "
       "the threshold shared by all types.")
CAPTION = ("a, How the answer layer treats one cell, in the order the service checks it. A cell with too few "
           "observed genes gets no answer and no best guess. A cell whose members' mean best cosine to the "
           "reference cells is below the out-of-distribution threshold is outside the supported region. "
           "Otherwise every type competes, and a type joins the cell's conformal set when its ensemble probability "
           "clears that type's bar; with no type in the set, no type stands out. A non-empty set also takes the "
           "answer path's top type and the fused best guess, and the answer is stated at the level the set's "
           "types share. Boxes take the Atlas page's looks: one type filled, a family paler in a dark ring, a "
           "lineage paler still, no answer a grey ring, broken when too little was measured. b, Each type's bar: "
           "the probability it needs to join a set, one minus its conformal threshold, fitted once on labelled "
           "RNA uploads (the per-class, Mondrian, sets). The grey line is the marginal threshold, one shared bar, "
           "shown for comparison. Types are grouped by lineage (headers) and family (brackets); a family or lineage "
           "answer names one of these groups.")
SOURCES = (
    "web/data/workflow.json",
    "web/data/manuscript.json",
    "web/js/workflow-data.js",
)

WORKFLOW, MANUSCRIPT, PLAIN = SOURCES


def _plain_names() -> dict:
    """The site's plain type names (PLAIN_NAMES in web/js/workflow-data.js)."""
    text = (common.REPO / PLAIN).read_text(encoding="utf-8")
    block = re.search(r"export const PLAIN_NAMES = \{(.*?)\n\};", text, re.S).group(1)
    return {(a or b): c for a, b, c in re.findall(r"(?:'([^']+)'|([A-Za-z]+)): '([^']+)'", block)}


def data() -> list[dict]:
    w = common.read_json(WORKFLOW)
    records = common.read_json(MANUSCRIPT)["records"]
    rows = []
    for key, label, unit in (("wf_members", "members", "members"), ("ref_classes", "types", "types"),
                             ("wf_floor", "observed genes, floor", "genes"),
                             ("wf_ood_threshold", "similarity, threshold", "cosine"),
                             ("coverage_target", "target coverage", "share")):
        rows.append(common.row("a", label, common.measured(records[key]), unit=unit, source=MANUSCRIPT,
                               field=f"records.{key}.value"))

    plain = _plain_names()
    names = w["class_order"]
    qhat = w["trace"]["stages"]["calibration"]["qhat"]
    for i, (name, q, c) in enumerate(zip(names, qhat, w["reference"]["classes"])):
        if c["name"] != name:
            raise ValueError(f"{WORKFLOW}: reference.classes is not in class_order at {i}")
        rows.append(common.row("b", f"{c['lineage']} > {c['group']} > {plain.get(name, name)}", q, series="type",
                               unit="qhat (joins a set at probability 1 - qhat or more)", source=WORKFLOW,
                               field=f"trace.stages.calibration.qhat[{i}], {name}"))
    rows.append(common.row("b", "marginal", common.measured(records["qhat_marginal"]), series="marginal",
                           unit="qhat", source=MANUSCRIPT, field="records.qhat_marginal.value"))
    return rows


# ---- drawing ----

def _count(v) -> str:
    return f"{int(v):,}"


def _share(v) -> str:
    return f"{v * 100:.1f}".removesuffix(".0") + "%"


LOOKS = {   # the Atlas page's answer looks: (fill, edge, text, line, dashed)
    "class": (style.LEVELS["class"], style.LEVELS["class"], style.PAPER, style.LINE_WIDTH, False),
    "group": (style.LEVELS["group"], style.INK, style.INK, style.MARK_WIDTH, False),
    "lineage": (style.LEVELS["lineage"], style.LEVELS["lineage"], style.INK, style.LINE_WIDTH, False),
    "none": (style.PAPER, style.LEVELS["none"], style.INK_SOFT, style.MARK_WIDTH, False),
    "unplaced": (style.PAPER, style.LEVELS["none"], style.INK_SOFT, style.MARK_WIDTH, True),
}


def _outcome(ax, x, y, w, h, text, look):
    fill, edge, ink, line, dashed = LOOKS[look]
    patch = common.box(ax, x, y, w, h, text, fill=fill, edge=edge, text_colour=ink, size=style.SIZE, line=line)
    if dashed:
        patch.set_linestyle((0, (2.2, 1.6)))
    return patch


def _step(ax, x, y, w, h, heading, sub=""):
    common.box(ax, x, y, w, h, fill=style.PAPER)
    if sub:
        lines = sub.split("\n")
        step = 3.3
        top = y + h / 2 + len(lines) * step / 2
        common.note(ax, x + w / 2, top, heading, ha="center", size=style.SIZE_LABEL, colour=style.INK,
                    weight="bold")
        for i, text in enumerate(lines):
            common.note(ax, x + w / 2, top - (i + 1) * step, text, ha="center", colour=style.INK_SOFT)
    else:
        common.note(ax, x + w / 2, y + h / 2, heading, ha="center", size=style.SIZE_LABEL, colour=style.INK,
                    weight="bold")


def draw(rows, plt):
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    W, H = style.WIDTHS_MM[WIDTH], 96.0
    fig = common.new_figure(plt, WIDTH, H)
    ax = common.canvas(fig, W, H)
    get = {r["label"]: r["value"] for r in rows if r["panel"] == "a"}

    def heading(x, y, letter, text):
        common.note(ax, x, y, letter, size=style.SIZE_LETTER, colour=style.INK, weight="bold", va="baseline")
        common.note(ax, x + 4.2, y, text, size=style.SIZE_TITLE, colour=style.INK, va="baseline")

    def yes_no(x, y, text, ha="left"):
        common.note(ax, x, y, text, ha=ha, colour=style.INK_FAINT)

    # ---- a: the flow ----
    top = H - 4.0
    heading(2.0, top, "a", "From the members' views of one cell to its answer")
    sx, sw = 2.0, 60.0          # the spine
    ox, ow = 67.0, 27.0         # the outcomes beside it
    cx = sx + sw / 2
    sh, gap = 9.0, 4.2

    y = top - 4.0 - sh
    common.box(ax, sx, y, sw, sh, fill=style.FIELD, edge=style.FIELD)
    common.note(ax, cx, y + sh / 2 + 1.6, f"One cell, read by the {_count(get['members'])} members",
                ha="center", size=style.SIZE_LABEL, colour=style.INK, weight="bold")
    common.note(ax, cx, y + sh / 2 - 1.9, "observed genes, similarity, type probabilities", ha="center",
                colour=style.INK_FAINT)

    checks = (
        (f"At least {_count(get['observed genes, floor'])} observed genes?", "",
         "No answer and\nno best guess:\ntoo little measured", "unplaced", ""),
        (f"Similarity at least {get['similarity, threshold']:.3f}?",
         "the members' mean best cosine to reference cells",
         "No answer:\noutside the\nsupported region", "none", ""),
        ("Does any type clear its own bar (b)?",
         f"all {_count(get['types'])} types compete; target coverage {_share(get['target coverage'])}",
         "No answer:\nno type stands out", "none", ""),
    )
    for k, (question, sub, out_text, look, out_note) in enumerate(checks):
        prev = y
        y = prev - gap - sh
        common.arrow(ax, (cx, prev - 0.3), (cx, y + sh + 0.3))
        if k:
            yes_no(cx + 1.8, prev - gap / 2, "yes")
        _step(ax, sx, y, sw, sh, question, sub)
        oh = sh + (2.6 if out_text.count("\n") > 1 else 0.0)
        _outcome(ax, ox, y + sh / 2 - oh / 2, ow, oh, out_text, look)
        common.arrow(ax, (sx + sw + 0.3, y + sh / 2), (ox - 0.5, y + sh / 2))
        yes_no((sx + sw + ox) / 2, y + sh / 2 + 2.4, "no", ha="center")
        if out_note:
            common.note(ax, ox + ow / 2, y + sh / 2 - oh / 2 - 1.6, out_note, ha="center", colour=style.INK_FAINT)
    # the set, completed
    prev = y
    set_h = sh + 2.6
    y = prev - gap - set_h
    common.arrow(ax, (cx, prev - 0.3), (cx, y + set_h + 0.3))
    yes_no(cx + 1.8, prev - gap / 2, "yes")
    _step(ax, sx, y, sw, set_h, "The set",
          "the types that clear their bars, plus the answer\npath's top type and the fused best guess")
    # the level its types share
    fan = (("one type", "One type", "class"), ("one family", "A family", "group"),
           ("one lineage", "A lineage", "lineage"), ("otherwise", "No answer:\nseveral types fit", "none"))
    fw, fgap, fh = 21.5, 2.6, 8.0
    fy = 2.0
    total = len(fan) * fw + (len(fan) - 1) * fgap
    fx0 = (sx + ox + ow) / 2 - total / 2
    centres = [fx0 + i * (fw + fgap) + fw / 2 for i in range(len(fan))]
    bus = y - 3.0
    ax.plot([cx, cx], [y, bus], color=style.INK, lw=style.MARK_WIDTH, solid_capstyle="butt")
    ax.plot([centres[0], centres[-1]], [bus, bus], color=style.INK, lw=style.MARK_WIDTH, solid_capstyle="butt")
    for c, (cond, text, look) in zip(centres, fan):
        _outcome(ax, c - fw / 2, fy, fw, fh, text, look)
        common.arrow(ax, (c, bus), (c, fy + fh + 0.3))
        common.note(ax, c, (bus + fy + fh) / 2, cond, ha="center", colour=style.INK_SOFT).set_bbox(
            dict(facecolor=style.PAPER, edgecolor="none", pad=0.8))

    # ---- b: the bars, by lineage and family ----
    bx0 = 101.0
    heading(bx0, top, "b", "The bar each type must clear")
    types = [r for r in rows if r["series"] == "type"]
    marginal = [r for r in rows if r["series"] == "marginal"][0]["value"]
    paths = [r["label"].split(" > ") for r in types]
    order, seen = [], {}
    for lineage, group, _ in paths:            # lineages, then families, by first appearance
        seen.setdefault(lineage, {}).setdefault(group, None)
    for lineage, groups in seen.items():
        order.append(("lineage", lineage, None))
        for group in groups:
            for r, (lin, grp, name) in zip(types, paths):
                if lin == lineage and grp == group:
                    order.append(("type", (lin, grp, name), r["value"]))
    row_h = 2.72
    y_top, y_axis = top - 5.5, 12.0
    row_h = min(row_h, (y_top - y_axis) / len(order))
    fam_r = bx0 + 25.0                          # family labels end here
    name_x = fam_r + 3.0                       # type names start here
    strip_l, strip_r = bx0 + 60.0, W - 3.0     # the dot strip
    ys = [y_top - (i + 0.5) * row_h for i in range(len(order))]
    strip = fig.add_axes((strip_l / W, y_axis / H, (strip_r - strip_l) / W, (y_top - y_axis) / H))
    strip.set_xlim(0, 1)
    strip.set_ylim(y_axis, y_top)
    strip.set_yticks([])
    strip.spines["left"].set_visible(False)
    strip.xaxis.set_major_locator(MaxNLocator(2))
    strip.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    strip.set_xlabel("probability a type needs\nto join a set", fontsize=style.SIZE, color=style.INK_SOFT,
                     labelpad=2)
    strip.patch.set_alpha(0)
    xs = [1 - marginal] * 2
    strip.plot(xs, [y_axis, y_top], color=style.NEUTRAL, lw=style.LINE_WIDTH, zorder=1)
    strip.text(1 - marginal + 0.03, y_top - 0.2, "marginal", ha="left", va="top", fontsize=style.SIZE,
               color=style.INK_FAINT)
    block_start, last_group = None, None

    def bracket(first, last, group):
        common.note(ax, fam_r, ys[first], group, ha="right", colour=style.INK_SOFT)
        if last > first:
            ax.plot([fam_r + 1.4] * 2, [ys[first] + row_h * 0.35, ys[last] - row_h * 0.35],
                    color=style.LEVELS["group"], lw=style.MARK_WIDTH, solid_capstyle="butt")

    for i, (kind, item, q) in enumerate(order):
        if kind == "lineage":
            if last_group is not None:
                bracket(block_start, i - 1, last_group)
            last_group = None
            common.note(ax, bx0 + 2.0, ys[i] - 0.15, f"lineage: {item}", colour=style.INK, weight="bold")
            ax.plot([bx0 + 2.0, strip_r], [ys[i] - row_h * 0.5] * 2, color=style.LEVELS["lineage"],
                    lw=style.LINE_WIDTH, solid_capstyle="butt")
            continue
        lineage, group, name = item
        if group != last_group:
            if last_group is not None:
                bracket(block_start, i - 1, last_group)
            block_start, last_group = i, group
        common.note(ax, name_x, ys[i], name, colour=style.INK)
        strip.plot([0, 1], [ys[i]] * 2, color=style.LINE, lw=0.5, zorder=0)
        strip.plot([1 - q], [ys[i]], "o", ms=style.MARKER, color=style.INK, zorder=2, clip_on=False)
    bracket(block_start, len(order) - 1, last_group)
    return fig
