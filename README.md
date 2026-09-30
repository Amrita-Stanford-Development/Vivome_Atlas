# VivOME Atlas

**A living joint latent atlas for single-cell omics.**

A static web resource for exploring a joint latent embedding that places
single-cell modalities into one shared space. This build covers **RNA** and
**Protein**.

The website (`web/`) has no build step, no dependencies and no framework:
plain HTML, CSS and ES modules. The projection service (`service/`) is a
separate Python backend with its own dependencies. See
[Repository map](#repository-map).

---

## Quick start

```bash
git clone git@github.com:Amrita-Stanford-Development/Vivome_Atlas.git
cd Vivome_Atlas
git lfs install && git lfs pull     # required for the RNA view and the model (see below)
cd web && python3 -m http.server 8000
# open http://localhost:8000/index.html
```

The atlas fetches data from `web/data/` over HTTP, so opening `index.html` from
`file://` will not load. Serve the `web/` folder.

To run the projection service locally, see `service/README.md`:

```bash
pip install -r service/requirements.txt
python3 -m service.app              # from the repository root
```

**Git LFS is not optional.** Six files are LFS objects. Without
`git lfs pull` your checkout holds small pointer files in their place. The
site detects this and shows the fix instead of failing on a parse error.

| File | Size | Used by |
|---|---|---|
| `web/data/atlas_RNA_lat128.parquet` | ~1.43 GB | RNA view in `atlas.html` |
| `web/data/atlas_RNA_lat128-001-part1.csv`, `-part2.csv` | split CSV of the same | RNA view in `atlas.html` |
| `service/model/runtime/reference_model.pt` | ~94 MB | the production encoder |
| `service/model/legacy/dev/H_seed4.pt` | ~94 MB | development placeholder checkpoint (one guard test) |
| `service/model/source/app_export/blood_joint_cells_by_proteins_GENELEVEL.tsv` | ~82 MB | real SCoPE2 input for the end-to-end regression tests |

## Repository map

```
web/          the public website: static pages, data, plots, JS tests
service/      the projection API (Python): pipeline, model files, tests
benchmark/    fair comparison vs scANVI, MaxFuse, scGLUE, Harmony
scripts/      manifest builder and repository checks
docs/         how the products work: manifest, data, API contract
research/     the R&D record: roadmap, TODO, notebook outputs, benchmark write-up
data/         external datasets; incoming/ is a local, gitignored staging folder
```

[docs/project-structure.md](docs/project-structure.md) explains each folder
and where new files go. [docs/file-index.md](docs/file-index.md) gives one
line for every file.

## Pages

| Page | What it does |
|------|--------------|
| `index.html` | Landing page — animated intro, nav to every section |
| `home.html` | Dashboard: a way in to every tool, the current release, what's new |
| `atlas.html` | Interactive 3D cell viewer with cross-modal support map and alignment diagnostics |
| `project.html` | The projection contract and the label space the service supports |
| `benchmark.html` | Standing comparison against established integration methods |
| `versions.html` | Model card, data availability, release protocol |
| `miscellaneous.html` | Intentionally blank (former roadmap page) |

## The manifest rule

`web/data/atlas_manifest.json` is the single source of truth for every number the
pages display. Metrics that need the training pipeline are stored as explicit
*pending* records and render as `Pending`.

**No page ever displays a number that was not computed from data in this
repository.** This is enforced in code, not by convention — see
[docs/web/manifest.md](docs/web/manifest.md).

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
per-*dataset* version exists, see `docs/service/context-brief.md`), the
latter requires running established integration methods for comparison.

The prior architecture, `CrossModalNet` (jointly trained on RNA and
proteomics, 2,903-gene space), is kept as a documented baseline, not
erased — see `versions.html`'s "Prior baseline" card and
`service/model/legacy/v2/README.md`. The projection service pipeline (see
`service/README.md`) runs end to end against the v3 reference but is not
deployed or reachable from this site yet.

## Documentation

- [docs/README.md](docs/README.md) indexes the product docs and the research record.
- [docs/project-structure.md](docs/project-structure.md) covers the folder layout and where things go.
- [docs/file-index.md](docs/file-index.md) has one line per file.
- [CLAUDE.md](CLAUDE.md) sets the rules any change has to respect.
- [research/implementation-plan.md](research/implementation-plan.md) is the paper plan this work serves.
