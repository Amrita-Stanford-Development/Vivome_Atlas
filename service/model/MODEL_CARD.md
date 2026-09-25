# VivOME v3 reference — model card

## The claim, precisely

The reference encoder (`ModulePoolingEncoder`, `reference_model.pt`) is
**trained, supervised, on RNA only** — 85,233 cells across 22 immune/blood
cell classes (`reference_metadata.csv`). It is applied **zero-shot to
proteomics uploads**: no protein labels and no paired RNA-protein cells were
used at any point in training or in choosing the architecture. Every number
below is either measured directly or cites the file that measured it —
`docs/plans/VivOME_TODO.md` §5 ("Current verified numbers") is the running
source of truth this card draws from.

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
| RNA→RNA, SCoPE2 mask, **test cells only** | 93.2% acc / 65.7% bal (OT); 67.3% bal (nearest-centroid) | Corrected; see note below |
| RNA→RNA, full coverage, **test cells only** | 94.6% acc / 80.0% bal (OT) | Corrected; see note below |
| Protein (SCoPE2, 1,490 real cells), **restricted** to the two supported classes | 86.2% acc / 79.8% bal | What the live service delivers today |
| Protein (SCoPE2), **unrestricted** across all 22 classes | 45.4% acc / 31.1% bal | Shows the restricted number's cost — see failure mode 1 |
| Modality probe (RNA vs. protein separability in latent space) | 98.99% ± 0.28% | Lower is better; still high |

**A previously published RNA→RNA figure of 95.5% / 74.8% (SCoPE2 mask) is
superseded by the 93.2% / 65.7% figures above.** The published number
included cells the model had trained on in its own test split — an invalid
measurement. The corrected numbers here score test cells only.

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
4. **No donor-level holdout in training.** Every donor identified so far
   (TSP14, TSP21, TSP25) contributed roughly 65% of its own cells to
   training (`docs/plans/VivOME_TODO.md` §4). Published RNA→RNA numbers
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
