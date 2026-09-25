# VivOME Prototype, Build Context

Everything needed to build the projection service prototype and repoint the
atlas site at the current model. Methodology that does not affect the build is
left out.

Read alongside `download-checklist.md`, which says which files to fetch, and
the repo's existing `docs/projection-service.md`, whose response contract is
still correct and does not need changing.

Every number here was measured. Sources are the v3 export, the v3 tables, and
a verified run of `VivOME_Prototype_Export.ipynb` on 2026-09-22.

---

## 1. What the product is

A user uploads an expression matrix, features in rows, cells in columns. The
service places those cells into a shared 128 dimensional latent space built
from RNA, and returns coordinates, a calibrated label set, a confidence, and
an explicit abstention when the cell falls outside what the atlas has evidence
for.

The reference is frozen. Nothing about an upload retrains anything. This was
an open question until recently, four different adaptation mechanisms were
tried and all four failed, so `encode(values, mask) -> embedding` stays a
single forward pass, milliseconds, synchronous. The submit and poll API shape
that was being considered is not needed.

---

## 2. Serving constants

All in `provenance.json`. Read them from the file, do not copy them into code,
because the file is the thing that gets versioned.

| Key | Value | Meaning |
|---|---|---|
| `n_shared_genes` | 9002 | Feature space size |
| `n_classes` | 22 | Reference classes |
| `latent_dim` | 128 | Embedding width |
| `n_modules` | 501 | Module pooling groups |
| `mask_convention` | `1.0 observed, 0.0 missing` | Both arrays go into the model, values and mask |
| `abstain_threshold` | 0.9779 | Below this, abstain |
| `conformal_alpha` | 0.10 | 90 percent target coverage |
| `ot_eps`, `ot_tau` | 0.05, 0.10 | Optimal transport parameters, if OT is used at all, see section 6 |
| `production_seed` | 0 | Which of five seeds shipped |
| `gene_list_hash` | `5751dd1e569f` | Guard against a mismatched feature space |

The encoder is module pooling with an explicit mask channel. Input is values
concatenated with the binary mask, plus module pooled means and per module
coverage. It will not accept values alone.

---

## 3. The single most important serving decision

**Constrain label assignment to the classes that have cross modal support.**

Only 2 of the 22 reference classes have any proteomics cells anywhere in the
project, macrophage with 394 and monocyte with 1,096. The other 20 are RNA
only. Letting all 22 compete for the argmax means 20 classes with zero protein
evidence can win, and they frequently do.

Measured on real SCoPE2 data, same frozen encoder, same embeddings, the only
change being which classes are candidates:

| Regime | Accuracy | Balanced accuracy | Candidates |
|---|---|---|---|
| Unrestricted, all 22 classes | 45.37 | 31.08 | 22 |
| Restricted to supported classes | 86.17 | 79.79 | 2 |
| Restricted, threshold tuned on the margin | not applicable | 85.97 | 2 |

Macrophage versus monocyte AUC is 0.9278, and the best margin threshold sits
at −0.1586.

Three caveats, all of which must survive into whatever the site says:

The restricted regime is a two class problem, so its chance level is 50
percent, not the 4.5 percent that applies across 22 classes. The two rows are
not directly comparable, and 79.79 percent balanced accuracy is the honest
reading against a 50 percent baseline.

The tuned threshold row picked its threshold using true labels. It is an upper
bound on what a perfectly calibrated service could reach, not something
achievable on an unlabelled upload. The label free number is 79.79.

Both restricted rows describe performance on cells that genuinely are
macrophages or monocytes. They say nothing about a cell of some other type
arriving, which is what abstention handles.

With those caveats stated, the conclusion holds. A change in the candidate set
alone moves balanced accuracy by 48.7 points. Most of what the unrestricted
number reads as a modality gap is distractor contamination.

One consequence for the model card. The four failed self adaptation
experiments, and the cell line versus primary comparison, were all measured
under the unrestricted 22 class regime. They should not be quoted as ceilings
for the restricted serving configuration, because they did not measure it.

---

## 4. Abstention and the coverage floor

Abstention is not a disclaimer bolted onto a weak result, it is the behaviour
the data calls for. At the calibrated threshold of 0.9779, 80.2 percent of
real SCoPE2 cells abstain. A prototype that returned a confident label for
every uploaded cell would be wrong.

Score out of distribution risk by maximum cosine similarity to any single
reference cell. This requires `reference_embedding.npy` at serve time, all
85,233 rows, not just the centroids.

Coverage floor: below roughly 15 to 20 percent feature coverage, results stop
being trustworthy in a way confidence scores do not catch. Accuracy at 10
percent coverage came out non monotone, higher than at 20 and 30 percent,
which is the signature of mostly zero input producing an arbitrary answer. An
explicit low coverage refusal is more honest than a confidence number computed
from noise. Real datasets measured 32.3, 26.5 and 18.4 percent. A dataset
reporting 90 percent coverage is the surprising case, not 20.

`abstain_reason` should distinguish at least three cases: outside any
supported region, coverage too low to project at all, and ambiguous between
classes.

---

## 5. Measured constraints that look like mistakes

Each of these is the less obvious option, and each was measured. They are
listed because a reasonable engineer will otherwise revert them.

**Z score each uploaded dataset independently**, using only its own mean and
standard deviation, over only the genes it actually measured. Do not reuse any
statistic from RNA training. The two modalities are on unrelated scales.

**Keep the full 9,002 gene space and zero fill what is missing.** Restricting
to only well covered genes costs 0.005 AUC. A random subset of the same size
costs 0.098. Zero fill beat gaussian noise and hot deck imputation in every
test.

**Do not add distribution matching as preprocessing.** Matching skew and
kurtosis between proteomics and RNA was tried. Every transform that moved the
distribution closer to RNA made transfer worse, and the correlation between
closing that gap and losing accuracy was strongly positive.

**Calibrate conformal prediction on a random subset of the query, never a
confidence filtered one.** Confidence filtering violates exchangeability.
Filtering gave 36.2 percent empirical coverage against a 90 percent target. A
random subset recovered 70 percent. This bug has already been found and fixed
once, so treat any instinct to select good calibration examples as the bug
reappearing.

**Score abstention by maximum cosine to any single reference cell, not by vote
share among nearest neighbours.** Vote share reached AUC 0.974 on one held out
class but scored below chance, 0.345 and 0.239, on two others, meaning unseen
cells read as more confident than seen ones. Maximum cosine scored 1.000
across every held out class tested.

**If unbalanced optimal transport is used, keep the marginal constraint
relaxed.** Enforcing strict marginals collapsed accuracy from 72 to 47 percent
and dropped neutrophil recall from 100 to 55.9 percent. Permissiveness here is
a validated finding, not an oversight.

---

## 6. One thing still unresolved

Which label assignment method to use within the supported set. Do not hardcode
one.

Earlier RNA to RNA tests found optimal transport beating k nearest neighbour
by 14.46 points, and an older brief accordingly told builders to use OT and
warned that kNN loses. On real protein data that inverted, twice.

| Test | Nearest centroid | OT relaxed | kNN |
|---|---|---|---|
| v3, real SCoPE2, frozen embedding | 45.4 | 33.6 | not run |
| Self training pilot, adapted embedding | 38.3 | 33.8 | 40.4 |

Both cross modal measurements have OT losing. The likely reason is that OT
helps when queries are noisy but centred correctly, and here they are
systematically displaced, which is a different problem.

Make the assignment method a configuration value with all three implemented.
Nearest centroid over the supported set is the reasonable default on current
evidence. Note that both rows above were measured unrestricted, so the
comparison should be rerun inside the restricted regime before it is treated
as settled.

---

## 7. Hierarchical fallback

Six pairs of cell types were confirmed as genuine biological continua across
independent tests, not modelling failures:

1. macrophage, monocyte
2. naive thymus-derived cd4-positive, alpha-beta t cell and cd4-positive, alpha-beta t cell
3. cd8-positive, alpha-beta t cell and natural killer cell
4. mature nk t cell and cd8-positive, alpha-beta t cell
5. natural killer cell and cd8-positive, alpha-beta t cell
6. intermediate monocyte and classical monocyte

When a conformal set falls entirely inside one of these pairs, returning the
broader shared category is more honest than picking one side, and more useful
than an empty set. This is distinct from abstention, the model has real
partial information and simply cannot resolve the last step.

---

## 8. Alignment diagnostics, now measured

Two metrics moved out of `pending` with the latest run.

**Modality probe, 98.99 percent balanced accuracy**, standard deviation 0.28
across 5 folds, logistic regression on the 128 dimensional latent with RNA
subsampled to the protein count so the number is not an artefact of a 57 to 1
imbalance. Fifty percent would mean the modalities are indistinguishable. At
99 percent they are almost perfectly separable, which means the
representations stay modality specific even where same type cells point in
similar directions. The old build scored 98.7 percent, so this property
survived the architecture change intact.

**Latent centroid cosine**, measured for the 2 classes with cross modal
coverage, explicitly pending for the other 20.

| Class | Protein cells | Cosine |
|---|---|---|
| monocyte | 1,096 | 0.830 |
| macrophage | 394 | 0.190 |

A trap worth naming. The site already has a metric called
`pca_centroid_cosine`, computed in the 3 component projection, and the older
explainability work reported figures above 0.98. That is a different quantity
from the table above, which is the full 128 dimensional latent on the frozen
RNA only reference. The flattering number is the less meaningful one. Label
the two distinctly in any panel, and do not let a reader assume the 0.98 style
figure describes latent space alignment.

Macrophage at 0.190 is also the quantitative form of the problem section 3
describes. Monocyte sits near its RNA centroid, macrophage does not.

---

## 9. What must still render as pending

The repo's rule holds, no page displays a number that was not computed from
data in the repository.

| Metric | Blocked on |
|---|---|
| `benchmark.rows` | No comparison against GLUE, MaxFuse, scArches, Seurat bridge or Harmony has been run. None. |
| Label stability across versions | Needs a predecessor release to compare against |
| `latent_centroid_cosine` for 20 of 22 classes | No cross modal coverage exists for them. This is the correct record, not a gap to fill. |

`modality_probe_accuracy`, `latent_centroid_cosine` for the supported pair,
`model.seeds` and `transfer_accuracy` can all now be measured records.

---

## 10. The site currently serves a superseded model

`versions.html` describes `CrossModalNet`, a single run, trained jointly on
RNA and proteomics together on a 2,903 gene space. The current model is a
frozen RNA only reference on a 9,002 gene space, with the query side handled
separately at inference.

This is a structural change, not a metric refresh, and the model card should
say so. The old jointly trained model had implicitly seen SCoPE2 during
training, which is part of why its numbers looked better. Both are real, they
answer different questions, and the card should state which is being reported
and why the newer, lower number is the trustworthy one.

The 3D viewer data also comes from the old build. Replacements are in
`app_export/`. The three component projection captures 69.7 percent of latent
variance, 38.05, 19.12 and 12.55 per component. Every new dataset must be
projected through the saved `pca3_projection.npz` rather than its own PCA, or
the viewer plots coordinates from different spaces on the same axes.

---

## 11. Two failure modes already hit once

Recorded because both cost real time and both look plausible on the way in.

**Calibrating against the wrong condition.** An abstention threshold was first
calibrated on full coverage RNA self scores, giving 1.0000, which abstained on
100 percent of real cells regardless of correctness. Recalibrating against RNA
masked to each dataset's real coverage gave 0.9779 and a sensible 80.2 percent
rate. Any threshold must be calibrated under the conditions it will be applied
in.

**A cache path that silently never engages.** Checkpoint resumption was added
to avoid retraining after a Colab disconnect, then did not fire on either
subsequent run, costing a full retrain each time, because nothing verified the
path existed. If the prototype caches anything, assert the cache was actually
read, do not assume it.
