"""Accessions this package must never open.

PXD042367, MSV000094189 and PXD052341 are the organ references' locked
tests and PXD061065 is the reserve (research/benchmark/side-tests.md). They
sit on disk beside the development sets, so every path, URL and accession
the corpus tools touch is checked here first, and nothing globs the folder
that holds them.
"""
from __future__ import annotations

SEALED = frozenset({"PXD042367", "MSV000094189", "PXD052341", "PXD061065"})


class SealedData(RuntimeError):
    """Raised before a sealed accession is read."""


def check(*texts: object) -> None:
    """Raises SealedData when any text (a path, URL or accession) names a
    sealed accession, in any letter case."""
    for text in texts:
        upper = str(text).upper()
        for accession in SEALED:
            if accession in upper:
                raise SealedData(f"{accession} is sealed and must not be opened ({text})")
