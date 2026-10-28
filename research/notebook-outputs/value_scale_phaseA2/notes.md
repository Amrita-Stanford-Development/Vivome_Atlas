# Phase A2 notes, written after the run

The report beside this file is generated; these notes explain it against
`valuescale/bank/expectations/phaseA2.json`, written before the change and
not edited after.

## Every check passes, after two fixes the first runs called for

- **The service, fixed.** The first run failed "a table with no 0 gives the
  same answers" on fulcher_tmt, furtwangler_log2_imputed and
  furtwangler_log2_nan, three tables traced on a 2,000-cell subsample. The
  answers were in fact the same (0 changed); the check compared the whole
  reply, which is stricter than the expectation. The cause: a subsample is
  column-major, and saying a 0 is not measured made a row-major copy, which
  changes the order of the sums downstream and so the coordinates' last
  digits (up to 0.0000067). The copy now keeps the table's layout
  (`alignment.apply_reading`), with a test, and the replies are identical.
- **The expectations, wrong.** They named furtwangler_log2 for the app check,
  but its 2,506 cells are over the service's 2,000, so the service rightly
  answered 413. The check now sends the 2,000-cell subsample Phase A traced,
  written as a plain matrix that reads back to the same values. It is
  compared with the pipeline's reply to the table as the service parses it:
  the parser's table is row-major, which (as above) moves the last digits
  against the column-major subsample. A real upload is always parsed, so
  this does not reach a user.

## B1 and B2

- **The automatic reply is unchanged:** the baseline's sha256 on all 30
  traced tables (`../value_scale_phaseA/baseline.json`).
- **Zeros measured changes nothing** but `value_scale.zeros`, on every
  table: under a log reading a 0 already counts as measured.
- **Zeros missing is applied and said.**
- **Zeros is refused** without a stated log reading, on every table.

## What saying a 0 is not measured changes (reported, not judged)

Tables with zeros, read as log:

| Table | Share of 0 | Answered, 0 measured | Answered, 0 not measured | Answers changed |
|---|---|---|---|---|
| furtwangler_log2 | 0.68 | 524 | 806 | 1,100 of 2,000 |
| furtwangler_log2_raw_sn | 0.68 | 946 | 975 | 1,302 of 2,000 |
| furtwangler_batchcorr | 0.68 | 792 | 638 | 1,280 of 2,000 |
| furtwangler_batchcorr_norm | 0.68 | 634 | 787 | 1,096 of 2,000 |
| pxd064083_t | 0.44 | 47 | 40 | 39 of 78 |
| pxd064083_b | 0.47 | 20 | 23 | 22 of 70 |
| krull_singlecells | 0.0007 | 51 | 53 | 13 of 143 |

As expected, the change is largest on the Furtwangler tables, whose zeros
stand for missing values. On furtwangler_log2, a real log table, reading
them as not measured lifts the cells answered from 524 to 806 of 2,000.
Whether the answers are also better is B1's question (the cost study). The
two batchcorr layers and PXD064083 are linear tables: read as log they are
read wrongly whatever their zeros mean.

## B3, B4, B5

- **B3:** every stage invariant held under a log reading with zeros
  missing. The z-score check was left out, as the expectations said: its
  five failures are the next step's (`../value_scale_phaseA/notes.md`).
- **B4:** through the app, 7 of 7: a log reading with zeros missing gives the
  pipeline's reply, and each wrong combination is answered 400 in words.
- **B5:** the final review's smaller points, 4 of 4: the pipeline itself
  refuses a stated scale or zeros on an RNA upload, an unknown reading is
  refused, and one negative value is "1 value is negative".
