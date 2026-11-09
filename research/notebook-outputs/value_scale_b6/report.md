# Value-scale diagnostics, B6: the staged Space against this repository's service

Run 2026-11-09 11:57 by research/notebooks/value_scale_diagnostics.py (683 s). Expectations: valuescale/bank/expectations/b6.json, written before the run. Each side ran in its own fresh interpreter with the hosted settings: the Space from deploy/huggingface/space alone, the repository's service from the repository root. Explained in notes.md beside this file.

## The rows

| row | result |
|---|---|
| B6_build | PASS |
| B6_isolated | PASS |
| B6_pipeline | PASS |
| B6_status | PASS |
| B6_app | PASS |
| B6_zeros | PASS |
| B6_since_b5 | PASS |

## The build

- build_space.py exit 0: v4.1: 32 model files (582 MB), 32 Python files (31 modules import from the staged folder alone), 10 in Git LFS; total 583 MB in deploy/huggingface/space/
- space_manifest.json: commit fdf31f576fcbcdad17085bf5fc0017fbde522b1d (HEAD fdf31f576fcbcdad17085bf5fc0017fbde522b1d), uncommitted_changes False, pipeline_version v4.1
- 64 staged files under service/ and valuescale/; differing from the repository's: none
- the staged valuescale/: valuescale/__init__.py, valuescale/baselines.py, valuescale/calibrated.py, valuescale/calibration/protein-v1.json, valuescale/conformal.py, valuescale/gates.py, valuescale/method.py, valuescale/report.py, valuescale/score.py, valuescale/statistics.py

## Where each child imported from

| child | service | valuescale |
|---|---|---|
| pipeline space | D:\Project\Vivome\Vivome_Atlas\deploy\huggingface\space\service\__init__.py | D:\Project\Vivome\Vivome_Atlas\deploy\huggingface\space\valuescale\__init__.py |
| pipeline repo | D:\Project\Vivome\Vivome_Atlas\service\__init__.py | D:\Project\Vivome\Vivome_Atlas\valuescale\__init__.py |
| server space | D:\Project\Vivome\Vivome_Atlas\deploy\huggingface\space\service\__init__.py | D:\Project\Vivome\Vivome_Atlas\deploy\huggingface\space\valuescale\__init__.py |
| server repo | D:\Project\Vivome\Vivome_Atlas\service\__init__.py | D:\Project\Vivome\Vivome_Atlas\valuescale\__init__.py |

## Every bank table (37)

| table | label | cells | sent as | MiB | pipeline prot | pipeline rna | app prot (Space/repo) | app rna (Space/repo) | verdict | a 0 read as | summary vs B5 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pbmc240_diann | linear | 238 | its file | 2.63 | same | same | 200/200 same | 200/200 same | linear |  | same |
| kabatnik_cra_timstofultra | linear | 25 | its file | 2.12 | same | same | 200/200 same | 200/200 same | linear |  | same |
| kabatnik_c3_region | linear | 27 | its file | 0.91 | same | same | 200/200 same | 200/200 same | linear |  | same |
| pxd073250_diann | linear | 557 | its file | 5.79 | same | same | 200/200 same | 200/200 same | linear |  | same |
| pxd077946_diann_genes | linear | 40 | its file | 0.62 | same | same | 200/200 same | 200/200 same | linear |  | same |
| zamore_diann | linear | 30 | its file | 0.85 | same | same | 200/200 same | 200/200 same | linear |  | same |
| pxd064083_t | linear | 78 | its file | 2.11 | same | same | 200/200 same | 200/200 same | linear | missing | same |
| pxd064083_b | linear | 70 | its file | 1.84 | same | same | 200/200 same | 200/200 same | linear | missing | same |
| pxd021882_maxquant | linear | 15 | its file | 6.62 | same | same | 400/400 same | 400/400 same | refused by validation |  |  |
| dusszachniewicz_maxquant | linear | 45 | its file | 90.24 | same | same | over 31 MiB, not sent | over 31 MiB, not sent | linear |  | same |
| herrera2025_fragpipe | linear | 91 | its file | 6.5 | same | same | 200/200 same | 200/200 same | linear |  | same |
| lungmap_bpd_fragpipe | linear | 20 | its file | 2.69 | same | same | 200/200 same | 200/200 same | linear |  | same |
| msv000099294_hmc3 | linear | 47 | its file | 2.0 | same | same | 200/200 same | 200/200 same | linear |  | same |
| msv000099294_microglia | linear | 57 | its file | 1.23 | same | same | 200/200 same | 200/200 same | linear |  | same |
| pxd061052_spectronaut | linear | 29 | its file | 4.76 | same | same | 200/200 same | 200/200 same | linear |  | same |
| pxd043355_pd | linear | 59 | its file | 1.63 | same | same | 200/200 same | 200/200 same | linear |  | same |
| fulcher_tmt | linear | 2000 | its 2,000-cell subsample | 15.65 | same | same | 200/200 same | 200/200 same | linear |  | same |
| scope2_export | log | 1490 | its file | 53.16 | same | same | over 31 MiB, not sent | over 31 MiB, not sent | log |  | same |
| khoury_column_normalized | log | 1651 | its file | 44.44 | same | same | over 31 MiB, not sent | over 31 MiB, not sent | log |  | same |
| furtwangler_batchcorr | linear | 2000 | its 2,000-cell subsample | 26.86 | same | same | 200/200 same | 200/200 same | linear | missing | same |
| furtwangler_batchcorr_norm | linear | 2000 | its 2,000-cell subsample | 26.97 | same | same | 200/200 same | 200/200 same | linear | missing | same |
| furtwangler_log2 | log | 2000 | its 2,000-cell subsample | 26.94 | same | same | 200/200 same | 200/200 same | log | missing | same |
| furtwangler_log2_imputed | log | 2000 | its 2,000-cell subsample | 60.97 | same | same | over 31 MiB, not sent | over 31 MiB, not sent | cant_tell |  | same |
| furtwangler_log2_nan | log | 2000 | its 2,000-cell subsample | 23.1 | same | same | 200/200 same | 200/200 same | log |  | same |
| furtwangler_log2fc_nan | log | 2000 | its 2,000-cell subsample | 26.18 | same | same | 200/200 same | 200/200 same | log | measured | same |
| furtwangler_log2_raw_sn | log | 2000 | its 2,000-cell subsample | 26.75 | same | same | 200/200 same | 200/200 same | log | missing | same |
| pxd049412_hela250pg | linear | 3 | its file | 1.94 | same | same | 400/400 same | 400/400 same | refused by validation |  |  |
| pxd049412_a549_singlecells | linear | 50 | its file | 15.06 | same | same | 200/200 same | 200/200 same | linear |  | same |
| pxd069060_diann_report | linear | 12 | its file | 0.13 | same | same | 400/400 same | 400/400 same | refused by validation |  |  |
| quantms_pxd004452_ibaq | linear | 4 | its file | 0.36 | same | same | 400/400 same | 400/400 same | refused by validation |  |  |
| quantms_pxd004452_ribaq | log | 4 | its file | 0.36 | same | same | 400/400 same | 400/400 same | refused by validation |  |  |
| brunner_diann_1ng | linear | 15 | its file | 0.78 | same | same | 400/400 same | 400/400 same | refused by validation |  |  |
| brunner_mq_singlecells | linear | 51 | its file | 25.64 | same | same | 200/200 same | 200/200 same | linear |  | same |
| krull_singlecells | linear | 143 | its file | 0.71 | same | same | 200/200 same | 200/200 same | linear | missing | same |
| cong_mq_singlecells | linear | 7 | its file | 1.52 | same | same | 400/400 same | 400/400 same | refused by validation |  |  |
| hu2023_pd_k562 | linear | 72 | its file | 0.95 | same | same | 200/200 same | 200/200 same | linear |  | same |
| cptac_ccrcc_tumor | log | 110 | its file | 18.47 | same | same | 200/200 same | 200/200 same | log |  | same |

## pbmc240_diann with 2 values made negative, through both servers

| request | Space | repo | identical | reason |
|---|---|---|---|---|
| nothing stated | 400 | 400 | same | If the values are already log, choose Already log. If they are raw intensities, remove the negative values and send the file again. |
| value_scale linear | 400 | 400 | same | Choose Already log, or I don't know, for this file. |
| value_scale log | 200 | 200 | same |  |
| value_scale log, zeros measured | 200 | 200 | same |  |

## GET /api/status

- the Space: `{"atlas_version": "0.6.0", "limits": {"concurrent_projections": 1, "max_cells": 2000, "max_upload_mb": 31.0}, "model_version": "v4.1 (v4 with the correlation term weighted more where it is used; chosen on Fulcher 2026)", "pipeline_version": "v4.1", "status": "ready", "value_scale": {"choices": ["auto", "linear", "log"], "modalities": ["prot"], "zeros": ["auto", "missing", "measured"]}}`
- the repository: `{"atlas_version": "0.6.0", "limits": {"concurrent_projections": 1, "max_cells": 2000, "max_upload_mb": 31.0}, "model_version": "v4.1 (v4 with the correlation term weighted more where it is used; chosen on Fulcher 2026)", "pipeline_version": "v4.1", "status": "ready", "value_scale": {"choices": ["auto", "linear", "log"], "modalities": ["prot"], "zeros": ["auto", "missing", "measured"]}}`

