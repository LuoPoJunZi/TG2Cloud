"""Offline regression for the pinned SDK's real file iterator and safe waits."""
from __future__ import annotations

import asyncio
import inspect
import io
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from telethon import TelegramClient
from telethon.errors import FloodPremiumWaitError, FloodWaitError
from telethon.sessions import MemorySession
from telethon.tl import functions, types
from telethon.tl.functions.upload import GetCdnFileRequest, GetFileRequest

from tg2cloud.listening.transport import (
    MAX_CHUNK_WAITS,
    ListeningClient,
    download_scope,
)


def client():
    session = MemorySession()
    session.set_dc(2, "127.0.0.1", 443)
    return ListeningClient(session, 1234, "a" * 32, request_retries=0,
                           raise_last_call_error=True, flood_sleep_threshold=0,
                           receive_updates=False)


def request():
    return GetFileRequest(types.InputDocumentFileLocation(
        id=41, access_hash=42, file_reference=b"synthetic", thumb_size=""),
        offset=0, limit=4096)


class PremiumWaitTests(unittest.IsolatedAsyncioTestCase):
    def test_pinned_sdk_rpc_signature_matches_the_adapter(self):
        def parameters(method):
            return [(p.name, p.kind, p.default) for p in inspect.signature(method).parameters.values()]
        self.assertEqual(parameters(ListeningClient._call), parameters(TelegramClient._call))

    async def test_real_download_media_keeps_written_bytes_and_retries_same_offset(self):
        sdk = client()
        body = b"a" * (128 * 1024) + b"b" * (128 * 1024) + b"tail"
        media = types.MessageMediaDocument(document=types.Document(
            id=41, access_hash=42, file_reference=b"synthetic",
            date=datetime.now(timezone.utc), mime_type="video/mp4", size=len(body),
            dc_id=2, attributes=[types.DocumentAttributeFilename("synthetic.mp4")],
        ))
        offsets, delays = [], []
        clock = [1000.0]
        def send(query, ordered=False):
            if isinstance(query, functions.InvokeWithoutUpdatesRequest):
                query = query.query
            self.assertIsInstance(query, GetFileRequest)
            offsets.append(query.offset)
            future = asyncio.get_running_loop().create_future()
            if query.offset == 128 * 1024 and offsets.count(query.offset) <= 2:
                future.set_exception(FloodPremiumWaitError(request=query, capture=3))
            else:
                future.set_result(types.upload.File(type=types.storage.FileUnknown(),
                    mtime=0, bytes=body[query.offset:query.offset + query.limit]))
            return future
        async def sleep(seconds):
            delays.append(seconds)
            clock[0] += seconds
        output = io.BytesIO()
        validate, waiting, progress = Mock(), Mock(), Mock()
        with patch.object(sdk._sender, "send", side_effect=send), \
                patch("telethon.client.users.time.time", side_effect=lambda: clock[0]), \
                patch("tg2cloud.listening.transport.asyncio.sleep", side_effect=sleep), \
            download_scope(validate, waiting):
            await sdk.download_media(media, file=output, progress_callback=progress)
        self.assertEqual(output.getvalue(), body)
        self.assertEqual(offsets, [0, 128 * 1024, 128 * 1024, 128 * 1024, 256 * 1024])
        self.assertEqual(delays, [3, 3])
        self.assertEqual(waiting.call_count, 2)
        self.assertEqual(validate.call_count, 4)
        self.assertEqual(progress.call_args.args, (len(body), len(body)))

    async def test_concurrent_real_sdk_calls_share_premium_gate_without_false_flood_failure(self):
        sdk = client()
        clock, delays = [1000.0], []
        sleeping, release = asyncio.Event(), asyncio.Event()
        sends = []
        def send(query, ordered=False):
            if isinstance(query, functions.InvokeWithoutUpdatesRequest):
                query = query.query
            sends.append(query)
            future = asyncio.get_running_loop().create_future()
            if len(sends) == 1:
                future.set_exception(FloodPremiumWaitError(request=query, capture=4))
            else:
                future.set_result(types.upload.File(type=types.storage.FileUnknown(), mtime=0, bytes=b"ok"))
            return future
        async def sleep(seconds):
            delays.append(seconds)
            sleeping.set()
            if len(delays) == 2:
                release.set()
            await release.wait()
            clock[0] += seconds
        async def download():
            with download_scope(Mock(), Mock()):
                return await sdk._call(sdk._sender, request())
        with patch.object(sdk._sender, "send", side_effect=send), \
                patch("telethon.client.users.time.time", side_effect=lambda: clock[0]), \
                patch("tg2cloud.listening.transport.monotonic", side_effect=lambda: clock[0]), \
                patch("tg2cloud.listening.transport.asyncio.sleep", side_effect=sleep):
            first = asyncio.create_task(download())
            await asyncio.wait_for(sleeping.wait(), 2)
            second = asyncio.create_task(download())
            try:
                second_result = await asyncio.wait_for(asyncio.gather(second, return_exceptions=True), 2)
            finally:
                release.set()
            first_result = await first
        self.assertEqual(first_result.bytes, b"ok")
        self.assertIsInstance(second_result[0], types.upload.File)
        self.assertEqual(second_result[0].bytes, b"ok")
        self.assertEqual(delays, [4, 4])
        self.assertEqual(len(sends), 3)

    async def test_short_waits_cover_file_and_cdn_without_changing_global_threshold(self):
        for rpc in (request(), GetCdnFileRequest(file_token=b"synthetic", offset=0, limit=4096)):
            with self.subTest(rpc=type(rpc).__name__):
                sdk = client()
                result = object()
                parent = AsyncMock(side_effect=[FloodPremiumWaitError(request=rpc, capture=4), result])
                validate, waiting = Mock(), Mock()
                with patch.object(TelegramClient, "_call", parent), \
                        patch("tg2cloud.listening.transport.asyncio.sleep", new=AsyncMock()) as sleep, \
                    download_scope(validate, waiting):
                    self.assertIs(await sdk._call(sdk._sender, rpc), result)
                sleep.assert_awaited_once_with(4)
                waiting.assert_called_once_with(4)
                self.assertEqual(parent.await_args_list[0].args, parent.await_args_list[1].args)
                self.assertEqual(sdk.flood_sleep_threshold, 0)

    async def test_long_or_repeated_waits_are_bounded_and_not_silently_ignored(self):
        for waits, expected_calls, expected_waits in (([61], 1, 0), ([40, 40], 2, 1),
                ([3] * (MAX_CHUNK_WAITS + 1), MAX_CHUNK_WAITS + 1, MAX_CHUNK_WAITS)):
            with self.subTest(waits=waits):
                sdk = client()
                parent = AsyncMock(side_effect=[FloodPremiumWaitError(request=None, capture=x) for x in waits])
                with patch.object(TelegramClient, "_call", parent), \
                        patch("tg2cloud.listening.transport.asyncio.sleep", new=AsyncMock()) as sleep, \
                    download_scope(Mock(), Mock()), \
                    self.assertRaises(FloodPremiumWaitError):
                    await sdk._call(sdk._sender, request())
                self.assertEqual(parent.await_count, expected_calls)
                self.assertEqual(sleep.await_count, expected_waits)

    async def test_ordinary_flood_and_unrelated_requests_keep_durable_policy(self):
        for rpc, error in ((request(), FloodWaitError(request=None, capture=90)),
                           (types.InputPeerSelf(), FloodPremiumWaitError(request=None, capture=3))):
            with self.subTest(error=type(error).__name__, rpc=type(rpc).__name__):
                sdk = client()
                parent = AsyncMock(side_effect=error)
                with patch.object(TelegramClient, "_call", parent), \
                        patch("tg2cloud.listening.transport.asyncio.sleep", new=AsyncMock()) as sleep, \
                    download_scope(Mock(), Mock()), \
                    self.assertRaises(type(error)):
                    await sdk._call(sdk._sender, rpc)
                parent.assert_awaited_once()
                sleep.assert_not_awaited()

    async def test_wait_is_cancelable_and_identity_is_rechecked_before_retry(self):
        for mode in ("cancel", "identity"):
            with self.subTest(mode=mode):
                sdk = client()
                parent = AsyncMock(side_effect=FloodPremiumWaitError(request=None, capture=3))
                validate = Mock()
                async def sleep(seconds, mode=mode, validate=validate):
                    if mode == "cancel":
                        raise asyncio.CancelledError()
                    validate.side_effect = PermissionError("synthetic identity changed")
                with patch.object(TelegramClient, "_call", parent), \
                        patch("tg2cloud.listening.transport.asyncio.sleep", side_effect=sleep), \
                    download_scope(validate, Mock()), \
                    self.assertRaises(asyncio.CancelledError if mode == "cancel" else PermissionError):
                    await sdk._call(sdk._sender, request())
                parent.assert_awaited_once()

    async def test_scope_is_not_inherited_by_child_tasks_or_leaked_after_exit(self):
        sdk = client()
        parent = AsyncMock(side_effect=FloodPremiumWaitError(request=None, capture=3))
        with patch.object(TelegramClient, "_call", parent), \
                patch("tg2cloud.listening.transport.asyncio.sleep", new=AsyncMock()) as sleep:
            with download_scope(Mock(), Mock()), self.assertRaises(FloodPremiumWaitError):
                await asyncio.create_task(sdk._call(sdk._sender, request()))
            with self.assertRaises(FloodPremiumWaitError):
                await sdk._call(sdk._sender, request())
        self.assertEqual(parent.await_count, 2)
        sleep.assert_not_awaited()


class DownloadBackoffTests(unittest.TestCase):
    def test_unlimited_until_signal_and_zero_resource_window_is_preserved(self):
        from tg2cloud.listening.transport import DownloadBackoff
        backoff = DownloadBackoff()
        self.assertEqual(backoff.allowed(8), 8)
        self.assertEqual(backoff.allowed(0), 0)
        with patch("tg2cloud.listening.transport.monotonic", return_value=0):
            backoff.limited(8)
        with patch("tg2cloud.listening.transport.monotonic", return_value=100):
            self.assertEqual(backoff.allowed(0), 0)
            self.assertEqual(backoff.cap, 4)

    def test_simultaneous_signals_halve_once_and_sustained_limits_reach_one(self):
        from tg2cloud.listening.transport import DownloadBackoff
        backoff = DownloadBackoff()
        for now, expected in ((0, 4), (10, 4), (30, 2), (40, 2), (60, 1), (90, 1)):
            with patch("tg2cloud.listening.transport.monotonic", return_value=now):
                for _ in range(5):
                    backoff.limited(8)
                self.assertEqual(backoff.allowed(8), expected)

    def test_quiet_interval_is_extended_and_growth_is_one_slot_per_minute(self):
        from tg2cloud.listening.transport import DownloadBackoff
        backoff = DownloadBackoff()
        for now in (0, 10):
            with patch("tg2cloud.listening.transport.monotonic", return_value=now):
                backoff.limited(8)
        for now, expected in ((69, 4), (70, 5), (70, 5), (129, 5), (130, 6), (190, 7), (250, 8)):
            with patch("tg2cloud.listening.transport.monotonic", return_value=now):
                self.assertEqual(backoff.allowed(8), expected)
        self.assertIsNone(backoff.cap)

    def test_limits_are_per_listener_and_never_exceed_shared_resource_window(self):
        from tg2cloud.listening.transport import DownloadBackoff
        first, second = DownloadBackoff(), DownloadBackoff()
        with patch("tg2cloud.listening.transport.monotonic", return_value=0):
            first.limited(8)
            self.assertEqual(first.allowed(2), 2)
            self.assertEqual(second.allowed(8), 8)
            first.limited(0)
            self.assertGreaterEqual(first.allowed(1), 1)

    def test_source_temporary_error_uses_fixed_text_even_if_exception_args_change(self):
        from tg2cloud.domain.errors import (
            SourceTemporaryError,
            failure_kind,
            safe_failure,
        )
        for kind in ("network", "server"):
            error = SourceTemporaryError(kind)
            error.args = ("PRIVATE_TOKEN https://private.invalid/secret",)
            self.assertEqual(failure_kind(error), kind)
            self.assertIn("Telegram", safe_failure(error))
            self.assertNotIn("PRIVATE_TOKEN", safe_failure(error))
        with self.assertRaises(ValueError):
            SourceTemporaryError("untrusted")
