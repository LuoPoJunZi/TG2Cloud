"""Regenerate both lockfiles with the same uv tool; never install dependencies."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def runtime_python(root: Path) -> str:
    """Lock Bot/development dependencies for the container, not the host CLI."""
    text = (root / "packaging/Dockerfile").read_text(encoding="utf-8")
    match = re.search(r"(?m)^FROM python:([0-9]+\.[0-9]+)(?:\.[0-9]+)?[-@]", text)
    if not match:
        raise ValueError("Dockerfile must declare an explicit Python runtime version")
    return match[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upgrade", action="store_true", help="explicit dependency update; not a structural refactor")
    args = parser.parse_args()
    python_version = runtime_python(ROOT)
    for name, extras in (("bot", ("bot",)), ("dev", ("bot", "dev"))):
        command = [sys.executable, "-m", "uv", "pip", "compile", "pyproject.toml", "--universal", "--python-version", python_version, "--generate-hashes"]
        for extra in extras:
            command.extend(("--extra", extra))
        command.extend(("--output-file", f"requirements/{name}.lock.txt"))
        if name == "dev":
            command.extend(("--constraint", "requirements/bot.lock.txt"))
        if args.upgrade:
            command.append("--upgrade")
        subprocess.run(command, cwd=ROOT, check=True, shell=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
