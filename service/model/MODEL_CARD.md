# VivOME v3 reference — model card

## The claim, precisely

The reference encoder (`ModulePoolingEncoder`, `reference_model.pt`) is
**trained, supervised, on RNA only** — 85,233 cells across 22 immune/blood
cell classes (`reference_metadata.csv`). It is applied **zero-shot to
proteomics uploads**: no protein labels and no paired RNA-protein cells were
used at any point in training or in choosing the architecture. Every number
below cites the committed file that measured it —
`docs/plans/VivOME_TODO.md` §5 ("Current verified numbers") is the running
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
| RNA→RNA, SCoPE2 mask, **test cells only** | 93.2% acc / 65.7% bal (OT); 67.3% bal (nearest-centroid) | `docs/plans/nb1/rna_to_rna_membership_corrected.csv` |
| RNA→RNA, full coverage, **test cells only** | 94.6% acc / 80.0% bal (OT) | `docs/plans/nb1/rna_to_rna_membership_corrected.csv` |
| Protein (SCoPE2, 1,490 real cells), **restricted** to the two supported classes | 86.2% acc / 79.8% bal | `service/model/v3_tables/support_restricted_assignment.csv` |
| Protein (SCoPE2), **unrestricted** across all 22 classes | 45.4% acc / 31.1% bal | `service/model/v3_tables/support_restricted_assignment.csv` — see the variance caveat below |
| Modality probe (RNA vs. protein separability in latent space) | 98.99% ± 0.28% | `docs/plans/VivOME_TODO.md` §5 |

**A previously published RNA→RNA figure of 95.5% / 74.8% (SCoPE2 mask) is
superseded by the 93.2% / 65.7% figures above.** The published number
included cells the model had trained on in its own test split — an invalid
measurement. The corrected numbers here score test cells only.

**The restricted 79.8% balanced accuracy is exact for SCoPE2 by
construction, not a generalizable result.** SCoPE2's protein cells are only
ever macrophage or monocyte, so restricting Stage 4's candidate space to
exactly those two classes (`config.CROSS_MODAL_SUPPORTED_CLASSES`) is, on
this one dataset, restricting to the true label set — the number reflects
that match, not a property of the model that holds on other data. On any
upload containing other cell types (e.g. PBMC240, which has T and NK
cells), the same hardcoded restriction is actively wrong: see failure mode
1 below.

**SCoPE2 unrestricted results vary strongly across retrains.** A faithful
retrain of the same recipe scored 9.1% balanced accuracy unrestricted,
against the 31.1% shipped in the table above — the unrestricted number is
not a stable property of this architecture at this sample size. Seed
variance for this measurement is not yet quantified (pending T1 NB1c);
until it lands, treat the 31.1% figure as one draw, not a target.

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
   roughly 65% of their own cells to training (`docs/plans/VivOME_TODO.md`
   §4) — not a subset of donors, all of them. Published RNA→RNA numbers
   reflect this; a true held-out-donor evaluation does not yet exist.
   Planned for v4 (T2 NB8).

## Versioning

- Model artifact provenance: `service/model/provenance.json` (`created`,
  `gene_list_hash`, training config).
- Gene identifier mapping table: `service/model/gene_id_map_v1.tsv`, built
  from a one-time HGNC bulk download — provenance, source sha256, and the
  derived table's own sha256 in `service/model/gene_id_map_v1_provenance.json`.
- Site-facing atlas version: `ATLAS_VERSION` in `service/config.py` /
  `tools/build_manifest.py`.
