from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections.abc import Callable

from .config import Settings
from .rclone_client import RcloneClient


class DestinationVerificationError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


async def verify_destination(
    settings: Settings,
    client: RcloneClient | None = None,
    report: Callable[[str], None] | None = None,
) -> str:
    rclone = client or RcloneClient(settings)
    destination_label = getattr(settings, "destination_label", "CloudDrive2")
    token = uuid.uuid4().hex
    local_path = settings.data_dir / f".tg115-verify-{token}.bin"
    remote_temp = f".tg115-verify-{token}.uploading"
    remote_final = f".tg115-verify-{token}.ok"
    payload = os.urandom(256)
    verification_succeeded = False
    stage = "AUTH"

    def emit(value: str) -> None:
        if report is not None:
            report(value)

    local_path.write_bytes(payload)
    try:
        try:
            await rclone.verify_authentication()
        except Exception as exc:
            raise DestinationVerificationError(stage, str(exc)) from exc
        emit("TG2CLOUD_WEBDAV_AUTH=OK")
        stage = "LIST"
        try:
            await rclone.prepare_destination()
        except Exception as exc:
            raise DestinationVerificationError(stage, str(exc)) from exc
        emit("TG2CLOUD_WEBDAV_LIST=OK")
        emit("TG2CLOUD_WEBDAV=OK")
        stage = "WRITE"
        await rclone.upload(local_path, remote_temp)
        emit("TG2CLOUD_WEBDAV_WRITE=OK")
        stage = "SIZE"
        uploaded_size = await rclone.remote_size(remote_temp)
        if uploaded_size != len(payload):
            raise RuntimeError(
                f"{destination_label} WebDAV 临时测试文件大小错误："
                f"{uploaded_size} != {len(payload)}"
            )
        emit("TG2CLOUD_WEBDAV_SIZE=OK")
        emit("TG2CLOUD_UPLOAD=OK")
        stage = "MOVE"
        await rclone.move(remote_temp, remote_final)
        final_size = await rclone.remote_size(remote_final)
        if final_size != len(payload):
            raise RuntimeError(
                f"{destination_label} WebDAV 最终测试文件大小错误："
                f"{final_size} != {len(payload)}"
            )
        if await rclone.exists(remote_temp):
            raise RuntimeError(
                f"{destination_label} WebDAV 临时测试文件改名后仍然存在"
            )
        emit("TG2CLOUD_WEBDAV_MOVE=OK")
        emit("TG2CLOUD_RENAME=OK")
        stage = "DELETE"
        await rclone.remove(remote_final)
        if await rclone.exists(remote_final):
            raise RuntimeError(
                f"{destination_label} WebDAV 测试文件清理失败"
            )
        emit("TG2CLOUD_WEBDAV_DELETE=OK")
        emit("TG2CLOUD_DELETE=OK")
        verification_succeeded = True
        return remote_final
    except DestinationVerificationError:
        raise
    except Exception as exc:
        raise DestinationVerificationError(stage, str(exc)) from exc
    finally:
        try:
            local_path.unlink(missing_ok=True)
        except OSError:
            pass
        if not verification_succeeded:
            for remote_path in (remote_temp, remote_final):
                try:
                    await rclone.remove(remote_path)
                except Exception as exc:  # noqa: BLE001 - best-effort cleanup
                    print(
                        f"TG2CLOUD_CLEANUP_WARNING={remote_path}: {exc}",
                        file=sys.stderr,
                    )


async def async_main() -> int:
    settings = Settings.from_env()
    print(f"TG2CLOUD_STORAGE_GATEWAY={settings.storage_backend}")
    remote_path = await verify_destination(settings, report=print)
    print("TG2CLOUD_DESTINATION=OK")
    print(f"TG2CLOUD_TEST_PATH={remote_path}")
    return 0


def main() -> int:
    try:
        return asyncio.run(async_main())
    except DestinationVerificationError as exc:
        print(f"TG2CLOUD_WEBDAV_{exc.stage}=FAILED", file=sys.stderr)
        aggregate = {
            "AUTH": "WEBDAV",
            "LIST": "WEBDAV",
            "WRITE": "UPLOAD",
            "SIZE": "UPLOAD",
            "MOVE": "RENAME",
            "DELETE": "DELETE",
        }.get(exc.stage)
        if aggregate:
            print(f"TG2CLOUD_{aggregate}=FAILED", file=sys.stderr)
        print(f"TG2CLOUD_DESTINATION=FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI error boundary
        print(f"TG2CLOUD_DESTINATION=FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
