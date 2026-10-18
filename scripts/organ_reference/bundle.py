"""An organ reference's files, in one directory, and their loading.

The layout follows the served blood model (v4.1 on v3.1's answers), every
file in one place:

  reference_metadata.csv      cell, class_idx, class_name, lineage
  feature_space_genes.csv     the encoder's gene order
  gene_id_map.tsv             the gene space's identifier map (gene_ids.py)
  answers_spec.json           the answers: temperatures, conformal sets,
                              abstention, hierarchy (nb2_spec_v31.json's layout)
  spec.json                   the best guess (spec_v41.json's layout and
                              settings), naming the organ
  class_balanced_stats.npz, class_means_cb.npy
  members/                    each member's checkpoint, reference latents,
                              centroids and class-balanced centroids
  reference_properties.npy, property_names.json   only where validated (blood)
  MANIFEST.json               every file's sha256

load() builds the service's own bundle objects (ensemble.V31Bundle under
fusion.V4Bundle) from such a directory, so research code runs an organ's
uploads through the served pipeline unchanged. The service resolves upload
identifiers with one map (service/pipeline/gene_ids.py), so a run on an organ
goes inside gene_map(directory), which hands the resolver the organ's map.
The service learns to load organ directories, maps included, in Stage 3
(research/organ-references.md).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import re
import shutil
from datetime import date
from pathlib import Path
from unittest import mock

import numpy as np

from service import config
from service.pipeline import coordinates, encoder, ensemble, fusion, gene_ids, reference

from . import data

REPO = data.REPO
SERVED_ANSWERS = REPO / "service" / "model" / "v3_1" / "nb2_spec_v31.json"
SERVED_SPEC = REPO / "service" / "model" / "v4_1" / "spec_v41.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed(name: str) -> str:
    return re.search(r"seed(\d+)", name).group(1)


def write_manifest(directory: Path, source: str) -> None:
    files = sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*")
                   if p.is_file() and p.name != "MANIFEST.json")
    data.save_json(directory / "MANIFEST.json", {"source": source, "files": {
        rel: {"sha256": sha256(directory / rel), "bytes": (directory / rel).stat().st_size} for rel in files}})


def verify_manifest(directory: Path) -> None:
    manifest = json.loads((directory / "MANIFEST.json").read_text(encoding="utf-8"))
    for rel, entry in manifest["files"].items():
        path = directory / rel
        if not path.exists() or sha256(path) != entry["sha256"]:
            raise reference.PendingArtifactError(f"{path} is missing or does not match {directory / 'MANIFEST.json'}")


def answers_spec(class_order: list[str], hierarchy: dict, cal: dict, cfg: dict, members: list[str], source: str) -> dict:
    """nb2_spec_v31.json's layout with the organ's own values."""
    spec = json.loads(SERVED_ANSWERS.read_text(encoding="utf-8"))
    spec["created"] = str(date.today())
    spec["source"] = source
    spec["encoder"]["members"] = members
    spec["encoder"]["family"] = "V2 (NB1d's recipe and architecture), trained on this organ's reference"
    spec["assignment"]["temperature"] = cal["temperature"]
    spec["conformal"]["alpha"] = cfg["calibration"]["alpha"]
    spec["conformal"]["qhat_by_class"] = cal["qhat_by_class"]
    spec["conformal"]["marginal_qhat"] = cal["marginal_qhat"]
    spec["conformal"]["calibrated_on"] = "labelled RNA simulated uploads (the organ's calibration suite, validation split cells)"
    spec["ood"]["threshold"] = cal["ood_threshold"]
    spec["hierarchy"] = hierarchy
    spec["class_order"] = class_order
    spec.pop("caveats", None)
    return spec


def best_guess_spec(answers: dict, organ: str, label: str, n_cells: int, rna: str, evaluation: dict) -> dict:
    """spec_v41.json's layout and fusion settings, unchanged, on the organ's members."""
    spec = json.loads(SERVED_SPEC.read_text(encoding="utf-8"))
    spec["created"] = str(date.today())
    spec["source"] = "scripts/build_organ_reference.py (v4.1's best-guess rule and settings, untuned)"
    spec["organ"] = organ
    spec["reference_version"] = label
    spec.pop("based_on", None)
    spec["encoder"] = {"members": answers["encoder"]["members"], "files": "members/ (this directory's MANIFEST)"}
    spec["reference"] = {"statistics": "class_balanced", "rna": rna, "n_cells": n_cells,
                         "ood_and_coordinates": "this reference's own latents"}
    spec["answers"] = {"from": organ, "spec": "answers_spec.json",
                       "what": "conformal sets, abstention, answer levels and coordinates from this organ's members"}
    spec["best_guess"]["temperature"] = answers["assignment"]["temperature"]
    spec["evaluation"] = evaluation
    spec["hierarchy"] = answers["hierarchy"]
    spec["class_order"] = answers["class_order"]
    return spec


def write(work: Path, target: Path, cfg: dict, label: str, evaluation: dict, checkpoints: dict) -> None:
    """The organ's bundle from its build's work folder; checkpoints maps each
    member to the file the calibration used."""
    if target.exists():
        shutil.rmtree(target)
    (target / "members").mkdir(parents=True)
    import pandas as pd
    table = pd.read_csv(work / "labels.csv.gz", keep_default_na=False)
    table[["cell", "class_idx", "class_name", "lineage"]].to_csv(target / "reference_metadata.csv", index=False, lineterminator="\n")
    shutil.copyfile(work / "feature_space_genes.csv", target / "feature_space_genes.csv")
    shutil.copyfile(work / "gene_id_map.tsv", target / "gene_id_map.tsv")
    classes = json.loads((work / "classes.json").read_text(encoding="utf-8"))
    cal = json.loads((work / "calibration.json").read_text(encoding="utf-8"))
    members = sorted(cal["temperature"])
    source = f"scripts/build_organ_reference.py on scripts/organs/{cfg['organ']}.json"
    answers = answers_spec(classes["class_order"], classes["hierarchy"], cal, cfg, members, source)
    data.save_json(target / "answers_spec.json", answers)
    rna = data.resolve(cfg["rna"]).name
    data.save_json(target / "spec.json", best_guess_spec(answers, cfg["organ"], label, len(table), rna, evaluation))
    shutil.copyfile(work / "class_balanced_stats.npz", target / "class_balanced_stats.npz")
    shutil.copyfile(work / "class_means_cb.npy", target / "class_means_cb.npy")
    for name in members:
        k = _seed(name)
        if sha256(checkpoints[name]) != cal["members"][name]:
            raise SystemExit(f"{name} is not the checkpoint the calibration used")
        shutil.copyfile(checkpoints[name], target / "members" / name)
        for suffix in ("reference_latent_f16.npy", "centroids.npy", "centroids_cb.npy"):
            shutil.copyfile(work / "members" / f"V2_seed{k}_{suffix}", target / "members" / f"V2_seed{k}_{suffix}")
    write_manifest(target, source)


def assemble_served_blood(target: Path) -> None:
    """Blood's served v4.1 files in this layout (acceptance tier 4)."""
    if target.exists():
        shutil.rmtree(target)
    (target / "members").mkdir(parents=True)
    runtime, v31, v4 = config.MODEL_DIR / "runtime", config.V31_DIR, config.V4_DIR
    for name in ("reference_metadata.csv", "feature_space_genes.csv", "reference_properties.npy", "property_names.json"):
        shutil.copyfile(runtime / name, target / name)
    shutil.copyfile(runtime / "gene_id_map_v1.tsv", target / "gene_id_map.tsv")
    shutil.copyfile(SERVED_ANSWERS, target / "answers_spec.json")
    shutil.copyfile(SERVED_SPEC, target / "spec.json")
    for name in ("class_balanced_stats.npz", "class_means_cb.npy"):
        shutil.copyfile(v4 / name, target / name)
    answers = json.loads(SERVED_ANSWERS.read_text(encoding="utf-8"))
    for name in answers["encoder"]["members"]:
        k = _seed(name)
        shutil.copyfile(v31 / "members" / name, target / "members" / name)
        for suffix in ("reference_latent_f16.npy", "centroids.npy"):
            shutil.copyfile(v31 / "members" / f"V2_seed{k}_{suffix}", target / "members" / f"V2_seed{k}_{suffix}")
        shutil.copyfile(v4 / "members" / f"V2_seed{k}_centroids_cb.npy", target / "members" / f"V2_seed{k}_centroids_cb.npy")
    write_manifest(target, "blood's served v4.1 files (service/model/v3_1, v4, v4_1, runtime), assembled for the loader check")


@contextlib.contextmanager
def gene_map(directory: Path):
    """The service's identifier resolver reads this organ's map inside the block."""
    organ_map = gene_ids.load_gene_id_map(directory / "gene_id_map.tsv")
    with mock.patch.object(gene_ids, "load_gene_id_map", lambda path=None: organ_map):
        yield organ_map


def load(directory: Path) -> "fusion.V4Bundle":
    """The service's bundle objects for an organ directory (module docstring)."""
    verify_manifest(directory)
    answers_spec_ = json.loads((directory / "answers_spec.json").read_text(encoding="utf-8"))
    spec = json.loads((directory / "spec.json").read_text(encoding="utf-8"))
    metadata = reference.load_reference_metadata(directory / "reference_metadata.csv")
    class_names = [c.class_name for c in metadata.classes]
    ensemble.validate_spec(answers_spec_, class_names)
    if spec["class_order"] != class_names or spec["encoder"]["members"] != answers_spec_["encoder"]["members"]:
        raise ValueError(f"{directory / 'spec.json'} does not match its answers")
    if spec["best_guess"]["rule"] != "fusion" or spec["label_space"]["method"] != "none":
        raise ValueError(f"{directory / 'spec.json'}: not v4.1's rule")
    members = []
    for name in answers_spec_["encoder"]["members"]:
        k = _seed(name)
        members.append(ensemble.Member(
            name=name, encoder_handle=encoder.load_encoder(directory / "members" / name),
            reference_latents=np.load(directory / "members" / f"V2_seed{k}_reference_latent_f16.npy").astype(np.float32),
            centroids=np.load(directory / "members" / f"V2_seed{k}_centroids.npy").astype(np.float32),
            temperature=float(answers_spec_["assignment"]["temperature"][name])))
    if (directory / "reference_properties.npy").exists():
        property_names, property_values = reference.load_reference_properties(
            directory / "reference_properties.npy", directory / "property_names.json")
    else:
        property_names, property_values = [], np.zeros((len(metadata.cell_ids), 0), np.float32)
    coordinate_member = answers_spec_["encoder"]["members"].index(config.V31_COORDINATE_MEMBER)
    answers = ensemble.V31Bundle(
        members=tuple(members), coordinate_member=coordinate_member,
        feature_genes=reference.load_feature_space_genes(directory / "feature_space_genes.csv"), metadata=metadata,
        class_names=class_names, hierarchy=answers_spec_["hierarchy"], ood_threshold=float(answers_spec_["ood"]["threshold"]),
        min_observed_genes=int(answers_spec_["preprocessing"]["min_observed_genes"]),
        pca=ensemble.sign_fixed(coordinates.fit_pca_3d(members[coordinate_member].reference_latents)),
        property_names=property_names, property_values=property_values, spec=answers_spec_,
        components=ensemble.build_components(answers_spec_))
    b = spec["best_guess"]
    cb_members = tuple(
        ensemble.Member(name=m.name, encoder_handle=m.encoder_handle, reference_latents=m.reference_latents,
                        centroids=np.load(directory / "members" / f"V2_seed{_seed(m.name)}_centroids_cb.npy").astype(np.float32),
                        temperature=float(b["temperature"][m.name]))
        for m in members)
    return fusion.V4Bundle(
        answers=answers, members=cb_members, class_means=np.load(directory / "class_means_cb.npy").astype(np.float32),
        fusion_weight=float(b["fusion_weight"]), correlation_temperature=float(b["correlation_temperature"]),
        smoothed_share=float(b["smoothed_share"]), agreement_threshold=float(b["agreement_threshold"]),
        spec=spec, components=fusion.build_components(answers_spec_, spec["version"]),
        gate_on_fusion_weight=float(b["gate_on_fusion_weight"]) if "gate_on_fusion_weight" in b else None)
