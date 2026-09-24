# Known limitations

Open, unresolved issues. Read this before trusting any single number out of
[results.md](results.md) in isolation.

## The `atlas_PROT_lat128.csv` provenance problem — RESOLVED

**Status: resolved.** The real files were re-fetched from the project's
Google Drive and committed to this repository at `service/model/app_export/`
(sha256-verified against `BUNDLE_MANIFEST.json`). This section keeps the
original history for context; see [results.md](results.md) for the current
numbers, which no longer depend on any reconstruction.

**What the problem was:** `tools/fair_benchmark/ours_run.py` originally
needed a protein input file to reconstruct "ours" through the shared
harness, and the only candidate found in this repository, or anywhere on
the development machine, was `Atlas/atlas_PROT_lat128.csv`.

`git log` on that file shows it was added in this repository's **very
first commit** (`307e483`, 2025-08-17) — it **predates the entire v3
model**. Its `gene_*` columns are restricted to exactly the ~2,907-gene
RNA/protein intersection used for the atlas viewer's "click a point, see
its gene profile" feature, a legacy artifact of the *original* (pre-v2,
pre-v3) atlas viewer, not the protein assay's true native gene panel.

The export notebook that produced the shipped 45.37%/31.08% (unrestricted)
and 86.17%/79.79% (restricted) figures instead reads
`blood_joint_cells_by_proteins_GENELEVEL.tsv` — the protein assay's own
full native panel (2,935 genes, confirmed once obtained) — and uses *that*
full panel to build Stage 2's fuzzy-smoothing kNN graph. At the time, this
raw TSV, and a second independently useful artifact
(`prot_embedding_scope2.npy`, the notebook's own saved protein embeddings,
which had briefly existed at `service/model/v3_pending/app_export/` before
that directory was deleted without ever being committed to git), were both
confirmed absent from this machine by exhaustive search.

**What actually happened once the real files arrived:** re-running "ours"
directly against `prot_embedding_scope2.npy` (no reconstruction at all —
see `tools/fair_benchmark/ours_run.py`) confirmed the file-panel theory was
*part* of the story but not the dominant one. The real, bigger cause,
found via the end-to-end pipeline check this real data finally made
possible, was a second, separate, and more serious bug:
`service/pipeline/encoder.py` used the wrong activation function (ReLU
instead of the notebook's GELU) — see
[bugs-and-fixes.md](bugs-and-fixes.md#0-servicepipelineencoderpy-used-the-wrong-activation-function--relu-instead-of-gelu-fixed-in-the-real-repo)
for the full story. With both bugs fixed, the complete production pipeline
(alignment → smoothing → encoder) run on the real raw TSV reproduces the
notebook's saved embedding at **cosine similarity 1.000000 for every one
of the 1,490 cells.**

**The broader lesson, worth keeping even though the specific problem is
fixed:** an artifact that exists only as an uncommitted local file is one
`rm -rf` away from requiring a fresh multi-week investigation to
approximately reconstruct. `service/model/app_export/README.md` documents
why these specific files are now committed (with the raw TSV under Git
LFS) for exactly this reason.

## scANVI's run-to-run variance

Two runs of the exact same scANVI architecture and training budget (200
pretrain epochs + 100 fine-tune epochs, early stopping, full 85,232-cell
RNA reference) produced meaningfully different point estimates — not
because anything crashed or diverged, but because the first run had no
fixed random seed. See [bugs-and-fixes.md](bugs-and-fixes.md#6-scanvi-no-fixed-seed-meant-the-first-runs-numbers-werent-reproducible)
for the mechanism, and [results.md](results.md) for both runs' full
numbers.

**What this means concretely:** treat any single scANVI measurement in this
comparison as one draw from a distribution with real spread, not a fixed
ground truth. A more rigorous future version of this benchmark should run
scANVI (and arguably every stochastically-trained method — MaxFuse's random
batching, scGLUE's minibatch shuffling) multiple times with different seeds
and report a mean ± spread, the same way `model.seeds` already does for the
production reference elsewhere in this project
(`service/model/v3_tables/reference_seeds.csv`, five seeds, mean balanced
accuracy 0.7143). This has **not** been done yet for any baseline in this
comparison — every number in [results.md](results.md) beyond "ours" and
scANVI-v2 is a single run.

## The rule-2 subsampling fallback was never needed, and so was never built

Methodology rule 2 requires: attempt the full 85,232-cell RNA reference for
every method; if compute genuinely forces a subsample for one method, apply
the *identical* subsample to *every* arm (including "ours") and disclose it.

In practice, once MaxFuse's `cca_components` numerical issue was fixed
(see [bugs-and-fixes.md](bugs-and-fixes.md)), every method completed at
full scale within a real but tractable training budget on a 16&nbsp;GB,
CPU-only machine. **The subsampling fallback branch of rule 2 was never
triggered, and so its actual implementation — coordinating one shared
subsample size and index set across every script — does not exist yet.**
If a future method (or a future, larger RNA reference) genuinely cannot run
at full scale, that coordination needs to be built from scratch; nothing
here provides it.

## RNA cell count: 85,232 vs. 85,233

The Atlas CSVs baselines train on (`Atlas/atlas_RNA_lat128-001-part{1,2}.csv`)
are missing one cell (`orig_index=42616`, a neutrophil) that
`service/model/reference_embedding.npy` has — see
[bugs-and-fixes.md](bugs-and-fixes.md#7-atlasatlas_rna_lat128-001-part12csv-are-missing-one-cell-between-them).
"Ours" is aligned down to the baselines' 85,232-cell set rather than the
baselines being retrained on the corrected 85,233. The Atlas CSVs
themselves still have this one-row gap; if they're ever regenerated (e.g.
from `tools/promote_v3_atlas.py`, or however the LFS split was originally
produced), it should be fixed at the source rather than patched around
again in every future benchmarking script.

## No held-out validation of the shared kNN rule's `k=30`

`k=30` for the shared kNN-classifier rule was chosen as "large relative to
the rarest RNA class" (which has one cell) and deliberately not tuned per
method — but it was also not tuned via any held-out validation at all. It
is a single, fixed, reasonable-looking choice, not a value selected to
maximize or equalize any particular method's score. This is intentional
(a rule tuned per method would defeat the point of a *shared* rule), but it
does mean the absolute numbers under this rule are somewhat arbitrary in a
way that comparisons *between* methods under the same rule are not.

## Every result here is pre-decision, not pre-registered

This entire comparison was built, debugged, and iterated on by looking at
its own intermediate results (e.g. MaxFuse's `cca_components` was lowered
*because* the original value crashed; scANVI's seeding was added *because*
the first run's numbers looked unstable on inspection). This is normal and
appropriate for building a measurement tool, but it means the final numbers
in [results.md](results.md) are the result of a debugging process that had
visibility into intermediate outcomes, not numbers from a pre-registered,
frozen protocol run once and reported unconditionally. No method's core
algorithm or the shared evaluation rule (`evaluate.py`) was changed *because
of* a disliked result — only genuine crashes (SVD non-convergence, NaN
encoder outputs) were fixed — but this distinction is worth stating
explicitly rather than leaving implicit.
