"""Candidate v5.4's extra rows (route B of run history entry 65): cells of the
Allen Human Immune Health Atlas (Gong 2025; CELLxGENE dataset
e522d2cd-7927-4e59-a4ed-064009569279; side-tests amendment 21) in the
reference's form, for training (research/notebooks/v5_train.py --variant
v5.4) and for an RNA check on donors held out of training
(research/notebooks/v54_gates.py).

Fixed before any row is drawn:
- **Donors:** the 108 donors in sorted order, shuffled with seed 0; the
  first 22 (about 20%) are held out, the other 86 give the training rows.
- **Classes:** each cell's Cell Ontology label (CELLxGENE's cell_type) to a
  reference class by MAP; a label mapped to None is left out. Naive CD8 T
  cells are left out because Tabula Sapiens's original labels, which v5.4
  trains on, file naive CD8 T cells under CD4: the two atlases would
  contradict each other there. Labels without a reference class (AXL+ DC,
  ILC, MAIT, gamma-delta T, generic T, thymocyte-like, CLP, basophil-mast
  progenitor) are left out.
- **How many:** from the training donors, up to 3,000 cells for each class
  the step is about (myeloid DC, pDC, CMP) and up to 1,500 for every other
  class; from the held-out donors, up to 500 per class. Drawn with seed 0.
- **Values:** the raw counts to log1p(counts / total x 10,000), the total over
  every gene, as Tabula Sapiens's X (checked: each cell's expm1 sums to
  10,000) and Hao's; then the reference's feature genes by symbol, a gene
  missing from the atlas left at 0.

Writes the rows (float16) and their labels, donors and Cell Ontology labels
to ROWS on the project Drive (outside git, beside the checkpoints), and a
record with the counts, the donors and the file's sha256 into its own folder
of research/notebook-outputs (OUT).

    python research/notebooks/allen_rows.py      # from the repository root
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from service import config  # noqa: E402
from service.pipeline import reference  # noqa: E402

SOURCE = REPO / "data" / "incoming" / "public_sets" / "Gong2025_HIHA" / "c1ce03ce-4b71-4b8d-b695-c3cec99cdfc2.h5ad"
ROWS = REPO.parent / "drive" / "Data" / "Results" / "Tier1_v31" / "V5" / "allen_rows_v54.npz"
OUT = REPO / "research" / "notebook-outputs" / "v54_allen_rows"
SEED, HELD_OUT_DONORS = 0, 22
CAP_TARGET, CAP_OTHER, CAP_HELD = 3000, 1500, 500
MDC, PDC, CMP = "myeloid dendritic cell", "plasmacytoid dendritic cell", "common myeloid progenitor"
CD4, CD8 = "cd4-positive, alpha-beta t cell", "cd8-positive, alpha-beta t cell"
MAP = {
    "CD14-positive, CD16-negative classical monocyte": "classical monocyte",
    "intermediate monocyte": "intermediate monocyte",
    "CD14-low, CD16-positive monocyte": "non-classical monocyte",
    "CD1c-positive myeloid dendritic cell": MDC,
    "CD141-positive myeloid dendritic cell": MDC,
    "plasmacytoid dendritic cell": PDC,
    "natural killer cell": "natural killer cell",
    "CD16-positive, CD56-dim natural killer cell, human": "natural killer cell",
    "CD16-negative, CD56-bright natural killer cell, human": "natural killer cell",
    "naive B cell": "b cell", "memory B cell": "b cell", "transitional stage B cell": "b cell", "Be cell": "b cell",
    "plasma cell": "plasma cell",
    "naive thymus-derived CD4-positive, alpha-beta T cell": "naive thymus-derived cd4-positive, alpha-beta t cell",
    "CD4-positive, alpha-beta memory T cell": CD4,
    "central memory CD4-positive, alpha-beta T cell": CD4,
    "effector memory CD4-positive, alpha-beta T cell": CD4,
    "naive regulatory T cell": "regulatory t cell", "memory regulatory T cell": "regulatory t cell",
    "memory CCR4-positive regulatory T cell": "regulatory t cell",
    "CD8-positive, alpha-beta memory T cell": CD8,
    "central memory CD8-positive, alpha-beta T cell": CD8,
    "effector memory CD8-positive, alpha-beta T cell": CD8,
    "common myeloid progenitor": CMP,
    "platelet": "platelet", "erythrocyte": "erythrocyte",
    # left out: see the docstring
    "naive thymus-derived CD8-positive, alpha-beta T cell": None, "Axl+ dendritic cell, human": None,
    "innate lymphoid cell": None, "mucosal-associated invariant T cell": None, "mature gamma-delta T cell": None,
    "T cell": None, "CD8-positive, alpha-beta regulatory T cell": None, "CD8aa(I) thymocyte": None,
    "double negative thymocyte": None, "common lymphoid progenitor": None, "basophil mast progenitor cell": None,
}


def draw(classes: np.ndarray, donors: np.ndarray, keep: np.ndarray, cap, rng) -> np.ndarray:
    """Row indices: up to cap(class) cells per class among the kept cells."""
    picked = []
    for c in sorted(set(classes[keep])):
        at = np.flatnonzero(keep & (classes == c))
        n = min(cap(c), len(at))
        picked.append(rng.choice(at, size=n, replace=False))
    return np.sort(np.concatenate(picked))


def rows_of(a, idx: np.ndarray, cols: np.ndarray, n_features: int, block: int = 2000) -> np.ndarray:
    out = np.zeros((len(idx), n_features), np.float16)
    for i in range(0, len(idx), block):
        part = idx[i:i + block]
        counts = sp.csr_matrix(a.raw.X[part]).astype(np.float64)
        total = np.asarray(counts.sum(1)).ravel()
        X = (sp.diags(1e4 / total) @ counts).tocsr()
        X.data = np.log1p(X.data)
        sums = np.asarray(X.expm1().sum(1)).ravel()
        if np.abs(sums - 1e4).max() > 1e-3 * 1e4:
            raise SystemExit("the normalisation is not counts per 10,000")
        out[i:i + len(part)][:, cols >= 0] = X[:, cols[cols >= 0]].toarray().astype(np.float16)
    return out


def main() -> None:
    t0 = time.time()
    a = ad.read_h5ad(SOURCE, backed="r")
    labels = a.obs["cell_type"].astype(str).to_numpy()
    unknown = sorted(set(labels) - set(MAP))
    if unknown:
        raise SystemExit(f"labels without a decision in MAP: {unknown}")
    meta = pd.read_csv(config.MODEL_DIR / "runtime" / "reference_metadata.csv")
    names = meta.drop_duplicates("class_idx").sort_values("class_idx")["class_name"].tolist()
    classes = np.array([MAP[x] or "" for x in labels], dtype=object)
    donors = a.obs["donor_id"].astype(str).to_numpy()
    order = sorted(set(donors))
    rng = np.random.default_rng(SEED)
    held = set(np.array(order)[rng.permutation(len(order))[:HELD_OUT_DONORS]])
    mapped = classes != ""
    train_keep, held_keep = mapped & ~np.isin(donors, list(held)), mapped & np.isin(donors, list(held))
    cap_train = lambda c: CAP_TARGET if c in (MDC, PDC, CMP) else CAP_OTHER  # noqa: E731
    i_train = draw(classes, donors, train_keep, cap_train, rng)
    i_held = draw(classes, donors, held_keep, lambda c: CAP_HELD, rng)

    genes = reference.load_feature_space_genes()
    symbols = a.var["gene_symbols"].astype(str).str.upper().to_numpy()
    first: dict = {}
    for j, s in enumerate(symbols):
        first.setdefault(s, j)
    cols = np.array([first.get(g.upper(), -1) for g in genes])
    print(f"{len(i_train):,} training and {len(i_held):,} held-out rows; {int((cols >= 0).sum()):,} of "
          f"{len(genes):,} feature genes in the atlas ({time.time() - t0:.0f}s)", flush=True)
    X_train = rows_of(a, i_train, cols, len(genes))
    X_hold = rows_of(a, i_held, cols, len(genes))
    idx = {n: k for k, n in enumerate(names)}
    ROWS.parent.mkdir(parents=True, exist_ok=True)
    np.savez(ROWS, X_train=X_train, y_train=np.array([idx[c] for c in classes[i_train]], np.int64),
             donor_train=donors[i_train], label_train=labels[i_train],
             X_hold=X_hold, y_hold=np.array([idx[c] for c in classes[i_held]], np.int64),
             donor_hold=donors[i_held], label_hold=labels[i_held])
    count = lambda ii: {c: int((classes[ii] == c).sum()) for c in sorted(set(classes[ii]))}  # noqa: E731
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "record.json").write_text(json.dumps({
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "run": datetime.now().isoformat(timespec="seconds"), "source": SOURCE.name,
        "rows_file": ROWS.name, "rows_sha256": hashlib.sha256(ROWS.read_bytes()).hexdigest(),
        "feature_genes_found": int((cols >= 0).sum()), "feature_genes": len(genes),
        "donors": {"training": len(order) - HELD_OUT_DONORS, "held_out": sorted(held)},
        "training_rows": count(i_train), "held_out_rows": count(i_held),
        "seconds": round(time.time() - t0)}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {ROWS} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
