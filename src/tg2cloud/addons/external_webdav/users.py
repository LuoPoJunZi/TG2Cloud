"""Independent family read accounts, all confined to the approved shared root.

Native account creation and read-only scope remain explicit gateway steps.
Only the selected entry is revoked on failure; no backend account is deleted.
"""
from __future__ import annotations

import copy
import os
import secrets

from tg2cloud.addons.external_webdav import config, verification


def entries(service, item):
    values = config.auth_entries(service.auth.read_text(encoding="ascii"))
    allowed = {item["username"], *(m["username"] for m in item.get("members", [])
                                  if m["phase"] in {"enabled", "pending"})}
    if values.keys() - allowed:
        raise ValueError("认证文件包含未登记或已撤销的账号；请先人工核对。")
    return values


def write(service, values):
    # Existing, preflight-validated directory bind: preserve its worker GID.
    # Revocation must not depend on starting a helper Docker container.
    info = service.auth.stat()
    config.atomic(service.auth, config.auth_content(values), mode=0o640,
                  gid=info.st_gid if os.name == "posix" else None)


def reload_auth(service):
    # Identity/configuration are checked by preflight under the shared lock.
    # Only a hash file changes: don't call route activation's Edition-wide
    # fallback (which intentionally disables the whole external route).
    service.verify_mounted_hash()
    for argument in ("-t", "-s reload"):
        code, _ = service.session.run("docker exec tg2cloud-proxy-nginx nginx " + argument, timeout=30)
        if code:
            raise RuntimeError("认证文件已变更，但共享代理重载未确认；请检查状态，不假定旧读取连接已退出。")


def checked(service, item, *, closing=False):
    instance, state = service.preflight(item["instance_dir"], require_running=not closing)
    if not closing:
        service.assert_binding(item, instance)
    if state.get("external_webdav", {}).get(service.product.key) != service.route(item, item["phase"] == "enabled"):
        raise ValueError("外部路由与登记状态不符；先修复整个入口。")
    entries(service, item)
    return instance, state


def account(service, action: str, user: str, *, sample_file: str = "") -> None:
    """The only mutator; confirmations precede writes; CAS spans manual steps."""
    original = service.record()
    closing = action in {"disable", "remove"}
    if original is None or (not closing and original["phase"] != "enabled"):
        raise ValueError("请先安装并启用主入口；用户管理不自动修复或扩大共享范围。")
    instance, _ = checked(service, original, closing=closing)
    config.username(user, "" if closing else config.decode(instance.config, "USERNAME"))
    member = next((m for m in original.get("members", []) if m["username"] == user), None)
    if action not in {"add", "enable", "disable", "remove", "rotate", "check"}:
        raise ValueError("不支持的用户操作。")
    if user.casefold() == original["username"].casefold():
        raise ValueError("主账号请使用入口的检查／配置功能；本菜单只管理新增家庭账号。")
    if action == "add":
        if (len(original.get("members", [])) >= config.MAX_MEMBERS
                or user.casefold() in {m["username"].casefold() for m in original.get("members", [])}):
            raise ValueError("账号已登记或达到家庭共享数量限制。")
    elif member is None:
        raise ValueError("没有找到已登记的家庭账号。")
    route = dict(service.route(original, True), username=user)
    if action == "check":
        if member["phase"] != "enabled" or user not in entries(service, original):
            raise ValueError("该账号未启用或缺少有效认证记录。")
        secret = service.ui.ask("此账号当前密码（隐藏输入）", secret=True, validate=config.password)
        service.log.register({"EXTERNAL_PASSWORD": secret})
        with service.locked():
            service.assert_record(original)
            checked(service, original)
            verification.check_backend(route, secret)
            verification.check_public(route, secret, sample_file=sample_file)
            service.verify_mounted_hash()
        service.log("所选家庭账号本机读取检查通过；后台目录／只读权限仍需人工核对。")
        return
    opening = action in {"add", "enable", "rotate"}
    secret = None
    if opening:
        prompt = "新的外部密码（回车自动生成 9 位随机密码）" if action in {"add", "rotate"} else "该账号当前密码（隐藏输入）"
        secret = service.ui.ask(prompt, secret=True, default=config.new_password() if action in {"add", "rotate"} else "", validate=config.password)
        service.log.register({"EXTERNAL_PASSWORD": secret})
    service.log(f"所选账号：{user}；操作：" + {"add": "添加", "enable": "启用", "rotate": "换密", "disable": "停用", "remove": "移除入口授权"}[action])
    service.log("共同目录：" + original["target_dir"])
    service.log("仅处理所选账号；不修改其他用户、Bot 配置、云端文件或后台账号。重载可能短暂影响读取连接。")
    if not service.ui.confirm("确认继续？所选账号将先关闭，失败时保持拒绝访问"):
        return
    pending = copy.deepcopy(original)
    pending.update(schema=2, revision=secrets.token_hex(16))
    pending.setdefault("members", [])
    selected = next((m for m in pending["members"] if m["username"] == user), None)
    if selected is None:
        selected = {"username": user, "phase": "pending"}
        pending["members"].append(selected)
    selected["phase"] = "pending"
    try:
        with service.locked():
            service.assert_record(original)
            _, state = checked(service, original, closing=closing)
            values = entries(service, original)
            service.backup(state)
            # Persist intent before changing the gate, in the same write lock.
            service.save(pending)
            values.pop(user, None)
            write(service, values)
            reload_auth(service)
        if opening:
            service.log("请在 " + service.product.display_name + " 后台创建／核对此独立只读账号；能力不足请取消。")
            service.log("用户名：" + user)
            if action in {"add", "rotate"}:
                service.ui.show_password(secret)
            service.log(("base path：" if service.product.is_openlist else "根目录：") + original["target_dir"])
            confirmed = service.ui.ask("后台已设置的账号根目录（不能为 /）", validate=config.logical_path)
            if (confirmed != original["target_dir"] or not service.ui.confirm(
                    "已确认原生独立账号、只读和共同目录，无上传／删除／移动／管理权限？")):
                raise ValueError("未完成原生只读及目录确认；所选账号不开放。")
            verification.check_backend(route, secret)
        with service.locked():
            service.assert_record(pending)
            checked(service, pending, closing=closing)
            values = entries(service, pending)
            if opening:
                try:
                    values[user] = config.password_hash(secret)
                    write(service, values)
                    reload_auth(service)
                    verification.check_public(route, secret, sample_file=sample_file)
                except BaseException:
                    # Close before releasing the lock: a second user's update
                    # cannot inherit a failed activation while CAS advances.
                    values.pop(user, None)
                    write(service, values)
                    raise
            completed = copy.deepcopy(pending)
            if action == "remove":
                completed["members"] = [m for m in completed["members"] if m["username"] != user]
            else:
                next(m for m in completed["members"] if m["username"] == user)["phase"] = "enabled" if opening else "disabled"
            service.save(completed)
        if opening:
            service.display(dict(completed, username=user), secret=secret if action in {"add", "rotate"} else None)
        service.log("所选账号入口授权已更新；程序未删除后台账号或云端数据。")
    except BaseException:
        with service.locked():
            current = service.record()
            if current and current["revision"] == pending["revision"]:
                values = entries(service, pending)
                values.pop(user, None)
                write(service, values)
                selected["phase"] = "needs_repair"
                service.save(pending)
                try:
                    reload_auth(service)
                except (ValueError, RuntimeError, OSError):
                    service.log("所选账号已从认证文件移除；旧读取连接退出未确认，请检查共享代理。")
        service.log("所选账号需修复，不退回 Bot 凭据；后台密码无法自动回滚，其他账号认证记录保留。")
        raise


def menu(service, *, sample_file: str = "") -> None:
    from tg2cloud.addons.external_webdav.cli import choose

    while True:
        item = service.record()
        if item is None:
            raise ValueError("请先安装外部 WebDAV。")
        service.log("\n── 外部 WebDAV 用户管理 ──\n共同目录：" + item["target_dir"])
        service.log("主账号：" + item["username"] + "（由入口配置管理）")
        for index, member in enumerate(item.get("members", []), 1):
            service.log(f"  {index}. {member['username']} · " + {"enabled": "已启用", "disabled": "已停用", "pending": "待完成", "needs_repair": "需修复"}[member["phase"]])
        action = choose(service.ui, service.log, "请选择操作：", (
            ("add", "添加只读账号"), ("check", "检查账号"), ("enable", "启用账号"),
            ("disable", "停用账号"), ("rotate", "更改密码"), ("remove", "移除入口授权")))
        if not action:
            return
        if action == "add":
            user = service.ui.ask("新的外部专用用户名", validate=config.username)
        else:
            choices = tuple((m["username"], m["username"]) for m in item.get("members", []))
            if not choices:
                service.log("没有新增的家庭账号。")
                continue
            user = choose(service.ui, service.log, "请选择账号：", choices)
            if not user:
                continue
        account(service, action, user, sample_file=sample_file)
