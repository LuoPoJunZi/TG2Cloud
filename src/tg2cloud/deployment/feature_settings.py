"""Secondary offline controls, using only stdlib and the selected Bot endpoint."""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from tg2cloud.cli.presentation import numbered_menu, page_heading
from tg2cloud.deployment.host import edition_lock

MODES = {"off": "不分类", "type": "按文件类型", "year": "按年份", "month": "按年月", "type_month": "按文件类型和年月"}


def request(manager, instance, action, **values):
    payload = {"admin_id": int(instance.config["ALLOWED_USER_ID"]), "action": action, **values}
    command = "printf %s " + shlex.quote(json.dumps(payload, ensure_ascii=True)) + " | docker exec -i " + shlex.quote(
        manager.product.bot_container) + " python -B -m tg2cloud.persistence.control"
    code, output = manager.session.run(command, timeout=20)
    try:
        if code or len(output) > 16384:
            raise ValueError
        result = json.loads(output)
        if result["api"] != 1:
            raise ValueError
        return result
    except (ValueError, TypeError, KeyError):
        raise ValueError("可选功能操作未核实；请确认 Bot 已升级并运行，不直接修改离线数据库") from None


def number(value):
    if not value.isascii() or not value.isdecimal() or not 0 <= int(value) <= 100000:
        raise ValueError("请输入 0～100000 的整数；0 表示不限制")
    return value


def read_settings(manager, instance):
    if not instance.running:
        raise ValueError("请先启动支持新协议的 Bot")
    current = request(manager, instance, "settings-read").get("settings")
    if (not isinstance(current, dict) or not isinstance(current.get("classification"), str)
            or current["classification"] not in MODES or type(current.get("notifications")) is not bool
            or type(current.get("recovery_notifications")) is not bool
            or not isinstance(current.get("revision"), str)
            or not re.fullmatch(r"initial|[a-f0-9]{32}", current["revision"])
            or any(type(current.get(key)) is not int or not 0 <= current[key] <= 2**60 for key in
                   ("disk_threshold_bytes", "cooldown_seconds", "sustained_seconds", "blocked_seconds"))):
        raise ValueError("配置协议无法确认")
    return current


def save_settings(manager, instance, current, updates):
    if not manager.ui.confirm("确认保存？不重启 Bot；分类不整理历史文件，通知只发给管理员"):
        return
    with edition_lock(Path("/opt/tg2cloud-cli-locks") / (manager.product.key + ".lock")):
        manager.recheck(instance)
        request(manager, instance, "settings-write", revision=current["revision"], updates=updates)
    manager.log("设置已保存。")


def manage_classification(manager, instance):
    from tg2cloud.cli.management import choose
    ui, log = manager.ui, manager.log
    modes = tuple(MODES)
    while True:
        current = read_settings(manager, instance)
        log(page_heading("文件分类设置", manager.product, getattr(instance, "version", ""))
            + "\n当前规则：" + MODES[current["classification"]]
            + "\n分类目录位于现有 Bot 保存目录下；只影响新任务，不移动历史文件。\n\n"
            + numbered_menu((*enumerate(MODES.values(), 1), (0, "返回主菜单"))))
        action = choose(ui, "选择规则", ("0", "1", "2", "3", "4", "5"), "0")
        if action == "0":
            return
        save_settings(manager, instance, current, {"classification": modes[int(action) - 1]})


def manage_notifications(manager, instance):
    from tg2cloud.cli.management import choose
    ui, log = manager.ui, manager.log
    while True:
        current = read_settings(manager, instance)
        threshold = current["disk_threshold_bytes"]
        log(page_heading("异常通知设置", manager.product, getattr(instance, "version", ""))
            + "\n异常通知：" + ("开启" if current["notifications"] else "关闭")
            + "\n恢复通知：" + ("开启" if current["recovery_notifications"] else "关闭") + "（异常通知开启后生效）"
            + "\n磁盘提醒：" + (f"{threshold / 1024**3:g} GB（不低于原磁盘安全线）" if threshold else "跟随原磁盘安全线")
            + f"\n通知冷却：{current['cooldown_seconds']} 秒"
            + f"\n持续故障：{current['sustained_seconds']} 秒"
            + f"\n资源等待：{current['blocked_seconds']} 秒"
            + "\n\n" + numbered_menu((
                (1, "关闭异常通知" if current["notifications"] else "开启异常通知"),
                (2, "关闭恢复通知" if current["recovery_notifications"] else "开启恢复通知"),
                (3, "修改磁盘提醒阈值"), (0, "返回主菜单"),
            )))
        action = choose(ui, "选择操作", ("0", "1", "2", "3"), "0")
        if action == "0":
            return
        if action == "1":
            updates = {"notifications": not current["notifications"]}
        elif action == "2":
            updates = {"recovery_notifications": not current["recovery_notifications"]}
        else:
            log("单位 GB；0 跟随现有磁盘安全线，不能降低原磁盘保护。")
            updates = {"disk_threshold_bytes": int(ui.ask("提醒阈值", default="0", validate=number)) * 1024**3}
        save_settings(manager, instance, current, updates)


def member_quota(manager, instance, record, member_id, *, action):
    if action not in {"view", "set", "clear"}:
        raise ValueError("请选择有效的配额操作")
    current = request(manager, instance, "quota-read", user_id=member_id)["usage"]
    keys = ("daily_bytes", "max_queued", "max_active")
    if any(type(current.get(key)) is not int or not 0 <= current[key] <= 2**60 for key in keys):
        raise ValueError("配额协议无效")
    manager.log("\n── 成员配额 ──\n每日额度：" + (f"{current['daily_bytes'] / 1024**3:g} GB" if current["daily_bytes"] else "不限")
                + f"\n最大排队：{current['max_queued'] or '不限'}\n最大同时传输：{current['max_active'] or '不限'}")
    for key, label in (("completed_bytes", "今日已完成"), ("reserved_bytes", "未完成预留")):
        amount = current.get(key)
        if type(amount) is not int or not 0 <= amount <= 2**60:
            raise ValueError("用量协议无效")
        manager.log(f"{label}：{amount / 1024**3:.2f} GB")
    if action == "view":
        return
    if action == "clear":
        values = dict.fromkeys(keys, 0)
    else:
        values = {"daily_bytes": int(manager.ui.ask("每日 GB（0 不限）", validate=number)) * 1024**3,
                  "max_queued": int(manager.ui.ask("最大排队（0 不限）", validate=number)),
                  "max_active": int(manager.ui.ask("最大同时传输（0 不限）", validate=number))}
    if manager.ui.confirm("确认配额变更？不取消正在执行的任务，不删除历史记录或文件"):
        with edition_lock(Path("/opt/tg2cloud-cli-locks") / (manager.product.key + ".lock")):
            manager.recheck(instance)
            request(manager, instance, "quota-write", user_id=member_id, revision=record["revision"],
                    expected={key: current[key] for key in keys}, values=values)
        manager.log("配额已更新；家人发送 /quota 查看自己的用量。")
