"""Local speech-to-text transcription using faster-whisper.

Wraps the faster-whisper WhisperModel to transcribe audio files and return
structured results with per-segment timestamps.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
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

# Mapping from user-facing model names to HuggingFace repos for mlx-whisper.
# mlx-whisper uses Apple's MLX framework for GPU-accelerated transcription on
# Apple Silicon (M-series chips) via Metal and the Apple Neural Engine.
# Models are downloaded from HuggingFace on first use and cached locally.
MLX_MODEL_REPOS: dict[str, str] = {
    "tiny":             "mlx-community/whisper-tiny-mlx",
    "tiny.en":          "mlx-community/whisper-tiny.en-mlx",
    "base":             "mlx-community/whisper-base-mlx",
    "base.en":          "mlx-community/whisper-base.en-mlx",
    "small":            "mlx-community/whisper-small-mlx",
    "small.en":         "mlx-community/whisper-small.en-mlx",
    "medium":           "mlx-community/whisper-medium-mlx",
    "medium.en":        "mlx-community/whisper-medium.en-mlx",
    "large-v1":         "mlx-community/whisper-large-v1-mlx",
    "large-v2":         "mlx-community/whisper-large-v2-mlx",
    "large-v3":         "mlx-community/whisper-large-v3-mlx",
    # turbo = openai/whisper-large-v3-turbo (pruned large-v3, 8× faster)
    "turbo":            "mlx-community/whisper-large-v3-turbo",
    "distil-small.en":  "mlx-community/distil-whisper-small.en-mlx",
    "distil-medium.en": "mlx-community/distil-whisper-medium.en-mlx",
    "distil-large-v2":  "mlx-community/distil-whisper-large-v2-mlx",
    "distil-large-v3":  "mlx-community/distil-whisper-large-v3-mlx",
}

# HuggingFace hub cache root (respects HF_HOME / HF_HUB_CACHE env overrides)
_HF_CACHE_ROOT: Path = Path(
    os.environ.get(
        "HF_HUB_CACHE",
        os.path.join(os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface")), "hub"),
    )
)


@contextmanager
def _stdout_to_stderr() -> Iterator[None]:
    """Temporarily redirect sys.stdout writes to sys.stderr.

    Used so that mlx_whisper's verbose=True per-segment progress output goes to
    stderr (alongside other progress messages) instead of polluting stdout (which
    carries the final transcript).
    """
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout


def _mlx_model_cache_path(hf_repo: str) -> Path | None:
    """Return the local cache directory for an MLX HuggingFace repo, or None if not cached.

    Uses the HuggingFace hub cache layout:
        ~/.cache/huggingface/hub/models--<org>--<repo>/snapshots/<hash>/

    Args:
        hf_repo: HuggingFace repo ID, e.g. ``"mlx-community/whisper-tiny-mlx"``.

    Returns:
        Path to the snapshot directory if fully cached, None otherwise.
    """
    try:
        from huggingface_hub import try_to_load_from_cache  # type: ignore[import-untyped]

        # Probe for a file that every mlx-whisper model has
        result = try_to_load_from_cache(hf_repo, "config.json", cache_dir=_HF_CACHE_ROOT)
        if result and not isinstance(result, type(None)):
            # result is a full file path; the snapshot dir is two levels up
            return Path(str(result)).parent
    except Exception:
        pass
    return None


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


def _transcribe_mlx(
    audio_path: Path,
    model_name: str,
    vad_filter: bool,
    verbose: bool,
) -> TranscriptResult:
    """Transcribe using mlx-whisper (Apple Silicon Metal/ANE GPU backend).

    Requires the ``mlx`` optional dependency group:
        uv sync --extra mlx

    Args:
        audio_path: Path to the audio file.
        model_name: Whisper model name (e.g. "turbo", "large-v3").
        vad_filter: Not supported by mlx-whisper; ignored with a warning.
        verbose: If True, write progress messages to stderr.

    Returns:
        A TranscriptResult with segments, language, and duration.

    Raises:
        click.ClickException: If mlx-whisper is not installed or transcription fails.
    """
    try:
        import mlx_whisper  # type: ignore[import-untyped]
    except ImportError as exc:
        raise click.ClickException(
            "mlx-whisper is not installed. Install it with:\n"
            "  uv sync --extra mlx\n\n"
            "This is required for GPU-accelerated transcription on Apple Silicon.\n"
            "Alternatively, force CPU mode with: --device cpu"
        ) from exc

    hf_repo = MLX_MODEL_REPOS.get(model_name)
    if hf_repo is None:
        raise click.ClickException(
            f"Model '{model_name}' has no MLX repo mapping. "
            "Use --device cpu to fall back to faster-whisper."
        )

    if vad_filter:
        click.echo(
            "  Warning: --vad is not supported with the MLX backend and will be ignored.",
            err=True,
        )

    if verbose:
        # Check whether the model weights are already in the HF cache
        cached_path = _mlx_model_cache_path(hf_repo)
        if cached_path:
            click.echo(
                f"  Model '{model_name}' loaded from cache:",
                err=True,
            )
            click.echo(f"    {cached_path}", err=True)
        else:
            click.echo(
                f"  Model '{model_name}' not in cache — downloading from HuggingFace...",
                err=True,
            )
            click.echo(f"    Repo : {hf_repo}", err=True)
            click.echo(f"    Cache: {_HF_CACHE_ROOT}", err=True)

        click.echo("  Transcribing audio segments (Apple Silicon GPU):", err=True)

    log.debug("MLX transcribe: path=%s model=%s repo=%s", audio_path, model_name, hf_repo)

    try:
        # When verbose, mlx_whisper prints each decoded segment as "[HH:MM:SS --> HH:MM:SS] text".
        # Redirect stdout → stderr so that output appears alongside other progress messages
        # and does NOT pollute the transcript written to stdout.
        stdout_ctx = _stdout_to_stderr() if verbose else contextlib.nullcontext()
        with stdout_ctx:
            raw = mlx_whisper.transcribe(
                str(audio_path),
                path_or_hf_repo=hf_repo,
                verbose=verbose,  # None = silent, True = per-segment timestamps + text
            )
    except Exception as exc:
        log.exception("mlx-whisper transcription failed for path=%s", audio_path)
        raise click.ClickException(f"mlx-whisper transcription failed: {exc}") from exc

    segments: list[TranscriptSegment] = []
    for seg in raw.get("segments", []):
        segments.append(
            TranscriptSegment(
                start=float(seg["start"]),
                end=float(seg["end"]),
                text=seg["text"],
            )
        )

    duration = float(raw["segments"][-1]["end"]) if raw.get("segments") else 0.0
    result = TranscriptResult(
        segments=segments,
        language=raw.get("language", "unknown"),
        duration=duration,
    )

    if verbose:
        from youtube_transcriber.utils import format_duration
        click.echo("", err=True)
        click.echo(
            f"  Transcription complete. "
            f"Language: {result.language} | "
            f"Duration: {format_duration(result.duration)} | "
            f"Segments: {len(segments)}",
            err=True,
        )

    return result


def transcribe_audio(
    audio_path: Path,
    model_name: str = DEFAULT_MODEL,
    device: str = "auto",
    compute_type: str = "auto",
    beam_size: int = 5,
    num_threads: int = 4,
    vad_filter: bool = False,
    verbose: bool = True,
) -> TranscriptResult:
    """Transcribe an audio file using the best available backend.

    Automatically selects the transcription backend based on ``device``:

    * ``"mps"``  → mlx-whisper (Apple Silicon GPU via Metal/ANE).  Requires
      the ``mlx`` optional dependency: ``uv sync --extra mlx``.
    * ``"cuda"`` → faster-whisper with float16 on an NVIDIA GPU.
    * ``"cpu"``  → faster-whisper with int8 quantization (all platforms).
    * ``"auto"`` → auto-detects: mps → cuda → cpu.

    Downloads the specified model on first use (cached in HuggingFace cache).

    Args:
        audio_path: Path to the audio file to transcribe.
        model_name: Whisper model name (e.g. "turbo", "large-v3", "small").
        device: Compute device — "auto", "mps", "cuda", or "cpu".
        compute_type: Quantization type for faster-whisper — "auto", "float16",
            "int8_float16", "int8". Ignored when using the MLX backend.
        beam_size: Beam size for beam search decoding (higher = more accurate, slower).
            Ignored when using the MLX backend (which uses greedy decoding).
        num_threads: Maximum CPU threads for faster-whisper. Defaults to 4 to
            avoid pegging all cores. Ignored when using the MLX (mps) backend.
        vad_filter: Enable Silero VAD pre-filtering to strip silence.
            Not supported by the MLX backend; ignored with a warning.
        verbose: If True, write progress messages to stderr.

    Returns:
        A TranscriptResult containing segments, detected language, and duration.

    Raises:
        click.ClickException: If transcription fails.
    """
    from youtube_transcriber.utils import detect_device

    # Resolve device
    resolved_device = detect_device() if device == "auto" else device

    # Route to MLX backend for Apple Silicon
    if resolved_device == "mps":
        return _transcribe_mlx(audio_path, model_name, vad_filter=vad_filter, verbose=verbose)

    if verbose:
        device_label = "GPU (CUDA)" if resolved_device == "cuda" else "CPU"
        click.echo(
            f"  Loading model '{model_name}' on {device_label} "
            f"(threads: {num_threads})...",
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
            cpu_threads=num_threads,
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
