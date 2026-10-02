"""VivOME T1 NB1b core: composition robust standardization.

Encoder variants, training loop, query side preprocessing, and scoring. RNA only;
no proteomics label is read anywhere in this module. Imported by
T1_NB1b_Composition_Robust.ipynb, and reusable by NB2 and NB3.

Standardization variants (the `std` argument):
  global      v3 exactly: genes z scored with whole reference statistics.
              At query time a real upload can only be z scored within itself.
  batch_gene  genes z scored within each training batch, and training batches are
              drawn as narrow "mini uploads", so the encoder learns to handle the
              per upload z scoring every real query receives.
  row         each cell z scored across its own observed genes. Composition free
              by construction, but keeps any gene level offset between modalities.
  dual        two value channels, batch_gene and row, trained on mini uploads.
"""
import copy
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.decomposition import PCA
from sklearn.metrics import balanced_accuracy_score
from sklearn.neighbors import NearestNeighbors

N_CH = {"global": 1, "batch_gene": 1, "row": 1, "dual": 2}
QUERY_KIND = {"global": "gene", "batch_gene": "gene", "row": "row", "dual": "dual"}


# ----------------------------------------------------------------- model
def mlp(in_dim, hidden, dropout):
    layers, last = [], in_dim
    for h in hidden:
        layers += [nn.Linear(last, h, bias=False), nn.LayerNorm(h), nn.GELU()]
        if dropout:
            layers.append(nn.Dropout(dropout))
        last = h
    return nn.Sequential(*layers)


class ModulePoolEncV(nn.Module):
    """v3's module pooling encoder generalised to n value channels. With n_ch=1 the
    input layout is exactly v3's [x*m, m, pool, cov], so the shipped state dict
    loads unchanged. With n_ch=2: [x1*m, x2*m, m, pool1, pool2, cov]."""

    def __init__(self, G, hidden, dropout, latent_dim, assign, n_ch=1):
        super().__init__()
        self.register_buffer("A", assign)
        K = assign.shape[1]
        self.n_ch = n_ch
        self.body = mlp(n_ch * G + G + n_ch * K + K, hidden, dropout)
        self.proj = nn.Linear(hidden[-1], latent_dim, bias=False)
        self.norm = nn.LayerNorm(latent_dim)

    def forward(self, xs, m, return_hidden=False):
        if torch.is_tensor(xs):
            xs = [xs]
        assert len(xs) == self.n_ch
        den = m @ self.A
        pools = [((x * m) @ self.A) / (den + 1e-6) for x in xs]
        cov = den / (self.A.sum(0, keepdim=True) + 1e-6)
        h = self.body(torch.cat([x * m for x in xs] + [m] + pools + [cov], 1))
        z = F.normalize(self.norm(self.proj(h)), dim=-1)
        return (z, h) if return_hidden else z


class ClassifierHead(nn.Module):
    def __init__(self, latent_dim, n_classes):
        super().__init__()
        self.fc = nn.Linear(latent_dim, n_classes, bias=True)

    def forward(self, z):
        return self.fc(z)


class RefModelV(nn.Module):
    def __init__(self, G, n_classes, hidden, dropout, latent_dim, assign, n_ch=1):
        super().__init__()
        self.encoder = ModulePoolEncV(G, hidden, dropout, latent_dim, assign, n_ch)
        self.classifier = ClassifierHead(latent_dim, n_classes)

    def forward(self, xs, m):
        z = self.encoder(xs, m)
        return z, self.classifier(z)


# ------------------------------------------------------- standardization
def std_gene_batch(x, m, eps=1e-8):
    """Gene wise z score over the cells in this batch, observed entries only."""
    cnt = m.sum(0, keepdim=True).clamp(min=1.0)
    mu = (x * m).sum(0, keepdim=True) / cnt
    var = (((x - mu) * m) ** 2).sum(0, keepdim=True) / cnt
    return (x - mu) / (var.sqrt() + eps) * m


def std_row(x, m, eps=1e-8):
    """Cell wise z score across that cell's observed genes."""
    cnt = m.sum(1, keepdim=True).clamp(min=1.0)
    mu = (x * m).sum(1, keepdim=True) / cnt
    var = (((x - mu) * m) ** 2).sum(1, keepdim=True) / cnt
    return (x - mu) / (var.sqrt() + eps) * m


def standardize_t(x, m, std, mu=None, sd=None):
    if std == "global":
        return [((x - mu) / (sd + 1e-8)) * m]
    if std == "batch_gene":
        return [std_gene_batch(x, m)]
    if std == "row":
        return [std_row(x, m)]
    if std == "dual":
        return [std_gene_batch(x, m), std_row(x, m)]
    raise ValueError(std)


def standardize_reference(x, m, std, mu, sd):
    """The reference is one natural composition "upload", so gene wise statistics
    over it are the global statistics."""
    if std in ("global", "batch_gene"):
        return [((x - mu) / (sd + 1e-8)) * m]
    if std == "row":
        return [std_row(x, m)]
    if std == "dual":
        return [((x - mu) / (sd + 1e-8)) * m, std_row(x, m)]
    raise ValueError(std)


# ----------------------------------------------------------------- losses
def logit_adjusted_ce(logits, y, prior_log, tau=1.0):
    return F.cross_entropy(logits + tau * prior_log.unsqueeze(0), y)


def supcon_margin_loss(z, y, temp=0.10, margin=0.20):
    n = z.shape[0]
    if n < 4:
        return z.sum() * 0.0
    sim = (z @ z.T) / temp
    eye = torch.eye(n, dtype=torch.bool, device=z.device)
    pos = (y.unsqueeze(0) == y.unsqueeze(1)) & (~eye)
    if pos.sum() == 0:
        return z.sum() * 0.0
    sim = sim - (margin / temp) * pos.float()
    sim = sim.masked_fill(eye, -1e9)
    logprob = sim - torch.logsumexp(sim, dim=1, keepdim=True)
    ppos = (logprob * pos.float()).sum(1) / pos.float().sum(1).clamp(min=1)
    valid = pos.float().sum(1) > 0
    return -(ppos[valid]).mean()


def soft_hubness_penalty(z, temp=0.10):
    n = z.shape[0]
    if n < 8:
        return z.sum() * 0.0
    sim = (z @ z.T) / temp
    sim = sim.masked_fill(torch.eye(n, dtype=torch.bool, device=z.device), -1e9)
    occ = torch.softmax(sim, dim=1).sum(0)
    return ((occ - 1.0) ** 2).mean()


# ------------------------------------------------------------------ training
def sample_mini_upload(rng, TR, TR_by, elig, bs, p_natural):
    """One training batch drawn as an upload would be: 30 percent natural
    composition, otherwise 1, 2, 3, 5 or 8 classes with Dirichlet proportions."""
    if rng.random() < p_natural:
        return rng.choice(TR, bs, replace=False), "natural"
    k = int(rng.choice([1, 2, 3, 5, 8]))
    cls = rng.choice(elig, min(k, len(elig)), replace=False)
    p = rng.dirichlet(np.ones(len(cls)))
    n = np.maximum(1, np.round(p * bs)).astype(int)
    idx = np.concatenate([rng.choice(TR_by[c], nn_, replace=len(TR_by[c]) < nn_)
                          for c, nn_ in zip(cls, n)])
    return idx, "narrow"


def train_variant(XG, y_all, TR, VA, *, std, sampler, seed, assign, prior, mu_t, sd_t,
                  device, n_classes, hidden=(1024, 512), dropout=0.1, latent=128,
                  epochs=60, bs=512, lr=1e-3, wd=1e-4, patience=12, cov_range=(0.15, 0.6),
                  w_ce=1.0, w_supcon=0.5, w_hub=0.10, w_consist=1.0, temp=0.10, margin=0.20,
                  tau=1.0, p_natural=0.3, val_cov=0.35, log=print):
    """v3's recipe (logit adjusted CE, margin supervised contrastive, hubness penalty,
    two masked views with a consistency loss, uniform masking at 0.15 to 0.6
    coverage, AdamW, cosine schedule, early stopping on validation CE) with the
    standardization and the batch sampler as the only things that change.

    XG: (n_cells, G) tensor of log normalised RNA on `device` (float16 is fine).
    Training uses only TR; early stopping uses only VA."""
    t0 = time.time()
    torch.manual_seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)
    G = XG.shape[1]
    model = RefModelV(G, n_classes, hidden, dropout, latent, assign, N_CH[std]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    y_t = torch.from_numpy(np.asarray(y_all, dtype=np.int64)).to(device)
    prior_log = torch.log(torch.clamp(torch.as_tensor(prior, dtype=torch.float32), min=1e-12)).to(device)
    TR_by = {c: TR[y_all[TR] == c] for c in np.unique(y_all[TR])}
    elig = np.array([c for c, v in TR_by.items() if len(v) >= 20])
    n_batches = max(1, len(TR) // bs)

    gen = torch.Generator(device="cpu").manual_seed(seed + 1000)
    VA_t = torch.from_numpy(np.asarray(VA)).to(device)
    vm = (torch.rand(len(VA), G, generator=gen) < val_cov).float().to(device)
    xsv = standardize_t(XG[VA_t].float(), vm, std, mu_t, sd_t)

    best, best_state, bad, hist = np.inf, None, 0, []
    for ep in range(epochs):
        model.train()
        if sampler == "natural":
            perm = rng.permutation(TR)
            batches = [(perm[i:i + bs], "natural") for i in range(0, len(perm), bs)]
        else:
            batches = [sample_mini_upload(rng, TR, TR_by, elig, bs, p_natural)
                       for _ in range(n_batches)]
        for bi, kind in batches:
            bi_t = torch.from_numpy(bi).to(device)
            xb, yb = XG[bi_t].float(), y_t[bi_t]
            loss, zs = 0.0, []
            for _view in range(2):
                cov = rng.uniform(*cov_range)
                m = (torch.rand(len(bi), G, device=device) < cov).float()
                z, lg = model(standardize_t(xb, m, std, mu_t, sd_t), m)
                ce = (logit_adjusted_ce(lg, yb, prior_log, tau) if kind == "natural"
                      else F.cross_entropy(lg, yb))
                loss = loss + w_ce * ce + w_supcon * supcon_margin_loss(z, yb, temp, margin) \
                    + w_hub * soft_hubness_penalty(z, temp)
                zs.append(z)
            loss = loss + w_consist * (1 - F.cosine_similarity(zs[0], zs[1], dim=1)).mean()
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        sched.step()

        model.eval()
        with torch.no_grad():
            L = []
            for i in range(0, len(VA), 4096):
                sl = slice(i, i + 4096)
                _, lg = model([x[sl] for x in xsv], vm[sl])
                L.append(lg)
            L = torch.cat(L)
            vloss = F.cross_entropy(L, y_t[VA_t]).item()
            pv = L.argmax(1).cpu().numpy()
        rec = {"epoch": ep, "val_loss": vloss,
               "val_acc": float((pv == y_all[VA]).mean()),
               "val_bal": float(balanced_accuracy_score(y_all[VA], pv))}
        hist.append(rec)
        if ep % 10 == 0:
            log(f"    ep{ep:3d} vloss={vloss:.4f} acc={rec['val_acc']:.3f} bal={rec['val_bal']:.3f}"
                f"  ({time.time() - t0:.0f}s)")
        if vloss < best - 1e-5:
            best, bad = vloss, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            bad += 1
            if bad >= patience:
                log(f"    early stop at epoch {ep}")
                break
    model.load_state_dict(best_state)
    model.eval()
    return model, {"history": hist, "best_val_loss": best, "epochs_run": len(hist),
                   "seconds": time.time() - t0}


# ---------------------------------------------------------------- encoding
@torch.no_grad()
def encode_inputs(model, xs, M, device, bs=2048, logits=False, hidden=False):
    model.eval()
    Zs, Ls, Hs = [], [], []
    for i in range(0, len(M), bs):
        m = torch.from_numpy(np.ascontiguousarray(M[i:i + bs], dtype=np.float32)).to(device)
        xb = [torch.from_numpy(np.ascontiguousarray(x[i:i + bs], dtype=np.float32)).to(device) for x in xs]
        z, h = model.encoder(xb, m, return_hidden=True)
        Zs.append(z.cpu())
        if logits:
            Ls.append(model.classifier(z).cpu())
        if hidden:
            Hs.append(h.cpu())
    out = [torch.cat(Zs).numpy()]
    if logits:
        out.append(torch.cat(Ls).numpy())
    if hidden:
        out.append(torch.cat(Hs).numpy())
    return out[0] if len(out) == 1 else tuple(out)


@torch.no_grad()
def reference_embedding(model, XG, std, mu_t, sd_t, device, bs=4096):
    model.eval()
    Z = []
    for i in range(0, XG.shape[0], bs):
        x = XG[i:i + bs].float()
        m = torch.ones_like(x)
        Z.append(model.encoder(standardize_reference(x, m, std, mu_t, sd_t), m).cpu())
    return torch.cat(Z).numpy()


def centroids_from(Z, y, n_classes):
    cen = np.stack([Z[y == c].mean(0) if (y == c).any() else np.zeros(Z.shape[1], np.float32)
                    for c in range(n_classes)]).astype(np.float32)
    return cen / (np.linalg.norm(cen, axis=1, keepdims=True) + 1e-8)


# ------------------------------------------------------------ query side
def knn_graph(full, k=15, n_pca=50, seed=0):
    n = full.shape[0]
    k = int(min(k, max(2, n - 1)))
    comp = int(min(n_pca, full.shape[1], max(2, n - 1)))
    P = PCA(n_components=comp, random_state=seed).fit_transform(np.asarray(full, dtype=np.float32))
    P /= (np.linalg.norm(P, axis=1, keepdims=True) + 1e-8)
    dist, idx = NearestNeighbors(n_neighbors=k + 1, metric="cosine").fit(P).kneighbors(P)
    idx, dist = idx[:, 1:], dist[:, 1:]
    w = np.exp(-(dist ** 2) / (dist[:, -1:] ** 2 + 1e-8))
    return idx, (w / (w.sum(1, keepdims=True) + 1e-8)).astype(np.float32)


def apply_graph(vals, idx, w, alpha=0.60, chunk=256):
    out = np.empty_like(vals, dtype=np.float32)
    for i in range(0, len(vals), chunk):
        sl = slice(i, min(i + chunk, len(vals)))
        nb = np.einsum("ijk,ij->ik", vals[idx[sl]], w[sl], optimize=True)
        out[sl] = (1 - alpha) * vals[sl] + alpha * nb
    return out


def query_inputs(raw, gs, kind, convention="service", smooth=True, graph_input="zscored",
                 scale="log", graph_full=None):
    """raw: (n, G) log scale values, NaN where not measured for that cell.
    gs: (G,) bool gene set the dataset measures.
    kind: "gene" (per upload gene wise z), "row" (per cell z), "dual" (both).
    convention: "notebook" (median fill, mask 1 for the whole gene set) or
                "service" (no fill, mask 1 only where the cell observed the gene).
    graph_input: "zscored" builds the smoothing graph on the first standardized
                 channel; "raw" on raw values with NaN set to 0, as pipeline.py
                 currently does. graph_full, if given, is used instead (the
                 dataset's own full feature matrix, for real data).
    scale: "linear" simulates an upload arriving as linear intensities that are
           never log transformed. Only used by the A2 ablation.
    Returns (list of (n, G) value channels, (n, G) mask)."""
    n, G = raw.shape
    cols = np.where(gs)[0]
    sub = raw[:, cols].astype(np.float32)
    if scale == "linear":
        sub = (np.expm1(sub) * 1000.0).astype(np.float32)
    obs = ~np.isnan(sub)
    with np.errstate(all="ignore"):
        if convention == "notebook":
            med = np.nanmedian(sub, axis=0)
            med = np.where(np.isfinite(med), med, 0.0)
            base = np.where(obs, sub, med[None, :]).astype(np.float32)
            mcol = np.ones_like(base)
        elif convention == "service":
            base = sub
            mcol = obs.astype(np.float32)
        else:
            raise ValueError(convention)

        chans = []
        if kind in ("gene", "dual"):
            if convention == "notebook":
                z = (base - base.mean(0)) / (base.std(0) + 1e-8)
            else:
                mu, sd = np.nanmean(base, 0), np.nanstd(base, 0)
                z = np.nan_to_num((base - mu) / np.clip(sd, 1e-8, None), nan=0.0)
            chans.append(z.astype(np.float32))
        if kind in ("row", "dual"):
            rmu = np.nanmean(base, 1, keepdims=True)
            rsd = np.nanstd(base, 1, keepdims=True)
            chans.append(np.nan_to_num((base - rmu) / (rsd + 1e-8), nan=0.0).astype(np.float32))

    if smooth and n >= 3:
        if graph_full is not None:
            g_in = graph_full
        elif graph_input == "zscored":
            g_in = chans[0]
        else:
            g_in = np.nan_to_num(sub, nan=0.0)
        idx, w = knn_graph(g_in)
        chans = [apply_graph(c, idx, w) for c in chans]

    xs = []
    for c in chans:
        X = np.zeros((n, G), np.float32)
        X[:, cols] = c
        xs.append(X)
    M = np.zeros((n, G), np.float32)
    M[:, cols] = mcol
    return xs, M


def raw_upload(spec, X_raw, profiles, G, sg):
    """First half of sim_generator.materialize: same rng consumption, so the realised
    gene set, stress and dropout are identical to NB1's uploads."""
    rng = np.random.default_rng(spec["seed"])
    raw = np.asarray(X_raw[np.asarray(spec["cell_idx"])], dtype=np.float32).copy()
    prof = spec["profile"]
    if prof.startswith("random_"):
        gs = sg.random_gene_set(G, float(prof.split("_")[1]), rng)
        det, fracs = np.where(gs, 1.0, np.nan), np.array([1.0])
    else:
        gs = profiles[f"gene_set_{prof}"].astype(bool)
        det, fracs = profiles[f"det_prob_{prof}"], profiles[f"cell_frac_{prof}"]
    raw[:, ~gs] = np.nan
    if spec["stress"]:
        raw = sg.apply_stress(raw, gs, rng)
    if spec["missingness"] == "per_cell":
        raw[sg.sample_missingness(len(raw), gs, det, fracs, rng)] = np.nan
    return raw, gs


def score(Z, L, y, present, cen):
    sim = Z @ cen.T
    pu = sim.argmax(1)
    pr = np.array(present)[sim[:, present].argmax(1)]
    out = {"acc_unres": 100 * float((pu == y).mean()),
           "bal_unres": 100 * float(balanced_accuracy_score(y, pu)),
           "bal_oracle": 100 * float(balanced_accuracy_score(y, pr)) if len(present) > 1 else np.nan,
           "in_support": 100 * float(np.isin(pu, present).mean())}
    if L is not None:
        out["bal_head"] = 100 * float(balanced_accuracy_score(y, L.argmax(1)))
    return out