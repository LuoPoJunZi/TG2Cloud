"""Read-only public-file, build-input and document-index checks (stdlib only)."""

from __future__ import annotations

import ast
import re
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
BUILD_FILES = (
    "legacy/desktop/build.ps1", "legacy/desktop/requirements-build.txt", ".github/scripts/release_metadata.py",
    "legacy/desktop/installer.py", "legacy/desktop/installer_clouddrive2.py", "legacy/desktop/installer_openlist.py",
    "deployer_products.py", "domain_proxy.py", "legacy/desktop/operation_feedback.py",
    "proxy_maintenance.py", "vps_resources.py",
    "legacy/desktop/packaging/windows/TG2Cloud-CloudDrive2.version.txt",
    "legacy/desktop/packaging/windows/TG2Cloud-OpenList.version.txt",
    "assets/brand/tg2cloud.ico", "assets/brand/tg2cloud-logo.svg",
    "assets/brand/tg2cloud-icon-256.png",
)
LOCAL_DIRECTORIES = frozenset({
    "build", "dist", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", ".hypothesis", ".tox", ".nox", ".venv", "venv", "htmlcov", ".codex",
})
INTERNAL_FILES = frozenset({
    "agents.md", "agents_old.md", "qa_report.md", "tg2cloud-codex-kickoff-prompt.md",
    "tg2cloud-v1.0.0-release-checklist.md",
})
PRIVATE_EXTENSIONS = frozenset({
    ".exe", ".pyc", ".pyo", ".spec", ".db", ".sqlite", ".sqlite3", ".session", ".log",
    ".pem", ".key", ".p12", ".pfx", ".csr", ".crt", ".tmp", ".bak", ".swp",
})
LOCAL_FILES = frozenset({
    ".coverage", "coverage.xml", ".ds_store", "thumbs.db", "desktop.ini", "rclone.conf",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
})
LINK = re.compile(r'(?<!!)\[[^\]]*\]\((<[^>]+>|[^)\s]+)(?:\s+"[^"]*")?\)')


def public_files(root: Path) -> list[str]:
    # NUL-delimited paths preserve spaces and Chinese names. No Git writes or network.
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("Git is required for repository inventory")
    result = subprocess.run(  # nosec B603
        [git, "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--"],
        capture_output=True, text=True, encoding="utf-8", check=True, shell=False,
    )
    return sorted({path for path in result.stdout.split("\0") if path})


def forbidden_reason(name: str) -> str | None:
    path = PurePosixPath(name)
    parts = tuple(part.casefold() for part in path.parts)
    basename = path.name.casefold()
    if path.is_absolute() or ".." in parts or "\\" in name or re.match(r"^[a-zA-Z]:", name):
        return "invalid repository-relative path"
    if any(part in LOCAL_DIRECTORIES for part in parts[:-1]):
        return "generated output, cache or local development directory"
    if basename in INTERNAL_FILES or name.casefold() in {"docs/audit.md", "docs/worklog.md"}:
        return "local-only internal development record"
    if (basename == ".env" or basename.startswith(".env.")) and basename != ".env.example":
        return "local environment configuration"
    if path.suffix.casefold() in PRIVATE_EXTENSIONS or basename in LOCAL_FILES:
        return "binary output, runtime data, temporary file or private configuration"
    if basename.startswith(".coverage.") or basename.endswith((
        ".db-shm", ".db-wal", ".db-journal", ".sqlite-shm", ".sqlite-wal", ".sqlite-journal",
        ".sqlite3-shm", ".sqlite3-wal", ".sqlite3-journal",
    )):
        return "coverage or database sidecar"
    return None


def payload_files(root: Path) -> set[str]:
    # Inspect literal paths in product definitions without importing runtime modules.
    tree = ast.parse((root / "deployer_products.py").read_text(encoding="utf-8"))
    paths = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value.startswith(("payload_clouddrive2/", "payload_openlist/"))
    }
    if not any(path.startswith("payload_clouddrive2/") for path in paths) or not any(path.startswith("payload_openlist/") for path in paths):
        raise ValueError("both product payload manifests must contain literal paths")
    return paths


def check_build_inputs(root: Path, files: list[str]) -> list[str]:
    errors: list[str] = []
    candidate_files = set(files)
    required = set(BUILD_FILES)
    product_path = root / "deployer_products.py"
    if product_path.is_file() and not product_path.is_symlink():
        try:
            required.update(payload_files(root))
        except (OSError, SyntaxError, UnicodeError, ValueError):
            errors.append("deployer_products.py: cannot inspect both payload manifests")
    for name in sorted(required):
        path = root / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            errors.append(f"{name}: required build input missing or not a repository-local regular file")
        elif name not in candidate_files:
            errors.append(f"{name}: required build input excluded from the public file set")
    return errors


def check_document_index(root: Path, files: list[str]) -> list[str]:
    index = root / "docs/README.md"
    if not index.is_file() or index.is_symlink() or not index.resolve().is_relative_to(root):
        return ["docs/README.md: missing repository-local document index"]
    try:
        text = index.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ["docs/README.md: cannot read UTF-8 document index"]
    candidate_files = set(files)
    linked: set[str] = set()
    errors: list[str] = []
    for match in LINK.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        try:
            url = urlsplit(match[1].strip("<>"))
            if url.scheme in {"https", "http", "mailto"}:
                continue
            if url.scheme or url.netloc:
                raise ValueError("non-relative file link")
            if not url.path:
                continue  # In-page anchors are outside the file-target check.
            target = (index.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                raise ValueError("missing or outside repository")
            relative = target.relative_to(root).as_posix()
            if forbidden_reason(relative) or relative not in candidate_files:
                raise ValueError("local-only or excluded target")
            linked.add(relative)
        except (OSError, ValueError):
            # Never echo document content or a possible local absolute path.
            errors.append(f"docs/README.md:{line}: invalid, missing or non-public file target")
    for name in files:
        if (name.startswith("docs/") and name.endswith(".md") and name != "docs/README.md"
                and not forbidden_reason(name) and name not in linked):
            errors.append(f"{name}: public document missing from docs/README.md")
    return errors


def validate_repository(root: Path, files: list[str]) -> list[str]:
    root = root.resolve()
    errors = [f"{name}: {reason}" for name in files if (reason := forbidden_reason(name))]
    errors.extend(check_build_inputs(root, files))
    errors.extend(check_document_index(root, files))
    return errors


def main() -> int:
    try:
        files = public_files(ROOT)
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        print("Repository check failed: Git public-file inventory unavailable; use a complete Git checkout.", file=sys.stderr)
        return 1
    errors = validate_repository(ROOT, files)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"Repository check PASS: {len(files)} tracked/unignored candidate files; build inputs and document index OK.")
    print("Read-only path checks only; not a secret-content scan, EXE build or VPS acceptance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
