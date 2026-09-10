# Example / demo material

Not ground truth, not part of the reference contract — material for
demonstrating the projection service once it can serve real requests.

| File | What it is |
|---|---|
| `pbmc240_cell_metadata.csv` | Weak, marker-derived labels for three lineages (T cell, NK cell, monocyte, dendritic, platelet), from the PBMC240 dataset. |
| `pbmc240_provenance.json` | How those weak labels were derived, and PBMC240's real coverage against the feature space: 34.8%. |

**The actual PBMC240 expression matrix is not included in this repo** — only
its derived weak labels and provenance. These files document expected
coverage and demonstrate the weak-labelling approach; they cannot be
uploaded to `/api/project` as-is, since the service needs an expression
matrix, not a labels table.
