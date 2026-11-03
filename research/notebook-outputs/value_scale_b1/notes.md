# B1 notes, written after the run

The report beside this file is generated. These notes explain it against
`valuescale/bank/expectations/b1.json`, which was written before the script
existed and not edited after. `posthoc.md` is a probe written after the
run to explain the failed row; it is not an expectation
(`research/notebooks/value_scale_b1_posthoc.py`).

The run: v4.1 on the 30 bank tables the service accepts, plus
pxd064083_union (31 tables; 7 more are refused by validation, as in Phase
A), each read linear, as log with zeros measured, and as log with zeros
missing.

## Five rows pass

- **B1_invariants:** every stage invariant holds on every table and
  reading the pipeline accepts, and every cell has an answer or a reason.
- **B1_refusals:** the linear reading is refused on exactly the three
  tables with negative values (scope2_export, furtwangler_log2fc_nan,
  cptac_ccrcc_tumor).
- **B1_direction:** log tables read linear change a median 12.4% of best
  guesses (5 tables). Linear tables read as log change 22.0% (23 tables).
- **B1_zeros:** on all 7 tables with at least 5% zeros, zeros missing
  changes fewer best guesses than zeros measured. On the two log tables
  with zeros, measured changes 92.5% and 74.5%; missing is their right
  reading.
- **B1_accuracy:** PBMC240 53.0 right against 45.0 wrong; the sorted T and
  B cells 86.0 against 85.2; Fulcher 65.9 against 67.3. On Fulcher the
  wrong reading is 1.4 points ahead, inside the 2 points allowed.

## The decisions, by the rules written first

- **On "can't tell", read linear.** The cheaper misread, 12.4% against
  22.0%. Even the costliest log table (14.0%) is below the linear median.
- **A protein 0 is missing under both readings.**

Both as expected.

## The failed row: B1_log_read_linear_small

Expected: log tables read linear change a median of at most 10% of best
guesses. Found: 12.4%.

- Five log tables can be read linear; the other three have negatives and
  are refused. Four of the five are one deposit: Furtwangler 2025's 2,000
  CD34+ cells, processed four ways. They change 8.0, 12.4, 12.8 and 14.0%.
  The fifth, Khoury's blood cells, changes 1.2%. So the median is one
  deposit's result.
- Changed answers, what the user sees, have a median of 11.1% (2.0, 2.7,
  11.1, 12.6, 12.7%).
- Why the Furtwangler tables move more (`posthoc.md`, after the fact):
  - Their log values are small (median 3.5, against Khoury's 10.6), so a
    second log bends them more. The median per-gene correlation between x
    and log2(x) is 0.986 to 0.994, against Khoury's 0.998.
  - These are stem and progenitor cells the blood reference barely holds
    (24 to 49% answered under the right reading, against Khoury's 93%), so
    their best guesses are weakly fixed. Across all 28 tables scored under
    a wrong reading, the share answered tracks the change only weakly
    (Spearman −0.26, p = 0.17), so this is not claimed as the cause.
- What it means: reading a log table as linear costs little on the blood
  table, and about one best guess in eight on the stem cells. The decision
  this row informs does not change: linear is still the cheaper reading
  for "can't tell".

## Found along the way, for B2

**The "can't tell" check's bar.** B2, and the protocol
(`research/benchmark/protocol-value-scale.md`, "When the detector can't
tell"), say: if the median per-gene correlation between z(x) and
z(log2 x) is at least 0.98, the reply says the choice barely matters. The
probe computes that statistic for every bank table. Seven reach 0.98, and
on six of them the other reading changes 8 to 20% of best guesses:

| Table | Label | Correlation | Changed |
|---|---|---|---|
| khoury_column_normalized | log | 0.998 | 1.2% |
| furtwangler_log2_imputed | log | 0.994 | 8.0% |
| furtwangler_log2_nan | log | 0.991 | 12.4% |
| furtwangler_log2 | log | 0.991 | 12.8% |
| kabatnik_cra_timstofultra | linear | 0.990 | 16.0% |
| furtwangler_log2_raw_sn | log | 0.986 | 14.0% |
| lungmap_bpd_fragpipe | linear | 0.980 | 20.0% |

At 0.98, the message would be wrong on most of the tables that reach it.
Proposed: drop the "barely matters" message. On "can't tell" the service
reads linear, warns, and offers the other reading. No calibration or test
deposit has been fetched yet, so the change would be a dated amendment to
the protocol. It is the owner's to accept.

**Zeros, when the reading is wrong.** The sorted T and B cells (45% zeros)
are the one labelled table with zeros. Misread as log, zeros missing gives
73.3, against 85.2 with zeros measured, though both change about the same
share of best guesses (28.4 and 29.0%). The right reading (linear, zeros
missing) gives 86.0. The zeros decision is about real log tables. The only
ones with zeros (Furtwangler) write 0 for "not measured": the authors'
`_nan` layer has gaps exactly there, and reading those zeros as measured
moves 75 to 92% of best guesses. But once the decision ships, a linear
table with zeros that is misread as log has its zeros read as missing. On
this one table that costs 12 points against today's misread. The
calibrated detector is what makes that misread rare.

## For the owner, before B2

1. Accept the failed row, as explained above, or not.
2. Accept the proposed change to the "can't tell" message, or not.
