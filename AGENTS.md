# AGENTS.md — youtube-transcriber

Guidance for contributors and coding agents working in this repository. This is the
canonical instruction file; `CLAUDE.md` points here.

Start with `README.md` for the user-facing picture, then the reference table at the
bottom of this file.

This repo has two consumers, and any change to user-visible behavior affects both:

1. **Someone editing the CLI** in this repo — the audience for the conventions below.
2. **An agent driving the installed CLI over a shell** — Claude Desktop, Claude Code,
   or any tool with local shell access. It sees a black box and depends entirely on the
   stdout/stderr contract and exit codes in *The agent contract* below, plus the shipped
   skill at `skill/youtube-transcribe/SKILL.md`.

---

## What this project is

A **local, offline-first Python CLI** that downloads YouTube audio with `yt-dlp` and
transcribes it with `mlx-whisper` (Apple Silicon) or `faster-whisper` (CPU/CUDA). One URL
in, one transcript out.

### Design philosophy (do not violate without discussion)

- **Always transcribe locally.** No cloud transcription APIs, no transcription API keys.
  Audio and transcripts never leave the machine.
- **Do not scrape YouTube captions.** They are inconsistent and the endpoint is
  unofficial. Whisper always runs locally for quality consistency.
- **stdout = transcript, stderr = everything else.** A hard contract — the whole point is
  that an agent can pipe stdout into another prompt. Every progress, banner, or warning
  line MUST use `click.echo(..., err=True)`.
- **Batch, not interactive.** No prompts, no menus. One video per invocation.
- **Single instance.** A PID lock prevents parallel runs from overwhelming the GPU/CPU.
- **Nothing written to the user's working directory by default.** Audio goes to a
  `tempfile.TemporaryDirectory()`; the transcript goes to stdout unless `--output` is given.
- **Minimal dependencies.** Four runtime packages. Keep the graph small and purposeful.

### What "local" precisely means

Audio and transcripts are never uploaded — verified: nothing in `src/` sends user content
anywhere. But the tool is not hermetic, and the docs must not claim it is. Three outbound
destinations exist:

| Destination | When | Why |
|---|---|---|
| `youtube.com` | every run | yt-dlp downloads the audio stream |
| `huggingface.co` | first use of a model, plus a metadata check on later runs | Whisper weights (`local_files_only` is never set) |
| `github.com` | when YouTube serves a JS challenge | `remote_components = {"ejs:github"}` (`downloader.py`) fetches yt-dlp's challenge solver |

Removing `remote_components` breaks challenge solving on many videos. Do not drop it to
make an offline claim tidier — correct the claim instead.

---

## The agent contract

This is the part an agent driving the CLI depends on. All of it is verified against the
source; keep it in sync when you change `cli.py`.

### Streams

- **stdout** carries exactly the formatted transcript plus a trailing newline — and only
  when `--output` was NOT passed. With `--output`, stdout is empty and the file is written
  with no trailing newline.
- **stderr** carries the banner, both step headers, per-segment progress, warnings, and
  errors.
- `--quiet` / `-q` suppresses *progress* on stderr. It does **not** silence stderr:
  errors, and the MLX `--vad` warning, still print. Prefer `--quiet` over `2>/dev/null`,
  which throws away the diagnosis you need when a run fails.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Runtime failure — ffmpeg missing, run lock held, download failure, model load or transcription failure, `mlx-whisper` not installed, `Ctrl-C`. May be a one-line `Error: ...` **or** a full traceback, so capture stderr |
| `2` | Usage error — bad or non-video URL, unknown model, invalid `--format`/`--device`/`--compute-type`, non-integer `--beam-size`/`--num-threads`, `--output` pointing at a directory, unknown option |

A bare `youtube-transcriber` with no arguments prints help to **stderr** and exits **2**,
not 0. `--help` and `--version` print to stdout and exit 0.

### Reading progress output

Three docs have previously told readers to match on strings the tool never prints. These
are the real ones — quote them exactly, and re-verify against source if you change them:

| String (stderr) | Source | Means |
|---|---|---|
| `  Device: Apple Silicon GPU  [MLX / Metal + Neural Engine]` | `cli.py` | MLX backend selected (two spaces before `[`) |
| `  Device: NVIDIA GPU  [CUDA / faster-whisper]` | `cli.py` | CUDA backend |
| `  Device: CPU  [faster-whisper]` | `cli.py` | CPU backend |
| `[ Step 1/2 ] Downloading audio...` / `[ Step 2/2 ] Transcribing...` | `cli.py` | phase markers |
| `  Transcribing audio segments (Apple Silicon GPU):` | `transcriber.py` | MLX transcription started |
| `  Loading model '<name>' on <CPU\|GPU (CUDA)> (threads: N)...` | `transcriber.py` | faster-whisper only — never printed on the MLX path |
| `  Transcription complete. Language: .. \| Duration: .. \| Segments: N` | both backends | done |

There is **no** `Loading model ... on Apple Silicon GPU (Metal/ANE)` line. `Metal/ANE`
appears only in docstrings.

### Operational rules

- **One run at a time.** A second concurrent invocation exits 1. The lock is
  `tempfile.gettempdir()/youtube-transcriber.lock` — on macOS that is the per-user
  `$TMPDIR`, **not** `/tmp`. Never hardcode the path in docs or scripts; the contention
  error prints the resolved path. To clear a stale lock:
  `rm "${TMPDIR:-/tmp}/youtube-transcriber.lock"`.
- **`--output` auto-injects the video ID** into the filename stem —
  `--output transcript.txt` writes `transcript_dQw4w9WgXcQ.txt`. If the ID is already in
  the stem it is not duplicated. This exists so an agent transcribing several videos in
  one prompt cannot silently overwrite an earlier transcript. The parent directory is
  created if missing; if the write still fails, the transcript is printed to stdout rather
  than lost.
- **An empty output file means 0 segments, not a crash** — almost always `--vad` on
  mixed audio. Exit code was 0.
- **One video per invocation.** Playlist, channel, and search URLs are rejected with exit
  2. A watch URL carrying `&list=...` is accepted and only the single video is downloaded.

---

## Tech stack and conventions

| Layer | Tool | Notes |
|---|---|---|
| Language | Python 3.11+ | `requires-python = ">=3.11"`; `.python-version` pins 3.12 for development; ruff `target-version = "py311"`. Keep all three consistent. |
| Package manager | `uv` | Always `uv sync` / `uv run`. `uv.lock` is committed. |
| CLI | `click` | Two commands: `transcribe`, `models`. |
| Audio download | `yt-dlp` Python API | Needs a JS runtime (Node/Deno/Bun) — see Landmine 2. |
| Transcription (default) | `faster-whisper` (CTranslate2) | CPU + CUDA. |
| Transcription (Apple Silicon) | `mlx-whisper` (Apple MLX) | Metal GPU + Neural Engine. Optional extra: `uv sync --extra mlx`. Selected automatically — see Landmine 3. |
| Tests | `pytest` | `uv run --extra dev pytest`. |
| Lint | `ruff` | Config in `pyproject.toml`; enforced by `.github/workflows/ci.yml`. |
| License | GPL-3.0-or-later | `LICENSE` is verbatim upstream GPL-3.0 — do not edit it. |

### Style

- Type hints on all function signatures, return types included.
- Google-style docstrings on public functions and classes.
- `snake_case` functions/vars, `PascalCase` classes, `ALL_CAPS` module constants,
  `_leading_underscore` for private helpers.
- `pathlib.Path` over `os.path`.
- Context managers for resource cleanup (temp files, model handles, stdout redirect).
- Validate inputs early; raise `click.BadParameter` (exit 2) or `click.ClickException`
  (exit 1) with an actionable hint.
- Default to writing no comments. Only add them for non-obvious "why".

### Ruff rules you must satisfy

`line-length = 100` with `E501` ignored, plus `E`, `W`, `F`, `I` (isort,
`known-first-party = ["youtube_transcriber"]`), `B`, `C4`, `UP`. Import ordering (`I`) is
the most common first failure. Run `uv run --extra dev ruff check src/ tests/` before
committing — CI runs exactly that.

---

## Module layout

```text
src/youtube_transcriber/
├── __init__.py          # __version__ — keep in sync with pyproject.toml
├── cli.py               # click entry point; args, validation, banner, output routing
├── downloader.py        # yt-dlp wrapper; download_audio() contextmanager; JS runtime probe
├── transcriber.py       # MLX + faster-whisper backends; model tables; dataclasses
├── formatters.py        # text/json/srt/vtt; register new formats in FORMAT_FUNCTIONS
├── utils.py             # URL parsing/validation, device detection, ffmpeg check, run lock, time formatting
└── logging_config.py    # rotating file handler enabled by --log / --log-file

skill/youtube-transcribe/   # the Claude skill that ships to end users
├── SKILL.md
└── references/{models-and-quality,troubleshooting}.md
scripts/
├── build-skill.sh              # zips skill/ -> build/youtube-transcribe.skill (release asset)
└── transcribe_local_videos.sh  # batch-transcribe local video files, no network
docs/
├── setup-claude-desktop.md
└── lessons-learned/            # dated post-mortems — historical record, do not rewrite
tests/                          # utils, formatters, cli, downloader, transcriber
```

---

## Backend applicability

`transcribe_audio()` forks on the resolved device. On Apple Silicon, `auto` resolves to
`mps` and returns from `_transcribe_mlx()` **before** most options are read. A new flag
threaded only through the faster-whisper path is silently a no-op on the default Mac path.

| Flag | faster-whisper (cpu/cuda) | mlx-whisper (mps) |
|---|---|---|
| `--model`, `--format`, `--output`, `--quiet`, `--log`, `--log-file`, `--cookies-from-browser` | applies | applies |
| `--compute-type`, `--beam-size`, `--num-threads` | applies | **ignored silently** |
| `--vad` | applies | **ignored, warns on stderr** (deliberately outside the verbose guard so it survives `--quiet` — keep it there) |

`--num-threads 0` means "CTranslate2's default", which faster-whisper documents as 4 — it
does **not** mean all cores. Pass an explicit count
(`--num-threads "$(sysctl -n hw.logicalcpu)"` / `$(nproc)`) for full core usage.

---

## Landmines — read before changing the relevant code

These are bugs that have actually shipped. `docs/lessons-learned/` holds the post-mortem
for the first three.

### 1. VAD filter discards music as non-speech

Silero VAD classifies music and mixed audio as "not speech" and silently throws it away —
0 segments, no error.

- `--vad` MUST default to off. Do not flip this.
- Keep it opt-in, for clean-speech recordings only (talks, podcasts, interviews).
- If a user reports "0 segments returned", ask whether they used `--vad`.

### 2. yt-dlp needs a JS runtime that GUI processes can find

YouTube uses JS challenges. yt-dlp's Python API defaults `js_runtimes` to `{"deno": {}}`,
which is almost never installed. `downloader._find_js_runtime()` exists to fix this.

- **`js_runtimes` must be a Python dict** — `{"node": {"path": "/path/to/node"}}`. The CLI
  string form `"node:/path"` raises `ValueError` inside yt-dlp.
- **PATH-based discovery is not enough on macOS.** GUI apps (Claude Desktop) launch
  without sourcing `~/.zshrc`, so shell-managed runtimes are invisible. The fallback walks
  `/opt/homebrew/bin`, `/usr/local/bin`, Homebrew versioned kegs
  (`/opt/homebrew/opt/node@*/bin/node`), `~/.nvm/versions/node/*/bin/node`, `~/.volta`,
  and `~/.fnm`. Two rules keep it working: selection must be **numeric**
  (`_nvm_version_key`) — a plain name sort ranks `v9.x` above `v22.x` — and the keg glob
  must stay, because `brew install node@22` never creates `/opt/homebrew/bin/node`, so a
  machine with only a versioned formula has no Node on the plain paths at all.
  Verify changes here with PATH stripped, not just from your shell:
  `PATH=/usr/bin:/bin uv run python -c "from youtube_transcriber.downloader import _find_js_runtime; print(_find_js_runtime())"`

Docs everywhere say: **install Node via Homebrew, not nvm.**

### 3. Apple Silicon defaults to MLX, and there is no CPU fallback

`detect_device()` returns `"mps"` on arm64 macOS regardless of whether `mlx_whisper` is
importable. `transcribe_audio()` then routes to `_transcribe_mlx()`, which raises a
`ClickException` if the `mlx` extra is missing.

So on Apple Silicon the `mlx` extra is **required**, not a performance upgrade. A missing
extra is a hard failure, not a slow run, and the banner still reads
`Apple Silicon GPU`. The only way to reach faster-whisper on a Mac is an explicit
`--device cpu`. "CPU pegged / fans loud" on an Apple Silicon Mac therefore means someone
passed `--device cpu` — it is not a symptom of a missing extra.

### 4. The stdout/stderr split is load-bearing

`mlx_whisper.transcribe(verbose=True)` prints `[hh:mm:ss --> hh:mm:ss] text` to
**stdout**. Without `_stdout_to_stderr()` in `transcriber.py` those lines corrupt the
transcript the agent reads. Do not remove that contextmanager, and keep it in the verbose
path if you refactor.

### 5. Output filename auto-injects the video ID

See *The agent contract*. `SKILL.md`'s `/tmp/transcript_<video_id>.txt` pattern depends on
the no-duplication branch. Don't remove the injection.

### 6. `noplaylist` must stay set

Any watch URL opened from inside a playlist carries `&list=...`, and yt-dlp's default is
to download the **whole playlist**. `ydl_opts["noplaylist"] = True` bounds each run to one
video. Removing it makes a single transcribe request download an unbounded number of
videos into the temp directory.

### 7. yt-dlp must stay current, and `noprogress` must stay set

Two separate traps in the same place.

**Staleness.** YouTube changes its extraction surface constantly; yt-dlp ships date-versioned
releases many times a month. A yt-dlp even two months old fails, and fails *opaquely* —
`HTTP Error 403: Forbidden` or `The page needs to be reloaded`, never anything mentioning a
version. Measured: a 5-month-old yt-dlp failed on every video tested; upgrading fixed all of
them with no other change. Keep the `yt-dlp` floor in `pyproject.toml` current, refresh it at
each release (`uv lock --upgrade-package yt-dlp`), and do not "fix" a download failure by
adding cookies before checking the version. `_warn_if_yt_dlp_stale()` surfaces this on stderr
past 60 days.

**`noprogress`.** `quiet: True` alone does **not** suppress yt-dlp's download progress bar,
and yt-dlp writes that bar to **stdout** — the transcript stream. Without
`ydl_opts["noprogress"] = True`, every successful download prepends ~765 bytes of
`[download]  12.3% of 5.01MiB ...` to the transcript an agent reads. This is invisible in any
test that does not perform a real download, so it survived until a live run. Progress belongs
to `_ProgressHook`, which writes to stderr.

### 8. The two model tables must be edited together

`AVAILABLE_MODELS` gates `--model` validation; `MLX_MODEL_REPOS` maps a name to a
HuggingFace repo for Apple Silicon. Adding to the first without the second fails at
runtime on every Mac, not at parse time.

Two models are intentionally in `AVAILABLE_MODELS` but **not** in `MLX_MODEL_REPOS`:
`distil-small.en` and `distil-large-v2`. `mlx-community` publishes no MLX conversion of
either, so on Apple Silicon they raise "has no MLX repo mapping" and point at
`--device cpu`. `tests/test_transcriber.py` pins this — update the test if that changes.
Note the two distil repos that *do* exist carry no `-mlx` suffix, unlike the rest of the
family; verify a new repo name resolves before adding it.

---

## Key patterns

```python
from youtube_transcriber.downloader import download_audio
from youtube_transcriber.transcriber import transcribe_audio

with download_audio("https://youtube.com/watch?v=...") as audio_path:
    # audio_path is a Path to a temp .wav; the temp directory is removed on exit,
    # so do all work with the audio inside this block.
    result = transcribe_audio(audio_path, model_name="turbo", device="auto")
```

The keyword is `model_name`, not `model`. The full signature:

```python
transcribe_audio(
    audio_path,            # Path — any local media file, not just YouTube downloads
    model_name="turbo",
    device="auto",         # "auto" | "mps" | "cuda" | "cpu"
    compute_type="auto",
    beam_size=5,
    num_threads=0,
    vad_filter=False,
    verbose=True,
)
```

`transcribe_audio()` accepts **any local media path**, which is what makes offline
local-file transcription possible — see `scripts/transcribe_local_videos.sh`.

```python
@dataclass
class TranscriptSegment:
    start: float   # seconds
    end: float     # seconds
    text: str

@dataclass
class TranscriptResult:
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = "unknown"
    duration: float = 0.0

    @property
    def text(self) -> str:  # space-joined
        ...
```

`TranscriptResult.text` joins with a **single space**; `formatters.format_text` joins with
a **blank line** (one paragraph per segment). They are not interchangeable — "simplifying"
`format_text` to `return result.text` breaks `tests/test_formatters.py`.

---

## Common commands

```bash
uv sync                          # base deps
uv sync --extra mlx              # + Apple Silicon GPU backend (required on Apple Silicon)
uv sync --extra dev              # + pytest, ruff

uv run youtube-transcriber --help
uv run youtube-transcriber transcribe "<url>"
uv run youtube-transcriber models

uv run --extra dev pytest                        # tests
uv run --extra dev ruff check src/ tests/        # lint

uv run youtube-transcriber transcribe "<url>" --log
tail -f ~/.local/share/youtube-transcriber/debug.log
```

Use the `--extra dev` form. Bare `uv run pytest` fails on a cold checkout
(`Failed to spawn: pytest`) because uv's implicit sync does not install extras.

---

## Testing and the verification boundary

`uv run --extra dev pytest` green does **not** mean the tool works end to end. Know what
is and is not covered before claiming verification:

- **Covered, no network or model needed:** URL parsing and validation, timestamp/duration
  formatting, all four formatters and the format registry, the run-lock helpers, device
  detection, the CLI exit-code contract, `--output` video-ID injection, the stdout/stderr
  split, `_find_js_runtime`'s return shape and probe order, and the model-table invariant.
- **Not covered, and not coverable in CI:** the actual yt-dlp download and the actual
  Whisper decode. Both need network, `ffmpeg` on PATH, a JS runtime, and (on Apple
  Silicon) the `mlx` extra plus a model download.

So: **never claim an end-to-end verification you did not run.** Manual verification is a
short real video with `--log`, e.g.
`uv run youtube-transcriber transcribe "<short url>" --model tiny --log`, then check
`Segments:` is non-zero in the completion line.

Add tests for pure logic even in the "manual" modules — `_find_js_runtime`, the model
tables, the stdout redirect, and the filename-injection rule are all pure and all guard
documented landmines.

---

## Adding things

**New output format** — add `format_<name>(result: TranscriptResult) -> str` to
`formatters.py`, register it in the `FORMAT_FUNCTIONS` dict at the bottom of that file,
and add a test class to `tests/test_formatters.py`. **Nothing in `cli.py` changes**: the
`--format` `click.Choice` and the dispatch are both derived from `FORMAT_FUNCTIONS`.

**New Whisper model** — add to `AVAILABLE_MODELS` *and* `MLX_MODEL_REPOS` (see Landmine
7), confirm the HuggingFace repo actually resolves, then update the README model table and
`skill/youtube-transcribe/references/models-and-quality.md`.

**New CLI flag** — add a `@click.option` on `cli.transcribe`, thread it through to
`transcribe_audio()`, and decide which backends it applies to (see *Backend
applicability*) — a flag wired only into the faster-whisper branch is a silent no-op on
Apple Silicon, the default Mac path. If it is ignored on a backend, say so in the help
text and warn on stderr like `--vad` does. Then update the README flag table and, if an
agent benefits from controlling it, `skill/youtube-transcribe/SKILL.md`'s Quick Command
Reference and `references/troubleshooting.md`.

**Anything under `skill/youtube-transcribe/`** — the distributable is a build artifact.
Re-run `./scripts/build-skill.sh` and attach the result to the release, or your edit never
reaches a user.

---

## Release process

Keep a Changelog + SemVer. Record changes in `## [Unreleased]` as they land, so nothing
has to be reconstructed at release time.

1. Move `## [Unreleased]` content into `## [X.Y.Z] - YYYY-MM-DD` with the standard
   categories (`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`).
2. Bump the version in **both** places — they drift otherwise, and the banner an agent
   reads comes from the first while installers read the second:
   - `src/youtube_transcriber/__init__.py` — `__version__ = "X.Y.Z"`
   - `pyproject.toml` — `version = "X.Y.Z"`
3. `uv run --extra dev pytest` and `uv run --extra dev ruff check src/ tests/` — both must
   pass. Run `uv lock --check`; if it fails, relock and commit the result.

   > **Relock with `UV_NO_CONFIG=1 uv lock --no-config`.** A machine-local
   > `~/.config/uv/uv.toml` that sets a custom index (a corporate mirror or proxy
   > registry) rewrites the `source = { registry = ... }` line of every package in
   > `uv.lock`. That leaks the private registry URL into this public repo and produces a
   > ~200-line diff of pure noise. Suppressing the local config keeps the lock on
   > `https://pypi.org/simple`. Always check `git diff uv.lock` before committing: the
   > diff should touch only what you actually changed.
4. `./scripts/build-skill.sh` — rebuilds `build/youtube-transcribe.skill`.
5. Commit: `chore: release vX.Y.Z`. Tag it.
6. **Attach `build/youtube-transcribe.skill` to the GitHub Release.** The README's primary
   skill-install path points at `/releases/latest`, so a release without this asset breaks
   that path for everyone the moment it is published.

Never correct a historical CHANGELOG entry by rewriting it. Add a `Fixed` note in the
current release that corrects the record.

Ordinary commits use conventional prefixes (`feat:`, `fix:`, `chore:`, `docs:`,
`refactor:`).

---

## Platform notes

- **macOS is the primary target.** Apple Silicon uses MLX (extra required); Intel Macs run
  on CPU.
- **Linux works for the CLI.** The Claude Desktop skill uses `osascript` and is macOS-only.
- **Windows is unsupported.** Don't add Windows paths to `_find_js_runtime` unless asked.
- macOS GUI apps launch with a stripped PATH — anything needed at runtime must be found by
  absolute path or a `_find_js_runtime`-style fallback.

---

## What NOT to do

- Don't add cloud transcription to the core workflow.
- Don't scrape YouTube captions or add `youtube-transcript-api`.
- Don't print transcript text to stderr or progress text to stdout.
- Don't write audio or transcripts to the user's working directory by default.
- Don't hardcode model paths. faster-whisper resolves by name from the HuggingFace cache;
  mlx-whisper resolves via `MLX_MODEL_REPOS` and `_HF_CACHE_ROOT` (which honors `HF_HOME` /
  `HF_HUB_CACHE`).
- Don't hardcode the run-lock path in docs or scripts — it is `$TMPDIR` on macOS.
- Don't quote a progress string in docs without grepping `src/` to confirm it exists.
- Don't edit `LICENSE`. It is the verbatim GPL-3.0 text.
- Don't rewrite `docs/lessons-learned/` — dated post-mortems are historical record.

---

## Cross-references

| File | Purpose |
|---|---|
| `README.md` | User-facing install, usage, full flag reference, agent contract |
| `CLAUDE.md` | Pointer to this file |
| `CHANGELOG.md` | Version history (Keep a Changelog) |
| `docs/setup-claude-desktop.md` | End-user setup for Claude Desktop and Claude Code |
| `docs/lessons-learned/2026-03-02-vad-and-nodejs-fixes.md` | VAD + JS-runtime post-mortem |
| `skill/youtube-transcribe/SKILL.md` | The skill Claude loads — osascript-driven macOS flow |
| `skill/youtube-transcribe/references/models-and-quality.md` | Model choice, transcript-quality interpretation, VAD decisions |
| `skill/youtube-transcribe/references/troubleshooting.md` | Agent-facing error recovery |
| `scripts/build-skill.sh` | Builds the `.skill` release asset |
| `scripts/transcribe_local_videos.sh` | Batch-transcribe local video files, fully offline |
| `.github/workflows/ci.yml` | The CI gate: `uv lock --check`, ruff, pytest on 3.11–3.13 |
