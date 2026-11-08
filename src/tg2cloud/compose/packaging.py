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
from tg2cloud.deployment.runtime import files as host_files
from tg2cloud.version import VERSION

IMAGE = re.compile(r"ghcr\.io/[a-z0-9_.-]+/[a-z0-9_./-]+(?::[A-Za-z0-9_.-]+)?(?:@sha256:[a-f0-9]{64})?")

# Compose reads .env on the host; only Bot settings enter the Bot process.
# In particular, never grant the Bot the gateway's bootstrap admin password.
BOT_ENVIRONMENT = (
    "TELEGRAM_API_ID", "TELEGRAM_API_HASH_B64", "BOT_TOKEN_B64", "ALLOWED_USER_ID",
    "WEBDAV_URL_B64", "WEBDAV_USERNAME_B64", "WEBDAV_PASSWORD_B64", "WEBDAV_TARGET_PATH_B64",
    "CD2_WEBDAV_URL_B64", "CD2_WEBDAV_USERNAME_B64", "CD2_WEBDAV_PASSWORD_B64", "CD2_TARGET_PATH_B64",
    "TG2CLOUD_STORAGE_BACKEND", "TG115_STORAGE_BACKEND", "TG2CLOUD_RCLONE_REMOTE_NAME", "TG115_RCLONE_REMOTE_NAME",
    "LOCAL_TEMP_BUDGET_GB", "MIN_FREE_DISK_GB", "CONTROL_INTERVAL_SECONDS",
    "CPU_TARGET_LOW_PERCENT", "CPU_TARGET_HIGH_PERCENT", "CPU_PRESSURE_PERCENT",
    "MEMORY_SOFT_MIN_MB", "MEMORY_HARD_MIN_MB", "RAMP_UP_STEP", "RAMP_DOWN_FACTOR",
    "MAX_RETRIES", "REMOTE_HEALTH_INTERVAL_SECONDS", "TZ",
)
BOT_DEFAULTS = {
    "LOCAL_TEMP_BUDGET_GB": "20", "MIN_FREE_DISK_GB": "8", "CONTROL_INTERVAL_SECONDS": "3",
    "CPU_TARGET_LOW_PERCENT": "60", "CPU_TARGET_HIGH_PERCENT": "80", "CPU_PRESSURE_PERCENT": "90",
    "MEMORY_SOFT_MIN_MB": "1024", "MEMORY_HARD_MIN_MB": "512", "RAMP_UP_STEP": "1",
    "RAMP_DOWN_FACTOR": "0.5", "MAX_RETRIES": "3", "REMOTE_HEALTH_INTERVAL_SECONDS": "30",
    "TZ": "Asia/Shanghai",
}


def https_tools(root: Path) -> dict[str, bytes]:
    """Package only the verified shared host helpers and Compose source/resources."""
    helpers = host_files(root)
    manifest = json.loads((root / "packaging/bootstrap-manifest.json").read_bytes())
    if (not isinstance(manifest, dict) or set(manifest) != {"format", "files"}
            or type(manifest.get("format")) is not int or manifest["format"] != 1
            or manifest.get("files") != sorted(helpers)):
        raise ValueError("invalid or stale bootstrap source manifest")
    selected = dict(helpers)
    selected.update({path.relative_to(root).as_posix(): b""
                     for path in (root / "src/tg2cloud/compose").rglob("*.py")})
    selected.update({"packaging/compose/docker-compose." + edition + ".yml": b"" for edition in PRODUCTS})
    for name in selected:
        path = root / name
        if (path.is_symlink() or path.absolute() != path.resolve() or not path.is_file()
                or path.stat().st_nlink != 1
                or path.stat().st_size > 2 * 1024**2):
            raise ValueError("HTTPS helper source missing, oversized or contains a link")
        selected[name] = path.read_bytes()
    if not {"src/tg2cloud/compose/https.py", "src/tg2cloud/compose/access.py"} <= selected.keys():
        raise ValueError("HTTPS host helper source missing")
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in sorted(selected.items())}
    content = (json.dumps({"format": 1, "files": hashes}, indent=2) + "\n").encode()
    launcher = root / "packaging/compose-https.sh"
    if launcher.is_symlink() or launcher.absolute() != launcher.resolve() or not launcher.is_file():
        raise ValueError("HTTPS launcher missing or contains a link")
    template = launcher.read_bytes().replace(b"\r\n", b"\n")
    placeholder = b"@HTTPS_MANIFEST_SHA256@"
    if template.count(placeholder) != 1:
        raise ValueError("unexpected HTTPS launcher template")
    launcher_body = template.replace(placeholder, hashlib.sha256(content).hexdigest().encode())
    result = {"https.sh": launcher_body,
              "manage.sh": launcher_body.replace(b"tg2cloud.compose.https", b"tg2cloud.compose.management"),
              "https-tools/manifest.json": content}
    result.update({"https-tools/" + name: body for name, body in sorted(selected.items())})
    return result


def render(root: Path, edition: str, image: str, *, legacy: bool = False) -> str:
    if not IMAGE.fullmatch(image) or (":" not in image.split("/")[-1] and "@" not in image):
        raise ValueError("use an explicit GHCR version or digest")
    product = PRODUCTS[edition]
    source = root / "packaging/compose" / ("docker-compose." + edition + ".yml")
    text = source.read_text(encoding="utf-8")
    build = "    build:\n      context: .\n      dockerfile: Dockerfile\n"
    if text.count(build) != 1:
        raise ValueError("unexpected managed Compose build definition")
    text = text.replace(build, "    image: " + image + "\n")
    if legacy:
        text = text.replace("      - .env", "      - path: .env\n        required: false")
    else:
        defaults = dict(BOT_DEFAULTS, TG2CLOUD_STORAGE_BACKEND=product.key,
                        TG2CLOUD_RCLONE_REMOTE_NAME="openlist" if product.is_openlist else "cd2")
        injection = "".join(f"      {key}: ${{{key}:-{defaults.get(key, '')}}}\n" for key in BOT_ENVIRONMENT)
        text = text.replace("    env_file:\n      - .env\n    environment:\n", "    environment:\n" + injection)
    text = text.replace('"127.0.0.1:', '"${TG2CLOUD_BIND_IP:-127.0.0.1}:')
    if product.is_openlist:
        text = text.replace("${OPENLIST_ADMIN_PASSWORD}", "${OPENLIST_ADMIN_PASSWORD:-}")
    if not legacy:
        bot_header = "  " + product.bot_service + ":\n"
        text = text.replace(bot_header, bot_header + '    pids_limit: ${TG2CLOUD_BOT_PIDS_LIMIT:-256}\n'
                            + '    mem_limit: ${TG2CLOUD_BOT_MEMORY_LIMIT:-0}\n'
                            + '    cpus: ${TG2CLOUD_BOT_CPUS:-0}\n')
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
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    restart: "no"

"""
    return text.replace("\nnetworks:\n", "\n" + tools + "networks:\n")


def bundle_files(root: Path, edition: str, image: str, commit: str = "") -> dict[str, bytes]:
    if commit and not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid source commit")
    metadata = {"format": 3, "https_tools": 1, "mode": "compose", "edition": edition,
                "version": VERSION, "image": image, "commit": commit}
    return {
        "docker-compose.yml": render(root, edition, image).encode(),
        "compose-bundle.json": (json.dumps(metadata, indent=2) + "\n").encode(),
        ".env.example": b"# Run the setup service to generate the private .env. Do not put secrets here.\nTG2CLOUD_BIND_IP=127.0.0.1\n",
        "README.md": (root / "docs/COMPOSE.md").read_bytes(),
        "LICENSE": (root / "LICENSE").read_bytes(),
        **https_tools(root),
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
                target = directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                info = tarfile.TarInfo(name + "/" + relative)
                mode = 0o755 if relative in {"https.sh", "manage.sh"} else 0o644
                target.chmod(mode)
                info.size, info.mode, info.mtime = len(content), mode, 0
                tar.addfile(info, io.BytesIO(content))
        archives.append(archive)
    (output / "COMPOSE-SHA256SUMS.txt").write_text("".join(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n" for path in archives
    ), encoding="ascii")
    return archives
