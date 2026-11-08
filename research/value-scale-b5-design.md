# B5's design: the upload question, and the detector in the service

Agreed with the owner on 2026-11-08 ("good enough - go forward"), for step B5
of `research/value-scale-plan.md`. This document covers how the site asks an
uploader about their protein file's values, and how the projection service
uses B4's calibrated detector when they don't know. The plan's B5 section
lists the tests and diagnostics; this document says what gets built.

## Why

The model expects log-scale protein values. Until now the service guessed
the scale with one rule (log when the median is under 50), and the
diagnostic bank found it misreads small-scale raw tables (PXD064083, and 6 of
the bank's 28 linear tables). Phase A let uploaders say the scale in a menu
that defaults to Automatic. Phase B built a calibrated detector
(`valuescale.detect`, `valuescale/calibration/protein-v1.json`) to replace
the rule.

Uploaders mostly know whether their file is raw or log (owner, 2026-11-04).
So the site asks them first, and the detector is for those who don't know.
A menu set to Automatic by default is easy to miss, and a misread reading
changes up to 22% of the answers (B1).

## Goals

- Every protein upload is either read as its uploader says, or checked by
  the calibrated detector.
- The uploader is asked once, at the moment they choose the file, in plain
  words, with their own file's facts in view.
- After Send, the uploader can see who decided the reading (they or the
  service), and what the service's check found.
- When the check can't decide, or the table is unlike the tables the check
  was built on, the uploader is told in a place they will see, with what to
  do about it.

## Non-goals

- RNA uploads. They keep today's median rule, unchanged, and are never
  asked.
- The example file. It asks nothing, and is always sent with no
  `value_scale` or `zeros` (the service checks it), whatever the menus
  hold. The menus now carry the last file's answers, and the raw example
  sent as "Already log" would be misread.
- Any change to the detector's method or calibration (fixed in B4).
- Going live. B5 builds and checks. B6 assembles the deploy and B7 scores the
  sealed test before anything goes live, with the owner's OK.

## Anti-goals (a failure even if it works)

- **A guess in the browser.** No scale is guessed from the numbers in the
  page. It would be a second, uncalibrated detector that could contradict
  the real one. The page shows only the file's facts (range, zeros, empty
  cells, negatives), as it does today.
- **Data sent before Send.** The check runs in the service, on the upload,
  when the uploader presses Send. Nothing is sent to check the file first.
- **The service overriding the uploader.** A reading the uploader states is
  always the one used. When the check disagrees, the receipt says so, as it
  does today.
- **A warning folded away.** The warning about an undecided reading must be
  visible without opening anything.

## What the uploader sees

### The pop-up

**When it opens.** It opens after a protein file is chosen (by the file
picker or by dropping it on the map) and the browser's file check has
passed. It does not open:
- for an RNA file (Modality is RNA when the check finishes);
- for the example;
- when the check found a problem that stops the file being sent.

**What it shows:**
- the file's name and size in proteins and cells, as the check found them;
- the facts line the check already writes (`valueFactsText`): range, zeros,
  empty cells, negatives;
- the question: "Are these values raw intensities, or already log?"
- three buttons, in this order, none chosen in advance:
  - **Raw intensities:** the service takes log2;
  - **Already log:** used as they are;
  - **I don't know:** the service checks the numbers when the file is sent.

**Already log, second question.** When the uploader answers Already log and
the file has at least one 0, the same pop-up then asks what a 0 means:
- **Not measured:** a 0 means the protein was not seen;
- **Measured:** a 0 is a real value;
- **I don't know:** the service decides: not measured, unless the values
  are centred (below, "Zeros").

A file with no 0 skips this question.

**Closing it.** Escape, or the close button, counts as "I don't know" for
whichever question is open. A reading already chosen is kept.

**After it closes.** The answers are written into the Values and Zeros menus
on the tab. Send is then available as today. Answering does not send the
file.

### The menus

The Values and Zeros menus stay where they are, and stay the one place the
choice lives. The pop-up only sets them. Changing a menu later works as
today: after the service turns a file down, changing it offers Send again
(`OPTIONS_CHANGED`).

Their wording changes so that "Automatic" says what it now means:
- **Values:** "I don't know: the service checks the numbers" (sends no
  field), "Raw intensities: the service takes log2" (`linear`), "Already
  log: used as they are" (`log`).
- **Zeros (files already log):** "I don't know: a 0 is not measured,
  unless the values are centred" (sends no field), "Not measured: a 0 means the protein was not
  seen" (`missing`), "Measured: a 0 is a real value" (`measured`).

The request's fields are unchanged: `value_scale` and `zeros`, as in
`docs/service/projection-api.md`.

### After Send

**The receipt's Values line, and About this answer** (`valueScaleText`), say
who decided and what:

| Case | What it says |
|---|---|
| The uploader chose, the check agrees | today's text: "Linear intensities, log2-transformed. You chose this; the service reads them so too." |
| The uploader chose, the check read the other reading | today's text: "... You chose this; on its own the service reads them as already on a log scale." |
| The uploader chose, the check couldn't tell or found them unlike either | "... You chose this; on its own the service could not tell." |
| The check decided linear or log | "Linear intensities, log2-transformed, as the service's check read them." |
| The check couldn't tell | "Linear intensities, log2-transformed. The service's check could not tell raw from log, so it read them as raw." |
| The check found them unlike either | "Linear intensities, log2-transformed. The service's check found them unlike both raw and log tables, so it read them as raw." |
| No value observed | today's "No values to read" |

Where the reply says what a 0 was read as, the text adds it, as today
(", each 0 read as not measured").

When the reply carries the warning (unlike the tables the check was built
on), the Values line adds: "The table is unlike the tables the check was
built on: check the reading."

For the reasons the site knows, the Values line says why in plain words:
- too few columns: fewer than 20 cells, too few to tell;
- per-protein normalised: each protein's level was removed;
- no value missing: the table may have been filled in.

Other reasons (the probabilities against their thresholds) are not shown on
the page. They are in the reply, which the uploader can download.

**The visible note.** When the service read the file as raw because its
check could not decide (can't tell or unlike either), or the warning fired,
a note shows on the results card under its first line, outside the folding
receipt: "The service could not tell whether your values are raw or log, and
read them as raw. If they are already log, send the file again and choose
Already log." (With the warning alone: "Your table is unlike the tables the
service's check was built on, so check how its values were read.") The plan
put this warning beside the Values menu. After a run the setup with the
menus is hidden, so the note goes on the results card instead.

**A refused file** shows the service's reason where a refusal shows today,
and changing the Values menu offers Send again (`OPTIONS_CHANGED`).

**A service older than B5** sends no `verdict`. The site then shows today's
texts, and the note never shows.

## What the service does

In `service/pipeline/alignment.py` `detect_and_transform_value_scale`, for a
protein upload:
1. +/-inf becomes missing, as today.
2. No observed value: `detected` is "unknown", as today, and the detector is
   not called.
3. Otherwise `valuescale.detect` reads the upload's values (genes x cells),
   whatever the request stated. Its reading is `detected` ("linear" or
   "log"; on "can't tell" and "unlike either", the undecided reading,
   linear, by B1).
4. The reading used is the stated one when the request gave one, else the
   detector's (today's rule for `stated`, unchanged).
5. **Zeros:** under a linear reading every 0 is not detected, as today.
   Under a log reading, when the request does not say what a 0 means:
   - in a table with no more than a few negative values, a 0 is not
     measured (B1's decision: "A protein 0 is missing under both
     readings", `research/notebook-outputs/value_scale_b1/notes.md`). Today
     it counts as measured;
   - in a centred table (at least 1% of its observed values negative, the
     detector's negatives gate, `valuescale/gates.py` `NEGATIVE_SHARE`), a 0
     is a measured value, as today. Such a table holds log ratios, where 0
     is a ratio of 1.

   A request that says `missing` or `measured` is always followed.

   Owner, 2026-11-08: "Measured in centred tables". B1's evidence came from
   log tables without negatives (Furtwangler's, where 0 means not seen), and
   the bank has no centred table with zeros. On scope2_reprocessed (centred,
   156 zeros in 1,128 cells), reading its zeros as not measured would change
   5 best guesses (0.44%, under v4.1 and v4.2 alike), with no way to tell
   whether for the better.
6. A linear reading of a table with a negative value is refused (no
   intensity is negative). The values are never changed to make the file
   fit a reading:
   - **Stated linear:** refused, as today.
   - **The service's own linear reading** (the check's, or the undecided
     linear): refused, in clear words. The detector sets aside a few
     negatives (under 1% of the values, `valuescale/gates.py`
     `NEGATIVE_SHARE`), so it can read such a file as raw, or fail to
     decide. The file then contradicts itself, and only the uploader knows
     which it is. The reply's reason says:
     - how many values are negative, so they can't be raw intensities;
     - what the check found for the rest (read as raw, or could not tell);
     - what to do: choose Already log if the values are log, or remove the
       negative values if they are raw intensities.

     Today's refusal text ("Choose Already log, or Automatic") is wrong for
     this case and is not used for it.
   - A log reading (stated, or the check's) takes negatives, as today.

   Owner, 2026-11-08: "Refuse, in clear words", for accuracy: a wrong guess
   changes the answers silently, a refusal costs one more Send. The cost
   accepted: such a file is read as log today, and will be refused. None of
   the bank's 37 tables is such a file (each has no negative, or 44 to 50%
   of its values negative).

An RNA upload keeps the median rule, its zeros voting, exactly as today, and
its reply is unchanged.

**The reply's `value_scale`** keeps every field it has (`detected`,
`transformed`, `stated`, `zeros`, with today's meanings) and gains, for a
protein upload:
- `verdict`: "linear", "log", "cant_tell" or "unlike_either" (the
  detector's verdict), or "unknown" with no observed value;
- `zeros_read`: what a 0 was read as, "missing" or "measured";
- `evidence`: the detector's report (`ScaleReport.to_json()`), with the
  reason, the warning, the probabilities and thresholds, the stratum and the
  guarantee.

These are listed in a "fields added since freezing" list in
`service/tests/test_pipeline_versions.py` `assert_same`. The golden tests
compare the frozen keys only, and the frozen fixtures are never regenerated.

**`service/config.py`** gains:
- `VALUE_SCALE_METHOD`: "calibrated" (the detector) or "median" (today's
  rule, with today's reply and zeros, as a way back);
- `VALUE_SCALE_UNDECIDED_READING`: "linear".

`LINEAR_SCALE_MEDIAN_THRESHOLD` stays, for RNA and for the "median" method.

`VALUE_SCALE_METHOD` is a constant, not a switch on the live service. The
way back is a redeploy of the service and the site together, since the
site's wording depends on the method.

**Who follows the new method:**
- every path in the service that reads a protein upload's scale: Stage 0,
  and `service/pipeline/fusion.py`, which calls the function itself when it
  is given no scale;
- `scripts/trace_workflow.py`, which traces the served service.

**Who keeps the median rule:** the benchmark scripts and the tests whose
protocols froze their method, among them `benchmark/sorted_cd4cd8_intake.py`
(the sealed external test, whose Fulcher rehearsal must reproduce its
committed tables), `benchmark/pxd064083_intake.py` and
`benchmark/organ_baselines.py`. They ask for the median method by name, so
B5 changes nothing they measure. Moving one to the new method would be a
dated amendment to its protocol, decided by the owner. The research
notebooks are records of their runs and are not changed.

## Constraints

- The site: plain HTML, CSS and ES modules, no build step and no new
  dependency (`CLAUDE.md`). `web/js/panels.js` stays pure.
- Every value from the reply or the file is escaped (`escapeHtml`).
- The page shows no number not computed from data: the facts line comes from
  the uploader's file, and the numbers in a reply come from the service.
- `valuescale` never imports `service`. Guards that the copied rules stay in
  step live in `service/tests`.
- PC screens only. The owner checks the page by eye; Claude runs only the
  automated tests.
- The service and the site go live together: the menus' new wording ("a 0 is
  not measured, unless the values are centred") is false for today's
  service.
- Detection should take under about 3 s on the service's 2 CPUs (B4:
  0.07 s on PBMC240's 3,100 x 238).

## Decided

**By the owner:**
- The pop-up, its three answers and when it opens; leaving out a browser
  guess and a check before Send (2026-11-08).
- Uploaders mostly know their file's scale (2026-11-04).
- A file the service would read as raw that holds negative values is
  refused in clear words, not read some other way (2026-11-08).
- In a centred log table, a 0 the uploader says nothing about is a
  measured value; elsewhere under a log reading it is not measured
  (2026-11-08).
- The score is the probability alone, and the warning never removes a
  reading (B4, 2026-11-07).

**By earlier steps, under rules written first:**
- On "can't tell" (and "unlike either"), the reading is linear (B1).
- A protein 0 is not measured under either reading (B1), except in a
  centred log table (the owner's choice above).
- The reply's new fields, the config names, RNA unchanged, and the tests and
  diagnostics (the plan's B5 section).

**My calls (Claude's), open to the owner:**
- The wording of the pop-up, menus and receipt above, in the page's voice
  ("the service").
- The second question only for Already log, and only when the file has a 0.
- Escape counts as "I don't know".
- The note on the results card rather than beside the menu.
- The reasons shown in plain words for the three known reasons, and not for
  the others.
- `zeros_read` as a new field, rather than changing what `zeros` means.
- The example always sent with no stated reading.
- The benchmark scripts and frozen tests kept on the median rule.
- `VALUE_SCALE_METHOD` a constant, changed only by a joint redeploy.

## Left to the builder

- How the pop-up is built (a native `<dialog>` is the natural choice), its
  layout and styling within `docs/web/design.md`, focus and keyboard
  handling, and where its logic lives. Logic that decides what to ask and
  what to set is best kept pure, so `node --test` can cover it.
- The exact test cases, beyond the plan's list.
- The order of the work, and how the diagnostics on the bank are written,
  within the rules: expectations written and committed before the run, and
  never edited after it.
- Which docs each change touches (at least `docs/web/atlas.md`,
  `docs/service/projection-api.md`, `valuescale/README.md`, the plan,
  `research/todo.md` and `docs/file-index.md`).
