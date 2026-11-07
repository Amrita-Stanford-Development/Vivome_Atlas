"""The raw-or-log plan's B4: the calibration of the protein detector.

Checks valuescale/bank/expectations/b4.json, written after protocol
amendment 5 and before B4's code existed, before any detector statistic was
computed on a calibration or test deposit. Two parts, run in order:

    python research/notebooks/value_scale_calibrate.py --part design
    python research/notebooks/value_scale_calibrate.py --part calibrate

**The design part** reads the bank alone (no calibration or test deposit):
- B4_model: B2's design rows rebuilt (value_scale_method.design_rows) and
  fitted give B2's full_model, every number equal after the JSON round trip.
- B4_no_gaps: two things are recorded for every bank table as B2 loads it:
  where the rule's condition holds (no gate decides, and no value is missing
  after the gates' clean-up), and where the rule decides in the method's
  order. The row passes when the condition holds on
  furtwangler_log2_imputed alone, and the rule decides no variant of B2's
  (value_scale_method.all_variants) but variants of that table.
- Writes design.json. The calibration part refuses to run unless B4_model
  and B4_no_gaps passed there, or B4_no_gaps failed exactly as the owner
  accepted (OWNER_ACCEPTED): the condition on furtwangler_log2_imputed
  alone, and the rule deciding, beside that table's variants, only
  furtwangler_log2/per_protein_median (whose gaps, stored as 0, become
  values in its linear form). The first run, before the variants fault was
  fixed, is kept as design_run1.json.

**The calibration part:**
- builds the calibration (valuescale/corpus/calibrate.py) from the
  calibration split with the refitted model, and writes
  valuescale/calibration/protein-v1.json once. If the file exists it is
  never overwritten: the fresh build is compared with it, `written` aside.
- B4_calibration_size, B4_thresholds, B4_typicality_zero (in each
  calibrated stratum, S1 and S2+S3; the protocol strata are recorded),
  B4_calibration_coverage and B4_gated, from every subsample's row.
- B4_bank_verdicts and B4_bank_variants: each bank table and each of B2's
  variants scored by B2's model fitted without its deposit
  (value_scale_method.fit_models), against the calibrated thresholds of the
  stratum its column count falls in (S1's below 20 columns, where the size
  rule decides first).
- B4_baselines: every baseline on every bank table as B2 loads it. "The
  four real log tables without negatives" are the four B4_bank_verdicts
  names as log; median-50 on the bank's other log tables without negatives
  (furtwangler_log2_imputed, quantms_pxd004452_ribaq) is recorded.
- B4_detect: valuescale.detect on PBMC240 read from its TSV (DIA-NN's six
  annotation columns dropped, empty cells missing); the time is that of the
  first call in this process with the calibration's cache cleared, so it
  includes reading protein-v1.json, not the TSV.
- B4_rehearsal: `python -m valuescale.corpus.score_test --rehearse` as its
  own process, end to end on the calibration split.
- Writes report.md, report.json, calibration_rows.json (every calibration
  subsample's score) and rehearsal.json in
  research/notebook-outputs/value_scale_b4/.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import value_scale_method as vsm  # noqa: E402
from value_scale_method import r, rdict  # noqa: E402

import valuescale  # noqa: E402
from valuescale import baselines, calibrated, conformal, gates, method, score  # noqa: E402
from valuescale.corpus import calibrate, score_test  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "value_scale_b4"
EXPECTATIONS = REPO / "valuescale" / "bank" / "expectations" / "b4.json"
B2_REPORT = REPO / "research" / "notebook-outputs" / "value_scale_b2" / "report.json"
CALIBRATION = calibrated.CALIBRATION_DIR / f"{calibrated.DEFAULT}.json"
CORPUS = REPO / "valuescale" / "corpus"
DATA = REPO / "data" / "incoming" / "value-scale-corpus"
PBMC240 = REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv"
PBMC240_ANNOTATIONS = 6  # Protein.Group to N.Proteotypic.Sequences
IMPUTED = "furtwangler_log2_imputed"
EXPECTED_LINEAR = ("pbmc240_diann", "kabatnik_cra_timstofultra", "kabatnik_c3_region", "pxd073250_diann",
                   "pxd077946_diann_genes", "zamore_diann", "pxd064083_t", "pxd064083_b", "herrera2025_fragpipe",
                   "lungmap_bpd_fragpipe", "msv000099294_hmc3", "msv000099294_microglia", "pxd061052_spectronaut",
                   "pxd043355_pd", "fulcher_tmt", "furtwangler_batchcorr", "furtwangler_batchcorr_norm",
                   "pxd049412_a549_singlecells", "brunner_mq_singlecells", "krull_singlecells", "hu2023_pd_k562")
EXPECTED_LOG = ("khoury_column_normalized", "furtwangler_log2", "furtwangler_log2_nan", "furtwangler_log2_raw_sn")
SMALL_SCALE = ("pxd064083_t", "pxd064083_b", "msv000099294_hmc3", "msv000099294_microglia", "furtwangler_batchcorr",
               "furtwangler_batchcorr_norm")
WARNED = ("pxd043355_pd",)
SIZE = {"S1": 218, "S2+S3": 68, "S2 alone": 65, "S2 and S3": 3}
K = {"S1": 6, "S2+S3": 1}
MIN_THRESHOLD = 0.05
MAX_WRONG_VARIANTS = 0.05
DETECT_SECONDS = 3.0
OTHER = {"linear": "log", "log": "linear"}
OWNER_ACCEPTED = {"B4_no_gaps": {
    "decided": "2026-11-07, the owner: \"Accept, fix, calibrate\" (the variants fault fixed test first, the design "
               "part re-run, then the calibration)",
    "extra_variants": ["furtwangler_log2/per_protein_median"]}}


def no_gaps_as_accepted(row: dict) -> bool:
    """B4_no_gaps failed exactly as the owner accepted, and no other way."""
    extra = sorted(v for v in row["variants_decided"] if not v.startswith(IMPUTED + "/"))
    return row["condition_holds"] == [IMPUTED] and extra == OWNER_ACCEPTED["B4_no_gaps"]["extra_variants"]


def differences(a, b, path="", out=None, limit=10):
    """Up to `limit` paths where two JSON values differ."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'the refit' if k in a else 'B2'}")
            else:
                differences(a[k], b[k], f"{path}/{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: {len(a)} items, B2 {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                differences(x, y, f"{path}[{i}]", out, limit)
    elif a != b:
        out.append(f"{path}: {a!r}, B2 {b!r}")
    return out[:limit]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")


def bank_and_design():
    bank = vsm.vsd.fetch.load_bank()
    print("Loading the bank", flush=True)
    tables = vsm.load_tables(bank)
    rows, info = vsm.design_rows(tables)
    return tables, rows, info


def labelled_tables(tables):
    return [t for t in tables if t["values"].shape[1] >= conformal.MIN_COLUMNS and t["label"] in ("linear", "log")]


# ------------------------------------------------------------------ design part

def design_part() -> int:
    started = time.time()
    b2 = json.loads(B2_REPORT.read_text(encoding="utf-8"))
    tables, rows, info = bank_and_design()
    full = score.fit(rows)
    refit = json.loads(json.dumps(full.to_json(), default=str))
    diff = differences(refit, b2["full_model"])
    results = {"B4_model": (not diff, {"design_rows": len(rows), "linear_rows": sum(x.label == "linear" for x in rows),
                                       "log_rows": sum(x.label == "log" for x in rows),
                                       "deposits": len({x.deposit for x in rows}), "differences": diff})}

    print("The no-gaps rule on the bank", flush=True)
    condition, decides = [], []
    for t in tables:
        g = gates.gate(t["values"])
        if g.gate is None and not np.isnan(g.values).any():
            condition.append(t["id"])
        if method.assess(t["values"], full, calibrate.NEUTRAL)["reason"] == method.NO_GAPS_REASON:
            decides.append(t["id"])
    variant_decides, variants_seen = [], 0
    for t in labelled_tables(tables):
        for name, values, _ in vsm.all_variants(t):
            variants_seen += 1
            if method.assess(values, full, calibrate.NEUTRAL)["reason"] == method.NO_GAPS_REASON:
                variant_decides.append(f"{t['id']}/{name}")
        print(f"  {t['id']}: done ({time.time() - started:.0f} s)", flush=True)
    ok = condition == [IMPUTED] and all(v.startswith(IMPUTED + "/") for v in variant_decides)
    results["B4_no_gaps"] = (ok, {"condition_holds": condition, "rule_decides": decides,
                                  "variants_seen": variants_seen, "variants_decided": variant_decides})

    report = {"step": "b4", "part": "design", "run": datetime.now().isoformat(timespec="seconds"),
              "seconds": round(time.time() - started),
              "rows": {k: {"pass": v[0], **v[1]} for k, v in results.items()}}
    write_json(OUT / "design.json", report)
    for k, v in results.items():
        print(f"{k}: {'PASS' if v[0] else 'FAIL'}")
    return 0


# ------------------------------------------------------------------ calibration part

def values_of(record) -> np.ndarray:
    with np.load(DATA / record["accession"] / "table.npz") as z:
        return z["values"].astype(np.float64)


def read_pbmc240() -> np.ndarray:
    lines = PBMC240.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    body = [line.split("\t")[PBMC240_ANNOTATIONS:] for line in lines[1:] if line]
    return np.array([[float(v) if v.strip() else np.nan for v in row] for row in body], dtype=np.float64)


def stratum_or_s1(cal: calibrated.Calibration, columns: int) -> calibrated.Stratum:
    return cal.stratum_for(columns) or cal.strata[0]


def check_size(data: dict, rows: list[dict]) -> tuple[bool, dict]:
    counts = Counter(f"{row['stratum']}/{row['label']}" for row in rows)
    strata_of = defaultdict(set)
    for row in rows:
        strata_of[row["accession"]].add(row["stratum"])
    s2_alone = sorted(a for a, s in strata_of.items() if "S2" in s and "S3" not in s)
    s2_s3 = sorted(a for a, s in strata_of.items() if {"S2", "S3"} <= s)
    s3_alone = sorted(a for a, s in strata_of.items() if "S3" in s and "S2" not in s)
    no_statistic = [f"{row['accession']}/{row['stratum']}/{row['label']}" for row in rows if row["typicality"] is None]
    by = {s["name"]: s for s in data["strata"]}
    ok = (counts["S1/linear"] == counts["S1/log"] == SIZE["S1"]
          and by["S1"]["n"] == {"linear": SIZE["S1"], "log": SIZE["S1"]}
          and by["S2+S3"]["n"] == {"linear": SIZE["S2+S3"], "log": SIZE["S2+S3"]}
          and len(s2_alone) == SIZE["S2 alone"] and len(s2_s3) == SIZE["S2 and S3"] and not s3_alone
          and all(by[name]["k"] == {"linear": k, "log": k} for name, k in K.items()) and not no_statistic)
    return ok, {"subsamples": dict(sorted(counts.items())), "deposits": len(strata_of),
                "n": {name: by[name]["n"] for name in by}, "k": {name: by[name]["k"] for name in by},
                "s2_alone": len(s2_alone), "s2_and_s3": s2_s3, "s3_alone": s3_alone, "no_statistic": no_statistic}


def check_thresholds(data: dict) -> tuple[bool, dict]:
    t = {s["name"]: s["thresholds"] for s in data["strata"]}
    ok = all(v is not None and v > MIN_THRESHOLD for th in t.values() for v in th.values())
    return ok, {"thresholds": t}


def check_typicality_zero(rows: list[dict]) -> tuple[bool, dict]:
    member_of = {m: name for name, members in calibrate.POOLS.items() for m in members}
    zero = defaultdict(set)
    zero_protocol = defaultdict(set)
    for row in rows:
        if row["label"] == "linear" and row["typicality"] == 0:
            zero[member_of[row["stratum"]]].add(row["accession"])
            zero_protocol[row["stratum"]].add(row["accession"])
    ok = all(zero.get(name) for name in calibrate.POOLS)
    return ok, {"linear_deposits_at_zero": {k: len(v) for k, v in sorted(zero.items())},
                "by_protocol_stratum": {k: len(v) for k, v in sorted(zero_protocol.items())}}


def check_coverage(data: dict, rows: list[dict]) -> tuple[bool, dict]:
    pooled = calibrate.pooled_scores(rows)
    out, ok = {}, True
    for s in data["strata"]:
        for y in calibrate.LABELS:
            scores = pooled.get((s["name"], y), {})
            t = s["thresholds"][y]
            misses = sorted(a for a, v in scores.items() if t is None or v < t)
            k = s["k"][y]
            ok &= k is not None and len(misses) <= k - 1
            out[f"{s['name']}/{y}"] = {"n": len(scores), "k": k, "threshold": t, "misses": misses}
    return ok, out


def check_gated(rows: list[dict]) -> tuple[bool, dict]:
    groups = defaultdict(Counter)
    for row in rows:
        groups[f"{row['label']}/{row['stratum']}"][row["decided_by"] or "the score"] += 1
    shares = {g: {k: {"count": v, "share": r(v / sum(c.values()))} for k, v in sorted(c.items())}
              for g, c in sorted(groups.items())}
    negatives_on_linear = [f"{row['accession']}/{row['stratum']}" for row in rows
                           if row["label"] == "linear" and row["decided_by"] == "negatives"]
    counts_on_log = [f"{row['accession']}/{row['stratum']}" for row in rows
                     if row["label"] == "log" and row["decided_by"] == "counts"]
    return not negatives_on_linear and not counts_on_log, {
        "decided_by": shares, "negatives_on_linear": negatives_on_linear, "counts_on_log": counts_on_log}


def bank_verdicts(tables, models, cal, b2) -> tuple[list[dict], tuple[bool, dict]]:
    b2_bank = {b["id"]: b for b in b2["bank"]}
    out = []
    for t in tables:
        m = vsm.model_for(models, t["deposit"])[0]
        s = stratum_or_s1(cal, t["values"].shape[1])
        a = method.assess(t["values"], m, s.thresholds)
        out.append({"id": t["id"], "label": t["label"], "deposit": t["deposit"], "columns": a["columns"],
                    "stratum": s.name if cal.stratum_for(a["columns"]) else None, "gate": a["gate"],
                    "verdict": a["verdict"], "set": a["set"], "reason": a["reason"], "warning": a["warning"],
                    "scores": rdict(a["scores"]),
                    "typicality": {y: r(p["typicality"]) for y, p in a["parts"].items()} if a["parts"] else None,
                    "thresholds": rdict(s.thresholds),
                    "b2": {"verdict": b2_bank[t["id"]]["verdict"], "reason": b2_bank[t["id"]]["reason"]}})
    problems = []
    for b in out:
        if b["id"] in EXPECTED_LINEAR:
            want = ("linear", None)
        elif b["id"] in EXPECTED_LOG:
            want = ("log", None)
        elif b["id"] == IMPUTED:
            want = ("cant_tell", method.NO_GAPS_REASON)
        else:
            want = (b["b2"]["verdict"], b["b2"]["reason"])
        got = (b["verdict"], b["reason"] if b["id"] not in EXPECTED_LINEAR + EXPECTED_LOG else None)
        if got != want:
            problems.append(f"{b['id']}: {b['verdict']} ({b['reason']}); expected {want[0]} ({want[1]})")
    warned = sorted(b["id"] for b in out if b["scores"] is not None and b["warning"])
    missing = [i for i in (*EXPECTED_LINEAR, *EXPECTED_LOG, IMPUTED) if i not in {b["id"] for b in out}]
    ok = not problems and warned == sorted(WARNED) and not missing
    return out, (ok, {"problems": problems, "warned": warned, "not_in_bank": missing,
                      "verdicts": dict(Counter(b["verdict"] for b in out)),
                      "changed_from_b2": [f"{b['id']}: {b['b2']['verdict']} -> {b['verdict']}" for b in out
                                          if b["verdict"] != b["b2"]["verdict"]]})


def bank_variants(tables, models, cal, b2) -> tuple[list[dict], tuple[bool, dict]]:
    b2_items = {(it["table"], it["variant"]): it for it in b2["variants"]}
    items = []
    for t in labelled_tables(tables):
        m = vsm.model_for(models, t["deposit"])[0]
        for name, values, label in vsm.all_variants(t):
            s = stratum_or_s1(cal, values.shape[1])
            a = method.assess(values, m, s.thresholds)
            before = b2_items.get((t["id"], name), {})
            items.append({"table": t["id"], "variant": name, "label": label, "columns": a["columns"],
                          "gate": a["gate"], "verdict": a["verdict"], "set": a["set"], "reason": a["reason"],
                          "warning": a["warning"], "scores": rdict(a["scores"]), "b2_verdict": before.get("verdict")})
        print(f"  variants of {t['id']}: done", flush=True)
    labelled = [it for it in items if it["label"] in ("linear", "log")]
    wrong = [it for it in labelled if it["verdict"] == OTHER[it["label"]]]
    foreign_expect = {"zscore_genes": ("negatives", "log", None), "ranks": ("counts", "linear", None),
                      "presence": (None, "unlike_either", "no spread")}
    foreign_off = [f"{it['table']}/{it['variant']}: gate {it['gate']}, {it['verdict']} ({it['reason']})"
                   for it in items if it["variant"] in foreign_expect
                   and (it["gate"], it["verdict"], it["reason"]) != foreign_expect[it["variant"]]]
    share = len(wrong) / max(len(labelled), 1)
    by_variant = defaultdict(Counter)
    for it in items:
        kind = ("right" if it["verdict"] == it["label"] else
                "wrong" if it["label"] in OTHER and it["verdict"] == OTHER[it["label"]] else it["verdict"])
        by_variant[it["variant"]][kind] += 1
    return items, (share <= MAX_WRONG_VARIANTS and not foreign_off, {
        "labelled": len(labelled), "wrong": len(wrong), "share_wrong": r(share),
        "wrong_items": [f"{it['table']}/{it['variant']} ({it['label']} -> {it['verdict']})" for it in wrong],
        "foreign_not_as_predicted": foreign_off,
        "percentile_ranks": dict(Counter(it["verdict"] for it in items if it["variant"] == "percentile_ranks")),
        "warned": sum(1 for it in items if it["warning"]),
        "changed_from_b2": sum(1 for it in items if it["b2_verdict"] is not None and it["verdict"] != it["b2_verdict"]),
        "by_variant": {k: dict(v) for k, v in sorted(by_variant.items())}})


def check_baselines(tables) -> tuple[bool, dict]:
    readings, errors = {}, []
    for t in tables:
        readings[t["id"]] = {}
        for name, f in baselines.BASELINES.items():
            try:
                answer = f(t["values"])
            except Exception as e:  # noqa: BLE001 - every error is a finding here
                errors.append(f"{t['id']}/{name}: {type(e).__name__}: {e}")
                continue
            if answer not in ("linear", "log", None):
                errors.append(f"{t['id']}/{name}: answered {answer!r}")
            readings[t["id"]][name] = answer
    median_off = [i for i in (*SMALL_SCALE, *EXPECTED_LOG) if readings.get(i, {}).get("median_50") != "log"]
    others = {t["id"]: readings[t["id"]].get("median_50") for t in tables
              if t["label"] == "log" and t["id"] not in EXPECTED_LOG
              and not (np.nan_to_num(t["values"], nan=0.0) < 0).any()}
    tally = {name: dict(Counter(f"{t['label']}->{readings[t['id']].get(name)}" for t in tables))
             for name in baselines.BASELINES}
    return not errors and not median_off, {"errors": errors, "median_50_not_log": median_off,
                                           "median_50_other_log_tables": others, "tally": tally,
                                           "readings": readings}


def check_detect() -> tuple[bool, dict]:
    values = read_pbmc240()
    calibrated.load.cache_clear()
    t0 = time.perf_counter()
    rep = valuescale.detect(values)
    seconds = time.perf_counter() - t0
    ok = (values.shape[1] == 238 and rep.verdict == "linear" and rep.stratum == "S2+S3"
          and rep.calibration == calibrated.DEFAULT and rep.guarantee is not None and seconds < DETECT_SECONDS)
    return ok, {"shape": list(values.shape), "seconds": round(seconds, 3), "report": rep.to_json()}


def check_rehearsal() -> tuple[bool, dict]:
    out = OUT / "rehearsal.json"
    before = score_test.TEST_SCORED.exists()
    t0 = time.time()
    run = subprocess.run([sys.executable, "-m", "valuescale.corpus.score_test", "--rehearse", str(out)], cwd=REPO)
    after = score_test.TEST_SCORED.exists()
    detail = {"returncode": run.returncode, "seconds": round(time.time() - t0), "marked_before": before,
              "marked_after": after}
    if run.returncode != 0 or not out.exists():
        return False, detail
    res = json.loads(out.read_text(encoding="utf-8"))
    problems = []
    if res.get("split") != "calibration" or not res.get("rehearsal"):
        problems.append(f"split {res.get('split')}, rehearsal {res.get('rehearsal')}")
    want = {"S1": SIZE["S1"], "S2+S3": SIZE["S2+S3"]}
    for pool, classes in res["by_calibrated_stratum"].items():
        for c, t in classes.items():
            if t["n"] != want.get(pool):
                problems.append(f"{pool}/{c}: n {t['n']}, expected {want.get(pool)}")
    for scope in ("by_calibrated_stratum", "by_stratum"):
        for pool, classes in res[scope].items():
            for c, t in classes.items():
                if sum(t["counts"].values()) != t["n"]:
                    problems.append(f"{scope} {pool}/{c}: counts add to {sum(t['counts'].values())}, n {t['n']}")
                if any(v["interval"] is None or len(v["interval"]) != 2 for v in t["rates"].values()):
                    problems.append(f"{scope} {pool}/{c}: an interval is missing")
    if res["primary"]["tables"] != SIZE["S1"]:
        problems.append(f"primary: {res['primary']['tables']} tables")
    detail.update({"problems": problems, "deposits": res["deposits"], "subsamples": res["subsamples"],
                   "by_calibrated_stratum": {p: {c: {"n": t["n"], "counts": t["counts"], "miss": t["miss"],
                                                     "miss_interval": t["rates"]["miss"]["interval"],
                                                     "guarantee_contradicted": t["guarantee_contradicted"]}
                                                 for c, t in cs.items()}
                                             for p, cs in res["by_calibrated_stratum"].items()},
                   "primary": res["primary"],
                   "baselines": res["baselines"], "foreign": res.get("foreign")})
    return not problems and not before and not after, detail


def calibrate_part() -> int:
    started = time.time()
    design = json.loads((OUT / "design.json").read_text(encoding="utf-8"))
    no_gaps = design["rows"]["B4_no_gaps"]
    accepted = not no_gaps["pass"] and no_gaps_as_accepted(no_gaps)
    if not (design["rows"]["B4_model"]["pass"] and (no_gaps["pass"] or accepted)):
        raise SystemExit("design.json: B4_model or B4_no_gaps did not pass (and not as the owner accepted), so the "
                         "calibration does not run; the owner decides (valuescale/bank/expectations/b4.json)")
    b2 = json.loads(B2_REPORT.read_text(encoding="utf-8"))
    tables, rows, _ = bank_and_design()
    models = vsm.fit_models(rows)
    full = models["*"][0]

    print("Calibration", flush=True)
    walk = [json.loads(line) for line in (CORPUS / "walk.jsonl").read_text(encoding="utf-8").splitlines() if line]
    audit = json.loads((CORPUS / "audit.json").read_text(encoding="utf-8"))
    records = calibrate.calibration_records(walk, audit)
    data, cal_rows = calibrate.build(records, values_of, full, written=date.today().isoformat(),
                                     progress=lambda s: print(f"  {s}", flush=True))
    data = json.loads(json.dumps(data))
    if CALIBRATION.exists():
        frozen = json.loads(CALIBRATION.read_text(encoding="utf-8"))
        same = differences({k: v for k, v in data.items() if k != "written"},
                           {k: v for k, v in frozen.items() if k != "written"})
        if same:
            raise SystemExit(f"{CALIBRATION} exists and differs from this build: {same}")
        data = frozen
        print(f"  {CALIBRATION.name} exists and matches this build; left as it is", flush=True)
    else:
        write_json(CALIBRATION, data)
        print(f"  wrote {CALIBRATION}", flush=True)
    calibrated.load.cache_clear()
    cal = calibrated.load()
    write_json(OUT / "calibration_rows.json", {"calibration": cal.id, "corpus_sha256": cal.corpus_sha256,
                                               "rows": cal_rows})

    results = {"B4_model": (design["rows"]["B4_model"]["pass"], {"from": "design.json"}),
               "B4_no_gaps": (no_gaps["pass"], {"from": "design.json",
                                                "owner_accepted": OWNER_ACCEPTED["B4_no_gaps"] if accepted else None,
                                                "variants_decided": no_gaps["variants_decided"]})}
    results["B4_calibration_size"] = check_size(data, cal_rows)
    results["B4_thresholds"] = check_thresholds(data)
    results["B4_typicality_zero"] = check_typicality_zero(cal_rows)
    results["B4_calibration_coverage"] = check_coverage(data, cal_rows)
    results["B4_gated"] = check_gated(cal_rows)
    print("Bank verdicts", flush=True)
    bank_rows, results["B4_bank_verdicts"] = bank_verdicts(tables, models, cal, b2)
    print("Bank variants", flush=True)
    items, results["B4_bank_variants"] = bank_variants(tables, models, cal, b2)
    print("Baselines on the bank", flush=True)
    results["B4_baselines"] = check_baselines(tables)
    print("PBMC240", flush=True)
    results["B4_detect"] = check_detect()
    print("The rehearsal", flush=True)
    results["B4_rehearsal"] = check_rehearsal()

    expect = json.loads(EXPECTATIONS.read_text(encoding="utf-8"))
    report = {"step": "b4", "part": "calibrate", "run": datetime.now().isoformat(timespec="seconds"),
              "seconds": round(time.time() - started), "calibration": {k: v for k, v in data.items() if k != "model"},
              "rows": {k: {"pass": v[0], **v[1]} for k, v in results.items()},
              "bank": bank_rows, "variants": items}
    write_json(OUT / "report.json", report)
    (OUT / "report.md").write_text(render(report, expect, design), encoding="utf-8", newline="\n")
    for k, v in results.items():
        print(f"{k}: {'recorded' if v[0] is None else 'PASS' if v[0] else 'FAIL'}")
    return 0


def render(report: dict, expect: dict, design: dict) -> str:
    rows = report["rows"]
    out = ["# B4: the calibration of the protein detector", "",
           f"Run {report['run']} ({report['seconds']} s; the design part {design['run']}, {design['seconds']} s), "
           "by research/notebooks/value_scale_calibrate.py. Expectations: valuescale/bank/expectations/b4.json, "
           "written before the run.", "", "| Row | Result | Expected |", "|---|---|---|"]
    for k, text in expect["rows"].items():
        v = rows.get(k, {}).get("pass")
        result = "recorded" if v is None else "pass" if v else "**fail**"
        if rows.get(k, {}).get("owner_accepted"):
            result += ", accepted by the owner"
        out.append(f"| {k} | {result} | {text} |")
    cal = report["calibration"]
    out += ["", "## The calibration", "", f"`{cal['id']}`, alpha {cal['alpha']}, delta {cal['delta']}, "
            f"corpus sha256 `{cal['corpus_sha256']}` ({len(cal['corpus']['deposits'])} deposits).", "",
            "| Stratum | Columns | Class | n | k | Threshold |", "|---|---|---|---|---|---|"]
    for s in cal["strata"]:
        for y in calibrate.LABELS:
            t = s["thresholds"][y]
            out.append(f"| {s['name']} | {s['columns'][0]} to {s['columns'][1]} | {y} | {s['n'][y]} | {s['k'][y]} | "
                       f"{'none' if t is None else f'{t:.4f}'} |")
    cov = rows["B4_calibration_coverage"]
    out += ["", "Calibration deposits under their class's threshold:", ""]
    out += [f"- {k}: {len(v['misses'])} of {v['n']} (k = {v['k']})" for k, v in cov.items() if isinstance(v, dict)
            and "misses" in v]
    out += ["", "What would decide each calibration subsample before its score (B4_gated):", ""]
    for g, c in rows["B4_gated"]["decided_by"].items():
        out.append(f"- {g}: " + ", ".join(f"{k} {v['count']} ({v['share']:.0%})" for k, v in c.items()))
    out += ["", "## The bank", "", "| Table | Label | Columns | Verdict | B2 | Reason | Warning |", "|---|---|---|---|---|---|---|"]
    for b in report["bank"]:
        out.append(f"| {b['id']} | {b['label']} | {b['columns']} | {b['verdict']} | {b['b2']['verdict']} | "
                   f"{b['reason'] or ''} | {'yes' if b['warning'] else ''} |")
    bv = rows["B4_bank_verdicts"]
    if bv["problems"]:
        out += ["", "Not as expected:", ""] + [f"- {p}" for p in bv["problems"]]
    var = rows["B4_bank_variants"]
    out += ["", f"Variants: {var['wrong']} of {var['labelled']} labelled variants given the other class alone "
            f"({var['share_wrong']:.1%}); {var['changed_from_b2']} verdicts changed from B2.", ""]
    out += [f"- {w}" for w in var["wrong_items"]]
    det = rows["B4_detect"]
    out += ["", "## PBMC240", "", f"{det['shape'][0]} x {det['shape'][1]}: {det['report']['verdict']} in "
            f"{det['report']['stratum']}, {det['seconds']} s.", "", f"> {det['report']['guarantee']}"]
    reh = rows["B4_rehearsal"]
    out += ["", "## The rehearsal (calibration split; checks the code, not the method)", ""]
    if "by_calibrated_stratum" in reh:
        out += ["| Stratum | Class | n | Right | Wrong | Can't tell | Unlike either | Miss (95% CI) |",
                "|---|---|---|---|---|---|---|---|"]
        for p, cs in reh["by_calibrated_stratum"].items():
            for c, t in cs.items():
                lo, hi = t["miss_interval"]
                n = t["counts"]
                out.append(f"| {p} | {c} | {t['n']} | {n['right']} | {n['wrong']} | {n['cant_tell']} | "
                           f"{n['unlike_either']} | {t['miss']} ({lo:.3f} to {hi:.3f}) |")
        pr = reh["primary"]
        out += ["", f"Whole linear tables: the detector reads {pr['detector_wrong']} of {pr['tables']} wrong, "
                f"median-50 {pr['median_50_wrong']}; one-sided McNemar p = {pr['p_value']:.3g}.", ""]
        out += ["| Baseline | Linear: right / wrong / no answer | Constructed log: right / wrong / no answer |",
                "|---|---|---|"]
        for name, b in reh["baselines"].items():
            out.append(f"| {name} | {b['linear']['right']} / {b['linear']['wrong']} / {b['linear']['no_answer']} | "
                       f"{b['constructed_log']['right']} / {b['constructed_log']['wrong']} / "
                       f"{b['constructed_log']['no_answer']} |")
    if reh.get("problems"):
        out += ["", "Problems:", ""] + [f"- {p}" for p in reh["problems"]]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--part", choices=("design", "calibrate"), required=True)
    args = parser.parse_args(argv)
    return design_part() if args.part == "design" else calibrate_part()


if __name__ == "__main__":
    sys.exit(main())
