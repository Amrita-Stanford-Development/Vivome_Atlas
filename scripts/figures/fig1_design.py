"""Figure 1: the design at a glance (the Manuscript page's Experimental
procedures). What training fixes once, on RNA (the reference, the shared
gene list, the members, the parts kept fixed), and the path one uploaded
cell takes through the online service: the website's door, reading the
upload, the members placing it in the shared space and on the atlas map,
the answer layer, the best guess with its second opinion and gate, and the
answer as JSON.

Every component and its name is one the procedures sections describe
(#reference, #gene-space, #processing, #encoder, #answers, #best-guess,
#implementation); every number is a web/data/manuscript.json record, the
same one the page's text shows.
"""
from __future__ import annotations

from . import common, style

NAME = "fig1-design"
TITLE = "Figure 1"
SECTION = "procedures"
WIDTH = "double"

MANUSCRIPT = "web/data/manuscript.json"
SOURCES = (MANUSCRIPT,)

ALT = ("A schematic in two parts. a, training, done once and on RNA only: the RNA reference of blood cells, "
       "read over the shared gene list drawn from proteomics gene lists, trains the members of the encoder, "
       "and the parts the service keeps fixed follow from them: the type centroids, the atlas map, one "
       "threshold per type and the type means. Nothing is fitted on the user's upload. b, the path one "
       "uploaded cell takes, drawn in blue: a protein or RNA matrix comes in through the website's door to "
       "the online service, is read onto the shared gene list, and the members place the cell in the shared "
       "space, one of them also on the atlas map. The answer layer names one type, a family or a lineage, or gives no "
       "answer with its reason. Below it, a second opinion, the cell's correlation to the type means, enters "
       "the best guess only when enough of the file's cells agree with the encoder, and the best guess joins "
       "the set. The answer goes back as JSON. Dashed lines show what training hands to the service.")
CAPTION = ("The design at a glance. a, Training, done once and on RNA only: the RNA reference, read over the "
           "shared gene list (pooled from proteomics gene lists), trains the encoder's members; the type "
           "centroids, the atlas map, one conformal threshold per type and the type means are fixed before any "
           "upload, and nothing is fitted on the user's upload. b, The path one uploaded cell takes through the "
           "online service (blue): in through the website's door, the upload is read onto the shared gene list "
           "(Methods illustration: reading an upload), the members place the cell in the shared space (one of "
           "them also on the atlas map), and the answer layer states one type, a family or a lineage, or no "
           "answer with its reason. The best guess takes the second opinion, a correlation to the type means over the cell's "
           "measured genes, only when the file passes the agreement gate, and it joins the cell's set. Each "
           "cell's answer goes back as JSON. Dashed lines: what training hands to the service. A schematic: "
           "the numbers are the served model's settings.")


def _value(records: dict, key: str):
    value = common.measured(records[key])
    if value is None:
        raise ValueError(f"{MANUSCRIPT}: records.{key} is not measured")
    return value


# (panel, label, record key, unit): every number the picture shows.
NUMBERS = (
    ("a", "reference cells", "ref_cells", "cells"),
    ("a", "reference types", "ref_classes", "types"),
    ("a", "families", "ref_groups", "families"),
    ("a", "lineages", "ref_lineages", "lineages"),
    ("a", "shared gene list", "gs_size", "genes"),
    ("a", "proteomics gene lists", "gs_sources", "lists"),
    ("a", "members", "wf_members", "members"),
    ("b", "most cells per upload", "wf_service_max_cells", "cells"),
    ("b", "shared space", "wf_latent", "dimensions"),
    ("b", "target coverage", "coverage_target", "share"),
    ("b", "agreement gate", "wf_agreement_threshold", "share"),
    ("b", "encoder weight at the gate", "wf_weight_used", "weight"),
)


def data() -> list[dict]:
    records = common.read_json(MANUSCRIPT)["records"]
    return [common.row(panel, label, _value(records, key), unit=unit, source=MANUSCRIPT,
                       field=f"records.{key}.value")
            for panel, label, key, unit in NUMBERS]


# ---- drawing ----

W, H = style.WIDTHS_MM[WIDTH], 106.0
PAD = 4.4          # mm from a box's top to its title's baseline
TITLE_STEP = 1.6   # mm from the title's baseline to the body's top
LINE = 3.1         # mm per line of body text


def _fmt(r: dict) -> str:
    value = r["value"]
    if r["unit"] == "share":
        pct = value * 100
        return f"{pct:.0f}%" if abs(pct - round(pct)) < 1e-9 else f"{pct:.1f}%"
    if r["unit"] == "weight":
        return f"{value:g}"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}"


def _card(ax, x, y, w, h, title, body="", *, fill=style.PAPER, edge=style.INK):
    """A box with a bold title and a softer body under it, both centred."""
    common.box(ax, x, y, w, h, fill=fill, edge=edge)
    baseline = y + h - PAD
    common.note(ax, x + w / 2, baseline, title, size=style.SIZE_LABEL, colour=style.INK, ha="center",
                va="baseline", weight="bold")
    if body:
        common.note(ax, x + w / 2, baseline - TITLE_STEP, body, colour=style.INK_SOFT, ha="center", va="top")


def _connector(ax, x, y_from, y_to):
    """What training hands to the service: a quiet dashed arrow, top to bottom."""
    common.arrow(ax, (x, y_from), (x, y_to), colour=style.NEUTRAL, line=style.LINE_WIDTH, head=4.0, dashed=True)


def _path(ax, start, end):
    """The uploaded cell's path."""
    common.arrow(ax, start, end, colour=style.ACCENT, line=style.MARK_WIDTH)


def _swatch(ax, x, y, colour, text):
    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle((x, y - 1.1), 2.2, 2.2, facecolor=colour, edgecolor="none"))
    common.note(ax, x + 3.4, y, text, colour=style.INK)


def _key(ax, x, y, text, *, colour, dashed=False):
    ax.plot((x, x + 5.0), (y, y), color=colour, linewidth=style.LINE_WIDTH if dashed else style.MARK_WIDTH,
            linestyle="--" if dashed else "-", solid_capstyle="butt")
    common.note(ax, x + 6.5, y, text, colour=style.INK_SOFT)


def _heading(ax, x, y, letter, text):
    common.note(ax, x, y, letter, size=style.SIZE_LETTER, colour=style.INK, weight="bold", va="baseline")
    common.note(ax, x + 4.2, y, text, size=style.SIZE_TITLE, colour=style.INK, va="baseline")


def draw(rows, plt):
    n = {r["label"]: _fmt(r) for r in rows}
    fig = common.new_figure(plt, WIDTH, H)
    ax = common.canvas(fig, W, H)

    # Columns shared by both rows, so what training fixes sits above where the service uses it.
    reading_x, reading_w = 42.0, 29.0
    members_x, members_w = 77.0, 30.0
    answer_x, answer_w = 113.0, 44.0
    json_x, json_w = 161.5, 26.0

    # a: trained once, on RNA
    _heading(ax, 2.0, H - 4.5, "a", "Trained once, on RNA")
    a_y, a_h = 78.0, 18.0
    a_mid = a_y + a_h / 2
    _card(ax, 2.0, a_y, 36.0, a_h, "RNA reference",
          f"Tabula Sapiens blood\n{n['reference cells']} cells, {n['reference types']} types\n"
          f"in {n['families']} families, {n['lineages']} lineages", fill=style.WELL)
    _card(ax, reading_x, a_y, reading_w, a_h, "Shared gene list",
          f"{n['shared gene list']} genes from\n{n['proteomics gene lists']} proteomics\ngene lists", fill=style.WELL)
    _card(ax, members_x, a_y, members_w, a_h, f"{n['members']} members",
          "one architecture,\ntrained on RNA only", fill=style.WELL)
    _card(ax, answer_x, a_y, answer_w, a_h, "Fixed in advance",
          "type centroids, the atlas map,\none threshold per type,\nthe type means", fill=style.WELL)
    # the reference is read over the gene list: two inputs, so a plus, then the steps that follow
    common.note(ax, (38.0 + reading_x) / 2, a_mid, "+", size=style.SIZE_TITLE + 2, colour=style.INK, ha="center",
                weight="bold")
    for x0, x1 in ((reading_x + reading_w, members_x), (members_x + members_w, answer_x)):
        common.arrow(ax, (x0, a_mid), (x1, a_mid), colour=style.INK, line=style.LINE_WIDTH, head=4.0)
    common.note(ax, json_x + 1.0, a_mid, "Nothing is fitted\non the user's upload.", colour=style.INK_SOFT)

    # b: one uploaded cell, through the online service
    _heading(ax, 2.0, 70.0, "b", "One uploaded cell")
    _key(ax, 2.0, 64.5, "its path", colour=style.ACCENT)
    _key(ax, 2.0, 60.5, "from training", colour=style.NEUTRAL, dashed=True)
    frame_x = 31.0
    common.box(ax, frame_x, 2.0, W - 0.5 - frame_x, 64.0, fill=style.FIELD, edge=style.FIELD, radius=2.4)
    common.note(ax, W - 2.5, 6.5, "Online service,\non Google Cloud Run", colour=style.INK_SOFT, ha="right")

    row_y, row_h = 32.0, 25.0
    mid = row_y + row_h / 2
    _card(ax, 2.0, row_y, 19.0, row_h, "Upload", f"protein or\nRNA matrix,\nup to {n['most cells per upload']}\ncells")
    door_x, door_w = 24.5, 13.0
    _card(ax, door_x, row_y + 3.0, door_w, row_h - 6.0, "Door", "the\nwebsite's\n/api")
    _card(ax, reading_x, row_y, reading_w, row_h, "Reading",
          "matched to the shared\ngene list, linear\nvalues to log2, scaled\nwithin the file,\nsmoothed, with a mask")
    _card(ax, members_x, row_y, members_w, row_h, f"{n['members']} members",
          f"each places the cell\nin the shared space\n({n['shared space']} dimensions);\none, on the atlas map")

    ans_y, ans_h = 27.0, 37.5
    _card(ax, answer_x, ans_y, answer_w, ans_h, "Answer layer",
          f"conformal sets, one threshold\nper type, target coverage {n['target coverage']}")
    sw_x = answer_x + 3.0
    sw_top = ans_y + ans_h - PAD - TITLE_STEP - 2 * LINE - 2.6
    for i, (level, text) in enumerate((("class", "one type"), ("group", "a family"), ("lineage", "a lineage"),
                                       ("none", "no answer, with its reason:"))):
        _swatch(ax, sw_x, sw_top - i * 3.5, style.LEVELS[level], text)
    common.note(ax, sw_x + 3.4, sw_top - 3 * 3.5 - 1.8,
                "too little measured, outside\nthe supported region, no type\nstands out, several types fit",
                colour=style.INK_FAINT, va="top")
    _card(ax, json_x, row_y, json_w, row_h, "Answer as JSON",
          "each cell's answer,\nits level and set,\nthe best guess, its\nsimilarity, and the\nreason for none")

    # the second opinion and its gate, under the answer path
    low_y, low_h = 4.0, 13.5
    so_x, so_w = reading_x, 50.0
    gate_x = so_x + so_w + 6.0
    gate_w = answer_x + answer_w - gate_x
    _card(ax, so_x, low_y, so_w, low_h, "Second opinion",
          "correlation to the type means\nover the cell's measured genes")
    _card(ax, gate_x, low_y, gate_w, low_h, "Agreement gate",
          f"at least {n['agreement gate']}: encoder weight {n['encoder weight at the gate']};\n"
          "below it, the encoder alone")

    # the cell's path, in the accent
    _path(ax, (21.0, mid), (door_x, mid))
    _path(ax, (door_x + door_w, mid), (reading_x, mid))
    _path(ax, (reading_x + reading_w, mid), (members_x, mid))
    _path(ax, (members_x + members_w, mid), (answer_x, mid))
    _path(ax, (answer_x + answer_w, mid), (json_x, mid))
    _path(ax, (reading_x + 8.0, row_y), (reading_x + 8.0, low_y + low_h))
    _path(ax, (so_x + so_w, low_y + low_h / 2), (gate_x, low_y + low_h / 2))
    _path(ax, (members_x + members_w - 4.0, row_y), (members_x + members_w - 4.0, low_y + low_h))
    join_x = answer_x + answer_w - 8.0
    _path(ax, (join_x, low_y + low_h), (join_x, ans_y))
    common.note(ax, join_x + 1.5, (low_y + low_h + ans_y) / 2, "the best guess\njoins the set", colour=style.INK_SOFT)

    # what training hands to the service
    _connector(ax, reading_x + reading_w / 2, a_y, row_y + row_h)
    _connector(ax, members_x + members_w / 2, a_y, row_y + row_h)
    _connector(ax, answer_x + answer_w / 2, a_y, ans_y + ans_h)
    return fig
