# Data

## `web/data/`

Latent embeddings and metadata, latent dim 128.

| File | Contents |
|---|---|
| `atlas_RNA_lat128.parquet` | RNA coordinates — **Git LFS**, ~1.43 GB |
| `atlas_RNA_lat128-001-part1.csv`, `-part2.csv` | Split CSV form of the same — **Git LFS** |
| `metadata_RNA_lat128.csv` | RNA metadata, 85,233 rows — from the v3 reference (`scripts/archive/promote_v3_atlas.py`) |
| `atlas_PROT_lat128.parquet` / `.csv` | Protein coordinates, ~45 MB |
| `metadata_PROT_lat128.csv` | Protein metadata, 1,490 rows — from the v3 reference (`scripts/archive/promote_v3_atlas.py`) |
| `atlas_manifest.json` | Generated — see [manifest.md](manifest.md) |

RNA metadata columns: `latent_dim, modality, orig_index, class_idx,
class_name, lineage, PC1, PC2, PC3`.

Protein metadata columns: `latent_dim, modality, orig_index, class_idx,
class_name, pred_class_name, max_cos_ref, abstained, PC1, PC2, PC3`.
`class_name` is the cell's **true** label (SCoPE2 ground truth, matching
what this column has always meant); `pred_class_name`, `max_cos_ref`, and
`abstained` are extra columns beyond the RNA schema — the v3 reference's own
prediction, its similarity to the reference, and whether it would abstain.
Both `atlas.html` and `scripts/build_manifest.py` read columns by name and
ignore the ones they don't recognise.

Class names are quoted CSV fields and **some contain commas** (`class_idx` 2,
3, and 14). Parse with `csv.DictReader` or equivalent — a naive `split(',')`
corrupts those rows.

## What ships and what does not

| Artifact | Status |
|---|---|
| 3-component PCA projection of the latent space | Ships — this is what the viewer plots |
| Full 128-d latent coordinates | **Not distributed** with this build |
| Protein expression matrix | Available (`atlas_PROT_lat128.csv`) |
| RNA expression matrix | Git LFS object, absent until fetched |

The viewer's 3D coordinates are a PCA projection, not the latent space itself.
`latent_centroid_cosine` (the full 128-d measurement) is now measured for the
2 cross-modal classes, from `service/model/runtime/reference_embedding.npy` — see
[manifest.md](manifest.md). It stays pending for the other 20, which have no
cross-modal coverage to measure it from.

## Git LFS

```bash
git lfs install
git lfs pull
```

Six files are LFS-tracked (see `.gitattributes`): the three RNA files above,
and three model files under `service/model/` (`runtime/reference_model.pt`,
`legacy/dev/H_seed4.pt`, `source/app_export/blood_joint_cells_by_proteins_GENELEVEL.tsv`).
A fresh clone without `git lfs pull` holds pointer files that begin:

```
version https://git-lfs.github.com/spec/v1
```

The app handles this rather than crashing. `isLfsPointer()` in
`web/js/manifest.js` detects the magic string, and `atlas.html` checks before
parsing an RNA profile and shows `git lfs pull` as the remedy.

`atlas.html`'s main script is a classic script and cannot import the module,
so the magic string exists in two places. `web/tests/lfs.test.js` pins them
byte-for-byte — a typo in either copy would silently disable the guard on one
side while the suite stayed green.

That suite also asserts the shipped part files are *still* unfetched pointers.
If you have run `git lfs pull` locally the test fails by design; do not
"fix" it by weakening the assertion.

## `web/plots/`

30 precomputed interactive 3D plots, standalone HTML, from the original 2025
model (before the v3 reference). No page shows them since `visual.html` was
removed; plots from the current runs will replace them.

- `supervised/` — 5 plots, `interactive_latent{32,64,128,256,512}_to3d_PCA_mm.html`, one per latent dimension.
- `semi-supervised/` — 25 plots, `PCA3D_semi_r{5,10,25,50,75}_p{5,10,25,50,75}.html`, a sweep over RNA (`r`) and protein (`p`) label percentages.
