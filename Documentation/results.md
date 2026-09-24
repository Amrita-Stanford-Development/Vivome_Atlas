# Results

All numbers below: full 85,232-cell RNA reference for every method (no
subsampling anywhere; "ours" aligned down from 85,233 by dropping one
CSV-split-dropped neutrophil cell — see
[bugs-and-fixes.md](bugs-and-fixes.md#7)), RNA labels used freely, **protein
labels touched only at this final scoring step, in every arm**. 95%
bootstrap confidence intervals (2,000 stratified resamples) in brackets.
Ranked by **balanced accuracy**, not accuracy.

**"Ours" is scored on the real artifacts, not a reconstruction:**
`service/model/reference_embedding.npy` (RNA, live production embedding)
and `service/model/app_export/prot_embedding_scope2.npy` (the export
notebook's own real, saved SCoPE2 protein embedding, sha256-verified
against `BUNDLE_MANIFEST.json`), with labels from
`atlas_PROT_v3_meta.csv`'s `true_class_name` column in that file's own row
order — never `Atlas/atlas_PROT_lat128.csv`, a legacy file with an
unverified row order (see [known-limitations.md](known-limitations.md)).
An earlier version of this table scored a from-scratch *reconstruction* of
the protein embedding instead; that reconstruction turned out to be
distorted by two real bugs (one in the protein-side file used, one — the
larger effect — in `service/pipeline/encoder.py`'s activation function; see
[bugs-and-fixes.md](bugs-and-fixes.md)) and has been removed from this
table entirely, not kept as a labeled row.

**Sanity check (run before trusting anything else here):** the real
protein embedding, scored by cosine-argmax against
`service/model/reference_centroids.npy` (the trained centroids, not
recomputed class means), reproduces the historical figures to 4 decimal
places: 45.3691%/31.0833% unrestricted, 86.1745%/79.7915% restricted
(targets: 45.37/31.08, 86.17/79.79). The trained centroids and
harness-computed RNA class-mean centroids are cosine-identical (1.0000) for
all 22 classes — there is no meaningful difference between "the trained
centroids" and "class means of the real RNA embedding" in this model.

**A separate, open caveat that does *not* affect any number in this
document:** "ours" here is scored directly against
`prot_embedding_scope2.npy` (the notebook's own saved embedding), never
re-derived through `service/pipeline`. Whether a live user uploading a
similar file to the real API would get an embedding this close to the
notebook's depends on a currently-unresolved convention gap between
`service/pipeline/pipeline.py` and the notebook — see
[known-limitations.md](known-limitations.md#the-full_query_values-convention-gap-service-vs-notebook).
On dense data like SCoPE2 the gap is small (~0.9985 median cosine); on data
with substantial missing values (typical for real single-cell proteomics)
it can be severe (~0.78 median, some cells anti-correlated). This is about
the *live service's* fidelity, not about anything reported below.

## Restricted regime (candidates = {macrophage, monocyte})

The only regime with real cross-modal ground truth for every candidate
class — every one of the 1,490 protein query cells is either macrophage or
monocyte.

| Rank | Method | Protocol | Accuracy % | Balanced accuracy % |
|---|---|---|---|---|
| 1 | **Ours** | shared kNN rule | 84.97 [83.22, 86.78]\* | **88.40** [86.85, 89.92]\* |
| 2 | **Ours** | native nearest-centroid | 86.17 [84.56, 87.85]\* | 79.79 [77.38, 82.27]\* |
| 3 | scANVI (3-seed mean) | shared kNN rule | 70.67 (±2.48) | 76.89 (±0.99) |
| 4 | scANVI (3-seed mean) | native scANVI classifier | 74.77 (±18.59) | 73.15 (±28.49) |
| 5 | scANVI (3-seed mean) | native nearest-centroid | 61.21 (±19.13) | 64.42 (±26.66) |
| 6 | MaxFuse | shared kNN rule | 69.80 [68.39, 71.21]\* | 50.05 [48.49, 51.63]\* |
| — | **Majority class ("monocyte")** | trivial floor | 73.56 [71.34, 75.77]\* | 50.00 [50.00, 50.00]\* |
| 7 | Harmony (batch-correction floor) | native nearest-centroid | 50.20 [47.65, 52.68]\* | 54.20 [51.42, 57.02]\* |
| 8 | Harmony (batch-correction floor) | shared kNN rule | 46.78 [44.36, 49.40]\* | 50.49 [47.70, 53.38]\* |
| 9 | MaxFuse | native nearest-centroid | 51.95 [49.53, 54.50]\* | 52.38 [49.45, 55.29]\* |
| 10 | PCA floor | shared kNN rule | 67.25 [65.17, 69.40]\* | 57.66 [55.04, 60.37]\* |
| 11 | PCA floor | native nearest-centroid | 55.97 [53.42, 58.52]\* | 58.21 [55.42, 60.96]\* |
| 12 | scGLUE | shared kNN rule | 28.59 [27.32, 29.93]\* | 48.21 [46.52, 49.78]\* |
| 13 | scGLUE | native nearest-centroid | 47.92 [45.37, 50.54]\* | 47.20 [44.22, 50.20]\* |

\* 95% bootstrap CI (single run). scANVI rows show 3-seed mean (±spread —
**range, max−min**, across seeds 0/1/2, not standard deviation; see the
[paired bootstrap](#paired-bootstrap-ours-minus-scanvi) section below for
the SD alongside the range) instead — see
[scANVI across seeds](#scanvi-across-seeds) for the per-seed breakdown;
seed 0 alone is not representative given the spread.

**Reading this table:** on the real embedding, under the one rule applied
identically to every method, "ours" leads scANVI's 3-seed mean by **11.5
points of balanced accuracy** (88.40% vs. 76.89%). This is not just an
eyeballed non-overlap of two independent CIs — a **paired** bootstrap
(same resampled query cells scored under both methods in every resample,
which is the statistically correct comparison here) confirms the
restricted-regime difference is **+11.1 to +12.1 points across all 3
scANVI seeds, with every seed's 95% CI on the difference excluding zero**
(smallest: seed 0, [+9.10, +13.22]) — see
[Paired bootstrap](#paired-bootstrap-ours-minus-scanvi) below for the full
table. Under scANVI's own native classifier the mean gap narrows (73.15%
vs. "ours"'s native-centroid 79.79%) but the ±28.49-point range across
seeds (SD ≈12.3) means that comparison is far less trustworthy than the
shared-rule one; see [scANVI across seeds](#scanvi-across-seeds) below.
scANVI is the clear second-place method regardless of protocol. The three
genuinely unsupervised methods (MaxFuse, Harmony, scGLUE) all cluster in
the high-40s to low-50s% — indistinguishable from each other and from the
50.00% trivial
floor.

**For the record, since it materially changed once real data replaced the
reconstruction:** the earlier reconstruction-based table had scANVI's
shared-kNN-rule restricted balanced accuracy (77.26%) *ahead* of the
reconstruction's own shared-kNN-rule number (74.50%) — i.e., "ours" looked
like it was *behind* scANVI under that one specific protocol. That
reconstruction was computed through `service/pipeline` before the
`service/pipeline/encoder.py` ReLU/GELU fix (commit `056f136` — see
[bugs-and-fixes.md](bugs-and-fixes.md#0)), so every number it produced,
including this one, is invalid on its own terms, not just "distorted." On
the real embedding, "ours" leads scANVI under every protocol tested.

## Unrestricted regime (all 22 RNA classes as candidates)

Every RNA class competes for every prediction, even though only two classes
have any real protein ground truth. Much harder for every method.

| Rank | Method | Protocol | Accuracy % | Balanced accuracy % |
|---|---|---|---|---|
| 1 | **Ours** | shared kNN rule | 55.37 [53.42, 57.32]\* | **38.69** [37.17, 40.30]\* |
| 2 | **Ours** | native nearest-centroid | 45.37 [43.29, 47.45]\* | 31.08 [29.60, 32.51]\* |
| 3 | scANVI (3-seed mean) | native scANVI classifier | 18.01 (±19.26) | 12.92 (±15.04) |
| 4 | scANVI (3-seed mean) | shared kNN rule | 17.27 (±11.07) | 11.77 (±7.53) |
| 5 | PCA floor | shared kNN rule | 15.84 [14.09, 17.72]\* | 11.01 [9.79, 12.37]\* |
| 6 | scANVI (3-seed mean) | native nearest-centroid | 10.60 (±7.92) | 7.48 (±6.20) |
| 7 | MaxFuse | native nearest-centroid | 5.91 [4.76, 7.11]\* | 4.91 [3.84, 5.99]\* |
| 8 | Harmony | shared kNN rule | 7.11 [5.84, 8.32]\* | 4.84 [3.97, 5.66]\* |
| 9 | PCA floor | native nearest-centroid | 3.69 [2.82, 4.70]\* | 2.59 [1.96, 3.31]\* |
| 10 | Harmony | native nearest-centroid | 3.76 [2.89, 4.77]\* | 2.55 [1.96, 3.24]\* |
| 11 | MaxFuse | shared kNN rule | 1.07 [0.60, 1.61]\* | 0.81 [0.41, 1.25]\* |
| 12 | scGLUE | shared kNN rule | 0.47 [0.20, 0.87]\* | 0.40 [0.14, 0.76]\* |
| 13 | scGLUE | native nearest-centroid | 0.20 [0.00, 0.47]\* | 0.30 [0.00, 0.73]\* |

\* 95% bootstrap CI (single run). scANVI rows show 3-seed mean (±spread,
max−min across seeds 0/1/2) instead — see
[scANVI across seeds](#scanvi-across-seeds).

*(Majority-class floor omitted here: predicting "monocyte" scores the same
73.56%/50.00% regardless of candidate-class count, since it never varies
its prediction.)*

**Reading this table:** everyone, "ours" included, is far worse here than
in the restricted regime — full 22-way transfer from RNA to a genuinely
different measurement modality, at real SCoPE2 noise levels, is hard for
every method. "Ours" still leads by a wide margin under both protocols.

**Correcting an earlier claim in this document:** a previous version of
this table, using the (now-removed) reconstruction, observed that its
shared-kNN-rule unrestricted balanced accuracy (60.39%) was much higher
than its own native-nearest-centroid number (6.98%), and concluded this
showed "classifier choice matters more than embedding quality." **That
conclusion does not hold on the real embedding and should not have been
stated as generally as it was — and the reconstruction numbers it was based
on (60.39%, 6.98%, and every other reconstruction figure this document ever
cited) were computed through `service/pipeline` before the encoder's
ReLU/GELU fix (commit `056f136`), so they were never trustworthy evidence
about classifier choice, embedding quality, or anything else in the first
place.** Under the *same* native-nearest-centroid rule, the real embedding
scores 31.08% — more than 4× the reconstruction's (invalid) 6.98% on that
identical rule. The embedding itself — corrected for both the file-panel
issue and the ReLU bug — was the dominant source of the earlier gap, not
the choice of decision rule. (Classifier choice
still matters at the margins — "ours" shared-kNN unrestricted, 38.69%, is
higher than its own native-centroid unrestricted, 31.08% — but this is a
real, secondary effect on top of a correct embedding, not the primary
explanation for a large discrepancy.)

## scANVI across seeds

All 3 seeds (0, 1, 2) complete, same architecture and training budget
(200 pretrain epochs + 100 fine-tune epochs, early stopping) each time.

| Protocol | Regime | Seed 0 bal | Seed 1 bal | Seed 2 bal | Mean bal | Spread (max−min) |
|---|---|---|---|---|---|---|
| Shared kNN rule | restricted | 77.26 | 77.16 | 76.26 | **76.89** | **0.99** |
| Shared kNN rule | unrestricted | 15.24 | 7.71 | 12.35 | 11.77 | 7.53 |
| Native scANVI classifier | restricted | 57.89 | 75.18 | 86.37 | 73.15 | **28.49** |
| Native scANVI classifier | unrestricted | 12.86 | 5.43 | 20.47 | 12.92 | 15.04 |
| Native nearest-centroid | restricted | 50.70 | 65.20 | 77.36 | 64.42 | 26.66 |
| Native nearest-centroid | unrestricted | 4.79 | 6.66 | 10.99 | 7.48 | 6.20 |

(Accuracy figures, for completeness — shared kNN rule restricted:
69.53/70.47/72.01; native scANVI classifier restricted: 65.91/73.89/84.50;
native nearest-centroid restricted: 52.35/59.80/71.48.)

**Reading this table — and answering the question this whole investigation
started with:**

- **Under the shared kNN rule — the one apples-to-apples protocol applied
  identically to every method — scANVI is remarkably *stable* across seeds
  (76.26–77.26%, a spread of under 1 point) and "ours" (88.40%) leads its
  3-seed mean (76.89%) by 11.5 points, with zero overlap across any seed.
  This comparison is solid.**
- Under scANVI's *own* native classifier, the picture is far noisier: a
  28.5-point spread across 3 seeds (57.89% to 86.37%). Seed 2's native
  classifier (86.37%) actually *exceeds* "ours"'s native-nearest-centroid
  number (79.79%) — though it's still below "ours"'s shared-kNN number
  (88.40%). Averaged across seeds (73.15%), scANVI's own classifier trails
  "ours" by a smaller, noisier margin than the shared-rule comparison
  shows.
- The honest summary: **"ours" leads scANVI clearly and robustly under the
  one rule that's actually comparable across methods. Under scANVI's own
  best-case, best-seed native protocol, the gap narrows and in one seed
  nearly closes against "ours"'s own native protocol** — but that
  observation is itself evidence of how unstable scANVI's own native
  training is here, not evidence the two methods are close in general.

Context: the shipped reference ("ours") is one trained model, not an
ensemble — its bootstrap CI reflects sampling uncertainty in the 1,490-cell
SCoPE2 query, not training variance. For scale on training variance
specifically: the production reference's own 5-seed training run
(`service/model/v3_tables/reference_seeds.csv`) measured mean balanced
accuracy 0.7143 on its own (RNA-only) validation task — a different task
and dataset than this benchmark's protein-transfer scoring, not directly
comparable to any number above, but useful context for how much a *trained
model's own seed* typically moves a number in this project (that task's
own spread is far smaller than scANVI's 28.5-point native-classifier
spread here).

## Paired bootstrap: ours minus scANVI

The tables above compare two *independent* 95% CIs and note whether they
overlap. A **paired** bootstrap is the statistically correct way to compare
two methods scored on the identical query set: the same resampled cell
indices are applied to *both* methods in every one of 2,000 resamples, and
the balanced-accuracy difference is computed per resample, directly giving
a CI on the difference itself.

| scANVI seed | Regime | Δ balanced accuracy (ours − scANVI), pts | 95% CI |
|---|---|---|---|
| 0 | restricted | +11.14 | [+9.10, +13.22] |
| 1 | restricted | +11.24 | [+9.14, +13.35] |
| 2 | restricted | +12.14 | [+9.88, +14.43] |
| 0 | unrestricted | +23.46 | [+21.72, +25.23] |
| 1 | unrestricted | +30.98 | [+29.27, +32.71] |
| 2 | unrestricted | +26.34 | [+24.50, +28.11] |

**Every single seed, both regimes: the 95% CI on the difference excludes
zero, and by a wide margin.** This is the most rigorous statement this
document can make about "ours vs. scANVI, shared kNN rule": the lead is
real, positive, and consistent across all 3 independently-trained scANVI
models, not an artifact of comparing two possibly-overlapping independent
intervals.

(scANVI's spread figures elsewhere in this document — e.g. "±0.99" for the
shared-rule restricted regime — are the **range** (max−min) across the 3
seed values, not standard deviation. For that same regime, SD is ≈0.55
(sample, ddof=1) or ≈0.45 (population, ddof=0); for the shared-rule
unrestricted regime, range is 7.53 and SD is ≈3.80/≈3.10. Range is reported
as the primary figure throughout this document because n=3 is too small
for SD to be a very meaningful summary on its own, but both are given here
for precision.)

## Pool-first kNN: what the product would actually deliver

Every kNN number elsewhere in this document uses **post-hoc masking**: fit
one kNN classifier on all 22 RNA classes, then restrict the *output*
probability columns to `{macrophage, monocyte}` before taking the argmax.
This is a clean, method-agnostic evaluation rule, but it is **not** what
`service/pipeline/assignment.py`'s real `method="knn"` option actually
does in production. The real code (`_assign_knn`) restricts the *candidate
pool* of RNA cells to the supported classes **before** running the
nearest-neighbour search — a structurally different algorithm, not just a
different bookkeeping step. `pool_first_knn_predict` in
`tools/fair_benchmark/evaluate.py` mirrors `_assign_knn` exactly (same
`chunked_topk` helper, same pool-restriction-then-vote logic), so this
table shows what the product would actually deliver if `ASSIGNMENT_METHOD`
were set to `"knn"` — distinct from `nearest_centroid`, the method
currently configured as the shipped default.

| Method | Post-hoc masking bal. acc. % | Pool-first (real) bal. acc. % | Δ |
|---|---|---|---|
| **Ours** | 88.40 [86.85, 89.92] | 77.50 [74.92, 80.02] | −10.9 |
| scANVI (seed 0) | 77.26 [75.37, 79.15] | 49.85 [48.09, 51.71] | −27.4 |
| scANVI (seed 1) | 77.16 [75.24, 79.14] | 61.99 [59.55, 64.45] | −15.2 |
| scANVI (seed 2) | 76.26 [73.96, 78.54] | 67.66 [65.27, 70.28] | −8.6 |
| PCA floor | 57.66 [55.04, 60.37] | 53.37 [51.23, 55.65] | −4.3 |
| Harmony | 50.49 [47.70, 53.38] | 52.86 [50.46, 55.30] | +2.4 |
| MaxFuse | 50.05 [48.49, 51.63] | 50.00 [50.00, 50.00] | −0.1 |
| scGLUE | 48.21 [46.52, 49.78] | 49.80 [48.09, 51.55] | +1.6 |

**Reading this table:** pool-first restriction costs a large amount of
balanced accuracy for the embeddings that actually carry real cell-type
signal ("ours": −10.9 points; scANVI: −8.6 to −27.4 points, itself highly
seed-dependent), and costs essentially nothing for the near-chance
embeddings (MaxFuse, scGLUE — restricting the pool barely matters when the
full-pool search was already close to random). This makes sense
mechanically: if a query cell's true nearest neighbours in a *good*
embedding happen to be an easy, well-separated set that includes some
non-restricted-class cells, post-hoc masking still benefits from finding
those genuinely close neighbours first and only tallying the restricted
subset among them; pool-first forces the search into a smaller,
sometimes-worse-matching subset from the start. **"Ours" still clearly
leads every pool-first scANVI number (77.50% vs. 49.85–67.66%)**, but
77.50% pool-first is a real, disclosed drop from the 88.40% the post-hoc
evaluation rule reports — worth knowing before assuming the live service's
actual kNN option (if ever selected over the current `nearest_centroid`
default) would deliver the higher number.

## Two protocols, not a chosen one

Per the repository owner's explicit instruction: the choice between the
shared kNN-classifier rule and native nearest-centroid is **not** made
based on which one favors "ours" on this SCoPE2 evaluation set — doing so
would be tuning a product decision on the test set. Both are reported for
every method, in both tables above, and no recommendation is made here
about which one the live service should use. The same non-tuning
discipline applies to the pool-first-vs-post-hoc-masking kNN choice above.

## What's still open

- No baseline besides scANVI has been run more than once; MaxFuse's random
  batching and scGLUE's minibatch shuffling both have their own
  un-quantified run-to-run variance (see
  [known-limitations.md](known-limitations.md)).
- `Atlas/atlas_manifest.json`'s `benchmark.rows` is untouched — still `[]`,
  `status: "pending"` — regardless of everything above. Nothing here is
  wired into the live site.
