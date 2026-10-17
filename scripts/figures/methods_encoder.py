"""Methods illustration: the encoder. How one cell's profile becomes a place:
one member's layers (a), the five members, how they were trained and what
each gives (b), and the coordinate member's projection that is the atlas map,
drawn from the site's own coordinate files (c).

Every number comes from a committed record: the layers and members from
web/data/workflow.json (the served model, traced by scripts/trace_workflow.py),
the training recipe and the reference from web/data/manuscript.json (the
Manuscript page's own records), the map from web/data/metadata_RNA_lat128.csv
and web/data/metadata_PROT_lat128.csv. The words follow the page's
procedures section (#encoder), service/model/MODEL_CARD.md (v3.1),
docs/service/projection-api.md (v3.1) and service/pipeline/ensemble.py.
"""
from __future__ import annotations

from . import common, style

NAME = "methods-encoder"
TITLE = "Methods illustration: the encoder"
SECTION = "encoder"
WIDTH = "double"
ALT = ("Three panels. a: one member of the encoder, as boxes from left to right: a cell's measured values and "
       "its mask over the gene space, with the mean and measured share of each gene module, form the input; two "
       "blocks lead to a unit-length latent. b: training on labelled RNA only, the members of one recipe with "
       "their fitted temperatures, and what each gives: type probabilities and a similarity to the reference "
       "cells, both averaged over the members for the answer layer, and, from the coordinate member alone, the "
       "coordinates of the atlas map. c: the map itself, the first two components of the coordinate member's "
       "projection, for a subsample of the RNA reference cells in orange and of the atlas's protein cells in "
       "green.")
CAPTION = ("a, One member of the encoder: the masked values and the mask over the model's genes, with the mean and "
           "measured share of each gene module, pass through two blocks to a unit-length latent; the number of "
           "weights is per member. b, The members share one architecture and one training recipe on labelled RNA "
           "only, and differ by seed; each has its own fitted temperature T. A member scores a cell by the "
           "softmax of its cosines to the type centroids over T, and the ensemble averages the members' "
           "probabilities; the members' best cosines to the reference cells, averaged, give the similarity the "
           "answer layer checks. One member, the coordinate member, places cells on the atlas map through a "
           "principal component projection of its reference latents. c, The atlas map: the first two components "
           "for the RNA reference cells (orange) and the atlas's protein cells, placed by the service (green). A "
           "fixed subsample, every so many rows of each file; the protein file is sampled more densely so its "
           "cells stay visible. The axes have no units.")
SOURCES = (
    "web/data/workflow.json",
    "web/data/manuscript.json",
    "web/data/metadata_RNA_lat128.csv",
    "web/data/metadata_PROT_lat128.csv",
)

WORKFLOW, MANUSCRIPT, RNA_CSV, PROT_CSV = SOURCES
MAP_POINTS = 1500          # at most this many points in the map, all files together
PROT_STEP = 3              # every third protein row; the RNA step fills the rest


def _steps(n_rna: int, n_prot: int) -> tuple[int, int]:
    """Row steps for a deterministic subsample of at most MAP_POINTS points."""
    prot = -(-n_prot // PROT_STEP)
    room = MAP_POINTS - prot
    rna_step = -(-n_rna // room)
    return rna_step, PROT_STEP


def data() -> list[dict]:
    w = common.read_json(WORKFLOW)
    records = common.read_json(MANUSCRIPT)["records"]
    rows = []

    # a: one member's layers, as traced from the served coordinate member.
    enc = w["trace"]["stages"]["encoder"]
    parts = enc["layers"][0]["parts"]
    for key in ("values", "mask", "module_values", "module_mask_fraction"):
        rows.append(common.row("a", key, parts[key], series="input part", unit="columns", source=WORKFLOW,
                               field=f"trace.stages.encoder.layers[0].parts.{key}"))
    for i, layer in enumerate(enc["layers"]):
        rows.append(common.row("a", layer["name"], layer["width"], series="layer", unit="units", source=WORKFLOW,
                               field=f"trace.stages.encoder.layers[{i}].width"))
    rows.append(common.row("a", "weights per member", enc["parameters"], unit="weights", source=WORKFLOW,
                           field="trace.stages.encoder.parameters"))

    # b: the members and their recipe.
    rows.append(common.row("b", "members", common.measured(records["wf_members"]), unit="members",
                           source=MANUSCRIPT, field="records.wf_members.value"))
    for i, m in enumerate(w["training"]["members"]):
        rows.append(common.row("b", m["name"], common.measured(m["answer_temperature"]), series="member",
                               unit="temperature", source=WORKFLOW,
                               field=f"training.members[{i}].answer_temperature.value"))
    rows.append(common.row("b", enc["coordinate_member"], None, series="coordinate member", source=WORKFLOW,
                           field="trace.stages.encoder.coordinate_member"))
    for key, label, unit in (("ref_cells", "reference cells", "cells"), ("ref_classes", "types", "types"),
                             ("wf_recipe_coverage_low", "genes kept, lowest", "share"),
                             ("wf_recipe_coverage_high", "genes kept, highest", "share"),
                             ("wf_recipe_natural_share", "batches like the reference", "share"),
                             ("wf_recipe_epochs", "epochs", "epochs"), ("wf_recipe_batch", "batch", "cells")):
        rows.append(common.row("b", label, common.measured(records[key]), series="training", unit=unit,
                               source=MANUSCRIPT, field=f"records.{key}.value"))

    # c: the map, the coordinate member's projection as the site ships it.
    rna = common.read_csv(RNA_CSV)
    prot = common.read_csv(PROT_CSV)
    components = [c for c in rna[0] if c.startswith("PC")]
    rows.append(common.row("c", "projection components", len(components), unit="components", source=RNA_CSV,
                           field="columns " + ", ".join(components)))
    rna_step, prot_step = _steps(len(rna), len(prot))
    for series, source, table, step in (("RNA", RNA_CSV, rna, rna_step), ("protein", PROT_CSV, prot, prot_step)):
        for i in range(0, len(table), step):
            for pc in ("PC1", "PC2"):
                rows.append(common.row("c", f"cell {table[i]['orig_index']}", float(table[i][pc]), series=series,
                                       unit=pc, source=source, field=f"row {i}, {pc}"))
    return rows


# ---- drawing ----

def _count(v) -> str:
    return f"{int(v):,}"


def _share(v) -> str:
    return f"{v * 100:.1f}".removesuffix(".0") + "%"


def _seed(name: str) -> str:
    stem = name.removesuffix(".pt")
    return "seed " + stem.rsplit("seed", 1)[1] if "seed" in stem else stem


def _wrap(text: str, limit: int = 24) -> str:
    """A long layer name on two lines, broken at its last comma."""
    if len(text) <= limit or ", " not in text:
        return text
    head, tail = text.rsplit(", ", 1)
    return f"{head},\n{tail}"


def _card(ax, x, y, w, h, heading, lines, *, edge=style.INK, line=style.LINE_WIDTH, tail_colour=style.INK_FAINT):
    """A box with a heading and smaller lines under it, centred; the last line may take its own colour."""
    common.box(ax, x, y, w, h, fill=style.PAPER, edge=edge, line=line)
    n = 1 + len(lines)
    step = 3.1
    top = y + h / 2 + (n - 1) * step / 2
    common.note(ax, x + w / 2, top, heading, ha="center", size=style.SIZE_LABEL, colour=style.INK, weight="bold")
    for i, text in enumerate(lines):
        last = i == len(lines) - 1
        common.note(ax, x + w / 2, top - (i + 1) * step, text, ha="center",
                    colour=tail_colour if last else style.INK_SOFT)


def draw(rows, plt):
    W, H = style.WIDTHS_MM[WIDTH], 90.0
    fig = common.new_figure(plt, WIDTH, H)
    ax = common.canvas(fig, W, H)

    def pick(panel, label=None, series=None):
        return [r for r in rows if r["panel"] == panel and (label is None or r["label"] == label)
                and (series is None or r["series"] == series)]

    def value(panel, label):
        return pick(panel, label)[0]["value"]

    def heading(x, y, letter, text):
        common.note(ax, x, y, letter, size=style.SIZE_LETTER, colour=style.INK, weight="bold", va="baseline")
        common.note(ax, x + 4.2, y, text, size=style.SIZE_TITLE, colour=style.INK, va="baseline")

    # ---- a: one member ----
    top = H - 4.0
    heading(2.0, top, "a", "One member: a cell's profile to a point in its latent space")
    common.note(ax, W - 2.0, top, f"{_count(value('a', 'weights per member'))} weights per member",
                ha="right", va="baseline", colour=style.INK_SOFT)
    parts = {r["label"]: r["value"] for r in pick("a", series="input part")}
    layers = pick("a", series="layer")
    y0, h = top - 26.0, 22.0
    # the cell's profile: values and mask over the genes, and the modules
    common.box(ax, 2.0, y0, 48.0, h, fill=style.FIELD, edge=style.FIELD)
    common.note(ax, 4.0, y0 + h - 3.2, "A cell's profile", colour=style.INK, size=style.SIZE_LABEL, weight="bold")
    common.box(ax, 4.0, y0 + 9.6, 21.0, 7.0, f"values\n{_count(parts['values'])} genes", fill=style.PAPER,
               size=style.SIZE)
    common.box(ax, 27.0, y0 + 9.6, 21.0, 7.0, f"mask\n{_count(parts['mask'])} genes", fill=style.PAPER,
               size=style.SIZE)
    common.box(ax, 4.0, y0 + 1.6, 44.0, 6.6,
               f"mean and measured share\nof {_count(parts['module_values'])} gene modules", fill=style.PAPER,
               size=style.SIZE)
    # the layers, left to right
    xs, bw, gap = [], 29.0, 5.0
    x = 56.0
    for i in range(len(layers)):
        xs.append(x)
        x += bw + gap
    last_w = W - 2.0 - xs[-1]
    by, bh = y0 + 9.0, 10.0
    words = ["Input"] + ["Block"] * (len(layers) - 2) + ["Latent"]
    for i, (layer, x, word) in enumerate(zip(layers, xs, words)):
        last = i == len(layers) - 1
        width = last_w if last else bw
        unit = "dimensions" if last else "wide" if i == 0 else "units"
        _card(ax, x, by, width, bh, word, (f"{_count(layer['value'])} {unit}",),
              edge=style.ACCENT if last else style.INK, line=style.MARK_WIDTH if last else style.LINE_WIDTH,
              tail_colour=style.INK_SOFT)
        under = "values, mask\nand modules" if i == 0 else _wrap(layer["label"])
        common.note(ax, x + width / 2, by - 1.4, under, ha="center", va="top", colour=style.INK_FAINT)
        start = 2.0 + 48.0 if i == 0 else xs[i - 1] + bw
        common.arrow(ax, (start + 0.8, by + bh / 2), (x - 0.8, by + bh / 2))
    common.note(ax, xs[-1] + last_w / 2, by + bh + 1.6, "unit length", ha="center", va="bottom",
                colour=style.ACCENT)

    # ---- b: the members ----
    members = pick("b", series="member")
    coord = pick("b", series="coordinate member")[0]["label"]
    train = {r["label"]: r["value"] for r in pick("b", series="training")}
    latent = layers[-1]["value"]
    btop = y0 - 6.0
    heading(2.0, btop, "b", f"{_count(value('b', 'members'))} members, one recipe, trained on RNA only")
    floor = 2.0
    # training
    tx, tw, th = 2.0, 40.0, btop - 4.0 - floor
    common.box(ax, tx, floor, tw, th, fill=style.WELL, edge=style.WELL)
    common.note(ax, tx + 2.0, floor + th - 3.4, "Training", colour=style.INK, size=style.SIZE_LABEL, weight="bold")
    lines = (
        f"{_count(train['reference cells'])} labelled RNA\nreference cells, {_count(train['types'])} types",
        f"each cell keeps {_share(train['genes kept, lowest'])} to\n"
        f"{_share(train['genes kept, highest'])} of its genes at random",
        f"{_share(train['batches like the reference'])} of batches keep the\nreference's mix; the rest hold\n"
        "a few types, like narrow uploads",
        f"{_count(train['epochs'])} epochs, batches of {_count(train['batch'])}",
        "losses: cross-entropy, supervised\ncontrastive, hubness, and the\nagreement of two masked views",
    )
    yy = floor + th - 7.2
    for text in lines:
        common.note(ax, tx + 2.0, yy, text, va="top", colour=style.INK_SOFT)
        yy -= 3.6 + 3.1 * text.count("\n")
    # the members, stacked
    mx, mw, mh, mgap = 49.0, 26.0, 5.4, 1.8
    stack = len(members) * mh + (len(members) - 1) * mgap
    mid = floor + th / 2 - 1.5
    my_top = mid + stack / 2
    centres = []
    for i, m in enumerate(members):
        yb = my_top - (i + 1) * mh - i * mgap
        is_coord = m["label"] == coord
        common.box(ax, mx, yb, mw, mh, f"{_seed(m['label'])}    T = {m['value']:.3f}", fill=style.PAPER,
                   edge=style.ACCENT if is_coord else style.INK, size=style.SIZE,
                   line=style.MARK_WIDTH if is_coord else style.LINE_WIDTH)
        centres.append((yb + mh / 2, is_coord))
    common.arrow(ax, (tx + tw + 0.8, mid), (mx - 0.8, mid))
    common.note(ax, mx + mw / 2, my_top + 1.4, f"each: a {latent}-dimensional\nlatent, unit length",
                ha="center", va="bottom", colour=style.INK_FAINT)
    # every member feeds a bus; the bus feeds the averaged outputs
    bus = mx + mw + 4.0
    for cy, _ in centres:
        ax.plot([mx + mw, bus], [cy, cy], color=style.INK, lw=style.LINE_WIDTH, solid_capstyle="butt")
    ax.plot([bus, bus], [centres[-1][0], centres[0][0]], color=style.INK, lw=style.LINE_WIDTH,
            solid_capstyle="butt")
    gx, gw, gh = bus + 7.0, 46.0, 11.0
    upper = (centres[0][0], centres[0][0] - 13.0)
    outs = (
        ("Type probabilities", ("softmax(cosine to type centroids / T)", "averaged over the members")),
        ("Similarity to the reference", ("best cosine to any reference cell", "averaged over the members")),
    )
    for yc, (head, sub) in zip(upper, outs):
        _card(ax, gx, yc - gh / 2, gw, gh, head, sub)
        common.arrow(ax, (bus, min(max(yc, centres[-1][0]), centres[0][0])), (gx - 0.8, yc))
    # the coordinate member's projection
    n_pc = value("c", "projection components")
    cy = [c for c, is_coord in centres if is_coord][0]
    py = floor + 1.0
    _card(ax, gx, py, gw, gh, "Map coordinates",
          (f"{_count(n_pc)}-component PCA projection", "coordinate member only, map in c"),
          edge=style.ACCENT, line=style.MARK_WIDTH, tail_colour=style.ACCENT)
    common.arrow(ax, (mx + mw + 0.6, cy - 0.6), (gx - 0.8, py + gh / 2), colour=style.ACCENT, curve=0.0)

    # ---- c: the map ----
    cx0 = gx + gw + 6.0
    heading(cx0, btop, "c", "The atlas map")
    left, bottom = cx0 + 5.0, floor + 12.0
    mapax = fig.add_axes((left / W, bottom / H, (W - 2.0 - left) / W, (btop - 4.0 - bottom) / H))
    for series, colour, name in (("RNA", style.RNA, "RNA reference cells"),
                                 ("protein", style.PROT, "protein cells, SCoPE2")):
        pts = pick("c", series=series)
        x = [r["value"] for r in pts if r["unit"] == "PC1"]
        y = [r["value"] for r in pts if r["unit"] == "PC2"]
        mapax.scatter(x, y, s=1.3, color=colour, linewidths=0, label=name)
    mapax.set_xticks([])
    mapax.set_yticks([])
    mapax.set_xlabel("first component", fontsize=style.SIZE, color=style.INK_SOFT, labelpad=2)
    mapax.set_ylabel("second component", fontsize=style.SIZE, color=style.INK_SOFT, labelpad=2)
    mapax.set_aspect("equal", adjustable="datalim")
    for spine in ("left", "bottom"):
        mapax.spines[spine].set_color(style.INK_FAINT)
    mapax.legend(loc="upper left", bbox_to_anchor=(-0.02, -0.09), ncol=1, markerscale=3.5, handletextpad=0.1,
                 borderaxespad=0, labelspacing=0.3, fontsize=style.SIZE, labelcolor=style.INK_SOFT)
    return fig
