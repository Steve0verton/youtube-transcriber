# Changelog

All notable changes to the "YouTube Transcriber" will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-09-01

Everything here came from running the tool against a real video for the first time in a
while. The 0.3.0 audit below reconciled every documented claim against the source, but it
could not perform a live download — and two of the most consequential defects in the project
turned out to be observable only once one succeeded.

### Fixed

- **yt-dlp's download progress bar was corrupting the transcript on stdout.** `quiet: True`
  does not suppress yt-dlp's progress display, and yt-dlp writes it to **stdout** — the
  stream that carries the transcript. Every successful download prepended ~765 bytes of
  `[download]  12.3% of 5.01MiB at ...` to the transcript, breaking the tool's core
  contract for exactly the audience it exists to serve. Fixed with
  `ydl_opts["noprogress"] = True`. This was invisible to every test and to the whole doc
  audit, because it only manifests on a download that actually succeeds.
- **Homebrew versioned Node formulas were invisible to the JS-runtime fallback.** A
  versioned keg (`brew install node@22`) installs to `/opt/homebrew/opt/node@22/bin/node`
  and is symlinked into `/opt/homebrew/bin` only when it is the linked formula — so a
  machine whose only Node is a versioned keg has no `/opt/homebrew/bin/node` at all. With
  PATH stripped, as it is for a process launched by a macOS GUI app, `_find_js_runtime()`
  returned `None` on such a machine and yt-dlp lost JS-challenge solving entirely — the
  exact Claude Desktop failure the fallback exists to prevent. `_homebrew_keg_paths()` now
  globs `/opt/homebrew/opt/<rt>@*/bin/<rt>` and the `/usr/local` equivalent, newest version
  first. Reproduced and verified on a machine with only `node@22` installed.
- **`scripts/transcribe_local_videos.sh` aborted the whole batch on the first bad file.**
  `set -euo pipefail` meant one failing video ended the run, so the closing summary never
  printed — which defeats the purpose of a batch tool whose design is "skip what's already
  done and re-run". Each file's failure is now reported and the batch continues; the
  summary counts failures and the script exits 1 if any occurred.
- **`youtube-transcriber models` labelled the default model twice** — the header already
  reads `(default: turbo)` and the turbo row's note already opens with `DEFAULT —`, so the
  appended ` (default)` marker was redundant.

### Changed

- **yt-dlp is no longer effectively pinned, and staleness is now surfaced.** The floor was `>=2024.1.1` while the lock held `2026.3.17` — 96 releases and
  five months behind current. YouTube changes constantly and yt-dlp ships fixes within
  days, so that version failed on every video tested, always opaquely: `HTTP Error 403:
  Forbidden` or `The page needs to be reloaded`, never anything naming a version. Upgrading
  yt-dlp alone fixed every case, with no cookies and no other change. The floor is now
  `>=2026.8.19`, the lock is refreshed, `_warn_if_yt_dlp_stale()` warns on stderr past 60
  days, and every download-failure message names the running version and puts "update
  yt-dlp" as step 1. Troubleshooting across the README and the skill was reordered to match:
  update yt-dlp first, reach for `--cookies-from-browser` only after — cookies hand yt-dlp a
  logged-in session and should not be spent on a failure a version bump fixes.
- **Primary example video changed to a speech-only talk**
  ([`H14bBuluwB8`](https://youtu.be/H14bBuluwB8)) in the three places a reader is told to
  actually run a command — the README quick start and both test steps of the setup guide. A
  music video is the worst possible first test: it is the one content type `--vad` destroys,
  and it is among the most heavily rate-limited on YouTube. The original video is kept where
  it earns its place — the CLI's own `--help` examples, the URL-parsing tables, and as the
  `--vad` counter-example.
- **Documented that the skill and the CLI update separately.** The skill is three Markdown
  files and contains no yt-dlp; re-importing it cannot fix a download failure, which is the
  most likely wrong turn a user takes when one occurs. The README carries a comparison table
  and the skill's troubleshooting opens by ruling the reinstall out.
- **`AGENTS.md` gained a relock warning.** A machine-local `~/.config/uv/uv.toml` pointing at
  a private index rewrites the `source = { registry = ... }` line of every package in
  `uv.lock`, which would leak an internal registry URL into this public repository and
  produce a ~200-line diff of pure noise. The release process now specifies
  `UV_NO_CONFIG=1 uv lock --no-config`, and says to inspect `git diff uv.lock` before
  committing.
- **New landmine documented** in `AGENTS.md` covering both yt-dlp traps: keeping the release
  current, and keeping `noprogress` set so the progress bar never reaches stdout.

## [0.3.0] - 2026-09-01

> Not published as a standalone release — these changes shipped to users as part of 0.4.0,
> which followed the same day. Kept as its own section because it is a distinct body of
> work: a full reconciliation of the documentation against the source.

Repository moved to [github.com/overtonlabs/youtube-transcriber](https://github.com/overtonlabs/youtube-transcriber).
GitHub redirects the old URLs, but all in-repo references were updated.

This release is the result of a full audit of every documented claim against the source.
Several docs described behavior the code never had; a handful of real bugs were found in
the process. Corrections to earlier CHANGELOG entries are recorded here rather than by
rewriting those entries.

### Added

- **`AGENTS.md`** — the canonical instruction file for contributors and coding agents,
  replacing `.github/copilot-instructions.md`. It is read natively by Copilot, Codex,
  Cursor, Gemini CLI, and others; `CLAUDE.md` is now a pointer to it. It documents the
  stdout/stderr and exit-code contract, a backend-applicability table, the exact progress
  strings the tool prints, eight landmines, and the verification boundary (what
  `pytest` green does and does not prove).
- **The agent contract is now documented** — stdout/stderr split, exit codes (`0` success,
  `1` runtime failure, `2` usage error, including that a bare invocation exits 2), the
  single-instance lock and its real path, and the "empty transcript with exit 0 means 0
  segments" case. Previously discoverable only by running the tool. Now in `README.md`,
  `AGENTS.md`, and `skill/youtube-transcribe/SKILL.md`.
- **`.github/workflows/ci.yml`** — runs `uv lock --check`, ruff, and pytest on Python 3.11,
  3.12, and 3.13. The project previously claimed ruff was "enforced in CI" with no CI.
- **`scripts/transcribe_local_videos.sh` is documented** — it landed in the previous commit
  and appeared in no doc. Batch-transcribes every `.mp4`/`.webm`/`.mkv`/`.mov`/`.m4v` one
  level deep in a directory, writing `<name>_transcript.txt` beside each video, skipping
  files already transcribed so it is safely re-runnable. Fully offline.
- **`music.youtube.com` is now an accepted host.** YouTube Music share links previously
  failed URL validation with exit 2 even though the video ID parsed fine.
- **Tests for the CLI contract and the landmines** — `tests/test_cli.py` (exit codes,
  `--output` video-ID injection, stdout/stderr separation), `tests/test_downloader.py`
  (`_find_js_runtime` return shape, probe order, nvm version selection), and
  `tests/test_transcriber.py` (model-table invariants, the stdout redirect), plus run-lock
  and device-detection tests in `tests/test_utils.py`. `cli.py`, `downloader.py`, and
  `transcriber.py` previously had zero coverage.

### Fixed

- **Playlist URLs no longer download the entire playlist.** `noplaylist` was never set, and
  yt-dlp's default is to fetch the whole playlist when a URL is ambiguous. Any
  `watch?v=X&list=PL...` URL — the shape you get from opening a video inside a playlist —
  downloaded every video in that playlist to the temp directory and then transcribed an
  arbitrary one. `ydl_opts["noplaylist"] = True` bounds each run to one video.
- **Playlist, channel, and search URLs are now rejected with a clear message** (exit 2)
  instead of being passed to yt-dlp with no video ID.
- **Four Whisper models were unusable on Apple Silicon.** Every `distil-*` entry in
  `MLX_MODEL_REPOS` named a HuggingFace repo that does not exist — the real repos carry no
  `-mlx` suffix, unlike the rest of the family. `distil-medium.en` and `distil-large-v3`
  now point at the correct repos. `distil-small.en` and `distil-large-v2` have no MLX build
  published at all, so they are removed from the MLX map and now raise the existing
  "no MLX repo mapping" error pointing at `--device cpu`, instead of failing with an opaque
  404 from inside `mlx_whisper`. The skill was actively recommending `distil-large-v3`.
- **`--output` no longer discards a completed transcript** when the parent directory does
  not exist. The write happened after the download and full transcription, so a missing
  directory raised an unhandled `FileNotFoundError` and the entire run was lost. The
  directory is now created, and if the write still fails the transcript is printed to
  stdout rather than thrown away.
- **The nvm fallback selected the oldest installed Node, not the newest.** Version
  directories were sorted as strings, so `v9.11.2` ranked above `v22.9.0`. Sorting is now
  numeric via `_nvm_version_key`. yt-dlp handed an ancient Node fails YouTube's JS
  challenges — the exact failure the fallback exists to prevent.
- **`scripts/transcribe_local_videos.sh` failed on a relative directory argument.** `find`
  ran in the caller's working directory while the loop `cd`-ed to the repo root before
  invoking Python, so paths stopped resolving after the first file. The argument is now
  resolved to an absolute path once, and the `cd` is hoisted out of the loop.
- **Documented GPU-verification string did not exist.** `docs/setup-claude-desktop.md` told
  users three times to confirm Metal acceleration by looking for
  `Loading model '<name>' on Apple Silicon GPU (Metal/ANE)...`. That string is printed
  nowhere — `Metal/ANE` appears only in docstrings, and the MLX path emits no "Loading
  model" line at all. The verification step therefore failed 100% of the time on a working
  install. Replaced with the strings the tool actually prints.
- **Documented CPU fallback on Apple Silicon does not exist.** Several docs described a
  graceful fall back to faster-whisper when the `mlx` extra is missing. `detect_device()`
  returns `"mps"` regardless, so a missing extra is a hard failure with a clear error, not
  a slow run. Consequently "CPU pegged / fans loud" on an Apple Silicon Mac means
  `--device cpu` was passed — it is not a symptom of a missing extra. Corrected across the
  README, the setup guide, and both skill reference files.
- **README claimed `--cookies-from-browser` did not exist.** The bot-detection section
  denied the flag was available (it shipped in 0.2.4), then walked the reader through
  installing a third-party Chrome extension and hand-exporting full-account-access session
  cookies to disk. Replaced with the one-line flag. `docs/setup-claude-desktop.md`'s note
  that it "is a yt-dlp option — see the downloader source" is also gone; it is a
  first-class CLI flag.
- **The documented run-lock path was wrong on macOS.** The lock is
  `tempfile.gettempdir()/youtube-transcriber.lock`, which on macOS is the per-user
  `$TMPDIR`, not `/tmp`. `rm /tmp/youtube-transcriber.lock` — given as the recovery step in
  four docs, including the skill's Critical Rules — silently deletes nothing, leaving the
  lock held with no obvious next step. Docs now point at the path the error message prints,
  or use `"${TMPDIR:-/tmp}/youtube-transcriber.lock"`. This also corrects the 0.2.0 entry
  below, which introduced the wrong path.
- **Corrected the record on `--quiet`.** The 0.2.6 entry stated the flag "does not exist on
  the CLI and never did under this version line." It has existed since 0.1.0 — as the same
  CHANGELOG's own 0.1.0 section records — and still does. That false premise removed a
  working flag from every user-facing doc; it is documented again. Its help text also
  overclaimed ("suppress all progress output (stderr)"): errors and the MLX `--vad` warning
  still print. Reworded.
- **Corrected the record on `--num-threads 0`.** The 0.2.5 entry described `cpu_threads=0`
  as "use all available logical CPUs" that "saturates the machine's full thread count".
  Neither faster-whisper nor CTranslate2 documents that behavior: faster-whisper's own
  docstring says 4 by default, and forwards the value to CTranslate2's `intra_threads`,
  where 0 means "use a default value". The 4 → 0 change did not increase thread usage or
  reduce wall-clock time; its only effect was that `OMP_NUM_THREADS` is honored when set.
  Pass an explicit count for full core usage. The in-code help was corrected shortly after
  0.2.5 shipped but the CHANGELOG was not; this records it.
- **Corrected the record on the model-table column.** The 0.2.6 entry said the old "VRAM"
  column "mixed up weight file sizes with runtime memory". It did not — those were genuine
  float16 VRAM figures, and `AVAILABLE_MODELS` still carries them under a `vram` key. Left
  standing, that entry invites a wrong "fix" to `transcriber.py`.
- **Model download sizes corrected.** `turbo` was documented as ~800 MB in four places; the
  MLX weights the default Apple Silicon path downloads measure 1.5 GiB (~1.6 GB). `small`
  was listed at ~250 MB, contradicting the table's own stated float16 convention (~0.5 GB).
  Tables now state which backend's download they describe.
- **`--vad` is not "silently" ignored on MLX** — the backend warns on stderr, deliberately
  outside the verbose guard so the warning survives `--quiet`. Corrected in `AGENTS.md` and
  the skill reference.
- **Skill completion detection was unbounded and mis-parsed.** `SKILL.md` polled with
  `wc -w <file>`, whose output is `N filename`, not the bare `0` the doc promised — and the
  transcript file is only written at the very end of a successful run, so on any failure it
  never appears and the poll never terminates. The skill now captures the run's exit status
  to a `.status` sidecar, polls that, bounds the loop, and uses `wc -w <` for a bare count.
- **Docstring corrections** — `check_ffmpeg` documented `Raises: SystemExit` but raises
  `click.ClickException`; `format_text` claimed "single-space separation" but joins with a
  blank line (one paragraph per segment, which the tests pin); `download_audio` omitted
  `cookies_from_browser` from its Args block.
- **`LICENSE` restored to the verbatim GPL-3.0 text.** The appendix template placeholders
  had been filled in with a real copyright notice, modifying text the license itself
  forbids modifying. The notice now lives in the README's License section, where it belongs.

### Changed

- **`secretstorage` is now Linux-only** (`sys_platform == "linux"`). It exists solely to
  back yt-dlp's Linux keyring cookie path — macOS uses the Keychain and Windows its own
  decryptor, so neither ever reaches it. Gating it removes 5 packages and ~22 MB
  (secretstorage, jeepney, cryptography, cffi, pycparser) from every macOS install. It was
  added unconditionally alongside `--cookies-from-browser` in 0.2.4 and never recorded.
- **`yt-dlp` floor raised to `>=2026.3.17`.** `downloader.py` passes `js_runtimes` and
  `remote_components`, which belong to yt-dlp's modern JS-challenge subsystem; the declared
  `>=2024.1.1` floor predates it. `uv tool install` and `pip install git+...` do not read
  `uv.lock`, so those users resolved against the raw floor.
- **ruff `target-version` is now `py311`**, matching `requires-python = ">=3.11"`. The
  previous `py310` silently disabled pyupgrade's 3.11+ rules. Verified to need no code
  changes.
- **Operating System classifiers** changed from `OS Independent` to `MacOS :: MacOS X` and
  `POSIX :: Linux`, matching the documented platform support.
- **Added `Changelog` and `Documentation` project URLs** to `pyproject.toml`.
- **The offline claim is now precise.** Audio and transcripts still never leave the machine
  — verified — but the docs claimed yt-dlp and HuggingFace were the only network calls.
  There is a third: `remote_components = {"ejs:github"}` fetches yt-dlp's JS challenge
  solver from GitHub. All three destinations are now named in the README, the setup guide,
  and `AGENTS.md`.
- **README restructured** for a first-time reader and for agents: a Quick Start near the
  top, a complete flag table (five flags were documented nowhere — `--quiet`,
  `--compute-type`, `--beam-size`, `--num-threads`, `--cookies-from-browser`), an agent
  contract section, the local-file transcription workflow, CI and license badges, and the
  19-line VAD warning moved from above the feature list down to the `--vad` section it
  describes.
- **The `mlx` extra is documented as required on Apple Silicon**, not as an optional
  performance upgrade, and install commands use the declared extra
  (`uv tool install ".[mlx]"`) rather than `--with mlx-whisper`, so the `>=0.4.0` floor
  applies.
- **The release process now includes building and attaching the `.skill` bundle.** The
  documented four-step process never mentioned `scripts/build-skill.sh`, while the README
  directs users to download `youtube-transcribe.skill` from the latest release — so cutting
  a release by the book would have silently broken the primary skill-install path.
- **A standing `## [Unreleased]` section** is now kept at the top, so changes are recorded
  as they land rather than reconstructed at release time.

### Removed

- **`.github/copilot-instructions.md`** — superseded by `AGENTS.md`. It carried six errors,
  including a `transcribe_audio(audio_path, model="turbo")` example (the parameter is
  `model_name`, so the snippet raises `TypeError`), a "Python 3.10+" floor, a claim that
  ruff was enforced in CI when no CI existed, and an add-a-new-format recipe describing
  `cli.py` edits that have not been necessary since formats became registry-driven.
- **"OpenAI Whisper API as optional cloud backend" removed from the README roadmap.** It
  contradicted the project's stated non-negotiable — no cloud transcription APIs — and read
  as standing permission to add one.

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
