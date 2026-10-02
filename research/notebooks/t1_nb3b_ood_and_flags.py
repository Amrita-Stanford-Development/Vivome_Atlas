"""T1 NB3b: an out-of-distribution (OOD) score on the encoders' 512-d hidden
features, and v3.1's service flags on RNA. Run on the Windows PC's GPU as a
script (owner, 2026-10-02), not on Colab.

Why: v3.1 abstains "outside_supported_region" when the members' mean max
cosine to any reference cell is below 0.779 (T1 NB2). NB2's own control
rejected 5.5% of real cells and 1.0% of scrambled ones, and the served model
flags 1.3% of 2,506 CD34+ progenitors the reference barely holds
(research/benchmark/results.md).

Rules fixed before the run (owner, 2026-10-02):
- Target false abstention on in-distribution RNA: 5%.
- Scores are chosen on RNA-derived controls only. The CD34+ progenitors
  (Furtwängler 2025) and the real protein datasets are reported, never used
  to choose.
- The calibration suite (validation-split cells) fits and chooses; the
  evaluation suite (test-split cells) is scored once, after every choice.

Sections:
0. Gate: reproduce NB2 before anything new (reference embeddings, its OOD
   threshold, its evaluation false abstention, its scrambled control). A miss stops the run.
1. Hidden features: every member, every reference and query cell, exactly as
   NB2 encodes them (nb1b_core / nb2_core, extracted from NB2's own cells).
2. Candidate scores (mean over the five members; higher = more in distribution):
   maxcos (today's), msp, energy, kNN on L2-normalised hidden features
   (k = 1, 10, 50) and relative Mahalanobis, the last two against either the
   training-split reference (full mask, as served) or a masked index: the
   calibration uploads redrawn from training-split cells (what
   in-distribution uploads look like, sharing no cell with either suite).
3. Thresholds: per band of observed genes, the 5th percentile of
   in-distribution scores (conformal at 95%), fitted on the calibration FIT half.
4. Choice, on the calibration SELECT half: among scores whose false
   abstention there is at most 1.5 x target, the highest mean AUROC over three
   controls (scrambled cells, uploads of one repeated cell, each large class
   held out of the reference). Ties within 0.005 go to the simpler score.
5. Evaluation suite, once: false abstention overall, by scenario, profile,
   band and class; the controls; then real data (reported only).
6. The flags on RNA: NB2's rule against each flag, and restricted mode.

Go / no-go on the evaluation suite: false abstention at most 6% overall and
at most 10% in every scenario (pooled over cells with at least 200 observed
genes, the rate a conformal threshold controls; the mean over uploads is
reported beside it); at least 90% of scrambled cells rejected; a higher AUROC
than today's max cosine on every control. A smoke run (--smoke) checks the
plumbing on calibration uploads only and never touches the evaluation suite.

Outputs: tables and summary.json in research/notebook-outputs/nb3b/; caches
and the chosen score's index in drive/Data/Results/Tier1_v31/NB3b/.

    python research/notebooks/t1_nb3b_ood_and_flags.py           # from the repository root
    python research/notebooks/t1_nb3b_ood_and_flags.py --smoke   # a few uploads, to scratch: plumbing only
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

warnings.filterwarnings("ignore")
T0 = time.time()
REPO = Path(__file__).resolve().parents[2]
DRIVE = REPO.parent / "drive" / "Data"
T1 = DRIVE / "Results" / "Tier1_v31"
NB1 = T1 / "NB1"
V3_EXP = DRIVE / "Results" / "ReferenceProjection_v3" / "export"
RNA_H5AD = DRIVE / "scRNA-seq" / "Blood_TSP1_30_version2d_10X_smartseq_scvi_Nov122024.h5ad"
OUT = T1 / "NB3b"
TABLES = REPO / "research" / "notebook-outputs" / "nb3b"
sys.path[:0] = [str(NB1), str(REPO / "research" / "notebook-outputs" / "nb2"), str(REPO)]
import nb1b_core as core  # noqa: E402  (NB2's cell 2, verbatim)
import nb2_core as n2  # noqa: E402  (NB2's cell 3, verbatim)
import sim_generator as sg  # noqa: E402  (NB1's)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SPEC = json.loads((REPO / "service" / "model" / "v3_1" / "nb2_spec_v31.json").read_text())
MEMBER_FILES = SPEC["encoder"]["members"]
MEMBERS = [f"V2_s{f.split('seed')[1][0]}" for f in MEMBER_FILES]
MEMBER_DIR = REPO / "service" / "model" / "v3_1" / "members"

# ---- rules fixed before the run ---------------------------------------------
TARGET = 0.05
SELECT_MAX_FALSE = 1.5 * TARGET
BANDS = (200, 500, 1000, 2000, 10**9)
MIN_BAND_CELLS = 500
K_GRID = (1, 10, 50)
TIE = 0.005
HELD_OUT_MIN_SEL_CELLS, HELD_OUT_MIN_TR_CELLS = 100, 300
REPEAT_CELLS = 300
GO = {"false_overall": 0.06, "false_scenario": 0.10, "scrambled_rejected": 0.90}
NB2_GATE = {"ood_threshold": (0.7789892554283142, 0.002), "eval_false_pct": (2.97, 0.3),
            "real_rejected_pct": (5.49, 0.6), "shuffled_rejected_pct": (0.96, 0.4)}
# simplest first: today's score, then the scores without a fitted index, then the indexed ones
COMPLEXITY = ["maxcos", "msp", "energy"] + [f"knn{k}_{v}" for v in ("ref", "cal") for k in K_GRID] + \
             ["relmaha_ref", "relmaha_cal"]


def log(msg: str) -> None:
    print(f"[{(time.time() - T0) / 60:5.1f} min] {msg}", flush=True)


# ---- data, as NB2 loads it ------------------------------------------------------
FS = pd.read_csv(V3_EXP / "feature_space_genes.csv")["gene"].astype(str).str.upper().tolist()
G = len(FS)
meta = pd.read_csv(V3_EXP / "reference_metadata.csv")
classes = meta[["class_idx", "class_name"]].drop_duplicates().sort_values("class_idx")["class_name"].astype(str).tolist()
C = len(classes)
cls2idx = {c: i for i, c in enumerate(classes)}
y_all = np.load(NB1 / "y_all.npy")
assert np.array_equal(y_all, meta["class_idx"].values)
sp = np.load(NB1 / "splits_seed0.npz")
TR, VA, TE = sp["train"], sp["val"], sp["test"]
PROF = dict(np.load(NB1 / "mask_profiles.npz"))
CALIB = json.loads((NB1 / "sim_suite_calib_v1.json").read_text())
EVAL = json.loads((NB1 / "sim_suite_eval_v1.json").read_text())
CAL_FIT = [s for u, s in enumerate(CALIB) if (u // 14) % 2 == 0]  # thresholds
CAL_SEL = [s for u, s in enumerate(CALIB) if (u // 14) % 2 == 1]  # the choice


def tr_substitute(spec: dict, rng) -> dict:
    """The same upload (classes, composition, masking seed) drawn from
    training-split cells instead. The calibration uploads reuse validation
    cells (77,086 draws of 11,996), so an index built from them would hold
    near-copies of the cells it scores; training cells are in neither suite."""
    by_class = {c: TR[y_all[TR] == c] for c in np.unique(y_all[TR])}
    idx = [int(rng.choice(by_class[c])) for c in y_all[np.asarray(spec["cell_idx"])] if c in by_class]
    return {**spec, "id": f"{spec['id']}_tr", "cell_idx": idx}
GRP = np.array([sorted(set(n2.group_of(c) for c in classes)).index(n2.group_of(c)) for c in classes])
LIN = np.array([sorted(set(sg.lineage_of(c) for c in classes)).index(sg.lineage_of(c)) for c in classes])
TEMPS = np.array([SPEC["assignment"]["temperature"][f] for f in MEMBER_FILES])
QHAT = np.array([SPEC["conformal"]["qhat_by_class"][c] for c in classes])
OOD_THR_NB2 = SPEC["ood"]["threshold"]


def load_rna() -> np.ndarray:
    with h5py.File(RNA_H5AD, "r") as f:
        var = f["var"]
        gnode = var[var.attrs["_index"]] if "_index" in var.attrs else var["_index"]
        rna_genes = pd.Index(np.array(gnode).astype(str)).str.upper()
        layer = f["layers"]["log_normalized"] if ("layers" in f and "log_normalized" in f["layers"]) else f["X"]
        n_cells, n_col = int(layer.attrs["shape"][0]), int(layer.attrs["shape"][1])
        cols = rna_genes.get_indexer(pd.Index(FS))
        assert (cols >= 0).all()
        colmap = -np.ones(n_col, dtype=np.int64)
        colmap[cols] = np.arange(G)
        X = np.zeros((n_cells, G), dtype=np.float32)
        indptr = layer["indptr"][:]
        data, indices = layer["data"][:], layer["indices"][:]
    for r in range(n_cells):
        s, e = int(indptr[r]), int(indptr[r + 1])
        if e > s:
            ind = indices[s:e]
            keep = colmap[ind] >= 0
            if keep.any():
                X[r, colmap[ind[keep]]] = data[s:e][keep]
    return X


# ---- models and reference features --------------------------------------------
def load_members() -> dict:
    mod = np.load(V3_EXP / "module_assignment.npy")
    assign = torch.zeros(G, int(mod.max() + 1))
    assign[torch.arange(G), torch.from_numpy(mod.astype(np.int64))] = 1.0
    assign = assign.to(DEVICE)
    models = {}
    for name, f in zip(MEMBERS, MEMBER_FILES):
        m = core.RefModelV(G, C, (1024, 512), 0.1, 128, assign, 1).to(DEVICE)
        m.load_state_dict(torch.load(MEMBER_DIR / f, map_location=DEVICE), strict=True)
        models[name] = m.eval()
    return models


@torch.no_grad()
def reference_features(model, XG, mu, sd, bs=4096) -> tuple[np.ndarray, np.ndarray]:
    """core.reference_embedding, returning the hidden features too."""
    Z, H = [], []
    for i in range(0, XG.shape[0], bs):
        x = XG[i:i + bs].float()
        m = torch.ones_like(x)
        z, h = model.encoder(core.standardize_reference(x, m, "batch_gene", mu, sd), m, return_hidden=True)
        Z.append(z.cpu())
        H.append(h.cpu())
    return torch.cat(Z).numpy(), torch.cat(H).numpy()


def unit(x: torch.Tensor) -> torch.Tensor:
    return x / (x.norm(dim=1, keepdim=True) + 1e-8)


def maha_params(H: np.ndarray, y: np.ndarray, ridge: float = 1e-3) -> dict:
    """Relative Mahalanobis (Ren et al. 2021): class means with a shared
    covariance, and one background Gaussian over all cells."""
    Ht = torch.from_numpy(H.astype(np.float32)).to(DEVICE)
    present = np.unique(y)
    mus = torch.stack([Ht[torch.from_numpy(y == c).to(DEVICE)].mean(0) for c in present])
    yy = torch.from_numpy(np.searchsorted(present, y)).to(DEVICE)
    within = Ht - mus[yy]
    eye = torch.eye(H.shape[1], device=DEVICE)
    cov = within.T @ within / len(H) + ridge * eye
    mu0 = Ht.mean(0)
    cov0 = (Ht - mu0).T @ (Ht - mu0) / len(H) + ridge * eye
    return {"classes": present, "mus": mus, "prec": torch.linalg.inv(cov), "mu0": mu0, "prec0": torch.linalg.inv(cov0)}


def relmaha(h: torch.Tensor, p: dict, exclude: int | None = None) -> np.ndarray:
    keep = torch.from_numpy(p["classes"] != exclude if exclude is not None else np.ones(len(p["classes"]), bool)).to(DEVICE)
    mus = p["mus"][keep]
    hp = h @ p["prec"]
    md = (hp * h).sum(1, keepdim=True) - 2 * hp @ mus.T + ((mus @ p["prec"]) * mus).sum(1)[None, :]
    d0 = h - p["mu0"]
    md0 = ((d0 @ p["prec0"]) * d0).sum(1)
    return (-(md.min(1).values - md0)).float().cpu().numpy()


@torch.no_grad()
def kth_cos(q: torch.Tensor, index: torch.Tensor, ks, index_y: torch.Tensor | None = None,
            exclude: int | None = None, chunk: int = 2048) -> dict:
    """The k-th largest cosine between each (unit) query row and the (unit) index, per k."""
    kmax, out = max(ks), {k: [] for k in ks}
    for i in range(0, len(q), chunk):
        s = q[i:i + chunk].half() @ index.T
        if exclude is not None:
            s[:, index_y == exclude] = -2.0
        top = s.topk(kmax, dim=1).values.float()
        for k in ks:
            out[k].append(top[:, k - 1].cpu())
    return {k: torch.cat(v).numpy() for k, v in out.items()}


# ---- encoding an upload ----------------------------------------------------------
@torch.no_grad()
def encode_upload(models, xs, M) -> dict:
    """Per member: z (n, 128) and h (n, 512), kept as float16 on the CPU."""
    out = {}
    for name, model in models.items():
        z, h = core.encode_inputs(model, xs, M, DEVICE, hidden=True)
        out[name] = (z.astype(np.float16), h.astype(np.float16))
    return out


def upload_record(spec, X_raw, models, transform=None, cell_idx=None) -> dict:
    s = dict(spec)
    if cell_idx is not None:
        s["cell_idx"] = cell_idx
    raw, gs_ = core.raw_upload(s, X_raw, PROF, G, sg)
    if transform is not None:
        raw = transform(raw)
    xs, M = core.query_inputs(raw, gs_, "gene", convention="service", graph_input="zscored", smooth=True)
    y = y_all[np.asarray(s["cell_idx"])]
    return {"id": s["id"], "scenario": s["scenario"], "profile": s["profile"], "y": y,
            "nobs": M.sum(1).astype(np.int32), "feat": encode_upload(models, xs, M)}


def scramble(seed):
    def f(raw):
        rng = np.random.default_rng(seed)
        out = raw.copy()
        for i in range(len(out)):
            o = np.flatnonzero(~np.isnan(out[i]))
            out[i, o] = rng.permutation(out[i, o])
        return out
    return f


# ---- scoring -----------------------------------------------------------------------
class Scorer:
    """Every candidate score for a set of encoded cells, against fixed references."""

    def __init__(self, ref: dict):
        self.ref = ref  # per member: z_tr, cen, h_tr, y_tr, maha_ref; optional h_cal, y_cal, maha_cal

    def scores(self, feat: dict, exclude: int | None = None) -> tuple[dict, np.ndarray]:
        per = {k: [] for k in COMPLEXITY}
        P = []
        for (name, (z, h)), T in zip(feat.items(), TEMPS):
            r = self.ref[name]
            zt = torch.from_numpy(z).to(DEVICE)
            ht = torch.from_numpy(h.astype(np.float32)).to(DEVICE)
            per["maxcos"].append(kth_cos(unit(zt.float()), r["z_tr"], (1,), r["y_tr_t"], exclude)[1])
            cos = (zt.float() @ r["cen"].T).cpu().numpy().astype(np.float64)
            if exclude is not None:
                cos[:, exclude] = -np.inf
            per["energy"].append(T * np.log(np.exp(cos / T).sum(1)))
            P.append(n2.softmax(cos, T))
            hu = unit(ht)
            for variant in ("ref", "cal"):
                kk = kth_cos(hu, r[f"h_{variant}"], K_GRID, r[f"y_{variant}_t"], exclude)
                for k in K_GRID:
                    per[f"knn{k}_{variant}"].append(kk[k])
                per[f"relmaha_{variant}"].append(relmaha(ht, r[f"maha_{variant}"], exclude))
        P = np.mean(P, 0)
        per["msp"] = [P.max(1)]
        return {k: np.mean(v, 0).astype(np.float32) for k, v in per.items()}, P


def band_of(nobs: np.ndarray) -> np.ndarray:
    return np.digitize(nobs, BANDS[1:-1])  # 0: 200-499, 1: 500-999, 2: 1000-1999, 3: 2000+


def fit_thresholds(scores: np.ndarray, nobs: np.ndarray) -> dict:
    ok = nobs >= BANDS[0]
    s, b = scores[ok], band_of(nobs[ok])
    pooled = float(np.quantile(s, TARGET))
    return {"pooled": pooled, "bands": [float(np.quantile(s[b == i], TARGET)) if (b == i).sum() >= MIN_BAND_CELLS
                                        else pooled for i in range(len(BANDS) - 1)]}


def rejects(scores: np.ndarray, nobs: np.ndarray, thr: dict) -> np.ndarray:
    return scores < np.asarray(thr["bands"])[band_of(nobs)]


def auc_in_vs_out(s_in: np.ndarray, s_out: np.ndarray) -> float:
    return float(roc_auc_score(np.r_[np.ones(len(s_in)), np.zeros(len(s_out))], np.r_[s_in, s_out]))


# ---- main ------------------------------------------------------------------------
def main() -> None:
    global CAL_FIT, CAL_SEL, EVAL, OUT, TABLES
    if "--smoke" in sys.argv:  # plumbing only: a few calibration uploads, nothing from EVAL, nothing in the record
        CAL_FIT, CAL_SEL, EVAL = CAL_FIT[:28:3], CAL_SEL[:28:3], CAL_SEL[1:42:3]
        OUT = TABLES = T1 / "NB3b_smoke"
    OUT.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    summary = {"rules": {"target": TARGET, "select_max_false": SELECT_MAX_FALSE, "bands": list(BANDS[:-1]),
                         "k_grid": list(K_GRID), "go": GO}, "device": str(DEVICE)}
    log(f"device {DEVICE}; CAL FIT {len(CAL_FIT)}, CAL SEL {len(CAL_SEL)}, EVAL {len(EVAL)} uploads")

    X_raw = load_rna()
    stats = np.load(NB1 / "rna_global_stats.npz")
    assert np.allclose(stats["mu"], X_raw.mean(0), atol=1e-5) and np.allclose(stats["sd"], X_raw.std(0), atol=1e-5)
    MU = torch.from_numpy(X_raw.mean(0)).to(DEVICE)
    SD = torch.from_numpy(X_raw.std(0)).to(DEVICE)
    XG = torch.from_numpy(X_raw).to(DEVICE, dtype=torch.float16)
    log(f"RNA {X_raw.shape}; global stats match NB1's")

    models = load_members()
    ref, gate = {}, {}
    for name, f in zip(MEMBERS, MEMBER_FILES):
        Z, H = reference_features(models[name], XG, MU, SD)
        served = np.load(MEMBER_DIR / f"V2_seed{name[-1]}_reference_latent_f16.npy").astype(np.float32)
        gate[f"{name}_reference_median_cos"] = float(np.median((Z * served).sum(1)))
        Ztr, Htr = torch.from_numpy(Z[TR]).to(DEVICE), torch.from_numpy(H[TR]).to(DEVICE)
        ref[name] = {"z_tr": unit(Ztr.float()).half(), "y_tr_t": torch.from_numpy(y_all[TR]).to(DEVICE),
                     "cen": torch.from_numpy(core.centroids_from(Z[TR], y_all[TR], C)).to(DEVICE),
                     "h_ref": unit(Htr.float()).half(), "y_ref_t": torch.from_numpy(y_all[TR]).to(DEVICE),
                     "maha_ref": maha_params(H[TR], y_all[TR]),
                     "z_all": unit(torch.from_numpy(Z).to(DEVICE).float()).half(),
                     "cen_all": torch.from_numpy(core.centroids_from(Z, y_all, C)).to(DEVICE),
                     "h_all": unit(torch.from_numpy(H).to(DEVICE).float()).half(),
                     "y_all_t": torch.from_numpy(y_all).to(DEVICE), "maha_all": maha_params(H, y_all)}
    del XG
    torch.cuda.empty_cache()
    gate["reference_reproduced"] = all(v > 0.9999 for k, v in gate.items() if k.endswith("median_cos"))
    log(f"reference features for {len(models)} members; reproduced: {gate['reference_reproduced']}")
    if not gate["reference_reproduced"]:
        (TABLES / "summary.json").write_text(json.dumps({"gate": gate}, indent=2) + "\n")
        sys.exit("GATE FAILED: the members do not reproduce the served reference latents")

    # Section 1: encode the calibration suite (one preprocessing per upload, shared by members)
    def encode_suite(specs, label, **kw):
        t, recs = time.time(), [upload_record(s, X_raw, models, **kw) for s in specs]
        log(f"encoded {label}: {len(recs)} uploads, {sum(len(r['y']) for r in recs):,} cells in {(time.time()-t)/60:.1f} min")
        return recs

    sub_rng = np.random.default_rng(2026)
    fit_index = encode_suite([tr_substitute(s, sub_rng) for s in CAL_FIT], "masked index (CAL FIT uploads, training cells)")
    fit_thr = encode_suite(CAL_FIT, "CAL FIT")
    sel = encode_suite(CAL_SEL, "CAL SELECT")

    # the masked index: training cells as uploads see them
    for name in MEMBERS:
        Hc = np.concatenate([r["feat"][name][1] for r in fit_index]).astype(np.float32)
        yc = np.concatenate([r["y"] for r in fit_index])
        ref[name].update({"h_cal": unit(torch.from_numpy(Hc).to(DEVICE)).half(), "y_cal_t": torch.from_numpy(yc).to(DEVICE),
                          "maha_cal": maha_params(Hc, yc)})
    scorer = Scorer(ref)

    def score_recs(recs, exclude=None):
        for r in recs:
            r["s"], r["P"] = scorer.scores(r["feat"], exclude)
        return recs

    score_recs(fit_index)
    score_recs(fit_thr)
    score_recs(sel)

    # Gate, part 2: NB2's threshold (1st percentile of the members' mean max cosine, all calibration cells)
    mc_all = np.concatenate([r["s"]["maxcos"] for r in fit_thr + sel])
    del fit_index
    gate["ood_threshold"] = float(np.quantile(mc_all, 0.01))
    log(f"gate: NB2 threshold reproduced as {gate['ood_threshold']:.5f} (NB2 {OOD_THR_NB2:.5f})")

    # Section 3: thresholds per band, fitted on CAL FIT (validation cells; the masked index holds training cells)
    nobs_thr = np.concatenate([r["nobs"] for r in fit_thr])
    THR = {k: fit_thresholds(np.concatenate([r["s"][k] for r in fit_thr]), nobs_thr) for k in COMPLEXITY}

    # Section 4: controls on CAL SELECT, then the choice
    def controls(recs, specs, label):
        """Scores for scrambled cells, uploads of one repeated cell, and held-out classes."""
        scr = [upload_record(s, X_raw, models, transform=scramble(s["seed"] + 101)) for s in specs]
        rep = [upload_record(s, X_raw, models, cell_idx=[s["cell_idx"][0]] * min(REPEAT_CELLS, len(s["cell_idx"])))
               for s in specs]
        score_recs(scr)
        score_recs(rep)
        ys = np.concatenate([r["y"] for r in recs])
        tr_counts = np.bincount(y_all[TR], minlength=C)
        held = [c for c in range(C) if (ys == c).sum() >= HELD_OUT_MIN_SEL_CELLS and tr_counts[c] >= HELD_OUT_MIN_TR_CELLS]
        held_scores = {}
        for c in held:
            feats_in = [{n: (r["feat"][n][0][r["y"] == c], r["feat"][n][1][r["y"] == c]) for n in MEMBERS}
                        for r in recs if (r["y"] == c).any()]
            feats_other = [{n: (r["feat"][n][0][r["y"] != c], r["feat"][n][1][r["y"] != c]) for n in MEMBERS}
                           for r in recs if (r["y"] != c).any()]
            s_out = [scorer.scores(f, exclude=c)[0] for f in feats_in]
            s_keep = [scorer.scores(f, exclude=c)[0] for f in feats_other]
            held_scores[classes[c]] = ({k: np.concatenate([s[k] for s in s_keep]) for k in COMPLEXITY},
                                       {k: np.concatenate([s[k] for s in s_out]) for k in COMPLEXITY})
        log(f"controls on {label}: {len(scr)} scrambled and {len(rep)} repeated uploads, {len(held)} classes held out")
        return scr, rep, held_scores

    def control_table(recs, scr, rep, held_scores, thr):
        rows = []
        for k in COMPLEXITY:
            s_in = np.concatenate([r["s"][k] for r in recs])
            nobs_in = np.concatenate([r["nobs"] for r in recs])
            ok = nobs_in >= BANDS[0]
            # pooled over cells, the rate a conformal threshold controls; the mean over uploads is reported beside it
            rj = rejects(s_in[ok], nobs_in[ok], thr[k])
            per_upload = np.mean([rejects(r["s"][k][r["nobs"] >= BANDS[0]], r["nobs"][r["nobs"] >= BANDS[0]], thr[k]).mean()
                                  for r in recs if (r["nobs"] >= BANDS[0]).any()])
            row = {"score": k, "false_abstention": float(rj.mean()), "false_abstention_upload_mean": float(per_upload)}
            for name, cr in (("scrambled", scr), ("repeated", rep)):
                s_c = np.concatenate([r["s"][k] for r in cr])
                n_c = np.concatenate([r["nobs"] for r in cr])
                row[f"auc_{name}"] = auc_in_vs_out(s_in[ok], s_c[n_c >= BANDS[0]])
                row[f"rejected_{name}"] = float(rejects(s_c[n_c >= BANDS[0]], n_c[n_c >= BANDS[0]], thr[k]).mean())
            row["auc_held_out"] = float(np.mean([auc_in_vs_out(keep[k], out[k]) for keep, out in held_scores.values()]))
            row["auc_mean"] = (row["auc_scrambled"] + row["auc_repeated"] + row["auc_held_out"]) / 3
            rows.append(row)
        return pd.DataFrame(rows)

    sel_scr, sel_rep, sel_held = controls(sel, CAL_SEL, "CAL SELECT")
    CAND = control_table(sel, sel_scr, sel_rep, sel_held, THR)
    CAND.to_csv(TABLES / "candidates_calsel.csv", index=False, float_format="%.5f")
    eligible = CAND[CAND.false_abstention <= SELECT_MAX_FALSE].copy()
    if eligible.empty:
        eligible = CAND.copy()
        summary["note"] = "no score met the false-abstention bound on CAL SELECT; chose among all"
    best = eligible.auc_mean.max()
    eligible["rank"] = eligible.score.map(COMPLEXITY.index)
    CHOSEN = eligible[eligible.auc_mean >= best - TIE].sort_values("rank").iloc[0]["score"]
    log(f"chosen on CAL SELECT: {CHOSEN}")
    print(CAND.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    # final thresholds: the whole calibration suite, as NB2 refitted
    nobs_final = np.concatenate([r["nobs"] for r in fit_thr + sel])
    THR_FINAL = {k: fit_thresholds(np.concatenate([r["s"][k] for r in fit_thr + sel]), nobs_final) for k in COMPLEXITY}
    del fit_thr, sel, sel_scr, sel_rep, sel_held

    # Section 5: the evaluation suite, once
    ev = encode_suite(EVAL, "EVAL")
    score_recs(ev)
    ev_scr, ev_rep, ev_held = controls(ev, EVAL, "EVAL")
    EVC = control_table(ev, ev_scr, ev_rep, ev_held, THR_FINAL)
    EVC.to_csv(TABLES / "eval_candidates.csv", index=False, float_format="%.5f")

    # Gate, part 3: NB2's own rule on EVAL (fixed 0.779, max cosine) and its scrambled control on EVAL[:40]
    # NB2 counts an OOD abstention over all cells; cells under the gene floor abstain for coverage first
    nb2_false = [100 * ((r["nobs"] >= 200) & (r["s"]["maxcos"] < OOD_THR_NB2)).mean() for r in ev]
    gate["eval_false_pct"] = float(np.mean(nb2_false))
    rng = np.random.default_rng(0)
    pos, neg = [], []
    for s in EVAL[:40]:
        raw, gs_ = core.raw_upload(s, X_raw, PROF, G, sg)
        shuf = raw.copy()
        for i in range(len(shuf)):
            o = np.flatnonzero(~np.isnan(shuf[i]))
            shuf[i, o] = rng.permutation(shuf[i, o])
        for arr, sink in ((raw, pos), (shuf, neg)):
            xs, M = core.query_inputs(arr, gs_, "gene", convention="service", graph_input="zscored", smooth=True)
            sink.append(scorer.scores(encode_upload(models, xs, M))[0]["maxcos"])
    pos, neg = np.concatenate(pos), np.concatenate(neg)
    gate["real_rejected_pct"] = 100 * float((pos < OOD_THR_NB2).mean())
    gate["shuffled_rejected_pct"] = 100 * float((neg < OOD_THR_NB2).mean())
    gate["nb2_reproduced"] = {k: abs(gate[k] - want) <= tol for k, (want, tol) in NB2_GATE.items()}
    log(f"gate vs NB2: {json.dumps({k: round(gate[k], 4) for k in NB2_GATE})} -> {gate['nb2_reproduced']}")

    # breakdowns for the chosen score (and today's, beside it)
    rows = []
    for r in ev:
        ok = r["nobs"] >= BANDS[0]
        if not ok.any():
            continue
        base = {"id": r["id"], "scenario": r["scenario"], "profile": r["profile"], "cells": int(ok.sum())}
        for k in (CHOSEN, "maxcos"):
            rj = rejects(r["s"][k][ok], r["nobs"][ok], THR_FINAL[k])
            rows.append({"score": k, **base, "rejected": int(rj.sum()), "false_abstention": float(rj.mean())})
        rj = r["s"]["maxcos"][ok] < OOD_THR_NB2
        rows.append({"score": "maxcos (NB2 rule, 0.779)", **base, "rejected": int(rj.sum()), "false_abstention": float(rj.mean())})
    BYUP = pd.DataFrame(rows)
    BYUP.to_csv(TABLES / "eval_false_abstention_by_upload.csv", index=False, float_format="%.5f")
    y_ev = np.concatenate([r["y"][r["nobs"] >= BANDS[0]] for r in ev])
    rj_ev = np.concatenate([rejects(r["s"][CHOSEN][r["nobs"] >= BANDS[0]], r["nobs"][r["nobs"] >= BANDS[0]], THR_FINAL[CHOSEN])
                            for r in ev])
    PERCLASS = pd.DataFrame({"class": classes, "n": np.bincount(y_ev, minlength=C),
                             "false_abstention": [rj_ev[y_ev == c].mean() if (y_ev == c).any() else np.nan for c in range(C)]})
    PERCLASS.to_csv(TABLES / "eval_false_abstention_per_class.csv", index=False, float_format="%.5f")

    chosen_ev = EVC.set_index("score").loc[CHOSEN]
    today_ev = EVC.set_index("score").loc["maxcos"]
    pooled_scen = BYUP[BYUP.score == CHOSEN].groupby("scenario")[["rejected", "cells"]].sum()
    by_scen = pooled_scen.rejected / pooled_scen.cells  # pooled over cells within each scenario
    go = {"false_overall": bool(chosen_ev.false_abstention <= GO["false_overall"]),
          "false_every_scenario": bool(by_scen.max() <= GO["false_scenario"]),
          "scrambled_rejected": bool(chosen_ev.rejected_scrambled >= GO["scrambled_rejected"]),
          "beats_maxcos_every_control": bool(all(chosen_ev[c] > today_ev[c] for c in ("auc_scrambled", "auc_repeated", "auc_held_out")))}
    summary.update({"gate": gate, "chosen": CHOSEN, "thresholds": THR_FINAL[CHOSEN], "go": go, "GO": all(go.values()),
                    "eval_chosen": chosen_ev.to_dict(), "eval_today": today_ev.to_dict(),
                    "eval_false_by_scenario": by_scen.to_dict()})
    log(f"GO/NO-GO: {go} -> {'GO' if summary['GO'] else 'NO GO'}")

    # Section 5b: real data, reported only (never used to choose)
    from benchmark import baselines_v31, datasets
    from service.pipeline import alignment, pipeline as svc, reference as svc_reference
    feature_genes = svc_reference.load_feature_space_genes()  # the service's own list, in model-input order
    real = {"Furtwängler 2025 CD34+ HSPCs (out of reference)": datasets.load_furtwangler2025_upload(),
            "Fulcher 2026 PBMCs": datasets.load_fulcher2026_upload(),
            "PBMC240 raw": alignment.parse_matrix_csv(baselines_v31.PBMC240.read_text()),
            "SCoPE2 (macrophage/monocyte)": baselines_v31.scope2_raw()}
    ref_all = {n: {**ref[n], "z_tr": ref[n]["z_all"], "y_tr_t": ref[n]["y_all_t"], "cen": ref[n]["cen_all"],
                   "h_ref": ref[n]["h_all"], "y_ref_t": ref[n]["y_all_t"], "maha_ref": ref[n]["maha_all"]} for n in MEMBERS}
    real_scorer = Scorer(ref_all)  # every reference cell, as served; the masked index is unchanged
    real_rows, furt_cells = [], None
    for label, raw in real.items():
        smoothed, aligned, _ = svc._prepare_query(feature_genes, raw)
        feat = encode_upload(models, [smoothed.astype(np.float32)], aligned.mask.astype(np.float32))
        s, _ = real_scorer.scores(feat)
        nobs = aligned.per_cell_observed_genes
        ok = nobs >= BANDS[0]
        for k in (CHOSEN, "maxcos"):
            real_rows.append({"dataset": label, "score": k, "cells": int(ok.sum()),
                              "rejected": float(rejects(s[k][ok], nobs[ok], THR_FINAL[k]).mean())})
        real_rows.append({"dataset": label, "score": "maxcos (NB2 rule, 0.779)", "cells": int(ok.sum()),
                          "rejected": float((s["maxcos"][ok] < OOD_THR_NB2).mean())})
        if label.startswith("Furtwängler"):
            furt_cells = pd.DataFrame({"cell_id": raw.cell_ids, "rejected_chosen": rejects(s[CHOSEN], nobs, THR_FINAL[CHOSEN]),
                                       "rejected_nb2": s["maxcos"] < OOD_THR_NB2})
    REAL = pd.DataFrame(real_rows)
    REAL.to_csv(TABLES / "real_data_rejection.csv", index=False, float_format="%.5f")
    lab = datasets.load_furtwangler2025_labels()
    FURT = furt_cells.merge(lab, on="cell_id").groupby("cluster")[["rejected_chosen", "rejected_nb2"]].mean()
    FURT.to_csv(TABLES / "furtwangler_rejection_by_cluster.csv", float_format="%.5f")
    summary["real_data"] = REAL.to_dict(orient="records")
    log("real data scored (reported only)")
    print(REAL.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    # Section 6: the service flags and restricted mode on RNA (EVAL), with today's OOD rule
    flag_rows = []
    for r in ev:
        S0 = n2.prediction_sets(r["P"], QHAT, np.ones(C, bool))
        S1 = S0.copy()
        nonempty = S1.any(1)
        S1[nonempty, r["P"][nonempty].argmax(1)] = True
        for label, S in (("NB2 rule", S0), ("set_includes_best_guess", S1)):
            for ood_label, ood in (("OOD today", r["s"]["maxcos"] < OOD_THR_NB2),
                                   (f"OOD {CHOSEN}", rejects(r["s"][CHOSEN], r["nobs"], THR_FINAL[CHOSEN]))):
                kind, val = n2.resolve(S, GRP, LIN, ood, r["nobs"] < BANDS[0])
                flag_rows.append({"rule": label, "ood": ood_label, "id": r["id"], "scenario": r["scenario"],
                                  "coverage": 100 * S[np.arange(len(r["y"])), r["y"]].mean(),
                                  **n2.output_metrics(kind, val, r["y"], GRP, LIN)})
    FLAGS = pd.DataFrame(flag_rows)
    FLAGS.to_csv(TABLES / "eval_flags_by_upload.csv", index=False, float_format="%.5f")
    keep_cols = ["coverage", "fine_rate", "group_rate", "lineage_rate", "abstain_rate", "abstain_ood",
                 "abstain_ambiguous", "abstain_empty", "correct_when_committed"]
    FLAGSUM = FLAGS.groupby(["rule", "ood"])[[c for c in keep_cols if c in FLAGS]].mean()
    FLAGSUM.to_csv(TABLES / "eval_flags_summary.csv", float_format="%.4f")
    print(FLAGSUM.to_string(float_format=lambda v: f"{v:7.2f}"))

    mac, mon = cls2idx["macrophage"], cls2idx["monocyte"]
    keep = np.zeros(C, bool)
    keep[[mac, mon]] = True
    rest_rows = []
    for r in ev:
        if r["scenario"] != "scope2_like":
            continue
        P = r["P"]
        Pr = P * keep
        Pr = Pr / Pr.sum(1, keepdims=True)
        for label, Q, add_guess in (("restricted, NB2 rule", P, False), ("restricted, renormalised", Pr, False),
                                    ("restricted, as served (renormalised + best guess)", Pr, True)):
            S = n2.prediction_sets(Q, QHAT, keep)
            if add_guess:
                nonempty = S.any(1)
                S[nonempty, np.where(Q[nonempty, mac] >= Q[nonempty, mon], mac, mon)] = True
            kind, val = n2.resolve(S, GRP, LIN, r["s"]["maxcos"] < OOD_THR_NB2, r["nobs"] < BANDS[0])
            guess = np.where(Q[:, mac] >= Q[:, mon], mac, mon)
            rest_rows.append({"rule": label, "id": r["id"], **n2.output_metrics(kind, val, r["y"], GRP, LIN),
                              "best_guess_bal_acc": 100 * balanced_accuracy_score(r["y"], guess)})
    REST = pd.DataFrame(rest_rows)
    REST.groupby("rule").mean(numeric_only=True).to_csv(TABLES / "eval_restricted_summary.csv", float_format="%.4f")
    summary["flags"] = FLAGSUM.reset_index().to_dict(orient="records")
    summary["minutes"] = round((time.time() - T0) / 60, 1)
    (TABLES / "summary.json").write_text(json.dumps(summary, indent=2, default=float) + "\n")

    # the chosen score's thresholds and, for an indexed score, what the service would need
    (OUT / "ood_config.json").write_text(json.dumps({"score": CHOSEN, "thresholds": THR_FINAL[CHOSEN],
                                                     "bands": list(BANDS[:-1]), "target": TARGET}, indent=2) + "\n")
    log(f"done: {'GO' if summary['GO'] else 'NO GO'}, chosen {CHOSEN}")


if __name__ == "__main__":
    main()
