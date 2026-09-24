# Methodology

## The problem with the first comparison

An earlier version of this benchmark scored the shipped, frozen v3 reference
encoder ("ours") with full access to RNA cell-type labels, against MaxFuse,
Harmony, scArches (vanilla trVAE), and scGLUE — each of which ran
*unsupervised*, on a 15,000-cell stratified subsample of the RNA reference
(instead of the full 85,232 cells), scored by a nearest-centroid rule built
around "ours"'s own methodology rather than each method's native protocol.

The repository owner's verdict: *"It compares a method that was given RNA
labels against methods that were given none, so it measures label access and
effort, not method quality."*

## The nine rules (verbatim intent, lightly paraphrased)

1. **No proteomics labels anywhere, in any arm, except once, at the end, to
   score.** This is the project's core claim and is non-negotiable.
2. **Every method gets the full 85,232-cell RNA reference and RNA labels.**
   No subsampling for some arms and not others. If compute genuinely forces
   a subsample, the *same* subsample must be applied to *every* arm
   including "ours," and disclosed.
3. **One label-transfer rule for every arm:** fit a classifier on RNA cells
   inside that method's own embedding, then predict on protein cells whose
   labels it has never seen. Do not score an embedding with the "our"
   nearest-centroid rule unless that method's own native protocol is *also*
   reported alongside.
4. **Use scANVI, not vanilla trVAE**, for the scArches arm — scANVI is the
   label-consuming variant. Either drop Harmony or explicitly relabel it a
   *batch-correction floor*, not a cross-modal integration method.
5. **Report restricted and unrestricted for every arm, in the same table.**
6. **Keep the PCA + nearest-centroid floor** — a legitimate unsupervised
   comparator.
7. **Give each baseline a real training budget**, not default settings for
   a few minutes.
8. **If a run diverges, say so in the table**, not only in prose.
9. **Nothing gets wired into the site.** `benchmark.rows` stays pending
   until the methodology is clean.

## Three follow-up requirements

Once the first rebuild satisfying rules 1–9 was done, a second round of
feedback added:

- **A. "Ours" must go through the exact same harness as every baseline** —
  not just report a number copied out of a CSV. If the harness genuinely
  cannot reproduce the historical figure, report the harness number and say
  so; never mix a copied figure into a table of harness-produced ones.
- **B. Bootstrap confidence intervals on every arm.** Stratified bootstrap
  over the 1,490 protein query cells, 2,000 resamples, 95% percentile
  interval, on balanced accuracy specifically (the metric the table should
  be ranked by).
- **C. A majority-class baseline row**, so the accuracy column can't be
  misread as informative on its own, and **rank the table by balanced
  accuracy, not accuracy.**

## What "restricted" vs. "unrestricted" means

Only two of the 22 RNA cell classes — **macrophage** and **monocyte** —
have any real cross-modal (protein) coverage in the SCoPE2 query set (1,096
monocyte + 394 macrophage = all 1,490 query cells; every other RNA class has
zero protein cells to ever be scored against). "Unrestricted" lets a method
choose among all 22 RNA classes for every prediction; "restricted" masks
the candidate space down to just `{macrophage, monocyte}` before taking the
argmax. This is applied **at prediction time, not by refitting** — the same
convention `service/pipeline/assignment.py` uses in the real production
code, and the same one the original export notebook's own "Section E"
analysis used ("does restricting to the supported label space help... a
product decision, not a methodology one").

## The shared evaluation protocol (`tools/fair_benchmark/evaluate.py`)

Every method — floors, baselines, and "ours" alike — is scored by the
*same* two prediction rules, so that a difference in the reported number
reflects a difference in *embedding quality*, not classifier tuning:

- **Shared kNN-classifier rule** (rule 3's rule): `sklearn.neighbors.
  KNeighborsClassifier(n_neighbors=30, metric="cosine", weights="distance")`,
  fit on RNA cells in that method's own embedding space, predicted on
  protein cells. `k=30` is deliberately large relative to the rarest RNA
  class (one class, "myeloid dendritic cell," has exactly one cell in the
  entire 85,232-cell reference) and is **not tuned per method** — a fixed,
  simple, shared rule is the entire point.
- **Native nearest-centroid rule**, reported *alongside* the shared rule for
  every method per rule 3's "report the native protocol too" clause: one
  centroid per RNA class (the class mean in that method's embedding,
  L2-normalized), cosine-argmax at query time.
- **scANVI's own native classifier** is additionally reported for the
  scANVI arm specifically, since scANVI has a built-in classifier head
  jointly trained with its VAE — `.predict()` on unseen protein cells
  already *is* rule 3's protocol, natively built into the method, distinct
  from both of the above.

Both prediction functions return **unrestricted and restricted predictions
in one call** (masking, not refitting, per the restricted-regime rule
above), so every arm reports both regimes automatically.

### Bootstrap confidence intervals

`bootstrap_ci(true_labels, pred_labels, n_boot=2000, seed=0)` — a
**stratified** bootstrap: resamples are drawn *within* each true class
separately (with replacement, same size as that class), then concatenated,
so every resample preserves the real query set's class proportions (e.g.
1096:394 monocyte:macrophage in the restricted regime, or the true 22-class
proportions unrestricted) rather than letting resampling noise shift the
class balance itself. 2,000 resamples, 95% **percentile** interval (2.5th
to 97.5th percentile of the resampled statistic), computed independently
for accuracy and balanced accuracy.

This is cheap by design: it resamples already-computed `(true, pred)` pairs
— no re-embedding, no refitting, no retraining. That is *why* a CI could be
added to every already-finished arm's cached embeddings (`recompute_v2.py`)
without rerunning any of the actual (expensive) model training — see
[architecture.md](architecture.md).

### The majority-class floor

Predict "monocyte" (the majority class in both the RNA reference and the
protein query — not a coincidence, since it is the numerically dominant
myeloid lineage in blood) for every one of the 1,490 protein cells,
regardless of any embedding. This gives **73.56% accuracy, 50.00% balanced
accuracy** — verified directly against the real data (1096 + 394 = 1490
total; 1096/1490 = 73.56%; a constant predictor's balanced accuracy is
always exactly 50% for a 2-class problem, by definition — 100% recall on
the predicted class, 0% on the other, averaged).

This row exists specifically so the accuracy column cannot be misread as
informative on its own: several genuinely-unsupervised baselines' accuracy
numbers land at or below this trivial floor once measured fairly, which is
invisible unless the floor itself sits in the same table. **This is also
why the final table is ranked by balanced accuracy, not accuracy** —
accuracy alone rewards a classifier for doing nothing more than guessing
the majority class.
