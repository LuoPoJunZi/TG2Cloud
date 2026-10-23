"""Human-facing installer presentation; parsers still consume raw command results."""
from __future__ import annotations

import re

from tg2cloud.deployment.host import SafeLog


def numbered_menu(items) -> str:
    """Left-align both the number column and the label column, without tabs."""
    rows = [(str(number) + ".", label) for number, label in items]
    width = max((len(number) for number, _ in rows), default=0)
    return "\n".join(f"{number:<{width}} {label}" for number, label in rows)


class InstallerLog:
    def __init__(self, log: SafeLog) -> None:
        self.log = log

    def register(self, config) -> None:
        self.log.register(config)

    def clean(self, text: str) -> str:
        return self.log.clean(text)

    def __call__(self, text: str) -> None:
        # Never alter session.run's returned output: machine completion markers
        # remain mandatory even when the interactive presentation is Chinese.
        lines = []
        for line in text.splitlines():
            if line.startswith("正式 Release："):
                line = line.split("；", 1)[0].replace("正式 Release：", "正式稳定版本：")
            elif line.startswith("TG2CLOUD_CLI_RESULT=BASE_HTTPS_OK"):
                line = "基础安装与 HTTPS 检查通过；WebDAV 和真实转存以单独验收为准。\n下次管理请运行：tg2cloud"
            elif line.startswith("TG2CLOUD_LAN_RESULT=BASE_LAN_OK"):
                line = "基础安装与内网入口检查通过；WebDAV 和真实转存以单独验收为准。\n下次管理请运行：tg2cloud"
            elif re.match(r"TG2CLOUD_(?:CLI|LAN)_RESULT=", line):
                label, _, detail = line.partition("；")
                translations = {"NO_CHANGE": "当前无需变更", "CANCELLED": "已取消", "INTERRUPTED": "操作中断"}
                key = label.split("=", 1)[1]
                line = translations.get(key, label.replace("TG2CLOUD_CLI_RESULT=FAILED：", "操作失败：").replace("TG2CLOUD_LAN_RESULT=FAILED：", "操作失败：")) + ("；" + detail if detail else "")
            elif line.startswith("TG2CLOUD_CLI_WEBDAV=NOT_RUN"):
                line = "WebDAV 验收已跳过，可稍后运行 tg2cloud 进行验收。"
            elif line.startswith("TG2CLOUD_CLI_WEBDAV=OK"):
                line = "WebDAV 写入与大小复验通过；请在云存储官方客户端确认最终文件。"
            elif line.startswith("TG2CLOUD_CLI_BASE_HTTPS=OK"):
                line = "HTTPS 管理入口本机检查通过；公网访问仍需外部网络检查。"
            lines.append(line)
        self.log("\n".join(lines))


def edition_menu(ui, log, *, default: str = "1", both: bool = False, title: str = "安装向导") -> str:
    labels = ("CloudDrive2", "OpenList") + (("升级两套已有实例",) if both else ())
    log("\n── TG2Cloud " + title + " ──\n" + numbered_menu(enumerate(labels, 1)))
    def validate(value):
        if value not in ({"1", "2", "3"} if both else {"1", "2"}):
            raise ValueError("请选择菜单中的序号")
        return value
    return ui.ask("选择 Edition", default=default, validate=validate)
