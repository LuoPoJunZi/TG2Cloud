"""Static historical layout adapter. Never import downloaded release code."""
from __future__ import annotations

import ast
from pathlib import Path, PurePosixPath


def version_path(root: Path) -> tuple[Path, str]:
    for relative, name in (
        ("src/tg2cloud/version.py", "VERSION"),
        ("app/tg2cloud/version.py", "VERSION"),
        ("app/version.py", "VERSION"),
        ("app/__init__.py", "__version__"),
        ("payload_clouddrive2/app/version.py", "VERSION"),
        ("payload_clouddrive2/app/__init__.py", "__version__"),
    ):
        path = root / relative
        if path.is_symlink():
            raise ValueError("version file is linked")
        if path.is_file():
            return path, name
    raise ValueError("no recognized version source")


def literal_version(root: Path) -> str:
    path, name = version_path(root)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = [node.value.value for node in tree.body
              if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
              and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    if len(values) != 1 or not isinstance(values[0], str):
        raise ValueError("invalid literal version source")
    return values[0]


def _strings(node, values):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(_strings(item, values) for item in node.elts)
    if isinstance(node, ast.Name) and node.id in values:
        return values[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _strings(node.left, values) + _strings(node.right, values)
    raise ValueError("unsupported historical manifest expression")


def legacy_manifest(root: Path, edition: str) -> tuple[str, ...]:
    for relative in ("scripts/lib/deployer_products.py", "deployer_products.py"):
        path = root / relative
        if not path.is_file():
            continue
        if path.is_symlink():
            raise ValueError("historical manifest is linked")
        values = {}
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.Assign):
                continue
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "ProductProfile":
                keywords = {item.arg: item.value for item in node.value.keywords}
                key = keywords.get("key")
                if isinstance(key, ast.Constant) and key.value == edition:
                    result = _strings(keywords["required_payload"], values)
                    if not isinstance(result, tuple) or not result:
                        raise ValueError("empty historical manifest")
                    return result
            else:
                try:
                    value = _strings(node.value, values)
                except ValueError:
                    continue
                for name in node.targets:
                    if isinstance(name, ast.Name):
                        values[name.id] = value
        raise ValueError("historical Edition manifest cannot be verified")
    # Old pre-profile sources: require the actual shared app and selected hooks.
    # These roots must still come from a resolved official stable tag, never main.
    shared = root / "payload_clouddrive2"
    variant = root / ("payload_" + edition)
    names = [path.relative_to(root).as_posix() for path in (shared / "app").rglob("*.py")]
    for name in ("Dockerfile", "requirements.txt", ".dockerignore", "backup_retention.sh", "preserve_runtime_config.sh"):
        if (shared / name).is_file():
            names.append((shared / name).relative_to(root).as_posix())
    for path in variant.glob("*"):
        if path.is_file() and (path.suffix == ".sh" or path.name == "docker-compose.yml"):
            names.append(path.relative_to(root).as_posix())
    return tuple(names)


def legacy_payload(root: Path, product, *, strict: bool = True) -> dict[str, Path]:
    result = {}
    for name in legacy_manifest(root, product.key):
        if not isinstance(name, str):
            raise ValueError("invalid historical payload path")  # noqa: TRY004 - invalid archive metadata, not an API type contract
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or path.parts[0] not in {"payload_clouddrive2", "payload_openlist"}:
            raise ValueError("unsafe historical payload path")
        source = root / name
        if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            if strict:
                raise ValueError("historical payload file missing: " + name)
            continue
        result[str(path.relative_to(path.parts[0]))] = source
    if not {"app/main.py", "Dockerfile", "docker-compose.yml", "manage.sh"} <= result.keys():
        raise ValueError("historical payload lacks verifiable minimum inputs")
    return result
