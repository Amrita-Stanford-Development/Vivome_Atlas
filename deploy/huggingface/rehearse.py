"""Rehearses a deploy of the projection service on this machine: starts it
with the hosted image's settings (the ENV lines of this folder's Dockerfile),
listening on 127.0.0.1 only and without the website's secret, runs
check_space.py against it, and stops it. Its exit status is check_space's: 0
when every cell's answer matches this repository's own run.

It checks this repository's code with the hosted settings, not the image:
run build_space.py and the deploy after it, then check_space.py against the
live service (PUBLISH.md).

    python deploy/huggingface/rehearse.py      # from the repository root
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DOCKERFILE = HERE / "Dockerfile"


def hosted_env(dockerfile: Path = DOCKERFILE) -> dict[str, str]:
    """The Dockerfile's ENV settings (KEY=value, continued lines joined)."""
    text = re.sub(r"\\[ \t]*\r?\n", " ", dockerfile.read_text(encoding="utf-8"))
    env: dict[str, str] = {}
    for line in text.splitlines():
        if line.strip().startswith("ENV "):
            for key, value in re.findall(r"(\w+)=(\S+)", line.strip()[4:]):
                env[key] = value
    return env


def rehearsal_env(port: int, base: "dict[str, str] | None" = None) -> dict[str, str]:
    """This environment with the hosted settings, on 127.0.0.1:port, without
    the website's secret (the local copy answers check_space directly)."""
    env = {**(os.environ if base is None else base), **hosted_env(),
           "VIVOME_HOST": "127.0.0.1", "VIVOME_PORT": str(port)}
    env.pop("VIVOME_PROXY_SECRET", None)
    return env


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until_ready(base: str, server: subprocess.Popen, seconds: float = 300) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if server.poll() is not None:
            raise SystemExit(f"the service stopped before it was ready (exit {server.returncode})")
        try:
            with urllib.request.urlopen(f"{base}/api/status", timeout=5) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1)
    raise SystemExit(f"the service was not ready within {seconds:.0f} s")


def main() -> int:
    port = free_port()
    env = rehearsal_env(port)
    base = f"http://127.0.0.1:{port}"
    print(f"rehearsal: the service with the hosted settings on {base}")
    server = subprocess.Popen([sys.executable, "-m", "service.app"], cwd=REPO, env=env)
    try:
        wait_until_ready(base, server)
        return subprocess.call([sys.executable, str(HERE / "check_space.py"), base], cwd=REPO, env=env)
    finally:
        server.terminate()
        server.wait(timeout=60)


if __name__ == "__main__":
    sys.exit(main())
