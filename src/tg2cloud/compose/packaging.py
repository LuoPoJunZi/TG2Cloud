"""Generate direct Compose bundles from the existing Edition resources."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

from tg2cloud.deployment.profiles import PRODUCTS
from tg2cloud.version import VERSION

IMAGE = re.compile(r"ghcr\.io/[a-z0-9_.-]+/[a-z0-9_./-]+(?::[A-Za-z0-9_.-]+)?(?:@sha256:[a-f0-9]{64})?")


def render(root: Path, edition: str, image: str) -> str:
    if not IMAGE.fullmatch(image) or (":" not in image.split("/")[-1] and "@" not in image):
        raise ValueError("use an explicit GHCR version or digest")
    product = PRODUCTS[edition]
    source = root / "packaging/compose" / ("docker-compose." + edition + ".yml")
    text = source.read_text(encoding="utf-8")
    build = "    build:\n      context: .\n      dockerfile: Dockerfile\n"
    if text.count(build) != 1:
        raise ValueError("unexpected managed Compose build definition")
    text = text.replace(build, "    image: " + image + "\n")
    text = text.replace("      - .env", "      - path: .env\n        required: false")
    text = text.replace('"127.0.0.1:', '"${TG2CLOUD_BIND_IP:-127.0.0.1}:')
    if product.is_openlist:
        text = text.replace("${OPENLIST_ADMIN_PASSWORD}", "${OPENLIST_ADMIN_PASSWORD:-}")
    # Every Edition service carries the ownership boundary; source templates
    # remain the sole source for capabilities, gateway pins and persistent paths.
    text = re.sub(r"(?m)^(  [a-z0-9-]+:)\n", r'\1\n    labels:\n      com.tg2cloud.install-mode: compose\n', text)
    tools = f"""  setup:
    image: {image}
    profiles: [tools]
    user: "0:0"
    command: ["python", "-m", "tg2cloud.compose", "setup"]
    working_dir: /workspace
    network_mode: none
    read_only: true
    cap_drop: [ALL]
    cap_add: [CHOWN, DAC_OVERRIDE, FOWNER]
    security_opt: ["no-new-privileges:true"]
    tmpfs: ["/tmp:rw,noexec,nosuid,size=64m"]
    volumes:
      - ./:/workspace
      - ./backups:/backups
    restart: "no"

"""
    return text.replace("\nnetworks:\n", "\n" + tools + "networks:\n")


def bundle_files(root: Path, edition: str, image: str, commit: str = "") -> dict[str, bytes]:
    if commit and not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid source commit")
    metadata = {"format": 1, "mode": "compose", "edition": edition,
                "version": VERSION, "image": image, "commit": commit}
    return {
        "docker-compose.yml": render(root, edition, image).encode(),
        "compose-bundle.json": (json.dumps(metadata, indent=2) + "\n").encode(),
        ".env.example": b"# Run the setup service to generate the private .env. Do not put secrets here.\nTG2CLOUD_BIND_IP=127.0.0.1\n",
        "README.md": (root / "docs/COMPOSE.md").read_bytes(),
        "LICENSE": (root / "LICENSE").read_bytes(),
    }


def build_bundles(root: Path, output: Path, image: str, commit: str = "") -> list[Path]:
    output.mkdir(parents=True, exist_ok=False)
    archives = []
    for edition in PRODUCTS:
        name = f"TG2Cloud-v{VERSION}-compose-{edition}"
        directory = output / edition
        directory.mkdir()
        files = bundle_files(root, edition, image, commit)
        archive = output / (name + ".tar.gz")
        with archive.open("wb") as out, gzip.GzipFile(fileobj=out, mode="wb", filename="", mtime=0) as zipped, tarfile.open(fileobj=zipped, mode="w") as tar:
            for relative, content in files.items():
                (directory / relative).write_bytes(content)
                info = tarfile.TarInfo(name + "/" + relative)
                info.size, info.mode, info.mtime = len(content), 0o644, 0
                tar.addfile(info, io.BytesIO(content))
        archives.append(archive)
    (output / "COMPOSE-SHA256SUMS.txt").write_text("".join(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n" for path in archives
    ), encoding="ascii")
    return archives
