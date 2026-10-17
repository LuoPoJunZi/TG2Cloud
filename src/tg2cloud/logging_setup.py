from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from tg2cloud.config import Settings
from tg2cloud.domain.errors import (
    redact_text,
)


def setup_logging(settings: Settings) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    class PrivateFormatter(logging.Formatter):
        def format(self, record):
            return redact_text(super().format(record), settings)

    formatter = PrivateFormatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        settings.log_dir / "tg2cloud.log",
        maxBytes=10 * 1024**2,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)
