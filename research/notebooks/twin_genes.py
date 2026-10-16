"""Protein groups that name several genes on the shared list (the Workflow
page's "measured with a twin"): should the service use them? (research/
todo.md; the owner's go-ahead, 2026-10-17.)

A DIA-NN protein group such as FCGR3A;FCGR3B is a protein the instrument
could not split between near-identical genes. service/pipeline/gene_ids.py
leaves such a row out when two or more of its genes are on the shared list
(59 of PBMC240's 3,098 rows). Two alternatives:
- first: give the row to the first of its genes on the list (DIA-NN lists
  the leading protein first);
- each: copy the row to every one of its genes on the list.

No labelled development file has such rows: Fulcher 2026 and both SCoPE2
versions are one row per gene, and PXD070599's PBMC runs DS18 and DS19 have
no cell types. So the test, fixed before it runs:
1. The served model (v4.2, a protein upload, as fusion.project answers) on
   every development DIA-NN file with such rows: PBMC240, DS18's three run
   sets and DS19. Per file and way: the rows affected, and the cells whose
   answer or best guess changes from leaving the rows out.
2. PBMC240's marker-based labels (weak; service/examples/
   pbmc240_cell_metadata.csv), mapped to families as scripts/
   trace_workflow.py does (WEAK_FAMILY): the share of labelled cells whose
   best guess falls in the family their markers name, for each way, and
   each way minus leaving out, with a cell-level bootstrap (2,000 draws,
   seed 0).
Decision: switch to a way only if its agreement minus leaving out has a 95%
interval wholly above 0. Otherwise the service keeps leaving the rows out:
there is then no evidence that the amount can be given to one gene.

Needs the DS18 and DS19 searches extracted as research/notebooks/
astral_abstention.py describes. Writes research/notebook-outputs/
twin_genes/summary.json.

    python research/notebooks/twin_genes.py      # from the repository root
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import warnings
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from service import config  # noqa: E402
from service.pipeline import alignment, fusion, gene_ids  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "twin_genes"
PUBLIC = REPO / "data" / "incoming" / "public_sets" / "PXD070599_PBMC" / "extracted"
FILES = {"PBMC240": REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv",
         "DS18 Standard Astral": PUBLIC / "DS18" / "Standard_Astral_MBR" / "report.pg_matrix.tsv",
         "DS18 FAIMS Astral": PUBLIC / "DS18" / "FAIMS_Astral_MBR" / "report.pg_matrix.tsv",
         "DS18 FAIMS Astral-Zoom": PUBLIC / "DS18" / "FAIMS_Astral-Zoom_MBR" / "report.pg_matrix.tsv",
         "DS19": PUBLIC / "DS19" / "MBR" / "report.pg_matrix.tsv"}
WEAK_LABELS = REPO / "service" / "examples" / "pbmc240_cell_metadata.csv"
WEAK_FAMILY = {"T cell": "T cell", "NK cell": "NK cell", "Monocyte": "monocyte/macrophage",
               "Dendritic": "dendritic cell", "Platelet": "platelet/megakaryocyte"}
WAYS = ("leave out", "first", "each")


def members(identifier: str, gene_map) -> list[str]:
    """The shared-list genes a group names, in the group's own order (the
    parts _resolve_one tries, each resolved the same way)."""
    out = []
    for part in (p.strip() for p in identifier.split(";") if p.strip()):
        upper, base = part.upper(), gene_ids._uniprot_base_accession(part)
        found = (gene_map.symbol_to_feature.get(upper) or gene_map.ensembl_to_feature.get(part)
                 or gene_map.uniprot_to_feature.get(part) or gene_map.uniprot_to_feature.get(base))
        for gene in ([found] if found else sorted(gene_map.shared_accessions.get(base, ()))):
            if gene not in out:
                out.append(gene)
    return out


def rewrite(raw: alignment.RawMatrix, way: str, gene_map) -> tuple[alignment.RawMatrix, int]:
    """The upload with its several-gene rows given to one gene or copied to each."""
    names, rows, affected = [], [], 0
    for r, name in enumerate(raw.gene_names):
        genes = members(name, gene_map) if ";" in name else []
        if way == "leave out" or len(genes) < 2:
            names.append(name)
            rows.append(r)
            continue
        affected += 1
        for gene in (genes[:1] if way == "first" else genes):
            names.append(gene)
            rows.append(r)
    return alignment.RawMatrix(gene_names=names, cell_ids=raw.cell_ids, values=raw.values[rows]), affected


def answers(bundle, raw) -> tuple[list[str], list[str]]:
    response = fusion.project(bundle, raw, False, None, modality="prot")
    outcome = [c["label_level"] + ":" + c["label"] if not c["abstained"] else c["abstain_reason"] for c in response["cells"]]
    guess = [(c.get("best_guess") or {}).get("label") or "" for c in response["cells"]]
    return outcome, guess


def main() -> None:
    warnings.simplefilter("ignore")
    bundle = fusion.V4Bundle.load(require_evaluation=True, version="v4.2")
    group = {n: bundle.answers.hierarchy[n]["group"] for n in bundle.class_names}
    gene_map = gene_ids.load_gene_id_map()
    with WEAK_LABELS.open(newline="", encoding="utf-8") as handle:
        weak = {row["cell"]: row["label"] for row in csv.DictReader(handle)}
    summary = {"model": "v4.2 as served (fusion.project, protein upload)",
               "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "spec_v42_sha256": hashlib.sha256(config.V42_SPEC_PATH.read_bytes()).hexdigest(), "files": {}}
    agree = {}
    for name, path in FILES.items():
        raw = alignment.parse_matrix_csv(path.read_text(encoding="utf-8"))
        base_outcome, base_guess = None, None
        entry = {"cells": len(raw.cell_ids), "rows": len(raw.gene_names)}
        for way in WAYS:
            upload, affected = rewrite(raw, way, gene_map)
            outcome, guess = answers(bundle, upload)
            if way == "leave out":
                base_outcome, base_guess = outcome, guess
                entry["several_gene_rows"] = rewrite(raw, "first", gene_map)[1]
            else:
                entry[way] = {"answers_changed": int(sum(a != b for a, b in zip(outcome, base_outcome))),
                              "best_guesses_changed": int(sum(a != b for a, b in zip(guess, base_guess)))}
            if name == "PBMC240":
                family = [WEAK_FAMILY.get(weak.get(c)) for c in raw.cell_ids]
                agree[way] = np.array([group.get(g) == f for g, f in zip(guess, family) if f is not None], float)
        summary["files"][name] = entry
        print(name, json.dumps(entry))
    rng = np.random.default_rng(0)
    n = len(agree["leave out"])
    draws = rng.integers(0, n, (2000, n))
    pbmc = {"labelled_cells": int(n), "agreement_pct": {w: round(100 * float(a.mean()), 2) for w, a in agree.items()}}
    decision = "leave out"
    for way in ("first", "each"):
        diff = 100 * (agree[way][draws].mean(1) - agree["leave out"][draws].mean(1))
        lo, hi = (round(float(x), 2) for x in np.percentile(diff, [2.5, 97.5]))
        pbmc[f"{way}_minus_leave_out"] = {"point": round(100 * float(agree[way].mean() - agree["leave out"].mean()), 2),
                                          "ci_95": [lo, hi]}
        if lo > 0 and decision == "leave out":
            decision = way
    summary["pbmc240_marker_agreement"] = pbmc
    summary["decision"] = decision
    summary["rule"] = ("switch to a way only if its agreement with PBMC240's marker labels minus leaving out has a 95% "
                       "interval wholly above 0; otherwise keep leaving the rows out")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", newline="\n")
    print(json.dumps(pbmc, indent=1), "\ndecision:", decision)


if __name__ == "__main__":
    main()
