"""Full-scale, label-free-until-scoring data loader for the fair baseline
comparison. Loads the FULL 85,233-cell RNA reference and the full 1,490-cell
SCoPE2 protein query, restricted to their shared ~2,907 gene columns (the
only genes both modalities actually measured — every integration method
below works on this raw shared feature space, not the frozen v3 encoder's
9,002-gene training space, which none of these baselines ever see).

RNA class labels are kept (every arm is allowed to see them — that's the
supervision signal for label transfer). Protein class labels are loaded but
NEVER touched by any arm until the final scoring step.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).resolve().parents[1]  # repo root
OUT = Path(__file__).resolve().parent / "results"


def main():
    os.makedirs(OUT, exist_ok=True)
    rna1 = pd.read_csv(f"{D}/web/data/atlas_RNA_lat128-001-part1.csv")
    rna2 = pd.read_csv(f"{D}/web/data/atlas_RNA_lat128-001-part2.csv")
    rna = pd.concat([rna1, rna2], ignore_index=True)
    prot = pd.read_csv(f"{D}/web/data/atlas_PROT_lat128.csv")

    rna_gene_cols = [c for c in rna.columns if c.startswith("gene_")]
    prot_gene_cols = [c for c in prot.columns if c.startswith("gene_")]
    shared = sorted(set(rna_gene_cols) & set(prot_gene_cols))
    assert set(rna_gene_cols) == set(prot_gene_cols), "gene columns are supposed to be identical"
    print(f"RNA cells: {len(rna)}, PROT cells: {len(prot)}, shared genes: {len(shared)}")

    rna_X = rna[shared].to_numpy(dtype=np.float32)
    prot_X = prot[shared].to_numpy(dtype=np.float32)

    np.save(f"{OUT}/rna_X.npy", rna_X)
    np.save(f"{OUT}/prot_X.npy", prot_X)
    rna[["orig_index", "class_idx", "class_name"]].to_csv(f"{OUT}/rna_meta.csv", index=False)
    prot[["orig_index", "class_idx", "class_name"]].to_csv(f"{OUT}/prot_meta.csv", index=False)
    with open(f"{OUT}/gene_cols.txt", "w") as f:
        f.write("\n".join(shared))

    print(f"rna_X {rna_X.shape}, prot_X {prot_X.shape}")
    print("RNA class distribution:")
    print(rna["class_name"].value_counts())


if __name__ == "__main__":
    main()
