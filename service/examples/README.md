# Example / demo material

Not ground truth, not part of the reference contract — material for
demonstrating the projection service once it can serve real requests.

| File | What it is |
|---|---|
| `pbmc240_cell_metadata.csv` | Weak, marker-derived labels for three lineages (T cell, NK cell, monocyte, dendritic, platelet), from the PBMC240 dataset. |
| `pbmc240_provenance.json` | How those weak labels were derived. Real coverage against the 9,002-gene feature space is 26.5% (2,387/9,002 genes matched) — verified end to end against the live service; `docs/service/context-brief.md` and `download-checklist.md` cite the same figure. |
| `pbmc240_zscored_all_genes.csv` | The actual PBMC240 expression matrix — features (genes) in rows, cell IDs in the header row, matching the upload contract exactly. Uploadable to `/api/project` as-is; confirmed live: 237 cells, 26.5% coverage, labels restricted to macrophage/monocyte as expected, 22.8% abstain rate. |
| `pbmc240_proteins_raw.tsv` | The raw DIA-NN protein-group search output behind the zscored matrix. Audit trail only — not a per-cell matrix, not uploadable. |

`pbmc240_cell_metadata.csv`'s labels are weak and marker-derived, not ground
truth — treat any prediction against them as a sanity check, not an accuracy
measurement.
