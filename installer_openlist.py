#!/usr/bin/env python3
"""OpenList product entry for the shared TG115 PySide6 deployer."""

from __future__ import annotations

from deployer_products import OPENLIST_PRODUCT
from installer import _startup_error, main

APP_TITLE = OPENLIST_PRODUCT.app_title
APP_VERSION = OPENLIST_PRODUCT.app_version
UI_VERSION = "qt-1.0-single"


if __name__ == "__main__":
    try:
        raise SystemExit(main(product=OPENLIST_PRODUCT))
    except Exception as exc:
        _startup_error(str(exc), OPENLIST_PRODUCT.app_title)
        raise SystemExit(1) from exc
