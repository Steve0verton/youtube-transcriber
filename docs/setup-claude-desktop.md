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

## Step 4: Install the Claude Skill

Pick the option that matches how you use Claude.

---

### Option A — Claude Desktop / Claude.ai (recommended)

Download the packaged `.skill` bundle from the latest GitHub Release and import it.

1. Open the [latest release](https://github.com/Steve0verton/youtube-transcriber/releases/latest).
2. Download the `youtube-transcribe.skill` asset.
3. In Claude Desktop or Claude.ai, open **Settings → Skills** and choose **Import skill** (or
   drag the file onto the window — most builds accept it).
4. The skill is now available in every conversation. Paste a YouTube URL and ask Claude to
   transcribe or summarize it.

> The packaged bundle is just a zipped folder containing `SKILL.md` and `references/`.
> Source lives at `skill/youtube-transcribe/` in this repo if you want to inspect it
> before importing.

---

### Option B — Claude Code (user-level install)

Claude Code loads skills from `~/.claude/skills/`. Copy the folder there:

```bash
# From inside this repo:
mkdir -p ~/.claude/skills
cp -r skill/youtube-transcribe ~/.claude/skills/
```

Or fetch it without cloning:

```bash
mkdir -p ~/.claude/skills/youtube-transcribe/references
curl -L https://raw.githubusercontent.com/Steve0verton/youtube-transcriber/main/skill/youtube-transcribe/SKILL.md \
  -o ~/.claude/skills/youtube-transcribe/SKILL.md
curl -L https://raw.githubusercontent.com/Steve0verton/youtube-transcriber/main/skill/youtube-transcribe/references/models-and-quality.md \
  -o ~/.claude/skills/youtube-transcribe/references/models-and-quality.md
curl -L https://raw.githubusercontent.com/Steve0verton/youtube-transcriber/main/skill/youtube-transcribe/references/troubleshooting.md \
  -o ~/.claude/skills/youtube-transcribe/references/troubleshooting.md
```

Final structure:

```
~/.claude/skills/
└── youtube-transcribe/
    ├── SKILL.md
    └── references/
        ├── models-and-quality.md
        └── troubleshooting.md
```

Claude Code discovers it on next launch.

---

### Option C — Project-scoped install

To install the skill into a specific project (so only that project's Claude Code sessions
see it, and the skill is checked in alongside the code):

```bash
# From the target project's root:
mkdir -p .claude/skills
cp -r /path/to/youtube-transcriber/skill/youtube-transcribe .claude/skills/
```

This produces `.claude/skills/youtube-transcribe/SKILL.md` plus its `references/` folder
inside the project — committable to that repo if desired.

---

## Step 5: Test Claude Integration

Open Claude Desktop (or your Claude Code session) and try:

```text
Transcribe this YouTube video for me:
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

```text
Please summarize the key points from this video:
https://youtu.be/dQw4w9WgXcQ
```

The skill will:

1. Open a Terminal window on your Mac via `osascript`
2. Run `youtube-transcriber transcribe "<url>" --output /tmp/transcript_<video_id>.txt`
3. Poll the output file until transcription completes
4. Read the transcript back and summarize / analyze as requested

You can watch the download + transcription progress live in the Terminal window the skill
opens. The transcript is saved to `/tmp/transcript_<video_id>.txt` for inspection.

---

## How It Works Under the Hood

```text
You ask Claude about a YouTube video
        │
        ▼
Claude (via the skill) runs: osascript -e 'tell application "Terminal" to do script
        "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<vid>.txt"'
        │
        ├── yt-dlp downloads the best audio stream → tempfile.TemporaryDirectory()
        │
        ├── mlx-whisper (Apple Silicon GPU) or faster-whisper (CPU/CUDA) transcribes locally
        │
        ├── Transcript written to /tmp/transcript_<video_id>.txt
        │
        └── Temp audio file is automatically deleted
                │
                ▼
        Claude polls the output file via osascript, reads it, and summarizes
        / answers questions / extracts what you asked for.
```

**No audio or transcripts are sent to any cloud service.** The only network
activity is the YouTube download (yt-dlp) and (on first use) the Whisper model download
from HuggingFace.

---

## Common Commands Reference

| Goal | Command |
|---|---|
| Basic transcript | `youtube-transcriber transcribe "<url>"` |
| Clean output only (no progress) | `youtube-transcriber transcribe "<url>" 2>/dev/null` |
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

See the canonical [Whisper Model Reference table in the README](../README.md#whisper-model-reference)
for parameter counts, on-disk sizes, and speed trade-offs. The short version: `turbo` is the
default and is the right choice for almost every use case. Switch to `large-v3` only when
turbo's transcript quality isn't good enough on a specific video.

**Apple Silicon (M-series) — GPU acceleration via MLX:**

With `uv sync --extra mlx` installed, the tool automatically uses `mlx-whisper`, which runs
on the Metal GPU and Apple Neural Engine. This is dramatically faster than CPU-only and keeps
the fans quiet. The device flag is `--device mps` (the default on Apple Silicon).

> **Note:** `faster-whisper` (the CPU backend) uses CTranslate2, which only supports CUDA
> GPUs — it always falls back to CPU on Apple Silicon. The `mlx` extra is the right answer
> for Apple Silicon GPU acceleration.

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
