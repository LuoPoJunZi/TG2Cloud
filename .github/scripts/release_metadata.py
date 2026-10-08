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
    module = ast.parse((root / "payload_clouddrive2/app/version.py").read_text(encoding="utf-8"))
    values = [node.value.value for node in module.body
              if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
              and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)]
    if len(values) != 1 or not re.fullmatch(CORE, values[0]):
        raise ValueError("invalid single version source")
    return values[0]


def windows_resources(root: Path, version: str, *, sync: bool = False) -> None:
    numbers = tuple(map(int, version.split("."))) + (0,)
    for edition in ("CloudDrive2", "OpenList"):
        path = root / f"packaging/windows/TG2Cloud-{edition}.version.txt"
        text = path.read_text(encoding="utf-8")
        if sync:
            for key in ("filevers", "prodvers"):
                text, count = re.subn(rf"{key}=\([0-9, ]+\)", f"{key}={numbers}", text)
                if count != 1:
                    raise ValueError("invalid fixed Windows version resource")
            for key in ("FileVersion", "ProductVersion"):
                text, count = re.subn(rf"StringStruct\('{key}', '[^']+'\)", f"StringStruct('{key}', '{version}')", text)
                if count != 1:
                    raise ValueError("invalid Windows string version resource")
            path.write_text(text, encoding="utf-8", newline="\n")
        tree = ast.parse(text)
        fixed = {keyword.arg: ast.literal_eval(keyword.value)
                 for node in ast.walk(tree) if isinstance(node, ast.Call)
                 for keyword in node.keywords if keyword.arg in {"filevers", "prodvers"}}
        strings = {node.args[0].value: node.args[1].value
                   for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Name) and node.func.id == "StringStruct"
                   and len(node.args) == 2 and all(isinstance(arg, ast.Constant) for arg in node.args)}
        if fixed != {"filevers": numbers, "prodvers": numbers} or any(strings.get(key) != version for key in ("FileVersion", "ProductVersion")):
            raise ValueError(f"Windows version mismatch: {edition}")


def release_metadata(root: Path, tag: str) -> dict[str, str]:
    match = TAG.fullmatch(tag)
    version = source_version(root)
    if not match or match[1] != version:
        raise ValueError("release tag must match the source version")
    windows_resources(root, version)
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"^## TG2Cloud v{re.escape(version)}\s*$", changelog, re.MULTILINE):
        raise ValueError("current version missing from CHANGELOG")
    notes = (root / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    versions = re.findall(rf"TG2Cloud (v{CORE}(?:-(?:alpha|beta|rc)\.[1-9][0-9]*)?)", notes)
    if not versions or versions[0] != tag:
        raise ValueError("Release Notes identity must match the exact release tag")
    title = f"TG2Cloud v{version}"
    if match[2]:
        title += f" {match[2].upper()}{match[3]}"
    return {"release_tag": tag, "release_title": title,
            "release_artifact": f"TG2Cloud-{tag}-windows",
            "is_prerelease": "true" if match[2] else "false"}


def main() -> int:
    parser = argparse.ArgumentParser(description="校验版本/Windows 资源/发布文档；不会创建 Tag 或 Release")
    parser.add_argument("--tag")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--sync-windows", action="store_true")
    args = parser.parse_args()
    try:
        version = source_version(ROOT)
        windows_resources(ROOT, version, sync=args.sync_windows)
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
