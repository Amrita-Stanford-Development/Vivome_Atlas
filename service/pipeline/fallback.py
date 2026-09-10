"""Stage 7 — hierarchical fallback (Claude_Code_Context_Brief.md, "Stage 7").

Six pairs of adjacent cell types were found genuinely confusable across
independent tests, each reflecting a real biological continuum rather than
a modelling failure. When a conformal set's members fall *entirely* within
one of these pairs, the broader shared category is a more honest answer
than either specific label and more useful than an empty set. This is
different from generic abstention: the model has real partial information
here, it simply cannot resolve the last step, so these cells are reported
resolved (abstained=False), not ambiguous.

Two of the phrases in the brief name the same unordered pair — "CD8 positive
T cell and natural killer cell" and, later, "natural killer cell and CD8 T
cell" — found independently in the controlled RNA test and in the real
SCoPE2 projection respectively. That is the brief's point about the finding
holding "across independent tests, not as an artefact of any one dataset",
not a sixth distinct pair, so the table below has five entries. Where one of
the 22 reference classes already names the shared parent exactly (naive CD4
T cell / CD4 T cell more broadly; intermediate / classical monocyte, both of
which already have "cd4-positive, alpha-beta t cell" and "monocyte" as
existing classes), the fallback reuses that class rather than inventing a
label the reference doesn't otherwise have.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfusablePair:
    members: frozenset[str]  # class_name (lowercase, as in reference_metadata.csv)
    fallback_label: str


# class_name values exactly as they appear in reference_metadata.csv.
CONFUSABLE_PAIRS: tuple[ConfusablePair, ...] = (
    ConfusablePair(
        members=frozenset({"macrophage", "monocyte"}),
        fallback_label="monocyte/macrophage lineage",
    ),
    ConfusablePair(
        members=frozenset({
            "naive thymus-derived cd4-positive, alpha-beta t cell",
            "cd4-positive, alpha-beta t cell",
        }),
        fallback_label="cd4-positive, alpha-beta t cell",  # the existing broader class
    ),
    ConfusablePair(
        members=frozenset({"cd8-positive, alpha-beta t cell", "natural killer cell"}),
        fallback_label="cytotoxic lymphocyte (cd8 t cell / nk cell)",
    ),
    ConfusablePair(
        members=frozenset({"mature nk t cell", "cd8-positive, alpha-beta t cell"}),
        fallback_label="cytotoxic lymphocyte (nkt / cd8 t cell)",
    ),
    ConfusablePair(
        members=frozenset({"intermediate monocyte", "classical monocyte"}),
        fallback_label="monocyte",  # the existing broader class
    ),
)

_PAIR_BY_MEMBERS = {pair.members: pair for pair in CONFUSABLE_PAIRS}


def resolve_fallback(label_set_class_names: list[str]) -> str | None:
    """label_set_class_names: the conformal set's class names for one cell.
    Returns the shared fallback label if the set is exactly a known
    confusable pair, else None (not resolvable this way)."""
    if len(label_set_class_names) != 2:
        return None
    pair = _PAIR_BY_MEMBERS.get(frozenset(label_set_class_names))
    return pair.fallback_label if pair else None
