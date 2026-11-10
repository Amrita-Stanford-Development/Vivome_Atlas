# Value-scale diagnostics, R1: the corpus checks

Run 2026-11-10 17:27 by research/notebooks/value_scale_r1.py (24 s), on commit 4b521d0 (uncommitted changes: False). Expectations: valuescale/bank/expectations/r1.json, written before the run. Explained in notes.md beside this file.

## The rows

| row | result |
|---|---|
| R1_empty | PASS |
| R1_flag | PASS |
| R1_bank_empty | PASS |
| R1_bank_control | PASS |
| R1_bank_linear | recorded |
| R1_service | PASS |
| R1_site | PASS |
| R1_walk | PASS |

## B3's 457 kept tables

- labels: linear 457
- empty: PXD022054, PXD047898
- flagged (99% of the observed values under 64): PXD066316

| table | split | software | rows x columns | smallest | median | 99th percentile | largest |
|---|---|---|---|---|---|---|---|
| PXD066316 | test | Spectronaut | 5842 x 27 | 7.963 | 15.02 | 21.75 | 26.76 |

## The bank's 37 tables

| table | label | rows x columns | empty | the flag's rule | smallest | median | 99th percentile | largest |
|---|---|---|---|---|---|---|---|---|
| pbmc240_diann | linear | 3098 x 238 | no | does not fire |  |  |  |  |
| kabatnik_cra_timstofultra | linear | 7883 x 25 | no | does not fire |  |  |  |  |
| kabatnik_c3_region | linear | 4762 x 27 | no | does not fire |  |  |  |  |
| pxd073250_diann | linear | 5923 x 557 | no | does not fire |  |  |  |  |
| pxd077946_diann_genes | linear | 3271 x 40 | no | does not fire |  |  |  |  |
| zamore_diann | linear | 3300 x 30 | no | does not fire |  |  |  |  |
| pxd064083_t | linear | 2505 x 78 | no | does not fire |  |  |  |  |
| pxd064083_b | linear | 2508 x 70 | no | does not fire |  |  |  |  |
| pxd021882_maxquant | linear | 3817 x 15 | no | does not fire |  |  |  |  |
| dusszachniewicz_maxquant | linear | 9978 x 45 | no | does not fire |  |  |  |  |
| herrera2025_fragpipe | linear | 4937 x 91 | no | does not fire |  |  |  |  |
| lungmap_bpd_fragpipe | linear | 5074 x 20 | no | does not fire |  |  |  |  |
| msv000099294_hmc3 | linear | 3300 x 47 | no | does not fire |  |  |  |  |
| msv000099294_microglia | linear | 2178 x 57 | no | does not fire |  |  |  |  |
| pxd061052_spectronaut | linear | 3642 x 29 | no | does not fire |  |  |  |  |
| pxd043355_pd | linear | 5728 x 59 | no | does not fire |  |  |  |  |
| fulcher_tmt | linear | 1661 x 2343 | no | does not fire |  |  |  |  |
| scope2_export | log | 2935 x 1490 | no | fires | -2.597 | -0.000754 | 0.7017 | 3.021 |
| khoury_column_normalized | log | 3732 x 1651 | no | fires | 0.4259 | 10.64 | 16.54 | 26.4 |
| furtwangler_batchcorr | linear | 2934 x 2506 | no | does not fire |  |  |  |  |
| furtwangler_batchcorr_norm | linear | 2934 x 2506 | no | does not fire |  |  |  |  |
| furtwangler_log2 | log | 2934 x 2506 | no | fires | 0.718 | 3.54 | 7.051 | 10.91 |
| furtwangler_log2_imputed | log | 2934 x 2506 | no | fires | 0.718 | 2.433 | 6.511 | 10.91 |
| furtwangler_log2_nan | log | 2934 x 2506 | no | fires | 0.718 | 3.54 | 7.051 | 10.91 |
| furtwangler_log2fc_nan | log | 2934 x 2506 | no | fires | -5.563 | 0.01227 | 1.086 | 7.919 |
| furtwangler_log2_raw_sn | log | 2934 x 2506 | no | fires | 0.1375 | 3.689 | 7.673 | 11.93 |
| pxd049412_hela250pg | linear | 6014 x 3 | no | does not fire |  |  |  |  |
| pxd049412_a549_singlecells | linear | 5755 x 50 | no | does not fire |  |  |  |  |
| pxd069060_diann_report | linear | 1844 x 12 | no | does not fire |  |  |  |  |
| quantms_pxd004452_ibaq | linear | 8657 x 4 | no | does not fire |  |  |  |  |
| quantms_pxd004452_ribaq | log | 8657 x 4 | no | fires | 1.517 | 4.5 | 7.348 | 9.004 |
| brunner_diann_1ng | linear | 4339 x 15 | no | does not fire |  |  |  |  |
| brunner_mq_singlecells | linear | 8228 x 51 | no | does not fire |  |  |  |  |
| krull_singlecells | linear | 1409 x 143 | no | does not fire |  |  |  |  |
| cong_mq_singlecells | linear | 1726 x 7 | no | does not fire |  |  |  |  |
| hu2023_pd_k562 | linear | 1409 x 72 | no | does not fire |  |  |  |  |
| cptac_ccrcc_tumor | log | 11710 x 110 | no | fires | -5.261 | 0.05077 | 1.027 | 4.711 |

## The step's tests

- R1_walk: `python.exe -m unittest valuescale.tests.test_draw.VisitTests valuescale.tests.test_draw.LooksLogAuditTests`, exit 0; Ran 16 tests in 0.021s; OK
- R1_service: `python.exe -m unittest service.tests.test_validation.ValidateValuesTests service.tests.test_app.ProjectionHandlerHttpTests.test_a_table_with_no_observed_value_is_400_saying_why`, exit 0; Ran 4 tests in 1.181s; OK
- R1_site: `node --test --test-name-pattern=no observed value web/tests/atlas-file-check.test.js`, exit 0; ℹ tests 1; ℹ pass 1; ℹ fail 0
