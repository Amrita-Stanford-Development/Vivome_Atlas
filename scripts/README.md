# scripts/

Repository build and check scripts. Standard library only. Run them from the
repository root.

| Script | When to run it |
|---|---|
| `build_manifest.py` | After any change to `web/data/` metadata or `service/model/` evidence. It regenerates `web/data/atlas_manifest.json`; commit the result. See [docs/web/manifest.md](../docs/web/manifest.md). |
| `check_paths.py` | Runs as part of `python3 -m unittest discover -s scripts`. It fails if a path cited anywhere in the repo doesn't exist, or a tracked file is missing from [docs/file-index.md](../docs/file-index.md). |
| `archive/promote_v3_atlas.py` | Never. It is a one-off that has already run, kept as the record of how the v3 viewer metadata was produced. Its inputs were deleted by design. |

```bash
python3 scripts/build_manifest.py
python3 scripts/check_paths.py
python3 -m unittest discover -s scripts     # both test suites
```
