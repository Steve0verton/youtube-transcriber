# GitHub Copilot Instructions — youtube-transcriber

## Project Overview

`youtube-transcriber` is a **Python CLI tool** that downloads audio from YouTube videos
and transcribes them locally using faster-whisper. It is designed to be invoked directly
by LLMs (Claude Desktop, Claude Code, etc.) that have local shell access. The transcript
is written to **stdout** as clean text; progress/status messages go to **stderr**.

Core design philosophy:
- **Always transcribe locally** — no cloud transcription, no API keys for the core workflow
- **Batch, not interactive** — one command in, one transcript out
- **LLM-friendly output** — stdout is clean text only, ready to be piped into an AI model
- **Minimal dependencies** — keep the dependency graph small and purposeful

---

## Tech Stack

| Layer | Tool | Notes |
|---|---|---|
| Language | Python 3.10+ | Type hints required on all functions |
| Package manager | uv | Use `uv sync` / `uv run` |
| CLI framework | click | Commands: `transcribe`, `models` |
| Audio download | yt-dlp (Python API) | Extracts best audio to temp file |
| Transcription | faster-whisper | CTranslate2 backend; auto GPU/CPU |
| Output formats | built-in string formatting | text, json, srt, vtt |
| Testing | pytest | Unit tests for utils + formatters |
| Linting | ruff | Enforced in CI |
| License | GPL-3.0 | All derivatives must remain open source |

---

## Project Structure

```
youtube-transcriber/
├── pyproject.toml
├── src/
│   └── youtube_transcriber/
│       ├── __init__.py      # version string
│       ├── cli.py           # click CLI entry point
│       ├── downloader.py    # yt-dlp wrapper — download_audio()
│       ├── transcriber.py   # faster-whisper wrapper — transcribe_audio()
│       ├── formatters.py    # text / json / srt / vtt formatters
│       └── utils.py         # URL parsing, GPU detection, ffmpeg check
└── tests/
    ├── __init__.py
    ├── test_utils.py
    └── test_formatters.py
```

---

## Coding Conventions

- **Type hints** on all function signatures (parameters and return type)
- **Docstrings** on all public functions and classes (Google style)
- **snake_case** for functions, variables, modules
- **PascalCase** for classes
- **ALL_CAPS** for module-level constants
- Progress/status output → `click.echo(..., err=True)` (stderr)
- Transcript output → `click.echo(...)` or `print(...)` (stdout)
- Use `pathlib.Path` instead of `os.path` string manipulation
- Prefer context managers for resource cleanup (temp files, model handles)
- Validate YouTube URL early; raise `click.BadParameter` with a helpful message

---

## Key Patterns

### Downloading audio

```python
from youtube_transcriber.downloader import download_audio

with download_audio("https://youtube.com/watch?v=...") as audio_path:
    # audio_path is a Path to a temp .wav/.m4a file
    # automatically cleaned up on context manager exit
    result = transcribe_audio(audio_path, model="turbo", device="auto")
```

### Transcription result shape

```python
@dataclass
class TranscriptSegment:
    start: float   # seconds
    end: float     # seconds
    text: str

@dataclass
class TranscriptResult:
    segments: list[TranscriptSegment]
    language: str
    duration: float
```

### Adding a new output format

Add a function to `formatters.py` following the pattern:
```python
def format_myformat(result: TranscriptResult) -> str:
    ...
```
Then add the format name to the `--format` option choices in `cli.py` and dispatch to your
new function in the format routing block.

---

## What NOT to do

- Do **not** write any audio files or transcripts to the user's working directory by default
  (use `tempfile` for intermediate audio; only write transcript if `--output` is specified)
- Do **not** add cloud transcription calls in the core workflow (keep it offline by default)
- Do **not** scrape YouTube captions or use `youtube-transcript-api` — we always transcribe
  locally for quality consistency
- Do **not** print transcript text to stderr or progress text to stdout — keep them separated
- Do **not** hardcode model paths — use faster-whisper's built-in HuggingFace cache

---

## Running Locally

```bash
uv sync                  # install deps
uv run youtube-transcriber --help
uv run youtube-transcriber transcribe "<url>"
uv run pytest            # tests
uv run ruff check src/   # lint
```

---

## Changelog Maintenance

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

When work is complete and ready to record, add an entry to `CHANGELOG.md` under the
appropriate version section. Use one of these category headings:

| Category | When to use |
|---|---|
| `Added` | New features or commands |
| `Changed` | Changes to existing behaviour |
| `Deprecated` | Features that will be removed in a future release |
| `Removed` | Features removed in this release |
| `Fixed` | Bug fixes |
| `Security` | Security-related changes or vulnerability fixes |

### Version bump checklist
1. Add all completed changes to `CHANGELOG.md` under the new version + today's date
2. Update `__version__` in `src/youtube_transcriber/__init__.py`
3. Update `version` in `pyproject.toml`
4. Run `uv run pytest` and `uv run ruff check src/ tests/` — both must pass
5. Commit with message: `chore: release vX.Y.Z`
