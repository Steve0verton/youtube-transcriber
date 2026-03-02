"""Command-line interface for youtube-transcriber.

Entry point: `youtube-transcriber`

Commands:
    transcribe  Download and transcribe a YouTube video.
    models      List available Whisper models with memory requirements.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from youtube_transcriber import __version__
from youtube_transcriber.formatters import FORMAT_FUNCTIONS
from youtube_transcriber.transcriber import AVAILABLE_MODELS, DEFAULT_MODEL
from youtube_transcriber.utils import check_ffmpeg, is_youtube_url


@click.group()
@click.version_option(__version__, prog_name="youtube-transcriber")
def cli() -> None:
    """youtube-transcriber — download and locally transcribe YouTube videos.

    Transcript text is written to stdout; progress messages go to stderr.
    This makes it easy to pipe the transcript into an LLM or file:

    \b
      youtube-transcriber transcribe "https://youtu.be/..." > transcript.txt
      youtube-transcriber transcribe "https://youtu.be/..." 2>/dev/null | llm ...
    """


@cli.command()
@click.argument("url")
@click.option(
    "--model",
    "-m",
    default=DEFAULT_MODEL,
    show_default=True,
    metavar="MODEL",
    help=(
        f"Whisper model to use. Choices: {', '.join(AVAILABLE_MODELS.keys())}. "
        "Larger models are slower but more accurate."
    ),
)
@click.option(
    "--format",
    "-f",
    "output_format",
    default="text",
    show_default=True,
    type=click.Choice(list(FORMAT_FUNCTIONS.keys()), case_sensitive=False),
    help="Output format for the transcript.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    default=None,
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    help="Write transcript to this file instead of stdout.",
)
@click.option(
    "--device",
    "-d",
    default="auto",
    show_default=True,
    type=click.Choice(["auto", "cuda", "cpu"], case_sensitive=False),
    help=(
        "Compute device. 'auto' uses CUDA if available, otherwise CPU."
    ),
)
@click.option(
    "--compute-type",
    default="auto",
    show_default=True,
    type=click.Choice(
        ["auto", "float16", "int8_float16", "int8", "float32"],
        case_sensitive=False,
    ),
    help=(
        "Model quantization. 'auto' picks float16 for GPU, int8 for CPU."
    ),
)
@click.option(
    "--beam-size",
    default=5,
    show_default=True,
    type=int,
    help="Beam size for decoding (higher = more accurate, slower).",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress all progress output (stderr). Only the transcript is printed.",
)
def transcribe(
    url: str,
    model: str,
    output_format: str,
    output_path: Path | None,
    device: str,
    compute_type: str,
    beam_size: int,
    quiet: bool,
) -> None:
    """Download and transcribe a YouTube video.

    URL can be any valid YouTube URL format:
    standard watch URLs, youtu.be short URLs, Shorts URLs, etc.

    \b
    Examples:
      youtube-transcriber transcribe "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
      youtube-transcriber transcribe "https://youtu.be/dQw4w9WgXcQ" --model small
      youtube-transcriber transcribe "https://youtu.be/..." --format srt -o subs.srt
      youtube-transcriber transcribe "https://youtu.be/..." --quiet > transcript.txt
    """
    verbose = not quiet

    # Validate URL
    if not is_youtube_url(url):
        raise click.BadParameter(
            f"'{url}' does not appear to be a YouTube URL.\n"
            "Supported formats: youtube.com/watch?v=..., youtu.be/..., youtube.com/shorts/...",
            param_hint="URL",
        )

    # Validate model name
    if model not in AVAILABLE_MODELS:
        raise click.BadParameter(
            f"Unknown model '{model}'.\n"
            f"Run 'youtube-transcriber models' to see available options.",
            param_hint="--model",
        )

    # Check ffmpeg before doing any work
    check_ffmpeg()

    if verbose:
        click.echo(f"youtube-transcriber v{__version__}", err=True)
        click.echo(f"  URL:    {url}", err=True)
        click.echo(f"  Model:  {model}", err=True)
        click.echo(f"  Format: {output_format}", err=True)
        click.echo(f"  Device: {device}", err=True)
        click.echo("", err=True)
        click.echo("[ Step 1/2 ] Downloading audio...", err=True)

    from youtube_transcriber.downloader import download_audio
    from youtube_transcriber.transcriber import transcribe_audio

    try:
        with download_audio(url, verbose=verbose) as audio_path:
            if verbose:
                click.echo("", err=True)
                click.echo("[ Step 2/2 ] Transcribing...", err=True)

            result = transcribe_audio(
                audio_path,
                model_name=model,
                device=device,
                compute_type=compute_type,
                beam_size=beam_size,
                verbose=verbose,
            )

    except SystemExit:
        sys.exit(1)

    # Format the transcript
    formatter = FORMAT_FUNCTIONS[output_format]
    transcript = formatter(result)

    if verbose:
        click.echo("", err=True)

    # Write output
    if output_path is not None:
        output_path.write_text(transcript, encoding="utf-8")
        if verbose:
            click.echo(f"Transcript saved to: {output_path}", err=True)
    else:
        click.echo(transcript)


@cli.command()
def models() -> None:
    """List available Whisper models with size and memory requirements.

    \b
    Model selection guide:
      tiny / base   — Quick tests, very fast, lower accuracy
      small         — Good balance for short clips
      medium        — Better accuracy, moderate resources
      turbo         — DEFAULT: optimized large-v3 at 8× speed, ~6GB VRAM
      large-v3      — Highest accuracy, ~10GB VRAM
      distil-*      — Fast distilled models (English-optimized)
    """
    click.echo(f"\nAvailable Whisper models (default: {DEFAULT_MODEL})\n")

    # Column widths
    col_model = 20
    col_params = 8
    col_vram = 8

    header = (
        f"  {'Model':<{col_model}} {'Params':<{col_params}} {'VRAM':<{col_vram}} Notes"
    )
    click.echo(header)
    click.echo("  " + "-" * (col_model + col_params + col_vram + 30))

    for name, info in AVAILABLE_MODELS.items():
        default_marker = " (default)" if name == DEFAULT_MODEL else ""
        notes = info["notes"] + default_marker if info["notes"] else default_marker.strip()
        click.echo(
            f"  {name:<{col_model}} {info['params']:<{col_params}} "
            f"{info['vram']:<{col_vram}} {notes}"
        )

    click.echo()
    click.echo(
        "  Models are downloaded from HuggingFace on first use and cached locally.\n"
        "  Cache location: ~/.cache/huggingface/hub/\n"
    )
