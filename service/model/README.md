# Reference artifacts

The production contract (fixed, from the implementation task this service
was built against):

```
reference_model.pt        state dict, keys prefixed "encoder." and "classifier."
reference_embedding.npy   float32, shape (n_rna_cells, 128), L2 normalised
reference_centroids.npy   float32, shape (22, 128), L2 normalised
reference_metadata.csv    class_idx here is authoritative — centroids and
                           any classifier head must match its ordering
feature_space_genes.csv   row order here is authoritative — every input
                           array to the encoder must match it
provenance.json           config, seed, gene list hash, headline numbers
```

Mask convention, both training and inference: **1.0 = observed, 0.0 =
missing.**

## What's here today

| File | Status |
|---|---|
| `feature_space_genes.csv` | **Real, authoritative.** The fixed 9,002-gene input space. Replaces the old 2,903-gene list entirely. |
| `feature_space_detail.csv` | **Real.** Per gene, which of the six proteomics sources detected it. |
| `feature_space_provenance.json` | **Real.** The union math behind the 9,002 figure. |
| `reference_metadata.csv` | **Real, authoritative.** Cell id, class index, class name, lineage for all 85,233 RNA cells. Labels don't depend on encoder architecture — this stays valid across the architecture change. |
| `decisive_summary.json` | **Real.** The architecture decision: module pooling encoder, uniform mask sampler, consistency loss on, over the 9,002-gene space. This is the config the production reference will be trained with — `pipeline/encoder.py` reads it rather than hardcoding a family. |
| `masking_test_tables/rna_sweep.csv`, `masking_test_tables/scope2_projection.csv` | **Real.** The paired comparison numbers behind the architecture decision. |
| `dev/H_seed4.pt` | **Real, but a development placeholder** — see `dev/README.md`. |
| `legacy_v2/` | **Real, historical.** The old CrossModalNet run's audit trail and provenance — see `legacy_v2/README.md`. |

## What's still pending

Blocked on the full v3 training run — logit adjustment for class imbalance,
supervised contrastive loss, hubness penalty, sink penalty, five seeds,
module pooling encoder, on the 9,002-gene space, with query-time fuzzy
smoothing wired into the pipeline it will actually be evaluated in:

| File | Blocked on |
|---|---|
| `reference_model.pt` | Full v3 training run |
| `reference_embedding.npy` | Same |
| `reference_centroids.npy` | Same |
| `provenance.json` (this directory's own, the real contract file) | Same |
| `reference_properties.csv` (Stage 8 continuous properties, per RNA cell) | Not part of the six-file contract above and not produced by any pipeline in this repo — needs the RNA reference's full transcriptome, which is not itself in this repo. Compute once RNA data access exists, name the shipped subset in `config.SHIPPED_PROPERTIES`. |

`pipeline/reference.py`'s loaders raise `PendingArtifactError` naming which
of these is missing, rather than a bare `FileNotFoundError` — the same
"pending, not fabricated" principle as `Atlas/atlas_manifest.json`, applied
at request time.

`transfer_accuracy` and `model.seeds` in the atlas manifest are correctly
pending until the above exists. The architecture being decided does not
mean the model is trained.
