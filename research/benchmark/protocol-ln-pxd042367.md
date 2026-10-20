# Protocol: the lymph node reference's locked test, PXD042367 (Makhmut 2023)

**No file of this set has been opened or downloaded.** This protocol was
written on 2026-10-18 from PRIDE's file listing (names and sizes only) and the
paper (Makhmut et al., Cell Systems 2023, doi 10.1016/j.cels.2023.10.003;
preprint doi 10.1101/2023.05.13.540426), before any label, sample name or
protein list of the set was read. Its role is set in
`research/benchmark/side-tests.md`, amendment 11; the reference it tests is
planned in `research/organ-references.md`, "Lymph node".

- **Freezing.** This file is frozen at the commit that adds it. Changes
  before unsealing go in dated amendments, committed first. After unsealing,
  only format fixes (rule 9).
- **One scoring,** after the lymph node candidate is frozen (rule 1).
- **What a result means.** An internal held-out test of the lymph node
  reference on laser-microdissected tonsil micro-regions, never external
  validation and never a single-cell accuracy. Every report states:
  - the regions are mixtures of the cells in a 4,000 µm² circle;
  - the tissue is tonsil, a secondary lymphoid organ like the lymph node but
    not one;
  - all regions come from one section of one donor;
  - the development set PXD047762 comes from the same lab and may share
    tonsils (the owner's choice, amendment 11).

## Data (PRIDE record and the paper)

- **File used:** `DIANN_results_Fig4.rar` (230,205,158 bytes), the DIA-NN
  results of the paper's tonsil-niche experiment (its Figure 4). Not used: the
  other figures' results, the raw archives and the FASTA files.
- **Samples (the paper's methods):**
  - FFPE palatine tonsil from recurrent chronic tonsillitis;
  - one section stained for CD19 or CD20 (B cells), CD3 (T cells),
    pan-cytokeratin (epithelium) and DNA;
  - 146 circular micro-regions of 4,000 µm², annotated by hand in QuPath on
    the staining and the tissue's architecture;
  - the classes: germinal-centre dark, grey and light zones, mantle zone
    (36), interfollicular T-cell zone (34) and squamous epithelium.
- **Acquisition:** EASY-nLC 1200 with a timsTOF SCP or Pro 2, dia-PASEF.
  DIA-NN 1.8.1 with a refined human tonsil library, no match-between-runs,
  proteins inferred from genes.

## Rules

1. **Candidate.** Exactly one: the lymph node bundle "lymph_node v1". An
   amendment freezes its MANIFEST sha256 before unsealing. If it misses its
   development gates (`research/organ-references.md`, "Lymph node"), there is
   no candidate and the set stays sealed.
2. **Scores come from the service's own code,** with the lymph node bundle's
   own gene map. The fused best-guess probabilities are recomputed, and their
   argmax must equal the served best guess on every region.
3. **Inclusion.** The micro-regions of the tonsil-niche experiment, with their
   class read at unsealing from the run names, or from an annotation table in
   the archive.
   - The classes are matched by meaning: "dark", "light", "grey"/"gray",
     "GC" → germinal centre; "mantle" → mantle zone; "T" with "zone",
     "interfollicular" or "IF" → T zone; "epi" → epithelium.
   - Blanks, library and QC runs are excluded.
   - If any region's class is in doubt, the map is written by hand by these
     rules, with the reason, from the paper's figure.
4. **Groups.**

   | Region | Group |
   |---|---|
   | germinal centre (dark, grey, light) and mantle zone | B zone |
   | interfollicular T-cell zone | T zone |
   | squamous epithelium | outside the reference (secondary only) |

5. **Upload.** One upload: every included region together.
6. **Reader.** DIA-NN output by the service's own parser: the `pg_matrix`
   when the archive has one, otherwise the precursor report's protein groups
   rolled up as the service rolls up a DIA-NN report.
7. **Primary.**
   - S = P(B cell group) − P(T cell group), from the fused best-guess
     probabilities.
   - The measure is the AUROC of S, B-zone regions over T-zone regions.
   - **p-value:** a one-sided permutation p with 10,000 permutations, seed 0.
     There is one section, so permutations are not blocked.
   - **Pass if p < 0.05.**
   - Void with fewer than 3 regions on either side, or fewer than 20 B-zone
     and T-zone regions in all.
8. **Secondary,** reported and never deciding:
   - each region's argmax group, and the answers and abstention per zone;
   - germinal centre against mantle zone, as P(B cell group) and the best
     guesses;
   - the epithelium regions: AUROC of reference similarity, lymphoid regions
     over epithelium, and the share abstained;
   - the baselines, as for the other organs.
9. **Unsealing and format fixes** follow the colon protocol's rule 10
   (`research/benchmark/protocol-colon-pxd052341.md`). The scripts are
   `benchmark/ln_heldout_intake.py` and `benchmark/ln_heldout_score.py`,
   rehearsed before unsealing.

## Rehearsal, before unsealing

The intake and scorer run end to end on RNA pseudobulk "regions" of the
reference's test cells (B-rich, T-rich, and a non-reference decoy), written
in DIA-NN's layout. The record goes to
`research/benchmark/heldout/rehearsals/`.

## Outputs, at scoring only

`research/benchmark/heldout/pxd042367/` (`summary.json`, `scores.csv`).

## Amendments

**Amendment 1, 2026-10-19: the candidate is "lymph_node v2".** The v1 bundle
missed its development gates, so under rule 1 it is no candidate. The
organ's v2 (`scripts/organs/lymph_node_v2.json`; `research/organ-references.md`,
"Version 2"; `side-tests.md`, amendment 14) replaces it as the one
candidate. Its intake reads the v2 work folder (`CANDIDATE` in the intake
script). Its bundle's MANIFEST.json sha256 is added below at freeze, before
any unsealing, and only if the v2 gates pass. Nothing else in this
protocol changes.

**Amendment 2, 2026-10-20: where the baselines run.** Rule 8's two
baselines, correlation and PCA with kNN, run in `benchmark/organ_baselines.py`.

- **Inputs:** the candidate's reference cells over its own gene space,
  scaled with every class weighted equally, as in
  `benchmark/baselines_corrected.py`.
- **When:** after the intake and before the scorer. The intake now also
  saves the upload over the organ's genes (`query_organ.npz`).
- **Scoring:** each baseline is scored by this protocol's primary measure,
  and the scorer copies `baselines.json` into `summary.json`.
- **Guard:** the scorer refuses to score the real set before the baselines
  exist.
- **Rehearsal:** done on the rehearsal intake.

They remain secondary and never decide.

**Amendment 3, 2026-10-20: the PCA baseline's centre, and the setup
checks.** A code review found the PCA with kNN baseline weak on both
rehearsals: lymph node AUROC 0.597 against correlation's 1.0, with 27 of 40
regions called classical monocyte.

- **The cause:** the components are fitted on RNA cells sampled per class,
  and the projection subtracted that sample's own mean. Sampling per class
  leaves the mean off the reference's class-balanced centre, and the shift
  moved every query toward the small classes. The queries' neighbours were
  65% other queries.
- **What was ruled out:** fitting on RNA and queries stacked, with
  distance-weighted votes as in `benchmark/baselines_corrected.py`, gave
  the same 0.596. So the method's documented use was not the cause.
- **The fix:** both sides are projected around the class-balanced centre,
  which `class_balanced_z` puts at 0.
  - Lymph node rehearsal: 1.0.
  - Lung rehearsal: 100 (was 96.9).
- **The setup checks:** each `baselines.json` now records the space's
  held-out RNA kNN balanced accuracy against chance, and the queries' share
  of RNA neighbours.
- **Missing scores:** a sample without a correlation score (fewer than 3
  measured genes) is called "(none)". It counts as wrong for the lung and is
  left out of the lymph node's AUROC; the count is reported.

This was fixed on the rehearsals, before any real scoring. The baselines
stay secondary and never decide.
