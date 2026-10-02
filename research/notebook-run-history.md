# VivOME, Every Notebook Run

In order, with what each one established. The existing notebooks come first,
since they predate everything built during this project, followed by every
notebook built and run over the course of it.

---

## Where the notebooks are

The notebooks are not in git. They live in the project Drive's
`Colab Notebooks/`, and run against the Drive root
`/content/drive/My Drive/Vivome - Live Atlas` (inputs in `Data/scProteomics`,
`Data/scRNA-seq` and `Data/Results/`; outputs in `Data/Results/<notebook
folder>`). On the Windows PC, 15 of them are in `D:\Project\Vivome\notebooks\`
with their saved outputs, and `Data/Results/` is in
`D:\Project\Vivome\drive\Data\Results\` ([setup](../docs/setup-windows.md)).

| Entry | File on the PC | Cells | Run time printed |
|---|---|---|---|
| 1, 2 | `Reference_Projection_Diagnostics.ipynb` | 13 (Q1 to Q5, summary, Q7 to Q9) | |
| 3 | `Unsupervised_PBMC240.ipynb` | 9 | |
| 4 | `Masking_Coverage_Baseline.ipynb` | 11 | |
| 5 | `Build_Feature_Space.ipynb` | 8 | |
| 6 | `Masking_Techniques_Experiment.ipynb` | 16 (three follow up cells after the twelve: a modality probe shortcut check, rebuilt modules, balanced module pooling) | training log to 8,068 s |
| 7 | `Masking_Decisive_Test.ipynb` | 11 | training log to 7,691 s |
| 9 | `Reference_Projection_v3.ipynb` | 21 | |
| 10 | `SelfTraining_Pilot_SCoPE2.ipynb` | 13 | |
| 11 | `CellLine_vs_Primary_Comparison.ipynb` | 12 | |
| 12 | `VivOME_Prototype_Export.ipynb` | 13 | |
| 13 | `T1_NB1_Simulation_Bench.ipynb` | 12 | 11.3 min |
| 14 | `T1_NB1b_Composition_Robust.ipynb` | 14 | 24.3 min |
| 15 | `T1_NB1c_Real_Data_Diagnostics.ipynb` | 10 | 3.4 min |
| 16 | `T1_NB1d_V2_Seed_Check.ipynb` | 13 | 30.6 min |
| 17 | `T1_NB2_Label_Space_and_Abstention.ipynb` | 16 | 12.9 min |

Cell counts include markdown and the empty last cell Colab leaves; the
entries below count the cells that ran. NB1b's real data cell (section 9)
has no saved output; its figures come from
`research/notebook-outputs/nb1b/real_data_confirmatory.csv`. The copy of the
export notebook in `service/model/source/` is the same run with Colab's
per cell execution metadata removed.

Not on the PC: `Reference_Projection_v2.ipynb` (entry 8),
`SelfTraining_Pilot_SCoPE2_v2_mass_based.ipynb` (entry 10),
`Deep_Learning_SCoPE2_Fully_Supervised_All.ipynb`, and a separate Q6 to Q9
file (entry 2). The two other existing notebooks,
`Deep_Learning_SCoPE2_Unsupervised.ipynb` and
`Deep_Learning_SCoPE2_Unsupervised_Continued.ipynb`, are in
`D:\Project\Vivome\notebooks\existing\`.

---

## Existing notebooks, read, diagnosed, or extended

| Notebook | What we did with it |
|---|---|
| `Deep_Learning_SCoPE2_Fully_Supervised_All.ipynb` | The original supervised pipeline. The zero shot probe was appended here as a new cell, since it needed this notebook's trained checkpoint. |
| `Deep_Learning_SCoPE2_Unsupervised.ipynb` | Walked through cell by cell. Confirmed the fixed MMD kernel was in place, uploaded three times across the project, all three byte identical. |
| `Deep_Learning_SCoPE2_Unsupervised_Continued.ipynb` | The user's own merged notebook, combining the supervised preprocessing with six of the diagnostic scripts pasted in as sequential cells. |

---

## Notebooks built and run, in order

### 1. `Reference_Projection_Diagnostics.ipynb`
Nine cells, Q1 through Q5. Macrophage's apparent negative silhouette (in the v2
reference) turned out to be a sampling artefact, the real value is positive. Conformal
miscalibration traced to calibrating on a confidence filtered subset rather
than a random one. `max_cos_cell` established as the out of distribution
score, AUC 1.000 across five held out classes against a scorer that had
previously read as below chance.

### 2. `Diagnostics_Followup_Q6_to_Q9.ipynb`
Four cells, Q6 through Q9. Six adjacent class pairs confirmed as genuine
biological continua rather than model failures. Distribution moment matching
found to actively hurt cross modal transfer. Optimal transport found to beat
k nearest neighbour by 14.46 points on a controlled RNA to RNA test, directly
contradicting an earlier assumption that kNN was a safe default.

No separate file survives. Q7 to Q9 are cells 9 to 11 of
`Reference_Projection_Diagnostics.ipynb` (Q9 prints the kNN upper bound
72.67 percent, OT relaxed 87.14 percent, a gap of 14.46 points). No copy of
the Q6 cell survives.

### 3. `Unsupervised_PBMC240.ipynb`
Nine cells. Preprocessing for the second proteomics dataset. Marker derived
weak labels were assigned to 140 of 237 cells (59.1 percent) across five
lineages: T cell 61, NK cell 56, dendritic 11, platelet 7, monocyte 5. Real
coverage against the reference gene space at the time, the old 2,903 gene
space, was 38.3 percent (1,111 genes). Against the later 9,002 gene space it
is 34.8 percent (3,136 genes), as measured in `Build_Feature_Space.ipynb`
and the notebooks after it.

### 4. `Masking_Coverage_Baseline.ipynb`
Ten cells. Established that a dataset's real, non random gene coverage costs
almost nothing, 0.005 AUC, against a random subset of the same size costing
0.098. Zero fill for missing genes confirmed as the best of four strategies
tested, beating gaussian noise and hot deck imputation.

### 5. `Build_Feature_Space.ipynb`
Eight cells. Built the 9,002 gene feature space as the union of six
independent proteomics sources intersected with the RNA reference, replacing
the old 2,903 gene space entirely. All 2,903 original genes retained inside
the new space, none dropped.

### 6. `Masking_Techniques_Experiment.ipynb`
Twelve cells, seven architecture arms, two seeds each. Established that
masking during training is not optional, uniform random masking beats
sampling that mimics real detection patterns, and module pooling first
emerged as a contender worth a proper comparison.

### 7. `Masking_Decisive_Test.ipynb`
Eleven cells, three arms, five seeds, paired by construction since the split
depends only on the seed. Module pooling won against mask channel alone,
paired mean difference −1.5 points (p = 0.067), averaged over the realistic
coverages (`service/model/evidence/masking_test_tables/rna_sweep.csv`). Selected
as the production architecture.

### 8. `Reference_Projection_v2.ipynb`
Twenty five cells. The full pipeline built on the old 2,903 gene space, a
jointly reasoned reference plus a separate per dataset fine tuning stage.
Established fuzzy smoothing as a real improvement, plus 0.026 AUC, and
surfaced the conformal and abstention problems that the diagnostics notebooks
then chased down.

### 9. `Reference_Projection_v3.ipynb`
Twenty one cells. The masking native reference, trained on the 9,002 gene
space with the decisive test's winning architecture. Five seeds, mean
balanced accuracy 0.7143. Proved masking native training generalises
correctly to missing genes on its own, RNA at 32.3 percent coverage scores
95.5 percent, and proved that real protein data at that identical coverage
scores only 45.4 percent, isolating the modality gap as the problem still
open.

### 10. `SelfTraining_Pilot_SCoPE2.ipynb` and `SelfTraining_Pilot_SCoPE2_v2_mass_based.ipynb`
Twelve cells each, plus a thirteenth added in v2. Tested whether class balanced
self training closes the gap v3 exposed, against an explicit kill threshold of
60 percent. Four structurally different mechanisms were tried, all label free on
the protein side, and all four failed:

| Attempt | Best balanced accuracy | Why it failed |
|---|---|---|
| Unrestricted seeding, all 22 classes | below 60 | Noise from 20 classes with no protein cells |
| Peak confidence class list | below 60 | Picked the wrong second class |
| Aggregate mass class list | 32.73 (acc 46.24) | Found macrophage, but buried under larger wrong classes |
| Confidence weighted soft distillation | 36.67 (acc 53.36) | Moved 5.6 points, far short of the threshold |

Zero shot floor was 31.08 balanced, 45.37 accuracy. Label assignment on the
adapted embedding gave kNN 40.4, nearest centroid 38.3, OT 33.8. Query encoder not
saved. Later work showed every attempt ran in the unrestricted 22 class regime,
where label shift collapse is a documented failure mode, so these results do not
bound self training inside a restricted label space.

The surviving `SelfTraining_Pilot_SCoPE2.ipynb` holds only the peak confidence
attempt: 2 of 22 classes estimated, best 51.61 accuracy / 35.08 balanced in round
1, label assignment nearest centroid 33.85, OT 33.53, kNN 33.81. The other three
rows and the kNN 40.4 / nearest centroid 38.3 figures come from the v2 notebook,
which is not among the files on the PC.

### 11. `CellLine_vs_Primary_Comparison.ipynb`
Eleven cells. Asked whether the gap was a cell line artefact, since SCoPE2's
macrophages and monocytes are PMA differentiated U-937 cells, not primary blood.
Same frozen encoder on SCoPE2 (cell line), PBMC240 (primary) and Fulcher (primary,
geometry only). PBMC240 lineage accuracy came out at 43.44 percent, about chance,
below SCoPE2's 45.37 exact accuracy. Conclusion: cell line origin does not explain
the gap. A formatting bug in the comparison table (a `numpy.float32` failing an
`isinstance(v, float)` check) was fixed along the way.

### 12. `VivOME_Prototype_Export.ipynb`
Eleven cells. Produced everything the application needed that the v3 export
lacked, into `app_export/`: RNA and protein plotting coordinates through one
saved 3 component PCA (69.7 percent of latent variance), the SCoPE2 protein
embedding, and the per reference cell property matrix (85,233 by 8). Measured
three results that reshaped the plan:

- **Restricting candidates to the two classes with protein support** moved
  SCoPE2 from 45.37 / 31.08 to 86.17 / 79.79. More than half the cells had been
  landing in 20 classes with no protein evidence at all.
- **Modality probe 98.99 ± 0.28**: modalities remain almost perfectly separable in
  latent space.
- **Latent centroid cosine**: monocyte 0.830, macrophage 0.190.

Bundled with the v3 export into a verified zip on Drive (24 files, sha256
manifest). Its `app_export/` was later lost locally before being committed and
recovered from Drive; it is now committed at `service/model/source/app_export/`, the
SCoPE2 matrix with LFS.

### 13. `T1_NB1_Simulation_Bench.ipynb`
Twelve cells, Tier 1 notebook 1. Built the label free test bed: simulated uploads
from held out RNA, masked with real MS gene sets and realistic per cell dropout.
All three gates passed: the rebuilt RNA reproduced the shipped embedding (cosine
1.000000), and the seed 0 split reproduced its recorded test accuracy exactly
(0.917341 / 0.724889). Produced `sim_generator.py`, `mask_profiles.npz`, and two
frozen suites of 240 uploads each (calibration from the validation split,
evaluation from the test split). Four findings:

- **No donor was ever held out from v3's training.** Seed 0 used a random split by
  cell; every donor contributed about 65 percent of its cells to training. The
  published RNA to RNA figure of 95.5 / 74.8 was inflated; on test cells only it
  is 93.2 / 65.7. The held out cell type AUC of 1.000 is not a valid unseen type
  test either.
- **Per upload z scoring collapses narrow uploads.** On RNA alone, a SCoPE2 like
  upload dropped from 64.7 to 49.1 unrestricted balanced accuracy, and single cell
  type uploads scored 11.2 percent. Roughly half of SCoPE2's "modality gap" is this
  preprocessing artefact.
- **The coverage floor would refuse most real data**: 79 percent of PBMC240 cells
  and 100 percent of Fulcher cells under the per cell mask. SCoPE2 has no missing
  values at all (already imputed), which is why it never revealed this.
- **Smoothing costs 10 points on natural compositions** while helping narrow ones.

### 14. `T1_NB1b_Composition_Robust.ipynb`
Fourteen cells, Tier 1 notebook 1b, added after NB1. Retrained the v3
architecture under four standardizations, selected on the calibration suite only,
reported on the evaluation suite. Implementation control passed (retrained v3
recipe within 0.9 points of the shipped model).

| Evaluation suite, unrestricted balanced accuracy | v3 shipped | Dual channel, 3 seeds |
|---|---|---|
| All 240 uploads | 35.2 | 72.1 (+36.9, 95% CI 33.7 to 40.2) |
| Single cell type | 11.3 | 80.6 |
| SCoPE2 like | 49.7 | 55.6 |
| Oracle restricted, all uploads | 74.3 | 86.3 |

Source: `research/notebook-outputs/nb1b/eval_winner_vs_v0.csv` (evaluation suite).

The dual channel variant (per upload gene wise z plus per cell z, trained on mini
uploads) won; per cell z alone was close and better on the SCoPE2 like scenario.
A synthetic check had shown why both channels matter: gene wise z scoring within a
single population erases its identity, per cell z keeps it.

**Verdict: NO GO on the pre set criteria.** Every simulation gate passed, but the
confirmatory real data gate failed. From `research/notebook-outputs/nb1b/real_data_confirmatory.csv`, the
dual encoder scored 0.1 to 2.4 unrestricted and 49.9 to 64.6 restricted on real
SCoPE2 across its three seeds, against 31.1 and 79.8 for v3 shipped. The retrained
v3 recipe, the implementation control, scored only 9.1 unrestricted, although it
matched v3 on RNA. That gap raised the seed variance question NB1c answered.
Per cell z alone scored 0.0 unrestricted on SCoPE2 but 97.5 on the processed
PBMC240 file, so the two real datasets pointed in opposite directions.

It also settled Track A2's preprocessing choices on the shipped model: the per cell
mask beat median fill by 3.2 points unrestricted and 4.7 oracle, skipping the log
transform of linear intensities cost about 3 points, and building the smoothing
graph on raw rather than z scored log values made no difference. The coverage
curve puts the floor at about 200 observed genes, with accuracy at chance below
100.

### 15. `T1_NB1c_Real_Data_Diagnostics.ipynb`
Seven cells, no training, 3.4 minutes. Scored twelve models (v3 shipped, v3's five
production seeds, six NB1b checkpoints) on real data to explain NB1b's
contradictions. The reproduction gate passed (31.08 / 79.79), and v3 seed 0 is
byte identical to the shipped export. Three findings:

- **The shipped SCoPE2 numbers are a favourable seed.** Across v3's own five
  seeds, SCoPE2 unrestricted balanced accuracy was 25.6 ± 17.3 (range 0.1 to 48.2)
  and restricted was 63.3 ± 10.8 (range 50.8 to 79.8). The shipped 79.8 is the
  best of the five. The comparison against scANVI used seed 0 alone.
- **The published SCoPE2 matrix is centred per protein and per cell.** All genes
  have mean zero and half the values are negative. Absolute abundance was removed
  upstream, so SCoPE2 cannot test how the pipeline handles a real upload. Raw
  PBMC240 keeps its abundance: no centred genes, almost no negative values
  (0.0001 percent), 63 percent missing
  (`research/notebook-outputs/nb1c/matrix_structure.csv`).
- **On raw PBMC240 through the fixed service path, V2 stands out.** The mini
  upload gene z encoder scored 91.8 lineage accuracy, against 45.9 for v3 shipped
  and 45.9 to 64.8 across v3's seeds. Its predicted composition, 77 percent
  lymphoid, fits a PBMC sample. Per cell z (5.7) and the dual encoder (0.0 to
  13.9) collapsed. Per cell z had scored 97.5 on the processed PBMC file, which was
  already gene centred.

The explanation proposed here: each gene carries a roughly fixed protein to mRNA
offset in log space. Per upload gene z cancels it, per cell z keeps it. The same
centring causes composition dependence, so V2 keeps gene z and learns to cope with
narrow uploads. NB1b's simulation missed this because its stress multiplied log
values per gene, which gene z removes entirely.

### 16. `T1_NB1d_V2_Seed_Check.ipynb`
Thirteen cells, 30.6 minutes. Trained V2 seeds 1 to 4 (about 5 minutes each) and
compared five V2 seeds against v3's five seeds. All gates passed, including the
SCoPE2 reproduction and the cosine match to the app export. v3's provenance shows
seed 0 was the default production seed, not chosen on SCoPE2. On RNA validation it
sits mid range.

| Five seeds each, smoothing on | v3 | V2 |
|---|---|---|
| Raw PBMC240 lineage accuracy | 54.8 ± 7.4 | 92.3 ± 0.7 |
| Cells where all five seeds agree on lineage, PBMC240 | 67.5% | 88.2% |
| RNA evaluation slice, unrestricted balanced | 36.1 ± 2.7 | 55.3 ± 1.8 |
| RNA, single cell type uploads | 18.1 | 35.8 |
| RNA, oracle restricted | 75.7 | 84.3 |
| SCoPE2 unrestricted balanced | 25.6 ± 17.3 | 3.1 ± 3.4 |
| SCoPE2 restricted balanced | 63.3 ± 10.8 | 61.0 ± 10.0 |

Seed averaged paired bootstrap on PBMC240, V2 minus v3: +37.5 points, 95% CI
+29.5 to +45.4, on 122 weakly labelled cells. **Decision, on a rule fixed before
the run: carry V2 into NB2, with v3 as the control.**

The mechanism test on RNA supported the offset explanation. A per gene offset of
twice the spread of gene means left V2 and v3 almost unchanged (V2 55.3 to 54.7,
v3 flat), while per cell z lost 10.6 points and the dual encoder 16.6. On clean RNA
those two beat V2, which is why NB1b's simulation picked the dual encoder. The
real PBMC collapse is far larger than this stress produces, so real offsets are
probably well above twice the spread.

SCoPE2 remains unexplained. V2 sends most macrophages to CD4 T cell classes and
monocytes to neutrophil, dendritic and erythrocyte classes, so the lineage is wrong,
not only the fine label. v3 seed 0 also sends 79 percent of macrophages to CD8 T
cells, and scores 79.8 only because the restriction forces a two class choice.
Centring alone does not explain it, since V2 scores 67.6 on SCoPE2 like RNA
uploads. Carrier channel ratios, batch correction, imputation and per cell
centring are the remaining suspects. PBMC240 has now been used to choose an
encoder, so it is a development dataset. Confirmation needs a fresh MS dataset.
Per seed embeddings are exported in `data/incoming/NB1d/embeddings/` (local, not
in git) for the Track D rerun against scANVI.

**Later correction (Track D, 2026-09-29).** Plain lineage accuracy was the wrong
measure for PBMC240: 117 of its 122 labelled cells are lymphoid and only 5 are
myeloid, so calling every cell lymphoid would score 95.9 percent. The paired
difference between V2 and v3 above still holds, because both models were scored on
the same cells. The informative numbers are lymphoid recall: V2 92.8, v3 52.8, and
scANVI 38.8 at its best (trained only on the genes PBMC240 measures). Myeloid
recall rests on 5 cells and is anecdotal.

**Held out check (Track E, 2026-09-30).** On Fulcher 2026, a TMT PBMC dataset no
model had seen, V2 scored 57.3 ± 2.2 balanced accuracy over six cell types against
42.3 ± 3.4 for v3, and won all 50 seed pairings. scANVI at its fairest scored 47.8.
That was the first held out evidence for V2. Fulcher has since become a
development dataset, and Khoury 2026 is the sealed final test.

### 17. `T1_NB2_Label_Space_and_Abstention.ipynb`
Sixteen cells, 12.9 minutes. The first attempt lost its Drive connection while
reading the RNA file, so the notebook now copies that file to local disk first.
This notebook merged the planned NB2 and NB3: it designed everything after the
encoder, for V2, so that the product could replace its interim fix. All choices
were fitted on half of the calibration suite and made on the other half, under
rules written before the run. The evaluation suite was scored once.

It first rebuilt today's service on RNA simulations to see why it abstains so
often. The probabilities were nearly flat (top probability 0.10 on average), the
conformal sets were calibrated against the model's own guesses, and the out of
distribution rule removed 5 percent of every upload by design. v3 abstained on 41
percent of simulated cells and V2 on 60 percent.

| Choice | Result |
|---|---|
| Temperature | V2 about 0.15, v3 0.31; calibration error fell from 0.52 to 0.07 |
| Encoder | Five seed V2 ensemble, smoothing on, nearest centroid (58.3; seed 4 alone 57.4; v3 36.5) |
| Label space estimation | None. It helped single cell type uploads by 11 points but cost broad uploads (eight cell types and PBMC-like, pooled) 12 points, and about 5 averaged over all other scenarios (`research/notebook-outputs/nb2/tables/label_space_grid_calsel.csv`) |
| Conformal sets | One threshold per class (Mondrian) |
| Out of distribution | Fixed threshold, 1st percentile of in distribution max cosine (0.779) |

| Evaluation suite | Service today (v3) | v3.1 candidate |
|---|---|---|
| Correct when a label is given | 35.0% | 94.9% |
| Abstained | 45.5% | 19.2% |
| Answers at type / group / lineage level | 54.5 / 0 / 0% | 19.1 / 17.7 / 44.0% |
| Top guess, balanced accuracy | | 56.1 |
| Conformal coverage (target 90%) | | 87.1% |

The candidate is far more trustworthy, but most of its answers are broad (a group
such as "T cell", or a lineage). That is honest: at about 56 percent top guess
accuracy, a 90 percent confident answer often has to be broad. It led to a product
change: each cell now also gets a best guess label alongside the confident one.

Three weak points remained. The out of distribution filter passed 99 percent of
cells whose values had been scrambled, so a better score is needed. B cell
coverage was 69 percent and single cell type uploads 67 percent. SCoPE2 still
failed, with 31 percent of its cells called T cell. On PBMC240 (development) the
candidate labelled 79.5 percent of lymphoid cells correctly at the stated level,
against 12.8 percent for the service today.

The output is `research/notebook-outputs/nb2/nb2_spec_v31.json`, which Track F built into
the service (`service/model/v3_1/`). Track F
reproduced NB2's SCoPE2 results from raw input (one cell apart in composition). On
PBMC240 it first came within 1.3 points (72.7 against 73.9 committed). A full code
review then traced the gap to a service bug: when several upload rows mapped to
the same gene, only the last row was kept. With duplicates merged by per cell
median, as every notebook already did, the service reproduces NB2's committed, out
of distribution and ambiguous figures exactly. The research numbers were never
affected.

The same review found a weakness in NB2's rule. A few classes have a very low bar
for entering a conformal set, so on unfamiliar data a cell could be answered with a
class at about 1 percent probability (on SCoPE2, "mature NK T cell" at 0.011). Two
conservative flags were added to the service: every non empty set also contains
the best guess, so a class level answer is always the best guess; and restricted
mode rescales probabilities over the allowed classes. Both still need evaluating on
RNA, in the next notebook (T1 NB3b), together with a better out of distribution
score and a measured false abstention rate. v3.1 shipped as release 0.3.0 on
2026-10-01, with v3 kept as the previous release.

### 18. T1 NB3b: `research/notebooks/t1_nb3b_ood_and_flags.py`

The first notebook run on the Windows PC, as a script in the repository, 6
minutes on its GPU (2026-10-02). It searched for an out of distribution score
better than v3.1's max cosine, and evaluated the two service flags on RNA. Its
rules were committed before the run (`53f61a8`):

- a 5 percent false abstention target;
- scores chosen on RNA controls only;
- the CD34+ progenitors and the real protein sets reported, never used to
  choose;
- go / no go criteria fixed in advance.

Tables are in `research/notebook-outputs/nb3b/`.

**Gate.** It reproduced NB2 before anything new:

- every member's reference latents (median cosine above 0.9999);
- the 0.77899 threshold;
- 2.96 percent false abstention on the evaluation suite (NB2: 2.97);
- 5.47 percent of real cells and 0.96 percent of scrambled ones rejected
  (NB2: 5.49 and 0.96).

**Choice.** Eleven scores were tried, each a mean over the five members:

- max cosine;
- maximum probability;
- energy;
- kNN on the 512-d hidden features, k 1, 10 and 50;
- relative Mahalanobis.

The last two were each built against the training reference and against a
masked index of training cells. Thresholds were set per band of observed
genes, at the 5th percentile of the calibration FIT half. On the SELECT half,
energy had the best mean AUROC over the three controls (0.866) among the
scores within 1.5 times the target. Relative Mahalanobis on the masked index
scored 0.867 but abstained on 8.8 percent, so it was not eligible.

**Evaluation suite, scored once: NO GO.**

| Criterion | Rule | Energy |
|---|---|---|
| False abstention, all cells | at most 6% | 10.2% |
| Worst scenario | at most 10% | 33.6% (single cell type) |
| Scrambled cells rejected | at least 90% | 76.4% |
| AUROC above max cosine on every control | yes | yes (scrambled 0.915 vs 0.868, repeated cell 0.903 vs 0.864, held out class 0.713 vs 0.590) |

**Real data** (`real_data_rejection.csv`; reported, not used to choose):

| Dataset | Energy rejects | Served rule rejects |
|---|---|---|
| CD34+ progenitors | 23.3% (HSCs 47.3%) | 1.3% (HSCs 0%) |
| Fulcher | 1.8% | 0.4% |
| PBMC240 | 8.9% | 1.7% |
| SCoPE2 | 64.3% | 0% |

So energy separates far better than today's rule, but its threshold does not
hold. Two causes, and they affect every score, today's included:

- **Calibration cells are not exchangeable with test cells.** The thresholds
  were fitted on validation split cells, which the encoders saw during early
  stopping, and every score abstains on about twice the target on test split
  cells. NB2's 1 percent threshold already gave 2.96 percent.
- **The score depends on what else is in the upload.**
  - Per upload gene z scoring distorts narrow uploads: single cell type
    uploads abstain on 33.6 percent, lymphoid ones on 19.5, broad ones
    (pbmc like, eight types) on 0.1 to 1.1.
  - By class, B cells abstain on 39.4 percent and erythrocytes on 22.4.
  - A threshold per cell cannot separate a narrow upload from unfamiliar
    cells.

**The flags on RNA** (evaluation suite, today's OOD rule):

- **`set_includes_best_guess`:**
  - coverage 87.1 to 88.3 percent, still under the 90 target;
  - correct when committed 94.9 to 95.5;
  - ambiguous abstentions 15.9 to 17.8.
- **Restricted mode, renormalised** (macrophage/monocyte uploads):
  - committed 96.4 to 99.6 percent;
  - correct when committed 91.8 to 96.2.
  - But class answers fall from 56.7 to 28.6 percent, because the two
    allowed classes share a group, and the best guess is unchanged (88.1).

These are the RNA evaluations release 0.3.0 left open.

*Review note (2026-10-02).* The script says a missed NB2 reproduction stops
the run. In fact the check was computed after the evaluation suite was
scored, and only logged. All four figures reproduced, so no result is
affected, but the gate was not enforced as written.

### 19. T1 NB3c: `research/notebooks/t1_nb3c_ood_calibration.py`

Five minutes on the PC (2026-10-02), with its rules committed before the run
(`04aa884`). It attacked NB3b's two causes. Tables are in
`research/notebook-outputs/nb3c/`.

**The fixes it tried:**

- **Calibration on cells the encoders never saw.** The test split was halved
  by class (8,520 and 8,526 cells). A new calibration suite came from one
  half and a new evaluation suite from the other, with NB1's generator and
  new seeds.
  - Declared: the evaluation cells were scored once by NB3b, in other
    uploads.
- **Thresholds that may depend on the predicted class or on upload
  diversity.** Four schemes were tried against four scores: max cosine,
  energy, kNN 50 and relative Mahalanobis.

**What it found:**

- **The calibration shift is fixed.** On the fresh evaluation suite, false
  abstention is close to target: 4.9 to 6.6 percent for max cosine, energy
  and kNN, and 5.8 to 8.5 for relative Mahalanobis. NB3b's was about 10,
  and NB2's rule gives 2.0 here.
- **The choice fell to max cosine.** On the calibration SELECT half, every
  energy, kNN and Mahalanobis pair exceeded the 15 percent bound on
  single-cell-type uploads (19 to 35 percent). Only max cosine met it, so
  the pre-fixed rule chose max cosine with per-band thresholds.

**Evaluation suite: NO GO.**

| Criterion | Rule | Max cosine, per band |
|---|---|---|
| False abstention, all cells | at most 6% | 6.6% |
| Worst scenario | at most 10% | 14.3% (single cell type) |
| Scrambled cells rejected | at least 90% | 46.1% |

**What the schemes did:**

- **Per predicted class:** brought the single-type worst case down to 9.5
  to 12.9 percent. But rejection of the controls dropped too: energy's
  scrambled rejection fell from 74.9 to 47.3 percent.
- **Per upload diversity:** did not work as intended. The measure (the
  effective number of types in the upload's mean predicted probabilities)
  reads 11 to 13.5 on single-tissue real uploads, because v3.1's
  probabilities are diffuse, so it cannot see a narrow upload.
- **B cells:** still abstain on 37.5 percent under max cosine, a weakness of
  that score for one class.

**The binding limit is separation, not calibration.** No score reaches 90
percent scrambled rejection at about 5 percent false abstention. The best
AUROC is 0.94 (energy), and that operating point needs about 0.97. The best
achieved is energy, rejecting 74.9 percent of scrambled cells at 5.7 percent
false abstention, with 16.4 percent on single-type uploads.

**Real data under the chosen rule** (reported only):

- the CD34+ progenitors are flagged at 2.0 percent (NB2's rule: 1.3);
- Fulcher 0.4 percent;
- PBMC240 3.4 percent;
- SCoPE2 18.3 percent.

Max cosine still does not see the progenitors as unfamiliar.

*Review notes (2026-10-02).* A code review found four things that change no
verdict; NB3c stays NO GO on three criteria.

- **The "beats max cosine" flag.** `summary.json` records it as true
  because the script passes it automatically when max cosine is chosen.
  Under NB3b's rule, which needs a strictly higher AUROC than max cosine,
  it is false.
- **Held-out AUROC.** NB3c pools all held-out classes into one AUROC over
  cells with at least 200 observed genes. NB3b averaged per-class AUROCs
  over all cells. So that column is not directly comparable between the
  two runs.
- **Diversity of the held-out controls.** They reuse their parent upload's
  diversity, which biases the two diversity schemes' held-out rejection.
- **Real data, in both NB3b and NB3c.** It is scored against every
  reference cell, while the thresholds were fitted on scores against the
  training split, as NB2 also did. A larger reference can only raise max
  cosine and kNN scores, so the reported real-data rejection rates are
  biased low.

---

## The throughline

Seventeen notebooks built end to end, three existing ones worked inside of. None of
this was planned as a sequence in advance, each notebook answered a question the
previous one's actual results raised. The diagnostics notebooks exist because v2
produced numbers that didn't add up on inspection. The masking notebooks exist
because the diagnostics traced several of those numbers to a fixed feature space
that couldn't handle a real dataset's actual coverage. v3 exists because the
masking comparison needed a full production run. The self training pilot exists
because v3's own results showed what still needed solving, and its failure plus
the cell line comparison ruled out two easy explanations. The prototype export
exists because the application needed artefacts v3 never saved, and while
producing them it found that restricting the label space mattered more than any
adaptation tried so far. NB1 exists because every Tier 1 choice needed a test bed
that did not use protein labels, and in building it found that the preprocessing
every real query receives was itself causing much of the failure. NB1b exists to
remove that cause, and succeeded on RNA while leaving one real protein question
open. NB1c exists because NB1b's two real datasets disagreed. It found that
the shipped SCoPE2 numbers were a lucky seed and that SCoPE2 cannot test a real
upload. NB1d exists to check that V2's result on raw data was not luck too. It
held across all five seeds, and V2 became the encoder going into NB2. A held
out dataset then confirmed it. NB2 exists because the product, once unrestricted,
abstained on half of a real PBMC upload. It found the causes in the service's own
calibration, replaced them with rules fitted on labelled RNA, and turned the result
into a specification the service now builds from.
