# Troubleshooting Reference

## "command not found" in Terminal window

The tool isn't on PATH in the shell that Terminal opens.

**Fix:** Have the user run in Terminal:
```bash
uv tool update-shell && source ~/.zshrc
```

**Workaround:** Replace `youtube-transcriber` with the full path in the osascript command:
```bash
osascript -e 'tell application "Terminal" to do script "~/.local/bin/youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt"'
```

---

## CPU at 100%, fans loud (GPU not active)

mlx-whisper is not installed. The tool fell back to the CPU backend. The Terminal banner will show:
```
Device: CPU  [faster-whisper]
```

**Fix:** Have the user run in Terminal:
```bash
cd ~/path/to/youtube-transcriber
uv tool install . --with mlx-whisper --force
```

After reinstalling, the banner should show `Apple Silicon GPU  [MLX / Metal + Neural Engine]`.

---

## Transcript file is empty after run completes

Most common cause: `--vad` discarded everything (classified all audio as non-speech).

**Diagnose:** Check the debug log:
```bash
cat ~/.local/share/youtube-transcriber/debug.log | grep -i vad
```

If you see `VAD filter removed Xm Xs of audio`, that's the cause.

**Fix:** Remove `--vad` and retry.

---

## "Another youtube-transcriber process is already running"

A previous run left a stale lock file (likely crashed or was interrupted).

**Fix:**
```bash
rm /tmp/youtube-transcriber.lock
```

---

## yt-dlp JavaScript runtime error

```
No supported JavaScript runtime could be found
```

Node.js must be installed via Homebrew — not nvm. Terminal's PATH won't include nvm-managed runtimes
because macOS GUI apps launch without a full shell environment.

**Fix:**
```bash
brew install node
```

This puts Node at `/opt/homebrew/bin/node`, which is always on PATH regardless of shell config.

---

## "Sign in to confirm you're not a bot"

YouTube is rate-limiting the download. Pass browser cookies to authenticate:

```bash
youtube-transcriber transcribe "<url>" --cookies-from-browser chrome --output /tmp/transcript_<video_id>.txt
```

Via osascript:
```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --cookies-from-browser chrome --output /tmp/transcript_<video_id>.txt"'
```

---

## Debug logging

When anything unexpected happens, enable debug logging to see what yt-dlp and the whisper backend are doing:

```bash
osascript -e 'tell application "Terminal" to do script "youtube-transcriber transcribe \"<url>\" --output /tmp/transcript_<video_id>.txt --log"'
```

Then read the log:
```bash
osascript -e 'do shell script "cat ~/.local/share/youtube-transcriber/debug.log"'
```

**Key log lines to look for:**

| Log line | Meaning |
|---|---|
| `VAD filter removed Xm Xs of audio` | VAD discarded audio — remove `--vad` |
| `JS runtime selected: node at /opt/homebrew/...` | Node.js found correctly |
| `MLX transcribe: ...` | GPU backend is active |
| `Failed to load Whisper model` | Try a smaller model — possible memory issue on 8 GB machines |

---

## Platform check

This skill only supports macOS with Apple Silicon. If the user is on Windows or Linux, stop and let them
know. They can still run the CLI tool directly from a terminal on Linux, but the osascript-based agent
workflow is macOS-only.
