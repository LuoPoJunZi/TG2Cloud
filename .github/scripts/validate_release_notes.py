from __future__ import annotations

import re
import sys
from pathlib import Path

BLOCK_START = re.compile(
    r"^(?:#{2,6}\s|[-+*]\s|\d+[.)]\s|>\s?|```|~~~|\||<| {4}|\t)"
)


def validate_release_notes(text: str) -> list[str]:
    errors: list[str] = []
    previous_prose_line: int | None = None
    fence_marker: str | None = None

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()

        if fence_marker is not None:
            if re.fullmatch(rf"{re.escape(fence_marker)}\s*", stripped):
                fence_marker = None
            previous_prose_line = None
            continue

        fence_match = re.match(r"^(```|~~~)", stripped)
        if fence_match:
            fence_marker = fence_match.group(1)
            previous_prose_line = None
            continue

        if not stripped:
            previous_prose_line = None
            continue

        if re.match(r"^#\s", stripped):
            errors.append(
                f"line {line_number}: remove the level-1 heading; "
                "GitHub Release already displays the release title"
            )

        if line.endswith("  "):
            errors.append(
                f"line {line_number}: remove the Markdown hard-break spaces"
            )

        is_prose = BLOCK_START.match(line) is None
        if is_prose and previous_prose_line is not None:
            errors.append(
                f"lines {previous_prose_line}-{line_number}: prose is hard-wrapped; "
                "keep one natural paragraph on one source line"
            )
        previous_prose_line = line_number if is_prose else None

    if fence_marker is not None:
        errors.append(f"unclosed {fence_marker} code fence")
    if not text.strip():
        errors.append("release notes are empty")
    if not re.search(r"(?m)^##\s+", text):
        errors.append("release notes need at least one level-2 section")
    return errors


def read_source(argument: str) -> tuple[str, str]:
    if argument == "-":
        return "stdin", sys.stdin.read()
    source_path = Path(argument)
    return str(source_path), source_path.read_text(encoding="utf-8")


def main() -> int:
    source = sys.argv[1] if len(sys.argv) > 1 else "RELEASE_NOTES.md"
    label, text = read_source(source)
    errors = validate_release_notes(text)
    if errors:
        for error in errors:
            print(f"{label}: {error}", file=sys.stderr)
        return 1
    print(f"{label}: release notes layout OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
