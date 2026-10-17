"""Lazy Linux command dispatch; importing/help needs only the standard library."""
from __future__ import annotations

import argparse
import signal
import sys


def interrupted(_signal, _frame):
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TG2Cloud Linux 安装与维护入口")
    parser.add_argument("command", choices=("install", "lan", "uninstall"))
    # Leave every existing Edition-specific option to its original parser.
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        parser.print_help()
        return 0
    args = parser.parse_args(arguments[:1])
    remaining = arguments[1:]
    if args.command == "install":
        from .vps import main as operation
    elif args.command == "lan":
        from tg2cloud.deployment.proxy.lan import main as operation
    else:
        from tg2cloud.deployment.uninstall import main as operation
    signal.signal(signal.SIGTERM, interrupted)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, interrupted)
    return operation(remaining)
