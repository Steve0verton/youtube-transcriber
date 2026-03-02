# Skill: YouTube Transcription

You have access to a local CLI tool called `youtube-transcriber` installed on this machine.

**Binary path:** `~/.local/bin/youtube-transcriber` (run `which youtube-transcriber` to confirm on your machine)

## Purpose

Downloads and transcribes YouTube videos locally using Whisper AI.
Runs entirely offline after the initial model download — no API keys needed.

## When to Use

- User shares a YouTube URL and asks you to watch, summarize, analyze, or transcribe it
- User says "transcribe this", "summarize this video", "what does this video say"
- Any request that involves understanding or extracting content from a YouTube video

## Usage

```bash
# Basic transcription (transcript → stdout, progress → stderr)
youtube-transcriber transcribe "<youtube-url>"

# Clean transcript only (suppress progress output — use this when capturing output)
youtube-transcriber transcribe "<youtube-url>" --quiet

# Higher quality (slower)
youtube-transcriber transcribe "<youtube-url>" --model large-v3

# With timestamps (JSON)
youtube-transcriber transcribe "<youtube-url>" --format json

# Subtitle format
youtube-transcriber transcribe "<youtube-url>" --format srt

# Save to file
youtube-transcriber transcribe "<youtube-url>" --output out.txt

# VAD pre-filtering — only for clean speech with NO background music
# (podcasts, lectures, interviews). NEVER use for music videos.
youtube-transcriber transcribe "<youtube-url>" --vad

# Enable debug logging (write to default path)
youtube-transcriber transcribe "<youtube-url>" --log

# Enable debug logging (write to custom path)
youtube-transcriber transcribe "<youtube-url>" --log-file /tmp/yt-debug.log

# List available models
youtube-transcriber models
```

> **PATH note:** If Claude cannot find the command, use the full path instead.
> Run `which youtube-transcriber` in your terminal to get it (typically `~/.local/bin/youtube-transcriber`),
> then replace `youtube-transcriber` above with that full path.

## Behavior Guidelines

- Always use `--quiet` when you intend to capture only the clean transcript text
- Default model is `turbo` — good balance of speed and quality
- Use `--model large-v3` only if the user explicitly asks for higher accuracy
- On first use of a new model, weights download from HuggingFace (~75 MB for `tiny`, ~800 MB for `turbo`) — warn the user this may take a moment
- Run the command, capture the transcript from stdout, then summarize or analyze as requested

### VAD flag — read before using

Do **NOT** use `--vad` unless the content is clean speech with no background audio.
The VAD filter uses a speech-detection model that classifies music, background noise,
and mixed audio as “not speech” and silently discards it — resulting in 0 transcript segments.

| Content type | Use `--vad`? |
|---|---|
| Music video | ❌ No — entire track will be discarded |
| YouTube video with background music | ❌ No |
| Podcast, lecture, interview (no music) | ✅ Yes — removes silence, speeds up transcription |
| Panel discussion, quiet room | ✅ Generally safe |

### Debug logging

If a transcription returns empty or unexpectedly short output, always retry with `--log`
before concluding there is a content problem. The debug log reveals exactly what
yt-dlp downloaded and what faster-whisper did with it:

```bash
youtube-transcriber transcribe "<url>" --log
# Log written to: ~/.local/share/youtube-transcriber/debug.log
```

Key lines to look for in the log:
- `VAD filter removed Xm Xs of audio` → do not use `--vad` for this content
- `JS runtime selected: ...` → confirms Node.js was found for YouTube access
- `Segment [X–Y]: ...` → confirms individual transcript lines were produced

## Model Reference

| Model | Approx. Size | Notes |
|---|---|---|
| `tiny` | ~75 MB | Fastest, lowest accuracy |
| `small` | ~250 MB | Good for short clips |
| `turbo` | ~800 MB | **Default** — fast, high quality |
| `large-v3` | ~3 GB | Highest accuracy, slowest |
