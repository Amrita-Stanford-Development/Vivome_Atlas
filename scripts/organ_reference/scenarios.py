"""The split and the simulated uploads.

Blood keeps T1 NB1's own: stratified_split by class (NB1 cell 4, seed 0) and
sim_generator.make_suite with its blood scenarios, so its suites come out
byte for byte. Another organ splits within class and donor (each donor's
cells of a class spread over train, validation and test alike) and draws its
uploads from scenarios built from its hierarchy (make_suite below):
- random_1, 2, 3, 5 and 8 classes, twice each per cycle, as for blood;
- one upload of 2 to 4 classes from each lineage;
- "tissue": every eligible class in the pool's own proportions, as a whole
  dissociated sample would arrive.
Everything else follows sim_generator.make_suite: sizes, proportions, the
upload's minimum cells per class, half of real-profile uploads with per-cell
missingness, 15% stressed.
"""
from __future__ import annotations

import numpy as np

from . import sim_generator as sg


def stratified_split(y, test_size, val_size, seed):
    """NB1 cell 4, unchanged."""
    rng = np.random.default_rng(seed)
    n = len(y); idx = np.arange(n)
    tr, va, te = [], [], []
    for c in np.unique(y):
        ci = idx[y == c]; rng.shuffle(ci)
        n_te = max(1, int(round(test_size * len(ci)))) if len(ci) > 4 else 0
        n_va = max(1, int(round(val_size * len(ci)))) if len(ci) > 4 else 0
        te.append(ci[:n_te]); va.append(ci[n_te:n_te + n_va]); tr.append(ci[n_te + n_va:])
    return np.concatenate(tr), np.concatenate(va), np.concatenate(te)


def split(cfg: dict, y: np.ndarray, donors: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    s = cfg["split"]
    if s["stratify"] == "class":
        return stratified_split(y, s["test"], s["val"], s["seed"])
    if s["stratify"] == "class_donor":
        # NB1's rule applied to each (class, donor) stratum
        keys = np.unique(donors, return_inverse=True)[1]
        strata = y.astype(np.int64) * (keys.max() + 1) + keys
        tr, va, te = stratified_split(strata, s["test"], s["val"], s["seed"])
        return np.sort(tr), np.sort(va), np.sort(te)
    raise ValueError(s["stratify"])


def _classes_for(scenario, eligible, classes, hierarchy, rng):
    if scenario.startswith("random_"):
        k = min(int(scenario.split("_")[1]), len(eligible))
        return sorted(rng.choice(eligible, k, replace=False).tolist())
    if scenario.startswith("lineage:"):
        pool = [c for c in eligible if hierarchy[classes[c]]["lineage"] == scenario.split(":", 1)[1]]
        return sorted(rng.choice(pool, min(len(pool), rng.integers(2, 5)), replace=False).tolist())
    if scenario == "tissue":
        return sorted(eligible.tolist())
    raise ValueError(scenario)


def make_suite(name, pool_idx, pool_y, classes, hierarchy, profiles, n_uploads, seed, min_cells=20,
               cap_per_class=False):
    """sim_generator.make_suite with the organ's scenarios and profiles.

    With cap_per_class (organ references v2), a class with fewer cells than
    its share gives all it has and the other classes keep their share;
    otherwise, as v1, the whole upload shrinks to the scarcest class, so a
    low min_cells would shrink most uploads. Each upload also records how
    many lineages its classes span."""
    rng = np.random.default_rng(seed)
    by_class = {c: pool_idx[pool_y == c] for c in np.unique(pool_y)}
    eligible = np.array([c for c, v in by_class.items() if len(v) >= min_cells])
    lineages = sorted({hierarchy[classes[c]]["lineage"] for c in eligible})
    scen = (["random_1", "random_2", "random_3", "random_5", "random_8"] * 2
            + [f"lineage:{x}" for x in lineages] + ["tissue"])
    specs = []
    for u in range(n_uploads):
        sc = scen[u % len(scen)]
        cls = _classes_for(sc, eligible, classes, hierarchy, rng)
        if sc == "tissue":
            props = np.array([len(by_class[c]) for c in cls], float)
            props /= props.sum()
        else:
            props = rng.dirichlet(np.ones(len(cls)))
        n_total = int(rng.choice(sg.SIZES))
        want = np.maximum(5, np.round(props * n_total)).astype(int)
        avail = np.array([len(by_class[c]) for c in cls])
        if cap_per_class:
            take = np.minimum(want, avail)
        else:
            scale = min(1.0, float(np.min(avail / want)))
            take = np.maximum(3, np.floor(want * scale)).astype(int)
        cell_idx = np.concatenate([rng.choice(by_class[c], min(t, len(by_class[c])), replace=False)
                                   for c, t in zip(cls, take)])
        prof = str(rng.choice(profiles))
        miss = "per_cell" if (not prof.startswith("random") and rng.random() < 0.5) else "none"
        spec = {"id": f"{name}_{u:04d}", "suite": name, "scenario": sc,
                "classes": [classes[c] for c in cls],
                "cell_idx": [int(i) for i in cell_idx],
                "profile": prof, "missingness": miss,
                "stress": bool(rng.random() < 0.15),
                "seed": int(rng.integers(0, 2**31 - 1))}
        if cap_per_class:
            spec["lineages"] = len({hierarchy[classes[c]]["lineage"] for c in cls})
        specs.append(spec)
    return specs


def suites(cfg: dict, y: np.ndarray, classes: list[str], VA: np.ndarray, TE: np.ndarray) -> tuple[list, list]:
    """(calibration suite from the validation cells, evaluation suite from the test cells)."""
    s = cfg["suites"]
    if s["scenarios"] == "blood":
        return (sg.make_suite("calib", VA, y[VA], classes, s["n_uploads"], seed=s["calib_seed"]),
                sg.make_suite("eval", TE, y[TE], classes, s["n_uploads"], seed=s["eval_seed"]))
    h, p = cfg["hierarchy"], tuple(s["profiles"])
    return (make_suite("calib", VA, y[VA], classes, h, p, s["n_uploads"], s["calib_seed"]),
            make_suite("eval", TE, y[TE], classes, h, p, s["n_uploads"], s["eval_seed"]))
