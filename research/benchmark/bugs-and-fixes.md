# Bugs and fixes

Every real, confirmed bug hit while building this tool, in the order they
mattered. Two of these are bugs in the **actual production service**, not
just this benchmark tooling — flagged clearly below. The second one
(`encoder.py`'s activation function) turned out to be the dominant cause of
a discrepancy this document's earlier version had misattributed entirely to
a data-provenance gap — see the postscript at the end of entry 0.

## 0. `service/pipeline/encoder.py` used the wrong activation function — ReLU instead of GELU (fixed in the real repo)

**The single most consequential bug found in this entire investigation.**
Once the real notebook-produced protein embedding (`prot_embedding_scope2.npy`)
and the real raw input it came from
(`blood_joint_cells_by_proteins_GENELEVEL.tsv`) were obtained (see
[known-limitations.md](known-limitations.md)), running that raw file
through the full, already-fixed `service/pipeline` (alignment → smoothing →
encoder) gave embeddings only **~0.75 median cosine similarity** to the
notebook's real embedding — nowhere near the ~1.0 a correct pipeline should
produce, per the repository owner's own explicit acceptance criterion.

Direct comparison of `service/pipeline/encoder.py`'s `ModulePoolingEncoder`
against the notebook's `ModulePoolEnc`/`mlp()` found the cause immediately:
the notebook's trained architecture uses `nn.GELU()` between its `Linear`→
`LayerNorm` layers; the shipped `encoder.py` used `nn.ReLU()` in the exact
same position. **Activation functions carry no learnable parameters**, so
`model.load_state_dict(state_dict, strict=True)` — which only checks
parameter *names and shapes* — loaded the real, correctly-trained weights
into a model that computes a genuinely different function. No error, no
warning, no shape mismatch: just a systematically wrong forward pass that
happened to still correlate with the right answer (real trained weights
carry most of a representation's structure even through the wrong
nonlinearity) without reproducing it.

**Fix:** `nn.ReLU()` → `nn.GELU()` in `ModulePoolingEncoder.__init__`, in
both of the body's two hidden layers. Verified: running the real raw TSV
through the notebook's own preprocessing convention (dataset-level median
fill, then z-score, for both alignment and the smoothing graph) plus the
GELU-corrected encoder reproduces the notebook's saved embedding at
**cosine similarity 1.000000 for every one of the 1,490 cells** — median,
5th percentile, mean, and minimum all exactly 1.0, confirming the
activation function was the entire remaining gap once that exact
preprocessing is used. Running the real *production* pipeline
(`service/pipeline/pipeline.py`'s actual, un-changed Stage 2 convention,
which differs from the notebook's — see
[known-limitations.md](known-limitations.md#the-full_query_values-convention-gap--service-vs-notebook--resolved))
with the same GELU fix reaches ~0.9985 median cosine on this same input,
not exactly 1.0 — still an enormous improvement over the ~0.75 the ReLU
bug produced, but a second, smaller, separate, and currently unfixed
convention gap, documented on its own in
[known-limitations.md](known-limitations.md). Added
`test_body_uses_gelu_not_relu` and `test_e2e_real_export.py` to
`service/tests/` as permanent regression guards — the latter tests the
*real* production convention (not the notebook's), with thresholds set to
what that real, imperfect convention actually achieves.

**Postscript — this changes an earlier conclusion in this document, and
invalidates every "ours" number this benchmark work computed through
`service/pipeline` before this fix (commit `056f136`).** An earlier round
of this benchmark work found that a from-scratch reconstruction of "ours"
could get very close to the historical restricted figure (85.50%/83.32% vs.
86.17%/79.79%) but not the unrestricted one, and attributed essentially the
entire residual gap to the protein-side file provenance issue (the
reconstruction reading a narrower, wrong-gene-panel file — see
[known-limitations.md](known-limitations.md)). **That attribution was
wrong, or at least badly incomplete: that reconstruction ran through this
same buggy ReLU encoder, so its 85.50%/83.32% and every other number it
produced cannot be trusted as evidence about the file-provenance issue in
isolation — the two problems were confounded.** With both bugs now fixed
and the real files in hand, "ours" is scored directly on
`prot_embedding_scope2.npy` with no reconstruction step at all — see
[results.md](results.md), which no longer contains any pre-`056f136`
reconstruction number. The file-provenance issue was real and worth
finding, but the activation-function bug was the larger effect.

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

(Both pinned in `service/model/evidence/v3_tables/support_restricted_assignment.csv`,
produced by `service/model/source/VivOME_Prototype_Export.ipynb`.)

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

**Residual gap — reported at the time as "not a code bug," which was
premature.** After this fix, a from-scratch reconstruction of "ours" got
the *restricted* regime to 85.50%/83.32% — very close to the documented
86.17%/79.79%. The *unrestricted* regime did not close the same way. This
was attributed entirely to a separate data-provenance issue (see
[known-limitations.md](known-limitations.md#the-atlas_prot_lat128csv-provenance-problem)).
**That reconstruction was also running through the ReLU-instead-of-GELU
encoder bug (entry 0), not found until a later round — the 85.50%/83.32%
number itself, and the attribution of the unrestricted gap to file
provenance alone, should both be treated as superseded, not as evidence
about either issue in isolation.** See entry 0's postscript.

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

## 7. `Atlas/atlas_RNA_lat128-001-part{1,2}.csv` are missing one cell between them

The baselines' RNA reference load (`benchmark/load.py`) counts
85,232 cells; `service/model/runtime/reference_embedding.npy` (the real, live
artifact) has 85,233. Tracing it down: `-part1.csv` ends at
`orig_index=42615`; `-part2.csv` starts at `orig_index=42617`.
`orig_index=42616` — a neutrophil cell, barcode
`TSP14_Blood_NA_10X_2_1_AGGAGGTGTGTCCAAT` — exists in
`reference_embedding.npy`/`reference_metadata` but was dropped somewhere in
whatever process split the original 85,233-row file into these two
Git-LFS-sized halves.

**Fix:** since every baseline had already trained on the 85,232-cell set
(retraining them was explicitly out of scope — see
[known-limitations.md](known-limitations.md)), "ours" is aligned *down* to
match: `benchmark/ours_run.py` drops row 42616 from
`reference_embedding.npy` before fitting anything, rather than the Atlas
CSVs being fixed to add the missing row back (which would require
retraining every baseline on the corrected 85,233-cell set instead). One
cell out of 85,233, in the single largest RNA class (32,197 neutrophils
originally), has no material effect on any result — but every arm should
still see the identical set, and now they do.

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
