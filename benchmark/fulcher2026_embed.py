"""Gate, then embeddings: T1 NB1d's ten models on Fulcher 2026 through the
service's own query path (pipeline.embed_query). Fixed by
research/benchmark/protocol-fulcher2026.md, sections "Gate" and "Our query path".

Gate: PBMC240 raw (the 237 NB1d cells, NB1d's first-symbol gene convention)
through embed_query must reproduce NB1d's V2_seed0 latents at a median cosine
of at least 0.999. The service's own identifiers are also reported. If the
gate fails, nothing is embedded. The gate record, including every
checkpoint's sha256, goes to gate.json in research/benchmark/fulcher2026.

Embeddings: the 1,275-cell Fulcher upload, one embed_query call per model,
saved to results/fulcher2026/<model>_latent.npy (rows in upload order,
cell_ids.txt). This script never reads a label.

    python benchmark/fulcher2026_embed.py
"""
import dataclasses
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datasets  # noqa: E402  (also puts the repo root on sys.path)
from service.pipeline import alignment, encoder, pipeline, reference  # noqa: E402

REPO = datasets.REPO
OUT = Path(__file__).resolve().parent / "results" / "fulcher2026"
TABLES = REPO / "research" / "benchmark" / "fulcher2026"
NB1D = REPO / "data" / "incoming" / "NB1d" / "embeddings"
V3_CKPT = REPO / "data" / "incoming" / "Reference_Projection_V3_ckpt"
V2_CKPT = REPO / "data" / "incoming" / "NB1b" / "ckpt"
RUNTIME = REPO / "service" / "model" / "runtime"
GATE_MODEL, GATE_MIN_MEDIAN_COSINE = "V2_seed0", 0.999

MODELS = {"v3_seed0": RUNTIME / "reference_model.pt"}
MODELS.update({f"v3_seed{s}": V3_CKPT / f"reference_seed{s}.pt" for s in range(1, 5)})
MODELS.update({f"V2_seed{s}": V2_CKPT / f"V2_batchgene_aug_seed{s}.pt" for s in range(5)})


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def pbmc240_upload(first_symbol: bool) -> alignment.RawMatrix:
    """PBMC240 raw, restricted to NB1d's 237 cells in NB1d's order. With
    first_symbol, each DIA-NN protein group becomes its first gene symbol,
    uppercased (NB1d's convention); otherwise the service's own identifiers."""
    raw = alignment.parse_matrix_csv((REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv").read_text())
    ids = pd.read_csv(NB1D / "pbmc240_raw_cell_ids.csv")["cell_id"].tolist()
    columns = [raw.cell_ids.index(c) for c in ids]
    raw = dataclasses.replace(raw, cell_ids=ids, values=raw.values[:, columns])
    if first_symbol:
        raw = dataclasses.replace(raw, gene_names=[g.split(";")[0].upper() for g in raw.gene_names])
    return raw


def cosine_stats(z: np.ndarray, reference_z: np.ndarray) -> dict:
    cos = (z * reference_z).sum(1) / (np.linalg.norm(z, axis=1) * np.linalg.norm(reference_z, axis=1))
    return {"median": float(np.median(cos)), "p05": float(np.percentile(cos, 5)), "min": float(cos.min())}


def run_gate(genes: list[str]) -> dict:
    uploads = {"nb1d_first_symbol": pbmc240_upload(True), "service_identifiers": pbmc240_upload(False)}
    record = {"criterion": f"{GATE_MODEL} median cosine >= {GATE_MIN_MEDIAN_COSINE} (nb1d_first_symbol)", "models": {}}
    for name in (GATE_MODEL, "v3_seed0"):
        handle = encoder.load_encoder(MODELS[name])
        nb1d = np.load(NB1D / name / "pbmc240_raw_latent.npy")
        record["models"][name] = {
            identifiers: cosine_stats(pipeline.embed_query(handle, genes, upload)[0], nb1d)
            for identifiers, upload in uploads.items()
        }
    # Protocol amendment 1: the check is a row cosine, not a max absolute difference.
    served, nb1d_c = np.load(RUNTIME / "reference_centroids.npy"), np.load(NB1D / "v3_seed0" / "centroids.npy")
    record["v3_seed0_centroids_vs_runtime"] = {
        "min_row_cosine": float(((served * nb1d_c).sum(1) / (np.linalg.norm(served, axis=1) * np.linalg.norm(nb1d_c, axis=1))).min()),
        "max_abs_diff": float(np.abs(nb1d_c - served).max()),
    }
    record["passed"] = record["models"][GATE_MODEL]["nb1d_first_symbol"]["median"] >= GATE_MIN_MEDIAN_COSINE
    return record


def main() -> None:
    missing = [str(p) for p in MODELS.values() if not p.exists()]
    if missing:
        sys.exit("missing checkpoints (see the protocol's Models section):\n  " + "\n  ".join(missing))
    genes = reference.load_feature_space_genes()
    TABLES.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    gate = run_gate(genes)
    gate["checkpoints"] = {name: {"file": path.name, "sha256": sha256(path)} for name, path in MODELS.items()}
    # The served file and NB1d's reference_seed0.pt differ as files; record whether their weights do.
    import torch
    served_sd, seed0_sd = (torch.load(p, map_location="cpu", weights_only=False)
                           for p in (MODELS["v3_seed0"], V3_CKPT / "reference_seed0.pt"))
    gate["served_equals_reference_seed0_weights"] = list(served_sd) == list(seed0_sd) and all(
        torch.equal(served_sd[k], seed0_sd[k]) for k in served_sd)
    (TABLES / "gate.json").write_text(json.dumps(gate, indent=2) + "\n")
    print(json.dumps(gate["models"], indent=2))
    if not gate["passed"]:
        sys.exit(f"GATE FAILED: {GATE_MODEL} does not reproduce NB1d. Nothing embedded.")
    if gate["v3_seed0_centroids_vs_runtime"]["min_row_cosine"] < 0.99999:
        sys.exit("NB1d's v3_seed0 centroids differ from the served ones. Nothing embedded.")

    upload = datasets.load_fulcher2026_upload()
    (OUT / "cell_ids.txt").write_text("\n".join(upload.cell_ids) + "\n")
    for name, path in MODELS.items():
        z, aligned, value_scale = pipeline.embed_query(encoder.load_encoder(path), genes, upload)
        np.save(OUT / f"{name}_latent.npy", z)
        print(f"{name}: {z.shape}, value scale {value_scale.detected}, "
              f"{aligned.n_features_matched} genes matched, observed per cell min {aligned.per_cell_observed_genes.min()}")


if __name__ == "__main__":
    main()
