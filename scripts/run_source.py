"""Controlled src entry, independent of cwd; no pip or Bot dependencies."""
from __future__ import annotations

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "src"
if not (source / "tg2cloud/cli/commands.py").is_file():
    raise SystemExit("TG2Cloud source package is missing")
sys.path.insert(0, str(source))
os.environ["TG2CLOUD_SOURCE_ROOT"] = str(root)

from tg2cloud.cli.commands import main

if __name__ == "__main__":
    raise SystemExit(main())
