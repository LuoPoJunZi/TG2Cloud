from __future__ import annotations

import base64
import re
import secrets
from contextlib import ExitStack
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tg2cloud.deployment import configuration, install, releases
from tg2cloud.deployment.host import SafeLog
from tg2cloud.deployment.profiles import ProductProfile


class Terminal:
    def __init__(self) -> None:
        # A terminal is not seekable: buffered r+ (BufferedRandom) fails before
        # the first prompt. Separate streams still use only the controlling TTY.
        with ExitStack() as streams:
            self.tty = streams.enter_context(open("/dev/tty", "r", encoding="utf-8", buffering=1))
            self.output = streams.enter_context(open("/dev/tty", "w", encoding="utf-8", buffering=1))
            if not self.tty.isatty() or not self.output.isatty():
                raise RuntimeError("需要交互终端；不从管道/历史记录读取密码")
            self._streams = streams.pop_all()

    def close(self) -> None:
        self._streams.close()

    def ask(self, prompt: str, *, default: str = "", secret: bool = False, validate=configuration.plain) -> str:
        import termios

        while True:
            previous = None
            try:
                if secret:
                    previous = termios.tcgetattr(self.tty.fileno())
                    hidden = previous.copy()
                    hidden[3] &= ~termios.ECHO
                    termios.tcsetattr(self.tty.fileno(), termios.TCSANOW, hidden)
                self.output.write(prompt + (f" [{default}]" if default and not secret else "") + ": ")
                self.output.flush()
                line = self.tty.readline()
            finally:
                if previous is not None:
                    termios.tcsetattr(self.tty.fileno(), termios.TCSANOW, previous)
                    self.output.write("\n")
            if not line:
                raise EOFError("输入已中断")
            value = line.rstrip("\r\n") or default
            try:
                return validate(value)
            except (ValueError, ZoneInfoNotFoundError):
                self.output.write("输入格式不正确，请重新填写（不显示输入值）。\n")

    def confirm(self, prompt: str) -> bool:
        return self.ask(prompt + " [y/N]", default="n", validate=lambda text: text.lower()) == "y"

    def reveal(self, label: str, value: str) -> None:
        if self.confirm("是否仅在当前终端显示" + label + "？请确保没有旁观/录屏"):
            self.output.write(label + ": " + value + "\n")
            self.output.flush()


def show_credentials(ui: Terminal, product: ProductProfile, config: dict[str, str], log: SafeLog) -> None:
    """Read saved setup values only; never query/reset a gateway password."""
    log(product.display_name + "：逐项确认后仅向当前私有终端显示已保存凭据；默认不显示。")
    for key, label in (("USERNAME", "WebDAV 用户名"), ("PASSWORD", "WebDAV 密码")):
        # Older CloudDrive2 installations may only have the compatibility keys.
        encoded_value = config.get("WEBDAV_" + key + "_B64")
        if encoded_value is None:
            encoded_value = config.get("CD2_WEBDAV_" + key + "_B64", "")
        try:
            value = configuration.plain(base64.b64decode(encoded_value, validate=True).decode("utf-8"))
        except (ValueError, UnicodeError):
            log(label + "未保存或格式无法安全显示；请在私有终端核对，不会重置。")
            continue
        ui.reveal(label, value)
    if product.is_openlist:
        log("OpenList 仅保存初始化管理员密码；若已在管理页更改，它不代表当前密码。")
        try:
            value = configuration.plain(config.get("OPENLIST_ADMIN_PASSWORD", ""))
        except ValueError:
            value = ""
        if value:
            ui.reveal("OpenList 初始化管理员密码（可能已更改）", value)
        else:
            log("未保存可显示的 OpenList 初始化管理员密码；不会重置。")


def collect_config(ui: Terminal, product: ProductProfile, *, storage: tuple[str, str] | None = None) -> dict[str, str]:
    def api_hash(value: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{32}", value):
            raise ValueError("API Hash 格式不正确")
        return value

    def token(value: str) -> str:
        if not re.fullmatch(r"[0-9]{6,12}:[A-Za-z0-9_-]{20,}", value):
            raise ValueError("Bot Token 格式不正确")
        return value

    def target(value: str) -> str:
        value = value.strip().strip("/")
        if value:
            configuration.plain(value)
        if "\\" in value or any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("目标路径不能包含父目录或反斜杠")
        return value

    def timezone(value: str) -> str:
        ZoneInfo(value)
        return value

    values = {
        "api_id": ui.ask("Telegram API ID", validate=configuration.positive),
        "api_hash": ui.ask("Telegram API Hash（隐藏输入）", secret=True, validate=api_hash),
        "bot_token": ui.ask("Bot Token（隐藏输入）", secret=True, validate=token),
        "user_id": ui.ask("允许使用 Bot 的 Telegram 用户 ID", validate=configuration.positive),
        "webdav_user": ui.ask("专用 WebDAV 用户名", default=product.webdav_username or "tg2cloud"),
        "webdav_password": ui.ask("WebDAV 密码（留空安全生成）", secret=True, default=secrets.token_urlsafe(21)),
        "target": ui.ask("WebDAV 根目录下的子目录（根目录已选中目标时留空）", validate=target),
        "budget": storage[0] if storage else ui.ask("本地任务预算 GB", default="20", validate=configuration.size_gb),
        "reserve": storage[1] if storage else ui.ask("磁盘最少保留 GB", default="8", validate=configuration.size_gb),
        "timezone": ui.ask("时区", default="Asia/Shanghai", validate=timezone),
        "admin_password": secrets.token_urlsafe(21),
    }
    if float(values["reserve"]) < 8:
        raise ValueError("首版首次安装的磁盘保留空间不能低于 8GB")
    return configuration.new_config(product, values)


def preview(plan: install.Plan, release: releases.Release, log: SafeLog) -> None:
    instance = plan.instance
    labels = {"install": "首次安装", "upgrade": "保留配置升级", "current": "已是最新，不重建", "newer": "高于 latest，不降级"}
    log(f"{instance.product.display_name}：{labels[plan.action]}；{instance.version or '未安装'} → {release.version}")
    log("安装目录：" + str(instance.directory))
    if plan.action == "upgrade":
        log("保留 .env、Session、SQLite、downloads 和云网关数据；所选 Bot 将短暂停止，执行现有备份/回退流程。")
        log("复用安装器的 APT 基础依赖检查，可能更新相关系统软件包；不主动升级 Docker 引擎。")
    if plan.action == "install":
        log("将通过现有安装器安装 APT/Docker 依赖及固定镜像；配置只保存在本机私有文件。")
        if plan.config:
            log("任务预算/保留空间 GB：" + plan.config["LOCAL_TEMP_BUDGET_GB"] + " / " + plan.config["MIN_FREE_DISK_GB"])
    log("HTTPS：" + ("显式配置 " + (plan.domain or "尚需收集域名") if plan.configure_https else "不修改现有路由/证书"))
    log("不切换另一 Edition 的域名，不迁移 TG115；不会重启未选中的 Bot。")
