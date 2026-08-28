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
| `index.html` | Landing page — animated intro with two nav nodes: **Visuals** and **Live Atlas** |
| `atlas.html` | Interactive **3D cell visualization** of the latent atlas (RNA + Protein); loads the `Atlas/` CSV data |
| `visual.html` | Plot viewer for the precomputed 3D plots (**Supervised** + **Semi-Supervised** modes) |
| `miscellaneous.html` | Intentionally **blank** (former Roadmap page, cleared) |

Nav/back links point to `index.html`.

### `Atlas/` — latent embeddings + metadata (latent dim = 128)

Each modality has coordinates plus a metadata table with
`latent_dim, modality, orig_index, class_idx, class_name, PC1, PC2, PC3`
(PCA coords are precomputed for plotting).

| Modality | Cells | Files |
|----------|-------|-------|
| RNA | ~85,233 | `atlas_RNA_lat128.parquet` (Git LFS), split CSV parts (LFS), `metadata_RNA_lat128.csv` |
| Protein | 1,490 | `atlas_PROT_lat128.parquet` / `.csv` (~45 MB), `metadata_PROT_lat128.csv` |

- `shared_genes_lat128.txt` — shared gene list used for alignment.
- Large RNA files are tracked via **Git LFS** (see `.gitattributes`).

### `Plots/` — 30 precomputed interactive 3D plots

- **`Supervised/`** — 5 plots, `interactive_latent{32,64,128,256,512}_to3d_PCA_mm.html`
  (one per latent dimension).
- **`Semi Supervised/`** — 25 plots, `PCA3D_semi_r{5,10,25,50,75}_p{5,10,25,50,75}.html`
  (sweep over two label-percentage hyperparameters, `r` (RNA) × `p` (protein)).

---

## How to Use

It's a static site — serve the folder over HTTP (the atlas fetches from `Atlas/`,
so `file://` won't load data):

```bash
python3 -m http.server 8000
# then open http://localhost:8000/index.html
```

Standalone plots live in `Plots/`. The RNA data files require **Git LFS**
(`git lfs pull`) to download fully.
