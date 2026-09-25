# VivOME Improvement Roadmap: Notebooks and Claude Code Tracks

Plan for taking VivOME v3 to a deployable, state of the art v3.1 (Tier 1,
reference frozen) and then v4 (Tier 2, retrained). Notebooks run on Colab Pro
because they need the RNA h5ad and a GPU. Claude Code tracks run in the repo in
parallel, on separate branches, and never wait on each other except where a
dependency is stated.

Grounded in: `Findings_v3.md`, the prototype export run, the fair benchmark
docs, the research report on Tier 1 and Tier 2 improvements, and the current
service code (`pipeline.py`, `assignment.py`, `alignment.py`, `smoothing.py`,
`config.py`, `app.py`, `evaluate.py`).

---

## Revision, 2026-09-25

T1 NB1 and the latest Claude Code round changed the order of work:

1. **Per upload z scoring is a root cause, not a detail.** On RNA alone, a
   SCoPE2 like upload loses 15.6 points from preprocessing, and single cell type
   uploads score 11.2 percent. A new notebook, **T1 NB1b**, retrains the same
   architecture under composition robust standardizations, before NB2.
2. **The live service has preprocessing defects** (median cosine 0.78 on data
   with missing values, no log transform of linear intensities, a coverage floor
   that refuses 79 to 100 percent of real MS cells). **Track A2** now fixes them,
   rather than only measuring them.
3. **No v3 donor was held out from training**, so published RNA to RNA numbers
   included training cells. Honest test cell numbers replace them.
4. **Selection happens on the calibration suite, reporting on the evaluation
   suite.** Real MS data is confirmatory only.

NB2 onward builds on whichever encoder NB1b selects.

---

## 1. Rules that apply to every notebook and every track

1. **Zero proteomics labels, anywhere, except final scoring.** No protein label
   is used to train, tune, calibrate, select a threshold, pick a method, or
   stop early. This is the project's claim.
2. **Every choice is made on simulated RNA uploads or on a dataset that is not
   being reported.** Picking kNN over centroid because it scored better on
   SCoPE2 is tuning on the evaluation set.
3. **Calibration donors and evaluation donors are disjoint**, and neither was
   used to train the production model. T1 NB1 verifies this first.
4. **Faithfulness before improvement.** The service must reproduce the
   notebook's embedding before any v3.1 component is measured on top of it.
5. **Every exported artifact is committed** (git LFS for arrays) with a sha256
   manifest before anything else touches it. `app_export/` was lost once
   because it never was.
6. **Nothing is wired into the site** until the relevant notebook's go or no
   go criteria pass. `benchmark.rows` stays pending.
7. **Current v3 behaviour stays the default** behind a config flag until v3.1
   passes T1 NB4.

---

## 2. What the current service code already tells us

Found while reading the service, and they shape the plan:

| Finding | Where | Consequence |
|---|---|---|
| Mask is set per cell (0 where that cell's value is missing). The notebook set it per dataset (1 for every matched gene, missing values median filled). | `alignment.py` | The encoder sees a sparser mask than in every measured number. Per cell coverage can fall under `COVERAGE_FLOOR = 0.15`, causing mass refusals. |
| Smoothing graph built from raw, un z scored values with NaN set to 0. The notebook used the z scored, median filled matrix. | `pipeline.py` Stage 2 | The graph is dominated by the highest abundance proteins. A second drift, separate from the fixed alpha bug. |
| Candidate classes hardcoded to macrophage and monocyte. | `config.py`, `pipeline.py` | Any non myeloid upload (T cells, NK) can only be labelled macrophage or monocyte. A correctness risk, not only an accuracy one. |
| Nearest centroid probabilities are a softmax over raw cosine, no temperature. | `assignment.py` | Two class probabilities cluster near 0.5 whatever the true separation. Confidences and conformal sets inherit this. |
| Abstention threshold is a live quantile of the query's own calibration slice. Conformal calibrates on the model's own predictions. | `pipeline.py`, `calibration.py`, `abstention.py` | Both are self referential. This is why coverage was 33.7 percent. |
| Benchmark restricts after computing 22 class kNN; the service restricts the neighbour pool first. | `evaluate.py` vs `assignment.py` | Benchmark kNN numbers are not what the service would produce. |

---

## 3. Dependency map

```
Claude Code (parallel, now)            Colab notebooks (sequential)
---------------------------            ----------------------------
A   rescore ours (done)                T1 NB1  simulation bench (done)
A2  preprocessing fixes  ◄──────────►  T1 NB1b composition robust standardization
    (log, graph input, floor)             │   (A2 ablation + coverage curve inside)
B   deployment hardening                  │
C   v3.1 scaffold (interfaces) ──┐        ▼
D   benchmark extension          │     T1 NB2  label space + decision rule
                                 │        │
                                 │        ▼
                                 │     T1 NB3  abstention + conformal
                                 │        │
                                 │        ▼
F   v3.1 integration  ◄──────────┴──── T1 NB4  integration, evaluation, export
                                          │
                                          ▼
                                       T1 NB5  optional modes (concordance, self training)

E   Tier 2 data ingestion  ─────────►  T2 NB6  external data build
    (after B's ID mapping lands)          │
                                          ▼
                                       T2 NB7  wider reference, Cell Ontology hierarchy
                                          │
                                          ▼
                                       T2 NB8  v4 training (partial DA + SSL + bridge)
                                          │
                                          ▼
                                   D   final multi dataset benchmark for the paper
```

---

## 4. Timeline

| Week | Colab | Claude Code |
|---|---|---|
| 1 | T1 NB1 (done), T1 NB1b | A done; A2 fixes, B, C, D start |
| 2 | T1 NB2, T1 NB3 | B, C, D continue; E starts once B's mapping table is merged; if NB1b exports a new encoder, C adds a variant slot for it |
| 3 | T1 NB4 | F integrates NB4 exports; D reruns on v3.1 |
| 4 | T1 NB5 (optional), T2 NB6 | E continues |
| 5 to 8 | T2 NB7, T2 NB8 | D final benchmark |

---

## 5. Tier 1 notebooks (v3 frozen)

### T1 NB1, `T1_NB1_Simulation_Bench.ipynb`

**Purpose.** Build the label free test bed every later choice is made on:
simulated uploads from held out RNA, masked the way real MS data is masked.

**Inputs.** RNA h5ad, v3 export (`reference_model.pt`, `feature_space_genes.csv`,
`module_assignment.npy`, `reference_metadata.csv`), SCoPE2, PBMC240 and Fulcher
matrices (for mask profiles only, never labels), the v3 notebook's data loading
code, and A2's canonical preprocessing spec.

**Sections.**
1. Rebuild the RNA matrix on the 9,002 gene space exactly as v3 did. Check
   that re encoding reproduces `reference_embedding.npy` for a sample of cells
   (cosine at least 0.999).
2. **Training membership check.** Establish from the v3 notebook which cells
   trained production seed 0. If TSP14, TSP21 and TSP25 were in training,
   calibration on them is optimistic; record it and use the v3 test split
   cells instead. Split the usable held out cells into **calibration donors**
   and **evaluation donors**, disjoint.
3. **Real missingness profiles.** From each MS dataset: which genes are ever
   observed, per gene detection probability, and the distribution of per cell
   observed fraction. Structure only, no labels.
4. **Upload generator.** Parameters: number of classes present (1, 2, 3, 5, 8),
   cells per upload (100 to 2,000), class proportions (Dirichlet), mask profile
   (SCoPE2, PBMC240, Fulcher, or random at a set coverage), and an optional
   stress perturbation (gene wise scaling and noise) as a rough proxy for
   modality shift. Stress sims are labelled as a proxy, not as protein.
5. **Freeze two suites.** A calibration suite built only from calibration
   donors, and an evaluation suite built only from evaluation donors, about
   200 uploads each, saved as specs (cell indices plus mask spec), not as data.

**Outputs.** `heldout_rna_9002.h5ad` (calibration and evaluation donors only,
sparse, float16), `mask_profiles.npz`, `sim_suite_calib_v1.json`,
`sim_suite_eval_v1.json`, `sim_generator.py`.

**Go / no go.** Embedding reproduction at cosine 0.999 or better; calibration
and evaluation donors verified disjoint from each other and from training, or
the overlap documented.

**Compute.** High RAM Colab. No training.

---

### T1 NB1b, `T1_NB1b_Composition_Robust.ipynb` (added 2026-09-25)

**Purpose.** Make a query's embedding independent of what else is in the upload.
NB1 showed per upload z scoring removes shared identity on narrow uploads.

**Variants**, same architecture and recipe, trained on the seed 0 train split only:
V0r (v3 recipe retrained, implementation control), V1 per cell z, V2 per batch
gene z on mini uploads, V3 dual channel (both) on mini uploads. A synthetic check
showed mini upload training alone cannot rescue single population uploads, since
gene wise z scoring within one population erases its identity; per cell z keeps it.

**Sections.** Equivalence gate against NB1; the A2 preprocessing ablation on the
shipped model (mask convention, graph input, missing log transform); the coverage
floor curve; screening on the calibration suite with smoothing on and off;
winner with 3 seeds reported on the evaluation suite with paired CIs; real
SCoPE2 and PBMC240 as confirmation, including the modality probe; export.

**Go / no go.** Single cell type uploads up at least 15 points, SCoPE2 like up at
least 5, oracle restricted and broad compositions not down more than 1, real
SCoPE2 restricted not below 77.8, V0 reproducing 31.08 / 79.79 exactly. On GO,
the new encoder is exported with `variant_config.json`; on NO GO, v3 stays.

---

### T1 NB2, `T1_NB2_Label_Space_and_Decision_Rule.ipynb`

**Purpose.** Replace the hardcoded two class restriction with a per upload,
label free estimate of which classes are present (research T1-1), then choose
the assignment rule inside that set (T1-4).

**Inputs.** NB1 outputs, v3 export, SCoPE2, PBMC240, Fulcher (labels only for
final scoring).

**Sections.**
1. **Logits.** Use the v3 classifier head's logits (it exists, 22 outputs),
   not the untempered centroid softmax, as the base scores.
2. **Calibration (BCTS).** Fit temperature plus per class bias on calibration
   donors masked to each profile. Check expected calibration error on the
   evaluation suite. Decide between two designs and record why:
   (a) per request, re masking a stored RNA calibration set to the upload's
   own gene mask and refitting, or (b) parameters binned by coverage.
3. **Prior estimation (EM / MLLS)** on each simulated upload.
4. **Cluster support test.** Cluster the query on its own graph (the one
   smoothing already builds). A class is supported only if its estimated prior
   clears a floor and at least one query cluster assigns it top 1 with a
   margin. Also test a hierarchical variant, lineage first then type.
5. **Set quality.** Precision and recall of the estimated class set on the
   evaluation suite, broken down by number of classes present and by mask
   profile. Thresholds chosen on the calibration suite only.
6. **Decision rule within the set.** Classifier head, centroid with fitted
   temperature, kNN with the neighbour pool restricted first, and kNN plus
   label propagation over the query graph. Chosen on the evaluation suite.
7. **Real data, scoring only.** SCoPE2 (expect monocyte and macrophage, report
   anything extra), PBMC240 at lineage level, Fulcher as geometry only.

**Outputs.** `bcts_params.json` (or the per request calibration set),
`label_space_config.json`, chosen decision rule and its parameters, results
tables.

**Go / no go.** On SCoPE2, with nothing hardcoded, the estimated set contains
monocyte and macrophage and no lymphoid class; balanced accuracy within 3
points of 79.79 or better. On simulations, set recall at least 0.9 for
uploads with 1 to 3 classes present.

**Compute.** Single GPU, a few hours.

---

### T1 NB3, `T1_NB3_Abstention_and_Conformal.ipynb`

**Purpose.** Replace self referential abstention and conformal calibration with
versions that have a defined guarantee (research T1-2 and T1-3).

**Inputs.** NB1 and NB2 outputs; `encode_with_hidden` from track C so the 512
dimensional pre projection features are extracted exactly as the service will.

**Sections.**
1. **Pre projection features** for the reference and every query (512
   dimensions, before the LayerNorm and L2 projection).
2. **Out of distribution score.** k th nearest neighbour distance (k grid) and
   relative Mahalanobis, against the current max cosine. Measured on false
   abstention for in distribution masked RNA, and on class removal tests (a
   class is removed from the reference index; a weaker proxy than the v3
   retrained held out test, and labelled as such).
3. **Threshold as a conformal p value**, calibrated per mask profile on
   calibration donors, targeting a chosen false abstention rate (for example
   5 percent).
4. **Conformal sets.** Class conditional (Mondrian) APS, calibrated on masked
   calibration donors, reweighted by NB2's estimated priors, restricted to the
   estimated label space.
5. **Real data.** Abstention rate split by reason, empirical coverage, set size
   per class. State plainly that the guarantee holds on masked RNA only.

**Outputs.** `ood_config.json`, `ood_reference_index` (512 dimensional features,
float16 or PCA reduced), `conformal_calibration.npz`, results tables.

**Go / no go.** On the evaluation suite, per class coverage at least 0.90 and
false abstention at or below target. On SCoPE2, total abstention at or below
25 percent after label space estimation, with every abstention carrying a
reason.

**Compute.** Single GPU, a few hours.

---

### T1 NB4, `T1_NB4_v31_Integration_and_Export.ipynb`

**Purpose.** The release gate for v3.1. Run the whole new pipeline, compare it
against current v3 service behaviour, export everything the service needs.

**Sections.**
1. Current v3 pipeline replicated with the canonical preprocessing (baseline).
2. v3.1 pipeline: label space estimation, chosen decision rule, new
   abstention, new conformal.
3. **Ablations**: each component switched on and off individually.
4. **Real data evaluation** on SCoPE2, PBMC240 and Fulcher, bootstrap CIs.
5. **Export** to `Data/Results/Tier1_v31/export/` with a sha256 manifest.
6. **`service_change_spec.md`**: exact parameters, files, and behavioural
   changes for track F.
7. Numbers for the model card (coverage stratified accuracy, known failure
   modes, the three axes claim).

**Go / no go (overall Tier 1).** All of NB2 and NB3's criteria hold together in
the integrated pipeline, and no component regresses masked RNA accuracy by
more than 1 point.

---

### T1 NB5, `T1_NB5_Optional_Modes.ipynb` (only after NB4 passes)

**Purpose.** Two optional improvements, each kept only if it beats v3.1 on
leave one dataset out without touching evaluation labels.

1. **Concordance gene masking (T1-5).** Per gene RNA to protein concordance
   from external sources only (GTEx tissue proteome PXD016999, nanoSPLITS,
   CPTAC). Mask low concordance genes before encoding; the encoder was trained
   under random masking, so this is in distribution. Never use SCoPE2's
   companion scRNA-seq for this, that leaks target information.
2. **Restricted self training (T1-6).** Class balanced self training inside the
   estimated label space only, reliable cells only, LayerNorm parameters only,
   anchored to v3, stopped if masked RNA accuracy drops more than 1 point.
   Offered as an optional asynchronous "adapt" mode, since it breaks the single
   forward pass contract. Kill threshold carried over, now on restricted
   balanced accuracy.

---

## 6. Tier 2 notebooks (retraining, v4)

### T2 NB6, `T2_NB6_External_Data_Build.ipynb`

**Purpose.** Turn track E's downloads into training ready inputs on Drive.

Contents: unlabeled MS datasets on the frozen Ensembl gene space (SCoPE2,
plexDIA, Bubis PXD049412, Chip Tip, Petrosius), each with its own mask profile;
nanoSPLITS and nanoSPINS paired cells for per gene bridge statistics; Hao 2021
CITE-seq for the surface protein subset only; Tabula Sapiens macrophage and
monocyte populations from other tissues. Leakage table stating which dataset
may be used for what, and which is evaluation only in which fold.

**Go / no go.** Every dataset maps to the frozen gene table with coverage and
unmapped counts reported; dataset counts checked against the papers (several
in the research report are unverified).

### T2 NB7, `T2_NB7_Reference_Widening.ipynb`

**Purpose.** Fix the macrophage class at its root (RNA recall 0.504 to 0.758)
and prepare for non blood uploads (research T2-3).

Contents: multi tissue reference under a Cell Ontology hierarchy, tissue
resident macrophage subtypes kept separate under a parent node, in vitro
macrophage like cells as their own labelled node, hierarchical cross entropy,
predictions at the deepest confident level (generalising the six hand picked
fallback pairs). Retrain the v3 architecture unchanged first, so any gain is
attributable to the data.

**Go / no go.** RNA macrophage recall rises; no class regresses by more than 2
points on masked RNA.

### T2 NB8, `T2_NB8_v4_Training.ipynb`

**Purpose.** Attack the modality gap directly (research T2-1, T2-2, T2-4).

Contents: self supervised objective on pooled unlabeled MS data; class weighted
partial domain adversarial alignment, with class weights from the NB2
estimator so distractor classes are not pulled toward protein cells;
pseudo protein views of RNA from the NB6 bridge with a consistency loss;
one vs all open set head. Leave one MS dataset out throughout. Model selection
on masked RNA and on other MS datasets only.

**Go / no go.** Modality probe below 80 percent (from 98.99), macrophage
recall on held out SCoPE2 above 30 percent (from 0.76), masked RNA accuracy
within 1 point of v3.

---

## 7. File ownership (prevents parallel tracks from colliding)

| Area | Owner | Others may |
|---|---|---|
| `service/pipeline/smoothing.py`, preprocessing conventions in `alignment.py` and `pipeline.py` Stage 1 and 2 | A2 | read only |
| New `service/pipeline/gene_ids.py`, input validation, export, FAISS, model card, logging | B | read only |
| New interfaces for label space, abstention, conformal; `encoder.py` hidden feature hook; response schema; `docs/projection-service.md` | C | read only |
| `tools/fair_benchmark/**` | D | read only |
| `data/**` ingestion scripts and registry | E | read only |
| Wiring NB4 exports into the pipeline | F | after A2, B, C merge |

Each track works on its own branch (or git worktree). Merge order: A2, then B,
then C, then F. D and E merge independently.

---

## 8. Claude Code prompts

Paste each into its own Claude Code session. A is already running.

### Track A2, preprocessing fixes (revised 2026-09-25, replaces the original A2 prompt)

```
Branch: faithfulness/a2. Read docs/plans/VivOME_TODO.md section 1 first.

Fix the live service's preprocessing defects. The e2e check found median cosine
0.78 (5th percentile 0.23, some cells anti correlated) on raw PBMC240 between the
service and the notebook convention, and T1 NB1 found the coverage floor would
refuse 79 percent of PBMC240 and 100 percent of Fulcher cells. Zero protein labels
in any decision. PBMC240 weak lineage labels may be used only to score before and
after, never to choose.

1. Log transform. Detect linear scale input with an explicit, tested rule (for
   example: no negative values and median of observed values above 50) and apply
   log2 to observed values, treating 0 as not detected. Never transform data that
   is already on a log scale. Add "value_scale": {"detected": ..., "transformed":
   ...} to the response. Test: a log matrix and its 2**x version must give the same
   embedding (cosine >= 0.9999).

2. Smoothing graph input. pipeline.py builds the graph from raw values with NaN set
   to 0. Build it from the z scored matrix the encoder receives (after step 1),
   missing entries 0. Keep PCA(50), k=15, alpha 0.6, Gaussian kernel exactly.

3. Mask convention. Keep the per cell mask (1 only where that cell observed the
   gene). NB1's simulations with realistic dropout favour it over median filling.
   Do not revert to median fill.

4. Coverage floor. Replace COVERAGE_FLOOR = 0.15 (1,350 of 9,002 genes) with
   MIN_OBSERVED_GENES, an absolute count, default 100, marked PROVISIONAL until
   T1 NB1b's coverage curve is committed (the owner will add
   docs/plans/nb1b/coverage_curve_v0.csv). Report each cell's observed gene count
   in the response.

5. Re measure. Raw PBMC240 (DIA-NN report) through the fixed pipeline: report the
   median and 5th percentile cosine to the embedding of the same cells from the
   notebook preprocessed file (their upstream preprocessing differs, it included
   imputation, so 1.0 is not expected; the point is no anti correlated cells).
   Report lineage accuracy on weak labels before and after, as a score only.
   SCoPE2 must still reproduce 45.37 / 31.08 and 86.17 / 79.79 exactly.

6. Golden fixtures on 50 PBMC240 cells (with missing values), alongside SCoPE2.

7. Commit service/model/canonical_preprocessing.json:
   {"convention": "service", "graph_input": "zscored", "log_transform": <rule>,
    "min_observed_genes": 100, "provisional": ["min_observed_genes"]}.
   The owner copies it to Drive Data/Results/Tier1_v31/ for the notebooks.

8. If T1 NB1b later exports a new encoder with per cell standardization, that is
   a separate integration (track F style), not part of this task.

9. Update docs/plans/VivOME_TODO.md: tick what you finished, add commit hashes.
```

### Track B, deployment hardening

```
Branch: hardening/b. Independent of the notebooks. Do NOT edit smoothing.py,
assignment.py, calibration.py or abstention.py, and do not change the mask or
value conventions in alignment.py (track A2 owns those).

1. Gene identifiers. Create service/pipeline/gene_ids.py and a frozen, versioned
   mapping table service/model/gene_id_map_v1.tsv (pinned Ensembl release,
   HGNC IDs, UniProt accessions, symbols, with a sha256 and the release numbers
   recorded). Map the 9,002 feature space to Ensembl IDs and report any that do
   not map. At upload time accept symbols (case insensitive), Ensembl IDs, or
   UniProt accessions including semicolon separated protein groups and DIA-NN
   style reports with a Genes column. Never call MyGene or any live service at
   runtime; symbol drift from live lookups already corrupted an earlier build.
   Report matched, unmapped and ambiguous identifiers in the response.
   alignment.py only gains a call to gene_ids before matching, nothing else.

2. Input validation. Detect orientation (features in rows vs cells in rows)
   and reject the ambiguous case with a clear message rather than guessing.
   Minimum cell count (refuse below 20, warn below 100, since smoothing and any
   per upload statistic need a population). Detect value scale (log vs linear)
   and report it; do not silently transform.

3. Serving. Export the encoder to TorchScript or ONNX with an equivalence test
   (max absolute difference < 1e-5 on 1,000 cells). Replace the brute force
   max cosine and kNN searches with FAISS, with an exact equivalence test
   against the current numpy results.

4. Model card: service/model/MODEL_CARD.md and versions.html content. State
   the claim precisely: reference supervised on RNA, zero shot on proteomics,
   no protein labels, no cell pairing. Include coverage stratified accuracy
   from the v3 tables and the known failure modes (macrophage placement, 2 of 22
   classes with protein support). Numbers only from committed tables.

5. Logging per upload: input hash, coverage, supported class set, abstention
   rate by reason, score distributions, model and mapping table versions.

Tests for everything. All existing test suites must still pass.
```

### Track C, v3.1 scaffold

```
Branch: integration/v31-scaffold. Build the interfaces that the Colab notebooks'
outputs will plug into. Current v3 behaviour must remain the default and stay
byte for byte identical (add a golden test proving it). Do not edit
alignment.py or smoothing.py.

1. Config flag PIPELINE_VERSION = "v3" | "v3.1", default "v3".

2. Interfaces, each with a v3 implementation reproducing today's behaviour:
   - LabelSpaceEstimator: returns supported class positions plus a per class
     support score. v3 implementation = the current hardcoded
     CROSS_MODAL_SUPPORTED_CLASSES.
   - AbstentionScorer: returns decision plus reason. v3 implementation = the
     current abstention.py logic.
   - ConformalCalibrator: returns label sets plus metadata. v3 implementation
     = the current calibration.py logic.
   Loaders for v3.1 artifacts under service/model/v3_1/, raising
   PendingArtifactError if missing, same as today.

3. encoder.py: add encode_with_hidden(values, mask) returning both the 128
   dimensional embedding and the 512 dimensional pre projection features.
   Test that the embedding is identical to encode().

4. assignment.py: add an optional temperature and per class bias to the
   probability step (defaults reproduce today's output exactly), so fitted
   calibration parameters can be dropped in later.

5. Response schema, versioned and additive: supported_classes (names, method,
   per class support score), abstain_reason split into no_reference_support,
   low_coverage, ambiguous, and a calibration block stating what the coverage
   guarantee applies to ("masked RNA", not protein). Update
   docs/projection-service.md with a v3.1 section; do not remove v3 fields.

No new methods are implemented here. This track only builds the sockets.
```

### Track D, benchmark extension

```
Branch: benchmark/d. Owns tools/fair_benchmark/ only. Starts after the rescore
run finishes. Nothing goes on the site; benchmark.rows stays pending.

1. Freeze tools/fair_benchmark/PROTOCOL.md before any new run: datasets, cell
   set, decision rules, k, seeds, metrics, CI method. Any later change is
   logged there with the reason.

2. One identical cell set for every arm (resolve 85,232 vs 85,233).

3. Add a second restricted kNN variant that restricts the neighbour pool first,
   exactly like service/pipeline/assignment.py, and report it alongside the
   current post hoc masking. Label both clearly.

4. Seeds: scANVI seeds 0 to 4, MaxFuse and scGLUE seeds 0 to 2. Cache
   embeddings and predictions to disk immediately after each run. Report mean,
   SD, and per seed bootstrap CIs.

5. Paired comparison ours vs scANVI: paired bootstrap over cells, per seed, on
   balanced accuracy. Report the difference and its CI, not only two numbers.

6. Restructure around a dataset registry so PBMC240 (lineage level) and further
   MS datasets drop in without code changes. Add them as they become available.

7. When v3.1 lands (track F), add it as its own arm alongside v3.
```

### Track E, Tier 2 data ingestion (start once track B's mapping table is merged)

```
Branch: data/e. Owns data/** only.

1. data/registry.yaml: for each dataset, accession, URL, download date,
   sha256, license, platform, cell types, label status, and allowed use
   (training, bridge, evaluation only). Start with: SCoPE2 MSV000083945,
   plexDIA MSV000089093, Bubis PXD049412, Chip Tip PXD049211 and PXD049181,
   Petrosius MSV000095333, nanoSPLITS (MSV000089280, MSV000090828,
   MSV000093330; GEO GSE201575, GSE219047, GSE247519), Hao 2021 CITE-seq
   GSE164378, GTEx tissue proteome PXD016999, Tabula Sapiens. Several cell
   counts in the research report are unverified; check each against its paper
   and record the verified number.

2. Download scripts, idempotent, checksum verified.

3. Convert each MS dataset to a gene level matrix on the frozen Ensembl table
   from track B, reporting coverage against the 9,002 space and unmapped
   counts. Keep protein group handling identical across datasets.

4. Leakage guard: tag SCoPE2's companion scRNA-seq and any dataset used for
   evaluation as evaluation only, and make the loader refuse to return them
   for training or bridge use.

Raw downloads stay out of git (data/external, gitignored); processed outputs
go to Drive for the Tier 2 notebooks, with the registry committed.
```

### Track F, v3.1 integration (template, finalise when T1 NB4 exports land)

```
Branch: integration/v31. Depends on A2, B, C merged and T1 NB4 exports.

Bring Data/Results/Tier1_v31/export/ into service/model/v3_1/ via git LFS and
verify every sha256 against the export manifest. Implement the v3.1 versions of
LabelSpaceEstimator, AbstentionScorer and ConformalCalibrator exactly as
specified in service_change_spec.md, with the parameters from the export,
nothing re derived. Add a test that reproduces T1 NB4's SCoPE2 numbers through
the service to within 0.1 points. Keep PIPELINE_VERSION default at "v3" until
the owner signs off.
```

---

## 9. Open decisions to settle along the way

| Decision | Settled in | Default until then |
|---|---|---|
| Canonical mask and value convention | A2 with T1 NB1b ablation | Per cell mask, graph on z scored values, log2 for linear input |
| Were TSP14, TSP21, TSP25 in production training | T1 NB1 | Assume yes, use v3 test split |
| Per request calibration vs coverage binned parameters | T1 NB2 | Per request if latency allows |
| Flat vs hierarchical label space | T1 NB2 (v3.1), T2 NB7 (v4) | Flat with the six pair fallback |
| Whether the service ships RNA calibration cells | T1 NB2 / NB3 | Yes, float16, a few thousand cells |
| Adapt mode offered publicly | T1 NB5 | No |
