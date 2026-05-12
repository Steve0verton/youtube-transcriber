# CLAUDE.md — youtube-transcriber

Guidance for Claude Code (or any AI assistant) working in this repository.
For broader project background, also read `README.md`, `.github/copilot-instructions.md`,
and the lessons-learned files under `docs/lessons-learned/`.

---

## What this project is

`youtube-transcriber` is a **local, offline Python CLI** that downloads YouTube audio
with `yt-dlp` and transcribes it with `faster-whisper` (or `mlx-whisper` on Apple Silicon).
The tool is designed to be **invoked by an LLM agent** (Claude Desktop, Claude Code) over
shell — not used interactively by a human.

Two distinct audiences for this tool:

1. **Human developer using Claude Code on this repo** — that's you, working on the CLI.
2. **Claude Desktop running the installed CLI** — sees the CLI as a black box; relies on the
   stdout/stderr contract and the macOS skill at `docs/youtube-transcribe.skill.md`.

Keep both in mind when changing user-visible behavior.

### Design philosophy (do not violate without discussion)

- **Always transcribe locally.** No cloud APIs, no transcription API keys. yt-dlp is the
  only network call; everything else runs on-device.
- **Do not scrape YouTube captions.** They are inconsistent and the endpoint is unofficial.
  Whisper always runs locally for quality consistency.
- **stdout = transcript, stderr = everything else.** This is a hard contract — the entire
  point is that an LLM can pipe stdout into another prompt. Any progress, banner, or
  warning text MUST go through `click.echo(..., err=True)`. The MLX backend has a
  `_stdout_to_stderr()` context manager specifically because `mlx_whisper.transcribe(verbose=True)`
  prints to stdout — do not remove it.
- **Batch, not interactive.** One URL in, one transcript out. No prompts, no menus.
- **Single instance.** A PID lock at `/tmp/youtube-transcriber.lock` prevents parallel
  runs from overwhelming the GPU/CPU. Don't remove this.
- **No files written to the user's working directory by default.** Audio goes to
  `tempfile.TemporaryDirectory()`; the transcript goes to stdout unless `--output` is given.

---

## Tech stack and conventions

| Layer | Tool | Notes |
|---|---|---|
| Language | Python 3.11+ | `.python-version` pins to 3.12; `requires-python = ">=3.11"` in `pyproject.toml`. Ruff `target-version = "py310"` is a known minor inconsistency — leave it. |
| Package manager | `uv` | Always use `uv sync` / `uv run`. `uv.lock` is committed. |
| CLI | `click` | Two commands: `transcribe`, `models`. |
| Audio download | `yt-dlp` Python API | Needs a JS runtime (Node/Deno/Bun) — see "Landmines" below. |
| Transcription (default) | `faster-whisper` (CTranslate2) | CPU + CUDA. |
| Transcription (Apple Silicon) | `mlx-whisper` (Apple MLX) | Optional extra: `uv sync --extra mlx`. Metal GPU + ANE. |
| Tests | `pytest` | Only `utils` + `formatters` (no network/model deps). |
| Lint | `ruff` | Config in `pyproject.toml`. |
| License | GPL-3.0 | |

### Style

- Type hints on all function signatures, return types included.
- Google-style docstrings on public functions and classes.
- `snake_case` functions/vars, `PascalCase` classes, `ALL_CAPS` module constants, `_leading_underscore` for private helpers.
- `pathlib.Path` over `os.path`.
- Context managers for resource cleanup (temp files, model handles, stdout redirect).
- Validate inputs early; raise `click.BadParameter` or `click.ClickException` with actionable hints.
- Default to writing no comments. Only add them for non-obvious "why."

---

## Module layout

```text
src/youtube_transcriber/
├── __init__.py          # __version__ — keep in sync with pyproject.toml
├── cli.py               # click entry point; argument parsing, banner, file output routing
├── downloader.py        # yt-dlp wrapper; download_audio() contextmanager; JS runtime probe
├── transcriber.py       # WhisperModel + mlx-whisper; TranscriptResult/Segment dataclasses
├── formatters.py        # text/json/srt/vtt; register new formats in FORMAT_FUNCTIONS
├── utils.py             # URL parsing, device detection, ffmpeg check, run lock, time formatting
└── logging_config.py    # Rotating file handler enabled by --log / --log-file
```

`tests/` covers `test_utils.py` and `test_formatters.py` only. The downloader and
transcriber require network and model downloads, so they are exercised manually.

---

## Landmines — read before changing the relevant code

These are the bugs that have actually shipped and been fixed. See
`docs/lessons-learned/2026-03-02-vad-and-nodejs-fixes.md` for the post-mortem.

### 1. VAD filter discards music as non-speech

Silero VAD (used by faster-whisper) classifies music and mixed audio as "not speech"
and silently throws it away — returns 0 segments with no error.

- `--vad` MUST default to off. Do not flip this.
- The flag must remain opt-in for clean-speech recordings only (talks, podcasts).
- `--vad` is silently ignored by the MLX backend; this is intentional.
- If a user reports "0 segments returned," ask whether they used `--vad`.

### 2. yt-dlp needs a JS runtime that GUI processes can find

YouTube uses JS challenges. `yt-dlp`'s Python API defaults `js_runtimes` to `{"deno": {}}`
which is almost never installed. `downloader._find_js_runtime()` exists to fix this.

Two things to never break:
- **`js_runtimes` must be a Python dict** like `{"node": {"path": "/path/to/node"}}` — not the
  CLI string format `"node:/path"`. The latter raises `ValueError` inside yt-dlp.
- **PATH-based discovery is not enough on macOS.** Claude Desktop and other GUI apps launch
  without sourcing `~/.zshrc`, so nvm-managed runtimes are invisible. The fallback walks
  `/opt/homebrew/bin`, `/usr/local/bin`, `~/.nvm/versions/node/*/bin/node`, `~/.volta`,
  and `~/.fnm`. Keep this fallback list current with reality.

Documentation everywhere says: **install Node via Homebrew, not nvm.**

### 3. Apple Silicon defaults to MLX, not CPU

`detect_device()` returns `"mps"` on arm64 macOS. `transcribe_audio()` then routes to
`_transcribe_mlx()`, which requires the `mlx` extra (`uv sync --extra mlx`). On Apple
Silicon without that extra installed, transcription will fail with a clear ImportError
message.

If you see CPU pegging on a Mac, the `mlx` extra is not installed.

### 4. The stdout/stderr split is load-bearing

`mlx_whisper.transcribe(verbose=True)` prints `[hh:mm:ss --> hh:mm:ss] text` lines to
**stdout**. Without `_stdout_to_stderr()` in `transcriber.py`, those lines would corrupt
the transcript that the agent reads. Do not remove that contextmanager; verify it stays
in the verbose path if you refactor.

### 5. Output filename auto-injects the video ID

`cli.transcribe` rewrites `--output transcript.txt` to `transcript_<videoId>.txt`. This
exists because an LLM transcribing two videos in one prompt would otherwise silently
overwrite the first transcript with the second. Don't remove the injection; the skill
doc relies on this behavior.

---

## Common commands

```bash
# Install
uv sync                          # base deps
uv sync --extra mlx              # + Apple Silicon GPU backend
uv sync --extra dev              # + pytest, ruff

# Run
uv run youtube-transcriber --help
uv run youtube-transcriber transcribe "<url>"
uv run youtube-transcriber models

# Test + lint (run both before opening a PR)
uv run pytest
uv run ruff check src/ tests/

# Debug transcription issues
uv run youtube-transcriber transcribe "<url>" --log
tail -f ~/.local/share/youtube-transcriber/debug.log
```

---

## Adding things

**New output format** — add a `format_<name>(result: TranscriptResult) -> str` function to
`formatters.py`, register it in the `FORMAT_FUNCTIONS` dict at the bottom, and add a unit
test class to `tests/test_formatters.py`. The `--format` click.Choice is wired from
`FORMAT_FUNCTIONS.keys()` automatically.

**New Whisper model** — add to `AVAILABLE_MODELS` and `MLX_MODEL_REPOS` (in `transcriber.py`)
and to the README/skill-doc model tables. The CLI validates against `AVAILABLE_MODELS`.

**New CLI flag** — add a `@click.option` on `cli.transcribe`, thread it through to
`transcribe_audio()`, and update the README usage section and `docs/youtube-transcribe.skill.md`
if the agent should know about it. Whether to surface it to the agent depends on whether
the agent benefits from controlling it — default flags rarely need to appear in the skill.

---

## Release process

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) + SemVer.
When the user asks to cut a release:

1. Add a new section to `CHANGELOG.md` under `## [X.Y.Z] - YYYY-MM-DD` with categories
   (`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`).
2. Bump the version in **both** places:
   - `src/youtube_transcriber/__init__.py` — `__version__ = "X.Y.Z"`
   - `pyproject.toml` — `version = "X.Y.Z"`
3. `uv run pytest` and `uv run ruff check src/ tests/` — both must pass.
4. Commit: `chore: release vX.Y.Z`.

Do not skip the dual version bump — they will drift, and the banner shown to the agent
reads from `__init__.py` while installers read from `pyproject.toml`.

---

## Platform notes

- **macOS is the primary target.** Apple Silicon gets MLX; Intel Macs fall back to CPU.
- **Linux works for the CLI** but the Claude Desktop skill (`docs/youtube-transcribe.skill.md`)
  uses `osascript` and is macOS-only.
- **Windows is unsupported.** Don't add Windows install paths to the `_find_js_runtime`
  fallback list unless the user asks for Windows support.
- macOS GUI apps launch with a stripped PATH — anything the tool needs at runtime must be
  discoverable via absolute path or via `_find_js_runtime`-style fallback.

---

## Cross-references

| File | Purpose |
|---|---|
| `README.md` | User-facing install + usage |
| `.github/copilot-instructions.md` | Copilot agent context (overlaps with this file) |
| `docs/setup-claude-desktop.md` | End-user setup guide for Claude Desktop |
| `docs/youtube-transcribe.skill.md` | Skill that Claude Desktop loads — describes osascript invocation |
| `docs/lessons-learned/2026-03-02-vad-and-nodejs-fixes.md` | VAD + JS-runtime post-mortem |
| `CHANGELOG.md` | Version history (Keep a Changelog format) |
