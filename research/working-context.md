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

## Where things stand (2026-10-02)

- **Release.** Atlas 0.3.0; model v3.1.
  - Tag `atlas-v0.3.0` is at `eae50af`, which is `main`.
  - v3's release is archived as tag `atlas-v0.2.0` (`bf315f7`).
- **Branches.** `integration/v31` is the working branch. It is ahead of
  `main` by the post-release commits:
  - the docs corrections;
  - Khoury amendment 2;
  - the Track D extension and Khoury amendments 3 and 4;
  - the move to the Windows PC.
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
- **Runs:** Harmony, Seurat CCA and v3.1 on the Mac; MaxFuse, scGLUE (GPU)
  and the correlation baseline on the PC. Seurat CCA is deterministic (its
  three seeds are identical). scGLUE diverged on all three Fulcher seeds,
  reported, not rerun.
- **Headline:**
  - Fulcher: v3.1 57.9% balanced, ahead in all 16 pairings; correlation
    baseline 46.9%.
  - PBMC240 lymphoid recall: v3.1 92.3%, correlation 59.8%, integration
    tools 38.8% or below.
  - SCoPE2 restricted: v3.1 61.3%, level with the correlation baseline,
    below scANVI.
  - SCoPE2 unrestricted: every mean under 10%.

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

1. **The Khoury final-evaluation scripts: done** (amendment 5).
   `khoury2026_embed.py`, `scanvi_run_khoury2026.py` and
   `khoury2026_score.py` were rehearsed on Fulcher. They reproduce
   Fulcher's committed per-type recalls across 34 runs.
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
   - **Owner decision pending** on how to proceed.
3. **Unseal Khoury once,** in amendment 5's order. If v3.1 changes after
   NB3b, an amendment fixes the new candidate first.
4. Post the bioRxiv preprint, and choose the journal from the Khoury result.

## Owner decisions and standing instructions

**Science:**

- **Khoury 2026 stays sealed.**
  - Never read or score its labels; the loader refuses without
    `unseal=True`.
  - Nothing embeds it before the final v3.1 evaluation, which scores it
    once.
  - Changes to its protocol are amendments made before unsealing.
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
  Research. Genome Biology is a stretch, only if v3.1 is clearly ahead on
  Khoury. Nature Methods is not realistic on current results.
- **Sequence:**
  1. finish Track D (done, 2026-10-02);
  2. unseal Khoury once;
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

- **scGLUE on Fulcher:** why it diverges is not investigated. A CPU run or
  other settings are untested, and either would need a Khoury amendment
  before unsealing.
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
