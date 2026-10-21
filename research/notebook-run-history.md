# VivOME, Every Notebook Run

In order, with what each one established. The existing notebooks come first,
since they predate everything built during this project, followed by every
notebook built and run over the course of it.

**SCoPE2's labels were swapped until 2026-10-04**
([bugs-and-fixes.md](benchmark/bugs-and-fixes.md), 8). Every SCoPE2
figure at class level in the entries before 22 was scored against them, and
each entry records what was printed at the time:

- **Restricted figures** (macrophage or monocyte only): the true value is
  100 minus the one shown.
- **Unrestricted balanced accuracy and recalls** changed in no simple way.
  The corrected values are in the rescored tables (entry 22).
- **Unaffected:**
  - group- and lineage-level correctness;
  - committed and abstention shares;
  - the "SCoPE2-like" RNA simulations, which carry their own RNA labels.

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

### 20. v4 pre-tests: `research/notebooks/v4_pretest.py`

**When and why.** On the PC, 2026-10-04, after the fair re-benchmark
(`research/benchmark/baseline-corrections.md`) put v3.1's best guess level
with simple, correctly scaled baselines. The owner asked for intensive
pre-testing before any plan.

**How.**
- Seven exploratory rounds ran in memory, writing nothing.
- They used development data only: SCoPE2, PBMC240, Fulcher 2026,
  Furtwängler 2025, and NB1's RNA simulation suites.
- **Khoury 2026 was not read.**
- A control reproduced v3.1's served best guesses exactly (Fulcher 57.94,
  every cell).
- The adopted design was then fixed in the committed script. Its outputs are
  in `research/notebook-outputs/v4_pretest/`.

**What the exploratory rounds found (in-memory figures):**

- **Query smoothing off** helps all three protein datasets:
  - Fulcher 57.9 → 61.7;
  - SCoPE2 restricted 61.3 → 64.9;
  - PBMC240 lymphoid recall 92.3 → 90.6, the one small loss.

  The RNA simulation prefers smoothing on, through single-type uploads
  (33.0 vs 26.8). Real protein was given priority, and the disagreement is
  recorded.
- **Class-balanced reference statistics** for re-encoding the reference
  (re-encoding with the stored statistics reproduces the served latents,
  median cosine 1.000000):
  - PBMC240 90.6 → 94.0;
  - Fulcher and SCoPE2 about +1.
- **Correlation to class means over each cell's observed genes** (9,002-gene
  space, class-balanced) is strong on Fulcher (69.6) but fails narrow
  uploads (13% on single-type) and PBMC240 (75). Fused with the encoder, it
  is the main gain.
- **No gain:**
  - kNN rules instead of centroids, and class-balanced kNN;
  - EM prior re-estimation (it collapses Fulcher to 51 and SCoPE2 to 50);
  - a reference matched to each upload's predicted composition.
- **Rejected:**
  - Whole-tissue reference expansion (Tabula Sapiens Lymph Node, Lung and
    Large Intestine). The frozen encoder rises on Fulcher, but SCoPE2
    restricted falls to 56.
  - Retraining V2 on blood plus tissues, one seed: Fulcher 59.1, SCoPE2 44.1,
    simulation 55.8, against a blood-only retrain at 61.4 / 63.0 / 57.8.
- **Training collapsed:** retraining with naive protein-like augmentation
  (RNA zeros masked, gene-wise power distortions, cell offsets) stopped at
  epoch 18, with the simulation at 17% and 90% of cells called progenitor.
- **Gated for later:** tissue cells for the rarest classes (mDC, pDC,
  basophil, Treg). Fulcher rises to 71.0 (DC 30%), but the simulation falls
  4 points.

**The committed run.** The fusion weight and temperature had been picked on
NB1's evaluation suite in memory. The script picks them on the calibration
suite instead:
- the grid is w ∈ {0.3, 0.5, 0.7} and τ ∈ {0.03, 0.05, 0.10};
- it chose **w 0.7, τ 0.05**, with 62.99 on the calibration suite;
- it then scored the evaluation suite once.

| Evaluation suite, per-upload balanced accuracy | v3.1 as served | Encoder, smoothing off, class-balanced | v4 candidate |
|---|---|---|---|
| All 240 uploads | 56.1 | 58.7 | **60.3** |
| PBMC-like | 61.9 | 72.2 | **74.3** |
| Mixed (5–8 types) | 62.7 | 70.1 | **72.5** |
| Single type | **33.0** | 26.8 | 26.9 |
| SCoPE2-like | **68.9** | 65.4 | 65.5 |

| Development data, all 85,233 reference cells (as v4 will serve) | v4 candidate |
|---|---|
| Fulcher, six types | 65.5 (NK 86, DC 4, CD8T 24) |
| PBMC240 lymphoid / myeloid recall | 93.2 / 100 |
| SCoPE2 restricted / unrestricted | 67.4 / 6.8 |
| Fulcher vs Furtwängler, max-probability AUROC | 0.804 (v3.1 0.748) |

These are Phase 2's gate figures (research/todo.md, Track G).

**Declared.**
- The development datasets were looked at throughout the exploration, so
  their figures are development numbers, not tests. Only the selection is
  clean, made on the calibration suite.
- The exploratory rounds' code was not kept; only the adopted design is in
  the script.
- Unsolved:
  - CD8T, under 30% for every method: Fulcher measures neither CD4 nor
    CD8A, and CD8B, GNLY, NKG7, KLRD1 and CD79A are outside the gene space;
  - single-type uploads;
  - out-of-reference cells: 43% of Furtwängler's CD34+ cells are still
    called T cells.

**Addendum, 2026-10-04: SCoPE2's labels.** Every SCoPE2 figure above was
scored against swapped labels (entry 22). Restricted figures convert
exactly (100 minus the figure shown), so the in-memory calls can be read
again:

- **Query smoothing off:** SCoPE2 restricted goes from 38.7 to 35.1, a loss
  rather than a gain. Its case now rests on Fulcher (+3.8), against the RNA
  simulation, which prefers smoothing on.
- **Class-balanced statistics:** SCoPE2 about −1 rather than +1. PBMC240's
  +3.4 stands.
- **Whole-tissue reference expansion:** SCoPE2 restricted rises to 44 rather
  than falling to 56, and Fulcher rises too. The reason it was rejected no
  longer holds, and it is reopened.
- **Retraining on blood plus tissues:** SCoPE2 is 55.9 against the
  blood-only retrain's 37.0, a reversal. Fulcher (59.1 against 61.4) and the
  simulation (55.8 against 57.8) still favour blood only.
- **EM prior re-estimation:** SCoPE2 at 50 is chance either way.
- **The committed run, rerun:** the selection, the evaluation suite and the
  per-cell predictions are byte for byte the same. SCoPE2 restricted /
  unrestricted is 32.6 / 0.7 for the v4 candidate, against v3.1's 39.7 / 0.0
  in the same run.

### 21. v4 calibration (Track G, Phase 3): `research/notebooks/v4_calibration.py`

**When and how.** On the PC, 2026-10-04. The rules were fixed in the
script's docstring before the run; it writes its sha256 and start time
to `rules.json` before computing anything.
- **Cells:** NB3c's split, which the encoders never saw: 240 calibration
  uploads from `te_cal`, 240 evaluation uploads from `te_eval`.
- **References:** train and validation cells only, for v4 and for the
  v3.1 comparator alike.
- **Code path:** the service's own, from `_prepare_query` through
  `fusion.project_prepared` (v4) and `ensemble.project_prepared` (v3.1).
- **Run 1** completed the evaluation, then crashed while writing its
  summary (a numpy boolean is not JSON-serialisable), before any number
  was shown. The one-line fix casts the checks to `bool`. **Run 2**
  reproduced run 1's 125,890 per-cell rows exactly. Outputs are in
  `research/notebook-outputs/v4_calibration/`.

**Fitted on the calibration suite:**
- Mondrian qhat: marginal 0.964, from 66,881 cells with at least 200
  observed genes;
- out-of-distribution threshold 0.772;
- refitting with the served all-cells bundle moves a qhat by at most 0.007.

**Evaluation suite, scored once: NO GO.**

| Cells with at least 200 genes (62,945) | v3.1 | v4 | Pre-set check |
|---|---|---|---|
| Coverage | 87.1% | 89.7% | pass (≥ 88, ≥ v3.1) |
| False abstention | 0.4% | 0.7% | pass (≤ 3) |
| Correct when committed | 97.0% | 97.4% | pass (≥ 94) |
| Best guess, per-upload balanced | 60.6 | 64.0 | pass (≥ v3.1 + 2) |
| Largest scenario drop | | single type: 8.6 points below v3.1 | **fail** (≤ 3) |

Best guess against v3.1, by scenario:

| Scenario | v4 against v3.1, points |
|---|---|
| PBMC-like | +12.3 |
| Mixed | +10.6 |
| Narrow | +2.1 |
| Lineage | +1.3 |
| SCoPE2-like | +0.3 |
| Single type | **−8.6** |

**Not a pre-set check, but a regression:** v4 commits on 56.7% of cells
against v3.1's 88.6%, and abstains on 43.3%, almost all as ambiguous.
- **The cause:** the fused probability is flatter than the encoder's, so
  the conformal sets grow and often span lineages.
- **Answer levels,** v4 against v3.1:
  - class 8.6% against 20.8%;
  - group 8.1% against 17.9%;
  - lineage 40.0% against 49.9%.

**Consequence.**
- The v4 spec is not frozen, and v4 stays unserved.
- Two causes to address in a follow-up, with its rules fixed before it
  runs and a fresh evaluation suite, since this one has been scored:
  - **single-type uploads:** v4 has smoothing off and fuses in a
    correlation term, and per-upload z-scoring removes a single type's
    signal;
  - **set width under fusion:** for example, conformal sets from the
    encoder's probability with the fused best guess, or a sharpened fused
    probability.

### 22. SCoPE2's labels corrected, every SCoPE2 table rescored (scripts, 2026-10-04)

**Why.** Track G's reprocessing of SCoPE2 took labels from the experimental
design and found 814 macrophages to 314 monocytes. VivOME's copy had a
monocyte majority. The authors' curated object (SingleCellMultiModal,
EH4694) disagrees with VivOME's label on all 1,490 cells, and the markers
side with the curated labels
([bugs-and-fixes.md](benchmark/bugs-and-fixes.md), 8).

**What ran,** one job at a time on the PC:

1. `python -m benchmark.scope2_labels --apply`. It fixed every copy of the
   labels, changing only the label fields. It then recomputed v3's three
   SCoPE2 evidence tables from v3's saved latents, after reproducing their
   old values with the old labels.
2. `benchmark.baselines_score` and `benchmark.baselines_corrected_score`.
   Only the SCoPE2 tables and paired bootstraps changed; the Fulcher and
   PBMC240 tables regenerated byte for byte.
3. `benchmark/scope2_5seed_scores.py` (new). It rebuilds Track D's per-seed
   table and NB1d's own SCoPE2 figures from the saved latents, after first
   reproducing each with the old labels to 1e-9.
4. `benchmark/scope2_5seed_paired.py`.
5. `benchmark.v31_service_flags` and `benchmark.v31_dev_gate`. The gate
   passed and its record is unchanged.
6. `research/notebooks/v4_pretest.py` and `benchmark.v4_dev_gate`. The gate
   passed, with 100% per-cell agreement.
7. `scripts/v31_evidence.py`, then `scripts/build_manifest.py`.

**What changed.**

- **Restricted figures** became 100 minus the old ones:
  - v3 (`v3_seed0`) 79.8 → 20.2, and its 5-seed mean 63.3 → 36.7;
  - v3.1 61.3 → 38.7;
  - scANVI 77.7 → 22.3;
  - only Harmony with nearest centroid, 63.0, is above chance.
- **Unrestricted figures** fell for nearly every method: v3 31.1 → 0.7, and
  v3.1 1.1 → 0.0.
- **v3's macrophage-vs-monocyte AUROC** is 0.072.
- **Unchanged:** group- and lineage-level correctness, committed and
  abstention shares, everything on other datasets.

**Not recomputed:**

- NB1d's smoothing-off unrestricted figures, left empty, since NB1d did not
  save those latents;
- figures printed in the notebooks of entries before this one (see the
  note at the top). NB1b's and NB1c's tables were corrected in place:
  restricted figures exactly, unrestricted ones where the same model's
  corrected value is known.

### 23. v4 Phase 3b (Track G): `research/notebooks/v4_phase3b.py`

**Why.** Phase 3 (entry 21) failed on single-type uploads, and its sets
were too wide. The owner chose to fix both. An exploration on the
calibration suite and the development data (never the evaluation pool)
traced the wide sets to conformal sets fitted on the fused probability, and
the single-type loss to smoothing off. Hence the design:
- **Answers:** v3.1's conformal sets, abstention and answer levels;
- **Best guess:** v4's fused guess, which joins non-empty sets;
- **The guess's encoder probability:** a mix of the smoothed and
  unsmoothed query's, with a smoothed share s;
- **Fusion:** w 0.7 and τ 0.05, as before.

**When and how.** On the PC, 2026-10-04 23:53 to 2026-10-05 00:18. The
rules were fixed in the script's docstring before the run; `rules.json`
records the script's sha256 (`9ccc2c26…`, which matches the file) and the
start time.
- **Candidates:** s in {0, 0.5, 1}.
- **Selection:** on NB3c's calibration suite (240 uploads, 66,881 cells
  with at least 200 observed genes).
- **Evaluation:** a fresh suite of 240 new uploads from NB3c's `te_eval`
  cells (seed 20261004; 60,509 cells with at least 200 genes). It was
  written before it was scored. Phase 3 had scored the same cells once, in
  other uploads.
- **Code path:** the service's own, as in Phase 3.

Outputs are in `research/notebook-outputs/v4_phase3b/`.

**Selection, calibration suite:**

| | Best guess, per-upload balanced | Committed | Largest scenario drop | Eligible |
|---|---|---|---|---|
| v3.1 | 58.57 | 87.69% | | |
| v4, s = 0 | 62.37 | 85.00% | 6.35 | no |
| v4, s = 0.5 | 64.10 | 86.90% | 2.09 | yes |
| v4, s = 1 | 64.19 | 87.48% | 0.52 | yes |

s = 0.5 and s = 1 tied within 0.5 points. The tie went to Fulcher (65.0
against 63.5), so **s = 0.5**.

**Evaluation suite, scored once: NO GO.**

| Cells with at least 200 genes (60,509) | v3.1 | v4 | Pre-set check |
|---|---|---|---|
| Coverage | 88.28% | 87.59% | **fail** (≥ 88, ≥ v3.1) |
| False abstention | 0.37% | 0.37% | pass (≤ 3) |
| Correct when committed | 97.62% | 97.55% | pass (≥ 94) |
| Committed | 86.74% | 86.00% | pass (≥ v3.1 − 2) |
| Best guess, per-upload balanced | 59.60 | 64.69 | pass (≥ v3.1 + 2) |
| Largest scenario drop | | single type: 5.41 points below v3.1 | **fail** (≤ 3) |

Best guess against v3.1, by scenario:

| Scenario | v4 against v3.1, points |
|---|---|
| PBMC-like | +13.0 |
| Mixed | +10.6 |
| Lineage | +6.7 |
| Narrow | +3.3 |
| SCoPE2-like | +1.0 |
| Single type | **−5.4** |

**Development data,** s = 0.5 against v3.1:
- Fulcher, six types: 65.0 against 57.9;
- PBMC240 lymphoid recall: 90.6 against 92.3;
- SCoPE2 unrestricted: 0.3 against 0.0;
- out-of-reference AUROC: 0.813 against 0.744.

**Diagnosis,** from the saved per-cell rows (nothing refitted or rescored):

- **Both misses come from single-type uploads.**
  - Coverage there is 72.2% against v3.1's 77.4%.
  - Elsewhere, v4's coverage is higher: 91.5% against 91.1%.
- **Coverage.** v4's set is v3.1's conformal set with the fused guess
  added *in place of* v3.1's top label, not beside it. So the answers were
  not exactly v3.1's, as the design stated. The gate built its comparison
  the same way, so it did not catch this.
  - **Cells that lost coverage:** 807. In every one, v3.1's top label was
    the true class, outside the conformal set, and v4's guess was another
    class. 690 of them are in single-type uploads, and 645 of those are
    neutrophils.
  - **Cells that gained coverage:** 386.
- **Single type.** 35 uploads. CD8 T cells (5 uploads, 20.9 points lower
  each) and neutrophils (4 uploads, 15.0 lower) make up 164 of the 189
  points lost.
  - **The cause:** z-scoring each gene within an upload removes a single
    type's contrast, and the correlation term needs that contrast.
  - **The selection's estimate was optimistic:** 2.1 points on the
    calibration suite. Single-type figures vary widely between suites;
    v3.1 itself scores 33.7 on the calibration suite and 47.1 here.
- **Per cell, the best guess is level:** 60.6% correct against v3.1's
  60.7%. The per-upload balanced gain comes from better recall of each
  upload's minority types.

**Consequence.**
- The v4 spec is not frozen, and v4 stays unserved.
- `spec_v4.json` keeps its smoothed share unset and its evaluation pending.
  `spec_block.json` records the failed evaluation.
- `te_eval`'s cells have now been scored in two suites. A further
  evaluation drawn from them is weaker evidence than this one.

### 24. v4 Phase 3c (Track G): `research/notebooks/v4_phase3c.py`

**Why.** Phase 3b's two misses both came from single-type uploads (entry
23). The owner chose to explore a fix on calibration data first, then fix
one rule and score it once.

**The exploration** (2026-10-05, outside the repository; its record is
`research/notebook-outputs/v4_phase3c/exploration.json`):
- **Data:** NB3c's calibration cells and the development data only.
  - the 240-upload calibration suite;
  - 60 extra single-type uploads drawn from `te_cal`, 4 per class with at
    least 20 cells (`exploration_single_type_suite.json`).
- **Method:** every cell's ingredients were cached once through the
  service's code. The cache reproduced Phase 3b's best guesses on all 66,881
  calibration cells and its development figures exactly.
- **Single-type losses on calibration cells:** the same types as Phase 3b's
  evaluation. CD8 T −22.3 points, neutrophil −14.2, erythrocyte −9.7.
- **Why they lose:** in a single-type upload, the correlation term's top
  class is scattered. It named neutrophils for 25% of real neutrophils,
  against 83% when other types are present. Confident-looking correlation
  was wrong there too, so per-cell gates on its strength did not help.
- **The signal that worked: upload agreement,** the share of an upload's
  cells whose top class under the correlation term is v3.1's top class.
  - Median by scenario: single type 0.20, against mixed 0.68 and PBMC-like
    0.57.
  - On the development data: Fulcher 0.42, PBMC240 0.37, SCoPE2 0.17,
    Furtwängler 0.18.
- **Robustness:** the share of resampled 35-upload single-type suites more
  than 3 points below v3.1. Phase 3b's rule fails 29% of them. That fits its
  evaluation, which drew CD8 T and neutrophil uploads often.
- **Finalists:**
  - A, smoothed only, correlation everywhere: 0.6% fail;
  - B, the rule below: 0.1% fail;
  - C, smoothed with the gate;
  - D, gated on the share of v3.1's commonest guess.
- **Rejected:** a lower fusion weight, and per-cell gates on the
  correlation's strength.
- **Choice:** the owner chose B (2026-10-05). The comparison shown then did
  not include D, which had first been set aside without its full figures. D
  was measured afterwards and B kept: D has a worse worst type, PBMC240 and
  AUROC.

**The rule,** fixed before the run (in the script's docstring; `rules.json`
records the script's sha256 `2ae56060…` and the exploration record's
`e2ea79d2…`, both matching the files):
- **Answers:** v3.1's. v4's best guess joins every non-empty set *beside*
  v3.1's own, so v4's sets contain v3.1's.
- **At or above an upload agreement of 0.4:** 0.7 × (0.5 smoothed + 0.5
  unsmoothed class-balanced encoder) + 0.3 × softmax(r / 0.05).
- **Below 0.4:** the correlation term is flat and the encoder is the
  smoothed query's alone.
- **Coverage check:** coverage must not fall below v3.1's (the owner's
  decision, 2026-10-05). v4's sets contain v3.1's, so an absolute floor would
  test v3.1's calibrator. That calibrator covered 85.7%, 87.1% and 88.3% on
  the last three suites.
- **The other GO checks:** as in Phase 3b.

**When and how.** On the PC, 2026-10-05 10:50 to 11:15.
1. **Implementation check:** on the calibration suite, the service
   reproduced the exploration's figures for both methods exactly (every
   difference 0.00).
2. **Development figures.**
3. **A fresh evaluation suite,** `eval_v4c`: 240 new uploads from NB3c's
   `te_eval` cells (seed 20261005; 62,082 cells with at least 200 genes),
   written before it was scored.
   - **Declared:** Phases 3 and 3b scored these cells in other uploads, and
     Phase 3b's diagnosis of them prompted this design. So this is weaker
     evidence than a first look.
   - **The SCoPE2-like mix is reversed:** those uploads keep NB1's 26%
     macrophage share, taken from SCoPE2's swapped labels. Their labels are
     right.

**Evaluation suite, scored once: GO.**

| Cells with at least 200 genes (62,082) | v3.1 | v4 | Pre-set check |
|---|---|---|---|
| Coverage | 88.98% | 89.23% | pass (≥ v3.1) |
| False abstention | 0.26% | 0.26% | pass (≤ 3) |
| Correct when committed | 97.41% | 97.49% | pass (≥ 94) |
| Committed | 88.97% | 88.51% | pass (≥ v3.1 − 2) |
| Best guess, per-upload balanced | 59.26 | 64.73 | pass (≥ v3.1 + 2) |
| Largest scenario drop | | none: every scenario at or above v3.1 | pass (≤ 3) |

Best guess by scenario, and how often the correlation term was used:

| Scenario | v3.1 | v4 | Correlation term used |
|---|---|---|---|
| PBMC-like | 57.9 | 71.6 | 100% of uploads |
| Mixed | 68.3 | 77.4 | 98.5% |
| SCoPE2-like | 65.9 | 71.0 | 0% |
| Narrow | 57.2 | 61.3 | 58.0% |
| Lineage | 60.5 | 63.0 | 55.9% |
| Single type | 41.8 | 42.1 | 8.6% |

- **Per cell,** the best guess is right on 61.5% of cells against v3.1's
  58.3%.
- **Single-type uploads still losing:** neutrophil (3 uploads, −8.8 points)
  and erythrocyte (3, −7.0).

**Development data,** v4 against v3.1, through the served all-cells bundle:
- **Fulcher, six types:** 65.0 against 57.9. The correlation term was used
  (agreement 0.42).
- **PBMC240 lymphoid recall:** 92.3, the same. The term was flat (0.37).
- **SCoPE2 unrestricted:** 0.0, the same. The term was flat (0.17).
- **Out-of-reference AUROC:** 0.829 against 0.744.

**Then:**
- `scripts/build_v4_bundle.py --spec-only` recorded the passed evaluation in
  `spec_v4.json`, so the service now serves v4 on request. v3.1 stays the
  default.
- `benchmark.v4_dev_gate` passed:
  - 100% per-cell agreement with an independent recomputation on all four
    development datasets;
  - the gate's decision the same as the service's on each;
  - every answer v3.1's with the guess joined;
  - every figure exact.
- v4's responses were frozen (`service/tests/fixtures/v4_full_*.json`).

**What this does not show.** v4 against the corrected baselines. On Fulcher
it is ahead of the best of them (Harmony with nearest centroid, 63.0;
correlation, 62.1). But Fulcher is development data that shaped v4's design,
and no paired bootstrap has been run. That is Phase 4; the claim needs the
sealed test (Phase 5).

### 25. v4 Phase 4 (Track G): v4 against the corrected baselines (scripts, 2026-10-05 to 07)

**What ran,** one job at a time on the PC:
1. `benchmark/baselines_v4.py`: v4 as served on every development upload,
   and v3.1 on the reprocessed SCoPE2.
2. `benchmark/baselines_v4_score.py`: v4 against every corrected baseline
   run and against v3.1. It uses `baselines_score.py`'s functions and
   bootstrap, and writes to `research/benchmark/v4_development/`. The
   existing tables are not rewritten.
3. `benchmark/khoury2026_posthoc_v4.py`: Khoury 2026, post-hoc.
   - **Step 1, label-free:** v4 on the upload.
   - **Step 2:** scoring with the sealed scorer's code, after checking
     v3.1's row against the sealed tables.
4. The corrected baselines on the reprocessed SCoPE2:
   - **The run:** `benchmark/baselines_corrected_queue.sh scope2_reprocessed`,
     in the owner's terminal.
   - **The setup:** the dataset was added to the corrected runner as its
     own tuple, so the existing tables are unchanged.

**Results** (research/benchmark/results.md, "v4 against the corrected
baselines"):
- **The Phase 4 checks pass.** No paired CI favours v3.1 on any development
  dataset, and correct-when-committed drops by at most 0.05 points.
- **Fulcher (development):** v4 65.0 against v3.1's 57.9, +7.1 (CI 5.2 to
  9.1).
  - Level with Harmony NC (63.0) and the correlation baseline (62.1): CIs
    include zero.
  - Ahead of every other baseline.
- **Khoury (post-hoc):** v4 61.8 against v3.1's 56.9, +4.9 (CI 3.4 to 6.3).
  - Level with PCA kNN (62.8) and scANVI kNN.
  - Ahead of the rest.
- **PBMC240:** unchanged at 92.3, still the best.
- **SCoPE2:** Harmony NC is the only method above chance.
- **SCoPE2 reprocessed** (1,128 cells): v3.1 and v4 both at about 33%
  restricted and 5.5% unrestricted.
  - Every corrected baseline is at or below chance restricted (41.8 to 51.8).
  - Harmony NC falls from 63.0 on the published matrix to 48.9.
  - Run in the owner's terminal, 2026-10-07: 15 runs, all completed.

**What followed.** The owner asked for v4 to beat the baselines, not match
them (v4.1, below).
- **Diagnosis on Fulcher** (development data; Khoury not read):
  - v4 and Harmony share their errors: both are wrong on 17.5% of cells,
    and each is uniquely right on only 5–6%.
  - Stacking Harmony's scores adds about 1.5.
  - v4's own correlation term scores 69.6 alone, against the encoder's
    61.0.
  - Its 0.7 encoder weight was chosen on simulated RNA uploads, where the
    encoder never crosses the modality gap.
- **The plan:** choose the gate-on weight on Fulcher under fixed rules
  (Phase A, `research/notebooks/v41_pretest.py`), then check it once on
  Khoury (Phase B).

### 26. v4.1 (Track G): Phases A to D, 2026-10-07

**Why.** v4 matched the best simple baselines but did not beat them
(entry 25). The owner asked for a clear win and decided:
- choose v4's encoder weight where the correlation term is used, on
  Fulcher, under fixed rules;
- check that weight once on Khoury;
- keep a baseline pre-layer as a research arm only.

**Phase A, the pre-test.**
- **`research/notebooks/v41_cache.py`** caches every calibration and
  development cell's four ingredients through the service's code. It
  reproduced Phase 3c's records exactly before writing anything.
- **`research/notebooks/v41_pretest.py`** recorded its rules and sha256
  first. It tried 15 candidates: gate-on weight 0.2 to 0.7 × correlation
  temperature 0.05 to 0.1.
- **Guardrails:**
  - the calibration suite within 1 point of v4;
  - every scenario within 2 points of v4 and 3 of v3.1;
  - single-type p_fail at most 1%;
  - committed share within 2 points of v3.1;
  - PBMC240 and both SCoPE2 versions within 2 points of v4.
- **Objective:** Fulcher, with a stability rule over 200 halvings of its
  runs.
- **Result:**
  - The ~71.5 options (weights 0.2 to 0.4 at τ 0.05) failed the guardrails:
    committed share and the PBMC-like scenario.
  - Three candidates were stable, all at about 69.1 on Fulcher.
  - **Locked: weight 0.5, τ 0.05**, the stable one closest to v4. Fulcher
    69.05 (in-sample).
  - **Research arm:** Harmony NC or PCA kNN blended on top does not help.
    Harmony at β 0.33 lifts Fulcher to 70.3 but drops PBMC240 from 92.3 to
    77.8.

**Phase B, the cross-lab check** (`benchmark/khoury2026_posthoc_v41_check.py`;
its verdict was written before Phase A ran):
- **Verdict: carries over.**
- Khoury, post-hoc: v4.1 62.5 against v4's 61.8, +0.7 (CI −0.04 to 1.5).
- NK recall 45.9 → 50.7.
- Still level with PCA kNN (62.8).

**Phase D, the service.**
- **The code:** `"v4.1"` is v4's code and data with its own spec
  (`service/model/v4_1/`, `scripts/build_v41_spec.py`). Its MANIFEST pins
  v4's data files.
- **The gate:** `benchmark/v41_dev_gate.py` passes, with 100% per-cell
  agreement and Fulcher 69.05 as Phase A.
- **v4 is unchanged,** and v4.1 answers exactly as v4 wherever its
  correlation term is flat.
- **The cost:** the out-of-reference AUROC of the best guess's probability
  is 0.790, against v4's 0.829 and v3.1's 0.744. Out-of-distribution
  abstention is v3.1's and unchanged.

**Phase C, the pre-registered evaluation** (`research/notebooks/v41_phase3.py`;
rules and sha256 recorded first).
- **Implementation check:** the service reproduced Phase A on the
  calibration suite exactly.
- **The suite:** fresh, from `te_eval` cells (seed 20261007; 64,779 cells
  with at least 200 genes), written before it was scored.
  - **Declared:** this is those cells' fourth use, so it is a safety check
    on simulated RNA uploads, not evidence of the protein gain.

**Verdict: GO; all eight checks pass.**

| | v3.1 | v4 | v4.1 |
|---|---|---|---|
| Best guess, per-upload balanced | 60.6 | 65.4 | 65.0 |
| Coverage | 86.7% | 87.2% | 87.2% |
| Committed; correct when committed | 86.9%; 96.0% | 86.4%; 96.2% | 85.8%; 96.3% |
| False abstention | 0.5% | 0.5% | 0.5% |

- Against v4, v4.1 is at most 0.75 points lower in any scenario.
- Its correlation term was used in 97% of mixed and 94% of PBMC-like
  uploads, and 11% of single-type ones.

**Then:**
- `scripts/build_v41_spec.py` recorded the pass, so v4.1 serves on request.
  v3.1 stays the default.
- The v4.1 gate passed again.
- v4.1's responses were frozen (`service/tests/fixtures/v41_full_*.json`).

**What this does not show.** Fulcher chose the weight, so its 69.05 is
in-sample. Khoury's +0.7 is post-hoc. The simulated suite is a safety check.
"v4.1 beats the corrected baselines" needs the sealed test.

---

### 27. v5 and v5.1 (Track H): cleaned reference labels, retrained members, 2026-10-12

**Why.** Every method fails CD8 T: v4.1 recalls 2.7% on Khoury and 24% on
Fulcher. Read on the reference only (no protein label):
- **The labels:** 1,657 of the 4,572 cells Tabula Sapiens labels CD8 T are NK
  by its own `free_annotation`, and the markers agree.
- **The encoder:** V2, trained with those labels, merges CD8 T and NK
  (centroid cosine 0.99; 49% recall of the reference's own CD8 T).

**Phase 0, the labels** (`research/notebooks/v5_labels.py`). 2,011 cells in
the T and NK block were relabelled by `free_annotation`. The cleaned CD8 T
class expresses CD3D in 66% of cells (41% before).
- A planned move of 930 "dendritic cells" and "macrophages" out of
  "monocyte" was dropped: their markers are monocyte's (CD1C 0.6%).

**Phase 1, the current encoder with cleaned centroids**
(`research/notebooks/v5_checkpoint.py`).
- **Result:** no CD8 T gain (41.5 → 39.8 in simulated multi-type uploads).
- **So the encoder is the bottleneck.**

**Phase 2, retraining** (`research/notebooks/v5_train.py`, NB1d's recipe on
this PC's GPU).
- **The reproduction passed:** NB1d's seed 1 validation loss was matched
  exactly, then retrained within tolerance.
- **The five cleaned members:** CD8 T–NK cosine 0.66–0.71; reference CD8 T
  recall 77–80%.

**Phase 3, the build** (`research/notebooks/v5_build.py`, NB2's recipe).
- **Its self-test reproduces v3.1's spec from v3.1's members:**
  - the temperatures and the out-of-distribution threshold exactly;
  - the conformal thresholds within one rank. Plasma cell is one rank off
    from GPU rounding; the check was amended to be rank-based, and the
    amendment is recorded in the docstring.

**v5: not evaluated.** The smoke run's development figures, which are the
same as the real run's, fail both guardrails:
- Fulcher 58.5 against v4.1's 69.05;
- PBMC240 89.7 against 92.3.

**The diagnosis** (`research/notebooks/v5_diagnose.py`):
- **Fulcher:** the drop is the agreement gate alone. v5's agreement is 0.383,
  under the 0.4 bar; with the correlation term forced on, v5 scores 69.4.
- **Simulation:** v5 moves NK errors into "mature NK T" (34% of NK cells).
- **That class is NK by markers:** CD3D 7%, TRAC 13%, KLRF1 92%.

**v5.1** (`research/notebooks/v51_labels.py`): NK T folded into NK. The
class stays, with no cells, so it is never chosen.
- **The members:** reference CD8 T recall 81–84%, NK 98–99%.

**v5.1's pre-registered evaluation** (`v5_phase4.py --version v5.1`).
- **The terms:** truth is v5.1's labels; the rules are unchanged; the suite
  is a fresh eval_v51 (te_eval's fifth use).
- **Two risks were declared before the run:** the scope2-like scenario and
  the CD8 T margin.
- **The implementation check:** exact.

**Verdict: NO GO.** Nine of ten checks pass. The scope2-like scenario is 2.94
points below v4.1, against a bound of 2.

| | v3.1 | v4.1 | v5.1 |
|---|---|---|---|
| Best guess, per-upload balanced | 60.8 | 66.2 | 67.0 |
| CD8 T recall, multi-type uploads | 59.8 | 47.9 | 60.8 |
| NK recall, multi-type uploads | 28.6 | 35.3 | 41.3 |
| Coverage; false abstention | 89.0%; 0.55% | 89.8%; 0.55% | 90.4%; 0.17% |
| Fulcher; PBMC240 lymphoid | 57.9; 92.3 | 69.05; 92.3 | 69.09; 91.5 |

**What this shows.**
- **On the reference,** cleaning the labels fixes the CD8 T and NK merge.
- **In simulated uploads,** v5.1 restores the CD8 T recall that v4.1's
  correlation term costs, and raises NK.
- **Under the original labels** it trails (61.0 vs 64.2), so the gain rests
  on the marker-based relabelling.
- **Fulcher cannot show a CD8 T gain:** it measures no CD8A.
- **v5.1 is not served:** its spec records the failed evaluation.

**Khoury 2026, post-hoc, once** (`benchmark/khoury2026_posthoc_v51_check.py`,
the owner's choice, 2026-10-13).
- **Its reproductions passed exactly:** v4's saved guesses, the service's
  v5.1 guesses, and v4.1's recorded Khoury scores.
- **Verdict, fixed in the plan: carries over,** barely. Balanced accuracy
  62.7 vs v4.1's 62.5 (+0.2, CI −0.9 to 1.4).
- **Per type, v5.1 against v4.1:** CD8 T 7.8 vs 2.7; NK 56.7 vs 50.7; CD4 T
  71.3 vs 82.8.
- **The confusion shows the real limit:** 262 of Khoury's 333 CD8 T cells are
  called CD4 T. Of v5.1's 192 CD8 T calls, only 26 are right; 104 are CD4 T.
  On protein data CD8 T fails against CD4 T, not against NK. Cleaning the
  reference's CD8 T and NK labels does not reach that.

**Provenance.** v5's records were written before the scripts gained their
v5.1 options (`--variant`, `--version`), whose defaults keep v5's
behaviour, so they carry those earlier versions' sha256s. The records are
`research/notebook-outputs/v5_train/`, `v5_build/` and
`v5_diagnose/diagnosis.json`. Every v5.1 record matches the committed
scripts.

---

### 28. Why CD8 T fails on protein data (Track H), 2026-10-13

`research/notebooks/cd8_cd4_diagnosis.py` →
`research/notebook-outputs/cd8_cd4_diagnosis/diagnosis.json`. A diagnosis
that chooses nothing. Khoury's labels are read post-hoc; the reference part
reads no protein label.

**Every method fails Khoury's CD8 T cells:** PCA kNN recalls 0.9%,
correlation 0.9%, Harmony 3–6%, scANVI kNN 1.8–34%, v4.1 2.7%
(`research/benchmark/khoury2026_posthoc/per_seed_scores.csv`).

**1. Khoury's CD8 and CD4 clusters split on T-cell state, not lineage.**
The protocol names its CD8 T cluster by CD8A and GZMA. In its own data:

| Separating Khoury's CD8 cluster from its CD4 cluster | AUC |
|---|---|
| CD8A, in the 248 cells where it is measured | 0.61 |
| S100A4, lower in the CD8 cluster | 0.93 |
| ANXA1, lower in the CD8 cluster | 0.91 |

- **No separation on the naming markers:** GZMA is detected in 34% vs 38%;
  CD4 in 4% of both.
- **High S100A4 and ANXA1 mark memory and effector T cells.** The "CD8"
  cluster looks largely naive, the "CD4" cluster largely memory.

**2. Every model calls Khoury's CD8 cluster naive CD4 T:** v3.1 79%, v4.1
54%, v5.1 41%. The rest is mostly CD4 T.

**3. The reference has almost no naive CD8 T cells under a CD8 label.**
- **The annotation:** `free_annotation` names 6. The CD8 T class is
  effector and memory: CCR7 4%, GZMA 92%, CCL5 92%.
- **Where they sit instead:** 356 cells look naive CD8 by RNA (CD8A or CD8B,
  CCR7, LEF1 or SELL, no cytotoxic genes, no CD4). Of these, 320 are
  labelled CD4 T and 26 naive CD4 T.
- **More loosely,** the CD4 T class holds 922 CD8A/B-positive, CD4-negative
  cells, 518 of them naive-like.

**So CD8 T on Khoury fails twice over.**
- **Khoury's labels:** they mostly encode naive against memory. Its CD8 T
  recall is a weak target and should not be tuned toward.
- **Our reference:** it gives naive CD8 T cells no home but CD4 T.

v5's CD8/NK cleanup did not touch either.

---

### 29. v5.2 (Track H): CD4/CD8 T labels corrected with Hao et al. 2021, 2026-10-13

**Why:** entry 28 found that the reference files naive CD8 T cells under
CD4 T.
- **The owner's dataset search** found no new public proteomics test set,
  but verified Hao et al. 2021 (GEO GSE164378): 161,764 PBMCs with RNA and a
  228-antibody surface panel, whose `celltype.l2` includes CD8 Naive (10,768
  cells).
- **The owner chose** to relabel Tabula Sapiens with a classifier trained
  on Hao.

**Labels** (`research/notebooks/v52_labels.py`).
- **The classifier:** logistic regression on 2,012 genes (24 markers),
  trained on 84,387 of Hao's T and NK cells.
- **The gate,** on held-out donors P7 and P8, at P ≥ 0.9: CD4-lineage cells
  called CD8 T 1.004%, against a 1% bound, so it failed and nothing was
  relabelled.
- **The amendment** (owner, stricter): threshold 0.95. The gate then passed
  (0.79%, 0.83%).
- **Moves, only between the CD4 and CD8 lineages:**
  - 932 cells CD4 → CD8 T: CD8A 82%, CD8B 88%, CD4 1.5%, mostly naive;
  - 407 CD8 T → CD4: CD4 41%, CD8B 4%, granzymes high, so cytotoxic CD4 T.
  - The CD4 T class's CD8A/B detection falls from 19.7% to 2%.

**Members:** five, as v5.1; reference CD8 T recall 82–85%, NK 98%.

**Diagnosis** (`v5_diagnose.py --version v5.2`). Calibration suite, v5.2's
truth, multi-type uploads:

| | v4.1 | v5.1 | v5.2 |
|---|---|---|---|
| Overall, per-upload balanced | 59.3 | 59.3 | 61.8 |
| CD8 T recall | 26.1 | 34.5 | 47.9 |
| NK recall | 48.1 | 59.7 | 61.7 |
| CD4 T recall | 52.1 | 60.7 | 60.0 |
| Naive CD4 T recall | 78.4 | 67.5 | 63.7 |
| Scope2-like scenario | 72.2 | 68.7 | 73.6 |

- **Every scenario group** is at or above v4.1, or within 0.3 points.
- **Answers:** coverage 85.8% (v3.1 84.0%); committed 89.7%; correct when
  committed 96.1%.
- **Naive CD4 is what it gives up:** naive CD8 and naive CD4 T cells now
  differ mainly in CD8 and CD4 themselves.

**Development (in-sample):**
- **Fulcher:** 69.6 (v4.1 69.05). CD8 T 29.3, NK 94.0, DC 25.9, but CD4 T
  71.8 against 82.5.
- **PBMC240 lymphoid recall:** 89.7 against 92.3, below the pre-registered
  guardrail (at most 2 points of loss) by about one cell.
- **So its Phase 4 would be a certain NO GO.** It was not run.

### 30. The marker audit (Goal 2, Phase 1.1), 2026-10-16

**Why:** the 9,002-gene input space lacks most canonical markers (CD8B, CCR7,
SELL; GNLY, NKG7, KLRD1, KLRF1; CD79A; CD1C, CLEC4C, LILRA4, IL3RA, CLEC9A,
FCER1A; CD68, CD163). If single-cell proteomics measures them, adding them to
the best guess's correlation term (Phase 2a) could help the weak classes.

**How** (`research/notebooks/marker_audit.py`; rules in its docstring before
the run; development data only, no Khoury, no held-out set):
- detection in Fulcher 2026, PBMC240, PXD070599 DS18 (three searches) and
  DS19, and Furtwängler 2025;
- Rieckmann 2017's sorted bulk proteomes: the donors with a two-fold
  difference between the confused populations;
- the reference RNA's AUROC for each pair, under v5.2's labels.

**Result** (`research/notebook-outputs/marker_audit/`):
- **The missing markers do separate the confused populations in deep bulk
  proteomes:** in Rieckmann, CD8B (CD8 vs CD4), GNLY and KLRD1 (NK vs CD8),
  CD1C and CLEC10A (myeloid DC vs monocyte), IL3RA and TCF4 (pDC), CD79A (B)
  each differ at least two-fold in 3 or 4 of 4 donors.
- **Single-cell proteomics does not measure them.** None of the 16 is
  detected in any of the seven single-cell datasets, except CD1C (2.2% of
  one search's cells), GNLY (3.4%) and SELL (0.6%). They are missing from
  the input space because single cells do not yield them.
- **The present markers are rarely seen too:** CD8A in 2–19% of cells, CD4
  in 3–12%.
- **Two markers pass all three criteria,** CCL5 (CD8 vs CD4) and PRF1 (NK vs
  CD8), and both are already in the input space.

**What it means:**
- Widening the gene space, for the encoder or the correlation term, would
  add nothing for current single-cell data; Phase 2a's wider panel is
  dropped.
- Telling the weak classes apart has to come from patterns across the
  abundant proteins single cells do yield. Rieckmann's class means over
  those proteins (the other half of Phase 2a) are the next test.

### 31. Protein class means from sorted cells (Goal 2, Phase 2a feasibility), 2026-10-16

**Why:** entry 30 found that single cells yield only abundant proteins. Do
class means built from sorted cells' proteomes (Rieckmann 2017, 27
steady-state populations x 4 donors, mapped to 16 of the reference's classes)
separate single cells better than v4.1's RNA class means?

**How** (`research/notebooks/rieckmann_feasibility.py`; decision rule in its
docstring before the run): the correlation term alone (`fusion.masked_pearson`),
each cell against each class mean over its observed genes, three sets of
means choosing from the same 16 classes: RNA (v4.1's), RNA over the genes both
share, protein. Development data: Fulcher 2026 (six author types) and PBMC240
(lymphoid recall).

**Result** (`research/notebook-outputs/rieckmann_feasibility/`):

| | RNA | RNA, shared genes | Protein |
|---|---|---|---|
| Fulcher, balanced accuracy | 75.2 | 75.3 | **79.6** |
| Fulcher, DC recall | 61.1 | 61.1 | **87.0** |
| Fulcher, CD8 T recall | 19.3 | 18.8 | 21.6 |
| Fulcher, monocyte recall | 98.0 | 96.9 | 88.8 |
| PBMC240, lymphoid recall | 73.5 | 75.2 | **78.6** |

- **The rule set before the run is met** (at least 3 points on Fulcher over
  both RNA variants, no loss on PBMC240), so a Phase 2a candidate is built.
- **The gain is the dendritic cells,** the class the RNA reference barely
  has; CD8 T barely moves, and monocytes lose some cells to DC.
- **Restricting the choice to 16 classes helps every arm:** the RNA means
  alone reach 75.2 here, against v4.1's 69.05 for the full fused guess over
  22 classes. The candidate must keep the classes Rieckmann lacks
  (macrophage, the progenitors, NK T) without losing this.
- **Protein means fit protein uploads only,** so the candidate's gates are
  protein development data, not the RNA simulation suites.

### 32. v4.2: v4.1 with protein class means (Goal 2, Phase 2a), 2026-10-16

**The rule** (`research/notebooks/v42_protein_means.py`; rule and gates in its
docstring before the run): v4.1's answers and weights, with a hybrid
correlation term: Rieckmann's protein class means for the 16 classes it has a
sorted population for, v4.1's RNA means for the other 6 (macrophage, the
three progenitor classes, mature NK T, the generic monocyte class); the
upload's agreement gate computed on the hybrid term. Nothing tuned. Scored
from v4.1's development cache; the self-check reproduces v4.1's committed
figures to 5e-5 points.

| Development | v4.1 | v4.2 |
|---|---|---|
| Fulcher, balanced accuracy (six types) | 69.05 | **75.79** |
| Fulcher, DC recall | 22.2 | **63.0** |
| Fulcher, NK / monocyte / CD8 T recall | 90.0 / 97.8 / 23.8 | 92.0 / 95.4 / 23.2 |
| PBMC240, lymphoid recall | 92.3 | 92.3 |
| SCoPE2 restricted, published / reprocessed | 38.0 / 33.3 | 38.0 / 33.3 |
| Fulcher answers, committed / correct | 88.6% / 97.9% | 88.8% / 98.3% |
| Out-of-reference AUROC | 0.79 | 0.80 |

- **GO on all five gates** set before the run.
- **The gain is Fulcher's dendritic cells,** where the RNA reference has one
  myeloid DC. CD8 T does not move.
- **Only Fulcher's upload uses the term:** its agreement is 0.43 under the
  hybrid term; PBMC240 (0.27), both SCoPE2 versions (0.08, 0.13) and
  Furtwangler (0.09) fall below 0.4, so v4.2 answers there exactly as v4.1.
  The hybrid term agrees less often with v3.1 than the RNA term did.
- **Fulcher chose v4.1's weight,** so this is development evidence. The held-out
  protein sets and the sorted cells are the tests.
- **Frozen as a candidate** (owner, 2026-10-16): `"v4.2"` in the service,
  refused until evaluated (`scripts/build_v42_spec.py`, `service/model/v4_2/`);
  the served guess equals this script's on every development dataset
  (`service/tests/test_v42.py`); added to the sorted test (protocol amendment
  3) and to the internal held-out test (`side-tests.md`, amendment 2).

### 33. Why SCoPE2's macrophages are called monocytes (Goal 2, Phase 1.3), 2026-10-16

**Why:** on SCoPE2 (PMA-differentiated U-937 macrophages against
undifferentiated monocytes; development data) v4.1 is below chance restricted
to the two classes, and every corrected baseline is at or below chance on the
reprocessed matrix.

**How** (`research/notebooks/mac_mono_diagnosis.py`; questions fixed in its
docstring): the reference's macrophage class (donors, assay, the atlas's
free annotation, marker RNA); each SCoPE2 protein's AUC, macrophage against
monocyte, on both matrices; the reference's class-balanced RNA difference,
macrophage minus monocyte, for the same genes; the correlation term's lean.

**Result** (`research/notebook-outputs/mac_mono_diagnosis/`):
- **The reference's "macrophage" class is monocyte-like.** 1,228 cells, all
  10x, 77% from two donors (TSP21 559, TSP2 385), annotated "macrophage"
  throughout. Against the monocyte classes it carries less of the monocyte
  genes (CD14 60% of cells against 88-90%; LYZ, S100A8/9, VCAN, FCN1 lower)
  and a little more C1QA/C1QB and MRC1, with no macrophage program.
- **SCoPE2's differentiation is a different signal.** Its strongest protein
  differences (VIM, ANXA2, LMNA up in macrophages, AUC 0.93-0.98) are
  cytoskeletal and adhesion changes from PMA.
- **The two differences are unrelated:** Spearman between SCoPE2's protein
  AUC and the reference's RNA difference is -0.009 (published) and -0.015
  (reprocessed); among the 50 strongest proteins the direction agrees for 40%
  and 46%. VIM and ANXA2, the top two, are lower in the reference's
  macrophage class (RNA difference -1.08 and -0.57).
- **The correlation term leans the wrong way:** median r(macrophage) -
  r(monocyte) is lower for SCoPE2's macrophages than for its monocytes on
  both matrices.

**What it means:**
- Nothing in this reference tells a PMA-differentiated macrophage from a
  monocyte, so no reweighting or retraining on it can fix SCoPE2; the
  macrophage/monocyte group answer is the most it supports.
- A fix needs a reference with real differentiated macrophages (for
  instance an RNA atlas of monocyte-derived or tissue macrophages), which is
  new model work, not a correction.
- The held-out PXD046211 (THP-1 and U-937, with and without PMA) will test
  the same question once, at the end.

### 34. Conformal coverage on real protein (Goal 2, Phase 1.4), 2026-10-16

**Why:** v3.1's sets were calibrated to hold the true class 90% of the time
on simulated RNA uploads; on protein the guarantee is stated as approximate.
How approximate?

**How** (`research/notebooks/protein_coverage.py`): from the served per-cell
tables of v3.1 and v4.1 (v4.1's sets are v3.1's with its guess joined), the
share of labelled cells whose set holds their type (Fulcher, via COARSE),
their class (SCoPE2) or their lineage (PBMC240).

**Result** (`research/notebook-outputs/protein_coverage/coverage.json`),
v4.1 (v3.1 within two points):

| Dataset | Coverage | Among cells given a set | Lowest classes |
|---|---|---|---|
| Fulcher 2026 | 78.3% | 88.5% | CD8 T 44.2%, DC 46.3%, CD4 T 76.3% |
| PBMC240 (lineage) | 77.9% | 96.9% | myeloid 60.0% (5 cells) |
| SCoPE2 published / reprocessed | 2.5% / 6.4% | 4.7% / 20.6% | both classes |

- **On blood protein the sets fall short of 90% by about 12 points,** and the
  shortfall sits in the classes the model confuses: CD8 T and DCs near 45%,
  NK, B and monocytes 84-91%.
- **On SCoPE2 the sets rarely hold the right class** (macrophage appears in 36
  of 1,490 sets), as entry 33 explains.
- **Recalibrating on real protein** would need labelled protein calibration
  cells; Fulcher is the only candidate, and using it would make it in-sample
  for the answers too. Not done; the limit is stated.

### 35. Uploads of one cell type, on real protein (Goal 2, Phase 1.5), 2026-10-16

**Why:** every gene is z-scored within its upload, so an upload of one cell
type loses the contrast between types; simulated RNA showed the cost. Users
who upload a sorted population meet it on real data.

**How** (`research/notebooks/single_type_uploads.py`): Fulcher 2026's cells
(development data) through the served service three ways: the full mixed
upload; each author type alone; CD4 T with CD8 T, and B with monocytes. Best
guess recall, committed share and correct when committed at the stated level.

**Result** (`research/notebook-outputs/single_type_uploads/summary.json`),
v4.1 (v3.1 and v4.2 alike):

| Type | Mixed: recall / committed / correct | Alone: recall / committed / correct |
|---|---|---|
| B | 98.0 / 85.3 / 98.9 | 11.8 / 31.4 / **6.3** |
| NK | 90.0 / 92.0 / 99.3 | 6.7 / 44.0 / **43.9** |
| monocyte | 97.8 / 91.5 / 100.0 | 22.4 / 29.6 / **37.0** |
| CD4 T | 82.5 / 88.0 / 93.4 | 23.4 / 37.7 / 54.3 |
| CD8 T | 23.8 / 93.4 / 98.8 | 11.1 / 46.4 / 72.6 |
| DC | 22.2 / 48.1 / 96.2 | 16.7 / 42.6 / 65.2 |

- **One type alone breaks the model, answers included.** The answers that
  are right 93-100% of the time in a mixed upload are right 6-73% of the
  time alone: they stay committed but become wrong.
- **Two close types together break it too:** CD4 T with CD8 T, 28% and 22%
  recall; B with monocytes holds for B (100%) but monocytes fall to 49%.
- **For users:** a sorted population uploaded on its own gets confident,
  wrong answers. Stated as a known limit on the site and in the model card;
  the sorted CD4/CD8 test already uploads every cell together.
- **The candidate fix** is Phase 2d, scaling each gene against the reference
  instead of within the upload; NB1b's version helped simulated single-type
  uploads but failed its real-data gate, so it is re-tested here first.

### 36. Typing a cell without scaling within its upload (Goal 2, Phase 2d probe), 2026-10-16

**Why:** entry 35 traced the single-type collapse to scaling each gene within
the upload. Can a cell be typed from its own profile alone?

**How** (`research/notebooks/upload_independent_probe.py`; exploratory):
Fulcher's mixed upload against Rieckmann's protein class means three ways:
genes scaled within the upload (Phase 2a's rule); each cell's raw log
profile, centred within the cell only; the same minus each protein's mean
across Rieckmann's classes. The last two depend on nothing else in the upload.

**Result** (`research/notebook-outputs/upload_independent_probe/summary.json`):
balanced accuracy over the six types 79.6 within the upload, **27.9** from the
raw profile and **20.9** reference-centred (chance 16.7), on the 674 proteins
every Rieckmann class shows (231 observed per cell). Without scaling, almost
every lymphocyte is called a monocyte or a DC.

**What it means:**
- Each dataset measures each protein at its own offset (detectability,
  instrument, normalisation), and scaling within a mixed upload is what
  cancels it. A single sorted population cannot be typed from its own file.
- The workable answers are to keep a mixed reference in the same upload (a
  user's own PBMCs beside the sorted cells), or to detect a narrow upload and
  say so instead of answering. Neither is built yet.

### 37. A check for narrow uploads: two designs, both NO GO (Goal 2), 2026-10-16

**Why:** entry 35 found that one cell type uploaded alone gets confident,
wrong answers, and entry 36 that it cannot be typed without a mixed upload.
The owner asked for a label-free check that says when an upload looks narrow.

**The pass rule, fixed before each run:** calibrate a threshold on simulated
RNA uploads (NB3c's calibration suite and 60 single-type uploads, te_cal
cells only), at the 5th percentile of uploads with five or more types; then,
on protein development data, flag none of Fulcher's full upload, PBMC240,
DS18 (three searches) and DS19, and at least 5 of Fulcher's 6 single-type
uploads. Otherwise nothing is served.

**Design 1, structure** (`research/notebooks/narrow_upload_calibration.py`):
the variance in an upload's top five principal components over a
per-protein permutation null. Threshold 2.24; simulated single-type uploads
flagged 42%, broad ones 6% (mixed 7%, PBMC-like 0%). On protein it flagged **1 of 6** single-type uploads
(the DCs): single-type uploads scored 2.1-5.9 and mixed ones 4.9-11.3, so
they overlap. The score reads technical structure (plexes, loading) as well as
cell types.

**Design 2, commitment** (`research/notebooks/narrow_upload_committed.py`; a
second look at the same protein data): the share of cells the answers commit
on. Threshold 0.784; simulated single-type uploads flagged 62%. On protein it
flagged **all 6** single-type uploads (29.6-46.4% committed) but also every
mixed PBMC set except Fulcher's: PBMC240 73.4%, DS18 27.0-37.4%, DS19 40.7%.

**Results:** `research/notebook-outputs/narrow_upload/` (calibration.json,
scores.csv, committed.json).

**What it means:**
- **No check is served.** Neither signal tells a narrow upload from an
  unfamiliar dataset: commitment falls on both.
- **The guidance stays:** the site and the model card tell users to send
  mixed cells, never one sorted population alone.
- **New finding:** on the Astral PBMC runs (PXD070599 DS18 and DS19, Olsen
  lab), v4.1 commits on only 27-41% of cells, against 87% on Fulcher. Their
  labels come from clustering, so whether the rest are hard cells or an
  unfamiliar instrument is not known; a newer instrument is worth a closer
  look.

### 38. Why v4.1 abstains on the Astral PBMC runs (Goal 2), 2026-10-16

**Why:** entry 37 found that v4.1 commits on only 27-41% of the cells in
PXD070599's Astral PBMC runs, against 87% on Fulcher 2026. A diagnosis on
development data, label-free; it changes nothing.

**The data:** frozen PBMCs sorted one per well. DS18 is three run sets:
Standard Astral (88 cells, DIA range 425-625 m/z), FAIMS Astral (89), and
FAIMS 20-40 on a second instrument, "Astral-Zoom" (91, plate B3). DS19 is a
second plate on that instrument (81 cells, plate B2). Every search used
match-between-runs. Eight empty-well runs were acquired beside each run set
(the deposit's raw-file mapping lists 32), but none was searched into a
deposited matrix.

**What it is not** (`research/notebooks/astral_abstention.py`):
- **Upload size.** Fulcher's mixed upload cut to 90 cells commits on a
  median 95.6% (91.1-98.9, 20 seeds).
- **Depth.** The Astral cells show 1,024-3,570 proteins each, against
  Fulcher's 776. Keeping only the proteins seen in half the cells, or only
  Fulcher's proteins, leaves 20.5-54.3% committed.
- **Match-between-runs.** A median 28-46% of each cell's precursor values
  were not identified in that cell's first pass. With the precursors rolled
  up to genes the same way in every arm, keeping only the first pass's
  identifications, or using the first-pass precursors, gives 20.5-44.4%
  committed, against 22.5-42.0% with every value. Reference similarity moves
  by under 0.02.
- **A removable platelet or red-cell signal.** Dropping the reference's 100
  most platelet-specific and 100 most erythrocyte-specific genes (196 genes;
  67-111 rows per Astral upload) moves the committed share from -7.9 to +4.4
  points. That is within, or just outside, the range of ten random drops of
  as many genes, in both directions. Fulcher and PBMC240 move by under one
  point.

**What is different:**
- **The cells sit farther from the reference.** Median similarity is
  0.84-0.88, against 0.96-0.98 on Fulcher and PBMC240. Ambiguity between
  classes is the main abstention reason (48-58% of cells).
- **The best guesses fall on classes rare in PBMCs.** Platelet is the best
  guess for 49.4% of DS18 FAIMS cells, 21.6% of Standard and 18.7% of
  Astral-Zoom. Macrophage takes 29.5% of Standard, neutrophil 25.9% of DS19,
  and myeloid DC 12-13% of Astral-Zoom and DS19. On Fulcher and PBMC240 the
  six commonest guesses are all monocyte, T, NK, B or plasma cells.
- **Every well carries platelet and red-cell proteins.** PPBP, ITGA2B and
  TUBB1 are seen in 83-100% of the Astral cells, at a median rank of
  0.78-0.98 among each cell's own proteins (1 is the most abundant). In
  Fulcher, PPBP and ITGA2B are seen in 5% and 1% of cells; in PBMC240, the
  platelet markers in 14-40%. HBB and HBA1 are seen in 99-100% of the Astral
  cells (median rank 0.44-1.0), against HBB in 59% of Fulcher's (rank 0.18).
- **DS18 shows few T-cell markers,** although PBMCs are mostly T cells.
  CD3E, CD3D, LCK and CD247 are each seen in 4.5-13.5% of DS18's cells,
  against 22-39% for CD3D, LCK and CD247 in Fulcher, which measures fewer
  proteins per cell. DS19 sees CD3E, CD2 and CD247 in 72-74% of its cells.

**Results:** `research/notebook-outputs/astral_abstention/summary.json`.

**What it means:**
- **Abstaining is the right answer here.** These cells do not look like the
  reference's blood cells, and v4.1 declines rather than guesses. No change
  to the service.
- **Why they differ is not settled.** Platelet and red-cell proteins in
  every well and weak T-cell signals in DS18 fit material shared across
  wells (ambient protein, platelets bound to cells), or a sorting or lysis
  difference. Two things would settle it, and the deposit has neither in
  usable form: the empty-well runs searched beside the cells (raw files
  only; they need DIA-NN, which is not installed here), or the paper's cell
  labels. The empty-well runs are now on the alternatives list
  (`research/benchmark/side-tests.md`).
- **For development:** DS18 and DS19 are poor controls for "a normal mixed
  PBMC upload". Treat them as an unfamiliar-dataset case. Entry 37's second
  design fails without them too: it also flagged PBMC240.

### 39. The held-out test's designs, rehearsed on RNA (Goal 2, Phase 0.3), 2026-10-16

**Why:** most held-out sets are narrow uploads (one or two cell types, or
pools), the weakness entry 35 found. A design that cannot pass even on RNA
would waste a held-out set, so each was rehearsed before its protocol.

**How** (`research/notebooks/heldout_rehearsal.py`): RNA calibration cells
(te_cal) with real protein mask profiles, through v4.1's served code against
references without those cells; 20 seeds per design. Bulks and pools are
pseudo-bulks. Scrambled cells (a cell's observed values shuffled among its
genes) stand in for non-immune cells, which the blood reference lacks. Each
bar is what the design's protocol would need to pass, fixed before the run.

| Design (held-out set) | Statistic | Median (range) | Bar | Viable |
|---|---|---|---|---|
| T-cell bulk pairs (Tian) | CD8 bulk above its CD4 pair, of 10 | 10 (10-10) | 9 | yes |
| Monocyte vs macrophage-like cells (PXD046211) | AUROC | 0.941 (0.923-0.959) | 0.65 | yes |
| T-cell line beside foreign cells (PXD043355) | AUROC, reference similarity | 0.978 (0.911-1.0) | 0.65 | yes |
| Neutrophils alone (PXD061065) | best-guess recall, worse of two masks | 34.7% (27.8-45.1) | 50% | **no** |
| Immune beside foreign cells (PXD073250) | AUROC, reference similarity | 0.993 (0.982-0.999) | 0.65 | yes |
| B vs T pools (PXD021882) | AUROC | 1.0 (1.0-1.0) | 0.8 | yes |

**Results:** `research/notebook-outputs/heldout_rehearsal/summary.json`.

**What it means:**
- **Neutrophils uploaded alone fail:** recall 34.7% with Fulcher's mask and
  52.0% with PBMC240's. PXD061065 leaves the internal test unopened and joins
  the reserve (`research/benchmark/side-tests.md`, amendment 3).
- **The other five designs go to protocols.** Two cautions carry over:
  - In the T-cell bulks, the pairs are won but half the CD8 bulks' best guess
    is NK. The protocol's primary is the within-pair score; the best guess
    is secondary.
  - Scrambled cells are a low bar. A real HeLa cell or keratinocyte may sit
    closer to the reference, so the two foreign-cell tests are harder than
    their rehearsal.
- The Hao 2021 suite is rehearsed on its development donors by its own
  intake.

### 40. Dendritic cells from Hao 2021 in the class centres: NO GO (Goal 2, Phases 1.2 and 2b), 2026-10-16

**Why:** the reference has one myeloid DC and 29 pDCs, so the best guess's
DC centroids and class means rest on almost nothing. Hao et al. 2021's
Batch1 (donors P1 to P4, development) has 945 cDC1 and cDC2 cells and 221
pDCs.

**Design 1** (`research/notebooks/hao_dc_centres.py`; rules, checks and gates
fixed before the run): v4.1 and v4.2 with every member's DC centroids and
the two DC class means recomputed over Tabula Sapiens's cells plus Hao's,
embedded the reference's way. Self-checks passed: the recombined best guess
equals the served one, and both bases reproduce their committed development
figures.

| Check or gate | v4.1 | v4.1+DC | v4.2 | v4.2+DC |
|---|---|---|---|---|
| C1 atlas probe, mean AUC (Fulcher, PBMC240 masks) | | 0.923, 0.934 (bar 0.9) | | same |
| C2 swap: Tabula Sapiens pDC recall, Hao-built pDC centre | 65.2 (in-sample) | **0.0** (bar 70) | | |
| Hao suite DC recall, donors held out (G1) | 7.8 | 2.3 | 4.5 | 0.0 |
| Hao suite coarse balanced accuracy (G2) | 62.5 | 63.2 | 57.4 | 59.1 |
| Fulcher balanced accuracy; DC recall (G3) | 69.05; 22.2 | 65.53; **0.0** | 75.79; 63.0 | 75.68; 59.3 |
| Calibration suite, best guess (G6) | 63.6 | 65.3 | 61.1 | 63.0 |

Both fail C1, C2, C3 (leakage: Fulcher DC precision undefined for v4.1+DC;
DS18 Standard's DC share up 5.7 points for both), G1 and G3. **NO GO.**

**Design 2, a per-gene offset** (`research/notebooks/hao_dc_offset.py`; the
plan's fallback, a second look, recorded as such): Hao cells corrected by
their mean difference from Tabula Sapiens over B, NK, CD4, naive CD4 and
CD8 T cells (z-scale), checked on classes the offset never saw. The atlas
probe then passes narrowly (mean AUC 0.870 and 0.892), but the swap still
recalls **0%** of Tabula Sapiens's pDCs. Checks fail, so no candidate.

**Why it fails:** the swap code rebuilds the served pDC centre exactly from
Tabula Sapiens cells (cosine 1.0, identical calls), so this is not a bug.
Hao's pDC centre is nearly orthogonal to Tabula Sapiens's (cosine -0.19 to
0.19 across the five members): the encoder's reference-side space is
specific to the atlas it was trained on, and a per-gene offset does not
remove that.

**Results:** `research/notebook-outputs/hao_dc_centres/` (summary.json,
offset.json).

**What it means:**
- **No Hao DC candidate.** The plan's chain (the cells as they are, then a
  per-gene offset, else no Hao DCs) ends here. Dendritic cells stay with
  v4.2's protein class means (Fulcher DC recall 63.0 against v4.1's 22.2).
- **On RNA from another atlas, v4.1 finds few DCs:** 7.8% recall on Hao's
  held-out donors (myeloid DC 1.7%, pDC 34.3%), coarse balanced accuracy
  62.5. The Hao held-out suite will measure this on Batch2.
- **Open, outside this plan:** building DC centres from query-side
  embeddings (cells processed the way uploads are), or retraining the
  encoder with Hao cells.

### 41. Out-of-distribution scores beyond the served one: NO GO (Goal 2, Phase 2c), 2026-10-16

**Why:** does a cell's distance to the reference say "not a blood cell"
better than the served score (the members' mean maximum cosine to the
reference latents)?

**Scores** (`research/notebooks/ood_candidates.py`; rules fixed before the
run): S0 served; S1 the best correlation with v4.1's RNA class means; S2 the
best correlation with v4.2's protein class means; S3 the members' best
cosine to a class centroid. Tuned, as the plan fixed, on scrambled cells and
Furtwangler 2025 only.

| AUROC (in-reference over foreign) | S0 served | S1 | S2 | S3 |
|---|---|---|---|---|
| scrambled cells in Fulcher's upload | 0.952 | 0.896 | **0.974** | 0.953 |
| scrambled cells in PBMC240's upload | 0.770 | **0.824** | 0.784 | 0.765 |
| PBMC240 over Furtwangler's CD34+ cells | 0.747 | 0.718 | **0.832** | 0.750 |
| mean | 0.823 | 0.813 | **0.863** | 0.823 |

**Verdict:** S2 is best, but by 0.040 against the 0.05 required (rule 1);
rules 2 and 3 pass. **NO GO:** the served score stays.

**The real foreign cells** (development, reported): at each score's
threshold (the 1st percentile of RNA calibration cells, NB2's rule), the
served score flags **0%** of PXD077946's HEK293T (13 cells), HCT116 (13) and
K562 (14), 6.4% of MSV000099294's HMC3 (47) and 12.3% of its microglia
(57). Its AUROC against PBMC240's cells is 0.85-0.87 for the three lines.
S2 flags every HMC3 and microglia cell but none of the three lines; S3
flags 21-23% of the lines.

**Results:** `research/notebook-outputs/ood_candidates/summary.json`.

**What it means:**
- **The served check does not refuse whole foreign cell lines.** It ranks
  them below blood cells (AUROC about 0.86), but its threshold, set on RNA
  calibration cells, lets them through, so none is refused as outside the
  reference. v4.1 as served (checked after the run): most still abstain as
  ambiguous between classes, but some get a confident blood-cell answer:
  HEK293T 3 of 13 (erythrocyte, neutrophil), HCT116 4 of 13 (T cell,
  lymphoid), K562 4 of 14, HMC3 19 of 47. This is a known limit to state on
  the site and in the model card.
- The held-out foreign-cell tests (PXD043355, PXD073250) use the score's
  ranking as their primary, which this result predicts will separate; their
  abstention rates are secondary and are predicted to be low.
- **Open:** a threshold set on protein data (it would need labelled
  in-reference protein cells to calibrate), or S2 with its own threshold.

### 42. The held-out test's protocols (Goal 2, Phase 0.4), 2026-10-16

**Why:** every part of the internal held-out test needs a committed
protocol and intake before any of its files is opened (`side-tests.md`,
amendments 1 and 4).

**What:** one primary comparison per set, pass at p < 0.05 (or a bootstrap
bound above 0), every candidate scored, v4.1 the headline:
- **Protein sets** (`research/benchmark/protocol-heldout.md`;
  `benchmark/heldout_formats.py`, `heldout_intake.py`, `heldout_score.py`),
  written from the PRIDE and MassIVE records only:
  - Tian: the CD8 bulk above its CD4 pair on P(CD8T) - P(CD4T), sign test;
  - PXD021882: AUROC of P(B) - P(T), B pools over T pools;
  - PXD043355 and PXD073250: AUROC of reference similarity, immune over
    foreign;
  - PXD046211: AUROC of P(macrophage) - P(monocytes), PMA over untreated,
    with failure predicted (entry 33).
  The per-class probabilities are recomputed with the service's functions
  and must agree with the served best guess. After unsealing only format
  fixes are allowed.
- **Hao 2021's held-out donors** (`research/benchmark/protocol-heldout-hao2021.md`;
  `benchmark/heldout_hao2021.py`): 108 protein-like uploads; v4.1's
  per-upload coarse balanced accuracy minus the correlation baseline's,
  donor-blocked bootstrap, passing if the one-sided 95% lower bound is
  above 0.

**Rehearsals** (development or synthetic data; records in
`research/benchmark/heldout/rehearsals/`), v4.1:
- Tian on Rieckmann's T populations: 16 of 16 pairs won (p 1.5e-05). CD8
  bulks were guessed CD8 T 25.0% of the time (v5.2 62.5%, baselines 0%).
- B against T on Rieckmann: AUROC 1.0.
- Synthetic Proteome Discoverer files from PBMC240 against shuffled cells:
  0.901.
- DS18 against shuffled cells: 0.769.
- SCoPE2 through a synthetic sage file: 0.338, failing as predicted.
- Hao on donors P1 to P4: v4.1 60.7 against correlation 57.6 (+3.08, lower
  bound +1.19), v5.2 62.3, v4.2 54.9 (its protein term applied to RNA),
  PCA kNN 48.0; dendritic-cell recall 7.3 for v4.1.

**What it means:** the readers, label rules, scoring and guards work end to
end. The sets stay sealed until Phase 3, scored once on the candidates
frozen by then: v4.1, v4.2 and v5.2, since Phase 2 froze no new one
(entries 40 and 41).

### 43. How much the encoder leans on its training donors (Goal 2, Phase 1.6), 2026-10-16

**Why:** every protein dataset comes from donors the encoder never saw. A
diagnosis on the reference RNA only; it decides nothing.

**How** (`research/notebooks/donor_heldout.py`; folds fixed before the run):
Tabula Sapiens's 9 blood donors in three folds of about equal cell counts
(F1 TSP7, TSP1, TSP25; F2 TSP14, TSP8, TSP27; F3 TSP21, TSP2, TSP10). Per
fold, one member was retrained with the served recipe on the other donors.
It was scored on test cells under Fulcher's mask, in 500-cell uploads, by
nearest class centroid, over the classes with at least 20 test cells on
both sides.

| Fold | Classes | Unseen donors | Seen donors | Gap |
|---|---|---|---|---|
| F1 | 11 | 58.7 | 65.2 | 6.5 |
| F2 | 6 | 35.6 | 57.7 | 22.2 |
| F3 | 13 | 63.0 | 63.6 | 0.6 |

Mean gap 9.8 points of balanced accuracy.

**Where the gap is:**
- **F1:** the generic "monocyte" class falls from 89.7% recall on seen
  donors to 3.7% on unseen ones, and "classical monocyte" from 50.9 to
  23.8.
- **F2** (without its largest donor, TSP14): plasma cells 100 to 60.5,
  neutrophils 96.0 to 61.4, CD8 T 45.4 to 20.0.
- **F3** is nearly level.

**Results:** `research/notebook-outputs/donor_heldout/summary.json`.

**What it means:**
- **Part of what the encoder learned is the donors.** A new donor costs about
  10 points on RNA before any change of technology, and up to 22 in one
  fold.
- **Some classes are a donor's annotation more than a cell type.** "Monocyte"
  against "classical monocyte" is one example: which one a monocyte gets
  depends on who annotated its donor. Merging such classes, or training
  with donors held out, are options for a future model; this plan does not
  test them.

### 44. The internal held-out test, scored once (Goal 2, Phase 3), 2026-10-16

**Why:** the plan's milestone. Six sets were set aside before development
(`side-tests.md`, amendment 1), and each is scored once under its committed
protocol (`protocol-heldout.md`, `protocol-heldout-hao2021.md`). The
candidates were final before any file was opened (amendment 1 of both
protocols): v4.1 (served, the headline), v4.2 and v5.2, with v3.1 for
reference. The format fixes found at unsealing are protocol amendment 2,
committed before the last set was scored.

| Set (question) | Primary | v4.1 | v4.2 | v5.2 | v3.1 |
|---|---|---|---|---|---|
| Hao 2021 donors P5-P8, RNA (B, monocytes, DCs on another atlas) | coarse BA minus correlation's, one-sided 95% lower bound | **+4.73 (+2.82) pass** | +1.88 (-0.95) fail | **+5.88 (+4.54) pass** | +0.34 (-4.40) fail |
| PXD043355 (T-cell line over HeLa) | AUROC of reference similarity | **0.674, p 0.015 pass** | 0.674 pass | 0.631, p 0.049 pass | 0.674 pass |
| PXD073250 (immune over keratinocytes) | AUROC of reference similarity | 0.442, p 0.975 fail | 0.442 fail | 0.446 fail | 0.442 fail |
| PXD046211 (PMA over untreated monocyte lines) | AUROC of P(macrophage) - P(monocytes) | 0.517, p 0.30 fail (predicted) | 0.517 fail | 0.525 fail | 0.520 fail |
| Tian (CD8 over CD4 sorted bulks) | pairs won, sign test | void: 1 pair | void | void | void |
| PXD021882 (B over T pools) | AUROC | void: no pools in the deposited table | void | void | void |

**Secondary, v4.1:**
- **Hao:** coarse balanced accuracy 62.2 (correlation 57.5, PCA kNN 49.1).
  B recall 98.6, monocytes 83.4, dendritic cells 10.4 (correlation 21.9).
  v5.2 beats v4.1 by 1.16 points (lower bound +0.25).
- **PXD043355:** 96.6% of Jurkat cells and 66.7% of HeLa cells abstain, so
  a third of the HeLa cells get a confident blood-cell answer.
- **PXD073250:** the keratinocytes abstain less often than the immune cells
  (56.8% against 67.6%).
- **Tian's one pair** (CD8 against CD4 bulks) is won by every model. Only
  19% of its CD8 bulks are best-guessed CD8 T.

**Results:** `research/benchmark/heldout/` (one summary per set; the Hao
suite's in `hao2021/`).

**What it means:**
- **Typing transfers to held-out donors of another atlas.** On RNA made
  protein-like, v4.1 beats the stronger simple baseline by about 5 points.
  It is never protein evidence.
- **Refusing foreign cells is the weak point.** The reference-similarity
  score ranks a T-cell line above HeLa (AUROC 0.67), but not immune cells
  above keratinocytes from the same tumour (0.44), and a third of HeLa cells
  get an answer. With entry 41 (cell lines pass the threshold), this is now
  a held-out finding, not only a development one.
- **Macrophage-like cell lines are not separated from monocyte lines,** as
  entry 33 predicted.
- **Dendritic cells stay weak** on held-out RNA (10.4% for v4.1).
- **The CD4/CD8 question is untested here:** Tian's deposit has no matched
  CD4 and CD8 samples, so the sorted single cells (requested by email)
  remain the only test of it.
- **Between the candidates:**
  - **v4.2** ties v4.1 on every protein set (the same answers and similarity)
    and loses on RNA, where its protein term does not belong.
  - **v5.2** is slightly ahead on RNA (+1.16 points). On protein it is
    behind on the one set that passes (0.631 against 0.674) and level, within
    noise, on the two that fail. It still fails a development guardrail by
    one cell.
  - **No candidate beats v4.1 on held-out protein data.**
- **Decision on the served model (this plan's end): keep v4.1.** The rule
  applied, stated here because the plan left the choice open: switch only to
  a candidate that beats v4.1 on held-out protein data without losing a
  passed primary. v4.2 ties it, and v5.2 does not beat it on protein.
  - v5.2 stays frozen for the sorted CD4/CD8 test, its own question.
  - v4.2 stays selectable and refused, as before.
  - Superseded by entry 45: v4.2 is served from release 0.5.0.

### 45. v4.2 served, release 0.5.0 (Goal 2, after Phase 3), 2026-10-16

**Why:** the owner asked that the site and service carry the best model we
have. Entry 44 kept v4.1 because v4.2 lost on Hao's RNA suite. That loss
came from a routing fault, not from v4.2's idea: the service ran v4.2's
protein class means on RNA uploads, where they do not belong.

**What changed:**
- **The fault is fixed.** The service passes the upload's modality to the
  best guess; an RNA upload takes v4.1's RNA class means
  (`service/pipeline/fusion.py`). `service/tests/test_v42.py` checks that an
  RNA upload is answered exactly as by v4.1, and that the same Fulcher upload
  sent as protein is not. The fix came after the held-out scoring, so v4.2's
  Hao result is now v4.1's by construction, not a fresh held-out result.
- **The choice, from `research/notebooks/v42_release.py`**
  (`research/notebook-outputs/v42_release/summary.json`):
  - **Held-out, protein:** v4.2's primaries equal v4.1's on every set, since
    two read reference similarity, which v4.2 does not change, and the third
    found its term flat.
  - **Held-out, RNA:** v4.1's pass, by the fix.
  - **Fulcher 2026 (development, in-sample):** six-type balanced accuracy
    75.79 against 69.05, +6.74 (95% CI 4.26 to 9.23, cell-level bootstrap;
    the stratified paired bootstrap in
    `research/benchmark/v42_development/` gives 4.41 to 9.16). Dendritic
    cells 22.2 to 63.0, NK 90.0 to 92.0, monocytes 97.8 to 95.4.
  - **PBMC240, both SCoPE2 versions, Furtwängler 2025:** no best guess
    differs.
  - **Licence:** PXD004352 is in PRIDE under the EMBL-EBI terms; the model
    card and site credit Rieckmann et al. 2017.
- **The rule applied:** serve a candidate that loses nothing held-out and
  gains on development data with an interval above zero. Entry 44's stricter
  rule (beat v4.1 on held-out protein data) cannot be met by a change that
  only acts where the correlation term is used, which none of the held-out
  protein primaries read. The gain is development evidence, and the site
  says so.
- **Its spec's evaluation is "passed"** (`scripts/build_v42_spec.py
  --passed`), which lets the service serve it. `service/config.py` makes it
  the default, atlas version 0.5.0. `benchmark/baselines_v4_score.py
  --version v4.2` built `research/benchmark/v42_development/`, and its
  checks pass against v3.1 and v4.1.
- **Khoury 2026 is not scored for v4.2.** Each use needs the owner's
  decision; the manifest marks v4.2's Khoury row pending and keeps v4.1's
  post-hoc figure as the previous release's.
- **Also recorded:** the corrected baselines rerun on v5.2's labels
  (`research/benchmark/baselines_corrected_labels_v52/`, from
  `python -m benchmark.baselines_corrected_score --labels v52`). scANVI's
  seed 2 failed as it did on the original labels.

**What it means:** the served model now uses protein evidence from sorted
cells where an upload's correlation carries signal, and RNA uploads are
untouched. CD8 T cells are still unsolved (23.2% recall on Fulcher), and the
sorted CD4/CD8 cells remain the decisive test.

---

### 46. Protein groups that name several genes: left out, as served (2026-10-17)

**Why:** the Workflow page shows that 59 of PBMC240's 3,098 rows are left
out because each names several genes on the shared list (FCGR3A;FCGR3B,
HSPA1A;HSPA1B, CALM1;CALM2;CALM3). The owner asked why VivOME does not use
them, and later gave the go-ahead to test it.

**What ran:** `research/notebooks/twin_genes.py`, committed with its decision
rule before it ran (`b9c626a`). The served v4.2, as a protein upload, on
every development DIA-NN file with such rows (PBMC240, DS18's three run sets,
DS19), three ways: leave the rows out (served), give each to the first of its
genes on the list, or copy it to each. No labelled development file has such
rows (Fulcher 2026 and both SCoPE2 versions are one row per gene), so the
scored check is PBMC240's marker-based labels, mapped to families.

**Result** (`research/notebook-outputs/twin_genes/summary.json`):
- 56 to 63 rows per file are affected. Giving them to the first gene changes
  4 to 15 answers per file; copying them changes 10 to 24.
- Agreement with PBMC240's marker labels (140 labelled cells): leave out
  58.57%, first 58.57% (difference 0.00, 95% CI -2.14 to 2.14), each 60.00%
  (+1.43, -1.43 to 4.29).
- **Decision: leave out**, by the rule fixed before running (switch only on a
  gain whose interval lies wholly above 0). Either alternative would change
  answers with no evidence that the changes are right. The service is
  unchanged.

### 47. v4.2 on Khoury 2026, post-hoc, after its release: falls short (2026-10-17)

**Why:** v4.2 was released (entry 45) on development evidence and the
internal held-out test, none of whose protein primaries read its new term.
The owner gave the go-ahead to score it once on Khoury 2026.

**What ran:** `benchmark/khoury2026_posthoc_v42_check.py`, committed with
its verdict before it read a label (`2fe8228`). v4 and v4.1 from their
ingredients (v4's saved Khoury guesses and v4.1's recorded scores both
reproduce exactly); v4.2's best guesses from the service's own response.

**Result** (`research/benchmark/khoury2026_posthoc_v42_check/`): balanced
accuracy 60.12 against v4.1's 62.51, −2.39 (95% CI −3.56 to −1.26). NK
44.2 (v4.1 50.7), monocyte 91.7 (94.7), CD8 T 1.8 (2.7). Below PCA with kNN
(−2.72, CI −4.47 to −0.99). The upload's agreement under v4.2's protein
means is 0.43, so the term is used. **Verdict: falls short.** The release
stands, as the script states; the benchmark page, the model card and the
what's-new list now report it.

### 48. Release 0.6.0: v4.1 served again (2026-10-17)

**Why:** entry 47 found v4.2 below v4.1 on Khoury 2026 (v4.1 ahead by 2.39,
95% CI 1.26 to 3.56), a second lab's data that neither model was tuned on,
while v4.2's gain was measured on Fulcher 2026, where it was checked, and the
internal held-out test could not separate them. The owner decided to serve
v4.1 again.

**What changed:**
- `service/config.py`: the default is v4.1, atlas 0.6.0; v4.2 stays
  selectable. The Dockerfile serves v4.1.
- The manifest's model is v4.1 again (`build_v41_model`), its previous
  release v4.2 (0.5.0, `build_v42_release`). The benchmark puts v4.1 first,
  with its own paired comparisons (`research/benchmark/v41_development/`,
  `research/benchmark/khoury2026_posthoc_v41_check/`); the tables comparing
  the two models, written as v4.2 minus v4.1, are turned round.
- The Workflow page is traced with v4.1
  (`service/model/evidence/workflow/pbmc240_trace_v41.json.gz`). On PBMC240
  its best guesses equal v4.2's (the correlation term is flat under both);
  its second opinion is the reference's RNA class means, and Step 9 says so.
- Pages, model card, READMEs and API doc name v4.1 as served.

### 49. A reference builder, proven on blood (Track I, Stage 1), 2026-10-18

**Why:** no script built a reference from an atlas; blood's came from the
Colab notebooks. The large intestine (`research/organ-references.md`) needs
the same steps run on its own atlas, so they were ported first and checked
against blood's served files.

**How:** `scripts/build_organ_reference.py` with `scripts/organ_reference/`,
driven by `scripts/organs/blood.json`:
- labels, split and suites: NB1's;
- the gene space: Build_Feature_Space's, from its six source files;
- missingness profiles: NB1's;
- modules: Reference_Projection_v3's;
- training: NB1d's, through nb1b_core;
- calibration: NB2's, as `research/notebooks/v5_build.py` runs it;
- the best-guess layer: v4's.

For blood, the calibration and layer run on the served v3.1 members.
Tiers fixed in the plan before the run.

**Results** (`research/notebook-outputs/organ_builder_blood/`):
- **Tier 1, exact:**
  - class indices, the split, both 240-upload suites, the 9,002 genes
    (recomputed from the six sources), the class order, the hierarchy and
    the reference metadata are all identical.
  - The genes needed NB1's upper case; the atlas spells 44 of them
    otherwise.
- **Tier 2:**
  - the RNA statistics and all nine mask-profile arrays differ by 0.0;
  - v4's class-balanced statistics and class means differ by 0.0;
  - class-balanced centroids are at cosine ≥ 0.9999998.
- **Tier 3:** the calibration of the served members, by v5_build's
  rules:
  - temperatures exact;
  - every conformal threshold within one rank;
  - out-of-distribution threshold 0.77898926, equal to NB2's;
  - latents and centroids matching.
- **Tier 4:** blood's served files, assembled in the organ layout and
  loaded by the new loader (`scripts/organ_reference/bundle.py`),
  reproduce v4.1's four frozen responses with no difference. The bundle
  from the rebuilt files agrees on 100% of labels; it differs only in the
  calibration's wording and the properties organ bundles do not ship.
- **Tier 5, seed 1 retrained against the served seed 1:**
  - best validation loss 0.449 (NB1d 0.455);
  - balanced accuracy 66.1 against 66.0;
  - calibration top-1 61.5 against 62.2.
  - **The check "every class's recall within 5 points" failed as written:**
    hematopoietic stem cell is −10.0 (10 validation cells), and naive CD4
    T is +9.5. The five served members differ by more than 5 points from
    each other on 11 of 20 classes (naive CD4 T from 0% to 100%), so this
    check could not tell a sound training path from a faulty one
    (`training_served_spread.json`). It is reported, not changed.
- **Modules are not reproduced** (adjusted Rand 0.30 against the served
  ones; another scikit-learn). The port is deterministic, with the same
  size distribution. Blood keeps its served modules; other organs use the
  port.

### 50. The large intestine's label audit (Track I, Stage 2), 2026-10-18

**Why:** Tabula Sapiens annotated each donor separately, and the colon's
classes follow donors closely. Before any colon model, each class should
mean the same cells in every donor. RNA only.

**How** (`research/notebooks/li_labels.py`; markers fixed before the run):
- for each class and donor with at least 20 cells, the share expressing
  each canonical marker;
- the free annotations behind each class.

**Results** (`research/notebook-outputs/li_labels/`):
- **"Paneth cell of colon" is not Paneth cells in any donor.** DEFA5 and
  DEFA6 are expressed by 0% of its cells everywhere. By donor:
  - TSP25's are best4+ cells (BEST4 77%, CA7 84%);
  - TSP2's look like stem and TA cells;
  - TSP14's are mixed colonocytes.

  The class is dropped (217 cells), recorded in
  `scripts/organs/large_intestine.json`. The reference has 22 classes.
- **The other classes hold:**
  - best4+ cells are genuine in every donor, TSP26's 593 included (BEST4
    100%);
  - goblet cells express MUC2 at 98 to 99%;
  - enterocytes, TA and mast cells are consistent.
- **"Myeloid leukocyte" looks like macrophages** with fewer genes detected
  (C1QA 70 to 79%). It stays apart in the myeloid group, where the answer
  layer can fall back to the group.
- The marker-signature score flags 14 class–donor groups, most of them
  ambient-RNA artefacts of z-scoring near-zero genes (CD4 T cells
  "matching" Paneth markers). The decisions above rest on absolute shares.

### 51. The colon's locked-test rehearsal finds two faults before any gate is scored (Track I, Stage 2), 2026-10-18

**Why:** gate G4 asks the locked test's intake and scorer
(`benchmark/colon_heldout_intake.py`, `benchmark/colon_heldout_score.py`) to
run end to end before anything is unsealed.

**How:** RNA pseudobulk pools of the colon's test cells (100 cells each,
three per donor and group), detection drawn from the development DVP pools,
written as a DIA-NN pg_matrix with a metadata table and three decoys
(organoid, transplant, blank).

**Two faults found, both fixed before any gate was scored:**
- **The service's DIA-NN parser read `Protein.Ids` as a sample.** DIA-NN 1.8
  writes that column (Zheng, Kabatnik, and Post 2025, which used 1.8.1), so
  such uploads failed to parse. The column joins the parser's annotation
  columns (`service/pipeline/alignment.py`, with a test); blood's uploads,
  which lack it, read the same. This also affects the live service.
- **The service's identifier map covers blood's 9,002 genes only**
  (`gene_id_map_v1.tsv`), so a colon upload dropped every gene the colon
  adds (KRT20, MUC2, TFF3, OLFM4, CDX2, about 2,400 in all): 9,002 of 11,448
  features matched.
  - Each organ now builds its own map from HGNC's complete set by the same
    rule (`scripts/organ_reference/gene_ids.py`); on blood's genes it
    reproduces `gene_id_map_v1.tsv` exactly.
  - Colon runs resolve identifiers with the colon's map
    (`bundle.gene_map`), and all 11,448 features match.
  - The service learns to do this itself in Stage 3.
- **The first G1 and G3 run was stopped** at 40 of 240 simulated uploads,
  before anything was written or read, so that one run uses both fixes.

**Result (G4 passes):**
- the label reader keeps the 45 pools and drops all three decoys;
- primary balanced accuracy 97.3% against 20% chance, p = 0.0001;
- crypt bottom over upper crypt AUROC 1.0;
- record: `research/benchmark/heldout/rehearsals/pxd052341.json`.

Pseudobulk is easy; this says the code works, not how the real pools will
score.

### 52. The colon reference's gates: NO GO as built (Track I, Stage 2), 2026-10-18

**Why:** research/organ-references.md fixed gates G1 to G4 before any colon
model existed. A miss stops the work and goes to the owner; nothing is
tuned to pass.

**The model:**
- five members trained by NB1d's recipe on the colon's 22 classes and 11,448
  genes (`research/notebook-outputs/li_build/`);
- validation balanced accuracy about 63% under the 35% training mask
  (blood: 66%);
- calibration-suite top-1 56.3% (blood: 62.4%);
- conformal thresholds near 0.98 for most classes (blood's marginal: 0.91).

**G1, the evaluation suite through the service's code**
(`research/notebooks/li_development.py`; 240 uploads, 72,850 cells):

| | Value | Bar | |
|---|---|---|---|
| Correct when committed | 99.35% | ≥ 90 | pass |
| Committed | 12.01% | ≥ 75 | **miss** |
| Coverage | 85.33% | ≥ 85 | pass |
| False abstention | 0.24% | ≤ 2 | pass |

The best guess's mean per-upload balanced accuracy is 54.2 (blood v4.1:
65.0). By scenario:
- **whole-tissue mixtures:** best guess 86.5, coverage 99.7, committed 21.9;
- **single-class uploads:** best guess 5.3, committed 0.2.

**G3, development protein:**
- **Kabatnik:** epithelium over stroma, AUROC 1.0 (pass). Mean P(epithelial)
  is 0.62 for CDX2-high pools, 0.37 for CDX2-medium and 0.13 for stroma.
- **Zheng:** group accuracy 16.7% (miss). Its upload holds only immune pools,
  two-thirds T cells, and they are guessed mast cell, monocyte or endothelial
  cell.
- **The polyp plate:** every cell abstained. The best guesses are mostly
  epithelial (secretory 110, stem/TA 104, absorptive 101). Marker
  concordance passes for stem/TA (AUROC 0.97) and B cells (0.82), and misses
  for absorptive (0.40), endothelial (0.48), myeloid (0.65) and secretory
  (0.54).

**G4:** passed (entry 51).

**G2, one donor held out** (`research/notebooks/li_donor_heldout.py`; a
diagnosis; mean over five folds):

| | Unseen donor | Seen donors |
|---|---|---|
| Class balanced accuracy | 43.1 | 55.6 |
| Group recall | 67.9 | 75.4 |
| Lineage recall | 82.0 | 89.5 |

The gap is 12.5 points (blood's was 9.8). TSP25 is the worst fold: 26.9
when unseen.

**Diagnosis, on the calibration suite only:**
- **The sets are too wide to commit.** Conformal sets are fitted over every
  kind of upload, and narrow uploads score badly. Uploads of one lineage
  have a median nonconformity score of 0.91, single classes 0.99, and
  whole-tissue mixtures 0.39.
- **Single-class uploads are not the only cause.** Leaving them out moves
  the marginal threshold only from 0.987 to 0.970.
- **The cause is per-upload scaling.** Each upload is standardised against
  itself, and on the colon this costs narrow compositions much more than on
  blood.
- **Real data follow the same pattern.** Kabatnik's upload (epithelium with
  stroma) separates perfectly. Zheng's (immune only) fails.

**Verdict:** NO GO for the colon reference as built. The decision goes to
the owner; nothing was changed to pass a gate. The locked test (PXD052341)
stays sealed, and the evaluation suite has now been used once.

### 53. The colon closed; on to the next organ (Track I), 2026-10-18

**The owner's decision, after entry 52:** document every failure and move to
the next organ.
- **Where it is documented:** `research/organ-references.md`, "The large
  intestine's outcome", lists every gate, fault and data limit in one place.
- **PXD052341 stays sealed** (`side-tests.md`, amendment 8).
- **The two service fixes are committed but not deployed:** the DIA-NN 1.8
  parse, and organ gene maps for research runs. The live service still fails
  on DIA-NN 1.8 protein tables until a deploy.

### 54. The lung: data roles, label audit (Track I), 2026-10-18

**Why:** after the colon (entry 53), the owner chose the lung, keeping the
recipe and the gates.

**The search** (repositories and literature; pages, listings and papers
only): no human lung single-cell MS set with fine independent labels exists.
The best are FACS-sorted lineage pools from one PNNL/LungMAP group, plus the
Human Protein Atlas DVP pools of AT1 and AT2.

**Roles** (`side-tests.md`, amendment 9; the owner's choice):
- MSV000094189 is locked, with its protocol committed before any download;
- MSV000094373, the HPA DVP samples and PXD029341 are development;
- MSV000081973 is in reserve.

**Classes** (`scripts/organs/lung.json`): 28 kept, 6 dropped by the class
rule (113 cells).

**Label audit** (`research/notebooks/organ_labels.py`, the colon's audit
with its markers in the organ file):
- most classes express their own markers in every donor;
- the four doubtful groups each stay within their group (TSP14's ambient
  surfactant signal, the mixed generic monocytes, TSP2's venous-looking
  arteries, club-like goblet cells);
- nothing more is dropped.

### 55. The lung reference's gates: NO GO as built, narrowly (Track I), 2026-10-18

**Why:** the lung's gates were fixed before any lung model
(`research/organ-references.md`, "Lung"): G1, G2 and G4 are the colon's, and
G3 uses its own development data.

**The model:**
- 28 classes and 12,614 genes;
- members at 72 to 75% validation balanced accuracy;
- calibration top-1 60.5%;
- marginal conformal threshold 0.961.

**G1** (`research/notebooks/lung_development.py`; 240 uploads, 79,807 cells):
- **committed 73.4%: miss** (bar 75%);
- correct when committed 97.4%, coverage 90.3% and false abstention 0.01%,
  all passing.
- **By upload kind:**

  | Upload | Committed | Best guess |
  |---|---|---|
  | whole tissue | 99.1% | 81.9% |
  | eight classes | 98.0% | 79.2% |
  | one lineage | 55.7% | 49.9% |
  | one class | 31.6% | 24.5% |

**G3:**
- **MSV000094373: AUROC 0.62, miss.** 4 of the 5 control donors' epithelial
  pools are called macrophage (corrected 2026-10-19; it said 4 of 4). The BPD donors' epithelial pools are mostly
  called epithelial, and 7 of 10 endothelial pools are right.
- **The Protein Atlas: AT2 over AT1, AUROC 1.0, pass.** Every AT1 pool's
  argmax lineage is immune.
- **PXD029341: fibroblastic foci over alveoli, AUROC 0.88, pass.** Mean
  P(stromal) is 0.60 in foci, 0.33 in mature scar and 0.10 in alveoli.

**G4:** passed. The rehearsal on RNA pseudobulk written as a MaxQuant table
gave 32 pools and 100%.

**G2** (`research/notebooks/organ_donor_heldout.py lung fulcher_rank`; a
diagnosis):

| | Unseen donor | Seen donors |
|---|---|---|
| Class balanced accuracy | 68.4 | 72.1 |
| Group recall | 94.2 | 98.3 |
| Lineage recall | 97.9 | 99.7 |

The gap is 3.7 points (colon 12.5, blood 9.8).

**Verdict:** NO GO as built. Nothing was tuned. MSV000094189 stays sealed
(`side-tests.md`, amendment 10), and the decision goes to the owner.

**Note:** the lung is far closer than the colon. The colon's cause, narrow
uploads, shows here in milder form.

### 56. The lymph node: data roles, label audit (Track I), 2026-10-18

**Why:** after the lung (entry 55), the owner chose to move to the next organ
with the same recipe: the lymph node.

**The search:** no lymphoid-tissue single-cell MS set with independent labels
exists. The usable sets are tonsil micro-regions (Coscia lab) and sorted or
enriched B cells.

**Roles** (`side-tests.md`, amendment 11; the owner's choice):
- PXD042367's tonsil niches are locked, with the protocol committed before
  any download;
- PXD047762 (same lab), Zheng's tonsil pools, the Protein Atlas lymph-node
  pools and PXD011683 are development.

**Label audit** (`research/notebooks/organ_labels.py`):
- the class rule drops erythrocytes, pDCs and precursors;
- the "thymocytes" are mature T cells (CD1A, RAG1, DNTT at 0%; CD3E at 100%)
  and are merged into CD4 T and CD8 T;
- the generic "monocyte" class (9 to 32% on its own markers) is dropped.
- 19 classes remain.

### 57. The lymph node reference's gates: NO GO as built (Track I), 2026-10-18

**Why:** the lymph node's gates were fixed before any lymph node model
(`research/organ-references.md`, "Lymph node", with its note on the
deposits' layouts). G1, G2 and G4 are the colon's.

**The model:**
- 19 classes and 12,668 genes;
- members at 69.8 to 72.5% validation balanced accuracy;
- calibration top-1 60.5%;
- marginal conformal threshold 0.923.

**G1** (`research/notebooks/lymph_node_development.py`; 240 uploads, 78,926
cells): all four pass.
- committed 84.4% (bar 75%);
- correct when committed 95.5%, coverage 89.2%, false abstention 0.65%.
- **By upload kind:**

  | Upload | Committed | Best guess |
  |---|---|---|
  | whole tissue | 90.2% | 74.9% |
  | eight classes | 78.6% | 74.9% |
  | one lineage | 79.3% | 59.0% |
  | one class | 86.8% | 43.8% |

- Rare myeloid cells: the best guess names most of them, but the answer
  layer commits on 9 to 12% of macrophages, neutrophils and mast cells.

**G3:**
- **PXD047762's Fig. 3: AUROC 1.0, pass.** All 4 epithelium regions are
  called plasma cell at class level.
- **Zheng's tonsil pools: 41.0%, miss.** 44 of 48 pools are guessed plasma
  cell, whatever their population.
- **The Protein Atlas lymph-node pools: 100%, pass.**
- **PXD011683: 71.1%, miss.** 8 of sample group C's 15 and 5 of D's 15 are
  called T cell; F is all B cell.

**G4:** passed (`0ab21b9`). The rehearsal on RNA pseudobulk written as a
DIA-NN matrix in Excel gave B over T AUROC 1.0. The scorer's pass flag was
written as text, and is now a JSON boolean.

**G2** (`research/notebooks/organ_donor_heldout.py lymph_node fulcher`; a
diagnosis):

| | Unseen donor | Seen donors |
|---|---|---|
| Class balanced accuracy | 53.7 | 57.2 |
| Group recall | 89.9 | 93.4 |
| Lineage recall | 96.6 | 97.3 |

The gap is 3.5 points (lung 3.7, colon 12.5, blood 9.8).

**Verdict:** NO GO as built. Nothing was tuned. PXD042367 stays sealed
(`side-tests.md`, amendment 12), and the decision goes to the owner.

**Note:** the misses are on protein pools, not on simulated uploads. Out of
the reference, and in one upload of mixed pools, the lymph node's answers
collapse onto plasma cell.

### 58. Organ references v2: diagnostics, candidates and freeze (Track I), 2026-10-18 to 2026-10-20

**Why:** the owner asked to correct the three organs that missed their
gates (entries 52, 55 and 57). Every suspected cause was tested by a
diagnostic, each committed with its rules before it ran, on v1's bundles,
v1's calibration suites and seen development sets only. The design is in
`research/organ-references.md`, "Version 2".

**The owner's decisions (2026-10-18), fixed before any diagnostic:**
- G1 is split: mixed uploads meet the four bars; narrow uploads must be
  correct when committed at least 90%;
- fresh G3 sets, never read before; the v1 sets are reported as seen;
- the order is the lymph node, the lung, then the colon.

**The diagnostics** (`research/notebook-outputs/organ_v2_*`):

| Step | Commit | Result | Decision |
|---|---|---|---|
| A1, Ig and serum masking | `bff18d6` | No sink moves in any organ | v2 removes no genes |
| A1b, sink probes | `6e07438` | The encoder makes the sink on deep, mixed pools; thinning pools to single-cell depth halves the lymph node's; B-cell pools alone are never plasma | An explanation only |
| A0, calibration cache | `e9ab07e` | The cache replays the service exactly; the refit check was amended from rank to a qhat bound of 0.005 (`b2fc37c`; largest shift 0.0008) | A2 and A3 may run |
| A2, banded calibration | `93566be` | Lung mixed uploads 96.6% committed on v1's own rule; lymph node 78.5%; colon 16.8%, and 97.1% only with each upload's band known. Mixed-only calibration leaves narrow uploads 65 to 88% correct when committed | Mixed-only calibration is unsafe; the colon needs a band key |
| A3, rare and hard classes | `93566be` | The chance floor lifts the lymph node's rare-class commitment 82 → 97 (coverage 91.1 → 88.2); the group fallback suits the lung and colon | Lymph node: the chance floor; lung and colon: the group fallback below 30 cells |
| A4, colon band key | `23f3747` | No label-free key passes: each reads a real narrow upload as mixed, or no real mixed upload as mixed | **The colon v2 is not built** |
| A6, pool training | `23f3747` | The lymph node's plasma guesses fall 44 → 35 of 48 (the bar asked 12 fewer); single-cell validation rises 0.7 to 6.5 points in every organ | v2 does not train on pools |
| A5, profiles | — | Not run; no v2 decision depends on it once G1 is split | — |

**Fresh G3 sets** (`side-tests.md`, amendment 13, `ad6b3c4`):
- the lymph node: PXD045043, spleen red and white pulp voxels. jPOST
  refused this network until 2026-10-20; the fetched matrix holds exactly
  26 labelled voxels (`c5d0524`);
- the lung: PXD058626, control airway and alveolar regions;
- the colon: PXD069723, reserved and unread, since no colon v2 is built.

**The candidates** (`271daae`; pre-registered in `bdeefbb`, with the suites'
sha256s in `research/notebook-outputs/organ_v2_registry.json` before
training):

| | Lymph node v2 | Lung v2 |
|---|---|---|
| Classes | 18 (v1's minus the generic "t cell") | 27 (v1's minus the generic "monocyte") |
| Calibration | chance floor | group fallback below 30 cells |
| Members' validation | 69.8 to 72.8% | 74.3 to 78.6% |
| Calibration top-1 | 66.4% | 66.3% |
| Marginal qhat | 0.888 | 0.944 |
| MANIFEST sha256 (frozen `d9d400f`) | `5fb71df0…` | `1e545828…` |

Everything else is v1's: split (carried through the atlas rows), gene
space, profiles, training and fusion.

**The locked tests' baselines** (`a806049`): the protocols' rule 8
baselines (correlation and PCA with kNN) now run on each candidate's own
gene space and labels (`benchmark/organ_baselines.py`). The intakes save
the upload over the organ's genes, and the scorers refuse a real scoring
without `baselines.json` (each protocol's amendment 2).

**G4, the locked tests' rehearsals on the v2 bundles:**
- lymph node v2: B over T AUROC 1.0, p 1e-4 (`f805bec`); baselines:
  correlation 1.0, PCA kNN 0.597;
- lung v2: 32 pools, every lineage 100% (`476fcc1`); baselines: correlation
  100, PCA kNN 96.9.

A code review then found the PCA baseline's projection off-centre: queries
were shifted toward the small classes, and 65% of their neighbours were
other queries. Projected around the class-balanced centre, the rehearsals
give PCA kNN 1.0 (lymph node) and 100 (lung). Each protocol's amendment 3
records the fix and the setup checks, before any real scoring.

G1 and G3 then ran once per candidate (entry 59).

### 59. Organ references v2: the gates, both NO GO; A7 (Track I), 2026-10-20

**Why:** entry 58's two frozen candidates ran their gates once
(`research/notebooks/organ_v2_gates.py`), the lymph node first, under the
split G1 and the fresh G3 sets. Details are in `research/organ-references.md`,
"Version 2".

| | Lymph node v2 | Lung v2 |
|---|---|---|
| G1 mixed: committed, correct when committed | 96.5, 97.7 (pass) | 97.3, 98.6 (pass) |
| G1 mixed: coverage, false abstention | 92.4, 0.32 (pass) | 96.6, 0.0 (pass) |
| G1 narrow: correct when committed (≥ 90) | **89.8 (miss)** | 90.1 (pass) |
| G1 as v1 wrote it: committed | 95.5 (v1 84.4) | 83.7 (v1 73.4) |
| G3, fresh (AUROC ≥ 0.8) | PXD045043 spleen, white over red pulp: 0.917 (pass) | PXD058626, control airways over alveoli: **0.764 (miss)** |
| G4, the rehearsal | pass | pass |
| Verdict | **NO GO** | **NO GO** |

**What the misses show:**
- **The lymph node:** the chance floor commits more narrow uploads (94.3%
  against 87.3% under v1's rule in A2), and one- and two-class uploads are
  then wrong more often (84.7% and 86.8% correct when committed). A3 judged
  the floor on a pooled suite, and its adoption rule did not check the
  narrow band.
- **The lung:** every region gets the right lineage, but airway epithelium
  is often guessed as alveolar (4 of 12 control airways are type II
  pneumocyte). No v1 gate tested within-epithelium regions.
- **The plasma sink** on tissue pools remains in both (seen sets).

**Locked tests:** PXD042367 and MSV000094189 stay sealed. Each protocol's
rule 1 allows no candidate that missed its gates. Nothing was tuned. A
change to either organ is a v3, the owner's call, and its G3 cannot reuse
PXD045043 or PXD058626, which these runs read.

**G2** (one donor held out, a diagnosis), class balanced accuracy unseen
against seen:
- lymph node v2: 55.7 against 59.3, a gap of 3.6 (v1 3.5);
- lung v2: 70.30 against 75.55, a gap of 5.25 (v1 3.7).

**A7, the colon** (`research/notebooks/organ_v2_declared.py`, rules
committed before it ran, `2bdbcf3`): could a user declare a colon upload
mixed, so it gets the mixed band's thresholds? On simulated uploads,
declared-mixed uploads stay at 94.0% correct when committed even with 10%
of them really narrow. On real protein the idea fails:
- Kabatnik's truly mixed upload, declared mixed, has 44.4% of its cells
  committed and wrong (bar 10%);
- narrow uploads declared mixed reach up to 83% wrong.

Not supported. The colon's pools are placed in the wrong lineage before any
threshold applies, so calibration cannot fix it. The colon stays NO GO.

**Also tonight:**
- a code review of the organ v2 code found the PCA baseline off-centre
  (entry 58's note; amendment 3);
- an organ map's hidden Your data could be reached by an arrow key or a
  dropped file, which would have drawn blood answers on the organ's map.
  It is closed, with a test.

### 60. Label stability between releases (release protocol), 2026-10-20

**Why:** the release protocol's step 5 (`docs/web/manifest.md`) asks for
label stability against the previous release. No release had measured it,
because v3 answers at class level only and later models at three levels.

**The definition** (`research/notebooks/label_stability.py`, committed
before the run, `af116da`):
- each answer stands for the classes it covers in v3.1's hierarchy;
- a cell is same, refined, coarsened, contradicted, newly answered or newly
  abstained;
- stability is same, refined and coarsened together.

Every served model (v3, v3.1, v4.1, v4.2) answered the development protein
uploads, each sent whole through `run_projection`: Fulcher 2026, PBMC240,
SCoPE2 as published and Furtwängler 2025, 5,509 cells. The first check
passed: v4.1 answered every upload identically twice.

| Release | Stable | Contradicted | Newly answered | Newly abstained | Best guess agrees |
|---|---|---|---|---|---|
| 0.2.0 (v3) to 0.3.0 (v3.1) | 31.4% | 16.3% | 30.4% | 21.9% | (none in v3) |
| 0.3.0 (v3.1) to 0.4.0 (v4.1) | 99.5% | 0% | 0% | 0.5% | 79.4% |
| 0.4.0 (v4.1) to 0.5.0 (v4.2) | 99.9% | 0% | 0.07% | 0% | 95.6% |
| 0.5.0 (v4.2) to 0.6.0 (v4.1) | 99.9% | 0% | 0% | 0.07% | 95.6% |

**What it shows:**
- v3.1 replaced v3's answers wholesale: a new encoder, a new rule and
  hierarchical answers.
- Since then, every release kept v3.1's answers and changed only the best
  guess. Fulcher moved most: 97.8% stable into v4.1, and its best guess
  agrees 70.8%. v4.2's protein class means changed Fulcher only, among
  these uploads.
- Nothing any release answered was contradicted by the next.

### 61. Blood, trained with RNA pools as well as single cells (a diagnostic), 2026-10-20

**Why:** in the organs, training on pseudobulk pools did not remove the
sinks, but it raised single-cell validation by 0.7 to 6.5 points in every
organ (entry 58, A6). Blood's served encoder never saw pools.

**How** (`research/notebooks/blood_pools.py`; rules committed before the
run, `953490f`; a plumbing fix after a crash before any result,
`8e09c50`):
- blood's organ-layout work folder, with A6's pool settings: 3,110 pools
  over 22 classes;
- control and pooled members for seeds 1 and 2;
- each read by nearest centroid.

| | Seed 1 control | Seed 1 pooled | Seed 2 control | Seed 2 pooled |
|---|---|---|---|---|
| Validation balanced accuracy | 66.7 | 71.1 | 67.8 | 73.3 |
| Calibration-suite top-1 | 60.9 | 66.3 | 63.2 | 67.3 |
| Fulcher 2026, six types (development) | 56.8 | 58.7 | 53.0 | 60.1 |

**Reading, fixed before the run:** pools are "promising for blood" only if
Fulcher gains at least 2 points in every seed, and nothing else falls by
more than 2. Seed 1 gained 1.82 on Fulcher, so the verdict is **not
promising**, as written.

**What it shows anyway:**
- Every measure improved in both seeds: validation +4.4 and +5.5,
  calibration top-1 +5.4 and +4.1, Fulcher +1.8 and +7.1.
- One seed's Fulcher swing is about the seed spread (V2's five seeds:
  57.3 ± 2.2).

Blood v4.1 is unchanged. A pooled blood candidate would be a new model:
five members, its own pre-registered gates on a fresh suite, and the
owner's decision.

### 62. The lymph node v3 (calibration-only), 2026-10-21

**Why.** The owner chose the calibration-only v3 from "Options for a v3":
lymph node v2's members with v1's calibration rule, since v2 missed only its
narrow-upload bar (89.82, bar 90) and the chance floor commits more of the
narrow uploads it gets wrong.

**Fixed first** (`431fa3b`, before calibration): `scripts/organs/lymph_node_v3.json`
(v2's file without the floor, a new evaluation-suite seed); the data stages
reproduced v2's files, the calibration suite's sha256 included; side-tests
amendment 16 (G3 reuses PXD045043 with the owner's leave); the protocol's
amendment 6; `research/organ-references.md`, "Version 3".

**Build** (`b9e4bd9`): v2's members copied (sha256 equal); calibrate, layer
and bundle. The pre-registered checks passed: every bundle file but the two
specs equals v2's; the temperatures and the out-of-distribution threshold are
v2's; the thresholds change only for the 8 classes v2's floor had capped at
0.9444. MANIFEST `0cbd39dc…` registered before any gate.

**Gates** (`research/notebook-outputs/lymph_node_v3_development/`; G4 passed
first, the rehearsal's B over T AUROC 1.0):

| Gate | v3 | v2 | Bar | |
|---|---|---|---|---|
| G1 mixed: committed / correct when committed / coverage / false abstention | 80.37 / 98.73 / 95.20 / 0.26 | 96.47 / 97.65 / 92.38 / 0.32 | ≥ 75 / ≥ 90 / ≥ 85 / ≤ 2 | pass |
| G1 narrow: correct when committed | **89.99** | 89.82 | ≥ 90 | **miss, by 0.01** |
| G3 PXD045043, white over red pulp | 0.9172 | 0.917 | ≥ 0.8 | pass (unchanged, as predicted) |
| G1 as v1 wrote it: committed / correct when committed | 80.37 / 95.36 | 95.55 / 94.39 | (reported) | |

G2 is v2's (it never reads calibration): 55.7 unseen, 59.3 seen.

**NO GO, by 0.01 points.** v1's rule commits less (80.4% against 96.5% for
mixed uploads) but barely changes the narrow uploads' accuracy, because the
miss is still the B cells': in narrow uploads they are committed 94.1% and
correct when committed 67.7% (read as T cells), 2,395 of the 3,087 wrong
answers. Without them narrow uploads are 97.05% correct when committed. The
floor's 8 rare classes were never the cause. Nothing is tuned; PXD042367
stays sealed (side-tests amendment 17).

**What would move it** is the B cells' reading in narrow uploads, the same
weakness blood v4.1 shows (a listed Manuscript failure mode), not
calibration. A v4 would need a change to the encoder or the reference, and
a fresh G3 set.

### 63. The pooled blood candidate v5.3, 2026-10-21

**Why.** The owner chose to build a pooled blood candidate although entry
61's fixed reading said "not promising" (seed 1's Fulcher gain 1.82, bar 2).
That reading stood; v5.3 was a new candidate with its own gates.

**Fixed first** (`600c2ad`, before any training): side-tests amendment 18;
`research/notebooks/v53_gates.py`, with its gates and a self-check that v4.1
reproduces its committed development figures.

**How:** five V2 members trained on this PC's GPU with the diagnostic's 3,110
RNA pools added to the 55,402 training rows, on the original labels
(`v5_train.py clean --variant v5.3`, 885 s). Validation balanced accuracy by
seed: 73.59, 71.97, 70.30, 69.97, 72.57. v4.1's rule on them
(`v5_build.py build --variant v5.3`): calibration-suite top-1 67.23.

**Gates** (`research/notebook-outputs/v53_gates/`; the self-check passed,
v4.1 at 69.05 and 92.31 exactly):

| Gate | v5.3 | v4.1 | Bar | |
|---|---|---|---|---|
| Fulcher 2026, six-type balanced accuracy | 69.39 | 69.05 | ≥ 71.05 | miss |
| PBMC240, lymphoid recall | 87.18 | 92.31 | ≥ 90.31 | miss |
| Fulcher, answers committed | 85.69 | 88.57 | ≥ 86.57 | miss |
| Fulcher, correct when committed | 95.43 | 97.93 | ≥ 96.93 | miss |
| Out-of-reference AUROC (Fulcher against Furtwängler's progenitors) | 0.7985 | 0.7898 | ≥ 0.7598 | pass |

Reported only: PBMC240 myeloid recall 100 (v4.1 80); Fulcher CD8 T recall
23.76 (unchanged), CD4 T 80.19 (82.47), DC 29.63 (22.22); SCoPE2 restricted
40.97 (48.4).

**NO GO.** Pools raised the members' own validation scores, but as served,
with v4.1's rule, v5.3 is no better on Fulcher and worse on PBMC240's
lymphoid cells and on the answers. CD8 T recall, the weakness the pools were
hoped to help, did not move. The spec's evaluation block says "development
gates missed", so the service keeps refusing v5.3; it is not a candidate for
the sorted CD4/CD8 test. Nothing is tuned.

### 64. Gene weights from protein-RNA agreement in the correlation term (candidate v4.3), 2026-10-21

**Why:** step 1 of the 2026-10-21 data search's report
(`research/reference-data-search.md`). v4.1's correlation term counts every
gene the same, although some genes' RNA contrasts between classes might not
hold on protein.

**Fixed first** (`research/notebooks/gene_weights.py`, committed before the
run; side-tests amendment 20 for its data): each feature gene weighted by
max(0, rho), rho the Pearson correlation across v4.2's 16 covered classes
between v4.1's RNA class means and Rieckmann 2017's protein class means;
protein uploads only. Self-checks passed: unit weights reproduce v4.1's
correlation exactly, and v4.1 reproduced Fulcher 69.05 and PBMC240 92.31.

**The weights:** 7,996 of 9,002 feature genes have a protein; their median
rho is 0.435, and 17.1% get weight 0. Monaco 2019's sorted RNA gives similar
weights (Spearman 0.64 over 7,989 genes and 14 classes).

| Gate | v4.3 | v4.1 | Bar | |
|---|---|---|---|---|
| Fulcher 2026, six types | 69.34 | 69.05 | ≥ 71.05 | miss |
| PXD056050 pools (another lab), five sorted groups | 57.5 | 57.5 | ≥ 57.5 | pass |
| PBMC240, lymphoid recall | 92.31 | 92.31 | ≥ 90.31 | pass |
| Fulcher, answers committed / correct when committed | 88.65 / 97.93 | 88.57 / 97.93 | ≥ 86.57 / ≥ 96.93 | pass |
| Out-of-reference AUROC | 0.7951 | 0.7898 | ≥ 0.7598 | pass |

Fulcher's CD8 T recall is 23.76 for both. PBMC240, both SCoPE2 versions and
Furtwängler are unchanged (the correlation term is flat there).

**NO GO.** Nothing is tuned; v4.3 is not built.

**What it shows:**
- Most genes' RNA contrasts between classes hold on protein (median rho
  0.435), so the correlation term is not where CD8 T cells are lost.
- **Another lab's sorted pools show the CD8 T failure plainly:** v4.1 calls
  all 4 FACS-sorted CD8 T pools of PXD056050 CD4 T, and both activated-NK
  pools non-classical monocyte; B (7 of 8), total T (4 of 4) and monocytes
  (4 of 4) are right. With Fulcher (CD8 T recall 23.8) and Khoury (2.7),
  that is a third lab where CD8 T cells are read as CD4 T. The cause lies in
  the encoder and its reference, not the correlation term.

### 65. Do the Allen atlas's dendritic cells land on Tabula Sapiens's centroids? A probe, 2026-10-21

**Why:** step 2 of the data search's report: fill blood's empty classes
(myeloid DC, pDC, CMP) from the Allen Human Immune Health Atlas (108
donors). Hao 2021's DCs failed in the class centres (entry 40), so a probe
first, with its reading fixed before the run
(`research/notebooks/allen_dc_probe.py`, `fb58067`).

**How:** up to 2,000 cells per Allen label, normalised as Tabula Sapiens
(log1p of counts per 10,000), embedded the reference's way by v4.1's five
members; each member's class-balanced centroids. Platelets and erythrocytes
are the control.

| Allen cells | n | Recall of the target class | Where most land |
|---|---|---|---|
| cDC1 | 943 | 0.0 | non-classical monocyte, monocyte, CD4 T |
| cDC2 (three states) | 5,236 | 0.0 to 0.03 | non-classical monocyte, monocyte, CD4 T |
| pDC | 2,000 | 0.09 | monocyte, HSC, CD4 T |
| CMP | 1,075 | 4.26 | monocyte, non-classical monocyte |
| Platelet (control) | 2,000 | 85.74 | platelet |
| Erythrocyte (control) | 1,508 | 66.25 | erythrocyte |

The Allen pDC centre's cosine with Tabula Sapiens's pDC centroid is -0.13
to 0.20 across the members; the cDC centre's with the myeloid DC centroid,
-0.36 to 0.35 (bar 0.5).

**Reading, as fixed: route B.** The controls land, so the atlases are not
the problem in general; the encoder never learned a dendritic cell (it
trained on 1 myeloid DC and 29 pDCs), and it reads the Allen DCs as other
myeloid or T cells. No class centre can fix that. The Allen cells go into
training, beside Allen cells of every class, so that the atlas cannot stand
in for the class (side-tests amendment 21).

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
into a specification the service now builds from. Correcting SCoPE2's swapped
labels (entry 22) then reversed several of the SCoPE2 readings above,
among them the prototype export's finding about the restricted label space.
