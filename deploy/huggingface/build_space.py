"""Assembles the projection service as a Hugging Face Space (Docker SDK) in
the gitignored folder deploy/huggingface/space, ready to publish (PUBLISH.md
beside this file).

The Space serves one pipeline version, the one its Dockerfile names
(VIVOME_PIPELINE_VERSION, v4.1), so it ships only that version's files. They
are found, not listed by hand: this script loads that version's bundle and
projects the PBMC240 example, unrestricted and restricted, with an audit hook
recording every file opened under the model folder, then copies exactly those.
With them go the service's Python package (no tests, no examples), the
raw-or-log package valuescale/ with its shipped calibration (no tests, corpus
or bank), the Dockerfile, the Space card (space_card.md, as README.md), requirements.txt
pinned to this interpreter's versions (torch as its CPU build), and a
.gitattributes that puts every file over 10 MB in Git LFS.
space_manifest.json lists every file with its size and sha256, the commit it
was built from, and whether service/, valuescale/ or deploy/ had uncommitted
changes. Last, a fresh interpreter imports every staged module of the two
packages from the staged folder alone and loads the calibration (B6): a
piece left out stops the build.

A previous build is replaced, except a .git folder (a clone of the Space).

    python deploy/huggingface/build_space.py      # from the repository root
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "deploy" / "huggingface"
OUT = HERE / "space"
MODEL = REPO / "service" / "model"
EXAMPLE = REPO / "service" / "examples" / "pbmc240_proteins_raw.tsv"
LFS_BYTES = 10 * 1024 * 1024  # Hugging Face refuses plain git files over 10 MB
PINNED = ("numpy", "pandas", "scipy", "scikit-learn", "POT", "faiss-cpu")
TORCH_INDEX = "https://download.pytorch.org/whl/cpu"
SOURCES = ("service", "valuescale", "deploy")  # what the staged Space is built from
# Run with -I -B in a fresh interpreter: the staged folder is the only place the
# two packages can come from, and every module of theirs must load.
IMPORT_CHECK = """\
import importlib, pathlib, sys
space = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(space))
names = sorted({".".join(p.relative_to(space).with_suffix("").parts).removesuffix(".__init__")
                for package in ("service", "valuescale") for p in (space / package).rglob("*.py")})
for name in names:
    importlib.import_module(name)
from valuescale import calibrated
calibrated.load()
outside = sorted(n for n, m in sys.modules.items() if n.split(".")[0] in ("service", "valuescale")
                 and getattr(m, "__file__", None) and not pathlib.Path(m.__file__).resolve().is_relative_to(space))
if outside:
    raise SystemExit("imported from outside the staged Space: " + ", ".join(outside))
print(len(names))
"""


def dockerfile_setting(name: str) -> str:
    match = re.search(rf"\b{name}=(\S+)", (HERE / "Dockerfile").read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"the Dockerfile sets no {name}")
    return match.group(1)


def runtime_files(version: str) -> tuple[list[Path], str]:
    """Every file under service/model/ that loading `version` and projecting the example open,
    and the bundle's model_version."""
    for key in [k for k in os.environ if k.startswith("VIVOME_")]:
        del os.environ[key]  # the Space uses the default paths: no override may redirect the trace
    os.environ["VIVOME_PIPELINE_VERSION"] = version
    opened: set[Path] = set()
    root = str(MODEL).lower()

    def hook(event: str, args: tuple) -> None:
        if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            path = os.path.abspath(os.fsdecode(args[0]))
            if path.lower().startswith(root):
                opened.add(Path(path))

    sys.addaudithook(hook)
    sys.path.insert(0, str(REPO))
    import warnings
    warnings.simplefilter("ignore")
    from service import config
    from service.pipeline import alignment, pipeline, validation
    if config.PIPELINE_VERSION != version:
        raise SystemExit(f"service.config picked {config.PIPELINE_VERSION}, not {version}")
    bundle = pipeline.load_bundle(version)
    raw = alignment.parse_matrix_csv(EXAMPLE.read_text(encoding="utf-8"))
    validation.validate(raw)
    for restrict in (False, True):
        pipeline.run_projection(bundle, raw, restrict_to_supported_classes=restrict)
    return sorted(p for p in opened if p.is_file()), bundle.model_version


def package_files() -> list[Path]:
    service = REPO / "service"
    files = [service / "__init__.py", service / "app.py", service / "config.py"]
    files += sorted((service / "pipeline").glob("*.py"))
    # Stage 0 reads a protein table with the raw-or-log package (B5): its
    # modules and the calibration it ships, not its tests, corpus or bank.
    valuescale = REPO / "valuescale"
    sys.path.insert(0, str(REPO))
    from valuescale import calibrated
    files += sorted(valuescale.glob("*.py"))
    files.append(calibrated.CALIBRATION_DIR / f"{calibrated.DEFAULT}.json")
    return files


def requirements() -> str:
    torch = metadata.version("torch").split("+")[0]
    lines = ["# Pinned to the interpreter that built and checked this Space (deploy/huggingface/build_space.py).",
             f"--extra-index-url {TORCH_INDEX}", f"torch=={torch}+cpu"]
    lines += [f"{name}=={metadata.version(name)}" for name in PINNED]
    return "\n".join(lines) + "\n"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def uncommitted_changes() -> bool:
    """Whether service/, valuescale/ or deploy/ holds a change not committed."""
    return bool(git("status", "--porcelain", "--", *SOURCES))


def import_check(space: Path) -> int:
    """Every staged module of service/ and valuescale/ imported from `space`
    alone, and the shipped calibration loaded, in a fresh interpreter (-I),
    writing no bytecode (-B: the folder stays as space_manifest.json lists
    it); the number of modules. A module or file left out stops the build."""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", IMPORT_CHECK, str(space)], cwd=space,
                            capture_output=True, text=True)
    if result.returncode:
        last = (result.stderr.strip().splitlines() or ["no message"])[-1]
        raise SystemExit(f"the staged Space does not import on its own: {last}")
    return int(result.stdout.split()[-1])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main(argv: "list[str] | None" = None) -> None:
    # Only --help: it says what the script does, before anything is replaced.
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args(argv)
    version = dockerfile_setting("VIVOME_PIPELINE_VERSION")
    data, model_version = runtime_files(version)
    from service import config
    if OUT.exists():
        for child in OUT.iterdir():
            if child.name != ".git":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    for source in package_files() + data:
        target = OUT / source.relative_to(REPO)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(HERE / "Dockerfile", OUT / "Dockerfile")
    card = (HERE / "space_card.md").read_text(encoding="utf-8")
    write(OUT / "README.md", card.format(
        model_version=model_version.split(" (")[0], atlas_version=config.ATLAS_VERSION,
        max_cells=f"{int(dockerfile_setting('VIVOME_MAX_UPLOAD_CELLS')):,}",
        max_upload_mb=dockerfile_setting("VIVOME_MAX_UPLOAD_MB")))
    write(OUT / "requirements.txt", requirements())
    large = sorted({p.relative_to(OUT).as_posix() for p in OUT.rglob("*")
                    if p.is_file() and ".git" not in p.relative_to(OUT).parts and p.stat().st_size > LFS_BYTES})
    write(OUT / ".gitattributes", "".join(f"{p} filter=lfs diff=lfs merge=lfs -text\n" for p in large))
    files = sorted(p for p in OUT.rglob("*") if p.is_file() and ".git" not in p.relative_to(OUT).parts)
    manifest = {
        "pipeline_version": version, "model_version": model_version, "atlas_version": config.ATLAS_VERSION,
        "commit": git("rev-parse", "HEAD"),
        "uncommitted_changes": uncommitted_changes(),
        "files": {p.relative_to(OUT).as_posix(): {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in files},
    }
    write(OUT / "space_manifest.json", json.dumps(manifest, indent=2) + "\n")
    modules = import_check(OUT)
    model_bytes = sum(p.stat().st_size for p in data)
    print(f"{version}: {len(data)} model files ({model_bytes / 2**20:.0f} MB), {len(package_files())} Python files "
          f"({modules} modules import from the staged folder alone), "
          f"{len(large)} in Git LFS; total {sum(p.stat().st_size for p in files) / 2**20:.0f} MB in "
          f"{OUT.relative_to(REPO).as_posix()}/")


if __name__ == "__main__":
    main()
