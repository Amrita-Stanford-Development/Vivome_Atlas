# Working context

This page is for a new Claude Code session, or a new collaborator, picking up
the work. It covers how the project got here, the owner's decisions and
standing instructions that live outside the code, where the work stands,
and what comes next. It condenses the Claude Code sessions up to
2026-10-01, when the work moved from a Mac to a Windows PC
([setup](../docs/setup-windows.md)).

More detail lives in:

- the changelog in [todo.md](todo.md);
- [notebook-run-history.md](notebook-run-history.md);
- `git log`.

Before changing anything, read [CLAUDE.md](../CLAUDE.md). Before a roadmap
task, read [todo.md](todo.md) and [roadmap.md](roadmap.md), whose latest
revision is at the top.

## Where things stand (2026-10-26)

The sections further down ("Where things stand (2026-10-05)", "Next",
"Open after Track D") describe early October and are kept as history.
This section is the current state. The changelog in [todo.md](todo.md) and
the run history have the detail.

- **Release:**
  - atlas 0.6.0 (tag `atlas-v0.6.0`), serving model v4.1
    (`service/config.py`, `PIPELINE_VERSION`);
  - earlier releases: 0.5.0 (v4.2), 0.4.0 (v4.1's first), 0.3.0 (v3.1),
    0.2.0 (v3).
  - **Label stability** between them is measured (run history entry 60).
    Since v3.1, no release has contradicted the one before.
- **Branch:** `integration/v4` is the working branch.
- **Hosting:**
  - the site is on Cloudflare Pages (`vivome-atlas.pages.dev`);
  - the service is on Google Cloud Run (`docs/web/hosting.md`,
    `deploy/huggingface/PUBLISH.md`).
- **Deployed 2026-10-26:** Cloud Run revision `vivome-atlas-00007-flw`
  (the same model; restricted mode answers 400), and the site with
  everything below, the gene profiles as shards (a click fetches one
  shard) and the beta's sign-in (`docs/web/hosting.md`, "The beta
  sign-in": an invited email and one password; invited: the owner).
  `check_space.py`: 0 of 238 cells differ.
- **Deployed 2026-10-21** (Cloud Run revision `vivome-atlas-00006-rkt`,
  then the site; `research/todo.md`, the deploy item):
  - the service reads DIA-NN 1.8, Spectronaut, MaxQuant and FragPipe LFQ
    tables. Upload faults found by review are fixed, and the parse runs
    inside the projection slot;
  - 2,000 cells take about 10 s instead of 32 s, with identical answers;
  - model files are read as tensors only; the upload limit is 31 MiB;
  - the site has security headers, the film's captions and accessibility
    fixes.

  `check_space.py` against the live service: 0 of 238 cells differ.
- **Other organs (Track I):**
  - the colon, lung and lymph node references were built from Tabula
    Sapiens RNA alone;
  - v1 missed its gates for all three, and v2 (lymph node, lung) missed by
    one gate each. No colon v2 was built;
  - the lymph node v3 (v2's members with v1's calibration rule) missed by
    0.01 points: narrow B cells are read as T cells, an encoder weakness
    that calibration cannot fix (run history entry 62);
  - the three locked tests stay sealed;
  - a further version is the owner's decision, and needs an encoder or
    reference change and fresh protein development sets;
  - everything is in [organ-references.md](organ-references.md). The
    organ maps are on the Atlas page, map only.
- **Blood:** v4.1 unchanged. The pooled candidate v5.3 (five members
  trained with RNA pools) missed 4 of its 5 pre-registered development
  gates and is refused by the service (run history entry 63).
- **Restricted mode is retired** (owner, 2026-10-21): the service answers
  400 to `restrict_to_supported_classes`.
- **SCoPE2 is off the Atlas map** (owner, 2026-10-21): the map is the RNA
  reference alone; SCoPE2 is a Manuscript result, labelled development
  data, not an external test.
- **Live since 2026-10-26:** the SCoPE2 and restricted-mode changes, and
  the visible accessibility changes (contrast, the Workflow story for
  screen readers, the map by keyboard, a Pause motion switch, the Atlas
  page at high zoom), for the owner to look at.
- **Blood candidate v5.5** (v5.4 recalibrated with held-out Allen donors,
  2026-10-26): NO GO on the answers committed (42.52, bar 86.57); the
  members are unsure of the Allen cells under protein-like coverage, so
  honest calibration widened the sets (run history entry 67).
- **Open, for the owner:** an organ v4, a blood candidate that changes the
  members or the answer rule, and the DOI. The Google Cloud free trial
  ends about 2027-01-14: "Activate full account" before then.

## The project

VivOME Atlas is a versioned joint latent atlas of single-cell RNA and
protein. It has three parts:

- a static site, in `web/`;
- a projection service, in `service/`, which places an uploaded
  mass-spectrometry proteomics matrix into the RNA reference;
- a benchmark, in `benchmark/`, that compares the model with established
  integration methods under one fair protocol.

The service answers with conformal label sets and abstains with a reason
when it can't answer. The goal is the resource claim of
[implementation-plan.md](implementation-plan.md), and a commercial product.

The model is trained on RNA only and applied to protein zero-shot. Colab
notebooks do the training and evaluation (Tier 1: T1 NB1 to NB5; Tier 2:
NB6 to NB8). Claude Code tracks (A2 to F) carry the results into the code.

## Machines

- **Until 2026-10-01:**
  - a 16 GB Mac ran the Claude Code sessions and the Track D Harmony and
    Seurat runs;
  - Colab ran the notebooks.
- **From 2026-10-01:** a Windows PC with an NVIDIA RTX 4000 Ada. Files that
  git doesn't carry came over in two zips on the project Drive
  ([setup, step 3](../docs/setup-windows.md#3-the-files-git-does-not-carry)).
  Setup is done: the `vivome` conda env with CUDA, the five v3.1 checkpoints
  restored, `GATE PASSED`, all three test suites passing. Floats frozen on
  the Mac differ here by up to 2.1e-6 (float32 summation order); the tests
  allow for that, and labels match exactly.

## How we got here

| When | What | Key commits |
|---|---|---|
| 2025-08 | The original static atlas site | `307e483` |
| 2026-08-28 to 09-10 | **Resource layer:** manifest pipeline, the projection, benchmark and versions pages, the docs set ([plan](archive/2026-08-29-resource-layer-plan.md)). Phase 5 projection service backend | `5c591dd`, `20381f9` |
| 2026-09-24 | **Fair benchmark:** rebuilt under nine rules. **Encoder fix:** ReLU replaced by the trained model's GELU. Ours rescored on the real embedding. scANVI with 3 seeds | `056f136`, `f15cbd1`, `ed5c927` |
| 2026-09-25 | **Track A2:** log transform, smoothing graph on z-scored values, coverage floor of 200 observed genes. **Track B:** gene ID resolution, FAISS search, DIA-NN uploads | `2334e48`, `cf3b98e` |
| 2026-09-29 | **Track D rescore over 5 seeds (T1 NB1d).** "Ours beats scANVI" held only for the shipped seed, `v3_seed0`, not the architecture. PBMC240 became a development dataset | `62aefe8` |
| 2026-09-30 | **Repository reorganised** into the current layout. **Track E:** Fulcher 2026 held-out evaluation, where V2 beats v3 in 50 of 50 seed pairings. Fulcher then became a development dataset. Khoury 2026 registered as the sealed final test. V2 chosen as the v3.1 encoder. **Web redesign** foundation | `629d2cf`, `6d67d32`, `1f486f0` |
| 2026-10-01 | **v3.1:**<br>• Track C scaffold, `167f138`;<br>• the Project page projecting through a local service;<br>• Track F: T1 NB2's five-seed V2 ensemble becomes the default pipeline, `9567ffd`;<br>• a deep review, whose follow-up fixed duplicate gene rows, `af07dac`;<br>• **release 0.3.0**, `a5b31dc`.<br>**After the release:**<br>• docs update;<br>• Khoury amendment 2, `491053b`;<br>• Track D extension started, `7963031`;<br>• Windows-safe clone, `c698188` | see each bullet |
| 2026-10-01 to 02 | **The Windows PC takes over:** Mac-isms replaced, tests fitted to the PC's float differences, R/Seurat and harmonypy installed. **Track D extension finished:** four baselines plus a correlation baseline against v3.1 as served; Khoury amendments 3 and 4 | `d9a3cfe`, `65bfc10`, and the results commit |
| 2026-10-02 to 03 | **Before unsealing:** the Khoury final-evaluation scripts, rehearsed on Fulcher (amendment 5); T1 NB3b and NB3c, both NO GO; two code reviews (amendments 6 and 7). The second found that every Seurat run had seen scrambled inputs, and that scGLUE's cluster balancing divides by zero on Fulcher: Seurat rerun with the fix, scGLUE rerun with balancing off, every table rescored. The public site on Cloudflare Pages | `73cac67`, `379c53c`, `a52570e`, `4d217f1`, `35532a5`, `c516d98` |
| 2026-10-04 | **Baseline corrections** run (`d8522cd`). **Track G (v4.0):** pre-test, bundle, fusion pipeline and gate; Phase 3 calibration NO GO. **SCoPE2's labels found swapped** on every cell (`research/benchmark/bugs-and-fixes.md`, 8), corrected in every copy and every SCoPE2 table rescored: v3 restricted 79.8 → 20.2, v3.1 61.3 → 38.7, scANVI 77.7 → 22.3. Every local copy, the Drive source included, now carries the curated labels | `d8522cd`, `578fe99` |
| 2026-10-05 | **Track G, Phase 3b: NO GO** (run-history entry 23). v3.1's answers with v4's fused best guess. Fixed: the set width (committed 86.0% against v3.1's 86.7%). Best guess 64.7 against 59.6. Failed: coverage 87.6% (v3.1 88.3%) and single-type uploads 5.4 points below v3.1. Both come from single-type uploads. **Phase 3c: GO** (entry 24): the guess joined beside v3.1's, and the correlation term gated by upload agreement. Best guess 64.7 against 59.3, every scenario at or above v3.1, coverage 89.2% against 89.0%. Spec frozen; v4 servable on request, v3.1 still the default | `578fe99` |
| 2026-10-06 to 07 | **v4 Phase 4** (run-history entry 25): v4 against the corrected baselines. Fulcher 65.0 and Khoury (post-hoc) 61.8 are level with the best simple baselines (Harmony NC 63.0; PCA kNN 62.8), ahead of the rest. **v4.1** (the owner asked to beat them, not match them): Phase A chose the encoder weight 0.5 where the correlation term is used, on Fulcher under fixed rules (Fulcher 69.05, in-sample); Phase B checked it once on Khoury: carries over (62.5, +0.7 over v4, still level with PCA kNN); Phase D added `"v4.1"` to the service, refused until its evaluation passes. Stacking Harmony or PCA under the model does not help (research arm). The reprocessed SCoPE2's baselines run in the owner's terminal | `77718f7` |
| 2026-10-07 | **v4.1 Phase C: GO** (run-history entry 26): the pre-registered evaluation passes all eight checks (fresh simulated suite, a safety check: v4.1 65.0, v4 65.4, v3.1 60.6). Spec frozen; v4.1 serves on request, v3.1 stays the default. The reprocessed SCoPE2's baselines scored (`f3d9a76`): every method at or below chance, Harmony's published-matrix edge gone | `3d701e7` |
| 2026-10-09 | **v4.1 Phase E:** against every corrected baseline. On Fulcher (in-sample) v4.1 is ahead of all of them, every CI excluding zero (Harmony NC +6.0, correlation +6.9); identical to v4 elsewhere. **The sealed-test search:** two searches and the owner's Gemini deep research found no public PBMC proteomics set with independent labels; data requests drafted (O'Connor/Pirrotte, TGen; Krisp, Bruker) | `94d0385` |
| 2026-10-03 | **Khoury 2026 unsealed and scored once,** the final v3.1 evaluation. As run, v3.1 is ahead of every comparator in all 77 paired bootstraps, but a review then found the comparators handicapped by our setup (item 4 under Next) (best guess 56.9% balanced over five types; scGLUE 42.8, v3 40.9, scANVI's best arm 36.1). Its weakness is CD8T (2.7% recall) and NK (29.0%). **Web:** the living water behind every page; the landing redesigned around a 3D hero | `74942f2`, `0a8de8f`, `c84ee02`, `578fe99` |

## Where things stand (2026-10-05)

- **Release.** Atlas 0.3.0; model v3.1.
  - Tag `atlas-v0.3.0` is at `eae50af`, which is `main`.
  - v3's release is archived as tag `atlas-v0.2.0` (`bf315f7`).
- **Branches.** `integration/v4` is the working branch, made from
  `integration/v31` on 2026-10-05. `integration/v31` is ahead of `main` by
  the post-release commits:
  - the docs corrections;
  - Khoury amendment 2;
  - the Track D extension and Khoury amendments 3 and 4;
  - the move to the Windows PC;
  - Khoury amendments 5 and 6, T1 NB3b and NB3c, and the Pages site.

  Then amendment 7 (`c516d98`), the living water (`0a8de8f`), the
  go-ahead to unseal (`74942f2`) and the baseline corrections (`d8522cd`).
  `integration/v4` adds the landing redesign (`c84ee02`), then the Khoury
  results, the corrected baselines' results, the SCoPE2 label correction
  and Track G to Phase 3c (`578fe99`).
- **Public site.** Redeployed from `578fe99` on 2026-10-05
  (`docs/web/hosting.md`): the redesigned landing and the corrected SCoPE2
  labels.
- **v3.1** (`service/pipeline/ensemble.py`):
  - five V2 encoders, each a tempered softmax over cosine to the class
    centroids, averaged;
  - per-class (Mondrian) conformal sets;
  - out of distribution when the members' mean best cosine is below 0.779;
  - answers at class, group or lineage level;
  - a `best_guess` and a `reference_similarity` beside every answer;
  - coordinates from member seed 4.
- **Service flags.** Two are on by default, and neither has been evaluated
  on RNA yet:
  - `set_includes_best_guess` adds the best guess to non-empty sets only, so
    an empty set still abstains;
  - `restricted_renormalise`.
- **Checkpoints.** The five members live outside git.
  `scripts/fetch_v31_members.py` restores them from `data/incoming/NB1b/ckpt/`
  and checks their sha256.

## Done: the Track D extension (2026-10-02)

The owner's brief of 2026-10-01 (gene fairness for every tool; MaxFuse,
scGLUE, Harmony + kNN and Seurat CCA on SCoPE2, PBMC240 and Fulcher, seeds
0-2 where stochastic; Fulcher rows labelled; v3.1 as served on its best
guess; paired bootstrap; a Khoury amendment before unsealing) is done, plus
a fifth, deliberately simple baseline the owner added: correlation to the
RNA class mean.

- **Write-up:** `research/benchmark/results.md`, "Baselines beyond scANVI";
  tables in `research/benchmark/baselines/`; model card and TODO updated.
- **Khoury:** amendment 3 (`65bfc10`) fixes the scripts, settings, rules
  scored, the PC environment and the PC-vs-Mac reproduction check;
  amendment 4 adds the divergence rule. Still sealed.
- **Runs:** Harmony and v3.1 on the Mac; MaxFuse, Seurat CCA, scGLUE (GPU)
  and the correlation baseline on the PC.
  - Seurat CCA was rerun on 2026-10-02 after its inputs were found
    scrambled (amendment 7); every earlier Seurat number is void. It is
    deterministic: its three seeds are identical.
  - scGLUE was rerun on 2026-10-03 with its cluster balancing off (the
    owner's decision, amendment 7). All nine runs completed.
- **Headline** (rescored 2026-10-03):
  - Fulcher: v3.1 57.9% balanced, ahead in all 22 pairings; correlation
    baseline 46.9%; scGLUE 24.2% at best; Seurat 18.9%.
  - PBMC240 lymphoid recall: v3.1 92.3%, correlation 59.8%, integration
    tools 38.8% or below.
  - SCoPE2 restricted (labels corrected 2026-10-04, `bugs-and-fixes.md`, 8):
    v3.1 38.7%, below every new tool (40.4 to 50.6), all at or below chance.
  - SCoPE2 unrestricted: every mean under 5%.

**The scripts:**

- `benchmark/baselines_inputs.py`: what every tool receives.
- `benchmark/baselines_run.py`: one tool, one dataset, one seed (`--out` for
  check runs; each JSON records its environment).
- `benchmark/seurat_cca_transfer.R`: Seurat's half.
- `benchmark/baselines_queue.sh`: sequential runs that resume where they
  stopped.
- `benchmark/baselines_v31.py`: v3.1 through the service's own parser.
- `benchmark/baselines_score.py`: the tables in
  `research/benchmark/baselines/`.

Predictions and embeddings are cached in
`benchmark/results/baselines_ext/<dataset>/`; `pc_check/` holds the
reproduction runs.

## Next

Following the publication plan below:

1. **The Khoury final-evaluation scripts: done** (amendment 5), reviewed
   twice (amendments 6 and 7). `khoury2026_embed.py`,
   `scanvi_run_khoury2026.py` and `khoury2026_score.py` were rehearsed
   again on Fulcher on 2026-10-03 with amendment 7's checks: they
   reproduce Fulcher's per-type recalls across 37 runs.
   - Amendment 7, its fixes, reruns and rescored tables: committed in
     `c516d98` (2026-10-03).
2. **T1 NB3b: run 2026-10-02, NO GO** (`research/notebook-run-history.md`
   entry 18).
   - **What it found:** energy separates out-of-distribution cells far
     better than today's max cosine. But no score's threshold holds:
     - calibration on validation cells under-covers test cells about 2x;
     - per-upload gene z makes the score depend on upload composition
       (single-type uploads abstain 34%).
   - **The owner chose a follow-up, NB3c (entry 19): also NO GO.**
     - **What it fixed:** calibrating on never-seen test cells puts false
       abstention near target.
     - **What remains:** separation is the binding limit, since no score
       reaches 90% scrambled rejection at about 5% false abstention.
       Narrow uploads still abstain more, and the upload-diversity measure
       cannot see them.
   - **The owner's decision (2026-10-03):** go to the final evaluation with
     v3.1 as released. v3.1 did not change after NB3b or NB3c, so no
     amendment for a new candidate is needed.
3. **Khoury unsealed and scored once: done, 2026-10-03,** in amendment 5's
   order, on the PC. Write-up: `research/benchmark/results.md`, "Khoury
   2026: the sealed final evaluation"; tables in
   `research/benchmark/khoury2026/`.
   - All 20 training runs completed. MaxFuse seed 0 failed once ("SVD did
     not converge") and its one rerun under amendment 7 completed.
   - v3.1's best guess 56.9% balanced over five types; as run, every one
     of the 77 paired bootstraps excludes zero in its favour (or v3's,
     against scANVI). See item 4: the comparators were handicapped. Committed answers: 93.8% of cells, 96.7% correct at the
     stated level.
   - Its weakness: CD8T recall 2.7% (94% called CD4T), NK 29.0%.
   - The scorer's one allowed rerun reproduced all seven tables byte for
     byte.
4. **Baseline review (2026-10-03, owner's request): the comparators were
   handicapped by our setup.** Scoring is correct. But the RNA reference is
   z-scored over whole blood while queries are z-scored over PBMCs;
   MaxFuse ran without its SVD settings (no class signal); scANVI's Normal
   mean cannot go negative yet was fitted to z-scores; Harmony is worse than
   plain PCA here; Seurat rescales its inputs. **Owner's decision:** fix
   from each tool's documentation, nothing tuned; rerun SCoPE2, PBMC240 and
   Fulcher; then rerun Khoury as a labelled post-hoc analysis beside the
   sealed result; everything in one queue. Plan and results:
   `research/benchmark/baseline-corrections.md`.
   - **Done, 2026-10-04:** fixes committed first (`d8522cd`), then 60
     runs (59 completed; scANVI Fulcher seed 2 failed twice identically).
   - **Outcome: v3.1's best guess is level with the best simple baselines,
     not ahead.** Khoury (post-hoc): PCA + kNN 62.8, scANVI 61.5, v3.1 56.9
     (members 60.0), Harmony 56.9. Fulcher: Harmony 60.8–63.0 and the
     correlation baseline 62.1 ahead of v3.1's 57.9. v3.1 stays ahead of
     MaxFuse, scGLUE and Seurat CCA. Its distinct value is its committed
     answers (93.8% committed, 96.7% correct at the stated level on Khoury).
5. **Owner decisions after the reruns:** whether the result supports "state
   of the art" or "beats scANVI" in the site's copy, and what goes in the
   landing's "Evidence" section.
6. Post the bioRxiv preprint, and choose the journal from the Khoury result.

## Owner decisions and standing instructions

**Science:**

- **Khoury 2026 has been scored, once (2026-10-03).**
  - Its result is final. Nothing about it is rescored after a change, and
    its protocol is not amended after unsealing.
  - The loader still refuses without `unseal=True`. Any further use of
    Khoury, for example as development data, is the owner's decision.
- **Don't tune anything to make a gate or a comparison pass.**
- **Development datasets.** Fulcher 2026 and PBMC240 are development
  datasets. Fulcher's first scoring stays the held-out result.
- **"Ours" is v3.1 as served:** release 0.3.0, both flags on.
- **Pending is a feature.** Never fill a gap with a plausible number. Every
  displayed number comes from the manifest (CLAUDE.md).

**Working:**

- **Heavy jobs run one at a time.** Three parallel lanes on the 16 GB Mac
  caused a memory spike that killed a Seurat run.
- **Long runs go in the owner's own terminal window.** Claude Code
  background tasks stop after 2 hours or when the session ends.
- **Deleting.** List what you'd delete and get approval first.
- **Before committing:** run all three suites, and keep
  `docs/file-index.md` current.
- **Summaries the owner asks for "for online Claude"** go in the chat as
  plain text, not as an artifact.
- **Don't commit `.impeccable/`**, the design tool's cache.
- **Commercial direction.** Keep the standard layout and conventional,
  self-explanatory names.

**The website:**

- The design language on every page is the original animated background
  (`web/js/background.js`) and the white card with the blue halo. Don't
  propose replacing them.
- Never claim "every ome": the atlas covers RNA and protein only.
- Copy rules are in [docs/web/design.md](../docs/web/design.md). Words such
  as "calibrated", "beats scANVI", "state of the art" and "deployed" wait
  for the evidence.

## Publication plan (discussed 2026-10-01)

- **Target.** Molecular & Cellular Proteomics or the Journal of Proteome
  Research. Genome Biology was a stretch, only if v3.1 is clearly ahead on
  Khoury; with fair baselines it is not (2026-10-04). Nature Methods is not
  realistic on current results.
- **Sequence:**
  1. finish Track D (done, 2026-10-02);
  2. unseal Khoury once (done, 2026-10-03);
  3. post a bioRxiv preprint;
  4. choose the journal from the Khoury result.
- **Framing.** Label transfer with honest abstention, not a shared latent
  space. v3.1's own evidence shows the modalities sit further apart in its
  space even though labels transfer better.
- **Weaknesses worth fixing first:**
  1. T1 NB3b: a better out-of-distribution score on the encoder's hidden
     features, plus the flag evaluation on RNA;
  2. reprocess SCoPE2 from its raw files, since the published matrix is
     centred per protein and per cell;
  3. request a dataset with independent labels, such as sorted PBMCs.
- **Paperwork.** Every dataset needs a public accession. PBMC240's
  provenance needs checking.

## Open after Track D

- **scGLUE's balancing:** it divides by zero when no RNA and query cluster
  pair reaches its 0.5 similarity cutoff, as on Fulcher, so every run now
  has it off (amendment 7). How much it changes scGLUE's scores where it
  can run is not measured.
- **T1 NB3 / NB3b:**
  - recalibrated abstention: the OOD filter passes 99% of scrambled cells,
    and B cell coverage is 69%;
  - both service flags evaluated on RNA;
  - restricted mode evaluated under v3.1, or retired.
- **Release protocol:**
  - label stability from 0.2.0 to 0.3.0 needs a definition first;
  - a DOI needs the owner's archive account.
- **Not started:**
  - the rest of Track E: registry, download scripts, leakage guard,
    further MS datasets;
  - Tier 2, NB6 to NB8.

## Lessons from the sessions

- **Duplicate gene rows.** These must collapse by a per-cell median after
  log2. When the last row won, PBMC240 lost 1,338 observed values; that bug
  was the whole gap between the service and NB2.
- **Seurat 5.** `SetAssayData` takes `layer=`; `slot=` is defunct.
- **Empty strings in pandas.** Read v3.1's prediction files with
  `keep_default_na=False`, or an empty `label_level` becomes NaN.
- **Exit status in shell scripts.** Capture `$?` straight after the command,
  before any `$(date)`.
- **Table rounding.** Round from cell counts, never from percentages that
  were already rounded.
