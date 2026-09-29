# VivOME Atlas

**A living joint latent atlas for single-cell omics.**

A static web resource for exploring a joint latent embedding that places
single-cell modalities into one shared space. This build covers **RNA** and
**Protein**.

No build step, no dependencies, no framework — plain HTML, CSS, and ES modules.
The one exception is `service/`, a separate Python backend for the
projection service — see [Layout](#layout) and `service/README.md`.

---

## Quick start

```bash
git clone git@github.com:Amrita-Stanford-Development/Vivome_Atlas.git
cd Vivome_Atlas
git lfs install && git lfs pull     # required for the RNA data (see below)
cd web && python3 -m http.server 8000
# open http://localhost:8000/index.html
```

The atlas fetches data from `web/data/` over HTTP, so opening `index.html` from
`file://` will not load. Serve the `web/` folder.

**Git LFS is not optional for the RNA view.** `web/data/atlas_RNA_lat128.parquet`
(~1.43 GB) and the two split CSV parts are LFS objects. Without `git lfs pull`
your checkout holds pointer files; the app detects this and tells you the
remedy rather than failing on a parse error. `service/model/legacy/dev/H_seed4.pt`
(~94 MB, the projection service's dev placeholder checkpoint) is LFS-tracked
too — the same `git lfs pull` fetches it.

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
web/data/      latent embeddings, metadata CSVs, atlas_manifest.json
web/plots/      30 precomputed interactive 3D plots
web/css/        page.css — shared page styling
web/js/         manifest.js, panels.js — pure ES modules, unit-tested
scripts/    build_manifest.py, check_paths.py and their unittest suites
benchmark/  fair comparison harness vs scANVI, MaxFuse, scGLUE, Harmony
web/tests/      node --test suites for the JS modules
docs/       documentation (see docs/README.md)
service/    Phase 5 projection service backend — separate dependencies,
            separate tests, see service/README.md
```

## The manifest rule

`web/data/atlas_manifest.json` is the single source of truth for every number the
pages display. Metrics that need the training pipeline are stored as explicit
*pending* records and render as `Pending`.

**No page ever displays a number that was not computed from data in this
repository.** This is enforced in code, not by convention — see
[docs/manifest.md](docs/manifest.md).

Regenerate after any change to the metadata CSVs:

```bash
python3 scripts/build_manifest.py
```

## Tests

Nothing to install.

```bash
node --test                                          # JS modules under web/js/
python3 -m unittest discover -s scripts             # manifest builder + repo path check
python3 -m unittest discover -s service/tests -t .   # projection service (needs service/requirements.txt)
```

## Current state

Atlas version `0.2.0`, manifest schema `1.0`. Model `VivOME v3 reference` —
a frozen, RNA-only encoder over a 9,002-gene feature space, module pooling
architecture, 5 production seeds — latent dim 128. 22 cell types: 2
cross-modal (macrophage, monocyte), 20 RNA-only. RNA 85,233 cells; Protein
1,490 cells (SCoPE2 mass spectrometry).

Latent centroid cosine and the modality probe are measured for the 2
cross-modal classes. Per-class transfer accuracy and every benchmark row
are **pending** — the former has no per-class source data yet (a
per-*dataset* version exists, see `service/docs/context-brief.md`), the
latter requires running established integration methods for comparison.

The prior architecture, `CrossModalNet` (jointly trained on RNA and
proteomics, 2,903-gene space), is kept as a documented baseline, not
erased — see `versions.html`'s "Prior baseline" card and
`service/model/legacy/v2/README.md`. The projection service pipeline (see
`service/README.md`) runs end to end against the v3 reference but is not
deployed or reachable from this site yet.

## Documentation

- [docs/README.md](docs/README.md) — documentation index
- [SUMMARY.md](SUMMARY.md) — detailed repository inventory
- [VivOME_NatComms_Implementation_Plan.md](VivOME_NatComms_Implementation_Plan.md) — the paper plan this work serves
