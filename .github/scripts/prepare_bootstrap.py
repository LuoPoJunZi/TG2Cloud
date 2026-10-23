"""Prepare unpublished new-layout bootstrap candidates; never change live pins."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def helper_files(root: Path) -> list[str]:
    paths = ["scripts/run_source.py", "src/tg2cloud/__init__.py", "src/tg2cloud/version.py", "src/tg2cloud/config.py"]
    if (root / "src/tg2cloud/deployment/backup.py").is_file() or (root / "src/tg2cloud/cli/naming.py").is_file():
        paths.extend("src/tg2cloud/" + name for name in (
            "persistence/__init__.py", "persistence/backup.py", "persistence/bundle.py",
            "domain/__init__.py", "domain/naming.py"))
    for directory in ("cli", "deployment", "addons"):
        for path in (root / "src/tg2cloud" / directory).rglob("*.py"):
            if path.is_symlink() or path.absolute() != path.resolve():
                raise ValueError("helper source contains a link")
            paths.append(path.relative_to(root).as_posix())
    for name in paths:
        path = root / name
        if not path.is_file() or path.is_symlink() or path.absolute() != path.resolve():
            raise ValueError("helper source missing or contains a link")
    return sorted(set(paths))


def runtime_files(root: Path) -> list[str]:
    paths = []
    for path in (root / "src/tg2cloud").rglob("*.py"):
        if path.is_symlink() or path.absolute() != path.resolve():
            raise ValueError("runtime source contains a link")
        paths.append(path.relative_to(root).as_posix())
    return sorted(paths)


def render_entry(root: Path, name: str) -> str:
    text = (root / name).read_text(encoding="utf-8")
    start = text.index("<<'PY' &\n") + len("<<'PY' &\n")
    end = text.index("\nPY\n", start)
    block = text[start:end]
    nodes = [node for node in ast.walk(ast.parse(block)) if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == "files" for target in node.targets)]
    if len(nodes) != 1:
        raise ValueError("one explicit bootstrap manifest is required")
    node = nodes[0]
    lines = block.splitlines()
    indentation = " " * node.col_offset
    replacement = indentation + "files = (\n" + "".join(indentation + "    " + repr(path) + ",\n" for path in helper_files(root)) + indentation + ")"
    lines[node.lineno-1:node.end_lineno] = replacement.splitlines()
    block = "\n".join(lines).replace("payload_clouddrive2/app/version.py", "src/tg2cloud/version.py")
    result = text[:start] + block + text[end:]
    command = {"install.sh": "install", "install-lan.sh": "lan", "uninstall.sh": "uninstall"}[name]
    module = {"install.sh": "scripts.vps_installer", "install-lan.sh": "scripts.lan_installer", "uninstall.sh": "scripts.uninstaller"}[name]
    # Only the post-download launch changes. Legacy local-source compatibility
    # branches and the existing real immutable pin remain untouched.
    return result.replace(f'python3 -B -m {module} "$@" &', f'python3 -B scripts/run_source.py {command} "$@" &')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    for name, files in (("bootstrap", helper_files(ROOT)), ("runtime", runtime_files(ROOT))):
        manifest = {"format": 1, "files": files}
        path = ROOT / f"packaging/{name}-manifest.json"
        if args.write_manifest:
            path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        elif json.loads(path.read_text(encoding="utf-8")) != manifest:
            raise ValueError(f"{name} manifest stale; regenerate after reviewing added source files")
    if args.directory:
        args.directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        for name in ("install.sh", "install-lan.sh", "uninstall.sh"):
            (args.directory / name).write_text(render_entry(ROOT, name), encoding="utf-8", newline="\n")
        print("CANDIDATE_ONLY: existing pins retained; publish/review helper commit A before setting pins in B")
    print("BOOTSTRAP_MANIFEST=OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
