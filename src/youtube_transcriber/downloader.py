"""YouTube audio downloader using yt-dlp.

Provides a context-manager-based interface that downloads the best available audio
from a YouTube URL to a temporary file, then cleans up automatically on exit.
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import click
import yt_dlp

log = logging.getLogger(__name__)

# yt-dlp ships date-versioned releases (YYYY.MM.DD) many times a month because YouTube
# changes its extraction surface constantly. A stale yt-dlp is by far the most common
# cause of download failure, and it presents as an opaque "HTTP Error 403" or
# "The page needs to be reloaded" rather than as anything version-related.
_YT_DLP_STALE_DAYS = 60


def _yt_dlp_version() -> str:
    """Return the installed yt-dlp version string, or ``"unknown"``."""
    try:
        return str(yt_dlp.version.__version__)
    except Exception:  # pragma: no cover - defensive
        return "unknown"


def _yt_dlp_age_days(today: date | None = None) -> int | None:
    """Return the age in days of the installed yt-dlp release.

    Args:
        today: Reference date, for testing. Defaults to the current date.

    Returns:
        Age in days, or None if the version string is not date-shaped.
    """
    match = re.match(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})", _yt_dlp_version())
    if not match:
        return None
    try:
        released = date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None
    return ((today or date.today()) - released).days


def _warn_if_yt_dlp_stale(verbose: bool) -> None:
    """Warn on stderr when the installed yt-dlp is old enough to likely fail."""
    age = _yt_dlp_age_days()
    if age is None or age < _YT_DLP_STALE_DAYS:
        return
    log.warning("yt-dlp %s is %d days old", _yt_dlp_version(), age)
    if verbose:
        click.echo(
            f"  Note: yt-dlp {_yt_dlp_version()} is {age} days old. YouTube extraction "
            "commonly breaks with a stale yt-dlp —\n"
            "        update it first if this download fails "
            "(uv tool upgrade youtube-transcriber, or uv sync --upgrade-package yt-dlp).",
            err=True,
        )


def _nvm_version_key(path: Path) -> tuple[int, ...]:
    """Return a numeric sort key for an nvm version directory name.

    nvm stores runtimes as ``~/.nvm/versions/node/vMAJOR.MINOR.PATCH``. Sorting
    those names as strings puts ``v9.11.2`` above ``v22.9.0``, so the newest
    install must be found by comparing the numbers instead. Non-version entries
    (nvm also creates alias directories) sort lowest.

    Args:
        path: A directory inside the nvm versions root.

    Returns:
        A tuple of up to three integers, or ``(-1,)`` for a non-version name.
    """
    parts = re.findall(r"\d+", path.name)[:3]
    return tuple(int(p) for p in parts) if parts else (-1,)


def _homebrew_keg_paths(runtime: str) -> list[str]:
    """Return Homebrew versioned-formula binaries for a runtime, newest first.

    A versioned Homebrew formula such as ``node@22`` installs to
    ``/opt/homebrew/opt/node@22/bin/node`` and is symlinked into
    ``/opt/homebrew/bin`` only when it is the linked formula. A machine whose
    only Node is a versioned keg therefore has no ``/opt/homebrew/bin/node`` at
    all, which is invisible to the plain fallback paths.

    Args:
        runtime: Runtime name, e.g. ``"node"``.

    Returns:
        Absolute paths to matching binaries, highest version first.
    """
    matches: list[Path] = []
    for prefix in ("/opt/homebrew/opt", "/usr/local/opt"):
        matches.extend(Path(prefix).glob(f"{runtime}@*/bin/{runtime}"))
    # The version lives in the keg directory name (node@22), two levels up.
    matches.sort(key=lambda p: _nvm_version_key(p.parent.parent), reverse=True)
    return [str(p) for p in matches]


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
            "/opt/homebrew/bin/node",  # Homebrew, Apple Silicon
            "/usr/local/bin/node",  # Homebrew, Intel
            *_homebrew_keg_paths("node"),  # Homebrew versioned formula (node@22)
            str(Path.home() / ".nvm/versions/node"),  # searched below
            str(Path.home() / ".volta/bin/node"),
            str(Path.home() / ".fnm/aliases/default/bin/node"),
        ],
        "deno": [
            "/opt/homebrew/bin/deno",
            "/usr/local/bin/deno",
            *_homebrew_keg_paths("deno"),
            str(Path.home() / ".deno/bin/deno"),
        ],
        "bun": [
            "/opt/homebrew/bin/bun",
            "/usr/local/bin/bun",
            *_homebrew_keg_paths("bun"),
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
                    # Sort by parsed version numbers, highest first. A plain name sort
                    # is lexicographic, which ranks v9.x above v22.x and would select
                    # the oldest installed Node.
                    versions = sorted(nvm_versions_dir.iterdir(), key=_nvm_version_key)
                    for ver in reversed(versions):
                        node_bin = ver / "bin" / "node"
                        if node_bin.is_file():
                            log.debug(
                                "Found %s via nvm fallback: %s", runtime, node_bin
                            )
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
            click.echo(
                f"  Download complete ({size_mb:.1f} MB). Extracting audio...", err=True
            )
        elif status == "error":
            click.echo("  Download error.", err=True)


@contextmanager
def download_audio(
    url: str,
    verbose: bool = True,
    cookies_from_browser: str | None = None,
) -> Generator[Path, None, None]:
    """Download the best audio stream from a YouTube URL to a temporary file.

    Uses yt-dlp to download and extract audio. The temporary file is deleted
    automatically when the context manager exits.

    Args:
        url: A YouTube URL (any supported format). If it carries a playlist
            parameter, only the single video is downloaded.
        verbose: If True, progress messages are written to stderr.
        cookies_from_browser: Optional browser name (e.g. "chrome", "firefox")
            whose cookie store yt-dlp should use, for age-gated or rate-limited
            videos. The value is passed through to yt-dlp unvalidated.

    Yields:
        A Path pointing to the downloaded audio file (m4a or best available).

    Raises:
        click.ClickException: If the download fails for any reason.

    Example:
        with download_audio("https://youtube.com/watch?v=...") as audio_path:
            result = transcribe_audio(audio_path, model_name="turbo", device="auto")
    """
    _warn_if_yt_dlp_stale(verbose)

    # Create a temp directory; yt-dlp will write to it
    with tempfile.TemporaryDirectory(prefix="yt_transcriber_") as tmpdir:
        output_template = str(Path(tmpdir) / "%(id)s.%(ext)s")

        ydl_opts: dict = {
            # Pull best audio-only stream; fall back to best available
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            # `quiet` alone does NOT suppress yt-dlp's download progress bar, and yt-dlp
            # writes it to STDOUT — which is the transcript stream. Without this, every
            # successful download prepends ~765 bytes of "[download]  12.3% of ..." to
            # the transcript an agent reads. Progress is reported by _ProgressHook on
            # stderr instead.
            "noprogress": True,
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
            # A watch URL opened from inside a playlist carries &list=...; yt-dlp's
            # default is to download the whole playlist. This tool transcribes exactly
            # one video per invocation, so the playlist is always ignored.
            "noplaylist": True,
        }

        # Pass browser cookies to bypass age-gates and 403 errors.
        # Opt-in only — not enabled by default. Pass cookies_from_browser='chrome'
        # (or 'firefox' etc.) to use the user's logged-in browser session.
        if cookies_from_browser:
            ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)

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

        log.debug(
            "Starting yt-dlp download: url=%s opts=%s",
            url,
            {k: v for k, v in ydl_opts.items() if k != "progress_hooks"},
        )

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
                    info.get("id"),
                    info.get("title"),
                    info.get("duration"),
                    info.get("format"),
                )

                # Find the downloaded file in the temp directory
                downloaded_files = list(Path(tmpdir).iterdir())
                log.debug("Files in tmpdir after download: %s", downloaded_files)
                if not downloaded_files:
                    log.error(
                        "No audio file found in tmpdir=%s after yt-dlp download", tmpdir
                    )
                    raise click.ClickException(
                        "yt-dlp reported success but no audio file was found in "
                        f"the temp directory. URL: {url}"
                    )

                # Prefer .wav (post-processed), then grab whatever is there
                wav_files = [f for f in downloaded_files if f.suffix == ".wav"]
                audio_path = wav_files[0] if wav_files else downloaded_files[0]
                log.debug(
                    "Selected audio file: %s (%.1f MB)",
                    audio_path,
                    audio_path.stat().st_size / 1_048_576,
                )

                if verbose:
                    click.echo(f"  Audio ready: {audio_path.name}", err=True)

                yield audio_path

        except yt_dlp.utils.DownloadError as exc:
            log.exception("yt-dlp DownloadError for url=%s", url)
            raise click.ClickException(
                f"Failed to download audio from YouTube.\n\n"
                f"Error: {exc}\n\n"
                "Most download failures are a stale yt-dlp. YouTube changes frequently and\n"
                f"yt-dlp ships fixes within days; this run used yt-dlp {_yt_dlp_version()}.\n\n"
                "Tips, in the order worth trying:\n"
                "  1. Update yt-dlp — it is almost always this:\n"
                "       uv tool upgrade youtube-transcriber   (if installed with uv tool)\n"
                "       uv sync --upgrade-package yt-dlp      (from a clone)\n"
                "  2. Check the URL is a valid, public, single video\n"
                "  3. For age-gated or rate-limited videos: --cookies-from-browser chrome\n"
                "  4. Install Node.js for JS challenge solving: brew install node"
            ) from exc
