"""The Manuscript page's figures and the Methods illustrations, drawn from
the repository's committed data by scripts/build_figures.py.

Each module here is one figure. It names itself and where it goes, and
splits what it shows from how it is drawn:

    NAME = "fig2-transfer"         # the file stem under web/figures/
    TITLE = "Figure 2"             # how the page and the paper call it
    SECTION = "transfer"           # the Manuscript section it sits in (an id on web/manuscript.html)
    WIDTH = "double"               # a journal width in style.WIDTHS_MM
    ALT = "..."                    # what the picture shows, in words, for a screen reader
    CAPTION = "..."                # its legend: what each panel shows (no result numbers: those are the data's)
    SOURCES = ("research/...",)    # the committed files it reads

    def data() -> list[dict]       # every number drawn, with the file and field it came from
                                   # (standard library only, so the scripts suite checks it anywhere)
    def draw(rows, plt) -> Figure  # the picture, from those rows alone (matplotlib, passed in)

Nothing in a figure is typed in: a number drawn is a row of data(), read
from a committed record, and common.save writes those rows beside the
picture as CSV.
"""
