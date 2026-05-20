---
name: video-summary
description: Turn a Hebrew YouTube lesson into a polished first-person Word (.docx) document. Use when the user provides a YouTube URL (especially Hebrew lessons, lectures, shiurim, podcasts) and wants an edited transcript saved as a Word file with paragraphs, subheadings, and every idea/source preserved. Triggers on "תמלל", "סכם את הסרטון", "ערוך את הסרטון", "transcript", "video summary", or pasting a YouTube URL with a request to edit/summarize/transcribe.
allowed-tools: Bash(yt-dlp:*), Bash(ffmpeg:*), Bash(python3:*), Bash(python:*), Bash(py:*), Bash(bash:*), Bash(ls:*), Bash(mkdir:*), Bash(mv:*), Bash(rm:*), Bash(brew:*), Bash(pip3:*), Bash(wc:*), Bash(head:*), Bash(command:*), Bash(open:*), Read, Write
---

# /video-summary — Hebrew YouTube → Edited Word Lesson

Turn a Hebrew YouTube video into a coherent, first-person, full-length lesson saved as a `.docx` file in the current directory. Every idea and every source in the original is preserved.

Cross-platform (macOS, Linux, Windows). All helpers are pure Python — no platform-specific shell scripts.

## When to invoke

- User pastes a YouTube URL and asks to edit / summarize / transcribe / `תמלל`.
- User says "תכין מהסרטון הזה שיעור", "שיעור מהוידאו", "Word מהסרטון", or similar.
- A bare YouTube URL with the rules-language ("גוף ראשון", "כותרות משנה", "אל תוריד אף רעיון") in the same message.

## The four editing rules (verbatim, in Hebrew — apply ALL of them)

1. **סדר את המלל באופן קוהרנטי** עם חלוקה לפסקאות וכותרות משנה. **אל תוריד אף רעיון או מקור** — גם אם זה ארוך, תמשיך עד שתסיים את כל החומר.
2. **שלא יהיה קצר מידי.** ערוך את זה כשיעור שלם שאני יכול להעביר בעצמי **בגוף ראשון** (אני, ש**אני** רוצה להעביר).
3. אם יש המשך, תכתוב את כולו **בלי מילים מסביב** — רק הטקסט הערוך עצמו.
4. הכן את התמלול הסופי על פי הכללים **ישירות לקובץ Word** (`.docx`).

## Workflow

> All Python invocations below use `python3`. On Windows, if `python3` is not on PATH, substitute `python` (or `py -3`).

### Step 1 — Extract the YouTube URL

Pull the URL from the user's message. If they pasted multiple URLs, ask which one. Accept `youtu.be/…`, `youtube.com/watch?v=…`, `youtube.com/shorts/…`, and live URLs.

### Step 2 — Fetch the raw transcript

```bash
python3 ~/.claude/skills/video-summary/scripts/fetch_transcript.py "<URL>"
```

Stdout returns exactly three lines:
```
TITLE=<sanitized video title>
TRANSCRIPT=<absolute path to .txt, may be empty>
SOURCE=<subs|missing>
```

- `SOURCE=subs` → Hebrew subtitles were found and parsed. Continue to step 4.
- `SOURCE=missing` → no Hebrew subs. Fall through to step 3.

### Step 3 — Whisper fallback (only when SOURCE=missing)

```bash
python3 ~/.claude/skills/video-summary/scripts/whisper_transcribe.py "<URL>"
```

Same three-line output with `SOURCE=whisper`. If the script exits 2 with an install message, **stop and show that message to the user verbatim** — do not try to install Whisper yourself.

Default model is `large-v3-turbo` (~1.6 GB, downloaded once into `~/.cache/whisper-cpp/`). Override with the `WHISPER_MODEL` env var (e.g. `WHISPER_MODEL=small` for a smaller/faster but lower-quality run).

### Step 4 — Read and report the raw transcript

```bash
wc -l -w "<TRANSCRIPT path>"   # macOS/Linux
# or, cross-platform:
python3 -c "import sys; t=open(sys.argv[1],encoding='utf-8').read(); print(f'{len(t.splitlines())} lines, {len(t.split())} words')" "<TRANSCRIPT path>"
```

Tell the user something like "Raw transcript: 1,234 words. Editing now — this may take a few minutes for long videos." Then `Read` the transcript file.

### Step 5 — Edit the transcript (the core of the skill)

Edit the raw transcript following the four Hebrew rules above. Then **write the full edited Hebrew lesson** to a temp markdown file using the `Write` tool. Suggested path:

- macOS/Linux: `/tmp/video-summary-edited.md`
- Windows: `%TEMP%\video-summary-edited.md` (use `os.environ['TEMP']` if scripting)

Format conventions inside that file:
- `# Title` (one line) — the lesson title (usually equals or refines the video title).
- `## Subheading` — for each major section of the lesson.
- `### Sub-subheading` — sparingly, when a section has clear sub-parts.
- **Blank line** between paragraphs.
- Body text in flowing Hebrew prose. No bullet lists unless the source itself enumerates items.
- Quote sources exactly as said in the video: rabbi names, book titles, page numbers, scripture references (e.g., `שולחן ערוך אורח חיים, סימן רל"ב, סעיף ב'`).

**Hard guardrails:**
- **Never abridge.** If you catch yourself writing `[המשך בהמשך]`, `…`, `[...]`, or skipping a topic — that is a bug. Stop, go back, write the full content.
- **Never translate.** Hebrew in → Hebrew out. English technical terms in the original stay in English.
- **First person.** "אני רוצה לדבר היום על…", not "המרצה רוצה לדבר היום על…".
- **No prefaces, no commentary, no closing notes from you.** The file contains only the lesson as the user would teach it.
- **Preserve every idea and every source.** If the speaker mentions five reasons, all five appear. If they cite three rabbis, all three appear.

If the raw transcript is very long (over ~10,000 words), this step may require thinking carefully across multiple chunks — but the **output file** is a single, complete document. Do not stop partway and ask the user; finish the whole thing.

### Step 6 — Produce the .docx

```bash
python3 ~/.claude/skills/video-summary/scripts/write_docx.py \
  --input /tmp/video-summary-edited.md \
  --title "<TITLE from step 2>" \
  --output "./<sanitized-title>.docx"
```

Use the same sanitized title for both the document title and the filename. The script applies RTL Hebrew formatting, Heading 1/2/3 styles, David-family fonts, and `he-IL` document language.

### Step 7 — Report and clean up

Report the absolute output path to the user. Then clean up temp files:

```bash
# macOS/Linux
rm -f /tmp/video-summary-edited.md /tmp/vs-*.vtt /tmp/vs-*.txt /tmp/vs-*.mp3

# Cross-platform alternative
python3 -c "import glob, os, tempfile; tmp = tempfile.gettempdir(); [os.remove(p) for pat in ('video-summary-edited.md', 'vs-*.vtt', 'vs-*.txt', 'vs-*.mp3') for p in glob.glob(os.path.join(tmp, pat))]"
```

Do not auto-open the file — the user decides when to open it.

## System dependencies

- **yt-dlp** (required, all platforms): `brew install yt-dlp` · `pipx install yt-dlp` · `winget install yt-dlp`
- **Python 3.9+** with `python-docx` (required): `pip3 install python-docx`
- **ffmpeg** (required only for Whisper fallback): `brew install ffmpeg` · `apt install ffmpeg` · `winget install Gyan.FFmpeg`
- **whisper** (required only for videos without Hebrew subs): `brew install whisper-cpp` (recommended) · `pipx install openai-whisper` · `scoop install whisper-cpp`

## Notes for Claude

- The skill is **YouTube only**. If the user gives a non-YouTube link (Vimeo, Spaces, direct mp4), say so and stop.
- The output filename uses the `TITLE` from step 2, which is already filesystem-safe. Don't second-guess the sanitization.
- This skill produces a long document. Keep your conversation-side commentary brief — the artifact is the .docx, not your chat output.
- For very long raw transcripts (1+ hour videos): the editing step is the slow part. Don't stop midway and ask "should I continue" — finish the whole thing.
