# Setting Up youtube-transcriber with Claude

This guide walks through installing `youtube-transcriber` on a new machine and installing the
bundled skill so Claude transcribes any YouTube URL you paste.

---

## Prerequisites

- **macOS** — required for the Claude skill, which drives Terminal via `osascript`. The CLI
  itself also runs on Linux, but the skill does not.
- **Claude Desktop** (or Claude Code) installed
- **Homebrew** — https://brew.sh
- **Git**

---

## Step 1: Install System Dependencies

```bash
# uv — fast Python package and project manager
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.zshrc   # or ~/.bashrc

# ffmpeg — yt-dlp uses it to extract audio
brew install ffmpeg

# Node.js — yt-dlp needs a JS runtime to solve YouTube's challenges.
# IMPORTANT: use Homebrew, not nvm. macOS GUI apps (Claude Desktop) launch without a
# full shell, so nvm-managed runtimes are often invisible to them.
brew install node
```

---

## Step 2: Install youtube-transcriber

Installing as a global tool puts `youtube-transcriber` on your PATH so the skill can call it
without needing a project directory.

```bash
# Apple Silicon (M1/M2/M3/M4) — the mlx extra is REQUIRED, not optional
uv tool install "git+https://github.com/overtonlabs/youtube-transcriber.git[mlx]"

# Intel Mac / Linux
uv tool install git+https://github.com/overtonlabs/youtube-transcriber.git

youtube-transcriber --help
youtube-transcriber models
```

> **Why the `mlx` extra is mandatory on Apple Silicon:** on an M-series Mac the tool always
> selects the MLX (Metal GPU) backend, and there is **no automatic CPU fallback**. Without
> `mlx-whisper` installed the run fails with `mlx-whisper is not installed`. You can still force
> the CPU backend explicitly with `--device cpu`, which works but is much slower.

> **Note:** if `uv tool install` puts the binary somewhere not yet on your PATH, run
> `uv tool update-shell` and restart your terminal.

### From a clone instead (for development)

```bash
git clone https://github.com/overtonlabs/youtube-transcriber.git
cd youtube-transcriber
uv sync --extra mlx      # Apple Silicon; use plain `uv sync` elsewhere
uv run youtube-transcriber --help
```

---

## Step 3: Test a Real Transcription

Confirm the tool works end to end before installing the skill. The `tiny` model is only ~75 MB:

```bash
youtube-transcriber transcribe "https://youtu.be/H14bBuluwB8" --model tiny
```

You should see progress on stderr followed by the transcript on stdout.

**Confirming the Apple Silicon GPU is in use.** Look for this exact line in the banner (note the
two spaces before the bracket):

```text
  Device: Apple Silicon GPU  [MLX / Metal + Neural Engine]
```

and, once transcription starts:

```text
  Transcribing audio segments (Apple Silicon GPU):
```

If instead you see `Device: CPU  [faster-whisper]`, you passed `--device cpu` — the default path
on Apple Silicon never falls back to CPU on its own.

> **First run of any model** downloads the weights from HuggingFace into
> `~/.cache/huggingface/hub/`. Sizes range from ~75 MB (`tiny`) to ~1.6 GB (`turbo`, the default)
> to ~3 GB (`large-v3`). Later runs load from cache instantly.

---

## Step 4: Install the Claude Skill

Pick the option matching how you use Claude.

### Option A — Claude Desktop / Claude.ai (recommended)

1. Open the [latest release](https://github.com/overtonlabs/youtube-transcriber/releases/latest).
2. Download the `youtube-transcribe.skill` asset.
3. In Claude Desktop or Claude.ai, open **Settings → Skills** and choose **Import skill** (most
   builds also accept the file dragged onto the window).
4. The skill is now available in every conversation.

> The bundle is just a zipped folder containing `SKILL.md` and `references/`. The source is at
> `skill/youtube-transcribe/` in this repo if you want to inspect it before importing.

### Option B — Claude Code (user-level)

```bash
# From a clone of this repo:
mkdir -p ~/.claude/skills
cp -r skill/youtube-transcribe ~/.claude/skills/
```

Or without cloning:

```bash
mkdir -p ~/.claude/skills/youtube-transcribe/references
BASE=https://raw.githubusercontent.com/overtonlabs/youtube-transcriber/main/skill/youtube-transcribe
curl -L "$BASE/SKILL.md" -o ~/.claude/skills/youtube-transcribe/SKILL.md
curl -L "$BASE/references/models-and-quality.md" -o ~/.claude/skills/youtube-transcribe/references/models-and-quality.md
curl -L "$BASE/references/troubleshooting.md" -o ~/.claude/skills/youtube-transcribe/references/troubleshooting.md
```

Final structure:

```text
~/.claude/skills/
└── youtube-transcribe/
    ├── SKILL.md
    └── references/
        ├── models-and-quality.md
        └── troubleshooting.md
```

Claude Code discovers it on next launch.

### Option C — Project-scoped

To scope the skill to one project (and check it in alongside that project's code):

```bash
# From the target project's root:
mkdir -p .claude/skills
cp -r /path/to/youtube-transcriber/skill/youtube-transcribe .claude/skills/
```

---

## Step 5: Test the Claude Integration

Open Claude Desktop (or your Claude Code session) and try:

```text
Transcribe this YouTube video for me:
https://youtu.be/H14bBuluwB8
```

The skill will:

1. Open a Terminal window on your Mac via `osascript`
2. Run `youtube-transcriber transcribe "<url>" --output /tmp/transcript_<video_id>.txt`, capturing
   the exit status to `/tmp/transcript_<video_id>.status`
3. Poll the status file until it reports `EXIT=0`
4. Read the transcript back and answer whatever you asked

You can watch the download and transcription live in the Terminal window the skill opens. The
transcript stays at `/tmp/transcript_<video_id>.txt` for inspection.

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
        Claude polls the status file, reads the transcript, and answers
```

**No audio and no transcript is ever sent to a cloud service.** The tool does still make three
kinds of outbound request, and it is worth naming them precisely:

| Destination | When | Why |
|---|---|---|
| `youtube.com` | every run | yt-dlp downloads the audio |
| `huggingface.co` | first use of a model, plus a metadata check on later runs | Whisper weights |
| `github.com` | when YouTube serves a JS challenge | yt-dlp's challenge-solver component |

---

## Common Commands Reference

| Goal | Command |
|---|---|
| Basic transcript | `youtube-transcriber transcribe "<url>"` |
| Suppress progress, keep errors | `youtube-transcriber transcribe "<url>" --quiet` |
| Highest quality | `youtube-transcriber transcribe "<url>" --model large-v3` |
| Save to file | `youtube-transcriber transcribe "<url>" --output transcript.txt` |
| SRT subtitles | `youtube-transcriber transcribe "<url>" --format srt` |
| JSON with timestamps | `youtube-transcriber transcribe "<url>" --format json` |
| Force Apple GPU (mps) | `youtube-transcriber transcribe "<url>" --device mps` |
| Force CPU | `youtube-transcriber transcribe "<url>" --device cpu` |
| Use all CPU cores | `youtube-transcriber transcribe "<url>" --device cpu --num-threads "$(sysctl -n hw.logicalcpu)"` |
| Age-gated / bot-check videos | `youtube-transcriber transcribe "<url>" --cookies-from-browser chrome` |
| VAD filtering (speech-only, CPU/CUDA) | `youtube-transcriber transcribe "<url>" --vad` |
| Debug log (default path) | `youtube-transcriber transcribe "<url>" --log` |
| Debug log (custom path) | `youtube-transcriber transcribe "<url>" --log-file /tmp/debug.log` |
| List all models | `youtube-transcriber models` |

The full flag table lives in the [README](../README.md#full-flag-reference).

---

## Model Selection Guide

See the canonical [Whisper Model Reference in the README](../README.md#whisper-models) for parameter
counts, download sizes, and trade-offs. Short version: `turbo` is the default and right for almost
every use case. Switch to `large-v3` only when turbo's quality isn't good enough on a specific video.

**Apple Silicon — GPU acceleration via MLX.** With the `mlx` extra installed the tool uses
`mlx-whisper`, which runs on the Metal GPU and Neural Engine. This is dramatically faster than CPU
and keeps the fans quiet. The device flag is `--device mps`, which is the default on Apple Silicon.

> `faster-whisper` uses CTranslate2, which supports CUDA GPUs only — it always runs on CPU on a Mac.
> The `mlx` extra is the answer for Apple Silicon GPU acceleration.

---

## Keeping the Tool Updated

```bash
# Apple Silicon
uv tool install "git+https://github.com/overtonlabs/youtube-transcriber.git[mlx]" --force

# Intel Mac / Linux
uv tool install git+https://github.com/overtonlabs/youtube-transcriber.git --force
```

After updating the CLI, re-import the skill if a new release changed it — check
[CHANGELOG.md](../CHANGELOG.md).

---

## Troubleshooting

### "command not found: youtube-transcriber"

```bash
uv tool update-shell
source ~/.zshrc
```

Or use the full path: `~/.local/bin/youtube-transcriber`.

### "ffmpeg is not installed"

```bash
brew install ffmpeg
```

### "mlx-whisper is not installed"

You're on Apple Silicon without the `mlx` extra, and there is no CPU fallback on that path.

```bash
uv tool install "git+https://github.com/overtonlabs/youtube-transcriber.git[mlx]" --force
# from a clone:  uv sync --extra mlx
```

Verify by looking for `Device: Apple Silicon GPU  [MLX / Metal + Neural Engine]` in the banner.

### CPU pegged / fans blowing on Apple Silicon

This means the CPU backend is running, which on Apple Silicon only happens if `--device cpu` was
passed. Drop the flag. (On an Intel Mac, CPU is the only backend and this is expected — use a
smaller model to reduce load.)

### "Another youtube-transcriber process is already running"

Only one transcription runs at a time. Wait for it to finish, or clear a stale lock left by a
crashed run. The error message prints the exact path; on macOS the lock is in `$TMPDIR`, not `/tmp`:

```bash
rm "${TMPDIR:-/tmp}/youtube-transcriber.lock"
```

### Transcript is empty / 0 segments

Almost always the VAD filter discarding audio it classified as non-speech — music, effects, and
background audio all trigger it. Confirm with debug logging:

```bash
youtube-transcriber transcribe "<url>" --model tiny --log
```

If `~/.local/share/youtube-transcriber/debug.log` contains `VAD filter removed Xm Xs of audio`,
that's the cause. Don't use `--vad` for anything but clean speech.

### yt-dlp JavaScript runtime warning

`No supported JavaScript runtime could be found` means Node.js isn't on the PATH of the process
running the tool.

```bash
brew install node
```

Don't use nvm, volta, or fnm for this — they inject PATH only in interactive shells, and GUI apps
like Claude Desktop launch without one.

### "Sign in to confirm you're not a bot"

YouTube is rate-limiting the download. Pass your browser's cookies:

```bash
youtube-transcriber transcribe "<url>" --cookies-from-browser chrome
```

Any browser yt-dlp supports works: `chrome`, `firefox`, `safari`, `edge`, `brave`. The browser's
cookie store must be readable. (There is no `--cookies FILE` flag.)

### "No video ID could be extracted"

The URL is a playlist, channel, or search page. This tool transcribes one video per invocation —
pass a single video URL. A watch URL carrying `&list=...` is fine; only that video is downloaded.

### Transcription is slow

- **Apple Silicon:** make sure the `mlx` extra is installed and the banner shows the MLX device line.
- First run of a model downloads it — later runs are much faster.
- Use a smaller model: `--model small` or `--model tiny`.
- On the CPU backend the default is 4 threads, not all cores. Pass
  `--num-threads "$(sysctl -n hw.logicalcpu)"` to use them all.

### Claude doesn't use the tool automatically

- Confirm the skill is installed and enabled: **Settings → Skills** in Claude Desktop, or
  `~/.claude/skills/youtube-transcribe/` for Claude Code.
- Ask explicitly: *"Use the youtube-transcribe skill on this: \<url\>"*.
- Confirm the CLI is on your PATH from a fresh Terminal window — that is the environment the skill
  invokes it in.
