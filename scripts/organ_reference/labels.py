"""The reference's classes: the atlas's labels, merged as the organ file
says, in NB1's order (class names sorted, class_idx their position).

The class rule (research/organ-references.md, "Classes") is checked, not
applied: the organ file lists its merges, and a class that still fails the
rule stops the build, so a merge is always a written decision. A class the
label audit found to be something else is dropped by name ("drop"): its cells
leave the reference, and each kept cell carries its atlas row.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import data


def build(cfg: dict, apply_drop: bool = True) -> tuple[pd.DataFrame, list[str]]:
    """(the label table in the atlas's row order, the class names). The table
    has row (the atlas row), cell, original label, class_name, class_idx,
    group, lineage, donor. apply_drop=False keeps the dropped classes (the
    label audit looks at every annotated cell)."""
    label, donor = cfg["label_column"], cfg["donor_column"]
    obs = data.read_obs(data.resolve(cfg["rna"]), [label, donor])
    merge = cfg.get("merge", {})
    unknown = sorted(set(merge) - set(obs[label]))
    if unknown:
        raise SystemExit(f"{cfg['organ']}: merges name labels the atlas does not have: {unknown}")
    table = pd.DataFrame({"row": np.arange(len(obs)), "cell": obs["cell"], "original": obs[label], "donor": obs[donor]})
    table["class_name"] = table["original"].map(lambda c: merge.get(c, c))
    drop = cfg.get("drop", [])
    if set(drop) - set(table["class_name"]):
        raise SystemExit(f"{cfg['organ']}: drops name classes it does not have: {sorted(set(drop) - set(table['class_name']))}")
    if apply_drop:
        table = table[~table["class_name"].isin(drop)].reset_index(drop=True)
    hierarchy = cfg["hierarchy"] if apply_drop else {**cfg["hierarchy"], **cfg.get("dropped_hierarchy", {})}
    names = sorted(table["class_name"].unique())
    if sorted(hierarchy) != names:
        raise SystemExit(f"{cfg['organ']}: the hierarchy's classes are not the merged labels: "
                         f"missing {sorted(set(names) - set(hierarchy))}, extra {sorted(set(hierarchy) - set(names))}")
    table["class_idx"] = table["class_name"].map({c: i for i, c in enumerate(names)}).astype(np.int64)
    table["group"] = table["class_name"].map(lambda c: hierarchy[c]["group"])
    table["lineage"] = table["class_name"].map(lambda c: hierarchy[c]["lineage"])
    rule = cfg.get("class_rule")
    if rule:
        failing = check_rule(table[~table["class_name"].isin(drop)], rule)  # the kept classes
        if failing:
            raise SystemExit(f"{cfg['organ']}: classes failing the class rule {rule}: {failing}")
    return table, names


def check_rule(table: pd.DataFrame, rule: dict) -> dict:
    """Classes below the rule: too few cells, or too few donors with enough cells."""
    counts = pd.crosstab(table["class_name"], table["donor"])
    out = {}
    for c, row in counts.iterrows():
        donors = int((row >= rule["min_cells_per_donor"]).sum())
        if row.sum() < rule["min_cells"] or donors < rule["min_donors"]:
            out[c] = {"cells": int(row.sum()), "donors_with_enough": donors}
    return out


def by_donor(table: pd.DataFrame) -> pd.DataFrame:
    return pd.crosstab(table["class_name"], table["donor"], margins=True, margins_name="all")
