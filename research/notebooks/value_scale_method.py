"""The raw-or-log plan's B2: the method, run on the bank and its variants.

Checks valuescale/bank/expectations/b2.json, written before the method
existed: which gate fires where, the statistics' invariance and drift, the
separation of the classes on the score, the conformal code in simulation,
and the verdicts on every bank table and variant.

The design rows are the bank's (research/benchmark/protocol-value-scale.md,
"Splits"): one subsample per stratum of each bank table no gate decides, and
a constructed log variant of each linear subsample. A table and its variants
are scored by a model fitted without the table's deposit, with rehearsal
thresholds from that model's design scores (no calibration split exists
until B3, so no guarantee is claimed).

Writes research/notebook-outputs/value_scale_b2/report.md and report.json.

Since protocol amendment 5 (B4) the package's class score is the
probability alone, a table with no missing value gets "can't tell", and
the bank's missing-value variants reach a column-first table too, so a
re-run of this notebook gives the amended method's answers, not the B2
report's. That report stays the record of its run; B4's notebook
(value_scale_calibrate.py) reuses this one's tables, design rows and models.

    python research/notebooks/value_scale_method.py
"""
from __future__ import annotations

import json
import math
import sys
import time
import warnings
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import value_scale_diagnostics as vsd  # noqa: E402
from valuescale import conformal, gates, method, score  # noqa: E402
from valuescale import statistics as st  # noqa: E402
from valuescale.corpus import strata, variants  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "value_scale_b2"
EXPECTATIONS = REPO / "valuescale" / "bank" / "expectations" / "b2.json"
TOL = 1e-9
SIM_REPEATS = 1000
SIM_SIZES = (59, 120, 200)
DRIFT = ("subsample_20", "subsample_50", "subsample_300", "missing_40", "missing_70")
SCALE_VARIANTS = ("times_1e-6", "times_1e-3", "times_1e3")
LOG_VARIANTS = ("log10", "ln", "log2_plus10", "log2_times_0.5", "log2_minus_min")
NEGATIVE_TABLES = {"scope2_export", "furtwangler_log2fc_nan", "cptac_ccrcc_tumor"}
SMALL_SCALE = {"pxd064083_t", "pxd064083_b"}
STRAY_PREDICTED = {"msv000099294_hmc3", "msv000099294_microglia", "pxd049412_a549_singlecells"}
PREDICTED_LINEAR = None  # every linear table with at least 20 columns (b2.json)
PREDICTED_LOG = {"khoury_column_normalized", "furtwangler_log2", "furtwangler_log2_nan", "furtwangler_log2_raw_sn",
                 "furtwangler_log2_imputed"}
MAY_CANT_TELL = {"furtwangler_log2_imputed"}
WRONG_ALLOWED_VARIANTS = {"subsample_20", "missing_70"}


def r(v, n=4):
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        return None if not math.isfinite(float(v)) else round(float(v), n)
    return v


def rdict(d, n=4):
    return None if d is None else {k: (rdict(v, n) if isinstance(v, dict) else r(v, n)) for k, v in d.items()}


# ------------------------------------------------------------------ tables

def load_tables(bank: dict) -> list[dict]:
    """Every bank table as a user would upload it: genes x cells, at most
    the service's 2,000 cells, drawn with D3's seed (as Phase A traced it)."""
    out = []
    for e in bank["entries"]:
        raw = vsd.load_entry(e)[0]
        values = np.asarray(raw.values, dtype=np.float64)
        if values.shape[1] > vsd.MAX_CELLS:
            keep = np.sort(variants.rng_for(e["id"], "d3").choice(values.shape[1], vsd.MAX_CELLS, replace=False))
            values = values[:, keep]
        out.append({"id": e["id"], "label": e["label"], "deposit": e["accession"], "values": values})
        print(f"  loaded {e['id']}: {values.shape[0]} x {values.shape[1]}", flush=True)
    return out


def linear_form(values: np.ndarray, label: str) -> np.ndarray:
    """The table on its linear scale with zeros missing, as the bank's
    variants make it (valuescale/corpus/variants.py, _positive)."""
    with np.errstate(all="ignore"):
        return np.where(values > 0, values, np.nan) if label == "linear" else np.exp2(values)


def b2_made(values: np.ndarray, label: str) -> list[tuple[str, np.ndarray, str]]:
    """The variants B2 adds: counts (linear), and per-protein percentile
    ranks (foreign; the protocol's foreign set)."""
    lin = linear_form(values, label)
    positive = lin[lin > 0]
    counts = np.round(lin / np.median(positive) * 5)
    pr = np.full(values.shape, np.nan)
    for i in range(values.shape[0]):
        ok = ~np.isnan(values[i])
        if ok.any():
            pr[i, ok] = st._ranks(values[i, ok]) / ok.sum()
    return [("counts", counts, "linear"), ("percentile_ranks", pr, "foreign")]


def all_variants(t: dict) -> list[tuple[str, np.ndarray, str]]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        made = list(variants.variants(t["id"], t["values"], t["label"]))
    return made + b2_made(t["values"], t["label"])


# ------------------------------------------------------------------ design

def design_rows(tables: list[dict]) -> tuple[list[score.DesignRow], list[dict]]:
    rows, info = [], []
    for t in tables:
        v = t["values"]
        if t["label"] not in ("linear", "log") or v.shape[1] < conformal.MIN_COLUMNS:
            continue
        if gates.gate(v).gate is not None:
            info.append({"id": t["id"], "excluded": "a gate decides the table"})
            continue
        for s in strata.strata_reached(v.shape[1]):
            sub, cols = strata.subsample(v, t["id"], s)
            candidates = [(t["label"], sub, "as deposited")]
            if t["label"] == "linear":
                form, logged = strata.constructed_log(sub, t["id"], s)
                candidates.append(("log", logged, f"constructed {form}"))
            for label, values, form in candidates:
                g = gates.gate(values)
                rec = {"id": t["id"], "deposit": t["deposit"], "stratum": s, "columns": int(values.shape[1]),
                       "label": label, "form": form}
                if g.gate is not None:
                    info.append({**rec, "excluded": f"the {g.gate} gate decides it"})
                    continue
                f = st.features(g.values)
                rows.append(score.DesignRow(f, label, t["deposit"], s))
                info.append({**rec, "features": rdict(f)})
    return rows, info


def fit_models(rows: list[score.DesignRow]) -> dict:
    """One model per design deposit, fitted without it, with its rehearsal
    thresholds; and one fitted on every row, for tables whose deposit gave
    no design row."""
    def thresholds(m):
        d = score.design_scores(m)
        return {y: conformal.rehearsal_threshold(d[y]) for y in conformal.CLASSES}
    full = score.fit(rows)
    models = {"*": (full, thresholds(full))}
    for d in sorted({row.deposit for row in rows}):
        m = score.fit([row for row in rows if row.deposit != d])
        models[d] = (m, thresholds(m))
    return models


def model_for(models: dict, deposit: str):
    return models.get(deposit, models["*"])


# ------------------------------------------------------------------ checks

def check_gates(items: list[dict], tables: list[dict]) -> tuple[bool, dict]:
    fired = defaultdict(set)
    stray_tables = set()
    linear_negative = []
    for it in items:
        key = (it["table"], it["variant"])
        if it["gate"]:
            fired[it["gate"]].add(key)
        if it["gate"] == "negatives" and it["label"] == "linear":
            linear_negative.append(key)
        if it["gate"] is None and it["stray_negatives"] and it["label"] in ("linear", "log"):
            stray_tables.add(it["table"])
    have_variants = {t["id"] for t in tables if t["values"].shape[1] >= conformal.MIN_COLUMNS and t["label"] in ("linear", "log")}
    expected_neg = {(t, "-") for t in NEGATIVE_TABLES}
    expected_neg |= {(t, "zscore_genes") for t in have_variants}
    expected_neg |= {(t, v) for t in SMALL_SCALE for v in ("log2", "log10", "ln", "log2_times_0.5")}
    expected_neg |= {(it["table"], it["variant"]) for it in items
                     if it["table"] in NEGATIVE_TABLES and it["variant"].startswith(("subsample_", "missing_"))}
    expected_counts = {(t, v) for t in have_variants for v in ("counts", "ranks")}
    detail = {
        "negatives_unexpected": sorted(map(list, fired["negatives"] - expected_neg)),
        "negatives_missing": sorted(map(list, expected_neg - fired["negatives"])),
        "negatives_on_linear_labelled": sorted(map(list, linear_negative)),
        "counts_unexpected": sorted(map(list, fired["counts"] - expected_counts)),
        "counts_missing": sorted(map(list, expected_counts - fired["counts"])),
        "stray_negative_tables": sorted(stray_tables),
        "stray_predicted": sorted(STRAY_PREDICTED),
    }
    ok = not any(detail[k] for k in ("negatives_unexpected", "negatives_missing", "negatives_on_linear_labelled",
                                     "counts_unexpected", "counts_missing")) and stray_tables == STRAY_PREDICTED
    return ok, detail


def check_invariance(feats: dict, tables: list[dict]) -> tuple[bool, dict]:
    worst = {name: 0.0 for name in st.FEATURES}
    failures, excluded, compared = [], [], 0

    def compare(tid, base_name, other, names):
        nonlocal compared
        a, b = feats.get((tid, base_name)), feats.get((tid, other))
        if a is None or b is None:
            return
        compared += 1
        for name in names:
            x, y = a[name], b[name]
            if math.isnan(x) and math.isnan(y):
                continue
            diff = math.inf if (math.isnan(x) != math.isnan(y)) else abs(x - y)
            worst[name] = max(worst[name], diff)
            if diff > TOL:
                failures.append({"table": tid, "base": base_name, "variant": other, "feature": name, "diff": r(diff, 12)})

    for t in tables:
        if t["values"].shape[1] < conformal.MIN_COLUMNS or t["label"] not in ("linear", "log"):
            continue
        if t["label"] == "linear":
            for v in SCALE_VARIANTS:
                compare(t["id"], "linear_form", v, st.FEATURES)
        if feats.get((t["id"], "log2_has_negative")):
            excluded.append(t["id"])
            continue
        for v in LOG_VARIANTS:
            compare(t["id"], "log2", v, st.CORE + st.BOTH)
    return not failures, {"comparisons": compared, "worst": {k: r(v, 12) for k, v in worst.items()},
                          "failures": failures[:50], "failure_count": len(failures), "excluded_log2_with_negatives": excluded}


def check_drift(drift: dict) -> tuple[bool, dict]:
    """drift[(label, condition)] = list of feature dicts."""
    med = {}
    for (label, cond), rows in drift.items():
        med[(label, cond)] = {name: float(np.nanmedian([f[name] for f in rows])) if any(not math.isnan(f[name]) for f in rows) else math.nan
                              for name in st.CORE}
    conditions = ["none"] + [c for c in DRIFT if ("linear", c) in med and ("log", c) in med]
    signs, flips = {}, []
    for name in st.CORE:
        base = np.sign(med[("linear", "none")][name] - med[("log", "none")][name])
        for c in conditions:
            s = np.sign(med[("linear", c)][name] - med[("log", c)][name])
            signs[f"{name}/{c}"] = int(s) if not np.isnan(s) else None
            if s != base:
                flips.append(f"{name}/{c}")
    predicted_direction = all(signs[f"{name}/none"] == 1 for name in st.CORE)
    bowley_rises, bowley_below = True, True
    for c in ("missing_40", "missing_70"):
        if ("log", c) in med:
            bowley_rises &= med[("log", c)]["bowley"] > med[("log", "none")]["bowley"]
            bowley_below &= med[("log", c)]["bowley"] < med[("linear", "none")]["bowley"]
    table = {f"{label}/{cond}": rdict(m) for (label, cond), m in sorted(med.items())}
    counts = {f"{label}/{cond}": len(rows) for (label, cond), rows in sorted(drift.items())}
    ok = not flips and predicted_direction and bowley_rises and bowley_below
    return ok, {"medians": table, "rows": counts, "signs": signs, "flips": flips, "linear_above_log_without_drift": predicted_direction,
                "log_bowley_rises_with_missingness": bool(bowley_rises), "and_stays_below_linear": bool(bowley_below)}


def check_separation(rows: list[score.DesignRow], models: dict) -> tuple[bool, dict]:
    lin, log = [], []
    for row in rows:
        m, _ = model_for(models, row.deposit)
        s = score.class_scores(row.features, m)
        (lin if row.label == "linear" else log).append(s["linear"] - s["log"])
    lin, log = np.array(lin), np.array(log)
    greater = (lin[:, None] > log[None, :]).mean()
    ties = (lin[:, None] == log[None, :]).mean()
    auc = float(greater + 0.5 * ties)
    return auc >= 0.95, {"auc": r(auc), "linear_rows": len(lin), "log_rows": len(log),
                         "linear_margin_below_0": int((lin <= 0).sum()), "log_margin_above_0": int((log >= 0).sum())}


def check_conformal() -> tuple[bool, dict]:
    from scipy import stats  # the diagnostics may use scipy; the package does not

    out, ok = {}, True
    ks = {n: conformal.umbrella_k(n) for n in (58, 59, 120, 200)}
    ok &= ks == {58: None, 59: 1, 120: 2, 200: 5}
    out["umbrella_k"] = {str(n): k for n, k in ks.items()}
    rng = np.random.default_rng(20261103)
    sims = {}
    for n in SIM_SIZES:
        k = conformal.umbrella_k(n)
        exact = conformal.binom_cdf(k - 1, n, conformal.ALPHA)
        miss = np.empty(SIM_REPEATS)
        for i in range(SIM_REPEATS):
            t = conformal.umbrella_threshold(rng.normal(size=n))
            miss[i] = 0.5 * (1 + math.erf(t / math.sqrt(2)))  # P(score < t), scores N(0, 1)
        over = float((miss > conformal.ALPHA).mean())
        se = math.sqrt(exact * (1 - exact) / SIM_REPEATS)
        good = abs(over - exact) <= 3 * se and exact <= conformal.DELTA and miss.mean() <= conformal.ALPHA
        ok &= good
        sims[str(n)] = {"k": k, "share_miss_over_alpha": r(over), "exact": r(exact), "se": r(se),
                        "mean_miss": r(float(miss.mean())), "pass": bool(good)}
    out["simulation"] = sims
    worst = 0.0
    for n in (7, 20, 59, 120, 300):
        for x in range(0, n + 1, max(1, n // 7)):
            lo, hi = conformal.clopper_pearson(x, n)
            slo = 0.0 if x == 0 else stats.beta.ppf(0.025, x, n - x + 1)
            shi = 1.0 if x == n else stats.beta.ppf(0.975, x + 1, n - x)
            one = conformal.clopper_pearson_lower(x, n)
            sone = 0.0 if x == 0 else stats.beta.ppf(0.05, x, n - x + 1)
            worst = max(worst, abs(lo - slo), abs(hi - shi), abs(one - sone))
    ok &= worst <= 1e-9
    out["clopper_pearson_worst_vs_scipy"] = worst
    return bool(ok), out


# ------------------------------------------------------------------ run

def main() -> int:
    started = time.time()
    expect = json.loads(EXPECTATIONS.read_text(encoding="utf-8"))
    bank = vsd.fetch.load_bank()
    print("Loading the bank", flush=True)
    tables = load_tables(bank)

    print("Design rows and models", flush=True)
    rows, design_info = design_rows(tables)
    models = fit_models(rows)

    print("Bank verdicts", flush=True)
    bank_rows = []
    for t in tables:
        m, th = model_for(models, t["deposit"])
        a = method.assess(t["values"], m, th)
        bank_rows.append({"id": t["id"], "label": t["label"], "deposit": t["deposit"], "columns": a["columns"],
                          "gate": a["gate"], "negative_share": r(a["negative_share"]), "stray_negatives": a["stray_negatives"],
                          "min_ties": a["min_ties"], "verdict": a["verdict"], "set": a["set"], "reason": a["reason"],
                          "scores": rdict(a["scores"]), "parts": {y: rdict(p) for y, p in a["parts"].items()} if a["parts"] else None,
                          "thresholds": rdict(th), "features": rdict(a["features"])})

    print("Variants", flush=True)
    items, feats = [], {}
    drift = defaultdict(list)
    for t in tables:
        if t["values"].shape[1] < conformal.MIN_COLUMNS or t["label"] not in ("linear", "log"):
            continue
        m, th = model_for(models, t["deposit"])
        g_table = gates.gate(t["values"])
        items.append({"table": t["id"], "variant": "-", "label": t["label"], "gate": g_table.gate,
                      "stray_negatives": g_table.stray_negatives,
                      "verdict": next(b["verdict"] for b in bank_rows if b["id"] == t["id"])})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            lin = linear_form(t["values"], t["label"])
            feats[(t["id"], "linear_form")] = st.features(gates.gate(lin).values)
            undecided = g_table.gate is None
            if undecided:
                own = feats[(t["id"], "linear_form")] if t["label"] == "linear" else st.features(g_table.values)
                drift[(t["label"], "none")].append(own)
                if t["label"] == "linear":
                    drift[("log", "none")].append(st.features(gates.gate(np.log2(np.where(lin > 0, lin, np.nan))).values))
            for name, values, vlabel in all_variants(t):
                g = gates.gate(values)
                f = st.features(g.values)
                feats[(t["id"], name)] = f
                if name == "log2":
                    feats[(t["id"], "log2_has_negative")] = bool(np.nanmin(values) < 0) if np.isfinite(values).any() else False
                a = method.assess(values, m, th)
                items.append({"table": t["id"], "variant": name, "label": vlabel, "gate": a["gate"],
                              "stray_negatives": a["stray_negatives"], "verdict": a["verdict"], "set": a["set"],
                              "reason": a["reason"], "scores": rdict(a["scores"])})
                if undecided and name in DRIFT:
                    drift[(t["label"], name)].append(f)
                    if t["label"] == "linear":
                        drift[("log", name)].append(st.features(gates.gate(np.log2(np.where(values > 0, values, np.nan))).values))
        print(f"  {t['id']}: done ({time.time() - started:.0f} s)", flush=True)

    print("Checks", flush=True)
    results = {}
    results["B2_gates"] = check_gates(items, tables)
    results["B2_invariance"] = check_invariance(feats, tables)
    results["B2_drift"] = check_drift(drift)
    results["B2_separation"] = check_separation(rows, models)
    results["B2_conformal"] = check_conformal()

    by_id = {b["id"]: b for b in bank_rows}
    bank_problems = []
    for b in bank_rows:
        right = b["verdict"] == b["label"]
        if b["columns"] < conformal.MIN_COLUMNS:
            if not (b["verdict"] == "cant_tell" and b["reason"] == "too few columns"):
                bank_problems.append(f"{b['id']}: {b['verdict']} (expected can't tell, too few columns)")
            continue
        if b["id"] in NEGATIVE_TABLES:
            if not (b["gate"] == "negatives" and b["verdict"] == "log"):
                bank_problems.append(f"{b['id']}: {b['verdict']} (expected log by the negatives gate)")
            continue
        if b["label"] == "linear" and not right:
            bank_problems.append(f"{b['id']}: {b['verdict']} (predicted linear)")
        if b["label"] == "log" and not (right or (b["id"] in MAY_CANT_TELL and b["verdict"] == "cant_tell")):
            bank_problems.append(f"{b['id']}: {b['verdict']} (predicted log)")
    wrong_bank = [b["id"] for b in bank_rows if b["label"] in ("linear", "log")
                  and b["verdict"] == ({"linear": "log", "log": "linear"}[b["label"]])]
    results["B2_verdicts_bank"] = (not bank_problems, {"problems": bank_problems, "wrong_class_alone": wrong_bank,
                                                       "verdicts": dict(Counter(b["verdict"] for b in bank_rows))})

    labelled = [it for it in items if it["variant"] != "-" and it["label"] in ("linear", "log")]
    wrong = [it for it in labelled if it["verdict"] == {"linear": "log", "log": "linear"}[it["label"]]]
    foreign_expect = {"zscore_genes": ("negatives", "log"), "ranks": ("counts", "linear"),
                      "presence": (None, "unlike_either"), "percentile_ranks": (None, "unlike_either")}
    foreign_off = [f"{it['table']}/{it['variant']}: gate {it['gate']}, {it['verdict']}" for it in items
                   if it["label"] == "foreign" and (it["gate"], it["verdict"]) != foreign_expect[it["variant"]]]
    share_wrong = len(wrong) / max(len(labelled), 1)
    ok_variants = share_wrong <= 0.05 and all(it["variant"] in WRONG_ALLOWED_VARIANTS for it in wrong) and not foreign_off
    by_variant = defaultdict(Counter)
    for it in items:
        if it["variant"] == "-":
            continue
        kind = ("right" if it["verdict"] == it["label"] else
                "wrong" if it["label"] in ("linear", "log") and it["verdict"] == {"linear": "log", "log": "linear"}[it["label"]] else
                it["verdict"])
        by_variant[it["variant"]][kind] += 1
    results["B2_verdicts_variants"] = (ok_variants, {
        "labelled": len(labelled), "wrong": len(wrong), "share_wrong": r(share_wrong),
        "wrong_items": [f"{it['table']}/{it['variant']} ({it['label']} -> {it['verdict']})" for it in wrong],
        "foreign_not_as_predicted": foreign_off,
        "by_variant": {k: dict(v) for k, v in sorted(by_variant.items())}})

    size = Counter((row.label, row.stratum) for row in rows)
    forms = Counter(i.get("form") for i in design_info if "features" in i)
    results["B2_design_size"] = (None, {"rows": {f"{label}/{s}": n for (label, s), n in sorted(size.items())},
                                        "linear_rows": sum(row.label == "linear" for row in rows),
                                        "log_rows": sum(row.label == "log" for row in rows),
                                        "deposits": len({row.deposit for row in rows}), "forms": dict(forms),
                                        "excluded": [i for i in design_info if "excluded" in i]})

    OUT.mkdir(parents=True, exist_ok=True)
    report = {"step": "b2", "run": datetime.now().isoformat(timespec="seconds"), "seconds": round(time.time() - started),
              "rows": {k: {"pass": v[0], **v[1]} for k, v in results.items()},
              "bank": bank_rows, "variants": items, "design": design_info,
              "full_model": models["*"][0].to_json(), "full_thresholds": rdict(models["*"][1])}
    (OUT / "report.json").write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    (OUT / "report.md").write_text(render(report, expect), encoding="utf-8", newline="\n")
    for k, v in results.items():
        print(f"{k}: {'recorded' if v[0] is None else 'PASS' if v[0] else 'FAIL'}")
    return 0


def render(report: dict, expect: dict) -> str:
    rows = report["rows"]
    out = ["# B2: the method on the bank", "",
           f"Run {report['run'][:10]}, {report['seconds']} s. Expectations: `valuescale/bank/expectations/b2.json`, "
           "written before the method existed. A table and its variants are scored by a model fitted without the "
           "table's deposit, with rehearsal thresholds from that model's design scores (no guarantee: there is no "
           "calibration split until B3).", "", "## Expectations", "", "| Row | Result | Detail |", "|---|---|---|"]
    for name, row in rows.items():
        result = "recorded" if row["pass"] is None else "PASS" if row["pass"] else "FAIL"
        detail = {k: v for k, v in row.items() if k not in ("pass", "by_variant", "medians", "signs", "excluded", "rows")}
        out.append(f"| {name} | {result} | `{json.dumps(detail)[:900]}` |")
    out += ["", "## Bank verdicts", "",
            "| Table | Label | Columns | Gate | Verdict | Linear score (typ., prob.) | Log score (typ., prob.) | Thresholds | Reason |",
            "|---|---|---|---|---|---|---|---|---|"]
    for b in report["bank"]:
        def cell(y):
            if not b["scores"]:
                return ""
            p = b["parts"][y]
            return f"{b['scores'][y]} ({p['typicality']}, {p['probability']})"
        th = f"{b['thresholds']['linear']} / {b['thresholds']['log']}" if b["scores"] else ""
        out.append(f"| {b['id']} | {b['label']} | {b['columns']} | {b['gate'] or ''} | {b['verdict']} | {cell('linear')} | "
                   f"{cell('log')} | {th} | {b['reason'] or ''} |")
    out += ["", "## Verdicts by variant", "", "| Variant | Right | Wrong | Can't tell | Unlike either |", "|---|---|---|---|---|"]
    for name, c in rows["B2_verdicts_variants"]["by_variant"].items():
        out.append(f"| {name} | {c.get('right', 0)} | {c.get('wrong', 0)} | {c.get('cant_tell', 0)} | {c.get('unlike_either', 0)} |")
    drift = rows["B2_drift"]
    out += ["", "## Drift: class medians of the core features", "", "| Class / condition | Rows | " + " | ".join(st.CORE) + " |",
            "|---|---|" + "---|" * len(st.CORE)]
    for key, m in drift["medians"].items():
        out.append(f"| {key} | {drift['rows'][key]} | " + " | ".join(str(m[n]) for n in st.CORE) + " |")
    size = rows["B2_design_size"]
    out += ["", "## Design rows", "", f"{size['linear_rows']} linear and {size['log_rows']} log rows from "
            f"{size['deposits']} deposits: " + ", ".join(f"{k} {v}" for k, v in size["rows"].items()) + ".", ""]
    if size["excluded"]:
        out += ["Excluded (a gate decides them):", ""] + [f"- {e['id']} {e.get('stratum', '')} {e.get('form', '')}: {e['excluded']}"
                                                         for e in size["excluded"]] + [""]
    out += ["## Features of each bank table", "", "| Table | " + " | ".join(st.FEATURES) + " |", "|---|" + "---|" * len(st.FEATURES)]
    for b in report["bank"]:
        if b["features"]:
            out.append(f"| {b['id']} | " + " | ".join(str(b["features"][n]) for n in st.FEATURES) + " |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.exit(main())
