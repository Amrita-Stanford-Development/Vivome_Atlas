"""VivOME T1 simulation bench helpers, shared by NB1, NB2 and NB3.

Copied from the project Drive (Data/Results/Tier1_v31/NB1/sim_generator.py,
sha256 c1819784459abd8b105b6176565bbee5a3ff6206c48bc15a8b3402ba7db30fc7) on
2026-10-15, with one amendment, marked below: the scope2_like scenario's
macrophage and monocyte shares follow SCoPE2's corrected labels
(research/benchmark/bugs-and-fixes.md, entry 8). Every suite built before this
copy used the Drive original; this copy is for suites built from now on.

RNA only. Nothing in this module reads a proteomics label. Uploads are specified
by JSON serialisable specs (cell indices plus mask settings) and materialised on
demand, so suites are reproducible without storing any expression data twice.
"""
import numpy as np
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors

SMOOTH_K, SMOOTH_ALPHA, SMOOTH_PCA, SMOOTH_SEED = 15, 0.60, 50, 0

LINEAGE_KEYS = {
    "myeloid": ("monocyte", "macrophage", "neutrophil", "basophil", "eosinophil",
                "granulocyte", "dendritic", "myeloid", "mast", "megakaryocyte"),
    "lymphoid": ("t cell", "b cell", "nk", "natural killer", "plasma", "lymph",
                 "thymus", "regulatory t"),
    "erythroid": ("erythro",),
    "progenitor": ("progenitor", "precursor", "stem", "hematopoietic"),
}

def lineage_of(name):
    lc = name.lower()
    return next((k for k, keys in LINEAGE_KEYS.items() if any(x in lc for x in keys)), "other")


# ---------------------------------------------------------------- smoothing
def fuzzy_smooth(shared, full, k=SMOOTH_K, alpha=SMOOTH_ALPHA, n_pca=SMOOTH_PCA,
                 seed=SMOOTH_SEED, chunk=256):
    """Identical math to service/pipeline/smoothing.py after the alpha and graph
    fix: PCA(50) of the query's own features, L2 normalised, cosine kNN, Gaussian
    kernel with per cell bandwidth, (1 - alpha) * original + alpha * neighbours."""
    n = full.shape[0]
    if n < 3:
        return shared.astype(np.float32).copy()
    k = int(min(k, max(2, n - 1)))
    comp = int(min(n_pca, full.shape[1], max(2, n - 1)))
    P = PCA(n_components=comp, random_state=seed).fit_transform(np.asarray(full, dtype=np.float32))
    P /= (np.linalg.norm(P, axis=1, keepdims=True) + 1e-8)
    dist, idx = NearestNeighbors(n_neighbors=k + 1, metric="cosine").fit(P).kneighbors(P)
    idx, dist = idx[:, 1:], dist[:, 1:]
    w = np.exp(-(dist ** 2) / (dist[:, -1:] ** 2 + 1e-8))
    w = (w / (w.sum(1, keepdims=True) + 1e-8)).astype(np.float32)
    out = np.empty_like(shared, dtype=np.float32)
    for i in range(0, n, chunk):
        sl = slice(i, min(i + chunk, n))
        nb = np.einsum("ijk,ij->ik", shared[idx[sl]], w[sl], optimize=True)
        out[sl] = (1 - alpha) * shared[sl] + alpha * nb
    return out


# ---------------------------------------------------------- preprocessing
def canonical_preprocess(raw, gene_set, convention="notebook", smooth=True,
                         zscore="per_upload", graph_input="zscored",
                         global_mu=None, global_sd=None):
    """raw: (n, G) in the dataset's own units, NaN = not measured for that cell.
    gene_set: (G,) bool, the genes this dataset measures at all.

    convention="notebook": missing values median filled per gene within the upload,
        z scored per gene over the upload's cells (ddof 0), mask 1 for every gene in
        the gene set. This is how every measured v3 number was produced.
    convention="service": z scored with nanmean / nanstd, missing set to 0, mask
        per cell (1 only where that cell observed the gene). The service's current
        alignment.py behaviour.
    zscore="global" reproduces v3's RNA validation (whole reference statistics);
        it cannot be used for protein, it exists only for the composition experiment.
    graph_input="raw" reproduces pipeline.py's current smoothing input (raw values,
        NaN set to 0) instead of the z scored matrix.
    Genes outside gene_set are 0 with mask 0 under every option.
    """
    n, G = raw.shape
    cols = np.where(gene_set)[0]
    sub = raw[:, cols].astype(np.float32)
    obs = ~np.isnan(sub)

    if zscore == "global":
        z = (np.where(obs, sub, global_mu[cols]) - global_mu[cols]) / (global_sd[cols] + 1e-8)
        m = np.ones_like(sub) if convention == "notebook" else obs.astype(np.float32)
    elif convention == "notebook":
        med = np.nanmedian(np.where(obs, sub, np.nan), axis=0)
        med = np.where(np.isfinite(med), med, 0.0)
        filled = np.where(obs, sub, med[None, :])
        z = (filled - filled.mean(0)) / (filled.std(0) + 1e-8)
        m = np.ones_like(sub)
    elif convention == "service":
        mu = np.nanmean(np.where(obs, sub, np.nan), axis=0)
        sd = np.nanstd(np.where(obs, sub, np.nan), axis=0)
        z = (sub - mu) / np.clip(sd, 1e-8, None)
        z = np.nan_to_num(z, nan=0.0)
        m = obs.astype(np.float32)
    else:
        raise ValueError(convention)
    z = z.astype(np.float32)

    if smooth:
        g_in = z if graph_input == "zscored" else np.nan_to_num(sub, nan=0.0)
        z = fuzzy_smooth(z, g_in)

    X = np.zeros((n, G), np.float32); M = np.zeros((n, G), np.float32)
    X[:, cols] = z; M[:, cols] = m
    return X, M


# ----------------------------------------------------------- missingness
def random_gene_set(G, coverage, rng):
    gs = np.zeros(G, bool)
    gs[rng.choice(G, int(round(coverage * G)), replace=False)] = True
    return gs

def sample_missingness(n, gene_set, det_prob, cell_fracs, rng):
    """Per cell dropout inside the gene set, following each gene's real detection
    probability, scaled so each cell's observed fraction follows the real
    distribution of per cell observed fractions."""
    cols = np.where(gene_set)[0]
    p = np.clip(np.nan_to_num(det_prob[cols], nan=np.nanmedian(det_prob[cols])), 1e-3, 1.0)
    f = rng.choice(np.asarray(cell_fracs), size=n, replace=True)
    P = np.clip(p[None, :] * (f / p.mean())[:, None], 0.0, 1.0)
    miss = np.zeros((n, gene_set.size), bool)
    miss[:, cols] = rng.random((n, len(cols))) >= P
    return miss

def apply_stress(raw, gene_set, rng, scale_sigma=0.5, noise_frac=0.3):
    """A rough, clearly labelled PROXY for modality shift: gene wise rescaling plus
    noise. Not protein. Used only to check that methods degrade gracefully."""
    cols = np.where(gene_set)[0]
    out = raw.copy()
    s = rng.lognormal(0.0, scale_sigma, size=len(cols)).astype(np.float32)
    sd = np.nanstd(raw[:, cols], axis=0) + 1e-6
    out[:, cols] = raw[:, cols] * s + rng.normal(0, 1, raw[:, cols].shape).astype(np.float32) * noise_frac * sd
    return out


# -------------------------------------------------------- specs and suites
SIZES = (150, 400, 1000, 2000)
PROFILE_CHOICES = ("scope2", "pbmc240", "fulcher", "random_0.15", "random_0.25", "random_0.35")

def _scenario_classes(scenario, eligible, classes, rng):
    lin = {c: lineage_of(classes[c]) for c in eligible}
    if scenario.startswith("random_"):
        k = min(int(scenario.split("_")[1]), len(eligible))
        return sorted(rng.choice(eligible, k, replace=False).tolist())
    if scenario == "myeloid":
        pool = [c for c in eligible if lin[c] == "myeloid"]
        return sorted(rng.choice(pool, min(len(pool), rng.integers(2, 5)), replace=False).tolist())
    if scenario == "lymphoid":
        pool = [c for c in eligible if lin[c] == "lymphoid"]
        return sorted(rng.choice(pool, min(len(pool), rng.integers(2, 5)), replace=False).tolist())
    if scenario == "pbmc_like":
        want = ("cd4", "cd8", "natural killer", "b cell", "monocyte")
        pool = [c for c in eligible if any(w in classes[c].lower() for w in want)]
        return sorted(pool)
    if scenario == "scope2_like":
        return sorted([classes.index("macrophage"), classes.index("monocyte")])
    raise ValueError(scenario)

def make_suite(name, pool_idx, pool_y, classes, n_uploads, seed, min_cells=20):
    """pool_idx: global row indices available to this suite. pool_y: their labels."""
    rng = np.random.default_rng(seed)
    by_class = {c: pool_idx[pool_y == c] for c in np.unique(pool_y)}
    eligible = np.array([c for c, v in by_class.items() if len(v) >= min_cells])
    scen = (["random_1", "random_2", "random_3", "random_5", "random_8"] * 2 +
            ["myeloid", "lymphoid", "pbmc_like", "scope2_like"])
    specs = []
    for u in range(n_uploads):
        sc = scen[u % len(scen)]
        cls = _scenario_classes(sc, eligible, classes, rng)
        if sc == "scope2_like":
            mac, mon = classes.index("macrophage"), classes.index("monocyte")
            # Amended 2026-10-15: SCoPE2's corrected labels, 1,096 macrophages and 394
            # monocytes; the original had the swapped labels' 394:1096.
            props = {mac: 1096 / 1490, mon: 394 / 1490}
            props = np.array([props[c] for c in cls])
        else:
            props = rng.dirichlet(np.ones(len(cls)))
        n_total = int(rng.choice(SIZES))
        want = np.maximum(5, np.round(props * n_total)).astype(int)
        avail = np.array([len(by_class[c]) for c in cls])
        scale = min(1.0, float(np.min(avail / want)))
        take = np.maximum(3, np.floor(want * scale)).astype(int)
        cell_idx = np.concatenate([rng.choice(by_class[c], min(t, len(by_class[c])), replace=False)
                                   for c, t in zip(cls, take)])
        prof = str(rng.choice(PROFILE_CHOICES))
        miss = "per_cell" if (not prof.startswith("random") and rng.random() < 0.5) else "none"
        specs.append({"id": f"{name}_{u:04d}", "suite": name, "scenario": sc,
                      "classes": [classes[c] for c in cls],
                      "cell_idx": [int(i) for i in cell_idx],
                      "profile": prof, "missingness": miss,
                      "stress": bool(rng.random() < 0.15),
                      "seed": int(rng.integers(0, 2**31 - 1))})
    return specs

def materialize(spec, get_raw, profiles, G, convention="notebook", smooth=True,
                graph_input="zscored"):
    """get_raw(global_idx) -> (n, G) float32 log normalised RNA. profiles: dict
    loaded from mask_profiles.npz. Returns X, M, the realised gene set."""
    rng = np.random.default_rng(spec["seed"])
    raw = get_raw(np.asarray(spec["cell_idx"])).astype(np.float32).copy()
    prof = spec["profile"]
    if prof.startswith("random_"):
        gs = random_gene_set(G, float(prof.split("_")[1]), rng)
        det, fracs = np.where(gs, 1.0, np.nan), np.array([1.0])
    else:
        gs = profiles[f"gene_set_{prof}"].astype(bool)
        det, fracs = profiles[f"det_prob_{prof}"], profiles[f"cell_frac_{prof}"]
    raw[:, ~gs] = np.nan
    if spec["stress"]:
        raw = apply_stress(raw, gs, rng)
    if spec["missingness"] == "per_cell":
        raw[sample_missingness(len(raw), gs, det, fracs, rng)] = np.nan
    X, M = canonical_preprocess(raw, gs, convention=convention, smooth=smooth,
                                graph_input=graph_input)
    return X, M, gs
