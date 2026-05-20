#!/usr/bin/env python3
"""whisper_transcribe.py <youtube-url>

Cross-platform fallback for videos without Hebrew subs. Downloads audio with
yt-dlp, transcribes with the first available whisper backend (whisper.cpp,
openai-whisper, or mlx-whisper), and emits the same TITLE/TRANSCRIPT/SOURCE
contract as fetch_transcript.py.

Exit 2 with install instructions if no whisper binary is present.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

WHISPER_MODEL_DEFAULT = "large-v3-turbo"
WHISPER_BINARIES = [
    ("whisper-cli", "cpp"),
    ("whisper-cpp", "cpp"),
    ("whisper", "openai"),
    ("mlx_whisper", "mlx"),
]

INSTALL_HINTS = {
    "darwin": (
        "Whisper is not installed. Install one of:\n"
        "  brew install whisper-cpp        # Apple-silicon optimized, recommended\n"
        "  pip3 install -U openai-whisper  # Pure Python (slower)\n"
        "  pip3 install -U mlx-whisper     # MLX, fast on Apple silicon"
    ),
    "linux": (
        "Whisper is not installed. Install one of:\n"
        "  # whisper.cpp (build from source — fastest CPU option):\n"
        "  git clone https://github.com/ggerganov/whisper.cpp && cd whisper.cpp && make\n"
        "  # or pure Python:\n"
        "  pipx install openai-whisper"
    ),
    "win32": (
        "Whisper is not installed. Install one of:\n"
        "  scoop install whisper-cpp\n"
        "  winget install ggerganov.WhisperCpp\n"
        "  pip install -U openai-whisper"
    ),
}


def install_hint() -> str:
    plat = sys.platform if sys.platform in INSTALL_HINTS else "linux"
    return INSTALL_HINTS[plat]


def find_whisper() -> tuple[str | None, str | None]:
    for name, kind in WHISPER_BINARIES:
        path = shutil.which(name)
        if path:
            return name, kind
    return None, None


def sanitize_title(title: str) -> str:
    title = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title[:80]


def workdir() -> Path:
    return Path(tempfile.gettempdir())


def cache_dir() -> Path:
    d = Path.home() / ".cache" / "whisper-cpp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def require_dep(binary: str, hint: str) -> None:
    if shutil.which(binary) is None:
        print(f"{binary} is not installed.\n{hint}", file=sys.stderr)
        sys.exit(2)


def fetch_metadata(url: str) -> tuple[str, str]:
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
    return video_id, raw_title


def download_audio(url: str, video_id: str) -> Path:
    audio = workdir() / f"vs-{video_id}.mp3"
    print("Downloading audio...", file=sys.stderr)
    subprocess.check_call(
        [
            "yt-dlp",
            "-f",
            "bestaudio",
            "-x",
            "--audio-format",
            "mp3",
            "--no-warnings",
            "-o",
            str(workdir() / f"vs-{video_id}.%(ext)s"),
            url,
        ],
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
    if not audio.exists():
        raise RuntimeError(f"audio download failed: expected {audio}")
    return audio


def download_model(model_name: str) -> Path:
    model_file = cache_dir() / f"ggml-{model_name}.bin"
    if model_file.exists():
        return model_file

    url = (
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"
        f"ggml-{model_name}.bin"
    )
    print(
        f"Downloading Whisper model ggml-{model_name}.bin "
        "(one-time, may take a few minutes)...",
        file=sys.stderr,
    )
    try:
        with urllib.request.urlopen(url) as r, open(model_file, "wb") as f:
            shutil.copyfileobj(r, f, length=1024 * 1024)
    except Exception as e:
        if model_file.exists():
            model_file.unlink()
        raise RuntimeError(f"model download failed: {e}") from e
    return model_file


def transcribe_cpp(
    whisper_cmd: str, audio: Path, video_id: str, model_name: str
) -> Path:
    require_dep("ffmpeg", "Install ffmpeg: brew install ffmpeg (mac), apt install ffmpeg (linux), winget install Gyan.FFmpeg (windows)")
    model_file = download_model(model_name)

    wav = workdir() / f"vs-{video_id}.wav"
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(audio),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(wav),
        ],
        stderr=sys.stderr,
    )

    out_base = workdir() / f"vs-{video_id}"
    subprocess.check_call(
        [
            whisper_cmd,
            "-m",
            str(model_file),
            "-l",
            "he",
            "-mc",
            "0",            # don't carry context between segments (anti-loop)
            "-wt",
            "0.5",          # stricter word-level threshold
            "-otxt",
            "-of",
            str(out_base),
            str(wav),
        ],
        stderr=sys.stderr,
    )
    wav.unlink(missing_ok=True)

    out_txt = workdir() / f"vs-{video_id}.txt"
    if not out_txt.exists():
        raise RuntimeError(f"whisper.cpp did not produce {out_txt}")
    return out_txt


def transcribe_openai(whisper_cmd: str, audio: Path, video_id: str) -> Path:
    subprocess.check_call(
        [
            whisper_cmd,
            str(audio),
            "--language",
            "he",
            "--output_format",
            "txt",
            "--output_dir",
            str(workdir()),
            "--model",
            "medium",
        ],
        stderr=sys.stderr,
    )
    out_txt = workdir() / f"vs-{video_id}.txt"
    if not out_txt.exists():
        raise RuntimeError(f"openai-whisper did not produce {out_txt}")
    return out_txt


def transcribe_mlx(whisper_cmd: str, audio: Path, video_id: str) -> Path:
    subprocess.check_call(
        [
            whisper_cmd,
            str(audio),
            "--language",
            "he",
            "--output-format",
            "txt",
            "--output-dir",
            str(workdir()),
        ],
        stderr=sys.stderr,
    )
    out_txt = workdir() / f"vs-{video_id}.txt"
    if not out_txt.exists():
        raise RuntimeError(f"mlx_whisper did not produce {out_txt}")
    return out_txt


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: whisper_transcribe.py <youtube-url>", file=sys.stderr)
        return 1

    require_dep(
        "yt-dlp",
        "Install yt-dlp: brew/apt/winget/scoop install yt-dlp  (or: pipx install yt-dlp)",
    )

    whisper_cmd, kind = find_whisper()
    if not whisper_cmd:
        print(install_hint(), file=sys.stderr)
        return 2

    url = argv[1]
    try:
        video_id, raw_title = fetch_metadata(url)
    except (subprocess.CalledProcessError, RuntimeError) as e:
        print(f"yt-dlp failed to read metadata for: {url}\n{e}", file=sys.stderr)
        return 1
    sanitized = sanitize_title(raw_title) or video_id

    audio = download_audio(url, video_id)

    model_name = os.environ.get("WHISPER_MODEL", WHISPER_MODEL_DEFAULT)
    print(
        f"Transcribing with {whisper_cmd} ({kind}); model={model_name}. "
        "This can take several minutes.",
        file=sys.stderr,
    )

    try:
        if kind == "cpp":
            out_txt = transcribe_cpp(whisper_cmd, audio, video_id, model_name)
        elif kind == "openai":
            out_txt = transcribe_openai(whisper_cmd, audio, video_id)
        elif kind == "mlx":
            out_txt = transcribe_mlx(whisper_cmd, audio, video_id)
        else:
            raise RuntimeError(f"unknown whisper kind: {kind}")
    finally:
        audio.unlink(missing_ok=True)

    print(f"TITLE={sanitized}")
    print(f"TRANSCRIPT={out_txt}")
    print("SOURCE=whisper")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
