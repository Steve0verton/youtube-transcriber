# Changelog

All notable changes to the "YouTube Transcriber" will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-02

### Added

- **Apple Silicon GPU acceleration via `mlx-whisper`** — on M-series Macs the tool
  now automatically uses `mlx-whisper` (Apple's MLX framework) instead of
  `faster-whisper`. This routes transcription through the Metal GPU and Apple Neural
  Engine, delivering dramatically faster results (a 63-minute video in ~22 seconds)
  with no CPU overload, no fan noise. Requires the new optional dependency group:
  `uv sync --extra mlx` (or `uv tool install . --with mlx-whisper`).
- `is_apple_silicon()` utility — detects arm64 macOS via `platform.machine()`.
- `MLX_MODEL_REPOS` mapping in `transcriber.py` — maps all user-facing model names
  to their `mlx-community/` HuggingFace repos for automatic download on first use.
- `_transcribe_mlx()` private function — full MLX transcription backend that returns
  a `TranscriptResult` using the same data contract as the faster-whisper backend.
- `--device mps` option — explicitly selects the MLX backend; `auto` now resolves
  to `mps` on Apple Silicon, `cuda` on NVIDIA GPUs, then `cpu`.
- `--num-threads INTEGER` option — caps the number of CPU threads faster-whisper may
  use (default: 4). Prevents pegging all cores on non-Apple-Silicon machines.
  Ignored when using the MLX backend.
- **Process-level run lock** — `acquire_run_lock()` / `release_run_lock()` in
  `utils.py` write a PID file to `/tmp/youtube-transcriber.lock`. The CLI checks the
  lock at startup and exits immediately with a clear error if another instance is
  already running, preventing multiple parallel transcriptions from overwhelming
  system resources.
- `mlx = ["mlx-whisper>=0.4.0"]` optional dependency group in `pyproject.toml`.

### Changed

- `detect_device()` now returns `"mps"` on Apple Silicon instead of `"cpu"`.
  The faster-whisper path (cuda/cpu) is used only on non-Apple-Silicon machines.
- `transcribe_audio()` now accepts `num_threads` parameter (default 4) and routes
  to `_transcribe_mlx()` when `resolved_device == "mps"`.
- `--device` CLI option now includes `mps` as a valid choice alongside `auto`,
  `cuda`, and `cpu`.
- Updated `docs/setup-claude-desktop.md`: install instructions for `mlx` extra,
  revised system prompt with parallel-run warning and Terminal monitoring guidance,
  expanded model selection table with Apple Silicon GPU notes, new troubleshooting
  sections for CPU pegging and process lock errors.

## [0.1.1] - 2026-03-02

### Fixed

- **VAD filter was hardcoded `True`, causing 0 segments on all mixed-audio content.**
  The Silero VAD model classifies music, background audio, and mixed content as
  non-speech and silently discards it before Whisper runs. Any YouTube video with
  background music (including music videos, videos with intros, etc.) returned an
  empty transcript with no error. VAD is now **off by default** and must be
  explicitly opted into via `--vad`.
- yt-dlp `js_runtimes` was passed as a CLI string (`"node:/path/to/node"`) instead
  of the Python API dict format (`{"node": {"path": "..."}}`), raising a `ValueError`
  crash when the JS runtime fix was first applied.
- Node.js runtime discovery now probes well-known absolute paths (Homebrew, nvm
  version directories, Volta, fnm) as fallbacks when `shutil.which` cannot find a
  runtime. This ensures yt-dlp JS challenge solving works when the tool is invoked
  from non-interactive contexts (e.g. Claude Desktop) that do not source shell
  config files and therefore lack nvm/volta PATH injections.

### Added

- `--vad` flag — opt-in Voice Activity Detection pre-filtering for clean speech
  recordings (talks, podcasts, interviews with no background audio). Removes silence
  and speeds up transcription. **Do not use for music videos or mixed-audio content.**
- `--log` flag — enables structured debug logging to the default path
  (`~/.local/share/youtube-transcriber/debug.log`) using a rotating file handler
  (5 MB × 3 backups).
- `--log-file FILE` flag — same as `--log` but writes to a user-specified path.
- `src/youtube_transcriber/logging_config.py` — new module providing `setup_logging()`
  for consistent file-based debug logging; suppresses noisy third-party loggers.
- Debug `log.*` calls throughout `downloader.py` and `transcriber.py` (JS runtime
  selection, yt-dlp options and download result, VAD decisions, model load,
  per-segment output).
- `docs/lessons-learned/2026-03-02-vad-and-nodejs-fixes.md` — post-mortem covering
  the VAD silence bug, the Node.js runtime issues, and the role debug logging played
  in diagnosing both.

### Changed

- `transcribe_audio()` signature gains a `vad_filter: bool = False` parameter;
  VAD parameters (`threshold`, `min_speech_duration_ms`, `speech_pad_ms`, etc.) are
  only applied when `vad_filter=True`.
- `_find_js_runtime()` in `downloader.py` now returns a `dict` (Python API format)
  instead of a string; probes PATH first, then falls back through a curated list of
  absolute install locations.
- Node.js (`brew install node`) added to documented system requirements; install
  instructions updated in README and setup guide to recommend Homebrew over nvm.
- README features callout and `--vad` usage section now include a content-type
  decision table to prevent misuse on mixed-audio content.

## [0.1.0] - 2026-03-02

### Added

- Initial release of `youtube-transcriber` CLI tool
- `transcribe` command — downloads YouTube audio via yt-dlp and transcribes locally
  using faster-whisper; supports any standard YouTube URL format (watch, youtu.be,
  Shorts, embed, live)
- `models` command — lists all available Whisper models with parameter counts and VRAM
  requirements
- Four output formats: `text` (default), `json` (with timestamps), `srt`, `vtt`
- `--model` flag for selecting Whisper model size (`tiny` through `large-v3`, default `turbo`)
- `--device` flag for compute device selection (`auto`, `cuda`, `cpu`)
- `--compute-type` flag for quantization control (`auto`, `float16`, `int8`, etc.)
- `--beam-size` flag for decoding quality/speed trade-off
- `--output` flag to write transcript to a file instead of stdout
- `--quiet` / `-q` flag to suppress all stderr progress output for clean LLM piping
- `--version` flag showing package version
- Auto GPU detection via CTranslate2; graceful fallback to CPU if CUDA unavailable or
  insufficient VRAM
- Voice Activity Detection (VAD) via Silero — skips silence for faster transcription
- Temp audio file auto-cleanup via context manager (no files left in working directory)
- ffmpeg presence check at startup with clear install instructions
- URL validation using `urlparse` hostname matching (resistant to subdomain spoofing)
- Progress output to stderr; clean transcript text to stdout — designed for LLM piping
- HuggingFace model cache integration (models downloaded once, reused automatically)
- Project scaffolding: `pyproject.toml` (uv), `ruff` lint config, `pytest` test config
- Unit test suite: 61 tests covering URL parsing, timestamp formatting, and all four
  output format functions
- `CHANGELOG.md` following Keep a Changelog format with Semantic Versioning
- GPL-3.0 license, copyright Overton Labs, LLC
- `.gitattributes` for consistent LF line endings across platforms
- `.github/copilot-instructions.md` for AI-assisted development context
