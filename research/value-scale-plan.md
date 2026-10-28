# Plan: a calibrated raw-or-log detector for uploads, built as a reusable framework

Status: approved by the owner on 2026-10-28. Step 1 (the diagnostic bank) is done and its two explained failures accepted (`research/notebook-outputs/value_scale_step1/notes.md`); Phase A is next, and nothing below Step 1 is built yet.

## Context

Stage 0 of the service (`service/pipeline/alignment.py:347-402`, `detect_and_transform_value_scale`) decides whether a protein upload still needs a log. Its rule is "no negative value and a non-zero median above 50 means linear". It read PXD064083's linear values (median 7, max 211,481, about 45% zeros) as log. No log2 was taken, and the zeros were treated as measured values.

What the research found (`research/value-scale-detection.md`, plus the 2026-10-28 searches):
- **Every tool uses a hand-set threshold.** Each automatic rule found (GEO2R, CIBERSORT, scGPT, ExpressAnalyst, Omics Playground, ProteoPy, Gemma) is a size threshold set by hand, with no published error rate.
- **The gap is open.** No tool has a labelled benchmark, a guaranteed error rate per class, a "can't tell" answer, or any proteomics validation.

The goal is a detector whose error rate is guaranteed and measured, which says "can't tell" honestly. It is built as a self-contained package that the service uses and other researchers can reuse.

**Owner's decisions (2026-10-28):**
- Protein first, then RNA.
- A 5% guarantee now (α = δ = 0.05, about 60 deposits per class), growing to 1% (about 300 per class).
- The code lives as its own package in this repo, and later becomes its own repository and PyPI package.
- The product comes first; no manuscript work here.
- **The first step is a bank of real test datasets from public accessions. Every later step ends with diagnostic runs on that bank, checking each stage's outputs against what we intend.**

## The diagnostics rule (applies to every step below)

- **Expectations come first.** Before a step is built, its expected outputs are written down for each bank table in `valuescale/bank/expectations/<step>.json`: the verdict, which gate fires, the feature ranges, the stage invariants. They are not edited after the run.
- **Each step ends with a run.** `research/notebooks/value_scale_diagnostics.py --step <step>` runs on every bank table and every bank variant. It writes `research/notebook-outputs/value_scale_<step>/report.md` (expected vs observed, one row per table, PASS / FAIL) and `report.json`, with an entry in `research/notebook-run-history.md`.
- **The next step starts only when** every row passes, or the owner accepts each failure after it has been explained in the report.
- **The stage-by-stage trace follows the service's own calls**, as in `scripts/trace_workflow.py:166-189`: parse → Stage 0 → duplicate merge → gene matching → feature alignment and mask → z-score → smoothing → encoders → answer.
- **Invariants checked at every stage, on every table:**
  - no ±inf after Stage 0;
  - zeros made missing equal the zeros counted (protein, raw reading);
  - mask sum = observed values in matched genes;
  - each z-scored gene's observed mean ≈ 0 and SD ≈ 1, or exactly 0 for a constant gene;
  - the encoder input is finite;
  - smoothing equals the service's (as `trace_workflow.py:189` asserts);
  - every cell gets an answer or an abstention reason.

## Step 1 (first): the diagnostic bank

The bank is a fixed set of real tables. Each has its scale known from provenance (software docs or the paper's methods, quoted), and each is chosen to cover one case the detector must handle. Bank tables count as "looked at": they belong to the design split, and the calibration and test fetches must exclude their accessions.

**1a. Tables already on disk** (development or spent roles in `research/benchmark/public-sets-downloads.json`; nothing sealed is touched):

| Case | Tables |
|---|---|
| Linear, DIA-NN | PBMC240 (`service/examples/`); Kabatnik PXD046999 (timsTOF Ultra); Zheng PXD057118; PXD077946 (single cells); Zamore PXD056050; PXD073250 |
| Linear, small scale | PXD064083 (median 7) |
| Linear, MaxQuant | PXD021882 `proteinGroups.txt`; DusSzachniewicz PXD011683 |
| Linear, FragPipe | Herrera PXD058626 and LungMAP MSV000094373 `combined_protein.tsv` |
| Linear, Spectronaut | MSV000099294 (one cell per run); PXD061052 |
| TMT, scale to be settled from provenance | Fulcher 2026 `abundance_protein_MD.tsv` (TMT-Integrator's docs disagree on whether its abundance tables are log2); SCeptre PXD020586 |
| Log | SCoPE2 export (centred, with negatives); Khoury 2026 (log2); Furtwangler 2025 h5ad (log2) |

**1b. Downloads to fill the gaps** (verified by a search on 2026-10-28; a zip's contents are listed before it is admitted):

| Case | Accession, file |
|---|---|
| One real table on both scales | PXD049412 (Bubis 2025, Astral, Spectronaut 18): `JB_250pgHeLa_50SPD_SO_MBR_Report_Protein_JB_Pivot_.tsv`, 2 MB, has linear `PG.Quantity` and `PG.Log2Quantity` side by side |
| Same samples on several instruments | PXD069060 (Edwards 2026: Astral, Eclipse, timsTOF Pro): `P4777_15_Report.tsv` (72 MB) and siblings; scale confirmed from headers and tool docs before labelling |
| Linear, small-scale, relative | quantms-data PXD004452 `…absolute.tsv` (1.9 MB): linear `ibaq`, plus `ribaq` (relative iBAQ) |
| Sparse single cells, timsTOF | PXD024043 (Brunner 2022): `DIANN1.8_diaPASEF_1ng_repetitions.zip` (116 MB), `MQ_Dilutions_SingleCells_RawPlusMBR.zip` (43 MB); PXD053464 (Krull 2024): `03_SingleCell_Searches.zip` (79 MB) |
| Single cells, MaxQuant, Orbitrap | PXD016921 (Cong 2020): `MQsearchresults_Single_cell.zip` (199 MB) |
| Log, zero-imputed | Hu 2023 K562 (GitHub dionezhang/CPM): `ProteinAbundances.csv` |
| Log, imputed and batch-corrected | SCoPE2 `Proteins-processed.csv` (Slavov lab page); plexDIA `plexDIA_protein_imputed.csv` (Leduc 2022) |
| Centred log ratios | CPTAC-CCRCC (LinkedOmics) `HS_CPTAC_CCRCC_proteome_Tumor.cct` (log2 ratio to a pooled reference) |

- **Known gap:** no open MSstats, Perseus or TMT-Integrator log table was found. Non-negative real log tables come from PXD049412's log2 column, Khoury and Furtwangler. Labelled constructed variants fill the rest.

**1c. Tooling**, which starts the package's `valuescale/corpus/`:
- **`bank.json`**, one record per table:
  - accession, URL, sha256 and size;
  - software and version, instrument;
  - the label, with the quote and URL that establish it;
  - the case ids, and the expected parser layout.
- **`fetch.py`:**
  - follows `scripts/fetch_public_sets.py`;
  - MassIVE needs `curl --ssl-reqd ftp://…`;
  - data goes to `data/incoming/value-scale-bank/` (gitignored);
  - a hard denylist (PXD042367, MSV000094189, PXD052341, PXD061065), with a test.
- **`extract.py`:** gives each entry's protein table as `alignment.parse_matrix_csv` reads it.
- **`variants.py`:** labelled variants with a fixed seed:
  - ×10^k;
  - log2, log10, ln, log2(x+1) and +offset;
  - per-protein and per-cell normalised;
  - subsampled to 20, 50 and 300 cells;
  - missing values induced by intensity at 20–80%;
  - zero-imputed;
  - z-scored, percentage and 0/1 presence tables (the "foreign" set).

**1d. Step 1's own diagnostics:**
- **D1, the bank itself:**
  - every file matches its sha256;
  - each parses with the expected layout;
  - recorded per table: cells, proteins, genes matched, missing share, zero share, negative share, and value quantiles;
  - each label has its quote.
  - Tables failing any of these are dropped and counted.
- **D2, today's rule on the bank (the "before" picture):** what the median-50 rule reads for every table and variant, against its label. Expected: the small-scale linear tables, and linear variants divided by 10^k, are misread.
- **D3, today's full pipeline traced stage by stage on every bank table:** the stage invariants above, plus the answers. This is the baseline every later step is compared with.

## Phase A: show how each file was read, and the user's override

This is the framework's front end; the default reading is unchanged.

**Service**
- `alignment.py`:
  - Split the function into `median_rule(...)` and `apply_reading(values, reading)`.
  - `ValueScale` gains `stated: str | None = None`. Defaulting it keeps `benchmark/v31_dev_gate.py`'s positional constructor working.
  - `ValueScale.response()` adds `"stated"` only when given, so automatic replies stay byte-identical.
- Thread `value_scale` from `app.py` → `pipeline.run_projection` → `_prepare_query` / `embed_query*` → `ensemble.project` / `fusion.project`.
  - `fusion.protein_query` takes the reading already decided, instead of detecting again at `fusion.py:185`.
  - The reply builders (`pipeline.py:362`, `ensemble.py:371`, `fusion.py:494`) use `response()`.
- `app.py`:
  - accepts `value_scale` ∈ {"", auto, linear, log};
  - answers 400 for RNA with a stated scale, and for "linear" when the table holds negatives;
  - lists the allowed values in `/api/status`.

**Site**
- `web/atlas.html`: a `#value-scale` select (Automatic / Raw intensities / Already log), disabled for RNA.
- `web/js/atlas/main.js` `options()`.
- `web/js/atlas/landing.js` `request()` appends the field only when it isn't automatic. It warns if the reply lacks `stated`, which means an older service ignored the choice.
- `web/js/panels.js`: one pure `valueScaleText(scale)`, used by `buildProjectionSummary` and by `buildReceipt` (`web/js/atlas/atlas-panels.js:142-160`, which drops the scale today).
- `web/js/atlas/answers.js` `receiptFromWorkflow` takes the scale from the trace.

**Tests**
- `test_app.py`, `test_alignment.py` and `test_v42.py`: the new paths.
- The golden fixtures and `test_pipeline_versions.py` stay unchanged.
- Site tests:
  - `atlas-panels.test.js`: 4 → 5 "Pending";
  - `panels.test.js`;
  - `atlas-answers.test.js`;
  - `atlas-landing.test.js`: a new stated-scale case.

**Diagnostics A**, on every bank table × {auto, raw, log}:
- automatic replies are byte-identical to D3;
- a stated reading sets `transformed` as expected and echoes `stated`;
- the stage invariants hold under each reading;
- the answers that change with the reading are tabled.

**Docs:** `docs/service/projection-api.md`, `service/README.md`, `service/model/MODEL_CARD.md` limit 8, and `docs/web/atlas.md`.

**Release:** the service deploy first, then the site, each only with the owner's explicit permission at the time. A live check follows: 3 bank tables through `/api` give the same replies as locally.

## Phase B: the calibrated protein detector

### B0. Protocol before new data

- `research/benchmark/protocol-value-scale.md` covers:
  - the sampling frame and seed;
  - the labelling rule (a label follows what the reading does: log1p of values far below 1 is linear-shaped);
  - the three splits;
  - α and δ, the metrics, and how "can't tell" is resolved;
  - the denylist (sealed sets and bank accessions).
- `research/value-scale-detection.md` is updated with the revised method.

### B1. What each mistake costs

- `research/notebooks/value_scale_cost.py` runs v4.1 on the bank, crossing the right reading vs the wrong one with zeros measured vs zeros missing. It counts the answers that change and the accuracy where labels exist.
- The result fixes the reading used on "can't tell", and whether a protein 0 should be missing under both readings.
- **Diagnostics B1:** the cost table itself, with each table's stage invariants still holding.

### B2. The method (revised after an adversarial review)

**Gates**
- A real share of negatives means "do not take a log". A few stray negatives are set to missing, and the detector runs.
- All non-negative integers, with at least 20 distinct values, means counts, so linear.
- Not gates:
  - Gemma's rounding check (kept for RNA);
  - constant column sums (a feature);
  - ties at a cell's minimum (imputation spikes, set to missing before the statistics).

**Statistics unchanged by each class's nuisance**
- Linear tables vary by x → c·x; log tables by x → a + c·x (base, offset and units).
- Core features:
  - per-cell Bowley and Moors skewness;
  - the tail ratio (Q99−Q50)/(Q75−Q25);
  - the Spearman correlation between each protein's level and its spread, with missing values ranked lowest, over at most 1,000 proteins chosen with a seed taken from the file.
- Side features:
  - D, on the linear side only;
  - the missing share;
  - how much row medians vary, which turns off the level–spread feature on per-protein-normalised tables;
  - how much the per-cell statistics vary across cells;
  - the column-sum spread.
- A missing feature (fewer than about 5 cells) is allowed for.

**Decision: per-class split conformal on two kinds of score**
- A typicality score per class (a robust Mahalanobis or kNN distance to that class's design tables), giving p_y^typ.
- A discriminative score, giving p_y^disc.
- Class y joins the answer set when both p-values exceed α/2.
- {linear} or {log} is the answer; {both} is "can't tell"; {} is "unlike either".
- Thresholds use the Neyman–Pearson umbrella order statistic, so P(error > α) ≤ δ. That needs 59 deposits per class and stratum at 5%.

**Splits, strata and the log class**
- Splits by deposit: design (the bank and everything already looked at), calibration (fresh), and test (sealed, scored once).
- Strata by cell count (<50, 50–300, >300), with one subsample per deposit per stratum. A short stratum pools with its neighbour, and the reply says so.
- The log class is calibrated on constructed variants plus the real non-negative log tables. The real log tables also form a separate sealed test stratum.

**On "can't tell"**
- A check without the model: the median per-gene correlation between z(x) and z(log2 x). If it is ≥ about 0.98, the reply says the choice barely matters.
- Otherwise the service uses B1's cheaper reading, warns, and offers a re-run with the other reading.

**Diagnostics B2, on the bank and its variants:**
- **Gates:** which gate fires, against the expectation. For example, SCoPE2 hits the negatives gate (73,419 of the 146,750 values in its 50-cell slice are negative), and the count variants hit the integers gate.
- **Invariance:** each core feature is unchanged, to float tolerance, under ×10^k, a change of log base and +a.
- **Drift:** each feature's shift under induced missingness and subsampling is tabled, with no sign flips across classes beyond the expected ones.
- **Separation:** linear and log bank tables are separated on the score.
- **Conformal code:** in simulation (1,000 repeats with known distributions), per-class coverage is ≥ 1−α, and the umbrella rule keeps P(error > α) ≤ δ.
- **Verdicts:** every bank table's verdict is right, or it is "can't tell" with the reason shown.

### B3. The corpus, protein v1 (for the 5% guarantee)

- **Linear class:** about 60 calibration and about 60 test deposits, freshly drawn with a seed from PRIDE and MassIVE projects of 2020–2026 that hold processed tables, stratified by software and instrument. Only processed tables are fetched. Bank accessions are excluded.
- **Labels:** from provenance, with a quote, fixed by script before any statistic is computed. A sample is checked by hand; unclear tables are excluded and counted.
- **Log class:** constructed variants, one per calibration deposit, plus real non-negative log tables. The foreign set is used for the "unlike either" flag.
- **Diagnostics B3** (on the calibration split, with no statistic looked at beyond D1's parse and provenance checks):
  - every record has its sha256, parses, and has its quote;
  - each stratum holds at least 59 deposits;
  - the hand audit's agreement rate is recorded.

### B4. The package: `valuescale/` (placeholder name)

A new top-level folder. It uses numpy only and imports nothing from `service/`.
- `__init__.py`: `detect(matrix) → ScaleReport` and `apply(matrix, reading)`.
- `gates.py`, `statistics.py`.
- `conformal.py`: p-values, the umbrella rank, Clopper–Pearson.
- `report.py`: a small JSON scale report (verdict, set, p-values, statistics, calibration id and guarantee).
- `calibration/protein-v1.json`: frozen, with the corpus manifest's sha256.
- `baselines.py`: GEO2R, ExpressAnalyst, scGPT, Omics Playground, ProteoPy, Gemma, CellTypist and median-50, each re-implemented from a cited permalink. CIBERSORT is re-implemented from its description, because of its licence.
- `corpus/`: bank, fetch, extract, variants, split, and `score_test.py`, which refuses a second run.
- `bank/expectations/`: one file per step.
- `valuescale/tests/`:
  - invariance properties;
  - the gates and the reports;
  - the denylist;
  - the readers agree with `parse_matrix_csv`;
  - nothing imports `service`.

### B5. Wiring it into the service

- `service/config.py` gains `VALUE_SCALE_METHOD` and `VALUE_SCALE_UNDECIDED_READING`. `LINEAR_SCALE_MEDIAN_THRESHOLD` stays for RNA.
- `alignment.detect_and_transform_value_scale` calls `valuescale.detect` for protein. RNA keeps the median rule, and a test proves it.
- The reply's `value_scale` gains `verdict` (linear / log / cant_tell / unlike_either) and `evidence` (the scale report).
  - These are recorded in a "fields added since freezing" list in `service/tests/test_pipeline_versions.py` `assert_same`.
  - `test_golden_fixtures.py` compares the frozen keys only. The frozen fixtures are never regenerated.
- The site's `valueScaleText` covers the new verdicts. "Can't tell" and "unlike either" show a warning beside the scale menu.
- **Tests:**
  - the tiny-matrix and uniform-random tests in `test_alignment.py` (412-472) move to `median_rule` / `apply_reading`;
  - new log-normal cases: PXD064083-like, 45% zeros, log2, log10 and +10 offsets, ratio tables, too-small-to-tell;
  - `test_pxd064083.py:157` → `apply_reading`.
- **Diagnostics B5:** the full stage-by-stage trace on every bank table, compared with D3:
  - PBMC240 reads linear, on the 50-cell slice and on all 238 cells;
  - SCoPE2 reads log;
  - PXD064083 reads linear, and its answers are tabled against D3;
  - the RNA fixtures are byte-identical;
  - every stage invariant holds;
  - detection takes under about 3 s on 2 CPUs.

### B6. Deploy assembly

- `deploy/huggingface/build_space.py`:
  - `package_files()` adds `valuescale/` (not tests, corpus or bank) and the calibration JSON;
  - the `git status` check covers it;
  - a new import check runs on the assembled Space.
- `deploy/huggingface/Dockerfile` gains `COPY --chown=user valuescale ./valuescale`.
- A test in `scripts/` covers both.
- **Diagnostics B6:** the assembled Space, run in a subprocess, gives replies identical to the repo's service on every bank table.

### B7. Sealed test, the owner's OK, then deploy

- `score_test.py` scores the sealed test once. The results go in `research/benchmark/results.md`, per class and stratum:
  - the share wrong, the share "can't tell" and the share "unlike either", with Clopper–Pearson intervals;
  - risk–coverage;
  - results by software and instrument;
  - real vs constructed log tables;
  - the power to catch foreign tables;
  - every baseline rule on the same test.
- After the owner's OK, regenerate in this order:
  1. `scripts/trace_workflow.py`: `stages.scale` carries the verdict and evidence.
  2. `scripts/build_manifest.py`: replaces the `scale_threshold` and `median_linear` facts.
  3. `scripts/build_manuscript.py`: the site's Stage 0 sentence at `web/manuscript.html:298-299`.
  4. `scripts/build_figures.py`: `methods_reading.py`.
- **Docs:**
  - `CLAUDE.md`, `README.md` and `docs/project-structure.md`: the tree entry, a "where a file goes" row, and a fourth test suite, `python -m unittest discover -s valuescale/tests -t .`;
  - `docs/file-index.md`;
  - `docs/service/projection-api.md`;
  - the model card: limit 8 removed;
  - `service/model/canonical_preprocessing.json`;
  - `research/todo.md`.
- The service deploy needs the owner's explicit permission. The live check repeats Phase A's, with the new verdicts.

## Phase C: the RNA module, and a 1% guarantee

- **Protein corpus to about 300 deposits per class**, under the same rules.
- **RNA bank first, then the RNA module:**
  - CELLxGENE Census raw counts and ARCHS4 counts for the linear class;
  - CPM, log1p and log2(x+1) variants;
  - GEO GDS value_type labels (4,348 sets), used as declared labels rather than ground truth;
  - Gemma's rounding gate;
  - its own strata, diagnostics and sealed test.
  - Then the service's RNA path moves off the median rule.
- **Release for outside use:** its own repository and PyPI package, plus the corpus and bank manifests (accessions, labels, sha256s; no data redistributed). The licence is the owner's decision; the repo has none today.

## Verification

- **Every step:** `node --test`, `python -m unittest discover -s scripts` and `python -m unittest discover -s service/tests -t .`, run with `/c/Users/amarn/miniforge3/envs/vivome/python.exe`. From B4, also `python -m unittest discover -s valuescale/tests -t .`.
- **Every step's diagnostic report:** all rows pass, or the owner has accepted each explained failure, before the next step starts.
- **End to end:**
  - D3, A, B5 and B6 traces agree where they should;
  - the sealed test is scored once;
  - after each deploy (with permission), the live check matches the local replies.
