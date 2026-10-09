"""Local implementation of the HTTPS RemoteLike protocol (standard library only)."""

from __future__ import annotations

import base64
import os
import queue
import re
import shutil
import signal
import stat
import subprocess  # nosec B404
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path


class SafeLog:
    def __init__(self, emit: Callable[[str], None] = print) -> None:
        self.emit = emit
        self.secrets: set[str] = set()

    def register(self, values: dict[str, str]) -> None:
        for key, value in values.items():
            if any(word in key.upper() for word in ("PASSWORD", "TOKEN", "HASH", "SECRET")):
                if value:
                    self.secrets.add(value)
                if key.endswith("_B64"):
                    try:
                        self.secrets.add(base64.b64decode(value, validate=True).decode("utf-8"))
                    except (ValueError, UnicodeError):
                        pass

    def clean(self, text: str) -> str:
        for secret in sorted(self.secrets, key=len, reverse=True):
            if secret:
                text = text.replace(secret, "[REDACTED]")
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        text = re.sub(r"[0-9]{6,12}:[A-Za-z0-9_-]{20,}", "[REDACTED_BOT_TOKEN]", text)
        text = re.sub(r"(?i)(https?://)[^\s/:@]+:[^\s/@]+@", r"\1[REDACTED]@", text)
        text = re.sub(
            r'''(?im)^.*(?:["']?(?:authorization|(?:set[-_])?cookie|password|passwd|'''
            r'''(?:access[_-]|refresh[_-]|bot[_-]|oauth[_-])?token|api[_-]?(?:hash|key)|'''
            r'''secret)["']?\s*[:=]|密码\s*[:：]).*$''',
            "[REDACTED]", text,
        )
        return text

    def __call__(self, text: str) -> None:
        self.emit(self.clean(text))


def stop_process(process: subprocess.Popen, *, grace: float = 150) -> None:
    """Give installer traps time to roll back; never kill unrelated processes."""
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


class LocalFiles:
    """Only the private, uniquely created HTTPS staging tree is writable here."""

    @staticmethod
    def validate(path: str) -> Path:
        target = Path(path)
        parts = target.parts
        if len(parts) < 3 or parts[:2] != ("/", "tmp"):
            raise ValueError("HTTPS 临时文件位置不安全")
        if not re.fullmatch(r"tg2cloud-proxy-[0-9a-f]{32}", parts[2]):
            raise ValueError("HTTPS 临时文件位置不安全")
        # Existing HTTPS code creates this private UUID staging tree.
        root = Path("/tmp") / parts[2]  # nosec B108
        if not root.is_dir() or root.is_symlink() or target.resolve() != target:
            raise ValueError("HTTPS 临时目录缺失或经过链接")
        info = root.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("HTTPS 临时目录所有者/权限不安全")
        return target

    def mkdir(self, path: str, mode: int) -> None:
        self.validate(path).mkdir(mode=mode)

    def put(self, source: str, destination: str) -> None:
        target = self.validate(destination)
        with Path(source).open("rb") as reader, target.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        target.chmod(0o600)

    def chmod(self, path: str, mode: int) -> None:
        self.validate(path).chmod(mode)

    def close(self) -> None:
        pass


class LocalSession:
    def __init__(self, log: SafeLog, *, bash: str = "bash") -> None:
        self.log = log
        self.bash = bash
        self.lock_process: subprocess.Popen | None = None

    def run(
        self, command: str, *, sudo: bool = False,
        stream: Callable[[str], None] | None = None, timeout: float | None = None,
    ) -> tuple[int, str]:
        if sudo:
            raise RuntimeError("请先以 root 运行入口；不在内部传递 sudo 密码")
        if self.lock_process is not None and self.lock_process.poll() is not None:
            raise RuntimeError("共享代理事务锁已丢失，停止后续操作")
        # Internally generated commands; validated inputs are shlex-quoted.
        process = subprocess.Popen(  # nosec B603
            [self.bash, "-c", command], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            start_new_session=os.name == "posix",
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
        )
        lines: queue.Queue[str | None] = queue.Queue()

        def read_output() -> None:
            try:
                for line in process.stdout:
                    lines.put(line)
            finally:
                lines.put(None)

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        captured: list[str] = []
        size = 0
        deadline = time.monotonic() + (timeout if timeout is not None else 1800)
        try:
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError("VPS 命令超时；已请求终止，请核对回退与运行状态")
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    continue
                if line is None:
                    break
                size += len(line)
                if size > 8 * 1024 * 1024:
                    raise RuntimeError("命令输出异常过大；停止并核对状态")
                # Raw data (e.g. Compose JSON) is only returned to its parser.
                captured.append(line)
                if stream:
                    stream(self.log.clean(line.rstrip("\n")))
            code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
            return code, "".join(captured)
        finally:
            stop_process(process)
            process.stdout.close()
            reader.join(timeout=1)

    def sftp(self) -> LocalFiles:
        return LocalFiles()

    @contextmanager
    def hold_lock(
        self, command: str, *, sudo: bool = False, timeout: float = 15,
    ) -> Iterator[None]:
        if sudo or self.lock_process is not None:
            raise RuntimeError("不支持嵌套代理锁或内部 sudo")
        # The existing backend generates the shared proxy lock command.
        process = subprocess.Popen(  # nosec B603
            [self.bash, "-c", command], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", start_new_session=os.name == "posix",
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
        )
        result: queue.Queue[str] = queue.Queue()
        reader = threading.Thread(target=lambda: result.put(process.stdout.readline()), daemon=True)
        reader.start()
        try:
            try:
                marker = result.get(timeout=timeout).strip()
            except queue.Empty as exc:
                raise TimeoutError("获取共享代理锁超时") from exc
            if marker != "TG2CLOUD_REMOTE_LOCK=ACQUIRED" or process.poll() is not None:
                raise RuntimeError("共享代理锁不可用或已被其他操作持有；没有修改 HTTPS")
            self.lock_process = process
            yield
        finally:
            self.lock_process = None
            if process.poll() is None:
                try:
                    process.stdin.write("TG2CLOUD_REMOTE_LOCK_RELEASE\n")
                    process.stdin.flush()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    stop_process(process)
            process.stdin.close()
            process.stdout.close()
            reader.join(timeout=1)


@contextmanager
def edition_lock(path: Path) -> Iterator[None]:
    # This additional lock coordinates CLI invocations. The existing Windows
    # base installer has no equivalent lock: do not run it concurrently.
    import fcntl

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.parent.resolve() != path.parent:
        raise RuntimeError("CLI 锁目录经过链接")
    info = path.parent.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError("CLI 锁目录所有者/权限不安全")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeError("CLI 锁文件所有者/权限不安全")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("另一个一键脚本正在操作此 Edition") from exc
        yield
    finally:
        os.close(descriptor)
