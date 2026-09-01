# YouTube Transcriber

[![CI](https://github.com/overtonlabs/youtube-transcriber/actions/workflows/ci.yml/badge.svg)](https://github.com/overtonlabs/youtube-transcriber/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

A local CLI that downloads audio from a YouTube video and transcribes it with Whisper on
your own machine — Apple Silicon GPU via [MLX](https://github.com/ml-explore/mlx), or
CPU/CUDA via [faster-whisper](https://github.com/SYSTRAN/faster-whisper). No cloud
transcription, no API keys. The transcript goes to stdout, ready to pipe into any LLM.

Built to be driven by an AI agent over a shell. If you are an agent, read
**[the agent contract](#the-agent-contract)** — it specifies the stream split and exit
codes. If you are editing this repo, read **[AGENTS.md](AGENTS.md)**.

> **Why not just pull YouTube's auto-captions?** They are often inaccurate, missing
> entirely for many videos, and rely on an undocumented API that breaks without notice.
> Local Whisper gives consistent, high-quality results on *every* video.

---

## Quick start

```bash
# macOS (Apple Silicon) — the mlx extra is required, not optional
brew install ffmpeg node
uv tool install "git+https://github.com/overtonlabs/youtube-transcriber.git[mlx]"

# Transcribe to stdout
youtube-transcriber transcribe "https://youtu.be/H14bBuluwB8"

# Or straight to a file (the video ID is added to the filename automatically)
youtube-transcriber transcribe "<url>" --output transcript.txt
```

First run of a model downloads its weights from HuggingFace (~1.6 GB for the default
`turbo`) and caches them in `~/.cache/huggingface/hub/`. Later runs load instantly.

---

## Features

- **Local transcription** — audio and transcripts never leave your machine
- **No transcription API keys** — Whisper runs on-device
- **Device auto-detection** — Apple Silicon GPU via MLX (Metal + Neural Engine), else CUDA
  if available, else CPU
- **16 Whisper models** — `tiny` through `large-v3`, plus `turbo` (default) and the
  distilled family
- **Four output formats** — plain text, JSON with timestamps, SRT, WebVTT
- **Agent-friendly** — clean transcript on stdout, everything else on stderr, documented
  exit codes, single-instance lock
- **Ships a Claude skill** — paste a YouTube URL into Claude and it transcribes on your Mac
- **Also does local files** — `scripts/transcribe_local_videos.sh` batch-transcribes video
  files with no network at all
- **Minimal dependencies** — four runtime packages

> `--vad` is off by default and should usually stay off. It silently discards anything it
> classifies as non-speech, including music. See
> [VAD pre-filtering](#vad-pre-filtering--speech-only-content).

---

## What "local" means precisely

**No audio and no transcript is ever uploaded anywhere.** The tool does still reach the
network in three places, and it is worth being exact about them:

| Destination | When | Why |
|---|---|---|
| `youtube.com` | every run | yt-dlp downloads the audio stream |
| `huggingface.co` | first use of a model, plus a metadata check on later runs | Whisper model weights |
| `github.com` | when YouTube serves a JS challenge | fetches yt-dlp's challenge-solver component |

---

## Platform support

- **macOS** — primary target. Apple Silicon requires the `mlx` extra (see
  [Installation](#installation)); Intel Macs run on CPU.
- **Linux** — fully supported for the CLI. Good for servers and automated pipelines. The
  Claude skill is macOS-only because it drives Terminal via `osascript`.
- **Windows** — not tested or supported.

---

## Requirements

- **Python 3.11+**
- **[ffmpeg](https://ffmpeg.org/download.html)** — yt-dlp uses it to extract audio
- **[uv](https://docs.astral.sh/uv/)** — recommended for installing and running
- **[Node.js](https://nodejs.org/)** — yt-dlp needs a JS runtime to solve YouTube's
  challenges and reliably enumerate audio formats

```bash
brew install ffmpeg node              # macOS
sudo apt install ffmpeg nodejs        # Ubuntu/Debian
```

> **macOS: install Node via Homebrew, not nvm.** GUI apps (including Claude Desktop) launch
> without a full shell environment, so nvm-managed runtimes are often invisible to them.
> Homebrew puts node at a fixed system path (`/opt/homebrew/bin/node`) that always resolves.

---

## Installation

### As a standalone tool with uv (recommended)

```bash
# Apple Silicon — include the mlx extra
uv tool install "git+https://github.com/overtonlabs/youtube-transcriber.git[mlx]"

# Intel Mac / Linux / CUDA
uv tool install git+https://github.com/overtonlabs/youtube-transcriber.git

youtube-transcriber --help
```

Upgrade later with `uv tool upgrade youtube-transcriber`.

> **Apple Silicon: the `mlx` extra is required, not a performance upgrade.** On an M-series
> Mac the tool selects the MLX backend automatically and there is **no CPU fallback** — if
> `mlx-whisper` is missing the run fails with a clear error. (You can force the CPU backend
> explicitly with `--device cpu`, which is slower but works without the extra.)

### From a local clone (for development)

```bash
git clone https://github.com/overtonlabs/youtube-transcriber.git
cd youtube-transcriber

uv sync                  # base dependencies (Python 3.12 is pinned via .python-version)
uv sync --extra mlx      # + Apple Silicon GPU backend
uv sync --extra dev      # + pytest, ruff

uv run youtube-transcriber --help
```

### Using pip

```bash
pip install "git+https://github.com/overtonlabs/youtube-transcriber.git#egg=youtube-transcriber[mlx]"
```

---

## Usage

```bash
youtube-transcriber transcribe "<url>" [OPTIONS]
youtube-transcriber models
youtube-transcriber --version
```

Accepted URL forms: `youtube.com/watch?v=...`, `youtu.be/...`, `youtube.com/shorts/...`,
`/embed/...`, `/live/...`, and `music.youtube.com`. One video per invocation — playlist,
channel, and search URLs are rejected. A watch URL carrying `&list=...` is fine; only that
one video is downloaded.

### Full flag reference

| Flag | Default | Notes |
|---|---|---|
| `--model`, `-m` | `turbo` | Any of the 16 models; run `youtube-transcriber models` for the list |
| `--format`, `-f` | `text` | `text`, `json`, `srt`, `vtt` |
| `--output`, `-o` | — | Write to a file instead of stdout. The video ID is injected into the filename |
| `--device`, `-d` | `auto` | `auto`, `mps`, `cuda`, `cpu`. `auto` → MLX on Apple Silicon, else CUDA, else CPU |
| `--compute-type` | `auto` | `float16`, `int8_float16`, `int8`, `float32`. Ignored on MLX |
| `--beam-size` | `5` | Higher is more accurate and slower. Ignored on MLX (greedy decoding) |
| `--num-threads` | `0` | CPU threads for faster-whisper. `0` = CTranslate2's default (4), **not** all cores. Ignored on MLX |
| `--vad` | off | Silero VAD pre-filter. Speech-only content only — see below |
| `--quiet`, `-q` | off | Suppress progress on stderr. Errors still print |
| `--cookies-from-browser` | — | Browser name (`chrome`, `firefox`, `safari`, `edge`, `brave`) for age-gated or rate-limited videos |
| `--log` | off | Debug log to `~/.local/share/youtube-transcriber/debug.log` |
| `--log-file` | — | Debug log to a specific path |
| `--help` / `--version` | — | Print to stdout, exit 0 |

### Output formats

```bash
youtube-transcriber transcribe "<url>" --format text   # default: one paragraph per segment
youtube-transcriber transcribe "<url>" --format json   # segments with start/end timestamps
youtube-transcriber transcribe "<url>" --format srt    # SubRip subtitles
youtube-transcriber transcribe "<url>" --format vtt    # WebVTT subtitles
```

### Saving to a file

```bash
youtube-transcriber transcribe "<url>" --output transcript.txt
youtube-transcriber transcribe "<url>" --format srt --output subtitles.srt
```

The 11-character video ID is inserted into the filename stem automatically —
`--output transcript.txt` writes `transcript_dQw4w9WgXcQ.txt`. That way transcribing
several videos in one session never silently overwrites an earlier result. If the ID is
already in the name it is not duplicated.

### VAD pre-filtering — speech-only content

`--vad` runs Silero Voice Activity Detection before Whisper and **discards everything it
classifies as non-speech**. On a music video that means the entire track: 0 segments, no
error message. It is off by default; leave it off unless the audio is clean speech
throughout.

| Content type | Use `--vad`? |
|---|---|
| Music video | Never — the whole track is discarded |
| Video with intro music or background audio | No |
| Lecture, talk, podcast (voice only) | Yes — removes silence, speeds up transcription |
| Interview in a quiet room | Generally safe |

`--vad` is ignored by the MLX backend, which warns on stderr. If you get 0 segments, re-run
with `--log` and look for `VAD filter removed Xm Xs of audio`.

### Debug logging

```bash
youtube-transcriber transcribe "<url>" --log                     # default path
youtube-transcriber transcribe "<url>" --log-file /tmp/yt.log    # custom path
```

---

## The agent contract

Everything an agent driving this CLI needs. All of it is verified against the source.

**Streams.** stdout carries exactly the formatted transcript plus a trailing newline, and
only when `--output` was *not* passed — with `--output`, stdout is empty. stderr carries the
banner, progress, warnings, and errors. Prefer `--quiet` over `2>/dev/null`: it drops the
progress noise but keeps the error message you need when something fails.

**Exit codes.**

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Runtime failure — ffmpeg missing, run lock held, download failure, model load or transcription failure, `mlx-whisper` not installed, `Ctrl-C`. May be a one-line `Error: ...` or a full traceback, so capture stderr |
| `2` | Usage error — bad or non-video URL, unknown model, invalid option value, `--output` pointing at a directory |

A bare `youtube-transcriber` with no arguments prints help to **stderr** and exits **2**.

**Single instance.** A PID lock allows only one transcription at a time; a second exits 1.
The lock lives at `$TMPDIR/youtube-transcriber.lock` on macOS and
`/tmp/youtube-transcriber.lock` on Linux — the error message prints the resolved path, so
use that rather than assuming. To clear a stale lock:
`rm "${TMPDIR:-/tmp}/youtube-transcriber.lock"`.

**An empty transcript with exit 0 means 0 segments**, not a crash — almost always `--vad`
on mixed audio.

**Timing.** Expect roughly real-time on CPU and far faster than real-time on Apple Silicon;
a long video can still take minutes. Poll with a bound, and remember the output file is
written once, at the very end of a successful run.

---

## Using it with Claude

The recommended path is the bundled skill: once installed, paste a YouTube URL and ask.

```text
Transcribe this YouTube video and give me a 5-bullet summary:
https://www.youtube.com/watch?v=...
```

Without the skill, Claude Code can drive the CLI directly, since it has shell access on the
same machine:

```bash
youtube-transcriber transcribe "<url>" --quiet
```

Claude Desktop cannot reach YouTube from its own sandbox, which is exactly the gap the
skill fills — it runs the command on your Mac via `osascript` and reads the result back.

### Install the Claude skill

The skill source lives at [`skill/youtube-transcribe/`](skill/youtube-transcribe/).

**Claude Desktop / Claude.ai** — download `youtube-transcribe.skill` from the
[latest release](https://github.com/overtonlabs/youtube-transcriber/releases/latest), then
**Settings → Skills → Import skill**.

**Claude Code (user-level)**

```bash
mkdir -p ~/.claude/skills
cp -r skill/youtube-transcribe ~/.claude/skills/
```

**Project-scoped**

```bash
mkdir -p .claude/skills
cp -r /path/to/youtube-transcriber/skill/youtube-transcribe .claude/skills/
```

> The skill requires macOS (it drives Terminal via `osascript`) and needs the CLI already
> installed and on `PATH`.

Step-by-step setup and troubleshooting: [`docs/setup-claude-desktop.md`](docs/setup-claude-desktop.md).

---

## Transcribing local video files

`transcribe_audio()` accepts any local media path, so the same Whisper backend works
entirely offline on files you already have:

```bash
bash scripts/transcribe_local_videos.sh ~/Downloads/recordings
```

Transcribes every `.mp4`, `.webm`, `.mkv`, `.mov`, and `.m4v` one level deep, writing
`<name>_transcript.txt` beside each video and skipping files that already have one, so it
is safe to re-run after an interruption. Requires a clone of this repo.

It uses the same auto-detected backend as the CLI, so on Apple Silicon the `mlx` extra is
required. It also calls `transcribe_audio()` directly rather than going through the CLI, so
it does not take the single-instance lock — don't run it alongside a
`youtube-transcriber transcribe` invocation.

---

## Whisper models

`turbo` is the default and the right choice for almost everything. Switch to `large-v3`
only when turbo's quality is not good enough on a specific video.

Sizes below are the Apple Silicon (MLX) download, which is what the default path pulls. The
CPU/CUDA path downloads CTranslate2 weights instead, which are smaller at `int8`.

| Model | Parameters | Speed | Download | Notes |
|---|---|---|---|---|
| `tiny` | 39M | Fastest | ~75 MB | Pipeline testing |
| `base` | 74M | Very fast | ~150 MB | |
| `small` | 244M | Fast | ~0.5 GB | Reasonable for short clips |
| `medium` | 769M | Moderate | ~1.5 GB | |
| `turbo` | 809M | Fast | ~1.6 GB | **Default** — pruned large-v3, ~8× faster, minimal quality loss |
| `distil-large-v3` | 756M | Fast | ~1.5 GB | Near large-v3 accuracy, English-only |
| `large-v3` | 1550M | Slow | ~3 GB | Best quality |

`youtube-transcriber models` prints all 16, including `large-v1`/`large-v2`, the `.en`
English-only variants of `tiny`/`base`/`small`/`medium`, and the distilled family — that
list is generated from the source, so it is always accurate.

> `distil-small.en` and `distil-large-v2` have no MLX build published, so on Apple Silicon
> they need `--device cpu`. The tool says so if you try.

---

## Architecture

```text
YouTube URL
    │
    ▼
youtube-transcriber CLI (click)  ── cli.py: validation, banner, output routing
    │
    ├── utils.py          ── URL parsing, device detection, ffmpeg check, run lock
    ├── downloader.py     ── yt-dlp → best audio → temp .wav (JS runtime discovery)
    ├── transcriber.py    ── mlx-whisper (Apple Silicon) or faster-whisper (CPU/CUDA)
    ├── formatters.py     ── text / json / srt / vtt
    └── logging_config.py ── rotating debug log (--log)
    │
    ▼
stdout (transcript)  +  stderr (progress, warnings, errors)
```

| Package | Purpose |
|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | YouTube audio download |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Local speech-to-text on CPU/CUDA (CTranslate2) |
| [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) | Apple Silicon GPU speech-to-text (`mlx` extra) |
| [click](https://click.palletsprojects.com/) | CLI framework |
| [secretstorage](https://github.com/mitya57/secretstorage) | Linux-only; backs yt-dlp's keyring cookie access |

---

## Troubleshooting

### Transcript is empty / 0 segments

Almost always the VAD filter on content with background audio. Re-run with `--log`; if the
log shows `VAD filter removed Xm Xs of audio`, that is the cause. Do not use `--vad` for
music videos or mixed audio.

### `mlx-whisper is not installed`

You are on Apple Silicon without the `mlx` extra. There is no CPU fallback on this path.

```bash
uv tool install "git+https://github.com/overtonlabs/youtube-transcriber.git[mlx]" --force
# or, from a clone:  uv sync --extra mlx
```

Confirm it is active by looking for this exact banner line on stderr:

```text
  Device: Apple Silicon GPU  [MLX / Metal + Neural Engine]
```

### `No supported JavaScript runtime could be found`

Node.js is missing or not on the PATH of the process running the tool. Install it via
Homebrew (`brew install node`) or apt (`sudo apt install nodejs`). Avoid nvm, volta, and
fnm for non-interactive contexts such as Claude Desktop — they only inject PATH in
interactive shells.

### Two things to keep updated — they are separate

This trips people up, so it is worth stating plainly. The skill and the CLI are different
artifacts with different update paths:

| Artifact | What it is | Contains yt-dlp? | Update with |
|---|---|---|---|
| The **skill** | three Markdown files Claude reads | **No** | re-import the `.skill`, or re-copy `skill/youtube-transcribe/` |
| The **CLI** | the Python package that does the work | **Yes** | `uv tool upgrade youtube-transcriber` |

**Re-installing the skill does not update yt-dlp**, so it will not fix a download failure.
It only updates the instructions Claude follows. Downloads are fixed by upgrading the CLI.

### Any download failure — start here

**Update yt-dlp first. It is almost always this.** YouTube changes its extraction surface
constantly and yt-dlp ships fixes within days, so a version even a couple of months old
fails — and it fails *opaquely*, as `HTTP Error 403: Forbidden` or
`The page needs to be reloaded`, never as anything that mentions a version.

```bash
uv tool upgrade youtube-transcriber        # if installed with uv tool
uv sync --upgrade-package yt-dlp           # from a clone
```

The tool warns on stderr when its yt-dlp is more than 60 days old, and prints the version
in every download-failure message.

### `Sign in to confirm you're not a bot` / `HTTP Error 403`

If yt-dlp is current and it still fails, YouTube is rate-limiting or gating the video. Pass
your logged-in browser's cookies:

```bash
youtube-transcriber transcribe "<url>" --cookies-from-browser chrome
```

Any browser yt-dlp supports works — `chrome`, `firefox`, `safari`, `edge`, `brave`. The
browser's cookie store must be readable; on macOS this may prompt for Keychain access the
first time. There is no `--cookies FILE` flag.

> Reach for cookies **second**, not first. They hand yt-dlp your logged-in session, so
> there is no reason to expose them for a failure a version bump fixes.

### `Another youtube-transcriber process is already running`

Only one transcription runs at a time. Wait for it, or clear a stale lock left by a crashed
run — the error message prints the exact path:

```bash
rm "${TMPDIR:-/tmp}/youtube-transcriber.lock"
```

### Transcription is slow

Install the `mlx` extra on Apple Silicon. Otherwise: the first run of a model downloads it;
try a smaller model; on CPU pass `--num-threads "$(sysctl -n hw.logicalcpu)"` (macOS) or
`--num-threads "$(nproc)"` (Linux), since the default is 4 threads, not all cores.

---

## Documentation

| Doc | Description |
|---|---|
| [AGENTS.md](AGENTS.md) | Canonical guidance for contributors and coding agents |
| [skill/youtube-transcribe/](skill/youtube-transcribe/) | The Claude skill source (SKILL.md + references) |
| [docs/setup-claude-desktop.md](docs/setup-claude-desktop.md) | Step-by-step setup for Claude Desktop and Claude Code |
| [docs/lessons-learned/2026-03-02-vad-and-nodejs-fixes.md](docs/lessons-learned/2026-03-02-vad-and-nodejs-fixes.md) | VAD silence bug and Node.js runtime discovery |
| [CHANGELOG.md](CHANGELOG.md) | Release history (Keep a Changelog) |

---

## Roadmap

- [ ] Speaker diarization
- [ ] Post-processing with local LLMs via Ollama
- [ ] MCP server mode for richer agent integration

Cloud transcription backends are explicitly out of scope — local-only is the point of the
tool.

---

## Contributing

Pull requests welcome. For major changes, open an issue first. Read
[AGENTS.md](AGENTS.md) before changing user-visible behavior — it documents the landmines.

```bash
uv sync --extra dev
uv run --extra dev pytest
uv run --extra dev ruff check src/ tests/
```

CI runs exactly those two commands plus `uv lock --check` on Python 3.11, 3.12, and 3.13.

---

## License

YouTube Transcriber — Copyright (C) 2026 Overton Labs, LLC

Licensed under the GNU General Public License v3.0 or later. See [LICENSE](LICENSE) for the
full text.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
