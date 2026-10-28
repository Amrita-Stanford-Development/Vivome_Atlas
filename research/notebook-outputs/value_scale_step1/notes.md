# Step 1 notes, written after the run

The report beside this file is generated; these notes explain what it shows
against `valuescale/bank/expectations/step1.json`, which was not edited after
the run.

## D1: two failures, both errors in the bank's listing

`msv000099294_hmc3` and `msv000099294_microglia` failed `layout_as_listed`.
The bank listed them as Spectronaut pivots. The files have no `PG.Genes`
column, only `PG.ProteinGroups` and per-run `PG.Quantity` columns, so the
service's parser reads them as plain matrices keyed by protein accession
(`alignment.parse_matrix_csv`'s first-column path). They parse, and 3,018
and 1,877 genes match the feature space. The listing was wrong, not the
parser.

The owner accepted both failures on 2026-10-28, and the listing in
`valuescale/corpus/bank.json` now says `matrix` for both. Re-running D1 on
the two tables after the fix, both pass. The report beside this file is the
run before the fix and still shows them as failures.

## D2: today's rule misreads 6 of the 28 real linear tables

Every one of the 9 real log tables was read correctly. Of the 28 real linear
tables, 6 were read as log:

| Table | Software | Non-zero median | What happens today |
|---|---|---|---|
| `pxd064083_t`, `pxd064083_b` | Spectronaut | 7.0, 7.9 | the known case (protocol-pxd064083.md, amendment 1) |
| `msv000099294_hmc3`, `msv000099294_microglia` | Spectronaut, single cells (nanoPOTS) | 5.8, 3.9 | **new**: read as log, no log2 taken |
| `furtwangler_batchcorr`, `furtwangler_batchcorr_norm` | TMTpro S/N, single cells | 10.8, 10.6 | **new**: read as log, no log2 taken, and their 68% zeros (missing values written as 0) kept as measured values |

So the fault is not one odd deposit. Three of the bank's single-cell
sources, from two labs and two kinds of quantity, carry linear values on a
scale below today's threshold of 50.

Variants (the predicted misreads held):
- Dividing a linear table by 10^6 fools the rule on 36 of 37 tables; by
  10^3, on 28 (not predicted, but the same fault: the threshold is a size).
- Per-protein normalised and per-cell percent tables are misread on every
  table (37 of 37), as predicted. Per-cell CPM is misread on 13 of 37.
- The linear forms of the log tables (2^x, then rescaled or normalised) are
  misread whenever they land below 50. No prediction was written for log
  sources; these are the same fault.
- Every log variant (log2, log10, ln, offsets, ×0.5, zero-filled) was read
  correctly: today's rule does not err in that direction on this bank.
- Foreign tables get a confident reading: 0/1 presence and z-scores are read
  as log, ranks as linear. Today's rule has no "neither" answer.

A further finding for B1: `furtwangler_log2` and `furtwangler_log2_raw_sn`
are log tables with 68% zeros that stand for missing values. A log reading
keeps them as measured, so the zero question arises on log tables too, not
only on misread linear ones.

## D3: 33 of 37 pass, not 37 (corrected 2026-10-28, in Phase A)

The report says 37 of 37. That is wrong: the script counted a check as
failed only when it was Python's `False`, and the z-score check returned
NumPy's `False`, so its failures were never counted (report.json stores them
as the string "False"). Four tables fail it: pbmc240_diann,
dusszachniewicz_maxquant, lungmap_bpd_fragpipe and
furtwangler_log2_imputed. Their worst z-scored gene has a mean of 0.0001 to
0.0016, not 0 to 1e-4. Every other invariant held on all 37.

The cause is float32 rounding in the service's z-score
(`alignment.zscore_per_gene`), on genes whose few values differ by much
less than their level: lungmap_bpd_fragpipe's RAB2B is 22.7172 and 22.7186.
Computed in float64 the same means are below 1e-13. Phase A's diagnostics
found it (`../value_scale_phaseA/notes.md`), and the script now counts NumPy
results too. 8 tables were refused for fewer than 20 cells, as the service
refuses them. The expectation's example
"3 runs in the sdrf" for `pxd069060_diann_report` was wrong (the report
holds 12 runs), but the rule the expectation states held.
