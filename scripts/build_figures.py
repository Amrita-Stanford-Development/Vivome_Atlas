"""Draws the Manuscript page's figures and the Methods illustrations from the
repository's committed data (scripts/figures/, one module per figure).

Writes web/figures/<NAME>.svg (what the page shows) and NAME.csv (every number
drawn, with its source and field) for each, and web/figures/index.json (each
figure's title, legend, alt text and section, which the page places them
by); with --journal, also
research/figures/journal/<NAME>.pdf and a 600 dpi NAME.tif for the paper
(gitignored: rebuilt on request). Needs matplotlib: run it in the vivome
environment.

    python scripts/build_figures.py                 # every figure
    python scripts/build_figures.py fig5-benchmark  # some, by NAME
    python scripts/build_figures.py --journal       # and the journal's files
"""
from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figures import common  # noqa: E402

FIGURES_DIR = Path(__file__).resolve().parent / "figures"
SHARED = {"common", "style"}


def modules() -> list:
    """Every figure module in scripts/figures/, in file-name order."""
    found = []
    for info in sorted(pkgutil.iter_modules([str(FIGURES_DIR)]), key=lambda m: m.name):
        if info.name in SHARED or info.name.startswith("_"):
            continue
        module = importlib.import_module(f"figures.{info.name}")
        for attr in ("NAME", "TITLE", "SECTION", "WIDTH", "ALT", "CAPTION", "SOURCES", "data", "draw"):
            if not hasattr(module, attr):
                raise AttributeError(f"scripts/figures/{info.name}.py has no {attr}")
        found.append(module)
    return found


def index(found: list | None = None) -> bytes:
    """web/figures/index.json: each figure's title, legend, alt text, section and
    sources, so the Manuscript page places and captions it from one source."""
    entries = [{
        "name": m.NAME, "title": m.TITLE, "section": m.SECTION, "width": m.WIDTH,
        "alt": m.ALT, "caption": m.CAPTION, "sources": list(m.SOURCES),
        "svg": f"figures/{m.NAME}.svg", "csv": f"figures/{m.NAME}.csv",
    } for m in (modules() if found is None else found)]
    return (json.dumps({"figures": entries}, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*", help="figure NAMEs to draw (default: all)")
    parser.add_argument("--journal", action="store_true", help="also write PDF and 600 dpi TIFF")
    args = parser.parse_args()
    chosen = [m for m in modules() if not args.names or m.NAME in args.names]
    missing = set(args.names) - {m.NAME for m in chosen}
    if missing:
        raise SystemExit(f"no figure named {', '.join(sorted(missing))}")
    for module in chosen:
        written = common.save(module, journal=args.journal)
        print(f"{module.NAME}: " + ", ".join(p.relative_to(common.REPO).as_posix() for p in written.values()))
    common.WEB_FIGURES.mkdir(parents=True, exist_ok=True)
    (common.WEB_FIGURES / "index.json").write_bytes(index())
    print("web/figures/index.json")


if __name__ == "__main__":
    main()
