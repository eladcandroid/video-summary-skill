#!/usr/bin/env python3
"""vtt_to_text.py <input.vtt> <output.txt>

Strip WEBVTT timing/markup from a YouTube subtitle file and emit flowing text.
Handles the common YouTube auto-subtitle quirks:
- Repeated lines (each cue overlaps the previous one to form a rolling caption)
- Inline <c>/<00:00:00.000> timing tags
- Cue settings on the timestamp line (align:start position:0%)
- WEBVTT header, NOTE blocks, STYLE blocks, blank separators

Also importable as a module: `from vtt_to_text import parse_vtt`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TIMESTAMP_RE = re.compile(r"-->")
INLINE_TAG_RE = re.compile(r"<[^>]+>")
CUE_ID_RE = re.compile(r"^\d+$")


def parse_vtt(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    skip_block = False

    for raw in lines:
        line = raw.rstrip()

        if not line:
            skip_block = False
            continue

        if line.startswith("WEBVTT"):
            continue
        if line.startswith(("NOTE", "STYLE", "REGION")):
            skip_block = True
            continue
        if skip_block:
            continue
        if TIMESTAMP_RE.search(line):
            continue
        if CUE_ID_RE.match(line):
            continue

        cleaned = INLINE_TAG_RE.sub("", line).strip()
        if not cleaned:
            continue

        if out and out[-1] == cleaned:
            continue
        if out and cleaned.startswith(out[-1]):
            out[-1] = cleaned
            continue

        out.append(cleaned)

    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: vtt_to_text.py <input.vtt> <output.txt>", file=sys.stderr)
        return 1

    in_path = Path(argv[1])
    out_path = Path(argv[2])

    text = in_path.read_text(encoding="utf-8", errors="replace")
    out_path.write_text(parse_vtt(text), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
