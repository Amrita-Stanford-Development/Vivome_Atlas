// Shared fixtures for the manifest and panel test suites.

export const measured = (v, basis) => ({ value: v, status: 'measured', basis });
export const pending = (phase) => ({ value: null, status: 'pending', phase, note: 'n/a' });

// One manifest shaped like the real generated file. Both suites read from it;
// panels.test.js relies on the metric records, manifest.test.js on the key set.
//
// next_reference is null here, matching the real manifest — the v3
// architecture change this field described is complete, folded into
// `model` instead (feature_space_size etc. below). previous_release is
// untouched by that migration and still describes CrossModalNet — a good
// canary that a fixture edit hasn't overreached into that block.
export function manifestFixture() {
  return {
    schema_version: '1.0',
    atlas_version: '0.2.0',
    generated: '2026-09-23',
    model: {
      name: 'VivOME v3 reference', latent_dim: 128, training_regime: 'supervised',
      seeds: measured(5, 'balanced accuracy 0.7143, 95% CI [0.6851, 0.7435]'),
      notes: 'A frozen, RNA-only reference encoder. PCA projection of the latent space.',
      feature_space_size: 9002, previous_feature_space_size: 2903,
      detected_by_source: { scope2: 2907, fulcher: 1654 },
      encoder_family: 'module pooling', mask_sampling: 'uniform',
    },
    modalities: {
      rna: { label: 'RNA', cells: 85233, classes: 22, source: 'scRNA-seq' },
      prot: { label: 'Protein', cells: 1490, classes: 2, source: 'SCoPE2 mass spectrometry' },
    },
    cell_types: [
      { class_idx: 16, name: '<script>alert(1)</script>', rna_cells: 32198, prot_cells: 0,
        support: 'rna_only',
        pca_centroid_cosine: pending('Phase 2'),
        latent_centroid_cosine: pending('N/A'),
        modality_probe_accuracy: pending('N/A'),
        transfer_accuracy: pending('N/A') },
      { class_idx: 12, name: 'monocyte', rna_cells: 9602, prot_cells: 1096,
        support: 'cross_modal',
        pca_centroid_cosine: measured(0.820639, '3-PC projection'),
        latent_centroid_cosine: measured(0.830313, '128-d latent centroid cosine, 1096 protein cells'),
        modality_probe_accuracy: measured(0.989933, 'global metric, not per-class'),
        transfer_accuracy: pending('N/A') },
      { class_idx: 10, name: 'macrophage', rna_cells: 1228, prot_cells: 394,
        support: 'cross_modal',
        pca_centroid_cosine: measured(0.563158, '3-PC projection'),
        latent_centroid_cosine: measured(0.189762, '128-d latent centroid cosine, 394 protein cells'),
        modality_probe_accuracy: measured(0.989933, 'global metric, not per-class'),
        transfer_accuracy: pending('N/A') },
    ],
    summary: { total: 3, cross_modal: 2, rna_only: 1, prot_only: 0 },
    next_reference: null,
    previous_release: {
      model_name: 'CrossModalNet', n_shared_genes: 2903,
      zero_shot_auc_raw: measured(0.6416827225906852, 'jointly trained, had seen SCoPE2'),
      zero_shot_auc_smoothed: measured(0.6679295268442699, 'jointly trained, had seen SCoPE2, query-time smoothing'),
      shipped_properties: ['ribosome', 'antigen_presentation', 'oxphos', 'glycolysis'],
      note: 'Jointly trained and had implicitly seen SCoPE2; kept as the documented prior baseline.',
    },
    benchmark: {
      status: 'pending', phase: 'Phase 4', note: 'Not run yet.',
      methods: ['CrossModalNet (ours)', 'GLUE'], rows: [],
    },
    data_availability: {
      rna_expression: {
        status: 'lfs_not_fetched',
        note: 'Git LFS object (~1.43 GB) is not present in this checkout.',
        remedy: 'git lfs install && git lfs pull',
      },
      prot_expression: { status: 'available', note: 'web/data/atlas_PROT_lat128.csv' },
    },
  };
}

// A hypothetical non-null next_reference, matching the pre-v3 manifest
// shape — used only by the tests guarding buildNextReferenceCard's
// rendering path now that the default fixture's own next_reference is null.
export function nextReferenceFixture() {
  return {
    feature_space_size: 9002, previous_feature_space_size: 2903,
    detected_by_source: { scope2: 2907, fulcher: 1654 },
    encoder_family: 'module pooling', mask_sampling: 'uniform', trained: false,
    note: 'Architecture settled by a five-seed masking comparison; the reference is not trained yet.',
  };
}
