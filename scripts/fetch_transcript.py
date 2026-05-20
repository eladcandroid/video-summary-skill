#!/usr/bin/env python3
"""fetch_transcript.py <youtube-url>

Cross-platform replacement for fetch_transcript.sh. Emits three KEY=VALUE
lines on stdout: TITLE, TRANSCRIPT, SOURCE.

SOURCE is "subs" if Hebrew subs (auto or manual) were found, "missing" otherwise.
Exit 0 in both cases; exit non-zero only on hard errors (bad URL, yt-dlp failure).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from vtt_to_text import parse_vtt  # noqa: E402

SUB_LANGS = "he,iw,he-IL"
SUB_SUFFIXES = (".he.vtt", ".iw.vtt", ".he-IL.vtt")


def sanitize_title(title: str) -> str:
    title = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title[:80]


def workdir() -> Path:
    return Path(tempfile.gettempdir())


def fetch_metadata(url: str) -> tuple[str, str]:
    """Return (video_id, raw_title) from yt-dlp."""
    out = subprocess.check_output(
        [
            "yt-dlp",
            "--print",
            "%(id)s|||%(title)s",
            "--skip-download",
            "--no-warnings",
            url,
        ],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()
    if "|||" not in out:
        raise RuntimeError(f"yt-dlp returned unexpected metadata: {out!r}")
    video_id, raw_title = out.split("|||", 1)
    if not video_id or not raw_title:
        raise RuntimeError(f"yt-dlp returned empty metadata: {out!r}")
    return video_id, raw_title


def download_subs(url: str, video_id: str) -> Path | None:
    """Try to download Hebrew subs. Returns path to .vtt file or None."""
    prefix = workdir() / f"vs-{video_id}"

    for existing in workdir().glob(f"vs-{video_id}.*.vtt"):
        existing.unlink()

    subprocess.run(
        [
            "yt-dlp",
            "--write-auto-subs",
            "--write-subs",
            "--sub-langs",
            SUB_LANGS,
            "--sub-format",
            "vtt",
            "--skip-download",
            "--no-warnings",
            "-o",
            f"{prefix}.%(ext)s",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for suffix in SUB_SUFFIXES:
        candidate = Path(f"{prefix}{suffix}")
        if candidate.exists():
            return candidate
    return None


def emit(title: str, transcript: Path | None, source: str) -> None:
    print(f"TITLE={title}")
    print(f"TRANSCRIPT={transcript if transcript else ''}")
    print(f"SOURCE={source}")


def require_yt_dlp() -> None:
    if shutil.which("yt-dlp") is None:
        print(
            "yt-dlp is not installed. Install:\n"
            "  macOS:    brew install yt-dlp\n"
            "  Linux:    sudo apt install yt-dlp   (or: pipx install yt-dlp)\n"
            "  Windows:  winget install yt-dlp     (or: scoop install yt-dlp)\n"
            "  Universal: pipx install yt-dlp",
            file=sys.stderr,
        )
        sys.exit(2)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: fetch_transcript.py <youtube-url>", file=sys.stderr)
        return 1

    require_yt_dlp()
    url = argv[1]

    try:
        video_id, raw_title = fetch_metadata(url)
    except (subprocess.CalledProcessError, RuntimeError) as e:
        print(f"yt-dlp failed to read metadata for: {url}\n{e}", file=sys.stderr)
        return 1

    sanitized = sanitize_title(raw_title) or video_id
    vtt_file = download_subs(url, video_id)

    if vtt_file is None:
        emit(sanitized, None, "missing")
        return 0

    out_txt = workdir() / f"vs-{video_id}.txt"
    vtt_text = vtt_file.read_text(encoding="utf-8", errors="replace")
    out_txt.write_text(parse_vtt(vtt_text), encoding="utf-8")

    for f in workdir().glob(f"vs-{video_id}.*.vtt"):
        f.unlink()

    emit(sanitized, out_txt, "subs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
