"""Root-terminal family grants, via a versioned endpoint in the selected Bot."""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from tg2cloud.cli.presentation import numbered_menu
from tg2cloud.deployment.host import edition_lock


def numeric_id(value: str) -> str:
    if not re.fullmatch(r"[1-9][0-9]{0,14}", value):
        raise ValueError("请输入一个 Telegram 用户 ID")
    return value


def request(session, product, admin: int, **values) -> dict:
    payload = json.dumps({"admin_id": admin, **values}, ensure_ascii=True)
    command = ("printf %s " + shlex.quote(payload) + " | docker exec -i "
               + shlex.quote(product.bot_container) + " python -B -m tg2cloud.persistence.users")
    code, output = session.run(command, timeout=30)
    if code or len(output) > 40000:
        raise ValueError("家庭授权操作未完成；请刷新记录，核对 Bot 是否已升级支持新协议并运行。不修改安装配置。")
    try:
        result = json.loads(output)
        record = result["record"]
        if (result["api"] != 1 or record["schema"] != 1 or record["admin_id"] != admin
                or not isinstance(record["revision"], str)
                or not re.fullmatch(r"initial|[a-f0-9]{32}", record["revision"])
                or not isinstance(record["users"], list) or len(record["users"]) > 32):
            raise ValueError
        seen = {admin}
        for member in record["users"]:
            if (set(member) != {"id", "name", "enabled"} or type(member["id"]) is not int
                    or int(numeric_id(str(member["id"]))) in seen
                    or type(member["enabled"]) is not bool or not isinstance(member["name"], str)
                    or not 1 <= len(member["name"]) <= 40
                    or any(ord(c) < 32 or ord(c) == 127 for c in member["name"])):
                raise ValueError
            seen.add(member["id"])
        return record
    except (ValueError, KeyError, TypeError):
        raise ValueError("Bot 返回的家庭授权协议无法确认；不继续操作。") from None


def manage(manager, instance) -> None:
    """No restart, dotenv writes, native account changes or task deletions."""
    from tg2cloud.cli.management import choose

    if not instance.running:
        raise ValueError("请先启动 Bot；不直接修改离线数据库。")
    admin = int(numeric_id(instance.config.get("ALLOWED_USER_ID", "")))
    ui, log = manager.ui, manager.log
    while True:
        record = request(manager.session, manager.product, admin, action="list")
        log("\n── Bot 用户管理 ──\n安装时的用户是固定管理员；家人共用保存目录，仅管理自己的任务。")
        ui.private("管理员 ID", str(admin))
        for index, member in enumerate(record["users"], 1):
            ui.private(str(index), f"{member['name']} · {member['id']} · {'启用' if member['enabled'] else '停用'}")
        log(numbered_menu(((1, "添加家人"), (2, "启用家人"), (3, "停用家人"), (4, "移除授权"), (5, "成员配额与用量"), (0, "返回"))))
        selected = choose(ui, "选择操作", ("0", "1", "2", "3", "4", "5"), "0")
        if selected == "0":
            return
        action = {"1": "add", "2": "enable", "3": "disable", "4": "remove", "5": "quota"}[selected]
        if action == "add":
            member_id = int(ui.ask("家人的 Telegram 用户 ID", validate=numeric_id))
            def label(value):
                if not 1 <= len(value) <= 40 or any(ord(c) < 32 or ord(c) == 127 for c in value):
                    raise ValueError("名称应为 1～40 个字符")
                return value
            name = ui.ask("备注名称", default="家庭成员", validate=label)
        else:
            if not record["users"]:
                log("没有已登记的家人。")
                continue
            number = choose(ui, "选择上方成员序号（0 返回）", tuple(str(n) for n in range(len(record["users"]) + 1)))
            if number == "0":
                continue
            member = record["users"][int(number) - 1]
            member_id, name = member["id"], member["name"]
        if member_id == admin:
            raise ValueError("不能通过家庭成员管理修改管理员。")
        if action == "quota":
            from tg2cloud.deployment.feature_settings import member_quota
            member_quota(manager, instance, record, member_id)
            continue
        ui.private("操作对象", f"{name} · {member_id}")
        log("仅变更 Bot 授权；已接收任务继续处理，不删除任务或文件，不开通/撤销外部 WebDAV 账号。")
        if not ui.confirm("确认本次授权变更？"):
            continue
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (manager.product.key + ".lock")):
            manager.recheck(instance)
            request(manager.session, manager.product, admin, action=action, id=member_id,
                    name=name, revision=record["revision"])
        log("家庭授权已更新；无需重启 Bot。")
