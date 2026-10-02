#!/usr/bin/env python3
"""Fail if any repo path cited in the repo's own text doesn't exist.

Every number in this project cites the committed file it came from, and the
site, scripts and docs all hard-code paths to each other — so a moved or
renamed file silently breaks provenance unless something checks. This does,
over every tracked (and untracked, not-ignored) text file:

- Markdown links `[..](target)` and HTML `href=`/`src=` targets, resolved
  relative to the file that contains them;
- path mentions anywhere in text (backticked or not) whose first segment is a
  top-level folder — resolved from the repo root, or from the citing file's
  own folder (so `css/page.css` inside `web/*.html` counts);
- `.gitattributes` LFS entries, which must name real files;
- when `docs/file-index.md` exists, that every tracked file is listed in it
  (exact path or glob line), so the index can't rot as the project grows.

Only tokens that look like real paths are checked (a file extension, or a
trailing `/`), so prose like "data/metadata split" is left alone. Lines of a
directory-tree drawing (├ └ │) are skipped: their names are relative to the
branch they hang from.

    python scripts/check_paths.py        # exit 1 and a list if anything is broken
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Old top-level names are checked too, so a reference left behind by a move
# is caught instead of silently dangling.
RETIRED_TOP_LEVEL = {"Atlas", "Plots", "Documentation", "tools", "tests", "css", "js", "New_Files"}

TEXT_SUFFIXES = {".md", ".html", ".js", ".py", ".json", ".txt", ".yml", ".yaml"}
MAX_BYTES = 1_000_000  # skips large generated files (data tables, exports)

# Paths cited on purpose that don't exist in a checkout: gitignored local
# caches and staging areas, files removed by design and named only in the
# historical record, files the roadmap says a future track will create, and
# Google Drive paths ("Vivome - Live Atlas/Data/...") in provenance records.
ALLOWED_MISSING = (
    "benchmark/results/",
    "data/incoming/",
    "data/external",
    "data/registry.yaml",
    "service/model/v3_pending/",
    "service/model/v3_1/",
    "Atlas/shared_genes_lat128.txt",
    "Atlas/Data/",
    "benchmark/PROTOCOL.md",
    "web/plots/",  # the original-model plots, removed 2026-09-30
    "research/benchmark/khoury2026/",  # Khoury's tables, written once, at the final evaluation
    "dist/",  # the Pages build output (scripts/build_pages_site.py), gitignored
)

# Frozen historical records: their code samples use paths relative to files
# of their own era, so they are neither checked nor rewritten.
FROZEN = ("research/archive/", "scripts/check_paths.py")

MD_LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_ATTR = re.compile(r"(?:href|src)=\"([^\"]+)\"")
PATH_TOKEN = re.compile(r"(?<![\w/.~-])((?:\.\.?/)*([A-Za-z_][\w-]*)/(?:[\w./-]*[\w/])?)(?![\w/-])")


def repo_files(*, include_untracked: bool = True) -> list[str]:
    args = ["git", "ls-files", "--cached"] + (["--others", "--exclude-standard"] if include_untracked else [])
    out = subprocess.run(args, cwd=REPO, capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if (REPO / p).exists()]


def _looks_like_path(token: str) -> bool:
    last = token.rstrip("/").rsplit("/", 1)[-1]
    return token.endswith("/") or bool(re.search(r"\.[A-Za-z0-9]{1,6}$", last))


def _allowed(token: str) -> bool:
    bare = re.sub(r"^(\.\.?/)+", "", token)
    return any(bare.startswith(a) or a.startswith(bare) and bare.endswith("/") for a in ALLOWED_MISSING)


def _resolves(token: str, source: Path) -> bool:
    token = token.split("#", 1)[0].split("?", 1)[0]
    if not token:
        return True
    # A browser resolves a JS module's fetch() against the page, one folder up.
    candidates = [source.parent / token, source.parent.parent / token]
    if not token.startswith("."):
        candidates.append(REPO / token)
    return any(c.exists() for c in candidates)


def check_text_file(rel: str, top_level: set[str]) -> list[str]:
    path = REPO / rel
    if rel.startswith(FROZEN) or path.suffix not in TEXT_SUFFIXES or path.stat().st_size > MAX_BYTES:
        return []
    problems = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        targets = []
        if path.suffix == ".md":
            targets += [("link", t) for t in MD_LINK.findall(line)]
        if path.suffix == ".html":
            targets += [("link", t) for t in HTML_ATTR.findall(line)]
        for kind, target in targets:
            if re.match(r"^(https?:|mailto:|#|javascript:|data:)|\$\{", target):
                continue
            if not _resolves(target, path) and not _allowed(target):
                problems.append(f"{rel}:{lineno}: broken {kind}: {target}")
        # A directory-tree drawing names folders relative to their branch.
        tree_line = bool(re.search("[├└│]", line))
        for token, first in [] if tree_line else PATH_TOKEN.findall(line):
            if first not in top_level or not _looks_like_path(token) or re.search(r"[*{}<>$]|\.\.\.", token):
                continue
            if not _resolves(token, path) and not _allowed(token):
                problems.append(f"{rel}:{lineno}: missing path: {token}")
    return problems


def check_gitattributes() -> list[str]:
    problems = []
    for lineno, line in enumerate((REPO / ".gitattributes").read_text().splitlines(), 1):
        entry = line.split("#", 1)[0].split()
        if entry and "filter=lfs" in line and not re.search(r"[*?\[]", entry[0]) and not (REPO / entry[0]).exists():
            problems.append(f".gitattributes:{lineno}: LFS entry names a missing file: {entry[0]}")
    return problems


def check_file_index(tracked: list[str]) -> list[str]:
    index = REPO / "docs" / "file-index.md"
    if not index.exists():
        return []
    entries = set(re.findall(r"`([^`]+)`", index.read_text(encoding="utf-8")))
    patterns = [e for e in entries if re.search(r"[*?\[]", e)]
    return [
        f"docs/file-index.md: not listed: {f}"
        for f in tracked
        if f not in entries and not any(fnmatch.fnmatch(f, p) for p in patterns)
    ]


def find_problems() -> list[str]:
    files = repo_files()
    top_level = {p.split("/", 1)[0] for p in files if "/" in p} | RETIRED_TOP_LEVEL
    problems = [p for rel in files for p in check_text_file(rel, top_level)]
    problems += check_gitattributes()
    problems += check_file_index(repo_files(include_untracked=False))
    return problems


if __name__ == "__main__":
    found = find_problems()
    print("\n".join(found) if found else "check_paths: every cited path resolves")
    sys.exit(1 if found else 0)
