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
cd web && python -m http.server 8000
# open http://localhost:8000/index.html
```

Development runs on a Windows PC with an NVIDIA GPU: the full setup (conda
environment with CUDA, checkpoints, local-only files, long runs) is in
[docs/setup-windows.md](docs/setup-windows.md). The commands here run in Git
Bash.

The atlas fetches data from `web/data/` over HTTP, so opening `index.html` from
`file://` will not load. Serve the `web/` folder.

To run the projection service locally, see `service/README.md`:

```bash
pip install -r service/requirements.txt
python -m service.app              # from the repository root
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
| `index.html` | Landing page: the title panel, seven sections of cards, the finale |
| `atlas.html` | Interactive 3D cell viewer with cross-modal support map and alignment diagnostics |
| `project.html` | The projection tool: sends a matrix to a locally run service and shows the result |
| `manuscript.html` | Evidence bank for a journal paper on the served model, with the benchmark tables |
| `workflow.html` | How VivOME works start to end, following one cell of the PBMC240 example |
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
python scripts/build_manifest.py
```

## Tests

Nothing to install.

```bash
node --test                                          # JS modules under web/js/
python -m unittest discover -s scripts             # manifest builder + repo path check
python -m unittest discover -s service/tests -t .   # projection service (needs service/requirements.txt)
```

## Current state

Atlas version `0.6.0`, manifest schema `1.0`.
- **Model:** `VivOME v4.1`, served again (first released in `0.4.0`). Five
  RNA-trained encoders (V2, module pooling, 9,002-gene feature space, latent
  dim 128) whose probabilities are averaged, answering at class, group or
  lineage level, or abstaining with a reason. Its best guess also uses each
  cell's correlation to the reference's class means, where that carries
  signal.
- **Earlier releases:** `VivOME v4.2` (atlas `0.5.0`, protein class means in
  the best guess), `VivOME v3.1` (atlas `0.3.0`) and `VivOME v3 reference`
  (atlas `0.2.0`) stay selectable in the service.
- **Data:** 22 cell types, 2 of them cross-modal in the atlas (macrophage,
  monocyte) and 20 RNA-only. RNA 85,233 cells; protein 1,490 cells (SCoPE2
  mass spectrometry).
- **Benchmark:** published on `web/manuscript.html`: VivOME against the
  corrected baselines on Khoury 2026 (post-hoc), Fulcher 2026,
  PBMC240 and SCoPE2 (`research/benchmark/results.md`), beside the rest of
  the evidence a journal paper would use.

Latent centroid cosine and the modality probe are measured for the 2
cross-modal classes, in v3.1's coordinate space, which v4.1 and v4.2 share.
Per-class transfer accuracy is **pending**: it has no per-class source data
yet (a per-*dataset* version exists, see `docs/service/context-brief.md`).

The first architecture, `CrossModalNet` (jointly trained on RNA and
proteomics, 2,903-gene space), is kept as a documented baseline, not erased.
See `versions.html` and `service/model/legacy/v2/README.md`. The projection
service (see `service/README.md`) runs end to end and is hosted on Google
Cloud Run: the Project page sends uploads there, or to a copy you run
locally (`deploy/huggingface/PUBLISH.md`).

## Documentation

- [docs/README.md](docs/README.md) indexes the product docs and the research record.
- [docs/project-structure.md](docs/project-structure.md) covers the folder layout and where things go.
- [docs/file-index.md](docs/file-index.md) has one line per file.
- [CLAUDE.md](CLAUDE.md) sets the rules any change has to respect.
- [research/implementation-plan.md](research/implementation-plan.md) is the paper plan this work serves.
