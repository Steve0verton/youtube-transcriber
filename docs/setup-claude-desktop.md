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
```

---

## Step 2: Clone and Install youtube-transcriber

```bash
# Clone the repository
git clone https://github.com/Steve0verton/youtube-transcriber.git
cd youtube-transcriber

# Install dependencies into a local virtual environment
uv sync

# Verify it works
uv run youtube-transcriber --help
```

### (Recommended) Install as a Global Tool

Installing as a global tool puts `youtube-transcriber` on your PATH so Claude
can call it directly without needing to `cd` into the project directory first:

```bash
uv tool install .

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

```
You have access to a local CLI tool called `youtube-transcriber` installed on this machine.

TOOL: youtube-transcriber
PURPOSE: Downloads and transcribes YouTube videos locally using Whisper AI.
Runs entirely offline after the initial model download — no API keys needed.

USAGE:
  youtube-transcriber transcribe "<youtube-url>"                   # transcript to stdout
  youtube-transcriber transcribe "<youtube-url>" --quiet           # suppress progress output
  youtube-transcriber transcribe "<youtube-url>" --model large-v3  # highest quality
  youtube-transcriber transcribe "<youtube-url>" --format json     # with timestamps
  youtube-transcriber transcribe "<youtube-url>" --format srt      # subtitle format
  youtube-transcriber transcribe "<youtube-url>" --output out.txt  # save to file
  youtube-transcriber models                                        # list available models

WHEN TO USE:
- User shares a YouTube URL and asks you to watch, summarize, analyze, or transcribe it
- User says "transcribe this", "summarize this video", "what does this video say"
- Any request that involves understanding or extracting content from a YouTube video

BEHAVIOR:
- Run the command, capture the transcript, then analyze or summarize as requested
- Default model is "turbo" — good balance of speed and quality
- Use "--model large-v3" if the user asks for higher accuracy (requires ~10 GB VRAM or RAM)
- Always use "--quiet" when you want to capture only the clean transcript text
- First use of a new model downloads it from HuggingFace (~75 MB for tiny, ~800 MB for turbo)
  — warn the user this may take a moment on first use
```

---

## Step 5: Configure claude_desktop_config.json (Optional)

Claude Desktop reads a JSON config file that can register tool paths explicitly.
This is useful if `youtube-transcriber` is not on the default PATH that Claude Desktop
sees (macOS GUI apps sometimes have a different PATH than your terminal).

**Config file location (macOS):**
```
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
> ```bash
> which youtube-transcriber
> ```
> Then in your system prompt replace `youtube-transcriber` with the full path,
> e.g. `/Users/yourname/.local/bin/youtube-transcriber`.

---

## Step 6: Test Claude Integration

Open Claude Desktop and try one of the following prompts:

```
Transcribe this YouTube video for me:
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

```
Please summarize the key points from this video:
https://youtu.be/dQw4w9WgXcQ
```

```
What does this YouTube video say? Give me a bullet-point summary:
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Claude should:
1. Run `youtube-transcriber transcribe "<url>" --quiet`
2. Receive the transcript text
3. Summarize or analyze it as requested

---

## How It Works Under the Hood

```
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
| Force CPU | `youtube-transcriber transcribe "<url>" --device cpu` |
| List all models | `youtube-transcriber models` |

---

## Model Selection Guide

| Model | VRAM / RAM | Speed | Notes |
|---|---|---|---|
| `tiny` | ~1 GB | Fastest | Good for quick tests |
| `base` | ~1 GB | Very fast | |
| `small` | ~2 GB | Fast | |
| `medium` | ~5 GB | Moderate | |
| `turbo` | ~6 GB | Fast | **Default** — optimized large-v3, 8× faster |
| `large-v3` | ~10 GB | Slow | Highest accuracy |

On a MacBook with Apple Silicon (M1/M2/M3/M4), faster-whisper uses the CPU with
`int8` quantization by default. GPU acceleration via Metal is not yet supported by
faster-whisper — for GPU-accelerated transcription on Apple Silicon, consider
`whisper.cpp` as an alternative backend.

---

## Keeping the Tool Updated

```bash
cd youtube-transcriber

# Pull the latest changes
git pull

# Reinstall as global tool to pick up any updates
uv tool install . --force
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

### "yt-dlp: ERROR: Sign in to confirm you're not a bot"
YouTube is rate-limiting the download. Try passing your browser cookies:
```bash
youtube-transcriber transcribe "<url>" --cookies-from-browser chrome
```
> Note: `--cookies-from-browser` is a yt-dlp option. See the downloader source
> or yt-dlp docs for passing extra yt-dlp options.

### Transcription is slow
- First run downloads the model — subsequent runs are much faster
- Switch to a smaller model: `--model small` or `--model tiny`
- Make sure you're not running other heavy processes simultaneously

### Claude doesn't use the tool automatically
- Ensure the system prompt from Step 4 is saved in Claude Desktop settings
- Try explicitly asking: *"Use the youtube-transcriber tool to transcribe this: \<url\>"*
