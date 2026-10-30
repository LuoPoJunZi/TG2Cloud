"""Narrow adapter for the pinned Telethon download RPC boundary.

Retry the same file-chunk RPC after Telegram's premium wait, so Telethon keeps
its file reference/CDN handling and the existing output stream never rewinds.
Other requests and flood types retain the normal durable-cooldown policy.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from math import ceil
from time import monotonic

from telethon import TelegramClient
from telethon.errors import FloodPremiumWaitError, FloodWaitError
from telethon.tl.functions.upload import GetCdnFileRequest, GetFileRequest

FLOOD_WAITS = (FloodWaitError, FloodPremiumWaitError)
MAX_CHUNK_WAITS = 5
MAX_CHUNK_WAIT_SECONDS = 60


@dataclass(frozen=True)
class _DownloadScope:
    task: asyncio.Task
    validate: Callable[[], None]
    waiting: Callable[[int], None]


_scope: ContextVar[_DownloadScope | None] = ContextVar("listener_download", default=None)


@contextmanager
def download_scope(validate, waiting):
    token = _scope.set(_DownloadScope(asyncio.current_task(), validate, waiting))
    try:
        yield
    finally:
        _scope.reset(token)


class ListeningClient(TelegramClient):
    async def _call(self, sender, request, ordered=False, flood_sleep_threshold=None):
        # Telethon's iter_download calls _call with the exported DC/CDN sender.
        # Overriding __call__ would miss that path. The pinned SDK is exercised
        # offline with its real download_media iterator in the regression suite.
        scope = _scope.get()
        scoped = (scope is not None and scope.task is asyncio.current_task()
                  and isinstance(request, (GetFileRequest, GetCdnFileRequest)))
        if not scoped:
            return await super()._call(sender, request, ordered=ordered,
                                       flood_sleep_threshold=flood_sleep_threshold)
        # Telethon caches a premium wait by RPC constructor, then may surface
        # it to another download as ordinary FloodWaitError. Share only waits
        # actually observed as premium, before entering that native cache.
        gates = getattr(self, "_premium_download_gates", None)
        if gates is None:
            gates = self._premium_download_gates = {}
        key = request.CONSTRUCTOR_ID
        waits = waited = 0
        while True:
            deadline = gates.get(key, 0)
            remaining = max(0, ceil(deadline - monotonic()))
            if waits or remaining:
                scope.validate()
            if remaining:
                if waits >= MAX_CHUNK_WAITS or waited + remaining > MAX_CHUNK_WAIT_SECONDS:
                    raise FloodPremiumWaitError(request=request, capture=remaining)
                scope.waiting(remaining)
                waits += 1
                waited += remaining
                await asyncio.sleep(remaining)
                if gates.get(key) == deadline:
                    gates.pop(key, None)  # Never clear a newer, longer wait.
                continue
            try:
                return await super()._call(
                    sender, request, ordered=ordered, flood_sleep_threshold=0,
                )
            except FloodPremiumWaitError as exc:
                seconds = max(1, exc.seconds)
                gates[key] = max(gates.get(key, 0), monotonic() + seconds)
                # Next iteration waits, or leaves the long-wait cooldown to
                # CheckedSource. No byte or file handle has been rewound.


class DownloadBackoff:
    """Account-local admission cap; never cancel an already running transfer."""
    REDUCE_INTERVAL = 30
    RECOVER_INTERVAL = 60

    def __init__(self):
        self.cap = None
        self._last_reduction = None
        self._recover_after = 0.0

    def limited(self, total_window: int):
        now = monotonic()
        self._recover_after = now + self.RECOVER_INTERVAL
        # Concurrent chunks report the same wait. Do not halve once per task.
        if self._last_reduction is None or now - self._last_reduction >= self.REDUCE_INTERVAL:
            current = max(1, total_window)
            if self.cap is not None:
                current = min(current, self.cap)
            self.cap = max(1, current // 2)
            self._last_reduction = now

    def allowed(self, total_window: int) -> int:
        total_window = max(0, total_window)
        if self.cap is None or total_window == 0:
            return total_window
        now = monotonic()
        if now >= self._recover_after:
            self.cap += 1
            self._recover_after = now + self.RECOVER_INTERVAL
            if self.cap >= total_window:
                self.cap = None
                self._last_reduction = None
                return total_window
        return min(total_window, self.cap)
