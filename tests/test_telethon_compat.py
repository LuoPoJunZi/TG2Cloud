from __future__ import annotations

import io
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telethon import Button, TelegramClient, events
from telethon.crypto import AuthKey
from telethon.extensions import BinaryReader
from telethon.sessions import MemorySession, SQLiteSession
from telethon.tl import functions, types

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / "payload_clouddrive2"))

from app.bot_commands import CommandMixin
from app.main import TransferService


def callback_data(button: object) -> bytes:
    """Read callback payloads in both layer 227 and layer 229 button types."""
    data = getattr(button, "data", None)
    if data is None:
        data = getattr(getattr(button, "type", None), "data", None)
    if not isinstance(data, bytes):
        raise TypeError("Expected an inline callback button with bytes data")
    return data


class TelethonContractTests(unittest.IsolatedAsyncioTestCase):
    """Exercise real library objects offline; never authenticate to Telegram."""

    async def asyncSetUp(self) -> None:
        session = MemorySession()
        session.set_dc(2, "203.0.113.1", 443)
        self.client = TelegramClient(
            session, 12345, "a" * 32,
            request_retries=5, connection_retries=10,
            retry_delay=3, auto_reconnect=True,
        )
        self.connect_guard = patch.object(
            self.client, "connect",
            AsyncMock(side_effect=AssertionError("Offline test must not connect")),
        )
        self.connect_guard.start()
        self.addCleanup(self.connect_guard.stop)

    async def asyncTearDown(self) -> None:
        self.client.connect.assert_not_awaited()
        await self.client.disconnect()

    def test_callback_buttons_keep_payload_after_markup_serialization(self) -> None:
        buttons = CommandMixin._home_buttons()
        markup = self.client.build_reply_markup(buttons)
        self.assertIsInstance(markup, types.ReplyInlineMarkup)
        with BinaryReader(bytes(markup)) as reader:
            restored = reader.tgread_object()
        self.assertEqual(
            [[callback_data(button) for button in row.buttons] for row in restored.rows],
            [[b"queue:1", b"vps_resources", b"refresh:home"]],
        )
        self.assertEqual(
            [[button.text for button in row.buttons] for row in restored.rows],
            [["📋", "🖥", "🔄"]],
        )
        with self.assertRaises(TypeError):
            callback_data(Button.url("Not a callback", "https://example.com"))

    def test_event_handlers_register_without_connecting(self) -> None:
        async def message_handler(_event):
            return None

        async def callback_handler(_event):
            return None

        service = SimpleNamespace(
            client=self.client, _on_message=message_handler, _on_callback=callback_handler,
        )
        TransferService._register_handlers(service)
        handlers = self.client.list_event_handlers()
        self.assertEqual([handler for handler, _ in handlers], [message_handler, callback_handler])
        self.assertIsInstance(handlers[0][1], events.NewMessage)
        self.assertTrue(handlers[0][1].incoming)
        self.assertIsInstance(handlers[1][1], events.CallbackQuery)

    async def test_real_document_download_to_file_and_async_stream(self) -> None:
        payload = bytes(range(256)) * 41
        document = types.Document(
            id=17, access_hash=23, file_reference=b"offline-reference",
            date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            mime_type="application/octet-stream", size=len(payload), dc_id=2,
            attributes=[types.DocumentAttributeFilename("offline.bin")],
        )

        async def get_file(_sender, request, **_kwargs):
            self.assertIsInstance(request, functions.upload.GetFileRequest)
            self.assertEqual(request.location.id, document.id)
            self.assertEqual(request.location.file_reference, document.file_reference)
            return types.upload.File(
                type=types.storage.FileUnknown(), mtime=0,
                bytes=payload[request.offset:request.offset + request.limit],
            )

        class AsyncSink(io.BytesIO):
            async def write(self, chunk: bytes) -> int:
                return super().write(chunk)

        with patch.object(self.client, "_call", side_effect=get_file) as rpc:
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "离线下载.bin"
                progress = AsyncMock()
                result = await self.client.download_media(
                    types.MessageMediaDocument(document=document),
                    file=str(target), progress_callback=progress,
                )
                self.assertEqual(result, str(target))
                self.assertEqual(target.read_bytes(), payload)
                self.assertEqual(progress.await_args.args, (len(payload), len(payload)))
            sink = AsyncSink()
            progress = AsyncMock()
            location = types.InputDocumentFileLocation(17, 23, b"offline-reference", "")
            await self.client.download_file(
                location, file=sink, part_size_kb=4, file_size=len(payload),
                progress_callback=progress, dc_id=2,
            )
            self.assertEqual(sink.getvalue(), payload)
            self.assertEqual(progress.await_args.args, (len(payload), len(payload)))
            self.assertGreaterEqual(progress.await_count, 3)
            self.assertGreaterEqual(rpc.await_count, 4)
            self.assertFalse(sink.closed)
            sink.close()

    def test_sqlite_session_reopens_without_losing_state_or_entities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "offline-bot")
            session = SQLiteSession(path)
            try:
                session.set_dc(2, "203.0.113.1", 443)
                session.auth_key = AuthKey(data=b"a" * 256)
                session.process_entities(types.contacts.ResolvedPeer(
                    peer=types.PeerUser(17), chats=[],
                    users=[types.User(id=17, access_hash=23, username="offline_test")],
                ))
                session.set_update_state(0, types.updates.State(
                    pts=7, qts=0, date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    seq=9, unread_count=0,
                ))
                session.save()
            finally:
                session.close()
            restored = SQLiteSession(path)
            try:
                self.assertEqual(restored.dc_id, 2)
                self.assertEqual(restored.auth_key.key, b"a" * 256)
                self.assertEqual(restored.get_update_state(0).pts, 7)
                entity = restored.get_input_entity(types.PeerUser(17))
                self.assertEqual((entity.user_id, entity.access_hash), (17, 23))
            finally:
                restored.close()
