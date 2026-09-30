# Project structure

VivOME Atlas has three products and one record:

1. **The website** (`web/`) is a static atlas viewer. It has no build step
   and no dependencies.
2. **The projection service** (`service/`) is a Python API that places an
   uploaded proteomics matrix into the atlas. It has its own dependencies.
3. **The benchmark** (`benchmark/`) compares the model against established
   integration methods under one fair protocol.
4. **The research record** (`research/`) holds plans, progress, notebook
   outputs and findings. It explains why the products are the way they are.

`docs/` explains how the products work. `scripts/` builds and checks the
repository. For a one-line description of every file, see
[file-index.md](file-index.md).

```
Vivome_Atlas/
├── README.md                 start here: what it is, quick start, test commands
├── CLAUDE.md                 rules for changing the repo (read before any change)
├── package.json              runs the JS tests (node --test); no dependencies
│
├── web/                      THE WEBSITE: serve this folder as-is
│   ├── *.html                one file per page (index, home, atlas, project, benchmark, versions)
│   ├── css/  js/             shared styling; pure ES modules (manifest.js, panels.js)
│   ├── data/                 what the pages load: atlas_manifest.json, cell metadata, embeddings
│   ├── plots/                30 precomputed 3D plots from the original model; no page shows them
│   └── tests/                node --test suites for js/
│
├── service/                  THE PROJECTION API: Python, POST /api/project
│   ├── app.py  config.py     HTTP entry point; every path and tuned constant
│   ├── pipeline/             the eight stages (align → smooth → encode → assign →
│   │                         calibrate → abstain → fall back → transfer)
│   ├── model/                the trained model and its evidence
│   │   ├── runtime/          everything the server loads (a deployment ships this folder)
│   │   ├── evidence/         measured tables behind the model's claims
│   │   ├── source/           how runtime/ was produced: export notebook, inputs, checksums
│   │   └── legacy/           previous model (v2/) and the dev checkpoint (dev/)
│   ├── examples/             a real PBMC240 upload for demos and end-to-end tests
│   └── tests/                unittest suite, with golden fixtures
│
├── benchmark/                FAIR COMPARISON: ours vs scANVI, MaxFuse, scGLUE
│   └── results/              local 1 GB cache of runs (gitignored)
│
├── scripts/                  BUILD AND CHECKS: manifest builder, repo path checker
│   └── archive/              one-off scripts kept as a record, no longer runnable
│
├── docs/                     HOW THE PRODUCTS WORK
│   ├── web/                  the manifest contract; the site's data files and Git LFS
│   └── service/              the API contract; the pipeline build brief
│
├── research/                 THE R&D RECORD
│   ├── roadmap.md  todo.md   the current plan, and progress against it
│   ├── benchmark/            the benchmark write-up: methodology, harness, results, limitations
│   ├── notebook-outputs/     committed tables from Colab notebook runs (nb1, nb1c, nb1d)
│   └── archive/              finished plans, frozen as written
│
└── data/                     EXTERNAL DATASETS
    └── incoming/             local staging for notebook deliveries (gitignored)
```

## Where does a new file go?

| You are adding… | Put it in | And also |
|---|---|---|
| A page, style, or front-end module | `web/` | a test in `web/tests/` if it's a JS module |
| A number the site displays | `scripts/build_manifest.py`, which writes `web/data/atlas_manifest.json` | never hard-code it in HTML — see [web/manifest.md](web/manifest.md) |
| A pipeline stage or service behaviour | `service/pipeline/` | a test in `service/tests/`; a constant in `service/config.py` |
| A file the server loads | `service/model/runtime/` | a path constant in `service/config.py` |
| A table that backs a model claim | `service/model/evidence/` | cite it from `MODEL_CARD.md` |
| A new benchmark arm | `benchmark/` | results in `research/benchmark/results.md` |
| Output tables from a notebook run | `research/notebook-outputs/<run>/` | an entry in `research/notebook-run-history.md` |
| A plan, decision, or finding | `research/` | a changelog line in `research/todo.md` |
| Documentation of how something works | `docs/web/` or `docs/service/` | a line in `docs/README.md` |
| A downloaded or delivered dataset | `data/incoming/` (local only) | commit only the small tables that numbers cite |
| A repo tool or check | `scripts/` | a test beside it (`scripts/test_*.py`) |

Any new tracked file also needs a line in [file-index.md](file-index.md).
`scripts/check_paths.py` fails the test run otherwise.

## Naming

- Folders and Markdown docs use lowercase kebab-case (`semi-supervised/`,
  `projection-api.md`).
- `README.md`, `CLAUDE.md` and `MODEL_CARD.md` keep their conventional
  uppercase names.
- Python modules use snake_case. `service` is the import name
  (`python3 -m service.app`).
- Data and model files keep the names they were exported with, because
  URLs, checksums, LFS rules and the notebooks all refer to them by name.

## Deliberate oddities

- **Git LFS pointers.** Six large files are in Git LFS: the three RNA
  tables in `web/data/`, `reference_model.pt`, `H_seed4.pt` and the SCoPE2
  TSV. Without `git lfs pull` they are small pointer files. The site
  detects this and explains the fix. `web/tests/lfs.test.js` expects
  pointers, so it fails after an LFS pull. That failure is expected.
- **Pending numbers.** Metrics that haven't been measured show as
  `Pending` and are never filled in by hand.
- **`web/miscellaneous.html` is blank on purpose.**
- **Frozen records.** `research/archive/` and `scripts/archive/` cite
  paths from their own time. The path checker skips `research/archive/`.
- **Local-only caches.** `benchmark/results/` and `data/incoming/` are
  gitignored. Some of `benchmark/results/` took hours of training to
  produce, so don't delete it casually.

## Tests

Run all three from the repository root before committing:

```bash
node --test                                          # web/js
python3 -m unittest discover -s scripts              # manifest builder + path/index check
python3 -m unittest discover -s service/tests -t .   # projection service
```
