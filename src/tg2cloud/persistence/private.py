"""Tighten owned SQLite files without replacing their contents or identity."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def private_file(path: Path, *, create: bool = False) -> None:
    path = path.absolute()
    if path.resolve() != path:
        raise ValueError("私密文件路径经过链接；停止")
    info = None
    try:
        info = path.lstat()
    except FileNotFoundError:
        if not create:
            return
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    else:
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("私密文件必须是独立常规文件")
        flags = os.O_RDWR
    descriptor = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        current = os.fstat(descriptor)
        if (
            info is not None
            and (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino)
            or not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or os.name == "posix"
            and current.st_uid != os.geteuid()
        ):
            raise ValueError("私密文件归属不匹配；停止")
        if os.name == "posix":
            os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)


def private_sqlite(path: Path, *, create: bool = False) -> None:
    private_file(path)
    # SQLite derives new WAL/journal permissions from the main file. Tighten
    # existing sidecars before connecting; never unlink or checkpoint live data.
    for suffix in ("-wal", "-shm", "-journal"):
        private_file(path.with_name(path.name + suffix))
    if create:
        private_file(path, create=True)
