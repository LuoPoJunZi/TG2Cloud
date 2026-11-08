"""Compose resource settings and private backup operations; stdlib host only."""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import shutil
import subprocess  # nosec B404
import tempfile
from pathlib import Path

from tg2cloud.cli.management import choose
from tg2cloud.cli.presentation import numbered_menu
from tg2cloud.compose import runtime
from tg2cloud.compose.https import owned_file
from tg2cloud.deployment import backup
from tg2cloud.deployment.host import edition_lock
from tg2cloud.persistence import bundle


def validate_resources(config):
    memory = config.get("TG2CLOUD_BOT_MEMORY_LIMIT", "0")
    if not re.fullmatch(r"0|[1-9][0-9]{0,7}[mMgG]", memory):
        raise ValueError("内存限制使用 0 或正整数加 M/G；0 表示不限制")
    if memory != "0":
        amount = int(memory[:-1]) * (1024 if memory[-1].lower() == "g" else 1)
        if amount < int(config.get("MEMORY_HARD_MIN_MB", "512")) + 256:
            raise ValueError("容器内存上限至少高于下载保护门槛 256MiB；请勿降低保护来迁就过小限制")
    pids = config.get("TG2CLOUD_BOT_PIDS_LIMIT", "256")
    if not re.fullmatch(r"[1-9][0-9]{1,4}", pids) or not 32 <= int(pids) <= 65536:
        raise ValueError("Bot 进程数限制须为 32～65536")
    cpu = float(config.get("TG2CLOUD_BOT_CPUS", "0"))
    if not math.isfinite(cpu) or not 0 <= cpu <= 1024:
        raise ValueError("CPU 配额须为 0～1024 的有限数字；0 表示不限制")


def verify_resource_limits(manager, config):
    """Read only three non-secret Docker fields; do not inspect Config.Env."""
    output = manager.checked_run("docker inspect --format "
        + "'{{json .HostConfig.Memory}} {{json .HostConfig.NanoCpus}} {{json .HostConfig.PidsLimit}}' "
        + manager.product.bot_container, timeout=20)
    try:
        actual = [json.loads(value) for value in output.strip().split()]
        memory = config.get("TG2CLOUD_BOT_MEMORY_LIMIT", "0")
        amount = 0 if memory == "0" else int(memory[:-1]) * (1024**3 if memory[-1].lower() == "g" else 1024**2)
        expected = [amount, int(float(config.get("TG2CLOUD_BOT_CPUS", "0")) * 10**9), int(config.get("TG2CLOUD_BOT_PIDS_LIMIT", "256"))]
        if any(type(item) is not int for item in actual) or actual != expected:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("容器实际限额未与配置对应；保留旧配置备份，请核对，不标记已生效") from None


def replace_private(path: Path, content: bytes, *, expected: bytes):
    if owned_file(path, private=True) != expected:
        raise ValueError("确认后私有配置发生变化；不会覆盖")
    staged = path.with_name("." + path.name + "-" + secrets.token_hex(16))
    runtime.write_exclusive(staged, content)
    try:
        if owned_file(path, private=True) != expected:
            raise ValueError("私有配置已变化；停止")
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def resources(manager, instance):
    manager.heading("资源与安全", instance)
    from tg2cloud.deployment.diagnostics import (
        inspect_container_logs,
        log_rotation_lines,
    )
    manager.log("\n".join(log_rotation_lines(inspect_container_logs(instance, manager.session))))
    manager.log("内存保护会参考容器 cgroup；暂存预算不限制网关全部缓存。")
    manager.log(numbered_menu(((1, "查看业务放行条件"), (2, "设置 Bot 资源限额"), (3, "检查 Docker 与端口"), (0, "返回主菜单"))))
    action = choose(manager.ui, "选择操作", ("0", "1", "2", "3"), "0")
    if action == "0":
        return False
    if action == "1":
        manager.readiness(instance)
        manager.checked_run("docker exec " + manager.product.bot_container + " python -B -m tg2cloud.monitoring.diagnostics", timeout=30)
    elif action == "3":
        manager.checked_run("docker version --format '{{.Server.Version}}'", timeout=20)
        manager.log("请使用厂商当前受支持的 Docker；28.0.0 前回环端口存在同网段可达的历史风险，需独立核对。")
        for name in (manager.product.bot_container, manager.product.storage_container):
            manager.checked_run("docker port " + name, timeout=15)
    else:
        if manager.core.info["format"] < 3:
            raise ValueError("旧 Compose 包未声明资源与凭据隔离协议；请先通过安装与升级更新部署包")
        config = dict(instance.config)
        config["TG2CLOUD_BOT_MEMORY_LIMIT"] = manager.ui.ask("Bot 内存上限（如 1024M；0 表示不限制）", default=config.get("TG2CLOUD_BOT_MEMORY_LIMIT", "1024M"))
        config["TG2CLOUD_BOT_PIDS_LIMIT"] = manager.ui.ask("Bot 进程数上限", default=config.get("TG2CLOUD_BOT_PIDS_LIMIT", "256"))
        config["TG2CLOUD_BOT_CPUS"] = manager.ui.ask("Bot CPU 配额（如 1；0 表示不限制）", default=config.get("TG2CLOUD_BOT_CPUS", "0"))
        validate_resources(config)
        if not manager.ui.confirm("保存并重建当前 Bot 应用限额？不重启网关；先等待活动任务结束"):
            return False
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (manager.product.key + ".lock")), runtime.operation_lock(manager.root):
            manager.recheck(instance)
            from tg2cloud.compose.lifecycle import scheduler_state
            paused, active = scheduler_state(manager.root)
            if active or instance.running and not paused:
                raise ValueError("先暂停新任务并等待活动任务结束；不修改配置或重建 Bot")
            content = "".join(key + "=" + value + "\n" for key, value in config.items()).encode()
            previous = instance.raw_config
            receipt = manager.root / (".env-before-resources-" + secrets.token_hex(8))
            runtime.write_exclusive(receipt, previous)
            replace_private(manager.root / ".env", content, expected=previous)
            try:
                manager.checked_run(manager.compose_command("up", "-d", "--no-deps", "--force-recreate", manager.product.bot_service), timeout=180)
                manager.core.validate(loopback=False, require_running=False)
                verify_resource_limits(manager, config)
            except BaseException:
                manager.log("配置原件保留在本机私密 .env-before-resources-*；容器状态未确认，不宣称已经回退。")
                raise
        manager.log("Bot 资源配置已应用；请检查业务就绪和实际转存，旧配置备份保留。")
    return True


def encrypt_archive(source: Path, destination: Path, password: str):
    """Optional authenticated GnuPG backup; no passphrase in argv/env/logs."""
    gpg, gpgconf = shutil.which("gpg"), shutil.which("gpgconf")
    if not gpg or not gpgconf:
        raise ValueError("加密备份需要宿主机 GnuPG；不自动安装，也不新增 Bot 依赖")
    runtime.regular(source.parent, source.name)
    runtime.private_config_file(source)
    if source.stat().st_nlink != 1:
        raise ValueError("备份归档不是独立常规文件")
    if source.stat().st_size > bundle.MAX_BYTES + 32 * 1024**2:
        raise ValueError("备份超过加密资源上限")
    if not password or any(ord(c) < 32 or ord(c) == 127 for c in password) or len(password.encode()) > 1024:
        raise ValueError("备份口令不能为空、含控制字符或过长")
    if destination.exists() or destination.is_symlink() or destination.parent.resolve() != destination.parent:
        raise ValueError("加密目标已存在或目录经过链接；不会覆盖")
    if shutil.disk_usage(destination.parent).free < source.stat().st_size + bundle.MIN_FREE:
        raise ValueError("加密备份空间不足")
    with tempfile.TemporaryDirectory(prefix=".tg2cloud-gpg-", dir=destination.parent) as folder:
        private = Path(folder)
        private.chmod(0o700)
        encrypted = private / "backup.gpg"
        common = [gpg, "--no-options", "--homedir", str(private), "--batch", "--pinentry-mode", "loopback", "--no-symkey-cache", "--passphrase-fd", "0"]
        try:
            result = subprocess.run([*common, "--cipher-algo", "AES256", "--output", str(encrypted), "--symmetric", str(source)],
                                    input=(password + "\n").encode(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600, check=False)  # nosec B603
            if result.returncode:
                raise ValueError("备份加密未完成；原明文备份保留")
            result = subprocess.run([*common, "--yes", "--output", os.devnull, "--decrypt", str(encrypted)],
                                    input=(password + "\n").encode(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600, check=False)  # nosec B603
            if result.returncode:
                raise ValueError("加密归档回读校验失败；不发布加密副本")
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "wb") as writer, encrypted.open("rb") as reader:
                    shutil.copyfileobj(reader, writer, 1024 * 1024)
            except BaseException:
                destination.unlink(missing_ok=True)
                raise
        finally:
            subprocess.run([gpgconf, "--homedir", str(private), "--kill", "gpg-agent"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=15, check=False)  # nosec B603 - only this temporary homedir


def backups(manager, instance):
    manager.heading("数据备份管理", instance)
    manager.log(numbered_menu(((1, "创建实例备份"), (2, "隔离恢复预检"), (3, "加密现有备份"), (4, "备份共享代理"), (0, "返回主菜单"))))
    action = choose(manager.ui, "选择操作", ("0", "1", "2", "3", "4"), "0")
    if action == "0":
        return False
    if action == "4":
        if manager.ui.confirm("创建共享代理备份？包含证书私钥，不包含业务数据库"):
            manager.log(manager.proxy().proxy_backup())
        return True
    parent = Path(manager.ui.ask("私密备份目录", default="/opt/tg2cloud-snapshots/compose-" + manager.product.key)).absolute()
    backup.output_directory(parent, instance, create=True)
    if action == "1":
        manager.log("备份配置、数据库、两个 Session 和网关授权；不包含云端文件、下载、日志或共享代理。")
        if manager.ui.confirm("短暂停止当前 Bot 和网关创建备份，并恢复原运行状态？其他 Edition 保持运行"):
            with edition_lock(Path("/opt/tg2cloud-cli-locks") / (manager.product.key + ".lock")):
                archive = backup.create(manager.recheck(instance), manager.session, parent)
            manager.log("实例备份已核验：" + str(archive) + "；含敏感信息，可在本菜单另存加密副本。")
    else:
        archive = Path(manager.ui.ask("实例备份归档绝对路径")).absolute()
        if action == "2":
            if manager.ui.confirm("隔离检查备份结构与数据库？不覆盖现有配置或启动第二个 Bot"):
                result = bundle.preflight(archive, parent, manager.product.key, instance.version)
                manager.log(f"备份结构与数据库预检通过：{result['files']} 文件；不代表服务恢复验收。")
        else:
            password = manager.ui.ask("备份加密口令（隐藏输入；请另存密码管理器）", secret=True)
            confirm = manager.ui.ask("再次输入备份加密口令", secret=True)
            if password != confirm:
                raise ValueError("两次口令不一致；未生成加密副本")
            manager.log.register({"BACKUP_PASSWORD": password})
            if manager.ui.confirm("创建并回读验证 .gpg 加密副本？原备份保留，不自动删除"):
                destination = parent / (archive.name + ".gpg")
                try:
                    encrypt_archive(archive, destination, password)
                finally:
                    password = confirm = None
                manager.log("加密副本已验证：" + str(destination) + "；恢复时先在私密目录解密，再做隔离预检。")
    return True
