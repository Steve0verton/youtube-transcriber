# YouTube Transcriber

A local, privacy-preserving CLI tool that downloads audio from YouTube videos and transcribes them using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — entirely on your machine. No cloud transcription, no API keys required. The transcript is written to stdout, ready to be piped into any LLM for analysis.

> **Why not just pull YouTube's auto-captions?**  
> YouTube's captions are often inaccurate, missing entirely for many videos, and rely on an undocumented API that breaks without notice. Local transcription with Whisper gives you consistent, high-quality results on *every* video.

---

## Features

- **Fully local** — audio download + transcription happen on your machine
- **No API keys** — yt-dlp handles YouTube audio extraction; browser cookies can be used as a workaround for bot-detection issues
- **High-quality transcription** — faster-whisper with configurable model sizes (tiny → large-v3 → turbo)
- **GPU auto-detection** — uses CUDA if available, falls back to CPU automatically
- **Multiple output formats** — plain text, JSON (with timestamps), SRT, VTT
- **LLM-friendly** — clean text to stdout, status/progress to stderr; designed to pipe into Claude, Ollama, or any LLM
- **Lightweight** — minimal dependencies, single `uv` install

---

> ### ⚠️ VAD flag: read before using with any video
>
> The `--vad` flag enables Voice Activity Detection pre-filtering. It silently discards
> anything it classifies as "not speech" — including music, background audio, and
> mixed content. **Using `--vad` on a music video or any video with background audio
> will result in 0 transcript segments.**
>
> | Content type | Use `--vad`? |
> |---|---|
> | Music video | ❌ Never — entire track discarded |
> | YouTube video with intro music or background audio | ❌ No |
> | Lecture, talk, podcast (voice only, no music) | ✅ Yes — removes silence, speeds up transcription |
> | Interview in a quiet room | ✅ Generally safe |
>
> **Default: `--vad` is OFF.** Omit the flag for any video with music or mixed audio.
> If you get 0 segments, run with `--log` — look for `VAD filter removed Xm Xs of audio`.

---

## Platform Support

- **Linux (Ubuntu/Debian)** — fully supported. CLI tool runs natively; recommended for servers and automated pipelines.
- **macOS** — fully supported. Apple Silicon users can install the `mlx` extra for GPU-accelerated transcription via Metal.
- **Windows** — not currently tested or supported.

The `osascript`-based Claude Desktop integration examples in `docs/` are macOS-specific, but the CLI tool itself works identically on Linux and macOS.

---

## Requirements

- **Python 3.11+**
- **[ffmpeg](https://ffmpeg.org/download.html)** — required by yt-dlp for audio extraction
- **[uv](https://docs.astral.sh/uv/)** — recommended for installation and running
- **[Node.js](https://nodejs.org/)** — required by yt-dlp to solve YouTube's JS challenges and extract audio formats reliably

```bash
# macOS
brew install ffmpeg node

# Ubuntu/Debian
sudo apt install ffmpeg nodejs
```

> **macOS note:** Install Node.js via Homebrew (`brew install node`), not nvm.
> macOS GUI apps (including Claude Desktop) launch without a full shell environment,
> so nvm-managed runtimes may not be found. Homebrew puts node at a fixed system path
> (`/opt/homebrew/bin/node`) that is always accessible.

---

## Installation

### As a standalone tool with uv (recommended for most users)

Install once, run from anywhere — no virtual environment to activate, no `uv run` prefix needed:

```bash
uv tool install git+https://github.com/Steve0verton/youtube-transcriber.git
youtube-transcriber --help
```

To upgrade later:

```bash
uv tool upgrade youtube-transcriber
```

### From a local clone (for development)

```bash
# Clone the repo
git clone https://github.com/Steve0verton/youtube-transcriber.git
cd youtube-transcriber

# Install dependencies (Python 3.12 is pinned via .python-version)
uv sync

# Run
uv run youtube-transcriber --help
```

> **Apple Silicon (M1/M2/M3/M4):** Install the `mlx` extra for GPU-accelerated transcription
> via Apple Metal instead of CPU:
> ```bash
> uv sync --extra mlx
> ```

### Using pip

```bash
pip install git+https://github.com/Steve0verton/youtube-transcriber.git
youtube-transcriber --help
```

---

## Usage

### Basic transcription (outputs plain text to stdout)

```bash
youtube-transcriber transcribe "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Select a Whisper model

```bash
# Fast, low memory (good for testing)
youtube-transcriber transcribe <url> --model tiny

# Best quality (requires ~6GB VRAM or ~12GB RAM)
youtube-transcriber transcribe <url> --model large-v3

# Balanced speed + quality (default, ~800MB VRAM or ~2GB RAM)
youtube-transcriber transcribe <url> --model turbo
```

### Output formats

```bash
# Plain text (default)
youtube-transcriber transcribe <url> --format text

# JSON with timestamps
youtube-transcriber transcribe <url> --format json

# SRT subtitle file
youtube-transcriber transcribe <url> --format srt

# WebVTT subtitle file
youtube-transcriber transcribe <url> --format vtt
```

### Save to a file

```bash
youtube-transcriber transcribe <url> --output transcript.txt
youtube-transcriber transcribe <url> --format srt --output subtitles.srt
```

### Force CPU

```bash
youtube-transcriber transcribe <url> --device cpu
```

### VAD pre-filtering — speech-only content only

Default: **off.** Only enable for recordings where the full audio is clean speech
with no background music or effects.

```bash
# Safe: podcast, lecture, interview — no background music
youtube-transcriber transcribe <url> --vad

# WRONG — never use --vad with music videos, intros, or background audio
# The VAD model will classify the entire track as non-speech and return nothing
```

See the [VAD callout above](#️-vad-flag-read-before-using-with-any-video) for a full content-type decision table.

### Debug logging

When a transcription produces unexpected results (0 segments, wrong language, etc.),
enable debug logging to see exactly what yt-dlp and faster-whisper are doing.

```bash
# Log to the default path (~/.local/share/youtube-transcriber/debug.log)
youtube-transcriber transcribe <url> --log

# Log to a custom file
youtube-transcriber transcribe <url> --log-file /tmp/yt-debug.log
```

### List available models

```bash
youtube-transcriber models
```

---

## Integration with Claude Desktop

Claude Desktop can run shell commands directly — no MCP server needed. Just ask Claude:

> "Please transcribe this YouTube video for me: https://www.youtube.com/watch?v=..."

Claude will run:
```bash
youtube-transcriber transcribe "https://..." 2>/dev/null
```

The `2>/dev/null` suppresses progress output so Claude receives only the clean transcript text. From there, Claude can summarize, extract key points, translate, or answer questions about the content.

### Example Claude prompt

```text
Transcribe this YouTube video and give me a 5-bullet summary of the key points:
https://www.youtube.com/watch?v=...
```

Claude runs `youtube-transcriber transcribe <url>` and works with the returned text directly.

---

## Architecture

```text
YouTube URL
    │
    ▼
youtube-transcriber CLI (click)
    │
    ├── downloader.py   ── yt-dlp (downloads best audio → temp file)
    │
    ├── transcriber.py  ── faster-whisper (local AI transcription)
    │
    ├── formatters.py   ── text / json / srt / vtt output
    │
    └── stdout (transcript) + stderr (progress/status)
```

**Key dependencies:**
| Package | Purpose |
|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | YouTube audio download (cookies, auth, 1000+ sites) |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Local speech-to-text (4× faster, ½ the memory of original Whisper) |
| [click](https://click.palletsprojects.com/) | CLI framework |

---

## Whisper Model Reference

| Model | Parameters | Speed | VRAM | Notes |
|---|---|---|---|---|
| `tiny` | 39M | Fastest | ~1 GB | Good for testing |
| `base` | 74M | Very fast | ~1 GB | |
| `small` | 244M | Fast | ~2 GB | |
| `medium` | 769M | Moderate | ~5 GB | |
| `large-v3` | 1550M | Slow | ~10 GB | Best quality |
| `turbo` | 809M | Fast | ~6 GB | **Default** — optimized large-v3, 8× faster with minimal quality loss |

`.en` English-only variants are available for `tiny`, `base`, `small`, `medium` and are slightly faster/more accurate for English content.

---

## Roadmap

- [ ] Batch / playlist transcription (`youtube-transcriber playlist <url>`)
- [ ] Speaker diarization (identify different speakers)
- [ ] Post-processing with local LLMs via Ollama
- [ ] MCP server mode for richer LLM agent integration
- [ ] OpenAI Whisper API as optional cloud backend
- [ ] VS Code extension with transcript viewer and timestamp navigation

---

## Troubleshooting

### Transcript returns 0 segments

The most common cause is the VAD filter being enabled on content with background audio.
Run with `--log` to see what faster-whisper is actually doing:

```bash
youtube-transcriber transcribe <url> --model tiny --log
```

If the log contains `VAD filter removed Xm Xs of audio`, you have a VAD issue.
Do **not** use `--vad` for music videos or any content with background audio.

### yt-dlp JavaScript runtime warning

If you see `No supported JavaScript runtime could be found`, Node.js is either
not installed or not on the system PATH. Install it via your system package manager:

```bash
brew install node       # macOS
sudo apt install nodejs # Ubuntu/Debian
```

Avoid nvm or other shell-level version managers for deployments where the tool is
invoked non-interactively (e.g., by Claude Desktop).

### yt-dlp bot detection error

YouTube is rate-limiting the download. The tool does not currently expose a `--cookies`
CLI flag, but you can work around this at the yt-dlp level using a cookies file.

**Option 1 — Export cookies manually from Chrome:**

1. Install a browser extension such as [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   (audit any extension before installing — only use trusted, open-source options).
2. Navigate to `youtube.com` while logged in.
3. Export cookies to a `.txt` file in Netscape/Mozilla format.
4. Run yt-dlp directly to verify the cookies work, then use them as a workaround until
   a `--cookies` flag is added to this CLI.

**Option 2 — Chrome DevTools Protocol (CDP) / Chrome MCP:**

If you have a Chrome MCP server available (e.g., via a Puppeteer/Playwright MCP that
exposes CDP), you can instruct your LLM agent to:

1. Open `youtube.com` in the connected Chrome instance while logged in.
2. Use CDP's `Network.getCookies` domain to extract the session cookies.
3. Write them to a Netscape-format `cookies.txt` file.
4. Pass that file directly to yt-dlp outside of this CLI tool.

> **Security note:** Cookie files grant full account access. Store them outside your project
> directory, never commit them to version control, and delete them when no longer needed.

> **Roadmap:** Proper `--cookies` and `--cookies-from-browser` flags are candidates for a
> future release. If you need this, open an issue or submit a PR.

---

## Documentation

| Doc | Description |
|---|---|
| [setup-claude-desktop.md](docs/setup-claude-desktop.md) | Install on a new machine and configure Claude Desktop |
| [lessons-learned/2026-03-02-vad-and-nodejs-fixes.md](docs/lessons-learned/2026-03-02-vad-and-nodejs-fixes.md) | VAD silence bug and Node.js runtime discovery |

---

## Contributing

Pull requests are welcome. For major changes, open an issue first.

```bash
# Install dev dependencies
uv sync --extra dev

# Lint
uv run ruff check src/

# Run tests
uv run pytest
```

---

## License

[GPL-3.0](LICENSE) — see the LICENSE file for details.
