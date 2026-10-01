# Reference artifacts

Grouped by role, so what a deployment needs is one folder:

```
runtime/     everything the v3 pipeline loads, and the reference files v3.1 shares with it
v3_1/        v3.1, the default pipeline: T1 NB2's spec and its five ensemble members
evidence/    measured tables behind the model's claims (read by scripts/build_manifest.py and the docs)
source/      how runtime/ was produced: the export notebook, its inputs and checksums
legacy/      v2/ — the previous model's audit trail; dev/ — the development placeholder checkpoint
```

`MODEL_CARD.md` (what the model claims, and doesn't) and
`canonical_preprocessing.json` (the preprocessing contract an upload must
match) sit here, beside the folders.

The production contract (fixed, from the implementation task this service
was built against), all in `runtime/`:

```
reference_model.pt        state dict, keys prefixed "encoder." and "classifier."
reference_embedding.npy   float32, shape (n_rna_cells, 128), L2 normalised
reference_centroids.npy   float32, shape (22, 128), L2 normalised
reference_metadata.csv    class_idx here is authoritative — centroids and
                           any classifier head must match its ordering
feature_space_genes.csv   row order here is authoritative — every input
                           array to the encoder must match it
provenance.json           config, seed, gene list hash, headline numbers
```

Mask convention, both training and inference: **1.0 = observed, 0.0 =
missing.**

## runtime/

| File | Status |
|---|---|
| `feature_space_genes.csv` | **Real, authoritative.** The fixed 9,002-gene input space. Replaces the old 2,903-gene list entirely. |
| `gene_id_map_v1.tsv` + `gene_id_map_v1_provenance.json` | **Real, frozen.** Symbol / Ensembl / UniProt cross-reference for the 9,002 genes, built once from HGNC's bulk download; source URL, date and sha256 in the provenance file. |
| `reference_metadata.csv` | **Real, authoritative.** Cell id, class index, class name, lineage for all 85,233 RNA cells. Labels don't depend on encoder architecture — this stayed valid across the architecture change. |
| `decisive_summary.json` | **Real.** The architecture decision: module pooling encoder, uniform mask sampler, consistency loss on, over the 9,002-gene space — the config the production reference below was trained with. `pipeline/encoder.py` reads it rather than hardcoding a family. |
| `reference_model.pt` | **Real, production** (Git LFS). The trained v3 checkpoint — 20,058,134 params, `strict=True` load verified. `config.ENCODER_WEIGHTS_PATH` defaults to this now. |
| `reference_embedding.npy` | **Real.** (85233, 128) float32, L2 normalised — every reference cell in latent space. |
| `reference_centroids.npy` | **Real.** (22, 128) float32, L2 normalised, ordered by class_idx. |
| `provenance.json` | **Real.** Serving constants and headline measurements (gene list hash, module count, the calibrated abstain threshold, seed statistics) — see `pipeline/reference.py:load_provenance`. Recorded in every response for comparison; not yet the abstain decision itself (see `pipeline/abstention.py`'s module docstring). |
| `reference_properties.npy` + `property_names.json` | **Real.** (85233, 8) float32 per-cell continuous property scores, with `property_names.json` giving column names and order (a `.npy`, not the `.csv` the contract table above names — see `pipeline/reference.py:load_reference_properties`). |

## v3_1/

v3.1 is T1 NB2's ensemble (`service/pipeline/ensemble.py`). It reads the
reference metadata, feature space and properties from `runtime/`. Its own
files are below, each listed with its sha256, size and origin in
`MANIFEST.json`, which the service checks on load.

| File | Status |
|---|---|
| `nb2_spec_v31.json` | **Real.** NB2's export, as delivered: members, per-member temperature, per-class qhat, out-of-distribution threshold, output rule, hierarchy, caveats. Also kept at `research/notebook-outputs/nb2/`. |
| `MANIFEST.json` | **Real.** sha256, size and origin of every file here. |
| `members/V2_batchgene_aug_seed{0..4}.pt` | **Real, outside git.** T1 NB1b's V2 checkpoints (~98 MB each). Their home is the project Drive, `Data/Results/Tier1_v31/NB1b/ckpt/`. Download that folder to `data/incoming/NB1b/ckpt/` and run `python3 scripts/fetch_v31_members.py`, which copies each file only if its sha256 matches. Until then v3.1 answers 503 and names the missing file. |
| `members/V2_seed{0..4}_reference_latent_f16.npy` | **Real.** T1 NB1d: every reference cell through that member, float16, `reference_metadata.csv` row order. The out-of-distribution score's reference, and for seed 4, the coordinate space. |
| `members/V2_seed{0..4}_centroids.npy` | **Real.** T1 NB1d: the class means of those latents, L2 normalised, in class position order. |

Coordinates and property transfer use member seed 4
(`config.V31_COORDINATE_MEMBER`). The site's atlas coordinates are written
from it (`scripts/export_atlas_coordinates.py`).

## evidence/

| File | Status |
|---|---|
| `feature_space_detail.csv` | **Real.** Per gene, which of the six proteomics sources detected it. |
| `feature_space_provenance.json` | **Real.** The union math behind the 9,002 figure. |
| `masking_test_tables/rna_sweep.csv`, `masking_test_tables/scope2_projection.csv` | **Real.** The paired comparison numbers behind the architecture decision. |
| `v3_tables/` | **Real.** The measured tables behind `model.seeds`, `latent_centroid_cosine`, the restricted-assignment decision, property validation, and hierarchical fallback behaviour — see `docs/service/context-brief.md`. |

## source/

| File | Status |
|---|---|
| `VivOME_Prototype_Export.ipynb` | **Real.** The notebook that produced the v3 export — kept as the training/export provenance for everything in `runtime/`. |
| `v3_export_manifest.json` | **Real.** The v3 bundle's own sha256 checksum manifest, verified (24/24 match) before any of it was promoted here. |
| `pca3_projection.npz` | **Real.** The export's 3-component PCA basis over the 128-d latent space (components, mean, explained-variance ratio). |
| `app_export/` | **Real.** The export notebook's saved SCoPE2 protein input and outputs, used by the end-to-end and golden-fixture tests — see `app_export/README.md`. |

## legacy/

| File | Status |
|---|---|
| `dev/H_seed4.pt` | **Real, development placeholder** (Git LFS) — see `dev/README.md`. No longer the default; still used explicitly by `service/tests/test_encoder.py`'s dev-path guard test. |
| `v2/` | **Real, historical.** The old CrossModalNet run's audit trail and provenance — see `v2/README.md`. |

## Known gaps

- **`assignment.py`'s method comparison (nearest-centroid vs. OT vs. kNN)
  was measured *unrestricted*.** `config.ASSIGNMENT_METHOD` defaults to
  nearest-centroid on that evidence, but re-running the comparison *inside*
  `config.CROSS_MODAL_SUPPORTED_CLASSES`'s restricted candidate set has not
  been done — see `assignment.py`'s module docstring.
- **The abstain threshold is still computed live, per request**, not from
  `provenance.json`'s calibrated `abstain_threshold` — see
  `abstention.py`'s module docstring for why switching is a real behaviour
  change, not a data swap, and what would need verifying first.
