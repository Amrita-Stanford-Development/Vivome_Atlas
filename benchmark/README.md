# benchmark/

The fair comparison harness. It scores the shipped encoder ("ours") against
scANVI, MaxFuse, scGLUE and simple floors (PCA, Harmony, majority class)
under one shared protocol: same inputs, same classifier, same regimes, same
bootstrap confidence intervals, and no protein labels until scoring.

Nothing here feeds the website. `benchmark.rows` in the manifest stays
pending until the owner signs off on the results.

## Run order

```
python3 benchmark/load.py              # 1. shared, label-free inputs → results/ (must run first)
python3 benchmark/maxfuse_run.py       # 2. embeddings per method (heavy; any order)
python3 benchmark/scglue_run.py
python3 benchmark/scanvi_run.py
python3 benchmark/recompute_v2.py      # 3. scores every cached arm under the current protocol
python3 benchmark/ours_run.py          #    and ours, through the same evaluate.py
```

PBMC240 arm: `pbmc240_lineage_prep.py`, then `scanvi_run_pbmc240.py`.

Fulcher 2026, the held-out arm, fixed by
[research/benchmark/protocol-fulcher2026.md](../research/benchmark/protocol-fulcher2026.md):
1. `datasets.py` registers the dataset.
2. `fulcher2026_embed.py` runs the checkpoint gate, then embeds with all ten
   models.
3. `scanvi_run_fulcher2026.py SEED VARIANT` runs scANVI, six times in all.
4. `fulcher2026_score.py` scores; it is the only step that reads labels.
Follow-ups: `paired_and_pool_first.py` and `pbmc240_convention_check.py`.

Outputs go to `results/`. It is gitignored and ~1 GB. Some of it is scANVI
training output that took about an hour per seed, so regenerate before
deleting anything. The benchmark's dependencies (scvi-tools, MaxFuse,
scGLUE, Harmony) are not in `service/requirements.txt`.

## Documentation

- [research/benchmark/](../research/benchmark/README.md) has the
  methodology, a file-by-file harness guide, results, bugs found, and
  known limitations.
- [research/benchmark/harness.md](../research/benchmark/harness.md)
  covers each script's inputs and outputs, and how to reproduce from a
  fresh clone.
