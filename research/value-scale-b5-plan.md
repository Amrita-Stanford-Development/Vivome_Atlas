# B5 Implementation Plan: the upload question, and the detector in the service

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Protein uploads are read as their uploader says, or by B4's calibrated detector when they don't know. The site asks them in a pop-up when they choose the file.

**Architecture:**
- **Service:** Stage 0 (`service/pipeline/alignment.py` `detect_and_transform_value_scale`) gains a method. "calibrated" (the default) reads a protein table with `valuescale.detect`. "median" is today's rule, which RNA always uses.
- **The reply:** its `value_scale` gains `verdict`, `zeros_read` and `evidence`.
- **Site:** a pure module decides what the pop-up asks, and `data-tab.js` wires a native `<dialog>` to the Values and Zeros menus. `valueScaleText` and a new results-card note say what the service did.

**Tech Stack:**
- Python 3 with numpy (service, valuescale), tested with `unittest`.
- Plain ES modules, HTML and CSS (site), tested with `node --test`.

**Spec:** `research/value-scale-b5-design.md` (agreed with the owner, 2026-11-08). The step's plan section is `research/value-scale-plan.md` "B5". Where they differ, the design holds.

## Global Constraints

- The site has no build step, no bundler, no framework and no dependency. `web/js/panels.js` stays pure (no DOM).
- Every interpolated value from a reply or a file goes through `escapeHtml()`.
- No page shows a number not computed from data in the repo. The pop-up shows the uploader's own file facts (`valueFactsText`); no rule constant (such as 20 columns) is printed.
- `valuescale` (its tests included) never imports `service`. Guards that copied rules stay in step go in `service/tests/test_valuescale_in_step.py`.
- Files are LF only. Check every written file with Python: `open(f,'rb').read().count(b'\r') == 0`.
- Python is `/c/Users/amarn/miniforge3/envs/vivome/python.exe` (written `$PY` below).
- Run all four suites before every commit:
  - `node --test` (2 failures in `web/tests/lfs.test.js` are expected);
  - `$PY -m unittest discover -s scripts`;
  - `$PY -m unittest discover -s service/tests -t .`;
  - `$PY -m unittest discover -s valuescale/tests -t .`.
- `scripts/test_fetch_public_sets.py` `test_a_connection_dropped_half_way_is_retried` can fail in tearDown with WinError 145 (a Windows temp-folder race, unrelated). Re-run the scripts suite once, and ledger it.
- A new or moved tracked file gets its line in `docs/file-index.md` in the same commit (`scripts/check_paths.py` enforces this).
- Frozen golden fixtures are never regenerated.
- Sealed accessions (PXD042367, MSV000094189, PXD052341, PXD061065) are never opened. No test-split table is read; `valuescale/corpus/score_test.py` is not run.
- Commit messages end with:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01VoicwCZCHiEae6UvTGgmPb`
- No push and no deploy. Both wait for the owner's OK. B5 does not go live; the site and the service go live together, after B7.
- Wording (spec): the page's voice, "the service". The menus' first options read "I don't know: the service checks the numbers" and "I don't know: a 0 is not measured, unless the values are centred".

## Review Focus

1. **Degenerate protein tables reaching Stage 0:** one row, every value 0, every value equal, a single observed value. Each upload gets a reading (or a clear refusal), never "could not process the submitted matrix". Owned by Task 1, `test_degenerate_tables_get_a_reading`.
2. **Undefined numbers in the evidence:** a statistic or probability that is NaN or infinite. The reply is still strict JSON. Owned by Task 2, `test_the_reply_is_strict_json_with_the_evidence`.
3. **A second file chosen before the first one's check finishes:** the pop-up opens once, for the second file. Owned by Task 5, `asksScale` returns false for a null check (a stale check returns null from `chooseFile`).
4. **The size rule's edge:** 19 columns reads "can't tell", so linear. 20 columns is scored. Owned by Task 1, `test_the_size_rule_edge`.
5. **"I don't know" on a centred log table** (at least 1% negative values): read log by the negatives gate, not refused. Owned by Task 1, `test_a_table_with_many_negatives_is_read_log_not_refused`.

---

### Task 1: The calibrated reading in Stage 0

**Files:**
- Modify: `service/config.py`, next to `LINEAR_SCALE_MEDIAN_THRESHOLD` (line 234).
- Modify: `service/pipeline/alignment.py`:
  - `NotIntensities` (line 502);
  - `ValueScale` (lines 506-527);
  - `detect_and_transform_value_scale` (lines 585-633);
  - a new `scale_method` context manager.
- Test: `service/tests/test_alignment.py`:
  - a new class `CalibratedValueScaleTests`;
  - the existing `DetectAndTransformValueScaleTests` call with `method="median"`.
- Test: `service/tests/test_valuescale_in_step.py`, a new `test_the_undecided_reading_is_the_packages`.

**Interfaces:**
- Produces, in `service/config.py`:
  - `VALUE_SCALE_METHODS = ("calibrated", "median")`;
  - `VALUE_SCALE_METHOD = "calibrated"`;
  - `VALUE_SCALE_UNDECIDED_READING = "linear"`.
- Produces, in `alignment`:
  - `class NotIntensities(ValueError)`, with `__init__(self, message: str, reason: str | None = None)`, keeping `.reason`;
  - `ValueScale` gains `verdict: str | None = None`, `zeros_read: str | None = None` and `evidence: dict | None = None`;
  - `ValueScale.response()` adds `verdict`, `zeros_read` and `evidence` when each is not None. With all three None, the reply is unchanged.
- Produces: `detect_and_transform_value_scale(raw_values, median_threshold=config.LINEAR_SCALE_MEDIAN_THRESHOLD, zeros_vote=False, stated=None, zeros=None, method: str | None = None) -> tuple[np.ndarray, ValueScale]`.
  - `method=None` reads `config.VALUE_SCALE_METHOD` at call time.
  - `zeros_vote=True` (RNA) always uses the median rule.
  - `method="median"` is exactly today's code path and reply.
- Produces: `scale_method(method: str)`, a context manager (`contextlib.contextmanager`). It sets `config.VALUE_SCALE_METHOD` and restores it on exit. It raises ValueError for a method not in `VALUE_SCALE_METHODS`.
- Produces: `UNDECIDED_NEGATIVES_REASON = "If the values are already log, choose Already log. If they are raw intensities, remove the negative values and send the file again."`

**The calibrated path (protein), in order:**
1. `values = finite_or_missing(raw_values)`.
2. No observed value:
   - `ValueScale(detected="unknown", transformed=False, stated=stated, zeros=zeros, verdict="unknown")`;
   - `valuescale.detect` is not called;
   - `apply_reading(values, "unknown", zeros)`, as today.
3. `report = valuescale.detect(values)`.
   - `verdict = report.verdict`.
   - `detected = verdict` if it is "linear" or "log", else `config.VALUE_SCALE_UNDECIDED_READING`.
4. `reading = stated or detected`.
   - `zeros_read = "missing"` under a linear reading.
   - Under a log reading, `zeros_read = zeros` when stated. Otherwise:
     - `"measured"` when the table is centred: negative values are at least `valuescale.gates.NEGATIVE_SHARE` (0.01) of the observed values;
     - `"missing"` when it is not (B1's rule, narrowed by the owner, 2026-11-08).
5. A linear reading with a negative observed value:
   - **when `stated == "linear"`:** `apply_reading` raises as today (`reason` None);
   - **otherwise:** raise `NotIntensities(message, reason=UNDECIDED_NEGATIVES_REASON)`. The message is ``f"{n:,} {'value is' if n == 1 else 'values are'} negative, so they are not raw intensities, yet {FOUND[verdict]}"``, where FOUND is:
     - linear: "the service's check reads the rest as raw";
     - cant_tell: "the service's check could not tell whether the rest are raw or log";
     - unlike_either: "the service's check found the rest unlike both raw and log tables".
6. `out = apply_reading(values, reading, zeros_read if reading == "log" else None)`.
   - Return `ValueScale(detected, transformed=reading == "linear", stated, zeros, verdict, zeros_read, evidence=report.to_json())`.

The existing argument checks (an unknown `stated`, an unknown `zeros`, `zeros` without a stated log) stay first, for both methods. An unknown `method` raises ValueError naming `VALUE_SCALE_METHODS`.

- [ ] **Step 1: Write the failing tests** in `CalibratedValueScaleTests`. They use tables built in the test: lognormal linear values, at least 300 rows by 25 columns with 30% NaN, as `test_valuescale_in_step._tables()` builds them.
  - **`test_a_linear_table_is_read_by_the_check`:**
    - `scale.verdict == "linear"`, `scale.detected == "linear"` and `scale.transformed`;
    - `scale.zeros_read == "missing"`;
    - `scale.evidence["verdict"] == "linear"`;
    - `response()` holds `verdict`, `zeros_read` and `evidence`, and no `stated` or `zeros`.
  - **`test_a_log_table_reads_its_zeros_as_not_measured`:** log2 of the linear table, with 10% of the values set to 0 and nothing stated.
    - `detected == "log"`, `zeros_read == "missing"`, and every 0 is NaN in the output.
    - With `stated="log", zeros="measured"`, the zeros are kept as 0 and `zeros_read == "measured"`.
  - **`test_a_centred_log_tables_zeros_are_measured`:** a centred log table (about half its values negative) with 0.5% of its values set to exactly 0, and nothing stated.
    - `detected == "log"`, `zeros_read == "measured"`, and the zeros are kept as 0.
    - With `stated="log", zeros="missing"`, they become NaN.
  - **`test_the_size_rule_edge`:**
    - 19 columns (positive log-like values, 1 to 30): `verdict == "cant_tell"`, `detected == "linear"`, `transformed`;
    - 20 columns of the linear table: `verdict == "linear"`.
  - **`test_a_stated_reading_wins_and_the_check_is_reported`:** the linear table with `stated="log"`:
    - `detected == "linear"`, `stated == "log"`, not transformed;
    - `verdict == "linear"`.
  - **`test_a_few_negatives_under_the_services_own_raw_reading_are_refused`:**
    - The input: the linear table with 0.5% of its observed values made negative.
    - `NotIntensities` is raised.
    - Its message names the count and "the service's check".
    - Its `reason == alignment.UNDECIDED_NEGATIVES_REASON`.
  - **`test_a_stated_raw_reading_of_negatives_keeps_todays_refusal`:** the same table with `stated="linear"`.
    - `NotIntensities` is raised, with `reason is None`.
    - Its message is today's ("not raw intensities: the table is already on a log scale, or centred").
  - **`test_a_table_with_many_negatives_is_read_log_not_refused`:** a centred log table.
    - `verdict == "log"`, not transformed.
  - **`test_degenerate_tables_get_a_reading`:**
    - The tables: 1 row by 25 columns; 100 by 25 all 0; 100 by 25 all 7.0; 100 by 25 all NaN but one value.
    - Each returns a `ValueScale` without raising.
    - `verdict` is one of "linear", "log", "cant_tell", "unlike_either" or "unknown".
  - **`test_no_observed_value_is_unknown_and_the_check_is_not_called`:**
    - An all-NaN table: `detected == "unknown"`, `verdict == "unknown"`, `evidence is None`.
    - Patch `valuescale.detect` to raise, and assert that it is not called.
  - **`test_rna_and_the_median_method_reply_as_today`:**
    - With `zeros_vote=True`, and separately with `method="median"`, `response()` equals today's dict, `{"detected": ..., "transformed": ...}` with no new keys.
    - Under `method="median"`, a log reading keeps its 0 values.
  - **`test_the_method_is_read_at_call_time`:** `with alignment.scale_method("median"):` gives `response()` with no `verdict`, and the method is restored afterwards.
    - `alignment.scale_method("other")` raises ValueError.

  In `test_valuescale_in_step.py`:
  - `test_the_undecided_reading_is_the_packages`: `config.VALUE_SCALE_UNDECIDED_READING == valuescale.report.UNDECIDED_READING`.

- [ ] **Step 2: Run them, and watch them fail**
  - Run: `$PY -m unittest service.tests.test_alignment.CalibratedValueScaleTests service.tests.test_valuescale_in_step -v`.
  - Expected: errors on the missing `verdict`, `scale_method` and `VALUE_SCALE_UNDECIDED_READING`.
- [ ] **Step 3: Implement.**
  - Write the config constants, `NotIntensities.reason`, the `ValueScale` fields, `scale_method` and the calibrated path above.
  - `import valuescale` goes at the top of `alignment.py` (the service may import the package; the reverse is forbidden).
  - The docstring of `detect_and_transform_value_scale` gains a paragraph on the two methods. It cites `research/value-scale-b5-design.md`.
  - Add `method="median"` to every call in `DetectAndTransformValueScaleTests`: they test the median rule, which stays.
- [ ] **Step 4: Run them, and watch them pass**
  - Run: the same command, then `$PY -m unittest service.tests.test_alignment -v`.
  - Expected: all OK.
- [ ] **Step 5: Run the service suite, and triage.**
  - Run: `$PY -m unittest discover -s service/tests -t . > <workspace>/t1_service.log 2>&1`, then read its tail.
  - Expected: every failure listed under "Known breakage" below, and no other. Fix each as that list says, then run again until OK.
- [ ] **Step 6: Commit** after all four suites pass. Message: `B5: Stage 0 reads a protein table with the calibrated detector`.

**Known breakage.** A throwaway spike on 2026-11-08 patched Stage 0 in memory, with the zeros rule as B1 wrote it. It failed 11 of the service's tests (the spike added no reply keys; those are Task 2's).
- **`test_alignment` `DetectAndTransformValueScaleTests`**, `test_already_log_scale_is_not_transformed`: `method="median"`, as Step 3 says.
- **`test_alignment` `StatedValueScaleTests`**, all five that failed:
  - `test_a_log_reading_may_say_a_zero_is_not_measured`;
  - `test_a_stated_linear_reading_takes_log2_where_the_rule_reads_log`;
  - `test_a_zero_said_to_be_measured_is_read_as_a_log_reading_reads_it`;
  - `test_the_reply_names_the_stated_reading_only_when_one_was_stated`;
  - `test_the_rule_and_the_reading_are_separate_steps`.

  Each gets `method="median"`. They test Phase A's stated reading on top of the median rule, on tables of 3 to 5 cells. The calibrated equivalents are in `CalibratedValueScaleTests`.
- **`test_app`:** `test_a_stated_value_scale_is_applied_and_said_in_the_reply` and `test_with_a_log_reading_a_request_may_say_a_zero_is_not_measured`. Each runs inside `with alignment.scale_method("median"):`. First check that the test server runs in this process; if not, ledger a ruling. They test Phase A's stated fields through the app; Task 2 adds the calibrated app tests.
- **`test_v42` `ProteinQueryTests`**, `test_it_reads_the_table_as_stage_0_decided`: inside `with alignment.scale_method("median"):`. It is a 3-cell table the median rule reads log, and it tests that `fusion` passes Stage 0's scale.
- **`test_v42` `V42ServiceTests`**, `test_the_served_guess_is_the_notebooks_on_every_development_dataset` (scope2_reprocessed): expected to pass unchanged under the owner's centred-table rule. Its 156 zeros stay measured, and its reading is log either way (45% negative). If it fails, stop and report: do not change the test.
- **`test_valuescale_in_step` `MedianRuleInStepTests`** ('small'): a spike artifact (the spike patched `median_rule` itself). Expected to pass.

Any other failure gets a ledger line. The fix follows the same rule: a test of the median rule states `method="median"`, and a test of a whole reply compares the frozen keys (Task 2).

### Task 2: The reply and the refusal, through the app

**Files:**
- Modify: `service/app.py`, the `NotIntensities` handler (lines 393-395).
- Modify: `service/tests/test_pipeline_versions.py`, `assert_same` (lines 29-45).
- Modify: `service/tests/test_golden_fixtures.py`, `test_dataset_level_fields_match` (lines 77-81).
- Modify: `service/tests/test_app.py`, the value-scale tests (lines 358-415).
- Modify: `docs/service/projection-api.md`, the `modality`, `value_scale` and `zeros` sections (lines 27-72).

**Interfaces:**
- Consumes: `alignment.NotIntensities.reason` and `alignment.UNDECIDED_NEGATIVES_REASON` (Task 1).
- Produces: the 400 body for a refused reading. It is `{"error": str(exc), "reason": exc.reason or STATED_LINEAR_REASON}`, where `STATED_LINEAR_REASON = "Choose Already log, or I don't know, for this file."` is a module constant in `app.py`. The menu's "Automatic" is renamed "I don't know" (Task 5).
- Produces: `FIELDS_ADDED_SINCE_FREEZING = {"response.value_scale": ("verdict", "zeros_read", "evidence")}` in `test_pipeline_versions.py`.
  - `assert_same` allows exactly these keys in `fresh` beyond the frozen ones, at that path.
  - Every frozen key is still compared.

- [ ] **Step 1: Write the failing tests:**
  - **`test_app.py` `test_an_unsure_raw_reading_of_negatives_is_refused_in_clear_words`:**
    - The upload: a protein matrix of the synthetic bundle's genes, 25 cells, lognormal linear values with 2 values negative, and no `value_scale`.
    - The reply: status 400; `"negative"` in `error`; `reason` equal to `UNDECIDED_NEGATIVES_REASON`.
    - The same file with `value_scale=linear` gives reason `"Choose Already log, or I don't know, for this file."`.
  - **`test_app.py` `test_a_protein_reply_says_the_checks_verdict`:**
    - A protein reply's `value_scale` has `verdict`, `zeros_read` and `evidence`.
    - An RNA reply's has none of them.
  - **`test_app.py` `test_the_reply_is_strict_json_with_the_evidence`:** `json.dumps(payload, allow_nan=False)` does not raise for a protein reply.
  - **`test_pipeline_versions.py` `test_only_the_listed_fields_may_be_added`:**
    - `assert_same` passes when fresh has `value_scale.verdict` added;
    - it fails when fresh has `value_scale.other` added, or a frozen key removed.
- [ ] **Step 2: Run them, and watch them fail.**
  - Run: `$PY -m unittest service.tests.test_app service.tests.test_pipeline_versions -v`.
  - Expected: FAIL (today's reason text; the added keys are not allowed yet).
- [ ] **Step 3: Implement:**
  - write the handler and `STATED_LINEAR_REASON`;
  - write `FIELDS_ADDED_SINCE_FREEZING` in `assert_same`;
  - `test_golden_fixtures`: compare `value_scale` on the golden file's keys only, plus check that the fresh reply's extra keys are exactly the listed ones.
  - Update the existing `test_app.py` value-scale tests: they assert whole `value_scale` dicts. Compare their frozen keys, plus `verdict` where the test is about the reading, in the same way. A test whose reading changes is listed in Task 1's "Known breakage".
- [ ] **Step 4: Run them, and watch them pass.** The same command, then the service suite. Expected: OK.
- [ ] **Step 5: Docs.**
  - `docs/service/projection-api.md`:
    - `value_scale` auto: the calibrated check reads a protein table (`valuescale`), and on "can't tell" or "unlike either" it reads linear;
    - the new reply fields and their values;
    - a protein 0 under a log reading is not measured unless `zeros` says `measured`;
    - the refusal of the service's own raw reading of negative values, with its reason;
    - RNA unchanged;
    - `config.VALUE_SCALE_METHOD`.
  - Line 35's "non-zero median under 50" sentence becomes RNA's alone.
- [ ] **Step 6: Commit** after all four suites pass. Message: `B5: the reply says the check's verdict; an unsure raw reading of negatives is refused in words`.

### Task 3: The frozen scripts keep the median rule

**Files:**
- Modify: `benchmark/sorted_cd4cd8_intake.py`. Its direct calls are at lines 112 and 125, and its run goes through `run_projection`.
- Modify: `benchmark/pxd064083_intake.py`, line 175.
- Modify: `benchmark/organ_baselines.py`, line 62.
- Test: `service/tests/test_valuescale_in_step.py`, a new `test_the_frozen_scripts_keep_the_median_rule`.

**Interfaces:**
- Consumes: `alignment.scale_method` and the `method=` argument (Task 1).
- Produces: each of the three modules defines `SCALE_METHOD = "median"`, with a comment naming its protocol: `research/benchmark/protocol-sorted-cd4cd8.md`; `protocol-pxd064083.md`; and, for `organ_baselines.py`, the sealed organ tests' `protocol-ln-pxd042367.md` and `protocol-lung-msv000094189.md` (read the protocols only, never the sealed data). It:
  - passes `method=SCALE_METHOD` in every direct call;
  - wraps its `main()` body in `with alignment.scale_method(SCALE_METHOD):`.

- [ ] **Step 1: Write the failing test.** For each of the three modules:
  - `importlib.import_module(name).SCALE_METHOD == "median"`;
  - the module source holds no `detect_and_transform_value_scale(` call without `method=` (a regex over the source).
- [ ] **Step 2: Run it, and watch it fail.** Run: `$PY -m unittest service.tests.test_valuescale_in_step -v`. Expected: FAIL (no `SCALE_METHOD`).
- [ ] **Step 3: Implement** the three modules.
- [ ] **Step 4: Run it, and watch it pass.** Then run `service.tests.test_sorted_cd4cd8`, `test_pxd064083`, `test_organ_heldout` and `test_heldout`. Expected: OK, with no test output changed.
- [ ] **Step 5:** Check that `scripts/trace_workflow.py` follows the service (no change). Run `$PY -m unittest service.tests.test_workflow_trace -v`. Expected: OK.
- [ ] **Step 6: Commit** after all four suites pass. Message: `B5: the sealed and spent tests' scripts keep the median rule by name`.

### Task 4: The site says how the values were read

**Files:**
- Modify: `web/js/panels.js`, `valueScaleText` (lines 243-262).
- Modify: `web/js/atlas/atlas-panels.js`: `scaleLine` (lines 137-152), and a new `scaleNote`.
- Modify: `web/atlas.html`: a `<p class="panel-note atlas-scale-note" id="results-scale-note" hidden></p>` after `#results-note` (line 111).
- Modify: `web/js/atlas/data-tab.js` `update()` (lines 158-167), which sets `#results-scale-note`.
- Modify: `web/manuscript.html` line 298, the median-50 sentence.
- Test: `web/tests/panels.test.js` (next to lines 280-301) and `web/tests/atlas-panels.test.js`.

**Interfaces:**
- Consumes: the reply's `value_scale.verdict`, `zeros_read`, `evidence.warning` and `evidence.reason` (Tasks 1 and 2).
- Produces: `valueScaleText(scale) -> string | null`. Today's outputs are unchanged when `verdict` is absent.
- Produces: `scaleNote(receipt) -> string | null`, exported from `atlas-panels.js`. It returns the note's text, unescaped, or null.

**The exact text** (spec, "After Send"). `read` is today's `SCALE_READ[...]`. The zeros text comes from `scale.zeros` when it is stated, else from `scale.zeros_read` under a log reading (`!transformed`), using today's `ZEROS_READ`.
- verdict linear or log, nothing stated: `${read}, as the service's check read them.`
- cant_tell, nothing stated: `${read}. The service's check could not tell raw from log, so it read them as raw.`
- unlike_either, nothing stated: `${read}. The service's check found them unlike both raw and log tables, so it read them as raw.`
- stated, verdict cant_tell or unlike_either: `${read}. You chose this; on its own the service could not tell.`
- stated, verdict linear or log: today's two texts, comparing `stated` with `verdict`.
- When `evidence.warning` is a non-empty string, append: ` The table is unlike the tables the check was built on: check the reading.`
- Reasons, appended after the verdict's text, by the prefix of `evidence.reason`:
  - `"too few columns"`: ` Too few cells to tell.`
  - `"per-protein normalised"`: ` Each protein's level was removed, so its shape cannot tell.`
  - `"no value is missing"`: ` No value is missing: the table may have been filled in.`
  - any other reason: nothing.
- `scaleNote`:
  - null when there is no `verdict`, or when a reading was stated;
  - verdict cant_tell or unlike_either: `The service could not tell whether your values are raw or log, and read them as raw. If they are already log, send the file again and choose Already log.`
  - otherwise, with the warning: `Your table is unlike the tables the service's check was built on, so check how its values were read.`
  - otherwise null.

- [ ] **Step 1: Write the failing tests.**
  - `panels.test.js` `valueScaleText says what the check found`: one assertion per line above, plus a `<b>` in `reason` and `warning` that changes nothing (they are matched by prefix, never echoed).
  - `atlas-panels.test.js` `scaleNote shows only for the service's own unsure or unusual reading`: each case, null included.
  - A guard in `service/tests/test_valuescale_in_step.py`, `test_the_sites_reason_prefixes_are_the_packages`: the three prefixes appear in `web/js/panels.js`, and each starts the matching `valuescale.method` constant (`"too few columns"`, `PER_PROTEIN_REASON` and `NO_GAPS_REASON`).
- [ ] **Step 2: Run them, and watch them fail.**
  - Run: `node --test web/tests/panels.test.js web/tests/atlas-panels.test.js` and `$PY -m unittest service.tests.test_valuescale_in_step`.
  - Expected: FAIL.
- [ ] **Step 3: Implement.**
  - `data-tab.js`: `textContent = scaleNote(run.receipt)` and `hidden = !note`, when `shown`; hidden otherwise.
  - `web/manuscript.html`: the sentence becomes:
    - a protein matrix's scale is read by the uploader's choice, or by a calibrated check (`valuescale/`);
    - an RNA matrix with no negative values and a median observed value above `<span data-ms="wf_scale_threshold">` is read as linear;
    - the evidence source line adds `valuescale/`.
- [ ] **Step 4: Run them, and watch them pass.** The same commands. Expected: PASS.
- [ ] **Step 5: Commit** after all four suites pass. Message: `B5: the receipt and the results card say what the service's check found`.

### Task 5: The pop-up, and the menus' words

**Files:**
- Create: `web/js/atlas/scale-question.js` (pure, no DOM).
- Create: `web/tests/atlas-scale-question.test.js`.
- Modify: `web/atlas.html`:
  - the menus (lines 157-168);
  - a `<dialog id="scale-question" aria-labelledby="scale-question-title">` before the closing `</body>`.
- Modify: `web/js/atlas/data-tab.js`: the picker's `change` handler (lines 185-188) and the drop handler (lines 223-231).
- Modify: `web/css/atlas.css`, the dialog's styles.
- Test: `web/tests/atlas.test.js`, the markup.

**Interfaces:**
- Consumes: the check's `name`, `cells`, `features`, `values` and `ok`, and `valueFactsText` (`file-check.js`); `landing.chooseFile(file) -> Promise<check | null>`.
- Produces: in `scale-question.js`:
  - `asksScale({ modality, check }) -> boolean`: true only when `modality === 'prot'` and `check?.ok === true`;
  - `asksZeros(check) -> boolean`: `check?.values?.zeros > 0`;
  - `menuChoice(reading, zeros = 'auto') -> { valueScale, zeros }`:
    - `reading` is one of 'linear', 'log' or 'auto', anything else being 'auto';
    - `zeros` is 'missing', 'measured' or 'auto', and is kept only with 'log'.

**The dialog** (spec, "The pop-up"):
- **Title:** "Are these values raw intensities, or already log?"
- **A file line:** `${name}: ${features} feature rows, ${cells} cells`, then the facts line.
- **Step 1:** three buttons in this order, none focused by default (focus goes to the title, with `tabindex="-1"`):
  - "Raw intensities: the service takes log2" (`data-reading="linear"`);
  - "Already log: used as they are" (`log`);
  - "I don't know: the service checks the numbers" (`auto`).
- **Step 2,** shown only after Already log when `asksZeros`. The title is "What does a 0 mean in this file?", with three buttons:
  - "Not measured: the protein was not seen" (`missing`);
  - "Measured: a 0 is a real value" (`measured`);
  - "I don't know: the service decides" (`auto`).
- **Escape** (the dialog's `cancel` event) or the close button: 'auto' for the open step. A reading already chosen is kept.
- **On close:**
  - `const { valueScale, zeros } = menuChoice(...)`;
  - set `$('value-scale').value` and `$('zeros').value`;
  - call `landing.optionsChanged()` and `update()`;
  - focus `#project`.
- **Opened from:** the picker and drop handlers only, as `landing.chooseFile(file).then((check) => { if (asksScale({ modality: $('modality').value, check })) ask(check); })`. Never from `sendExample` or LIMITS.
- **The menus:**
  - Values options: `auto` "I don't know: the service checks the numbers", `linear` "Raw intensities: the service takes log2", `log` "Already log: used as they are".
  - Zeros options: `auto` "I don't know: a 0 is not measured, unless the values are centred", `missing` "Not measured: a 0 means the protein was not seen", `measured` "Measured: a 0 is a real value".

- [ ] **Step 1: Write the failing tests.**
  - `atlas-scale-question.test.js`:
    - **`asksScale`:** true for prot with an ok check; false for rna, for a null check (stale), and for a check with `ok: false`.
    - **`asksZeros`:** true with zeros 3; false with 0, or with no `values`.
    - **`menuChoice`:** ('log', 'missing') gives `{valueScale: 'log', zeros: 'missing'}`; ('linear', 'missing') gives `{'linear', 'auto'}`; ('x') gives `{'auto', 'auto'}`.
  - `atlas.test.js` `the page asks how the values are written`:
    - `#scale-question` is a `<dialog>` with `aria-labelledby`;
    - it has buttons with `data-reading` linear, log and auto, in that order, and with `data-zeros` missing, measured and auto;
    - the menus' auto options read the exact texts above.
- [ ] **Step 2: Run them, and watch them fail.**
  - Run: `node --test web/tests/atlas-scale-question.test.js web/tests/atlas.test.js`.
  - Expected: FAIL (no module, no dialog).
- [ ] **Step 3: Implement** the module, the markup, the wiring and the styles. Match `docs/web/design.md`'s tokens. PC screens only.
- [ ] **Step 4: Run them, and watch them pass.** Then `node --test`. Expected: 2 failures, in lfs only.
- [ ] **Step 5: Docs.**
  - `docs/web/atlas.md` "Values" (lines 110-123): the pop-up, when it opens, the new option words, the note, and the example.
  - `docs/file-index.md`: the two new files.
- [ ] **Step 6: Commit** after all four suites pass. Message: `B5: the site asks how a protein file's values are written`.

### Task 6: The example is sent with no stated reading

**Files:**
- Modify: `web/js/atlas/landing.js`, `request()` (lines 616-624) and `sendExample()` (lines 798-818).
- Test: `web/tests/atlas-landing.test.js`.

**Interfaces:**
- Consumes: the `options()` callback (main.js lines 166-169).
- Produces: `sendExample` records the `File` it made. `request()` sends no `value_scale` or `zeros` for that file, and passes `scaleAsked: 'auto', zerosAsked: 'auto'` to `arrive`. Other files are unchanged.

- [ ] **Step 1: Write the failing test** `the example is sent with no stated reading, whatever the menus hold`.
  - `options()` returns `{ modality: 'prot', valueScale: 'log', zeros: 'missing' }`, with `fetch` stubbed to return the example's bytes.
  - The form sent has `value_scale === null` and `zeros === null`.
  - `landing.run.receipt.scaleAsked === null`.
  - The test beside it, on a chosen file with the same options, still sends 'log'.
- [ ] **Step 2: Run it, and watch it fail.** Run: `node --test web/tests/atlas-landing.test.js`. Expected: FAIL (`value_scale` is 'log').
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run it, and watch it pass.** Expected: PASS.
- [ ] **Step 5: Commit** after all four suites pass. Message: `B5: the example is always sent for the service to read`.

### Task 7: Diagnostics B5, expectations first

**Files:**
- Create: `valuescale/bank/expectations/b5.json`, written and committed before the step's code runs on the bank, and never edited after the run.
- Modify: `research/notebooks/value_scale_diagnostics.py`: a `b5` step (a function `b5_step()`, registered in `main()`'s `steps`).
- Create: `research/notebook-outputs/value_scale_b5/` (`report.md`, `report.json`, `notes.md`).
- Modify (docs run-through):
  - `research/value-scale-plan.md` ("B5 as built", status);
  - `research/notebook-run-history.md` (entry 79);
  - `research/todo.md` (the Phase B line, changelog rows);
  - `valuescale/README.md` (a B5 section);
  - `research/working-context.md`;
  - `docs/file-index.md`.

**Interfaces:**
- Consumes: everything above; the bank (`valuescale/corpus/bank.json`), D3's records, and Phase A's baseline replies and their sha256 (`research/notebook-outputs/value_scale_phaseA/`).

- [ ] **Step 1: Write `b5.json`.** Rows, each a prediction made before the run:
  - **B5_pbmc240:** linear on the 50-cell slice and on all 238 cells.
  - **B5_scope2:** log.
  - **B5_pxd064083:** linear; its answers tabled against D3.
  - **B5_rna:** the RNA fixtures' replies byte-identical to Phase A's baseline.
  - **B5_frozen_keys:** every traced table's reply equal to its Phase A or z-score step baseline on the frozen keys, except the tables whose reading or zeros change, each named with its reason. Derive these from B4's bank verdicts (`research/notebook-outputs/value_scale_b4/report.json`) and each table's zero share (step 1's D1). Write them down before running.
  - **B5_invariants:** every stage invariant holds under the new reading.
  - **B5_time:** detection under 3 s per table on the PC, timed for the largest bank table.
  - **B5_refusals:** no bank table is refused (none has a few negatives; scratch probe, 2026-11-08).
  - **B5_app:** the same replies through the app (`b4_through_the_app`'s pattern).
- [ ] **Step 2: Commit `b5.json` alone.** Message: `B5: diagnostics expectations, before the run`.
- [ ] **Step 3: Implement `b5_step()`,** reusing `phase_a`'s tracing (`traced_table`, `summary_of`, `_reading_invariants`, `_post`) and writing `report.md` and `report.json`.
- [ ] **Step 4: Run it.**
  - Run: `$PY research/notebooks/value_scale_diagnostics.py --step b5 > <workspace>/b5.log 2>&1`.
  - Expected: each row as `b5.json` says. A row that differs is reported, never edited.
- [ ] **Step 5: Write `notes.md`,** each row against `b5.json`, in plain words. Then the docs run-through: every file listed above, current and in step.
- [ ] **Step 6: Commit** after all four suites pass. Message: `B5: diagnostics on the bank, and the docs run through`. Then a follow-up commit fills in the todo row's hash.
