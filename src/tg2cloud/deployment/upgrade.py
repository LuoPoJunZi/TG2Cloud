from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from tg2cloud.deployment import instances, payload, releases


def assert_unmodified(instance: instances.Instance, old_source: Path) -> None:
    expected = payload.payload_sources(old_source, instance.product, strict=False)
    version_file = ("app/tg2cloud/version.py" if "app/tg2cloud/version.py" in expected
                    else "app/version.py" if "app/version.py" in expected else "app/__init__.py")
    if not {"app/main.py", version_file, "Dockerfile", "docker-compose.yml", "manage.sh"} <= expected.keys():
        raise ValueError("旧版缺少可验证部署清单；请使用部署器人工核对")
    for relative, source in expected.items():
        local = instance.directory / relative
        if not local.is_file() or local.resolve() != local:
            raise ValueError("现有程序缺失或经过链接：" + relative)
        # Windows EXE payloads may carry CRLF. This is not a custom code edit.
        expected_bytes = source.read_bytes().replace(b"\r\n", b"\n")
        if relative == "docker-compose.yml":
            from tg2cloud.deployment.proxy.external_config import compose_network
            from tg2cloud.deployment.proxy.external_entry import retained_network
            from tg2cloud.deployment.proxy.maintenance import PROXY_ROOT
            from tg2cloud.deployment.proxy.state import normalize_state
            record = PROXY_ROOT / "state/domains.json"
            state = {}
            if record.is_file():
                from tg2cloud.deployment.configuration import regular_private
                state = normalize_state(regular_private(record))
            network = retained_network(instance.product, instance.directory, state, PROXY_ROOT)
            if network:
                expected_bytes = compose_network(expected_bytes.decode(), instance.product.key, network).encode()
        if local.read_bytes().replace(b"\r\n", b"\n") != expected_bytes:
            raise ValueError("现有程序与已发布版本不一致，需人工核对：" + relative)
    expected_apps = {name for name in expected if name.startswith("app/")}
    actual_apps = {path.relative_to(instance.directory).as_posix() for path in (instance.directory / "app").rglob("*.py")}
    if expected_apps != actual_apps:
        raise ValueError("现有 Bot 包含额外/缺失源码；停止自动覆盖")


def action_for(instance: instances.Instance, release: releases.Release) -> str:
    if not instance.present:
        return "install"
    current, target = releases.version_tuple(instance.version), releases.version_tuple(release.version)
    if current > target:
        return "newer"
    if current == target:
        return "current"
    if current[0] != target[0]:
        raise ValueError("跨主版本升级需要人工核对迁移说明")
    return "upgrade"


def record_release(directory: Path, release: releases.Release) -> None:
    """Write identity only after successful installation, never into rollback payload."""
    target = directory / "tg2cloud-release.json"
    if target.is_symlink() or target.resolve() != target:
        raise ValueError("版本记录文件经过链接")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, prefix=".release-", delete=False) as writer:
        staged = Path(writer.name)
        try:
            os.chmod(staged, 0o600)
            json.dump({"tag": release.tag, "commit": release.commit}, writer)
            writer.write("\n")
            writer.flush()
            os.fsync(writer.fileno())
        except BaseException:
            staged.unlink(missing_ok=True)
            raise
    try:
        os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)
