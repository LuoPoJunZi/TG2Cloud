"""Lazy Linux command dispatch; importing/help needs only the standard library."""
from __future__ import annotations

import argparse
import signal
import sys


def interrupted(_signal, _frame):
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    from tg2cloud.version import VERSION

    parser = argparse.ArgumentParser(prog="tg2cloud", description="TG2Cloud Linux 安装与维护入口")
    parser.add_argument("--version", action="version", version="TG2Cloud CLI v" + VERSION)
    parser.add_argument("command", choices=("install", "lan", "uninstall", "webdav", "manage", "proxy", "naming-preview", "listen"), nargs="?", default="manage")
    # Leave every existing Edition-specific option to its original parser.
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(arguments[:1])
    remaining = arguments[1:]
    signal.signal(signal.SIGTERM, interrupted)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, interrupted)
    if args.command in {"install", "lan"} and not remaining:
        from .management import main as management
        return management([], mode_hint="public" if args.command == "install" else "lan")
    if args.command == "listen":
        from tg2cloud.deployment.listening import main as operation
    elif args.command == "naming-preview":
        from .naming import main as operation
    elif args.command == "proxy":
        from .proxy import main as operation
    elif args.command == "install":
        from .vps import main as operation
    elif args.command == "lan":
        from tg2cloud.deployment.proxy.lan import main as operation
    elif args.command == "webdav":
        from tg2cloud.addons.external_webdav.cli import main as operation
    elif args.command == "manage":
        from .management import main as operation
    else:
        from tg2cloud.deployment.uninstall import main as operation
    return operation(remaining)
