// Shared fixtures for the manifest and panel test suites.

export const measured = (v, basis) => ({ value: v, status: 'measured', basis });
export const pending = (phase) => ({ value: null, status: 'pending', phase, note: 'n/a' });

// One manifest shaped like the real generated file. Both suites read from it;
// panels.test.js relies on the metric records, manifest.test.js on the key set.
//
// next_reference is null here, matching the real manifest. `model` is the
// current release (v4.2), previous_release is v4.1, earlier_release is v3,
// first_release is CrossModalNet, each with its own numbers.
export function manifestFixture() {
  return {
    schema_version: '1.0',
    atlas_version: '0.5.0',
    generated: '2026-10-16',
    model: {
      name: 'VivOME v4.2', latent_dim: 128, training_regime: 'supervised',
      seeds: measured(5, "v3.1's ensemble members: V2 seeds 0 to 4 (T1 NB1b), probabilities averaged"),
      notes: "v4.1's answers, with protein class means for protein uploads.",
      feature_space_size: 9002, previous_feature_space_size: 2903,
      detected_by_source: { scope2: 2907, fulcher: 1654 },
      encoder_family: 'module pooling', mask_sampling: null,
      evaluation: {
        suite: {
          title: "Simulated uploads of held-out RNA cells (v4.1's pre-registered evaluation; v4.2 answers RNA uploads exactly as v4.1)",
          rows: [{ key: 'correct_when_committed', measure: 'Correct when committed, at the stated level',
                   value: measured(0.9628, "v4.1's pre-registered evaluation, the suite's fourth use") }],
        },
        served: [{ dataset: 'Fulcher 2026', correct_label: 'correct when committed, at the stated level',
                   committed: measured(0.8729, 'served settings, development data'),
                   correct: measured(0.9829, 'served settings, development data') }],
        recall: [
          { dataset: 'Khoury 2026', type: 'CD8T', value: pending('post-hoc') },
          { dataset: 'Fulcher 2026', type: 'CD8T', value: measured(0.237569, 'best guess as served') },
          { dataset: 'Fulcher 2026', type: 'DC', value: pending('later') },
        ],
      },
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
        latent_centroid_cosine: measured(0.080971, '128-d latent centroid cosine (V2 seed 4), 394 protein cells'),
        modality_probe_accuracy: measured(0.989933, 'global metric, not per-class'),
        transfer_accuracy: pending('N/A') },
    ],
    summary: { total: 3, cross_modal: 2, rna_only: 1, prot_only: 0 },
    next_reference: null,
    previous_release: {
      model_name: 'VivOME v4.1', atlas_version: '0.4.0',
      seeds: measured(5, "v3.1's ensemble members: V2 seeds 0 to 4 (T1 NB1b), probabilities averaged"),
      feature_space_size: 9002, previous_feature_space_size: 2903,
      detected_by_source: { scope2: 2907, fulcher: 1654 },
      encoder_family: 'module pooling', mask_sampling: null,
      evaluation: {
        suite: {
          title: "Simulated uploads of held-out RNA cells (v4.1's pre-registered evaluation)",
          rows: [{ key: 'correct_when_committed', measure: 'Correct when committed, at the stated level',
                   value: measured(0.9628, "v4.1's pre-registered evaluation, the suite's fourth use") }],
        },
        served: [{ dataset: 'Fulcher 2026', correct_label: 'correct when committed, at the stated level',
                   committed: measured(0.8698, 'served settings, development data'),
                   correct: measured(0.9792, 'served settings, development data') }],
        recall: [
          { dataset: 'Khoury 2026', type: 'CD8T', value: measured(0.027, 'best guess, post-hoc') },
          { dataset: 'Fulcher 2026', type: 'DC', value: measured(0.222222, 'best guess as served, in-sample') },
        ],
      },
      note: "v3.1's answers with a fused best guess; v4.2 keeps it and adds protein class means.",
    },
    earlier_release: {
      model_name: 'VivOME v3 reference', atlas_version: '0.2.0',
      seeds: measured(5, 'balanced accuracy 0.7143, 95% CI [0.6851, 0.7435]'),
      feature_space_size: 9002, previous_feature_space_size: 2903,
      detected_by_source: { scope2: 2907, fulcher: 1654 },
      encoder_family: 'module pooling', mask_sampling: 'uniform',
      latent_centroid_cosine: {
        macrophage: measured(0.189762, 'v3 128-d latent centroid cosine, 394 protein cells'),
        monocyte: measured(0.830313, 'v3 128-d latent centroid cosine, 1096 protein cells'),
      },
      modality_probe_accuracy: measured(0.989933, 'global metric, not per-class'),
      note: 'The single-encoder release before v3.1, still selectable.',
    },
    first_release: {
      model_name: 'CrossModalNet', n_shared_genes: 2903,
      zero_shot_auc_raw: measured(0.6416827225906852, 'jointly trained, had seen SCoPE2'),
      zero_shot_auc_smoothed: measured(0.6679295268442699, 'jointly trained, had seen SCoPE2, query-time smoothing'),
      shipped_properties: ['ribosome', 'antigen_presentation', 'oxphos', 'glycolysis'],
      note: 'Jointly trained and had implicitly seen SCoPE2; kept as the documented prior baseline.',
    },
    benchmark: benchmarkFixture(),
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

// The benchmark as scripts/build_manifest.py writes it: one table per dataset,
// ours first, each other run with its spread and the current model minus it.
export function benchmarkFixture() {
  const versus = (difference, counts) => ({ pairings: counts.reduce((a, b) => a + b, 0),
    favour_current: counts[0], neither: counts[1], favour_other: counts[2], difference });
  return {
    status: 'measured', current: 'VivOME v4.2', note: 'Every method gets the same reference.',
    datasets: [
      { key: 'khoury2026', name: 'Khoury 2026', measure: 'Balanced accuracy over 5 types',
        chance: measured(0.2, 'one of 5 types at random'), role: 'Held out <b>from</b> development.',
        rows: [
          { method: 'VivOME v4.2 (ours)', rule: 'best guess, as served', ours: true, runs: 1,
            score: pending('post-hoc'), vs_current: null },
          { method: 'VivOME v4.1 (ours)', rule: 'best guess, as served', ours: true, runs: 1,
            score: measured(0.6251, 'post-hoc'), vs_current: null },
          { method: 'PCA, no correction', rule: 'shared kNN', ours: false, runs: 1,
            score: measured(0.628, 'corrected baselines'),
            vs_current: versus({ ...measured(-0.003298, 'paired'), ci_low: -0.021, ci_high: 0.014 }, [0, 1, 0]) },
          { method: '<script>x</script>', rule: 'shared kNN', ours: false, runs: 3,
            score: { ...measured(0.569, 'corrected baselines'), sd: 0.017, min: 0.554, max: 0.587 },
            vs_current: versus({ ...measured(0.0565, 'paired'), min: 0.038, max: 0.072 }, [3, 0, 0]) },
          { method: 'Not yet run', rule: 'its own', ours: false, runs: 1, score: pending('later'), vs_current: null },
        ] },
      { key: 'scope2', name: 'SCoPE2, published matrix', measure: 'Balanced accuracy, restricted',
        chance: measured(0.5, 'one of 2 types at random'), role: 'Development data.',
        rows: [
          { method: 'VivOME v4.2 (ours)', rule: 'best guess, as served', ours: true, runs: 1,
            score: measured(0.379726, 'development data'), vs_current: null },
        ] },
    ],
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
