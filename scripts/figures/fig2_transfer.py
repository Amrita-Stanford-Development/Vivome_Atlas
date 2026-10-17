"""Figure 2: labels learned on RNA transfer to protein (the Manuscript page's
#transfer). Recall by author type on Fulcher 2026 and Khoury 2026, recall by
lineage (with PBMC240, which is labelled by lineage only), and the modality
probe: the encoder keeps protein and RNA apart, yet the labels carry over.

The chance level of the probe is not stored in its record: it is the share a
balanced two-class probe gets by guessing (the record balances its two
classes, RNA subsampled to the protein cells' number), so it is computed here
from those two classes.
"""
from __future__ import annotations

from . import common, style

NAME = "fig2-transfer"
TITLE = "Figure 2"
SECTION = "transfer"
WIDTH = "double"

DEVELOPMENT = "research/notebook-outputs/v41_phase3/development.json"
KHOURY = "research/benchmark/khoury2026_posthoc_v41_check/summary.json"
FULCHER = "research/benchmark/v41_development/fulcher2026.csv"
PROBE = "service/model/evidence/v3_1_tables/modality_probe.json"
SOURCES = (DEVELOPMENT, KHOURY, FULCHER, PROBE)

ALT = ("Three panels. a, a dot plot of recall by cell type for the served model on Fulcher and on Khoury: "
       "the CD four T, B and monocyte types are mostly right on both, NK on Fulcher and about half on Khoury, "
       "CD eight T cells are mostly missed, most of all on Khoury, and dendritic cells are mostly missed on "
       "Fulcher and not labelled on Khoury. "
       "b, recall by lineage, lymphoid and myeloid, on Fulcher, Khoury and the PBMC protein set: high on all. "
       "c, the modality probe: a linear probe tells protein cells from RNA cells in the encoder's space "
       "almost perfectly, far above its chance level.")
CAPTION = ("Labels learned on RNA transfer to protein. a, Recall by author cell type of the served model's best "
           "guess on Fulcher (development data, on which its rule was chosen) and on Khoury (a post-hoc check); "
           "Khoury does not label dendritic cells. The legend gives each data set's balanced accuracy over its "
           "types. b, Recall by lineage on the same two data sets and on the PBMC protein set, which is labelled "
           "by lineage only and has very few myeloid cells. c, Balanced accuracy of a linear probe telling the "
           "macrophage and monocyte protein cells from as many RNA cells in the answer path's encoder space, "
           "against the chance level of a balanced two-class probe (grey line): the modalities stay apart, and "
           "labels transfer anyway. One point per value; the sources give no interval for recall.")

# Author types in the protocol's order (lymphoid, then myeloid), as the page's table names them.
TYPES = (("CD4T", "CD4 T"), ("CD8T", "CD8 T"), ("NK", "NK"), ("B", "B"), ("monocyte", "Monocyte"),
         ("DC", "Dendritic cell"))
LINEAGES = (("lymphoid", "Lymphoid"), ("myeloid", "Myeloid"))
DATASETS = ("Fulcher 2026", "Khoury 2026", "PBMC240")     # style.CATEGORICAL, in this order
MARKERS = ("o", "D", "s")                                  # a shape per data set too, for print
MODALITIES = ("RNA", "protein")                            # the probe's two classes
BALANCED = "balanced accuracy"
CHANCE = "chance"


def data() -> list[dict]:
    dev = common.read_json(DEVELOPMENT)["fulcher2026"]["v4.1"]
    khoury = common.read_json(KHOURY)["scores"]["v4.1"]
    served = [r for r in common.read_csv(FULCHER) if r["tool"] == "v4.1 (served)"]
    if len(served) != 1:
        raise ValueError(f"{FULCHER}: expected one v4.1 (served) row")
    fulcher = served[0]
    pbmc = common.read_json(DEVELOPMENT)["pbmc240"]["v4.1"]
    probe = common.read_json(PROBE)
    fu, kh, pb = DATASETS
    rows = []
    for key, label in TYPES:
        rows.append(common.row("a", label, dev[f"recall_{key}"], series=fu, unit="%", source=DEVELOPMENT,
                               field=f"fulcher2026.v4.1.recall_{key}"))
    for key, label in TYPES:
        if f"recall_{key}_pct" in khoury:
            rows.append(common.row("a", label, khoury[f"recall_{key}_pct"], series=kh, unit="%", source=KHOURY,
                                   field=f"scores.v4.1.recall_{key}_pct"))
    rows.append(common.row("a", BALANCED, dev["balanced_accuracy_6_types"], series=fu, unit="%",
                           source=DEVELOPMENT, field="fulcher2026.v4.1.balanced_accuracy_6_types"))
    rows.append(common.row("a", BALANCED, khoury["balanced_accuracy_pct"], series=kh, unit="%", source=KHOURY,
                           field="scores.v4.1.balanced_accuracy_pct"))
    for key, label in LINEAGES:
        rows.append(common.row("b", label, float(fulcher[f"{key}_recall_pct"]), series=fu, unit="%",
                               source=FULCHER, field=f"tool=v4.1 (served): {key}_recall_pct"))
        rows.append(common.row("b", label, khoury[f"{key}_recall_pct"], series=kh, unit="%", source=KHOURY,
                               field=f"scores.v4.1.{key}_recall_pct"))
        rows.append(common.row("b", label, pbmc[f"{key}_recall"], series=pb, unit="%", source=DEVELOPMENT,
                               field=f"pbmc240.v4.1.{key}_recall"))
    rows.append(common.row("c", "protein or RNA", probe["modality_probe_balanced_accuracy_pct"], unit="%",
                           source=PROBE, field="modality_probe_balanced_accuracy_pct"))
    rows.append(common.row("c", CHANCE, 100 / len(MODALITIES), unit="%", source=PROBE,
                           field=f"chance for its {len(MODALITIES)} balanced classes ({', '.join(MODALITIES)}; "
                                 "n_per_class each): 100 / classes"))
    return rows


def _dots(ax, rows, labels, series, offsets):
    """One marker per data set on each row, the sets side by side within the row."""
    for i, name in enumerate(series):
        got = {r["label"]: r["value"] for r in rows if r["series"] == name}
        ys = [labels.index(lab) + offsets[i] for lab in labels if lab in got]
        xs = [got[lab] for lab in labels if lab in got]
        ax.plot(xs, ys, linestyle="none", marker=MARKERS[i], markersize=style.MARKER + (0.4 if i == 0 else 0),
                color=style.CATEGORICAL[i], markeredgecolor=style.PAPER, markeredgewidth=0.5, zorder=3,
                clip_on=False, label=name)


def _head(fig, ax, letter, title, x):
    """The panel letter and a short title on one line, a fixed height above the plot."""
    y = 1 + (7 / 72) / (ax.get_position().height * fig.get_figheight())
    common.panel_letter(ax, letter, x=x, y=y)
    ax.text(0, y, title, transform=ax.transAxes, ha="left", va="bottom", fontsize=style.SIZE_TITLE,
            color=style.INK)


def _recall_axes(ax, labels, xlabel):
    ax.set_xlim(0, 100)
    ax.set_ylim(len(labels) - 0.5, -0.5)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xticks(range(0, 101, 25))
    ax.tick_params(axis="y", length=0, labelcolor=style.INK, pad=4)
    ax.tick_params(axis="x", length=2.5, width=style.LINE_WIDTH)
    ax.spines["left"].set_visible(False)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel)


def draw(rows, plt):
    fig = common.new_figure(plt, WIDTH, 62)
    grid = fig.add_gridspec(2, 2, width_ratios=(1.2, 1), height_ratios=(1.9, 1), left=0.085, right=0.985,
                            bottom=0.13, top=0.83, wspace=0.34, hspace=1.0)
    ax_a = fig.add_subplot(grid[:, 0])
    ax_b = fig.add_subplot(grid[0, 1])
    ax_c = fig.add_subplot(grid[1, 1])

    a = [r for r in rows if r["panel"] == "a" and r["label"] != BALANCED]
    types = list(dict.fromkeys(r["label"] for r in a))
    in_a = list(dict.fromkeys(r["series"] for r in a))
    _dots(ax_a, a, types, in_a, (-0.14, 0.14))
    _recall_axes(ax_a, types, "Recall (%)")
    for i, name in enumerate(in_a):
        for lab in types:
            if not any(r["series"] == name and r["label"] == lab for r in a):
                ax_a.text(1.5, types.index(lab) + (-0.14, 0.14)[i], f"{name.split()[0]}: not labelled",
                          ha="left", va="center", fontsize=style.SIZE, color=style.INK_FAINT)
    _head(fig, ax_a, "a", "Recall by type", -0.2)

    b = [r for r in rows if r["panel"] == "b"]
    lineages = list(dict.fromkeys(r["label"] for r in b))
    in_b = list(dict.fromkeys(r["series"] for r in b))
    _dots(ax_b, b, lineages, in_b, (-0.24, 0.0, 0.24))
    _recall_axes(ax_b, lineages, "Recall (%)")
    _head(fig, ax_b, "b", "Recall by lineage", -0.21)

    probe = next(r for r in rows if r["panel"] == "c" and r["label"] != CHANCE)
    chance = next(r for r in rows if r["panel"] == "c" and r["label"] == CHANCE)
    ax_c.axvline(chance["value"], color=style.NEUTRAL, linewidth=style.LINE_WIDTH, linestyle=(0, (3, 2)), zorder=1)
    ax_c.text(chance["value"] - 1.5, -0.3, "chance", ha="right", va="center", fontsize=style.SIZE,
              color=style.INK_SOFT)
    ax_c.plot([chance["value"], probe["value"]], [0, 0], color=style.INK, linewidth=style.MARK_WIDTH, zorder=2)
    ax_c.plot([probe["value"]], [0], linestyle="none", marker="o", markersize=style.MARKER + 0.4, color=style.INK,
              zorder=3, clip_on=False)
    ax_c.text(probe["value"], 0.3, f"{probe['value']:.2f}%", ha="right", va="bottom", fontsize=style.SIZE,
              color=style.INK)
    ax_c.set_ylim(-0.6, 0.6)
    ax_c.set_xlim(0, 100)
    ax_c.set_yticks([0], ["Protein or RNA"])
    ax_c.set_xticks(range(0, 101, 25))
    ax_c.tick_params(axis="y", length=0, labelcolor=style.INK, pad=4)
    ax_c.tick_params(axis="x", length=2.5, width=style.LINE_WIDTH)
    ax_c.spines["left"].set_visible(False)
    ax_c.set_xlabel("Balanced accuracy (%)")
    _head(fig, ax_c, "c", "Modality probe", -0.21)

    accuracy = {r["series"]: r["value"] for r in rows if r["panel"] == "a" and r["label"] == BALANCED}
    handles, names = ax_b.get_legend_handles_labels()
    names = [f"{n}, balanced accuracy {accuracy[n]:.2f}%" if n in accuracy else f"{n}, lineage only"
             for n in names]
    fig.legend(handles, names, loc="upper left", bbox_to_anchor=(0.085, 0.995), ncol=len(names),
               handletextpad=0.3, columnspacing=1.6, borderaxespad=0)
    return fig
