"""Versioned code identity shared by deployment and the running container.

V1 is restricted to historical flat app packages. V2 includes relative paths
and every nested Python source. This module also runs directly on the host.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

V2_PREFIX = "tg2cloud-code-v2:sha256:"


def source_files(root: Path) -> tuple[Path, ...]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("managed source directory missing")
    paths = []
    for path in root.rglob("*"):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("managed source contains links")
        if path.suffix == ".py":
            if not path.is_file():
                raise ValueError("managed source is not a regular file")
            paths.append(path)
    if not paths:
        raise ValueError("managed source is empty")
    return tuple(sorted(paths, key=lambda path: path.relative_to(root).as_posix()))


def fingerprint(root: Path, *, legacy: bool = False) -> str:
    if root.is_symlink() or root.absolute() != root.resolve():
        raise ValueError("managed source root contains links")
    root = root.resolve()
    paths = source_files(root)
    if legacy and any(path.parent != root for path in paths):
        raise ValueError("legacy fingerprint cannot cover nested or unknown code")
    manifest = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  app/{path.relative_to(root).as_posix()}\n"
                       for path in paths)
    value = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    return value if legacy else V2_PREFIX + value


def deployed_fingerprint(app: Path) -> str:
    # Marker is part of the managed code, not an untrusted operator flag.
    current = app / "tg2cloud/deployment/fingerprints.py"
    return fingerprint(app, legacy=not current.is_file())


def code_fingerprint() -> str:
    return fingerprint(Path(__file__).resolve().parents[2])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only recursive managed code fingerprint")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    print(fingerprint(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
