"""Organ references v2, diagnostic A1 (research/organ-references.md, "Version 2";
the plan of 2026-10-18): do immunoglobulin constant chains and serum proteins
cause the sinks on the development protein sets?

The lymph node calls tonsil pools and epithelium plasma cell; the lung calls
control epithelial pools macrophage; the colon calls T-cell pools myeloid.
Tissue protein carries extracellular immunoglobulin and serum proteins that,
in an RNA reference, only plasma cells (or no cell) make.

Each organ's own G3 code (research/notebooks/<organ>_development.py, g3)
runs on its v1 bundle with these gene sets removed from every upload, as a v2
gene space would remove them:
- IG: immunoglobulin constant chains and JCHAIN (IG_PATTERN);
- SERUM: the serum families in SERUM_FAMILIES that no reference class of
  that organ expresses (maximum class mean below TAU, log-normalised RNA);
  hemoglobins are always in, since no organ has an erythroid class;
- IG+SERUM;
- for each, RANDOM_DRAWS controls dropping as many genes the upload
  detects, chosen at random.

Decision rule, fixed here before the run. A set qualifies for every v2
organ if:
1. in at least one organ, its primary metric improves on no masking by
   more than the best of its random drops;
2. no guard falls below its bar in any organ;
3. no metric worsens by more than the worst of its random drops.

If IG and SERUM both qualify, v2 removes their union; if neither does, v2
removes nothing and the sinks' cause stays open.

The development sets read here were read before (G3 of v1); they are
"seen" (research/benchmark/side-tests.md). The evaluation suites are not
touched.

    python research/notebooks/organ_v2_masking.py      # from the repository root (GPU)

Writes research/notebook-outputs/organ_v2_masking/: rules.json (first),
runs.json, summary.json.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "research" / "notebooks"))
import li_development as li  # noqa: E402
import lung_development  # noqa: E402
import lymph_node_development  # noqa: E402
from organ_reference import bundle, data  # noqa: E402

from service.pipeline import alignment, gene_ids  # noqa: E402

OUT = REPO / "research" / "notebook-outputs" / "organ_v2_masking"
ORGANS = {"lymph_node": lymph_node_development, "lung": lung_development, "large_intestine": li}
IG_PATTERN = re.compile(r"^(IGH[AGMDE]\d?|IGKC|IGLC\d|IGLL\d|JCHAIN)$")
SERUM_FAMILIES = [
    # hemoglobins
    "HBA1", "HBA2", "HBB", "HBD", "HBG1", "HBG2", "HBE1", "HBZ", "HBM", "HBQ1",
    # albumin, apolipoproteins
    "ALB", "APOA1", "APOA2", "APOA4", "APOA5", "APOB", "APOC1", "APOC2", "APOC3", "APOC4", "APOD", "APOE", "APOH", "APOM",
    # complement
    "C1QA", "C1QB", "C1QC", "C1R", "C1S", "C2", "C3", "C4A", "C4B", "C4BPA", "C4BPB", "C5", "C6", "C7", "C8A", "C8B",
    "C8G", "C9", "CFB", "CFD", "CFH", "CFI",
    # coagulation and fibrinogen
    "FGA", "FGB", "FGG", "F2", "F9", "F10", "F12", "KNG1", "PLG", "HRG", "SERPINC1", "SERPIND1", "SERPINF2",
    # acute phase and carriers
    "HP", "HPX", "TF", "SERPINA1", "SERPINA3", "A2M", "ORM1", "ORM2", "AHSG", "ITIH1", "ITIH2", "ITIH3", "ITIH4",
    "VTN", "AMBP", "RBP4", "TTR", "GC", "CP", "SAA1", "SAA2", "CRP", "AGT", "AFM", "LPA",
]
HEMOGLOBINS = {g for g in SERUM_FAMILIES if g.startswith("HB")}
TAU = 0.5  # log-normalised RNA: a class mean at or above this means a reference class makes the gene
RANDOM_DRAWS = 10
SEED = 20261018
# Each organ's metrics from its g3 output. "better" is +1 if higher is better.
# The primary metric is the sink; guards carry their G3 bar.
METRICS = {
    "lymph_node": {
        "primary": "zheng_group_accuracy",
        "metrics": {
            "zheng_group_accuracy": (lambda r: r["zheng_tonsil"]["group_accuracy"], +1),
            "zheng_plasma_guesses": (lambda r: sum(a["best_guess"] == "plasma cell" for a in r["zheng_tonsil"]["answers"]), -1),
            "pxd011683_b_share": (lambda r: r["pxd011683"]["b_share"], +1),
            "coscia_auroc": (lambda r: r["coscia2024"]["auroc_b_over_t"], +1),
            "coscia_epithelium_plasma": (lambda r: sum(a["truth"] == "epithelium" and a["label"] == "plasma cell"
                                                       for a in r["coscia2024"]["answers"]), -1),
        },
        "guards": {"hpa_lymph_node_pools": (lambda r: r["hpa"]["group_accuracy_lymph_node_pools"], 80.0)},
        "reported": {"hpa_non_immune_pools_b_group": lambda r: sum(
            v for k, v in r["hpa"]["called_groups"].get("B cell", {}).items()
            if k not in ("b-cells", "cd4 t-cells", "cd8 t-cells", "macrophages", "neutrophils"))},
    },
    "lung": {
        "primary": "bpd_auroc",
        "metrics": {
            "bpd_auroc": (lambda r: r["bpd"]["auroc_epithelial"], +1),
            "bpd_epithelial_immune": (lambda r: r["bpd"]["argmax_lineage"].get("immune", {}).get("epithelial", 0), -1),
        },
        "guards": {"hpa_at2_over_at1": (lambda r: r["hpa"]["auroc_at2_over_at1"], 0.8),
                   "ipf_foci_over_alveoli": (lambda r: r["ipf"]["auroc_stromal_ff_over_alveoli"], 0.7)},
        "reported": {},
    },
    "large_intestine": {
        "primary": "zheng_group_accuracy",
        "metrics": {
            "zheng_group_accuracy": (lambda r: r["zheng"]["group_accuracy"], +1),
            "zheng_t_pools_myeloid": (lambda r: sum(r["zheng"]["called_groups"].get("myeloid", {}).get(t, 0) for t in ("cd4", "cd8")), -1),
        },
        "guards": {"kabatnik_auroc": (lambda r: r["kabatnik"]["auroc_epithelial"], 0.8)},
        "reported": {"polyp_group_aurocs": lambda r: {g: v["auroc"] for g, v in r["polyp"]["groups"].items()}},
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gene_sets(b, bundle_dir: Path) -> dict[str, list[str]]:
    """IG and SERUM for one organ, over its gene space."""
    space = [g.upper() for g in b.feature_genes]
    stats = np.load(bundle_dir / "class_balanced_stats.npz")
    absolute = b.class_means * stats["sd"][None, :] + stats["mu"][None, :]  # class means, log-normalised RNA
    top = dict(zip(space, absolute.max(0)))
    ig = sorted(g for g in space if IG_PATTERN.match(g))
    serum = sorted(g for g in SERUM_FAMILIES if g in top and (g in HEMOGLOBINS or top[g] < TAU))
    return {"IG": ig, "SERUM": serum, "IG+SERUM": sorted(set(ig) | set(serum)),
            "made_by_a_class": {g: round(float(top[g]), 3) for g in SERUM_FAMILIES if g in top and g not in serum}}


class Masker:
    """li.run_upload with some rows removed: a named gene set, or as many
    detected genes drawn at random."""

    def __init__(self, original, space: set[str]):
        self.original, self.space = original, space
        self.drop: set[str] = set()
        self.random: tuple[int, int] | None = None  # (draw, set size) when drawing at random
        self.dropped: list[int] = []

    def __call__(self, b, raw: alignment.RawMatrix):
        symbols = [s.upper() if s else None for s in gene_ids.resolve_identifiers(raw.gene_names).resolved]
        detected = np.isfinite(np.asarray(raw.values, np.float64)).any(1)
        in_set = np.array([s in self.drop for s in symbols])
        if self.random is not None:
            draw, _ = self.random
            k = int((in_set & detected).sum())
            pool = np.flatnonzero(detected & ~in_set & np.array([s in self.space for s in symbols]))
            rng = np.random.default_rng([SEED, draw, len(raw.cell_ids), k])
            remove = np.zeros(len(symbols), bool)
            remove[rng.choice(pool, size=min(k, len(pool)), replace=False)] = True
        else:
            remove = in_set
        self.dropped.append(int(remove.sum()))
        keep = ~remove
        masked = alignment.RawMatrix(gene_names=[g for g, k in zip(raw.gene_names, keep) if k], cell_ids=raw.cell_ids,
                                     values=np.asarray(raw.values)[keep])
        return self.original(b, masked)


def measure(organ: str, result: dict) -> dict:
    spec = METRICS[organ]
    return {"metrics": {k: float(f(result)) for k, (f, _) in spec["metrics"].items()},
            "guards": {k: float(f(result)) for k, (f, _) in spec["guards"].items()},
            "reported": {k: f(result) for k, f in spec["reported"].items()}}


def decide(runs: dict) -> dict:
    out = {}
    for name in ("IG", "SERUM"):
        organs, qualifies_somewhere, ok = {}, False, True
        for organ, spec in METRICS.items():
            base = runs[organ]["none"]["metrics"]
            mine = runs[organ][name]
            rand = runs[organ][f"{name} random"]
            gain = lambda m, r: spec["metrics"][m][1] * (r["metrics"][m] - base[m])  # noqa: E731
            primary = spec["primary"]
            best_random = max(gain(primary, r) for r in rand)
            beats = gain(primary, mine) > max(0.0, best_random)
            guards = {g: mine["guards"][g] >= bar for g, (_, bar) in spec["guards"].items()}
            worse = {m: gain(m, mine) < min(gain(m, r) for r in rand) - 1e-9 for m in spec["metrics"]}
            organs[organ] = {"primary_gain": round(gain(primary, mine), 4), "best_random_gain": round(best_random, 4),
                             "beats_random": beats, "guards_hold": guards, "worse_than_every_random": worse}
            qualifies_somewhere |= beats
            ok &= all(guards.values()) and not any(worse.values())
        out[name] = {"organs": organs, "qualifies": bool(qualifies_somewhere and ok)}
    chosen = [n for n in ("IG", "SERUM") if out[n]["qualifies"]]
    out["v2_removes"] = "IG+SERUM" if len(chosen) == 2 else (chosen[0] if chosen else "nothing")
    return out


def main() -> None:
    warnings.simplefilter("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    loaded, sets = {}, {}
    for organ in ORGANS:
        bundle_dir = data.WORK / organ / "bundle"
        b = bundle.load(bundle_dir)
        loaded[organ] = (b, bundle_dir)
        sets[organ] = gene_sets(b, bundle_dir)
        print(f"{organ}: IG {len(sets[organ]['IG'])}, SERUM {len(sets[organ]['SERUM'])} ({time.time() - t0:.0f}s)", flush=True)
    data.save_json(OUT / "rules.json", {
        "script_sha256": sha256(Path(__file__)), "started": datetime.now().isoformat(timespec="seconds"),
        "tau": TAU, "random_draws": RANDOM_DRAWS, "seed": SEED, "ig_pattern": IG_PATTERN.pattern,
        "serum_families": SERUM_FAMILIES, "sets": sets,
        "primary": {o: s["primary"] for o, s in METRICS.items()},
        "guards": {o: {g: bar for g, (_, bar) in s["guards"].items()} for o, s in METRICS.items()},
        "bundles": {o: sha256(d / "MANIFEST.json") for o, (_, d) in loaded.items()}})
    original = li.run_upload
    runs = {}
    try:
        for organ, module in ORGANS.items():
            b, bundle_dir = loaded[organ]
            masker = Masker(original, {g.upper() for g in b.feature_genes})
            li.run_upload = masker
            runs[organ] = {}
            with bundle.gene_map(bundle_dir):
                for name in ("none", "IG", "SERUM", "IG+SERUM"):
                    masker.drop, masker.random, masker.dropped = set(sets[organ].get(name, [])), None, []
                    runs[organ][name] = {**measure(organ, module.g3(b)), "rows_dropped": masker.dropped}
                    for draw_name in (("IG", "SERUM", "IG+SERUM") if name == "none" else ()):
                        draws = []
                        for draw in range(RANDOM_DRAWS):
                            masker.drop, masker.random, masker.dropped = set(sets[organ][draw_name]), (draw, 0), []
                            draws.append({**measure(organ, module.g3(b)), "rows_dropped": masker.dropped})
                        runs[organ][f"{draw_name} random"] = draws
                    print(f"{organ} {name}: {runs[organ][name]['metrics']} ({time.time() - t0:.0f}s)", flush=True)
            data.save_json(OUT / "runs.json", runs)
    finally:
        li.run_upload = original
    summary = {"finished": datetime.now().isoformat(timespec="seconds"), "seconds": round(time.time() - t0),
               "decision": decide(runs),
               "table": {o: {n: r["metrics"] | r["guards"] for n, r in runs[o].items() if not n.endswith("random")}
                         for o in runs}}
    data.save_json(OUT / "summary.json", summary)
    print(json.dumps(summary["decision"], indent=1))


if __name__ == "__main__":
    main()
