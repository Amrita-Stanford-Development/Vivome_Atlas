# VivOME, Every Notebook Run

In order, with what each one established. The existing notebooks come first,
since they predate everything built during this project, followed by every
notebook built and run over the course of it.

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
Nine cells, Q1 through Q5. Macrophage's apparent negative silhouette turned
out to be a sampling artefact, the real value is positive. Conformal
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

### 3. `Unsupervised_PBMC240.ipynb`
Nine cells. Preprocessing for the second proteomics dataset, marker derived
weak labels recovered for three lineages, T cell, NK cell, monocyte. Real
coverage against the reference gene space measured at 34.8 percent.

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
paired mean difference around −1.4 points, p between 0.05 and 0.07. Selected
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
recovered from Drive; it is now committed with LFS.

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
| Oracle restricted, all uploads | 75.5 | 86.5 |

The dual channel variant (per upload gene wise z plus per cell z, trained on mini
uploads) won; per cell z alone was close and better on the SCoPE2 like scenario.
A synthetic check had shown why both channels matter: gene wise z scoring within a
single population erases its identity, per cell z keeps it.

**Verdict: NO GO on the pre set criteria.** Every simulation gate passed, but the
confirmatory real data gate failed, with real SCoPE2 restricted below 77.8. The
real data section's output was not saved in the run, so the size of the miss is
pending (`tables/real_data_confirmatory.csv` on Drive). Plan: carry both v3 and the
dual encoder into NB2 and decide at NB4 on the full pipeline, without moving the
gate after the fact.

It also settled Track A2's preprocessing choices on the shipped model: the per cell
mask beat median fill by 3.2 points unrestricted and 4.7 oracle, skipping the log
transform of linear intensities cost about 3 points, and building the smoothing
graph on raw rather than z scored log values made no difference. The coverage
curve puts the floor at about 200 observed genes, with accuracy at chance below
100.

---

## The throughline

Fourteen notebooks built end to end, three existing ones worked inside of. None of
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
open.
