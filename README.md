# YouTube Transcriber

A local, privacy-preserving CLI tool that downloads audio from YouTube videos and transcribes them using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — entirely on your machine. No cloud transcription, no API keys required. The transcript is written to stdout, ready to be piped into any LLM for analysis.

> **Why not just pull YouTube's auto-captions?**  
> YouTube's captions are often inaccurate, missing entirely for many videos, and rely on an undocumented API that breaks without notice. Local transcription with Whisper gives you consistent, high-quality results on *every* video.

---

## Features

- **Fully local** — audio download + transcription happen on your machine
- **No API keys** — yt-dlp handles YouTube auth via browser cookies if needed
- **High-quality transcription** — faster-whisper with configurable model sizes (tiny → large-v3 → turbo)
- **GPU auto-detection** — uses CUDA if available, falls back to CPU automatically
- **Multiple output formats** — plain text, JSON (with timestamps), SRT, VTT
- **LLM-friendly** — clean text to stdout, status/progress to stderr; designed to pipe into Claude, Ollama, or any LLM
- **Lightweight** — minimal dependencies, single `uv` install

---

## Requirements

- **Python 3.10+**
- **[ffmpeg](https://ffmpeg.org/download.html)** — required by yt-dlp for audio extraction
- **[uv](https://docs.astral.sh/uv/)** — recommended for installation and running

Install ffmpeg (Ubuntu/Debian):
```bash
sudo apt install ffmpeg
```

Install ffmpeg (macOS):
```bash
brew install ffmpeg
```

---

## Installation

### Using uv (recommended)

```bash
# Clone the repo
git clone https://github.com/Steve0verton/youtube-transcriber.git
cd youtube-transcriber

# Install dependencies
uv sync

# Run
uv run youtube-transcriber --help
```

### Using pip

```bash
pip install -e .
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

```
Transcribe this YouTube video and give me a 5-bullet summary of the key points:
https://www.youtube.com/watch?v=...
```

Claude runs `youtube-transcriber transcribe <url>` and works with the returned text directly.

---

## Architecture

```
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

## Documentation

| Doc | Description |
|---|---|
| [setup-claude-desktop.md](docs/setup-claude-desktop.md) | Install on a new machine and configure Claude Desktop |

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
