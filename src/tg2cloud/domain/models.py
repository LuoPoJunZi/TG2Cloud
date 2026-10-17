from __future__ import annotations

import re
from dataclasses import dataclass, field

STAGING_PATTERN = re.compile(r"\.uploading-([1-9][0-9]{0,17})-[^/\\\r\n\x00]+")

@dataclass
class StagingScan:
    objects: list[tuple[int, str]] = field(default_factory=list)
    checked: int = 0
    found: int = 0
    complete: bool = True
    reason: str = ""

    def __iter__(self):
        return iter(self.objects)
