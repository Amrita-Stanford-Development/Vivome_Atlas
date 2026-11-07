"""The sealed test's one scoring (research/benchmark/protocol-value-scale.md,
"Scoring (once)" and amendment 5).

    python -m valuescale.corpus.score_test --rehearse OUT.json   # B4: the calibration split, a rehearsal
    python -m valuescale.corpus.score_test                       # B7: the sealed test, once

**Once.** Before it reads any test table, the real run writes TEST_STARTED
with the commit it runs on; when it has scored the test it writes
TEST_SCORED. It refuses to run while either file exists, so a run that
stopped midway (a power loss, an error) is not repeated silently: the
owner decides. The rehearsal reads the calibration split only and writes
neither file, and its output file may not be either of them or the test's
results: its output checks the code, not the method.

**What is scored**, for each deposit of the split (the walk's kept tables,
less those the hand audit disagreed with):
- one subsample per stratum its table reaches, and that subsample's
  constructed log variant, made exactly as the calibration made them
  (valuescale/corpus/strata.py); a real log table is scored as deposited;
- each is given to valuescale.detect with the shipped calibration, and its
  answer set becomes one of five outcomes for its true class: right (the
  class alone), wrong (the other alone), can't tell (both), unlike either
  (neither). A miss is wrong or unlike either;
- the whole table, as deposited, for the primary comparison and the
  baselines.

**What is reported:**
- per class (linear, constructed log, real log) and calibrated stratum, one
  outcome per deposit: in a pooled stratum a deposit misses when either of
  its subsamples misses (amendment 5); per protocol stratum and over all
  subsamples, one outcome per subsample. Each with Clopper-Pearson 95%
  intervals, and the guarantee check: contradicted when the one-sided 95%
  lower bound of the miss rate is above alpha;
- the primary comparison: the real linear tables, whole, the share given
  the wrong reading by the detector (its `reading`: "can't tell" and
  "unlike either" are read linear, B1) against median-50, with the exact
  one-sided McNemar test, paired by table;
- every baseline (valuescale/baselines.py) on the same whole tables and on
  each one's constructed log variant; a baseline that raises on a table is
  recorded as an error for that table, and the run goes on;
- risk against coverage on the subsamples: at each cut, the answers of one
  class whose probability for that class reaches the cut (a gate's answer
  always counts), and the share of them that are wrong; by software and by
  instrument family;
- the foreign tables' answers, made from calibration deposits only (the
  protocol), whichever split is scored: each calibration deposit's S1
  subsample z-scored per protein, as 0/1 presence, and as per-protein
  percentile ranks.

Not shipped; imports nothing from the service.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Mapping

import numpy as np

import valuescale
from valuescale import baselines, calibrated, conformal
from valuescale import statistics as st
from valuescale.corpus import calibrate, strata

CORPUS = Path(__file__).resolve().parent
REPO = CORPUS.parents[1]
DATA = REPO / "data" / "incoming" / "value-scale-corpus"
INDEX = DATA / "px_index_2026-11-03.tsv"
TEST_SCORED = CORPUS / "test_scored.json"
TEST_STARTED = CORPUS / "test_started.json"
RESULTS = REPO / "research" / "benchmark" / "value-scale-test" / "results.json"
OUTCOMES = ("right", "wrong", "cant_tell", "unlike_either")
CLASSES = {"linear": "linear", "constructed_log": "log", "real_log": "log"}
CLASS_READINGS = ("linear", "log")
COVERAGE_CUTS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99)
FAMILIES = (("Orbitrap", r"orbitrap|exactive|exploris|astral|fusion|lumos|eclipse|ltq|velos|elite"),
            ("timsTOF", r"timstof|tims tof"),
            ("SCIEX TOF", r"tripletof|zenotof|sciex|6600|5600|7600"))


def outcome(answer: Iterable[str], label: str) -> str:
    s = tuple(answer)
    if s == (label,):
        return "right"
    if len(s) == 1:
        return "wrong"
    return "cant_tell" if len(s) == 2 else "unlike_either"


def is_miss(o: str) -> bool:
    return o in ("wrong", "unlike_either")


def deposit_outcome(outcomes: list[str]) -> str:
    """One outcome for a deposit with several subsamples in a pooled stratum:
    its first miss, else "can't tell" if any, else right."""
    return next((o for o in outcomes if is_miss(o)), "cant_tell" if "cant_tell" in outcomes else "right")


def tally(outcomes: list[str], alpha: float = conformal.ALPHA) -> dict:
    n = len(outcomes)
    counts = Counter(outcomes)
    out = {"n": n, "counts": {o: counts.get(o, 0) for o in OUTCOMES}}
    miss = counts.get("wrong", 0) + counts.get("unlike_either", 0)
    out["miss"] = miss
    rates = {}
    for name, x in [*out["counts"].items(), ("miss", miss)]:
        rates[name] = {"rate": x / n if n else None, "interval": list(conformal.clopper_pearson(x, n)) if n else None}
    out["rates"] = rates
    out["miss_lower"] = conformal.clopper_pearson_lower(miss, n) if n else None
    out["guarantee_contradicted"] = bool(n) and out["miss_lower"] > alpha
    return out


def mcnemar_one_sided(detector_only_right: int, median_only_right: int) -> float:
    """P(X >= b), X ~ Binomial(b + c, 1/2): the exact one-sided McNemar test
    that the detector misreads fewer tables."""
    b, c = detector_only_right, median_only_right
    if b + c == 0:
        return 1.0
    return 1.0 - conformal.binom_cdf(b - 1, b + c, 0.5) if b else 1.0


def instrument_family(instrument: str) -> str:
    text = (instrument or "").lower()
    if not text.strip():
        return "not stated"
    return next((name for name, pattern in FAMILIES if re.search(pattern, text)), "other")


def instruments(raw: bytes) -> dict[str, str]:
    """{accession: instrument} from ProteomeXchange's index (the frame's
    reading of its records, valuescale/corpus/frame.py)."""
    from valuescale.corpus import frame
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
    records: list[str] = []
    for line in text.split("\n")[1:]:
        if line.startswith(frame.RECORD_START):
            records.append(line)
        elif line.strip() and records:
            records[-1] += " " + line
    out = {}
    for record in records:
        fields = record.split("\t")
        i = next((k for k in range(2, len(fields)) if fields[k].strip() in frame.REPOSITORIES), None)
        if i is not None and len(fields) >= i + 6:
            out[re.sub(r"<[^>]+>", "", fields[0]).strip()] = fields[i + 2].strip()
    return out


def split_records(records: Iterable[Mapping], split: str) -> list[dict]:
    return [dict(r) for r in records if r.get("split") == split]


def scored_records(walk: Iterable[Mapping], audit: Mapping, split: str) -> list[dict]:
    """The split's kept tables (linear or log), less the audit's disagreements."""
    disagree = {a for a, v in audit.get("verdicts", {}).items() if v.get("agrees") is False}
    return sorted((r for r in split_records(walk, split) if r.get("outcome") == "kept"
                   and r.get("label") in ("linear", "log") and r["accession"] not in disagree),
                  key=lambda r: r["accession"])


def _foreign(values: np.ndarray) -> dict[str, np.ndarray]:
    """The protocol's foreign tables from one subsample: per-protein
    z-scores, 0/1 presence, per-protein percentile ranks."""
    with np.errstate(all="ignore"):
        lin = np.where(values > 0, values, np.nan)
        mean = np.nanmean(lin, axis=1, keepdims=True)
        sd = np.nanstd(lin, axis=1, keepdims=True)
        z = (lin - mean) / np.where(sd > 0, sd, np.nan)
    presence = np.where(np.isnan(lin), 0.0, 1.0)
    ranks = np.full(values.shape, np.nan)
    for i in range(values.shape[0]):
        ok = ~np.isnan(lin[i])
        if ok.any():
            ranks[i, ok] = st._ranks(lin[i, ok]) / ok.sum()
    return {"zscore_proteins": z, "presence": presence, "percentile_ranks": ranks}


def _answer(rule: Callable[[np.ndarray], str | None], values: np.ndarray):
    """A baseline's answer, or "error: ..." when it raises on the table."""
    try:
        return rule(values)
    except Exception as e:  # noqa: BLE001 - one table's error is a result, not the end of the run
        return f"error: {type(e).__name__}: {e}"[:300]


def _is_error(answer) -> bool:
    return isinstance(answer, str) and answer.startswith("error:")


def risk_coverage(rows: list[Mapping], cuts=COVERAGE_CUTS) -> dict:
    """At each cut c: the answers holding one class whose probability for
    that class is at least c (a gate's answer, with no probability, always
    counts), as a share of all rows (coverage), and the share of those that
    are wrong (risk)."""
    curve = {}
    for c in cuts:
        answered = [row for row in rows if len(row["set"]) == 1 and (
            row["probabilities"] is None or row["probabilities"][row["set"][0]] >= c)]
        wrong = sum(row["outcome"] == "wrong" for row in answered)
        curve[str(c)] = {"coverage": len(answered) / len(rows) if rows else None,
                         "risk": wrong / len(answered) if answered else None}
    return curve


def _row(r: Mapping, stratum: str, cls: str, report, form: str) -> dict:
    return {"accession": r["accession"], "stratum": stratum, "class": cls, "form": form, "columns": report.columns,
            "software": r.get("software"), "verdict": report.verdict, "set": list(report.set),
            "outcome": outcome(report.set, CLASSES[cls]), "gate": report.gate, "reason": report.reason,
            "warning": report.warning, "probabilities": report.probabilities}


def score_split(records: list[Mapping], values_of: Callable[[Mapping], np.ndarray], cal: calibrated.Calibration,
                instrument_of: Mapping[str, str] | None = None, foreign_records: list[Mapping] | None = None,
                progress: Callable[[str], None] | None = None) -> dict:
    """The split's results; the foreign tables, when `foreign_records` is
    given, are made from those records, which must all be calibration
    deposits."""
    instrument_of = instrument_of or {}
    if foreign_records is not None:
        outside = [r["accession"] for r in foreign_records if r.get("split") != "calibration"]
        if outside:
            raise ValueError(f"foreign tables are made from calibration deposits only (the protocol); not {outside[:5]}")
    rows, tables, foreign_rows = [], [], defaultdict(list)
    for i, r in enumerate(records):
        values = np.asarray(values_of(r), dtype=np.float64)
        if values.shape[1] != r["columns"]:
            raise ValueError(f"{r['accession']}: {values.shape[1]} columns on disk, {r['columns']} in its record")
        if r["label"] == "log":
            for s in strata.strata_reached(values.shape[1]):
                sub, _ = strata.subsample(values, r["accession"], s)
                rows.append(_row(r, s, "real_log", valuescale.detect(sub, cal), "as deposited"))
        else:
            for s in strata.strata_reached(values.shape[1]):
                sub, _ = strata.subsample(values, r["accession"], s)
                form, logged = strata.constructed_log(sub, r["accession"], s)
                rows.append(_row(r, s, "linear", valuescale.detect(sub, cal), "as deposited"))
                rows.append(_row(r, s, "constructed_log", valuescale.detect(logged, cal), f"constructed {form}"))
            form, full_log = strata.constructed_log(values, r["accession"], "S1")
            whole = valuescale.detect(values, cal)
            tables.append({"accession": r["accession"], "software": r.get("software"),
                           "detector": whole.reading, "verdict": whole.verdict,
                           "baselines": {name: _answer(f, values) for name, f in baselines.BASELINES.items()},
                           "log_form": form,
                           "log_baselines": {name: _answer(f, full_log) for name, f in baselines.BASELINES.items()},
                           "log_detector": valuescale.detect(full_log, cal).reading})
        if progress:
            progress(f"{i + 1}/{len(records)} {r['accession']}")
    for r in foreign_records or ():
        if r.get("label") != "linear":
            continue
        sub, _ = strata.subsample(np.asarray(values_of(r), dtype=np.float64), r["accession"], "S1")
        for name, v in _foreign(sub).items():
            rep = valuescale.detect(v, cal)
            foreign_rows[name].append({"accession": r["accession"], "verdict": rep.verdict,
                                       "gate": rep.gate, "warning": rep.warning is not None})

    member_of = {m: name for name, members in calibrate.POOLS.items() for m in members}
    by_cal = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in rows:
        by_cal[member_of[row["stratum"]]][row["class"]][row["accession"]].append(row["outcome"])
    out = {"deposits": len(records), "subsamples": len(rows)}
    out["by_calibrated_stratum"] = {p: {c: tally([deposit_outcome(o) for o in deps.values()])
                                        for c, deps in classes.items()} for p, classes in by_cal.items()}
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["stratum"]][row["class"]].append(row["outcome"])
    out["by_stratum"] = {s: {c: tally(o) for c, o in cs.items()} for s, cs in sorted(grouped.items())}
    every = defaultdict(list)
    for row in rows:
        every[row["class"]].append(row["outcome"])
    out["all_subsamples"] = {c: tally(o) for c, o in every.items()}

    detector_right = [t["detector"] == "linear" for t in tables]
    median_right = [t["baselines"]["median_50"] == "linear" for t in tables]
    b = sum(d and not m for d, m in zip(detector_right, median_right))
    c = sum(m and not d for d, m in zip(detector_right, median_right))
    out["primary"] = {"tables": len(tables), "detector_right": sum(detector_right),
                      "detector_wrong": len(tables) - sum(detector_right),
                      "median_50_right": sum(median_right), "median_50_wrong": len(tables) - sum(median_right),
                      "detector_only_right": b, "median_50_only_right": c, "p_value": mcnemar_one_sided(b, c)}
    out["baselines"] = {}
    for name in baselines.BASELINES:
        res = {}
        for key, truth, field in (("linear", "linear", "baselines"), ("constructed_log", "log", "log_baselines")):
            readings = [t[field][name] for t in tables]
            res[key] = {"right": sum(x == truth for x in readings), "wrong": sum(x in CLASS_READINGS and x != truth
                                                                               for x in readings),
                        "no_answer": sum(x is None for x in readings), "error": sum(_is_error(x) for x in readings)}
        out["baselines"][name] = res
    out["detector_on_whole_tables"] = {
        "linear": dict(Counter(t["detector"] for t in tables)),
        "constructed_log": dict(Counter(t["log_detector"] for t in tables))}

    out["risk_coverage"] = risk_coverage(rows)
    by_sw, by_inst = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_sw[row["software"] or "not stated"][row["class"]].append(row["outcome"])
        by_inst[instrument_family(instrument_of.get(row["accession"], ""))][row["class"]].append(row["outcome"])
    out["by_software"] = {k: {c: tally(o) for c, o in v.items()} for k, v in sorted(by_sw.items())}
    out["by_instrument"] = {k: {c: tally(o) for c, o in v.items()} for k, v in sorted(by_inst.items())}
    if foreign_records is not None:
        out["foreign"] = {name: {"n": len(fr), "deposits": sorted(f["accession"] for f in fr),
                                 "verdicts": dict(Counter(f["verdict"] for f in fr)),
                                 "gates": dict(Counter(f["gate"] or "none" for f in fr)),
                                 "warned": sum(f["warning"] for f in fr)} for name, fr in foreign_rows.items()}
    out["rows"] = rows
    out["tables"] = tables
    return out


def check_not_scored(mark: Path | None = None, started: Path | None = None) -> None:
    """Refuses when the test has been scored, or a scoring started and did
    not finish (`started` defaults to TEST_STARTED's name beside `mark`)."""
    mark = TEST_SCORED if mark is None else mark
    started = mark.with_name(TEST_STARTED.name) if started is None else started
    if mark.exists():
        raise SystemExit(f"the sealed test is scored once, and {mark} says it has been: "
                         f"{json.loads(mark.read_text(encoding='utf-8')).get('scored_at')}")
    if started.exists():
        about = json.loads(started.read_text(encoding="utf-8"))
        raise SystemExit(f"a scoring of the sealed test started at {about.get('started_at')} on commit "
                         f"{about.get('commit')} and did not finish ({started}); the owner decides what follows")


def _write_mark(path: Path, data: Mapping) -> None:
    path.write_text(json.dumps(dict(data), indent=1) + "\n", encoding="utf-8", newline="\n")


def mark_started(mark: Path, about: Mapping) -> None:
    _write_mark(mark, {"started": True, "started_at": datetime.now().isoformat(timespec="seconds"), **about})


def mark_scored(mark: Path, about: Mapping) -> None:
    _write_mark(mark, {"scored": True, "scored_at": datetime.now().isoformat(timespec="seconds"), **about})


def _commit() -> dict:
    """The commit this runs on, and whether the working tree is clean."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()
    return {"commit": git("rev-parse", "HEAD"), "clean": git("status", "--porcelain") == ""}


def _rehearsal_out(text: str) -> Path:
    """The rehearsal's output file: never empty, never a file that records
    the sealed test."""
    if not text.strip():
        raise SystemExit("--rehearse needs the file to write the rehearsal into")
    out = Path(text)
    reserved = {p.resolve() for p in (TEST_SCORED, TEST_STARTED, RESULTS)}
    if out.resolve() in reserved:
        raise SystemExit(f"--rehearse would write over {out}, which records the sealed test; choose another file")
    return out


def _clean(v):
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def _values_of(r: Mapping) -> np.ndarray:
    with np.load(DATA / r["accession"] / "table.npz") as z:
        return z["values"].astype(np.float64)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--rehearse", metavar="OUT", help="score the calibration split instead, into OUT")
    args = parser.parse_args(argv)
    rehearse = args.rehearse is not None
    if rehearse:
        out = _rehearsal_out(args.rehearse)
    else:
        check_not_scored(TEST_SCORED, TEST_STARTED)
        out = RESULTS
    split = "calibration" if rehearse else "test"
    walk = [json.loads(line) for line in (CORPUS / "walk.jsonl").read_text(encoding="utf-8").splitlines() if line]
    audit = json.loads((CORPUS / "audit.json").read_text(encoding="utf-8"))
    cal = calibrated.load()
    records = scored_records(walk, audit, split)
    foreign_records = scored_records(walk, audit, "calibration")
    inst = instruments(INDEX.read_bytes()) if INDEX.exists() else {}
    about = {"calibration": cal.id, "calibration_corpus_sha256": cal.corpus_sha256, **_commit()}
    if not rehearse:
        mark_started(TEST_STARTED, {**about, "deposits": len(records)})
    result = score_split(records, _values_of, cal, instrument_of=inst, foreign_records=foreign_records,
                         progress=lambda s: print(s, flush=True))
    result = {"split": split, "rehearsal": rehearse, **about, "run": datetime.now().isoformat(timespec="seconds"),
              **result}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_clean(result), indent=1) + "\n", encoding="utf-8", newline="\n")
    if not rehearse:
        mark_scored(TEST_SCORED, {**about, "results": out.as_posix()})
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
