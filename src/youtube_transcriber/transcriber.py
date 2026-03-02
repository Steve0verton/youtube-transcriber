"""Local speech-to-text transcription using faster-whisper.

Wraps the faster-whisper WhisperModel to transcribe audio files and return
structured results with per-segment timestamps.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import click

log = logging.getLogger(__name__)

# Valid model names accepted by faster-whisper / Hugging Face
ModelSize = Literal[
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large-v1",
    "large-v2",
    "large-v3",
    "turbo",
    "distil-small.en",
    "distil-medium.en",
    "distil-large-v2",
    "distil-large-v3",
]

AVAILABLE_MODELS: dict[str, dict[str, str]] = {
    "tiny":            {"params": "39M",   "vram": "~1 GB",  "notes": "Fastest, lowest accuracy"},
    "tiny.en":         {"params": "39M",   "vram": "~1 GB",  "notes": "English-only variant of tiny"},
    "base":            {"params": "74M",   "vram": "~1 GB",  "notes": ""},
    "base.en":         {"params": "74M",   "vram": "~1 GB",  "notes": "English-only variant of base"},
    "small":           {"params": "244M",  "vram": "~2 GB",  "notes": ""},
    "small.en":        {"params": "244M",  "vram": "~2 GB",  "notes": "English-only variant of small"},
    "medium":          {"params": "769M",  "vram": "~5 GB",  "notes": ""},
    "medium.en":       {"params": "769M",  "vram": "~5 GB",  "notes": "English-only variant of medium"},
    "large-v1":        {"params": "1550M", "vram": "~10 GB", "notes": ""},
    "large-v2":        {"params": "1550M", "vram": "~10 GB", "notes": ""},
    "large-v3":        {"params": "1550M", "vram": "~10 GB", "notes": "Best quality"},
    "turbo":           {"params": "809M",  "vram": "~6 GB",  "notes": "DEFAULT — optimized large-v3, 8× faster"},
    "distil-small.en": {"params": "166M",  "vram": "~1 GB",  "notes": "Distilled, English-only, very fast"},
    "distil-medium.en":{"params": "394M",  "vram": "~3 GB",  "notes": "Distilled, English-only"},
    "distil-large-v2": {"params": "756M",  "vram": "~6 GB",  "notes": "Distilled large-v2"},
    "distil-large-v3": {"params": "756M",  "vram": "~6 GB",  "notes": "Distilled large-v3"},
}

DEFAULT_MODEL: str = "turbo"


@dataclass
class TranscriptSegment:
    """A single timestamped segment of a transcription.

    Attributes:
        start: Start time in seconds.
        end: End time in seconds.
        text: The transcribed text for this segment.
    """

    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    """The complete result of a transcription run.

    Attributes:
        segments: List of timestamped transcript segments.
        language: Detected or specified language code (e.g. "en").
        duration: Total audio duration in seconds.
    """

    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = "unknown"
    duration: float = 0.0

    @property
    def text(self) -> str:
        """Return all segment text joined as a single string."""
        return " ".join(seg.text.strip() for seg in self.segments)


def transcribe_audio(
    audio_path: Path,
    model_name: str = DEFAULT_MODEL,
    device: str = "auto",
    compute_type: str = "auto",
    beam_size: int = 5,
    vad_filter: bool = False,
    verbose: bool = True,
) -> TranscriptResult:
    """Transcribe an audio file using faster-whisper.

    Downloads the specified model on first use (cached in HuggingFace cache).
    Automatically selects float16 on GPU and int8 on CPU for best performance.

    Args:
        audio_path: Path to the audio file to transcribe.
        model_name: Whisper model name (e.g. "turbo", "large-v3", "small").
        device: Compute device — "auto", "cuda", or "cpu".
            "auto" will use CUDA if available, otherwise CPU.
        compute_type: Quantization type — "auto", "float16", "int8_float16", "int8".
            "auto" selects float16 for CUDA, int8 for CPU.
        beam_size: Beam size for beam search decoding (higher = more accurate, slower).
        vad_filter: Enable Silero VAD pre-filtering to strip silence before transcribing.
            Speeds up speech-only recordings (talks, podcasts) but will discard speech
            that is mixed with music or background audio. Disabled by default.
        verbose: If True, write progress messages to stderr.

    Returns:
        A TranscriptResult containing segments, detected language, and duration.

    Raises:
        click.ClickException: If transcription fails.
    """
    from youtube_transcriber.utils import detect_device

    # Resolve device
    resolved_device = detect_device() if device == "auto" else device

    if verbose:
        device_label = "GPU (CUDA)" if resolved_device == "cuda" else "CPU"
        click.echo(
            f"  Loading model '{model_name}' on {device_label}...",
            err=True,
        )

    # Resolve compute type
    if compute_type == "auto":
        resolved_compute_type = "float16" if resolved_device == "cuda" else "int8"
    else:
        resolved_compute_type = compute_type

    try:
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]
    except ImportError as exc:
        raise click.ClickException(
            "faster-whisper is not installed. Run: uv sync"
        ) from exc

    try:
        model = WhisperModel(
            model_name,
            device=resolved_device,
            compute_type=resolved_compute_type,
        )
        log.debug(
            "Loaded model: name=%s device=%s compute_type=%s",
            model_name, resolved_device, resolved_compute_type,
        )
    except Exception as exc:
        # GPU may have insufficient VRAM — suggest fallback
        if resolved_device == "cuda":
            log.warning("GPU error loading model '%s': %s — retrying on CPU", model_name, exc)
            click.echo(
                f"  Warning: GPU error ({exc}). Retrying on CPU...",
                err=True,
            )
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            resolved_device = "cpu"
        else:
            log.exception("Failed to load Whisper model '%s' on device=%s", model_name, resolved_device)
            raise click.ClickException(f"Failed to load Whisper model: {exc}") from exc

    if verbose:
        click.echo("  Transcribing... (this may take a while for large files)", err=True)

    try:
        log.debug(
            "Starting transcription: path=%s beam_size=%d vad_filter=%s audio_size=%.1f MB",
            audio_path, beam_size, vad_filter, audio_path.stat().st_size / 1_048_576,
        )

        transcribe_kwargs: dict = {
            "beam_size": beam_size,
            "vad_filter": vad_filter,
        }
        if vad_filter:
            transcribe_kwargs["vad_parameters"] = {
                # Lower threshold = more sensitive (catches quieter / music-mixed speech).
                "threshold": 0.3,
                # Minimum duration of a detected speech chunk (ms)
                "min_speech_duration_ms": 250,
                # Gap of silence required to split segments (ms)
                "min_silence_duration_ms": 500,
                # Padding added around each speech chunk (ms)
                "speech_pad_ms": 400,
            }

        segments_iter, info = model.transcribe(str(audio_path), **transcribe_kwargs)
        log.debug(
            "faster-whisper info: language=%s language_prob=%.3f duration=%.1fs",
            info.language, info.language_probability, info.duration,
        )

        segments: list[TranscriptSegment] = []
        for seg in segments_iter:
            log.debug("Segment [%.2f–%.2f]: %r", seg.start, seg.end, seg.text)
            segments.append(
                TranscriptSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                )
            )

        result = TranscriptResult(
            segments=segments,
            language=info.language,
            duration=info.duration,
        )

        if verbose:
            from youtube_transcriber.utils import format_duration
            click.echo(
                f"  Transcription complete. "
                f"Language: {info.language} | "
                f"Duration: {format_duration(info.duration)} | "
                f"Segments: {len(segments)}",
                err=True,
            )

        return result

    except Exception as exc:
        log.exception("Transcription failed for path=%s", audio_path)
        raise click.ClickException(f"Transcription failed: {exc}") from exc
