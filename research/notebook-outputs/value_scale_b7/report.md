# Value-scale diagnostics, B7: the sealed test, scored once

Judged 2026-11-09 12:25 by research/notebooks/value_scale_diagnostics.py from research/benchmark/value-scale-test/results.json, written by valuescale/corpus/score_test.py (62 s, commit e90d080). Expectations: valuescale/bank/expectations/b7.json, written before the scoring. Explained in notes.md beside this file.

## The rows

| row | result |
|---|---|
| B7_once | PASS |
| B7_counts | PASS |
| B7_guarantee | FAIL |
| B7_miss_ranges | FAIL |
| B7_wrong | FAIL |
| B7_primary | PASS |
| B7_whole_log | FAIL |
| B7_baselines | FAIL |
| B7_risk | PASS |
| B7_real_log | PASS |
| B7_foreign | PASS |

## Per calibrated stratum, one outcome per deposit (237 deposits, 624 subsamples)

| group | class | n | right | wrong | can't tell | unlike either | miss | miss rate [95% CI] | one-sided lower | guarantee (alpha 0.05) |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | linear | 237 | 224 | 1 | 1 | 11 | 12 | 0.051 [0.026, 0.087] | 0.0295 | holds |
| S1 | constructed_log | 237 | 214 | 0 | 1 | 22 | 22 | 0.093 [0.059, 0.137] | 0.0637 | CONTRADICTED |
| S2+S3 | linear | 67 | 67 | 0 | 0 | 0 | 0 | 0.000 [0.000, 0.054] | 0.0000 | holds |
| S2+S3 | constructed_log | 67 | 62 | 3 | 0 | 2 | 5 | 0.075 [0.025, 0.166] | 0.0299 | holds |

## Per protocol stratum, one outcome per subsample

| group | class | n | right | wrong | can't tell | unlike either | miss | miss rate [95% CI] | one-sided lower | guarantee (alpha 0.05) |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | linear | 237 | 224 | 1 | 1 | 11 | 12 | 0.051 [0.026, 0.087] | 0.0295 | holds |
| S1 | constructed_log | 237 | 214 | 0 | 1 | 22 | 22 | 0.093 [0.059, 0.137] | 0.0637 | CONTRADICTED |
| S2 | linear | 67 | 67 | 0 | 0 | 0 | 0 | 0.000 [0.000, 0.054] | 0.0000 | holds |
| S2 | constructed_log | 67 | 62 | 3 | 0 | 2 | 5 | 0.075 [0.025, 0.166] | 0.0299 | holds |
| S3 | linear | 8 | 8 | 0 | 0 | 0 | 0 | 0.000 [0.000, 0.369] | 0.0000 | holds |
| S3 | constructed_log | 8 | 7 | 1 | 0 | 0 | 1 | 0.125 [0.003, 0.527] | 0.0064 | holds |

## All subsamples

| group | class | n | right | wrong | can't tell | unlike either | miss | miss rate [95% CI] | one-sided lower | guarantee (alpha 0.05) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | linear | 312 | 299 | 1 | 1 | 11 | 12 | 0.038 [0.020, 0.066] | 0.0223 | holds |
| all | constructed_log | 312 | 283 | 4 | 1 | 24 | 28 | 0.090 [0.060, 0.127] | 0.0645 | CONTRADICTED |

## The primary comparison: the linear tables, whole

- The detector reads 236 of 237 linear (1 wrong); median-50 reads 233 linear (4 wrong).
- Right by the detector alone: 3; by median-50 alone: 0. Exact one-sided McNemar p = 0.1250.
- The detector's readings of the whole tables: {'linear': 236, 'log': 1}; of their constructed logs: {'linear': 22, 'log': 215}.

## Every baseline on the same whole tables

| rule | linear: right | wrong | no answer | error | constructed log: right | wrong | no answer | error |
|---|---|---|---|---|---|---|---|---|
| geo2r | 234 | 1 | 2 | 0 | 235 | 0 | 2 | 0 |
| expressanalyst | 234 | 1 | 2 | 0 | 235 | 0 | 2 | 0 |
| scgpt | 235 | 0 | 2 | 0 | 13 | 222 | 2 | 0 |
| omics_playground | 234 | 1 | 2 | 0 | 235 | 0 | 2 | 0 |
| proteopy | 234 | 1 | 2 | 0 | 235 | 0 | 2 | 0 |
| gemma | 233 | 1 | 3 | 0 | 114 | 0 | 123 | 0 |
| celltypist | 235 | 0 | 2 | 0 | 15 | 220 | 2 | 0 |
| cibersort | 234 | 1 | 2 | 0 | 235 | 0 | 2 | 0 |
| median_50 | 233 | 2 | 2 | 0 | 235 | 0 | 2 | 0 |

## Risk against coverage (subsamples)

| cut | coverage | risk |
|---|---|---|
| 0.5 | 0.934 | 0.0017 |
| 0.6 | 0.934 | 0.0017 |
| 0.7 | 0.933 | 0.0017 |
| 0.8 | 0.931 | 0.0017 |
| 0.9 | 0.918 | 0.0017 |
| 0.95 | 0.856 | 0.0019 |
| 0.99 | 0.526 | 0.0000 |

## By software

| group | class | n | right | wrong | can't tell | unlike either | miss | miss rate [95% CI] | one-sided lower | guarantee (alpha 0.05) |
|---|---|---|---|---|---|---|---|---|---|---|
| DIA-NN | linear | 96 | 95 | 0 | 0 | 1 | 1 | 0.010 [0.000, 0.057] | 0.0005 | holds |
| DIA-NN | constructed_log | 96 | 88 | 2 | 0 | 6 | 8 | 0.083 [0.037, 0.158] | 0.0421 | holds |
| FragPipe | linear | 11 | 9 | 0 | 0 | 2 | 2 | 0.182 [0.023, 0.518] | 0.0333 | holds |
| FragPipe | constructed_log | 11 | 7 | 1 | 0 | 3 | 4 | 0.364 [0.109, 0.692] | 0.1351 | CONTRADICTED |
| MaxQuant | linear | 166 | 165 | 0 | 0 | 1 | 1 | 0.006 [0.000, 0.033] | 0.0003 | holds |
| MaxQuant | constructed_log | 166 | 150 | 1 | 0 | 15 | 16 | 0.096 [0.056, 0.152] | 0.0614 | CONTRADICTED |
| Proteome Discoverer | linear | 6 | 5 | 0 | 0 | 1 | 1 | 0.167 [0.004, 0.641] | 0.0085 | holds |
| Proteome Discoverer | constructed_log | 6 | 6 | 0 | 0 | 0 | 0 | 0.000 [0.000, 0.459] | 0.0000 | holds |
| Spectronaut | linear | 33 | 25 | 1 | 1 | 6 | 7 | 0.212 [0.090, 0.389] | 0.1040 | CONTRADICTED |
| Spectronaut | constructed_log | 33 | 32 | 0 | 1 | 0 | 0 | 0.000 [0.000, 0.106] | 0.0000 | holds |

## By instrument family

| group | class | n | right | wrong | can't tell | unlike either | miss | miss rate [95% CI] | one-sided lower | guarantee (alpha 0.05) |
|---|---|---|---|---|---|---|---|---|---|---|
| Orbitrap | linear | 238 | 228 | 1 | 1 | 8 | 9 | 0.038 [0.017, 0.071] | 0.0199 | holds |
| Orbitrap | constructed_log | 238 | 219 | 1 | 1 | 17 | 18 | 0.076 [0.045, 0.117] | 0.0495 | holds |
| SCIEX TOF | linear | 3 | 3 | 0 | 0 | 0 | 0 | 0.000 [0.000, 0.708] | 0.0000 | holds |
| SCIEX TOF | constructed_log | 3 | 3 | 0 | 0 | 0 | 0 | 0.000 [0.000, 0.708] | 0.0000 | holds |
| other | linear | 5 | 5 | 0 | 0 | 0 | 0 | 0.000 [0.000, 0.522] | 0.0000 | holds |
| other | constructed_log | 5 | 5 | 0 | 0 | 0 | 0 | 0.000 [0.000, 0.522] | 0.0000 | holds |
| timsTOF | linear | 66 | 63 | 0 | 0 | 3 | 3 | 0.045 [0.009, 0.127] | 0.0125 | holds |
| timsTOF | constructed_log | 66 | 56 | 3 | 0 | 7 | 10 | 0.152 [0.075, 0.261] | 0.0846 | CONTRADICTED |

## The foreign tables (calibration deposits)

| kind | n | verdicts | gates | warned |
|---|---|---|---|---|
| zscore_proteins | 218 | {'log': 218} | {'negatives': 218} | 0 |
| presence | 218 | {'unlike_either': 218} | {'none': 218} | 0 |
| percentile_ranks | 218 | {'cant_tell': 185, 'log': 33} | {'none': 218} | 15 |

