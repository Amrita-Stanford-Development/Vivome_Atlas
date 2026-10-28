# Value-scale diagnostics, Phase A: the stated reading

Run 2026-10-28 11:58 by research/notebooks/value_scale_diagnostics.py. Expectations: valuescale/bank/expectations/phaseA.json, written before the change. Baseline: baseline.json beside this file, the replies before the change.

## A1 to A3, every bank table: 32 of 37 pass

A1: the automatic reply is the baseline's, byte for byte, and its summary is D3's. A2: a stated reading is applied and said; stating the rule's own reading changes nothing else; a linear reading of negative values is refused. A3: the stage invariants hold under each reading.

| table | label | rule reads | answered auto/linear/log | answers changed, auto to linear | answers differing, linear vs log | result |
|---|---|---|---|---|---|---|
| pbmc240_diann | linear | linear | 174/174/172 | 0 | 50 | FAIL: A3_linear_zscore_mean0_sd1 |
| kabatnik_cra_timstofultra | linear | linear | 10/10/11 | 0 | 6 | PASS |
| kabatnik_c3_region | linear | linear | 13/13/11 | 0 | 4 | PASS |
| pxd073250_diann | linear | linear | 170/170/159 | 0 | 98 | PASS |
| pxd077946_diann_genes | linear | linear | 20/20/18 | 0 | 5 | PASS |
| zamore_diann | linear | linear | 26/26/29 | 0 | 3 | PASS |
| pxd064083_t | linear | log | 47/40/47 | 36 | 36 | PASS |
| pxd064083_b | linear | log | 20/26/20 | 27 | 27 | PASS |
| pxd021882_maxquant |  |  |  |  |  | refused (fewer than 20 cells) |
| dusszachniewicz_maxquant | linear | linear | 20/20/22 | 0 | 13 | FAIL: A3_linear_zscore_mean0_sd1 |
| herrera2025_fragpipe | linear | linear | 38/38/49 | 0 | 54 | PASS |
| lungmap_bpd_fragpipe | linear | linear | 10/10/7 | 0 | 5 | FAIL: A3_linear_zscore_mean0_sd1, A3_log_zscore_mean0_sd1 |
| msv000099294_hmc3 | linear | log | 19/15/19 | 12 | 12 | PASS |
| msv000099294_microglia | linear | log | 19/14/19 | 11 | 11 | PASS |
| pxd061052_spectronaut | linear | linear | 7/7/8 | 0 | 7 | PASS |
| pxd043355_pd | linear | linear | 26/26/49 | 0 | 33 | PASS |
| fulcher_tmt | linear | linear | 1357/1357/1282 | 0 | 420 | PASS |
| scope2_export | log | log | 789/refused/789 | refused |  | PASS |
| khoury_column_normalized | log | log | 1535/1537/1535 | 33 | 33 | PASS |
| furtwangler_batchcorr | linear | log | 792/672/792 | 1243 | 1243 | FAIL: A3_linear_zscore_mean0_sd1 |
| furtwangler_batchcorr_norm | linear | log | 634/803/634 | 1125 | 1125 | PASS |
| furtwangler_log2 | log | log | 524/802/524 | 1092 | 1092 | PASS |
| furtwangler_log2_imputed | log | log | 488/480/488 | 54 | 54 | FAIL: A3_log_zscore_mean0_sd1 |
| furtwangler_log2_nan | log | log | 801/790/801 | 221 | 221 | PASS |
| furtwangler_log2fc_nan | log | log | 793/refused/793 | refused |  | PASS |
| furtwangler_log2_raw_sn | log | log | 946/1006/946 | 1283 | 1283 | PASS |
| pxd049412_hela250pg |  |  |  |  |  | refused (fewer than 20 cells) |
| pxd049412_a549_singlecells | linear | linear | 5/5/11 | 0 | 10 | PASS |
| pxd069060_diann_report |  |  |  |  |  | refused (fewer than 20 cells) |
| quantms_pxd004452_ibaq |  |  |  |  |  | refused (fewer than 20 cells) |
| quantms_pxd004452_ribaq |  |  |  |  |  | refused (fewer than 20 cells) |
| brunner_diann_1ng |  |  |  |  |  | refused (fewer than 20 cells) |
| brunner_mq_singlecells | linear | linear | 3/3/21 | 0 | 21 | PASS |
| krull_singlecells | linear | linear | 48/48/51 | 0 | 42 | PASS |
| cong_mq_singlecells |  |  |  |  |  | refused (fewer than 20 cells) |
| hu2023_pd_k562 | linear | linear | 4/4/3 | 0 | 9 | PASS |
| cptac_ccrcc_tumor | log | log | 47/refused/47 | refused |  | PASS |

## A4, the linear tables the rule reads as log

Reported, not judged: their stated linear reading is the right one.

| table | cells | answered, rule's reading | answered, stated linear | answers changed |
|---|---|---|---|---|
| pxd064083_t | 78 | 47 | 40 | 36 |
| pxd064083_b | 70 | 20 | 26 | 27 |
| msv000099294_hmc3 | 47 | 19 | 15 | 12 |
| msv000099294_microglia | 57 | 19 | 14 | 11 |
| furtwangler_batchcorr | 2000 | 792 | 672 | 1243 |
| furtwangler_batchcorr_norm | 2000 | 634 | 803 | 1125 |

## A5, through the app: 19 of 19 pass

| check | status | result |
|---|---|---|
| GET /api/status lists auto, linear and log |  | PASS |
| pbmc240_diann, value_scale absent: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| pbmc240_diann, value_scale auto: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| pbmc240_diann, value_scale linear: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| pbmc240_diann, value_scale log: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| pbmc240_diann: absent and auto give the same reply |  | PASS |
| khoury_column_normalized, value_scale absent: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| khoury_column_normalized, value_scale auto: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| khoury_column_normalized, value_scale linear: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| khoury_column_normalized, value_scale log: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| khoury_column_normalized: absent and auto give the same reply |  | PASS |
| scope2_export, value_scale absent: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| scope2_export, value_scale auto: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| scope2_export, value_scale linear: 400 naming the negative values | 400 | PASS |
| scope2_export, value_scale log: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| scope2_export: absent and auto give the same reply |  | PASS |
| modality rna, value_scale linear: 400 (protein only) | 400 | PASS |
| modality rna, value_scale log: 400 (protein only) | 400 | PASS |
| value_scale raw: 400 naming auto, linear and log | 400 | PASS |

