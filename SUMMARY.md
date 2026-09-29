# VivOME Atlas — Project Summary

**VivOME** — *A Living Joint Latent Atlas for Single-Cell Omics.*

This repository is a static web app + data bundle for exploring a joint latent
embedding that integrates single-cell omics modalities into one shared 3D space.
It currently covers **RNA and Protein**.

Repo: `github.com/Amrita-Stanford-Development/Vivome_Atlas`

---

## The Idea

A joint latent space where cells from different omics modalities can be compared
directly. The current build integrates **RNA and Protein**.

Key concepts:

- **RNA-anchored integration** — scRNA-seq acts as the anchor; other modalities
  are projected into the same latent space.
- **Unpaired integration** — no cell-to-cell correspondence required across
  datasets, donors, or platforms (label-free alignment).
- **Living / versioned atlas** — new datasets can be embedded over time.
- **Training regimes** — supervised and semi-supervised runs (precomputed 3D
  plots included).

---

## What's in the Folder

### Web pages (static HTML, no build step)

| File | Purpose |
|------|---------|
| `index.html` | Landing page — animated intro with nav nodes for every section |
| `atlas.html` | Interactive **3D cell visualization** (RNA + Protein), with the cross-modal support map and alignment diagnostics panels |
| `visual.html` | Plot viewer for the precomputed 3D plots (**Supervised** + **Semi-Supervised** modes) |
| `project.html` | Submit an expression matrix for projection into the shared latent space |
| `benchmark.html` | Standing comparison against established integration methods |
| `versions.html` | Model card, data availability, and release protocol |
| `miscellaneous.html` | Intentionally **blank** (former Roadmap page, cleared) |

Nav/back links point to `index.html`.

### `web/data/` — latent embeddings + metadata (latent dim = 128)

Each modality has coordinates plus a metadata table with
`latent_dim, modality, orig_index, class_idx, class_name, PC1, PC2, PC3`
(PCA coords are precomputed for plotting).

| Modality | Cells | Files |
|----------|-------|-------|
| RNA | ~85,233 | `atlas_RNA_lat128.parquet` (Git LFS), split CSV parts (LFS), `metadata_RNA_lat128.csv` |
| Protein | 1,490 | `atlas_PROT_lat128.parquet` / `.csv` (~45 MB), `metadata_PROT_lat128.csv` |

- Large RNA files are tracked via **Git LFS** (see `.gitattributes`).

### `docs/` — documentation

| Document | Covers |
|----------|--------|
| `docs/web/manifest.md` | Manifest pipeline, the measured/pending contract, release protocol |
| `docs/web/data.md` | Data layout, Git LFS, what ships and what does not |
| `docs/service/projection-api.md` | The `POST /api/project` contract, conformal label sets, abstention |
| `research/` | Implementation plans |

`README.md` is the repository front door; `CLAUDE.md` records the conventions
any change has to respect.

### `service/` — Phase 5 projection service backend

A separate Python backend implementing `POST /api/project` (contract:
`docs/service/projection-api.md`) — real dependencies (torch, an OT solver),
isolated from the dependency-free static app. Every pipeline stage (query
alignment, fuzzy smoothing, the reference encoder, restricted-candidate
label assignment, conformal calibration, abstention, hierarchical fallback,
property transfer) is implemented, tested, and runs end to end against the
real v3 reference — `reference_model.pt`, `reference_embedding.npy`,
`reference_centroids.npy`, and per-cell property values are all real. It is
not deployed or reachable from the static site. See `service/README.md`
and `service/model/README.md` for what exists today and the remaining
known gaps, and the design rationale behind each stage's less-obvious
choices.

### `web/plots/` — 30 precomputed interactive 3D plots

- **`Supervised/`** — 5 plots, `interactive_latent{32,64,128,256,512}_to3d_PCA_mm.html`
  (one per latent dimension).
- **`Semi Supervised/`** — 25 plots, `PCA3D_semi_r{5,10,25,50,75}_p{5,10,25,50,75}.html`
  (sweep over two label-percentage hyperparameters, `r` (RNA) × `p` (protein)).

---

### The manifest

`web/data/atlas_manifest.json` is the single source of truth for every number the
web pages display. Regenerate it after any change to the metadata CSVs:

```bash
python3 scripts/build_manifest.py
```

Metrics that require the training pipeline — latent-space alignment, the
modality probe, transfer accuracy, benchmark rows — are stored as explicit
pending records and render as `Pending`. No page ever displays a number that
was not computed from data in this repository.

### Tests

No dependencies to install for the app itself. From the repository root:

```bash
node --test                                          # JS modules under web/js/
python3 -m unittest discover -s scripts             # manifest builder + repo path check
python3 -m unittest discover -s service/tests -t .   # projection service (needs service/requirements.txt)
```

---

## How to Use

It's a static site — serve the folder over HTTP (the atlas fetches from `web/data/`,
so `file://` won't load data):

```bash
python3 -m http.server 8000
# then open http://localhost:8000/index.html
```

Standalone plots live in `web/plots/`. The RNA data files require **Git LFS**
(`git lfs pull`) to download fully.
