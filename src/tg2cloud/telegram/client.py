"""Telegram connection construction; no client is created at import time."""
from telethon import TelegramClient

from tg2cloud.config import Settings


def create_client(settings: Settings) -> TelegramClient:
    return TelegramClient(str(settings.data_dir / "bot"), settings.api_id, settings.api_hash,
                          request_retries=5, connection_retries=10, retry_delay=3,
                          auto_reconnect=True)
