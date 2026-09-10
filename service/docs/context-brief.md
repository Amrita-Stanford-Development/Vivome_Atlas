# Context for Building the Projection Service

This is the brief a local coding agent needs before touching Phase 5. Every
choice below came from a specific measured failure, not from a default or a
best practice guess. The most important job of this document is to stop a
well meaning agent from quietly reverting one of these choices back to the
more obvious seeming alternative, since several of the correct answers here
are the less obvious option.

The contract in `docs/projection-service.md` is already correct and does not
need to change. This document explains how to actually satisfy it.

---

## The shape of the pipeline

```
uploaded matrix
      |
align to the 9,002 gene feature space, build an observed mask
      |
fuzzy smooth the query, using the query's own full feature set
      |
embed through the frozen reference encoder, values plus mask
      |
assign labels, unbalanced optimal transport onto reference centroids
      |
calibrate a conformal set, on a random held out slice
      |
score abstention, max cosine similarity to any reference cell
      |
transfer continuous properties, k nearest neighbour weighted mean
      |
response: coordinates, label_set, confidence, abstained, matched/unmatched counts
```

Every stage below maps to one box in that diagram.

---

## Stage 1, query alignment

Take the uploaded matrix, reindex to `feature_space_genes.csv`, in that exact
order. Genes present get their values, genes absent get zero. Build a second
array the same shape, one where present, zero where absent. Both arrays go
into the model, not just the values.

**Z score per dataset, independently.** Do not reuse any statistic from RNA
training. Every dataset in this project, SCoPE2, PBMC240, Fulcher, was
z scored using its own mean and standard deviation, computed only from the
genes it actually measured. Applying RNA's z score parameters to a new
proteomics dataset would be wrong, since the two are on completely different
scales to begin with.

**Coverage will be low, and that is normal, not a bug to fix.** Measured
values against the 9,002 gene space: SCoPE2 32.3 percent, PBMC240 34.8
percent, Fulcher 18.4 percent. If a dataset comes back reporting 90 percent
coverage, that is the surprising result, not 20 percent.

**Do not filter the feature space down to only well covered genes.** This was
tried directly. Restricting SCoPE2 to only the genes it actually has costs
0.005 AUC against using the full space with the rest zero filled. A random
subset of the same size costs 0.098. The full space with zero fill is
correct, confirmed against three fill strategies, gaussian noise and hot deck
imputation were both worse than zero fill in every test run.

---

## Stage 2, fuzzy smoothing

Before the query touches the encoder, build a nearest neighbour graph within
the query dataset using its own complete feature set, not just the 9,002
shared genes, then smooth the shared feature values along that graph. This
is the MaxFuse idea, denoise the weakly linked shared features using the
richer within modality structure. It gave a measured plus 0.026 AUC on
SCoPE2, and the improvement was monotone across every setting tried.

This step is independent of which encoder architecture won the masking
comparison. Keep it regardless.

---

## Stage 3, the reference encoder

Which exact architecture to instantiate here is written in
`decisive_summary.json` once the five seed test finishes. Do not hardcode a
choice, read the config from that file.

What is settled regardless of which variant won:

**Masking during training is not optional.** An encoder trained without it
collapses to 44.9 percent balanced accuracy at 10 percent coverage, against
62 to 72 percent for every masked variant tested. Whatever ships, it was
trained with an explicit mask channel, values concatenated with a binary
present indicator, not values alone with missing entries silently zeroed.

**Uniform random masking during training beat masking that mimics real
detection patterns, twice, in two separate comparisons.** This was
counterintuitive going in. Do not swap in a smarter sampler later without
re running the comparison, since the more sophisticated option lost both
times.

**Drop any augmentation that changes the input distribution's shape.** An
earlier version tried matching skew and kurtosis between proteomics and RNA.
Every transform that moved the distribution closer to RNA's shape made
transfer worse, not better, and the correlation between closing that gap and
losing accuracy was strongly positive. Do not reintroduce distribution
matching as a preprocessing step.

---

## Stage 4, label assignment

**Use unbalanced optimal transport, at a relaxed marginal setting, not
nearest neighbour voting.** This beat kNN by 14.46 points of balanced
accuracy in a controlled RNA against RNA test, and separately gave the best
AUC on real SCoPE2 data. kNN is not a safe fallback default here, it
measurably loses.

**The marginal constraint must stay relaxed. Do not tighten it.** This is the
single most important warning in this document, since it was gotten wrong
once already in this project. Enforcing strict marginals, forcing transport
mass to spread evenly across all reference classes, collapsed SCoPE2 accuracy
from 72 to 47 percent and dropped neutrophil recall from 100 to 55.9 percent
in the RNA test. The reference has far more classes than most queries will
ever contain evidence for, so the constraint that seems like it should
improve calibration actively destroys the result. If a future engineer
reads the optimal transport code and thinks the marginal weight looks
suspiciously permissive, that permissiveness is a validated finding, not
an oversight.

Reasonable starting parameters, confirmed working across two independent
datasets: entropic regularisation epsilon around 0.05, marginal relaxation
tau in the range that behaves like 0.1 rather than anything above 10.

---

## Stage 5, conformal calibration

**Calibrate on a random subset of the query, not a confidence filtered
one.** This is the second thing that was gotten wrong once already.
Calibrating only on the query's most confident cells gave 36.2 percent
empirical coverage against a 90 percent target, because confidence filtering
violates the exchangeability assumption conformal prediction depends on.
Switching to a random subset, still using the model's own predictions as the
calibration labels since no ground truth exists for a new upload, recovered
70 percent coverage, and calibrating against true labels in a controlled
test reached 92.3 percent, close to nominal.

If there is any temptation to select "good" calibration examples to make the
guarantee look tighter, that temptation is exactly the bug that was already
found and fixed once.

---

## Stage 6, abstention

**Score out of distribution risk by maximum cosine similarity to any single
reference cell, not by the normalised vote share among nearest neighbours.**
The vote share approach reached an AUC of 0.974 detecting an unseen
neutrophil population but scored below chance, 0.345 and 0.239, on
erythrocyte and classical monocyte, meaning unseen cells looked more
confident than seen ones. Maximum cosine similarity scored a perfect 1.000
across every held out class type tested. The failure mode of vote share is
that a query cell can sit far from the entire reference and still produce a
sharply peaked distribution over whichever few neighbours happen to be
nearest, which reads as high confidence when it should read as low.

`abstained: true` should fire when this score falls below whatever threshold
calibration settles on, and the `abstain_reason` field should be able to
distinguish at minimum: falls outside any supported region, coverage too low
to trust the projection at all, and ambiguous between two or more classes,
which is a different situation from being outside the reference entirely.

**Below roughly 15 to 20 percent feature coverage, results stop being
trustworthy in a way that a simple confidence score will not catch.**
Accuracy at 10 percent coverage was non monotone across variants in one
comparison, higher than at 20 and 30 percent, which is the signature of an
input that is mostly zeros producing an arbitrary rather than a meaningful
answer. Consider an explicit coverage floor, below which the service returns
an honest low coverage refusal rather than a confidence score computed from
noise.

---

## Stage 7, hierarchical fallback

Six specific pairs of adjacent cell types were found to be genuinely
confusable across independent tests, not as an artefact of any one dataset:
macrophage and monocyte, naive CD4 T cell and CD4 T cell more broadly, CD8
positive T cell and natural killer cell, mature NK T cell and CD8 T cell,
natural killer cell and CD8 T cell, intermediate monocyte and classical
monocyte. Every one of these reflects a real biological continuum rather
than a modelling failure.

When a conformal set's members fall entirely within one of these known pairs,
returning the broader shared category is more honest than returning either
specific label, and more useful than an empty set. This is different from
generic abstention, since the model has genuine partial information here, it
simply cannot resolve the last step.

---

## Stage 8, property transfer

Continuous properties, cell cycle scores, pathway activity, transfer by
similarity weighted averaging over the k nearest reference neighbours in
embedding space, computed on RNA's full transcriptome rather than only the
9,002 gene feature space, since the reference side is not limited by what
proteomics can measure.

**Only ship properties that pass validation, do not ship all of them with a
caveat.** In the one validation run performed, 4 of 8 candidate properties
passed a correlation threshold of 0.5 against true values in a held out RNA
test, ribosome content and antigen presentation scoring well, interferon
response and cell cycle scoring poorly. Report a per property reliability
number if there is room in the response schema, rather than a single global
disclaimer.

Report an uncertainty alongside every transferred value, the weighted spread
across the contributing neighbours, not just the point estimate. A value
averaged from neighbours that disagree sharply is a different claim than one
averaged from neighbours that agree, and the response should be able to
represent that difference.

---

## What is genuinely still open, do not assume an answer

**Which exact encoder architecture is production.** Waiting on
`decisive_summary.json`.

**Whether the sorted PBMC dataset from O'Connor et al will ever be
available.** That paper has no data availability statement as published, an
email has gone out asking, and it remains the only proteomics data in this
project with experimentally sorted rather than inferred or RNA transferred
labels. Nothing about the pipeline should assume it will arrive.

**Benchmark comparisons against GLUE, MaxFuse, Seurat, or scArches.** None
have been run. `benchmark.rows` is correctly pending and should stay that
way until they are.

**Whether the reference should eventually widen beyond blood.** Tissue
resident macrophages differ enough by organ, Kupffer cells against alveolar
macrophages against blood macrophages, that naively pooling organs under one
label would likely make the reference worse, not better, for the classes
that already struggle. Any multi organ expansion needs organ specific labels
retained, not merged.

---

## For the model card in `versions.html`

The current card describes `CrossModalNet`, a single run, jointly trained on
RNA and proteomics together. The actual architecture now in use is a frozen
RNA only reference with a separately trained query encoder, which is a
structural difference worth stating plainly rather than treating as a metric
update. The old jointly trained model had implicitly seen SCoPE2 during
training, which is part of why its zero shot numbers looked better than the
honestly separated reference architecture's do. Both numbers are real, they
answer different questions, and the model card should say which one is being
reported and why the newer, lower number is the trustworthy one.
