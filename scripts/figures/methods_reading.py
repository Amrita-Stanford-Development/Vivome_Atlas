"""Methods illustration: reading an upload (the Manuscript page's #processing,
with #gene-space). How the service reads one file before the model sees
it, in the order it does it (service/pipeline/validation.py, then
pipeline._prepare_query: alignment.detect_and_transform_value_scale,
collapse_duplicate_genes, align_to_feature_space, smoothing.fuzzy_smooth;
the floor is config.MIN_OBSERVED_GENES): the matrix, linear values to
log2, names matched to the shared gene list, each gene scaled within the
file, smoothing with each cell's neighbours, and the mask with the floor of
measured genes.

The example is PBMC240 as the Workflow page traces it (web/data/workflow.json):
its file-level counts, a sample of its real presence pattern, its smoothing
graph, every cell's count of measured genes, and the values of the cell the
Workflow page follows (trace.story.default), drawn in the accent. The
scaling panel's dots are a schematic.
"""
from __future__ import annotations

import base64

from . import common, style

NAME = "methods-reading"
TITLE = "Methods illustration: reading an upload"
SECTION = "processing"
WIDTH = "double"

WORKFLOW = "web/data/workflow.json"
SOURCES = (WORKFLOW,)

ALT = ("Six steps in two rows, each with a small picture and the PBMC protein file as the example. "
       "a, the matrix: features in rows and cells in columns; a sample of the file's real pattern of measured "
       "and missing values, with one cell outlined in blue. b, linear values are taken to a base-two "
       "logarithm: one value of the blue cell before and after. c, names are matched to the shared gene list: "
       "a duplicated gene is merged by its median, an unknown name and a name for several genes are left out. "
       "d, each gene is scaled within the file, drawn as a schematic: in a mixed file the high and low cells "
       "stay apart, while in a file of one sorted type the cells' shared high level becomes the file's mean. "
       "e, smoothing: the file's cells on the first two axes of their own graph, the blue cell joined to its "
       "nearest neighbours. f, the mask of what the blue cell measured on marker genes, and every cell's count "
       "of measured genes against the floor below which a cell gets no answer.")
CAPTION = ("Reading an upload, step by step as the service does it, before the model sees it. a, The matrix: "
           "features in rows and cells in columns, or a DIA-NN or FragPipe TMT-Integrator table as it comes; the "
           "grid is a sample of the PBMC protein file's real rows and columns, filled where a value was measured. "
           "b, Linear values are taken to a base-two logarithm. c, Names resolve to the shared gene list through a "
           "frozen HGNC table; a group naming several genes is left out, and rows naming one gene merge by their "
           "median. d, Each gene is scaled within the file over its measured values (a schematic): this cancels "
           "each protein's own offset from its RNA, and in a file of one sorted type it also removes the contrast "
           "between types. e, Each value is smoothed with the cell's nearest neighbours on a graph of the file's "
           "own values (cells drawn on the graph's first two axes); the mask is not smoothed. f, The mask marks "
           "what each cell measured, and a cell below the floor of measured genes gets no answer. One cell of the "
           "PBMC file, the one the Workflow page follows, is drawn in blue; the numbers are the PBMC file's, from "
           "the service's own trace.")

FOLLOWED_GENES = ("CD3E", "CD8A")     # a gene the blue cell measured, and one it did not
GRID_FEATURES = 8                     # rows sampled, evenly, from the file's rows ordered by how many cells see them
GRID_CELLS = 12                       # consecutive columns around the blue cell
GRID_BEFORE = 5                       # columns left of the blue cell


def _measured(record, where: str):
    value = common.measured(record)
    if value is None:
        raise ValueError(f"{WORKFLOW}: {where} is not measured")
    return value


# (label, path under the file, unit): the file-level numbers each panel quotes.
FACTS = (
    ("a", "rows", ("facts", "rows"), "protein groups"),
    ("a", "cells", ("facts", "runs"), "cells"),
    ("a", "missing share", ("facts", "missing_share"), "share"),
    ("a", "fewest cells", ("service", "min_cells"), "cells"),
    ("a", "most cells", ("service", "max_cells"), "cells"),
    ("b", "median observed value", ("facts", "median_linear"), "linear"),
    ("b", "linear threshold", ("facts", "scale_threshold"), "linear"),
    ("c", "rows resolved", ("facts", "ids_matched"), "rows"),
    ("c", "rows unmapped", ("facts", "ids_unmapped"), "rows"),
    ("c", "rows ambiguous", ("facts", "ids_ambiguous"), "rows"),
    ("c", "genes filled", ("facts", "matched"), "genes"),
    ("c", "shared gene list", ("facts", "feature_space"), "genes"),
    ("e", "own share", ("facts", "smoothing_own"), "share"),
    ("e", "neighbour share", ("facts", "smoothing_alpha"), "share"),
    ("e", "neighbours", ("facts", "smoothing_k"), "cells"),
    ("e", "principal components", ("facts", "smoothing_pca"), "components"),
    ("f", "floor", ("facts", "floor"), "genes"),
    ("f", "median genes measured", ("facts", "observed_median"), "genes"),
    ("f", "cells below the floor", ("facts", "below_floor"), "cells"),
)


def _bits(encoded: str) -> bytes:
    return base64.b64decode(encoded)


def _bit(raw: bytes, k: int) -> int:
    """numpy.packbits order: the first flag is the high bit of the first byte."""
    return (raw[k // 8] >> (7 - k % 8)) & 1


def data() -> list[dict]:
    wf = common.read_json(WORKFLOW)
    rows = []

    def add(panel, label, value, *, series="", unit="", field):
        rows.append(common.row(panel, label, value, series=series, unit=unit, source=WORKFLOW, field=field))

    for panel, label, path, unit in FACTS:
        record = wf[path[0]][path[1]]
        add(panel, label, _measured(record, ".".join(path)), unit=unit, field=".".join(path) + ".value")

    trace, raw = wf["trace"], wf["raw"]["pbmc240"]
    cells = trace["cells"]
    blue = trace["story"]["default"]
    blue_id = cells[blue]["id"]
    add("all", blue_id, cells[blue]["observed"], series="blue cell", unit="genes",
        field=f"trace.cells[{blue}].observed (trace.story.default)")

    # a: a sample of the file's real presence pattern, the blue cell's column among its neighbours in file order
    presence = raw["parse"]["presence"]
    n_rows, n_cols = presence["rows"], presence["cols"]
    if n_cols != len(cells):
        raise ValueError(f"{WORKFLOW}: the presence grid's columns are not the trace's cells")
    flags = _bits(presence["bits"])
    first = min(max(blue - GRID_BEFORE, 0), n_cols - GRID_CELLS)
    for i in range(GRID_FEATURES):
        r = int((i + 0.5) * n_rows / GRID_FEATURES)
        for c in range(first, first + GRID_CELLS):
            add("a", cells[c]["id"], _bit(flags, r * n_cols + c), series=f"presence, row {r}", unit="measured",
                field=f"raw.pbmc240.parse.presence.bits[row {r}, column {c}]")

    # b: one of the blue cell's values, before and after log2
    detail = next(d for d in trace["detail"] if d["cell"] == blue)
    name, linear, logged = detail["raw_row"][0]
    add("b", name, linear, series="linear", unit="linear", field=f"trace.detail[cell {blue}].raw_row[0][1]")
    add("b", name, logged, series="log2", unit="log2", field=f"trace.detail[cell {blue}].raw_row[0][2]")

    # c: what happens to a duplicated name, an unknown one and an ambiguous one
    merged = raw["collapse"]["examples"][0]
    add("c", merged["gene"], merged["rows"], series="merged", unit="rows",
        field="raw.pbmc240.collapse.examples[0].rows")
    add("c", raw["ids"]["unmapped_examples"][1], None, series="unmapped",
        field="raw.pbmc240.ids.unmapped_examples[1]")
    add("c", raw["ids"]["ambiguous_examples"][1], None, series="ambiguous",
        field="raw.pbmc240.ids.ambiguous_examples[1]")

    # d, e, f: the blue cell's values for two marker genes, step by step, and its mask on every marker gene
    heat = trace["heatmap"]
    at = heat["cells"].index(blue)
    for gene in FOLLOWED_GENES:
        g = heat["genes"].index(gene)
        for step in ("log2", "z", "smoothed"):
            add("d" if step != "smoothed" else "e", gene, heat[step][at][g], series=step,
                unit="log2" if step == "log2" else "scaled", field=f"trace.heatmap.{step}[{at}][{g}]")
    for g, gene in enumerate(heat["genes"]):
        add("f", gene, heat["mask"][at][g], series="mask", unit="measured", field=f"trace.heatmap.mask[{at}][{g}]")

    # e: the smoothing graph, drawn on its first two axes, and the blue cell's neighbours with their weights
    for i, cell in enumerate(cells):
        add("e", cell["id"], cell["layout"][0], series="layout x", field=f"trace.cells[{i}].layout[0]")
        add("e", cell["id"], cell["layout"][1], series="layout y", field=f"trace.cells[{i}].layout[1]")
    smoothing = trace["stages"]["smoothing"]
    for j, (other, weight) in enumerate(zip(smoothing["neighbours"][blue], smoothing["weights"][blue])):
        add("e", cells[other]["id"], weight, series="neighbour", unit="weight",
            field=f"trace.stages.smoothing.weights[{blue}][{j}]")

    # f: every cell's count of measured genes in the shared list
    for i, cell in enumerate(cells):
        add("f", cell["id"], cell["observed"], series="genes measured", unit="genes",
            field=f"trace.cells[{i}].observed")
    return rows


# ---- drawing ----

W, H = style.WIDTHS_MM[WIDTH], 119.0
CARD_W, CARD_H, GAP = 59.0, 57.0, 5.5
INSET = 2.5                      # mm inside a card's edge
GLYPH_TOP, GLYPH_H = 8.0, 21.0   # the picture's band, from the card's top


def _fmt(value, unit: str = "") -> str:
    if unit == "share":
        pct = value * 100
        return f"{pct:.0f}%" if abs(pct - round(pct)) < 1e-9 else f"{pct:.1f}%"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}"


def _card(ax, x, top, letter, title):
    common.box(ax, x, top - CARD_H, CARD_W, CARD_H, fill=style.FIELD, edge=style.FIELD, radius=2.0)
    common.note(ax, x + INSET, top - 5.0, letter, size=style.SIZE_LETTER, colour=style.INK, weight="bold",
                va="baseline")
    common.note(ax, x + INSET + 4.2, top - 5.0, title, size=style.SIZE_TITLE, colour=style.INK, va="baseline")


def _words(ax, x, top, rule, example):
    """The step's rule, and PBMC240's own numbers under it."""
    common.note(ax, x + INSET, top - GLYPH_TOP - GLYPH_H - 2.2, rule, colour=style.INK_SOFT, va="top")
    common.note(ax, x + INSET, top - CARD_H + 2.0, example, colour=style.INK, va="bottom")


def _square(ax, x, y, size, *, filled, fill=style.INK_FAINT, edge=style.NEUTRAL, line=0.4):
    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle((x, y), size, size, facecolor=fill if filled else style.PAPER,
                           edgecolor=fill if filled else edge, linewidth=line))


def _chip(ax, x, y, w, h, text, *, edge=style.INK, line=style.LINE_WIDTH, size=style.SIZE_LABEL):
    common.box(ax, x, y, w, h, text, fill=style.PAPER, edge=edge, line=line, size=size, radius=1.0)


def _dots(ax, x, ys, *, filled):
    """A column of cells as dots, nudged left and right so close ones stay apart."""
    for i, y in enumerate(ys):
        ax.plot(x + (0.45 if i % 2 else -0.45), y, marker="o", markersize=2.8, linestyle="none",
                markerfacecolor=style.INK_SOFT if filled else style.PAPER, markeredgecolor=style.INK_SOFT,
                markeredgewidth=0.6)


def _zscores(values):
    mean = sum(values) / len(values)
    sd = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
    return [(v - mean) / sd for v in values]


def draw(rows, plt):
    fig = common.new_figure(plt, WIDTH, H)
    ax = common.canvas(fig, W, H)
    one = {r["label"]: r for r in rows if not r["series"]}
    n = {label: _fmt(r["value"], r["unit"]) for label, r in one.items()}
    series = {}
    for r in rows:
        if r["series"]:
            series.setdefault(r["series"], []).append(r)
    blue = series["blue cell"][0]
    step = {(r["series"], r["label"]): r["value"] for r in rows if r["series"] in ("log2", "z", "smoothed")}
    seen, missing = [r["label"] for r in series["z"]]

    xs = [1.0 + i * (CARD_W + GAP) for i in range(3)]
    tops = [H - 1.0, H - 1.0 - CARD_H - 3.0]

    # a: the matrix, a sample of PBMC240's own presence pattern
    x, top = xs[0], tops[0]
    _card(ax, x, top, "a", "The matrix")
    grid = [s for s in series if s.startswith("presence")]
    size, pitch = 1.75, 2.15
    gx, gy = x + INSET + 5.0, top - GLYPH_TOP - 4.5
    for i, name in enumerate(grid):
        for j, r in enumerate(series[name]):
            _square(ax, gx + j * pitch, gy - (i + 1) * pitch, size, filled=r["value"] == 1)
    blue_col = [r["label"] for r in series[grid[0]]].index(blue["label"])
    common.box(ax, gx + blue_col * pitch - 0.45, gy - len(grid) * pitch - 0.45, size + 0.9, len(grid) * pitch + 0.5,
               fill="none", edge=style.ACCENT, line=style.MARK_WIDTH, radius=0.5)
    grid_w = len(series[grid[0]]) * pitch
    common.arrow(ax, (gx, gy + 1.6), (gx + grid_w - 0.4, gy + 1.6), colour=style.INK_FAINT, line=0.6, head=3.0)
    common.note(ax, gx + grid_w + 1.0, gy + 1.6, "cells", colour=style.INK_SOFT)
    common.arrow(ax, (gx - 1.6, gy), (gx - 1.6, gy - len(grid) * pitch + 0.4), colour=style.INK_FAINT, line=0.6,
                 head=3.0)
    ax.text(gx - 3.0, gy - len(grid) * pitch / 2, "features", rotation=90, ha="center", va="center",
            fontsize=style.SIZE, color=style.INK_SOFT)
    lx = gx + grid_w + 4.0
    _square(ax, lx, gy - 6.2, 1.75, filled=True)
    common.note(ax, lx + 3.0, gy - 5.3, "measured", colour=style.INK_SOFT)
    _square(ax, lx, gy - 10.2, 1.75, filled=False)
    common.note(ax, lx + 3.0, gy - 9.3, "missing", colour=style.INK_SOFT)
    common.box(ax, lx + 0.4, gy - 15.0, 1.0, 2.6, fill="none", edge=style.ACCENT, line=style.MARK_WIDTH, radius=0.3)
    common.note(ax, lx + 3.0, gy - 13.7, "the blue cell", colour=style.INK_SOFT)
    _words(ax, x, top,
           "Features in rows and cells in columns, as\nCSV or TSV; DIA-NN reports and FragPipe\n"
           "TMT-Integrator tables as they come. The\n"
           f"orientation is checked; {n['fewest cells']} to {n['most cells']} cells.",
           f"PBMC240, a DIA-NN report: {n['rows']} protein\ngroups, {n['cells']} cells, "
           f"{n['missing share']} of values missing")

    # b: linear values to log2, one of the blue cell's own
    x, top = xs[1], tops[0]
    _card(ax, x, top, "b", "Linear values to log2")
    lin, lg = series["linear"][0], series["log2"][0]
    cy = top - GLYPH_TOP - 8.0
    _chip(ax, x + 8.0, cy - 3.5, 17.0, 7.0, _fmt(lin["value"]), edge=style.ACCENT, line=style.MARK_WIDTH)
    _chip(ax, x + 36.0, cy - 3.5, 15.0, 7.0, _fmt(lg["value"]), edge=style.ACCENT, line=style.MARK_WIDTH)
    common.arrow(ax, (x + 26.5, cy), (x + 34.5, cy), colour=style.INK, line=style.LINE_WIDTH, head=4.0)
    common.note(ax, x + 30.5, cy + 2.2, "log2", colour=style.INK_SOFT, ha="center", va="bottom")
    common.note(ax, x + 16.5, cy - 5.0, "linear", colour=style.INK_FAINT, ha="center", va="top")
    common.note(ax, x + 43.5, cy - 5.0, "log2", colour=style.INK_FAINT, ha="center", va="top")
    common.note(ax, x + CARD_W / 2, cy - 10.0, f"the blue cell's {lin['label']}", colour=style.INK_SOFT,
                ha="center", va="top")
    _words(ax, x, top,
           "A file with no negative values and a median\nobserved value above "
           f"{n['linear threshold']} is read as linear,\nand log2 is taken; a zero counts as missing.",
           f"PBMC240: median observed value\n{n['median observed value']}, so read as linear")

    # c: names matched to the shared gene list
    x, top = xs[2], tops[0]
    _card(ax, x, top, "c", "Matched to the shared gene list")
    merged, unmapped, ambiguous = series["merged"][0], series["unmapped"][0], series["ambiguous"][0]
    for i, (chip, outcome) in enumerate(((f"{merged['label']}, {_fmt(merged['value'])} rows", "merged: the median"),
                                         (unmapped["label"], "unmapped: left out"),
                                         (ambiguous["label"], "ambiguous: left out"))):
        cy = top - GLYPH_TOP - 3.5 - i * 6.5
        _chip(ax, x + INSET + 1.0, cy - 2.4, 21.0, 4.8, chip, size=style.SIZE)
        common.arrow(ax, (x + INSET + 23.5, cy), (x + INSET + 28.0, cy), colour=style.INK, line=style.LINE_WIDTH,
                     head=3.5)
        common.note(ax, x + INSET + 29.5, cy, outcome, colour=style.INK_SOFT)
    _words(ax, x, top,
           "Names resolve through a frozen HGNC table\n(symbols, Ensembl and UniProt accessions).\n"
           "A group naming several genes is left out;\nrows naming one gene merge by median.",
           f"PBMC240: {n['rows resolved']} rows resolve, {n['rows unmapped']} do not, "
           f"{n['rows ambiguous']}\nare ambiguous; {n['genes filled']} of {n['shared gene list']} genes filled")

    # d: each gene scaled within the file, a schematic: a mixed file keeps its contrast, one sorted type does not
    x, top = xs[0], tops[1]
    _card(ax, x, top, "d", "Each gene scaled within the file")
    band_top, band_bottom = top - GLYPH_TOP - 3.0, top - GLYPH_TOP - GLYPH_H + 4.0
    zero = (band_top + band_bottom) / 2
    half = (band_top - band_bottom) / 2
    high, low = (0.64, 0.76, 0.88, 1.0), (0.0, 0.12, 0.24, 0.36)
    for k, (label, groups) in enumerate((("a mixed file", ((high, True), (low, False))),
                                         ("one sorted type", ((high, True),)))):
        before, after = x + INSET + 5.0 + k * 27.0, x + INSET + 16.0 + k * 27.0
        values = [v for vs, _ in groups for v in vs]
        z = iter(_zscores(values))
        ax.plot((after - 3.0, after + 3.0), (zero, zero), color=style.NEUTRAL, linewidth=0.6, linestyle="--")
        common.note(ax, after + 3.6, zero, "mean", colour=style.INK_FAINT)
        for vs, filled in groups:
            _dots(ax, before, [band_bottom + 2 * half * v for v in vs], filled=filled)
            _dots(ax, after, [zero + next(z) * half / 1.5 for _ in vs], filled=filled)
        common.arrow(ax, (before + 2.0, zero), (after - 3.6, zero), colour=style.INK_FAINT, line=0.6, head=3.0)
        common.note(ax, before, band_top + 2.5, "log2", colour=style.INK_FAINT, ha="center")
        common.note(ax, after, band_top + 2.5, "scaled", colour=style.INK_FAINT, ha="center")
        common.note(ax, (before + after) / 2, band_bottom - 2.6, label, colour=style.INK_SOFT, ha="center")
    _words(ax, x, top,
           "Each gene is z-scored over its measured\nvalues in this file, so each protein's own\n"
           "offset from its RNA cancels; no RNA\nstatistics are used. In a sorted population\n"
           "its level becomes the mean: no contrast.",
           f"The blue cell's {seen}: {_fmt(step[('log2', seen)])} in log2, {_fmt(step[('z', seen)])}\n"
           f"scaled; {missing}, not measured: {_fmt(step[('z', missing)])}")

    # e: smoothing with each cell's neighbours, on the file's own graph
    x, top = xs[1], tops[1]
    _card(ax, x, top, "e", "Smoothed with neighbours")
    px = {r["label"]: r["value"] for r in series["layout x"]}
    py = {r["label"]: r["value"] for r in series["layout y"]}
    lo_x, hi_x, lo_y, hi_y = min(px.values()), max(px.values()), min(py.values()), max(py.values())
    scale = (GLYPH_H - 1.0) / max(hi_x - lo_x, hi_y - lo_y)
    ox, oy = x + INSET + 1.0, top - GLYPH_TOP - GLYPH_H + 0.5

    def at(label):
        return ox + (px[label] - lo_x) * scale, oy + (py[label] - lo_y) * scale

    others = [at(label) for label in px if label != blue["label"]]
    ax.plot([p[0] for p in others], [p[1] for p in others], marker="o", markersize=1.3, linestyle="none",
            markerfacecolor=style.NEUTRAL, markeredgecolor="none")
    bx, by = at(blue["label"])
    heaviest = max(r["value"] for r in series["neighbour"])
    for r in series["neighbour"]:
        nx, ny = at(r["label"])
        ax.plot((bx, nx), (by, ny), color=style.ACCENT, linewidth=0.5 + 0.5 * r["value"] / heaviest,
                solid_capstyle="round")
    ax.plot(bx, by, marker="o", markersize=3.8, linestyle="none", markerfacecolor=style.ACCENT,
            markeredgecolor=style.PAPER, markeredgewidth=0.5)
    common.note(ax, ox + (hi_x - lo_x) * scale + 3.0, top - GLYPH_TOP - 3.0,
                "each dot a PBMC240 cell,\non the graph's first\ntwo axes; lines: the\nblue cell's nearest\n"
                "neighbours", colour=style.INK_SOFT, va="top")
    _words(ax, x, top,
           f"Each value becomes {n['own share']} the cell's own plus\n"
           f"{n['neighbour share']} its {n['neighbours']} nearest neighbours', on a graph\n"
           f"of {n['principal components']} principal components of the file's\n"
           "scaled values (all its genes). The mask\nis left as measured.",
           f"The blue cell's {seen}: {_fmt(step[('z', seen)])}, then {_fmt(step[('smoothed', seen)])};\n"
           f"{missing}: {_fmt(step[('z', missing)])}, then {_fmt(step[('smoothed', missing)])}, "
           "still marked missing")

    # f: the mask, and the floor of measured genes
    x, top = xs[2], tops[1]
    _card(ax, x, top, "f", "The mask, and the floor")
    mask = series["mask"]
    mx, my, msize, mpitch = x + INSET + 1.0, top - GLYPH_TOP - 3.0, 1.6, 2.05
    common.note(ax, mx, my + 1.2, "the blue cell's mask on marker genes", colour=style.INK_SOFT, va="bottom")
    for i, r in enumerate(mask):
        _square(ax, mx + i * mpitch, my - msize, msize, filled=r["value"] == 1)
    for gene in (seen, missing):
        i = [r["label"] for r in mask].index(gene)
        common.note(ax, mx + i * mpitch + msize / 2, my - msize - 0.8, gene, colour=style.INK_FAINT, ha="center",
                    va="top")
    counts = series["genes measured"]
    most = max(r["value"] for r in counts)
    rx0, rx1 = x + INSET + 1.0, x + CARD_W - INSET - 1.0
    base = top - GLYPH_TOP - GLYPH_H + 4.0

    def rx(v):
        return rx0 + (rx1 - rx0) * v / most

    ax.plot((rx0, rx1), (base, base), color=style.LINE, linewidth=0.6)
    for r in counts:
        if r["label"] != blue["label"]:
            ax.plot((rx(r["value"]),) * 2, (base, base + 3.0), color=style.NEUTRAL, linewidth=0.35)
    ax.plot((rx(blue["value"]),) * 2, (base, base + 4.2), color=style.ACCENT, linewidth=style.MARK_WIDTH)
    floor = one["floor"]["value"]
    ax.plot((rx(floor),) * 2, (base - 0.6, base + 5.6), color=style.INK_SOFT, linewidth=0.8, linestyle="--")
    common.note(ax, rx(floor) + 0.8, base + 5.0, f"floor, {n['floor']}", colour=style.INK_SOFT)
    common.note(ax, (rx0 + rx1) / 2, base - 1.2, "genes measured per cell, one tick per cell", colour=style.INK_FAINT,
                ha="center", va="top")
    _words(ax, x, top,
           "Unmeasured genes are zero, and a mask\nmarks what each cell measured; the encoder\n"
           f"reads both. A cell with fewer than {n['floor']}\nmeasured genes gets no answer (too little\n"
           "measured); the floor is provisional.",
           f"PBMC240: median {n['median genes measured']} genes per cell; the\nblue cell {_fmt(blue['value'])}; "
           f"{n['cells below the floor']} cell below the floor")

    # the order: left to right, then the second row
    for top in tops:
        for i in range(2):
            edge = xs[i] + CARD_W
            common.arrow(ax, (edge + 0.8, top - 5.6), (edge + GAP - 0.8, top - 5.6), colour=style.ACCENT,
                         line=style.MARK_WIDTH, head=4.0)
    return fig
