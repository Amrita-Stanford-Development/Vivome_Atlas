"""Protein v2, R1: the corpus checks (research/value-scale-v2-plan.md), run
against valuescale/bank/expectations/r1.json.

The walk (valuescale/corpus/draw.py) now refuses a parsed table with no
observed value (outcome "empty") and flags a kept table labelled linear
whose observed values look log (looks_log, which sends it to the hand
audit). This runs both checks, as the walk would, on:
- the 457 tables B3 kept (valuescale/corpus/walk.jsonl), each from its
  parsed table (data/incoming/value-scale-corpus/<accession>/table.npz);
- the bank's 37 tables (valuescale/corpus/bank.json), each whole, as the
  service's parser reads it; the flag's rule also runs on the 9 labelled
  log, as a positive control;
and runs the step's tests (the walk's, the service's and the Atlas page's)
by name. No detector statistic is computed, no reserve deposit is listed
and no sealed accession is opened. Writes report.json and report.md to
OUT, the step's folder under research/notebook-outputs.

    python research/notebooks/value_scale_r1.py

From the repository root, with the vivome environment.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from valuescale.corpus import denylist, draw  # noqa: E402

DATA = REPO / "data" / "incoming" / "value-scale-corpus"
WALK = REPO / "valuescale" / "corpus" / "walk.jsonl"
BANK = REPO / "valuescale" / "corpus" / "bank.json"
EXPECT = REPO / "valuescale" / "bank" / "expectations" / "r1.json"
OUT = REPO / "research" / "notebook-outputs" / "value_scale_r1"

PREDICTED_EMPTY = {"PXD022054", "PXD047898"}
PREDICTED_FLAG = {"PXD066316": {"min": 7.96, "median": 15.02, "max": 26.76}}  # posthoc.json, two decimals

TESTS = {
    "R1_walk": [sys.executable, "-m", "unittest", "valuescale.tests.test_draw.VisitTests",
                "valuescale.tests.test_draw.LooksLogAuditTests"],
    "R1_service": [sys.executable, "-m", "unittest", "service.tests.test_validation.ValidateValuesTests",
                   "service.tests.test_app.ProjectionHandlerHttpTests.test_a_table_with_no_observed_value_is_400_saying_why"],
    "R1_site": ["node", "--test", "--test-name-pattern=no observed value", "web/tests/atlas-file-check.test.js"],
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def kept_tables() -> list[dict]:
    records = [json.loads(line) for line in WALK.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in records if r["outcome"] == "kept"]


def corpus_part(kept: list[dict]) -> dict:
    empty, flagged, labels = [], {}, {}
    for r in kept:
        acc = r["accession"]
        denylist.check(acc)
        labels[r["label"]] = labels.get(r["label"], 0) + 1
        with np.load(DATA / acc / "table.npz") as z:
            values = z["values"]
        if draw.empty(values):
            empty.append(acc)
            continue
        flag = draw.looks_log(values) if r["label"] == "linear" else None
        if flag:
            flagged[acc] = {**flag, "split": r["split"], "software": r["software"],
                            "shape": [int(values.shape[0]), int(values.shape[1])]}
    return {"kept": len(kept), "labels": labels, "empty": sorted(empty), "flagged": flagged}


def bank_part() -> list[dict]:
    import value_scale_diagnostics as vsd
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    rows = []
    for e in bank["entries"]:
        values = np.asarray(vsd.load_entry(e)[0].values, dtype=np.float64)
        rows.append({"id": e["id"], "label": e["label"], "shape": [int(values.shape[0]), int(values.shape[1])],
                     "empty": draw.empty(values), "looks_log": draw.looks_log(values)})
        print(f"  {e['id']}: empty {rows[-1]['empty']}, looks_log {rows[-1]['looks_log']}", flush=True)
    return rows


def run_tests() -> dict:
    out = {}
    for row, command in TESTS.items():
        done = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        tail = (done.stdout + done.stderr).strip().splitlines()[-8:]
        out[row] = {"command": " ".join(Path(c).name if c == sys.executable else c for c in command),
                    "exit": done.returncode, "tail": tail}
    return out


def results(corpus: dict, bank: list[dict], tests: dict) -> dict:
    flagged = corpus["flagged"]
    flag_ok = set(flagged) == set(PREDICTED_FLAG) and all(
        round(flagged[a][k], 2) == v for a, want in PREDICTED_FLAG.items() if a in flagged for k, v in want.items())
    log_tables = [b for b in bank if b["label"] == "log"]
    return {
        "R1_empty": set(corpus["empty"]) == PREDICTED_EMPTY,
        "R1_flag": flag_ok and corpus["labels"] == {"linear": corpus["kept"]},
        "R1_bank_empty": not any(b["empty"] for b in bank),
        "R1_bank_control": len(log_tables) == 9 and all(b["looks_log"] for b in log_tables),
        "R1_bank_linear": "recorded",
        "R1_service": tests["R1_service"]["exit"] == 0,
        "R1_site": tests["R1_site"]["exit"] == 0,
        "R1_walk": tests["R1_walk"]["exit"] == 0,
    }


def figure(x: float) -> str:
    return f"{x:,.4g}" if abs(x) < 1e4 else f"{x:,.0f}"


def markdown(payload: dict) -> str:
    c, bank = payload["corpus"], payload["bank"]
    lines = [
        "# Value-scale diagnostics, R1: the corpus checks", "",
        f"Run {payload['run'].replace('T', ' ')[:16]} by research/notebooks/value_scale_r1.py "
        f"({payload['seconds']} s), on commit {payload['commit'][:7]} (uncommitted changes: "
        f"{payload['uncommitted_changes']}). Expectations: valuescale/bank/expectations/r1.json, written before "
        "the run. Explained in notes.md beside this file.", "",
        "## The rows", "", "| row | result |", "|---|---|",
    ]
    for row, ok in payload["results"].items():
        lines.append(f"| {row} | {ok if isinstance(ok, str) else ('PASS' if ok else 'FAIL')} |")
    lines += ["", f"## B3's {c['kept']} kept tables", "",
              f"- labels: {', '.join(f'{k} {v}' for k, v in sorted(c['labels'].items()))}",
              f"- empty: {', '.join(c['empty']) or 'none'}",
              f"- flagged (99% of the observed values under {draw.LOG_CEILING:g}): "
              f"{', '.join(c['flagged']) or 'none'}", ""]
    if c["flagged"]:
        lines += ["| table | split | software | rows x columns | smallest | median | 99th percentile | largest |",
                  "|---|---|---|---|---|---|---|---|"]
        for acc, f in c["flagged"].items():
            lines.append(f"| {acc} | {f['split']} | {f['software']} | {f['shape'][0]} x {f['shape'][1]} | "
                         f"{figure(f['min'])} | {figure(f['median'])} | {figure(f['p99'])} | {figure(f['max'])} |")
    lines += ["", "## The bank's 37 tables", "",
              "| table | label | rows x columns | empty | the flag's rule | smallest | median | 99th percentile | largest |",
              "|---|---|---|---|---|---|---|---|---|"]
    for b in bank:
        f = b["looks_log"]
        cells = [figure(f[k]) for k in ("min", "median", "p99", "max")] if f else [""] * 4
        lines.append(f"| {b['id']} | {b['label']} | {b['shape'][0]} x {b['shape'][1]} | {'yes' if b['empty'] else 'no'} | "
                     f"{'fires' if f else 'does not fire'} | " + " | ".join(cells) + " |")
    lines += ["", "## The step's tests", ""]
    for row, t in payload["tests"].items():
        said = [x.strip() for x in t["tail"] if re.match(r"\s*(Ran \d+ tests?|OK|FAILED|ℹ (tests|pass|fail) \d+)", x)]
        lines += [f"- {row}: `{t['command']}`, exit {t['exit']}; " + "; ".join(said)]
    return "\n".join(lines) + "\n"


def main() -> int:
    started = time.time()
    commit, dirty = git("rev-parse", "HEAD"), bool(git("status", "--porcelain", "--untracked-files=no"))
    print("B3's kept tables", flush=True)
    corpus = corpus_part(kept_tables())
    print(f"  {corpus['kept']} kept; empty {corpus['empty']}; flagged {sorted(corpus['flagged'])}", flush=True)
    print("The bank", flush=True)
    bank = bank_part()
    print("The step's tests", flush=True)
    tests = run_tests()
    payload = {"step": "r1", "run": datetime.now().isoformat(timespec="seconds"), "commit": commit,
               "uncommitted_changes": dirty, "seconds": round(time.time() - started),
               "expectations": EXPECT.relative_to(REPO).as_posix(), "log_ceiling": draw.LOG_CEILING,
               "results": results(corpus, bank, tests), "corpus": corpus, "bank": bank, "tests": tests}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_bytes((json.dumps(payload, indent=1) + "\n").encode("utf-8"))
    (OUT / "report.md").write_bytes(markdown(payload).encode("utf-8"))
    print(json.dumps(payload["results"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
