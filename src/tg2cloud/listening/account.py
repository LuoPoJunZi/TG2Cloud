"""Single optional personal client, separate from bot.session and terminal-only login."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import re
import stat
from contextlib import contextmanager

from tg2cloud.config import Settings

KEY = "listener_account"


def state(db):
    with db._lock:
        row = db._conn.execute(
            "SELECT value FROM service_meta WHERE key=?", (KEY,)
        ).fetchone()
        return (
            json.loads(row[0])
            if row
            else {"enabled": False, "account": None, "status": "未登录"}
        )


def write_state(db, *, expected=None, **changes):
    with db._lock:
        db._conn.execute("BEGIN IMMEDIATE")
        try:
            current = state(db)
            if expected is not None and current != expected:
                db._conn.execute("COMMIT")
                return None  # An awaited request cannot overwrite a newer authorization.
            value = current | changes
            db._conn.execute(
                "INSERT OR REPLACE INTO service_meta VALUES(?,?)",
                (KEY, json.dumps(value)),
            )
            db._conn.execute("COMMIT")
            return value
        except BaseException:
            db._conn.execute("ROLLBACK")
            raise


@contextmanager
def session_lock(settings):
    # The selected Bot's existing /data bind is UID 10001-owned. Never touch bot.session.
    import fcntl

    directory = settings.data_dir / "listener"
    if settings.data_dir.resolve() != settings.data_dir.absolute():
        raise ValueError("监听数据目录含符号链接")
    directory.mkdir(mode=0o700, exist_ok=True)
    if (
        directory.is_symlink()
        or directory.stat().st_uid != os.geteuid()
        or stat.S_IMODE(directory.stat().st_mode) != 0o700
    ):
        raise ValueError("监听目录必须由当前运行用户拥有且权限为 700")
    for name in (
        "personal.session",
        "personal.session-journal",
        "personal.session-wal",
        "personal.session-shm",
    ):
        path = directory / name
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
            ):
                raise ValueError("监听 Session 归属或权限不安全")
    fd = os.open(
        directory / "session.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    try:
        if (
            not stat.S_ISREG(os.fstat(fd).st_mode)
            or os.fstat(fd).st_uid != os.geteuid()
        ):
            raise ValueError("监听锁文件归属无效")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield directory / "personal"
    finally:
        os.close(fd)


def client(settings, path):
    from telethon import TelegramClient

    return TelegramClient(
        str(path),
        settings.api_id,
        settings.api_hash,
        request_retries=2,
        # Keep the final RPC error type so transient failures are not mistaken
        # for invalid configuration after Telethon exhausts its own retries.
        raise_last_call_error=True,
        connection_retries=2,
        retry_delay=5,
        flood_sleep_threshold=0,
        receive_updates=False,
    )


async def login(settings, db):
    if not os.isatty(0) or not os.isatty(1):
        raise ValueError("监听登录必须在交互终端执行；不要把验证码发送给 Bot")
    write_state(db, enabled=False, status="已停用，等待终端授权")
    # Give the Bot's optional component time to disconnect/release its Session lock.
    from contextlib import ExitStack

    with ExitStack() as stack:
        for attempt in range(15):
            try:
                path = stack.enter_context(session_lock(settings))
                break
            except BlockingIOError:
                if attempt == 14:
                    raise ValueError("监听 Session 正在使用，请稍后重新登录") from None
                await asyncio.sleep(1)
        old_umask = os.umask(0o077)
        personal = None
        try:
            personal = client(settings, path)

            def phone():
                value = input("个人账号手机号: ").strip()
                if not re.fullmatch(r"\+?[0-9]{5,18}", value):
                    raise ValueError("请使用个人手机号；不接受 Bot Token")
                return value

            await personal.start(
                phone=phone,
                code_callback=lambda: input("Telegram 验证码: ").strip(),
                password=lambda: getpass.getpass("两步验证密码（隐藏输入）: "),
            )
            me = await personal.get_me()
            if not me or getattr(me, "bot", None) is not False:
                raise ValueError("必须使用个人 Telegram 账号，不能使用 Bot")
            previous = state(db).get("account")
            if previous is not None and previous != me.id:
                raise ValueError(
                    "监听账号身份已变化；保留原来源和任务，不能切换身份读取"
                )
            write_state(db, account=me.id, enabled=False, status="已登录，监听停用")
            print(
                "个人账号授权已保存；在 Bot 的监听管理中启用。原 Bot Session 保持不变。"
            )
        finally:
            try:
                if personal is not None:
                    await personal.disconnect()
            finally:
                os.umask(old_umask)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="个人监听账号：仅在当前实例的交互终端授权"
    )
    parser.add_argument("action", choices=("login", "status", "disable"))
    args = parser.parse_args(argv)
    from tg2cloud.persistence.paths import database_path
    from tg2cloud.persistence.sqlite import TaskDB

    settings = Settings.from_env()
    db = TaskDB(database_path(settings.data_dir))
    try:
        if args.action == "login":
            asyncio.run(login(settings, db))
        elif args.action == "disable":
            write_state(db, enabled=False, status="已停用")
            print("监听已停用；来源、任务和 Session 保留。")
        else:
            print("监听账号：" + state(db)["status"])
        return 0
    except Exception:  # noqa: BLE001 - private boundary must not expose credentials
        print(
            "监听操作失败；请核对终端、Session 归属、账号授权与网络，不输出凭据或原始异常。"
        )
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
