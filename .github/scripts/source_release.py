"""Build/verify one immutable source artifact; never deploy or publish anything."""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import re
import shutil
import subprocess  # nosec B404
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
TAG = re.compile(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.[1-9][0-9]*)?")
LIMIT = 100 * 1024 * 1024
REQUIRED = {
    "install.sh", "install-lan.sh", "uninstall.sh", "LICENSE",
    "scripts/vps_installer.py", "scripts/lan_installer.py", "scripts/uninstaller.py",
    "scripts/vps_runtime.py", "scripts/__init__.py", "scripts/lib/__init__.py",
    "scripts/lib/deployer_products.py", "scripts/lib/vps_resources.py",
    "scripts/lib/domain_proxy.py", "scripts/lib/proxy_maintenance.py",
    "payload_clouddrive2/app/version.py", "payload_clouddrive2/app/main.py",
    "payload_clouddrive2/Dockerfile", "payload_clouddrive2/requirements.txt",
    "payload_clouddrive2/remote_install.sh", "payload_openlist/remote_install.sh",
    "payload_clouddrive2/docker-compose.yml", "payload_openlist/docker-compose.yml",
    "assets/brand/tg2cloud-logo.svg",
}


def git(root: Path, *args: str) -> bytes:
    executable = shutil.which("git")
    if executable is None:
        raise ValueError("Git is required")
    return subprocess.check_output([executable, "-C", str(root), *args], shell=False)  # nosec B603


def artifact_name(tag: str) -> str:
    if not TAG.fullmatch(tag):
        raise ValueError("invalid release tag")
    return f"TG2Cloud-{tag}-source.tar.gz"


def validate_pins(root: Path, commit: str) -> None:
    """Catch a new release accidentally shipping old online wizard code."""
    for entry in ("install.sh", "install-lan.sh", "uninstall.sh"):
        text = git(root, "show", f"{commit}:{entry}").decode("utf-8")
        pins = re.findall(r'^installer_commit\s*=\s*"([0-9a-f]{40})"$', text, re.MULTILINE)
        if len(pins) != 1:
            raise ValueError(f"missing immutable helper pin: {entry}")
        paths = []
        for block in re.findall(r"<<'PY'[^\n]*\n(.*?)^PY\s*$", text, re.MULTILINE | re.DOTALL):
            for node in ast.walk(ast.parse(block)):
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "files" for t in node.targets):
                    paths.extend(ast.literal_eval(node.value))
        if not paths or any(not isinstance(name, str) or not safe_path(name) for name in paths):
            raise ValueError(f"invalid bootstrap input list: {entry}")
        for name in paths:
            pinned = git(root, "show", f"{pins[0]}:{name}").replace(b"\r\n", b"\n")
            target = git(root, "show", f"{commit}:{name}").replace(b"\r\n", b"\n")
            if pinned != target:
                raise ValueError(f"stale bootstrap helper: {entry}: {name}; commit helpers, then update pins before tagging")


def safe_path(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and not any(part in {"..", ".git"} for part in path.parts) and "\\" not in name and ":" not in name


def verify(directory: Path, tag: str) -> None:
    name = artifact_name(tag)
    if {path.name for path in directory.iterdir()} != {name, "SHA256SUMS.txt"}:
        raise ValueError("unexpected source release asset set")
    archive = directory / name
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > LIMIT:
        raise ValueError("invalid source archive")
    data = archive.read_bytes()
    expected = hashlib.sha256(data).hexdigest() + "  " + name + "\n"
    if (directory / "SHA256SUMS.txt").read_text(encoding="ascii") != expected:
        raise ValueError("source archive SHA256 mismatch")
    files = {}
    total = 0
    prefix = f"TG2Cloud-{tag}/"
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as bundle:
        seen = set()
        for member in bundle:
            if member.name in seen or len(seen) >= 5000:
                raise ValueError("duplicate/too many source archive members")
            seen.add(member.name)
            if member.isdir() and member.name == prefix.rstrip("/"):
                continue
            if not member.name.startswith(prefix) or not safe_path(member.name) or not (member.isfile() or member.isdir()):
                raise ValueError("unsafe source archive member")
            if member.isdir():
                continue
            total += member.size
            if total > LIMIT:
                raise ValueError("source archive exceeds uncompressed limit")
            relative = member.name[len(prefix):]
            if relative.lower().endswith((".exe", ".pyc")) or any(part in {"build", "dist", ".venv", "__pycache__", "legacy"} for part in PurePosixPath(relative).parts):
                raise ValueError("build output in source archive")
            files[relative] = bundle.extractfile(member).read()
    if not REQUIRED.issubset(files):
        raise ValueError("source archive missing required Linux inputs")
    # Verify all declared Edition payload inputs, not just a hand-maintained list.
    tree = ast.parse(files["scripts/lib/deployer_products.py"].decode("utf-8"))
    payloads = {node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
                and node.value.startswith(("payload_clouddrive2/", "payload_openlist/"))}
    if not all(any(path.startswith(edition + "/") for path in payloads) for edition in ("payload_clouddrive2", "payload_openlist")):
        raise ValueError("both Edition payload manifests are required")
    if not payloads.issubset(files):
        raise ValueError("missing Edition payload inputs: " + ", ".join(sorted(payloads - files.keys())))
    versions = [ast.literal_eval(node.value) for node in ast.parse(files["payload_clouddrive2/app/version.py"].decode("utf-8")).body
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in node.targets)]
    if versions != [tag[1:].split("-", 1)[0]]:
        raise ValueError("source archive version mismatch")
    for path, content in files.items():
        if path.endswith(".py"):
            ast.parse(content.decode("utf-8"), filename=path)


def build(root: Path, directory: Path, tag: str) -> None:
    name = artifact_name(tag)
    commit = git(root, "rev-parse", f"refs/tags/{tag}^{{commit}}").decode().strip()
    if git(root, "rev-parse", "HEAD").decode().strip() != commit:
        raise ValueError("checkout must match the release tag")
    if git(root, "diff", "HEAD", "--name-only"):
        raise ValueError("tracked source changes must be committed before packaging")
    validate_pins(root, commit)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("output directory must be empty; refusing to replace artifacts")
    archive = git(root, "archive", "--format=tar", f"--prefix=TG2Cloud-{tag}/", commit)
    if len(archive) > LIMIT:
        raise ValueError("source archive too large")
    data = gzip.compress(archive, mtime=0)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / name).open("xb") as writer:
        writer.write(data)
    with (directory / "SHA256SUMS.txt").open("x", encoding="ascii", newline="\n") as writer:
        writer.write(hashlib.sha256(data).hexdigest() + "  " + name + "\n")
    verify(directory, tag)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "build":
            build(ROOT, args.directory, args.tag)
        else:
            verify(args.directory, args.tag)
        print("SOURCE_RELEASE_" + args.action.upper() + "=OK")
        return 0
    except (ValueError, OSError, SyntaxError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        print("Source release validation failed: " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
