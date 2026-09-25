"""Gene identifier resolution (Track B).

Maps whatever identifier convention an uploaded file uses — gene symbols
(case-insensitive), Ensembl gene IDs, UniProt accessions, or a DIA-NN-style
semicolon-separated protein group of any of these — onto this service's
fixed 9,002-gene feature space, using a frozen, versioned, offline-built
mapping table (`gene_id_map_v1.tsv`, built from HGNC's public bulk dataset;
see `gene_id_map_v1_provenance.json` alongside it for the source, download
date, and sha256). Never calls a live identifier-lookup service (MyGene or
otherwise) at request time — symbol drift from a live lookup already
corrupted an earlier build of this project.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from service import config


@dataclass(frozen=True)
class GeneIdMap:
    symbol_to_feature: dict[str, str]  # UPPERCASE symbol -> feature-space gene symbol
    ensembl_to_feature: dict[str, str]  # Ensembl gene ID -> feature-space gene symbol
    uniprot_to_feature: dict[str, str]  # UniProt accession -> feature-space gene symbol
    feature_genes: frozenset[str]  # every feature-space gene symbol, for quick membership checks


def load_gene_id_map(path: Path = config.GENE_ID_MAP_PATH) -> GeneIdMap:
    """`match_type == "ambiguous"` rows (a feature-space gene whose own HGNC
    resolution was itself ambiguous — see the provenance file) contribute
    only their symbol; they never gain an Ensembl/UniProt cross-reference,
    since guessing one of several disagreeing HGNC candidates would be
    exactly the kind of silent guess this table exists to avoid."""
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    symbol_to_feature: dict[str, str] = {}
    ensembl_to_feature: dict[str, str] = {}
    uniprot_to_feature: dict[str, str] = {}

    for _, row in df.iterrows():
        feature_symbol = row["gene_symbol"]
        symbol_to_feature[feature_symbol.upper()] = feature_symbol
        if row["match_type"] == "ambiguous":
            continue
        if row["ensembl_gene_id"]:
            ensembl_to_feature[row["ensembl_gene_id"]] = feature_symbol
        if row["uniprot_ids"]:
            for accession in row["uniprot_ids"].split("|"):
                if accession:
                    uniprot_to_feature[accession] = feature_symbol

    return GeneIdMap(
        symbol_to_feature=symbol_to_feature,
        ensembl_to_feature=ensembl_to_feature,
        uniprot_to_feature=uniprot_to_feature,
        feature_genes=frozenset(df["gene_symbol"]),
    )


@dataclass(frozen=True)
class ResolvedIdentifiers:
    resolved: list[str | None]  # per input identifier, the feature-space symbol, or None
    matched: int
    unmapped: int
    ambiguous: int
    unmapped_identifiers: list[str]
    ambiguous_identifiers: list[str]


def _uniprot_base_accession(accession: str) -> str:
    """UniProt isoform notation (e.g. P12345-2) numbers one spliced variant
    of the same gene product; gene_id_map_v1.tsv's uniprot_ids column only
    ever stores the base accession before the hyphen."""
    return accession.split("-", 1)[0]


def _resolve_one(identifier: str, gene_map: GeneIdMap) -> tuple[str | None, str]:
    """A semicolon-separated group (the DIA-NN convention for an
    unresolved protein group) tries every member as a symbol, Ensembl ID,
    or UniProt accession; if the members that resolve at all agree on one
    feature-space gene, that's a match; if they resolve to more than one
    different feature-space gene, the group is ambiguous, not a guess."""
    parts = [p.strip() for p in identifier.split(";") if p.strip()]
    if not parts:
        return None, "unmapped"

    candidates: set[str] = set()
    for part in parts:
        upper = part.upper()
        if upper in gene_map.symbol_to_feature:
            candidates.add(gene_map.symbol_to_feature[upper])
        elif part in gene_map.ensembl_to_feature:
            candidates.add(gene_map.ensembl_to_feature[part])
        elif part in gene_map.uniprot_to_feature:
            candidates.add(gene_map.uniprot_to_feature[part])
        elif "-" in part and _uniprot_base_accession(part) in gene_map.uniprot_to_feature:
            candidates.add(gene_map.uniprot_to_feature[_uniprot_base_accession(part)])

    if len(candidates) == 1:
        return next(iter(candidates)), "matched"
    if len(candidates) > 1:
        return None, "ambiguous"
    return None, "unmapped"


def resolve_identifiers(identifiers: list[str], gene_map: GeneIdMap | None = None) -> ResolvedIdentifiers:
    """Resolves a list of raw uploaded identifiers to feature-space gene
    symbols. Order-preserving and duplicate-preserving: callers that need
    per-row matching (e.g. alignment.py's gene-to-column lookup) can zip
    this against their own identifier list unchanged."""
    gene_map = gene_map or load_gene_id_map()
    resolved: list[str | None] = []
    unmapped_ids: list[str] = []
    ambiguous_ids: list[str] = []

    for identifier in identifiers:
        symbol, status = _resolve_one(identifier, gene_map)
        resolved.append(symbol)
        if status == "unmapped":
            unmapped_ids.append(identifier)
        elif status == "ambiguous":
            ambiguous_ids.append(identifier)

    return ResolvedIdentifiers(
        resolved=resolved,
        matched=sum(1 for r in resolved if r is not None),
        unmapped=len(unmapped_ids),
        ambiguous=len(ambiguous_ids),
        unmapped_identifiers=unmapped_ids,
        ambiguous_identifiers=ambiguous_ids,
    )


def resolve_to_feature_symbols(identifiers: list[str], gene_map: GeneIdMap | None = None) -> list[str | None]:
    """The one call alignment.align_to_feature_space adds, immediately
    before its existing gene-to-column matching loop: translates whatever
    identifier convention the upload used into feature-space gene symbols
    (or None, which the existing `gene_index.get(gene)` lookup already
    treats as "not in the feature space", exactly like an unrecognised
    symbol always has)."""
    return resolve_identifiers(identifiers, gene_map).resolved
