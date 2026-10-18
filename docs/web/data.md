# Data

## `web/data/`

Latent embeddings and metadata, latent dim 128.

| File | Contents |
|---|---|
| `atlas_RNA_lat128.parquet` | RNA coordinates — **Git LFS**, ~1.43 GB |
| `atlas_RNA_lat128-001-part1.csv`, `-part2.csv` | Split CSV form of the same — **Git LFS** |
| `metadata_RNA_lat128.csv` | RNA metadata, 85,233 rows; PCs in v3.1's coordinate space (`scripts/export_atlas_coordinates.py`) |
| `atlas_PROT_lat128.parquet` / `.csv` | Protein coordinates, ~45 MB |
| `metadata_PROT_lat128.csv` | Protein metadata, 1,490 rows; the served v3.1 model's projection of SCoPE2 (`scripts/export_atlas_coordinates.py`) |
| `organs/tabula_sapiens.json` | Every organ of Tabula Sapiens v2, the atlas the references come from: name, file and size from its Figshare record (`scripts/tabula_sapiens_organs.py`); the manifest's `organs` marks each one |
| `organs/index.json` | The organ maps the Atlas page offers, without labelling: each organ's name, class order and hierarchy, cell count, bundle MANIFEST sha256 and gate record (`scripts/export_atlas_coordinates.py --organ`) |
| `organs/<organ>/metadata_RNA.csv` | One organ's map: `orig_index` (the row of its bundle's `reference_metadata.csv`), `class_idx` (in the index's class order) and `PC1`-`PC3`, from its coordinate member's reference latents through its bundle's own PCA |
| `atlas_manifest.json` | Generated — see [manifest.md](manifest.md) |
| `workflow.json` | Generated with the manifest, for the Workflow page: a trace of the PBMC240 example through the served model, an atlas sample, the gene space, the training recipe, the evaluation records; see [workflow.md](workflow.md) |

RNA metadata columns: `latent_dim, modality, orig_index, class_idx,
class_name, lineage, PC1, PC2, PC3`.

Protein metadata columns: `latent_dim, modality, orig_index, class_idx,
class_name, pred_class_name, max_cos_ref, abstained, PC1, PC2, PC3`.
`class_name` is the cell's **true** label: SCoPE2's curated cell type, from
the authors' SingleCellMultiModal object (`benchmark/scope2_labels.py`;
`service/tests/test_scope2_labels.py` pins every copy). The other columns go beyond the RNA
schema, and all come from the served v3.1 model with default settings:
- `pred_class_name` is its best guess;
- `max_cos_ref` is its out-of-distribution score (`reference_similarity`);
- `abstained` says whether it abstains.
Both the Atlas page (`web/js/atlas/reference-data.js`) and
`scripts/build_manifest.py` read columns by name and ignore the ones they
don't recognise.

**Coordinates.** The PCs are the service's own PCA of v3.1's coordinate
member (seed 4), with a fixed sign. A cell the service projects therefore
lands on the atlas the site displays; `service/tests/test_pipeline_versions.py`
pins the RNA file to it. The Atlas page maps PCs to scene units with one
frame computed from the reference (`atlasFrame`: the box round every RNA and
protein cell, 80 units across), and places uploaded cells through the same
frame.

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
`web/js/manifest.js` detects the magic string, and the Atlas page's gene
profile (`web/js/atlas/gene-profile.js`) checks before parsing a profile and
shows `git lfs pull` as the remedy. On the public site the large files are
left out (`scripts/build_pages_site.py`), and a click says the profiles are
not on that copy.

The magic string exists once, in `web/js/manifest.js`; `web/tests/lfs.test.js`
fails if a copy appears in any other page or module.

That suite also asserts the shipped part files are *still* unfetched pointers.
If you have run `git lfs pull` locally the test fails by design; do not
"fix" it by weakening the assertion.
