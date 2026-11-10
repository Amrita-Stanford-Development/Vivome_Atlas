# The raw-or-log detector, second round: protein v2

Planned on 2026-11-09, after B7 (`research/value-scale-plan.md`;
`research/notebook-outputs/value_scale_b7/notes.md`). Written for the owner's
approval before any work starts.

Status: approved by the owner on 2026-11-09 ("yes approved, push them and
start R1"); R2 waits for the owner's go-ahead ("dont R2 yet", 2026-11-09).
- **R1, the corpus checks:** done on 2026-11-10 (`56421b1`, the run on
  `4b521d0`; `research/notebook-outputs/value_scale_r1/notes.md`). Every
  expectation met: of B3's 457 kept tables, exactly the two empty ones
  refused and exactly PXD066316 flagged. The service and the Atlas page now
  refuse an upload with no observed value; not live.
- **R2 to R7:** not started.

## Why

B7's sealed test contradicted the detector's guarantee for log tables of
20 to 49 cells (S1): it missed 22 of 237, a one-sided lower bound of 0.064
against 0.05. The guarantee held for the other three classes and strata.

- **Corpus faults:** 3 of the misses come from faulty test tables. Two are
  empty (PXD022054, PXD047898), and one is a log2 table labelled linear
  (PXD066316).
- **The rest are log tables with half or more of their values missing.**
  - The detector's log probability falls as the missing share rises.
  - The S1 threshold came from the few such tables in calibration: 5 low
    scores of 214 tables, against 20 of 234 in the test.
  - B4 saw this on the bank as "the sparse-log gap".

**The owner's choices (2026-11-09):**
- rework, then a fresh test: the live service stays as it is;
- the method study considers two candidates and chooses between them by a
  rule written first;
- the corpus refuses empty tables, and sends a table whose values look log
  under a linear label to the hand audit.

## What stays from v1

- **The claim:** per true class and stratum, the true class is missing
  from the answer at most α = 0.05 of the time, with probability 1 − δ =
  0.95 over the calibration draw. The threshold is the umbrella k-th
  smallest calibration score.
- **The strata** (S1 20 to 49 columns; S2 50 to 300; S3 301 to 2,000),
  with S3 pooled into S2.
- **The frame and its rules:**
  - the frame (`valuescale/corpus/frame.json`, 18,813 deposits in a seeded
    order);
  - the hash split (`20261103:` + accession);
  - the provenance labels;
  - the audit rubric;
  - the walker and its fixes.
- **The constructed log class.** The corpus still holds no table labelled
  real log, a stated limitation.
- **The v1 record.** `protein-v1.json`, B7's results and its marks stand
  as they are. v2 writes its own files and marks, and v1's are never
  reused.

## The data

- **Design (development) data:**
  - the bank's 37 tables;
  - the 457 tables B3 kept: v1's 218 calibration and 237 test deposits,
    and the 2 the audit excluded.

  All of them are spent for testing (`research/benchmark/side-tests.md`,
  amendment 26). Every method choice is made on them.
- **Fresh calibration and test:**
  - drawn from the 8,813 frame deposits B3's walk did not list, in the
    frame's order, under the same split rule;
  - none is listed before protocol v2 is committed.
- **Size.** v1's 10,000 listings gave 164 S1 tables with half or more
  missing, about 1.6 per 100 listings. So the whole reserve would give
  about 145, some 72 per split. That is close to the 59 per class a
  separate threshold needs.
  - If R2's choice needs more, protocol v2 may widen the frame (deposits
    before 2020, say).
  - That is the owner's decision at R3.

## The steps

Each step is checked against expectations written before it runs
(`valuescale/bank/expectations/r<step>.json`). It ends with its notes in
`research/notebook-outputs/value_scale_r<step>/`, an entry in
`research/notebook-run-history.md`, and a run through every doc it touches.
Code is written test first.

### R1. The corpus checks

- **An empty table is refused:** one with no observed value, as a walk
  outcome of its own.
  - It says nothing about scale, so the refusal cannot bias the labels.
  - The service's and the site's handling of such an upload is checked in
    the same step and fixed test first if needed.
- **A table labelled linear whose values look log goes to the hand audit**
  (99% of its observed values under 64).
  - Its packet shows the value range, beside the headers and methods.
  - The auditor keeps the label, relabels it from provenance, or excludes
    the table.
  - There is no automatic refusal by value range: it would also drop
    small-scale linear tables like PXD064083's (median about 7), the kind
    the detector exists to catch.
- **The diagnostic:** both checks run over the 457 kept tables. Expected:
  - exactly PXD022054 and PXD047898 refused;
  - exactly PXD066316 flagged.

### R2. The method study (development data only)

Two candidates. Each is fitted and checked on disjoint deposits, never on
the deposit it scores:
- **A, a threshold by missingness.** Calibrate tables with half or more of
  their values missing apart from the rest, so the guarantee covers each
  group in its own right. Cells: column stratum × missing group, pooled
  where a cell cannot reach 59 per class.
- **B, a model that missingness does not move.** Change the features, or
  refit the model on the design deposits as well as the bank, so a log
  table's probability no longer falls as its missing share rises. The
  strata stay as in v1.

**The rule for choosing, written before the study:**
- The study repeats the protocol many times on the design deposits:
  calibrate on one random half, check on the other.
- A candidate passes if the guarantee would be contradicted at most δ of
  the time in every class, stratum and missing group.
- Among those that pass, the one with fewer "can't tell" and "unlike
  either" answers on whole tables is chosen. A and B together is a third
  candidate.
- If none passes, the study says so, and the owner decides.

The rule's exact form (repeats, folds, the cells) goes in `r2.json`,
committed before any candidate is scored.

### R3. Protocol v2

`research/benchmark/protocol-value-scale-v2.md`, committed before any
reserve deposit is listed. It covers:
- R2's method and its strata or groups;
- the sizes the calibration needs, and the walk's stop;
- the frame (the reserve, or the reserve widened, the owner's decision);
- the scoring, which is v1's;
- the primary comparison against median-50 on the linear tables.

### R4. The fresh draw

- The walk lists reserve deposits in the frame's order, with R1's checks,
  until protocol v2's stop.
- The audit, by B3's rubric, covers a seeded 20% of each split and every
  table R1 flags.
- Labels are committed before any detector statistic is computed on them.

### R5. Calibration v2

- `valuescale/calibration/protein-v2.json`, from the fresh calibration
  split.
- Then the scorer's rehearsal on that split, which checks the code.

### R6. The service and the site

- **The service and the site:**
  - the detector reads with protein-v2;
  - the reply's sentence on the guarantee is written from the calibration
    for each stratum or group, so that it is true of the table it
    describes. (v1's sentence claims 5% for every stratum, which B7
    contradicted for one.)
- **The checks:** B5's and B6's on the bank, with expectations written
  first.

### R7. Sealed test v2, once

- Scored once with the owner's go-ahead, under its own marks.
- Then the owner decides the release. The site and the service go live
  together, only with the owner's explicit OK.

## What the owner decides along the way

- **After R2:** the chosen method, and the sizes and frame it needs
  (protocol v2).
- **Before R7:** the go-ahead for the one scoring.
- **After R7:** the release.
- **Every push, and every deploy.**

## Until then

- **The live service stays at revision 00009-hcz,** with the median rule.
- **The site cannot deploy alone.** The site on `integration/v4` carries
  B5's pop-up and its words, which the live service does not match
  (`docs/web/hosting.md`). A site fix that cannot wait would go on a
  branch without B5.
