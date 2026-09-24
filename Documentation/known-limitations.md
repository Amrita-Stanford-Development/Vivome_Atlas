# Known limitations

Open, unresolved issues. Read this before trusting any single number out of
[results.md](results.md) in isolation.

## The `atlas_PROT_lat128.csv` provenance problem

`tools/fair_benchmark/ours_run.py` needs a protein input file to reconstruct
"ours" through the shared harness. The only candidate found in this
repository, or anywhere on the development machine, is
`Atlas/atlas_PROT_lat128.csv`.

`git log` on that file shows it was added in this repository's **very
first commit** (`307e483`, 2025-08-17) — it **predates the entire v3
model**. Its `gene_*` columns are restricted to exactly the ~2,907-gene
RNA/protein intersection used for the atlas viewer's "click a point, see
its gene profile" feature, almost certainly a legacy artifact of the
*original* (pre-v2, pre-v3) atlas viewer, not the protein assay's true
native gene panel.

The export notebook that produced the shipped 45.37%/31.08% (unrestricted)
and 86.17%/79.79% (restricted) figures instead reads
`blood_joint_cells_by_proteins_GENELEVEL.tsv` — the protein assay's own
full native panel, almost certainly containing far more than 2,907 genes —
and uses *that* full panel to build Stage 2's fuzzy-smoothing kNN graph.
Feeding the smoothing step a narrower "own full feature set" than the
notebook used produces a structurally different graph, and therefore a
different downstream embedding, even with completely correct code.

**That raw TSV file does not exist anywhere on this machine or in this
repository's history.** Confirmed by exhaustive search: the whole
filesystem, `.Trash`, and `git log --all --diff-filter=A` across every
branch (in case it was ever committed and later removed — it wasn't). It
only ever lived on the original project's Google Drive, referenced by path
in `service/docs/download-checklist.md`'s Tier 4 (optional demo data) and
never fetched into this repository.

A second, independently useful artifact — `prot_embedding_scope2.npy`, the
export notebook's *own* saved protein embeddings, which would have let
`ours_run.py` skip reconstruction entirely and score the real thing
directly — existed earlier in this project's history at
`service/model/v3_pending/app_export/prot_embedding_scope2.npy`, but that
directory was deleted (with the repository owner's explicit approval,
following this repo's "list before delete" working agreement) before ever
being committed to git. It, too, is unrecoverable from this machine.

**What this means concretely:** `ours_run.py`'s *restricted* number
(83.89%/74.50%, or 85.50%/83.32% under the native nearest-centroid rule) is
close to the historical figure and reasonably trustworthy. Its
*unrestricted* number is the one most affected by this gap — treat it as a
lower-fidelity reconstruction, not a faithful replay of the methodology
that produced 45.37%/31.08%. The historical figures are reported
separately, explicitly labeled, in the same table — see
[results.md](results.md) — specifically so the two are never confused for
each other.

**Not fixable from this machine.** Resolving this fully requires either
locating and fetching the original raw TSV from wherever the project's
Google Drive now lives, or permanently accepting the reconstruction's
disclosed limitation. There is no code fix available here.

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
