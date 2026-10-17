"""One look for every figure and illustration: the site's colours, one font,
the journal's widths. Standard library only (matplotlib settings are plain
values, applied by common.apply_style).

Colours are web/css/page.css's tokens. RNA and protein keep the colours the
site reserves for them; the categorical order below passed the dataviz
palette validator (light surface, every adjacent pair clear under colour
blindness, 2026-10-17). Cell types are named by position on an axis, not by
22 colours.
"""

INK = "#1D2B36"          # --ink: text, axes, outlines
INK_SOFT = "#4B4B4B"     # --ink-soft: secondary text
INK_FAINT = "#666666"    # --ink-faint: notes, tick labels
LINE = "#E4E3DE"         # --line: grid and rules
WELL = "#ECEBE7"         # --well: quiet fills
PAPER = "#FFFFFF"        # --paper: the figure's ground
FIELD = "#EAF0F6"        # --field: a panel's soft ground
ACCENT = "#0066A3"       # --accent: VivOME, the served model
RNA = "#C8641E"          # --rna
PROT = "#2F8F6A"         # --prot
NEUTRAL = "#8A96A0"      # no answer, and anything set apart

# Categorical identity, in this fixed order (never cycled; a fifth series
# goes to small multiples or "other").
CATEGORICAL = (ACCENT, RNA, PROT, "#8E5BB5")

# Answer levels, deepest first: one type, a family, a branch (one hue, light
# to dark as the answer gets more specific), then no answer in grey.
LEVELS = {"class": "#0066A3", "group": "#4F93C2", "lineage": "#A9C9E3", "none": NEUTRAL}

FONT = "Arial"
FONT_FALLBACK = ("Arial", "Helvetica", "DejaVu Sans")
SIZE = 7.0               # pt: tick labels, notes
SIZE_LABEL = 7.5         # pt: axis labels, box text
SIZE_TITLE = 8.0         # pt: panel titles
SIZE_LETTER = 9.0        # pt: panel letters, bold

# Journal widths in mm (Elsevier's single, one-and-a-half and double column).
WIDTHS_MM = {"single": 90.0, "one-half": 140.0, "double": 190.0}
MM = 1 / 25.4            # inches per mm

LINE_WIDTH = 0.8         # pt: axes and outlines
MARK_WIDTH = 1.2         # pt: data lines and interval whiskers
MARKER = 4.0             # pt: dot size
