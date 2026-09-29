# Architecture

All scripts live in `benchmark/`, use repo-relative paths (work
from a fresh clone, no hardcoded machine-specific paths), and write their
outputs to `benchmark/results/` (`.gitignore`d — regenerate
locally, don't expect it to be there after a fresh clone).

## Run order

```
load.py                     # 1. build the shared dataset (must run first)
  ├── pca / harmony          # 2. cheap floors (recompute_v2.py does these fresh)
  ├── maxfuse_run.py          # 2. heavy: produces embeddings only (~20 min)
  ├── scglue_run.py           # 2. heavy: produces embeddings only (~30 min)
  └── scanvi_run.py           # 2. heavy: produces embeddings only (~35 min)
                                    (2-5 can run in any order / in parallel)
recompute_v2.py              # 3. scores EVERYTHING: PCA, Harmony (refit fresh),
                              #    MaxFuse, scGLUE (loaded from cached .npy),
                              #    majority-class baseline. No retraining.
ours_run.py                  # 3. "ours" through the same harness (independent
                              #    of recompute_v2.py; reads real repo artifacts
                              #    directly, not benchmark/results/)
```

`evaluate.py` is imported by every scoring step (`recompute_v2.py`,
`scanvi_run.py`, `ours_run.py`) — it has no `__main__`, it's a library.

## File-by-file

### `load.py`

Reads directly from the real repo:

- `web/data/atlas_RNA_lat128-001-part1.csv` + `-part2.csv` → the full
  **85,232-cell** RNA reference. This is Git-LFS content — `git lfs pull`
  it first. (This repo deliberately ships these as unfetched LFS pointers
  by default; see `web/tests/lfs.test.js`. Fetching them is fine, it's just
  the one test that then correctly reports them as fetched.)
- `web/data/atlas_PROT_lat128.csv` → the 1,490-cell SCoPE2 protein query. See
  [known-limitations.md](known-limitations.md) for an important caveat
  about this specific file's provenance.

Both files carry `gene_*`-prefixed columns; `load.py` takes their
**intersection** (2,907 genes, confirmed identical sets between the two
files) — the natural, real shared feature space every integration
*baseline* (MaxFuse/Harmony/scANVI/scGLUE) works on. This is deliberately
**not** the frozen reference's own internal 9,002-gene training space,
which no baseline needs or sees.

Writes: `results/rna_X.npy` (85232×2907), `results/prot_X.npy`
(1490×2907), `results/rna_meta.csv` / `results/prot_meta.csv`
(`orig_index, class_idx, class_name`), `results/gene_cols.txt`.

RNA class labels are used freely by every downstream script (only *protein*
labels are restricted to final scoring, per methodology rule 1). No
subsampling happens here — every method script attempts the full 85,232
cells first (methodology rule 2's default), and none of them ended up
needing to fall back to a subsample.

### `pca_nn.py` (PCA floor) / `harmony_run.py` (Harmony floor)

Not present as standalone scripts in the repo — both are cheap enough
(~4s and ~15s respectively, even at full 85,232-cell scale) that
`recompute_v2.py` just refits them fresh every time it runs, rather than
caching intermediate embeddings for two near-instant computations. See
`recompute_v2.py` below.

If you want to run just the PCA/Harmony floors standalone, the logic is:
z-score RNA and protein independently (per-dataset, per-gene), concatenate,
fit one joint 50-component `sklearn.decomposition.PCA`, project both — that's
the PCA floor. Feed that same joint PCA embedding into
`harmonypy.run_harmony(pca_embedding, {"modality": [...]}, ["modality"],
max_iter_harmony=30)` — that's Harmony. Harmony's `Z_corr` output shape
varies by version; check `emb.shape[0] == n_pcs` and transpose if so, rather
than assuming an orientation.

### `maxfuse_run.py`

Unsupervised CCA-based fuzzy matching (`maxfuse` package). Full
85,232-cell RNA reference, no subsampling. Pipeline:
`Fusor(...) → split_into_batches → construct_graphs → find_initial_pivots →
refine_pivots(cca_components=10) → filter_bad_matches → propagate →
get_embedding`. Produces 20-dimensional embeddings.

`cca_components=10` (not MaxFuse's more common 20) — a deliberate,
disclosed choice for numerical robustness at this scale; see
[bugs-and-fixes.md](bugs-and-fixes.md).

Writes only embeddings: `results/rna_maxfuse.npy`, `results/prot_maxfuse.npy`.
Scoring is `recompute_v2.py`'s job — this keeps exactly one scoring code
path instead of one per method that could silently drift apart.

Wall time at full scale: ~21 minutes.

### `scglue_run.py`

Unsupervised graph-linked VAE (`scglue` package). The "guidance graph"
scGLUE needs is trivial here: a self-loop edge per shared gene (both
modalities' `AnnData.var_names` are identical gene name strings — that
string identity, not the graph structure, is what actually links the two
modalities in scGLUE; the self-loop just satisfies its structural
graph-validity check). `prob_model="Normal"` on both modalities, since the
input is already per-dataset z-scored continuous data, not raw counts (the
library's NB/ZINB defaults assume non-negative counts).

Must be run with `if __name__ == "__main__":` guarding all executable code
— scglue uses spawn-mode multiprocessing internally for background data
shuffling, which requires this on the calling script too.

At full scale, scGLUE's own dataset-size heuristic picks
`max_epochs`/`patience` automatically (48/4 here) — this script does not
override that; see [bugs-and-fixes.md](bugs-and-fixes.md) for how this
differs from a smaller-scale trial and what that revealed about training
stability.

Writes only embeddings: `results/rna_scglue.npy`, `results/prot_scglue.npy`
(8-dimensional, scGLUE's default). Wall time at full scale: ~29 minutes.

### `scanvi_run.py`

scANVI (`scvi-tools` package) — methodology rule 4's required
label-consuming scArches variant (not vanilla trVAE). Two-stage:
`SCVI(n_latent=30, n_layers=2, n_hidden=128, gene_likelihood="normal",
log_variational=False)` pretrained for up to 200 epochs (early stopping,
patience 15), then `SCANVI.from_scvi_model(...)` fine-tuned for up to 100
more epochs (same patience). Full 85,232-cell RNA reference.

Two real numerical fixes were needed to get scvi-tools to accept
per-dataset z-scored (negative-valued) input at all instead of the raw
non-negative counts it's built for by default — see
[bugs-and-fixes.md](bugs-and-fixes.md) for exactly what and why.

Sets `scvi.settings.seed = 0`, `torch.manual_seed(0)`, `np.random.seed(0)`
explicitly up front — **this matters a lot**: an earlier, unseeded run of
the same architecture/budget produced meaningfully different point
estimates on a rerun (see [results.md](results.md) for both sets of
numbers side by side, and [known-limitations.md](known-limitations.md) for
what this implies about trusting any single scANVI run).

Writes embeddings (`results/rna_scanvi.npy`, `results/prot_scanvi.npy`)
**and** scANVI's own native classifier's raw predictions
(`results/native_scanvi_pred_unrestricted.npy`,
`results/native_scanvi_pred_restricted.npy`) **and** a full scored,
CI-annotated `results/result_scanvi_v2.json` directly (unlike MaxFuse/
scGLUE, this script does its own scoring inline, since scANVI's *native*
protocol — its own built-in classifier head — isn't something
`recompute_v2.py` can derive from embeddings alone; it needs the trained
model object itself).

Wall time at full scale: ~35–36 minutes. Can be safely paused mid-training
with `kill -STOP <pid>` and resumed with `kill -CONT <pid>` (e.g. to free
up the machine) — this only adds the paused wall-clock duration to the
elapsed-time figure printed in the log; it does not corrupt or restart
training.

### `ours_run.py`

Runs the shipped model ("ours") through the *exact same* shared harness as
every baseline (methodology rule A) — on **real artifacts, no
reconstruction**.

**RNA side:** loads `service/model/runtime/reference_embedding.npy` directly — the
real, live, already-computed embedding for all 85,233 RNA cells that the
deployed service actually ships. Labels come from
`service.pipeline.reference.load_reference_metadata()`'s
`class_idx_by_cell`, aligned row-for-row with the embedding array. Row
42616 (a neutrophil cell absent from the Atlas CSVs) is dropped so this
script's RNA set exactly matches the 85,232 cells every baseline trained on
— see [bugs-and-fixes.md](bugs-and-fixes.md#7).

**Protein side:** `service/model/source/app_export/prot_embedding_scope2.npy` —
the export notebook's own real, saved embedding for all 1,490 SCoPE2
protein cells. Labels come from
`service/model/source/app_export/atlas_PROT_v3_meta.csv`'s `true_class_name`
column, in that file's own row order. See
`service/model/source/app_export/README.md` for these files' provenance and
sha256 verification.

An earlier version of this script reconstructed the protein embedding from
`web/data/atlas_PROT_lat128.csv` via the real `service.pipeline` stack
(`alignment.align_to_feature_space` → `smoothing.fuzzy_smooth` →
`encoder.load_encoder()`), because the real embedding wasn't available in
this repository at the time. That reconstruction is gone now that the real
artifacts are committed — but comparing the two was exactly what surfaced
two real production bugs (see [bugs-and-fixes.md](bugs-and-fixes.md)), and
`service/tests/test_e2e_real_export.py` keeps that same comparison running
permanently as a regression guard.

Imports directly from the real `service` package
(`sys.path.insert(0, str(Path(__file__).resolve().parents[2]))`, i.e. the
repo root) — this script only works when run from inside a checkout of
this repository, not standalone.

Writes `results/result_ours.json`, which includes the real-embedding
harness numbers alongside the historical documented figures
(`service/model/evidence/v3_tables/support_restricted_assignment.csv`) as a
separate, clearly-labeled field for comparison — never merged into one
number.

### `recompute_v2.py`

The scoring pass for every method that has cached embeddings or is cheap
enough to refit fresh. Deliberately does **zero retraining**:

- PCA and Harmony: refit fresh from `results/rna_X.npy`/`results/prot_X.npy`
  (deterministic, fixed `random_state=0`, seconds — not meaningfully a
  "rerun" of anything expensive).
- MaxFuse and scGLUE: **loads** their already-saved `.npy` embeddings from
  disk; does not touch the training packages (`maxfuse`, `scglue`) at all.
- Majority-class baseline: no embedding involved whatsoever.

For each, calls `evaluate.knn_classifier_predict` +
`evaluate.nearest_centroid_predict`, wraps both in `evaluate.evaluate_arm`
(scores + bootstrap CIs for both regimes), and writes
`results/result_<method>_v2.json`.

### `evaluate.py`

The shared library every other script imports. See
[methodology.md](methodology.md) for what each function means
methodologically; mechanically:

- `knn_classifier_predict(rna_emb, rna_labels, prot_emb, supported=("macrophage","monocyte"), k=30)`
  → `{"unrestricted": array, "restricted": array}` of predicted labels.
- `nearest_centroid_predict(rna_emb, rna_labels, prot_emb, supported=...)`
  → same shape.
- `score(true_labels, pred_labels, n_candidate_classes)` → accuracy/balanced
  accuracy as plain floats.
- `bootstrap_ci(true_labels, pred_labels, n_boot=2000, seed=0)` → 95%
  percentile CIs on both metrics.
- `evaluate_arm(true_labels, pred_unrestricted, pred_restricted, n_classes_unrestricted, n_classes_restricted)`
  → bundles the above into the `{"unrestricted": {...}, "restricted": {...}}`
  shape every `result_*_v2.json` uses.
- `pool_first_knn_predict(rna_emb, rna_labels, prot_emb, supported=..., k=30)`
  → restricted-only array of predicted labels, mirroring
  `service/pipeline/assignment.py`'s real `_assign_knn` (imports and reuses
  `service.pipeline.topk.chunked_topk` directly — not a reimplementation).
- `paired_bootstrap_diff(true_labels, pred_a, pred_b, n_boot=2000, seed=0)`
  → `{"point_estimate_pct": float, "ci_95_pct": [lo, hi]}` for
  `balanced_accuracy(pred_a) - balanced_accuracy(pred_b)`, using the same
  resampled indices for both predictions in every resample.

### `paired_and_pool_first.py`

Follow-up analysis script, run after every other script has produced its
cached embeddings. Computes, for every arm: the pool-first restricted kNN
number alongside the existing post-hoc-masking one
(`results/result_pool_first_knn.json`), and — for "ours" against each of
the 3 scANVI seeds — the paired bootstrap difference in both regimes
(`results/result_paired_bootstrap.json`). Zero retraining; reads only
already-cached `.npy` embeddings (including all 3 scANVI seeds' — run
`scanvi_run.py` under seeds 0, 1, and 2, each producing its own
`rna_scanvi_seed{N}.npy`/`prot_scanvi_seed{N}.npy`, before running this).

## Reproducing from a fresh clone

```bash
cd Vivome_Atlas
git lfs pull   # fetches the RNA expression matrix AND
               # service/model/source/app_export/blood_joint_cells_by_proteins_GENELEVEL.tsv
               # (large; flips web/tests/lfs.test.js red by design, see that
               # test's comment, and is required for ours_run.py and
               # service/tests/test_e2e_real_export.py)
python3 -m pip install -r service/requirements.txt   # includes scikit-learn,
                                                       # needed by both the
                                                       # real service and this
                                                       # benchmark's PCA/kNN
python3 -m pip install harmonypy maxfuse scarches scvi-tools scglue \
    anndata networkx   # one-off benchmark-only dependencies, not shipped
                        # with the real service
cd benchmark
python3 load.py
python3 maxfuse_run.py      # ~21 min
python3 scglue_run.py       # ~29 min
python3 scanvi_run.py 0     # ~35 min -- repeat with 1 and 2 for the 3-seed table
python3 scanvi_run.py 1
python3 scanvi_run.py 2
python3 recompute_v2.py     # seconds -- scores PCA/Harmony/MaxFuse/scGLUE/majority
python3 ours_run.py         # ~1 min -- scores "ours" through the same harness
python3 paired_and_pool_first.py   # seconds -- needs all 3 scANVI seeds' embeddings cached
```

The three heavy scripts (`maxfuse_run.py`, `scglue_run.py`, `scanvi_run.py`)
are independent of each other and can run in parallel if the machine has
the memory for it (each held ~2–3.6 GB resident at peak on a 16 GB, CPU-only
machine during original development — running all three at once was not
tested and is not guaranteed to fit).
