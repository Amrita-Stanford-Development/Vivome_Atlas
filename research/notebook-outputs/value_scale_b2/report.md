# B2: the method on the bank

Run 2026-11-03, 268 s. Expectations: `valuescale/bank/expectations/b2.json`, written before the method existed. A table and its variants are scored by a model fitted without the table's deposit, with rehearsal thresholds from that model's design scores (no guarantee: there is no calibration split until B3).

## Expectations

| Row | Result | Detail |
|---|---|---|
| B2_gates | FAIL | `{"negatives_unexpected": [["cptac_ccrcc_tumor", "ln"], ["cptac_ccrcc_tumor", "log10"], ["cptac_ccrcc_tumor", "log2"], ["cptac_ccrcc_tumor", "log2_times_0.5"], ["furtwangler_log2fc_nan", "ln"], ["furtwangler_log2fc_nan", "log10"], ["furtwangler_log2fc_nan", "log2"], ["furtwangler_log2fc_nan", "log2_times_0.5"], ["scope2_export", "ln"], ["scope2_export", "log10"], ["scope2_export", "log2"], ["scope2_export", "log2_times_0.5"]], "negatives_missing": [], "negatives_on_linear_labelled": [], "counts_unexpected": [["dusszachniewicz_maxquant", "-"], ["dusszachniewicz_maxquant", "missing_40"], ["dusszachniewicz_maxquant", "missing_70"], ["dusszachniewicz_maxquant", "subsample_20"], ["dusszachniewicz_maxquant", "times_1e3"], ["lungmap_bpd_fragpipe", "times_1e3"]], "counts_missing": [], "stray_negative_tables": ["furtwangler_batchcorr_norm", "msv000099294_hmc3", "msv000099294_microglia", "pbmc240_d` |
| B2_invariance | PASS | `{"comparisons": 166, "worst": {"bowley": 0.0, "moors": 0.0, "tail": 0.0, "level_spread": 0.0, "missing_share": 0.0, "row_median_spread": 0.0, "cell_bowley_iqr": 0.0, "decades": 0.0, "column_sum_cv": 0.0}, "failures": [], "failure_count": 0, "excluded_log2_with_negatives": ["pbmc240_diann", "pxd064083_t", "pxd064083_b", "msv000099294_hmc3", "msv000099294_microglia", "scope2_export", "furtwangler_batchcorr_norm", "furtwangler_log2fc_nan", "pxd049412_a549_singlecells", "cptac_ccrcc_tumor"]}` |
| B2_drift | FAIL | `{"flips": [], "linear_above_log_without_drift": true, "log_bowley_rises_with_missingness": false, "and_stays_below_linear": true}` |
| B2_separation | PASS | `{"auc": 0.9923, "linear_rows": 39, "log_rows": 50, "linear_margin_below_0": 2, "log_margin_above_0": 3}` |
| B2_conformal | PASS | `{"umbrella_k": {"58": null, "59": 1, "120": 2, "200": 5}, "simulation": {"59": {"k": 1, "share_miss_over_alpha": 0.043, "exact": 0.0485, "se": 0.0068, "mean_miss": 0.0161, "pass": true}, "120": {"k": 2, "share_miss_over_alpha": 0.013, "exact": 0.0155, "se": 0.0039, "mean_miss": 0.0159, "pass": true}, "200": {"k": 5, "share_miss_over_alpha": 0.021, "exact": 0.0264, "se": 0.0051, "mean_miss": 0.0244, "pass": true}}, "clopper_pearson_worst_vs_scipy": 5.845324224651449e-14}` |
| B2_verdicts_bank | FAIL | `{"problems": ["pxd021882_maxquant: linear (expected can't tell, too few columns)", "pxd043355_pd: unlike_either (predicted linear)", "furtwangler_log2_imputed: linear (predicted log)", "cong_mq_singlecells: linear (expected can't tell, too few columns)"], "wrong_class_alone": ["furtwangler_log2_imputed"], "verdicts": {"linear": 24, "unlike_either": 1, "log": 7, "cant_tell": 5}}` |
| B2_verdicts_variants | FAIL | `{"labelled": 571, "wrong": 17, "share_wrong": 0.0298, "wrong_items": ["furtwangler_log2_imputed/log2 (log -> linear)", "furtwangler_log2_imputed/log10 (log -> linear)", "furtwangler_log2_imputed/ln (log -> linear)", "furtwangler_log2_imputed/log2_plus1_after_min (log -> linear)", "furtwangler_log2_imputed/log2_plus10 (log -> linear)", "furtwangler_log2_imputed/log2_minus_min (log -> linear)", "furtwangler_log2_imputed/log2_times_0.5 (log -> linear)", "furtwangler_log2_imputed/log2_zeros_imputed (log -> linear)", "furtwangler_log2_imputed/subsample_50 (log -> linear)", "furtwangler_log2_imputed/subsample_300 (log -> linear)", "furtwangler_log2_imputed/missing_40 (log -> linear)", "furtwangler_log2_imputed/missing_70 (log -> linear)", "cptac_ccrcc_tumor/times_1e-6 (linear -> log)", "cptac_ccrcc_tumor/times_1e-3 (linear -> log)", "cptac_ccrcc_tumor/times_1e3 (linear -> log)", "cptac_ccrcc_t` |
| B2_design_size | recorded | `{"linear_rows": 39, "log_rows": 50, "deposits": 18, "forms": {"as deposited": 54, "constructed ln": 13, "constructed log2p1": 12, "constructed log2": 6, "constructed log10": 4}}` |

## Bank verdicts

| Table | Label | Columns | Gate | Verdict | Linear score (typ., prob.) | Log score (typ., prob.) | Thresholds | Reason |
|---|---|---|---|---|---|---|---|---|
| pbmc240_diann | linear | 238 |  | linear | 0.7568 (0.7568, 0.9932) | 0.0 (0.0, 0.0068) | 0.027 / 0.0417 |  |
| kabatnik_cra_timstofultra | linear | 25 |  | linear | 0.6486 (0.6486, 0.8601) | 0.0 (0.0, 0.1399) | 0.027 / 0.0417 |  |
| kabatnik_c3_region | linear | 27 |  | linear | 0.7297 (0.7297, 0.8883) | 0.0 (0.0, 0.1117) | 0.027 / 0.0417 |  |
| pxd073250_diann | linear | 557 |  | linear | 0.4444 (0.4444, 0.9836) | 0.0 (0.0, 0.0164) | 0.0278 / 0.0426 |  |
| pxd077946_diann_genes | linear | 40 |  | linear | 0.8988 (0.9474, 0.8988) | 0.0 (0.0, 0.1012) | 0.0263 / 0.0408 |  |
| zamore_diann | linear | 30 |  | linear | 0.7632 (0.7632, 0.9872) | 0.0 (0.0, 0.0128) | 0.0263 / 0.0408 |  |
| pxd064083_t | linear | 78 |  | linear | 0.9687 (1.0, 0.9687) | 0.0 (0.0, 0.0313) | 0.0286 / 0.04 |  |
| pxd064083_b | linear | 70 |  | linear | 0.961 (1.0, 0.961) | 0.0 (0.0, 0.039) | 0.0286 / 0.04 |  |
| pxd021882_maxquant | linear | 15 | counts | linear |  |  |  |  |
| dusszachniewicz_maxquant | linear | 45 | counts | linear |  |  |  |  |
| herrera2025_fragpipe | linear | 91 |  | linear | 0.4324 (0.4324, 0.997) | 0.0 (0.0, 0.003) | 0.027 / 0.0417 |  |
| lungmap_bpd_fragpipe | linear | 20 |  | linear | 0.7632 (0.7632, 0.97) | 0.0 (0.0, 0.03) | 0.0263 / 0.0408 |  |
| msv000099294_hmc3 | linear | 47 |  | linear | 0.9286 (0.9444, 0.9286) | 0.0 (0.0, 0.0714) | 0.0278 / 0.0426 |  |
| msv000099294_microglia | linear | 57 |  | linear | 0.9444 (0.9444, 0.9831) | 0.0 (0.0, 0.0169) | 0.0278 / 0.0426 |  |
| pxd061052_spectronaut | linear | 29 |  | linear | 0.0263 (0.0263, 0.9999) | 0.0 (0.0, 0.0001) | 0.0263 / 0.0408 |  |
| pxd043355_pd | linear | 59 |  | unlike_either | 0.0 (0.0, 0.9977) | 0.0 (0.0, 0.0023) | 0.027 / 0.0417 | neither reading fits: linear score 0 < 0.027 (typicality 0, probability 0.998); log score 0 < 0.0417 (typicality 0, probability 0.00227) |
| fulcher_tmt | linear | 2000 |  | linear | 0.1389 (0.1389, 0.9989) | 0.0 (0.0, 0.0011) | 0.0278 / 0.0426 |  |
| scope2_export | log | 1490 | negatives | log |  |  |  |  |
| khoury_column_normalized | log | 1651 |  | log | 0.0 (0.0, 0.0162) | 0.7021 (0.7021, 0.9838) | 0.0513 / 0.0426 |  |
| furtwangler_batchcorr | linear | 2000 |  | linear | 0.1818 (0.1818, 0.7618) | 0.0 (0.0, 0.2382) | 0.0303 / 0.0312 |  |
| furtwangler_batchcorr_norm | linear | 2000 |  | linear | 0.1818 (0.1818, 0.7518) | 0.0 (0.0, 0.2482) | 0.0303 / 0.0312 |  |
| furtwangler_log2 | log | 2000 |  | log | 0.0 (0.0, 0.0156) | 0.3438 (0.3438, 0.9844) | 0.0303 / 0.0312 |  |
| furtwangler_log2_imputed | log | 2000 |  | linear | 0.1212 (0.1212, 0.5726) | 0.0 (0.0, 0.4274) | 0.0303 / 0.0312 |  |
| furtwangler_log2_nan | log | 2000 |  | log | 0.0 (0.0, 0.0156) | 0.375 (0.375, 0.9844) | 0.0303 / 0.0312 |  |
| furtwangler_log2fc_nan | log | 2000 | negatives | log |  |  |  |  |
| furtwangler_log2_raw_sn | log | 2000 |  | log | 0.0 (0.0, 0.0141) | 0.9688 (0.9688, 0.9859) | 0.0303 / 0.0312 |  |
| pxd049412_hela250pg | linear | 3 |  | cant_tell |  |  |  | too few columns |
| pxd049412_a549_singlecells | linear | 50 |  | linear | 0.4324 (0.4324, 0.9949) | 0.0 (0.0, 0.0051) | 0.027 / 0.0417 |  |
| pxd069060_diann_report | linear | 12 |  | cant_tell |  |  |  | too few columns |
| quantms_pxd004452_ibaq | linear | 4 |  | cant_tell |  |  |  | too few columns |
| quantms_pxd004452_ribaq | log | 4 |  | cant_tell |  |  |  | too few columns |
| brunner_diann_1ng | linear | 15 |  | cant_tell |  |  |  | too few columns |
| brunner_mq_singlecells | linear | 51 |  | linear | 0.3243 (0.3243, 0.9927) | 0.0 (0.0, 0.0073) | 0.027 / 0.0417 |  |
| krull_singlecells | linear | 143 |  | linear | 0.0811 (0.0811, 0.9997) | 0.0 (0.0, 0.0003) | 0.027 / 0.0417 |  |
| cong_mq_singlecells | linear | 7 | counts | linear |  |  |  |  |
| hu2023_pd_k562 | linear | 72 |  | linear | 0.5946 (0.5946, 0.9272) | 0.0 (0.0, 0.0728) | 0.027 / 0.0417 |  |
| cptac_ccrcc_tumor | log | 110 | negatives | log |  |  |  |  |

## Verdicts by variant

| Variant | Right | Wrong | Can't tell | Unlike either |
|---|---|---|---|---|
| counts | 30 | 0 | 0 | 0 |
| ln | 29 | 1 | 0 | 0 |
| log10 | 29 | 1 | 0 | 0 |
| log2 | 29 | 1 | 0 | 0 |
| log2_minus_min | 27 | 1 | 2 | 0 |
| log2_plus10 | 27 | 1 | 2 | 0 |
| log2_plus1_after_min | 27 | 1 | 2 | 0 |
| log2_times_0.5 | 29 | 1 | 0 | 0 |
| log2_zeros_imputed | 27 | 1 | 2 | 0 |
| missing_40 | 28 | 1 | 0 | 1 |
| missing_70 | 28 | 1 | 0 | 1 |
| per_cell_cpm | 27 | 1 | 1 | 1 |
| per_cell_percent | 27 | 1 | 1 | 1 |
| per_protein_median | 0 | 0 | 28 | 2 |
| percentile_ranks | 0 | 0 | 21 | 7 |
| presence | 0 | 0 | 0 | 30 |
| ranks | 0 | 0 | 0 | 0 |
| subsample_20 | 28 | 0 | 0 | 1 |
| subsample_300 | 10 | 1 | 0 | 0 |
| subsample_50 | 19 | 1 | 0 | 1 |
| times_1e-3 | 26 | 1 | 2 | 1 |
| times_1e-6 | 26 | 1 | 2 | 1 |
| times_1e3 | 26 | 1 | 2 | 1 |
| zscore_genes | 0 | 0 | 0 | 0 |

## Drift: class medians of the core features

| Class / condition | Rows | bowley | moors | tail | level_spread |
|---|---|---|---|---|---|
| linear/missing_40 | 21 | 0.452 | 2.0494 | 33.7874 | 0.7139 |
| linear/missing_70 | 21 | 0.4495 | 2.0542 | 30.8937 | 0.6627 |
| linear/none | 21 | 0.452 | 2.0967 | 33.7874 | 0.7329 |
| linear/subsample_20 | 20 | 0.4602 | 2.0965 | 35.6183 | 0.7104 |
| linear/subsample_300 | 4 | 0.4476 | 1.786 | 16.4322 | 0.8352 |
| linear/subsample_50 | 13 | 0.4522 | 2.0085 | 34.8695 | 0.7646 |
| log/missing_40 | 26 | 0.0946 | 1.2701 | 2.4368 | -0.6027 |
| log/missing_70 | 26 | 0.0928 | 1.2485 | 2.4078 | -0.5993 |
| log/none | 26 | 0.0946 | 1.2862 | 2.4212 | -0.6002 |
| log/subsample_20 | 25 | 0.1008 | 1.2946 | 2.3339 | -0.4608 |
| log/subsample_300 | 9 | 0.0975 | 1.1055 | 1.7274 | -0.6099 |
| log/subsample_50 | 18 | 0.0915 | 1.2244 | 2.2952 | -0.5771 |

## Design rows

39 linear and 50 log rows from 18 deposits: linear/S1 21, linear/S2 14, linear/S3 4, log/S1 24, log/S2 17, log/S3 9.

Excluded (a gate decides them):

- pxd064083_t S1 constructed log2: the negatives gate decides it
- pxd064083_t S2 constructed ln: the negatives gate decides it
- pxd064083_b S1 constructed log10: the negatives gate decides it
- pxd064083_b S2 constructed log10: the negatives gate decides it
- dusszachniewicz_maxquant  : a gate decides the table
- scope2_export  : a gate decides the table
- furtwangler_log2fc_nan  : a gate decides the table
- cptac_ccrcc_tumor  : a gate decides the table

## Features of each bank table

| Table | bowley | moors | tail | level_spread | missing_share | row_median_spread | cell_bowley_iqr | decades | column_sum_cv |
|---|---|---|---|---|---|---|---|---|---|
| pbmc240_diann | 0.4445 | 2.0923 | 40.1378 | 0.8427 | 0.6278 | 3.0188 | 0.071 | 1.8401 | 0.9217 |
| kabatnik_cra_timstofultra | 0.4713 | 2.1411 | 21.0272 | 0.8394 | 0.0794 | 7.0265 | 0.0164 | 1.8431 | 0.0318 |
| kabatnik_c3_region | 0.4655 | 2.1912 | 21.2549 | 0.6468 | 0.2058 | 4.0975 | 0.0259 | 1.6345 | 0.1754 |
| pxd073250_diann | 0.3952 | 1.9967 | 26.3279 | 0.5787 | 0.8988 | 2.9005 | 0.084 | 1.4721 | 0.9972 |
| pxd077946_diann_genes | 0.4024 | 2.098 | 19.9506 | 0.5675 | 0.4506 | 2.1499 | 0.043 | 1.6129 | 0.7289 |
| zamore_diann | 0.4912 | 2.0967 | 44.0437 | 0.6978 | 0.2848 | 4.1013 | 0.0279 | 2.092 | 0.3515 |
| pxd064083_t | 0.452 | 1.9981 | 33.7874 | 0.7139 | 0.4387 | 2.9763 | 0.0507 | 1.6712 | 0.5602 |
| pxd064083_b | 0.4198 | 1.9034 | 36.8111 | 0.6944 | 0.4658 | 2.5737 | 0.0671 | 1.6383 | 0.8978 |
| herrera2025_fragpipe | 0.5407 | 2.2293 | 45.0633 | 0.8492 | 0.4688 | 1.0251 | 0.0396 | 2.2596 | 0.5729 |
| lungmap_bpd_fragpipe | 0.4495 | 1.9641 | 24.4604 | 0.648 | 0.7215 | 2.8522 | 0.0951 | 1.4692 | 0.3531 |
| msv000099294_hmc3 | 0.4176 | 2.0139 | 24.6122 | 0.7882 | 0.3511 | 2.3667 | 0.0275 | 1.5922 | 0.1731 |
| msv000099294_microglia | 0.4055 | 1.9602 | 39.2917 | 0.7329 | 0.5706 | 1.4043 | 0.039 | 1.4561 | 0.9155 |
| pxd061052_spectronaut | 0.5962 | 2.752 | 86.4693 | 0.8875 | 0.1935 | 4.1383 | 0.0158 | 2.9243 | 0.2857 |
| pxd043355_pd | 0.5765 | 2.2987 | 34.6373 | 0.7991 | 0.599 | 6.8023 | 0.0334 | 2.1574 | 2.9639 |
| fulcher_tmt | 0.4931 | 2.0312 | 59.0193 | 0.9108 | 0.5941 | 6.8227 | 0.0626 | 2.4629 | 0.3872 |
| khoury_column_normalized | 0.0951 | 1.2596 | 2.5799 | -0.7778 | 0.5874 | 1.9808 | 0.0451 | 0.2372 | 0.0619 |
| furtwangler_batchcorr | 0.4466 | 1.5483 | 6.1209 | 0.8733 | 0.6838 | 3.0168 | 0.0583 | 1.3852 | 0.2246 |
| furtwangler_batchcorr_norm | 0.4473 | 1.5476 | 6.1295 | 0.8433 | 0.6835 | 2.8098 | 0.0577 | 1.3866 | 0.0783 |
| furtwangler_log2 | 0.1246 | 1.0932 | 1.7296 | -0.8002 | 0.6839 | 2.46 | 0.0731 | 0.5005 | 0.0889 |
| furtwangler_log2_imputed | 0.3475 | 1.645 | 3.6849 | 0.5808 | 0.0 | 4.9077 | 0.0257 | 0.4652 | 0.0043 |
| furtwangler_log2_nan | 0.1237 | 1.0936 | 1.7287 | -0.7955 | 0.6842 | 2.4539 | 0.0723 | 0.5001 | 0.0895 |
| furtwangler_log2_raw_sn | 0.077 | 1.104 | 1.6466 | -0.6881 | 0.6834 | 1.0717 | 0.0707 | 0.5544 | 0.2015 |
| pxd049412_a549_singlecells | 0.5342 | 2.4202 | 38.555 | 0.684 | 0.4508 | 3.2821 | 0.0501 | 2.2773 | 1.2564 |
| brunner_mq_singlecells | 0.6118 | 2.4054 | 20.5902 | 0.7027 | 0.6025 | 0.968 | 0.0809 | 2.4456 | 0.4843 |
| krull_singlecells | 0.4061 | 2.4457 | 83.0985 | 0.597 | 0.6155 | 1.3738 | 0.095 | 1.7699 | 0.3712 |
| hu2023_pd_k562 | 0.5201 | 2.1222 | 20.6317 | 0.9395 | 0.1194 | 4.798 | 0.0247 | 2.1908 | 0.2515 |
