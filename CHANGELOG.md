# Changelog

All notable changes to the "YouTube Transcriber" will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
