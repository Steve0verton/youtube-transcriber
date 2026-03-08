# Setting Up youtube-transcriber with Claude Desktop

This guide walks through installing `youtube-transcriber` on a new machine and
configuring Claude Desktop to invoke it automatically whenever you share a YouTube URL.

---

## Prerequisites

- **macOS** (primary target for Claude Desktop; Linux also supported)
- **Claude Desktop** installed and running
- **Homebrew** (macOS): https://brew.sh
- **Git**

---

## Step 1: Install System Dependencies

```bash
# Install uv — fast Python package and project manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart your shell or source the updated PATH
source ~/.zshrc   # or ~/.bashrc for bash users

# Install ffmpeg — required by yt-dlp for audio extraction
brew install ffmpeg

# Install Node.js — required by yt-dlp to solve YouTube's JS challenges
# IMPORTANT: use Homebrew, not nvm. macOS GUI apps (Claude Desktop) launch
# without a full shell, so nvm-managed runtimes won't be found automatically.
brew install node
```

---

## Step 2: Clone and Install youtube-transcriber

```bash
# Clone the repository
git clone https://github.com/Steve0verton/youtube-transcriber.git
cd youtube-transcriber

# Install base dependencies
uv sync

# Apple Silicon (M1/M2/M3/M4) users: ALSO install the mlx extra for GPU acceleration
# This enables mlx-whisper which uses the Metal GPU and Apple Neural Engine
uv sync --extra mlx

# Verify it works
uv run youtube-transcriber --help
```

### (Recommended) Install as a Global Tool

Installing as a global tool puts `youtube-transcriber` on your PATH so Claude
can call it directly without needing to `cd` into the project directory first:

```bash
# Standard install
uv tool install .

# Apple Silicon: include the mlx GPU extra
uv tool install . --with mlx-whisper

# Verify the global install
youtube-transcriber --help
youtube-transcriber models
```

> **Note:** If `uv tool install` places the binary in a directory not yet on your
> PATH, run `uv tool update-shell` and restart your terminal.

---

## Step 3: Test a Real Transcription

Before configuring Claude, confirm the tool works end-to-end. The `tiny` model
is only ~75 MB and downloads quickly for a first test:

```bash
youtube-transcriber transcribe "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --model tiny
```

You should see progress messages on screen followed by the transcript text.
A successful run means everything is correctly installed.

> **Apple Silicon GPU:** On M-series Macs with the `mlx` extra installed, you will see
> `Loading model 'tiny' on Apple Silicon GPU (Metal/ANE)...` in the progress output.
> This confirms the Metal GPU is being used instead of CPU.

> **First run of any model:** Whisper model weights are downloaded from HuggingFace
> on first use and cached at `~/.cache/huggingface/hub/`. Subsequent runs using the
> same model are instant. Model sizes range from ~75 MB (tiny) to ~800 MB (turbo)
> to ~3 GB (large-v3).

---

## Step 4: Add a Claude Desktop System Prompt

A system prompt teaches Claude that the tool exists, when to use it, and how to
call it. This persists across all conversations in Claude Desktop.

**Claude Desktop → Settings → Custom Instructions**

Paste the following:

```text
You have access to a local CLI tool called `youtube-transcriber` installed on this machine.

TOOL: youtube-transcriber
PURPOSE: Downloads and transcribes YouTube videos locally using Whisper AI.
On Apple Silicon Macs (M-series), it uses the Metal GPU via mlx-whisper for fast,
hardware-accelerated transcription. Runs entirely offline after initial model download.

USAGE:
  youtube-transcriber transcribe "<youtube-url>"                   # transcript to stdout
  youtube-transcriber transcribe "<youtube-url>" --quiet           # suppress progress output
  youtube-transcriber transcribe "<youtube-url>" --model large-v3  # highest quality
  youtube-transcriber transcribe "<youtube-url>" --format json     # with timestamps
  youtube-transcriber transcribe "<youtube-url>" --format srt      # subtitle format
  youtube-transcriber transcribe "<youtube-url>" --output out.txt  # save to file
  youtube-transcriber transcribe "<youtube-url>" --vad             # VAD filter (speech-only, CPU/CUDA only)
  youtube-transcriber transcribe "<youtube-url>" --log             # enable debug log
  youtube-transcriber models                                        # list available models

WHEN TO USE:
- User shares a YouTube URL and asks you to watch, summarize, analyze, or transcribe it
- User says "transcribe this", "summarize this video", "what does this video say"
- Any request that involves understanding or extracting content from a YouTube video

CRITICAL: NEVER run more than one transcription at a time. Only one instance of
youtube-transcriber may run simultaneously. A second process will be immediately
blocked with an error. Wait for the first to complete before starting another.

BEHAVIOR:
- Run the command, capture the transcript, then analyze or summarize as requested
- Default model is "turbo" — good balance of speed and quality
- On Apple Silicon (M-series Macs), the --device flag defaults to "mps" which uses
  the Metal GPU and Apple Neural Engine via mlx-whisper. This is much faster than CPU
  and avoids fan noise / system overload. No extra flag needed — it's automatic.
- Use "--model large-v3" if the user asks for higher accuracy
- Always use "--quiet" when you want to capture only the clean transcript text
- For LONG videos (sermons, lectures, podcasts over 30 min): ask the user if they
  would like you to open a Terminal window to monitor progress, then do so with:
    osascript -e 'tell app "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript.txt"'
  Then read /tmp/transcript.txt once complete.
- Do NOT use "--vad" for music videos or any video with background audio
- First use of a new model downloads it from HuggingFace — warn the user
- If transcription returns empty or suspiciously short output, retry with --log
```

---

## Step 5: Configure claude_desktop_config.json (Optional)

Claude Desktop reads a JSON config file that can register tool paths explicitly.
This is useful if `youtube-transcriber` is not on the default PATH that Claude Desktop
sees (macOS GUI apps sometimes have a different PATH than your terminal).

**Config file location (macOS):**

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Open or create that file and add:

```json
{
  "mcpServers": {}
}
```

> If you run into PATH issues (Claude can't find the `youtube-transcriber` command),
> use the full absolute path instead. Find it by running:

```bash
which youtube-transcriber
```

> Then in your system prompt replace `youtube-transcriber` with the full path,
> e.g. `/Users/yourname/.local/bin/youtube-transcriber`.

---

## Step 6: Test Claude Integration

Open Claude Desktop and try one of the following prompts:

```text
Transcribe this YouTube video for me:
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

```text
Please summarize the key points from this video:
https://youtu.be/dQw4w9WgXcQ
```

```text
What does this YouTube video say? Give me a bullet-point summary:
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Claude should:

1. Run `youtube-transcriber transcribe "<url>" --quiet`
2. Receive the transcript text
3. Summarize or analyze it as requested

---

## How It Works Under the Hood

```text
You ask Claude about a YouTube video
        │
        ▼
Claude runs: youtube-transcriber transcribe "<url>" --quiet
        │
        ├── yt-dlp downloads the best audio stream → /tmp/tmpXXXXXX.wav
        │
        ├── faster-whisper transcribes locally (GPU if available, otherwise CPU)
        │
        ├── Temp audio file is automatically deleted
        │
        └── Clean transcript text returned to Claude via stdout
                │
                ▼
        Claude summarizes, answers questions, or analyzes the content
```

**No audio or transcripts are sent to any cloud service.** The only network
activity is the initial YouTube download and (on first use) the Whisper model download.

---

## Common Commands Reference

| Goal | Command |
|---|---|
| Basic transcript | `youtube-transcriber transcribe "<url>"` |
| Clean output only (no progress) | `youtube-transcriber transcribe "<url>" --quiet` |
| Highest quality | `youtube-transcriber transcribe "<url>" --model large-v3` |
| Save to file | `youtube-transcriber transcribe "<url>" --output transcript.txt` |
| SRT subtitles | `youtube-transcriber transcribe "<url>" --format srt` |
| JSON with timestamps | `youtube-transcriber transcribe "<url>" --format json` |
| Force Apple GPU (mps) | `youtube-transcriber transcribe "<url>" --device mps` |
| Force CPU (no GPU) | `youtube-transcriber transcribe "<url>" --device cpu` |
| Limit CPU threads | `youtube-transcriber transcribe "<url>" --device cpu --num-threads 2` |
| VAD filtering (speech-only, CPU/CUDA) | `youtube-transcriber transcribe "<url>" --vad` |
| Debug log (default path) | `youtube-transcriber transcribe "<url>" --log` |
| Debug log (custom path) | `youtube-transcriber transcribe "<url>" --log-file /tmp/debug.log` |
| List all models | `youtube-transcriber models` |

---

## Model Selection Guide

| Model | Size | Speed | Notes |
|---|---|---|---|
| `tiny` | ~1 GB | Fastest | Good for quick tests |
| `base` | ~1 GB | Very fast | |
| `small` | ~2 GB | Fast | |
| `medium` | ~5 GB | Moderate | |
| `turbo` | ~6 GB | Fast | **Default** — optimized large-v3, 8× faster |
| `large-v3` | ~10 GB | Slow | Highest accuracy |

**Apple Silicon (M-series) — GPU acceleration via MLX:**

With `uv sync --extra mlx` installed, the tool automatically uses `mlx-whisper`
which runs on the Metal GPU and Apple Neural Engine. This is dramatically faster
than CPU-only and keeps fans quiet:

| Mac | CPU-only (faster-whisper) | GPU (mlx-whisper) |
|---|---|---|
| M4 Pro | ~27 load avg, fans loud | Metal GPU, fans quiet |
| Device flag | `--device cpu` | `--device mps` (default on Apple Silicon) |

GPU acceleration via Metal is provided by the MLX framework (Apple's machine
learning framework for Apple Silicon). The `mlx-metal` package is installed
automatically with `uv sync --extra mlx`.

> **Note:** `faster-whisper` (the CPU backend) uses CTranslate2 which only
> supports CUDA GPUs — it always falls back to CPU on Apple Silicon.

---

## Keeping the Tool Updated

```bash
cd youtube-transcriber

# Pull the latest changes
git pull

# Reinstall as global tool to pick up any updates (Apple Silicon: include mlx)
uv tool install . --with mlx-whisper --force
```

---

## Troubleshooting

### "command not found: youtube-transcriber"

The global tool binary is not on your PATH. Run:

```bash
uv tool update-shell
source ~/.zshrc
```

Or use the full path: `~/.local/bin/youtube-transcriber`

### "ffmpeg is not installed"

```bash
brew install ffmpeg
```

### CPU is pegged / fans blowing on Apple Silicon

This happens when the `mlx` extra is not installed and `faster-whisper` falls back
to CPU with all available threads. Fix:

```bash
# In project directory:
uv sync --extra mlx

# OR if installed as a global tool:
uv tool install . --with mlx-whisper --force
```

Verify the GPU is being used by looking for this line in the progress output:

```text
Loading model 'turbo' on Apple Silicon GPU (Metal/ANE)...
```

If you still see `Loading model '...' on CPU`, the mlx extra is not in the active
environment.

### "Another youtube-transcriber process is already running"

The tool prevents parallel instances to avoid overloading the system. Wait for the
current transcription to finish. If no process is actually running (e.g. a previous
run crashed), delete the stale lock file:

```bash
rm /tmp/youtube-transcriber.lock
```

### Transcript returns 0 segments or is completely empty

The most common cause is the VAD (Voice Activity Detection) filter silently discarding
audio it classifies as non-speech — music, sound effects, and background audio all
trigger this. Enable debug logging to confirm:

```bash
youtube-transcriber transcribe "<url>" --model tiny --log
```

If the log at `~/.local/share/youtube-transcriber/debug.log` shows:

```text
VAD filter removed Xm Xs of audio
```

This is the cause. Do **not** use `--vad`. The default (no flag) processes all audio
regardless of content and works correctly for music videos and mixed audio.

### yt-dlp JavaScript runtime warning

If you see `No supported JavaScript runtime could be found`, Node.js is not on the
system PATH. On macOS, ensure it is installed via Homebrew:

```bash
brew install node
```

Do **not** use nvm, volta, or fnm for this — shell-level version managers only inject
PATH in interactive terminal sessions. Claude Desktop and other GUI apps launch without
a full shell and will not find runtimes managed this way.

### "yt-dlp: ERROR: Sign in to confirm you're not a bot"

YouTube is rate-limiting the download. Try passing your browser cookies:

```bash
youtube-transcriber transcribe "<url>" --cookies-from-browser chrome
```

> Note: `--cookies-from-browser` is a yt-dlp option. See the downloader source
> or yt-dlp docs for passing extra yt-dlp options.

### Transcription is slow

- **Apple Silicon:** Install the `mlx` extra (`uv sync --extra mlx`) — the Metal GPU
  backend is dramatically faster than CPU. Watch for `Apple Silicon GPU (Metal/ANE)`
  in the progress output to confirm it's active.
- First run downloads the model — subsequent runs are much faster
- Switch to a smaller model: `--model small` or `--model tiny`
- Make sure you're not running other heavy processes simultaneously

### Claude doesn't use the tool automatically

- Ensure the system prompt from Step 4 is saved in Claude Desktop settings
- Try explicitly asking: *"Use the youtube-transcriber tool to transcribe this: \<url\>"*
