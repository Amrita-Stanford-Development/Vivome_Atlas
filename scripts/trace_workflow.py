"""The Workflow page's trace (web/workflow.html, docs/web/workflow.md): the
PBMC240 example (service/examples/pbmc240_proteins_raw.tsv) run through the
served model's own code, stage by stage, with what each stage produced.

Every number the page shows about a projection comes from here; the browser
computes none of them. The script recomputes each stage with the service's
functions (service/pipeline/) and checks, before writing anything, that its
stage-by-stage answers equal pipeline.run_projection's on every cell: label,
level, set, reason and best guess. service/tests/test_workflow_trace.py
checks the written trace against a fresh run.

It writes, under service/model/evidence/workflow/:
- pbmc240_trace_v42.json.gz: every cell's outcome, the stages' summaries,
  the upload's smoothing graph, a heatmap of 24 genes over 52 cells at each
  preprocessing step, and the full detail of a few story cells (the file's
  first run, then the first run of each outcome);
- input_snippets.json: a few rows and columns of other development inputs
  (SCoPE2's published matrix, Fulcher 2026's protein table) and the
  reference's first cell ids, for the page's "what the files look like".

Re-run it whenever the served model changes (docs/web/manifest.md, the
release protocol), then scripts/build_manifest.py, which rebuilds
web/data/workflow.json from it (scripts/build_workflow.py).

    python scripts/trace_workflow.py      # from the repository root; needs torch and v3.1's members
"""
from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import json
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from service import config  # noqa: E402
from service.pipeline import alignment, ensemble, fusion, gene_ids, pipeline, search, smoothing  # noqa: E402
from service.pipeline.topk import chunked_topk  # noqa: E402

VERSION = "v4.2"
EXAMPLE = REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv"
WEAK_LABELS = REPO / "service" / "examples" / "pbmc240_cell_metadata.csv"
ATLAS_RNA = REPO / "web" / "data" / "metadata_RNA_lat128.csv"
OUT_DIR = REPO / "service" / "model" / "evidence" / "workflow"
TRACE = OUT_DIR / "pbmc240_trace_v42.json.gz"
SNIPPETS = OUT_DIR / "input_snippets.json"

# The heatmap's genes: the first 24 of these that the upload measures in at
# least a tenth of its cells, then the most observed others if fewer.
MARKERS = ("CD3E", "CD3D", "CD2", "LCK", "IL7R", "CD8A", "CD4", "NKG7", "GNLY", "PRF1", "GZMB", "GZMA", "KLRD1",
           "LYZ", "S100A8", "S100A9", "CD14", "FCGR3A", "CST3", "HLA-DRA", "CD74", "MS4A1", "CD79A", "PPBP", "PF4",
           "ITGA2B", "HBB", "CORO1A", "PTPRC", "VIM")
HEATMAP_GENES, HEATMAP_CELLS = 24, 52
# Heatmap cells after the story cells: per weak label, in file order.
HEATMAP_STRATA = (("T cell", 12), ("NK cell", 12), ("Monocyte", 5), ("Dendritic", 8), ("Platelet", 7),
                  ("unassigned", 8))
OUTCOMES = ("class", "group", "lineage", "ambiguous_between_classes", "no_confident_label",
            "outside_supported_region", "coverage_too_low")
RAW_ROW_ENTRIES = 40
SCATTER_POINTS = 200


def r4(x) -> float:
    return round(float(x), 4)


def r2(x) -> float:
    return round(float(x), 2)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def histogram(values, edges) -> dict:
    counts, _ = np.histogram(np.asarray(values, dtype=np.float64), bins=np.asarray(edges, dtype=np.float64))
    return {"edges": [float(e) for e in edges], "counts": counts.astype(int).tolist()}


def bits(flags) -> str:
    """A boolean vector, packed eight to a byte (first flag in the top bit), as base64."""
    return base64.b64encode(np.packbits(np.asarray(flags, dtype=bool)).tobytes()).decode("ascii")


def outcome(cell: dict) -> str:
    return cell["label_level"] if not cell["abstained"] else cell["abstain_reason"]


def weak_labels() -> dict:
    with WEAK_LABELS.open(newline="", encoding="utf-8") as handle:
        return {row["cell"]: row["label"] for row in csv.DictReader(handle)}


def story_cells(cells: list[dict]) -> list[int]:
    """The file's first run, then the first run of each outcome, in OUTCOMES order."""
    picked = [0]
    for kind in OUTCOMES:
        i = next((i for i, c in enumerate(cells) if outcome(c) == kind), None)
        if i is not None and i not in picked:
            picked.append(i)
    return picked


def heatmap_genes(aligned, feature_genes: list[str]) -> list[int]:
    index = {g: i for i, g in enumerate(feature_genes)}
    observed = aligned.mask.mean(axis=0)
    chosen = [index[g] for g in MARKERS if g in index and observed[index[g]] >= 0.1][:HEATMAP_GENES]
    for col in np.argsort(-observed, kind="stable"):
        if len(chosen) >= HEATMAP_GENES:
            break
        if int(col) not in chosen:
            chosen.append(int(col))
    return chosen


def heatmap_cells(story: list[int], cell_ids: list[str], weak: dict) -> list[int]:
    chosen = list(story)
    for label, n in HEATMAP_STRATA:
        for i in [i for i, c in enumerate(cell_ids) if weak.get(c) == label and i not in chosen][:n]:
            chosen.append(i)
    for i in range(len(cell_ids)):  # fill up from file order if a stratum ran short
        if len(chosen) >= HEATMAP_CELLS:
            break
        if i not in chosen:
            chosen.append(i)
    return chosen[:HEATMAP_CELLS]


def main() -> None:
    bundle = pipeline.load_bundle(VERSION)
    answers = bundle.answers
    names = bundle.class_names
    text = EXAMPLE.read_text(encoding="utf-8")
    weak = weak_labels()

    # The service's own run, the one the page must agree with.
    raw = alignment.parse_matrix_csv(text)
    response = json.loads(json.dumps(pipeline.run_projection(bundle, raw, modality="prot")))
    cells = response["cells"]

    # ---- Stages 0 to 2, step by step ----
    header = text.split("\n", 1)[0].rstrip("\r").split("\t")
    annotation = [h for h in header if h in alignment._DIA_NN_ANNOTATION_COLUMNS]
    run_headers = [h for h in header if h and h not in alignment._DIA_NN_ANNOTATION_COLUMNS and h != "Genes"]
    observed_raw = ~np.isnan(raw.values)
    scaled_values, value_scale = alignment.detect_and_transform_value_scale(raw.values)
    linear_observed = raw.values[observed_raw & np.isfinite(raw.values)]
    scaled = alignment.RawMatrix(raw.gene_names, raw.cell_ids, scaled_values)
    collapsed = alignment.collapse_duplicate_genes(scaled)
    resolution = gene_ids.resolve_identifiers(raw.gene_names)
    aligned = alignment.align_to_feature_space(collapsed, bundle.feature_genes)
    full_query = alignment.zscore_per_gene(collapsed.values).T
    smoothed, aligned_again, _ = pipeline._prepare_query(bundle.feature_genes, raw)
    assert np.array_equal(aligned.values, aligned_again.values) and np.array_equal(aligned.mask, aligned_again.mask)

    k, alpha, n_pca, seed = config.SMOOTHING_K, config.SMOOTHING_ALPHA, config.SMOOTHING_N_PCA, config.SMOOTHING_SEED
    knn_idx, knn_w = smoothing._knn_weights(full_query, k, n_pca, seed)
    mine = ((1 - alpha) * aligned.values + alpha * np.einsum("nk,nkf->nf", knn_w, aligned.values[knn_idx]))
    assert np.allclose(mine.astype(np.float32), smoothed, atol=1e-6), "the smoothing step differs from the service's"
    # A 2-D layout for drawing the graph: the first two axes of the same
    # L2-normalised PCA the neighbours are found in (smoothing._knn_weights).
    from sklearn.decomposition import PCA
    n_components = min(n_pca, full_query.shape[1], full_query.shape[0] - 1)
    projected = PCA(n_components=n_components, random_state=seed).fit_transform(np.asarray(full_query, np.float32))
    projected = projected / np.clip(np.linalg.norm(projected, axis=1, keepdims=True), 1e-8, None)

    # Duplicate rows merged (Stage 1), largest first.
    by_gene: dict[str, list[int]] = {}
    for i, g in enumerate(gene_ids.resolve_to_feature_symbols(raw.gene_names)):
        if g is not None:
            by_gene.setdefault(g, []).append(i)
    merged = sorted(((g, rows) for g, rows in by_gene.items() if len(rows) > 1),
                    key=lambda item: (-int(observed_raw[item[1]].any(axis=0).sum()), item[0]))
    merged_examples = [{"gene": g, "rows": len(rows),
                        "best_single_row_cells": int(observed_raw[rows].sum(axis=1).max()),
                        "merged_cells": int(observed_raw[rows].any(axis=0).sum())} for g, rows in merged[:6]]

    # ---- Stage 3: the encoders ----
    smoothed_z = [m.encoder_handle.encode(smoothed, aligned.mask) for m in answers.members]
    anchor_i = answers.coordinate_member
    model = answers.members[anchor_i].encoder_handle.model
    n_genes, n_modules = (int(x) for x in model.A.shape)
    module_sizes = model.A.sum(0).numpy()
    encoder_parameters = int(sum(p.numel() for p in model.parameters()))
    layers = [{"name": "input", "width": 2 * n_genes + 2 * n_modules,
               "parts": {"values": n_genes, "mask": n_genes, "module_values": n_modules,
                         "module_mask_fraction": n_modules}},
              {"name": "linear, LayerNorm, GELU", "width": int(model.body[0].weight.shape[0]),
               "parameters": int(model.body[0].weight.numel() + sum(p.numel() for p in model.body[1].parameters()))},
              {"name": "linear, LayerNorm, GELU", "width": int(model.body[4].weight.shape[0]),
               "parameters": int(model.body[4].weight.numel() + sum(p.numel() for p in model.body[5].parameters()))},
              {"name": "projection, LayerNorm, L2 normalisation", "width": int(model.proj.weight.shape[0]),
               "parameters": int(model.proj.weight.numel() + sum(p.numel() for p in model.norm.parameters()))}]
    assert sum(layer.get("parameters", 0) for layer in layers) == encoder_parameters

    # ---- Stage 4: probabilities (the answers' path, v3.1's centroids) ----
    answer_member_p = [ensemble.member_probabilities(z, m.centroids, m.temperature)
                       for z, m in zip(smoothed_z, answers.members)]
    all_class_probs = ensemble.ensemble_probabilities(answer_member_p)

    # ---- the best guess (v4.2) ----
    counted = aligned.per_cell_observed_genes >= int(bundle.spec["preprocessing"]["min_observed_genes"])
    guess_member_p = [ensemble.member_probabilities(z, m.centroids, m.temperature)
                      for z, m in zip(smoothed_z, bundle.members)]
    on = ensemble.ensemble_probabilities(guess_member_p)
    r_rna = fusion.masked_pearson(aligned.values, aligned.mask, bundle.class_means)
    protein_values, protein_mask = fusion.protein_query(raw, bundle.protein_genes)
    r_prot = fusion.masked_pearson(protein_values, protein_mask, bundle.protein_means)
    covered = bundle.protein_covered
    r = r_rna.copy()
    r[:, covered] = r_prot[:, covered]
    agreement = fusion.upload_agreement(r, all_class_probs, counted)
    used = agreement >= bundle.agreement_threshold
    correlation_p = fusion.correlation_probabilities(r, bundle.correlation_temperature)
    if used:
        raise SystemExit("PBMC240's correlation term is used: this script's detail assumes it is flat; extend it.")
    fused = fusion.fused_probabilities(on, np.full_like(on, 1.0 / on.shape[1]), bundle.fusion_weight)
    guess = fused.argmax(axis=1)
    agreeing = (r.argmax(axis=1) == all_class_probs.argmax(axis=1))

    # ---- Stages 5 to 7: sets, similarity, answers ----
    calibrated = bundle.components.calibrator.calibrate(
        all_class_probs, None, bundle.components.label_space.estimate(None, names, False), guess_positions=guess)
    similarity = np.mean([search.faiss_max_cosine_to_reference(z, m.reference_latents)
                          for z, m in zip(smoothed_z, answers.members)], axis=0)
    coords = answers.pca.project(smoothed_z[anchor_i])

    # Every cell, checked against the service's own run.
    index = {name: i for i, name in enumerate(names)}
    rows = []
    for i, cell in enumerate(cells):
        expected_set = [names[c] for c in calibrated.label_sets[i]] if not cell["abstained"] else []
        assert cell["label_set"] == expected_set, (cell["cell_id"], cell["label_set"], expected_set)
        if "best_guess" in cell:
            assert cell["best_guess"]["label"] == names[guess[i]], cell["cell_id"]
            assert abs(cell["best_guess"]["probability"] - fused[i, guess[i]]) < 5e-6, cell["cell_id"]
        assert abs(cell["reference_similarity"] - similarity[i]) < 5e-6, cell["cell_id"]
        assert np.allclose(cell["coordinates"], coords[i], atol=5e-6), cell["cell_id"]
        top = np.argsort(-all_class_probs[i], kind="stable")[:3]
        rows.append({
            "id": cell["cell_id"], "weak_label": weak.get(cell["cell_id"]),
            "observed": cell["observed_genes"], "similarity": r4(cell["reference_similarity"]),
            "outcome": outcome(cell), "label": cell["label"], "level": cell["label_level"],
            "set": [index[n] for n in cell["label_set"]],
            "candidate_set": calibrated.label_sets[i],
            "confidence": None if cell["confidence"] is None else r4(cell["confidence"]),
            "guess": index[cell["best_guess"]["label"]] if "best_guess" in cell else None,
            "guess_probability": r4(cell["best_guess"]["probability"]) if "best_guess" in cell else None,
            "xyz": [r4(x) for x in cell["coordinates"]],
            "top": [[int(c), r4(all_class_probs[i, c])] for c in top],
            "counted": bool(counted[i]), "agrees": bool(agreeing[i]) if counted[i] else None,
            "layout": [r4(projected[i, 0]), r4(projected[i, 1])],
        })
    outcomes = Counter(row["outcome"] for row in rows)
    assert sum(outcomes.values()) == len(cells)

    # ---- the story cells, in full ----
    story = story_cells(cells)
    anchor = answers.members[anchor_i]
    ref_idx, ref_sim = chunked_topk(smoothed_z[anchor_i][story], anchor.reference_latents, config.TRANSFER_K)
    ref_positions = answers.metadata.class_positions_by_cell()
    a = model.A.numpy()
    module_fraction = (aligned.mask @ a) / np.clip(a.sum(0), 1e-6, None)
    detail = []
    for s, i in enumerate(story):
        best_covered = int(np.flatnonzero(covered)[np.argmax(r_prot[i, covered])])
        observed_proteins = np.flatnonzero(protein_mask[i] > 0)
        step = max(1, len(observed_proteins) // SCATTER_POINTS)
        points = observed_proteins[::step][:SCATTER_POINTS]
        raw_row = []
        for g in range(min(RAW_ROW_ENTRIES, len(raw.gene_names))):
            v = raw.values[g, i]
            raw_row.append([raw.gene_names[g], None if np.isnan(v) else r2(v),
                            None if np.isnan(scaled_values[g, i]) else r2(scaled_values[g, i])])
        detail.append({
            "cell": i, "id": cells[i]["cell_id"],
            "raw_row": raw_row,
            "members": [{"name": m.name, "temperature": r4(m.temperature),
                         "cosine": [r4(x) for x in smoothed_z[j][i] @ m.centroids.T],
                         "probability": [r4(x) for x in answer_member_p[j][i]]}
                        for j, m in enumerate(answers.members)],
            "ensemble": [r4(x) for x in all_class_probs[i]],
            "guess": {
                "members": [{"name": m.name, "temperature": r4(m.temperature),
                             "probability": [r4(x) for x in guess_member_p[j][i]]}
                            for j, m in enumerate(bundle.members)],
                "encoder": [r4(x) for x in on[i]],
                "r_rna": [r4(x) for x in r_rna[i]],
                "r_protein": [r4(x) if ok else None for x, ok in zip(r_prot[i], covered)],
                "r": [r4(x) for x in r[i]],
                "correlation_probability": [r4(x) for x in correlation_p[i]],
                "fused": [r4(x) for x in fused[i]],
                "scatter": {"class": best_covered, "r": r4(r_prot[i, best_covered]),
                            "observed_proteins": int(len(observed_proteins)),
                            "points": [[r2(protein_values[i, j]), r2(bundle.protein_means[best_covered, j])]
                                       for j in points]},
            },
            "embedding": [round(float(x), 3) for x in smoothed_z[anchor_i][i]],
            "observed_bits": bits(aligned.mask[i] > 0),
            "module_fraction": [r2(x) for x in module_fraction[i]],
            "neighbours": [{"class": int(ref_positions[j]), "similarity": r4(sim),
                            "xyz": [r4(x) for x in answers.pca.project(anchor.reference_latents[[j]])[0]]}
                           for j, sim in zip(ref_idx[s], ref_sim[s])],
            "response": cells[i],
        })

    # ---- the heatmap: one gene panel over a few cells, at each step ----
    h_genes = heatmap_genes(aligned, bundle.feature_genes)
    h_cells = heatmap_cells(story, raw.cell_ids, weak)
    collapsed_rows = {g: i for i, g in enumerate(gene_ids.resolve_to_feature_symbols(collapsed.gene_names)) if g}
    log2 = [[None if np.isnan(collapsed.values[collapsed_rows[bundle.feature_genes[g]], c])
             else r2(collapsed.values[collapsed_rows[bundle.feature_genes[g]], c]) for g in h_genes] for c in h_cells]
    heatmap = {
        "genes": [bundle.feature_genes[g] for g in h_genes], "cells": h_cells,
        "rule": f"genes: the first {HEATMAP_GENES} of a fixed marker list measured in at least a tenth of the cells, "
                "then the most observed; cells: the story cells, then per weak label in file order",
        "log2": log2,
        "z": [[r2(aligned.values[c, g]) for g in h_genes] for c in h_cells],
        "mask": [[int(aligned.mask[c, g]) for g in h_genes] for c in h_cells],
        "smoothed": [[r2(smoothed[c, g]) for g in h_genes] for c in h_cells],
    }

    # The site's atlas coordinates must be the service's projection of the
    # coordinate member's reference latents (ensemble.py), or a projected
    # cell would land off the displayed atlas.
    with ATLAS_RNA.open(newline="", encoding="utf-8") as handle:
        head = [row for _, row in zip(range(200), csv.DictReader(handle))]
    site = np.array([[float(row[k]) for k in ("PC1", "PC2", "PC3")] for row in head])
    served = answers.pca.project(anchor.reference_latents[[int(row["orig_index"]) for row in head]])
    atlas_gap = float(np.abs(site - served).max())
    assert atlas_gap < 1e-4, f"the site's atlas coordinates differ from the service's by {atlas_gap}"

    observed_per_cell = observed_raw.sum(axis=0)
    observed_per_protein = observed_raw.mean(axis=1)
    trace = {
        "schema": 1,
        "built_for": {"atlas_version": config.ATLAS_VERSION, "pipeline_version": bundle.pipeline_version,
                      "model_version": bundle.model_version},
        "sources": {"example": {"path": EXAMPLE.relative_to(REPO).as_posix(), "sha256": sha256(EXAMPLE)},
                    "spec": {"path": config.V42_SPEC_PATH.relative_to(REPO).as_posix(),
                             "sha256": sha256(config.V42_SPEC_PATH)},
                    "weak_labels": {"path": WEAK_LABELS.relative_to(REPO).as_posix(), "sha256": sha256(WEAK_LABELS)}},
        "class_order": names,
        "hierarchy": {n: answers.hierarchy[n] for n in names},
        "stages": {
            "parse": {"format": "DIA-NN protein-group report", "rows": len(raw.gene_names), "runs": len(raw.cell_ids),
                      "annotation_columns": annotation, "identifier_column": "Genes",
                      "header_examples": [[h, alignment._clean_dia_nn_cell_id(h)] for h in run_headers[:4]],
                      "missing_share": r4(1 - observed_raw.mean()),
                      "proteins_per_run": histogram(observed_per_cell, np.arange(0, observed_per_cell.max() + 200, 200)),
                      "runs_per_protein": histogram(observed_per_protein, np.linspace(0, 1, 11))},
            "scale": {"detected": value_scale.detected, "transformed": value_scale.transformed,
                      "median_observed": r2(np.median(linear_observed)),
                      "threshold": config.LINEAR_SCALE_MEDIAN_THRESHOLD,
                      "linear_log10": histogram(np.log10(linear_observed[linear_observed > 0]), np.arange(0, 9.5, 0.5)),
                      "log2": histogram(scaled_values[~np.isnan(scaled_values)], np.arange(0, 31, 1))},
            "collapse": {"rows_before": len(scaled.gene_names), "rows_after": len(collapsed.gene_names),
                         "genes_merged": len(merged), "examples": merged_examples},
            "ids": {"matched": resolution.matched, "unmapped": resolution.unmapped, "ambiguous": resolution.ambiguous,
                    "unmapped_examples": resolution.unmapped_identifiers[:40],
                    "ambiguous_examples": resolution.ambiguous_identifiers[:20]},
            "align": {"feature_space": len(bundle.feature_genes), "matched": aligned.n_features_matched,
                      "unmatched_rows": aligned.n_features_unmatched, "floor": int(config.MIN_OBSERVED_GENES),
                      "below_floor": int((aligned.per_cell_observed_genes < config.MIN_OBSERVED_GENES).sum()),
                      "observed_median": int(np.median(aligned.per_cell_observed_genes)),
                      "matched_bits": bits(aligned.mask.any(axis=0)),
                      "bits_order": "service/model/runtime/feature_space_genes.csv"},
            "smoothing": {"k": k, "alpha": alpha, "pca_components": int(n_components), "seed": seed,
                          "neighbours": knn_idx.astype(int).tolist(),
                          "weights": [[round(float(w), 3) for w in row] for row in knn_w]},
            "encoder": {"members": [m.name for m in answers.members], "coordinate_member": anchor.name,
                        "genes": n_genes, "modules": n_modules, "parameters": encoder_parameters, "layers": layers,
                        "module_sizes": histogram(module_sizes, [1, 2, 3, 5, 10, 20, 40, 80, 160, 320, 640])},
            "fusion": {"agreement": r4(agreement), "threshold": bundle.agreement_threshold,
                       "correlation_term": "used" if used else "flat", "counted": int(counted.sum()),
                       "agreeing": int(agreeing[counted].sum()), "encoder_weight_flat": bundle.fusion_weight,
                       "encoder_weight_used": fusion.encoder_weight_where_used(bundle),
                       "correlation_temperature": bundle.correlation_temperature,
                       "smoothed_share": bundle.smoothed_share,
                       "protein_classes": [int(c) for c in np.flatnonzero(covered)],
                       "protein_genes": len(bundle.protein_genes),
                       "protein_genes_observed": int((protein_mask.sum(0) > 0).sum())},
            "calibration": {"alpha": answers.spec["conformal"]["alpha"],
                            "qhat": [r4(answers.spec["conformal"]["qhat_by_class"][n]) for n in names],
                            "calibrated_on": answers.spec["conformal"]["calibrated_on"],
                            "set_includes_best_guess": True},
            "ood": {"threshold": answers.ood_threshold, "atlas_gap": atlas_gap},
        },
        "outcomes": {kind: outcomes.get(kind, 0) for kind in OUTCOMES},
        "cells": rows,
        "story": {"rule": "the file's first run, then the first run of each outcome (class, group, lineage, "
                          "ambiguous, no confident label, outside the supported region, too few genes)",
                  "cells": story},
        "detail": detail,
        "heatmap": heatmap,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(trace, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    with gzip.GzipFile(TRACE, "wb", mtime=0) as handle:  # mtime 0: the same trace gives the same bytes
        handle.write(payload)
    SNIPPETS.write_bytes((json.dumps(snippets(), indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"wrote {TRACE.relative_to(REPO)} ({TRACE.stat().st_size:,} bytes) and {SNIPPETS.relative_to(REPO)}")
    print(f"  {len(cells)} cells; outcomes {dict(trace['outcomes'])}; story cells {story}")
    print(f"  agreement {agreement:.4f} (term {'used' if used else 'flat'}); atlas gap {atlas_gap:.2e}")


def cell(text: str):
    """A table cell as a number, or None where the file leaves it missing."""
    return None if text.strip() in ("", "NA", "NaN", "nan") else r2(text)


def snippets() -> dict:
    """A corner of each other development input, as its file holds it, and
    the reference's first cells (its expression matrix is not in this repository)."""
    from benchmark import baselines_v31, datasets
    out = {}
    scope2 = baselines_v31.SCOPE2
    with scope2.open(encoding="utf-8") as handle:
        lines = [next(handle).rstrip("\n").split("\t") for _ in range(7)]
    out["scope2"] = {"path": scope2.relative_to(REPO).as_posix(), "orientation": "cells in rows, genes in columns",
                     "values": "as published: centred and batch-corrected",
                     "header": lines[0][:7], "rows": [[row[0]] + [cell(v) for v in row[1:7]] for row in lines[1:]]}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            fulcher = datasets.FULCHER2026["files"]["matrix"]
            with fulcher.open(encoding="utf-8") as handle:
                header = handle.readline().rstrip("\n").split("\t")
                gene = header.index("Gene")
                channels = [i for i, h in enumerate(header) if h not in alignment._FRAGPIPE_TMT_ANNOTATION_COLUMNS
                            and not h.startswith(alignment._FRAGPIPE_TMT_REFERENCE_PREFIXES)][:5]
                body = []  # the first six proteins seen in at least three of these five channels
                for line in handle:
                    row = line.rstrip("\n").split("\t")
                    if sum(cell(row[i]) is not None for i in channels) >= 3:
                        body.append(row)
                    if len(body) == 6:
                        break
            out["fulcher2026"] = {
                "path": fulcher.relative_to(REPO).as_posix(),
                "sha256": datasets.FULCHER2026["sha256"]["matrix"],
                "orientation": "proteins in rows, TMT channels (cells) in columns",
                "values": "FragPipe TMT-Integrator abundances on a linear scale; the service takes log2",
                "annotation_columns": [h for h in header if h in alignment._FRAGPIPE_TMT_ANNOTATION_COLUMNS],
                "channels": len([h for h in header if h not in alignment._FRAGPIPE_TMT_ANNOTATION_COLUMNS
                                 and not h.startswith(alignment._FRAGPIPE_TMT_REFERENCE_PREFIXES)]),
                "header": ["Gene"] + [header[i] for i in channels],
                "rows": [[row[gene]] + [cell(row[i]) for i in channels]
                         for row in body]}
        except (FileNotFoundError, OSError):
            out["fulcher2026"] = None
    with (REPO / "service" / "model" / "runtime" / "reference_metadata.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        out["reference"] = {"path": "service/model/runtime/reference_metadata.csv",
                            "note": "the reference's expression matrix is not in this repository; its cells, "
                                    "labels and latent coordinates are",
                            "header": reader.fieldnames, "rows": [list(row.values()) for _, row in zip(range(6), reader)]}
    return out


if __name__ == "__main__":
    main()
