"""YouTube audio downloader using yt-dlp.

Provides a context-manager-based interface that downloads the best available audio
from a YouTube URL to a temporary file, then cleans up automatically on exit.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import click
import yt_dlp

log = logging.getLogger(__name__)


def _find_js_runtime() -> dict | None:
    """Return a yt-dlp ``js_runtimes`` dict for the first available JS runtime.

    YouTube requires JavaScript challenge solving for reliable format extraction.
    yt-dlp only enables Deno by default; this probes for Node, Deno, and Bun so
    the download works regardless of which runtime the user has installed.

    macOS GUI apps (like Claude Desktop) launch with a stripped system PATH that
    skips shell config files, so nvm-managed runtimes may not appear in
    ``shutil.which``.  We therefore also check a set of well-known fallback paths
    so that nvm/volta/fnm installs are still discovered even without PATH injection.

    Returns:
        A dict suitable for the yt-dlp ``js_runtimes`` option, e.g.
        ``{"node": {"path": "/opt/homebrew/bin/node"}}``, or ``None`` if no
        supported runtime is found.
    """
    # Common fallback locations when the runtime is not on the active PATH.
    # These cover: Homebrew (Apple Silicon / Intel), nvm defaults, volta, fnm.
    _FALLBACK_PATHS: dict[str, list[str]] = {
        "node": [
            "/opt/homebrew/bin/node",           # Homebrew, Apple Silicon
            "/usr/local/bin/node",              # Homebrew, Intel
            str(Path.home() / ".nvm/versions/node"),  # searched below
            str(Path.home() / ".volta/bin/node"),
            str(Path.home() / ".fnm/aliases/default/bin/node"),
        ],
        "deno": [
            "/opt/homebrew/bin/deno",
            "/usr/local/bin/deno",
            str(Path.home() / ".deno/bin/deno"),
        ],
        "bun": [
            "/opt/homebrew/bin/bun",
            "/usr/local/bin/bun",
            str(Path.home() / ".bun/bin/bun"),
        ],
    }

    for runtime in ("node", "deno", "bun"):
        # 1. Trust the active PATH first (works in terminal sessions)
        path = shutil.which(runtime)
        if path:
            log.debug("Found %s on PATH: %s", runtime, path)
            return {runtime: {"path": path}}

        # 2. Check static fallback paths
        for candidate in _FALLBACK_PATHS.get(runtime, []):
            # nvm stores per-version bins under ~/.nvm/versions/node/<ver>/bin/node
            if runtime == "node" and "/.nvm/versions/node" in candidate:
                # Walk the nvm versions directory and pick the most recent
                nvm_versions_dir = Path(candidate)
                if nvm_versions_dir.is_dir():
                    # Sort by version directory name, take the last (highest)
                    versions = sorted(nvm_versions_dir.iterdir())
                    for ver in reversed(versions):
                        node_bin = ver / "bin" / "node"
                        if node_bin.is_file():
                            log.debug("Found %s via nvm fallback: %s", runtime, node_bin)
                            return {runtime: {"path": str(node_bin)}}
                continue

            if Path(candidate).is_file():
                log.debug("Found %s via fallback path: %s", runtime, candidate)
                return {runtime: {"path": candidate}}

    log.debug("No JS runtime found on PATH or in fallback locations")
    return None


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

        # YouTube requires JS challenge solving; wire in the first available runtime.
        # Without this, yt-dlp may silently miss formats or fail entirely on some videos.
        js_runtime = _find_js_runtime()
        if js_runtime:
            ydl_opts["js_runtimes"] = js_runtime
            ydl_opts["remote_components"] = {"ejs:github"}
            log.debug("JS runtime selected: %s", js_runtime)
        else:
            log.warning(
                "No JS runtime (node/deno/bun) found on PATH. "
                "YouTube format extraction may be incomplete. "
                "Install Node.js with: brew install node"
            )

        log.debug("Starting yt-dlp download: url=%s opts=%s", url, {k: v for k, v in ydl_opts.items() if k != "progress_hooks"})

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    log.error("yt-dlp returned None for url=%s", url)
                    raise click.ClickException(
                        f"yt-dlp could not retrieve info for URL: {url}"
                    )

                log.debug(
                    "yt-dlp info: id=%s title=%r duration=%ss format=%s",
                    info.get("id"), info.get("title"), info.get("duration"), info.get("format"),
                )

                # Find the downloaded file in the temp directory
                downloaded_files = list(Path(tmpdir).iterdir())
                log.debug("Files in tmpdir after download: %s", downloaded_files)
                if not downloaded_files:
                    log.error("No audio file found in tmpdir=%s after yt-dlp download", tmpdir)
                    raise click.ClickException(
                        "yt-dlp reported success but no audio file was found in "
                        f"the temp directory. URL: {url}"
                    )

                # Prefer .wav (post-processed), then grab whatever is there
                wav_files = [f for f in downloaded_files if f.suffix == ".wav"]
                audio_path = wav_files[0] if wav_files else downloaded_files[0]
                log.debug("Selected audio file: %s (%.1f MB)", audio_path, audio_path.stat().st_size / 1_048_576)

                if verbose:
                    click.echo(f"  Audio ready: {audio_path.name}", err=True)

                yield audio_path

        except yt_dlp.utils.DownloadError as exc:
            log.exception("yt-dlp DownloadError for url=%s", url)
            raise click.ClickException(
                f"Failed to download audio from YouTube.\n\n"
                f"Error: {exc}\n\n"
                "Tips:\n"
                "  • Check that the URL is valid and the video is public\n"
                "  • For age-gated videos, try: --cookies-from-browser chrome\n"
                "  • Make sure yt-dlp is up to date: uv run pip install -U yt-dlp\n"
                "  • Install Node.js to enable YouTube challenge solving: brew install node"
                ) from exc
