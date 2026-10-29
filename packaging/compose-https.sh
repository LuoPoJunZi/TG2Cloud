#!/bin/bash
# Offline host entry. Hashes detect changes; they are not digital signatures.
set -euo pipefail
if [[ -L "${BASH_SOURCE[0]}" ]]; then
    printf '%s\n' 'HTTPS launcher must not be a symbolic link.' >&2
    exit 1
fi
bundle_root=$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
read -r -d '' launcher <<'PY' || :
import hashlib
import json
import os
import re
import runpy
import stat
import sys
from pathlib import Path, PurePosixPath

def verify():
    if sys.version_info < (3, 10):
        raise ValueError("Python 3.10+ is required")
    root = Path(sys.argv[1])
    tools = root / "https-tools"
    if tools.is_symlink() or tools.absolute() != tools.resolve() or not tools.is_dir():
        raise ValueError("invalid HTTPS tools directory")
    manifest = tools / "manifest.json"
    if (manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_nlink != 1
            or manifest.stat().st_size > 256 * 1024):
        raise ValueError("invalid HTTPS tools manifest")
    content = manifest.read_bytes()
    if hashlib.sha256(content).hexdigest() != "@HTTPS_MANIFEST_SHA256@":
        raise ValueError("HTTPS tools manifest checksum mismatch")
    value = json.loads(content)
    if (not isinstance(value, dict) or set(value) != {"format", "files"}
            or type(value.get("format")) is not int or value["format"] != 1
            or not isinstance(value.get("files"), dict) or not value["files"]):
        raise ValueError("unsupported HTTPS tools manifest")
    files = value["files"]
    resources = {"packaging/compose/docker-compose.clouddrive2.yml",
                 "packaging/compose/docker-compose.openlist.yml"}
    for name, digest in files.items():
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or path.as_posix() != name
                or any(part in {".", ".."} for part in path.parts)
                or "\\" in name or ":" in name
                or not (name == "scripts/run_source.py" or name in resources
                        or re.fullmatch(r"src/tg2cloud/(?:[a-z_][a-z0-9_]*/)*[a-z_][a-z0-9_]*\.py", name))
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("unsafe HTTPS tools manifest")
    required = {"src/tg2cloud/__init__.py", "src/tg2cloud/version.py",
                "src/tg2cloud/compose/__init__.py", "src/tg2cloud/compose/https.py",
                "src/tg2cloud/compose/access.py"} | resources
    if not required <= files.keys():
        raise ValueError("incomplete HTTPS tools manifest")
    expected = set(files) | {"manifest.json"}
    directories = {parent.as_posix() for name in expected
                   for parent in PurePosixPath(name).parents if parent != PurePosixPath(".")}
    actual = set()
    for directory, names, leaves in os.walk(tools, followlinks=False):
        for name in names + leaves:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            relative = path.relative_to(tools).as_posix()
            if stat.S_ISLNK(mode):
                raise ValueError("HTTPS tools contain a link")
            if stat.S_ISDIR(mode):
                if relative not in directories:
                    raise ValueError("HTTPS tools contain an unknown directory")
            elif stat.S_ISREG(mode):
                if (relative not in expected or path.stat().st_nlink != 1
                        or path.stat().st_size > 2 * 1024**2):
                    raise ValueError("HTTPS tools contain an unknown or oversized file")
                actual.add(relative)
                if relative in files and hashlib.sha256(path.read_bytes()).hexdigest() != files[relative]:
                    raise ValueError("HTTPS helper checksum mismatch")
            else:
                raise ValueError("HTTPS tools contain a special file")
    if actual != expected:
        raise ValueError("HTTPS helper file set mismatch")
    return root, tools

try:
    root, tools = verify()
except (OSError, ValueError, TypeError, UnicodeError):
    print("HTTPS helper validation failed; use an intact verified Compose bundle.", file=sys.stderr)
    raise SystemExit(1)
sys.path.insert(0, str(tools / "src"))
sys.argv = ["tg2cloud.compose.https", "--root", str(root), *sys.argv[2:]]
runpy.run_module("tg2cloud.compose.https", run_name="__main__")
PY
exec python3 -I -S -B -c "$launcher" "$bundle_root" "$@"
