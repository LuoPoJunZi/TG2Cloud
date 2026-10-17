"""Independent CLI. Parsing/help never imports Bot or probes Docker."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

ACTIONS = ("install", "status", "check", "enable", "disable", "configure", "uninstall", "upgrade", "print-config")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="TG2Cloud 外部 WebDAV：独立只读 HTTPS 附加功能（不安装 Bot）")
    result.add_argument("action", nargs="?", choices=ACTIONS)
    result.add_argument("--edition", choices=("clouddrive2", "openlist"))
    result.add_argument("--install-dir", help="已有受管实例的实际安装目录（须通过容器身份校验）")
    result.add_argument("--sample-file", default="", help="读取验收可选：现有文件的未编码相对名称；仅 HEAD/OPTIONS/单字节 Range")
    return result


def source_root() -> Path:
    return Path(os.environ.get("TG2CLOUD_SOURCE_ROOT", Path(__file__).resolve().parents[4]))


def source_identity(root: Path) -> dict:
    path = root / "installation.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    # The bootstrap only creates this marker after verified stable extraction.
    path = root / ".external-webdav-source.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    from tg2cloud.version import VERSION
    return {"source": "local-reviewed-source", "version": VERSION}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    os.umask(0o077)
    from tg2cloud.cli.commands import interrupted
    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), interrupted)
    from tg2cloud.addons.external_webdav import discovery
    from tg2cloud.addons.external_webdav.service import Service
    from tg2cloud.cli.terminal import Terminal
    from tg2cloud.deployment.host import LocalSession, SafeLog
    from tg2cloud.deployment.profiles import PRODUCTS

    log, ui = SafeLog(), None
    try:
        session = LocalSession(log)
        # Help has already exited above. Offline status still needs local Linux
        # root/private records, but never contacts GitHub, Docker or the gateway.
        if args.action not in {"status", "print-config"}:
            discovery.host(session)
        elif os.name != "posix" or os.geteuid() != 0:
            raise ValueError("本地状态仅允许 Linux root 读取。")
        if args.edition is None or args.action is None or args.action not in {"status", "print-config"}:
            ui = Terminal()
        if args.edition is None:
            # Never silently choose when two Editions exist. Selection is cheap
            # and explicit even before probing a custom instance directory.
            args.edition = ui.ask("选择 Edition：clouddrive2 / openlist", validate=lambda value: value if value in PRODUCTS else "")
            if args.edition not in PRODUCTS:
                raise ValueError("必须明确选择 Edition。")
        service = Service(PRODUCTS[args.edition], session, log, ui)
        if args.action is None:
            log("TG2Cloud 外部 WebDAV（独立功能，不进入主安装向导）")
            log("操作：" + " / ".join(ACTIONS))
            args.action = ui.ask("选择操作", default="status" if service.record() else "install",
                                 validate=lambda value: value if value in ACTIONS else "")
            if args.action not in ACTIONS:
                raise ValueError("未知操作。")
        if args.action in {"install", "configure"}:
            identity = source_identity(source_root())
            log("附加功能代码来源：" + identity.get("source", "unknown") + "；正式资产标记 " + identity.get("tag", "无（本地审阅源码）"))
            changed = service.configure(install_dir=args.install_dir, install=args.action == "install", sample_file=args.sample_file)
            if changed and service.record() is not None and service.record()["phase"] == "enabled":
                with service.locked():
                    service.install_runtime(source_root(), source_identity(source_root()))
        elif args.action == "upgrade":
            item = service.record()
            if item is None:
                raise ValueError("尚未安装；请先运行 install。")
            service.preflight(item["instance_dir"])
            log("升级仅更换附加功能离线维护代码并重新校验代理；不升级 Bot／网关，不自动更改账号。")
            if ui.confirm("确认从最新正式稳定 Release 下载并校验候选？"):
                from tg2cloud.addons.external_webdav.releases import download
                from tg2cloud.deployment.releases import source_version, version_tuple
                with tempfile.TemporaryDirectory(prefix="tg2cloud-webdav-upgrade-") as directory:
                    root, identity = download(Path(directory))
                    if version_tuple(source_version(root)) < version_tuple(source_version(source_root())):
                        raise ValueError("拒绝自动降级附加功能代码。")
                    # Execute the verified candidate, not just the old checker.
                    # No secret is passed in argv/env; candidate asks on /dev/tty.
                    action = "enable" if item["phase"] == "enabled" else "check"
                    result = subprocess.run(  # nosec B603
                        [sys.executable, "-B", str(root / "scripts/run_source.py"), "webdav", action,
                         "--edition", args.edition, *(["--sample-file", args.sample_file] if args.sample_file else [])], check=False,
                    )
                    if result.returncode:
                        raise ValueError("候选检查／配置未通过；离线维护入口未切换，请检查外部入口状态。")
                    with service.locked():
                        service.preflight(item["instance_dir"])
                        service.install_runtime(root, identity)
                    log("候选源码已校验并切换；使用 tg2cloud-webdav check 复核。旧运行目录仍保留。")
        else:
            service.maintain(args.action, sample_file=args.sample_file)
        return 0
    except (KeyboardInterrupt, EOFError):
        log("操作中断；已撤销的入口不会退回匿名或 Bot 凭据，请运行 status／configure 核对。")
        return 130
    except (ValueError, RuntimeError, OSError) as exc:
        log("EXTERNAL_WEBDAV=FAILED：" + (str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__))
        return 1
    except Exception as exc:  # noqa: BLE001 - never print raw response/traceback containing credentials
        log("EXTERNAL_WEBDAV=FAILED：未确认的运行错误（" + type(exc).__name__ + "），请核对本地状态；未声称回退成功。")
        return 1
    finally:
        if ui is not None:
            ui.close()


if __name__ == "__main__":
    from tg2cloud.cli.commands import interrupted
    signal.signal(signal.SIGTERM, interrupted)
    raise SystemExit(main())
