# B1, a probe written after the run

Not an expectation row: written after B1's report, to explain its one failed row (`notes.md`). Script: `research/notebooks/value_scale_b1_posthoc.py`. "Gene correlation" is the per-gene Pearson correlation between x and log2(x) over the gene's positive values (genes with at least 5), the statistic of B2's "can't tell" check; "at 0.98" is the share of genes at or above that check's bar. "Changed" is B1's share of best guesses the wrong reading changes (log tables: read linear; linear tables: read as log, zeros measured).

| Table | Label | Changed | Answered, right reading | Median value | 5th percentile | Below 1 | Gene correlation | At 0.98 | Genes |
|---|---|---|---|---|---|---|---|---|---|
| zamore_diann | linear | 0.067 | 0.867 | 6.41e+05 | 8.06e+04 | 0.000 | 0.9685 | 0.32 | 3110 |
| pxd077946_diann_genes | linear | 0.125 | 0.500 | 2.56e+03 | 558 | 0.000 | 0.9681 | 0.29 | 2967 |
| kabatnik_c3_region | linear | 0.148 | 0.481 | 1e+03 | 240 | 0.000 | 0.9839 | 0.60 | 4633 |
| pbmc240_diann | linear | 0.155 | 0.731 | 4.78e+03 | 743 | 0.000 | 0.9520 | 0.10 | 2718 |
| dusszachniewicz_maxquant | linear | 0.156 | 0.444 | 3.48e+08 | 4.01e+07 | 0.000 | 0.9435 | 0.11 | 7846 |
| kabatnik_cra_timstofultra | linear | 0.160 | 0.400 | 3.8e+04 | 6.86e+03 | 0.000 | 0.9902 | 0.77 | 7758 |
| hu2023_pd_k562 | linear | 0.194 | 0.056 | 1.19e+04 | 1.21e+03 | 0.000 | 0.9375 | 0.01 | 1372 |
| lungmap_bpd_fragpipe | linear | 0.200 | 0.500 | 2.28e+07 | 6.05e+06 | 0.000 | 0.9802 | 0.51 | 2016 |
| pxd061052_spectronaut | linear | 0.207 | 0.241 | 1.07e+04 | 522 | 0.000 | 0.9297 | 0.04 | 3441 |
| msv000099294_hmc3 | linear | 0.213 | 0.319 | 5.75 | 1.49 | 0.007 | 0.9662 | 0.18 | 3204 |
| fulcher_tmt | linear | 0.215 | 0.678 | 2.41e+05 | 1.23e+04 | 0.000 | 0.9279 | 0.05 | 1661 |
| pxd049412_a549_singlecells | linear | 0.220 | 0.100 | 268 | 27.9 | 0.001 | 0.9380 | 0.08 | 5553 |
| msv000099294_microglia | linear | 0.246 | 0.246 | 3.93 | 1.27 | 0.009 | 0.9620 | 0.20 | 1886 |
| brunner_mq_singlecells | linear | 0.255 | 0.059 | 1.41e+05 | 7.43e+03 | 0.000 | 0.8533 | 0.02 | 7536 |
| pxd073250_diann | linear | 0.277 | 0.305 | 3.14e+03 | 407 | 0.000 | 0.9687 | 0.37 | 5064 |
| pxd043355_pd | linear | 0.390 | 0.441 | 1.7e+04 | 1.33e+03 | 0.000 | 0.9696 | 0.37 | 4992 |
| krull_singlecells | linear | 0.413 | 0.336 | 547 | 125 | 0.000 | 0.9326 | 0.05 | 1243 |
| pxd064083_b | linear | 0.471 | 0.371 | 7.92 | 1.55 | 0.016 | 0.9463 | 0.12 | 2197 |
| herrera2025_fragpipe | linear | 0.549 | 0.418 | 4.18e+04 | 3.99e+03 | 0.000 | 0.8573 | 0.02 | 4781 |
| pxd064083_t | linear | 0.551 | 0.513 | 6.99 | 1.41 | 0.020 | 0.9595 | 0.22 | 2162 |
| furtwangler_batchcorr | linear | 0.832 | 0.336 | 10.7 | 2.8 | 0.000 | 0.9570 | 0.15 | 2876 |
| furtwangler_batchcorr_norm | linear | 0.893 | 0.402 | 10.6 | 2.76 | 0.000 | 0.9629 | 0.19 | 2934 |
| khoury_column_normalized | log | 0.012 | 0.930 | 10.6 | 8.11 | 0.000 | 0.9976 | 0.99 | 3485 |
| furtwangler_log2_imputed | log | 0.080 | 0.244 | 2.43 | 1.79 | 0.000 | 0.9940 | 0.98 | 2934 |
| furtwangler_log2_nan | log | 0.124 | 0.401 | 3.54 | 1.91 | 0.000 | 0.9912 | 0.97 | 2934 |
| furtwangler_log2 | log | 0.128 | 0.403 | 3.54 | 1.91 | 0.000 | 0.9912 | 0.97 | 2934 |
| furtwangler_log2_raw_sn | log | 0.140 | 0.487 | 3.69 | 1.77 | 0.001 | 0.9859 | 0.74 | 2934 |

Across all 28 tables scored under a wrong reading (pxd064083_union included), the Spearman correlation between the share answered under the right reading and the share changed is -0.26 (p = 0.17).
