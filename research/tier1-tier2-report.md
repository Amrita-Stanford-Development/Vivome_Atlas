# VivOME v3 Improvement Plan: Label-Free scRNA-seq to MS Proteomics Cell Type Transfer

Research report, 2026-09-24. Source for the Tier 1 and Tier 2 items in
`research/roadmap.md`.

> **Status note, added 2026-09-25.** Three findings from after this report change how
> it should be read. None of them contradicts it, but they reorder the work.
>
> 1. **Per upload z scoring is a root cause the report does not cover.** T1 NB1 showed
>    that on RNA alone, a SCoPE2 like upload loses 15.6 points of unrestricted balanced
>    accuracy from preprocessing, and single cell type uploads score 11.2 percent.
>    About half of the "54.2 percent distractor contamination" below is this artifact,
>    not biology. T1 NB1b addresses it before T1-1 is built.
> 2. **The live service had preprocessing defects** (a ReLU where the model uses GELU,
>    now fixed; a smoothing graph on raw values; no log transform of linear
>    intensities; a coverage floor refusing 79 to 100 percent of real MS cells). These
>    come before any accuracy work.
> 3. ~~**The lead over scANVI is now established on SCoPE2**: paired bootstrap CIs exclude
>    zero on every seed (+9.1 to +14.4 points restricted, +21.7 to +32.7 unrestricted,
>    shared kNN rule).~~ **Corrected 2026-09-29 (Track D, T1 NB1d):** that lead holds for
>    the shipped checkpoint `v3_seed0` only. Across five v3 seeds, scANVI is ahead under
>    the restricted shared kNN rule in 12 of 15 seed pairings; v3 reliably leads only
>    unrestricted (12 of 15). See `research/todo.md` §5. Any claimed lead still needs at
>    least two more MS datasets, as the report says.
>
> Published v3 RNA to RNA numbers (95.5 / 74.8) included training cells; the honest
> test cell numbers are 93.2 / 65.7. See `research/todo.md` for current verified numbers.

---

## Summary

I've put together a ranked plan for getting VivOME v3 to a deployable, state-of-the-art level. The biggest gain doesn't need a new encoder. Of your SCoPE2 cells, 54.2% currently land in reference classes that have no protein cells. If each upload first estimates, without labels, which classes are actually present, balanced accuracy should close most of the gap between 31.08% (all 22 classes) and 79.79% (restricted to the supported pair). v3 stays frozen and the zero-target-label claim holds.

**Tier 1 (v3 frozen, a few days of CPU work each):**
- **Class-set estimation:** replace the hardcoded two-class restriction with a per-upload estimate of which classes are present. It combines calibrated prior estimation (EM/MLLS with bias-corrected temperature scaling) with a check that each class is supported by a cluster in the upload. The prior estimation alone isn't enough, because it assumes the modality gap doesn't change p(x|y).
- **Abstention:** your current 1-nearest-neighbour cosine score is saturated (0.997–0.999 for unseen cells vs 1.000 for seen), which drives the 80.2% abstention rate. Switch to k-nearest-neighbour distance on the pre-projection features, with the threshold calibrated on RNA masked to each upload's own genes.
- **Conformal prediction:** calibrating on the model's own predictions is circular, which explains the 33.7% coverage. Rebuild it on held-out masked RNA with label-shift weighting and per-class sets.
- **Smaller items:** a kNN decision rule inside the supported classes, gene masking by RNA–protein concordance using external data only, optional restricted self-training, and deployment hardening (pinned Ensembl IDs, frozen ID mapping table, ONNX export, FAISS, a model card).

**Tier 2 (retraining on a single GPU, weeks):**
- **Class-weighted adversarial training plus self-supervised pretraining on unlabeled MS proteomics.** This is aimed at the 98.99% modality probe and the 0.76% macrophage recall.
- **An RNA→protein bridge learned from external paired data:** nanoSPLITS and nanoSPINS, plus CITE-seq for surface proteins only.
- **A wider reference:** multi-tissue Tabula Sapiens under a Cell Ontology hierarchy.
- **Later options:** a one-vs-all open-set head, and a set encoder that uses frozen ESM2 gene embeddings.

**Caveats:**
- I found no published accuracy figure for unpaired scRNA-seq → MS single-cell proteomics label transfer. A rigorous benchmark would itself be publishable, but your ~5-point lead over scANVI shouldn't be claimed yet. It needs bootstrap confidence intervals across at least three MS datasets.
- Expected Tier 2 gains aren't quantified anywhere for RNA→MS, so the plan gives go/no-go criteria rather than predictions.
- Some dataset cell counts and accessions weren't verified and should be checked against the papers.

---

# VivOME v3 → deployable state of the art: ranked improvement plan for label-free scRNA-seq → MS-proteomics transfer

The biggest improvement available is not a new encoder. It is to stop scoring the 20 distractor classes: estimate, without labels, which reference classes are present in each upload, then run assignment, conformal prediction and abstention inside that estimated label space. Of your SCoPE2 cells, 54.2% land in classes that have no protein cells, while 99.1% of the cells landing in the supported pair are correct. Principled label-space restriction therefore recovers most of the gap between 31.08% (22-class) and 79.79% (restricted) balanced accuracy without touching v3 weights, and it keeps the zero-target-label claim intact. After that, the gains come from (i) fixing calibration and abstention, which are currently invalid by construction, and (ii) a Tier 2 retrain that learns an RNA→MS bridge from external paired data and unlabeled MS proteomics. That retrain is what should move macrophage recall (0.76%) and the modality probe (98.99%). One competitive fact matters here: I found no published accuracy figure for unpaired scRNA-seq → MS single-cell proteomics label transfer. The literature pairs cells (nanoSPLITS) or clusters within modality. So a rigorous benchmark is itself a publishable contribution, and "state of the art" needs to be defined by your own CI-backed benchmark.

## TL;DR

- **Do first (Tier 1, v3 frozen, days of work):** (1) replace the hardcoded 2-class restriction with label-free label-space estimation, using EM/MLLS prior estimation with bias-corrected calibration plus a cluster-support test; (2) replace max-cosine-to-one-cell abstention with k-NN-distance OOD on pre-normalization features, calibrated on RNA masked to the upload's mask; (3) rebuild conformal calibration on RNA held-out cells, not on the model's own pseudo-labels, with label-shift weighting and class-conditional sets. All three preserve the claim.
- **Then (Tier 2, single GPU, weeks):** retrain with (a) a bridge learned from external paired scRNA+MS cells (nanoSPLITS/nanoSPINS) and CITE-seq; (b) self-supervised and partial-domain-adversarial pretraining on unlabeled MS datasets, with class weights from the Tier 1 estimator; (c) a wider reference that fixes the macrophage class, using multi-tissue Tabula Sapiens under a Cell Ontology hierarchy. None of these uses target protein labels.
- **Do not:** re-run moment matching, OT with strict marginals, unrestricted 22-class self-training, or pseudo-label conformal calibration. All of these failed here for identifiable reasons. Treat "lead over scANVI" as unproven until you have bootstrap CIs on at least three MS datasets.

## Key Findings (what the evidence says)

1. **Your failure is a partial domain adaptation problem, not only a modality gap.** Partial DA is the setting where the target label space is a subset of the source's. The canonical failure there is "negative transfer", where target samples are misclassified into source-only classes. BA3US (ECCV 2020) is explicit about this. That is exactly your 54.2% distractor contamination. The standard fix since PADA (Cao et al. 2018) is to compute class weights "by simply averaging the classifier prediction on all target samples" and down-weight source-only classes. BA3US adds balanced augmentation and complement-entropy suppression.
2. **Label-shift estimation can be done without target labels and without retraining.** Saerens-style EM, rebranded MLLS (Garg et al. 2020), is "hard-to-beat" when combined with bias-corrected temperature scaling (BCTS) (Alexandari, Kundaje & Shrikumar, ICML 2020). BCTS/vector scaling gave the best overall performance in their comparisons. LaSCal (NeurIPS 2024) extends this to label-shift calibration without target labels. The caveat: these methods assume p(x|y) is unchanged, and your modality gap violates that. So they must be combined with a structural support test (below) rather than trusted alone.
3. **Test-time adaptation collapses under label shift and needs a stable label space.** SAR (ICLR 2023) documents collapse to "assigning the same class label for all samples" under imbalanced label shift. It finds batch-agnostic norms (your LayerNorm) more stable but still failure-prone. DART (2024) reports that TENT and SAR "suffer significant performance degradation due to label distribution shifts." This explains why your four self-adaptation methods failed in the 22-class regime. It also explains why self-training worked (63→85%) in the old 2-class regime.
4. **Reliable-cell progressive bridging is the most transferable single-cell mechanism.** scBridge (Nat Commun 2023) iterates between identifying target cells "that have smaller omics differences" and integrating them with the reference. It is supervised on RNA and label-free on the target, which is exactly your setting. The OT label-transfer method scOT-LT (Briefings in Bioinformatics, bbag334) reported that scBridge had much lower macro-F1 than scOT-LT on RNA→ATAC (0.541 vs 0.715; P = 1.47e−4). So no single mechanism dominates across modalities, and your own finding that OT loses on protein is consistent with modality-dependent behaviour.
5. **k-NN OOD beats parametric distances in compressed embedding spaces.** Sun et al. (ICML 2022) show non-parametric k-th-nearest-neighbour distance "substantially reduces the false positive rate (FPR@TPR95) by 24.77%" versus a Mahalanobis-based baseline on ImageNet. It makes no Gaussian assumption. Your 1-NN max-cosine score (unseen 0.997–0.999 vs seen 1.000) saturates because of L2-normalized, contrastively trained compression. k>1 distances on the pre-projection features are the direct fix.
6. **Conformal under shift has a recipe, but no guarantee under your specific shift.** Podkopaev & Ramdas (UAI 2021) show label shift "hurts UQ, by showing degradation in coverage and calibration," and give reweighted conformal procedures that use unlabeled target data. Conformal for scRNA annotation with OOD detection has been published (Bioinformatics 2025, btaf521: classwise and cluster taxonomies, APS/RAPS scores). Calibrating on the model's own predictions, as you do now, is circular and has no validity guarantee. That is why coverage is 33.7%.
7. **Paired scRNA+MS data exist but are small.** nanoSPLITS (Fulcher et al., Nat Commun 2024) splits single-cell lysates for scRNA-seq and MS. It reports 95 human islet cells with both modalities, plus 26 C10 and 23 SVEC paired cell-line cells, with mRNA–protein cross-correlations "most … within the range of 0.35–0.45". nanoSPINS (Lab Chip 2026) adds TMTpro-multiplexed paired throughput. These are enough to learn gene-level bridge statistics and to validate, not to train a deep translator end-to-end.
8. **RNA–protein discordance is systematic and gene-specific.** Jiang et al. (Cell 2020) quantified proteins from 12,627 genes across 32 GTEx tissues (PRIDE PXD016999). They found many ubiquitous transcripts encode tissue-specific proteins, and that concordance varies by pathway. The 2025 MCP study "High-Throughput Single-Cell Proteomics of In Vivo Cells" summarizes that complexes (ribosome, spliceosome, electron transport chain, proteasome) show low RNA–protein correlation, while transcriptionally regulated pathways (interferon) show high correlation. This is usable as a per-gene weighting prior.
9. **Foundation models: use their gene tokens, not their weights.** UCE represents genes by ESM2 protein embeddings (5,120-d), which is naturally modality-shared. But UCE is a 33-layer, 650M-parameter model trained "for 40 days across 24 A100 80 GB GPUs". Training it or fine-tuning it is out of scope on Colab. Inference, or the smaller 4-layer variant, is feasible, as is borrowing frozen ESM2 gene embeddings for your own small set encoder. Bendidi et al.'s 2024 benchmark (arXiv 2410.13956) found scVI and PCA "far better suited" than existing foundation models for perturbation analysis, so do not assume a foundation model beats your task-specific encoder.
10. **MS-proteomics-native embedders exist.** scPROTEIN (Nat Methods 2024) does graph-contrastive embedding, denoising and batch removal for SCP data, with code at TencentAILabHealthcare/scPROTEIN. It is a candidate SSL recipe and baseline for the unlabeled-MS pretraining stage. It is not a cross-modal label-transfer tool.

## Tier 1: inference-side, v3 frozen (ranked by gain ÷ effort)

### T1-1. Label-free label-space estimation ("which of the 22 classes are in this upload?")

- **What:** A three-part estimator run per upload.
  - (a) Calibrate v3's logits on RNA held-out cells masked to the upload's own gene mask, using BCTS (temperature + per-class bias).
  - (b) Run EM/MLLS on the upload to estimate class priors π̂.
  - (c) Apply a structural support test. Cluster the upload on its own kNN graph (you already build k=15 on PCA-50). Compute each cluster's mean embedding. Mark a class as supported only if π̂_c > ε *and* at least one query cluster assigns it top-1 with a margin that beats the second class. Then restrict candidate labels to supported classes, and optionally restrict hierarchically: lineage first, then type.
  - Output the supported set in the API response so users can see and override it (user override is metadata, not training).
- **Targets:** 54.2% distractor contamination; hardcoded restriction; 45.37% acc / 31.08% balanced (22-class) vs 86.17% / 79.79% (restricted).
- **Expected gain:** Upper bound is the restricted number, 79.79% balanced; the oracle-threshold ceiling is 85.97%. Realistically, expect most of the ~49-point gap if the estimator selects {monocyte, macrophage}. EM alone is risky because macrophage cells currently score into distractors (recall 0.76%). The cluster-support test is what should rescue macrophage, since the macrophage-vs-monocyte AUC of 0.928 shows the ranking is right. Literature: MLLS+BCTS is "hard-to-beat" (Alexandari 2020); PADA-style averaged-prediction class weights are the standard partial-DA remedy.
- **Effort:** Low (2–4 days). **Compute:** CPU.
- **Data:** RNA reference + the unlabeled upload. Within allowed sources.
- **Preserves claim:** **Yes.** No protein labels are used; target statistics are unlabeled.
- **Validation you must add:** Simulate uploads by subsampling RNA held-out cells with random class subsets (1–8 classes), masked to real MS coverage. Report precision and recall of the estimated class set. Then report on SCoPE2, Fulcher and PBMC240 using ground truth only for scoring.
- **Papers/code:** Alexandari et al. 2020 (arXiv 1901.06852; code in the "abstention" package by kundajelab); Garg et al. 2020 "A unified view of label shift estimation"; Lipton et al. 2018 BBSE; PADA (arXiv 1808.04205); BA3US (github.com/tim-learn/BA3US).

### T1-2. Replace abstention with k-NN distance OOD on pre-projection features, plus a coverage-aware threshold

- **What:**
  - Compute OOD scores on the 512-d hidden layer before the 128-d LayerNorm + L2 projection, where compression is weaker. Use k-th-NN distance (k≈10–50) to the reference with FAISS, following Sun et al. 2022.
  - Also compute relative Mahalanobis: class-conditional minus background Mahalanobis.
  - Calibrate the threshold as a conformal p-value against RNA held-out cells masked to *the upload's own mask*, not a single global 0.9779. Target a user-chosen false-abstention rate (e.g., 5%) on in-distribution RNA.
  - Separate two abstention reasons in the API: "no support in reference" (OOD) and "ambiguous between supported classes" (conformal set size > 1).
- **Targets:** 80.2% abstention; saturated scores (unseen 0.997–0.999 vs seen 1.000).
- **Expected gain:** In ImageNet benchmarks k-NN OOD cut FPR@TPR95 by 24.77% vs a Mahalanobis baseline. For you, the main effect is converting a saturated 1-NN cosine into a spread-out score. Expect abstention to fall to whatever rate you set on masked RNA (e.g., 5–20%). The honest caveat: cross-modal cells are genuinely shifted, so a cross-modal query will look "OOD" to a detector trained on RNA. That is why abstention must be computed *after* label-space restriction and reported per reason.
- **Effort:** Low (2–3 days). **Compute:** CPU; FAISS on 85k × 512 fits easily in memory.
- **Data:** RNA reference only. **Preserves claim:** **Yes.**
- **Papers/code:** Sun et al. ICML 2022 (github.com/deeplearning-wisc/knn-ood); Lee et al. 2018 Mahalanobis; Ren et al. 2021 relative Mahalanobis.

### T1-3. Rebuild conformal prediction so it has a defined guarantee

- **What:**
  - Stop calibrating on the model's own predictions; it is circular.
  - Calibrate split-conformal scores (APS/RAPS, class-conditional/Mondrian) on RNA held-out cells masked to the upload's gene mask and passed through the same smoothing.
  - Reweight calibration scores by the estimated priors π̂/π_train from T1-1 (Podkopaev & Ramdas label-shift conformal).
  - Restrict the label set to supported classes.
  - Report two coverages in the paper: (i) guaranteed coverage on masked RNA; (ii) *empirical* coverage on SCoPE2/Fulcher/PBMC240, scored with ground truth that is never used for calibration.
  - State plainly that the p(x|y) modality shift breaks the formal guarantee on protein. Show the empirical gap as a diagnostic.
- **Targets:** 33.7% empirical coverage vs 90% target; 36.2% with confidence filtering.
- **Expected gain:** On masked RNA, coverage becomes ≥90% by construction. On protein, coverage should rise substantially once the label set is restricted, because 99.1% of supported-pair cells are correct. The macrophage-class coverage will stay low until Tier 2 fixes macrophage placement. Class-conditional conformal will expose this honestly instead of hiding it in a marginal average.
- **Effort:** Low–medium (3–5 days). **Compute:** CPU.
- **Data:** RNA reference + unlabeled upload. **Preserves claim:** **Yes.**
- **Papers/code:** Podkopaev & Ramdas UAI 2021 (PMLR v161); Tibshirani et al. 2019 weighted conformal; Angelopoulos et al. 2021 RAPS; "Conformal inference for reliable single cell RNA-seq annotation" (Bioinformatics 2025, btaf521; uses TorchCP); LaSCal (NeurIPS 2024) for label-free recalibration under label shift.

### T1-4. Cluster-level and kNN decision rule inside the supported label space

- **What:** Within the supported set, assign labels by a kNN vote (k≈15–30, distance-weighted) against *reference cells of supported classes only*. Then smooth labels over the query's own kNN graph (label propagation on the graph you already build). Keep nearest-centroid as the fallback. Do not use OT unless the marginals are relaxed and estimated (see Risks).
- **Targets:** The nearest-centroid vs kNN discrepancy (kNN 40.4 > centroid 38.3 on the adapted embedding). The unverified "large kNN gain" reconstruction. The headroom between 79.79 and the 85.97 oracle.
- **Expected gain:** Bounded: roughly 0–6 balanced-accuracy points inside the restricted space, since the oracle ceiling is 85.97. Verify on the native harness with five seeds and bootstrap CIs before claiming.
- **Effort:** Low (1–2 days). **Compute:** CPU/FAISS. **Data:** None new. **Preserves claim:** **Yes.**

### T1-5. RNA–protein-concordance gene masking at inference (exploits your masking-trained encoder)

- **What:** v3 was trained with uniform random masking (coverage 0.15–0.6), so *dropping* genes at inference is in-distribution. Build a per-gene concordance score from *external* sources only, and mask the bottom-concordance genes before encoding. Sources: nanoSPLITS paired single cells; GTEx tissue RNA vs protein (Jiang 2020, PXD016999); CPTAC tumor RNA–protein correlations; Wang et al. 2019 MSB tissue atlas. Tune the dropout fraction on masked RNA plus *other* MS datasets, never on the dataset you report.
- **Targets:** Modality gap on shared features; macrophage latent cosine 0.19 vs monocyte 0.830.
- **Expected gain:** Uncertain, likely modest (a few points), but nearly free. Evidence that concordance is gene/pathway-specific is strong (low for ribosome/proteasome complexes, high for transcriptionally regulated pathways). Your moment-matching failure suggests value-space transforms hurt, whereas *feature selection* sidesteps that.
- **Effort:** Low–medium (3–5 days, mostly ID mapping). **Compute:** CPU.
- **Data:** External paired/tissue data. Within allowed sources.
- **Preserves claim:** **Yes**, provided no concordance statistic is computed from the evaluation dataset. **Leakage warning:** the SCoPE2 paper includes 10x scRNA-seq of the same U-937 system. Using it to choose genes would leak target-domain information into a SCoPE2 benchmark. Keep it for analysis only.

### T1-6. Label-space-restricted, stable self-training (retry, now correctly framed)

- **What:** Re-run class-balanced self-training *only* on the supported label space from T1-1, scBridge-style:
  - Select "reliable" query cells (small reference distance, high margin, cluster-consistent).
  - Update only LayerNorm affine parameters, or a small adapter (SAR's finding: LN-based adaptation is more stable).
  - Keep an anchor penalty to v3, and stop when the RNA-masked accuracy drops by more than 1 point.
  - This is inference-time adaptation per upload, and it breaks the "single forward pass" API. Offer it as an optional asynchronous "adapt" mode, versioned separately.
- **Targets:** The four failed adaptation methods (best +5.59) that were all run unrestricted, against the earlier 63→85% success in a 2-class regime.
- **Expected gain:** Your own history is the best evidence: +22 points in the old 2-class setting. In the current regime, gains above the 79.79 restricted baseline are plausible but unproven. Keep your 60%-style kill threshold, now defined on restricted balanced accuracy.
- **Effort:** Medium (1 week). **Compute:** Single GPU (Colab) is fine; a single upload is at most thousands of cells.
- **Data:** Unlabeled upload. **Preserves claim:** **Yes.** Zero protein labels; pseudo-labels are model-derived.
- **Papers/code:** scBridge (Nat Commun 2023); SAR (github.com/mr-eggplant/SAR); NOTE (prediction-balanced memory); DART (label-shift-aware refinement, 2024).

### T1-7. Deployment hardening (required for a web service, independent of accuracy)

- **Gene IDs:** Key the 9,002-feature space on Ensembl gene IDs with a pinned release, plus HGNC IDs. Freeze a versioned UniProt→Ensembl mapping table shipped with the model instead of calling MyGene at runtime; this fixes the symbol drift. Accept symbols, UniProt accessions or Ensembl IDs on input, and report unmapped and ambiguous IDs back to the user.
- **Input validation:** Enforce a coverage floor. Your masking results show 91.9% RNA accuracy even at 18.4% coverage, so set a hard floor around 10–15% of features and a soft warning below 18%. Also enforce minimum cell count (for per-upload stats such as z-scoring, kNN smoothing and EM, require ≥50–100 cells) and value-scale checks (log vs linear, TMT ratio vs intensity).
- **Serving:** Export the encoder to TorchScript or ONNX; it is a 20M-parameter MLP with sub-millisecond per-cell latency on CPU. Use a FAISS IndexFlatIP/HNSW over reference features for k-NN/OOD. The per-upload steps (EM, clustering) are fast enough to remain synchronous for ≤10k cells.
- **Governance:** Publish a model card with training data, class list, coverage-stratified accuracy, known failure modes (macrophage, distractors) and the claim statement. Semantic-version the model and mapping table. Hash inputs and outputs for reproducibility, log per-upload coverage, supported-class sets, abstention rates and OOD-score distributions for drift monitoring. Comparable services follow this pattern: Azimuth ships versioned references with QC mapping scores, CellTypist ships versioned model files, and scArches/scvi-hub ship reference models for query mapping.
- **Preserves claim:** **Yes.**

## Tier 2: retraining / re-architecture (ranked by gain ÷ effort)

### T2-1. Partial-domain-adversarial + self-supervised training on unlabeled MS proteomics

- **What:** Retrain ModulePoolEnc with the RNA supervised losses unchanged, plus three additions:
  - (a) A masked-value reconstruction or contrastive SSL objective on pooled *unlabeled* MS datasets. scPROTEIN is a reference recipe. Candidate data: SCoPE2 MSV000083945, plexDIA MSV000089093, Bubis PXD049412, Chip-Tip PXD049211/PXD049181, Petrosius MSV000095333, K562 sets.
  - (b) A domain discriminator on the 128-d latent with a gradient-reversal layer, *class-weighted* PADA/BA3US-style. Source classes are weighted by the Tier 1 estimated target priors so that distractor classes are not pulled toward protein cells.
  - (c) Hold out entire MS datasets (leave-one-dataset-out) for evaluation.
- **Targets:** Modality probe 98.99% ± 0.28 (representations modality-specific); macrophage cosine 0.19; distractor contamination 54.2%.
- **Expected gain:** This is the lever for the 22-class unrestricted problem and for macrophage placement. The literature is clear that unweighted adversarial alignment causes negative transfer in partial settings, while class-weighted versions (PADA, BA3US) fix it. Your own baselines show unweighted alignment methods at chance. Gains are unquantified for this modality. Set success as a probe drop below ~80% with RNA-masked accuracy within 1 point of v3, and macrophage recall above 30% on SCoPE2 in a leave-SCoPE2-out run.
- **Effort:** Medium–high (2–4 weeks). **Compute:** Single GPU is fine; 20M parameters on about 85k RNA cells plus a few thousand MS cells.
- **Data:** Unlabeled MS (allowed). **Preserves claim:** **Yes**, as long as no target labels are used for model selection. Use RNA-masked validation and leave-one-dataset-out on *other* MS sets. Also report hyperparameter selection honestly: Salvador et al.'s 2022 reproducibility study of partial DA (arXiv 2210.01210) found that without target labels for model selection, accuracy drops by up to 30 percentage points.

### T2-2. Learn the RNA↔MS bridge from external paired data and train on "pseudo-protein" RNA

- **What:**
  - Use nanoSPLITS paired cells: 95 human islet cells with both modalities (MSV000093330/GSE247519 among its deposits), 26 C10 + 23 SVEC mouse cell-line pairs, and the nanoSPINS TMTpro paired sets. Fit a low-capacity, per-gene RNA→protein transform (gene-wise affine or monotone spline on ranks) plus an MS noise model: intensity-dependent missingness (MNAR), TMT ratio compression and carrier effects.
  - Add CITE-seq (Hao et al. 2021: 161,764 cells with 228 antibodies + 49,147 cells with 54 antibodies, GSE164378) *only* for the surface-protein subset, because antibody panels cover about 1–3% of your 9,002 features and are antibody-derived, not MS.
  - Then augment RNA training cells with "pseudo-protein views" generated by the bridge, and add a consistency loss between each RNA view and its pseudo-protein view (an extension of your existing two-view consistency loss).
- **Targets:** Modality gap (probe 98.99%); macrophage cosine 0.19; PBMC240 lineage accuracy 43.44% (~chance).
- **Expected gain:** Plausible but unproven, and the data are small. With about 144 paired cells, fit gene-level statistics, not a deep translator. Deep translators (BABEL, scTranslator, sciPENN, totalVI) are designed for antibody panels or large paired corpora and will overfit here. This is why "per-gene transform + noise model" is the recommended form. Your earlier finding that detection-pattern masking lost to uniform masking suggests keeping *masks* uniform and applying the bridge to *values*.
- **Effort:** Medium (2–3 weeks). **Compute:** Single GPU.
- **Data:** External paired data (allowed). **Preserves claim:** **Yes**: the bridge comes from external studies, and the target stays unpaired and unlabeled. The paper must state that the bridge includes no cells from any evaluation dataset, and that mouse cell-line pairs are used only for gene-level statistics via orthologs.

### T2-3. Widen and restructure the RNA reference to fix macrophage (and future non-blood uploads)

- **What:**
  - Add Tabula Sapiens macrophage and monocyte populations from other tissues (e.g., lung, spleen, bone marrow, liver) under a Cell Ontology hierarchy: a parent "macrophage" node with tissue-resident children kept separate. Train with hierarchical cross-entropy.
  - Predict at the deepest level supported by confidence, and report the parent when children are ambiguous; this generalizes your hand-picked 6-pair fallback.
  - Add in vitro monocyte-derived or PMA-differentiated macrophage scRNA-seq *from studies other than your benchmarks* as a separately labelled "in vitro macrophage-like" node. PMA-U937 cells are a differentiated cell-line model, not tissue-resident macrophages, and merging them into tissue macrophage labels would be biologically wrong.
- **Targets:** RNA macrophage recall 0.504 / 75.8%; protein macrophage recall 0.76%; cosine 0.19.
- **Expected gain:** Better RNA-side macrophage separability is a prerequisite for any protein-side improvement. Expect gains at the RNA level first; cross-modal gains depend on T2-1/T2-2.
- **Effort:** Medium (1–2 weeks, mostly curation). **Compute:** Single GPU; a few hundred thousand cells fits in Colab Pro RAM if you use sparse matrices or backed AnnData.
- **Data:** More labeled scRNA-seq (allowed). **Preserves claim:** **Yes.**

### T2-4. Open-set classifier head (one-vs-all) so rejection is learned, not thresholded

- **What:** Add OVANet-style one-vs-all heads alongside the softmax head. OVANet learns the known/unknown threshold from source data, using the idea that "a minimum inter-class distance in the source domain should be a good threshold." Use the OVA outputs as per-class support scores for T1-1 and as an abstention signal for T1-2.
- **Targets:** Distractor contamination; saturated OOD scores; 80.2% abstention.
- **Expected gain:** Moderate. OVANet was stable across openness levels where ROS and DANCE degraded. Its open-set entropy-minimization step uses unlabeled target data, which is allowed, but gate it behind the same stability rules as T1-6.
- **Effort:** Low–medium on retrain. **Compute:** Single GPU. **Preserves claim:** **Yes.**
- **Code:** OVANet (Saito & Saenko, ICCV 2021; arXiv 2104.03344).

### T2-5. Gene-token set encoder with frozen ESM2 gene embeddings (v4 architecture option)

- **What:** Replace the fixed 9,002-slot input with a set/transformer or DeepSets encoder over (gene token, value) pairs. Gene tokens come from frozen ESM2 protein embeddings, as UCE does, so that any panel, any ID system and genes outside the 9,002 can be encoded. Keep module pooling as an inductive bias (module membership as an extra token feature).
- **Targets:** Symbol drift and fixed feature space; generalization to new MS panels (TMT vs DIA vs Astral with different protein sets).
- **Expected gain:** Mainly robustness and extensibility, not guaranteed accuracy. Foundation-model benchmarks repeatedly find strong simple baselines. Do not train UCE, scGPT, Geneformer or scFoundation from scratch: UCE alone required 24 A100s for 40 days. A 2–6-layer set encoder with frozen ESM2 tokens is Colab-feasible. As a baseline, embed RNA and MS with the released UCE (4-layer model for speed) and report its label transfer.
- **Effort:** High (3–6 weeks). **Compute:** Single GPU for a small model; ESM2 embeddings can be precomputed once (or downloaded with UCE). **Preserves claim:** **Yes.**
- **Code:** github.com/snap-stanford/UCE.

## Risks and what not to do (grounded in your failures)

| Don't | Why it failed here | Principled variant, if any |
|---|---|---|
| Moment-match protein distributions to RNA (skew/kurtosis) | It forces value distributions to match when the per-gene RNA→protein relationship differs by gene (concordance is gene- and pathway-specific). It distorts exactly the genes that carry signal. | Per-gene transforms learned from *external paired* cells (T2-2) or gene masking by concordance (T1-5), not global moments. |
| OT with strict or balanced marginals | Balanced OT forces mass onto all 22 classes, and the target contains 2, so it manufactures distractor assignments (72→47% collapse; 33.6% on protein). | Unbalanced OT only with target marginals from T1-1 and the support restricted; otherwise use kNN. |
| Self-training / TTA in the full 22-class space | Label-shift collapse is a documented TTA failure mode (SAR, DART). Pseudo-labels in distractor classes self-reinforce. | Restricted-space, reliable-cell, LayerNorm-only adaptation with an RNA anchor (T1-6). |
| Conformal calibration on model pseudo-labels (random or confidence-filtered) | Circular: the scores are conditioned on the model being right, so coverage has no meaning (33.7%, 36.2%). | Calibrate on masked RNA, reweight by estimated priors, report empirical protein coverage separately (T1-3). |
| Unweighted adversarial or unsupervised alignment | Your benchmark shows scGLUE, Harmony and MaxFuse at or near chance. Partial-DA theory predicts negative transfer when source-only classes are aligned. | Class-weighted partial DA (T2-1). |
| Hyperparameter tuning on SCoPE2 labels | Violates the claim and inflates results. | Tune on masked RNA and on *other* MS datasets (leave-one-dataset-out). |
| Using SCoPE2's companion 10x RNA or any benchmark dataset in the bridge | Target-domain leakage. | Keep it for post hoc analysis only. |
| Claiming SOTA over scANVI now | A ~5-point lead without CIs, on one 2-class dataset with rerun pending. | Paired bootstrap CIs across ≥3 MS datasets, identical decision rules for all methods. |

## Credible evaluation for Nature Communications

- **Protocol:** Leave-one-MS-dataset-out. Use identical preprocessing, label space estimation and decision rule for all methods (report native and harmonized rules, as you started). Run five training seeds × 1,000-cell-bootstrap CIs. Use paired tests (per-cell McNemar, or paired bootstrap on balanced accuracy).
- **Metrics:** Balanced accuracy and macro-F1 (22-class and estimated-label-space), class-set estimation precision/recall, selective risk–coverage curves (AURC), conformal coverage and set size per class, and OOD AUROC/FPR95. Add scIB-style biology-conservation and modality-mixing metrics for the embedding. Report FOSCTTM on nanoSPLITS paired cells (the only place a true pairing exists). Do not use FOSCTTM on unpaired sets.
- **Baselines:** scANVI/scArches, Seurat v5 (CCA and bridge integration with nanoSPLITS as the bridge), scJoint, scBridge, MaxFuse, scGLUE, Harmony + kNN, PCA + centroid, UCE zero-shot + kNN, CellTypist on RNA-masked input. The 2025 Nature Methods multitask benchmark (40 integration methods on 64 real and 22 simulated datasets, 14 of them diagonal RNA/ATAC methods) is the model for how reviewers expect such comparisons to look.
- **Datasets reviewers will expect:** SCoPE2 (the canonical macrophage/monocyte set), plexDIA (U-937 among three cell lines), at least one Astral/DIA primary-cell dataset, nanoSPLITS islets (paired, which allows a direct test of whether unpaired transfer recovers labels assigned via RNA of the same cell), and a primary PBMC MS set (your PBMC240/Fulcher). Label-free MS primary blood data remain the critical gap; Furtwängler et al. (Science 2025; scp-MS of >2,500 human CD34+ hematopoietic stem and progenitor cells integrated with scRNA-seq; data on Zenodo record 15554000) is worth obtaining.

## Datasets

| Dataset | Accession | Size | Platform | Cell types | Use |
|---|---|---|---|---|---|
| Specht et al. 2021 SCoPE2 | MassIVE MSV000083945 (also MSV000084660) | 1,490 cells; 3,042 proteins | TMT, isobaric carrier, Orbitrap DDA | U-937 monocytes, PMA macrophage-like | Primary benchmark; unlabeled SSL only in leave-SCoPE2-out folds |
| Derks et al. 2023 plexDIA | MassIVE MSV000089093 | Single cells from 3 lines (count to verify) | mTRAQ 3-plex DIA, DIA-NN | Melanoma WM989, PDAC HPAF-II, U-937 | Unlabeled SSL/DA; U-937 monocyte test (cross-platform) |
| Fulcher et al. 2024 nanoSPLITS | MassIVE MSV000089280, MSV000090828, MSV000093330; GEO GSE201575, GSE219047, GSE247519 | 95 islet cells paired (106 RNA, 126 MS); 26 C10 + 23 SVEC paired | Label-free nanoPOTS, Orbitrap, FAIMS; Smart-seq2 | Human islet types (9); mouse C10/SVEC | External bridge (T2-2); FOSCTTM; non-blood benchmark |
| Dawar et al. 2025/2026 nanoSPINS | See Lab Chip 2026 / bioRxiv 2025.10.20.681067 | Higher-throughput paired (TMTpro) | TMTpro MS + scRNA-seq | Two cell lines | Bridge augmentation |
| Bubis et al. 2025 | PRIDE PXD049412 | Single cells, count to verify; up to 5,300 proteins/cell | Orbitrap Astral, FAIMS, DIA | A549, H460, hPSC, trophectoderm | Unlabeled SSL (Astral domain) |
| Ye et al. 2025 Chip-Tip | PRIDE PXD049211, PXD049181; iProX PXD054944 | Up to 120 samples/day; >5,000 proteins/HeLa cell | Orbitrap Astral, nDIA, label-free | HeLa, spheroids, hiPSC, embryoid bodies | Unlabeled SSL |
| Petrosius et al. 2025 | MassIVE MSV000095333 | ≥8 cells/method; ~1,300 proteins in CD34+ BM | Orbitrap Astral WISH-DIA | HEK293, U937, primary CD34+ BM | Unlabeled SSL; primary hematopoietic test |
| Your PBMC240; Fulcher PBMC | Internal / per source | 237; 2,130 cells | Astral DIA; nanoPOTS | Primary PBMC | Primary-cell benchmark (weak labels: evaluate at lineage level) |
| Hao et al. 2021 PBMC CITE-seq | GEO GSE164378 | 161,764 cells, 228 Abs + 49,147 cells, 54 Abs | 10x CITE-seq/ECCITE | PBMC, 57 clusters | Surface-protein bridge; immune label hierarchy |
| Jiang et al. 2020 GTEx proteome | PRIDE PXD016999 | 12,627 genes, 32 tissues, 201 samples | TMT bulk | Tissues | Gene concordance prior (T1-5) |
| Tabula Sapiens (all tissues) | CELLxGENE / figshare | ~500k cells from 24 tissues (v1, Science 2022); >1.1M cells from 28 tissues (v2, Cell 2026) | 10x/Smart-seq2 | Multi-tissue incl. macrophages | Reference widening (T2-3) |

## Recommendations: prioritized roadmap

1. **Weeks 1–2 (Tier 1 core, v3 frozen):** T1-1 label-space estimator → T1-4 kNN rule → T1-3 conformal rebuild → T1-2 k-NN OOD. Validate on simulated RNA uploads, then report SCoPE2/Fulcher/PBMC240 with bootstrap CIs. Ship as API v3.1 with a "supported classes" field and two-reason abstention. Go/no-go: estimated class set on SCoPE2 = {monocyte, macrophage} without hardcoding; restricted balanced accuracy within 3 points of 79.79; abstention ≤25%.
2. **Week 2–3 (parallel):** T1-7 hardening (Ensembl IDs, frozen mapping, ONNX, FAISS, model card) and the harness rerun of the scANVI comparison with identical rules.
3. **Week 3–4:** T1-5 concordance masking and T1-6 restricted self-training as optional modes. Keep them only if they beat v3.1 on leave-one-dataset-out without touching evaluation labels.
4. **Weeks 4–8 (Tier 2, v4):** T2-3 reference widening + hierarchy, then T2-1 partial-DA + SSL on unlabeled MS, then T2-2 bridge augmentation. Evaluate leave-one-MS-dataset-out. Promote to v4 only if the modality probe falls clearly (target <80%), macrophage recall on held-out SCoPE2 rises above 30%, and RNA-masked accuracy holds.
5. **Later / optional:** T2-4 OVA head (cheap to add during the v4 retrain) and T2-5 set encoder with ESM2 tokens (the path to panel-agnostic v5).

## Caveats

- Expected gains for Tier 2 are not quantified in the literature for RNA→MS; the numbers above are targets and kill criteria, not predictions.
- Label-shift estimators assume p(x|y) is invariant, which the modality gap violates. T1-1's cluster-support test is a heuristic safeguard, not a guarantee.
- Conformal guarantees hold on masked RNA only; protein-side coverage is empirical.
- Several dataset details (plexDIA single-cell count, Bubis and Chip-Tip cell counts, the SCoPE2 10x GEO accession) were not verified and should be checked against the papers.
- I found no published accuracy for unpaired scRNA → MS single-cell proteomics label transfer. nanoSPLITS transferred labels via paired RNA from the same cells, so absence of evidence should be stated carefully in the paper ("to our knowledge").
- Only 2 of 22 classes have protein support in your data. Any 22-class claim remains untested until primary multi-lineage MS data (e.g., sorted PBMC) are obtained.

## Sources

1. arXiv — https://arxiv.org/abs/2003.02541
2. arXiv — https://arxiv.org/pdf/2210.01210
3. arXiv — https://arxiv.org/pdf/2211.04274
4. arXiv — https://arxiv.org/abs/1901.06852
5. Proceedings of Machine Learning Research — http://proceedings.mlr.press/v119/alexandari20a/alexandari20a.pdf
6. NeurIPS — https://proceedings.neurips.cc/paper_files/paper/2024/file/783c5986e1d6112cb4688d9b2105609a-Paper-Conference.pdf
7. arXiv — https://arxiv.org/abs/2509.04977
8. arXiv — https://arxiv.org/abs/2302.12400
9. arXiv — https://arxiv.org/html/2411.15204v1
10. PubMed Central — https://pmc.ncbi.nlm.nih.gov/articles/PMC10539354/
11. ICML — https://icml.cc/virtual/2022/spotlight/16494
12. Proceedings of Machine Learning Research — https://proceedings.mlr.press/v161/podkopaev21a.html
13. Oxford Academic — https://academic.oup.com/bioinformatics/article/41/10/btaf521/8257682
14. PubMed Central — https://pmc.ncbi.nlm.nih.gov/articles/PMC12506889/
15. Nature — https://www.nature.com/articles/s41467-024-54099-z
16. OSTI — https://www.osti.gov/pages/biblio/3409404-high-throughput-single-cell-proteomics-transcriptomics-from-same-cells-nanoliter-scale-spin-transfer-approach
17. RSC — https://www.rsc.org/suppdata/d5/lc/d5lc01008j/d5lc01008j6.pdf
18. ResearchGate — https://www.researchgate.net/publication/336365371_A_Quantitative_Proteome_Map_of_the_Human_Body
19. EMBL-EBI — https://www.ebi.ac.uk/pride/archive/projects/PXD016999
20. bioRxiv — https://www.biorxiv.org/content/10.1101/2023.11.28.568918v1.full
21. PubMed Central — https://pmc.ncbi.nlm.nih.gov/articles/PMC13441871/
22. Nature — https://www.nature.com/articles/s41592-024-02214-9
23. MCP Online — https://www.mcponline.org/article/S1535-9476(25)00117-3/fulltext
24. SciSpace — https://scispace.com/papers/single-cell-proteomic-and-transcriptomic-analysis-of-jk5wx5c2jd
25. Genome Biology — https://genomebiology.biomedcentral.com/articles/10.1186/s13059-021-02267-5
26. MassIVE (UCSD) — https://massive.ucsd.edu/ProteoSAFe/dataset.jsp?task=bfd7f21d718940fdbaccc0d58ad6b122
27. Nature — https://www.nature.com/articles/s41587-022-01389-w
28. PubMed Central — https://pmc.ncbi.nlm.nih.gov/articles/PMC11903296/
29. Nature — https://www.nature.com/articles/s41592-024-02558-2
30. bioRxiv — https://www.biorxiv.org/content/10.1101/2024.07.31.605978.full.pdf
31. GitHub — https://github.com/Cajun-data/nanoSPLITS
32. Cell Press — https://www.cell.com/cell/fulltext/S0092-8674(21)00583-3
33. OmicsDI — https://www.omicsdi.org/dataset/geo/GSE164378
34. arXiv — https://arxiv.org/abs/2104.03344
35. arXiv — https://arxiv.org/html/2104.03344v4
36. PubMed Central — https://pmc.ncbi.nlm.nih.gov/articles/PMC9839897/
37. PubMed Central — https://pmc.ncbi.nlm.nih.gov/articles/PMC10704589/
38. Springer Nature Experiments — https://experiments.springernature.com/articles/10.1038/s41592-024-02559-1
