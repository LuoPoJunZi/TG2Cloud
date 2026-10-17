"""Validate release identity using the Bot/deployer version source (stdlib only)."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
TAG = re.compile(rf"v({CORE})(?:-(alpha|beta|rc)\.([1-9][0-9]*))?")


def source_version(root: Path) -> str:
    current = root / "src/tg2cloud/version.py"
    path = current if current.is_file() else root / "payload_clouddrive2/app/version.py"
    module = ast.parse(path.read_text(encoding="utf-8"))
    values = [node.value.value for node in module.body
              if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
              and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)]
    if len(values) != 1 or not re.fullmatch(CORE, values[0]):
        raise ValueError("invalid single version source")
    return values[0]


def linux_entries(root: Path, version: str) -> None:
    """Release entry pins must be enabled; VPS helper identity must agree."""
    for name in ("install.sh", "install-lan.sh", "uninstall.sh"):
        text = (root / name).read_text(encoding="utf-8")
        if len(re.findall(r'^installer_commit\s*=\s*"[0-9a-f]{40}"$', text, re.MULTILINE)) != 1:
            raise ValueError(f"invalid immutable Linux entry pin: {name}")
        if name == "install.sh" and re.findall(r'^installer_version\s*=\s*"([0-9.]+)"$', text, re.MULTILINE) != [version]:
            raise ValueError("Linux entry helper version must match release source")


def release_metadata(root: Path, tag: str) -> dict[str, str]:
    match = TAG.fullmatch(tag)
    version = source_version(root)
    if not match or match[1] != version:
        raise ValueError("release tag must match the source version")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"^## TG2Cloud v{re.escape(version)}\s*$", changelog, re.MULTILINE):
        raise ValueError("current version missing from CHANGELOG")
    notes = (root / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    versions = re.findall(rf"TG2Cloud (v{CORE}(?:-(?:alpha|beta|rc)\.[1-9][0-9]*)?)", notes)
    if not versions or versions[0] != tag:
        raise ValueError("Release Notes identity must match the exact release tag")
    linux_entries(root, version)
    title = f"TG2Cloud v{version}"
    if match[2]:
        title += f" {match[2].upper()}{match[3]}"
    return {"release_tag": tag, "release_title": title,
            "release_artifact": f"TG2Cloud-{tag}-source",
            "is_prerelease": "true" if match[2] else "false"}


def main() -> int:
    parser = argparse.ArgumentParser(description="校验脚本版本和发布文档；不会创建 Tag 或 Release")
    parser.add_argument("--tag")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        version = source_version(ROOT)
        metadata = release_metadata(ROOT, args.tag) if args.tag else {"version": version}
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as handle:
                for key, value in metadata.items():
                    handle.write(f"{key}={value}\n")
        print(json.dumps(metadata, ensure_ascii=True))
        return 0
    except (ValueError, SyntaxError, OSError) as exc:
        print(f"Release metadata validation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
