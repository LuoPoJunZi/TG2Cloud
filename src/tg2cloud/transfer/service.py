from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

from tg2cloud.config import Settings
from tg2cloud.monitoring.progress import _record_progress, _stage_rate
from tg2cloud.monitoring.resources import (
    AdaptiveWindow,
    ResourceMonitor,
    ResourceSnapshot,
)
from tg2cloud.transfer.actions import (
    _cancel_task_command,
    _command_cancel,
    _confirm_orphan_cleanup,
    _find_orphan_staging,
    _is_orphan_staging,
)
from tg2cloud.transfer.destination import _destination_loop, _probe_destination_once
from tg2cloud.transfer.download import _download_one
from tg2cloud.transfer.ports import Destination, MediaSource, TaskRepository
from tg2cloud.transfer.recovery import _local_complete, _resume_remote, _retry_task
from tg2cloud.transfer.scheduler import (
    _destination_ready,
    _enforce_disk_emergency,
    _errors_in_last_minute,
    _queued_batches,
    _resource_loop,
    _sample_fresh,
    _scheduler_loop,
    _start_downloads,
    _start_uploads,
    _stream_count,
)
from tg2cloud.transfer.streaming import (
    _begin_remote_write,
    _finalize_stream_remote,
    _stream_one,
)
from tg2cloud.transfer.upload import (
    _choose_remote_final,
    _complete_cloud_receive,
    _hold_transfer_failure,
    _upload_one,
)


class TaskService:
    _retry_task = _retry_task
    _local_complete = _local_complete
    _cancel_task_command = _cancel_task_command
    _command_cancel = _command_cancel
    _confirm_orphan_cleanup = _confirm_orphan_cleanup
    _find_orphan_staging = _find_orphan_staging
    _is_orphan_staging = _is_orphan_staging
    def __init__(
        self, settings: Settings, *, source: MediaSource | None = None,
        destination: Destination, client: MediaSource, repository: TaskRepository, monitor: ResourceMonitor,
    ):
        self.settings = settings
        self.log = logging.getLogger("tg2cloud")
        self.db = repository
        self.client = client
        self._source = source
        self.rclone = destination
        self.monitor = monitor
        self.download_window = AdaptiveWindow(settings, "download")
        self.upload_window = AdaptiveWindow(settings, "upload")
        self.snapshot: ResourceSnapshot | None = None
        self.destination_healthy = False
        self.destination_last_checked = 0.0
        self.destination_scope = "unknown"
        self.destination_error = "尚未检查"
        self.destination_failure_kind = ""
        self._progress: dict[int, dict[str, Any]] = {}
        self._watch_messages: dict[int, Any] = {}
        self.download_tasks: dict[int, asyncio.Task[None]] = {}
        self.upload_tasks: dict[int, asyncio.Task[None]] = {}
        self.recent_download_errors: deque[float] = deque(maxlen=50)
        self.recent_upload_errors: deque[float] = deque(maxlen=50)
        self._background: list[asyncio.Task[Any]] = []
        self._stop = asyncio.Event()
        self._finalize_lock = asyncio.Lock()
        self._destination_probe_lock = asyncio.Lock()
        self._destination_next_probe_at = 0.0
        self._destination_rate_limit_failures = 0
        self._orphan_cleanup_plan: dict[str, Any] | None = None
        self._cancel_confirmations: dict[int, dict[str, Any]] = {}

    @property
    def destination_label(self) -> str:
        return getattr(self.settings, "destination_label", "CloudDrive2")

    @property
    def source(self) -> MediaSource:
        return getattr(self, "_source", None) or self.client



    _sample_fresh = _sample_fresh
    _destination_ready = _destination_ready
    _stream_count = _stream_count
    _errors_in_last_minute = _errors_in_last_minute
    _enforce_disk_emergency = _enforce_disk_emergency
    _resource_loop = _resource_loop
    _scheduler_loop = _scheduler_loop
    _queued_batches = _queued_batches
    _start_downloads = _start_downloads
    _start_uploads = _start_uploads
    _download_one = _download_one
    _choose_remote_final = _choose_remote_final
    _hold_transfer_failure = _hold_transfer_failure
    _complete_cloud_receive = _complete_cloud_receive
    _upload_one = _upload_one
    _finalize_stream_remote = _finalize_stream_remote
    _begin_remote_write = _begin_remote_write
    _resume_remote = _resume_remote
    _stream_one = _stream_one
    _probe_destination_once = _probe_destination_once
    _destination_loop = _destination_loop
    _record_progress = _record_progress
    _stage_rate = _stage_rate
