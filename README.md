# video-summary

Turn a Hebrew YouTube lesson into a polished, first-person Word (`.docx`) document — full content preserved, paragraphs, subheadings, every source kept.

A [Claude Code](https://claude.com/claude-code) skill. Built for Hebrew Torah shiurim, but works for any Hebrew lecture, podcast, or talk on YouTube. Cross-platform (macOS / Linux / Windows).

## Install

Via [skills.sh](https://www.skills.sh/) — the package manager for agent skills:

```bash
# Global (recommended) — available from any directory, all agents on your system:
npx skills add -g eladcandroid/video-summary-skill

# Project-only — installs into ./.agents/skills/ for the current project:
npx skills add eladcandroid/video-summary-skill
```

The skill auto-installs into the Claude Code agent directory (`.claude/skills/`) and to any other Claude-Code-compatible agents you have. To force a specific agent:

```bash
npx skills add -g eladcandroid/video-summary-skill -a claude-code
```

## Use

Paste a YouTube URL into Claude Code and ask:

> תכין מהסרטון הזה שיעור Word: https://youtu.be/…

Claude will:

1. Pull Hebrew auto-subtitles from YouTube (instant), or fall back to Whisper if none exist.
2. Edit the raw transcript into a coherent first-person lesson with subheadings, keeping every idea and source.
3. Save the result as `<video-title>.docx` in your current directory — properly right-to-left, David font, `he-IL` language.

## How it works

```
YouTube URL
   │
   ▼
fetch_transcript.py  ──► Hebrew VTT found?
   │                       ├─ yes ──► vtt_to_text.py ──► raw .txt
   │                       └─ no  ──► whisper_transcribe.py ──► Whisper (large-v3-turbo) ──► raw .txt
   ▼
Claude reads the raw transcript and edits it in-conversation
according to the 4 Hebrew rules (paragraphs, subheadings, first person,
nothing dropped, no abridging).
   │
   ▼
write_docx.py  ──►  <title>.docx  (RTL, David font, Heading 1/2/3 styles)
```

## System dependencies

| Tool        | Required when         | macOS                 | Linux                       | Windows                          |
|-------------|-----------------------|-----------------------|-----------------------------|----------------------------------|
| Python 3.9+ | always                | preinstalled / brew   | preinstalled / apt          | `winget install Python.Python.3` |
| python-docx | always                | `pip3 install python-docx`                                                         |||
| yt-dlp      | always                | `brew install yt-dlp` | `pipx install yt-dlp`       | `winget install yt-dlp`          |
| ffmpeg      | Whisper fallback only | `brew install ffmpeg` | `apt install ffmpeg`        | `winget install Gyan.FFmpeg`     |
| whisper-cpp | Whisper fallback only | `brew install whisper-cpp` | build from source | `scoop install whisper-cpp` / `winget install ggerganov.WhisperCpp` |

The Whisper fallback is only used for videos with no Hebrew auto-subs. The first time it runs it downloads the `large-v3-turbo` model (~1.6 GB) into `~/.cache/whisper-cpp/`. Override with `WHISPER_MODEL=small|medium|large-v3` if you want a different size.

Alternative Whisper backends are auto-detected in this order: `whisper-cli`/`whisper-cpp` (whisper.cpp), `whisper` (openai-whisper), `mlx_whisper` (MLX, Apple-silicon).

## What "every idea preserved" really means

The four editing rules baked into the skill:

1. **סדר את המלל באופן קוהרנטי** — paragraphs and subheadings; **don't drop a single idea or source**, even if the result is long.
2. **שלא יהיה קצר מידי** — edit it as a complete lesson the user can teach themselves in **first person**.
3. **אם יש המשך, תכתוב את כולו** — no preamble, no closing remarks, only the lesson text.
4. **ישירות לקובץ Word** — output goes straight to a `.docx`.

Whisper isn't perfect on long Hebrew audio — proper names and technical halachic terms can get garbled. The skill reconstructs from context where reasonable, but always do a final pass on sources before teaching.

## Local development

The repo lives at the same path as the installed skill, so you can symlink:

```bash
rm -rf ~/.claude/skills/video-summary
ln -s "$PWD" ~/.claude/skills/video-summary
```

Now any edit to the repo is live in Claude Code immediately.

## License

MIT.
