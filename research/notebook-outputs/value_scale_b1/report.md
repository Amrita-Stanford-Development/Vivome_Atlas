# B1: what each mistake costs

Run 2026-11-03, v4.1, every bank table as Phase A traced it, plus pxd064083_union. Expectations and decision rules: `valuescale/bank/expectations/b1.json`, written before this script existed. "Changed" is the share of cells whose best guess differs from the table's right reading.

## Expectations

| Row | Result | Detail |
|---|---|---|
| B1_invariants | PASS | `{"failures": {}}` |
| B1_refusals | PASS | `{"wrong": []}` |
| B1_direction | PASS | `{"median_log_read_linear": 0.124, "median_linear_read_as_log": 0.22, "n_log": 5, "n_linear": 23}` |
| B1_log_read_linear_small | FAIL | `{"median_log_read_linear": 0.124}` |
| B1_zeros | PASS | `{"missing_better_on": ["furtwangler_batchcorr", "furtwangler_batchcorr_norm", "furtwangler_log2", "furtwangler_log2_raw_sn", "pxd064083_b", "pxd064083_t", "pxd064083_union"], "measured_at_least_as_good_on": [], "linear_tables_only": {"missing_better": 5, "of": 5}}` |
| B1_accuracy | PASS | `{"tables": {"pbmc240_diann": {"right": 52.99, "wrong": 45.01, "pass": true}, "fulcher_tmt": {"right": 65.94, "wrong": 67.32, "pass": true}, "pxd064083_union": {"right": 85.95, "wrong": 85.16, "pass": true}}}` |

## Decisions, by the rules written first

- **cant_tell_reading:** linear
- **zeros:** missing under both readings

## Per table

| Table | Label | Cells | Zeros | Right | linear: answered / changed / acc | log, 0 measured | log, 0 missing |
|---|---|---|---|---|---|---|---|
| pbmc240_diann | linear | 238 | 0.0% | linear | 73.1% / 0.0% / 52.99 | 72.3% / 15.6% / 45.01 | 72.3% / 15.6% / 45.01 |
| kabatnik_cra_timstofultra | linear | 25 | 0.0% | linear | 40.0% / 0.0% | 44.0% / 16.0% | 44.0% / 16.0% |
| kabatnik_c3_region | linear | 27 | 0.0% | linear | 48.1% / 0.0% | 40.7% / 14.8% | 40.7% / 14.8% |
| pxd073250_diann | linear | 557 | 0.0% | linear | 30.5% / 0.0% | 28.5% / 27.7% | 28.5% / 27.7% |
| pxd077946_diann_genes | linear | 40 | 0.0% | linear | 50.0% / 0.0% | 45.0% / 12.5% | 45.0% / 12.5% |
| zamore_diann | linear | 30 | 0.0% | linear | 86.7% / 0.0% | 96.7% / 6.7% | 96.7% / 6.7% |
| pxd064083_t | linear | 78 | 43.9% | linear | 51.3% / 0.0% | 60.3% / 55.1% | 51.3% / 30.8% |
| pxd064083_b | linear | 70 | 46.6% | linear | 37.1% / 0.0% | 28.6% / 47.1% | 32.9% / 24.3% |
| pxd021882_maxquant | linear | refused by validation | | | | | |
| dusszachniewicz_maxquant | linear | 45 | 0.0% | linear | 44.4% / 0.0% | 48.9% / 15.6% | 48.9% / 15.6% |
| herrera2025_fragpipe | linear | 91 | 0.0% | linear | 41.8% / 0.0% | 53.8% / 54.9% | 53.8% / 54.9% |
| lungmap_bpd_fragpipe | linear | 20 | 0.0% | linear | 50.0% / 0.0% | 35.0% / 20.0% | 35.0% / 20.0% |
| msv000099294_hmc3 | linear | 47 | 0.0% | linear | 31.9% / 0.0% | 34.0% / 21.3% | 34.0% / 21.3% |
| msv000099294_microglia | linear | 57 | 0.0% | linear | 24.6% / 0.0% | 33.3% / 24.6% | 33.3% / 24.6% |
| pxd061052_spectronaut | linear | 29 | 0.0% | linear | 24.1% / 0.0% | 27.6% / 20.7% | 27.6% / 20.7% |
| pxd043355_pd | linear | 59 | 0.0% | linear | 44.1% / 0.0% | 83.0% / 39.0% | 83.0% / 39.0% |
| fulcher_tmt | linear | 2000 | 0.0% | linear | 67.8% / 0.0% / 65.94 | 64.1% / 21.6% / 67.32 | 64.1% / 21.6% / 67.32 |
| scope2_export | log | 1490 | 0.0% | log_zeros_missing | refused | 52.9% / 0.0% | 52.9% / 0.0% |
| khoury_column_normalized | log | 1651 | 0.0% | log_zeros_missing | 93.1% / 1.2% | 93.0% / 0.0% | 93.0% / 0.0% |
| furtwangler_batchcorr | linear | 2000 | 68.4% | linear | 33.6% / 0.0% | 39.6% / 83.2% | 31.9% / 28.1% |
| furtwangler_batchcorr_norm | linear | 2000 | 68.3% | linear | 40.2% / 0.0% | 31.7% / 89.3% | 39.4% / 26.5% |
| furtwangler_log2 | log | 2000 | 68.4% | log_zeros_missing | 40.1% / 12.8% | 26.2% / 92.5% | 40.3% / 0.0% |
| furtwangler_log2_imputed | log | 2000 | 0.0% | log_zeros_missing | 24.0% / 8.0% | 24.4% / 0.0% | 24.4% / 0.0% |
| furtwangler_log2_nan | log | 2000 | 0.0% | log_zeros_missing | 39.5% / 12.4% | 40.1% / 0.0% | 40.1% / 0.0% |
| furtwangler_log2fc_nan | log | 2000 | 0.0% | log_zeros_missing | refused | 39.6% / 0.0% | 39.6% / 0.0% |
| furtwangler_log2_raw_sn | log | 2000 | 68.3% | log_zeros_missing | 50.3% / 14.0% | 47.3% / 74.5% | 48.8% / 0.0% |
| pxd049412_hela250pg | linear | refused by validation | | | | | |
| pxd049412_a549_singlecells | linear | 50 | 0.0% | linear | 10.0% / 0.0% | 22.0% / 22.0% | 22.0% / 22.0% |
| pxd069060_diann_report | linear | refused by validation | | | | | |
| quantms_pxd004452_ibaq | linear | refused by validation | | | | | |
| quantms_pxd004452_ribaq | log | refused by validation | | | | | |
| brunner_diann_1ng | linear | refused by validation | | | | | |
| brunner_mq_singlecells | linear | 51 | 0.0% | linear | 5.9% / 0.0% | 41.2% / 25.5% | 41.2% / 25.5% |
| krull_singlecells | linear | 143 | 0.1% | linear | 33.6% / 0.0% | 35.7% / 41.3% | 37.1% / 39.9% |
| cong_mq_singlecells | linear | refused by validation | | | | | |
| hu2023_pd_k562 | linear | 72 | 0.0% | linear | 5.6% / 0.0% | 4.2% / 19.4% | 4.2% / 19.4% |
| cptac_ccrcc_tumor | log | 110 | 0.0% | log_zeros_missing | refused | 42.7% / 0.0% | 42.7% / 0.0% |
| pxd064083_union | linear | 148 | 45.1% | linear | 68.9% / 0.0% / 85.95 | 77.0% / 29.0% / 85.16 | 71.6% / 28.4% / 73.26 |
