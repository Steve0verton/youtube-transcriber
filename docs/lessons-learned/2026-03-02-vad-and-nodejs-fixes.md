# Lessons Learned: 2026-03-02 — VAD Silence Bug and Node.js Runtime Discovery

## Summary

During initial local installation and testing, two separate bugs caused the
transcriber to produce empty output (0 segments) on a known-good YouTube video.
This document records what was found, why it happened, and what was changed.

---

## Problem 1: VAD Filter Was Silencing Entire Audio Files

### Symptom

`youtube-transcriber transcribe <url> --model tiny` completed without errors and
reported the correct video duration (e.g. 3m 33s), but returned:

```text
Transcription complete. Language: en | Duration: 3m 33s | Segments: 0
```

No transcript text was produced at all.

### Root Cause

The transcriber was calling `faster-whisper`'s `model.transcribe()` with
`vad_filter=True` hardcoded. The VAD (Voice Activity Detection) filter uses the
[Silero VAD](https://github.com/snakers4/silero-vad) model, which is trained on
clean speech recordings. It reliably detects speech in quiet environments but
classifies music-mixed audio — including background music, pop songs, video
intros, and YouTube-style content — as "not speech" and removes it.

The effect: the entire audio track was discarded before Whisper ever ran.
faster-whisper logs this internally as:

```text
VAD filter removed 03:33.043 of audio
VAD filter kept the following audio segments:   (empty)
```

This log line was invisible until debug logging was added.

### When VAD Is Harmful vs. Helpful

| Content type | VAD effect | Recommendation |
|---|---|---|
| Music video (e.g. Rick Astley) | **Removes everything** — music is classified as non-speech | Do **not** use `--vad` |
| YouTube video with background music | Removes or truncates large portions | Do **not** use `--vad` |
| Talk / lecture / podcast (no music) | Removes silence efficiently, speeds up transcription | Safe to use `--vad` |
| Interview with quiet background | Generally safe; may occasionally clip soft speech | Use `--vad` with caution |

### Fix

`vad_filter` was changed from hardcoded `True` to `False` (the new default).
A `--vad` CLI flag was added for users who explicitly want VAD on clean
speech recordings (talks, podcasts, interviews with no background audio).

```bash
# Default — VAD off. Works for all video types including music
youtube-transcriber transcribe "<url>"

# VAD on — only for clean speech recordings with no background music
youtube-transcriber transcribe "<url>" --vad
```

**Source changes:**
- `src/youtube_transcriber/transcriber.py` — `vad_filter` parameter added, default `False`; VAD parameters moved inside the conditional block
- `src/youtube_transcriber/cli.py` — `--vad` flag added and threaded through to `transcribe_audio()`

---

## Problem 2: yt-dlp Could Not Solve YouTube JS Challenges

### Symptom

`yt-dlp` emitted warnings about missing JavaScript runtime support and occasionally
failed to extract higher-quality audio formats from YouTube:

```
WARNING: [youtube] No supported JavaScript runtime could be found.
Only deno is enabled by default...
```

In some cases the download appeared to succeed (low-quality format fallback) but
repeated edge cases produced incomplete or missing audio.

### Root Cause

YouTube uses JavaScript-based challenge validation to protect its audio/video
format endpoints. yt-dlp needs an external JavaScript runtime (Node.js, Deno, or
Bun) to solve these challenges and unlock the full format list.

**yt-dlp defaults:** The Python API defaults `js_runtimes` to `{"deno": {}}`.
Deno is rarely installed by default, so the runtime is effectively absent for
most users.

**macOS complication:** Even though Node.js was installed (via nvm), it was
installed through nvm — a shell-level PATH manager. nvm injects its `bin/`
directory into PATH when a terminal session starts by sourcing `~/.bashrc` or
`~/.zshrc`. macOS GUI apps (like Claude Desktop) launch processes without
sourcing shell config files, so nvm's PATH injection never runs. This meant:

- `node` was reachable in a terminal session
- `node` was **not** reachable via `shutil.which("node")` from a GUI-launched process

**Additional bug:** The initial fix attempted to pass `js_runtimes` as a string
(`"node:/path/to/node"`) — the CLI format — rather than the Python API format,
which requires a dict: `{"node": {"path": "/path/to/node"}}`. This caused a
`ValueError` crash when yt-dlp tried to parse the option.

### Fix (two-part)

**Part A — Correct the Python API format** for `js_runtimes`:
```python
# Wrong (CLI string format):
ydl_opts["js_runtimes"] = "node:/usr/local/bin/node"

# Correct (Python API dict format):
ydl_opts["js_runtimes"] = {"node": {"path": "/usr/local/bin/node"}}
```

**Part B — Robust runtime discovery** that works whether or not shell PATH
injection has run. `_find_js_runtime()` in `downloader.py` now:

1. First calls `shutil.which(runtime)` — fast path, works in terminal sessions
2. Falls back to a list of well-known absolute paths:
   - `/opt/homebrew/bin/node` (Homebrew, Apple Silicon — **system-wide, always works**)
   - `/usr/local/bin/node` (Homebrew, Intel)
   - `~/.nvm/versions/node/` — walks the directory and picks the most recent version
   - `~/.volta/bin/node`, `~/.fnm/aliases/default/bin/node`
   - Equivalent paths for Deno and Bun

**Permanent recommendation:** Install Node.js via Homebrew rather than nvm so it
lives at a fixed, system-wide path accessible from any process context:

```bash
brew install node
```

This places node at `/opt/homebrew/bin/node`, which `shutil.which` always finds
regardless of shell configuration.

**Source changes:**
- `src/youtube_transcriber/downloader.py` — `_find_js_runtime()` rewritten to
  return a dict, probe PATH first, then fall back through known absolute paths
  including nvm version directory traversal

---

## Problem 3: Debug Logging Was Not Available (Root Enabler)

### Symptom

Neither problem above was immediately diagnosable — the `vad_filter` issue showed
as "Segments: 0" with no explanation, and the JS runtime issue showed as a Python
traceback on bad input but was otherwise silent.

### Fix

A structured debug logging system was added to the project:

- `src/youtube_transcriber/logging_config.py` — new module; `setup_logging()`
  configures a rotating file handler (5 MB × 3 backups) on the root logger
- `src/youtube_transcriber/cli.py` — `--log` flag (default path) and `--log-file FILE` (custom path)
- `src/youtube_transcriber/downloader.py` — `log.debug()` / `log.warning()` calls
  at each key step: runtime selection, yt-dlp options, download result, file list
- `src/youtube_transcriber/transcriber.py` — `log.debug()` calls at model load,
  transcription start, and per-segment output

The VAD problem became immediately obvious the moment logging was enabled:

```
INFO  | faster_whisper | VAD filter removed 03:33.043 of audio
INFO  | faster_whisper | VAD filter kept the following audio segments:
```

**Usage:**

```bash
# Write debug log to default location (~/.local/share/youtube-transcriber/debug.log)
youtube-transcriber transcribe "<url>" --log

# Write to a custom path
youtube-transcriber transcribe "<url>" --log-file /tmp/yt-debug.log
```

---

## Timeline

| Time | Event |
|---|---|
| Initial install | `uv sync` + `uv tool install .` succeeded; `youtube-transcriber --help` worked |
| First transcription test | Returned 0 segments; no error |
| JS runtime investigation | Discovered yt-dlp needed a JS runtime; attempted fix used wrong API format → crash |
| Logging added | Added `--log`/`--log-file` flags and structured logging throughout |
| VAD root cause found | First log run immediately showed `VAD filter removed 03:33.043 of audio` |
| Both fixes shipped | VAD default changed to `False`; `_find_js_runtime()` rewritten with fallbacks |
| Node.js system install | `brew install node` confirmed; `shutil.which("node")` now returns `/opt/homebrew/bin/node` |
| Final verification | 48 segments transcribed correctly from Rick Astley video |

---

## Recommendations for Future Debugging

1. **Always try `--log` first** when a transcription returns 0 segments or produces unexpected output.
2. **Check VAD first** if you have content with background audio. Default is off; add `--vad` only for pure speech.
3. **Install Node.js via Homebrew** (`brew install node`) on macOS for reliable yt-dlp JS challenge support across all process contexts, including Claude Desktop.
4. **Do not rely on nvm, volta, or fnm** for the node executable when running as a non-interactive process (e.g., as a tool invoked by Claude Desktop). These version managers inject PATH only in interactive shell sessions.

---

## Files Changed

| File | Change |
|---|---|
| `src/youtube_transcriber/logging_config.py` | **New** — rotating file logging, `setup_logging()` |
| `src/youtube_transcriber/cli.py` | Added `--vad`, `--log`, `--log-file` flags; debug log calls |
| `src/youtube_transcriber/downloader.py` | Rewrote `_find_js_runtime()` with fallback paths; added `log.*` calls throughout |
| `src/youtube_transcriber/transcriber.py` | Changed `vad_filter` default to `False`; added `vad_filter` parameter; added `log.*` calls |
