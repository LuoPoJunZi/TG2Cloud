"""Shared current-layout Linux validation commands for branch and Tag CI."""
from __future__ import annotations

import argparse
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def commands(stage: str, root: Path = ROOT) -> list[list[str]]:
    python = sys.executable
    if stage == "shell":
        entries = ["install.sh", "install-lan.sh"]
        hooks = [path.relative_to(root).as_posix() for path in sorted((root / "packaging/hooks").glob("*/*.sh"))]
        if not hooks:
            raise ValueError("managed Shell hooks missing")
        return ([["bash", "-n", name] for name in entries]
                + [["shellcheck", *entries], ["shellcheck", "-x", *hooks,
                    "tests/manage_harness.sh", "tests/maintenance_docker_stub.sh"]])
    if stage == "test":
        return [[python, "-B", ".github/scripts/check_python.py", "test"]]
    if stage == "quality":
        return [
            [python, "-B", ".github/scripts/check_python.py", "lint"],
            [python, "-B", ".github/scripts/check_python.py", "compile"],
            [python, "-B", ".github/scripts/release_metadata.py"],
            [python, "-B", ".github/scripts/prepare_bootstrap.py"],
            [python, "-m", "bandit", "-q", "-r", "src", "scripts", ".github/scripts/source_release.py"],
            [python, "-m", "pip_audit", "-r", "requirements/bot.lock.txt"],
            [python, "-m", "pip_audit", "-r", "requirements/dev.lock.txt"],
        ]
    raise ValueError("unknown validation stage")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("shell", "test", "quality"))
    args = parser.parse_args(argv)
    for command in commands(args.stage):
        print("+ " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=ROOT, shell=False, check=False)  # nosec B603
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
