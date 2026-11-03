# B2 notes, written after the run

The report beside this file is generated. These notes explain it against
`valuescale/bank/expectations/b2.json`, written before the method existed
and not edited after the run. One change to the method was made before any
bank statistic was computed, and is recorded inside b2.json: the
discriminative part of a class score is the probability itself, not its
design rank.

There were two runs. The first found two faults, both fixed test first and
described below. The report beside this file is the second run, with the
expectations unchanged.

The verdicts use rehearsal thresholds: each table is scored by a model
fitted without its deposit, with thresholds from that model's design scores.
There is no calibration split until B3, so no guarantee is claimed here.

## What the method gets right

- **The small-scale linear tables are read linear.** All six that today's
  median-50 rule reads as log: pxd064083_t and pxd064083_b,
  msv000099294_hmc3 and msv000099294_microglia, furtwangler_batchcorr and
  furtwangler_batchcorr_norm. Their linear scores are 0.18 to 0.97, against
  thresholds near 0.03. Their log scores are all 0.
- **The other linear tables** with at least 20 columns are read linear too,
  except pxd043355_pd (below).
- **The real log tables are read log:** khoury_column_normalized,
  furtwangler_log2, furtwangler_log2_nan and furtwangler_log2_raw_sn. The
  three with negatives (scope2_export, furtwangler_log2fc_nan,
  cptac_ccrcc_tumor) are read log by the gate. The exception is
  furtwangler_log2_imputed (below).
- **Separation:** with each deposit left out, the area under the curve is
  0.992, over 39 linear and 50 log design rows from 18 deposits.
- **The conformal code:**
  - the umbrella k is 1, 2 and 5 at n = 59, 120 and 200, and none at 58;
  - in 1,000 simulated calibrations each, the share whose miss rate exceeds
    5% is 0.043, 0.013 and 0.021, against the exact 0.0485, 0.0155 and
    0.0264;
  - Clopper–Pearson matches scipy within 6e-14.
- **Invariance:** every feature is unchanged within 1e-9, over 166
  comparisons.
- **Drift:** no core feature flips between the classes when tables are
  subsampled to 20, 50 or 300 cells or lose values by intensity. Linear
  stays above log on all four.
- **Variants:** 17 wrong of 571 labelled variants (3.0%).

## Fixed after the first run

1. **level_spread moved under rescaling,** by up to 7.6e-6 in 10 of 166
   comparisons. Many tables hold exactly equal spreads (float32 or
   whole-number values). A rescaled copy computes them with different last
   digits, which breaks those ties. Spreads are now ranked at float32
   precision, relative to their median.
   Test: `test_level_spread_keeps_tied_spreads_tied_under_scale`.
2. **Per-protein-normalised tables were read log.** This happened on 15 of
   the 30 per_protein_median variants, and on SCoPE2's linear forms.
   - Why: dividing each protein by its own level leaves ratios near 1, and
     their shape looks like logs.
   - The fix: such a table (row_median_spread below 0.1) is now "can't
     tell", with that reason, so B1's reading (linear) applies.
   - The margin is wide: every real table in the bank or the design rows
     is at 0.96 or more, and the variants are near 0.
   - After the fix: 28 of the 30 are "can't tell", 2 are "unlike either",
     and none is wrong.
   - Test: `test_a_per_protein_normalised_table_is_cant_tell`.

## The failures that remain

**B2_gates.** In every case below the gates behaved as designed. My list
was incomplete, or the gate met a case I had not foreseen.
- The log2, log10, ln and halved forms of the three log tables with
  negatives also hit the negatives gate. The list named only their
  subsamples and missing variants.
- Stray negatives were also made missing in two more tables:
  - pbmc240_diann: one raw value is below 1, so its log2 has one negative;
  - furtwangler_batchcorr_norm.
- **The counts gate fires on MaxQuant's intensities,** which MaxQuant
  writes as whole numbers. This hit dusszachniewicz_maxquant and its
  variants, and the two MaxQuant tables under 20 columns (pxd021882_maxquant,
  cong_mq_singlecells). It also hit lungmap's ×1000 variant, since FragPipe
  writes at most three decimals.
  - The reading, linear, is right in each case. Only the name "counts" is
    wrong for them.
  - The gate runs before the size check, so the two small tables are read
    linear instead of "too few columns".
  - Proposed: keep both, since a whole-number table cannot be a log table.

**B2_drift.** The rule that matters holds: no flips. My side prediction was
that induced missingness would raise the log tables' Bowley; it did not.
- The medians are 0.095 with no drift, 0.095 at 40% missing and 0.093 at
  70%.
- Most bank tables are already more than 40% missing, and the variant
  leaves those unchanged.

**B2_verdicts_bank.**
- **furtwangler_log2_imputed is read linear, which is wrong.**
  - 68% of its values were filled in by the authors. They form a low band
    that makes each cell's values right-skewed, like a linear table's.
  - The protocol excludes imputed tables, so no guarantee covers them.
  - B1 found that reading this table as linear changes 8% of best guesses,
    the least of the Furtwangler log tables.
- **pxd043355_pd is "unlike either".**
  - Its probability of being linear is 0.998. But its column sums vary far
    more than any other design table's (CV 2.96, against at most 1.5).
  - So it is farther from the linear design rows than they are from each
    other. Only one other design deposit is a Proteome Discoverer table.
  - "Unlike either" is read linear (B1), which is right here.
- **The two small MaxQuant tables** are read linear by the counts gate
  (above).

**B2_verdicts_variants.** 17 of 571 are wrong (3.0%), within the 5%
expected. But they do not come from the smallest subsamples or the most
missing values, as predicted:
- 12 are the imputed table's variants: the same error, repeated.
- 5 are CPTAC's linear forms (2^x of its values). CPTAC's values are log
  ratios to a reference sample, so 2^x gives plain ratios. Those are not
  normalised to each protein's median, so the new rule does not catch
  them. The protocol excludes ratio tables.
- **Foreign tables:** percentile ranks within each protein were predicted
  "unlike either". They came out mostly "can't tell" (21 of 30, by the
  per-protein rule, since ranking within a protein removes its level), 7
  "unlike either" and 2 "log". Neither reading suits such a table, and
  "can't tell" warns.

## For the owner

Accept the remaining failures as explained, or not:
1. the gates: the incomplete list, the counts gate on whole-number
   intensities, and the gates running before the size check;
2. drift's side prediction;
3. the imputed log table read linear, and pxd043355_pd "unlike either";
4. the variants: the imputed table, CPTAC's ratios and the percentile ranks.

The two fixes after the first run are in the plan's ledger as rulings.
