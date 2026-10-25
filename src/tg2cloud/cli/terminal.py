from __future__ import annotations

import base64
import re
import secrets
import string
from contextlib import ExitStack
from zoneinfo import ZoneInfoNotFoundError

from tg2cloud.deployment import configuration, install, releases
from tg2cloud.deployment.host import SafeLog
from tg2cloud.deployment.profiles import ProductProfile
from tg2cloud.deployment.proxy.state import (
    ProxyEnvironment,
    dns_diagnostic,
    validate_public_ipv4,
)


class Terminal:
    friendly = False

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

    def read_line(self) -> str:
        # TextIOWrapper.readline() can prefetch later answers. A parent menu
        # must leave those bytes for the independent child manager's /dev/tty.
        raw = self.tty.buffer.raw
        line = bytearray()
        while len(line) <= 16384:
            part = raw.read(1)
            if not part:
                break
            line.extend(part)
            if part == b"\n":
                break
        if len(line) > 16384:
            raise ValueError("输入过长，请分项填写。")
        return line.decode("utf-8", errors="replace")

    def ask(self, prompt: str, *, default: str = "", secret: bool = False, validate=configuration.plain) -> str:
        import termios

        while True:
            previous = termios.tcgetattr(self.tty.fileno())
            active = previous.copy()
            # Recover normal-field echo even if the caller inherited echo-off.
            # Keep password newlines private too; restore all flags on failure.
            active[0] &= ~(getattr(termios, "IGNCR", 0) | getattr(termios, "INLCR", 0))
            active[0] |= getattr(termios, "ICRNL", 0)
            active[3] |= getattr(termios, "ICANON", 0)
            active[3] = (active[3] & ~(termios.ECHO | getattr(termios, "ECHONL", 0))
                         if secret else active[3] | termios.ECHO)
            try:
                termios.tcsetattr(self.tty.fileno(), termios.TCSANOW, active)
                suffix = (f"（回车默认 {default}）" if self.friendly is True else f" [{default}]") if default and not secret and "回车默认" not in prompt else ""
                self.output.write(prompt + suffix + ": ")
                self.output.flush()
                line = self.read_line()
            finally:
                termios.tcsetattr(self.tty.fileno(), termios.TCSANOW, previous)
                if secret:
                    self.output.write("\n")
                    self.output.flush()
            if not line:
                raise EOFError("输入已中断")
            value = line.rstrip("\r\n")
            # Some SSH/web terminals retain bracketed-paste delimiters. Only
            # strip one complete envelope, never arbitrary embedded controls.
            if value.startswith("\x1b[200~") and value.endswith("\x1b[201~"):
                value = value[6:-6]
            value = value or default
            try:
                return validate(value)
            except (ValueError, ZoneInfoNotFoundError):
                self.output.write("输入格式不正确，请重新填写（不显示输入值）。\n")
                self.output.flush()

    def confirm(self, prompt: str) -> bool:
        if self.friendly is True:
            return self.ask(prompt + "（y/N）", validate=lambda text: text.lower()) == "y"
        return self.ask(prompt + " [y/N]", default="n", validate=lambda text: text.lower()) == "y"

    def private(self, label: str, value: str) -> None:
        """Confirmed setup output goes only to the controlling private terminal."""
        if not self.output.isatty():
            raise RuntimeError("凭据只能在当前交互终端显示")
        self.output.write(configuration.plain(label) + "：" + configuration.plain(value) + "\n")
        self.output.flush()

    def reveal(self, label: str, value: str) -> None:
        if self.confirm("是否仅在当前终端显示" + label + "？请确保没有旁观/录屏"):
            self.output.write(label + ": " + value + "\n")
            self.output.flush()


def confirm_nat_public_ipv4(ui: Terminal, domain: str, environment: ProxyEnvironment, log: SafeLog) -> str:
    """Ask the operator for an independent console value; never prefill DNS."""
    log("域名 " + domain + " 未匹配本机网卡，可能使用公网 NAT。")
    log(dns_diagnostic(environment, "127.0.0.1"))
    address = ui.ask("云控制台分配给本机的公网 IPv4（留空取消）",
                     validate=lambda value: validate_public_ipv4(value) if value else "")
    if not address:
        return ""
    if address not in environment.dns_a:
        raise ValueError("云控制台公网 IPv4 与域名 A 记录不一致，请核对 DNS；未放行 HTTPS。")
    if not ui.confirm("确认该公网 IPv4 直接映射到本机，且已配置 80/443 入站规则？"):
        return ""
    log("本次已人工确认 NAT 公网 IPv4；公网入站仍须通过证书签发及后续外部验收。")
    return address


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


def show_setup_credentials(ui: Terminal, product: ProductProfile, config: dict[str, str], log: SafeLog) -> None:
    """Only a fresh, explicitly confirmed installation uses consolidated output."""
    if getattr(ui, "friendly", False) is not True:
        show_credentials(ui, product, config, log)
        return
    log("\n── 后台账号设置 ──\n请在自己的管理页挂载云存储，再创建以下专用 WebDAV 用户。凭据仅显示在当前终端，请勿录屏。")
    for key, label in (("USERNAME", "WebDAV 用户名"), ("PASSWORD", "WebDAV 密码")):
        encoded = config.get("WEBDAV_" + key + "_B64", config.get("CD2_WEBDAV_" + key + "_B64", ""))
        ui.private(label, base64.b64decode(encoded, validate=True).decode("utf-8"))
    target = base64.b64decode(config.get("WEBDAV_TARGET_PATH_B64", config.get("CD2_TARGET_PATH_B64", "")), validate=True).decode("utf-8")
    log("Bot 保存子目录：" + (target or "未设置，使用该 WebDAV 账号根目录（在管理页设置）"))
    if product.is_openlist and config.get("OPENLIST_ADMIN_PASSWORD"):
        ui.private("OpenList 初始化管理员密码（后台已改密时不代表当前密码）", config["OPENLIST_ADMIN_PASSWORD"])


def generated_password() -> str:
    # Only the Bot's default WebDAV password changes. Admin/add-on policies stay separate.
    alphabet = string.ascii_letters + string.digits
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(8))
        if any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value):
            return value


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

    values = {
        "api_id": ui.ask("Telegram API ID", validate=configuration.positive),
        "api_hash": ui.ask("Telegram API Hash（隐藏输入）", secret=True, validate=api_hash),
        "bot_token": ui.ask("Bot Token（隐藏输入）", secret=True, validate=token),
        "user_id": ui.ask("允许使用 Bot 的 Telegram 用户 ID", validate=configuration.positive),
        "webdav_user": ui.ask("WebDAV 用户名（回车默认 tg2cloud）", default="tg2cloud"),
        "webdav_password": ui.ask("WebDAV 密码（回车自动生成；隐藏输入）", secret=True, default=generated_password()),
        "target": ui.ask("Bot 保存子目录（可留空；账号根目录在管理页设置）", validate=target),
        "budget": storage[0] if storage else ui.ask("本地任务预算 GB", default="20", validate=configuration.size_gb),
        "reserve": storage[1] if storage else ui.ask("磁盘最少保留 GB", default="8", validate=configuration.size_gb),
        "timezone": "Asia/Shanghai",
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
