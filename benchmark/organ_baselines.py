"""The baselines for an organ reference's locked test (the lymph node's and the
lung's protocols, rule 8: "the baselines, correlation and PCA with kNN,
against Tabula Sapiens <organ> with the candidate's labels, as for the
colon"), run after the intake and before the scorer. Secondary: they never
decide.

The two simple methods are the corrected benchmark's
(`benchmark/baselines_corrected.py`), on the organ's own gene space:
- **RNA side:** the candidate's reference cells over its feature genes,
  scaled per gene with every class weighted equally (class_balanced_z).
- **Query side:** the intake's upload over the same genes, on the service's
  log scale, z-scored per gene within the upload (unmeasured genes 0).
- **correlation:** Pearson over each sample's measured genes to every class
  mean of the RNA side; the predicted class is the argmax.
- **PCA + kNN:** a 50-component PCA of the RNA side (at most RNA_CELLS cells,
  sampled per class), both sides projected around the class-balanced centre;
  the K nearest RNA cells vote. Its setup checks (held-out RNA kNN, the
  queries' share of RNA neighbours) are recorded beside it.

Each is scored by its protocol's primary measure:
- lymph node: AUROC of S = score(B cell group) - score(T cell group),
  B-zone regions over T-zone regions. A group's score is its best class
  correlation, or its share of kNN votes.
- lung: balanced accuracy of the predicted lineage over the true lineages.

Writes baselines.json beside the intake's files; the scorer copies it into
summary.json.

    python -m benchmark.organ_baselines ln --rehearse     # or lung; without --rehearse after the real intake
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.neighbors import NearestNeighbors

from benchmark.baselines_corrected import class_balanced_z
from benchmark.colon_heldout_intake import REPO, organ_data
from service.pipeline import alignment, gene_ids

sys.path.insert(0, str(REPO / "scripts"))
from organ_reference import bundle as organ_bundle  # noqa: E402

RNA_CELLS = 30000
K = 30
SEED = 0
NONE = "(none)"  # a sample a baseline cannot score; wrong for the lung, left out of the lymph node's AUROC


def organ_matrix(raw: alignment.RawMatrix, candidate: Path) -> np.ndarray:
    """The upload over the candidate's feature genes (samples x genes), on the
    service's log scale, a gene's rows merged by median, NaN where unmeasured.
    The intake saves it as query_organ.npz."""
    values, _ = alignment.detect_and_transform_value_scale(raw.values)
    genes = pd.read_csv(candidate / "feature_space_genes.csv")["gene"].astype(str).str.upper().tolist()
    index = {g: i for i, g in enumerate(genes)}
    with organ_bundle.gene_map(candidate):
        symbols = [s.upper() if s else None for s in gene_ids.resolve_identifiers(raw.gene_names).resolved]
    out = np.full((len(raw.cell_ids), len(genes)), np.nan, dtype=np.float32)
    rows: dict[int, list[int]] = {}
    for r, s in enumerate(symbols):
        if s in index:
            rows.setdefault(index[s], []).append(r)
    for col, rr in rows.items():
        with np.errstate(all="ignore"):
            out[:, col] = np.nanmedian(values[rr], axis=0) if len(rr) > 1 else values[rr[0]]
    return out


def reference(work: Path, organ: str) -> tuple[np.ndarray, np.ndarray, dict]:
    lab = pd.read_csv(work / "labels.csv.gz", keep_default_na=False)
    genes = pd.read_csv(work / "feature_space_genes.csv")["gene"].tolist()
    X = organ_data.load_rna(organ_data.resolve(organ_data.load_organ(organ)["rna"]), genes)[lab["row"].to_numpy()]
    hierarchy = json.loads((work / "classes.json").read_text(encoding="utf-8"))["hierarchy"]
    return X, lab["class_name"].to_numpy(), hierarchy


def query_z(q: np.ndarray) -> np.ndarray:
    """Each gene z-scored over the upload's samples. A gene with one value in
    every sample is 0 by its spread, as the service's zscore_per_gene: float32's
    mean misses such a constant by a rounding error, and its z came out -1."""
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # an all-missing gene
        z = (q - np.nanmean(q, 0)) / np.nanstd(q, 0)
        spread = np.nanmax(q, 0) - np.nanmin(q, 0)
    return np.where(np.isfinite(z) & (spread > 0), z, 0.0).astype(np.float32)


def correlation_scores(rna_z, labels, q) -> tuple[np.ndarray, list[str]]:
    classes = sorted(set(labels))
    means = np.stack([rna_z[labels == c].mean(0) for c in classes])
    zq = query_z(q)
    out = np.full((len(q), len(classes)), np.nan)
    for i in range(len(q)):
        m = np.isfinite(q[i])
        if m.sum() < 3:
            continue
        a = zq[i, m] - zq[i, m].mean()
        B = means[:, m] - means[:, m].mean(1, keepdims=True)
        out[i] = (B @ a) / (np.linalg.norm(B, axis=1) * np.linalg.norm(a) + 1e-12)
    return out, classes


def knn_space(rna_z, labels, q) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(RNA cells, their labels, queries) in the PCA space. The components are
    fitted on RNA cells sampled per class; both sides are projected around the
    reference's class-balanced centre (0 after class_balanced_z), not the
    sample's own mean. Sampling per class leaves that mean off the centre, and
    the shift moved every query toward the small classes (amendment 3)."""
    rng = np.random.default_rng(SEED)
    classes = sorted(set(labels))
    per = max(1, RNA_CELLS // len(classes))
    keep = np.concatenate([rng.choice(np.flatnonzero(labels == c), min(per, int((labels == c).sum())), replace=False) for c in classes])
    pcs = PCA(n_components=50, random_state=SEED).fit(rna_z[keep])
    return rna_z[keep] @ pcs.components_.T, labels[keep], query_z(q) @ pcs.components_.T


def knn_votes(ref, ref_labels, qp, classes) -> tuple[np.ndarray, list[str]]:
    _, idx = NearestNeighbors(n_neighbors=K, metric="cosine").fit(ref).kneighbors(qp)
    lab = ref_labels[idx]
    return np.stack([(lab == c).mean(1) for c in classes], 1), classes


def setup_checks(ref, ref_labels, qp, classes) -> dict:
    """The kNN space's own checks (benchmark/baselines_corrected.py's): does it
    carry the classes on held-out RNA cells, and do queries sit among RNA
    cells or apart from them?"""
    rng = np.random.default_rng(SEED)
    test = rng.choice(len(ref), len(ref) // 5, replace=False)
    train = np.setdiff1d(np.arange(len(ref)), test)
    votes, _ = knn_votes(ref[train], ref_labels[train], ref[test], classes)
    held = balanced_accuracy_score(ref_labels[test], np.array(classes)[votes.argmax(1)])
    joint = np.vstack([ref, qp])
    _, idx = NearestNeighbors(n_neighbors=K + 1, metric="cosine").fit(joint).kneighbors(qp)
    return {"rna_holdout_knn_balanced_accuracy_pct": round(100 * float(held), 2),
            "rna_holdout_chance_pct": round(100 / len(classes), 2),
            "query_neighbour_share_median_pct": round(100 * float(np.median((idx[:, 1:] >= len(ref)).mean(1))), 2),
            "query_neighbour_share_if_mixed_pct": round(100 * len(qp) / len(joint), 3)}


def by_level(scores, classes, hierarchy, level, how) -> pd.DataFrame:
    keys = sorted({hierarchy[c][level] for c in classes})
    cols = {k: [i for i, c in enumerate(classes) if hierarchy[c][level] == k] for k in keys}
    agg = (lambda s, i: np.nanmax(s[:, i], 1)) if how == "max" else (lambda s, i: s[:, i].sum(1))
    return pd.DataFrame({k: agg(scores, i) for k, i in cols.items()})


def called_at(df: pd.DataFrame, scorable: np.ndarray) -> np.ndarray:
    return np.where(scorable, df.fillna(-np.inf).idxmax(1).to_numpy(), NONE)


def score_entry(organ: str, scores: np.ndarray, classes: list, hierarchy: dict, labels: pd.DataFrame, how: str) -> dict:
    """One baseline's scores (samples x classes) by the protocol's primary
    measure. A sample with no finite score (correlation needs 3 measured
    genes) is called NONE."""
    groups = by_level(scores, classes, hierarchy, "group", how)
    scorable = np.isfinite(scores).any(1)
    pred = np.where(scorable, np.array(classes)[np.nan_to_num(scores, nan=-np.inf).argmax(1)], NONE)
    entry = {"predicted_class": pd.Series(pred).value_counts().to_dict(), "unscorable_samples": int((~scorable).sum())}
    if organ == "ln":
        zone = labels["group"].to_numpy()
        bt = np.isin(zone, ["B zone", "T zone"])
        s = (groups["B cell"] - groups["T cell"]).to_numpy()
        ok = bt & np.isfinite(s)
        entry["auroc_b_over_t"] = round(float(roc_auc_score(zone[ok] == "B zone", s[ok])), 4)
        entry["argmax_group_by_zone"] = pd.crosstab(pd.Series(zone, name="zone"), pd.Series(called_at(groups, scorable), name="called")).to_dict()
    else:
        truth = labels["group"].to_numpy()
        scored = labels["scored"].astype(str).to_numpy() == "True"
        # rule 7: a lineage with fewer than 3 scored samples is left out, as the scorer does
        counts = pd.Series(truth[scored]).value_counts()
        kept = sorted(g for g, n in counts.items() if n >= 3)
        scored = scored & np.isin(truth, kept)
        entry["lineages_scored"] = kept
        called = called_at(by_level(scores, classes, hierarchy, "lineage", how), scorable)
        entry["balanced_accuracy"] = round(100 * float(balanced_accuracy_score(truth[scored], called[scored])), 2)
        entry["called_by_lineage"] = pd.crosstab(pd.Series(truth[scored], name="truth"), pd.Series(called[scored], name="called")).to_dict()
    return entry


def run(organ: str, rehearse: bool) -> dict:
    if organ == "ln":
        from benchmark import ln_heldout_intake as intake
        candidate_organ, prefix = intake.CANDIDATE, "ln"
    else:
        from benchmark import lung_heldout_intake as intake
        candidate_organ, prefix = intake.CANDIDATE, "lung"
    out = intake.out_dir(rehearse)
    work = organ_data.WORK / candidate_organ
    labels = pd.read_csv(out / "label_map.csv", keep_default_na=False)
    saved = np.load(out / "query_organ.npz", allow_pickle=True)
    if saved["cell_ids"].tolist() != labels["cell_id"].astype(str).tolist():
        raise SystemExit("the saved upload is not in label-map order")
    q = saved["x"]
    X, rna_labels, hierarchy = reference(work, candidate_organ)
    rna_z = class_balanced_z(X, rna_labels)
    result = {"method": __doc__.split("\n\n")[1].strip(), "rna_cells": int(len(X)), "query_samples": int(len(q)),
              "candidate": candidate_organ}
    classes = sorted(set(rna_labels))
    space = knn_space(rna_z, rna_labels, q)
    for name, (scores, cls), how in (("correlation", correlation_scores(rna_z, rna_labels, q), "max"),
                                     ("pca_knn", knn_votes(*space, classes), "sum")):
        result[name] = score_entry(organ, scores, cls, hierarchy, labels, how)
    result["pca_knn"]["setup_checks"] = setup_checks(*space, classes)
    (out / "baselines.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("organ", choices=("ln", "lung"))
    parser.add_argument("--rehearse", action="store_true")
    args = parser.parse_args(argv)
    r = run(args.organ, args.rehearse)
    print(json.dumps({k: v for k, v in r.items() if k in ("correlation", "pca_knn")}, indent=1, default=str))


if __name__ == "__main__":
    main()
