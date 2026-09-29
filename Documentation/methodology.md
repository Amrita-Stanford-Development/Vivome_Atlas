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

A third round added:

- **D. Score "ours" through the exact same harness, using the real
  embedding** (not a reconstruction) once it was obtained — see
  [known-limitations.md](known-limitations.md).
- **E. A paired bootstrap on the balanced-accuracy difference** between
  "ours" and scANVI (the closest competitor), per scANVI seed, under the
  shared kNN rule — a statistically stronger comparison than checking
  whether two independent confidence intervals happen to overlap.
- **F. A "pool-first" restricted kNN variant** that mirrors
  `service/pipeline/assignment.py`'s actual `_assign_knn` algorithm
  (candidate pool restricted *before* the neighbour search, not after),
  reported alongside — never instead of — the shared rule's post-hoc
  masking, so the difference between "the evaluation rule's number" and
  "what the product would actually deliver" is visible rather than
  conflated.

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

## The shared evaluation protocol (`benchmark/evaluate.py`)

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

### Paired bootstrap (rule E)

`paired_bootstrap_diff(true_labels, pred_a, pred_b, n_boot=2000, seed=0)` —
the same stratified resampling as `bootstrap_ci`, but applied to **both**
methods' predictions with the *same* resampled indices in every resample,
directly producing a distribution of `balanced_accuracy(a) -
balanced_accuracy(b)`. This is the statistically correct way to compare two
methods scored on an identical query set — comparing two independently
bootstrapped CIs and checking whether they overlap is a weaker, more
conservative test that can miss a real, consistent difference. See
[results.md](results.md#paired-bootstrap-ours-minus-scanvi) for what this
found comparing "ours" against each scANVI seed.

### Pool-first restricted kNN (rule F)

`pool_first_knn_predict(rna_emb, rna_labels, prot_emb, supported, k)` —
restricted-regime only, and reported *alongside*, never instead of, the
shared rule's post-hoc masking. Mirrors
`service/pipeline/assignment.py`'s real `_assign_knn` implementation
exactly, down to reusing the same `service.pipeline.topk.chunked_topk`
helper: the pool of candidate RNA cells is filtered down to
`{macrophage, monocyte}` cells **before** the k-nearest-neighbour search
runs, and the vote tally happens only among that restricted pool. This is a
structurally different algorithm from post-hoc masking (fit on all 22
classes, restrict the output columns afterward) — not just a different way
of computing the same thing — and answers a different question: not "how
good is this embedding under a fixed, product-agnostic rule" but "what
would the live service actually return if `ASSIGNMENT_METHOD` were set to
`'knn'`." See [results.md](results.md#pool-first-knn-what-the-product-would-actually-deliver)
for what this found — the gap between the two rules turned out to be large
for good embeddings and negligible for near-chance ones.
