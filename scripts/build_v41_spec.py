"""Writes v4.1's spec and MANIFEST into service/model/v4_1/ (research/todo.md,
Track G, v4.1, Phase D).

v4.1 is v4's code (service/pipeline/fusion.py) and v4's data files with its
own spec. The spec is v4's (service/model/v4/spec_v4.json) with:
- version "v4.1";
- best_guess.gate_on_fusion_weight and correlation_temperature from Phase
  A's locked rule (research/notebook-outputs/v41_pretest/locked_rule.json).
  fusion_weight stays v4's 0.7, the encoder's weight where the correlation
  term is flat;
- the evaluation from Phase C's spec block, once its run has written it;
  pending until then, and the service refuses v4.1 until it has passed.

The MANIFEST lists the spec and every v4 data file (as ../v4/...), each
with its sha256, so v4.1 is pinned to v4's exact files.

    python scripts/build_v41_spec.py      # from the repository root
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from service import config  # noqa: E402

LOCKED = REPO / "research" / "notebook-outputs" / "v41_pretest" / "locked_rule.json"
PHASE_C_BLOCK = REPO / "research" / "notebook-outputs" / "v41_phase3" / "spec_block.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    locked = json.loads(LOCKED.read_text(encoding="utf-8"))
    if locked["is_v4"]:
        raise SystemExit("Phase A kept v4: there is no v4.1 to build")
    v4 = json.loads(config.V4_SPEC_PATH.read_text(encoding="utf-8"))
    block = json.loads(PHASE_C_BLOCK.read_text(encoding="utf-8")) if PHASE_C_BLOCK.exists() else {}
    spec = copy.deepcopy(v4)
    spec["version"] = "v4.1"
    spec["created"] = str(date.today())
    spec["source"] = ("v4's spec (service/model/v4/spec_v4.json) with Phase A's locked rule "
                      "(research/notebooks/v41_pretest.py); built by scripts/build_v41_spec.py")
    spec["based_on"] = {"spec": "service/model/v4/spec_v4.json", "sha256": sha256(config.V4_SPEC_PATH)}
    b = spec["best_guess"]
    b["gate_on_fusion_weight"] = float(locked["w_on"])
    b["correlation_temperature"] = float(locked["tau"])
    b["chosen_on"]["gate_on_fusion_weight and correlation_temperature"] = (
        "Fulcher 2026 under fixed rules (research/notebooks/v41_pretest.py), checked once on Khoury 2026 "
        "(benchmark/khoury2026_posthoc_v41_check.py)")
    spec["evaluation"] = block.get("evaluation", {"status": "pending", "record": None})
    config.V41_DIR.mkdir(parents=True, exist_ok=True)
    (config.V41_DIR / "spec_v41.json").write_text(json.dumps(spec, indent=2) + "\n", newline="\n")

    v4_manifest = json.loads(config.V4_MANIFEST_PATH.read_text(encoding="utf-8"))
    files = {"spec_v41.json": {"sha256": sha256(config.V41_DIR / "spec_v41.json"),
                               "bytes": (config.V41_DIR / "spec_v41.json").stat().st_size,
                               "what": "v4.1's settings: v4's with its gate-on encoder weight and correlation temperature"}}
    for rel, entry in v4_manifest["files"].items():
        if rel == "spec_v4.json":
            continue
        path = config.V4_DIR / rel
        if sha256(path) != entry["sha256"]:
            raise SystemExit(f"{path} does not match v4's MANIFEST: rebuild v4 first")
        files[f"../v4/{rel}"] = {"sha256": entry["sha256"], "bytes": entry["bytes"], "what": f"v4's: {entry['what']}"}
    (config.V41_DIR / "MANIFEST.json").write_text(json.dumps({
        "source": "scripts/build_v41_spec.py; data files are v4's (service/model/v4/MANIFEST.json), pinned here by sha256",
        "files": files}, indent=2) + "\n", newline="\n")
    print(f"wrote {config.V41_DIR / 'spec_v41.json'} and MANIFEST.json: gate_on_fusion_weight {b['gate_on_fusion_weight']}, "
          f"correlation_temperature {b['correlation_temperature']}, evaluation {spec['evaluation']['status']}")


if __name__ == "__main__":
    main()
