---
name: youtube-transcribe
description: >
  Transcribe YouTube videos locally on the user's Mac using Whisper AI. Apple Silicon machines get
  GPU acceleration via MLX; Intel Macs transcribe on CPU. Use this skill whenever a user shares a
  YouTube URL and wants it transcribed, summarized, analyzed, or understood. Also trigger when the
  user says "transcribe this video", "what does this video say", "summarize this YouTube video",
  "watch this", or pastes any youtube.com or youtu.be link with a request to extract or work with
  its content. This skill handles the full pipeline: downloading audio via yt-dlp, transcribing
  via mlx-whisper (Apple Silicon GPU) or faster-whisper (CPU/CUDA), and reading the result back
  for analysis. Even if the user doesn't explicitly say "transcribe", if they share a YouTube link
  and ask Claude to do anything with the video's content, this skill applies.
compatibility: >
  Requires macOS for agent-driven execution — the workflow drives the user's Terminal via
  osascript. The youtube-transcriber CLI itself also runs on Linux, but not under this skill.
  Apple Silicon (M1/M2/M3/M4) is recommended and needs the mlx extra installed; Intel Macs fall
  back to CPU and still work, just slower. Requires the youtube-transcriber CLI installed and on
  PATH (https://github.com/overtonlabs/youtube-transcriber).
---

# YouTube Transcribe Skill

Transcribe YouTube videos locally on the user's Mac using Whisper AI. On Apple Silicon, transcription
runs on the Metal GPU and Apple Neural Engine via MLX; on Intel Macs it runs on CPU via faster-whisper.
No cloud transcription APIs and no API keys — audio and transcripts never leave the user's machine.

**Source:** https://github.com/overtonlabs/youtube-transcriber

## Execution Environment

The single most important thing to understand: **the Claude container cannot reach YouTube, and does
not have the tool installed.** Every command in this skill runs on the user's Mac via `osascript`.

| Environment | Can reach YouTube? | Has the tool? | Use it for |
|---|---|---|---|
| Claude container (`bash_tool`) | No — network-blocked | No | Nothing in this skill |
| User's Mac (`osascript`) | Yes | Yes (installed on PATH) | Everything |

Never reach for `bash_tool` here — not for the transcription, not for polling, not for reading the
result, not even to list models. The tool does not exist in the container, so `bash_tool` returns
"command not found" and that reads like a broken install when nothing is wrong. The model list is in
`references/models-and-quality.md`; you never need to run a command to answer "which models exist".

The `osascript` approach also opens a visible Terminal window, so the user can watch real-time
progress: the download, per-segment transcription, and the completion summary.

---

## Standard Workflow

### 1. Extract the video ID

Pull the 11-character ID from the URL. It keys the output filename, so multiple videos never collide.

| URL format | Video ID |
|---|---|
| `youtube.com/watch?v=dQw4w9WgXcQ` | `dQw4w9WgXcQ` |
| `youtu.be/dQw4w9WgXcQ` | `dQw4w9WgXcQ` |
| `youtube.com/watch?v=dQw4w9WgXcQ&t=120` | `dQw4w9WgXcQ` |
| `youtube.com/watch?v=dQw4w9WgXcQ&list=PL...` | `dQw4w9WgXcQ` (only this video is downloaded) |

Playlist, channel, and search URLs are **rejected by the tool** (exit 2). If the user pastes one, ask
which video they want rather than launching a run that cannot succeed.

### 2. Tell the user what's about to happen

Brief them: transcription runs on their Mac (on the GPU if Apple Silicon), a Terminal window will open
so they can watch progress, and the transcript saves to `/tmp/transcript_<video_id>.txt`. For videos
over ~20 minutes, say it will take a few minutes even on GPU. If this is the first use of a model, the
weights download first (~1.6 GB for the default `turbo`).

### 3. Launch transcription via osascript

Launch the run and capture its exit status to a sidecar file in the same command. The status file is
what makes the poll in step 4 terminate correctly:

```bash
osascript -e 'tell application "Terminal" to activate'
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt; echo EXIT=$? > /tmp/transcript_<video_id>.status"'
```

Always pass `--output` with the video ID in the filename. Without it the transcript only appears in
the Terminal window and you cannot read it back.

**Higher accuracy** (when `turbo` produces a poor transcript):
```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --model large-v3 --output /tmp/transcript_<video_id>.txt; echo EXIT=$? > /tmp/transcript_<video_id>.status"'
```

**With debug logging** (when troubleshooting):
```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt --log; echo EXIT=$? > /tmp/transcript_<video_id>.status"'
```

### 4. Poll for completion, then read

The files live on the user's Mac, so poll via `osascript`. Read the **status file first** — it is the
only reliable completion signal:

```bash
osascript -e 'do shell script "cat /tmp/transcript_<video_id>.status 2>/dev/null || echo RUNNING"'
```

| Status output | Meaning | Action |
|---|---|---|
| `RUNNING` | still working | wait and poll again |
| `EXIT=0` | success | read the transcript |
| `EXIT=1` | runtime failure | see `references/troubleshooting.md` |
| `EXIT=2` | usage error — bad URL, unknown model | fix the command, do not retry unchanged |

Poll every 15–30 seconds, and **bound the loop**: give up after roughly 2× the video's duration plus
three minutes, or about 20 polls, whichever comes first. If it is still `RUNNING` at that point, tell
the user and ask them to check the Terminal window — do not poll indefinitely.

Once `EXIT=0`, read the transcript:

```bash
osascript -e 'do shell script "cat /tmp/transcript_<video_id>.txt"'
```

To check size before reading a potentially huge transcript, use `wc -w <` — with the redirect, so the
output is a bare number with no filename attached:

```bash
osascript -e 'do shell script "wc -w < /tmp/transcript_<video_id>.txt"'
```

**`EXIT=0` with an empty transcript means 0 segments**, not a crash. That is almost always `--vad` on
audio containing music. Re-run without `--vad`.

### 5. Analyze the transcript

Proceed with whatever the user asked for — summary, analysis, Q&A, extraction. Before treating the
transcript as authoritative, apply the quality guidance in `references/models-and-quality.md`.

---

## Multiple Videos

The tool holds a process-level lock — only one transcription runs at a time, and a second concurrent
run exits 1 immediately. Process videos sequentially: launch, poll to `EXIT=0`, read, then launch the
next. Each video gets its own output and status file keyed by video ID.

---

## Critical Rules

**1. Always use `osascript`, never `bash_tool`.** The container has neither network access to YouTube
nor the tool installed. This applies to every step, including polling and reading the result.

**2. Always include `--output /tmp/transcript_<video_id>.txt`.** Without it there is no way to read
the transcript back. The tool also injects the video ID into the filename itself, so it is never
duplicated if you already included it.

**3. Always capture the exit status** (`; echo EXIT=$? > ...status`) and poll that file. The transcript
file is written only at the very end of a successful run, so on any failure it never appears — polling
for the transcript alone loops forever.

**4. Never use `--vad` unless the content is certainly clean speech with zero background audio.** VAD
silently discards music. On a music video that means 0 segments with exit code 0 and no error. See
`references/models-and-quality.md` for the decision table.

**5. One transcription at a time.** If a stale lock survives a crashed run, the error message prints
the exact path to delete. On macOS the lock is in `$TMPDIR`, **not** `/tmp`:
`rm "${TMPDIR:-/tmp}/youtube-transcriber.lock"`.

**6. Prefer `--quiet` over `2>/dev/null`** if you ever need to suppress progress. It drops the banner
but keeps error messages, which you need in order to diagnose a failure.

---

## Quick Command Reference

All of these go inside `osascript -e 'tell application "Terminal" to do script "..."'`.

| Task | Command |
|---|---|
| Transcribe (default `turbo`) | `youtube-transcriber transcribe "<url>" --output /tmp/transcript_<vid>.txt` |
| Higher accuracy | add `--model large-v3` |
| JSON with timestamps | add `--format json`, use a `.json` extension |
| SRT subtitles | add `--format srt`, use a `.srt` extension |
| Debug logging | add `--log` (writes `~/.local/share/youtube-transcriber/debug.log`) |
| Suppress progress, keep errors | add `--quiet` |
| Force CPU (Intel Mac, or no mlx extra) | add `--device cpu` |
| Age-gated / bot-check videos | add `--cookies-from-browser chrome` |
| Use all CPU cores (CPU backend only) | add `--num-threads "$(sysctl -n hw.logicalcpu)"` |

Exit codes: `0` success, `1` runtime failure, `2` usage error.

---

## Reference Files

Read these from the skill's `references/` directory when you need deeper guidance:

| File | When to read |
|---|---|
| `references/models-and-quality.md` | Choosing a model, the full model list, interpreting transcript quality, VAD decisions, reading the progress output |
| `references/troubleshooting.md` | Any `EXIT=1` or unexpected behavior — command not found, missing mlx extra, empty transcript, bot detection, stale lock |
