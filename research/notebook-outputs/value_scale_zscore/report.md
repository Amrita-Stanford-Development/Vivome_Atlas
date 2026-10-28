# Value-scale diagnostics: the float64 z-score

Run 2026-10-28 13:36 by research/notebooks/value_scale_diagnostics.py. Expectations: valuescale/bank/expectations/zscore.json, written before the change. Baseline: ../value_scale_phaseA/baseline.json (the replies before Phase A). Explained in notes.md beside this file.

## Z1 to Z3 and Z5, every traced table: 24 of 30 pass

Z1: the z-score invariant under the automatic, linear and log readings. Z2: no near-constant gene under the automatic reading. Z3: against the baseline, every field but the cells unchanged, at least 99% of answers kept, coordinates within 0.01. Z5: Phase A's other invariants.

| table | cells | answers changed | largest coordinate change | near-constant genes (auto/linear/log) | result |
|---|---|---|---|---|---|
| pbmc240_diann | 238 | 0 | 0.0386 | 0/0/0 | FAIL: Z3_coordinates_within_0.01 |
| kabatnik_cra_timstofultra | 25 | 0 | 0.0 | 0/0/0 | PASS |
| kabatnik_c3_region | 27 | 0 | 0.0 | 0/0/0 | PASS |
| pxd073250_diann | 557 | 0 | 0.0801 | 0/0/0 | FAIL: Z3_coordinates_within_0.01 |
| pxd077946_diann_genes | 40 | 0 | 0.0 | 0/0/0 | PASS |
| zamore_diann | 30 | 0 | 0.0 | 0/0/0 | PASS |
| pxd064083_t | 78 | 0 | 0.0 | 0/0/0 | PASS |
| pxd064083_b | 70 | 0 | 0.0 | 0/0/0 | PASS |
| dusszachniewicz_maxquant | 45 | 0 | 0.0 | 0/0/0 | PASS |
| herrera2025_fragpipe | 91 | 0 | 0.0 | 0/0/0 | PASS |
| lungmap_bpd_fragpipe | 20 | 0 | 0.0 | 0/0/0 | PASS |
| msv000099294_hmc3 | 47 | 3 | 0.0558 | 0/0/0 | FAIL: Z3_fields_but_cells_unchanged, Z3_answers_kept_99pct, Z3_coordinates_within_0.01 |
| msv000099294_microglia | 57 | 0 | 0.049 | 0/0/0 | FAIL: Z3_coordinates_within_0.01 |
| pxd061052_spectronaut | 29 | 0 | 0.0 | 0/0/0 | PASS |
| pxd043355_pd | 59 | 0 | 0.0 | 0/0/0 | PASS |
| fulcher_tmt | 2000 | 0 | 0.0 | 0/0/0 | PASS |
| scope2_export | 1490 | 0 | 0.0 | 0/refused/0 | PASS |
| khoury_column_normalized | 1651 | 0 | 0.0009 | 0/0/0 | PASS |
| furtwangler_batchcorr | 2000 | 0 | 0.0 | 0/10/0 | PASS |
| furtwangler_batchcorr_norm | 2000 | 0 | 0.0061 | 0/0/0 | PASS |
| furtwangler_log2 | 2000 | 0 | 0.0 | 0/0/0 | PASS |
| furtwangler_log2_imputed | 2000 | 0 | 0.0001 | 0/0/0 | PASS |
| furtwangler_log2_nan | 2000 | 0 | 0.0 | 0/0/0 | PASS |
| furtwangler_log2fc_nan | 2000 | 0 | 0.0 | 0/refused/0 | PASS |
| furtwangler_log2_raw_sn | 2000 | 0 | 0.0146 | 0/0/0 | FAIL: Z3_coordinates_within_0.01 |
| pxd049412_a549_singlecells | 50 | 0 | 0.0345 | 0/0/0 | FAIL: Z3_coordinates_within_0.01 |
| brunner_mq_singlecells | 51 | 0 | 0.0 | 0/0/0 | PASS |
| krull_singlecells | 143 | 0 | 0.0 | 0/0/0 | PASS |
| hu2023_pd_k562 | 72 | 0 | 0.0 | 0/0/0 | PASS |
| cptac_ccrcc_tumor | 110 | 0 | 0.0 | 0/refused/0 | PASS |

