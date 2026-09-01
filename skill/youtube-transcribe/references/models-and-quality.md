# Models, Quality, and VAD Reference

## Model Selection

Use `turbo` by default. Only suggest an alternative when there is a specific reason.

Sizes are the Apple Silicon (MLX) download — what the default path pulls. The CPU/CUDA path
downloads CTranslate2 weights instead, which are smaller at `int8`.

| Model | Download | Best for |
|---|---|---|
| `tiny` | ~75 MB | Quick pipeline test — fast, low accuracy |
| `base` | ~150 MB | Fast, acceptable for short clips |
| `small` | ~0.5 GB | Good balance for clips under 10 minutes |
| `turbo` | ~1.6 GB | **Default** — pruned large-v3, ~8× faster, minimal quality loss |
| `distil-large-v3` | ~1.5 GB | Near large-v3 accuracy, faster inference. English-only |
| `large-v3` | ~3 GB | Maximum accuracy. Suggest when turbo's transcript is poor |

### The full list

All 16 accepted `--model` values: `tiny`, `tiny.en`, `base`, `base.en`, `small`, `small.en`,
`medium`, `medium.en`, `large-v1`, `large-v2`, `large-v3`, `turbo`, `distil-small.en`,
`distil-medium.en`, `distil-large-v2`, `distil-large-v3`.

- The `.en` variants (`tiny`/`base`/`small`/`medium`) are slightly faster and more accurate on
  English-only audio.
- `large-v1` and `large-v2` exist but there is no good reason to prefer them over `large-v3`.
- **`distil-small.en` and `distil-large-v2` have no MLX build.** On Apple Silicon they fail with
  "has no MLX repo mapping" and need `--device cpu`. `distil-medium.en` and `distil-large-v3` work
  on both backends.

**First-time model download:** when a model is not cached, the tool downloads it from HuggingFace.
Warn the user this takes a few minutes (~1.6 GB for `turbo`). Later runs load from cache instantly.

---

## Interpreting Transcript Quality

Whisper is high quality but not perfect. These factors degrade output:

| Factor | Effect |
|---|---|
| Background music or ambient sound | Words garbled or invented — the model transcribes non-speech audio |
| Low audio quality or heavy compression | Word substitutions, dropped syllables |
| Heavy accents or non-standard pronunciation | Occasional word-level errors |
| Technical jargon, proper nouns, names | Frequently misspelled or phonetically approximated ("Kubernetes" → "Cubeerness") |
| Overlapping speakers | Words merged or misattributed |
| Music intro/outro | Spurious text fragments at the start or end |
| Very fast speech | Words run together or partially dropped |

### How to handle errors

- **Don't present phonetic guesses as facts.** If a proper noun looks wrong, infer the likely form
  from context and note the uncertainty when it matters.
- **Use context to resolve ambiguity.** A word that looks like a typo usually has a plausible
  correct reading.
- **Flag low-confidence passages.** If a section is clearly garbled — disconnected words, nonsense
  phrases, likely music or noise — say that portion wasn't reliably transcribed rather than
  summarizing gibberish.
- **Quote carefully.** When attributing specific words to a speaker, add a light caveat if there is
  any uncertainty: "roughly paraphrasing", or "the transcript may contain minor errors".
- **Suggest a better model if quality is poor.** If errors are pervasive: "The transcript has
  several unclear passages — re-running with `--model large-v3` will improve accuracy."

### Quick quality signals

| Signal | Likely cause | Action |
|---|---|---|
| Empty transcript, or very few segments for the video length | VAD discarded the audio | Retry without `--vad` |
| Opening segments are nonsensical | Intro music transcribed as speech | Discard those segments |
| Proper nouns consistently garbled | Phonetic approximation | Infer from context |
| Large blocks of repetitive or looping text | Model hallucination on near-silence | Ignore those sections |

---

## VAD (Voice Activity Detection)

`--vad` pre-filters the audio and discards anything classified as non-speech. It is destructive and
gives no error when it removes everything — you get an empty transcript with **exit code 0**.

| Content type | Use `--vad`? |
|---|---|
| Music video | Never — the entire track is discarded |
| Video with intro music or background sound | No |
| Podcast (speech only, no music) | Yes — removes silence, speeds up transcription |
| Lecture/interview in a quiet room | Generally safe |

**On the Apple Silicon (MLX) backend `--vad` is ignored**, and the tool warns on stderr:
`Warning: --vad is not supported with the MLX backend and will be ignored.` The flag only takes
effect on the faster-whisper backend (`--device cpu` or CUDA). The warning prints even with
`--quiet`.

---

## Reading the Terminal Output

A successful run on Apple Silicon looks like this:

```text
youtube-transcriber vX.Y.Z
  URL:    https://www.youtube.com/watch?v=dQw4w9WgXcQ
  Video:  dQw4w9WgXcQ
  Model:  turbo
  Format: text
  Device: Apple Silicon GPU  [MLX / Metal + Neural Engine]   ← GPU confirmed

[ Step 1/2 ] Downloading audio...
  Downloading audio: dQw4w9WgXcQ.webm
  Download complete (3.4 MB). Extracting audio...
  Audio ready: dQw4w9WgXcQ.wav

[ Step 2/2 ] Transcribing...
  Model 'turbo' loaded from cache:
    /Users/.../.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo/...
  Transcribing audio segments (Apple Silicon GPU):
Detected language: English
[00:00.000 --> 00:05.120]  Hello and welcome...
[00:05.120 --> 00:10.440]  Today we're going to talk about...

  Transcription complete. Language: en | Duration: 1h 3m 57s | Segments: 1341
Transcript saved to: /tmp/transcript_dQw4w9WgXcQ.txt
```

**What to look for:**

- **Device line** — `Apple Silicon GPU  [MLX / Metal + Neural Engine]` (two spaces before the
  bracket) confirms the GPU. `CPU  [faster-whisper]` on an Apple Silicon Mac means `--device cpu`
  was passed explicitly; it is not a symptom of a missing mlx extra. See `troubleshooting.md`.
- **Model loading** — "loaded from cache" is instant. "not in cache — downloading from HuggingFace"
  means a first-time download; warn the user it takes a few minutes.
- **Segment count** — a 1-hour video should produce roughly 1000+ segments. Zero or very few means
  something went wrong, most likely VAD.
- There is **no** `Loading model ... on Apple Silicon GPU (Metal/ANE)` line. The MLX path never
  prints one; `Loading model '<name>' on CPU (threads: N)...` appears only on the faster-whisper
  backend.
