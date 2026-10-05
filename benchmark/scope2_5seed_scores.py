"""SCoPE2 under T1 NB1d's ten model-seeds (v3_seed0-4, V2_seed0-4), rescored
with the corrected labels (research/benchmark/scope2_labels/corrected_labels.csv;
research/benchmark/bugs-and-fixes.md, 8). Rewrites, in
research/notebook-outputs/nb1d/:

- ours_scope2_5seed_scores.csv and ours_scope2_5seed_family_summary.csv:
  Track D's table under the shared harness's rules (benchmark/evaluate.py:
  the kNN classifier, the pool-first kNN, nearest centroid), unrestricted
  and restricted to the two supported classes.
- NB1d's own SCoPE2 figures: real_data_per_seed.csv's scope2_unres,
  scope2_restr and the two restricted recalls; real_data_family_summary.csv;
  nb1d_summary.json's real_smooth_on block; scope2_prediction_distribution.csv.
  With smoothing on they are nearest centroid on the saved latents. NB1d did
  not save its smoothing-off latents: those rows' restricted figures follow
  from the swap exactly (two classes, every label swapped: balanced accuracy
  becomes 100 minus it, each recall 100 minus the other class's), and the
  unrestricted one cannot be recomputed, so it is left empty.

Every table was first made without these labels being right. Before
writing, each is rebuilt with the previous labels and must match what is
committed (1e-9; the distribution exactly), so the rules are the ones that
made it. Columns and labels-independent fields are kept as they are, byte
for byte. Running it again changes nothing.

Reads cached embeddings only: NB1d's per-seed latents
(data/incoming/NB1d/embeddings/, gitignored).

    python benchmark/scope2_5seed_scores.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO))
from evaluate import knn_classifier_predict, nearest_centroid_predict, pool_first_knn_predict, score  # noqa: E402
from benchmark.scope2_labels import edit_csv  # noqa: E402

NB1D = REPO / "data" / "incoming" / "NB1d" / "embeddings"
OUT = REPO / "research" / "notebook-outputs" / "nb1d"
SCORES = OUT / "ours_scope2_5seed_scores.csv"
SUMMARY = OUT / "ours_scope2_5seed_family_summary.csv"
REAL = OUT / "real_data_per_seed.csv"
REAL_SUMMARY = OUT / "real_data_family_summary.csv"
NB1D_SUMMARY = OUT / "nb1d_summary.json"
DISTRIBUTION = OUT / "scope2_prediction_distribution.csv"
LABELS = REPO / "research" / "benchmark" / "scope2_labels" / "corrected_labels.csv"
METRICS = ["accuracy_pct", "balanced_accuracy_pct"]
REAL_COLUMNS = ["scope2_unres", "scope2_restr", "scope2_mac_recall_restr", "scope2_mon_recall_restr"]
TOL = 1e-9


def predictions(rna_emb, rna_labels, prot_emb) -> dict:
    knn = knn_classifier_predict(rna_emb, rna_labels, prot_emb)
    nc = nearest_centroid_predict(rna_emb, rna_labels, prot_emb)
    return {"unrestricted": knn["unrestricted"], "restricted_shared_knn": knn["restricted"],
            "restricted_pool_first": pool_first_knn_predict(rna_emb, rna_labels, prot_emb),
            "unrestricted_native_centroid": nc["unrestricted"], "restricted_native_centroid": nc["restricted"]}


def scores_table(committed: pd.DataFrame, preds: dict, truth: np.ndarray) -> pd.DataFrame:
    rows = []
    for model, family, regime, n_classes in committed[["model", "family", "regime", "n_candidate_classes"]].itertuples(index=False):
        rows.append({"model": model, "family": family, "regime": regime, **score(truth, preds[model][regime], int(n_classes))})
    return pd.DataFrame(rows, columns=committed.columns)


def summary(scores: pd.DataFrame) -> str:
    return scores.groupby(["family", "regime"])[METRICS].agg(["mean", "std", "min", "max"]).to_csv(lineterminator="\n")


def real_figures(pred: dict, truth: np.ndarray) -> dict:
    """NB1d's SCoPE2 columns, smoothing on: nearest centroid on the saved latents."""
    restricted = pred["restricted_native_centroid"]
    return {"scope2_unres": 100 * balanced_accuracy_score(truth, pred["unrestricted_native_centroid"]),
            "scope2_restr": 100 * balanced_accuracy_score(truth, restricted),
            "scope2_mac_recall_restr": 100 * float((restricted[truth == "macrophage"] == "macrophage").mean()),
            "scope2_mon_recall_restr": 100 * float((restricted[truth == "monocyte"] == "monocyte").mean())}


def swapped(row: pd.Series) -> dict:
    """Restricted figures when every label is swapped; the unrestricted one is unknown."""
    return {"scope2_unres": np.nan, "scope2_restr": 100 - row["scope2_restr"],
            "scope2_mac_recall_restr": 100 - row["scope2_mon_recall_restr"],
            "scope2_mon_recall_restr": 100 - row["scope2_mac_recall_restr"]}


def distribution(preds: dict, families: dict, truth: np.ndarray, lineage: dict) -> pd.DataFrame:
    rows = []
    for model, pred in preds.items():
        unrestricted = pred["unrestricted_native_centroid"]
        for true in sorted(set(truth)):
            shares = pd.Series(unrestricted[truth == true]).value_counts(normalize=True) * 100
            rows += [{"model": model, "family": families[model], "true": true, "rank": rank, "predicted": p,
                      "lineage": lineage[p], "share": float(s)} for rank, (p, s) in enumerate(shares.items(), 1)]
    return pd.DataFrame(rows)


def same_distribution(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """Equal shares, rank by rank; classes tied on a share may come in either order."""
    key = ["model", "true", "rank"]
    a, b = a.sort_values(key).reset_index(drop=True), b.sort_values(key).reset_index(drop=True)
    if len(a) != len(b) or not (a[["model", "true", "rank"]] == b[["model", "true", "rank"]]).all().all():
        return False
    if not np.allclose(a["share"], b["share"], rtol=0, atol=TOL):
        return False
    tie = lambda d: d.assign(share=d["share"].round(9)).groupby(["model", "true", "share"])["predicted"].apply(frozenset)  # noqa: E731
    return tie(a).equals(tie(b))


def stats_block(real: pd.DataFrame, column: str) -> dict:
    """nb1d_summary.json's {family: {mean, sd, min, max}} over the smoothing-on rows."""
    on = real[real["smooth"]]
    return {family: {"mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1)), "min": float(np.min(v)), "max": float(np.max(v))}
            for family, v in ((f, on.loc[on["family"] == f, column].to_numpy()) for f in pd.unique(on["family"]))}


def close(a, b) -> bool:
    return np.allclose(np.asarray(a, float), np.asarray(b, float), rtol=0, atol=TOL, equal_nan=True)


def main() -> None:
    labels = pd.read_csv(LABELS)
    if list(labels["orig_index"]) != list(range(len(labels))):
        raise ValueError(f"{LABELS} is not in orig_index order")
    if not (labels["label"].to_numpy() == pd.read_csv(NB1D / "scope2_cell_ids.csv")["cell_type"].to_numpy()).all():
        raise ValueError("NB1d's SCoPE2 cell ids do not carry the corrected labels; run python -m benchmark.scope2_labels --apply")
    old, new = labels["previous"].to_numpy(), labels["label"].to_numpy()
    meta = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")
    rna_labels = meta["class_name"].to_numpy()
    lineage = meta.groupby("class_name")["lineage"].first().to_dict()
    committed = pd.read_csv(SCORES, float_precision="round_trip")
    families = dict(zip(committed["model"], committed["family"]))
    preds = {}
    for model in pd.unique(committed["model"]):
        preds[model] = predictions(np.load(NB1D / model / "reference_latent_f16.npy").astype(np.float32), rna_labels,
                                   np.load(NB1D / model / "scope2_latent.npy").astype(np.float32))
        print(f"{model} predicted", flush=True)

    # Track D's table
    previous, corrected = scores_table(committed, preds, old), scores_table(committed, preds, new)
    if close(committed[METRICS], corrected[METRICS]):
        print("ours_scope2_5seed_scores.csv already has the corrected labels")
    elif close(committed[METRICS], previous[METRICS]):
        same = summary(previous) == SUMMARY.read_bytes().decode("utf-8").replace("\r\n", "\n")
        print(f"previous labels reproduce ours_scope2_5seed_scores.csv; its summary byte for byte: {same}")
    else:
        raise SystemExit("the previous labels do not reproduce ours_scope2_5seed_scores.csv")

    # NB1d's own table
    real = pd.read_csv(REAL, float_precision="round_trip")
    on = real["smooth"].to_numpy()
    fig_old = {m: real_figures(preds[m], old) for m in preds}
    fig_new = {m: real_figures(preds[m], new) for m in preds}
    now = real.loc[on, REAL_COLUMNS].to_numpy()
    as_old = np.array([[fig_old[m][c] for c in REAL_COLUMNS] for m in real.loc[on, "model"]])
    as_new = np.array([[fig_new[m][c] for c in REAL_COLUMNS] for m in real.loc[on, "model"]])
    if close(now, as_new):
        print("real_data_per_seed.csv already has the corrected labels")
        real_new = real
    elif close(now, as_old):
        print("previous labels reproduce real_data_per_seed.csv's smoothing-on SCoPE2 columns")
        real_new = real.copy()
        for i in real.index:
            values = fig_new[real.at[i, "model"]] if real.at[i, "smooth"] else swapped(real.loc[i])
            for c in REAL_COLUMNS:
                real_new.at[i, c] = values[c]
    else:
        raise SystemExit("the previous labels do not reproduce real_data_per_seed.csv")

    old_dist = distribution(preds, families, old, lineage)
    new_dist = distribution(preds, families, new, lineage)
    dist_now = pd.read_csv(DISTRIBUTION, float_precision="round_trip")
    if same_distribution(dist_now, new_dist):
        print("scope2_prediction_distribution.csv already has the corrected labels")
    elif same_distribution(dist_now, old_dist):
        print("previous labels reproduce scope2_prediction_distribution.csv")
    else:
        raise SystemExit("the previous labels do not reproduce scope2_prediction_distribution.csv")

    nb1d = json.loads(NB1D_SUMMARY.read_text(encoding="utf-8"))
    for column in ("scope2_unres", "scope2_restr"):
        for family, block in stats_block(real, column).items():
            if not close(list(block.values()), list(nb1d["real_smooth_on"][column][family].values())):
                raise SystemExit(f"nb1d_summary.json's {column} {family} is not reproduced from real_data_per_seed.csv")
    group = ["family", "smooth"]
    kept = [c for c in pd.read_csv(REAL_SUMMARY, header=[0, 1], index_col=[0, 1]).columns.get_level_values(0).unique()]
    old_summary = real.groupby(group)[kept].agg(["mean", "std", "min", "max"]).to_csv(lineterminator="\n")
    print(f"real_data_family_summary.csv reproduced byte for byte: {old_summary == REAL_SUMMARY.read_bytes().decode('utf-8').replace(chr(13) + chr(10), chr(10))}")

    # write
    corrected.to_csv(SCORES, index=False, lineterminator="\n")
    SUMMARY.write_bytes(summary(corrected).encode("utf-8"))
    by_row = {(r.model, str(r.smooth)): r for r in real_new.itertuples(index=False)}

    def edit(row: dict) -> dict:
        r = by_row[(row["model"], row["smooth"])]
        out = {}
        for c in REAL_COLUMNS:
            value = getattr(r, c)
            out[c] = "" if pd.isna(value) else row[c] if close(float(row[c] or "nan"), value) else repr(float(value))
        return out

    text, changed = edit_csv(REAL, edit)
    REAL.write_bytes(text)
    REAL_SUMMARY.write_bytes(real_new.groupby(group)[kept].agg(["mean", "std", "min", "max"]).to_csv(lineterminator="\n").encode("utf-8"))
    for column in ("scope2_unres", "scope2_restr"):
        nb1d["real_smooth_on"][column] = stats_block(real_new, column)
    NB1D_SUMMARY.write_bytes(json.dumps(nb1d, indent=2).encode("utf-8"))
    new_dist.to_csv(DISTRIBUTION, index=False, lineterminator="\n")
    print(f"real_data_per_seed.csv: {changed} rows changed")
    print(corrected.groupby(["family", "regime"])[METRICS].mean().round(2).to_string())
    print(real_new[["model", "smooth"] + REAL_COLUMNS].round(2).to_string())
    print(f"Wrote {SCORES.name}, {SUMMARY.name}, {REAL.name}, {REAL_SUMMARY.name}, {NB1D_SUMMARY.name}, {DISTRIBUTION.name}")


if __name__ == "__main__":
    main()
