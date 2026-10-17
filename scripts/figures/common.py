"""What every figure shares: reading committed records with their source,
writing the drawn numbers as CSV, saving the picture (SVG for the page,
PDF and TIFF for the journal), and the boxes and arrows of a schematic.

Reading and the CSV are standard library only, so the scripts suite checks
each figure's numbers on any Python; drawing and saving import matplotlib
when called (the vivome environment has it).
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from . import style

REPO = Path(__file__).resolve().parents[2]
WEB_FIGURES = REPO / "web" / "figures"                      # what the page shows: SVG and CSV, committed
JOURNAL = REPO / "research" / "figures" / "journal"         # PDF and TIFF for the paper, on request, gitignored

# The CSV's columns, in this order; a row may leave any of them empty.
COLUMNS = ("panel", "series", "label", "value", "lo", "hi", "unit", "source", "field")


# ---- reading committed records ----

def read_json(rel: str):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def read_csv(rel: str) -> list[dict]:
    with open(REPO / rel, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def measured(record):
    """A manifest-style record's value ({"value", "status": "measured"}), else None."""
    if isinstance(record, dict):
        return record.get("value") if record.get("status") == "measured" else None
    return record


def row(panel: str, label: str, value, *, series: str = "", lo=None, hi=None, unit: str = "",
        source: str, field: str) -> dict:
    """One number drawn, and exactly where it came from (a committed file and a field in it)."""
    if not (REPO / source).exists():
        raise FileNotFoundError(f"{source} is not in the repository")
    return {"panel": panel, "series": series, "label": label, "value": value, "lo": lo, "hi": hi,
            "unit": unit, "source": source, "field": field}


def csv_text(rows: list[dict]) -> str:
    """The rows as CSV, LF line ends, numbers as written in their sources."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for r in rows:
        writer.writerow(["" if r.get(c) is None else r.get(c) for c in COLUMNS])
    return out.getvalue()


# ---- drawing and saving ----

def apply_style(plt) -> None:
    """The house style, and what makes an SVG the same byte for byte on every build."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": list(style.FONT_FALLBACK),
        "font.size": style.SIZE,
        "axes.titlesize": style.SIZE_TITLE,
        "axes.labelsize": style.SIZE_LABEL,
        "xtick.labelsize": style.SIZE,
        "ytick.labelsize": style.SIZE,
        "legend.fontsize": style.SIZE,
        "axes.edgecolor": style.INK,
        "axes.labelcolor": style.INK,
        "xtick.color": style.INK_FAINT,
        "ytick.color": style.INK_FAINT,
        "text.color": style.INK,
        "axes.linewidth": style.LINE_WIDTH,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "grid.color": style.LINE,
        "grid.linewidth": 0.6,
        "legend.frameon": False,
        "figure.facecolor": style.PAPER,
        "savefig.facecolor": style.PAPER,
        "svg.fonttype": "none",          # text stays text: crisp, searchable, small
        "svg.hashsalt": "vivome-figures",
        "pdf.fonttype": 42,              # fonts embedded whole, as journals ask
        "path.simplify": False,
    })


def new_figure(plt, width: str = "double", height_mm: float = 80.0, **kwargs):
    apply_style(plt)
    return plt.figure(figsize=(style.WIDTHS_MM[width] * style.MM, height_mm * style.MM), **kwargs)


def panel_letter(ax, letter: str, x: float = -0.08, y: float = 1.04) -> None:
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=style.SIZE_LETTER, fontweight="bold",
            va="bottom", ha="left", color=style.INK)


def svg_bytes(fig) -> bytes:
    out = io.BytesIO()
    fig.savefig(out, format="svg", metadata={"Date": None, "Creator": None}, bbox_inches="tight", pad_inches=0.04)
    return out.getvalue().replace(b"\r\n", b"\n")


def pyplot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def render(module) -> bytes:
    """A figure module's SVG, as save writes it."""
    plt = pyplot()
    fig = module.draw(module.data(), plt)
    try:
        return svg_bytes(fig)
    finally:
        plt.close(fig)


def save(module, *, journal: bool = False, web_dir: Path = WEB_FIGURES, journal_dir: Path = JOURNAL) -> dict:
    """Draws one figure module and writes web/figures/<NAME>.svg and NAME.csv (and,
    with journal, research/figures/journal/<NAME>.pdf and NAME.tif at 600 dpi)."""
    plt = pyplot()
    rows = module.data()
    fig = module.draw(rows, plt)
    web_dir.mkdir(parents=True, exist_ok=True)
    svg = web_dir / f"{module.NAME}.svg"
    svg.write_bytes(svg_bytes(fig))
    table = web_dir / f"{module.NAME}.csv"
    table.write_bytes(csv_text(rows).encode("utf-8"))
    written = {"svg": svg, "csv": table}
    if journal:
        journal_dir.mkdir(parents=True, exist_ok=True)
        pdf = journal_dir / f"{module.NAME}.pdf"
        fig.savefig(pdf, format="pdf", metadata={"CreationDate": None, "Creator": None}, bbox_inches="tight", pad_inches=0.04)
        tif = journal_dir / f"{module.NAME}.tif"
        fig.savefig(tif, format="tiff", dpi=600, bbox_inches="tight", pad_inches=0.04,
                    pil_kwargs={"compression": "tiff_lzw"})
        written.update({"pdf": pdf, "tif": tif})
    plt.close(fig)
    return written


# ---- schematics: boxes and arrows on a canvas measured in mm ----

def canvas(fig, width_mm: float, height_mm: float):
    """An axes filling the figure, in mm from the bottom left, with nothing drawn."""
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, width_mm)
    ax.set_ylim(0, height_mm)
    ax.set_axis_off()
    return ax


def box(ax, x: float, y: float, w: float, h: float, text: str = "", *, fill: str = style.PAPER,
        edge: str = style.INK, text_colour: str = style.INK, size: float = style.SIZE_LABEL,
        weight: str = "normal", radius: float = 1.6, line: float = style.LINE_WIDTH):
    """A rounded box with its lower-left corner at (x, y), text centred (use \\n to break lines)."""
    from matplotlib.patches import FancyBboxPatch
    patch = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}",
                           facecolor=fill, edgecolor=edge, linewidth=line)
    ax.add_patch(patch)
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=text_colour,
                fontweight=weight, linespacing=1.25)
    return patch


def arrow(ax, start, end, *, colour: str = style.INK, line: float = style.MARK_WIDTH, head: float = 5.0,
          curve: float = 0.0, dashed: bool = False):
    """An arrow from start to end (mm); curve bends it (positive to the left)."""
    from matplotlib.patches import FancyArrowPatch
    patch = FancyArrowPatch(start, end, arrowstyle=f"-|>,head_length={head / 10:.2f},head_width={head / 20:.2f}",
                            connectionstyle=f"arc3,rad={curve}", color=colour, linewidth=line,
                            linestyle="--" if dashed else "-", shrinkA=0, shrinkB=0, mutation_scale=10)
    ax.add_patch(patch)
    return patch


def note(ax, x: float, y: float, text: str, *, size: float = style.SIZE, colour: str = style.INK_SOFT,
         ha: str = "left", va: str = "center", weight: str = "normal"):
    return ax.text(x, y, text, ha=ha, va=va, fontsize=size, color=colour, fontweight=weight, linespacing=1.25)
