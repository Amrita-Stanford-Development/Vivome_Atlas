"""Track D's paired bootstrap on SCoPE2: each of the ten "ours" model-seeds
(T1 NB1d: v3_seed0-4, V2_seed0-4) against each of the three scANVI seeds, in
three regimes (unrestricted, restricted with post-hoc masking, restricted
pool-first), all under the shared kNN rule. Writes
research/notebook-outputs/nb1d/paired_bootstrap_ours_vs_scanvi.csv.

ci_excludes_zero is True when the 95% interval lies entirely above OR
entirely below zero; verdict says which.

Reads cached embeddings only: NB1d's per-seed latents
(data/incoming/NB1d/embeddings/, gitignored) and scanvi_run.py's
results/{rna,prot}_scanvi_seed{0,1,2}.npy. Deterministic (evaluate.py's
fixed bootstrap seed), so a rerun reproduces the table byte for byte. It
rebuilt the table Track D first committed without a script: every
estimate and interval end within 1e-13, every verdict the same, and the
ci_excludes_zero flag corrected in the 57 rows whose interval lies below zero.

    python benchmark/scope2_5seed_paired.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import knn_classifier_predict, paired_bootstrap_diff, pool_first_knn_predict  # noqa: E402

D = Path(__file__).resolve().parent / "results"
REPO = Path(__file__).resolve().parents[1]
NB1D = REPO / "data" / "incoming" / "NB1d" / "embeddings"
OUT = REPO / "research" / "notebook-outputs" / "nb1d" / "paired_bootstrap_ours_vs_scanvi.csv"
MODELS = [f"V2_seed{s}" for s in range(5)] + [f"v3_seed{s}" for s in range(5)]
SCANVI_SEEDS = (0, 1, 2)
REGIMES = ("unrestricted", "restricted_shared_knn", "restricted_pool_first")


def predictions(rna_emb, rna_labels, prot_emb) -> dict:
    knn = knn_classifier_predict(rna_emb, rna_labels, prot_emb)
    return {"unrestricted": knn["unrestricted"], "restricted_shared_knn": knn["restricted"],
            "restricted_pool_first": pool_first_knn_predict(rna_emb, rna_labels, prot_emb)}


def verdict(lo: float, hi: float) -> str:
    return "ours_sig_better" if lo > 0 else "scanvi_sig_better" if hi < 0 else "not_significant"


def main() -> None:
    truth = pd.read_csv(D / "prot_meta.csv")["class_name"].to_numpy()
    if not (truth == pd.read_csv(NB1D / "scope2_cell_ids.csv")["cell_type"].to_numpy()).all():
        raise ValueError("NB1d's SCoPE2 order differs from the benchmark's; the pairing would be invalid")
    rna_labels = pd.read_csv(REPO / "service" / "model" / "runtime" / "reference_metadata.csv")["class_name"].to_numpy()
    bench_labels = pd.read_csv(D / "rna_meta.csv")["class_name"].to_numpy()
    scanvi = {s: predictions(np.load(D / f"rna_scanvi_seed{s}.npy"), bench_labels, np.load(D / f"prot_scanvi_seed{s}.npy"))
              for s in SCANVI_SEEDS}

    rows = []
    for model in MODELS:
        ours = predictions(np.load(NB1D / model / "reference_latent_f16.npy").astype(np.float32), rna_labels,
                           np.load(NB1D / model / "scope2_latent.npy").astype(np.float32))
        for regime in REGIMES:
            for s in SCANVI_SEEDS:
                result = paired_bootstrap_diff(truth, ours[regime], scanvi[s][regime])
                lo, hi = result["ci_95_pct"]
                rows.append({"ours_model": model, "family": model.split("_")[0], "regime": regime, "scanvi_seed": s,
                             "diff_point_pct": result["point_estimate_pct"], "ci_lo": lo, "ci_hi": hi,
                             "ci_excludes_zero": lo > 0 or hi < 0, "verdict": verdict(lo, hi)})
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"Wrote {len(rows)} rows to {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
