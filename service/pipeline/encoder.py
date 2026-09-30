"""Stage 3 — the reference encoder (docs/service/pipeline-brief.md, "Stage 3").

The interface (`ReferenceEncoder.encode(values, mask) -> embedding`) is built
directly against the artifact contract in the implementation plan / task
brief: a state dict with "encoder." and "classifier." prefixed keys. It is
NOT built against the dev checkpoint's incidental shape. The loader below
strips an "encoder." prefix when present and always drops "classifier.*"
keys (label assignment here is unbalanced OT onto centroids, not the joint
model's own classifier head) — so it accepts both the dev checkpoint's bare
keys today and the production export's prefixed keys later, unchanged.

Every dimension (gene count, module count, hidden widths, latent dim) is
read from the checkpoint's own tensor shapes, never hardcoded — a
differently-sized production export loads without touching this file.

What is settled regardless of which variant won the five-seed test (all
still apply to the module-pooling winner):
  - masking during training is not optional (44.9% vs 62-72% balanced
    accuracy at 10% coverage) — the model expects a mask channel at
    inference too, always pass one.
  - do not silently zero missing entries without also passing the mask;
    that reproduces the collapse case above.
"""
from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from service import config


class ModulePoolingEncoder(nn.Module):
    """The "H module, uniform" architecture from decisive_summary.json:
    module pooling with an explicit present/absent mask channel, both at
    the raw gene level and at the module level.

    `A` (n_genes, n_modules) is a fixed hard gene->module assignment,
    shipped inside the checkpoint itself (row sums to 1: every gene belongs
    to exactly one module). Body input is
    concat([masked_values, mask, module_value, module_mask_fraction]),
    width 2*n_genes + 2*n_modules.

    LayerNorm, not BatchNorm: the checkpoint's norm layers carry only
    weight/bias, no running_mean/running_var, and a projection service must
    stay correct on single-cell batches, where BatchNorm statistics would
    be meaningless.
    """

    def __init__(self, n_genes: int, n_modules: int, hidden1: int, hidden2: int, latent_dim: int, dropout: float = 0.1):
        super().__init__()
        self.register_buffer("A", torch.zeros(n_genes, n_modules))
        in_dim = 2 * n_genes + 2 * n_modules
        self.body = nn.Sequential(
            nn.Linear(in_dim, hidden1, bias=False), nn.LayerNorm(hidden1), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(hidden1, hidden2, bias=False), nn.LayerNorm(hidden2), nn.GELU(), nn.Dropout(dropout),
        )
        self.proj = nn.Linear(hidden2, latent_dim, bias=False)
        self.norm = nn.LayerNorm(latent_dim)

    def forward(self, values: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        masked = values * mask
        module_gene_count = self.A.sum(0).clamp_min(1e-6)
        module_mask_sum = mask @ self.A
        module_value = (masked @ self.A) / module_mask_sum.clamp_min(1e-6)
        module_mask_frac = module_mask_sum / module_gene_count
        x = torch.cat([masked, mask, module_value, module_mask_frac], dim=-1)
        h = self.body(x)
        z = self.norm(self.proj(h))
        return F.normalize(z, dim=-1)


def _strip_prefixes(state_dict: dict) -> dict:
    """Contract keys are prefixed "encoder." and "classifier."; the encoder
    only needs the former, with the prefix removed. The dev checkpoint has
    neither prefix, so an absent "encoder." prefix means "use as-is"."""
    has_encoder_prefix = any(k.startswith("encoder.") for k in state_dict)
    if not has_encoder_prefix:
        return dict(state_dict)
    return {k[len("encoder."):]: v for k, v in state_dict.items() if k.startswith("encoder.")}


def _build_module_pooling_encoder(state_dict: dict) -> ModulePoolingEncoder:
    n_genes, n_modules = state_dict["A"].shape
    hidden1 = state_dict["body.0.weight"].shape[0]
    hidden2 = state_dict["body.4.weight"].shape[0]
    latent_dim = state_dict["proj.weight"].shape[0]
    model = ModulePoolingEncoder(n_genes, n_modules, hidden1, hidden2, latent_dim)
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    return model


# Architecture family -> builder. decisive_summary.json's winner_config.enc
# is "module" today; this is the only family implemented because it is the
# only one that won. A future architecture change updates this table, not
# the dispatch logic in load_encoder().
_ENCODER_FAMILIES = {
    "module": _build_module_pooling_encoder,
}


def _read_encoder_family(architecture_config_path: Path) -> str:
    with open(architecture_config_path, encoding="utf-8") as handle:
        config_json = json.load(handle)
    winner_config = config_json.get("winner_config")
    if winner_config and "enc" in winner_config:
        return winner_config["enc"]
    raise ValueError(
        f"{architecture_config_path} has no winner_config.enc field. "
        "If this is the production provenance.json rather than "
        "decisive_summary.json, extend _read_encoder_family to read its "
        "architecture field instead of guessing a default."
    )


def trace_encoder(model: ModulePoolingEncoder) -> torch.jit.ScriptModule:
    """TorchScript export (Track B, "Serving"). Tracing, not scripting, is
    safe here: `forward()` has no data-dependent control flow, only matmul,
    clamp_min, cat, LayerNorm, GELU, Dropout (a no-op in eval mode) and
    normalize -- so the traced graph is exact for any input sharing the
    same n_genes as the example used to trace it. Equivalence against the
    eager model this traces is pinned in service/tests/test_encoder.py
    (<1e-5 max abs diff on 1,000 cells, the Track B spec's tolerance).
    Traced with batch size 2, not 1, so a singleton batch dim never gets
    baked into the graph as a constant."""
    n_genes = model.A.shape[0]
    example_values = torch.zeros(2, n_genes)
    example_mask = torch.ones(2, n_genes)
    with torch.no_grad():
        return torch.jit.trace(model, (example_values, example_mask))


@dataclass(frozen=True)
class EncoderHandle:
    model: ModulePoolingEncoder
    traced_model: torch.jit.ScriptModule
    weights_path: Path
    is_dev_placeholder: bool

    def encode(self, values: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """values, mask: (n_cells, n_genes) in feature_space_genes.csv
        order. Returns (n_cells, latent_dim) float32, L2 normalised —
        matches the reference_embedding.npy / reference_centroids.npy
        contract exactly, so downstream stages never branch on whether
        they're holding a query or reference embedding.

        Runs through the traced (TorchScript) model, not the eager one —
        `model` stays around for introspection (`.A`, `.body`, `.proj`)."""
        with torch.no_grad():
            values_t = torch.as_tensor(values, dtype=torch.float32)
            mask_t = torch.as_tensor(mask, dtype=torch.float32)
            out = self.traced_model(values_t, mask_t)
        return out.numpy().astype(np.float32)


def load_encoder(
    weights_path: Path = config.ENCODER_WEIGHTS_PATH,
    architecture_config_path: Path = config.DECISIVE_SUMMARY_PATH,
) -> EncoderHandle:
    """The one function every pipeline entry point calls. Swapping in the
    production checkpoint later means passing a different weights_path (or
    changing config.ENCODER_WEIGHTS_PATH's default) — nothing else here
    changes."""
    is_dev_placeholder = Path(weights_path) == Path(config.DEV_CHECKPOINT_PATH)
    if is_dev_placeholder:
        warnings.warn(
            "Loading the DEVELOPMENT placeholder checkpoint "
            f"({weights_path}). This is one seed of a simplified training "
            "recipe used only to answer 'which architecture generalises "
            "best' — it is missing the class imbalance correction, the "
            "hubness penalty, the sink penalty, and query-time smoothing "
            "was never combined with it. Do not treat its output as a "
            "production projection.",
            stacklevel=2,
        )

    raw_state_dict = torch.load(weights_path, map_location="cpu", weights_only=False)
    state_dict = _strip_prefixes(raw_state_dict)

    family = _read_encoder_family(architecture_config_path)
    builder = _ENCODER_FAMILIES.get(family)
    if builder is None:
        raise ValueError(
            f"Unknown encoder family '{family}' in {architecture_config_path}. "
            f"Implemented families: {sorted(_ENCODER_FAMILIES)}."
        )
    model = builder(state_dict)
    traced_model = trace_encoder(model)
    return EncoderHandle(
        model=model, traced_model=traced_model,
        weights_path=Path(weights_path), is_dev_placeholder=is_dev_placeholder,
    )


MODEL_VERSION_LABEL_DEV = "development-placeholder (H_seed4, decisive-test recipe — not production)"
MODEL_VERSION_LABEL_PRODUCTION = "production"


def model_version_label(handle: EncoderHandle) -> str:
    """Anywhere the model version might surface to a user (API response,
    logs, docs) this is the string to use, so a dev-placeholder projection
    can never be mistaken for a production one downstream."""
    return MODEL_VERSION_LABEL_DEV if handle.is_dev_placeholder else MODEL_VERSION_LABEL_PRODUCTION
