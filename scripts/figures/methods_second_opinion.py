"""Methods illustration: the best guess and its second opinion. The two terms
of the fused best guess, the agreement gate that decides whether the second
opinion is used, and where the guess goes (a); the gate worked on the upload
the Workflow page traces (b).

The rule is service/pipeline/fusion.py's (best_guess_probabilities,
upload_agreement, the module docstring), as the page's procedures section
(#best-guess), service/model/MODEL_CARD.md (v4.1) and
docs/service/projection-api.md (v4.1) state it. Numbers: the settings from
web/data/manuscript.json (the page's records, from
service/model/v4_1/spec_v41.json), the worked example from
web/data/workflow.json (the served model's trace of PBMC240).
"""
from __future__ import annotations

from . import common, style

NAME = "methods-second-opinion"
TITLE = "Methods illustration: the second opinion"
SECTION = "best-guess"
WIDTH = "one-half"
ALT = ("Two panels. a: two terms feed the best guess. The encoder term is the members' probabilities with every "
       "type weighted equally, from the smoothed and unsmoothed views in equal shares. The second opinion is each "
       "cell's correlation with the type means over its own measured genes. A gate measures the upload's "
       "agreement, the share of its counted cells whose top correlation names the answer path's top type. At or "
       "above the bar, the guess mixes the encoder and the correlation; below it, the correlation term is flat "
       "and the encoder decides. The guess then joins every non-empty set. b: the gate worked on the upload the "
       "Workflow page traces: a bar showing the share of counted cells that agree, ending short of the bar line, "
       "so the term is flat.")
CAPTION = ("a, The fused best guess. The encoder term averages the members' probabilities against type centroids "
           "re-encoded with every type weighted equally, half from the smoothed view of the upload and half from "
           "the unsmoothed one. The second opinion is each cell's Pearson correlation with the type means of the "
           "z-scored RNA, every type weighted equally, over the cell's own measured, unsmoothed genes, turned into "
           "probabilities by a softmax at a fixed temperature. The gate counts the upload's cells with at least "
           "the floor's observed genes and asks what share of them have the same top type under the correlation "
           "as under the answer path. At or above the bar, the guess weights the encoder by the chosen weight and "
           "gives the rest to the correlation; below it, the encoder's smoothed view alone decides, against a flat "
           "term. Either way, the guess joins every non-empty conformal set beside the answer path's top type. "
           "b, The gate on the Workflow page's example upload, as traced from the served model: the share of "
           "counted cells that agree, against the bar.")
SOURCES = (
    "web/data/manuscript.json",
    "web/data/workflow.json",
)

MANUSCRIPT, WORKFLOW = SOURCES


def data() -> list[dict]:
    records = common.read_json(MANUSCRIPT)["records"]
    w = common.read_json(WORKFLOW)
    rows = []
    for key, label, unit in (("wf_agreement_threshold", "bar", "share of counted cells"),
                             ("wf_weight_used", "encoder weight, term used", "weight"),
                             ("wf_weight_flat", "encoder weight, term flat", "weight"),
                             ("wf_smoothed_share", "smoothed share", "share"),
                             ("wf_correlation_temperature", "correlation temperature", "temperature"),
                             ("wf_floor", "observed genes, floor", "genes")):
        rows.append(common.row("a", label, common.measured(records[key]), unit=unit, source=MANUSCRIPT,
                               field=f"records.{key}.value"))
    facts = w["facts"]
    for key, label, unit in (("runs", "cells", "cells"), ("below_floor", "below the floor", "cells"),
                             ("counted", "counted", "cells"), ("agreeing", "agreeing", "cells"),
                             ("agreement", "agreement", "share of counted cells"),
                             ("agreement_threshold", "bar", "share of counted cells")):
        rows.append(common.row("b", label, common.measured(facts[key]), series="PBMC240", unit=unit,
                               source=WORKFLOW, field=f"facts.{key}.value"))
    rows.append(common.row("b", w["trace"]["stages"]["fusion"]["correlation_term"], None, series="PBMC240",
                           unit="correlation term", source=WORKFLOW, field="trace.stages.fusion.correlation_term"))
    return rows


# ---- drawing ----

def _count(v) -> str:
    return f"{int(v):,}"


def _share(v) -> str:
    return f"{v * 100:.1f}".removesuffix(".0") + "%"


def _plain(v) -> str:
    return f"{v:g}"


def _card(ax, x, y, w, h, heading, lines, *, edge=style.INK, line=style.LINE_WIDTH, fill=style.PAPER,
          heading_colour=style.INK):
    common.box(ax, x, y, w, h, fill=fill, edge=edge, line=line)
    n = 1 + len(lines)
    step = 3.1
    top = y + h / 2 + (n - 1) * step / 2
    common.note(ax, x + w / 2, top, heading, ha="center", size=style.SIZE_LABEL, colour=heading_colour,
                weight="bold")
    for i, text in enumerate(lines):
        common.note(ax, x + w / 2, top - (i + 1) * step, text, ha="center", colour=style.INK_SOFT)


def draw(rows, plt):
    W, H = style.WIDTHS_MM[WIDTH], 110.0
    fig = common.new_figure(plt, WIDTH, H)
    ax = common.canvas(fig, W, H)
    a = {r["label"]: r["value"] for r in rows if r["panel"] == "a"}
    b = {r["label"]: r["value"] for r in rows if r["panel"] == "b" and r["value"] is not None}
    term = [r["label"] for r in rows if r["panel"] == "b" and r["unit"] == "correlation term"][0]

    def heading(x, y, letter, text):
        common.note(ax, x, y, letter, size=style.SIZE_LETTER, colour=style.INK, weight="bold", va="baseline")
        common.note(ax, x + 4.2, y, text, size=style.SIZE_TITLE, colour=style.INK, va="baseline")

    # ---- a: the rule, top to bottom ----
    top = H - 4.0
    heading(2.0, top, "a", "Two terms, one gate")
    half = (W - 4.0 - 8.0) / 2                  # two columns, 8 mm apart
    lx, rx = 2.0, 2.0 + half + 8.0
    lc, rc = lx + half / 2, rx + half / 2
    lh = 17.0
    ty = top - 5.0 - lh
    _card(ax, lx, ty, half, lh, "Encoder term",
          ("the members' probabilities against type", "centroids, every type weighted equally;",
           "smoothed and unsmoothed views,", f"{_share(a['smoothed share'])} each"))
    _card(ax, rx, ty, half, lh, "Second opinion",
          ("each cell's Pearson correlation with the", "type means, over its own measured,",
           "unsmoothed genes; softmax at", f"temperature {_plain(a['correlation temperature'])}"))
    # the gate, on the second opinion's side
    gh = 19.0
    gy = ty - 6.0 - gh
    common.box(ax, rx, gy, half, gh, fill=style.FIELD, edge=style.FIELD)
    gate = ("The gate: the upload's agreement",
            "the share of its counted cells (at least",
            f"{_count(a['observed genes, floor'])} observed genes) whose top correlation",
            "names the answer path's top type",
            f"at or above {_share(a['bar'])}?")
    yy = gy + gh - 3.4
    for i, text in enumerate(gate):
        strong = i in (0, len(gate) - 1)
        common.note(ax, rc, yy, text, ha="center", size=style.SIZE_LABEL if strong else style.SIZE,
                    colour=style.INK if strong else style.INK_SOFT, weight="bold" if i == 0 else "normal")
        yy -= 3.4 if i in (0, len(gate) - 2) else 3.0
    common.arrow(ax, (rc, ty - 0.4), (rc, gy + gh + 0.4))
    common.note(ax, rx - 2.0, gy + gh / 2 + 2.4, "each cell's top type\non the answer path", ha="right",
                colour=style.INK_FAINT)
    common.arrow(ax, (rx - 15.0, gy + gh / 2 - 1.6), (rx - 0.6, gy + gh / 2 - 1.6), line=style.LINE_WIDTH,
                 head=4.0, colour=style.INK_FAINT)
    # the best guess, as the gate decides
    bh = 15.0
    by = gy - 6.0 - bh
    common.box(ax, lx, by, W - 4.0, bh, fill=style.PAPER)
    common.note(ax, lx + 3.0, by + bh - 3.4, "The best guess", size=style.SIZE_LABEL, colour=style.INK,
                weight="bold")
    lines = (
        ("at or above the bar, used:", style.ACCENT,
         f"weight {_plain(a['encoder weight, term used'])} on the encoder, the rest on the correlation"),
        ("below the bar, flat:", style.INK,
         f"weight {_plain(a['encoder weight, term flat'])} on the encoder's smoothed view, against a flat term; "
         "the encoder decides"),
    )
    yy = by + bh - 7.6
    for lead, colour, rest in lines:
        common.note(ax, lx + 3.0, yy, lead, colour=colour)
        common.note(ax, lx + 34.0, yy, rest, colour=style.INK_SOFT)
        yy -= 3.6
    common.arrow(ax, (lc, ty - 0.4), (lc, by + bh + 0.4))
    common.arrow(ax, (rc, gy - 0.4), (rc, by + bh + 0.4))
    # where the guess goes
    jh = 7.0
    jy = by - 5.0 - jh
    common.box(ax, lx, jy, W - 4.0, jh, "It joins every non-empty conformal set, beside the answer path's top type",
               fill=style.PAPER, size=style.SIZE)
    common.arrow(ax, (W / 2, by - 0.4), (W / 2, jy + jh + 0.4))

    # ---- b: the gate, worked ----
    btop = jy - 7.5
    heading(2.0, btop, "b", "The gate on the Workflow page's example, PBMC240")
    common.note(ax, 6.2, btop - 3.6,
                f"{_count(b['cells'])} cells; {_count(b['below the floor'])} below the floor, "
                f"so {_count(b['counted'])} counted; {_count(b['agreeing'])} of them agree",
                colour=style.INK_SOFT)
    left, right = 6.2, W - 30.0
    bar_y, bar_h = btop - 14.0, 5.0
    span = right - left
    common.box(ax, left, bar_y, span, bar_h, fill=style.WELL, edge=style.WELL, radius=0.6)
    common.box(ax, left, bar_y, span * b["agreement"], bar_h, fill=style.ACCENT, edge=style.ACCENT, radius=0.6)
    common.note(ax, left + span * b["agreement"] - 1.2, bar_y + bar_h / 2, f"agreement {_share(b['agreement'])}",
                ha="right", colour=style.PAPER)
    x_bar = left + span * b["bar"]
    ax.plot([x_bar, x_bar], [bar_y - 1.6, bar_y + bar_h + 1.6], color=style.NEUTRAL, lw=style.MARK_WIDTH,
            solid_capstyle="butt")
    common.note(ax, x_bar + 1.0, bar_y + bar_h + 1.2, f"bar {_share(b['bar'])}", colour=style.INK_FAINT)
    common.note(ax, right, bar_y - 2.4, "all counted cells", ha="right", colour=style.INK_FAINT)
    side = "below the bar" if b["agreement"] < b["bar"] else "at or above the bar"
    common.note(ax, right + 3.0, bar_y + bar_h / 2 + 1.6, f"term {term}", colour=style.INK, size=style.SIZE_LABEL)
    common.note(ax, right + 3.0, bar_y + bar_h / 2 - 1.8, side, colour=style.INK_FAINT)
    return fig
