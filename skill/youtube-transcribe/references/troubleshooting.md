# Troubleshooting Reference

Every command here runs on the user's Mac via `osascript`. Read the `.status` sidecar file first —
`EXIT=1` is a runtime failure (this file), `EXIT=2` is a bad command (fix the command, don't retry).

---

## "command not found" in the Terminal window

The tool isn't on the PATH of the shell Terminal opens.

**Fix:** have the user run in Terminal:
```bash
uv tool update-shell && source ~/.zshrc
```

**Workaround:** use the absolute path in the osascript command:
```bash
osascript -e 'tell application "Terminal" to do script "~/.local/bin/youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt; echo EXIT=$? > /tmp/transcript_<video_id>.status"'
```

---

## "mlx-whisper is not installed" (Apple Silicon)

On Apple Silicon the tool always selects the MLX backend and **there is no CPU fallback** — a missing
`mlx` extra is a hard failure, not a slow run. The full error:

```text
mlx-whisper is not installed. Install it with:
  uv sync --extra mlx
```

**Fix:** have the user run in Terminal:
```bash
uv tool install "git+https://github.com/overtonlabs/youtube-transcriber.git[mlx]" --force
# or from a clone:  cd ~/path/to/youtube-transcriber && uv sync --extra mlx
```

**Immediate workaround** without installing anything — force the CPU backend (slower, but works):
```bash
youtube-transcriber transcribe "<url>" --device cpu --output /tmp/transcript_<video_id>.txt
```

After reinstalling, the banner should read `Device: Apple Silicon GPU  [MLX / Metal + Neural Engine]`.

---

## CPU at 100%, fans loud

On an **Apple Silicon** Mac this means the run is on the CPU backend, which only happens if
`--device cpu` was passed — the default path uses the GPU. Drop the flag.

On an **Intel** Mac, CPU is the only backend and this is expected. A smaller model
(`--model small` or `--model base`) reduces the load. `--num-threads` caps thread use; note the
default of `0` means 4 threads, not all cores.

---

## Transcript file is empty after the run completes

If the status file says `EXIT=0`, the run succeeded and produced **0 segments**. Most common cause:
`--vad` classified all the audio as non-speech, which happens with any music or background audio.

**Diagnose:**
```bash
osascript -e 'do shell script "grep -i vad ~/.local/share/youtube-transcriber/debug.log | tail -5"'
```

`VAD filter removed Xm Xs of audio` confirms it.

**Fix:** re-run without `--vad`.

---

## "Another youtube-transcriber process is already running"

Exit 1. Either a transcription really is running — wait for it — or a crashed run left a stale lock.

The error message prints the exact path to delete. On macOS the lock is in `$TMPDIR`, **not** `/tmp`,
so a hardcoded `rm /tmp/youtube-transcriber.lock` silently deletes nothing and the lock survives.

**Fix:**
```bash
osascript -e 'do shell script "rm -f \"${TMPDIR:-/tmp}/youtube-transcriber.lock\""'
```

---

## yt-dlp JavaScript runtime error

```text
No supported JavaScript runtime could be found
```

Node.js must be installed via Homebrew, not nvm. Terminal's PATH won't include nvm-managed runtimes
when launched by a GUI app, because those only inject PATH in interactive shells.

**Fix:**
```bash
brew install node
```

That puts Node at `/opt/homebrew/bin/node`, which the tool finds regardless of shell config.

---

## Reinstalling this skill does NOT fix download failures

The skill is three Markdown files — it contains no code and no yt-dlp. The `youtube-transcriber`
CLI is a separate artifact, installed separately, and it is the one that holds yt-dlp. If a user
offers to re-import the skill to fix a failing download, tell them it will not help and point
them at the CLI upgrade below instead.

---

## Any download failure — check yt-dlp's age FIRST

`HTTP Error 403: Forbidden`, `The page needs to be reloaded`, `Sign in to confirm you're not a
bot`, and `Requested format is not available` are all usually the same root cause: **a stale
yt-dlp**. YouTube changes constantly and yt-dlp ships fixes within days, so a version a couple
of months old fails — and never says so. The tool warns on stderr when its yt-dlp is over 60
days old, and names the version in every download-failure message.

**Fix first, before anything else.** This upgrades software on the user's machine, so tell
them what it does and get their OK, then run:

```bash
osascript -e 'do shell script "uv tool upgrade youtube-transcriber"'
```

If they installed from a clone instead, the command is
`cd <repo> && uv sync --upgrade-package yt-dlp`.

Only if that does not fix it should you move on to cookies below. Do not reach for the user's
browser cookies to work around a problem a version bump solves.

---

## "Sign in to confirm you're not a bot" (with yt-dlp already current)

YouTube is rate-limiting or gating the video. Pass the user's browser cookies:

```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --cookies-from-browser chrome --output /tmp/transcript_<video_id>.txt; echo EXIT=$? > /tmp/transcript_<video_id>.status"'
```

Any browser yt-dlp supports works — `chrome`, `firefox`, `safari`, `edge`, `brave`. The browser's
cookie store must be readable. Tell the user what this does before running it: it reads their
logged-in session from the browser.

---

## "No video ID could be extracted" / "does not appear to be a YouTube URL"

Exit 2 — a usage error, so don't retry the same command. Either the URL isn't a YouTube video
(playlist, channel, or search page), or the host isn't recognised. Accepted hosts: `youtube.com`,
`www.youtube.com`, `m.youtube.com`, `music.youtube.com`, `youtu.be`. Ask the user for a single video
URL.

---

## "Model '<name>' has no MLX repo mapping"

Exit 1 on Apple Silicon. `distil-small.en` and `distil-large-v2` have no MLX build published. Either
pick a model that does (`distil-large-v3`, `distil-medium.en`, `turbo`, `large-v3`) or add
`--device cpu`.

---

## Debug logging

When anything unexpected happens, re-run with `--log`:

```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt --log; echo EXIT=$? > /tmp/transcript_<video_id>.status"'
```

Then read it:
```bash
osascript -e 'do shell script "cat ~/.local/share/youtube-transcriber/debug.log"'
```

**Key log lines:**

| Log line | Meaning |
|---|---|
| `VAD filter removed Xm Xs of audio` | VAD discarded the audio — drop `--vad` |
| `JS runtime selected: {'node': {'path': ...}}` | Node.js found correctly |
| `No JS runtime (node/deno/bun) found on PATH` | install Node via Homebrew |
| `MLX transcribe: path=... model=... repo=...` | MLX backend active |
| `mlx-whisper transcription failed: ...` | MLX failure — often a bad model repo or low memory |
| `Failed to load Whisper model` | faster-whisper path — try a smaller model (memory) |

---

## Platform check

This skill supports macOS only — the osascript workflow drives the user's Terminal. Apple Silicon
Macs get GPU acceleration via MLX; Intel Macs work on CPU, just slower. If the user is on Windows or
Linux, stop and tell them: the CLI itself runs fine on Linux from a terminal, but this skill cannot
drive it.
