# VivOME v3 reference — model card

## The claim, precisely

The reference encoder (`ModulePoolingEncoder`, `reference_model.pt`) is
**trained, supervised, on RNA only** — 85,233 cells across 22 immune/blood
cell classes (`reference_metadata.csv`). It is applied **zero-shot to
proteomics uploads**: no protein labels and no paired RNA-protein cells were
used at any point in training or in choosing the architecture. Every number
below cites the committed file that measured it —
`research/todo.md` §5 ("Current verified numbers") is the running
index of those files, not a source in its own right.

## Architecture

- Module-pooling encoder: a fixed gene→module assignment (`A`, row-normalised),
  concatenated masked values + mask + module-level value + module-level mask
  fraction, two LayerNorm/GELU/Dropout blocks, a linear projection to a
  128-dim latent space, L2-normalised. See `service/pipeline/encoder.py`.
- 9,002-gene feature space (`feature_space_provenance.json`): the union of
  six proteomics datasets' detected genes, replacing an earlier 2,903-gene
  space entirely.
- Winning config from a 5-seed architecture comparison (`decisive_summary.json`):
  "H module, uniform" (module-pooling encoder, uniform mask sampling,
  consistency loss on). Mean balanced accuracy 71.43%, 95% CI
  [68.51%, 74.35%] across the 5 seeds (`provenance.json:reference_seed_mean_bal_acc`).
- Served via TorchScript (`encoder.trace_encoder`), not the eager module —
  proven numerically identical to <1e-5 max absolute difference on 1,000
  cells (`service/tests/test_encoder.py`).

## Performance

| Measure | Value | Source |
|---|---|---|
| RNA→RNA, SCoPE2 mask, **test cells only** | 93.2% acc / 65.7% bal (OT); 67.3% bal (nearest-centroid) | `research/notebook-outputs/nb1/rna_to_rna_membership_corrected.csv` |
| RNA→RNA, full coverage, **test cells only** | 94.6% acc / 80.0% bal (OT) | `research/notebook-outputs/nb1/rna_to_rna_membership_corrected.csv` |
| Protein (SCoPE2, 1,490 real cells), **restricted** to the two supported classes, **shipped checkpoint (`v3_seed0`)** | 86.2% acc / 79.8% bal | `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` |
| Protein (SCoPE2), **restricted, 5-seed mean of the shipped architecture** | 75.3% ± 11.8 acc / 71.5% ± 10.6 bal (range 59.0–88.4 bal) | `research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` |
| Protein (SCoPE2), **unrestricted** across all 22 classes, **shipped checkpoint (`v3_seed0`)** | 55.4% acc / 38.7% bal | `research/notebook-outputs/nb1d/ours_scope2_5seed_scores.csv` |
| Protein (SCoPE2), **unrestricted, 5-seed mean of the shipped architecture** | 38.4% ± 25.7 acc / 29.1% ± 18.3 bal (range 1.3–49.8 bal) | `research/notebook-outputs/nb1d/ours_scope2_5seed_family_summary.csv` |
| Modality probe (RNA vs. protein separability in latent space) | 98.99% ± 0.28% | `research/todo.md` §5 |

**A previously published RNA→RNA figure of 95.5% / 74.8% (SCoPE2 mask) is
superseded by the 93.2% / 65.7% figures above.** The published number
included cells the model had trained on in its own test split — an invalid
measurement. The corrected numbers here score test cells only.

**The restricted 79.8% balanced accuracy is `v3_seed0`'s own number, is
exact for SCoPE2 by construction, and is not a generalizable result — on
two separate counts.** First: SCoPE2's protein cells are only ever
macrophage or monocyte, so restricting Stage 4's candidate space to exactly
those two classes (`config.CROSS_MODAL_SUPPORTED_CLASSES`) is, on this one
dataset, restricting to the true label set — the number reflects that
match, not a property of the model that holds on other data. On any upload
containing other cell types (e.g. PBMC240, which has T and NK cells), the
same hardcoded restriction is actively wrong: see failure mode 1 below.
Second: `v3_seed0` — the checkpoint actually shipped — is the
best-performing of five independently trained seeds of the same
architecture by a wide margin (79.8% vs. a 5-seed mean of 71.5% ± 10.6,
range 59.0–88.4). Neither caveat was known when this figure was first
published; both are measured directly in the table above, not inferred.

**Against scArches/scANVI (a real, supervised, label-consuming cross-modal
integration baseline — the strongest available comparison), the shipped
checkpoint's SCoPE2-restricted lead is real but does not generalize either.**
`v3_seed0` beats every scANVI seed under every protocol tested (paired
bootstrap, all 9 checks CI-excludes-zero in `v3_seed0`'s favor). Averaged
across all 5 v3 seeds, though, the architecture's shared-kNN-rule
restricted mean (71.5% bal) *trails* scANVI's 3-seed mean (77.15%) — only
3 of 15 seed-pairings favor "ours" there, 12 favor scANVI. The one regime
the architecture reliably wins is unrestricted (12 of 15 pairings, mean
margin +18.1 points). Full breakdown:
`research/notebook-outputs/nb1d/paired_bootstrap_ours_vs_scanvi.csv`, narrative in
`research/benchmark/results.md`. **The takeaway for anyone reading only this
card: "beats the strongest available baseline" is true of the specific
checkpoint running in production, not a property of the architecture that
would necessarily hold if it were retrained.**

**A methodological asymmetry in scANVI's favor, throughout the comparison
above: scANVI trains on the query cells (transductive); this encoder is
fixed and zero-shot on the query.**

## Known failure modes

1. **Hardcoded two-class label space.**
   `config.CROSS_MODAL_SUPPORTED_CLASSES = ("macrophage", "monocyte")`. A
   protein upload of any non-myeloid cell type (T cell, NK cell, B cell,
   etc.) can only ever be assigned "macrophage", "monocyte", or abstain —
   never its true label — no matter how well-separated its embedding is.
   Confirmed on real PBMC240 data: the same embeddings that score 0%
   lymphoid recall restricted score 46.6% lymphoid recall unrestricted. This
   is a **correctness** limitation, not only an accuracy one. Tracked until
   label-space estimation (T1 NB2) lands.
2. **Macrophage placement.** Even within the two supported classes,
   cross-modal alignment is weak for macrophage: latent centroid cosine is
   0.19 for macrophage vs. 0.830 for monocyte, and protein-side macrophage
   recall is 0.76%. The macrophage-vs-monocyte ranking is directionally
   correct (AUC 0.928) but the absolute placement is not — most macrophage
   protein cells are misassigned to monocyte or a distractor class.
3. **2 of 22 reference classes have any protein-side validation.**
   Macrophage and monocyte are the only classes ever checked against real
   protein ground truth. The other 20 classes' embeddings have not been
   validated against protein data at all.
4. **No donor-level holdout in training.** All nine donors contributed
   roughly 65% of their own cells to training (`research/todo.md`
   §4) — not a subset of donors, all of them. Published RNA→RNA numbers
   reflect this; a true held-out-donor evaluation does not yet exist.
   Planned for v4 (T2 NB8).
5. **High seed-to-seed variance on real cross-modal transfer, not yet
   explained.** Retraining the identical architecture with a different seed
   moves SCoPE2 restricted balanced accuracy by up to 29 points (59.0% to
   88.4% across 5 seeds) — `v3_seed0`, the shipped checkpoint, happens to be
   the best of the five, not a principled choice among them. The RNA-only
   validation task this architecture was selected on shows far less
   seed-to-seed spread (95% CI [68.5%, 74.4%] — `provenance.json`), so
   whatever drives this instability is specific to the RNA→protein transfer
   step, not the RNA-side training. A separate development-only check
   (PBMC240 raw, real ~75%-missing data, lineage-level labels — see
   `research/notebook-outputs/nb1d/`) is scored by recall per lineage, not plain accuracy —
   accuracy is uninformative at this sample's 117-lymphoid-vs-5-myeloid
   split, and a per-class recall is only meaningful read against its
   counterpart, not against an overall accuracy figure: a trivial model
   that calls every cell "lymphoid" scores 100% lymphoid recall and 0%
   myeloid recall. The shipped architecture's 5-seed mean **lymphoid
   recall** (52.8% ± 7.7%, n=117) paired with its **myeloid recall**
   (100.0%, n=5, anecdotal) shows real separation between lineages, not a
   one-class collapse; a second candidate architecture ("V2") reaches
   92.8% ± 0.8% lymphoid recall (80.0% myeloid, n=5, anecdotal) — a large,
   low-variance margin over the shipped architecture on real messy data
   specifically. (With only 5 myeloid cells, myeloid recall for every
   architecture is anecdotal — one misclassified cell moves it 20
   points — reported alongside lymphoid recall only to show overall
   behavior, never to rank on its own.) V2 is not shipped and does not
   carry that margin onto SCoPE2 (see `research/benchmark/results.md`); this is
   recorded as an open question, not a recommendation to switch.

## Versioning

- Model artifact provenance: `service/model/runtime/provenance.json` (`created`,
  `gene_list_hash`, training config).
- Gene identifier mapping table: `service/model/runtime/gene_id_map_v1.tsv`, built
  from a one-time HGNC bulk download — provenance, source sha256, and the
  derived table's own sha256 in `service/model/runtime/gene_id_map_v1_provenance.json`.
- Site-facing atlas version: `ATLAS_VERSION` in `service/config.py` /
  `scripts/build_manifest.py`.
