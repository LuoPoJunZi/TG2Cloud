"""Current runtime contexts and immutable historical fixtures; synthetic tests only."""
from __future__ import annotations

import atexit
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from tg2cloud.deployment.payload import build_payload
from tg2cloud.deployment.profiles import PRODUCTS

ROOT = Path(__file__).resolve().parents[1]
_temporary = tempfile.TemporaryDirectory(prefix="tg2cloud-test-contexts-")
atexit.register(_temporary.cleanup)


@lru_cache(maxsize=2)
def payload(edition: str) -> Path:
    destination = Path(_temporary.name) / edition
    build_payload(ROOT, PRODUCTS[edition], destination)
    return destination


def historical_file(commit: str, name: str) -> bytes:
    # The fixture uses the actual pinned helper from local Git objects, not main
    # and not a private legacy archive. No network, checkout or Git writes.
    return subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)


def historical_payload(destination: Path, edition: str) -> None:
    commit = "acce0f887c543b6df633727d1769753f328c6601"
    prefix = "payload_" + edition + "/"
    names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit, "--", prefix], cwd=ROOT).decode().splitlines()
    for name in names:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(historical_file(commit, name))
