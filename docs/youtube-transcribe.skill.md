# Skill: YouTube Transcription

> **Platform support: macOS only.**
> This skill relies on `osascript` and the macOS Terminal application to run commands
> on the user's machine. **Windows is currently not supported.** Linux support is not implemented in this skill. If the user is NOT on a Mac, stop and let them know.

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
  The transcript will be saved to /tmp/transcript_<video_id>.txt."

### Step 2 -- Open a Terminal window on the Mac via osascript

**Always include the video ID in the output filename.** Extract the 11-character video
ID from the URL (e.g. `dQw4w9WgXcQ` from `youtu.be/dQw4w9WgXcQ` or `?v=dQw4w9WgXcQ`).
This guarantees unique files when transcribing multiple videos in one prompt.

Run these two commands via bash_tool:

```bash
osascript -e 'tell application "Terminal" to activate'
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt"'
```

> **Auto-injection fallback:** If you pass a plain name like `--output /tmp/transcript.txt`,
> the tool automatically renames the file to `/tmp/transcript_<video_id>.txt` so existing
> transcripts are never overwritten. When running multiple videos, always use the video
> ID explicitly so you know the exact path to poll.

This opens a visible Terminal window on the user's Mac. The user can watch:
- Device confirmation banner (Apple Silicon GPU  [MLX / Metal + Neural Engine])
- Download progress bar from yt-dlp
- Live per-segment transcription output
- Final summary (language, duration, segment count)

### Step 3 -- Wait, then read the file

**CRITICAL: Do NOT use bash_tool to poll the transcript file — it lives on the
user's Mac filesystem, not inside the Claude container. bash_tool commands run in the
container and will not see the file. You must use `osascript` to check and read the
file.**

Poll via osascript until the file is non-empty (substitute the actual `<video_id>`):

```bash
# Check word count on the Mac (returns 0 if empty or missing)
osascript -e 'do shell script "wc -w /tmp/transcript_<video_id>.txt 2>/dev/null || echo 0"'

# Read the transcript from the Mac when complete
osascript -e 'do shell script "cat /tmp/transcript_<video_id>.txt"'
```

Repeat the word-count check every 15–30 seconds. When the count is greater than zero,
read the full file with the `cat` variant above and proceed to Step 4.

### Step 4 -- Summarize or analyze

Once you have the transcript text, proceed with what the user asked for.

Apply the guidance in **Interpreting Transcript Quality** below before treating the
transcript as authoritative.

---

## Interpreting Transcript Quality

Whisper-based transcription is high quality but not perfect. The output is shaped by
several real-world factors. Be aware of these when reading, summarizing, or quoting
a transcript.

### Known sources of errors

| Factor | Effect on output |
|---|---|
| Background music or ambient sound | Words may be garbled or invented; the model tries to transcribe audio that isn't speech |
| Low audio quality or heavy compression | Increased word substitution errors and dropped syllables |
| Heavy accents or non-standard pronunciation | Occasional mistranscriptions of individual words |
| Technical jargon, proper nouns, names | Frequently misspelled or phonetically approximated (e.g. "Kubernetes" → "Cubeerness") |
| Overlapping speakers | Words from different speakers may be merged or attributed incorrectly |
| Music intro/outro or background score | Spurious text fragments at the start or end of the transcript |
| Very fast speech | Words may run together or be partially dropped |

### How to handle errors as the AI copilot

- **Do not present phonetic guesses as facts.** If a proper noun or technical term looks
  wrong (e.g. a misspelled name, an acronym rendered as a word), use context to infer
  the likely correct form and note the uncertainty if it matters.
- **Use context to resolve ambiguity.** A word that looks like a typo usually has a
  plausible correct reading when you consider the surrounding sentences.
- **Flag low-confidence passages.** If a section of the transcript is clearly garbled
  (disconnected words, nonsensical phrases) — likely caused by music or noise — tell
  the user that portion was not reliably transcribed rather than summarizing gibberish.
- **Quote carefully.** When quoting specific words directly attributed to a speaker,
  add a light caveat if any uncertainty exists: *"roughly paraphrasing"* or
  *"transcript may contain minor errors"*.
- **Suggest a higher-accuracy model if quality is poor.** If the transcript has many
  obvious errors throughout, recommend the user retry with `--model large-v3`:

  "The transcript has several unclear passages — re-running with `--model large-v3`
  will improve accuracy, though it will take a bit longer."

### Quick quality signals to look for

- **Segment count is 0 or very low relative to video length** — VAD or audio issue; retry without `--vad`
- **Opening segments are nonsensical** — intro music was transcribed as speech; safe to discard
- **Proper nouns are consistently garbled** — phonetic approximation; infer from context
- **Large blocks of repetitive or looping text** — model hallucination on near-silence; ignore those sections

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

### 3. Always use --output with the video ID in the filename

Never run via osascript without `--output /tmp/transcript_<video_id>.txt`. If you omit
`--output`, the transcript prints to the Terminal window only — you cannot read it from
bash_tool. Using the video ID in the filename ensures unique files when transcribing
multiple videos in a single conversation.

### 4. Warn before starting long videos

For videos over ~20 minutes, say upfront:

  "This is a long video (~X min). The Apple Silicon GPU backend is fast but it will
  still take a few minutes. I'll let you know when it's done."

---

## osascript Command Patterns

In all patterns below, replace `<video_id>` with the 11-character YouTube video ID
extracted from the URL (e.g. `dQw4w9WgXcQ`).

### Basic -- write to file, progress visible in Terminal

```bash
osascript -e 'tell application "Terminal" to activate'
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt"'
```

### With a specific model

```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --model large-v3 --output /tmp/transcript_<video_id>.txt"'
```

### With debug logging (when something goes wrong)

```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt --log"'
```

Log is written to: ~/.local/share/youtube-transcriber/debug.log

### Check if complete and read (MUST use osascript — not bash_tool)

`/tmp/transcript_<video_id>.txt` lives on the user's Mac. bash_tool runs inside the
Claude container and cannot see it. Always use `osascript` to check and read the file:

```bash
# Poll: returns word count (0 = not done yet)
osascript -e 'do shell script "wc -w /tmp/transcript_<video_id>.txt 2>/dev/null || echo 0"'

# Read when done
osascript -e 'do shell script "cat /tmp/transcript_<video_id>.txt"'
```

### Multiple videos in one prompt

Run each transcription sequentially (the tool enforces a process lock — only one at a time).
Each video gets its own file named by its video ID:

```bash
# Video 1
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url1>\" --output /tmp/transcript_<id1>.txt"'
# Poll until done, then read /tmp/transcript_<id1>.txt via osascript

# Video 2
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url2>\" --output /tmp/transcript_<id2>.txt"'
# Poll until done, then read /tmp/transcript_<id2>.txt via osascript
```

---

## Full Command Reference

```bash
# Default -- turbo model, plain text output (replace <video_id> with the actual ID)
youtube-transcriber transcribe "<url>" --output /tmp/transcript_<video_id>.txt

# Higher accuracy
youtube-transcriber transcribe "<url>" --model large-v3 --output /tmp/transcript_<video_id>.txt

# JSON with per-segment timestamps
youtube-transcriber transcribe "<url>" --format json --output /tmp/transcript_<video_id>.json

# SRT subtitles
youtube-transcriber transcribe "<url>" --format srt --output /tmp/transcript_<video_id>.srt

# With debug logging
youtube-transcriber transcribe "<url>" --output /tmp/transcript_<video_id>.txt --log

# Force CPU (bypass GPU -- rarely needed)
youtube-transcriber transcribe "<url>" --device cpu --output /tmp/transcript_<video_id>.txt

# List available models (safe to run via bash_tool -- no YouTube needed)
youtube-transcriber models
```

---

## Reading the Verbose Output

The Terminal window shows this progression:

```
youtube-transcriber v0.2.2
  URL:    https://www.youtube.com/watch?v=dQw4w9WgXcQ
  Video:  dQw4w9WgXcQ
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
youtube-transcriber transcribe "<url>" --cookies-from-browser chrome --output /tmp/transcript_<video_id>.txt
```

### When in doubt -- enable debug logging

```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt --log"'
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
