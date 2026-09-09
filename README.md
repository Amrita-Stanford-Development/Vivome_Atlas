# VivOME Atlas

**A living joint latent atlas for single-cell omics.**

A static web resource for exploring a joint latent embedding that places
single-cell modalities into one shared space. This build covers **RNA** and
**Protein**.

No build step, no dependencies, no framework — plain HTML, CSS, and ES modules.

---

## Quick start

```bash
git clone git@github.com:Amrita-Stanford-Development/Vivome_Atlas.git
cd Vivome_Atlas
git lfs install && git lfs pull     # required for the RNA data (see below)
python3 -m http.server 8000
# open http://localhost:8000/index.html
```

The atlas fetches data from `Atlas/` over HTTP, so opening `index.html` from
`file://` will not load. Serve the folder.

**Git LFS is not optional for the RNA view.** `Atlas/atlas_RNA_lat128.parquet`
(~1.43 GB) and the two split CSV parts are LFS objects. Without `git lfs pull`
your checkout holds pointer files; the app detects this and tells you the
remedy rather than failing on a parse error.

## Pages

| Page | What it does |
|------|--------------|
| `index.html` | Landing page — animated intro, nav to every section |
| `atlas.html` | Interactive 3D cell viewer with cross-modal support map and alignment diagnostics |
| `visual.html` | Viewer for the 30 precomputed 3D plots (supervised + semi-supervised) |
| `project.html` | Submit an expression matrix for projection into the shared latent space |
| `benchmark.html` | Standing comparison against established integration methods |
| `versions.html` | Model card, data availability, release protocol |
| `miscellaneous.html` | Intentionally blank (former roadmap page) |

## Layout

```
Atlas/      latent embeddings, metadata CSVs, atlas_manifest.json
Plots/      30 precomputed interactive 3D plots
css/        page.css — shared page styling
js/         manifest.js, panels.js — pure ES modules, unit-tested
tools/      build_manifest.py and its unittest suite
tests/      node --test suites for the JS modules
docs/       documentation (see docs/README.md)
```

## The manifest rule

`Atlas/atlas_manifest.json` is the single source of truth for every number the
pages display. Metrics that need the training pipeline are stored as explicit
*pending* records and render as `Pending`.

**No page ever displays a number that was not computed from data in this
repository.** This is enforced in code, not by convention — see
[docs/manifest.md](docs/manifest.md).

Regenerate after any change to the metadata CSVs:

```bash
python3 tools/build_manifest.py
```

## Tests

Nothing to install.

```bash
node --test                                  # JS modules under js/
cd tools && python3 -m unittest discover     # manifest builder
```

## Current state

Atlas version `0.1.0`, manifest schema `1.0`. Model `CrossModalNet`, latent
dim 128, supervised regime, single run. 22 cell types: 2 cross-modal, 20
RNA-only. RNA 85,233 cells; Protein 1,490 cells (SCoPE2 mass spectrometry).

Alignment metrics, the modality probe, transfer accuracy, multi-seed
statistics, and every benchmark row are **pending** — they require the
training pipeline and are marked as such throughout.

## Documentation

- [docs/README.md](docs/README.md) — documentation index
- [SUMMARY.md](SUMMARY.md) — detailed repository inventory
- [VivOME_NatComms_Implementation_Plan.md](VivOME_NatComms_Implementation_Plan.md) — the paper plan this work serves
