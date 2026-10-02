"""T1 NB3c: recalibrating the out-of-distribution (OOD) threshold. Follows
T1 NB3b's NO GO (research/notebook-run-history.md, entry 18), which found
two causes shared by every score:

1. Thresholds fitted on validation-split cells (seen by the encoders during
   early stopping) under-cover test-split cells about 2x.
2. Per-upload gene z-scoring makes a cell's score depend on what else is in
   its upload: single-cell-type uploads abstained on 34%, broad ones on
   0-1%; B cells on 39%.

Rules fixed before the run (owner chose NB3c, 2026-10-02):
- Calibration on cells the encoders never saw: the test split is halved by
  class (TE_CAL, TE_EVAL); a new calibration suite is drawn from TE_CAL and a
  new evaluation suite from TE_EVAL, with NB1's own generator and new seeds.
  The masked index stays on training cells, so no cell is shared.
  Declared: TE_EVAL's cells were scored once by NB3b, in other uploads, so
  the evaluation uploads are fresh but the cells are not. Khoury 2026 stays
  the untouched test.
- Candidates: four scores (maxcos, energy, knn50_ref, relmaha_cal; NB3b's
  definitions) x four threshold schemes, each a 5% conformal quantile:
    band       per band of observed genes (NB3b's);
    class      per predicted class (the ensemble's argmax; Mondrian);
    div        per band of upload diversity, exp(entropy of the upload's
               mean predicted probabilities): under 1.5, 1.5 to 3, 3 and over;
    class_div  per predicted class within a diversity band.
  A key with fewer than 300 calibration cells falls back (class_div to
  class, then pooled; the others to pooled).
- Choice, on the new calibration suite's SELECT half: eligible if false
  abstention there is at most 7.5% overall and at most 15% in every
  scenario; the highest mean rejection over the three controls (scrambled
  cells, uploads of one repeated cell, held-out classes) wins. Ties within
  0.005 go to the simpler scheme, then the simpler score.
- Go / no-go on the new evaluation suite: identical to NB3b's (false
  abstention at most 6% overall and 10% in every scenario, pooled over cells
  with at least 200 observed genes; at least 90% of scrambled cells
  rejected; a higher AUROC than max cosine on every control).
- Real data (CD34+ progenitors, Fulcher, PBMC240, SCoPE2) reported, never
  used to choose.

It reuses NB3b's code (research/notebooks/t1_nb3b_ood_and_flags.py) for the
data, the members, the reference features and every score.

    python research/notebooks/t1_nb3c_ood_calibration.py           # from the repository root
    python research/notebooks/t1_nb3c_ood_calibration.py --smoke   # a few calibration uploads, to scratch
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t1_nb3b_ood_and_flags as nb3b  # noqa: E402  (data, members, reference features, scores)
from t1_nb3b_ood_and_flags import (  # noqa: E402
    BANDS, C, DEVICE, MEMBER_DIR, MEMBER_FILES, MEMBERS, NB1, OOD_THR_NB2, REPO, T1, TE, TR, auc_in_vs_out, band_of,
    classes, core, maha_params, reference_features, sg, unit, y_all,
)

T0 = time.time()
OUT = T1 / "NB3c"
TABLES = REPO / "research" / "notebook-outputs" / "nb3c"

# ---- rules fixed before the run ---------------------------------------------
TARGET = 0.05
SELECT_MAX_FALSE, SELECT_MAX_SCENARIO = 0.075, 0.15
MIN_KEY_CELLS = 300
DIV_EDGES = (1.5, 3.0)
SCORES = ("maxcos", "energy", "knn50_ref", "relmaha_cal")  # simplest first
SCHEMES = ("band", "class", "div", "class_div")  # simplest first
N_UPLOADS, SPLIT_SEED, CAL_SEED, EVAL_SEED = 240, 3, 31, 47
TIE = 0.005
GO = nb3b.GO


def log(msg: str) -> None:
    print(f"[{(time.time() - T0) / 60:5.1f} min] {msg}", flush=True)


def split_test() -> tuple[np.ndarray, np.ndarray]:
    """TE halved by class: every class with at least 2 test cells has cells on both sides."""
    rng = np.random.default_rng(SPLIT_SEED)
    cal, ev = [], []
    for c in np.unique(y_all[TE]):
        cells = rng.permutation(TE[y_all[TE] == c])
        half = len(cells) // 2
        cal.append(cells[:half])
        ev.append(cells[half:])
    return np.sort(np.concatenate(cal)), np.sort(np.concatenate(ev))


def diversity(P: np.ndarray) -> float:
    """Effective number of cell types the ensemble sees in the upload (label-free)."""
    p = P.mean(0)
    p = p[p > 0]
    return float(np.exp(-(p * np.log(p)).sum()))


def keys(scheme: str, nobs: np.ndarray, pred: np.ndarray, div: float) -> np.ndarray:
    d = np.digitize(div, DIV_EDGES)
    if scheme == "band":
        return band_of(nobs)
    if scheme == "class":
        return pred
    if scheme == "div":
        return np.full(len(pred), d)
    return pred * 10 + d  # class_div


def fit_scheme(scheme: str, cells: pd.DataFrame, score: str) -> dict:
    """cells: one row per calibration cell with >= 200 observed genes: score columns, nobs, pred, div."""
    s = cells[score].to_numpy()
    out = {"pooled": float(np.quantile(s, TARGET)), "keys": {}, "class": {}}
    nobs, pred, d = cells.nobs.to_numpy(), cells.pred.to_numpy(), np.digitize(cells["div"].to_numpy(), DIV_EDGES)
    k = {"band": band_of(nobs), "class": pred, "div": d, "class_div": pred * 10 + d}[scheme]  # as keys() does per upload
    for key in np.unique(k):
        if (k == key).sum() >= MIN_KEY_CELLS:
            out["keys"][int(key)] = float(np.quantile(s[k == key], TARGET))
    if scheme == "class_div":  # fallback level
        pred = cells.pred.to_numpy()
        for c in np.unique(pred):
            if (pred == c).sum() >= MIN_KEY_CELLS:
                out["class"][int(c)] = float(np.quantile(s[pred == c], TARGET))
    return out


def thresholds_for(scheme: str, thr: dict, nobs: np.ndarray, pred: np.ndarray, div: float) -> np.ndarray:
    k = keys(scheme, nobs, pred, div)
    out = np.empty(len(k))
    for i, key in enumerate(k):
        if int(key) in thr["keys"]:
            out[i] = thr["keys"][int(key)]
        elif scheme == "class_div" and int(pred[i]) in thr["class"]:
            out[i] = thr["class"][int(pred[i])]
        else:
            out[i] = thr["pooled"]
    return out


def cell_table(recs: list[dict]) -> pd.DataFrame:
    """One row per cell with >= 200 observed genes: scores, nobs, predicted class, upload diversity, scenario."""
    rows = []
    for r in recs:
        ok = r["nobs"] >= BANDS[0]
        if not ok.any():
            continue
        df = pd.DataFrame({k: r["s"][k][ok] for k in SCORES})
        df["nobs"], df["pred"], df["div"] = r["nobs"][ok], r["P"].argmax(1)[ok], r["div"]
        df["scenario"], df["upload"] = r["scenario"], r["id"]
        if "y" in r:
            df["y"] = r["y"][ok]
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def rejected(cells: pd.DataFrame, score: str, scheme: str, thr: dict) -> np.ndarray:
    out = np.zeros(len(cells), bool)
    for up, g in cells.groupby("upload", sort=False):
        t = thresholds_for(scheme, thr, g.nobs.to_numpy(), g.pred.to_numpy(), float(g["div"].iloc[0]))
        out[g.index.to_numpy()] = g[score].to_numpy() < t
    return out


def main() -> None:
    smoke = "--smoke" in sys.argv
    out_dir, tables = (T1 / "NB3c_smoke", T1 / "NB3c_smoke") if smoke else (OUT, TABLES)
    out_dir.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    te_cal, te_eval = split_test()
    cal = sg.make_suite("calib_v3c", te_cal, y_all[te_cal], classes, N_UPLOADS, CAL_SEED)
    ev = sg.make_suite("eval_v3c", te_eval, y_all[te_eval], classes, N_UPLOADS, EVAL_SEED)
    assert not set(te_cal) & set(te_eval) and not set(te_cal) & set(TR)
    cal_fit = [s for u, s in enumerate(cal) if (u // 14) % 2 == 0]
    cal_sel = [s for u, s in enumerate(cal) if (u // 14) % 2 == 1]
    if smoke:  # plumbing only, and never the evaluation suite
        cal_fit, cal_sel, ev = cal_fit[:28:3], cal_sel[:28:3], cal_sel[1:42:3]
    (out_dir / "suites.json").write_text(json.dumps({"te_cal": te_cal.tolist(), "te_eval": te_eval.tolist(),
                                                     "calib": cal, "eval": ev}) + "\n")
    log(f"TE {len(TE)} cells -> TE_CAL {len(te_cal)}, TE_EVAL {len(te_eval)}; "
        f"CAL FIT {len(cal_fit)}, CAL SEL {len(cal_sel)}, EVAL {len(ev)} uploads")

    # members and reference features, as NB3b builds them
    X_raw = nb3b.load_rna()
    MU, SD = torch.from_numpy(X_raw.mean(0)).to(DEVICE), torch.from_numpy(X_raw.std(0)).to(DEVICE)
    XG = torch.from_numpy(X_raw).to(DEVICE, dtype=torch.float16)
    models = nb3b.load_members()
    ref = {}
    for name, f in zip(MEMBERS, MEMBER_FILES):
        Z, H = reference_features(models[name], XG, MU, SD)
        served = np.load(MEMBER_DIR / f"V2_seed{name[-1]}_reference_latent_f16.npy").astype(np.float32)
        assert np.median((Z * served).sum(1)) > 0.9999, f"{name} does not reproduce the served reference"
        ref[name] = {"z_tr": unit(torch.from_numpy(Z[TR]).to(DEVICE).float()).half(), "y_tr_t": torch.from_numpy(y_all[TR]).to(DEVICE),
                     "cen": torch.from_numpy(core.centroids_from(Z[TR], y_all[TR], C)).to(DEVICE),
                     "h_ref": unit(torch.from_numpy(H[TR]).to(DEVICE).float()).half(), "y_ref_t": torch.from_numpy(y_all[TR]).to(DEVICE),
                     "maha_ref": maha_params(H[TR], y_all[TR]),
                     "z_all": unit(torch.from_numpy(Z).to(DEVICE).float()).half(), "cen_all": torch.from_numpy(core.centroids_from(Z, y_all, C)).to(DEVICE),
                     "h_all": unit(torch.from_numpy(H).to(DEVICE).float()).half(), "y_all_t": torch.from_numpy(y_all).to(DEVICE),
                     "maha_all": maha_params(H, y_all)}
    del XG
    torch.cuda.empty_cache()
    log("members reproduce the served reference latents")

    def encode(specs, label, **kw):
        recs = [nb3b.upload_record(s, X_raw, models, **kw) for s in specs]
        log(f"encoded {label}: {len(recs)} uploads, {sum(len(r['y']) for r in recs):,} cells")
        return recs

    # the masked index, from training cells drawn like the calibration uploads (NB3b's construction)
    sub_rng = np.random.default_rng(2026)
    index = encode([nb3b.tr_substitute(s, sub_rng) for s in cal_fit], "masked index (training cells)")
    for name in MEMBERS:
        Hc = np.concatenate([r["feat"][name][1] for r in index]).astype(np.float32)
        yc = np.concatenate([r["y"] for r in index])
        ref[name].update({"h_cal": unit(torch.from_numpy(Hc).to(DEVICE)).half(), "y_cal_t": torch.from_numpy(yc).to(DEVICE),
                          "maha_cal": maha_params(Hc, yc)})
    del index
    scorer = nb3b.Scorer(ref)

    def score(recs, exclude=None):
        for r in recs:
            r["s"], r["P"] = scorer.scores(r["feat"], exclude)
            r["div"] = diversity(r["P"])
        return recs

    fit = score(encode(cal_fit, "CAL FIT"))
    sel = score(encode(cal_sel, "CAL SELECT"))

    def control_cells(recs, specs, label):
        scr = score([nb3b.upload_record(s, X_raw, models, transform=nb3b.scramble(s["seed"] + 101)) for s in specs])
        rep = score([nb3b.upload_record(s, X_raw, models, cell_idx=[s["cell_idx"][0]] * min(nb3b.REPEAT_CELLS, len(s["cell_idx"])))
                     for s in specs])
        ys = np.concatenate([r["y"] for r in recs])
        tr_counts = np.bincount(y_all[TR], minlength=C)
        held = [c for c in range(C) if (ys == c).sum() >= nb3b.HELD_OUT_MIN_SEL_CELLS and tr_counts[c] >= nb3b.HELD_OUT_MIN_TR_CELLS]
        held_out, held_keep = [], []
        for c in held:
            for r in recs:
                for mask, sink in ((r["y"] == c, held_out), (r["y"] != c, held_keep)):
                    if not mask.any():
                        continue
                    sub = {n: (r["feat"][n][0][mask], r["feat"][n][1][mask]) for n in MEMBERS}
                    s, P = scorer.scores(sub, exclude=c)
                    sink.append({"id": f"{r['id']}_held{c}", "scenario": r["scenario"], "nobs": r["nobs"][mask],
                                 "s": s, "P": P, "div": r["div"], "held": c})
        log(f"controls on {label}: {len(scr)} scrambled, {len(rep)} repeated, {len(held)} classes held out")
        return {"scrambled": cell_table(scr), "repeated": cell_table(rep),
                "held_out": cell_table(held_out), "held_keep": cell_table(held_keep)}

    def evaluate(in_cells, ctrl, thr_all, label):
        rows = []
        for score_name in SCORES:
            for scheme in SCHEMES:
                thr = thr_all[(score_name, scheme)]
                rj = rejected(in_cells, score_name, scheme, thr)
                by_scen = pd.Series(rj).groupby(in_cells.scenario.to_numpy()).mean()
                row = {"score": score_name, "scheme": scheme, "false_abstention": float(rj.mean()),
                       "worst_scenario": float(by_scen.max()), "worst_scenario_name": by_scen.idxmax()}
                for name in ("scrambled", "repeated", "held_out"):
                    row[f"rejected_{name}"] = float(rejected(ctrl[name], score_name, scheme, thr).mean())
                row["rejected_mean"] = (row["rejected_scrambled"] + row["rejected_repeated"] + row["rejected_held_out"]) / 3
                # threshold-free separation, as NB3b reports it
                row["auc_scrambled"] = auc_in_vs_out(in_cells[score_name], ctrl["scrambled"][score_name])
                row["auc_repeated"] = auc_in_vs_out(in_cells[score_name], ctrl["repeated"][score_name])
                row["auc_held_out"] = auc_in_vs_out(ctrl["held_keep"][score_name], ctrl["held_out"][score_name])
                rows.append(row)
        table = pd.DataFrame(rows)
        log(f"{label}: scored {len(table)} score x scheme pairs")
        return table

    fit_cells = cell_table(fit)
    THR = {(sc, sch): fit_scheme(sch, fit_cells, sc) for sc in SCORES for sch in SCHEMES}
    sel_cells = cell_table(sel)
    CAND = evaluate(sel_cells, control_cells(sel, cal_sel, "CAL SELECT"), THR, "CAL SELECT")
    CAND.to_csv(tables / "candidates_calsel.csv", index=False, float_format="%.5f")
    elig = CAND[(CAND.false_abstention <= SELECT_MAX_FALSE) & (CAND.worst_scenario <= SELECT_MAX_SCENARIO)].copy()
    note = None
    if elig.empty:
        elig, note = CAND.copy(), "no pair met the SELECT bounds; chose among all"
    elig["rank"] = elig.scheme.map(SCHEMES.index) * 10 + elig.score.map(SCORES.index)
    best = elig.rejected_mean.max()
    pick = elig[elig.rejected_mean >= best - TIE].sort_values("rank").iloc[0]
    SCORE, SCHEME = pick.score, pick.scheme
    log(f"chosen on CAL SELECT: {SCORE} with {SCHEME} thresholds" + (f" ({note})" if note else ""))
    print(CAND.round(4).to_string(index=False))

    # final thresholds on the whole new calibration suite
    all_cal = pd.concat([fit_cells, sel_cells], ignore_index=True)
    THR_FINAL = {(sc, sch): fit_scheme(sch, all_cal, sc) for sc in SCORES for sch in SCHEMES}
    del fit, sel

    # the new evaluation suite, once
    ev_recs = score(encode(ev, "EVAL (new suite, TE_EVAL cells)"))
    ev_cells = cell_table(ev_recs)
    EVC = evaluate(ev_cells, control_cells(ev_recs, ev, "EVAL"), THR_FINAL, "EVAL")
    EVC.to_csv(tables / "eval_candidates.csv", index=False, float_format="%.5f")
    chosen = EVC[(EVC.score == SCORE) & (EVC.scheme == SCHEME)].iloc[0]
    today = EVC[(EVC.score == "maxcos") & (EVC.scheme == SCHEME)].iloc[0]
    rj = rejected(ev_cells, SCORE, SCHEME, THR_FINAL[(SCORE, SCHEME)])
    by_scen = pd.Series(rj).groupby(ev_cells.scenario.to_numpy()).mean()
    by_class = pd.DataFrame({"class": [classes[int(c)] for c in ev_cells.y], "rejected": rj}).groupby("class").rejected.agg(["mean", "size"])
    by_scen.rename("false_abstention").to_csv(tables / "eval_false_abstention_by_scenario.csv", float_format="%.5f")
    by_class.to_csv(tables / "eval_false_abstention_per_class.csv", float_format="%.5f")
    nb2_rule = float(((ev_cells.maxcos < OOD_THR_NB2)).mean())
    go = {"false_overall": bool(chosen.false_abstention <= GO["false_overall"]),
          "false_every_scenario": bool(chosen.worst_scenario <= GO["false_scenario"]),
          "scrambled_rejected": bool(chosen.rejected_scrambled >= GO["scrambled_rejected"]),
          "beats_maxcos_every_control": bool(SCORE == "maxcos" or all(chosen[c] > today[c] for c in ("auc_scrambled", "auc_repeated", "auc_held_out")))}
    log(f"GO/NO-GO: {go} -> {'GO' if all(go.values()) else 'NO GO'}")

    # real data, reported only
    from benchmark import baselines_v31, datasets
    from service.pipeline import alignment, pipeline as svc, reference as svc_reference
    feature_genes = svc_reference.load_feature_space_genes()
    ref_all = {n: {**ref[n], "z_tr": ref[n]["z_all"], "y_tr_t": ref[n]["y_all_t"], "cen": ref[n]["cen_all"],
                   "h_ref": ref[n]["h_all"], "y_ref_t": ref[n]["y_all_t"], "maha_ref": ref[n]["maha_all"]} for n in MEMBERS}
    real_scorer = nb3b.Scorer(ref_all)
    real = {"Furtwängler 2025 CD34+ HSPCs (out of reference)": datasets.load_furtwangler2025_upload(),
            "Fulcher 2026 PBMCs": datasets.load_fulcher2026_upload(),
            "PBMC240 raw": alignment.parse_matrix_csv(baselines_v31.PBMC240.read_text()),
            "SCoPE2 (macrophage/monocyte)": baselines_v31.scope2_raw()}
    real_rows, furt = [], None
    for label, raw in real.items():
        smoothed, aligned, _ = svc._prepare_query(feature_genes, raw)
        feat = nb3b.encode_upload(models, [smoothed.astype(np.float32)], aligned.mask.astype(np.float32))
        s, P = real_scorer.scores(feat)
        rec = {"id": label, "scenario": "real", "nobs": aligned.per_cell_observed_genes, "s": s, "P": P, "div": diversity(P)}
        cells = cell_table([rec])
        for sc, sch in ((SCORE, SCHEME), ("maxcos", SCHEME)):
            real_rows.append({"dataset": label, "score": sc, "scheme": sch, "upload_diversity": rec["div"], "cells": len(cells),
                              "rejected": float(rejected(cells, sc, sch, THR_FINAL[(sc, sch)]).mean())})
        real_rows.append({"dataset": label, "score": "maxcos (NB2 rule, 0.779)", "scheme": "fixed", "upload_diversity": rec["div"],
                          "cells": len(cells), "rejected": float((cells.maxcos < OOD_THR_NB2).mean())})
        if label.startswith("Furtwängler"):
            furt = pd.DataFrame({"cell_id": np.asarray(raw.cell_ids)[aligned.per_cell_observed_genes >= BANDS[0]],
                                 "rejected": rejected(cells, SCORE, SCHEME, THR_FINAL[(SCORE, SCHEME)])})
    REAL = pd.DataFrame(real_rows)
    REAL.to_csv(tables / "real_data_rejection.csv", index=False, float_format="%.5f")
    furt.merge(datasets.load_furtwangler2025_labels(), on="cell_id").groupby("cluster").rejected.mean() \
        .to_csv(tables / "furtwangler_rejection_by_cluster.csv", float_format="%.5f")
    print(REAL.round(4).to_string(index=False))

    summary = {"rules": {"target": TARGET, "select_max_false": SELECT_MAX_FALSE, "select_max_scenario": SELECT_MAX_SCENARIO,
                         "min_key_cells": MIN_KEY_CELLS, "div_edges": list(DIV_EDGES), "scores": list(SCORES),
                         "schemes": list(SCHEMES), "seeds": {"split": SPLIT_SEED, "calib": CAL_SEED, "eval": EVAL_SEED}, "go": GO},
               "smoke": smoke, "te_cal_cells": len(te_cal), "te_eval_cells": len(te_eval),
               "chosen": {"score": SCORE, "scheme": SCHEME, "note": note},
               "thresholds": THR_FINAL[(SCORE, SCHEME)], "eval_chosen": chosen.to_dict(),
               "eval_maxcos_same_scheme": today.to_dict(), "eval_nb2_rule_false_abstention": nb2_rule,
               "eval_false_by_scenario": by_scen.to_dict(), "go": go, "GO": all(go.values()),
               "real_data": REAL.to_dict(orient="records"), "minutes": round((time.time() - T0) / 60, 1)}
    (tables / "summary.json").write_text(json.dumps(summary, indent=2, default=float, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "ood_config.json").write_text(json.dumps({"score": SCORE, "scheme": SCHEME, "target": TARGET,
                                                         "div_edges": list(DIV_EDGES), "thresholds": THR_FINAL[(SCORE, SCHEME)]},
                                                        indent=2, default=float) + "\n")
    log(f"done: {'GO' if summary['GO'] else 'NO GO'}, chosen {SCORE} with {SCHEME} thresholds")


if __name__ == "__main__":
    main()
