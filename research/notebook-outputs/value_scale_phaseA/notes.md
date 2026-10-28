# Phase A notes, written after the run

The report beside this file is generated; these notes explain it against
`valuescale/bank/expectations/phaseA.json`, written before the change. One
line was added to that file before the first run (the three tables a linear
reading must refuse, as a list, so the script reads them instead of
parsing the sentence above it); nothing was edited after.

## A1 and A2: as expected on every table

- **The automatic reply is unchanged:** on all 30 traced tables it has the
  baseline's sha256 (`baseline.json`, the code before the change), no
  `stated` key, and D3's summary.
- **A stated reading is applied and said:** `detected` stays the rule's,
  `stated` is the request's, `transformed` follows the stated one.
- **Stating the rule's own reading changes nothing else.**
- **A linear reading is refused** on exactly scope2_export,
  furtwangler_log2fc_nan and cptac_ccrcc_tumor, the tables with negative
  values, and on no other.

## A3: five tables fail the z-score check, none because of this change

| Table | Fails under | Worst gene (float32 z mean, SD) |
|---|---|---|
| pbmc240_diann | linear (its automatic reading) | TUBG1, two values 10.4143 and 10.4230: mean -0.0001 |
| dusszachniewicz_maxquant | linear (its automatic reading) | mean 0.0002 |
| lungmap_bpd_fragpipe | linear (automatic) and log | RAB2B, 22.7172 and 22.7186: mean 0.0013 |
| furtwangler_log2_imputed | log (its automatic reading) | ERCC2: mean 0.0016 |
| furtwangler_batchcorr | linear (a stated reading) | MRPL13, 12 values within 2e-6 of 1.829: mean -0.38, SD 0.93 |

The check asks each z-scored gene for a mean of 0 and an SD of 1 to 1e-4.
The service z-scores in float32 (`alignment.zscore_per_gene`), and on a gene
whose few values differ by far less than their level the rounding moves the
mean by up to 0.0016. In float64 the same genes give means below 1e-13. The
first four fail under their automatic reading too, so the same failures
were in Step 1's D3, which its report missed (`../value_scale_step1/notes.md`).

The fifth is the same rounding at its limit. Read as linear,
furtwangler_batchcorr has genes whose log2 values differ only in the last
float32 bits (spread 2e-7 on a level of 1.8). Exactly, they z-score to ±1;
in float32 they come out as noise. Such a gene is constant in all but
rounding, so neither answer carries information. This is a finding for the
owner (`research/todo.md`): computing the z-score in float64, or treating a
gene whose spread is a few float32 steps as constant, would change every
reply slightly, so it is not part of Phase A.

Every other invariant held on every table under each reading: no ±inf
after Stage 0, Stage 0 making missing exactly the zeros and infinities a
linear reading should (and only the infinities under a log one), the mask,
the encoder's finite input, v4.2's protein query reading the table as
Stage 0 did, and every cell answered or abstained.

## A4: what a stated linear reading changes on the six misread tables

| Table | Cells | Answered, rule's reading | Answered, stated linear | Answers changed |
|---|---|---|---|---|
| pxd064083_t | 78 | 47 | 40 | 36 |
| pxd064083_b | 70 | 20 | 26 | 27 |
| msv000099294_hmc3 | 47 | 19 | 15 | 12 |
| msv000099294_microglia | 57 | 19 | 14 | 11 |
| furtwangler_batchcorr | 2,000 | 792 | 672 | 1,243 |
| furtwangler_batchcorr_norm | 2,000 | 634 | 803 | 1,125 |

Reported, not judged. The reading changes a large share of the answers,
and the answered count goes up on some tables and down on others. Whether
the right reading also gives better answers is B1's question (the cost
study), on the tables with labels.

## A5: through the app, 19 of 19

The request the site sends gives the same reply as `pipeline.run_projection`
for every reading on PBMC240, Khoury and SCoPE2. An absent field and `auto`
give the same reply. SCoPE2 read as linear, an RNA upload with a stated
scale, and an unknown value are each answered 400, in words.
