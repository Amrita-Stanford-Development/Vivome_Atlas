# Value-scale diagnostics, B5: Stage 0 with the calibrated check

Run 2026-11-08 23:10 by research/notebooks/value_scale_diagnostics.py (275 s). Expectations: valuescale/bank/expectations/b5.json, written before the run. Baseline: the same code under the median method (alignment.scale_method), in the same run. Explained in notes.md beside this file.

## The rows

| row | result |
|---|---|
| B5_pbmc240 | PASS |
| B5_scope2 | PASS |
| B5_pxd064083 | PASS |
| B5_verdicts | FAIL |
| B5_frozen_keys | PASS |
| B5_rna | PASS |
| B5_invariants | PASS |
| B5_time | PASS |
| B5_refusals | PASS |
| B5_app | PASS |

The slowest check: furtwangler_log2_imputed, 0.537 s.

## Every traced table (30)

| table | label | cells | B4 verdict | verdict | median rule read | now read | a 0 read as | frozen keys | answers changed | answered median/check | RNA | invariants | check s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pbmc240_diann | linear | 238 | linear | linear | linear | linear | missing | equal | 0 | 174/174 | same | ok | 0.052 |
| kabatnik_cra_timstofultra | linear | 25 | linear | linear | linear | linear | missing | equal | 0 | 10/10 | same | ok | 0.018 |
| kabatnik_c3_region | linear | 27 | linear | linear | linear | linear | missing | equal | 0 | 13/13 | same | ok | 0.008 |
| pxd073250_diann | linear | 557 | linear | linear | linear | linear | missing | equal | 0 | 170/170 | same | ok | 0.174 |
| pxd077946_diann_genes | linear | 40 | linear | linear | linear | linear | missing | equal | 0 | 20/20 | same | ok | 0.01 |
| zamore_diann | linear | 30 | linear | linear | linear | linear | missing | equal | 0 | 26/26 | same | ok | 0.008 |
| pxd064083_t | linear | 78 | linear | linear | log | linear | missing | changed: best_guess_rule, cells, value_scale.detected, value_scale.transformed | 36 | 47/40 | same | ok | 0.017 |
| pxd064083_b | linear | 70 | linear | linear | log | linear | missing | changed: best_guess_rule, cells, value_scale.detected, value_scale.transformed | 27 | 20/26 | same | ok | 0.015 |
| dusszachniewicz_maxquant | linear | 45 | linear | linear | linear | linear | missing | equal | 0 | 20/20 | same | ok | 0.009 |
| herrera2025_fragpipe | linear | 91 | linear | linear | linear | linear | missing | equal | 0 | 38/38 | same | ok | 0.032 |
| lungmap_bpd_fragpipe | linear | 20 | linear | linear | linear | linear | missing | equal | 0 | 10/10 | same | ok | 0.017 |
| msv000099294_hmc3 | linear | 47 | linear | linear | log | linear | missing | changed: cells, value_scale.detected, value_scale.transformed | 10 | 16/15 | same | ok | 0.013 |
| msv000099294_microglia | linear | 57 | linear | linear | log | linear | missing | changed: cells, value_scale.detected, value_scale.transformed | 11 | 19/14 | same | ok | 0.01 |
| pxd061052_spectronaut | linear | 29 | linear | linear | linear | linear | missing | equal | 0 | 7/7 | same | ok | 0.008 |
| pxd043355_pd | linear | 59 | linear | linear | linear | linear | missing | equal | 0 | 26/26 | same | ok | 0.021 |
| fulcher_tmt | linear | 2000 | linear | linear | linear | linear | missing | equal | 0 | 1357/1357 | same | ok | 0.301 |
| scope2_export | log | 1490 | log | log | log | log | measured | equal | 0 | 789/789 | same | ok | 0.042 |
| khoury_column_normalized | log | 1651 | log | log | log | log | missing | equal | 0 | 1535/1535 | same | ok | 0.47 |
| furtwangler_batchcorr | linear | 2000 | linear | linear | log | linear | missing | changed: best_guess_rule, cells, value_scale.detected, value_scale.transformed | 1243 | 792/672 | same | ok | 0.453 |
| furtwangler_batchcorr_norm | linear | 2000 | linear | linear | log | linear | missing | changed: best_guess_rule, cells, value_scale.detected, value_scale.transformed | 1125 | 634/803 | same | ok | 0.399 |
| furtwangler_log2 | log | 2000 | log | log | log | log | missing | changed: best_guess_rule, cells | 1100 | 524/806 | same | ok | 0.435 |
| furtwangler_log2_imputed | log | 2000 | cant_tell | cant_tell | log | linear | missing | changed: best_guess_rule, cells, value_scale.detected, value_scale.transformed | 54 | 488/480 | same | ok | 0.537 |
| furtwangler_log2_nan | log | 2000 | log | log | log | log | missing | equal | 0 | 801/801 | same | ok | 0.371 |
| furtwangler_log2fc_nan | log | 2000 | log | log | log | log | measured | equal | 0 | 793/793 | same | ok | 0.054 |
| furtwangler_log2_raw_sn | log | 2000 | log | log | log | log | missing | changed: best_guess_rule, cells | 1302 | 946/975 | same | ok | 0.403 |
| pxd049412_a549_singlecells | linear | 50 | linear | linear | linear | linear | missing | equal | 0 | 5/5 | same | ok | 0.02 |
| brunner_mq_singlecells | linear | 51 | linear | linear | linear | linear | missing | equal | 0 | 3/3 | same | ok | 0.026 |
| krull_singlecells | linear | 143 | linear | linear | linear | linear | missing | equal | 0 | 48/48 | same | ok | 0.018 |
| hu2023_pd_k562 | linear | 72 | linear | linear | linear | linear | missing | equal | 0 | 4/4 | same | ok | 0.007 |
| cptac_ccrcc_tumor | log | 110 | log | log | log | log | measured | equal | 0 | 47/47 | same | ok | 0.009 |

## Refused

| table | by | error |
|---|---|---|
| pxd021882_maxquant | validation | fewer than 20 cells |
| pxd049412_hela250pg | validation | fewer than 20 cells |
| pxd069060_diann_report | validation | fewer than 20 cells |
| quantms_pxd004452_ibaq | validation | fewer than 20 cells |
| quantms_pxd004452_ribaq | validation | fewer than 20 cells |
| brunner_diann_1ng | validation | fewer than 20 cells |
| cong_mq_singlecells | validation | fewer than 20 cells |

## The golden fixtures' 50-cell slices

| slice | verdict | gate | read | transformed | a 0 read as | frozen keys |
|---|---|---|---|---|---|---|
| pbmc240_50 | linear |  | linear | True | missing | equal |
| scope2_50 | log | negatives | log | False | measured | equal |

## PXD064083 against D3 (reported, not judged)

**pxd064083_t**, 78 cells:

|  | levels | no answer, by reason | top labels |
|---|---|---|---|
| D3 (median rule, read log) | {'class': 8, 'lineage': 19, 'group': 20} | {'ambiguous_between_classes': 28, 'no_confident_label': 3} | {'T cell': 20, 'lymphoid': 18, 'erythrocyte': 5, 'neutrophil': 3, 'myeloid': 1} |
| B5 (the check, read linear) | {'lineage': 19, 'class': 2, 'group': 19} | {'ambiguous_between_classes': 34, 'outside_supported_region': 3, 'no_confident_label': 1} | {'T cell': 19, 'lymphoid': 15, 'myeloid': 4, 'erythrocyte': 2} |

**pxd064083_b**, 70 cells:

|  | levels | no answer, by reason | top labels |
|---|---|---|---|
| D3 (median rule, read log) | {'group': 3, 'lineage': 14, 'class': 3} | {'ambiguous_between_classes': 48, 'outside_supported_region': 2} | {'lymphoid': 8, 'myeloid': 6, 'monocyte/macrophage': 2, 'b cell': 2, 'neutrophil': 1} |
| B5 (the check, read linear) | {'lineage': 14, 'group': 6, 'class': 6} | {'ambiguous_between_classes': 44} | {'lymphoid': 13, 'T cell': 5, 'b cell': 5, 'myeloid': 1, 'monocyte/macrophage': 1} |

## B5_app, through the app: 8 of 8 pass

| check | status | result |
|---|---|---|
| GET /api/status lists auto, linear and log, and the zeros choices |  | PASS |
| pbmc240_diann (its file), nothing stated: 200, equal to pipeline.run_projection's reply, with verdict, zeros_read and evidence | 200 | PASS |
| scope2_export (its file), nothing stated: 200, equal to pipeline.run_projection's reply, with verdict, zeros_read and evidence | 200 | PASS |
| pxd064083_t (its file), nothing stated: 200, equal to pipeline.run_projection's reply, with verdict, zeros_read and evidence | 200 | PASS |
| furtwangler_log2 (its 2,000-cell subsample), nothing stated: 200, equal to pipeline.run_projection's reply, with verdict, zeros_read and evidence | 200 | PASS |
| pbmc240_diann with 2 values made negative, nothing stated: 400, naming them and the service's check, with UNDECIDED_NEGATIVES_REASON | 400 | PASS |
| the same, value_scale linear: 400 with the stated reading's reason | 400 | PASS |
| the same, value_scale log: 200 | 200 | PASS |

