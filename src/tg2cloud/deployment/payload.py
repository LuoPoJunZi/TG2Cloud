from __future__ import annotations

import re
import shutil
from pathlib import Path

from tg2cloud.deployment.compatibility import legacy_payload
from tg2cloud.deployment.fingerprints import source_files
from tg2cloud.deployment.profiles import ProductProfile


def payload_sources(root: Path, product: ProductProfile, *, strict: bool = True) -> dict[str, Path]:
    if root.is_symlink() or root.absolute() != root.resolve():
        raise ValueError("source root contains links")
    root = root.resolve()
    if not (root / "src/tg2cloud/version.py").is_file():
        return legacy_payload(root, product, strict=strict)
    result = {}
    for relative in product.required_payload:
        source = root / relative
        if not source.is_file() or source.is_symlink() or source.absolute() != source.resolve():
            if strict:
                raise ValueError("稳定版本缺少必要部署资源：" + relative)
            continue
        if relative.startswith("packaging/compat/"):
            target = relative.removeprefix("packaging/compat/")
        elif relative.startswith("packaging/compose/"):
            target = "docker-compose.yml"
        elif relative == "requirements/bot.lock.txt":
            target = "requirements.txt"
        else:
            target = Path(relative).name
        if target in result:
            raise ValueError("duplicate deployment target: " + target)
        result[target] = source
    for source in source_files(root / "src/tg2cloud"):
        target = "app/tg2cloud/" + source.relative_to(root / "src/tg2cloud").as_posix()
        if target in result:
            raise ValueError("duplicate Python target")
        result[target] = source
    return result


def build_payload(root: Path, product: ProductProfile, destination: Path) -> None:
    destination.mkdir(mode=0o700)
    for relative, source in payload_sources(root, product).items():
        target = destination / relative
        # Only manifest-selected public source enters this Docker context.
        # COPY preserves its modes, so UID 10001 needs readable files and
        # traversable subdirectories. The enclosing private directory stays
        # 0700; candidate credentials remain outside the context at 0600.
        parent = destination
        for part in Path(relative).parts[:-1]:
            parent = parent / part
            parent.mkdir(mode=0o755, exist_ok=True)
            parent.chmod(0o755)
        shutil.copyfile(source, target)
        target.chmod(0o644)
    for name in ("LICENSE", "NOTICE", "README.md"):
        if (root / name).is_file():
            shutil.copyfile(root / name, destination / name)
            (destination / name).chmod(0o644)


def gateway_image(source: Path, product: ProductProfile) -> str:
    text = payload_sources(source, product)["docker-compose.yml"].read_text(encoding="utf-8")
    images = re.findall(r"(?m)^    image: ([^\r\n]+)$", text)
    if len(images) != 1 or not re.fullmatch(r"[A-Za-z0-9_./:-]+@sha256:[0-9a-f]{64}", images[0]):
        raise ValueError("网关镜像不是可识别的固定 digest")
    return images[0]
