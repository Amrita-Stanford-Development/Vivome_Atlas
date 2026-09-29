# app_export — real notebook artifacts

Four files from `VivOME_Prototype_Export.ipynb`'s v3 export bundle, added
here specifically because this exact set was lost once before: an earlier
version of this project had them staged (unpromoted) at
`service/model/v3_pending/app_export/`, that directory was deleted as part
of a cleanup, and — because it had never been committed to git — the
files were gone for good. `research/benchmark/known-limitations.md` documents
what that cost: weeks of a benchmark rebuild reconstructing "ours" from a
legacy, wrong-gene-panel protein file instead of using the real thing.

Committing them here (with `blood_joint_cells_by_proteins_GENELEVEL.tsv`
tracked via Git LFS — see `.gitattributes`) means this can't happen again.

## Files and provenance

| File | Bytes | sha256 (verified against `BUNDLE_MANIFEST.json`) |
|---|---|---|
| `prot_embedding_scope2.npy` | 763,008 | `c27c0830343babec6bd9ad0a3eaac19e42176c9efa2d4e791fa2b45094780167` |
| `atlas_PROT_v3_meta.csv` | 145,026 | `1c5234d279803b0fe91a7323c2f9f18693c968acc370b5c226bee0da34430cb1` |
| `blood_joint_cells_by_proteins_GENELEVEL.tsv` | 81,821,166 | not sha256-checked (not in `BUNDLE_MANIFEST.json`'s `app_export/` list — it's a Tier-4 raw input file the notebook reads, not an app-export output) |
| `BUNDLE_MANIFEST.json` | 4,340 | the manifest itself; only 3 of its 24 listed files (the ones above, plus this one) actually live here — the rest of the v3 bundle is already promoted to its own live paths elsewhere in `service/model/` |

## What each file is for

- **`prot_embedding_scope2.npy`** — the export notebook's own saved 128-d
  latent embedding for all 1,490 real SCoPE2 protein cells (`Z_prot` in
  the notebook), produced by its exact training-time pipeline. This is
  ground truth: any reconstruction attempt via `service/pipeline` should
  be checked against this directly (cosine similarity per cell), not
  assumed correct from code review alone. Row order matches
  `atlas_PROT_v3_meta.csv` exactly.
- **`atlas_PROT_v3_meta.csv`** — per-cell metadata for the same 1,490
  cells, same row order as the embedding above. Use the `true_class_name`
  column for ground-truth labels — **not** `web/data/atlas_PROT_lat128.csv`,
  a legacy, pre-v3 file with an unrelated, unverified row order (see
  `research/benchmark/known-limitations.md`).
- **`blood_joint_cells_by_proteins_GENELEVEL.tsv`** — the real raw SCoPE2
  protein-by-gene matrix (1,490 cells × 2,935 native genes) the notebook's
  `load_proteomics()` actually reads. This is the correct input for
  reproducing the notebook's pipeline end to end — not
  `web/data/atlas_PROT_lat128.csv`, which is restricted to a ~2,907-gene
  RNA-intersection subset and predates the v3 model entirely.
- **`BUNDLE_MANIFEST.json`** — the full v3 export bundle's file manifest
  (24 files, sha256 + byte count each). Kept for provenance and to verify
  any of these files again in the future; most of the 24 files it lists
  are promoted to their own live locations elsewhere in `service/model/`
  (`reference_model.pt`, `reference_embedding.npy`,
  `reference_centroids.npy`, `provenance.json`, `v3_tables/*`, etc.) —
  only the three files above still live specifically in this folder.

## Using these to validate `service/pipeline`

```python
from service.pipeline import alignment, smoothing, encoder, reference
import numpy as np, pandas as pd

df = pd.read_csv("service/model/source/app_export/blood_joint_cells_by_proteins_GENELEVEL.tsv",
                  sep="\t", index_col=0)
df.columns = df.columns.astype(str).str.upper()
raw = alignment.RawMatrix(gene_names=df.columns.tolist(),
                           cell_ids=df.index.astype(str).tolist(),
                           values=df.to_numpy(dtype="float32").T)
aligned = alignment.align_to_feature_space(raw, reference.load_feature_space_genes())

# full_query_values: notebook's own clean_numeric + zscore_cols, per gene, own cells
clean = df.apply(pd.to_numeric, errors="coerce").replace([float("inf"), float("-inf")], float("nan"))
clean = clean.apply(lambda c: c.fillna(c.median()), axis=0).fillna(0.0)
full_query_values = ((clean - clean.mean()) / (clean.std(ddof=0) + 1e-8)).to_numpy(dtype="float32")

smoothed = smoothing.fuzzy_smooth(aligned.values, full_query_values)
service_emb = encoder.load_encoder().encode(smoothed, aligned.mask)

notebook_emb = np.load("service/model/source/app_export/prot_embedding_scope2.npy")
# cosine(service_emb, notebook_emb) should be ~1.0 for every cell.
# If it drops, service/pipeline has regressed -- see
# research/benchmark/bugs-and-fixes.md for the two real bugs (smoothing.py's
# alpha convention, encoder.py's activation function) this check already
# caught once.
```
