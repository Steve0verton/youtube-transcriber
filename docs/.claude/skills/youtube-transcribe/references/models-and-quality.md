# Models, Quality, and VAD Reference

## Model Selection

Use `turbo` by default. Only suggest alternatives when there's a specific reason.

| Model | Size | Best for |
|---|---|---|
| `tiny` | ~75 MB | Quick pipeline test — low accuracy, fast |
| `base` | ~150 MB | Fast, acceptable quality for short clips |
| `small` | ~250 MB | Good balance for clips under 10 minutes |
| `turbo` | ~800 MB | **Default** — best overall on Apple Silicon. Optimized large-v3, 8× faster with minimal quality loss |
| `distil-large-v3` | ~1.5 GB | Near large-v3 accuracy, faster inference |
| `large-v3` | ~3 GB | Maximum accuracy. Suggest when transcript quality from turbo is poor |

`.en` English-only variants exist for tiny, base, small, and medium — slightly faster and more accurate
for English-only content.

**First-time model download:** When a model isn't cached yet, the tool downloads it from HuggingFace
(~800 MB for turbo). Warn the user this takes a few minutes. Subsequent runs load from cache instantly.

---

## Interpreting Transcript Quality

Whisper transcription is high quality but not perfect. These factors affect output:

| Factor | Effect |
|---|---|
| Background music or ambient sound | Words garbled or invented — model transcribes non-speech audio |
| Low audio quality or heavy compression | Increased word substitutions, dropped syllables |
| Heavy accents or non-standard pronunciation | Occasional word-level errors |
| Technical jargon, proper nouns, names | Frequently misspelled or phonetically approximated (e.g., "Kubernetes" → "Cubeerness") |
| Overlapping speakers | Words merged or misattributed |
| Music intro/outro | Spurious text fragments at start/end |
| Very fast speech | Words run together or partially dropped |

### How to handle errors

- **Don't present phonetic guesses as facts.** If a proper noun looks wrong, use surrounding context to
  infer the likely correct form. Note uncertainty when it matters.
- **Use context to resolve ambiguity.** A word that looks like a typo usually has a plausible correct
  reading in context.
- **Flag low-confidence passages.** If a section is clearly garbled (disconnected words, nonsensical
  phrases — likely music or noise), tell the user that portion wasn't reliably transcribed rather than
  summarizing gibberish.
- **Quote carefully.** When attributing specific words to a speaker, add a light caveat if uncertainty
  exists: "roughly paraphrasing" or "transcript may contain minor errors."
- **Suggest a better model if quality is poor.** If the transcript has many obvious errors throughout:
  "The transcript has several unclear passages — re-running with `--model large-v3` will improve accuracy."

### Quick quality signals

| Signal | Likely cause | Action |
|---|---|---|
| Segment count is 0 or very low relative to video length | VAD or audio pipeline issue | Retry without `--vad` |
| Opening segments are nonsensical | Intro music transcribed as speech | Discard those segments |
| Proper nouns consistently garbled | Phonetic approximation | Infer from context |
| Large blocks of repetitive or looping text | Model hallucination on near-silence | Ignore those sections |

---

## VAD (Voice Activity Detection)

The `--vad` flag pre-filters audio, discarding anything classified as non-speech. This is destructive
and silent — if it discards everything, you get 0 segments with no error message.

| Content type | Use `--vad`? |
|---|---|
| Music video | Never — entire audio track will be discarded |
| Video with intro music or background sound | No |
| Podcast (speech only, no music) | Yes — removes silence, speeds up transcription |
| Lecture/interview in a quiet room | Generally safe |

**Note:** `--vad` is silently ignored on the Apple Silicon (MLX) backend. It only applies when the
tool falls back to CPU (faster-whisper).

---

## Reading the Terminal Output

The Terminal window shows this progression during a successful run:

```
youtube-transcriber v0.2.2
  URL:    https://www.youtube.com/watch?v=dQw4w9WgXcQ
  Video:  dQw4w9WgXcQ
  Model:  turbo
  Format: text
  Device: Apple Silicon GPU  [MLX / Metal + Neural Engine]   ← GPU confirmed

[ Step 1/2 ] Downloading audio...
  (yt-dlp progress bar)

[ Step 2/2 ] Transcribing...
  Model 'turbo' loaded from cache:
    /Users/.../.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo/...
  Transcribing audio segments (Apple Silicon GPU):
Detected language: English
[00:00.000 --> 00:05.120]  Hello and welcome...
[00:05.120 --> 00:10.440]  Today we're going to talk about...

  Transcription complete. Language: en | Duration: 1h 3m 57s | Segments: 1341
```

**Key things to look for:**

- **Device line:** Should say `Apple Silicon GPU  [MLX / Metal + Neural Engine]`. If it says
  `CPU  [faster-whisper]`, mlx-whisper is not installed — see `troubleshooting.md`.
- **Model loading:** "loaded from cache" = instant. "not in cache -- downloading" = first-time download,
  warn the user it'll take a few minutes.
- **Segment count:** A 1-hour video should produce ~1000+ segments. If you see 0 or very few, something
  went wrong (likely VAD filtering or audio issue).
