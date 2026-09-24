"""Shared evaluation protocol for every arm of the fair baseline comparison.

One rule for all arms (the user's rule 3): fit a classifier on RNA cells
inside that method's own embedding, using RNA cell-type labels, then predict
on protein cells whose labels the classifier has never seen. Protein labels
are used only here, to score -- never as a feature, never at fit time.

Classifier: k-NN (k=30, cosine distance) on the method's own embedding.
Deliberately simple and identical across every method so that differences
in the reported number reflect embedding quality, not classifier tuning.

Restricted vs unrestricted is applied at prediction time, not by refitting:
the classifier always sees and is fit on all 22 RNA classes; "restricted"
only masks the predicted probability vector down to {macrophage, monocyte}
before taking the argmax.

Every function here returns per-cell predictions, not just a scalar score --
scoring and bootstrap confidence intervals are computed from those
predictions in a second pass, so nothing needs to be retrained or
re-embedded to add a CI later.

Also here: `pool_first_knn_predict`, a second, real-product-shaped
restricted kNN variant that mirrors `service/pipeline/assignment.py`'s
`_assign_knn` exactly (candidate pool restricted before the neighbour
search, not after) -- reported alongside `knn_classifier_predict`'s
post-hoc masking, never as a replacement for it, per methodology.md's rule
that a shared, product-agnostic rule and each method's own native protocol
are both always shown. And `paired_bootstrap_diff`, for comparing two
methods' balanced accuracy on the *same* query set with the same resampled
indices applied to both -- more powerful than eyeballing whether two
independent confidence intervals overlap.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from service.pipeline.topk import chunked_topk

SUPPORTED = ("macrophage", "monocyte")
KNN_K = 30
N_BOOT = 2000
BOOT_SEED = 0


def _restrict_proba(proba, classes, supported):
    supported_idx = [i for i, c in enumerate(classes) if c in supported]
    sub = proba[:, supported_idx]
    pred_idx = sub.argmax(axis=1)
    return np.array([classes[supported_idx[i]] for i in pred_idx])


def knn_classifier_predict(rna_emb, rna_labels, prot_emb, supported=SUPPORTED, k=KNN_K):
    clf = KNeighborsClassifier(n_neighbors=k, metric="cosine", weights="distance")
    clf.fit(rna_emb, rna_labels)
    classes = list(clf.classes_)
    proba = clf.predict_proba(prot_emb)
    return {
        "unrestricted": clf.predict(prot_emb),
        "restricted": _restrict_proba(proba, classes, supported),
    }


def nearest_centroid_predict(rna_emb, rna_labels, prot_emb, supported=SUPPORTED):
    classes = sorted(set(rna_labels))
    centroids = np.zeros((len(classes), rna_emb.shape[1]), dtype=np.float64)
    for i, c in enumerate(classes):
        centroids[i] = rna_emb[rna_labels == c].mean(axis=0)
    centroids_unit = centroids / np.clip(np.linalg.norm(centroids, axis=1, keepdims=True), 1e-8, None)
    prot_unit = prot_emb / np.clip(np.linalg.norm(prot_emb, axis=1, keepdims=True), 1e-8, None)

    sim_all = prot_unit @ centroids_unit.T
    pred_unrestricted = np.array(classes)[sim_all.argmax(axis=1)]

    supported_idx = [i for i, c in enumerate(classes) if c in supported]
    sim_supported = prot_unit @ centroids_unit[supported_idx].T
    pred_restricted = np.array([classes[supported_idx[i]] for i in sim_supported.argmax(axis=1)])

    return {"unrestricted": pred_unrestricted, "restricted": pred_restricted}


def pool_first_knn_predict(rna_emb, rna_labels, prot_emb, supported=SUPPORTED, k=KNN_K):
    """Restricted-only: mirrors service/pipeline/assignment.py's _assign_knn
    exactly, using the same chunked_topk helper -- the candidate POOL of
    RNA cells is restricted to `supported` classes BEFORE the k-nearest-
    neighbour search runs, not after (unlike knn_classifier_predict's
    post-hoc masking, which searches all 22 classes' cells and only
    restricts the output columns at the end). This is what the product's
    own kNN assignment method would actually deliver, not an evaluation-
    only approximation of it."""
    rna_emb = np.asarray(rna_emb, dtype=np.float32)
    prot_emb = np.asarray(prot_emb, dtype=np.float32)
    rna_unit = rna_emb / np.clip(np.linalg.norm(rna_emb, axis=1, keepdims=True), 1e-8, None)
    prot_unit = prot_emb / np.clip(np.linalg.norm(prot_emb, axis=1, keepdims=True), 1e-8, None)

    supported_arr = np.array(supported)
    label_to_position = {name: i for i, name in enumerate(supported_arr)}
    pool_mask = np.isin(rna_labels, supported)
    pool_embeddings = rna_unit[pool_mask]
    pool_labels = np.asarray(rna_labels)[pool_mask]
    pool_positions = np.array([label_to_position[name] for name in pool_labels])

    k_eff = min(k, pool_embeddings.shape[0])
    best_pos, _ = chunked_topk(prot_unit, pool_embeddings, k_eff, candidate_labels=pool_positions)

    votes = np.zeros((prot_unit.shape[0], len(supported_arr)), dtype=np.float32)
    for column in range(len(supported_arr)):
        votes[:, column] = (best_pos == column).sum(axis=1)
    pred = supported_arr[votes.argmax(axis=1)]
    return pred


def score(true_labels, pred_labels, n_candidate_classes):
    return {
        "accuracy_pct": float(accuracy_score(true_labels, pred_labels) * 100),
        "balanced_accuracy_pct": float(balanced_accuracy_score(true_labels, pred_labels) * 100),
        "n_candidate_classes": n_candidate_classes,
        "n_query_cells": int(len(true_labels)),
    }


def bootstrap_ci(true_labels, pred_labels, n_boot=N_BOOT, seed=BOOT_SEED):
    """Stratified bootstrap over query cells (stratified by true label, so
    each resample keeps the same class proportions as the real 1,490-cell
    query set), 95% percentile interval on accuracy and balanced accuracy.
    Resamples (true, pred) pairs already computed above -- no re-embedding,
    no refitting, no retraining."""
    true_labels = np.asarray(true_labels)
    pred_labels = np.asarray(pred_labels)
    rng = np.random.default_rng(seed)
    classes = np.unique(true_labels)
    idx_by_class = {c: np.where(true_labels == c)[0] for c in classes}

    accs, bals = [], []
    for _ in range(n_boot):
        boot_idx = np.concatenate([
            rng.choice(idx_by_class[c], size=len(idx_by_class[c]), replace=True)
            for c in classes
        ])
        t, p = true_labels[boot_idx], pred_labels[boot_idx]
        accs.append(accuracy_score(t, p))
        bals.append(balanced_accuracy_score(t, p))

    accs, bals = np.array(accs) * 100, np.array(bals) * 100
    return {
        "accuracy_ci": [float(np.percentile(accs, 2.5)), float(np.percentile(accs, 97.5))],
        "balanced_accuracy_ci": [float(np.percentile(bals, 2.5)), float(np.percentile(bals, 97.5))],
    }


def evaluate_arm(true_labels, pred_unrestricted, pred_restricted, n_classes_unrestricted, n_classes_restricted):
    return {
        "unrestricted": {
            **score(true_labels, pred_unrestricted, n_classes_unrestricted),
            **bootstrap_ci(true_labels, pred_unrestricted),
        },
        "restricted": {
            **score(true_labels, pred_restricted, n_classes_restricted),
            **bootstrap_ci(true_labels, pred_restricted),
        },
    }


def paired_bootstrap_diff(true_labels, pred_a, pred_b, n_boot=N_BOOT, seed=BOOT_SEED):
    """Stratified PAIRED bootstrap on balanced_accuracy(pred_a) - balanced_accuracy(pred_b):
    the same resampled cell indices are used for both predictions in every
    resample (both are scored on the same underlying query set), which is
    the statistically correct way to compare two methods evaluated on
    identical data -- more powerful than eyeballing overlap between two
    independently-computed CIs. 95% percentile interval on the difference."""
    true_labels = np.asarray(true_labels)
    pred_a = np.asarray(pred_a)
    pred_b = np.asarray(pred_b)
    rng = np.random.default_rng(seed)
    classes = np.unique(true_labels)
    idx_by_class = {c: np.where(true_labels == c)[0] for c in classes}

    point_diff = (balanced_accuracy_score(true_labels, pred_a) - balanced_accuracy_score(true_labels, pred_b)) * 100

    diffs = []
    for _ in range(n_boot):
        boot_idx = np.concatenate([
            rng.choice(idx_by_class[c], size=len(idx_by_class[c]), replace=True)
            for c in classes
        ])
        t, pa, pb = true_labels[boot_idx], pred_a[boot_idx], pred_b[boot_idx]
        diffs.append(balanced_accuracy_score(t, pa) - balanced_accuracy_score(t, pb))
    diffs = np.array(diffs) * 100
    return {
        "point_estimate_pct": float(point_diff),
        "ci_95_pct": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
    }
