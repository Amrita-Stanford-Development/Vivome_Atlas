# B4: the calibration of the protein detector

Run 2026-11-07T17:15:01 (274 s; the design part 2026-11-07T16:43:05, 182 s), by research/notebooks/value_scale_calibrate.py. Expectations: valuescale/bank/expectations/b4.json, written before the run.

| Row | Result | Expected |
|---|---|---|
| B4_model | pass | B2's design rows rebuilt from the bank and fitted give a model identical to B2's full_model (research/notebook-outputs/value_scale_b2/report.json): every number equal after the JSON round trip. |
| B4_no_gaps | **fail**, accepted by the owner | Design part. On the bank tables as B2 loads them, the no-gaps rule (no missing value after the gates' clean-up, on a table no gate decides) holds on exactly one: furtwangler_log2_imputed. Among B2's variants of the bank tables, it fires only on variants of furtwangler_log2_imputed. If this fails, the calibration does not run and the owner decides. |
| B4_calibration_size | pass | S1: 218 linear subsamples and 218 constructed log variants. S2+S3: 68 deposits (65 with an S2 subsample alone, 3 with S2 and S3), so n = 68 per class. k = 6 in S1 and 1 in S2+S3. Every subsample has its per-cell statistics: none scores 0 for want of them. |
| B4_thresholds | pass | All four thresholds (linear and log, in S1 and S2+S3) are above 0.05. |
| B4_typicality_zero | pass | The finding behind amendment 5 holds on the calibration split: in each stratum, at least one linear calibration deposit has a linear typicality rank of 0. |
| B4_calibration_coverage | pass | On the calibration split itself, each class misses at most k - 1 deposits per stratum (S1 at most 5 of 218; S2+S3 none of 68): the thresholds are the k-th smallest scores. |
| B4_gated | pass | Recorded, per class and stratum: the share of calibration subsamples each gate and rule would decide. Predicted: the negatives gate decides no linear subsample (no kept linear table holds a negative), and the counts gate decides no constructed log variant. |
| B4_bank_verdicts | pass | Linear: pbmc240_diann, kabatnik_cra_timstofultra, kabatnik_c3_region, pxd073250_diann, pxd077946_diann_genes, zamore_diann, pxd064083_t, pxd064083_b, herrera2025_fragpipe, lungmap_bpd_fragpipe, msv000099294_hmc3, msv000099294_microglia, pxd061052_spectronaut, pxd043355_pd (B2: unlike either), fulcher_tmt, furtwangler_batchcorr, furtwangler_batchcorr_norm, pxd049412_a549_singlecells, brunner_mq_singlecells, krull_singlecells, hu2023_pd_k562. Log: khoury_column_normalized, furtwangler_log2, furtwangler_log2_nan, furtwangler_log2_raw_sn. Can't tell by the no-gaps rule: furtwangler_log2_imputed. Every other bank table gets B2's verdict and reason (the gates and the size rule). Among the tables the score decides, the typicality warning fires on pxd043355_pd alone. |
| B4_bank_variants | pass | Of B2's labelled variants, at most 5% are given the other class alone. The foreign variants as in B2: zscore_genes log by the negatives gate, ranks linear by the counts gate, presence unlike either (no spread); percentile_ranks recorded. |
| B4_rehearsal | pass | score_test.py --rehearse runs end to end on the calibration split: each deposit counted once per class and stratum, the counts adding up, Clopper-Pearson intervals, and nothing written that marks the test as scored. |
| B4_baselines | pass | Every baseline in valuescale/baselines.py answers linear, log or no answer on every bank table, without an error. median_50 reads log on the six small-scale linear tables B2 names (pxd064083_t, pxd064083_b, msv000099294_hmc3, msv000099294_microglia, furtwangler_batchcorr, furtwangler_batchcorr_norm) and on the four real log tables without negatives. The other readings are recorded. |
| B4_detect | pass | valuescale.detect on PBMC240 (service/examples/pbmc240_proteins_raw.tsv, 238 cells) answers linear in S2+S3 with the calibration's id and guarantee, in under 3 s on this PC. |

## The calibration

`protein-v1`, alpha 0.05, delta 0.05, corpus sha256 `16ebf9548e2bd13aa9d946b3d847b614b73e95f1387b9a0f6a280ed983541f17` (218 deposits).

| Stratum | Columns | Class | n | k | Threshold |
|---|---|---|---|---|---|
| S1 | 20 to 49 | linear | 218 | 6 | 0.8122 |
| S1 | 20 to 49 | log | 218 | 6 | 0.9309 |
| S2+S3 | 50 to 2000 | linear | 68 | 1 | 0.1142 |
| S2+S3 | 50 to 2000 | log | 68 | 1 | 0.9189 |

Calibration deposits under their class's threshold:

- S1/linear: 5 of 218 (k = 6)
- S1/log: 5 of 218 (k = 6)
- S2+S3/linear: 0 of 68 (k = 1)
- S2+S3/log: 0 of 68 (k = 1)

What would decide each calibration subsample before its score (B4_gated):

- linear/S1: counts 84 (39%), no gaps 4 (2%), the score 130 (60%)
- linear/S2: counts 15 (22%), no gaps 2 (3%), the score 51 (75%)
- linear/S3: the score 3 (100%)
- log/S1: no gaps 4 (2%), the score 214 (98%)
- log/S2: no gaps 2 (3%), the score 66 (97%)
- log/S3: the score 3 (100%)

## The bank

| Table | Label | Columns | Verdict | B2 | Reason | Warning |
|---|---|---|---|---|---|---|
| pbmc240_diann | linear | 238 | linear | linear |  |  |
| kabatnik_cra_timstofultra | linear | 25 | linear | linear |  |  |
| kabatnik_c3_region | linear | 27 | linear | linear |  |  |
| pxd073250_diann | linear | 557 | linear | linear |  |  |
| pxd077946_diann_genes | linear | 40 | linear | linear |  |  |
| zamore_diann | linear | 30 | linear | linear |  |  |
| pxd064083_t | linear | 78 | linear | linear |  |  |
| pxd064083_b | linear | 70 | linear | linear |  |  |
| pxd021882_maxquant | linear | 15 | linear | linear |  |  |
| dusszachniewicz_maxquant | linear | 45 | linear | linear |  |  |
| herrera2025_fragpipe | linear | 91 | linear | linear |  |  |
| lungmap_bpd_fragpipe | linear | 20 | linear | linear |  |  |
| msv000099294_hmc3 | linear | 47 | linear | linear |  |  |
| msv000099294_microglia | linear | 57 | linear | linear |  |  |
| pxd061052_spectronaut | linear | 29 | linear | linear |  |  |
| pxd043355_pd | linear | 59 | linear | unlike_either |  | yes |
| fulcher_tmt | linear | 2000 | linear | linear |  |  |
| scope2_export | log | 1490 | log | log |  |  |
| khoury_column_normalized | log | 1651 | log | log |  |  |
| furtwangler_batchcorr | linear | 2000 | linear | linear |  |  |
| furtwangler_batchcorr_norm | linear | 2000 | linear | linear |  |  |
| furtwangler_log2 | log | 2000 | log | log |  |  |
| furtwangler_log2_imputed | log | 2000 | cant_tell | linear | no value is missing: the table may have been filled in (imputed), and filled-in values can make a log table look linear |  |
| furtwangler_log2_nan | log | 2000 | log | log |  |  |
| furtwangler_log2fc_nan | log | 2000 | log | log |  |  |
| furtwangler_log2_raw_sn | log | 2000 | log | log |  |  |
| pxd049412_hela250pg | linear | 3 | cant_tell | cant_tell | too few columns |  |
| pxd049412_a549_singlecells | linear | 50 | linear | linear |  |  |
| pxd069060_diann_report | linear | 12 | cant_tell | cant_tell | too few columns |  |
| quantms_pxd004452_ibaq | linear | 4 | cant_tell | cant_tell | too few columns |  |
| quantms_pxd004452_ribaq | log | 4 | cant_tell | cant_tell | too few columns |  |
| brunner_diann_1ng | linear | 15 | cant_tell | cant_tell | too few columns |  |
| brunner_mq_singlecells | linear | 51 | linear | linear |  |  |
| krull_singlecells | linear | 143 | linear | linear |  |  |
| cong_mq_singlecells | linear | 7 | linear | linear |  |  |
| hu2023_pd_k562 | linear | 72 | linear | linear |  |  |
| cptac_ccrcc_tumor | log | 110 | log | log |  |  |

Variants: 16 of 571 labelled variants given the other class alone (2.8%); 44 verdicts changed from B2.

- pxd073250_diann/log2 (log -> linear)
- pxd073250_diann/log10 (log -> linear)
- pxd073250_diann/ln (log -> linear)
- pxd073250_diann/log2_plus1_after_min (log -> linear)
- pxd073250_diann/log2_plus10 (log -> linear)
- pxd073250_diann/log2_minus_min (log -> linear)
- pxd073250_diann/log2_times_0.5 (log -> linear)
- pxd073250_diann/log2_zeros_imputed (log -> linear)
- furtwangler_log2_imputed/missing_40 (log -> linear)
- furtwangler_log2fc_nan/per_cell_cpm (linear -> log)
- furtwangler_log2fc_nan/per_cell_percent (linear -> log)
- cptac_ccrcc_tumor/times_1e-6 (linear -> log)
- cptac_ccrcc_tumor/times_1e-3 (linear -> log)
- cptac_ccrcc_tumor/times_1e3 (linear -> log)
- cptac_ccrcc_tumor/per_cell_cpm (linear -> log)
- cptac_ccrcc_tumor/per_cell_percent (linear -> log)

## PBMC240

3100 x 238: linear in S2+S3, 0.086 s.

> For tables like the 68 calibration deposits of this stratum (public processed protein tables, linear as deposited, and constructed logs of them), the right reading is missing from the answer at most 5% of the time, with 95% confidence (protein-v1).

## The rehearsal (calibration split; checks the code, not the method)

| Stratum | Class | n | Right | Wrong | Can't tell | Unlike either | Miss (95% CI) |
|---|---|---|---|---|---|---|---|
| S1 | linear | 218 | 210 | 0 | 4 | 4 | 4 (0.005 to 0.046) |
| S1 | constructed_log | 218 | 209 | 0 | 4 | 5 | 5 (0.007 to 0.053) |
| S2+S3 | linear | 68 | 66 | 0 | 2 | 0 | 0 (0.000 to 0.053) |
| S2+S3 | constructed_log | 68 | 66 | 0 | 2 | 0 | 0 (0.000 to 0.053) |

Whole linear tables: the detector reads 0 of 218 wrong, median-50 4; one-sided McNemar p = 0.0625.

| Baseline | Linear: right / wrong / no answer | Constructed log: right / wrong / no answer |
|---|---|---|
| geo2r | 218 / 0 / 0 | 218 / 0 / 0 |
| expressanalyst | 218 / 0 / 0 | 218 / 0 / 0 |
| scgpt | 218 / 0 / 0 | 15 / 203 / 0 |
| omics_playground | 218 / 0 / 0 | 218 / 0 / 0 |
| proteopy | 218 / 0 / 0 | 218 / 0 / 0 |
| gemma | 217 / 1 / 0 | 102 / 0 / 116 |
| celltypist | 218 / 0 / 0 | 20 / 198 / 0 |
| cibersort | 218 / 0 / 0 | 218 / 0 / 0 |
| median_50 | 214 / 4 / 0 | 218 / 0 / 0 |
