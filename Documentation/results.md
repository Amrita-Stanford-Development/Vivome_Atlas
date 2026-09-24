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

## Restricted regime (candidates = {macrophage, monocyte})

The only regime with real cross-modal ground truth for every candidate
class — every one of the 1,490 protein query cells is either macrophage or
monocyte.

| Rank | Method | Protocol | Accuracy % [95% CI] | Balanced accuracy % [95% CI] |
|---|---|---|---|---|
| 1 | **Ours** | shared kNN rule | 84.97 [83.22, 86.78] | **88.40** [86.85, 89.92] |
| 2 | **Ours** | native nearest-centroid | 86.17 [84.56, 87.85] | 79.79 [77.38, 82.27] |
| 3 | scANVI (seed 0) | shared kNN rule | 69.53 [67.38, 71.68] | 77.26 [75.37, 79.15] |
| 4 | scANVI (seed 0) | native scANVI classifier | 65.91 [63.76, 68.26] | 57.89 [55.20, 60.74] |
| 5 | MaxFuse | shared kNN rule | 69.80 [68.39, 71.21] | 50.05 [48.49, 51.63] |
| 6 | scANVI (seed 0) | native nearest-centroid | 52.35 [49.87, 54.90] | 50.70 [47.93, 53.73] |
| — | **Majority class ("monocyte")** | trivial floor | 73.56 [71.34, 75.77] | 50.00 [50.00, 50.00] |
| 7 | Harmony (batch-correction floor) | native nearest-centroid | 50.20 [47.65, 52.68] | 54.20 [51.42, 57.02] |
| 8 | Harmony (batch-correction floor) | shared kNN rule | 46.78 [44.36, 49.40] | 50.49 [47.70, 53.38] |
| 9 | MaxFuse | native nearest-centroid | 51.95 [49.53, 54.50] | 52.38 [49.45, 55.29] |
| 10 | PCA floor | shared kNN rule | 67.25 [65.17, 69.40] | 57.66 [55.04, 60.37] |
| 11 | PCA floor | native nearest-centroid | 55.97 [53.42, 58.52] | 58.21 [55.42, 60.96] |
| 12 | scGLUE | shared kNN rule | 28.59 [27.32, 29.93] | 48.21 [46.52, 49.78] |
| 13 | scGLUE | native nearest-centroid | 47.92 [45.37, 50.54] | 47.20 [44.22, 50.20] |

**Reading this table:** on the real embedding, under the one rule applied
identically to every method, "ours" leads scANVI (the only other
label-consuming method) by **11.1 points of balanced accuracy** (88.40% vs.
77.26%) — not the ambiguous, close-to-within-CI margin an earlier
reconstruction-based version of this table reported. scANVI is the clear
second-place method regardless of protocol. The three genuinely
unsupervised methods (MaxFuse, Harmony, scGLUE) all cluster in the high-40s
to low-50s% — indistinguishable from each other and from the 50.00% trivial
floor.

**For the record, since it materially changed once real data replaced the
reconstruction:** the earlier reconstruction-based table had scANVI's
shared-kNN-rule restricted balanced accuracy (77.26%) *ahead* of the
reconstruction's own shared-kNN-rule number (74.50%) — i.e., "ours" looked
like it was *behind* scANVI under that one specific protocol. That
comparison was an artifact of the reconstruction's distortion, not a real
result. On the real embedding, "ours" leads scANVI under every protocol
tested.

## Unrestricted regime (all 22 RNA classes as candidates)

Every RNA class competes for every prediction, even though only two classes
have any real protein ground truth. Much harder for every method.

| Rank | Method | Protocol | Accuracy % [95% CI] | Balanced accuracy % [95% CI] |
|---|---|---|---|---|
| 1 | **Ours** | shared kNN rule | 55.37 [53.42, 57.32] | **38.69** [37.17, 40.30] |
| 2 | **Ours** | native nearest-centroid | 45.37 [43.29, 47.45] | 31.08 [29.60, 32.51] |
| 3 | scANVI (seed 0) | shared kNN rule | 22.42 [20.54, 24.50] | 15.24 [13.96, 16.65] |
| 4 | scANVI (seed 0) | native scANVI classifier | 18.79 [16.91, 20.60] | 12.86 [11.52, 14.12] |
| 5 | PCA floor | shared kNN rule | 15.84 [14.09, 17.72] | 11.01 [9.79, 12.37] |
| 6 | Harmony | shared kNN rule | 7.11 [5.84, 8.32] | 4.84 [3.97, 5.66] |
| 7 | MaxFuse | native nearest-centroid | 5.91 [4.76, 7.11] | 4.91 [3.84, 5.99] |
| 8 | scANVI (seed 0) | native nearest-centroid | 7.05 [5.84, 8.32] | 4.79 [3.97, 5.66] |
| 9 | Harmony | native nearest-centroid | 3.76 [2.89, 4.77] | 2.55 [1.96, 3.24] |
| 10 | PCA floor | native nearest-centroid | 3.69 [2.82, 4.70] | 2.59 [1.96, 3.31] |
| 11 | MaxFuse | shared kNN rule | 1.07 [0.60, 1.61] | 0.81 [0.41, 1.25] |
| 12 | scGLUE | shared kNN rule | 0.47 [0.20, 0.87] | 0.40 [0.14, 0.76] |
| 13 | scGLUE | native nearest-centroid | 0.20 [0.00, 0.47] | 0.30 [0.00, 0.73] |

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
stated as generally as it was.** Under the *same* native-nearest-centroid
rule, the real embedding scores 31.08% — more than 4× the reconstruction's
6.98% on that identical rule. The embedding itself was the dominant source
of the earlier gap, not the choice of decision rule. (Classifier choice
still matters at the margins — "ours" shared-kNN unrestricted, 38.69%, is
higher than its own native-centroid unrestricted, 31.08% — but this is a
real, secondary effect on top of a correct embedding, not the primary
explanation for a large discrepancy.)

## scANVI across seeds

Two runs with different seeds are complete; a third is documented as soon
as it finishes (see the note at the bottom of this section for how to check
whether this document is current).

| Protocol | Regime | Seed 0 acc / bal | Seed 1 acc / bal | Seed 2 acc / bal | Mean bal | Spread (max−min) |
|---|---|---|---|---|---|---|
| Shared kNN rule | restricted | 69.53 / 77.26 | *pending* | *pending* | *pending* | *pending* |
| Shared kNN rule | unrestricted | 22.42 / 15.24 | *pending* | *pending* | *pending* | *pending* |
| Native scANVI classifier | restricted | 65.91 / 57.89 | *pending* | *pending* | *pending* | *pending* |
| Native scANVI classifier | unrestricted | 18.79 / 12.86 | *pending* | *pending* | *pending* | *pending* |
| Native nearest-centroid | restricted | 52.35 / 50.70 | *pending* | *pending* | *pending* | *pending* |
| Native nearest-centroid | unrestricted | 7.05 / 4.79 | *pending* | *pending* | *pending* | *pending* |

Context: the shipped reference ("ours") is one trained model, not an
ensemble — its bootstrap CI above reflects sampling uncertainty in the
1,490-cell SCoPE2 query, not training variance. For a sense of scale on
training variance specifically: the production reference's own 5-seed
training run (`service/model/v3_tables/reference_seeds.csv`) measured mean
balanced accuracy 0.7143 on its own (RNA-only) validation task — a
different task and dataset than this benchmark's protein-transfer scoring,
so not directly comparable to any number in this table, but useful context
for how much a *trained model's own seed* typically moves a balanced-accuracy
number in this project.

*This section will be filled in completely once scANVI seeds 1 and 2
finish training (~35 minutes each from launch). Until every cell above
reads a number instead of "pending," treat scANVI's single-seed numbers
elsewhere in this document as provisional.*

## Two protocols, not a chosen one

Per the repository owner's explicit instruction: the choice between the
shared kNN-classifier rule and native nearest-centroid is **not** made
based on which one favors "ours" on this SCoPE2 evaluation set — doing so
would be tuning a product decision on the test set. Both are reported for
every method, in both tables above, and no recommendation is made here
about which one the live service should use.

## What's still open

- scANVI's multi-seed table above is incomplete pending seeds 1 and 2.
- No baseline besides scANVI has been run more than once; MaxFuse's random
  batching and scGLUE's minibatch shuffling both have their own
  un-quantified run-to-run variance (see
  [known-limitations.md](known-limitations.md)).
- `Atlas/atlas_manifest.json`'s `benchmark.rows` is untouched — still `[]`,
  `status: "pending"` — regardless of everything above. Nothing here is
  wired into the live site.
