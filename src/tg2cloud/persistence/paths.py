"""One database identity for fresh installs and existing TG2Cloud instances.

Never rename/copy a live SQLite file, merge histories or create a replacement
when an ambiguous database/sidecar is present. No Bot dependencies or schema work.
"""
from __future__ import annotations

import argparse
import stat
import sys
from pathlib import Path

DATABASE_NAME = "tg2cloud.db"
LEGACY_DATABASE_NAME = "tg115.db"
DATABASE_NAMES = (DATABASE_NAME, LEGACY_DATABASE_NAME)
SIDECARS = ("-wal", "-shm", "-journal")


def database_path(directory: Path, *, require_existing: bool = False) -> Path:
    directory = directory.absolute()
    if directory.resolve() != directory or directory.is_symlink():
        raise ValueError("数据库目录经过链接；停止，不创建或移动数据库")
    present = []
    for name in DATABASE_NAMES:
        path = directory / name
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("数据库不是安全的独立常规文件；停止")
            present.append(path)
        for suffix in SIDECARS:
            sidecar = directory / (name + suffix)
            if sidecar.exists() or sidecar.is_symlink():
                info = sidecar.lstat()
                if sidecar.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or path not in present:
                    raise ValueError("数据库旁文件归属不明确；停止，不创建替代数据库")
    if len(present) > 1:
        raise ValueError("同时发现 tg2cloud.db 和旧数据库；请先核对备份与任务记录，不自动选择或合并")
    if present:
        return present[0]
    if require_existing:
        raise ValueError("业务数据库不存在；不会创建空数据库替代")
    return directory / DATABASE_NAME


def database_entry(names) -> str:
    selected = {"data/" + name for name in DATABASE_NAMES} & set(names)
    if len(selected) != 1:
        raise ValueError("备份必须包含唯一的业务数据库；不接受缺失或多个数据库")
    return selected.pop()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="只读核对 TG2Cloud 数据库文件名，不创建或迁移")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        print(database_path(args.directory).name)
        return 0
    except (ValueError, OSError):
        print("数据库身份不明确或路径不安全；停止，不修改现有数据。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
