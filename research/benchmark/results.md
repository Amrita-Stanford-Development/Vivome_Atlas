# Results

All numbers below: full 85,232-cell RNA reference for every method (no
subsampling anywhere; "ours" aligned down from 85,233 by dropping one
CSV-split-dropped neutrophil cell — see
[bugs-and-fixes.md](bugs-and-fixes.md#7)), RNA labels used freely, **protein
labels touched only at this final scoring step, in every arm**. 95%
bootstrap confidence intervals (2,000 stratified resamples) in brackets.
Ranked by **balanced accuracy**, not accuracy.

**"Ours" is now scored across all five seeds of two model families, not one
checkpoint (Track D, T1 NB1d):** `v3_seed0` is the shipped model —
everything in this document before this revision scored that one seed
only, labeled just "Ours." `v3_seed1`–`v3_seed4` are four more independently
trained runs of the same architecture; `V2_seed0`–`V2_seed4` are a second
candidate architecture (mini-upload gene z-scoring, same shape as v3)
evaluated as a possible replacement. Every "Ours" row below is a 5-seed
mean ± SD (min–max in parentheses), computed by
`benchmark/evaluate.py`'s real, unchanged scoring functions
against each seed's own RNA reference and SCoPE2 protein embeddings
(`data/incoming/NB1d/embeddings/`, gitignored — the small tables anything here
cites are committed at `research/notebook-outputs/nb1d/`). A single seed's number is never
reported alone again in this section: `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv`
has every individual seed's score if you need one.
**This is a real, material correction, not just more decimal places:**
the single-seed "Ours" number this document reported before was `v3_seed0`
specifically, and `v3_seed0` turns out to be the best-performing of the
five v3 seeds by a wide margin on SCoPE2 restricted (79.79% balanced vs.
a 5-seed mean of 63.32% ± 10.84 — see the table below) — the original
number was real, but not representative of the architecture, only of the
one seed that happened to ship.

An earlier version of this table (before the corrections above existed)
scored a from-scratch *reconstruction* of the protein embedding instead of
any real saved artifact; that reconstruction turned out to be distorted by
two real bugs (one in the protein-side file used, one — the larger effect —
in `service/pipeline/encoder.py`'s activation function; see
[bugs-and-fixes.md](bugs-and-fixes.md)) and has been removed from this
table entirely, not kept as a labeled row. Every "Ours" number in this
document, single-seed or five-seed, is scored on real saved embeddings —
either `service/model/runtime/reference_embedding.npy` /
`service/model/source/app_export/prot_embedding_scope2.npy` (the shipped
`v3_seed0`) or T1 NB1d's own per-seed exports (everything else) — never a
reconstruction, and protein labels come from
`research/notebook-outputs/nb1d/scope2_cell_ids.csv` for the 5-seed numbers (confirmed
identical, row for row, to `atlas_PROT_v3_meta.csv`'s `true_class_name` and
to `web/data/atlas_PROT_lat128.csv`'s `class_name`) — never a file with an
unverified row order (see [known-limitations.md](known-limitations.md)).

**Sanity check (run before trusting anything else here, `v3_seed0`/shipped
model specifically):** the real
protein embedding, scored by cosine-argmax against
`service/model/runtime/reference_centroids.npy` (the trained centroids, not
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

**A methodological asymmetry that applies to every scANVI comparison in
this document:** scANVI trains on the query cells (transductive). Our
encoder is fixed and zero-shot on the query. This should, if anything,
favor scANVI, which makes scANVI's weaker showings elsewhere in this
document (e.g. the PBMC240 lineage arm) more notable, not less.

## Restricted regime (candidates = {macrophage, monocyte})

The only regime with real cross-modal ground truth for every candidate
class — every one of the 1,490 protein query cells is either macrophage or
monocyte.

| Rank | Method | Protocol | Accuracy % | Balanced accuracy % |
|---|---|---|---|---|
| 1 | **Ours (v3, 5-seed)** | shared kNN rule | 75.32 ± 11.79 (55.03–84.97) | **71.50 ± 10.60** (59.04–88.40) |
| 2 | **Ours (v3, 5-seed)** | native nearest-centroid | 79.38 ± 4.71 (73.76–86.17) | 63.32 ± 10.84 (50.79–79.79) |
| 3 | **Ours (v3, 5-seed)** | pool-first restricted (real) | 78.11 ± 4.69 (74.23–83.29) | 61.64 ± 11.80 (51.35–77.50) |
| 4 | scANVI (3-seed mean) | shared kNN rule | 70.67 (±2.48) | 76.89 (±0.99) |
| 5 | scANVI (3-seed mean) | native scANVI classifier | 74.77 (±18.59) | 73.15 (±28.49) |
| 6 | scANVI (3-seed mean) | native nearest-centroid | 61.21 (±19.13) | 64.42 (±26.66) |
| 7 | **Ours (V2, 5-seed)** | native nearest-centroid | 69.64 ± 7.62 (57.18–76.17) | 60.96 ± 10.03 (51.43–73.23) |
| 8 | **Ours (V2, 5-seed)** | pool-first restricted (real) | 76.60 ± 4.24 (73.42–83.69) | 57.63 ± 10.87 (49.91–76.15) |
| 9 | **Ours (V2, 5-seed)** | shared kNN rule | 74.81 ± 4.83 (66.64–79.33) | 58.26 ± 6.40 (48.23–63.11) |
| 10 | MaxFuse | shared kNN rule | 69.80 [68.39, 71.21]\* | 50.05 [48.49, 51.63]\* |
| — | **Majority class ("monocyte")** | trivial floor | 73.56 [71.34, 75.77]\* | 50.00 [50.00, 50.00]\* |
| 11 | Harmony (batch-correction floor) | native nearest-centroid | 50.20 [47.65, 52.68]\* | 54.20 [51.42, 57.02]\* |
| 12 | Harmony (batch-correction floor) | shared kNN rule | 46.78 [44.36, 49.40]\* | 50.49 [47.70, 53.38]\* |
| 13 | MaxFuse | native nearest-centroid | 51.95 [49.53, 54.50]\* | 52.38 [49.45, 55.29]\* |
| 14 | PCA floor | shared kNN rule | 67.25 [65.17, 69.40]\* | 57.66 [55.04, 60.37]\* |
| 15 | PCA floor | native nearest-centroid | 55.97 [53.42, 58.52]\* | 58.21 [55.42, 60.96]\* |
| 16 | scGLUE | shared kNN rule | 28.59 [27.32, 29.93]\* | 48.21 [46.52, 49.78]\* |
| 17 | scGLUE | native nearest-centroid | 47.92 [45.37, 50.54]\* | 47.20 [44.22, 50.20]\* |

\* 95% bootstrap CI (single run, that method's only seed). scANVI rows show
3-seed mean (±spread — **range, max−min**, across seeds 0/1/2, not
standard deviation) — see [scANVI across seeds](#scanvi-across-seeds) for
the per-seed breakdown. "Ours" rows show 5-seed mean ± SD (min–max) —
see [Ours across seeds](#ours-across-five-seeds-v3-and-v2) below; no
single seed is representative, in either direction, of either family.
Rank ordering above is by mean balanced accuracy; ranking any individual
"Ours" seed against scANVI's per-seed spread is a materially different,
noisier comparison — see the paired bootstrap section.

**Reading this table:** the picture is far less one-sided than the
original single-seed version of this document reported, and this reverses
the original headline. Under the shared kNN rule, v3's 5-seed mean
balanced accuracy (71.50%) is **below** scANVI's 3-seed mean (76.89%) —
the original claim that "ours" beats
scANVI by double digits under this rule was true only for `v3_seed0`
specifically (88.40%, the best of the five v3 seeds by a wide margin), not
for the v3 architecture generally. Under native nearest-centroid, v3's
5-seed mean (63.32%) also trails scANVI's native-classifier mean (73.15%,
though that number itself has a huge ±28.49-point seed spread) and its
native-centroid mean (64.42%, statistically indistinguishable from v3's
63.32%). V2 does no better than v3 against scANVI on SCoPE2 under any
protocol. The **only** regime and seed where "ours" clearly, robustly beats
scANVI is `v3_seed0` — the one seed that happened to ship — which is why
the paired-bootstrap section below reports the comparison per seed, not as
a single family-level verdict. The three genuinely unsupervised methods
(MaxFuse, Harmony, scGLUE) remain in the high-40s to low-50s% — still
indistinguishable from each other and from the 50.00% trivial floor,
regardless of anything above.

### Ours across five seeds (v3 and V2)

| Family | Protocol | Accuracy % (mean ± SD, min–max) | Balanced accuracy % (mean ± SD, min–max) |
|---|---|---|---|
| v3 | shared kNN rule | 75.32 ± 11.79 (55.03–84.97) | 71.50 ± 10.60 (59.04–88.40) |
| v3 | native nearest-centroid | 79.38 ± 4.71 (73.76–86.17) | 63.32 ± 10.84 (50.79–79.79) |
| v3 | pool-first restricted (real) | 78.11 ± 4.69 (74.23–83.29) | 61.64 ± 11.80 (51.35–77.50) |
| V2 | shared kNN rule | 74.81 ± 4.83 (66.64–79.33) | 58.26 ± 6.40 (48.23–63.11) |
| V2 | native nearest-centroid | 69.64 ± 7.62 (57.18–76.17) | 60.96 ± 10.03 (51.43–73.23) |
| V2 | pool-first restricted (real) | 76.60 ± 4.24 (73.42–83.69) | 57.63 ± 10.87 (49.91–76.15) |

Source: `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` (per-seed),
`research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` (this table),
computed by `benchmark/evaluate.py`'s unchanged
`knn_classifier_predict`, `nearest_centroid_predict`, and
`pool_first_knn_predict` against T1 NB1d's per-seed embeddings. v3's
shared-kNN-rule SD (10.60 points) is comparable in size to the entire gap
this document previously reported between "ours" and scANVI (11.5 points)
— a single seed's number was never a safe stand-in for the architecture.

**For the record, since it materially changed once real data replaced the
reconstruction:** the earlier reconstruction-based table had scANVI's
shared-kNN-rule restricted balanced accuracy (77.26%) *ahead* of the
reconstruction's own shared-kNN-rule number (74.50%) — i.e., "ours" looked
like it was *behind* scANVI under that one specific protocol. That
reconstruction was computed through `service/pipeline` before the
`service/pipeline/encoder.py` ReLU/GELU fix (commit `056f136` — see
[bugs-and-fixes.md](bugs-and-fixes.md#0)), so every number it produced,
including this one, is invalid on its own terms, not just "distorted." On
the real embedding, `v3_seed0` leads scANVI under every protocol tested —
but, per the 5-seed table above, that is `v3_seed0`'s own result, not a
result of the v3 architecture in general.

## Unrestricted regime (all 22 RNA classes as candidates)

Every RNA class competes for every prediction, even though only two classes
have any real protein ground truth. Much harder for every method.

| Rank | Method | Protocol | Accuracy % | Balanced accuracy % |
|---|---|---|---|---|
| 1 | **Ours (v3, 5-seed)** | shared kNN rule | 38.36 ± 25.71 (1.88–69.26) | **29.07 ± 18.34** (1.28–49.84) |
| 2 | **Ours (v3, 5-seed)** | native nearest-centroid | 34.09 ± 25.25 (0.20–66.24) | 25.60 ± 17.35 (0.14–48.20) |
| 3 | scANVI (3-seed mean) | native scANVI classifier | 18.01 (±19.26) | 12.92 (±15.04) |
| 4 | scANVI (3-seed mean) | shared kNN rule | 17.27 (±11.07) | 11.77 (±7.53) |
| 5 | PCA floor | shared kNN rule | 15.84 [14.09, 17.72]\* | 11.01 [9.79, 12.37]\* |
| 6 | **Ours (V2, 5-seed)** | shared kNN rule | 12.17 ± 8.12 (2.89–22.48) | 8.63 ± 5.40 (1.96–15.28) |
| 7 | scANVI (3-seed mean) | native nearest-centroid | 10.60 (±7.92) | 7.48 (±6.20) |
| 8 | MaxFuse | native nearest-centroid | 5.91 [4.76, 7.11]\* | 4.91 [3.84, 5.99]\* |
| 9 | Harmony | shared kNN rule | 7.11 [5.84, 8.32]\* | 4.84 [3.97, 5.66]\* |
| 10 | **Ours (V2, 5-seed)** | native nearest-centroid | 4.05 ± 5.12 (0.34–13.09) | 3.08 ± 3.40 (0.23–8.98) |
| 11 | PCA floor | native nearest-centroid | 3.69 [2.82, 4.70]\* | 2.59 [1.96, 3.31]\* |
| 12 | Harmony | native nearest-centroid | 3.76 [2.89, 4.77]\* | 2.55 [1.96, 3.24]\* |
| 13 | MaxFuse | shared kNN rule | 1.07 [0.60, 1.61]\* | 0.81 [0.41, 1.25]\* |
| 14 | scGLUE | shared kNN rule | 0.47 [0.20, 0.87]\* | 0.40 [0.14, 0.76]\* |
| 15 | scGLUE | native nearest-centroid | 0.20 [0.00, 0.47]\* | 0.30 [0.00, 0.73]\* |

\* 95% bootstrap CI (single run). scANVI rows show 3-seed mean (±spread,
max−min across seeds 0/1/2) — see
[scANVI across seeds](#scanvi-across-seeds). "Ours" rows show 5-seed mean
± SD (min–max) — see [Ours across seeds](#ours-across-five-seeds-v3-and-v2).

*(Majority-class floor omitted here: predicting "monocyte" scores the same
73.56%/50.00% regardless of candidate-class count, since it never varies
its prediction.)*

**Reading this table:** everyone is far worse here than in the restricted
regime — full 22-way transfer from RNA to a genuinely different
measurement modality, at real SCoPE2 noise levels, is hard for every
method. Unlike the restricted regime, v3's 5-seed mean (29.07% balanced)
*does* clearly lead scANVI's 3-seed mean (12.92% at best) here, and by a
wide margin under either protocol — 12 of the 15 v3-seed × scANVI-seed
paired-bootstrap comparisons in this regime have a CI excluding zero in
v3's favor (see the paired bootstrap section). V2, however, does **not**
clearly beat scANVI here (8.63% mean vs. scANVI's 11.77–12.92%) — only 4 of
15 V2-seed × scANVI-seed pairings favor V2 significantly, 8 favor scANVI.
The unrestricted regime is the one place in this document where v3 and
scANVI are not close: v3 wins decisively, and V2 does not inherit that win.

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
(`v3_seed0` specifically, the number this document reported before the
5-seed correction above) scores 31.08% — more than 4× the reconstruction's
(invalid) 6.98% on that identical rule. The embedding itself — corrected
for both the file-panel issue and the ReLU bug — was the dominant source
of the earlier gap, not the choice of decision rule. (Classifier choice
still matters at the margins — `v3_seed0`'s shared-kNN unrestricted,
55.37% acc / 38.69% bal, is higher than its own native-centroid
unrestricted, 45.37% acc / 31.08% bal — but this is a real, secondary
effect on top of a correct embedding, not the primary explanation for a
large discrepancy. The 5-seed family means above are lower than either of
`v3_seed0`'s own numbers, consistent with `v3_seed0` being the strongest
of the five seeds on SCoPE2.)

## scANVI across seeds

All 3 seeds (0, 1, 2) complete, same architecture and training budget
(200 pretrain epochs + 100 fine-tune epochs, early stopping) each time.

**These are a fresh re-run (Track D, T1 NB1d follow-up), not the original
numbers** — scANVI was retrained from scratch to get real per-cell
predictions to pair-bootstrap against the new 5-seed "ours" data (none were
cached from the original run). Seeds 1 and 2 reproduced their original
numbers closely; **seed 0 did not** (its native-scANVI-classifier restricted
balanced accuracy moved from 57.89% originally to 73.51% here) — scVI/scANVI
training on this hardware (Apple MPS backend) is not bit-for-bit
deterministic even with an explicit seed set, unlike a CUDA run would be.
The table below is what this document's other sections (including the
paired bootstrap) actually use; the original run's numbers are kept in git
history, not reproduced here.

| Protocol | Regime | Seed 0 bal | Seed 1 bal | Seed 2 bal | Mean bal | Spread (max−min) |
|---|---|---|---|---|---|---|
| Shared kNN rule | restricted | 78.04 | 77.16 | 76.26 | **77.15** | **1.77** |
| Shared kNN rule | unrestricted | 12.73 | 7.71 | 12.35 | 10.93 | 5.02 |
| Native scANVI classifier | restricted | 73.51 | 75.18 | 86.37 | 78.35 | **12.86** |
| Native scANVI classifier | unrestricted | 12.38 | 5.43 | 20.47 | 12.76 | 15.04 |
| Native nearest-centroid | restricted | 49.99 | 65.20 | 77.36 | 64.18 | 27.37 |
| Native nearest-centroid | unrestricted | 7.07 | 6.66 | 10.99 | 8.24 | 4.33 |

(Accuracy figures, for completeness — shared kNN rule restricted:
71.28/70.47/72.01; native scANVI classifier restricted: 74.90/73.89/84.50;
native nearest-centroid restricted: 55.84/59.80/71.48.)

**Reading this table — and answering the question this whole investigation
started with, now against the 5-seed "ours" data above:**

- **Under the shared kNN rule — the one apples-to-apples protocol applied
  identically to every method — scANVI is remarkably *stable* across seeds
  (76.26–78.04%, a spread of under 2 points), and its 3-seed mean (77.15%)
  is now *higher* than v3's 5-seed mean (71.50%) under the same rule.
  Only `v3_seed0` (88.40%) individually beats every scANVI seed; the other
  four v3 seeds (59.04–70.10%) do not. This comparison is solid precisely
  because it is stable — and what it now shows is that v3 does not reliably
  beat scANVI here, `v3_seed0` does.**
- Under scANVI's *own* native classifier, the picture is far noisier: a
  12.9-point spread across 3 seeds (73.51% to 86.37%) this run (was a
  28.5-point spread, 57.89–86.37%, in the original run — itself evidence of
  how much a single scANVI training run can move). Seed 2's native
  classifier (86.37%) exceeds every "ours" number in this document except
  `v3_seed0`'s two best protocols. Averaged across seeds (78.35%), scANVI's
  own classifier is now *ahead* of v3's native-nearest-centroid mean
  (63.32%).
- The honest summary: **`v3_seed0` — the one seed that shipped — beats
  scANVI clearly under every protocol tested. The v3 architecture generally
  does not: its 5-seed mean trails scANVI's 3-seed mean under both the
  shared kNN rule (71.50% vs. 77.15%) and native protocols (63.32% vs.
  scANVI's 64.42–78.35% depending on protocol). This reverses what this
  document said before the 5-seed correction — it is not evidence the two
  methods perform similarly in general; it is evidence that a single
  seed, in either direction, is not a safe basis for that comparison.**

Context: this document now has training-variance data for "ours" too,
not just sampling-uncertainty CIs on one trained model. Restricted-regime
shared-kNN-rule balanced accuracy spans 59.04–88.40% across v3's own 5
training seeds (SD 10.60) — a wider spread than scANVI's 3-seed spread
under the same rule (76.26–78.04%, SD ≈0.93). The production reference's
separate 5-seed training run on its own RNA-only validation task
(`service/model/evidence/v3_tables/reference_seeds.csv`, mean balanced accuracy
0.7143) is a different task and dataset from this benchmark's
protein-transfer scoring and not directly comparable to any number above —
but it is notable that RNA-only validation shows far less seed-to-seed
spread than this document's real cross-modal SCoPE2 scoring does, meaning
whatever makes v3 unstable here is specific to the RNA→protein transfer
step, not the RNA-side training itself.

## Paired bootstrap: ours minus scANVI

The tables above compare two *independent* 95% CIs and note whether they
overlap. A **paired** bootstrap is the statistically correct way to compare
two methods scored on the identical query set: the same resampled cell
indices are applied to *both* methods in every one of 2,000 resamples, and
the balanced-accuracy difference is computed per resample, directly giving
a CI on the difference itself.

**This section changed the most of anything in this document under Track
D.** The original version ran this comparison for `v3_seed0` only — every
number in it was real, but it silently generalized a single seed's result
to "ours vs. scANVI." This version runs all **90** pairings (10 "ours"
model-seeds × 3 scANVI seeds × 3 regimes) and reports how many actually
support a claim of "ours ahead." Full table:
`research/notebook-outputs/nb1d/paired_bootstrap_ours_vs_scanvi.csv`.

### `v3_seed0` (the shipped model) — unchanged conclusion

| scANVI seed | Regime | Δ balanced accuracy (v3_seed0 − scANVI), pts | 95% CI |
|---|---|---|---|
| 0 | restricted, shared kNN rule | +10.36 | [+8.21, +12.55] |
| 1 | restricted, shared kNN rule | +11.24 | [+9.14, +13.35] |
| 2 | restricted, shared kNN rule | +12.14 | [+9.88, +14.43] |
| 0 | restricted, pool-first | +22.15 | [+18.84, +25.39] |
| 1 | restricted, pool-first | +15.51 | [+12.31, +18.68] |
| 2 | restricted, pool-first | +9.84 | [+6.50, +13.13] |
| 0 | unrestricted | +25.97 | [+24.16, +27.69] |
| 1 | unrestricted | +30.98 | [+29.27, +32.71] |
| 2 | unrestricted | +26.34 | [+24.50, +28.11] |

Every one of `v3_seed0`'s 9 pairings excludes zero, in `v3_seed0`'s favor.
This specific claim — about this specific, shipped checkpoint — is
unchanged and still correct.

### All 10 "ours" model-seeds × all 3 scANVI seeds — the claim does not generalize

| Family | Regime | CI excludes zero, ours ahead | CI excludes zero, scANVI ahead | Not significant | Mean Δ ± SD, pts |
|---|---|---|---|---|---|
| v3 | unrestricted | 12 / 15 | 3 / 15 | 0 / 15 | +18.14 ± 17.14 |
| v3 | restricted, shared kNN rule | 3 / 15 | 12 / 15 | 0 / 15 | −5.65 ± 9.84 |
| v3 | restricted, pool-first | 5 / 15 | 8 / 15 | 2 / 15 | −0.03 ± 12.10 |
| V2 | unrestricted | 4 / 15 | 8 / 15 | 3 / 15 | −2.30 ± 5.53 |
| V2 | restricted, shared kNN rule | 0 / 15 | 15 / 15 | 0 / 15 | −18.89 ± 5.97 |
| V2 | restricted, pool-first | 4 / 15 | 11 / 15 | 0 / 15 | −4.04 ± 11.33 |

**Reading this table:** of the 90 pairings, only **28 exclude zero in
"ours"'s favor** (62 either exclude zero in scANVI's favor or are not
significant). The **unrestricted regime is the one place v3 reliably beats
scANVI** (12 of 15 pairings, mean +18.14 points) — consistent with the
unrestricted-regime table above. Everywhere restricted candidates are
involved, the picture reverses: v3's shared-kNN-rule restricted mean is
**negative** (scANVI ahead by 5.65 points on average), and pool-first is a
coin flip. V2 never reliably beats scANVI under any regime tested, and is
reliably *behind* under the restricted shared-kNN rule (15 of 15 pairings
favor scANVI). **The corrected claim: "ours beats scANVI by +9 to +14
points under the shared kNN restricted rule" is true of `v3_seed0`
specifically and does not hold for the v3 architecture, or for V2, in
general.** This is the single most important correction Track D made to
this document.

(scANVI's spread figures elsewhere in this document are reported as
**range** (max−min) across seeds, not SD, because n=3 is too small for SD
to be a very meaningful summary on its own — see the scANVI-across-seeds
section above for both figures on scANVI's own numbers. "Ours" now has 5
seeds per family, where SD is a more meaningful summary; both tables above
use it directly.)

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
`benchmark/evaluate.py` mirrors `_assign_knn` exactly (same
`chunked_topk` helper, same pool-restriction-then-vote logic), so this
table shows what the product would actually deliver if `ASSIGNMENT_METHOD`
were set to `"knn"` — distinct from `nearest_centroid`, the method
currently configured as the shipped default.

| Method | Post-hoc masking bal. acc. % | Pool-first (real) bal. acc. % | Δ |
|---|---|---|---|
| **Ours (`v3_seed0`, shipped)** | 88.40 [86.85, 89.92] | 77.50 [74.92, 80.02] | −10.9 |
| **Ours (v3, 5-seed mean)** | 71.50 ± 10.60 | 61.64 ± 11.80 | −9.9 (mean) |
| **Ours (V2, 5-seed mean)** | 58.26 ± 6.40 | 57.63 ± 10.87 | −0.6 (mean) |
| scANVI (seed 0) | 78.04 [76.02, 79.98] | 55.35 [53.29, 57.69] | −22.7 |
| scANVI (seed 1) | 77.16 [75.24, 79.14] | 61.99 [59.55, 64.45] | −15.2 |
| scANVI (seed 2) | 76.26 [73.96, 78.54] | 67.66 [65.27, 70.28] | −8.6 |
| PCA floor | 57.66 [55.04, 60.37] | 53.37 [51.23, 55.65] | −4.3 |
| Harmony | 50.49 [47.70, 53.38] | 52.86 [50.46, 55.30] | +2.4 |
| MaxFuse | 50.05 [48.49, 51.63] | 50.00 [50.00, 50.00] | −0.1 |
| scGLUE | 48.21 [46.52, 49.78] | 49.80 [48.09, 51.55] | +1.6 |

(scANVI's seed-0 numbers here are this run's re-trained model — see the
reproducibility note in the scANVI-across-seeds section; seed 0's earlier
pool-first number, 49.85%, is not reproduced this run.)

**Reading this table:** pool-first restriction costs a large amount of
balanced accuracy for the embeddings that actually carry real cell-type
signal (v3's 5-seed mean: −9.9 points; scANVI: −8.6 to −22.7 points,
itself highly seed-dependent), and costs essentially nothing for the
near-chance embeddings (MaxFuse, scGLUE — restricting the pool barely
matters when the full-pool search was already close to random). This makes
sense mechanically: if a query cell's true nearest neighbours in a *good*
embedding happen to be an easy, well-separated set that includes some
non-restricted-class cells, post-hoc masking still benefits from finding
those genuinely close neighbours first and only tallying the restricted
subset among them; pool-first forces the search into a smaller,
sometimes-worse-matching subset from the start.

**Unlike the post-hoc-masking comparison above, "ours" does not clearly
lead scANVI under pool-first either** — v3's 5-seed pool-first mean
(61.64%) sits inside scANVI's 3-seed pool-first range (55.35–67.66%), and
V2's mean (57.63%) is below two of scANVI's three seeds. Only `v3_seed0`
(77.50%) clearly leads every scANVI pool-first number. This matches the
paired-bootstrap finding above: pool-first restricted is one of the
regimes where "ours" does not reliably beat scANVI once more than one seed
is considered — worth knowing before assuming the live service's actual
kNN option (if ever selected over the current `nearest_centroid` default)
would deliver a number resembling `v3_seed0`'s specifically.

## PBMC240 lineage arm — a development dataset, not a held-out evaluation

The real PBMC240 DIA-NN report (237 cells, ~75% missing values in the
shared gene space — nothing like SCoPE2's zero missingness) is scored here
at **lineage level** (myeloid vs. lymphoid), using weak labels from
clustering, not curated ground truth. **Label this arm plainly: it is a
development dataset used to choose V2 over v3, not a held-out evaluation of
either.** 122 of the 237 cells have a confident weak label (**117
lymphoid, 5 myeloid**); the other 115 ("unassigned") are excluded from
scoring, matching how T1 NB1d itself scored this arm.

### What scANVI actually received on PBMC240

"Ours" (v3, V2) never sees PBMC240 in a preprocessing choice — the live
service's own fixed pipeline runs identically regardless of input. scANVI,
by contrast, is trained from scratch on whatever matrix it's handed, so
its input is a real methodological choice that needs stating exactly, not
assumed neutral. Two variants were tested:

| | **raw** | **processed** |
|---|---|---|
| Source | `service/examples/pbmc240_proteins_raw.tsv` (the real DIA-NN report) | `service/examples/pbmc240_zscored_all_genes.csv` (this project's own earlier A2-investigation recipe) |
| Scale | Linear (as-measured intensity units) — **not log-transformed** | log2(x+1) |
| Per-cell normalization | None | Median-normalized (subtract each cell's own median, add back the global median of medians) |
| Missing values, within-panel | Left as NaN | Imputed: left-censored `Normal(1st percentile, 0.3)` |
| Genes | Reduced to the shared 2,907-gene fair-benchmark space; PBMC240 detected 1,215 of them | This file's own ≥5% detection-rate filter kept 2,402 genes; 1,111 of those overlap the shared 2,907-gene space |
| Final step, both variants | Per-gene z-score over observed values only, then **any entry still missing after reindexing to the shared 2,907-gene space set to 0** (genes never detected, for "raw"; genes outside this file's own filtered panel, for "processed" — 1,796 columns, 61.8% of the matrix) | (same) |

**Neither variant is NaN-free once reindexed to the full shared gene
space** — "processed" is not "raw, but complete"; it differs in how the
genes it does have are prepared (log-transformed, per-cell normalized,
imputed within its own smaller panel) and in exactly which genes those
are, not in whether missingness exists. The result reported as scANVI's
number in the table below is **the better of the two inputs**, so no
version of "scANVI underperforms because of a preprocessing
disadvantage" survives uncorrected; both variants' own numbers are also
shown for transparency. Source for both:
`benchmark/pbmc240_lineage_prep.py`; per-seed results:
`research/notebook-outputs/nb1d/scanvi_pbmc240_input_variants.csv`.

**Plain accuracy is not reported here — it is uninformative at 117 vs. 5.**
A single overall accuracy number is dominated almost entirely by lymphoid
performance (117 of 122 cells) and can hide a method that gets every
myeloid cell wrong, or hide a method that gets suspiciously many "right" by
predicting one lineage for nearly everyone. Recall per lineage, plus what
each method actually predicts across the full sample, shows both failure
modes directly; accuracy alone shows neither.

| Method | Protocol | Lymphoid recall % (n=117) | Myeloid recall % (n=5, anecdotal) | Predicted composition (all 237 cells) |
|---|---|---|---|---|
| **Ours (v3, 5-seed)** | native nearest-centroid → lineage | 52.82 ± 7.73 (43.59–63.25) | 100.0 ± 0.0 (5/5, every seed) | ~47% lymphoid, ~50% myeloid, ~3% other lineages |
| **Ours (V2, 5-seed)** | native nearest-centroid → lineage | 92.82 ± 0.76 (92.31–94.02) | 80.0 ± 0.0 (4/5, every seed) | ~78% lymphoid, ~17% myeloid, ~5% other lineages |
| scANVI, **processed input (better of the two — reported result)** | shared kNN rule → lineage | 17.95 (15.38–19.66) | 100.0 (5/5, every seed) | ~16% lymphoid, **~66% myeloid**, ~17% erythroid/other |
| scANVI, **processed input (better of the two — reported result)** | native scANVI classifier → lineage | 21.37 (5.13–50.43) | 100.0 (5/5, every seed) | ~17% lymphoid, **~82% myeloid** |
| scANVI, raw input | shared kNN rule → lineage | 8.83 (5.13–11.97) | 100.0 (5/5, every seed) | ~15% lymphoid, **~74% myeloid**, ~11% erythroid/other |
| scANVI, raw input | native scANVI classifier → lineage | 6.55 (3.42–12.82) | 100.0 (5/5, every seed) | ~9% lymphoid, **~91% myeloid** |

Source: `research/notebook-outputs/nb1d/real_data_per_seed.csv` ("ours" recall and
predicted-composition columns) and
`research/notebook-outputs/nb1d/scanvi_pbmc240_input_variants.csv` (scANVI, both input
variants, computed from the cached per-cell predictions
`benchmark/results/pbmc_scanvi_{knn,native}_pred_lineage{,_processed}_seed{0,1,2}.npy`
— gitignored, but not disposable; see `benchmark/.gitignore` —
produced by `benchmark/scanvi_run_pbmc240.py`, a fresh
integration of RNA + this arm's own real PBMC240 matrix in the shared gene
space, not the SCoPE2 scANVI run above; a different query set needs its
own joint embedding). Class→lineage mapping is
`service/model/runtime/reference_metadata.csv`'s own `lineage` column, the same one
the live service and every other lineage figure in this project use.

**Reading this table — recall and composition tell a different, more
specific story than the accuracy number this section previously led with.**
The right way to read a per-class recall is paired with its counterpart,
not against overall accuracy: **a trivial model that calls every cell
"lymphoid" scores 100% lymphoid recall and 0% myeloid recall** — a single
recall number in isolation says nothing until read alongside the other
one. Read as pairs: v3 (52.82% lymphoid, 100.0% myeloid) and V2 (92.82%
lymphoid, 80.0% myeloid) both show real, non-trivial separation between
the two lineages — neither is the trivial "call everything one class"
failure mode. scANVI's best pair (17.95–21.37% lymphoid on the processed
input, 100.0% myeloid) looks superficially similar to "ours" on myeloid
recall alone, but its predicted composition (66–82% of all 237 cells
labelled "myeloid") shows this remains close to that trivial failure mode
in practice: near-universal "myeloid" predictions trivially catch the 5
real myeloid cells while missing the large majority of the 117 real
lymphoid ones — and this is *after* giving scANVI the better-prepared of
two inputs (see "What scANVI actually received," above); the raw input's
numbers (8.83%/6.55% lymphoid, 74–91% myeloid composition) are worse
still. **With only 5 myeloid
cells, every method's myeloid recall is anecdotal — one misclassified cell
moves it by 20 points — and is reported alongside lymphoid recall only so
a method's overall behavior (real separation vs. one-class collapse) is
visible, never to rank methods on it in isolation.** The comparison that
matters here is not "which method wins" but the one T1 NB1d actually used
PBMC240 for: V2's lymphoid recall is a large, low-variance improvement
over v3's on real data with substantial missingness — the reason V2 was
carried forward as a candidate (`research/notebook-outputs/nb1d/nb1d_summary.json`'s
`decision.carry_V2: true`) — even though V2 does not carry that advantage
onto SCoPE2 (see the tables above, where V2 is no better than v3 against
scANVI). **Report both findings together, honestly:** V2 is the right
call for real, messy, high-missingness uploads; it is not a strictly
better encoder than v3 in every respect measured in this document. (See
the transductive-vs.-zero-shot caveat near the top of this document — it
applies here too, and if anything makes scANVI's near-collapse into
predicting one dominant lineage more notable, not less.)

## Fulcher 2026 — the first held-out evaluation

**What this is.** Fulcher 2026 is TMT32-multiplexed single-cell proteomics
of human PBMCs, processed with FragPipe. Nothing in this project was fitted,
tuned or selected on it.

- **Protocol.** [protocol-fulcher2026.md](protocol-fulcher2026.md) was
  committed at `2bcb657`, before any score existed. Amendment 1 (a
  label-free centroid check) was also made before scoring. Amendment 2 was
  added after the first results, on the owner's instruction. It added a
  scANVI arm restricted to the genes Fulcher measures, made scANVI's
  headline its best arm, and added an exploratory five-type score.
- **Scored cells.** 1,251 labelled cells in six types: CD4T 308, CD8T 181,
  NK 150, B 102, monocyte 456, DC 54. The upload holds all 1,275 QC-passed
  cells; 24 Unknown cells are kept in but not scored.
- **Scoring.** Every model classifies against all 22 reference classes,
  mapped to the six types or "other" by the protocol's fixed table. Chance
  balanced accuracy is 16.7%.
- **Tables** are in [`fulcher2026`](fulcher2026/per_seed_scores.csv).
- **Held-out result, then development data.** The results in this section
  are Fulcher's one held-out scoring under the frozen protocol. Since
  2026-09-30, by owner decision, Fulcher is a development dataset like
  PBMC240. Later scores on it are development numbers, and Khoury 2026 is
  the only sealed final test.

**Two caveats, stated plainly.**

- **The labels are not independent ground truth.** They are the authors' own
  annotation: a Seurat label transfer from an scRNA-seq reference, then
  cluster refinement. A score here measures agreement with that annotation.
- **This is a different technology from PBMC240.** Fulcher 2026 is TMT
  (FragPipe). PBMC240 is label-free DIA (DIA-NN), and SCoPE2 is a third
  technology again.

**Setup.**

- **Our models.** The five v3 seeds (seed 0 is the served model) and the
  five V2 seeds all ran through the service's own query path,
  `pipeline.embed_query`, with no batch correction.
- **The gate passed before anything was embedded.** V2_seed0 reproduces
  NB1d's PBMC240 latents at a median cosine of 0.99965
  ([gate.json](fulcher2026/gate.json)).
- **scANVI** ran three arms, three seeds each, with the same training setup
  as the PBMC240 arm. It is transductive: it trains on the Fulcher cells
  themselves. Its headline is `log2_measuredgenes`, its best arm
  (amendment 2). Under the original protocol rule, the better of the first
  two arms, it would be `log2`. Both are reported.

### What scANVI was trained and queried on

The per-gene record is in
[scanvi_gene_space.csv](fulcher2026/scanvi_gene_space.csv).

- **The original two arms (`log2`, `log2_cellmedian`)** use load.py's gene
  space: the 2,907 genes the atlas RNA reference and SCoPE2 share. That
  space was fixed before Fulcher existed.
  - Fulcher measures only 932 of those genes. The other 1,975 are unmeasured
    for every query cell.
  - Within the 932, a cell observes 402 to 932 genes (median 571).
  - Each gene is z-scored over its observed values, separately for the RNA
    reference and the query, and every unobserved query entry is then set
    to 0.
  - So about two thirds of every query cell's input is a constant 0 that
    scANVI's model reads as a measurement.
- **The measured-genes arm (`log2_measuredgenes`)** restricts both the RNA
  reference and the query to the 932 measured genes, with the same scaling
  and zero-fill for within-gene missingness. The gene set is chosen from
  measurement alone; no labels are involved.
- **Our encoders see more Fulcher genes.** v3 and V2 see 1,654 Fulcher
  genes through their 9,002-gene feature space. scANVI's best arm sees 932,
  because the RNA expression the benchmark has for the reference covers
  only the 2,907 atlas genes. Neither side's gene set was chosen on Fulcher
  labels.

### Balanced accuracy over the six types

Mean ± SD (min–max), over 5 seeds for our models and 3 for scANVI.

| Model | Nearest centroid (product rule) / scANVI native | Shared kNN rule |
|---|---|---|
| **V2** | **57.3 ± 2.2** (54.8–59.2) | **55.5 ± 2.6** (51.8–58.1) |
| v3 | 42.3 ± 3.4 (39.9–47.6) | 42.0 ± 2.9 (39.5–46.8) |
| `v3_seed0` (served) | 44.1 | 41.8 |
| scANVI, `log2_measuredgenes` (**best arm, headline**) | 37.7 ± 2.1 (35.4–39.6) | 47.8 ± 0.9 (46.9–48.6) |
| scANVI, `log2` (original-protocol headline) | 19.0 ± 11.4 | 21.4 ± 2.2 |
| scANVI, `log2_cellmedian` | 17.2 ± 9.3 | 17.8 ± 8.1 |

Source: [family_summary.csv](fulcher2026/family_summary.csv) and
[per_seed_scores.csv](fulcher2026/per_seed_scores.csv).

### Paired bootstrap

Balanced accuracy difference, 2,000 stratified resamples; the source is
[paired_bootstrap.csv](fulcher2026/paired_bootstrap.csv).

| Comparison | Rules | Pairings with CI excluding 0 | Mean difference (range) |
|---|---|---|---|
| V2 − v3 | nearest centroid | **25 of 25**, all favour V2 | +15.0 (+7.2 to +19.3) |
| V2 − v3 | shared kNN | **25 of 25**, all favour V2 | +13.4 (+5.0 to +18.7) |
| V2 − scANVI best arm | nearest centroid vs native | **15 of 15**, all favour V2 | +19.7 (+15.1 to +23.7) |
| V2 − scANVI best arm | shared kNN | **15 of 15**, all favour V2 | +7.6 (+3.2 to +11.3) |
| v3 − scANVI best arm | nearest centroid vs native | 9 of 15 favour v3, 6 inconclusive | +4.7 (+0.3 to +12.2) |
| v3 − scANVI best arm | shared kNN | **12 of 15 favour scANVI**, 3 inconclusive | −5.8 (−9.1 to −0.1) |
| v3 − scANVI `log2` (original headline) | nearest centroid vs native | 15 of 15 favour v3 | +23.4 (+8.2 to +37.8) |
| v3 − scANVI `log2` (original headline) | shared kNN | 15 of 15 favour v3 | +20.7 (+15.6 to +26.8) |
| V2 − scANVI `log2` (original headline) | nearest centroid vs native | 15 of 15 favour V2 | +38.3 (+23.0 to +49.4) |
| V2 − scANVI `log2` (original headline) | shared kNN | 15 of 15 favour V2 | +34.1 (+27.9 to +38.1) |

**The first write-up of this section compared us only against scANVI's
`log2` arm, and so overstated v3's lead.** That arm is near chance because
two thirds of its input columns are zero-filled. Against scANVI's best arm:

- **V2 still wins every pairing.**
- **v3 loses under the shared kNN rule,** by 5.8 points on average.
- **v3's product rule against scANVI's native classifier** leads in 9 of 15
  pairings, and the other 6 are inconclusive.

### What the numbers show

1. **V2 beats v3 on held-out data, in every seed pairing under both rules.**
   V2 was chosen over v3 on PBMC240, which is why PBMC240 can no longer test
   that choice. Fulcher can, and it agrees: +13 to +15 points of balanced
   accuracy, with every one of the 50 CIs above zero.
2. **V2 also beats the strongest baseline arm we have.** It beats scANVI on
   the genes Fulcher measures by +7.6 (shared kNN) and +19.7 (product rule
   vs native), in 30 of 30 pairings. v3 does not beat that arm under the
   shared rule.
3. **The two models fail differently.** The patterns below are nearest
   centroid, summed over seeds, with rows as true types
   ([confusion.csv](fulcher2026/confusion.csv)).
   - **v3's lymphoid errors.** It calls 41% of CD4T cells CD8T and 43% of NK
     cells CD8T, and sends 23% of CD4T and 40% of B cells to "other".
   - **v3's lineage recall.** Lymphoid 78.3% and myeloid 98.9%: about a fifth
     of lymphoid cells land in non-lymphoid classes.
   - **V2 separates lineages almost perfectly.** Lymphoid recall is 98.5% and
     myeloid 93.1%, with B recall at 96.1%.
   - **V2's weakness is CD8T.** It calls 63% of CD8T cells CD4T.
   - **scANVI's best arm, shared kNN.** Lymphoid recall is 81.7% and myeloid
     94.0%, with CD8T recall at 29.3%.
4. **v3 overuses "macrophage".** It calls 9.6% of all cells macrophage, a
   class absent from blood. Under the protocol's mapping that counts as
   "other" (owner decision, fixed before scoring). V2 uses it for 1.2%. Even
   so, v3's monocyte recall is 84.1%.
5. **DC is essentially unrecognised by every method.** DC recall is at most
   8.9% (V2, nearest centroid), and 0% for every scANVI arm. The reference
   holds 1 myeloid DC and 29 plasmacytoid DC cells out of 85,233, so the DC
   classes barely exist to be matched. True DCs are mostly called monocyte
   (76% for v3, 45% for V2).
6. **scANVI depends on its gene space.** With the 1,975 unmeasured genes
   zero-filled, it is near chance: 21.4% at best, predicting neutrophil,
   basophil or erythrocyte (none of them PBMC types) for about half of all
   cells. Restricted to the 932 measured genes, it reaches 47.8%. Its best
   arm's native classifier (37.7%) trails its shared-kNN rule by 10 points.

### Exploratory, added after results: five types (T = CD4T + CD8T)

Added on the owner's instruction after the six-type results were known
(amendment 2). It does not replace the primary metric. Balanced accuracy
over T, NK, B, monocyte and DC; the source is
[exploratory_5type_summary.csv](fulcher2026/exploratory_5type_summary.csv).

| Model | Nearest centroid / scANVI native | Shared kNN | T recall (NC / kNN) |
|---|---|---|---|
| V2 | 65.5 ± 2.6 | 63.0 ± 3.2 | 81.7 / 83.4 |
| v3 | 46.8 ± 3.8 | 46.8 ± 3.7 | 67.7 / 67.6 |
| scANVI, `log2_measuredgenes` | 42.0 ± 1.8 | 53.9 ± 1.1 | 59.4 / 60.1 |
| scANVI, `log2` | 23.5 ± 13.4 | 24.3 ± 3.5 | 16.4 / 39.9 |
| scANVI, `log2_cellmedian` | 21.2 ± 11.6 | 21.1 ± 9.6 | 28.6 / 24.2 |

Merging CD4T and CD8T raises every model's score. It doesn't change the
ordering under either rule. Under the shared kNN rule it is V2, then
scANVI's best arm, then v3. Comparing our product rule with scANVI's native
classifier, it is V2, then v3, then scANVI.

### Product check: the Fulcher upload through the running service

`benchmark/fulcher2026_product_check.py` POSTs the upload exactly as a user
would, with default settings: the FragPipe table as written, filtered to the
1,275 QC-passed cells. It records only what comes back, never an accuracy
([product_check.json](fulcher2026/product_check.json)).

**Before the interim fix, when the default restricted labels to
macrophage/monocyte.** The service returned only macrophage (43.5%) or
monocyte (44.3%), and abstained on the rest (12.2%). By the authors'
annotation, 741 of the 1,251 labelled cells are lymphoid. The same file
also gave different abstentions on a repeat POST (15.6%), because the Stage 5
calibration subset was unseeded.

**After the interim fix.** The restriction is now opt-in, via the
`restrict_to_supported_classes` request field, and the calibration subset
is seeded from a hash of the upload. The committed check now shows the new
default. Two POSTs of the same file return identical records, and the
output is no longer restricted:

| Returned | Share of 1,275 cells |
|---|---|
| abstained: ambiguous between classes | 40.4% |
| abstained: no confident label | 4.5% |
| abstained: outside supported region | 3.5% |
| cytotoxic lymphocyte (CD8 T / NK fallback) | 20.5% |
| CD8 T | 11.5% |
| neutrophil | 6.1% |
| macrophage | 5.4% |
| B cell | 2.6% |
| NK cell | 2.3% |
| classical monocyte, monocyte | 2.1% |
| regulatory T, plasma cell, myeloid DC, mature NK T | 1.1% |

Lymphoid cells now get lymphoid labels, and four of the five confusable
pairs can be reached again. The result is still far from usable:

- **Almost half the cells abstain,** mostly because their conformal sets
  span several of the 22 classes.
- **Monocytes are almost never called monocyte.** By the authors'
  annotation, 36% of cells are monocytes. The service labels 2.1% of cells
  monocyte and sends the rest to neutrophil, macrophage or abstention.

This is v3, the served model. NB2's decision rule, recalibrated abstention
and conformal, and the v3.1 encoder are the planned fixes. This check
reports composition only. It is not scored, and Fulcher is development data
now.

### Decision taken

V2 is selected as the v3.1 candidate encoder. v3 stays served until three
things are in place: the NB2 decision rule, recalibrated abstention and
conformal calibration, and the NB4 export.

### Still open from this evaluation

- CD4T/CD8T separation (V2, and scANVI) and lymphoid placement (v3) on real
  protein data.
- DC is effectively unsupported by the reference.
- scANVI's native classifier trails its own kNN rule by 10 points on
  Fulcher. It is not investigated here.

## Two protocols, not a chosen one

Per the repository owner's explicit instruction: the choice between the
shared kNN-classifier rule and native nearest-centroid is **not** made
based on which one favors "ours" on this SCoPE2 evaluation set — doing so
would be tuning a product decision on the test set. Both are reported for
every method, in both tables above, and no recommendation is made here
about which one the live service should use. The same non-tuning
discipline applies to the pool-first-vs-post-hoc-masking kNN choice above.

## What's still open

- **Why v3's SCoPE2 restricted-regime performance varies so much by seed
  (59.04–88.40% balanced, shared kNN rule) is not explained here** — only
  measured. `v3_seed0` shipping was not a principled choice among the five;
  it is simply the seed that was trained first. Not addressed by Track D;
  a real open question for whichever notebook takes it up next.
- No baseline besides scANVI has been run more than once; MaxFuse's random
  batching and scGLUE's minibatch shuffling both have their own
  un-quantified run-to-run variance (see
  [known-limitations.md](known-limitations.md)).
- **scANVI training on this hardware (Apple MPS) is not fully
  reproducible even with an explicit seed** — seed 0's re-run this round
  landed meaningfully differently from its original run (see the
  scANVI-across-seeds section). Seeds 1 and 2 reproduced closely. Not
  investigated further here; worth knowing before treating any single
  scANVI seed's number as fixed.
- `web/data/atlas_manifest.json`'s `benchmark.rows` is untouched — still `[]`,
  `status: "pending"` — regardless of everything above. Nothing here is
  wired into the live site.
