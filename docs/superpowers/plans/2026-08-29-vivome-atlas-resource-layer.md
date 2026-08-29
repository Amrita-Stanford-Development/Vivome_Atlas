# VivOME Atlas Resource Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the static VivOME viewer into the resource described in Phase 5 of the Nature Communications plan — support map, alignment diagnostics, projection UI, standing benchmark, and versioning — built now against a manifest whose unmeasured fields are visibly pending, so the deep-learning pipeline fills numbers in later without touching any HTML.

**Architecture:** A single generated JSON file, `Atlas/atlas_manifest.json`, becomes the one source of truth for every number the web layer displays. A Python build script computes what the repository can honestly support today (per-class cell counts, cross-modal support status, 3-PC centroid cosine) and emits explicit `pending` records for everything that requires training runs (latent-space alignment, modality probe, transfer accuracy, benchmark rows). Shared ES modules under `js/` load and render that manifest through pure, unit-tested functions. When Phases 1–4 produce real numbers, only the manifest changes.

**Tech Stack:** Static HTML/CSS/JS (no build step, no bundler), Three.js r128 + PapaParse 5.4.1 from cdnjs (already in use), Python 3.11 standard library for the builder, `python3 -m unittest` and `node --test` for tests. No new runtime or dev dependencies.

**Spec:** `VivOME_NatComms_Implementation_Plan.md` — principally §9 (Phase 5, VivOME as a Resource), §12 (What Gets Cut), and the honesty requirements in §2 and §6.

## Global Constraints

- **No fabricated numbers.** Any metric not computed from data present in the repository must render as the literal string `Pending`. Never `0`, never blank, never an invented value. A metric is displayable only when its record has `"status": "measured"`.
- **Every measured number carries its basis.** Values computed from PC1–PC3 are labelled `3-PC projection`, never presented as latent-space alignment. The 128-d latent files do not exist in this repository.
- **No new dependencies.** No npm install, no pip install. Python standard library only; Node built-in test runner only. Browser libraries come from the existing cdnjs allowlist.
- **Static-serveable.** Everything must work under `python3 -m http.server 8000`. No server-side execution is assumed by any page shipped in this plan.
- **Preserve existing optimisations.** The `needsRender` demand-rendering flag, flat `raycastTargets` array, 150 ms resize debounce, offscreen background layers, and `animationPaused` modal guard are all load-bearing. Do not reintroduce per-frame work.
- **Design tokens** (existing, hardcoded — match them): primary `#008ECC`, dark `#0066A3`, light `#0099E6`, body text `#4B4B4B`, danger `#dc3545`, surface `#ffffff`, muted surface `#f0f0f0`.
- **Generated files are committed.** `Atlas/atlas_manifest.json` is checked in so the static site works without running the builder.

## Verified Ground Truth

These values were measured from the repository on 2026-08-29 and are used as test fixtures. Do not alter them without rerunning the builder.

| Fact | Value |
|---|---|
| RNA cells | 85,233 |
| PROT cells | 1,490 |
| RNA cell types | 22 (`class_idx` 0–21) |
| PROT cell types | 2 |
| Cross-modal classes | `monocyte` (idx 12), `macrophage` (idx 10) |
| RNA-only classes | 20 |
| monocyte 3-PC centroid cosine | 0.998634 |
| macrophage 3-PC centroid cosine | 0.997242 |
| monocyte counts | rna 9,602 / prot 1,096 |
| macrophage counts | rna 1,228 / prot 394 |

`Atlas/atlas_RNA_lat128-001-part1.csv` and `-part2.csv` are 135-byte Git LFS pointers to a 1.43 GB object that is **not** fetched. `git lfs` is not installed on this machine. Class names 2, 3, and 14 contain commas and are double-quoted in the CSVs — always parse with a real CSV reader, never `split(',')`.

---

## File Structure

```
package.json                     NEW  {"type":"module","private":true} — lets node --test load js/*.js as ESM. No deps.
tools/build_manifest.py          NEW  Reads Atlas/metadata_*.csv, writes Atlas/atlas_manifest.json.
tools/test_build_manifest.py     NEW  stdlib unittest for the builder.
js/manifest.js                   NEW  Manifest load/validate + pending-safe formatters. Pure, no DOM.
js/panels.js                     NEW  HTML-string builders for every panel and table. Pure, no DOM.
tests/manifest.test.js           NEW  node --test for js/manifest.js
tests/panels.test.js             NEW  node --test for js/panels.js
Atlas/atlas_manifest.json        GEN  Generated, committed.
atlas.html                       MOD  + support panel, + diagnostics panel, + LFS guard on RNA gene profile.
versions.html                    NEW  Model card and version history.
benchmark.html                   NEW  Standing benchmark comparison, pending state.
project.html                     NEW  Projection submission UI against a documented stub contract.
index.html                       MOD  Nav nodes for the new pages.
SUMMARY.md                       MOD  Document the resource layer.
```

`js/manifest.js` holds data concerns only; `js/panels.js` holds presentation only and depends on `manifest.js`. Both return values rather than touching the DOM, which is what makes them testable under Node with no browser.

---

## Task 1: Manifest Builder

**Files:**
- Create: `tools/build_manifest.py`
- Create: `tools/test_build_manifest.py`
- Create: `Atlas/atlas_manifest.json` (generated by running the script)

**Interfaces:**
- Consumes: `Atlas/metadata_RNA_lat128.csv`, `Atlas/metadata_PROT_lat128.csv`
- Produces: `build_manifest(rna_rows, prot_rows) -> dict`; `class_stats(rows) -> dict`; `cosine(a, b) -> float | None`; `pending(phase, note) -> dict`; `measured(value, basis) -> dict`. The JSON shape produced here is the contract every later task reads.

- [ ] **Step 1: Write the failing test**

Create `tools/test_build_manifest.py`:

```python
import unittest

from build_manifest import build_manifest, class_stats, cosine, measured, pending


def row(modality, class_idx, class_name, pc1, pc2, pc3):
    return {
        "latent_dim": "128",
        "modality": modality,
        "orig_index": "0",
        "class_idx": str(class_idx),
        "class_name": class_name,
        "PC1": str(pc1),
        "PC2": str(pc2),
        "PC3": str(pc3),
    }


class TestCosine(unittest.TestCase):
    def test_identical_vectors_are_one(self):
        self.assertAlmostEqual(cosine((1.0, 2.0, 3.0), (1.0, 2.0, 3.0)), 1.0, places=9)

    def test_opposite_vectors_are_minus_one(self):
        self.assertAlmostEqual(cosine((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)), -1.0, places=9)

    def test_zero_vector_returns_none(self):
        self.assertIsNone(cosine((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)))


class TestClassStats(unittest.TestCase):
    def test_counts_and_centroid(self):
        rows = [
            row("RNA", 12, "monocyte", 0.0, 0.0, 0.0),
            row("RNA", 12, "monocyte", 2.0, 4.0, 6.0),
        ]
        stats = class_stats(rows)
        self.assertEqual(stats[12]["count"], 2)
        self.assertEqual(stats[12]["name"], "monocyte")
        self.assertEqual(stats[12]["centroid"], (1.0, 2.0, 3.0))

    def test_quoted_comma_name_survives(self):
        rows = [row("RNA", 2, "cd4-positive, alpha-beta t cell", 1.0, 1.0, 1.0)]
        self.assertEqual(class_stats(rows)[2]["name"], "cd4-positive, alpha-beta t cell")


class TestPendingAndMeasured(unittest.TestCase):
    def test_pending_has_null_value(self):
        rec = pending("Phase 1", "needs latent export")
        self.assertIsNone(rec["value"])
        self.assertEqual(rec["status"], "pending")
        self.assertEqual(rec["phase"], "Phase 1")

    def test_measured_carries_basis(self):
        rec = measured(0.5, "3-PC projection")
        self.assertEqual(rec["value"], 0.5)
        self.assertEqual(rec["status"], "measured")
        self.assertEqual(rec["basis"], "3-PC projection")


class TestBuildManifest(unittest.TestCase):
    def setUp(self):
        self.rna = [
            row("RNA", 12, "monocyte", 1.0, 0.0, 0.0),
            row("RNA", 16, "neutrophil", 0.0, 1.0, 0.0),
        ]
        self.prot = [row("PROT", 12, "monocyte", 2.0, 0.0, 0.0)]
        self.manifest = build_manifest(self.rna, self.prot)

    def test_shared_class_is_cross_modal(self):
        mono = next(c for c in self.manifest["cell_types"] if c["class_idx"] == 12)
        self.assertEqual(mono["support"], "cross_modal")
        self.assertEqual(mono["rna_cells"], 1)
        self.assertEqual(mono["prot_cells"], 1)

    def test_rna_only_class_marked_and_has_zero_prot(self):
        neut = next(c for c in self.manifest["cell_types"] if c["class_idx"] == 16)
        self.assertEqual(neut["support"], "rna_only")
        self.assertEqual(neut["prot_cells"], 0)

    def test_collinear_centroids_give_cosine_one(self):
        mono = next(c for c in self.manifest["cell_types"] if c["class_idx"] == 12)
        self.assertEqual(mono["pca_centroid_cosine"]["status"], "measured")
        self.assertAlmostEqual(mono["pca_centroid_cosine"]["value"], 1.0, places=6)
        self.assertEqual(mono["pca_centroid_cosine"]["basis"], "3-PC projection")

    def test_rna_only_class_has_pending_cosine(self):
        neut = next(c for c in self.manifest["cell_types"] if c["class_idx"] == 16)
        self.assertEqual(neut["pca_centroid_cosine"]["status"], "pending")
        self.assertIsNone(neut["pca_centroid_cosine"]["value"])

    def test_latent_and_probe_metrics_are_always_pending(self):
        for cell in self.manifest["cell_types"]:
            self.assertIsNone(cell["latent_centroid_cosine"]["value"])
            self.assertIsNone(cell["modality_probe_accuracy"]["value"])
            self.assertIsNone(cell["transfer_accuracy"]["value"])

    def test_summary_counts(self):
        self.assertEqual(self.manifest["summary"]["cross_modal"], 1)
        self.assertEqual(self.manifest["summary"]["rna_only"], 1)
        self.assertEqual(self.manifest["summary"]["total"], 2)

    def test_benchmark_block_is_pending_with_no_rows(self):
        self.assertEqual(self.manifest["benchmark"]["status"], "pending")
        self.assertEqual(self.manifest["benchmark"]["rows"], [])

    def test_required_top_level_keys(self):
        for key in ("schema_version", "atlas_version", "generated", "model",
                    "modalities", "cell_types", "summary", "benchmark", "data_availability"):
            self.assertIn(key, self.manifest)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools && python3 -m unittest test_build_manifest -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'build_manifest'`

- [ ] **Step 3: Write the implementation**

Create `tools/build_manifest.py`:

```python
#!/usr/bin/env python3
"""Generate Atlas/atlas_manifest.json from the metadata CSVs.

Every number emitted here is computed from data present in this repository.
Metrics that require the training pipeline — latent-space alignment, the
modality probe, transfer accuracy, benchmark rows — are emitted as explicit
pending records so the web layer renders them as pending instead of
inventing a value.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ATLAS_DIR = REPO_ROOT / "Atlas"
OUTPUT_PATH = ATLAS_DIR / "atlas_manifest.json"

SCHEMA_VERSION = "1.0"
ATLAS_VERSION = "0.1.0"

BENCHMARK_METHODS = [
    "CrossModalNet (ours)",
    "Seurat bridge integration",
    "GLUE",
    "MaxFuse",
    "scArches",
    "Harmony (shared features)",
    "PCA + nearest neighbour (floor)",
]


def read_metadata(path: Path) -> list[dict]:
    """Read a metadata CSV. Uses csv.DictReader so quoted class names
    containing commas (class_idx 2, 3, 14) parse correctly."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def class_stats(rows: list[dict]) -> dict:
    """-> {class_idx: {"name": str, "count": int, "centroid": (x, y, z)}}"""
    acc = defaultdict(lambda: {"name": None, "n": 0, "sx": 0.0, "sy": 0.0, "sz": 0.0})
    for row in rows:
        entry = acc[int(row["class_idx"])]
        entry["name"] = row["class_name"]
        entry["n"] += 1
        entry["sx"] += float(row["PC1"])
        entry["sy"] += float(row["PC2"])
        entry["sz"] += float(row["PC3"])
    return {
        idx: {
            "name": e["name"],
            "count": e["n"],
            "centroid": (e["sx"] / e["n"], e["sy"] / e["n"], e["sz"] / e["n"]),
        }
        for idx, e in acc.items()
    }


def cosine(a, b):
    """Cosine similarity of two 3-vectors. None if either has zero norm."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return None
    return dot / (norm_a * norm_b)


def pending(phase: str, note: str) -> dict:
    return {"value": None, "status": "pending", "phase": phase, "note": note}


def measured(value, basis: str) -> dict:
    return {"value": value, "status": "measured", "basis": basis}


def build_manifest(rna_rows: list[dict], prot_rows: list[dict]) -> dict:
    rna = class_stats(rna_rows)
    prot = class_stats(prot_rows)

    cell_types = []
    for idx in sorted(set(rna) | set(prot)):
        r = rna.get(idx)
        p = prot.get(idx)
        if r and p:
            support = "cross_modal"
            cos = cosine(r["centroid"], p["centroid"])
            pca_cos = (
                measured(round(cos, 6), "3-PC projection")
                if cos is not None
                else pending("Phase 2", "Degenerate centroid; cosine undefined")
            )
        else:
            support = "rna_only" if r else "prot_only"
            pca_cos = pending("Phase 2", "No paired modality coverage for this class")

        cell_types.append({
            "class_idx": idx,
            "name": (r or p)["name"],
            "rna_cells": r["count"] if r else 0,
            "prot_cells": p["count"] if p else 0,
            "support": support,
            "pca_centroid_cosine": pca_cos,
            "latent_centroid_cosine": pending("Phase 1", "Requires 128-d latent coordinate export"),
            "modality_probe_accuracy": pending("Phase 4", "Requires linear modality probe run"),
            "transfer_accuracy": pending("Phase 1", "Requires multi-seed transfer evaluation"),
        })

    summary = {
        "total": len(cell_types),
        "cross_modal": sum(1 for c in cell_types if c["support"] == "cross_modal"),
        "rna_only": sum(1 for c in cell_types if c["support"] == "rna_only"),
        "prot_only": sum(1 for c in cell_types if c["support"] == "prot_only"),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "atlas_version": ATLAS_VERSION,
        "generated": date.today().isoformat(),
        "model": {
            "name": "CrossModalNet",
            "latent_dim": 128,
            "training_regime": "supervised",
            "seeds": pending("Phase 1", "Single run only; ten-seed statistics pending"),
            "notes": (
                "Coordinates shown in the viewer are a 3-component PCA projection of the "
                "128-d latent space. The latent coordinates themselves are not distributed "
                "with this build."
            ),
        },
        "modalities": {
            "rna": {
                "label": "RNA",
                "cells": len(rna_rows),
                "classes": len(rna),
                "source": "scRNA-seq",
            },
            "prot": {
                "label": "Protein",
                "cells": len(prot_rows),
                "classes": len(prot),
                "source": "SCoPE2 mass spectrometry",
            },
        },
        "cell_types": cell_types,
        "summary": summary,
        "benchmark": {
            "status": "pending",
            "phase": "Phase 4",
            "note": "No comparison against established methods has been run yet.",
            "methods": BENCHMARK_METHODS,
            "rows": [],
        },
        "data_availability": {
            "rna_expression": {
                "status": "lfs_not_fetched",
                "note": "Git LFS object (~1.43 GB) is not present in this checkout.",
                "remedy": "git lfs install && git lfs pull",
            },
            "prot_expression": {"status": "available", "note": "Atlas/atlas_PROT_lat128.csv"},
            "latent_coordinates": {
                "status": "not_distributed",
                "note": "Only the 3-component PCA projection ships with this build.",
            },
        },
    }


def main() -> None:
    manifest = build_manifest(
        read_metadata(ATLAS_DIR / "metadata_RNA_lat128.csv"),
        read_metadata(ATLAS_DIR / "metadata_PROT_lat128.csv"),
    )
    OUTPUT_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    s = manifest["summary"]
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {s['total']} cell types: {s['cross_modal']} cross-modal, {s['rna_only']} RNA-only")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools && python3 -m unittest test_build_manifest -v`
Expected: PASS, 15 tests

- [ ] **Step 5: Generate the manifest and check it against verified ground truth**

Run:
```bash
python3 tools/build_manifest.py
python3 -c "
import json
m = json.load(open('Atlas/atlas_manifest.json'))
s = m['summary']
assert s['total'] == 22, s
assert s['cross_modal'] == 2, s
assert s['rna_only'] == 20, s
assert m['modalities']['rna']['cells'] == 85233
assert m['modalities']['prot']['cells'] == 1490
by_idx = {c['class_idx']: c for c in m['cell_types']}
assert round(by_idx[12]['pca_centroid_cosine']['value'], 6) == 0.998634, by_idx[12]
assert round(by_idx[10]['pca_centroid_cosine']['value'], 6) == 0.997242, by_idx[10]
assert by_idx[2]['name'] == 'cd4-positive, alpha-beta t cell'
print('manifest matches verified ground truth')
"
```
Expected: `manifest matches verified ground truth`

- [ ] **Step 6: Commit**

```bash
git add tools/build_manifest.py tools/test_build_manifest.py Atlas/atlas_manifest.json
git commit -m "feat: generate atlas manifest with explicit pending metrics"
```

---

## Task 2: Shared Manifest Module

**Files:**
- Create: `package.json`
- Create: `js/manifest.js`
- Create: `tests/manifest.test.js`

**Interfaces:**
- Consumes: the JSON shape produced by Task 1.
- Produces: `loadManifest(url) -> Promise<manifest>`, `validateManifest(m) -> m` (throws on missing key), `formatMetric(metric, digits = 3) -> string`, `formatPercent(metric) -> string`, `metricBasis(metric) -> string`, `supportRows(manifest) -> array`, `isLfsPointer(text) -> boolean`, and the constant `PENDING_LABEL`. Tasks 3–8 import from here.

- [ ] **Step 1: Write the failing test**

Create `tests/manifest.test.js`:

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  PENDING_LABEL, validateManifest, formatMetric, formatPercent,
  metricBasis, supportRows, isLfsPointer,
} from '../js/manifest.js';

const measured = (v, basis) => ({ value: v, status: 'measured', basis });
const pending = (phase) => ({ value: null, status: 'pending', phase, note: 'n/a' });

function fixture() {
  return {
    schema_version: '1.0',
    atlas_version: '0.1.0',
    generated: '2026-08-29',
    model: { name: 'CrossModalNet', latent_dim: 128 },
    modalities: { rna: { cells: 85233 }, prot: { cells: 1490 } },
    cell_types: [
      { class_idx: 16, name: 'neutrophil', rna_cells: 32198, prot_cells: 0,
        support: 'rna_only', pca_centroid_cosine: pending('Phase 2') },
      { class_idx: 12, name: 'monocyte', rna_cells: 9602, prot_cells: 1096,
        support: 'cross_modal', pca_centroid_cosine: measured(0.998634, '3-PC projection') },
      { class_idx: 10, name: 'macrophage', rna_cells: 1228, prot_cells: 394,
        support: 'cross_modal', pca_centroid_cosine: measured(0.997242, '3-PC projection') },
    ],
    summary: { total: 3, cross_modal: 2, rna_only: 1, prot_only: 0 },
    benchmark: { status: 'pending', rows: [] },
    data_availability: {},
  };
}

test('validateManifest returns the manifest when complete', () => {
  const m = fixture();
  assert.equal(validateManifest(m), m);
});

test('validateManifest throws naming the missing key', () => {
  const m = fixture();
  delete m.cell_types;
  assert.throws(() => validateManifest(m), /cell_types/);
});

test('measured metric formats to fixed digits', () => {
  assert.equal(formatMetric(measured(0.998634, '3-PC projection')), '0.999');
  assert.equal(formatMetric(measured(0.998634, '3-PC projection'), 6), '0.998634');
});

test('pending metric never renders a number', () => {
  assert.equal(formatMetric(pending('Phase 1')), PENDING_LABEL);
});

test('missing or malformed metric renders as pending, not as zero', () => {
  assert.equal(formatMetric(undefined), PENDING_LABEL);
  assert.equal(formatMetric(null), PENDING_LABEL);
  assert.equal(formatMetric({ value: 0, status: 'pending' }), PENDING_LABEL);
  assert.equal(formatMetric({ value: null, status: 'measured' }), PENDING_LABEL);
});

test('a genuine zero measurement still renders', () => {
  assert.equal(formatMetric(measured(0, 'probe')), '0.000');
});

test('formatPercent renders one decimal with a percent sign', () => {
  assert.equal(formatPercent(measured(0.4228, 'accuracy')), '42.3%');
  assert.equal(formatPercent(pending('Phase 1')), PENDING_LABEL);
});

test('metricBasis gives basis when measured and phase when pending', () => {
  assert.equal(metricBasis(measured(1, '3-PC projection')), '3-PC projection');
  assert.equal(metricBasis(pending('Phase 4')), 'Phase 4');
  assert.equal(metricBasis(undefined), '');
});

test('supportRows puts cross-modal first, then descending RNA count', () => {
  const rows = supportRows(fixture());
  assert.deepEqual(rows.map(r => r.name), ['monocyte', 'macrophage', 'neutrophil']);
});

test('supportRows does not mutate the manifest order', () => {
  const m = fixture();
  supportRows(m);
  assert.equal(m.cell_types[0].name, 'neutrophil');
});

test('isLfsPointer detects a pointer file', () => {
  const ptr = 'version https://git-lfs.github.com/spec/v1\noid sha256:765299ae\nsize 1432231477\n';
  assert.equal(isLfsPointer(ptr), true);
});

test('isLfsPointer is false for real CSV content and non-strings', () => {
  assert.equal(isLfsPointer('latent_dim,modality,orig_index\n128,RNA,0\n'), false);
  assert.equal(isLfsPointer(''), false);
  assert.equal(isLfsPointer(null), false);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test`
Expected: FAIL — `Cannot find module .../js/manifest.js`

- [ ] **Step 3: Write the implementation**

Create `package.json` — this exists solely so Node treats `js/*.js` as ES modules. It declares no dependencies and no install step:

```json
{
  "name": "vivome-atlas",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "description": "Static web resource for the VivOME joint latent atlas.",
  "scripts": {
    "test": "node --test"
  }
}
```

Create `js/manifest.js`:

```javascript
// Loading and formatting for Atlas/atlas_manifest.json.
// Pure functions only — no DOM access — so this runs under `node --test`.

export const PENDING_LABEL = 'Pending';

const REQUIRED_KEYS = [
  'schema_version', 'atlas_version', 'generated', 'model',
  'modalities', 'cell_types', 'summary', 'benchmark', 'data_availability',
];

export function validateManifest(manifest) {
  if (!manifest || typeof manifest !== 'object') {
    throw new Error('Manifest is not an object');
  }
  for (const key of REQUIRED_KEYS) {
    if (!(key in manifest)) throw new Error(`Manifest missing required key: ${key}`);
  }
  return manifest;
}

export async function loadManifest(url = './Atlas/atlas_manifest.json') {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Manifest fetch failed: ${response.status} ${response.statusText}`);
  }
  return validateManifest(await response.json());
}

// A metric is displayable only when it is explicitly measured with a non-null
// value. Everything else — pending, absent, malformed — renders as Pending.
// This is the single guard that keeps unmeasured quantities off the page.
function isMeasured(metric) {
  return Boolean(metric)
    && metric.status === 'measured'
    && metric.value !== null
    && metric.value !== undefined
    && Number.isFinite(Number(metric.value));
}

export function formatMetric(metric, digits = 3) {
  return isMeasured(metric) ? Number(metric.value).toFixed(digits) : PENDING_LABEL;
}

export function formatPercent(metric) {
  return isMeasured(metric) ? `${(Number(metric.value) * 100).toFixed(1)}%` : PENDING_LABEL;
}

export function metricBasis(metric) {
  if (!metric) return '';
  return metric.status === 'measured' ? (metric.basis || '') : (metric.phase || '');
}

const SUPPORT_ORDER = { cross_modal: 0, prot_only: 1, rna_only: 2 };

export function supportRows(manifest) {
  return [...manifest.cell_types].sort((a, b) => {
    const bySupport = (SUPPORT_ORDER[a.support] ?? 9) - (SUPPORT_ORDER[b.support] ?? 9);
    return bySupport !== 0 ? bySupport : b.rna_cells - a.rna_cells;
  });
}

const LFS_MAGIC = 'version https://git-lfs.github.com/spec/v1';

export function isLfsPointer(text) {
  return typeof text === 'string' && text.startsWith(LFS_MAGIC);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test`
Expected: PASS, 12 tests

- [ ] **Step 5: Commit**

```bash
git add package.json js/manifest.js tests/manifest.test.js
git commit -m "feat: shared manifest module with pending-safe formatting"
```

---

## Task 3: Panel HTML Builders

**Files:**
- Create: `js/panels.js`
- Create: `tests/panels.test.js`

**Interfaces:**
- Consumes: `formatMetric`, `formatPercent`, `metricBasis`, `supportRows`, `PENDING_LABEL` from `js/manifest.js`.
- Produces: `escapeHtml(s) -> string`, `buildSupportSummary(manifest) -> string`, `buildSupportTable(manifest) -> string`, `buildDiagnosticsTable(manifest) -> string`, `buildBenchmarkTable(manifest) -> string`, `buildModelCard(manifest) -> string`. All return HTML strings; Tasks 4, 6, 7, and 8 assign them to `innerHTML`.

- [ ] **Step 1: Write the failing test**

Create `tests/panels.test.js`:

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  escapeHtml, buildSupportSummary, buildSupportTable,
  buildDiagnosticsTable, buildBenchmarkTable, buildModelCard,
} from '../js/panels.js';

const measured = (v, basis) => ({ value: v, status: 'measured', basis });
const pending = (phase) => ({ value: null, status: 'pending', phase, note: 'n/a' });

function fixture() {
  return {
    schema_version: '1.0',
    atlas_version: '0.1.0',
    generated: '2026-08-29',
    model: {
      name: 'CrossModalNet', latent_dim: 128, training_regime: 'supervised',
      seeds: pending('Phase 1'), notes: 'PCA projection of the latent space.',
    },
    modalities: {
      rna: { label: 'RNA', cells: 85233, classes: 22, source: 'scRNA-seq' },
      prot: { label: 'Protein', cells: 1490, classes: 2, source: 'SCoPE2 mass spectrometry' },
    },
    cell_types: [
      { class_idx: 12, name: 'monocyte', rna_cells: 9602, prot_cells: 1096, support: 'cross_modal',
        pca_centroid_cosine: measured(0.998634, '3-PC projection'),
        latent_centroid_cosine: pending('Phase 1'),
        modality_probe_accuracy: pending('Phase 4'),
        transfer_accuracy: pending('Phase 1') },
      { class_idx: 16, name: '<script>alert(1)</script>', rna_cells: 32198, prot_cells: 0,
        support: 'rna_only',
        pca_centroid_cosine: pending('Phase 2'),
        latent_centroid_cosine: pending('Phase 1'),
        modality_probe_accuracy: pending('Phase 4'),
        transfer_accuracy: pending('Phase 1') },
    ],
    summary: { total: 2, cross_modal: 1, rna_only: 1, prot_only: 0 },
    benchmark: { status: 'pending', phase: 'Phase 4', note: 'Not run yet.',
                 methods: ['CrossModalNet (ours)', 'GLUE'], rows: [] },
    data_availability: {},
  };
}

test('escapeHtml neutralises angle brackets and quotes', () => {
  assert.equal(escapeHtml('<b>"x"&\'y\'</b>'),
    '&lt;b&gt;&quot;x&quot;&amp;&#39;y&#39;&lt;/b&gt;');
});

test('support summary reports the real coverage counts', () => {
  const html = buildSupportSummary(fixture());
  assert.match(html, /support-tile-value">1<\/div><div class="support-tile-label">Cross-modal/);
  assert.match(html, /support-tile-value">1<\/div><div class="support-tile-label">RNA-only/);
  assert.match(html, /support-tile-value">3<\/div><div class="support-tile-label">Cell types/);
});

test('support table marks cross-modal and RNA-only rows distinctly', () => {
  const html = buildSupportTable(fixture());
  assert.match(html, /support-cross_modal/);
  assert.match(html, /support-rna_only/);
  assert.match(html, /Cross-modal/);
  assert.match(html, /RNA only/);
});

test('support table escapes cell type names', () => {
  const html = buildSupportTable(fixture());
  assert.ok(!html.includes('<script>alert(1)</script>'));
  assert.match(html, /&lt;script&gt;/);
});

test('support table shows counts with thousands separators', () => {
  assert.match(buildSupportTable(fixture()), /32,198/);
});

test('diagnostics table renders measured cosine and Pending elsewhere', () => {
  const html = buildDiagnosticsTable(fixture());
  assert.match(html, /0\.9986/);
  assert.match(html, /Pending/);
});

test('diagnostics table labels the basis of the measured value', () => {
  assert.match(buildDiagnosticsTable(fixture()), /3-PC projection/);
});

test('diagnostics table never prints a bare zero for a pending metric', () => {
  const html = buildDiagnosticsTable(fixture());
  assert.ok(!/>0\.000</.test(html));
});

test('benchmark table renders a pending notice and lists planned methods', () => {
  const html = buildBenchmarkTable(fixture());
  assert.match(html, /Not run yet\./);
  assert.match(html, /GLUE/);
  assert.match(html, /Pending/);
});

test('benchmark table renders measured rows when present', () => {
  const m = fixture();
  m.benchmark.status = 'measured';
  m.benchmark.rows = [{ method: 'GLUE', dataset: 'SCoPE2',
    transfer_accuracy: measured(0.883, 'mean of 10 seeds'),
    modality_probe_accuracy: measured(0.51, 'linear probe') }];
  const html = buildBenchmarkTable(m);
  assert.match(html, /88\.3%/);
  assert.match(html, /51\.0%/);
});

test('model card shows version, dims, and a pending seed count', () => {
  const html = buildModelCard(fixture());
  assert.match(html, /0\.1\.0/);
  assert.match(html, /128/);
  assert.match(html, /Pending/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test`
Expected: FAIL — `Cannot find module .../js/panels.js`

- [ ] **Step 3: Write the implementation**

Create `js/panels.js`:

```javascript
// HTML-string builders for the manifest-driven panels.
// Pure functions only — they return strings and never touch the DOM — so the
// same code is unit-tested under Node and assigned to innerHTML in the browser.

import {
  formatMetric, formatPercent, metricBasis, supportRows, PENDING_LABEL,
} from './manifest.js';

const HTML_ESCAPES = {
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
};

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
}

const num = (n) => Number(n).toLocaleString('en-US');

const SUPPORT_LABEL = {
  cross_modal: 'Cross-modal',
  rna_only: 'RNA only',
  prot_only: 'Protein only',
};

export function buildSupportSummary(manifest) {
  const s = manifest.summary;
  const tile = (value, label) =>
    `<div class="support-tile"><div class="support-tile-value">${value}</div>` +
    `<div class="support-tile-label">${label}</div></div>`;
  return [
    tile(s.cross_modal, 'Cross-modal'),
    tile(s.rna_only, 'RNA-only'),
    tile(s.total, 'Cell types'),
  ].join('');
}

export function buildSupportTable(manifest) {
  const rows = supportRows(manifest).map((c) => `
    <tr class="support-${escapeHtml(c.support)}">
      <td class="support-name">${escapeHtml(c.name)}</td>
      <td class="support-num">${num(c.rna_cells)}</td>
      <td class="support-num">${c.prot_cells > 0 ? num(c.prot_cells) : '&mdash;'}</td>
      <td><span class="support-badge badge-${escapeHtml(c.support)}">${SUPPORT_LABEL[c.support] || escapeHtml(c.support)}</span></td>
    </tr>`).join('');
  return `
    <table class="support-table">
      <thead><tr><th>Cell type</th><th>RNA</th><th>Protein</th><th>Support</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

export function buildDiagnosticsTable(manifest) {
  const rows = supportRows(manifest)
    .filter((c) => c.support === 'cross_modal')
    .map((c) => `
      <tr>
        <td class="support-name">${escapeHtml(c.name)}</td>
        <td class="support-num">${formatMetric(c.pca_centroid_cosine, 4)}
          <span class="metric-basis">${escapeHtml(metricBasis(c.pca_centroid_cosine))}</span></td>
        <td class="support-num">${formatMetric(c.latent_centroid_cosine, 4)}
          <span class="metric-basis">${escapeHtml(metricBasis(c.latent_centroid_cosine))}</span></td>
        <td class="support-num">${formatPercent(c.modality_probe_accuracy)}
          <span class="metric-basis">${escapeHtml(metricBasis(c.modality_probe_accuracy))}</span></td>
      </tr>`).join('');
  return `
    <table class="support-table">
      <thead><tr>
        <th>Cell type</th><th>Centroid cosine</th><th>Latent cosine</th><th>Modality probe</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="panel-note">
      Centroid cosine is computed on the 3-component PCA projection that this build ships.
      It is not a latent-space alignment measurement. High centroid similarity alongside a
      high modality probe score is the directional-alignment signature; the probe column
      fills in once Phase 4 runs.
    </p>`;
}

export function buildBenchmarkTable(manifest) {
  const b = manifest.benchmark;
  if (b.status !== 'measured' || b.rows.length === 0) {
    const planned = b.methods
      .map((m) => `<tr><td>${escapeHtml(m)}</td><td>&mdash;</td>` +
                  `<td class="pending">${PENDING_LABEL}</td>` +
                  `<td class="pending">${PENDING_LABEL}</td></tr>`).join('');
    return `
      <div class="pending-banner">
        <strong>${escapeHtml(b.phase)} &mdash; not yet run.</strong> ${escapeHtml(b.note)}
      </div>
      <table class="support-table">
        <thead><tr>
          <th>Method</th><th>Dataset</th><th>Transfer accuracy</th><th>Modality probe</th>
        </tr></thead>
        <tbody>${planned}</tbody>
      </table>`;
  }
  const rows = b.rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.method)}</td>
      <td>${escapeHtml(r.dataset)}</td>
      <td class="support-num">${formatPercent(r.transfer_accuracy)}</td>
      <td class="support-num">${formatPercent(r.modality_probe_accuracy)}</td>
    </tr>`).join('');
  return `
    <table class="support-table">
      <thead><tr>
        <th>Method</th><th>Dataset</th><th>Transfer accuracy</th><th>Modality probe</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

export function buildModelCard(manifest) {
  const m = manifest.model;
  const field = (label, value) =>
    `<div class="card-field"><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`;
  return `
    <dl class="model-card">
      ${field('Atlas version', escapeHtml(manifest.atlas_version))}
      ${field('Generated', escapeHtml(manifest.generated))}
      ${field('Model', escapeHtml(m.name))}
      ${field('Latent dimension', escapeHtml(String(m.latent_dim)))}
      ${field('Training regime', escapeHtml(m.training_regime))}
      ${field('Seeds', `<span class="pending">${formatMetric(m.seeds, 0)}</span>`)}
      ${field('RNA cells', num(manifest.modalities.rna.cells))}
      ${field('Protein cells', num(manifest.modalities.prot.cells))}
    </dl>
    <p class="panel-note">${escapeHtml(m.notes)}</p>`;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test`
Expected: PASS, all tests across both test files

- [ ] **Step 5: Commit**

```bash
git add js/panels.js tests/panels.test.js
git commit -m "feat: pure HTML builders for support, diagnostics, benchmark, model card"
```

---

## Task 4: Support Map and Diagnostics Panels in the Atlas

**Files:**
- Modify: `atlas.html` — add CSS near the end of the existing `<style>` block (before `</style>` at line 795), add two panel containers inside `.controls-panel` after the Proteomics Cell Types section (currently ends line 851), add one `<script type="module">` block before `</body>`.

**Interfaces:**
- Consumes: `loadManifest` from `js/manifest.js`; `buildSupportSummary`, `buildSupportTable`, `buildDiagnosticsTable` from `js/panels.js`.
- Produces: no exports. The module block is self-contained and does not touch the Three.js viewer, so it cannot disturb the `needsRender` loop.

- [ ] **Step 1: Add the panel styles**

In `atlas.html`, immediately before the closing `</style>` on line 795, insert:

```css
        .support-tiles {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            margin-bottom: 12px;
        }
        .support-tile {
            background: #f0f0f0;
            border-radius: 6px;
            padding: 8px 4px;
            text-align: center;
        }
        .support-tile-value { font-size: 20px; font-weight: 600; color: #0066A3; }
        .support-tile-label { font-size: 10px; color: #4B4B4B; text-transform: uppercase; letter-spacing: 0.04em; }
        .support-table { width: 100%; border-collapse: collapse; font-size: 11px; }
        .support-table th {
            text-align: left;
            font-weight: 600;
            color: #4B4B4B;
            border-bottom: 1px solid #d9d9d9;
            padding: 4px 6px;
        }
        .support-table td { padding: 4px 6px; border-bottom: 1px solid #efefef; vertical-align: top; }
        .support-name { color: #4B4B4B; }
        .support-num { text-align: right; font-variant-numeric: tabular-nums; }
        .support-badge {
            display: inline-block;
            padding: 1px 6px;
            border-radius: 10px;
            font-size: 9px;
            white-space: nowrap;
        }
        .badge-cross_modal { background: #008ECC; color: #ffffff; }
        .badge-rna_only { background: #f0f0f0; color: #4B4B4B; }
        .badge-prot_only { background: #0099E6; color: #ffffff; }
        .metric-basis { display: block; font-size: 9px; color: #8a8a8a; }
        .pending { color: #8a8a8a; font-style: italic; }
        .panel-note { font-size: 10px; line-height: 1.5; color: #6a6a6a; margin-top: 8px; }
        .pending-banner {
            background: #fff8e6;
            border-left: 3px solid #008ECC;
            padding: 10px 12px;
            font-size: 12px;
            color: #4B4B4B;
            margin-bottom: 12px;
        }
        .panel-error { font-size: 11px; color: #dc3545; }
```

- [ ] **Step 2: Add the panel containers**

In `atlas.html`, after the closing `</div>` of the Proteomics Cell Types `control-section` (line 851) and before the closing `</div>` of `.controls-panel` (line 852), insert:

```html
                <div class="control-section">
                    <h3>Cross-Modal Support</h3>
                    <div class="support-tiles" id="support-tiles"></div>
                    <div id="support-table-mount"></div>
                    <p class="panel-note">
                        Protein coverage exists for only part of the label space. Cell types marked
                        RNA only have no proteomics evidence in this build, and projections onto them
                        should not be read as cross-modal results.
                    </p>
                </div>

                <div class="control-section">
                    <h3>Alignment Diagnostics</h3>
                    <div id="diagnostics-mount"></div>
                </div>
```

- [ ] **Step 3: Wire the module**

In `atlas.html`, immediately before `</body>`, insert:

```html
    <script type="module">
        import { loadManifest } from './js/manifest.js';
        import { buildSupportSummary, buildSupportTable, buildDiagnosticsTable } from './js/panels.js';

        loadManifest().then((manifest) => {
            document.getElementById('support-tiles').innerHTML = buildSupportSummary(manifest);
            document.getElementById('support-table-mount').innerHTML = buildSupportTable(manifest);
            document.getElementById('diagnostics-mount').innerHTML = buildDiagnosticsTable(manifest);
        }).catch((err) => {
            const message = `<p class="panel-error">Support data unavailable: ${err.message}</p>`;
            document.getElementById('support-table-mount').innerHTML = message;
            document.getElementById('diagnostics-mount').innerHTML = message;
        });
    </script>
```

- [ ] **Step 4: Verify in the browser**

Run: `python3 -m http.server 8000` then open `http://localhost:8000/atlas.html`

Expected, in the left controls panel below the cell type filters:
- Three tiles reading **2** Cross-modal, **20** RNA-only, **22** Cell types
- A support table with `monocyte` and `macrophage` at the top carrying blue `Cross-modal` badges, then the 20 RNA-only rows in descending RNA count starting with `neutrophil` at 32,198
- A diagnostics table with exactly two rows, showing `0.9986` and `0.9972` under Centroid cosine with `3-PC projection` beneath each, and italic `Pending` under Latent cosine and Modality probe
- Browser console clean; the 3D viewer still rotates, hovers, and toggles as before

- [ ] **Step 5: Confirm the render loop is untouched**

Run: `grep -c "needsRender" atlas.html`
Expected: unchanged from before this task (the module block must not reference it)

- [ ] **Step 6: Commit**

```bash
git add atlas.html
git commit -m "feat: cross-modal support map and alignment diagnostics panels"
```

---

## Task 5: Honest Failure for Unfetched RNA Expression Data

**Files:**
- Modify: `atlas.html` — `_streamSearchProfile` (near line 1698) and `_streamAllProfiles` (near line 1758)
- Create: `tests/lfs.test.js`

**Interfaces:**
- Consumes: `isLfsPointer` from `js/manifest.js` (already implemented and tested in Task 2).
- Produces: no new exports. Behaviour change only.

**Why this task exists.** `Atlas/atlas_RNA_lat128-001-part1.csv` and `-part2.csv` are 135-byte Git LFS pointer files. Clicking an RNA cell today fetches a pointer, parses it as CSV, finds nothing, and reports a misleading "cell not found" error that suggests a data bug rather than an unfetched download. PROT clicks work because that 45 MB file is real.

- [ ] **Step 1: Write the failing test**

Create `tests/lfs.test.js`:

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { isLfsPointer } from '../js/manifest.js';

test('the shipped RNA part files are still unfetched LFS pointers', () => {
  const part1 = readFileSync(new URL('../Atlas/atlas_RNA_lat128-001-part1.csv', import.meta.url), 'utf8');
  assert.equal(isLfsPointer(part1), true,
    'If this fails, git lfs pull has been run — the guard should now fall through to real parsing.');
});

test('atlas.html guards RNA profile loading behind an LFS check', () => {
  const html = readFileSync(new URL('../atlas.html', import.meta.url), 'utf8');
  assert.match(html, /isLfsPointer/, 'atlas.html must check for LFS pointers before parsing');
  assert.match(html, /git lfs pull/, 'the error shown to the user must name the remedy');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/lfs.test.js`
Expected: FAIL on the second test — `atlas.html must check for LFS pointers before parsing`

- [ ] **Step 3: Add the guard to atlas.html**

`atlas.html`'s main script is a classic (non-module) script, so it cannot `import`. Add the predicate as a method on the atlas class instead, mirroring `js/manifest.js`. Insert this method directly above `parseCSVLine(line)` (line 1815):

```javascript
            // Mirrors isLfsPointer in js/manifest.js. Duplicated because the main
            // atlas script is a classic script and cannot import ES modules.
            isLfsPointer(text) {
                return typeof text === 'string'
                    && text.startsWith('version https://git-lfs.github.com/spec/v1');
            }
```

**Critical structural note.** Both functions wrap their whole body in `try { ... } catch (e) { /* try next file */ }`. Throwing from inside that try is silently swallowed and the loop simply moves to the next file. The guard must therefore set a flag, break out, and throw *after* the loop. Do not throw inside the try.

Both functions stream through a reader, so there is no single response-text variable. The check runs against `buffer` on the first chunk, identified by `headers` still being null.

**In `_streamSearchProfile`** (starts line 1732), make three edits:

Add the flag as the first line of the function body, above `for (const fileName of fileNames) {`:

```javascript
                let lfsBlocked = false;
```

Immediately after `buffer += decoder.decode(value, { stream: true });` (line 1750), insert. Do not call `reader.releaseLock()` here — the existing call on line 1787 runs once the loop breaks, and releasing twice throws:

```javascript
                            if (headers === null && this.isLfsPointer(buffer)) {
                                lfsBlocked = true;
                                break;
                            }
```

Then replace the closing of the catch and the final throw (lines 1788–1792):

```javascript
                    } catch (e) {
                        // try next file
                    }
                    if (lfsBlocked) break;
                }
                if (lfsBlocked) {
                    throw new Error(
                        'RNA expression data is not present in this deployment. ' +
                        'The file is a 1.43 GB Git LFS object that has not been fetched. ' +
                        'Run: git lfs install && git lfs pull'
                    );
                }
                throw new Error(`Cell with orig_index ${cellData.orig_index} not found in ${modality} data`);
            }
```

**In `_streamAllProfiles`** (the PROT path), apply the same three edits. Its file is real today so the guard cannot currently fire, but it keeps the two paths consistent if RNA is ever routed through it. Add `let lfsBlocked = false;` above its `for (const fileName of fileNames) {`; insert the same guard after `buffer += decoder.decode(value, { stream: true });` (line 1690); and replace lines 1726–1730:

```javascript
                    } catch (e) {
                        // try next file
                    }
                    if (lfsBlocked) break;
                }
                if (lfsBlocked) {
                    throw new Error(
                        'RNA expression data is not present in this deployment. ' +
                        'The file is a 1.43 GB Git LFS object that has not been fetched. ' +
                        'Run: git lfs install && git lfs pull'
                    );
                }
            }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test`
Expected: PASS, all test files

- [ ] **Step 5: Verify the message in the browser**

Run: `python3 -m http.server 8000`, open `http://localhost:8000/atlas.html`, click any RNA cell (the large outer cloud).
Expected: the gene profile panel shows the sentence naming `git lfs pull`, not a "cell not found" error.
Then click a monocyte or macrophage protein cell.
Expected: a real gene profile table still loads, unchanged.

- [ ] **Step 6: Commit**

```bash
git add atlas.html tests/lfs.test.js
git commit -m "fix: report unfetched RNA LFS data honestly instead of cell-not-found"
```

---

## Task 6: Versions Page

**Files:**
- Create: `versions.html`

**Interfaces:**
- Consumes: `loadManifest` from `js/manifest.js`; `buildModelCard` from `js/panels.js`.
- Produces: a page at `versions.html`, linked from Task 9.

- [ ] **Step 1: Create the page**

Create `versions.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VivOME Atlas — Versions</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: #f5f5f3;
            color: #4B4B4B;
            line-height: 1.6;
            padding: 40px 20px;
        }
        .wrap { max-width: 860px; margin: 0 auto; }
        .back-button {
            display: inline-block;
            margin-bottom: 24px;
            padding: 6px 14px;
            background: #ffffff;
            border: 1px solid #d9d9d9;
            border-radius: 4px;
            color: #0066A3;
            text-decoration: none;
            font-size: 13px;
        }
        .back-button:hover { background: #008ECC; color: #ffffff; border-color: #008ECC; }
        h1 { font-size: 26px; color: #0066A3; font-weight: 600; margin-bottom: 4px; }
        .subtitle { font-size: 14px; color: #6a6a6a; margin-bottom: 28px; }
        section { background: #ffffff; border-radius: 8px; padding: 22px 26px; margin-bottom: 20px; }
        h2 { font-size: 16px; color: #0066A3; font-weight: 600; margin-bottom: 14px; }
        .model-card { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
        .card-field dt { font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: #8a8a8a; }
        .card-field dd { font-size: 16px; color: #4B4B4B; font-variant-numeric: tabular-nums; }
        .pending { color: #8a8a8a; font-style: italic; }
        .panel-note { font-size: 12px; color: #6a6a6a; margin-top: 14px; }
        .panel-error { font-size: 13px; color: #dc3545; }
        .avail { width: 100%; border-collapse: collapse; font-size: 13px; }
        .avail th { text-align: left; padding: 6px 8px; border-bottom: 1px solid #d9d9d9; font-size: 11px; text-transform: uppercase; color: #8a8a8a; }
        .avail td { padding: 8px; border-bottom: 1px solid #efefef; vertical-align: top; }
        code { background: #f0f0f0; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
        ol { margin-left: 20px; font-size: 13px; }
        ol li { margin-bottom: 6px; }
    </style>
</head>
<body>
    <div class="wrap">
        <a href="index.html" class="back-button">Back</a>
        <h1>Atlas Versions</h1>
        <p class="subtitle">Model card, data availability, and the protocol for releasing a new atlas version.</p>

        <section>
            <h2>Current release</h2>
            <div id="model-card-mount"></div>
        </section>

        <section>
            <h2>Data availability</h2>
            <table class="avail">
                <thead><tr><th>Asset</th><th>Status</th><th>Notes</th></tr></thead>
                <tbody id="availability-mount"></tbody>
            </table>
        </section>

        <section>
            <h2>Release protocol</h2>
            <ol>
                <li>Freeze inputs: record accession numbers, download dates, and checksums for every dataset.</li>
                <li>Train and export, then regenerate the manifest with <code>python3 tools/build_manifest.py</code>.</li>
                <li>Bump <code>ATLAS_VERSION</code> in <code>tools/build_manifest.py</code> and commit the regenerated manifest.</li>
                <li>Tag the release and archive it for a persistent identifier.</li>
                <li>Record label stability against the previous version and add it to this page.</li>
            </ol>
            <p class="panel-note">
                Label stability across versions is not yet measured. It is reported here from the
                first release that has a predecessor to compare against.
            </p>
        </section>
    </div>

    <script type="module">
        import { loadManifest } from './js/manifest.js';
        import { buildModelCard, escapeHtml } from './js/panels.js';

        loadManifest().then((manifest) => {
            document.getElementById('model-card-mount').innerHTML = buildModelCard(manifest);
            document.getElementById('availability-mount').innerHTML =
                Object.entries(manifest.data_availability).map(([key, info]) => `
                    <tr>
                        <td><code>${escapeHtml(key)}</code></td>
                        <td>${escapeHtml(info.status)}</td>
                        <td>${escapeHtml(info.note)}${info.remedy ? ` <code>${escapeHtml(info.remedy)}</code>` : ''}</td>
                    </tr>`).join('');
        }).catch((err) => {
            document.getElementById('model-card-mount').innerHTML =
                `<p class="panel-error">Manifest unavailable: ${err.message}</p>`;
        });
    </script>
</body>
</html>
```

- [ ] **Step 2: Export escapeHtml for page use**

`buildModelCard` and this page both need `escapeHtml`. It is already exported from `js/panels.js` in Task 3, so no change is required. Confirm:

Run: `grep -n "export function escapeHtml" js/panels.js`
Expected: one match

- [ ] **Step 3: Verify in the browser**

Run: `python3 -m http.server 8000`, open `http://localhost:8000/versions.html`
Expected: model card showing atlas version `0.1.0`, latent dimension `128`, RNA cells `85,233`, Protein cells `1,490`, and an italic `Pending` for Seeds. Data availability lists `rna_expression` as `lfs_not_fetched` with the `git lfs install && git lfs pull` remedy.

- [ ] **Step 4: Commit**

```bash
git add versions.html
git commit -m "feat: versions page with model card and data availability"
```

---

## Task 7: Benchmark Page

**Files:**
- Create: `benchmark.html`

**Interfaces:**
- Consumes: `loadManifest` from `js/manifest.js`; `buildBenchmarkTable` from `js/panels.js`.
- Produces: a page at `benchmark.html`, linked from Task 9. Filling `manifest.benchmark.rows` with `{method, dataset, transfer_accuracy, modality_probe_accuracy}` records and setting `status` to `measured` switches the page from pending to results with no HTML change.

- [ ] **Step 1: Create the page**

Create `benchmark.html`. It reuses the visual language of `versions.html`; the styles are repeated in full rather than shared, matching this repository's existing pattern of self-contained pages:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VivOME Atlas — Benchmark</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: #f5f5f3;
            color: #4B4B4B;
            line-height: 1.6;
            padding: 40px 20px;
        }
        .wrap { max-width: 940px; margin: 0 auto; }
        .back-button {
            display: inline-block;
            margin-bottom: 24px;
            padding: 6px 14px;
            background: #ffffff;
            border: 1px solid #d9d9d9;
            border-radius: 4px;
            color: #0066A3;
            text-decoration: none;
            font-size: 13px;
        }
        .back-button:hover { background: #008ECC; color: #ffffff; border-color: #008ECC; }
        h1 { font-size: 26px; color: #0066A3; font-weight: 600; margin-bottom: 4px; }
        .subtitle { font-size: 14px; color: #6a6a6a; margin-bottom: 28px; }
        section { background: #ffffff; border-radius: 8px; padding: 22px 26px; margin-bottom: 20px; }
        h2 { font-size: 16px; color: #0066A3; font-weight: 600; margin-bottom: 14px; }
        .table-scroll { overflow-x: auto; }
        .support-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .support-table th { text-align: left; padding: 6px 8px; border-bottom: 1px solid #d9d9d9; font-size: 11px; text-transform: uppercase; color: #8a8a8a; }
        .support-table td { padding: 8px; border-bottom: 1px solid #efefef; }
        .support-num { text-align: right; font-variant-numeric: tabular-nums; }
        .pending { color: #8a8a8a; font-style: italic; }
        .pending-banner { background: #fff8e6; border-left: 3px solid #008ECC; padding: 12px 14px; font-size: 13px; margin-bottom: 16px; }
        .panel-note { font-size: 12px; color: #6a6a6a; margin-top: 14px; }
        .panel-error { font-size: 13px; color: #dc3545; }
    </style>
</head>
<body>
    <div class="wrap">
        <a href="index.html" class="back-button">Back</a>
        <h1>Standing Benchmark</h1>
        <p class="subtitle">Fixed datasets, fixed metrics, every method scored the same way.</p>

        <section>
            <h2>Cross-modal integration comparison</h2>
            <div class="table-scroll" id="benchmark-mount"></div>
            <p class="panel-note">
                Transfer accuracy is the headline number most integration papers report.
                The modality probe column is the diagnostic: a linear classifier trained to
                recover the source modality from the integrated representation. High transfer
                accuracy together with high probe accuracy means the modalities point in the
                same direction without sharing a representation.
            </p>
        </section>

        <section>
            <h2>Why both columns</h2>
            <p style="font-size: 13px;">
                A method can score well on mixing and transfer while a probe still recovers the
                source modality almost perfectly. Reporting transfer accuracy alone hides that.
                Running the probe across every method is what turns the observation into a
                property of the field rather than a quirk of one model.
            </p>
        </section>
    </div>

    <script type="module">
        import { loadManifest } from './js/manifest.js';
        import { buildBenchmarkTable } from './js/panels.js';

        loadManifest().then((manifest) => {
            document.getElementById('benchmark-mount').innerHTML = buildBenchmarkTable(manifest);
        }).catch((err) => {
            document.getElementById('benchmark-mount').innerHTML =
                `<p class="panel-error">Manifest unavailable: ${err.message}</p>`;
        });
    </script>
</body>
</html>
```

- [ ] **Step 2: Verify the pending state renders**

Run: `python3 -m http.server 8000`, open `http://localhost:8000/benchmark.html`
Expected: an amber banner reading `Phase 4 — not yet run.` followed by the note, then a seven-row table listing each planned method with `Pending` in both metric columns. No numeric values anywhere.

- [ ] **Step 3: Verify the measured state renders**

Temporarily edit `Atlas/atlas_manifest.json`, setting `benchmark.status` to `"measured"` and `benchmark.rows` to:

```json
[
  {
    "method": "CrossModalNet (ours)",
    "dataset": "SCoPE2",
    "transfer_accuracy": { "value": 0.983, "status": "measured", "basis": "single run" },
    "modality_probe_accuracy": { "value": null, "status": "pending", "phase": "Phase 4", "note": "n/a" }
  }
]
```

Reload the page.
Expected: banner gone, one row showing `98.3%` for transfer accuracy and italic `Pending` for the probe.

Then restore the real manifest:

Run: `python3 tools/build_manifest.py`
Expected: `manifest matches verified ground truth` shape restored; `git diff --stat Atlas/atlas_manifest.json` shows no change.

- [ ] **Step 4: Commit**

```bash
git add benchmark.html
git commit -m "feat: standing benchmark page driven by the manifest"
```

---

## Task 8: Projection Page

**Files:**
- Create: `project.html`

**Interfaces:**
- Consumes: `loadManifest` from `js/manifest.js`; `escapeHtml` from `js/panels.js`.
- Produces: a page at `project.html`, linked from Task 9. Defines the request and response contract that the Phase 5 backend implements.

**Design note.** No backend exists. Rather than fake a projection result — which would violate the no-fabricated-numbers constraint — the page validates the submitted file locally, reports what it found, and states plainly that projection requires a service that is not yet deployed. The request and response schemas are published on the page so the backend can be written against them.

- [ ] **Step 1: Create the page**

Create `project.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VivOME Atlas — Project Data</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: #f5f5f3;
            color: #4B4B4B;
            line-height: 1.6;
            padding: 40px 20px;
        }
        .wrap { max-width: 860px; margin: 0 auto; }
        .back-button {
            display: inline-block;
            margin-bottom: 24px;
            padding: 6px 14px;
            background: #ffffff;
            border: 1px solid #d9d9d9;
            border-radius: 4px;
            color: #0066A3;
            text-decoration: none;
            font-size: 13px;
        }
        .back-button:hover { background: #008ECC; color: #ffffff; border-color: #008ECC; }
        h1 { font-size: 26px; color: #0066A3; font-weight: 600; margin-bottom: 4px; }
        .subtitle { font-size: 14px; color: #6a6a6a; margin-bottom: 28px; }
        section { background: #ffffff; border-radius: 8px; padding: 22px 26px; margin-bottom: 20px; }
        h2 { font-size: 16px; color: #0066A3; font-weight: 600; margin-bottom: 14px; }
        label { display: block; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: #8a8a8a; margin-bottom: 6px; }
        select, input[type="file"] {
            width: 100%; padding: 8px; font-size: 13px;
            border: 1px solid #d9d9d9; border-radius: 4px; background: #ffffff; margin-bottom: 16px;
        }
        button {
            background: #008ECC; color: #ffffff; border: none; border-radius: 4px;
            padding: 10px 20px; font-size: 14px; cursor: pointer;
        }
        button:hover { background: #0066A3; }
        button:disabled { background: #c9c9c9; cursor: not-allowed; }
        .pending-banner { background: #fff8e6; border-left: 3px solid #008ECC; padding: 12px 14px; font-size: 13px; margin-bottom: 16px; }
        .panel-note { font-size: 12px; color: #6a6a6a; margin-top: 14px; }
        .panel-error { font-size: 13px; color: #dc3545; }
        .result { font-size: 13px; margin-top: 16px; }
        .result dt { font-size: 10px; text-transform: uppercase; color: #8a8a8a; letter-spacing: 0.05em; }
        .result dd { margin-bottom: 10px; font-variant-numeric: tabular-nums; }
        pre { background: #f0f0f0; padding: 14px; border-radius: 6px; font-size: 12px; overflow-x: auto; }
        code { background: #f0f0f0; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
        .supported-list { font-size: 13px; margin-top: 8px; }
        .supported-list strong { color: #0066A3; }
    </style>
</head>
<body>
    <div class="wrap">
        <a href="index.html" class="back-button">Back</a>
        <h1>Project Your Data</h1>
        <p class="subtitle">Submit an expression matrix and receive coordinates in the shared latent space.</p>

        <section>
            <h2>Submit a matrix</h2>
            <div class="pending-banner">
                <strong>The projection service is not yet deployed.</strong>
                This page validates your file locally and reports what it found. It does not
                return coordinates or labels, because producing either without a trained
                projection would mean inventing them.
            </div>

            <label for="modality">Modality</label>
            <select id="modality">
                <option value="rna">RNA — genes &times; cells</option>
                <option value="prot">Protein — proteins &times; cells</option>
            </select>

            <label for="matrix">Matrix file (CSV, first column = feature name, header row = cell IDs)</label>
            <input type="file" id="matrix" accept=".csv,text/csv">

            <button id="submit" disabled>Validate matrix</button>

            <div id="result"></div>
        </section>

        <section>
            <h2>Supported label space</h2>
            <p style="font-size: 13px;">
                A projection is only meaningful onto cell types the atlas actually supports.
                The service returns no label when a query falls outside this space rather
                than guessing at it.
            </p>
            <div class="supported-list" id="supported"></div>
        </section>

        <section>
            <h2>Service contract</h2>
            <p style="font-size: 13px;">The backend built in Phase 5 implements this interface.</p>
            <pre>POST /api/project
Content-Type: multipart/form-data

  modality : "rna" | "prot"
  matrix   : CSV, features in rows, cells in columns

200 Response
{
  "atlas_version": "0.1.0",
  "n_cells": 298,
  "n_features_matched": 1204,
  "n_features_unmatched": 87,
  "cells": [
    {
      "cell_id": "AAACCTGAGAAACCAT-1",
      "coordinates": [0.41, -0.22, 0.09],
      "label": "monocyte",
      "label_set": ["monocyte", "macrophage"],
      "confidence": 0.91,
      "abstained": false
    },
    {
      "cell_id": "AAACCTGAGAAACCGC-1",
      "coordinates": [1.83, 0.94, -1.10],
      "label": null,
      "label_set": [],
      "confidence": null,
      "abstained": true,
      "abstain_reason": "outside supported latent space"
    }
  ]
}</pre>
            <p class="panel-note">
                <code>label_set</code> is a conformal prediction set at the stated coverage level,
                not a single argmax. <code>abstained</code> is true when the query falls outside
                the region the atlas has evidence for.
            </p>
        </section>
    </div>

    <script type="module">
        import { loadManifest } from './js/manifest.js';
        import { escapeHtml } from './js/panels.js';

        const fileInput = document.getElementById('matrix');
        const submitButton = document.getElementById('submit');
        const resultMount = document.getElementById('result');

        fileInput.addEventListener('change', () => {
            submitButton.disabled = fileInput.files.length === 0;
            resultMount.innerHTML = '';
        });

        submitButton.addEventListener('click', async () => {
            const file = fileInput.files[0];
            if (!file) return;
            submitButton.disabled = true;
            try {
                const text = await file.text();
                const lines = text.split(/\r?\n/).filter((line) => line.trim() !== '');
                if (lines.length < 2) throw new Error('File needs a header row and at least one feature row.');
                const cells = lines[0].split(',').length - 1;
                const features = lines.length - 1;
                if (cells < 1) throw new Error('Header row lists no cell IDs.');
                resultMount.innerHTML = `
                    <dl class="result">
                        <dt>File</dt><dd>${escapeHtml(file.name)} (${(file.size / 1024).toFixed(1)} KB)</dd>
                        <dt>Cells detected</dt><dd>${cells.toLocaleString('en-US')}</dd>
                        <dt>Features detected</dt><dd>${features.toLocaleString('en-US')}</dd>
                        <dt>Projection</dt>
                        <dd class="panel-error">Not performed — the projection service is not deployed.</dd>
                    </dl>`;
            } catch (err) {
                resultMount.innerHTML = `<p class="panel-error">${escapeHtml(err.message)}</p>`;
            } finally {
                submitButton.disabled = false;
            }
        });

        loadManifest().then((manifest) => {
            const supported = manifest.cell_types
                .filter((c) => c.support === 'cross_modal')
                .map((c) => escapeHtml(c.name));
            const rnaOnly = manifest.summary.rna_only;
            document.getElementById('supported').innerHTML = `
                <p><strong>Cross-modal support (${supported.length}):</strong> ${supported.join(', ')}</p>
                <p><strong>RNA-only (${rnaOnly}):</strong> projection onto these types has no
                proteomics evidence and the service abstains for protein queries.</p>`;
        }).catch((err) => {
            document.getElementById('supported').innerHTML =
                `<p class="panel-error">Manifest unavailable: ${err.message}</p>`;
        });
    </script>
</body>
</html>
```

- [ ] **Step 2: Verify with a real file**

Run:
```bash
python3 -m http.server 8000
```
Open `http://localhost:8000/project.html`, choose `Atlas/metadata_PROT_lat128.csv` and click Validate matrix.
Expected: the result block reports `Cells detected 7`, `Features detected 1,490`, and a red line stating projection was not performed. (The metadata CSV is a cells-in-rows table, so the counts read as transposed — this confirms the parser is reporting literally what it found rather than guessing.)

- [ ] **Step 3: Verify the supported label space**

Expected on the same page: `Cross-modal support (2): monocyte, macrophage` and `RNA-only (20)`.

- [ ] **Step 4: Commit**

```bash
git add project.html
git commit -m "feat: projection page with validation and published service contract"
```

---

## Task 9: Navigation and Documentation

**Files:**
- Modify: `index.html` — label divs near line 186, `colors` and `urls` arrays at lines 818–819
- Modify: `SUMMARY.md`

**Interfaces:**
- Consumes: nothing. The landing page's layout is driven by `urls.length`, so extending both parallel arrays and adding matching label divs is sufficient.
- Produces: navigation to `benchmark.html`, `project.html`, and `versions.html`.

- [ ] **Step 1: Extend the nav arrays**

In `index.html`, replace lines 818–819:

```javascript
    const colors = ['#5CB85C', '#0275D8'];
    const urls = ['visual.html', 'atlas.html'];
```

with:

```javascript
    const colors = ['#5CB85C', '#0275D8', '#008ECC', '#0066A3', '#5BC0DE'];
    const urls = ['visual.html', 'atlas.html', 'project.html', 'benchmark.html', 'versions.html'];
```

- [ ] **Step 2: Add the matching label divs**

In `index.html`, replace lines 186–187:

```html
      <div id="label0" class="overlay-label">Visuals</div>
      <div id="label1" class="overlay-label">Live Atlas</div>
```

with:

```html
      <div id="label0" class="overlay-label">Visuals</div>
      <div id="label1" class="overlay-label">Live Atlas</div>
      <div id="label2" class="overlay-label">Project Data</div>
      <div id="label3" class="overlay-label">Benchmark</div>
      <div id="label4" class="overlay-label">Versions</div>
```

- [ ] **Step 3: Verify the layout with five nodes**

Run: `python3 -m http.server 8000`, open `http://localhost:8000/index.html`
Expected: five labelled nodes, none overlapping, each hovering and navigating to its page. Resize the window and confirm the debounced rebuild still settles cleanly.

If the seeded layout crowds at five nodes, adjust the `radii` array on line 817 (reduce the first entry from `28` toward `22`) rather than changing the layout algorithm. Re-verify after any change.

- [ ] **Step 4: Confirm every label has a position**

Run:
```bash
node -e "
const fs = require('fs');
const html = fs.readFileSync('index.html', 'utf8');
const urls = html.match(/const urls = \[(.*?)\]/s)[1].split(',').length;
const colors = html.match(/const colors = \[(.*?)\]/s)[1].split(',').length;
const labels = (html.match(/id=\"label\d+\"/g) || []).length;
if (urls !== colors || urls !== labels) {
  throw new Error(\`mismatch: urls=\${urls} colors=\${colors} labels=\${labels}\`);
}
console.log('nav arrays aligned:', urls, 'nodes');
"
```
Expected: `nav arrays aligned: 5 nodes`

- [ ] **Step 5: Update SUMMARY.md**

In `SUMMARY.md`, replace the "Web pages (static HTML, no build step)" table with:

```markdown
| File | Purpose |
|------|---------|
| `index.html` | Landing page — animated intro with nav nodes for every section |
| `atlas.html` | Interactive **3D cell visualization** (RNA + Protein), with the cross-modal support map and alignment diagnostics panels |
| `visual.html` | Plot viewer for the precomputed 3D plots (**Supervised** + **Semi-Supervised** modes) |
| `project.html` | Submit an expression matrix for projection into the shared latent space |
| `benchmark.html` | Standing comparison against established integration methods |
| `versions.html` | Model card, data availability, and release protocol |
| `miscellaneous.html` | Intentionally **blank** (former Roadmap page, cleared) |
```

Then add this section immediately before "## How to Use":

```markdown
### The manifest

`Atlas/atlas_manifest.json` is the single source of truth for every number the
web pages display. Regenerate it after any change to the metadata CSVs:

```bash
python3 tools/build_manifest.py
```

Metrics that require the training pipeline — latent-space alignment, the
modality probe, transfer accuracy, benchmark rows — are stored as explicit
pending records and render as `Pending`. No page ever displays a number that
was not computed from data in this repository.

### Tests

No dependencies to install. From the repository root:

```bash
node --test                                  # JS modules under js/
cd tools && python3 -m unittest discover     # manifest builder
```
```

- [ ] **Step 6: Run the full suite and commit**

```bash
node --test
cd tools && python3 -m unittest discover && cd ..
git add index.html SUMMARY.md
git commit -m "feat: navigation for projection, benchmark, and versions pages"
```

---

## Final Verification

- [ ] **All tests pass**

```bash
node --test
cd tools && python3 -m unittest discover -v && cd ..
```
Expected: no failures in either runner.

- [ ] **Manifest still matches ground truth**

```bash
python3 tools/build_manifest.py
git diff --exit-code Atlas/atlas_manifest.json && echo "manifest reproducible"
```
Expected: `manifest reproducible` — regenerating produces no diff.

- [ ] **No fabricated numbers reached the pages**

```bash
grep -n "0\.98\|42\.28\|98\.3" atlas.html benchmark.html versions.html project.html \
  && echo "REVIEW: hardcoded metric found" || echo "no hardcoded metrics in page markup"
```
Expected: `no hardcoded metrics in page markup`. Every displayed number must arrive through the manifest.

- [ ] **Every page serves and runs clean**

```bash
python3 -m http.server 8000
```
Open each of `index.html`, `atlas.html`, `visual.html`, `project.html`, `benchmark.html`, `versions.html`.
Expected: all render, browser console clean on each, and the atlas viewer still rotates, hovers, toggles modalities without a flash, and opens a protein gene profile.

- [ ] **Existing optimisations intact**

```bash
grep -c "needsRender" atlas.html
grep -c "raycastTargets" atlas.html
grep -c "debounce" index.html
grep -c "animationPaused" visual.html
```
Expected: all counts greater than zero.

---

## What This Plan Deliberately Does Not Do

- **No numbers are invented.** Latent-space alignment, modality probe accuracy, transfer accuracy, and every benchmark row stay pending until the training pipeline produces them. The schema is built so filling them in touches only the manifest.
- **No backend.** `project.html` publishes the service contract and validates input locally. The Phase 5 service is separate work.
- **No Git LFS fetch.** Task 5 makes the missing 1.43 GB RNA expression object fail honestly rather than silently. Fetching it is a deployment decision, not a code change.
- **No changes to the viewer's render loop.** Every panel added here lives in its own module block and cannot affect demand rendering.
