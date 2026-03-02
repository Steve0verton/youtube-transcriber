# Skill: YouTube Transcription

You have access to a local CLI tool called `youtube-transcriber` installed on the
**user's Mac** (not in this container). This is a critical distinction that governs
everything about how this skill should be executed.

---

## Execution Environment — Read This First

| Environment | Can reach YouTube? | Has the tool? | How to run |
|---|---|---|---|
| Claude container (bash_tool) | No - Network-blocked | Sometimes | Cannot download YouTube audio |
| User's Mac | Yes | Yes (globally installed) | Via `osascript` -> Terminal |

**The correct execution method is always `osascript` to run the command in a
Terminal window on the user's Mac.** Do not attempt to run `youtube-transcriber`
directly via bash_tool expecting to download from YouTube — the container cannot
reach YouTube and the command will hang or fail.

`youtube-transcriber models` (no YouTube access required) can run in bash_tool.
Anything involving `transcribe <url>` must go via osascript.

---

## Purpose

Downloads audio from YouTube videos and transcribes them locally on the user's Mac
using Whisper AI. On Apple Silicon (M-series) Macs the tool automatically uses the
**Metal GPU and Apple Neural Engine** via `mlx-whisper` — fast, quiet, no CPU overload.
Runs entirely offline after the initial model download. No API keys required.

---

## When to Use

- User shares a YouTube URL and asks you to watch, summarize, analyze, or transcribe it
- User says "transcribe this", "summarize this video", "what does this video say"
- Any request involving understanding or extracting content from a YouTube video

---

## Standard Execution Pattern

### Step 1 -- Tell the user what you are about to do

Before running anything, say something like:

  "I'll run the transcription on your Mac -- it uses the Apple Silicon GPU so it
  should be fast and quiet. I'll open a Terminal window so you can watch progress.
  The transcript will be saved to /tmp/transcript.txt."

### Step 2 -- Open a Terminal window on the Mac via osascript

Run these two commands via bash_tool:

```bash
osascript -e 'tell application "Terminal" to activate'
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript.txt"'
```

This opens a visible Terminal window on the user's Mac. The user can watch:
- Device confirmation banner (Apple Silicon GPU  [MLX / Metal + Neural Engine])
- Download progress bar from yt-dlp
- Live per-segment transcription output
- Final summary (language, duration, segment count)

### Step 3 -- Wait, then read the file

Poll from bash_tool until the file is non-empty:

```bash
# Check if done
ls -lh /tmp/transcript.txt 2>/dev/null && wc -w /tmp/transcript.txt

# Read when complete
cat /tmp/transcript.txt
```

### Step 4 -- Summarize or analyze

Once you have the transcript text, proceed with what the user asked for.

---

## Critical Rules

### 1. Never run more than one transcription at a time

The tool enforces a process-level lock. A second concurrent instance exits immediately:

  Error: Another youtube-transcriber process is already running.

If no process is actually running (previous run crashed), clear the stale lock:

```bash
rm /tmp/youtube-transcriber.lock
```

### 2. Always confirm the GPU is active

The startup banner shows the backend immediately. The user should see:

  Device: Apple Silicon GPU  [MLX / Metal + Neural Engine]

If they see "Device: CPU  [faster-whisper]" instead, mlx-whisper is not installed.
Tell the user to run in Terminal:

```bash
uv tool install . --with mlx-whisper --force
```

### 3. Always use --output with osascript

Never run via osascript without --output /tmp/transcript.txt. If you omit it,
the transcript prints to the Terminal window only -- you cannot read it from bash_tool.

### 4. Warn before starting long videos

For videos over ~20 minutes, say upfront:

  "This is a long video (~X min). The Apple Silicon GPU backend is fast but it will
  still take a few minutes. I'll let you know when it's done."

---

## osascript Command Patterns

### Basic -- write to file, progress visible in Terminal

```bash
osascript -e 'tell application "Terminal" to activate'
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript.txt"'
```

### With a specific model

```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --model large-v3 --output /tmp/transcript.txt"'
```

### With debug logging (when something goes wrong)

```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript.txt --log"'
```

Log is written to: ~/.local/share/youtube-transcriber/debug.log

### Check if complete and read (from bash_tool)

```bash
[ -s /tmp/transcript.txt ] && cat /tmp/transcript.txt || echo "Still running or failed"
wc -w /tmp/transcript.txt
```

---

## Full Command Reference

```bash
# Default -- turbo model, plain text output
youtube-transcriber transcribe "<url>" --output /tmp/transcript.txt

# Higher accuracy
youtube-transcriber transcribe "<url>" --model large-v3 --output /tmp/transcript.txt

# JSON with per-segment timestamps
youtube-transcriber transcribe "<url>" --format json --output /tmp/transcript.json

# SRT subtitles
youtube-transcriber transcribe "<url>" --format srt --output /tmp/transcript.srt

# With debug logging
youtube-transcriber transcribe "<url>" --output /tmp/transcript.txt --log

# Force CPU (bypass GPU -- rarely needed)
youtube-transcriber transcribe "<url>" --device cpu --output /tmp/transcript.txt

# List available models (safe to run via bash_tool -- no YouTube needed)
youtube-transcriber models
```

---

## Reading the Verbose Output

The Terminal window shows this progression:

```
youtube-transcriber v0.2.0
  URL:    https://www.youtube.com/watch?v=...
  Model:  turbo
  Format: text
  Device: Apple Silicon GPU  [MLX / Metal + Neural Engine]   <- GPU confirmed

[ Step 1/2 ] Downloading audio...
  (yt-dlp progress bar)

[ Step 2/2 ] Transcribing...
  Model 'turbo' loaded from cache:                           <- instant, no download
    /Users/.../.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo/...
  Transcribing audio segments (Apple Silicon GPU):
Detected language: English
[00:00.000 --> 00:05.120]  Hello and welcome...             <- live as it processes
[00:05.120 --> 00:10.440]  Today we're going to talk about...

  Transcription complete. Language: en | Duration: 1h 3m 57s | Segments: 1341
```

If the model is not yet cached (first time using it):

```
  Model 'turbo' not in cache -- downloading from HuggingFace...
    Repo : mlx-community/whisper-large-v3-turbo
    Cache: /Users/.../.cache/huggingface/hub
```

Warn the user this will take a few minutes (~800 MB for turbo). Subsequent runs
load from cache instantly.

---

## Model Selection

| Model | Download size | Notes |
|---|---|---|
| tiny | ~75 MB | Test the pipeline quickly -- low accuracy |
| base | ~150 MB | Fast |
| small | ~250 MB | Good for short clips |
| turbo | ~800 MB | **Default** -- best overall choice on Apple Silicon |
| large-v3 | ~3 GB | Highest accuracy, slower |
| distil-large-v3 | ~1.5 GB | Nearly as accurate as large-v3, faster |

Use turbo by default. Suggest large-v3 only if the user asks for maximum accuracy
or reports poor transcription quality.

---

## VAD Flag -- Read Before Using

Do NOT use --vad unless the content is clean speech with zero background audio.

The VAD filter classifies music and background noise as non-speech and silently
discards it -- producing 0 transcript segments with no error message.

| Content type | Use --vad? |
|---|---|
| Music video | No -- entire audio track will be discarded |
| Video with intro music or background sound | No |
| Podcast (speech only, no music) | Yes |
| Lecture/interview in a quiet room | Generally safe |

Note: --vad is silently ignored on the Apple Silicon (MLX) backend.

---

## Troubleshooting

### "command not found" in Terminal window

The tool is not on PATH in the shell Terminal opens. Tell the user to run:

```bash
uv tool update-shell && source ~/.zshrc
```

Or replace `youtube-transcriber` with `~/.local/bin/youtube-transcriber` in the osascript command.

### Terminal window shows CPU at 100%, fans loud

mlx-whisper is not installed -- tool fell back to CPU. The banner will show
"Device: CPU  [faster-whisper]". Tell the user to run in Terminal:

```bash
uv tool install . --with mlx-whisper --force
```

### Transcript file is empty after run completes

Common cause: --vad discarded everything. Check debug log:

```bash
cat ~/.local/share/youtube-transcriber/debug.log | grep -i vad
```

Remove --vad and retry.

### "Another youtube-transcriber process is already running"

Clear the stale lock:

```bash
rm /tmp/youtube-transcriber.lock
```

### yt-dlp JavaScript runtime error

  No supported JavaScript runtime could be found

Node.js must be installed via Homebrew (not nvm -- Terminal's PATH won't include nvm):

```bash
brew install node
```

### "Sign in to confirm you're not a bot"

YouTube is rate-limiting. Run with browser cookies:

```bash
youtube-transcriber transcribe "<url>" --cookies-from-browser chrome --output /tmp/transcript.txt
```

### When in doubt -- enable debug logging

```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript.txt --log"'
```

Then ask the user to share:

```bash
cat ~/.local/share/youtube-transcriber/debug.log
```

| Log line | What it means |
|---|---|
| VAD filter removed Xm Xs of audio | Remove --vad |
| JS runtime selected: node at /opt/homebrew/... | Node.js found correctly |
| MLX transcribe: ... | GPU backend active |
| Failed to load Whisper model | Try a smaller model; possible memory issue |
