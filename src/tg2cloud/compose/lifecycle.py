"""Confirmed Compose upgrade and removal, fenced by physical ownership checks."""
from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import sqlite3
import stat
import tempfile
import time
from contextlib import closing
from pathlib import Path

from tg2cloud.cli.management import choose
from tg2cloud.cli.presentation import numbered_menu
from tg2cloud.compose import releases, runtime
from tg2cloud.compose.https import atomic_private, owned_file
from tg2cloud.deployment import backup
from tg2cloud.deployment.host import edition_lock
from tg2cloud.deployment.releases import version_tuple
from tg2cloud.persistence.paths import database_path

JOURNAL = ".compose-upgrade.json"
OWNER = "tg2cloud.compose.upgrade"


def scheduler_state(root):
    path = database_path(root / "data", require_existing=True)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)) as connection:
        row = connection.execute("SELECT value FROM service_meta WHERE key='paused'").fetchone()
    return bool(row and row[0] == "1"), backup.active_tasks(root)


def public_files(root):
    """Only release-owned files; never enumerate private instance directories."""
    result = {}
    for name in ("docker-compose.yml", "compose-bundle.json", "README.md", "LICENSE", ".env.example", "https.sh", "manage.sh"):
        path = root / name
        if path.exists() or path.is_symlink():
            result[name] = owned_file(path)
    tools = root / "https-tools"
    if tools.exists():
        for path in tools.rglob("*"):
            if path.is_symlink() or path.resolve() != path:
                raise ValueError("管理工具经过链接；停止")
            if path.is_file():
                name = path.relative_to(root).as_posix()
                if len(result) >= 600:
                    raise ValueError("管理工具清单过大")
                result[name] = owned_file(path)
    return result


def write_public(root, values):
    for name, body in values.items():
        target = root / name
        if target.resolve() != target or target.is_symlink():
            raise ValueError("部署资源路径发生变化")
        target.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
        if target.exists():
            owned_file(target)
        staged = target.with_name("." + target.name + "-" + secrets.token_hex(16))
        runtime.write_exclusive(staged, body)
        try:
            staged.chmod(0o755 if name in {"https.sh", "manage.sh"} else 0o644)
            os.replace(staged, target)
        finally:
            staged.unlink(missing_ok=True)


def switch_public(root, previous, candidate):
    write_public(root, candidate)
    for name in previous.keys() - candidate.keys():
        target = root / name
        if owned_file(target) != previous[name]:
            raise ValueError("旧工具发生变化，拒绝清理")
        target.unlink()
    parents = {parent for name in previous.keys() - candidate.keys()
               for parent in (root / name).parents if parent.is_relative_to(root / "https-tools")}
    for parent in sorted(parents, key=lambda path: len(path.parts), reverse=True):
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()


def wait_for_bot(manager, version):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        code, output = manager.session.run("docker exec " + manager.product.bot_container
                                          + " python -B -m tg2cloud.monitoring.readiness", timeout=15)
        try:
            value = json.loads(output)
            if (code == 0 and value.get("version") == version and value.get("schema") == 1
                    and value.get("checks", {}).get("heartbeat") == "ok"
                    and value["checks"].get("telegram") == "ok"):
                return value
        except (ValueError, KeyError, TypeError):
            pass
        time.sleep(2)
    raise RuntimeError("新 Bot 基础检查尚未通过；不标记升级成功")


def start_initial(manager, instance):
    manager.log("将先启动当前网关。请在管理页挂载存储并创建专用 WebDAV 账号，再启动 Bot。")
    if not manager.ui.confirm("启动当前 Compose 网关？不重新初始化配置"):
        return
    with edition_lock(Path("/opt/tg2cloud-cli-locks") / (manager.product.key + ".lock")):
        manager.recheck(instance)
        manager.checked_run(manager.compose_command("up", "-d", manager.product.key), timeout=180)
    manager.log("网关已启动。管理端口：" + str(manager.product.management_port))
    if manager.ui.confirm("已在后台完成挂载和专用账号配置，现在启动 Bot？"):
        current = manager.discover()
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (manager.product.key + ".lock")):
            manager.recheck(current)
            manager.checked_run(manager.compose_command("up", "-d", manager.product.bot_service), timeout=180)
        manager.log("Bot 已启动；请查看业务就绪、WebDAV 验收并实际转存一个小文件。")


def upgrade(manager, instance):
    if instance.container_ids[0] is None:
        return start_initial(manager, instance)
    marker = manager.root / JOURNAL
    if marker.exists() or marker.is_symlink():
        record = json.loads(owned_file(marker, private=True))
        if record.get("owner") != OWNER or record.get("phase") not in {"completed", "rolled-back"}:
            raise ValueError("上次升级尚未核实；保留快照与升级记录，先人工核对")
    manager.log("只更新当前 Compose 实例；先备份，保留 .env、Session、数据库、下载和网关数据。")
    tag = manager.ui.ask("目标正式版本（回车使用最新稳定版）", default="") or None
    with tempfile.TemporaryDirectory(prefix="tg2cloud-compose-release-") as directory:
        candidate = releases.download(manager.product.key, Path(directory).resolve(), tag=tag)
        info = json.loads((candidate / "compose-bundle.json").read_text(encoding="utf-8"))
        if version_tuple(info["version"]) < version_tuple(instance.version):
            raise ValueError("拒绝自动降级；数据库回退必须匹配备份与旧程序")
        if info["version"] == instance.version and manager.core.info["format"] == 3:
            manager.log("当前已是所选正式版本；未重建容器或改写配置。")
            return
        manager.log("升级计划：" + instance.version + " → " + info["version"] + "；可能短暂中断当前网关读取，其他 Edition 保留。")
        if not manager.ui.confirm("确认备份后升级？请先暂停新任务并等待活动传输结束"):
            return
        parent = Path("/opt/tg2cloud-snapshots/compose-" + manager.product.key)
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (manager.product.key + ".lock")), runtime.operation_lock(manager.root):
            current = manager.recheck(instance)
            paused, active = scheduler_state(manager.root)
            if active or current.running and not paused:
                raise ValueError("请先通过服务启停管理暂停新任务并等待活动任务结束；旧版可在 Bot 发送 /pause")
            previous, target = public_files(manager.root), public_files(candidate)
            states = {name: backup.container(manager.session, name) for name in
                      (manager.product.bot_container, manager.product.storage_container)}
            if tuple(states[name]["id"] for name in (manager.product.bot_container, manager.product.storage_container)) != current.container_ids:
                raise ValueError("升级前容器已被替换；停止")
            started_new_bot = False
            promoted = False
            receipt = {"format": 1, "owner": OWNER, "edition": manager.product.key, "root": str(manager.root),
                       "from": current.version, "target": info["version"], "phase": "prepared"}
            atomic_private(marker, receipt)
            try:
                if states[manager.product.bot_container]["running"]:
                    manager.checked_run("docker stop -t 45 " + shlex.quote(states[manager.product.bot_container]["id"]), timeout=90)
                archive = backup.create(current, manager.session, parent)
                receipt.update(phase="backed-up", backup=str(archive))
                atomic_private(marker, receipt)
                manager.checked_run(manager.compose_command("pull", manager.product.bot_service, manager.product.key, root=candidate), timeout=600)
                manager.recheck(instance)
                if states[manager.product.storage_container]["running"]:
                    manager.checked_run("docker stop -t 45 " + shlex.quote(states[manager.product.storage_container]["id"]), timeout=90)
                promoted = True
                switch_public(manager.root, previous, target)
                receipt["phase"] = "activated-files"
                atomic_private(marker, receipt)
                if states[manager.product.storage_container]["running"]:
                    manager.checked_run(manager.compose_command("up", "-d", manager.product.key), timeout=180)
                if states[manager.product.bot_container]["running"]:
                    # Once new code can migrate/write SQLite, never restore an
                    # old DB automatically or start old code against new schema.
                    started_new_bot = True
                    manager.checked_run(manager.compose_command("up", "-d", manager.product.bot_service), timeout=180)
                    wait_for_bot(manager, info["version"])
                manager.core.validate(loopback=False, require_running=states[manager.product.storage_container]["running"])
                receipt["phase"] = "completed"
                atomic_private(marker, receipt)
            except BaseException:
                if not started_new_bot:
                    try:
                        if promoted:
                            switch_public(manager.root, target, previous)
                        # Do not restart through changed credentials, labels,
                        # mounts or containers, even on the rollback path.
                        manager.recheck(instance)
                        for service, name in ((manager.product.key, manager.product.storage_container),
                                              (manager.product.bot_service, manager.product.bot_container)):
                            if states[name]["running"]:
                                manager.checked_run(manager.compose_command("up", "-d", service), timeout=180)
                        restored = manager.core.validate(loopback=False, require_running=False)
                        if any(restored.get(name, {}).get("running") != state["running"] for name, state in states.items()):
                            raise ValueError("原服务运行状态尚未恢复")
                        receipt["phase"] = "rolled-back"
                        atomic_private(marker, receipt)
                        manager.log("新 Bot 启动前失败，原部署文件与服务已恢复；数据库未被替换。")
                    except (Exception, KeyboardInterrupt):  # noqa: BLE001 - report uncertain rollback without replay
                        manager.log("原服务恢复尚未确认；保留升级记录和快照，不自动重复操作。")
                else:
                    receipt["phase"] = "needs-review"
                    atomic_private(marker, receipt)
                    try:
                        manager.core.validate(loopback=False, require_running=False)
                        manager.checked_run(manager.compose_command("stop", manager.product.bot_service), timeout=90)
                    except (Exception, KeyboardInterrupt):  # noqa: BLE001 - leave the journal for manual inspection
                        manager.log("新 Bot 停止状态未确认，请立即核对容器状态。")
                    manager.log("新 Bot 已启动过，保留新数据库和快照；不自动覆盖数据或启动旧程序，请按回退文档处理。")
                raise
    manager.log("Compose 升级完成；Bot 与离线管理资源来自同一正式部署包。调度暂停状态保留。")
    manager.log("仍需检查 WebDAV 写入、实际转存和公网访问；退出后重新运行 bash manage.sh 使用新管理工具。")


def removable_tree(root):
    """Bounded local-only cleanup plan; never traverse cloud/FUSE mounts."""
    mountpoints = backup.mountpoints()
    result, pending = [], [root]
    device = root.lstat().st_dev
    while pending:
        path = pending.pop()
        info = path.lstat()
        if (len(result) >= 30000 or path.is_symlink() or path.resolve() != path
                or len(path.relative_to(root).parts) > 64 or info.st_dev != device or path in mountpoints
                or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))):
            raise ValueError("清理范围含链接、挂载、特殊对象或超过数量上限；保留文件")
        result.append((path, info.st_dev, info.st_ino, stat.S_ISDIR(info.st_mode)))
        if stat.S_ISDIR(info.st_mode):
            with os.scandir(path) as entries:
                for item in entries:
                    if len(pending) + len(result) >= 30000:
                        raise ValueError("清理对象数量超过安全上限；保留文件")
                    pending.append(Path(item.path))
    return sorted(result, key=lambda item: len(item[0].parts), reverse=True)


def remove_tree(plan):
    for path, device, inode, directory in plan:
        info = path.lstat()
        if (info.st_dev, info.st_ino) != (device, inode) or path.is_symlink():
            raise ValueError("清理对象已变化；停止")
        path.rmdir() if directory else path.unlink()


def cleanup_plan(manager):
    """Check every deletion scope before removing even the first file."""
    if not manager.product.is_openlist:
        mounts = manager.root / "clouddrive/mounts"
        if mounts.is_symlink() or mounts.exists() and (mounts in backup.mountpoints() or any(mounts.iterdir())):
            raise ValueError("CloudDrive2 挂载点尚未清空或卸载，保留全部本地数据；不扫描云端")
    trees = []
    for child in ("data", "downloads", "logs", "config", "openlist" if manager.product.is_openlist else "clouddrive"):
        path = manager.root / child
        if path.exists() or path.is_symlink():
            trees.append(removable_tree(path))
    files = []
    candidates = [manager.root / name for name in (".env", runtime.MARKER, "compose-access.json")]
    candidates.extend(path for path in manager.root.glob(".env-before-resources-*")
                      if re.fullmatch(r"\.env-before-resources-[a-f0-9]{16}", path.name))
    for path in candidates:
        if path.exists() or path.is_symlink():
            owned_file(path, private=True)
            info = path.lstat()
            files.append((path, info.st_dev, info.st_ino, False))
    return trees, files


def uninstall(manager, instance):
    manager.heading("卸载当前实例", instance)
    from tg2cloud.addons.external_webdav import config
    record = config.read_record(config.ROOT / manager.product.key / "config.json")
    state = manager.proxy().read_state()
    if record or manager.product.key in state.get("external_webdav", {}):
        raise ValueError("外部 WebDAV 仍依赖当前网关；请先在外部 WebDAV 菜单单独卸载")
    manager.log(numbered_menu(((1, "移除服务，保留全部数据"), (2, "移除服务及当前实例数据"), (0, "返回主菜单"))))
    action = choose(manager.ui, "卸载方式", ("0", "1", "2"), "0")
    if action == "0":
        return False
    manager.log("仅当前 " + manager.product.display_name + "；保留其他 Edition、云端文件、独立导出备份及系统 Docker/Nginx。")
    if action == "2" and manager.ui.ask("删除当前实例数据不可恢复，请输入 Edition 名称确认") != manager.product.key:
        raise ValueError("确认不匹配；未删除任何内容")
    if not manager.ui.confirm("确认执行上述卸载计划？不会执行全项目 compose down"):
        return False
    with edition_lock(Path("/opt/tg2cloud-cli-locks") / (manager.product.key + ".lock")), runtime.operation_lock(manager.root):
        manager.recheck(instance)
        paused, active = scheduler_state(manager.root)
        if active or instance.running and not paused:
            raise ValueError("先暂停新任务并等待活动任务结束；停止卸载")
        if action == "2":
            cleanup_plan(manager)  # Read-only preflight before stopping services.
        proxy = manager.proxy()
        latest = proxy.read_state()
        if latest != state:
            raise ValueError("确认后代理状态变化；停止卸载")
        if manager.product.key in state["domains"]:
            proxy.remove()
        manager.checked_run(manager.compose_command("rm", "--stop", "--force", manager.product.bot_service, manager.product.key), timeout=180)
        name = manager.product.docker_network
        code, output = manager.session.run("docker network inspect --format '{{json .}}' " + shlex.quote(name), timeout=20)
        if not code:
            network = json.loads(output)
            labels = network.get("Labels") or {}
            if (labels.get("com.docker.compose.project") == manager.project
                    and labels.get("com.docker.compose.network") == name and network.get("Containers") == {}):
                manager.checked_run("docker network rm " + shlex.quote(name), timeout=30)
            else:
                manager.log("网络仍有其他连接或归属未确认，已保留。")
        if action == "2":
            trees, files = cleanup_plan(manager)  # Recheck all scopes after services stop.
            for tree in trees:
                remove_tree(tree)
            remove_tree(files)
            manager.log("当前实例配置、Session、数据库、下载和网关数据已清理；保留公开部署包、操作记录与锁文件，不删除独立导出备份。")
        else:
            manager.log("服务已移除；.env、数据库、Session、下载、网关数据和部署工具全部保留。")
    return True
