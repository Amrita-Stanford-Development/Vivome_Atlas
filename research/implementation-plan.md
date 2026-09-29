# VivOME, Implementation Plan for Nature Communications

**Target window:** 12 weeks to submission
**Target venue:** Nature Communications
**Fallback venues:** Genome Biology, then Nucleic Acids Research Web Server Issue

---

## 1. The Paper We Are Actually Writing

Before any task list, the claim has to be fixed, because every remaining piece of work either supports it or should be cut.

**Proposed title direction**
Cross modal single cell integration achieves directional alignment without representational alignment, and the resulting discordance identifies post transcriptionally regulated genes.

**The three claims**

1. **Diagnostic claim.** Current integration methods are judged by mixing scores and by transfer accuracy, and both can be high while a linear probe still recovers the source modality with near perfect accuracy. We call this directional alignment, meaning same type cells from both modalities point in the same direction, while the representations themselves remain modality specific. We quantify it, and we show it holds across published methods, not only our own.

2. **Biological claim.** The genes that the two encoders disagree on are not noise. They are enriched for genes with known poor agreement between messenger RNA level and protein level. A cross modal model therefore flags post transcriptional regulation without ever being told about it.

3. **Resource claim.** VivOME is a versioned joint latent atlas with a projection service, calibrated confidence, and explicit abstention outside supported label space.

Claim 1 is the methodological contribution, claim 2 is the discovery, and claim 3 is the deliverable. Nature Communications will accept a paper on claims 1 and 2 supported by claim 3. It will not accept claim 3 alone.

**What this means for the current work.** Track A stays central. The explainability pass becomes the evidence base for claims 1 and 2, rather than a standalone chapter. Track B moves to supplementary, as a generalisation check. Track C becomes an external validation dataset. The atlas becomes a real service.

---

## 2. Honest Assessment of the Gap

| Requirement at this venue | Current state | Severity |
|---|---|---|
| Comparison against established methods | None exist | Blocking |
| Statistical variance on reported numbers | Single runs only | Blocking |
| Cross modal claims across many cell types | Two cell types only | Blocking |
| Paired ground truth for alignment quality | None, all evidence is at centroid level | Blocking |
| Discovery separable from artefact | Explicitly unresolved | Blocking |
| Reproducible code | Notebooks with known bugs | High |
| Usable resource | Static viewer only | High |
| Flagship cell type performance | Macrophage RNA accuracy at 42.28% | High |

Five blocking items in twelve weeks is aggressive but achievable, provided the work is run as a pipeline rather than as notebooks, and provided two of the phases run in parallel.

---

## 3. Phase Structure

Phases overlap deliberately. The timeline does not survive a strictly sequential run.

```
Week:        1  2  3  4  5  6  7  8  9 10 11 12
Phase 0  [====]
Phase 1  [==========]
Phase 2     [================]
Phase 3        [======================]
Phase 4              [==================]
Phase 5                    [=========================]
Gates:              G1          G2          G3
```

---

## 4. Phase 0, Foundation Repair
**Weeks 1 to 2. Blocking for everything else.**

**Rationale.** Nothing downstream is possible from notebooks. Running six methods across five datasets at five seeds is roughly 150 training runs, and that cannot be managed by hand. This phase is unglamorous and it is also the phase most likely to be skipped, which is why it is listed first.

**Tasks**

- Refactor the codebase into an installable package with a command line entry point. Model, data loading, training, and evaluation become modules. Notebooks become thin wrappers that call the package.
- Introduce a configuration system, so that every run is described by a single config file that is saved alongside its outputs.
- Pin the environment. Produce a lockfile and a container image. The Enrichr and decoupler failures both trace back to environment drift.
- Fix the known bugs. The `rna_data` NameError in the export cell, the Enrichr JSON failure, which needs retry logic and a local gene set fallback rather than a live network call, and the missing decoupler dependency.
- Freeze dataset versions. Record accession numbers, download dates, and file checksums for every input.
- Set up experiment tracking, so that 150 runs remain interpretable.

**Exit criterion.** A single command reproduces the current headline result end to end, from raw files to reported number.

---

## 5. Phase 1, Statistical Rigour
**Weeks 1 to 4. Runs alongside Phase 0 once the package exists.**

**Rationale.** Every number in the current briefing comes from one run. This is the fastest route to rejection without review, and it is also the cheapest problem to fix.

**Tasks**

- Repeat every headline experiment across ten random seeds. Report mean with 95 percent confidence intervals. Ten rather than five, because several of your differences are around one percentage point, and five seeds will not resolve them.
- Re examine the latent dimension conclusion. The current claim is that the model is insensitive to latent size, based on a spread of about one point across single runs. With intervals, this claim either becomes properly supported or it dissolves. Both outcomes are publishable, but the current evidence supports neither.
- Complete the semi supervised sweep at 64 and 128 dimensions. The production setting is 128, and there are currently no label efficiency results at that setting, which a reviewer will notice.
- Add negative controls. Train with shuffled cell type labels, train with shuffled modality assignment, and train on random gene subsets. These establish the floor that every positive result is measured against, and they are required later in Phase 3.
- Address the macrophage problem. RNA accuracy of 42.28 percent on the flagship cell type is indefensible as reported. Test class balanced loss weighting, focal loss, and resampling. Report the corrected figure, and report the original alongside it, with the class imbalance relationship, currently r equals 0.807, presented as a finding rather than hidden.
- Replace point estimates on transfer accuracy with stratified bootstrap intervals. The proteomics test set is 298 cells, so the uncertainty on 98.3 percent is substantial and should be stated.

**Exit criterion.** Every number destined for the manuscript carries an interval.

---

## 6. Phase 2, Paired Ground Truth
**Weeks 2 to 6. The single most important addition.**

**Rationale.** Every cross modal claim currently rests on two cell types, and on unpaired data, which means alignment can only be measured at the centroid level. Centroid cosine similarity of 0.98 sounds strong, but it is a weak measurement, because it says nothing about individual cells. CITE-seq provides messenger RNA and protein measured in the same cell, which gives true per cell correspondence and twenty or more cell types instead of two.

**Tasks**

- Acquire two or three public CITE-seq datasets. The Hao et al human peripheral blood mononuclear cell reference is the obvious primary choice, given its scale and its large antibody panel. A second dataset from a different laboratory provides the replication.
- Train with pairing hidden. The model sees the two modalities as unpaired, exactly as it sees SCoPE2. Pairing is used only at evaluation time.
- Add per cell alignment metrics. Fraction of samples closer than the true match, which is the standard measure in this literature, plus k neighbour recall of the true partner cell. These are the metrics your work currently cannot produce, and they are the ones reviewers trust.
- Extend cross modal evaluation to the full cell type range that CITE-seq supports, which converts the two cell type limitation into a supplementary caveat rather than a central weakness.
- Apply the trained cross modal model to PBMC240, which currently has only a classical baseline. This is a second mass spectrometry proteomics dataset from a different instrument, so it is your platform generalisation evidence.

**Important caveat to state explicitly in the manuscript.** CITE-seq panels measure a few hundred surface proteins by antibody, while mass spectrometry measures thousands of intracellular and secreted proteins. They are not equivalent. CITE-seq is therefore used as a validation axis for alignment quality, and mass spectrometry remains the primary application. Stating this yourself is considerably better than having a reviewer state it.

**Exit criterion.** Per cell alignment accuracy reported across more than fifteen cell types, on at least two independent paired datasets.

---

## 7. Phase 3, The Discovery
**Weeks 3 to 9. This is what makes it Nature Communications.**

**Rationale.** The briefing already concedes that the discordant gene result cannot currently be separated from an artefact, because the two encoders rely on uncorrelated feature sets by construction. That concession is correct, and it is also solvable. If discordance survives controls and replicates against external data, it is a genuine discovery. If it does not, the paper drops to a different venue, and it is far better to know this at week five than at week eleven.

**Stage A, controls. Weeks 3 to 5.**

- Stability across seeds. Recompute the RNA dominance and proteomics dominance rankings across all ten seeds. If the top gene lists are unstable, the result is noise. This is the first and hardest test.
- Label shuffled retraining. Under shuffled labels, discordance should collapse toward the null. If it does not, discordance reflects encoder architecture rather than biology.
- Encoder swap control. Train two encoders on the same modality, split by donor or by batch. Any discordance recovered here is a baseline artefact level, and real cross modal discordance must exceed it.
- Complete Stage 6, the unsupervised run, which currently has no notebook. If discordance appears without any label supervision, the case strengthens considerably. Execute the clustering script that was written but never run, and report adjusted Rand index, normalised mutual information, and silhouette values.

**Gate G1, end of week 5.** If discordance is not stable across seeds, and does not collapse under shuffled labels, stop this phase. Move to the fallback venue plan in section 11.

**Stage B, external validation. Weeks 5 to 9.**

- Correlate the per gene discordance score against published measurements of messenger RNA to protein agreement. Candidate sources include large scale proteogenomic studies and human protein expression compendia. The prediction is that RNA dominant genes are enriched among genes with known poor correspondence.
- Test enrichment against mechanistic annotations of post transcriptional control, including RNA binding protein target sets, microRNA target predictions, protein half life measurements, and translation efficiency estimates from ribosome profiling.
- Run the cleanest available test, which comes free from Phase 2. In CITE-seq you can compute per gene messenger RNA to protein correlation directly, in the same cells, and compare it against the discordance score produced by a model that never saw the pairing. If those two agree, the claim is established rather than argued.
- Recover the failed enrichment analyses from the explainability pass, now that the environment is pinned. Gene ontology enrichment failed on all twenty one classes, and transcription factor enrichment was skipped entirely.

**A note on the attribution result.** The finding that attribution methods agree with each other far better than they agree with causal ablation, at 0.952 between methods against 0.341 against ablation, is a strong secondary result. It is a caution to the field about interpreting attribution outputs in single cell models. Keep it, and give it a supplementary figure, but do not let it compete with the main claim for space.

**Exit criterion.** Discordance replicates in at least two independent external sources, with effect sizes and significance reported.

---

## 8. Phase 4, Benchmarking
**Weeks 5 to 10.**

**Rationale.** There is currently no comparison against any established method. This is the criticism you will receive from every reviewer, without exception. It is also the phase that generalises claim 1 beyond your own model, which is what turns a local observation into a field level contribution.

**Tasks**

- Benchmark against the established methods. Seurat bridge integration, GLUE, MaxFuse, scArches, and Harmony on shared features, plus your existing principal component and nearest neighbour approach as the floor. Where paired data allows, include totalVI.
- Evaluate across all datasets, meaning SCoPE2, PBMC240, both CITE-seq datasets, and the multi tissue RNA set from Track B.
- Use the standard single cell integration benchmarking metric suite rather than metrics written in house. Reviewers trust established metrics, and homemade ones invite questions about selection.
- Add your own metric to the panel. Run the modality probe on the outputs of every competing method. This is the critical experiment for claim 1. If published methods also show high probe accuracy alongside good mixing scores, then directional alignment is a general property of the field, and your diagnostic becomes broadly useful. If only your model shows it, the finding becomes a limitation of your model instead, and the framing must change.
- Report runtime, memory, and scaling alongside accuracy.

**Gate G2, end of week 8.** Review benchmark outcomes. If competing methods substantially outperform CrossModalNet on transfer accuracy, the paper's centre shifts from the model to the diagnostic and the discovery, both of which survive that outcome. Decide this consciously rather than by default.

**Exit criterion.** A complete comparison table with intervals, plus the modality probe applied across all methods.

---

## 9. Phase 5, VivOME as a Resource
**Weeks 6 to 11.**

**Rationale.** In its current form VivOME is a static viewer serving precomputed coordinates from one frozen model, with thirty saved plots. That is a supplementary figure. For the resource claim to hold, a user must be able to submit their own data and receive something back.

**Tasks**

- Build the projection service. A user submits a proteomics or RNA matrix, and receives coordinates in the shared latent space, transferred labels, and a confidence score.
- Implement calibrated abstention. Use conformal prediction to return label sets with guaranteed coverage, and return no label when the query falls outside supported latent space. This directly converts your worst limitation into the tool's most defensible feature, since only two cell types have proteomics support and the tool should say so rather than guess.
- Add the support map. A view showing which of the twenty two cell types have genuine cross modal evidence, and which are RNA only. This is honesty made into an interface element, and reviewers respond well to it.
- Add the alignment diagnostic panel. Every projection returns the modality probe score, centroid gap, and per class alignment quality. This ships claim 1 as a usable tool rather than only as a figure.
- Publish the benchmark as a standing comparison page inside the atlas, with fixed datasets and metrics.
- Make the atlas genuinely versioned, as the name promises. Tagged releases, a persistent identifier for each, model cards, and a documented protocol for adding a dataset. Measure and report label stability across versions, which nobody in this space currently does.
- Move from static hosting to a backend that can run inference, with documentation, a tutorial, and example data.

**Exit criterion.** A third party can submit their own matrix and receive calibrated labels, without contacting you.

---

## 10. Phase 6, Writing and Submission
**Weeks 8 to 12.**

**Rationale.** Figures are drafted before text, because the figure set determines what the paper can claim, and because gaps in the figure set are cheaper to fix at week eight than at week eleven.

**Proposed main figure set**

1. Overview. Study design, data landscape, model architecture, and the label availability asymmetry that motivates the work.
2. Benchmarking. Transfer accuracy and biological conservation across all methods and datasets, with intervals.
3. Paired validation. Per cell alignment metrics on CITE-seq, across the full cell type range.
4. Directional alignment. Centroid similarity against modality probe accuracy, shown across all methods, with the disjoint encoder feature usage panel.
5. Discordance and post transcriptional regulation. Discordance scores against external messenger RNA to protein agreement, plus mechanistic enrichment.
6. VivOME. Projection, calibrated abstention, support map, and diagnostic panel.

**Supplementary set.** Latent dimension sweep with intervals, semi supervised label efficiency grids, the full explainability pass, ablation against attribution disagreement, Track B multi tissue generalisation, all negative controls, and per class performance tables.

**Tasks**

- Week 8, draft all main figures from available results, identify gaps, and route them back into the relevant phase.
- Week 8, submit a presubmission enquiry to the editor, once Gate G1 has passed. This costs little and can save six weeks.
- Weeks 9 to 10, write methods first, then results. Methods written while the work is fresh are considerably more accurate.
- Week 10, prepare data and code availability. Repository, container, archived release with identifier, and processed data deposits.
- Week 11, internal review by someone who has not worked on the project, followed by revision.
- Week 12, assemble reporting summary, cover letter, and submit.

**Gate G3, end of week 10.** Full draft complete with all figures. If any main figure is still missing data, either cut the claim it supports, or delay submission. Do not submit with a placeholder.

---

## 11. Risk Register and Fallbacks

| Risk | Likelihood | Response |
|---|---|---|
| Discordance fails seed stability at Gate G1 | Medium | Drop claim 2. Paper becomes tool plus benchmark plus diagnostic. Redirect to Genome Biology or the web server issue. Approximately four weeks saved. |
| CITE-seq per cell alignment is poor | Medium | Report honestly, and reframe as evidence that centroid level alignment overstates integration quality. This actually reinforces claim 1. |
| Competing methods outperform on transfer accuracy | Medium to high | Shift the centre to the diagnostic and the discovery, both of which are method agnostic. Prepared for at Gate G2. |
| Twelve weeks proves insufficient | High | Cut in this order. First the versioned release protocol, then Track B supplementary analysis, then the second CITE-seq dataset, then the semi supervised sweep extension. Never cut Phase 1 or the Phase 3 controls. |
| Compute becomes the bottleneck | Medium | Roughly 150 training runs are required. Confirm capacity in week 1, not week five. |

---

## 12. What Gets Cut

Some existing work does not serve this paper, and holding onto it costs time.

- The thirty precomputed plots in the atlas are replaced by the projection service. They can remain as an archive.
- Track B multi tissue work is complete and clean, but it is not central. It becomes a supplementary generalisation check, roughly one figure panel.
- The macrophage versus monocyte deep dive in Stage 2, including the parallel plane plots and the dedicated receiver operating characteristic curve, becomes supplementary once CITE-seq provides broader coverage.
- The two hundred and eighty two file output from the explainability pass needs curating down to what supports claims 1 and 2. Most of it will not appear.

---

## 13. Immediate Next Actions

The first three days determine whether the timeline is real.

1. Confirm compute capacity for approximately 150 training runs.
2. Begin the package refactor, since Phase 1 cannot start without it.
3. Identify and download the CITE-seq datasets, because acquisition and quality control always take longer than expected.
4. Run seed stability on the existing discordance result as soon as the package supports multiple seeds. This is the earliest possible read on whether the Nature Communications framing survives, and it can be done before anything else is finished.
