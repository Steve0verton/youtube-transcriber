# Changelog

All notable changes to the "YouTube Transcriber" will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.6] - 2026-05-11

### Changed

- **Claude skill moved to repo root at `skill/youtube-transcribe/`.** Previously the skill
  source lived under the hidden `docs/.claude/skills/` path, which was invisible in casual
  directory listings and obscured the fact that the project shipped a ready-to-import skill.
  The folder is now first-class — listed in the README's documentation table and surfaced in
  a top-level "Install the Claude Skill" section with three install paths (Claude Desktop /
  Claude.ai via `.skill` bundle, Claude Code via `~/.claude/skills/`, project-scoped via
  `.claude/skills/`).
- **`.skill` bundle is now a release asset, not an in-repo binary.** The packaged
  `youtube-transcribe.skill` (zip of `skill/youtube-transcribe/`) ships as an attached asset
  on each GitHub Release. A reproducible build is provided at `scripts/build-skill.sh`.
  Also fixes a name typo — the bundle was previously named `youtube-transcriber.skill`
  while the skill itself is `youtube-transcribe`.
- **Skill `compatibility` block loosened.** Previously claimed Apple Silicon was required;
  now correctly states macOS is required (osascript-driven workflow) and Apple Silicon is
  recommended for GPU acceleration but Intel Macs still work via the CPU backend.
- **README `Whisper Model Reference` column is now "Size on disk" with accurate values**
  (~75 MB / tiny to ~3 GB / large-v3) instead of the previous "VRAM" column that mixed up
  weight file sizes with runtime memory. The basic-usage examples are aligned with the same
  numbers.
- **`docs/setup-claude-desktop.md` overhauled.** Step 4 now matches the new install paths;
  Step 5 (the misleading empty `{"mcpServers": {}}` snippet) is removed; the "Test Claude
  Integration" and "How It Works" sections now describe the actual osascript-driven skill
  flow rather than a direct shell-pipe flow; the duplicated Model Selection table now links
  to the canonical README table.

### Fixed

- **`--quiet` flag references removed from `docs/setup-claude-desktop.md`.** That flag does
  not exist on the CLI and never did under this version line. Replaced with the documented
  `2>/dev/null` redirect.
- **Flat duplicate `docs/youtube-transcribe.skill.md` removed.** It referenced
  `references/models-and-quality.md` and `references/troubleshooting.md` that did not exist
  next to it, making the single-file form non-functional. The canonical folder form at
  `skill/youtube-transcribe/` is now the only source.

## [0.2.5] - 2026-03-24

### Changed

- **`--num-threads` default changed from `4` → `0` (all CPUs)** — faster-whisper's
  CTranslate2 backend treats `cpu_threads=0` as "use all available logical CPUs",
  meaning the model now saturates the machine's full thread count by default instead
  of being artificially capped at 4. On a machine with many cores this substantially
  reduces transcription wall-clock time with no accuracy trade-off. Users who want
  to limit CPU impact can still pass `--num-threads N` explicitly.
- **`transcribe_audio()` API default updated to match** — `num_threads` parameter
  in the public Python API now defaults to `0` as well, consistent with the CLI.

## [0.2.4] - 2026-03-18

### Fixed

- **Updated yt-dlp lockfile to 2026.03.17** — yt-dlp 2026.02.21 broke YouTube
  audio downloads due to a JS challenge solver regression with Node v25+. Bumping
  the lockfile resolves "Requested format is not available" errors on all player
  clients.

### Added

- **`--cookies-from-browser` CLI option** — pass browser cookies to yt-dlp to
  bypass age-gated and member-only YouTube videos (e.g. `--cookies-from-browser chrome`).
  Opt-in only; not enabled by default. The `download_audio()` function also accepts
  a `cookies_from_browser` parameter for programmatic use.

## [0.2.3] - 2026-03-09

### Changed

- **Bumped `requires-python` from `>=3.10` to `>=3.11`** — `onnxruntime` (a transitive
  dependency of the `mlx` extra) no longer ships wheels for Python 3.10, making installs
  on 3.10 fail. The minimum is now 3.11 to match what the full dependency graph actually
  requires.
- **Added `.python-version` file pinned to 3.12** — `uv` and other tooling (pyenv, mise)
  use this file to auto-select the right interpreter, so `uv sync` works out of the box
  without needing `--python` flags.
- **README updated** — Requirements section now states Python 3.11+; installation section
  notes the `.python-version` pin and adds an Apple Silicon callout for `uv sync --extra mlx`.

## [0.2.2] - 2026-03-08

### Added

- **Video ID injected into output filenames** — when `--output` is specified the tool
  now automatically inserts the 11-character YouTube video ID into the filename stem
  before the extension (e.g. `transcript.txt` → `transcript_dQw4w9WgXcQ.txt`). This
  guarantees unique output files when an LLM transcribes multiple videos in a single
  prompt. If the video ID is already present in the stem it is not duplicated.
- **Video ID shown in progress banner** — the startup banner now includes a `Video:`
  line displaying the extracted video ID alongside the URL, model, format, and device.

### Changed

- **Skill doc updated for video-ID-based filenames** — all `--output /tmp/transcript.txt`
  examples in `docs/youtube-transcribe.skill.md` updated to
  `--output /tmp/transcript_<video_id>.txt`. Added an explanation of the auto-injection
  behaviour, updated Step 2, Step 3 (poll/read), Critical Rule #3, the osascript command
  patterns section, the full command reference, and all troubleshooting examples.
  A new "Multiple videos in one prompt" osascript pattern was added showing how to
  sequence two transcriptions with distinct output files.

## [0.2.1] - 2026-03-08

### Changed

- **Skill doc: polling must use `osascript`, not bare shell commands** — updated
  `docs/youtube-transcribe.skill.md` to make clear that `/tmp/transcript.txt` lives
  on the user's Mac, not inside the Claude container. Step 3 and the "Check if
  complete and read" command pattern now use `osascript -e 'do shell script "..."'`
  for both the word-count poll and the final `cat` read, with a prominent `CRITICAL`
  warning explaining why bare bash commands will silently fail.
- **macOS-only platform support documented** — added a top-of-file callout to
  `docs/youtube-transcribe.skill.md` instructing the agent to stop and inform the
  user if they are not on a Mac. Added a **Platform Support** section to `README.md`
  explicitly stating that the LLM agent integration is macOS-only and that **Windows
  is not supported**. Removed the Ubuntu/Debian `apt install` snippet from README
  requirements (the CLI can still be run manually on Linux, but the agent skill is
  Mac-specific).

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
