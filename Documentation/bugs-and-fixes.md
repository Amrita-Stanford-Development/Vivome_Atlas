# Bugs and fixes

Every real, confirmed bug hit while building this tool, in the order they
mattered. One of these was a bug in the **actual production service**, not
just this benchmark tooling — flagged clearly below.

## 1. `service/pipeline/smoothing.py` had drifted from the notebook that measured its own numbers (fixed in the real repo)

**This is a production bug, not a benchmark-script bug.** Before trusting
any reconstruction of "ours," the repository owner asked why a from-scratch
run of the real `service/pipeline` (alignment → smoothing → encoder →
assignment, all real production code) could not reproduce the two
already-measured, already-verified headline numbers for the frozen
reference:

- unrestricted (22 classes): 45.37% accuracy / 31.08% balanced accuracy
- restricted ({macrophage, monocyte}): 86.17% accuracy / 79.79% balanced
  accuracy

(Both pinned in `service/model/v3_tables/support_restricted_assignment.csv`,
produced by `service/model/VivOME_Prototype_Export.ipynb`.)

**Root cause**, found by direct code comparison against the notebook:

- **Inverted alpha convention.** The notebook blends
  `(1 - alpha) * original + alpha * neighbour_average` — with `alpha=0.6`,
  that's *mostly smoothed*. The shipped code computed
  `alpha * original + (1 - alpha) * neighbour_average` — the same `alpha=0.6`
  constant, but meaning *mostly original, barely smoothed*. Same number,
  opposite meaning.
- **Different neighbor graph.** The notebook builds its kNN graph on a
  50-component PCA of the query's own full feature set (L2-normalized,
  Gaussian kernel over distance, bandwidth = each cell's own k-th neighbor
  distance). The shipped code built it on the raw, un-reduced feature set
  with a softmax-over-cosine-similarity kernel instead. A structurally
  different graph, not just a reweighting.

**Fix**, applied directly to the repository (not this benchmark's
scratchpad):

- `service/pipeline/smoothing.py` rewritten to match the notebook exactly:
  PCA(50)-reduced, L2-normalized, Gaussian-kernel kNN graph; corrected
  `(1 - alpha) * original + alpha * neighbour_average` blend.
- `service/config.py` gained `SMOOTHING_N_PCA = 50` and `SMOOTHING_SEED = 0`
  constants (previously only `SMOOTHING_K`/`SMOOTHING_ALPHA` existed).
- `scikit-learn>=1.3` added to `service/requirements.txt` (needed for
  `sklearn.decomposition.PCA` / `sklearn.neighbors.NearestNeighbors`, not
  previously a service dependency).
- `service/tests/test_smoothing.py`'s two tests were corrected — they had
  encoded the *old*, inverted alpha convention as their expected behavior
  (`alpha=1.0` "returns original unchanged" became `alpha=0.0`; an
  "identical neighbours fully swap values" test's `alpha=0.0` became
  `alpha=1.0`).

All three repo test suites pass after the fix: 51 JS tests, 31 manifest
tests, 86 backend tests.

**Residual gap, not a code bug:** after this fix, a from-scratch
reconstruction of "ours" got the *restricted* regime to 85.50%/83.32% —
very close to the documented 86.17%/79.79%. The *unrestricted* regime did
not close the same way. That residual gap turned out to be a separate,
data-provenance issue — see
[known-limitations.md](known-limitations.md#the-atlas_prot_lat128csv-provenance-problem).

## 2. Harmony's `Z_corr` output orientation

`harmonypy.run_harmony(...)`'s result object's `.Z_corr` attribute was
already `(n_cells, n_pcs)`-shaped in the installed version — an early draft
of the Harmony script assumed the historically-common `(n_pcs, n_cells)`
orientation and `.T`-transposed it, which silently produced a
`(50, 86722)` array instead of `(86722, 50)` and crashed downstream with a
`sklearn` "inconsistent number of samples" error the moment a classifier
tried to fit on it.

**Fix:** a shape check instead of an assumption —
`if emb.shape[0] == pca_emb.shape[1]: emb = emb.T`. Don't assume a specific
orientation from a library's output; check the shape you actually got.

## 3. MaxFuse: `SVD did not converge` at full 85,232-cell scale

At full scale, MaxFuse's internal batching (`split_into_batches`) split the
RNA reference into 85 batches of ~1,000 cells each — a much finer split
than an earlier, smaller-scale (15,000-cell) trial's 15 batches. With
`refine_pivots(cca_components=20)`, batch 38 of 85 hit a genuine
`numpy.linalg.LinAlgError: SVD did not converge` deep inside `sklearn`'s
CCA fit — one specific batch's pivot cross-covariance matrix was
apparently near-rank-deficient, likely because that particular random
batch happened to land very few, or highly collinear, matched pivot pairs.

**Fix:** lowered `cca_components` from 20 to 10 — a smaller, more
numerically conservative rank requirement for the same CCA fit — and
reran from scratch. Completed cleanly past the previous crash point on the
second attempt, with no further errors across all 85 batches. This is a
disclosed, legitimate hyperparameter choice (a smaller embedding rank is
not a subsample, and does not change which cells are used), not a
workaround that hides instability.

## 4. scANVI: two numerical bugs from assuming raw count data

`scvi-tools`, including `SCVI`/`SCANVI`, defaults are built for raw,
non-negative single-cell count data. This benchmark's input is per-dataset
z-scored continuous data (negative values are normal and common). Two
distinct defaults broke immediately on that mismatch:

- **`log_variational=True`** (the default): applies `torch.log1p` to the
  encoder's input before anything else. `log1p` of a value less than -1 is
  undefined (produces `NaN`) — and z-scored data routinely has such values.
  Result: `NaN` in the very first forward pass, before any training even
  began.

  **Fix:** `log_variational=False`.

- **The default "observed library size" path** computes
  `library = log(X.sum(axis=1))` from the raw input, per cell. A
  per-dataset z-scored row sums to approximately zero by construction
  (often exactly negative, depending on the specific gene panel) —
  `log` of a non-positive number is `NaN` or undefined. This crashed
  slightly later than the first bug, inside the *generative* (decoder)
  half of the model, once the first bug was already fixed.

  **Fix:** added a constant `adata.obs["size_factor"] = 1.0` column and
  passed `size_factor_key="size_factor"` to `SCVI.setup_anndata(...)`,
  which bypasses the count-based library-size *estimation* entirely in
  favor of a fixed constant — appropriate here, since z-scored continuous
  values have no library-size concept to normalize away in the first
  place.

## 5. scGLUE: real training instability at small scale, stable at full scale

An earlier, smaller-scale (15,000-cell RNA subsample) trial of scGLUE
showed genuine training instability during its fine-tuning phase:
`val_x_rna_nll` exploded across epochs (1.8 → 22 → 625 → 3,723) before
early stopping restored an earlier, good checkpoint. This was a real,
disclosed divergence — not silently ignored, and not hidden by only
reporting the post-early-stopping numbers without comment.

At **full 85,232-cell scale**, the same architecture trained cleanly:
`val_x_rna_nll` converged smoothly (1.38 → 1.32 → 1.32) with no blowup at
any point, across both scGLUE's pretrain and fine-tune phases. Full-scale
training is not automatically more stable than a subsample in general —
this is simply what was observed here, and is reported as such rather than
assumed to generalize.

Despite the stable training, scGLUE's resulting cross-modal transfer
accuracy is near chance (see [results.md](results.md)) — a real,
non-diverged, disappointing result, not a crash to work around.

## 6. scANVI: no fixed seed meant the first run's numbers weren't reproducible

The first scANVI run did not set any random seed (`scvi.settings.seed`,
`torch.manual_seed`, `np.random.seed` were all left at their process
defaults). It also never called `np.save` on its trained embeddings or
`model.save(...)` on the trained model itself — so once that process
exited, there was no way to recover its per-cell predictions to compute a
bootstrap confidence interval without training again.

A second run, with the *same* architecture and training budget but an
explicit `seed=0` set for all three RNG sources up front, produced
**meaningfully different point estimates** — not a rounding difference, a
real swing (e.g. the shared-kNN-rule restricted balanced accuracy moved
from 64.48% to 77.26% between the two runs; scANVI's own native classifier
moved from 74.47% to 57.89%, in the opposite direction). See
[results.md](results.md) for both runs' full numbers side by side, and
[known-limitations.md](known-limitations.md) for what this run-to-run
variance implies about trusting any single scANVI measurement.

**Fix, going forward:** always set `scvi.settings.seed` (and the
underlying `torch`/`numpy` seeds) explicitly *before* constructing any
`scvi-tools` model, and always cache embeddings/predictions to disk
immediately after training, specifically so a bootstrap CI (or any other
downstream analysis) never requires retraining a stochastic model a second
time just to recover something that should have been saved the first time.

## A benign, session-long red herring: Apple Accelerate BLAS warnings

Nearly every matrix multiplication run this session — PCA, Harmony,
MaxFuse, scANVI, scGLUE similarity computations, even runs on freshly
generated clean random data used specifically to test this — produced
`RuntimeWarning: divide by zero / overflow / invalid value encountered in
matmul`. This was confirmed to be a benign artifact of the macOS ARM
Accelerate BLAS backend, not real numerical corruption: running the exact
same matmul shape on fresh, clean random data reproduces the identical
warning. The practice adopted throughout this work was to always explicitly
check `.isnan().sum()` / `.isinf().sum()` on actual outputs, rather than
trusting or distrusting a computation based on this warning text alone.
