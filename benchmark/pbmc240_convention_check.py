"""Measures the divergence between the SERVICE convention (per-cell/dataset
nan_to_num on raw values for Stage 2's smoothing graph, z-scoring only
inside align_to_feature_space -- service/pipeline/pipeline.py's actual,
unchanged code) and the NOTEBOOK convention (dataset-level median fill then
z-score, reused for both alignment and the smoothing graph) on a real
dataset that actually has missing values. The SCoPE2 export
(service/model/source/app_export/) has none, so it can't reveal this gap --
service/tests/test_e2e_real_export.py's ~0.9985 median cosine is as close
as that dataset can show. Does NOT change either convention -- measurement
only. See research/benchmark/known-limitations.md#the-full_query_values-convention-gap-service-vs-notebook.

Input: a minimal, disclosed gene-level reduction of the raw DIA-NN search
output (service/examples/pbmc240_proteins_raw.tsv) -- not the undocumented
PBMC_240cells_proteins.tsv intermediate the original notebook used (not
present in this repo). Simplifications: first gene name per semicolon-
separated multi-gene protein group; duplicate gene rows after that
collapsed by median (matches the notebook's own collapse_dup_cols intent).
This means absolute embedding values here are not validated ground truth --
only the RELATIVE divergence between the two conventions, run on the same
input, is the thing being measured.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from service.pipeline import alignment, smoothing, encoder, reference

REPO = Path(__file__).resolve().parents[1]

raw_df = pd.read_csv(REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv", sep="\t")
raw_df = raw_df.dropna(subset=["Genes"])
raw_df["gene"] = raw_df["Genes"].astype(str).str.split(";").str[0].str.upper()
sample_cols = raw_df.columns[6:-1].tolist()  # exclude the 6 metadata cols and the new 'gene' col

mat = raw_df[sample_cols].copy()
mat.index = raw_df["gene"].values
mat = mat.groupby(level=0).median()  # collapse duplicate gene rows

df = mat.T  # cells x genes
df.columns = df.columns.astype(str).str.upper()
print(f"reduced matrix: {df.shape[0]} cells x {df.shape[1]} genes")
n_nan = df.isna().sum().sum()
print(f"NaN: {n_nan} / {df.size} ({100 * n_nan / df.size:.2f}%)")

gene_names = df.columns.tolist()
cell_ids = df.index.astype(str).tolist()
raw_values = df.to_numpy(dtype=np.float32)

feature_genes = reference.load_feature_space_genes()

# --- SERVICE convention: exactly pipeline.py's Stage 1+2 ---
raw = alignment.RawMatrix(gene_names=gene_names, cell_ids=cell_ids, values=raw_values.T)
aligned_service = alignment.align_to_feature_space(raw, feature_genes)
full_query_service = np.nan_to_num(raw.values.T, nan=0.0)
smoothed_service = smoothing.fuzzy_smooth(aligned_service.values, full_query_service)

# --- NOTEBOOK convention: dataset-level median fill, then z-score, reused for both ---
clean = df.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
clean = clean.apply(lambda c: c.fillna(c.median()), axis=0).fillna(0.0)
dz = ((clean - clean.mean(axis=0)) / (clean.std(axis=0, ddof=0) + 1e-8)).to_numpy(dtype=np.float32)
raw_dz = alignment.RawMatrix(gene_names=gene_names, cell_ids=cell_ids, values=dz.T)
aligned_notebook = alignment.align_to_feature_space(raw_dz, feature_genes)
smoothed_notebook = smoothing.fuzzy_smooth(aligned_notebook.values, dz)

enc = encoder.load_encoder()
emb_service = enc.encode(smoothed_service, aligned_service.mask)
emb_notebook = enc.encode(smoothed_notebook, aligned_notebook.mask)

a = emb_service / np.clip(np.linalg.norm(emb_service, axis=1, keepdims=True), 1e-8, None)
b = emb_notebook / np.clip(np.linalg.norm(emb_notebook, axis=1, keepdims=True), 1e-8, None)
cos = np.sum(a * b, axis=1)
print(f"\nservice-convention vs notebook-convention embedding, per-cell cosine (same real NaN-containing input):")
print(f"  median: {np.median(cos):.4f}  5th pct: {np.percentile(cos, 5):.4f}  "
      f"mean: {cos.mean():.4f}  min: {cos.min():.4f}  max: {cos.max():.4f}")
print(f"  # cells < 0.99: {(cos < 0.99).sum()}/{len(cos)}   "
      f"# cells < 0.90: {(cos < 0.90).sum()}/{len(cos)}   # cells < 0.5: {(cos < 0.5).sum()}/{len(cos)}")
