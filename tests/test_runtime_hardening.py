"""Private files, stdin credentials and bounded logs use isolated test data."""

import asyncio
import configparser
import json
import os
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from tg2cloud.compose.packaging import render
from tg2cloud.deployment.proxy.rendering import render_compose
from tg2cloud.persistence.private import private_file
from tg2cloud.persistence.sqlite import TaskDB
from tg2cloud.storage.rclone import RcloneClient, RcloneError
from tg2cloud.telegram.client import create_client

ROOT = Path(__file__).resolve().parents[1]
SECRET = "SYNTHETIC_password_不回显%[]"
OBSCURED = "a" * 40


class CredentialTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def client(self, edition="clouddrive2"):
        return RcloneClient(
            SimpleNamespace(
                rclone_config_path=self.root / "rclone.conf",
                cd2_url="http://127.0.0.1:1234/dav/",
                cd2_user="测试用户",
                cd2_password=SECRET,
                rclone_remote_name="openlist" if edition == "openlist" else "cd2",
            )
        )

    async def test_both_editions_use_stdin_preserve_options_and_only_initialize_once(
        self,
    ):
        for edition in ("clouddrive2", "openlist"):
            with self.subTest(edition=edition):
                client = self.client(edition)
                path = client.settings.rclone_config_path
                path.write_text(
                    "[archive]\ntype = local\ncustom = 100%\n["
                    + client.remote_name
                    + "]\ntype = webdav\ntimeout = 45s\n",
                    encoding="utf-8",
                )
                client._run = AsyncMock(return_value=(0, OBSCURED, ""))
                await asyncio.gather(client.ensure_config(), client.ensure_config())
                client._run.assert_awaited_once_with(
                    "obscure",
                    "-",
                    input_data=(SECRET + "\n").encode(),
                    timeout=30,
                    check=False,
                )
                self.assertNotIn(SECRET, json.dumps(client._run.call_args.args))
                parser = configparser.RawConfigParser()
                parser.read(path, encoding="utf-8")
                self.assertEqual(parser.get("archive", "custom"), "100%")
                self.assertEqual(parser.get(client.remote_name, "timeout"), "45s")
                self.assertEqual(parser.get(client.remote_name, "user"), "测试用户")
                self.assertEqual(parser.get(client.remote_name, "pass"), OBSCURED)
                self.assertNotIn(SECRET, path.read_text(encoding="utf-8"))
                if os.name == "posix":
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(list(self.root.glob(".rclone-*")), [])

    async def test_configuration_failure_or_interrupt_preserves_previous_file(self):
        for mode in (
            "failed_obscure",
            "malformed_output",
            "write_failure",
            "cancelled",
            "concurrent_change",
        ):
            with self.subTest(mode=mode):
                client = self.client()
                path = client.settings.rclone_config_path
                original = b"[cd2]\ntype = webdav\npass = previous\n"
                path.write_bytes(original)

                async def obscure(
                    *args, mode=mode, path=path, original=original, **kwargs
                ):
                    if mode == "cancelled":
                        raise asyncio.CancelledError()
                    if mode == "concurrent_change":
                        path.write_bytes(original + b"# other writer\n")
                    return (
                        (1, SECRET, SECRET)
                        if mode == "failed_obscure"
                        else (0, SECRET if mode == "malformed_output" else OBSCURED, "")
                    )

                client._run = obscure
                context = (
                    patch(
                        "tg2cloud.storage.rclone.os.replace",
                        side_effect=OSError("synthetic replace error"),
                    )
                    if mode == "write_failure"
                    else nullcontext()
                )
                with (
                    context,
                    self.assertRaises(
                        (RcloneError, OSError, asyncio.CancelledError)
                    ) as caught,
                ):
                    await client.ensure_config()
                self.assertNotIn(SECRET, str(caught.exception))
                self.assertFalse(client._config_ready)
                self.assertEqual(
                    path.read_bytes(),
                    original
                    + (b"# other writer\n" if mode == "concurrent_change" else b""),
                )
                self.assertEqual(list(self.root.glob(".rclone-*")), [])

    async def test_unsafe_config_is_never_overwritten(self):
        client = self.client()
        path = client.settings.rclone_config_path
        path.write_text("private invalid configuration", encoding="utf-8")
        client._run = AsyncMock()
        with self.assertRaises(RcloneError):
            await client.ensure_config()
        self.assertEqual(path.read_text(), "private invalid configuration")
        client._run.assert_not_called()
        client.settings.cd2_password = "bad\npassword"
        with self.assertRaises(RcloneError):
            await client.ensure_config()

    async def test_subprocess_receives_password_only_via_pipe(self):
        client = self.client()
        process = SimpleNamespace(
            returncode=0, communicate=AsyncMock(return_value=(OBSCURED.encode(), b""))
        )
        with patch(
            "tg2cloud.storage.rclone.asyncio.create_subprocess_exec",
            AsyncMock(return_value=process),
        ) as launch:
            await client.ensure_config()
        self.assertEqual(launch.call_args.kwargs["stdin"], asyncio.subprocess.PIPE)
        self.assertNotIn(SECRET, " ".join(launch.call_args.args))
        process.communicate.assert_awaited_once_with((SECRET + "\n").encode())

    async def test_cancelled_credential_process_is_reaped_and_old_config_retained(self):
        client = self.client()
        path = client.settings.rclone_config_path
        path.write_bytes(b"[cd2]\ntype=webdav\n")
        old = path.read_bytes()
        process = Mock(returncode=None)
        process.communicate = AsyncMock(side_effect=asyncio.CancelledError())
        process.wait = AsyncMock(return_value=-15)
        with (
            patch(
                "tg2cloud.storage.rclone.asyncio.create_subprocess_exec",
                AsyncMock(return_value=process),
            ),
            self.assertRaises(asyncio.CancelledError),
        ):
            await client.ensure_config()
        process.terminate.assert_called_once()
        process.wait.assert_awaited()
        self.assertEqual(path.read_bytes(), old)


class PrivateFileTests(unittest.TestCase):
    def test_existing_database_and_session_keep_content_identity_and_private_sidecars(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dbpath = root / "tg115.db"
            db = TaskDB(dbpath)
            task, _ = db.create_task(
                chat_id=1,
                message_id=1,
                sender_id=1,
                file_name="synthetic.bin",
                file_size=1,
            )
            before = dbpath.stat().st_ino
            db.close()
            dbpath.chmod(0o644)
            db = TaskDB(dbpath)
            try:
                self.assertEqual(db.get(task["id"])["file_name"], "synthetic.bin")
                self.assertEqual(before, dbpath.stat().st_ino)
                if os.name == "posix":
                    for p in (dbpath, root / "tg115.db-wal", root / "tg115.db-shm"):
                        if p.exists():
                            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            finally:
                db.close()
            session = root / "bot.session"
            session.write_bytes(b"synthetic preserved session")
            inode = session.stat().st_ino
            with patch("tg2cloud.telegram.client.TelegramClient") as constructor:
                create_client(
                    SimpleNamespace(data_dir=root, api_id=123, api_hash="synthetic")
                )
            self.assertEqual(session.read_bytes(), b"synthetic preserved session")
            self.assertEqual(session.stat().st_ino, inode)
            if os.name == "posix":
                self.assertEqual(session.stat().st_mode & 0o777, 0o600)
            self.assertEqual(constructor.call_args.args[0], str(root / "bot"))

    def test_real_telethon_session_keeps_the_existing_authorization(self):
        from telethon.crypto import AuthKey

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = SimpleNamespace(
                data_dir=root, api_id=12345, api_hash="synthetic-offline-only"
            )
            first = create_client(settings)
            first.session.auth_key = AuthKey(b"x" * 256)
            first.session.save()
            first.session.close()
            session = root / "bot.session"
            inode = session.stat().st_ino
            session.chmod(0o644)
            second = create_client(settings)
            try:
                self.assertEqual(second.session.auth_key.key, b"x" * 256)
                self.assertEqual(session.stat().st_ino, inode)
                if os.name == "posix":
                    self.assertEqual(session.stat().st_mode & 0o777, 0o600)
            finally:
                second.session.close()

    def test_link_hardlink_and_other_owner_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "private"
            path.write_bytes(b"keep")
            with (
                patch(
                    "tg2cloud.persistence.private.os.fstat",
                    return_value=SimpleNamespace(
                        st_mode=0o100644,
                        st_nlink=2,
                        st_dev=path.stat().st_dev,
                        st_ino=path.stat().st_ino,
                    ),
                ),
                self.assertRaises(ValueError),
            ):
                private_file(path)
            with (
                patch.object(Path, "resolve", return_value=path.with_name("other")),
                self.assertRaises(ValueError),
            ):
                private_file(path)
            if os.name == "posix":
                info = path.stat()
                with (
                    patch(
                        "tg2cloud.persistence.private.os.fstat",
                        return_value=SimpleNamespace(
                            st_mode=info.st_mode,
                            st_nlink=1,
                            st_uid=os.geteuid() + 1,
                            st_dev=info.st_dev,
                            st_ino=info.st_ino,
                        ),
                    ),
                    self.assertRaises(ValueError),
                ):
                    private_file(path)
            self.assertEqual(path.read_bytes(), b"keep")


class LogRotationTests(unittest.TestCase):
    def test_both_editions_managed_direct_compose_and_shared_proxy_are_bounded(self):
        expected = 'max-size: "10m"\n        max-file: "3"'
        for edition in ("clouddrive2", "openlist"):
            managed = (
                ROOT / "packaging/compose" / ("docker-compose." + edition + ".yml")
            ).read_text()
            direct = render(ROOT, edition, "ghcr.io/example/tg2cloud:v1.5.5")
            self.assertEqual(managed.count(expected), 2)
            self.assertEqual(direct.count(expected), 3)
            self.assertEqual(direct.count("driver: json-file"), 3)
        proxy = render_compose(("synthetic.example",))
        self.assertEqual(proxy.count(expected), 2)
        self.assertNotIn("daemon.json", proxy)
