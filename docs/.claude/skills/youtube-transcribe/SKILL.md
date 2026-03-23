---
name: youtube-transcribe
description: >
  Transcribe YouTube videos locally on the user's Mac using Whisper AI and Apple Silicon GPU acceleration.
  Use this skill whenever a user shares a YouTube URL and wants it transcribed, summarized, analyzed, or
  understood. Also trigger when the user says "transcribe this video", "what does this video say",
  "summarize this YouTube video", "watch this", or pastes any youtube.com or youtu.be link with a request
  to extract or work with its content. This skill handles the full pipeline: downloading audio via yt-dlp,
  transcribing via mlx-whisper on Apple Silicon GPU, and reading the result back for analysis. Even if the
  user doesn't explicitly say "transcribe", if they share a YouTube link and ask Claude to do anything with
  the video's content, this skill applies.
compatibility: >
  Requires macOS with Apple Silicon (M1/M2/M3/M4). Requires the youtube-transcriber CLI tool installed
  via uv (https://github.com/Steve0verton/youtube-transcriber). Requires the osascript tool to execute
  commands on the user's Mac. Windows and Linux are not supported for agent-driven execution.
---

# YouTube Transcribe Skill

Transcribe YouTube videos locally on the user's Mac using Whisper AI with Apple Silicon GPU acceleration.
No cloud APIs, no API keys — runs entirely on-device after initial model download.

**Source:** https://github.com/Steve0verton/youtube-transcriber

## Execution Environment

This is the single most important thing to understand about this skill: **the Claude container cannot
reach YouTube.** The CLI tool must run on the user's Mac via `osascript`, not via `bash_tool`.

| Environment | Can reach YouTube? | Has the tool? | Execution method |
|---|---|---|---|
| Claude container (`bash_tool`) | No — network-blocked | No | Only for non-network commands (`youtube-transcriber models`) |
| User's Mac | Yes | Yes (globally installed) | `osascript` → Terminal |

The reason this matters: if you try `bash_tool` with a YouTube URL, the download will hang or fail silently.
The `osascript` approach opens a visible Terminal window on the user's Mac where they can watch real-time
progress — download bar, per-segment transcription, completion summary.

---

## Standard Workflow

### 1. Extract the video ID

Pull the 11-character ID from the URL. This ensures unique filenames when transcribing multiple videos.

| URL format | Video ID |
|---|---|
| `youtube.com/watch?v=dQw4w9WgXcQ` | `dQw4w9WgXcQ` |
| `youtu.be/dQw4w9WgXcQ` | `dQw4w9WgXcQ` |
| `youtube.com/watch?v=dQw4w9WgXcQ&t=120` | `dQw4w9WgXcQ` |

### 2. Tell the user what's about to happen

Brief them: the transcription runs on their Mac using the Apple Silicon GPU, a Terminal window will open
so they can see progress, and the transcript saves to `/tmp/transcript_<video_id>.txt`. For videos over
~20 minutes, warn that it will take a few minutes even on GPU.

### 3. Launch transcription via osascript

```bash
osascript -e 'tell application "Terminal" to activate'
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt"'
```

Always include `--output` with the video ID in the filename. Without it, the transcript only prints to
the Terminal window and you cannot read it back.

**With a specific model** (when higher accuracy is needed):
```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --model large-v3 --output /tmp/transcript_<video_id>.txt"'
```

**With debug logging** (when troubleshooting):
```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt --log"'
```

### 4. Poll for completion, then read

The transcript file lives on the user's Mac — `bash_tool` cannot see it. Poll via `osascript`:

```bash
# Check word count (returns "0" if file is empty or missing)
osascript -e 'do shell script "wc -w /tmp/transcript_<video_id>.txt 2>/dev/null || echo 0"'
```

Poll every 15–30 seconds. When the word count is greater than zero:

```bash
# Read the completed transcript
osascript -e 'do shell script "cat /tmp/transcript_<video_id>.txt"'
```

### 5. Analyze the transcript

Proceed with whatever the user asked for — summary, analysis, Q&A, extraction. Before treating the
transcript as authoritative, apply the quality interpretation guidance in `references/models-and-quality.md`.

---

## Multiple Videos

The tool enforces a process-level lock — only one transcription runs at a time. A second concurrent
instance exits immediately with an error. Process videos sequentially: launch, poll until complete, read,
then launch the next one. Each video gets its own output file keyed by video ID.

---

## Critical Rules

**1. Always use osascript for anything involving a YouTube URL.** `bash_tool` cannot reach YouTube.
The only exception is `youtube-transcriber models` (lists available models, no network needed).

**2. Always include `--output /tmp/transcript_<video_id>.txt`.** Without it, you have no way to
read the transcript back — it only prints to the Terminal window.

**3. Always poll with osascript, never bash_tool.** The output file is on the user's Mac filesystem,
not in the Claude container.

**4. Never use `--vad` unless you're certain the content is clean speech with zero background audio.**
VAD silently discards music and background noise. On a music video, this means 0 segments with no error
message. See `references/models-and-quality.md` for the full decision table.

**5. One transcription at a time.** The tool has a process lock. If a stale lock exists from a crashed
run: `rm /tmp/youtube-transcriber.lock`

---

## Quick Command Reference

| Task | Command |
|---|---|
| Transcribe (default turbo model) | `youtube-transcriber transcribe "<url>" --output /tmp/transcript_<vid>.txt` |
| Higher accuracy | Add `--model large-v3` |
| JSON with timestamps | Add `--format json`, use `.json` extension |
| SRT subtitles | Add `--format srt`, use `.srt` extension |
| Debug logging | Add `--log` (writes to `~/.local/share/youtube-transcriber/debug.log`) |
| Force CPU | Add `--device cpu` |
| Browser cookies (bot detection) | Add `--cookies-from-browser chrome` |
| List models | `youtube-transcriber models` (safe in `bash_tool`) |

---

## Reference Files

Read these from the skill's `references/` directory when you need deeper guidance:

| File | When to read |
|---|---|
| `references/models-and-quality.md` | Choosing a model, interpreting transcript quality, VAD decisions, quality signals |
| `references/troubleshooting.md` | Any error or unexpected behavior — command not found, CPU fallback, empty transcripts, bot detection |
