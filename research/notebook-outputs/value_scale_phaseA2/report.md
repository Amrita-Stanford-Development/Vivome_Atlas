# Value-scale diagnostics, Phase A2: what a 0 means

Run 2026-10-28 13:16 by research/notebooks/value_scale_diagnostics.py. Expectations: valuescale/bank/expectations/phaseA2.json, written before the change. Baseline: ../value_scale_phaseA/baseline.json. Explained in notes.md beside this file.

## B1 to B3, every bank table: 37 of 37 pass

B1: the automatic reply is the baseline's, byte for byte. B2: with a log reading, zeros measured changes nothing but value_scale.zeros, zeros missing is applied and said, and zeros is refused without a log reading. B3: the stage invariants under a log reading with zeros missing (the z-score check is the next step's).

| table | share of 0 | answered, zeros measured/missing | answers changed | cells | result |
|---|---|---|---|---|---|
| pbmc240_diann | 0.0 | 172/172 | 0 | 238 | PASS |
| kabatnik_cra_timstofultra | 0.0 | 11/11 | 0 | 25 | PASS |
| kabatnik_c3_region | 0.0 | 11/11 | 0 | 27 | PASS |
| pxd073250_diann | 0.0 | 159/159 | 0 | 557 | PASS |
| pxd077946_diann_genes | 0.0 | 18/18 | 0 | 40 | PASS |
| zamore_diann | 0.0 | 29/29 | 0 | 30 | PASS |
| pxd064083_t | 0.4387 | 47/40 | 39 | 78 | PASS |
| pxd064083_b | 0.4658 | 20/23 | 22 | 70 | PASS |
| pxd021882_maxquant |  |  |  |  | refused (fewer than 20 cells) |
| dusszachniewicz_maxquant | 0.0 | 22/22 | 0 | 45 | PASS |
| herrera2025_fragpipe | 0.0 | 49/49 | 0 | 91 | PASS |
| lungmap_bpd_fragpipe | 0.0 | 7/7 | 0 | 20 | PASS |
| msv000099294_hmc3 | 0.0 | 19/19 | 0 | 47 | PASS |
| msv000099294_microglia | 0.0 | 19/19 | 0 | 57 | PASS |
| pxd061052_spectronaut | 0.0 | 8/8 | 0 | 29 | PASS |
| pxd043355_pd | 0.0 | 49/49 | 0 | 59 | PASS |
| fulcher_tmt | 0.0 | 1282/1282 | 0 | 2000 | PASS |
| scope2_export | 0.0 | 789/789 | 0 | 1490 | PASS |
| khoury_column_normalized | 0.0 | 1535/1535 | 0 | 1651 | PASS |
| furtwangler_batchcorr | 0.6838 | 792/638 | 1280 | 2000 | PASS |
| furtwangler_batchcorr_norm | 0.6835 | 634/787 | 1096 | 2000 | PASS |
| furtwangler_log2 | 0.6839 | 524/806 | 1100 | 2000 | PASS |
| furtwangler_log2_imputed | 0.0 | 488/488 | 0 | 2000 | PASS |
| furtwangler_log2_nan | 0.0 | 801/801 | 0 | 2000 | PASS |
| furtwangler_log2fc_nan | 0.0 | 793/793 | 0 | 2000 | PASS |
| furtwangler_log2_raw_sn | 0.6834 | 946/975 | 1302 | 2000 | PASS |
| pxd049412_hela250pg |  |  |  |  | refused (fewer than 20 cells) |
| pxd049412_a549_singlecells | 0.0 | 11/11 | 0 | 50 | PASS |
| pxd069060_diann_report |  |  |  |  | refused (fewer than 20 cells) |
| quantms_pxd004452_ibaq |  |  |  |  | refused (fewer than 20 cells) |
| quantms_pxd004452_ribaq |  |  |  |  | refused (fewer than 20 cells) |
| brunner_diann_1ng |  |  |  |  | refused (fewer than 20 cells) |
| brunner_mq_singlecells | 0.0 | 21/21 | 0 | 51 | PASS |
| krull_singlecells | 0.0007 | 51/53 | 13 | 143 | PASS |
| cong_mq_singlecells |  |  |  |  | refused (fewer than 20 cells) |
| hu2023_pd_k562 | 0.0 | 3/3 | 0 | 72 | PASS |
| cptac_ccrcc_tumor | 0.0 | 47/47 | 0 | 110 | PASS |

## B4, through the app: 7 of 7 pass

| check | status | result |
|---|---|---|
| GET /api/status lists the zeros choices |  | PASS |
| pbmc240_diann (its file), value_scale log with zeros missing: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| furtwangler_log2 (its 2,000-cell subsample), value_scale log with zeros missing: 200, equal to pipeline.run_projection's reply | 200 | PASS |
| zeros missing without value_scale: 400 naming value_scale log | 400 | PASS |
| zeros missing with value_scale linear: 400 naming value_scale log | 400 | PASS |
| modality rna with zeros missing: 400 | 400 | PASS |
| zeros none: 400 naming missing and measured | 400 | PASS |

## B5, the final review's smaller points: 4 of 4 pass

| check | result |
|---|---|
| the pipeline refuses {'stated_scale': 'log'} on an RNA upload | PASS |
| the pipeline refuses {'stated_scale': 'log', 'stated_zeros': 'missing'} on an RNA upload | PASS |
| apply_reading refuses the reading 'Linear' | PASS |
| one negative value is said as '1 value is negative' | PASS |

