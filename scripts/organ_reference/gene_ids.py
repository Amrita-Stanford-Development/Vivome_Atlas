"""An organ's gene identifier map, so an upload's symbols, Ensembl IDs and
UniProt accessions resolve onto the organ's own gene space
(service/pipeline/gene_ids.py reads it). Blood's served map,
service/model/runtime/gene_id_map_v1.tsv, covers blood's 9,002 genes only:
read with it, every gene the colon adds would be dropped from a colon upload.

The rule is gene_id_map_v1_provenance.json's, from HGNC's complete set: an
exact symbol match first (case-insensitive); only when there is none, HGNC's
alias and previous symbols, accepted when every matching row agrees on one
Ensembl gene ID, otherwise ambiguous with every candidate HGNC ID listed. A
gene HGNC does not know keeps its symbol only (match_type "unmapped").
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNS = ["gene_symbol", "hgnc_id", "ensembl_gene_id", "uniprot_ids", "match_type", "ambiguous_candidates"]


def _split(value: str) -> list[str]:
    return [v.strip().upper() for v in str(value).split("|") if v.strip()]


def build(genes: list[str], hgnc_path: Path) -> pd.DataFrame:
    hgnc = pd.read_csv(hgnc_path, sep="\t", dtype=str, keep_default_na=False, low_memory=False)
    by_symbol: dict[str, list[int]] = {}
    by_other: dict[str, list[int]] = {}
    for i, r in hgnc.iterrows():
        by_symbol.setdefault(r["symbol"].upper(), []).append(i)
        for s in set(_split(r["alias_symbol"]) + _split(r["prev_symbol"])):
            by_other.setdefault(s, []).append(i)
    rows = []
    for g in genes:
        direct = by_symbol.get(g.upper(), [])
        if len(direct) == 1:
            r = hgnc.loc[direct[0]]
            rows.append([g, r["hgnc_id"], r["ensembl_gene_id"], r["uniprot_ids"], "symbol", ""])
            continue
        hits = direct or by_other.get(g.upper(), [])
        ensembl = {hgnc.loc[i, "ensembl_gene_id"] for i in hits}
        if hits and len(ensembl) == 1 and "" not in ensembl and not direct:
            r = hgnc.loc[hits[0]]
            rows.append([g, r["hgnc_id"], r["ensembl_gene_id"], r["uniprot_ids"], "alias_or_prev_symbol", ""])
        elif hits:
            ids = sorted({hgnc.loc[i, "hgnc_id"] for i in hits}, key=lambda h: int(h.split(":")[1]))
            rows.append([g, "", "", "", "ambiguous", "|".join(ids)])
        else:
            rows.append([g, "", "", "", "unmapped", ""])
    return pd.DataFrame(rows, columns=COLUMNS)
