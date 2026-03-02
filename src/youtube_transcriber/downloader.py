"""YouTube audio downloader using yt-dlp.

Provides a context-manager-based interface that downloads the best available audio
from a YouTube URL to a temporary file, then cleans up automatically on exit.
"""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import click
import yt_dlp


class _ProgressHook:
    """Callback hook passed to yt-dlp to report download progress to stderr."""

    def __init__(self, verbose: bool = True) -> None:
        self._verbose = verbose
        self._reported_downloading = False

    def __call__(self, d: dict) -> None:
        if not self._verbose:
            return

        status = d.get("status")
        if status == "downloading" and not self._reported_downloading:
            filename = Path(d.get("filename", "")).name
            click.echo(f"  Downloading audio: {filename}", err=True)
            self._reported_downloading = True
        elif status == "finished":
            filepath = Path(d.get("filename", ""))
            size_mb = filepath.stat().st_size / 1_048_576 if filepath.exists() else 0
            click.echo(f"  Download complete ({size_mb:.1f} MB). Extracting audio...", err=True)
        elif status == "error":
            click.echo("  Download error.", err=True)


@contextmanager
def download_audio(url: str, verbose: bool = True) -> Generator[Path, None, None]:
    """Download the best audio stream from a YouTube URL to a temporary file.

    Uses yt-dlp to download and extract audio. The temporary file is deleted
    automatically when the context manager exits.

    Args:
        url: A YouTube URL (any supported format).
        verbose: If True, progress messages are written to stderr.

    Yields:
        A Path pointing to the downloaded audio file (m4a or best available).

    Raises:
        click.ClickException: If the download fails for any reason.

    Example:
        with download_audio("https://youtube.com/watch?v=...") as audio_path:
            result = transcribe_audio(audio_path, model_name="turbo", device="auto")
    """
    # Create a temp directory; yt-dlp will write to it
    with tempfile.TemporaryDirectory(prefix="yt_transcriber_") as tmpdir:
        output_template = str(Path(tmpdir) / "%(id)s.%(ext)s")

        ydl_opts: dict = {
            # Pull best audio-only stream; fall back to best available
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [_ProgressHook(verbose=verbose)],
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                    "preferredquality": "0",  # highest quality
                }
            ],
            # Avoid leaving partial files on failure
            "nopart": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    raise click.ClickException(
                        f"yt-dlp could not retrieve info for URL: {url}"
                    )

                # Find the downloaded file in the temp directory
                downloaded_files = list(Path(tmpdir).iterdir())
                if not downloaded_files:
                    raise click.ClickException(
                        "yt-dlp reported success but no audio file was found in "
                        f"the temp directory. URL: {url}"
                    )

                # Prefer .wav (post-processed), then grab whatever is there
                wav_files = [f for f in downloaded_files if f.suffix == ".wav"]
                audio_path = wav_files[0] if wav_files else downloaded_files[0]

                if verbose:
                    click.echo(f"  Audio ready: {audio_path.name}", err=True)

                yield audio_path

        except yt_dlp.utils.DownloadError as exc:
            raise click.ClickException(
                f"Failed to download audio from YouTube.\n\n"
                f"Error: {exc}\n\n"
                "Tips:\n"
                "  • Check that the URL is valid and the video is public\n"
                "  • For age-gated videos, try: --cookies-from-browser chrome\n"
                "  • Make sure yt-dlp is up to date: uv run pip install -U yt-dlp"
            ) from exc
