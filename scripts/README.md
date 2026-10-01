# scripts/

Repository build and check scripts. Standard library only. Run them from the
repository root.

| Script | When to run it |
|---|---|
| `build_manifest.py` | After any change to `web/data/` metadata or `service/model/` evidence. It regenerates `web/data/atlas_manifest.json`; commit the result. See [docs/web/manifest.md](../docs/web/manifest.md). |
| `export_atlas_coordinates.py` | After the served model's coordinate space changes. It rewrites the PCs and SCoPE2 calls in `web/data/metadata_{RNA,PROT}_lat128.csv` from the served v3.1 model; then run `build_manifest.py`. |
| `fetch_v31_members.py` | Once per checkout, to serve v3.1. It copies the five NB1b checkpoints, which are kept outside git, into `service/model/v3_1/members/`, checking each sha256 (`service/model/README.md`, v3_1/). |
| `v31_evidence.py` | When v3.1's members or the SCoPE2 matrix change. It writes `service/model/evidence/v3_1_tables/`, after checking that its method reproduces v3's tables; then run `build_manifest.py`. |
| `check_paths.py` | Runs as part of `python -m unittest discover -s scripts`. It fails if a path cited anywhere in the repo doesn't exist, or a tracked file is missing from [docs/file-index.md](../docs/file-index.md). |
| `archive/promote_v3_atlas.py` | Never. It is a one-off that has already run, kept as the record of how the v3 viewer metadata was produced. Its inputs were deleted by design. |

```bash
python scripts/build_manifest.py
python scripts/check_paths.py
python -m unittest discover -s scripts     # both test suites
```
