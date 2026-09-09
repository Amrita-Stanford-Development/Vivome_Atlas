// Shared fixtures for the manifest and panel test suites.

export const measured = (v, basis) => ({ value: v, status: 'measured', basis });
export const pending = (phase) => ({ value: null, status: 'pending', phase, note: 'n/a' });

// One manifest shaped like the real generated file. Both suites read from it;
// panels.test.js relies on the metric records, manifest.test.js on the key set.
export function manifestFixture() {
  return {
    schema_version: '1.0',
    atlas_version: '0.1.0',
    generated: '2026-08-29',
    model: {
      name: 'CrossModalNet', latent_dim: 128, training_regime: 'supervised',
      seeds: pending('Phase 1'), notes: 'PCA projection of the latent space.',
    },
    modalities: {
      rna: { label: 'RNA', cells: 85233, classes: 22, source: 'scRNA-seq' },
      prot: { label: 'Protein', cells: 1490, classes: 2, source: 'SCoPE2 mass spectrometry' },
    },
    cell_types: [
      { class_idx: 16, name: '<script>alert(1)</script>', rna_cells: 32198, prot_cells: 0,
        support: 'rna_only',
        pca_centroid_cosine: pending('Phase 2'),
        latent_centroid_cosine: pending('Phase 1'),
        modality_probe_accuracy: pending('Phase 4'),
        transfer_accuracy: pending('Phase 1') },
      { class_idx: 12, name: 'monocyte', rna_cells: 9602, prot_cells: 1096,
        support: 'cross_modal',
        pca_centroid_cosine: measured(0.998634, '3-PC projection'),
        latent_centroid_cosine: pending('Phase 1'),
        modality_probe_accuracy: pending('Phase 4'),
        transfer_accuracy: pending('Phase 1') },
      { class_idx: 10, name: 'macrophage', rna_cells: 1228, prot_cells: 394,
        support: 'cross_modal',
        pca_centroid_cosine: measured(0.997242, '3-PC projection'),
        latent_centroid_cosine: pending('Phase 1'),
        modality_probe_accuracy: pending('Phase 4'),
        transfer_accuracy: pending('Phase 1') },
    ],
    summary: { total: 3, cross_modal: 2, rna_only: 1, prot_only: 0 },
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
      prot_expression: { status: 'available', note: 'Atlas/atlas_PROT_lat128.csv' },
    },
  };
}
