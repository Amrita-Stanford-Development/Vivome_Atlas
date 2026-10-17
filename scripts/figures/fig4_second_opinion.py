"""Figure 4: the second opinion and its gate. (a) Each upload's agreement (the
share of its cells whose top correlation names the encoder's top type) by
kind of simulated upload and for each protein dataset, against the bar at
which the second opinion is used. (b) The answer path's guess against the
served best guess, by kind of upload and on the datasets the page cites; below
the bar the served guess is the re-encoded reference's alone, so a kind that
never reaches the bar (SCoPE2-like) can still differ. (c) Why the gate is there: the gain
over the answer path when the term is used in every upload, against gated at
the bar, from the exploration that chose it.
"""
from __future__ import annotations

from . import common, style

NAME = "fig4-second-opinion"
TITLE = "Figure 4"
SECTION = "second-opinion"
WIDTH = "double"

UPLOADS = "research/notebook-outputs/v41_phase3/eval_uploads.csv"
EXPLORATION = "research/notebook-outputs/v4_phase3c/exploration.json"
GATE = "research/benchmark/v41_dev_gate.json"
KHOURY = "research/benchmark/khoury2026_posthoc_v41_check/summary.json"
KHOURY_PAIRED = "research/benchmark/khoury2026_posthoc_v41_check/paired_bootstrap.csv"
SUITE = "research/notebook-outputs/v41_phase3/summary.json"
DEVELOPMENT = "research/notebook-outputs/v41_phase3/development.json"
FULCHER_PAIRED = "research/benchmark/v41_development/paired_bootstrap_v41_vs_v31.csv"
HAO = "research/benchmark/heldout/hao2021/summary.json"
SOURCES = (UPLOADS, EXPLORATION, GATE, KHOURY, KHOURY_PAIRED, SUITE, DEVELOPMENT, FULCHER_PAIRED, HAO)

ALT = ("Three panels. (a) A strip plot of upload agreement, one dot per simulated upload in six kinds and "
       "one dot per protein dataset, with a grey horizontal line at the bar. Dots at or above the bar, "
       "where the second opinion is used, are blue; dots below are grey. Uploads of one type sit mostly "
       "below the bar, uploads of many types and PBMC-like ones mostly above it, SCoPE-like ones all "
       "below; Fulcher and Khoury are above, PBMC, SCoPE and Furtwangler below. (b) For each kind of "
       "upload and for Fulcher, Khoury and the held-out Hao donors, a grey dot for the answer path's "
       "guess joined to a blue dot for the served best guess, with the gain written at the right: "
       "little change for uploads of one type, large gains for PBMC-like and many-type uploads and for "
       "Fulcher. (c) For each kind of upload, the gain over the answer path with the second opinion used "
       "in every upload, an open circle, and gated at the bar, a filled circle; gating shrinks the loss "
       "on uploads of one type and the chance that a type fails there, costs a little on uploads of a "
       "few types and of one lineage, and keeps the gains on many-type and PBMC-like uploads.")
CAPTION = ("The second opinion and its gate. (a) Upload agreement: the share of an upload's cells whose top "
           "correlation to the type means names the encoder's top type. Each dot is one upload of the "
           "simulated RNA suite, by kind (spread sideways at fixed offsets), or one protein dataset "
           "(diamonds, with their values). At or above the bar (grey line) the best guess uses the second "
           "opinion (blue); below it the encoder decides alone (grey). (b) Balanced accuracy of the answer "
           "path's guess (grey) and of the served best guess (blue), which adds the second opinion where an "
           "upload reaches the bar: mean per upload for each kind of simulated upload, and on Fulcher, "
           "Khoury and the held-out Hao donors (RNA masked like protein), with the gain in points at the "
           "right; for Fulcher and Khoury with its paired bootstrap 95% interval, for the Hao donors with "
           "its one-sided lower bound. Fulcher is in sample for the model's one tuned weight and Khoury is "
           "post hoc. (c) The gate, as chosen during development on the calibration uploads: the best "
           "guess's gain over the answer path with the second opinion used in every upload (open) and gated "
           "at the bar (filled), with the chance that some cell type fails on uploads of one type.")

# The suite's kinds of upload, in the page's order and words.
KINDS = (("single", "One type alone"), ("narrow", "A few types"), ("mixed", "Many types"),
         ("lineage", "One lineage"), ("pbmc", "PBMC-like"), ("scope2", "SCoPE2-like"))
# The protein datasets the page gives an agreement for: (key in the gate file, name).
DATASETS = (("fulcher2026", "Fulcher"), ("khoury", "Khoury"), ("pbmc240", "PBMC240"), ("scope2", "SCoPE2"),
            ("furtwangler2025", "Furtwängler"))
# Two-line names where a column is narrow.
TWO_LINES = {"One type alone": "One type\nalone", "A few types": "A few\ntypes", "Many types": "Many\ntypes",
             "One lineage": "One\nlineage", "PBMC-like": "PBMC-\nlike", "SCoPE2-like": "SCoPE2-\nlike"}
UNGATED = "Phase 3b: s=0.5, correlation in every upload"
GATED = "B: s=0.5, agreement gate 0.4 (chosen)"
SERIES_WITHOUT, SERIES_WITH, SERIES_GAIN = "answer path's guess", "served best guess", "gain"
SERIES_UNGATED, SERIES_GATED = "used in every upload", "gated at the bar"


def _dig(record, *keys):
    for key in keys:
        record = record[key]
    return record


def _agreement() -> list[dict]:
    rows = []
    uploads = common.read_csv(UPLOADS)
    bars = {r["agreement_threshold"] for r in uploads}
    if len(bars) != 1:
        raise ValueError(f"{UPLOADS}: more than one agreement_threshold: {sorted(bars)}")
    bar = float(bars.pop())
    rows.append(common.row("a", "the bar", bar, series="bar", unit="share of cells", source=UPLOADS,
                           field="agreement_threshold (every row)"))
    names = dict(KINDS)
    for key, _ in KINDS:
        for i, r in enumerate(uploads):
            if r["group"] != key:
                continue
            value = float(r["agreement"])
            if (value >= bar) != (r["correlation_term"] == "used"):
                raise ValueError(f"{UPLOADS} row {i + 1}: correlation_term disagrees with the bar")
            rows.append(common.row("a", r["upload"], value, series=names[key], unit="share of cells", source=UPLOADS,
                                   field=f"row {i + 1} ({r['upload']}, {r['group']}): agreement"))
    gate = common.read_json(GATE)
    for key, name in DATASETS:
        if key == "khoury":
            rows.append(common.row("a", name, common.read_json(KHOURY)["upload_agreement"], series="protein dataset",
                                   unit="share of cells", source=KHOURY, field="upload_agreement"))
        else:
            rows.append(common.row("a", name, gate["datasets"][key]["upload_agreement"], series="protein dataset",
                                   unit="share of cells", source=GATE, field=f"datasets > {key} > upload_agreement"))
    return rows


def _gain_rows() -> list[dict]:
    rows = []
    suite = common.read_json(SUITE)["by_scenario"]
    unit = "balanced accuracy, %"
    for key, name in KINDS:
        without = suite["v3.1"][key]["best_guess_per_upload_balanced"]
        with_ = suite["v4.1"][key]["best_guess_per_upload_balanced"]
        field = f"by_scenario > {{}} > {key} > best_guess_per_upload_balanced"
        rows.append(common.row("b", name, without, series=SERIES_WITHOUT, unit=unit, source=SUITE,
                               field=field.format("v3.1")))
        rows.append(common.row("b", name, with_, series=SERIES_WITH, unit=unit, source=SUITE,
                               field=field.format("v4.1")))
        rows.append(common.row("b", name, round(with_ - without, 2), series=SERIES_GAIN, unit="points", source=SUITE,
                               field=field.format("v4.1") + " minus the same for v3.1"))
    # Fulcher (development, in sample for the weight).
    fulcher = common.read_json(DEVELOPMENT)["fulcher2026"]
    name = "Fulcher, protein"
    for series, model in ((SERIES_WITHOUT, "v3.1"), (SERIES_WITH, "v4.1")):
        rows.append(common.row("b", name, fulcher[model]["balanced_accuracy_6_types"], series=series, unit=unit,
                               source=DEVELOPMENT, field=f"fulcher2026 > {model} > balanced_accuracy_6_types"))
    paired = [(i, r) for i, r in enumerate(common.read_csv(FULCHER_PAIRED)) if r["dataset"] == "Fulcher 2026"]
    (i, r), = paired
    rows.append(common.row("b", name, float(r["point_estimate_pct"]), series=SERIES_GAIN, lo=float(r["ci_lo"]),
                           hi=float(r["ci_hi"]), unit="points", source=FULCHER_PAIRED,
                           field=f"row {i + 1} (Fulcher 2026): point_estimate_pct, ci_lo, ci_hi"))
    # Khoury (post hoc).
    scores = common.read_json(KHOURY)["scores"]
    name = "Khoury, protein"
    for series, model in ((SERIES_WITHOUT, "v3.1"), (SERIES_WITH, "v4.1")):
        rows.append(common.row("b", name, scores[model]["balanced_accuracy_pct"], series=series, unit=unit,
                               source=KHOURY, field=f"scores > {model} > balanced_accuracy_pct"))
    (i, r), = [(i, r) for i, r in enumerate(common.read_csv(KHOURY_PAIRED)) if r["comparison"] == "v4.1 vs v3.1"]
    rows.append(common.row("b", name, float(r["diff_bal_acc_pct"]), series=SERIES_GAIN, lo=float(r["ci_lo"]),
                           hi=float(r["ci_hi"]), unit="points", source=KHOURY_PAIRED,
                           field=f"row {i + 1} (v4.1 vs v3.1): diff_bal_acc_pct, ci_lo, ci_hi"))
    # The held-out Hao donors (RNA masked like protein; a one-sided lower bound).
    hao = common.read_json(HAO)
    name = "Hao donors, held out"
    for series, model in ((SERIES_WITHOUT, "v31"), (SERIES_WITH, "v41")):
        rows.append(common.row("b", name, hao["by_model"][model]["coarse_ba_mean"], series=series, unit=unit,
                               source=HAO, field=f"by_model > {model} > coarse_ba_mean"))
    diff = hao["comparisons"]["v31 - v41"]
    rows.append(common.row("b", name, -diff["mean"], series=SERIES_GAIN, lo=-diff["upper_95_one_sided"],
                           unit="points", source=HAO,
                           field="comparisons > v31 - v41: minus mean; lo is minus upper_95_one_sided"))
    return rows


def _gate_rows() -> list[dict]:
    rows = []
    finalists = common.read_json(EXPLORATION)["finalists"]
    for series, arm in ((SERIES_UNGATED, UNGATED), (SERIES_GATED, GATED)):
        for key, name in KINDS:
            rows.append(common.row("c", name, _dig(finalists, arm, "calibration_suite", key), series=series,
                                   unit="points over the answer path", source=EXPLORATION,
                                   field=f"finalists > {arm} > calibration_suite > {key}"))
        rows.append(common.row("c", "chance a type fails, uploads of one type",
                               _dig(finalists, arm, "extra_single_type_uploads", "p_fail"), series=series,
                               unit="probability", source=EXPLORATION,
                               field=f"finalists > {arm} > extra_single_type_uploads > p_fail"))
    return rows


def data() -> list[dict]:
    return _agreement() + _gain_rows() + _gate_rows()


# ---- drawing (lengths in mm) ----

B_BOTTOM, B_H = 12.0, 42.0          # panel b's place
B_ROWS = 9 + 0.6 + 0.2                # its y range in rows: nine rows, a gap, and the margins


def _axes(fig, width, height, left, bottom, w, h):
    return fig.add_axes((left / width, bottom / height, w / width, h / height))


def _letter(ax, letter, title, dx_mm, w_mm, h_mm, dy_mm=3.2):
    ax.text(-dx_mm / w_mm, 1 + dy_mm / h_mm, letter, transform=ax.transAxes, fontsize=style.SIZE_LETTER,
            fontweight="bold", ha="left", va="baseline", color=style.INK)
    ax.text((4.0 - dx_mm) / w_mm, 1 + dy_mm / h_mm, title, transform=ax.transAxes, fontsize=style.SIZE_TITLE,
            ha="left", va="baseline", color=style.INK)


def _panel_a(fig, rows, W, H):
    bar = next(r for r in rows if r["series"] == "bar")["value"]
    kinds = [name for _, name in KINDS]
    sets = [r for r in rows if r["series"] == "protein dataset"]
    xs = {name: i for i, name in enumerate(kinds)}
    for j, r in enumerate(sets):
        xs[r["label"]] = len(kinds) + 0.6 + j
    left, bottom, w, h = 14.0, 75.0, 172.0, 40.0
    ax = _axes(fig, W, H, left, bottom, w, h)
    top = max(1.0, max(r["value"] for r in rows if r["panel"] == "a"))
    ax.set_xlim(-0.6, xs[sets[-1]["label"]] + 0.6)
    ax.set_ylim(-0.03, top)
    ax.axhline(bar, color=style.NEUTRAL, linewidth=style.LINE_WIDTH, zorder=1)
    ax.text(1.0, bar, f" bar {bar:g}", transform=ax.get_yaxis_transform(), ha="left", va="center",
            fontsize=style.SIZE, color=style.INK_SOFT)
    golden = 0.6180339887498949          # a fixed sideways spread, the same on every build
    for name in kinds:
        mine = [r for r in rows if r["series"] == name]
        for k, r in enumerate(mine):
            x = xs[name] + ((k * golden) % 1.0 - 0.5) * 0.62
            colour = style.ACCENT if r["value"] >= bar else style.NEUTRAL
            ax.plot([x], [r["value"]], "o", color=colour, markersize=style.MARKER * 0.8, markeredgecolor=style.PAPER,
                    markeredgewidth=0.3, zorder=3)
    for r in sets:
        colour = style.ACCENT if r["value"] >= bar else style.NEUTRAL
        ax.plot([xs[r["label"]]], [r["value"]], "D", color=colour, markersize=style.MARKER * 1.05,
                markeredgecolor=style.PAPER, markeredgewidth=0.4, zorder=3)
        ax.annotate(f"{r['value']:.2f}", (xs[r["label"]], r["value"]), xytext=(5, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=style.SIZE, color=style.INK_SOFT)
    ax.set_xticks([xs[name] for name in kinds] + [xs[r["label"]] for r in sets])
    ax.set_xticklabels([TWO_LINES.get(n, n) for n in kinds] + [r["label"] for r in sets], fontsize=style.SIZE,
                       color=style.INK_SOFT, linespacing=1.15)
    ax.tick_params(axis="x", length=0, pad=3)
    ax.set_ylabel("Upload agreement", fontsize=style.SIZE_LABEL)
    ax.axvline(len(kinds) - 0.2, color=style.LINE, linewidth=0.6)
    for x0, x1, text in ((-0.5, len(kinds) - 0.5, "Simulated RNA uploads, one dot each"),
                         (len(kinds) + 0.1, xs[sets[-1]["label"]] + 0.5, "Protein datasets, each one upload")):
        ax.text((x0 + x1) / 2, top * 1.02, text, ha="center", va="bottom", fontsize=style.SIZE, color=style.INK_SOFT)
    _letter(ax, "a", "Upload agreement against the bar", 12.0, w, h, dy_mm=7.0)
    from matplotlib.lines import Line2D
    mark = dict(marker="o", linestyle="none", markersize=style.MARKER * 0.8, markeredgecolor=style.PAPER,
                markeredgewidth=0.3)
    ax.legend(handles=[Line2D([], [], color=style.ACCENT, label="second opinion used", **mark),
                       Line2D([], [], color=style.NEUTRAL, label="below the bar: encoder alone", **mark)],
              loc="lower right", bbox_to_anchor=(1.0, 1.0 + 4.6 / h), ncol=2, fontsize=style.SIZE, frameon=False,
              handletextpad=0.3, columnspacing=1.2, borderaxespad=0)


def _panel_b(fig, rows, W, H):
    names = []
    for r in rows:
        if r["label"] not in names:
            names.append(r["label"])
    get = {(r["label"], r["series"]): r for r in rows}
    ys = {name: i + (0.6 if i >= len(KINDS) else 0) for i, name in enumerate(names)}
    left, bottom, w, h = 30.0, B_BOTTOM, 52.0, B_H
    ax = _axes(fig, W, H, left, bottom, w, h)
    values = [r["value"] for r in rows if r["series"] != SERIES_GAIN]
    ax.set_xlim(min(values) - 4, max(values) + 4)
    ax.set_ylim(max(ys.values()) + 0.6, -0.6)
    ax.grid(axis="x", color=style.LINE, linewidth=0.5)
    ax.set_axisbelow(True)
    for name in names:
        y = ys[name]
        a, b = get[(name, SERIES_WITHOUT)]["value"], get[(name, SERIES_WITH)]["value"]
        ax.plot([a, b], [y, y], color=style.NEUTRAL, linewidth=style.MARK_WIDTH, zorder=2)
        ax.plot([a], [y], "o", color=style.NEUTRAL, markersize=style.MARKER, markeredgecolor=style.PAPER,
                markeredgewidth=0.3, zorder=3)
        ax.plot([b], [y], "o", color=style.ACCENT, markersize=style.MARKER, markeredgecolor=style.PAPER,
                markeredgewidth=0.3, zorder=4)
        g = get[(name, SERIES_GAIN)]
        if g["lo"] is not None and g["hi"] is not None:
            text = f"{g['value']:+.1f} ({g['lo']:.1f} to {g['hi']:.1f})"
        elif g["lo"] is not None:
            text = f"{g['value']:+.1f} (lower bound {g['lo']:.1f})"
        else:
            text = f"{g['value']:+.1f}"
        ax.text(1.0 + 2.0 / w, y, text, transform=ax.get_yaxis_transform(), ha="left", va="center",
                fontsize=style.SIZE, color=style.INK_SOFT)
    ax.text(1.0 + 2.0 / w, -0.6, "gain, points", transform=ax.get_yaxis_transform(), ha="left", va="bottom",
            fontsize=style.SIZE, color=style.INK_FAINT)
    ax.set_yticks([ys[n] for n in names])
    ax.set_yticklabels(names, fontsize=style.SIZE, color=style.INK_SOFT)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Best guess, balanced accuracy (%)", fontsize=style.SIZE_LABEL)
    _letter(ax, "b", "The served best guess against the answer path's", 28.0, w, h, dy_mm=7.0)
    from matplotlib.lines import Line2D
    mark = dict(marker="o", linestyle="none", markersize=style.MARKER, markeredgecolor=style.PAPER,
                markeredgewidth=0.3)
    ax.legend(handles=[Line2D([], [], color=style.NEUTRAL, label=SERIES_WITHOUT, **mark),
                       Line2D([], [], color=style.ACCENT, label=SERIES_WITH, **mark)],
              loc="lower left", bbox_to_anchor=(-28.0 / w, 1.0 + 0.6 / h), ncol=2, fontsize=style.SIZE,
              frameon=False, handletextpad=0.3, columnspacing=1.2, borderaxespad=0)


def _panel_c(fig, rows, W, H):
    kinds = [name for _, name in KINDS]
    get = {(r["label"], r["series"]): r for r in rows}
    # Rows as tall as panel b's (B_ROWS units over its height), aligned to its top.
    left, w = 138.0, 46.0
    h = B_H * (len(kinds) + 0.2) / B_ROWS
    bottom = B_BOTTOM + B_H - h
    ax = _axes(fig, W, H, left, bottom, w, h)
    values = [get[(n, s)]["value"] for n in kinds for s in (SERIES_UNGATED, SERIES_GATED)]
    lo, hi = min(min(values), 0.0), max(values)
    pad = 0.08 * (hi - lo)
    ax.set_xlim(lo - pad, hi + pad)
    ax.set_ylim(len(kinds) - 1 + 0.6, -0.6)
    ax.grid(axis="x", color=style.LINE, linewidth=0.5)
    ax.set_axisbelow(True)
    ax.axvline(0, color=style.NEUTRAL, linewidth=style.LINE_WIDTH, zorder=1)
    for y, name in enumerate(kinds):
        a, b = get[(name, SERIES_UNGATED)]["value"], get[(name, SERIES_GATED)]["value"]
        ax.plot([a, b], [y, y], color=style.LINE, linewidth=style.MARK_WIDTH, zorder=2)
        ax.plot([a], [y], "o", markerfacecolor=style.PAPER, markeredgecolor=style.ACCENT, markeredgewidth=1.0,
                markersize=style.MARKER, zorder=3)
        ax.plot([b], [y], "o", color=style.ACCENT, markeredgecolor=style.PAPER, markeredgewidth=0.3,
                markersize=style.MARKER, zorder=4)
    ax.set_yticks(range(len(kinds)))
    ax.set_yticklabels(kinds, fontsize=style.SIZE, color=style.INK_SOFT)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Gain over the answer path (points)", fontsize=style.SIZE_LABEL)
    _letter(ax, "c", "The gate, chosen in development", 26.0, w, h, dy_mm=7.0)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="o", linestyle="none", markerfacecolor=style.PAPER,
                              markeredgecolor=style.ACCENT, markeredgewidth=1.0, markersize=style.MARKER,
                              label=SERIES_UNGATED),
                       Line2D([], [], marker="o", linestyle="none", color=style.ACCENT, markeredgecolor=style.PAPER,
                              markeredgewidth=0.3, markersize=style.MARKER, label=SERIES_GATED)],
              loc="lower left", bbox_to_anchor=(-26.0 / w, 1.0 + 0.6 / h), ncol=2, fontsize=style.SIZE,
              frameon=False, handletextpad=0.3, columnspacing=1.0, borderaxespad=0)
    fail = {r["series"]: r["value"] for r in rows if r["label"].startswith("chance a type fails")}
    ax.text(-26.0 / w, -13.0 / h, "Chance a type fails on uploads of one type:\n"
            f"{SERIES_UNGATED} {fail[SERIES_UNGATED]:g}, {SERIES_GATED} {fail[SERIES_GATED]:g}",
            transform=ax.transAxes, ha="left", va="top", fontsize=style.SIZE, color=style.INK_SOFT, linespacing=1.3)


def draw(rows, plt):
    W, H = style.WIDTHS_MM[WIDTH], 124.0
    fig = common.new_figure(plt, WIDTH, H)
    _panel_a(fig, [r for r in rows if r["panel"] == "a"], W, H)
    _panel_b(fig, [r for r in rows if r["panel"] == "b"], W, H)
    _panel_c(fig, [r for r in rows if r["panel"] == "c"], W, H)
    return fig
