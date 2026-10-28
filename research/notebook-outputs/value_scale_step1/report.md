# Value-scale diagnostics, Step 1: the bank

Run 2026-10-28 09:35 by research/notebooks/value_scale_diagnostics.py. Expectations: valuescale/bank/expectations/step1.json, written before this run. The bank: valuescale/corpus/bank.json.

## D1, the bank itself: 35 of 37 pass

| table | label | strength | layout | cells | proteins | matched | missing | zeros | negative | median non-zero | q99 | result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pbmc240_diann | linear | documented | dia-nn | 238 | 3098 | 2996 | 0.6278 | 0.0 | 0.0 | 4780.3198 | 433014.875 | PASS |
| kabatnik_cra_timstofultra | linear | documented | dia-nn | 25 | 7883 | 6260 | 0.0794 | 0.0 | 0.0 | 38036.8516 | 1615927.875 | PASS |
| kabatnik_c3_region | linear | documented | dia-nn | 27 | 4762 | 4120 | 0.2058 | 0.0 | 0.0 | 1001.025 | 39502.8945 | PASS |
| pxd073250_diann | linear | documented | dia-nn | 557 | 5923 | 5185 | 0.8988 | 0.0 | 0.0 | 3143.8201 | 189001.2969 | PASS |
| pxd077946_diann_genes | linear | documented | dia-nn | 40 | 3271 | 3201 | 0.4506 | 0.0 | 0.0 | 2558.99 | 79534.8984 | PASS |
| zamore_diann | linear | documented | dia-nn | 30 | 3300 | 3019 | 0.2848 | 0.0 | 0.0 | 640916.0 | 68118056.0 | PASS |
| pxd064083_t | linear | inferred | matrix | 78 | 2505 | 2305 | 0.0 | 0.4387 | 0.0 | 6.9903 | 227.0393 | PASS |
| pxd064083_b | linear | inferred | matrix | 70 | 2508 | 2305 | 0.0 | 0.4658 | 0.0 | 7.9171 | 250.9993 | PASS |
| pxd021882_maxquant | linear | documented | maxquant | 15 | 3817 | 3425 | 0.7176 | 0.0 | 0.0 | 25550500.0 | 4171870976.0 | PASS |
| dusszachniewicz_maxquant | linear | documented | maxquant | 45 | 9978 | 6721 | 0.3947 | 0.0 | 0.0 | 348350016.0 | 24373280768.0 | PASS |
| herrera2025_fragpipe | linear | documented | fragpipe-lfq | 91 | 4937 | 4207 | 0.4688 | 0.0 | 0.0 | 41783.2812 | 5532028.5 | PASS |
| lungmap_bpd_fragpipe | linear | documented | fragpipe-lfq | 20 | 5074 | 4479 | 0.7215 | 0.0 | 0.0 | 22832846.0 | 933974976.0 | PASS |
| msv000099294_hmc3 | linear | named | matrix | 47 | 3300 | 3018 | 0.3511 | 0.0 | 0.0 | 5.7525 | 224.345 | FAIL: layout_as_listed |
| msv000099294_microglia | linear | named | matrix | 57 | 2178 | 1877 | 0.5706 | 0.0 | 0.0 | 3.93 | 228.2244 | FAIL: layout_as_listed |
| pxd061052_spectronaut | linear | named | spectronaut | 29 | 3642 | 3260 | 0.1935 | 0.0 | 0.0 | 10662.5723 | 3057129.5 | PASS |
| pxd043355_pd | linear | documented | matrix | 59 | 5728 | 5495 | 0.599 | 0.0 | 0.0 | 16962.5273 | 148460832.0 | PASS |
| fulcher_tmt | linear | author_code | fragpipe-tmt | 2343 | 1661 | 1654 | 0.5952 | 0.0 | 0.0 | 241512.375 | 57583676.0 | PASS |
| scope2_export | log | documented | matrix | 1490 | 2935 | 2907 | 0.0 | 0.0 | 0.5013 | -0.0008 | 0.7017 | PASS |
| khoury_column_normalized | log | author_code | dia-nn | 1651 | 3732 | 3110 | 0.5874 | 0.0 | 0.0 | 10.6378 | 16.54 | PASS |
| furtwangler_batchcorr | linear | named | matrix | 2506 | 2934 | 2734 | 0.0 | 0.6839 | 0.0 | 10.7627 | 90.839 | PASS |
| furtwangler_batchcorr_norm | linear | named | matrix | 2506 | 2934 | 2734 | 0.0 | 0.6839 | 0.0 | 10.6345 | 87.3334 | PASS |
| furtwangler_log2 | log | named | matrix | 2506 | 2934 | 2734 | 0.0 | 0.6839 | 0.0 | 3.5403 | 6.4649 | PASS |
| furtwangler_log2_imputed | log | named | matrix | 2506 | 2934 | 2734 | 0.0 | 0.0 | 0.0 | 2.4327 | 6.511 | PASS |
| furtwangler_log2_nan | log | named | matrix | 2506 | 2934 | 2734 | 0.6839 | 0.0 | 0.0 | 3.5403 | 7.0514 | PASS |
| furtwangler_log2fc_nan | log | named | matrix | 2506 | 2934 | 2734 | 0.6839 | 0.0 | 0.1522 | 0.0123 | 1.0862 | PASS |
| furtwangler_log2_raw_sn | log | named | matrix | 2506 | 2934 | 2734 | 0.0 | 0.6833 | 0.0 | 3.6893 | 6.9402 | PASS |
| pxd049412_hela250pg | linear | named | spectronaut | 3 | 6014 | 5787 | 0.0336 | 0.0 | 0.0 | 605.1326 | 42307.6289 | PASS |
| pxd049412_a549_singlecells | linear | named | spectronaut | 50 | 5755 | 5623 | 0.4508 | 0.0 | 0.0 | 267.5581 | 36812.082 | PASS |
| pxd069060_diann_report | linear | documented | matrix | 12 | 1844 | 1423 | 0.356 | 0.0055 | 0.0 | 390449.5 | 1293640064.0 | PASS |
| quantms_pxd004452_ibaq | linear | documented | matrix | 4 | 8657 | 6610 | 0.1744 | 0.0 | 0.0 | 8642764.0 | 6144950272.0 | PASS |
| quantms_pxd004452_ribaq | log | inferred | matrix | 4 | 8657 | 6610 | 0.1744 | 0.0 | 0.0 | 4.4998 | 7.3482 | PASS |
| brunner_diann_1ng | linear | documented | dia-nn | 15 | 4339 | 3944 | 0.1004 | 0.0 | 0.0 | 9162.9297 | 272125.75 | PASS |
| brunner_mq_singlecells | linear | documented | maxquant | 51 | 8228 | 5956 | 0.6025 | 0.0 | 0.0 | 140730.0 | 11738600.0 | PASS |
| krull_singlecells | linear | documented | matrix | 143 | 1409 | 1146 | 0.615 | 0.0007 | 0.0 | 547.0395 | 90825.5938 | PASS |
| cong_mq_singlecells | linear | documented | maxquant | 7 | 1726 | 1540 | 0.591 | 0.0 | 0.0 | 2486150.0 | 167070400.0 | PASS |
| hu2023_pd_k562 | linear | author_code | matrix | 72 | 1409 | 1354 | 0.1194 | 0.0 | 0.0 | 11908.2178 | 777707.125 | PASS |
| cptac_ccrcc_tumor | log | documented | matrix | 110 | 11710 | 7486 | 0.2211 | 0.0 | 0.3403 | 0.0508 | 1.0267 | PASS |

## D2, today's rule on the bank and its variants

690 labelled tables and variants; today's rule reads 182 wrongly (97 of them not predicted); 1 predicted misreads did not happen.

| variant | label | tables | read wrongly | predicted |
|---|---|---|---|---|
| ln | log | 37 | 0 |  |
| log10 | log | 37 | 0 |  |
| log2 | log | 37 | 0 |  |
| log2_minus_min | log | 37 | 0 |  |
| log2_plus10 | log | 37 | 0 |  |
| log2_plus1_after_min | log | 37 | 0 |  |
| log2_times_0.5 | log | 37 | 0 |  |
| log2_zeros_imputed | log | 37 | 0 |  |
| missing_40 | linear | 28 | 6 |  |
| missing_40 | log | 9 | 0 |  |
| missing_70 | linear | 28 | 6 |  |
| missing_70 | log | 9 | 0 |  |
| original | linear | 28 | 6 |  |
| original | log | 9 | 0 |  |
| per_cell_cpm | linear | 37 | 13 |  |
| per_cell_percent | linear | 37 | 37 | yes |
| per_protein_median | linear | 37 | 37 | yes |
| subsample_20 | linear | 21 | 6 |  |
| subsample_20 | log | 8 | 0 |  |
| subsample_300 | linear | 4 | 2 |  |
| subsample_300 | log | 7 | 0 |  |
| subsample_50 | linear | 13 | 5 |  |
| subsample_50 | log | 8 | 0 |  |
| times_1e-3 | linear | 37 | 28 |  |
| times_1e-6 | linear | 37 | 36 | yes |
| times_1e3 | linear | 37 | 0 |  |

Read wrongly, by table:

| table | variant | label | read as | predicted |
|---|---|---|---|---|
| pbmc240_diann | times_1e-6 | linear | log | yes |
| pbmc240_diann | times_1e-3 | linear | log | no |
| pbmc240_diann | per_protein_median | linear | log | yes |
| pbmc240_diann | per_cell_percent | linear | log | yes |
| kabatnik_cra_timstofultra | times_1e-6 | linear | log | yes |
| kabatnik_cra_timstofultra | times_1e-3 | linear | log | no |
| kabatnik_cra_timstofultra | per_protein_median | linear | log | yes |
| kabatnik_cra_timstofultra | per_cell_cpm | linear | log | no |
| kabatnik_cra_timstofultra | per_cell_percent | linear | log | yes |
| kabatnik_c3_region | times_1e-6 | linear | log | yes |
| kabatnik_c3_region | times_1e-3 | linear | log | no |
| kabatnik_c3_region | per_protein_median | linear | log | yes |
| kabatnik_c3_region | per_cell_percent | linear | log | yes |
| pxd073250_diann | times_1e-6 | linear | log | yes |
| pxd073250_diann | times_1e-3 | linear | log | no |
| pxd073250_diann | per_protein_median | linear | log | yes |
| pxd073250_diann | per_cell_percent | linear | log | yes |
| pxd077946_diann_genes | times_1e-6 | linear | log | yes |
| pxd077946_diann_genes | times_1e-3 | linear | log | no |
| pxd077946_diann_genes | per_protein_median | linear | log | yes |
| pxd077946_diann_genes | per_cell_percent | linear | log | yes |
| zamore_diann | times_1e-6 | linear | log | yes |
| zamore_diann | per_protein_median | linear | log | yes |
| zamore_diann | per_cell_cpm | linear | log | no |
| zamore_diann | per_cell_percent | linear | log | yes |
| pxd064083_t | original | linear | log | yes |
| pxd064083_t | times_1e-6 | linear | log | yes |
| pxd064083_t | times_1e-3 | linear | log | no |
| pxd064083_t | per_protein_median | linear | log | yes |
| pxd064083_t | per_cell_percent | linear | log | yes |
| pxd064083_t | subsample_20 | linear | log | no |
| pxd064083_t | subsample_50 | linear | log | no |
| pxd064083_t | missing_40 | linear | log | no |
| pxd064083_t | missing_70 | linear | log | no |
| pxd064083_b | original | linear | log | yes |
| pxd064083_b | times_1e-6 | linear | log | yes |
| pxd064083_b | times_1e-3 | linear | log | no |
| pxd064083_b | per_protein_median | linear | log | yes |
| pxd064083_b | per_cell_percent | linear | log | yes |
| pxd064083_b | subsample_20 | linear | log | no |
| pxd064083_b | subsample_50 | linear | log | no |
| pxd064083_b | missing_40 | linear | log | no |
| pxd064083_b | missing_70 | linear | log | no |
| pxd021882_maxquant | times_1e-6 | linear | log | yes |
| pxd021882_maxquant | per_protein_median | linear | log | yes |
| pxd021882_maxquant | per_cell_percent | linear | log | yes |
| dusszachniewicz_maxquant | per_protein_median | linear | log | yes |
| dusszachniewicz_maxquant | per_cell_cpm | linear | log | no |
| dusszachniewicz_maxquant | per_cell_percent | linear | log | yes |
| herrera2025_fragpipe | times_1e-6 | linear | log | yes |
| herrera2025_fragpipe | times_1e-3 | linear | log | no |
| herrera2025_fragpipe | per_protein_median | linear | log | yes |
| herrera2025_fragpipe | per_cell_cpm | linear | log | no |
| herrera2025_fragpipe | per_cell_percent | linear | log | yes |
| lungmap_bpd_fragpipe | times_1e-6 | linear | log | yes |
| lungmap_bpd_fragpipe | per_protein_median | linear | log | yes |
| lungmap_bpd_fragpipe | per_cell_percent | linear | log | yes |
| msv000099294_hmc3 | original | linear | log | no |
| msv000099294_hmc3 | times_1e-6 | linear | log | yes |
| msv000099294_hmc3 | times_1e-3 | linear | log | no |
| msv000099294_hmc3 | per_protein_median | linear | log | yes |
| msv000099294_hmc3 | per_cell_percent | linear | log | yes |
| msv000099294_hmc3 | subsample_20 | linear | log | no |
| msv000099294_hmc3 | missing_40 | linear | log | no |
| msv000099294_hmc3 | missing_70 | linear | log | no |
| msv000099294_microglia | original | linear | log | no |
| msv000099294_microglia | times_1e-6 | linear | log | yes |
| msv000099294_microglia | times_1e-3 | linear | log | no |
| msv000099294_microglia | per_protein_median | linear | log | yes |
| msv000099294_microglia | per_cell_percent | linear | log | yes |
| msv000099294_microglia | subsample_20 | linear | log | no |
| msv000099294_microglia | subsample_50 | linear | log | no |
| msv000099294_microglia | missing_40 | linear | log | no |
| msv000099294_microglia | missing_70 | linear | log | no |
| pxd061052_spectronaut | times_1e-6 | linear | log | yes |
| pxd061052_spectronaut | times_1e-3 | linear | log | no |
| pxd061052_spectronaut | per_protein_median | linear | log | yes |
| pxd061052_spectronaut | per_cell_cpm | linear | log | no |
| pxd061052_spectronaut | per_cell_percent | linear | log | yes |
| pxd043355_pd | times_1e-6 | linear | log | yes |
| pxd043355_pd | times_1e-3 | linear | log | no |
| pxd043355_pd | per_protein_median | linear | log | yes |
| pxd043355_pd | per_cell_cpm | linear | log | no |
| pxd043355_pd | per_cell_percent | linear | log | yes |
| fulcher_tmt | times_1e-6 | linear | log | yes |
| fulcher_tmt | per_protein_median | linear | log | yes |
| fulcher_tmt | per_cell_percent | linear | log | yes |
| scope2_export | times_1e-6 | linear | log | no |
| scope2_export | times_1e-3 | linear | log | no |
| scope2_export | per_protein_median | linear | log | no |
| scope2_export | per_cell_percent | linear | log | no |
| khoury_column_normalized | times_1e-6 | linear | log | no |
| khoury_column_normalized | times_1e-3 | linear | log | no |
| khoury_column_normalized | per_protein_median | linear | log | no |
| khoury_column_normalized | per_cell_percent | linear | log | no |
| furtwangler_batchcorr | original | linear | log | no |
| furtwangler_batchcorr | times_1e-6 | linear | log | yes |
| furtwangler_batchcorr | times_1e-3 | linear | log | no |
| furtwangler_batchcorr | per_protein_median | linear | log | yes |
| furtwangler_batchcorr | per_cell_percent | linear | log | yes |
| furtwangler_batchcorr | subsample_20 | linear | log | no |
| furtwangler_batchcorr | subsample_50 | linear | log | no |
| furtwangler_batchcorr | subsample_300 | linear | log | no |
| furtwangler_batchcorr | missing_40 | linear | log | no |
| furtwangler_batchcorr | missing_70 | linear | log | no |
| furtwangler_batchcorr_norm | original | linear | log | no |
| furtwangler_batchcorr_norm | times_1e-6 | linear | log | yes |
| furtwangler_batchcorr_norm | times_1e-3 | linear | log | no |
| furtwangler_batchcorr_norm | per_protein_median | linear | log | yes |
| furtwangler_batchcorr_norm | per_cell_percent | linear | log | yes |
| furtwangler_batchcorr_norm | subsample_20 | linear | log | no |
| furtwangler_batchcorr_norm | subsample_50 | linear | log | no |
| furtwangler_batchcorr_norm | subsample_300 | linear | log | no |
| furtwangler_batchcorr_norm | missing_40 | linear | log | no |
| furtwangler_batchcorr_norm | missing_70 | linear | log | no |
| furtwangler_log2 | times_1e-6 | linear | log | no |
| furtwangler_log2 | times_1e-3 | linear | log | no |
| furtwangler_log2 | per_protein_median | linear | log | no |
| furtwangler_log2 | per_cell_cpm | linear | log | no |
| furtwangler_log2 | per_cell_percent | linear | log | no |
| furtwangler_log2_imputed | times_1e-6 | linear | log | no |
| furtwangler_log2_imputed | times_1e-3 | linear | log | no |
| furtwangler_log2_imputed | per_protein_median | linear | log | no |
| furtwangler_log2_imputed | per_cell_percent | linear | log | no |
| furtwangler_log2_nan | times_1e-6 | linear | log | no |
| furtwangler_log2_nan | times_1e-3 | linear | log | no |
| furtwangler_log2_nan | per_protein_median | linear | log | no |
| furtwangler_log2_nan | per_cell_percent | linear | log | no |
| furtwangler_log2fc_nan | times_1e-6 | linear | log | no |
| furtwangler_log2fc_nan | times_1e-3 | linear | log | no |
| furtwangler_log2fc_nan | per_protein_median | linear | log | no |
| furtwangler_log2fc_nan | per_cell_percent | linear | log | no |
| furtwangler_log2_raw_sn | times_1e-6 | linear | log | no |
| furtwangler_log2_raw_sn | times_1e-3 | linear | log | no |
| furtwangler_log2_raw_sn | per_protein_median | linear | log | no |
| furtwangler_log2_raw_sn | per_cell_percent | linear | log | no |
| pxd049412_hela250pg | times_1e-6 | linear | log | yes |
| pxd049412_hela250pg | times_1e-3 | linear | log | no |
| pxd049412_hela250pg | per_protein_median | linear | log | yes |
| pxd049412_hela250pg | per_cell_cpm | linear | log | no |
| pxd049412_hela250pg | per_cell_percent | linear | log | yes |
| pxd049412_a549_singlecells | times_1e-6 | linear | log | yes |
| pxd049412_a549_singlecells | times_1e-3 | linear | log | no |
| pxd049412_a549_singlecells | per_protein_median | linear | log | yes |
| pxd049412_a549_singlecells | per_cell_cpm | linear | log | no |
| pxd049412_a549_singlecells | per_cell_percent | linear | log | yes |
| pxd069060_diann_report | times_1e-6 | linear | log | yes |
| pxd069060_diann_report | per_protein_median | linear | log | yes |
| pxd069060_diann_report | per_cell_cpm | linear | log | no |
| pxd069060_diann_report | per_cell_percent | linear | log | yes |
| quantms_pxd004452_ibaq | times_1e-6 | linear | log | yes |
| quantms_pxd004452_ibaq | per_protein_median | linear | log | yes |
| quantms_pxd004452_ibaq | per_cell_cpm | linear | log | no |
| quantms_pxd004452_ibaq | per_cell_percent | linear | log | yes |
| quantms_pxd004452_ribaq | times_1e-6 | linear | log | no |
| quantms_pxd004452_ribaq | times_1e-3 | linear | log | no |
| quantms_pxd004452_ribaq | per_protein_median | linear | log | no |
| quantms_pxd004452_ribaq | per_cell_percent | linear | log | no |
| brunner_diann_1ng | times_1e-6 | linear | log | yes |
| brunner_diann_1ng | times_1e-3 | linear | log | no |
| brunner_diann_1ng | per_protein_median | linear | log | yes |
| brunner_diann_1ng | per_cell_percent | linear | log | yes |
| brunner_mq_singlecells | times_1e-6 | linear | log | yes |
| brunner_mq_singlecells | per_protein_median | linear | log | yes |
| brunner_mq_singlecells | per_cell_cpm | linear | log | no |
| brunner_mq_singlecells | per_cell_percent | linear | log | yes |
| krull_singlecells | times_1e-6 | linear | log | yes |
| krull_singlecells | times_1e-3 | linear | log | no |
| krull_singlecells | per_protein_median | linear | log | yes |
| krull_singlecells | per_cell_percent | linear | log | yes |
| cong_mq_singlecells | times_1e-6 | linear | log | yes |
| cong_mq_singlecells | per_protein_median | linear | log | yes |
| cong_mq_singlecells | per_cell_percent | linear | log | yes |
| hu2023_pd_k562 | times_1e-6 | linear | log | yes |
| hu2023_pd_k562 | times_1e-3 | linear | log | no |
| hu2023_pd_k562 | per_protein_median | linear | log | yes |
| hu2023_pd_k562 | per_cell_cpm | linear | log | no |
| hu2023_pd_k562 | per_cell_percent | linear | log | yes |
| cptac_ccrcc_tumor | times_1e-6 | linear | log | no |
| cptac_ccrcc_tumor | times_1e-3 | linear | log | no |
| cptac_ccrcc_tumor | per_protein_median | linear | log | no |
| cptac_ccrcc_tumor | per_cell_percent | linear | log | no |

Foreign variants (no right reading; reported only):

| variant | read as | tables |
|---|---|---|
| presence | log | 37 |
| ranks | linear | 37 |
| zscore_genes | log | 37 |

## D3, today's pipeline traced stage by stage: 37 of 37 pass

| table | cells traced | Stage 0 read | genes matched | answered | abstained (reason count) | result |
|---|---|---|---|---|---|---|
| pbmc240_diann | 238 | linear | 2996 | 174/238 | ambiguous_between_classes 59, outside_supported_region 4, coverage_too_low 1 | PASS |
| kabatnik_cra_timstofultra | 25 | linear | 6260 | 10/25 | ambiguous_between_classes 15 | PASS |
| kabatnik_c3_region | 27 | linear | 4120 | 13/27 | ambiguous_between_classes 12, outside_supported_region 2 | PASS |
| pxd073250_diann | 557 | linear | 5185 | 170/557 | coverage_too_low 187, ambiguous_between_classes 159, outside_supported_region 41 | PASS |
| pxd077946_diann_genes | 40 | linear | 3201 | 20/40 | ambiguous_between_classes 19, outside_supported_region 1 | PASS |
| zamore_diann | 30 | linear | 3019 | 26/30 | ambiguous_between_classes 4 | PASS |
| pxd064083_t | 78 | log | 2305 | 47/78 | ambiguous_between_classes 28, no_confident_label 3 | PASS |
| pxd064083_b | 70 | log | 2305 | 20/70 | ambiguous_between_classes 48, outside_supported_region 2 | PASS |
| pxd021882_maxquant | 15 |  |  |  |  | refused (expected) |
| dusszachniewicz_maxquant | 45 | linear | 6721 | 20/45 | ambiguous_between_classes 20, outside_supported_region 3, no_confident_label 2 | PASS |
| herrera2025_fragpipe | 91 | linear | 4207 | 38/91 | outside_supported_region 15, ambiguous_between_classes 37, no_confident_label 1 | PASS |
| lungmap_bpd_fragpipe | 20 | linear | 4479 | 10/20 | ambiguous_between_classes 10 | PASS |
| msv000099294_hmc3 | 47 | log | 3018 | 19/47 | ambiguous_between_classes 25, coverage_too_low 1, outside_supported_region 2 | PASS |
| msv000099294_microglia | 57 | log | 1877 | 19/57 | ambiguous_between_classes 26, outside_supported_region 2, coverage_too_low 10 | PASS |
| pxd061052_spectronaut | 29 | linear | 3260 | 7/29 | ambiguous_between_classes 21, outside_supported_region 1 | PASS |
| pxd043355_pd | 59 | linear | 5495 | 26/59 | ambiguous_between_classes 23, outside_supported_region 10 | PASS |
| fulcher_tmt | 2000 | linear | 1654 | 1357/2000 | ambiguous_between_classes 444, coverage_too_low 179, outside_supported_region 19, no_confident_label 1 | PASS |
| scope2_export | 1490 | log | 2907 | 789/1490 | ambiguous_between_classes 657, no_confident_label 44 | PASS |
| khoury_column_normalized | 1651 | log | 3110 | 1535/1651 | no_confident_label 3, ambiguous_between_classes 110, outside_supported_region 3 | PASS |
| furtwangler_batchcorr | 2000 | log | 2734 | 792/2000 | ambiguous_between_classes 1105, outside_supported_region 39, no_confident_label 64 | PASS |
| furtwangler_batchcorr_norm | 2000 | log | 2734 | 634/2000 | ambiguous_between_classes 1271, outside_supported_region 5, no_confident_label 90 | PASS |
| furtwangler_log2 | 2000 | log | 2734 | 524/2000 | ambiguous_between_classes 1390, outside_supported_region 19, no_confident_label 67 | PASS |
| furtwangler_log2_imputed | 2000 | log | 2734 | 488/2000 | ambiguous_between_classes 1492, no_confident_label 13, outside_supported_region 7 | PASS |
| furtwangler_log2_nan | 2000 | log | 2734 | 801/2000 | ambiguous_between_classes 1174, outside_supported_region 23, no_confident_label 2 | PASS |
| furtwangler_log2fc_nan | 2000 | log | 2734 | 793/2000 | ambiguous_between_classes 1173, outside_supported_region 33, no_confident_label 1 | PASS |
| furtwangler_log2_raw_sn | 2000 | log | 2734 | 946/2000 | ambiguous_between_classes 995, outside_supported_region 25, no_confident_label 34 | PASS |
| pxd049412_hela250pg | 3 |  |  |  |  | refused (expected) |
| pxd049412_a549_singlecells | 50 | linear | 5623 | 5/50 | ambiguous_between_classes 34, coverage_too_low 7, outside_supported_region 4 | PASS |
| pxd069060_diann_report | 12 |  |  |  |  | refused (expected) |
| quantms_pxd004452_ibaq | 4 |  |  |  |  | refused (expected) |
| quantms_pxd004452_ribaq | 4 |  |  |  |  | refused (expected) |
| brunner_diann_1ng | 15 |  |  |  |  | refused (expected) |
| brunner_mq_singlecells | 51 | linear | 5956 | 3/51 | ambiguous_between_classes 44, coverage_too_low 4 | PASS |
| krull_singlecells | 143 | linear | 1146 | 48/143 | ambiguous_between_classes 88, outside_supported_region 4, coverage_too_low 3 | PASS |
| cong_mq_singlecells | 7 |  |  |  |  | refused (expected) |
| hu2023_pd_k562 | 72 | linear | 1354 | 4/72 | ambiguous_between_classes 46, outside_supported_region 22 | PASS |
| cptac_ccrcc_tumor | 110 | log | 7486 | 47/110 | ambiguous_between_classes 46, outside_supported_region 8, no_confident_label 9 | PASS |

