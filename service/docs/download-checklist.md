# What to Download, and From Where

Everything below comes from Google Drive under `Vivome - Live Atlas/Data/Results/`.
Updated now that the encoder architecture decision has actually run. The
production reference has still not been trained, that is the one thing left.

---

## Download now

### From `FeatureSpace/`

| File | What it is |
|---|---|
| `feature_space_genes.csv` | The fixed 9,002 gene input space. Replaces the 2,903 gene list and `shared_genes_lat128.txt` entirely. |
| `feature_space_detail.csv` | Per gene, which of the six proteomics sources detected it. Useful for the model card and for explaining coverage numbers. |
| `provenance.json` | The union math behind the 9,002 figure. |

### From `MaskingDecisiveTest/`

| File | What it is |
|---|---|
| `decisive_summary.json` | **New.** The architecture question is settled. Module pooling encoder, uniform mask sampler, consistency loss on, 501 modules at target size 18, on the 9,002 gene space. This is the config the production reference will be trained with. |
| `ckpt/H_seed0.pt` through `H_seed4.pt` | The five checkpoints from the winning arm in the decisive test. **These are not the production model.** They were trained to answer one narrow question, which architecture generalises best under masking, using a simplified recipe, cross entropy plus a contrastive term plus consistency. They do not include the class imbalance correction, the hubness penalty, or the sink penalty that the full training recipe uses, and they were never combined with query time smoothing. Treat them as a development placeholder only, useful for wiring up and testing the backend pipeline end to end before the real model exists, and label them clearly as such anywhere they appear. |
| `tables/rna_sweep.csv`, `tables/scope2_projection.csv` | The paired comparison numbers behind the architecture decision, useful for the model card's methodology section. |

### From `ReferenceProjection_v2/export/`

| File | What it is |
|---|---|
| `reference_metadata.csv` | Cell id, class index, class name, lineage for all 85,233 RNA cells. Labels do not depend on encoder architecture, this stays valid. |
| `shared_genes.csv` | The old 2,903 gene list. Audit trail only, do not use as input anywhere. |
| `provenance.json` | The old CrossModalNet run's numbers, the documented "before" baseline the current model card describes. |

### From `PBMC240/`

| File | What it is |
|---|---|
| `tables/pbmc240_cell_metadata.csv` | Weak, marker derived labels for three lineages. Demo upload material, not ground truth. |
| `provenance.json` | Real coverage against the space, 34.8 percent. |

---

## Still waiting on

**The production reference model.** `decisive_summary.json` fixes the
architecture, it does not produce a trained model. Someone still has to run
the full training recipe, logit adjustment for class imbalance, supervised
contrastive loss, hubness penalty, sink penalty, five seeds, using the module
pooling encoder from the decisive test, on the 9,002 gene space, with query
time fuzzy smoothing wired into the pipeline it will actually be evaluated
in. Until that finishes, none of the following exist:

| File | Blocked on |
|---|---|
| `reference_model.pt` | Full v3 training run |
| `reference_embedding.npy` | Same |
| `reference_centroids.npy` | Same |
| `provenance.json` (v3's own) | Same |

`transfer_accuracy` and `model.seeds` in the manifest are correctly pending
until this exists. The architecture being decided does not mean the model is
trained.
