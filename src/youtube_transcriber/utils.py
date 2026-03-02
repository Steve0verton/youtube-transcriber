"""Utility helpers for youtube-transcriber.

Provides URL validation, video ID extraction, GPU availability detection,
ffmpeg presence checks, and run-lock helpers to prevent parallel execution.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Lock file used to prevent multiple concurrent transcription processes
_LOCK_FILE: Path = Path(tempfile.gettempdir()) / "youtube-transcriber.lock"

# Regex patterns for YouTube URL formats
_YOUTUBE_ID_PATTERNS: list[re.Pattern[str]] = [
    # Standard watch URL: https://www.youtube.com/watch?v=VIDEO_ID
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([A-Za-z0-9_-]{11})"),
    # Short URL: https://youtu.be/VIDEO_ID
    re.compile(r"(?:https?://)?youtu\.be/([A-Za-z0-9_-]{11})"),
    # Shorts URL: https://www.youtube.com/shorts/VIDEO_ID
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})"),
    # Embedded URL: https://www.youtube.com/embed/VIDEO_ID
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{11})"),
    # Live URL: https://www.youtube.com/live/VIDEO_ID
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/live/([A-Za-z0-9_-]{11})"),
]

_YOUTUBE_VALID_HOSTS: frozenset[str] = frozenset(
    [
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "www.youtu.be",
    ]
)


def extract_video_id(url: str) -> str | None:
    """Extract the 11-character YouTube video ID from a URL.

    Args:
        url: A YouTube URL in any common format (watch, short, shorts, embed, live).

    Returns:
        The 11-character video ID string, or None if not found.
    """
    for pattern in _YOUTUBE_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)

    # Fallback: parse query string for ?v= parameter
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if "v" in params and len(params["v"][0]) == 11:
            return params["v"][0]
    except Exception:
        pass

    return None


def is_youtube_url(url: str) -> bool:
    """Return True if the URL appears to be a valid YouTube URL.

    Uses urlparse to extract the hostname so that URLs like
    ``https://youtube.com.evil.com/...`` are correctly rejected.

    Args:
        url: The URL string to check.

    Returns:
        True if the URL host is a known YouTube domain, False otherwise.
    """
    try:
        # Ensure a scheme is present so urlparse extracts the hostname correctly
        normalized = url if "://" in url else f"https://{url}"
        host = urlparse(normalized).hostname or ""
        return host in _YOUTUBE_VALID_HOSTS
    except Exception:
        return False


def check_ffmpeg() -> None:
    """Verify that ffmpeg is installed and accessible on PATH.

    Raises:
        SystemExit: If ffmpeg is not found, prints an installation hint and exits.
    """
    if shutil.which("ffmpeg") is None:
        import click

        raise click.ClickException(
            "ffmpeg is not installed or not on PATH.\n\n"
            "Install it with:\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  macOS:         brew install ffmpeg\n"
            "  Windows:       https://ffmpeg.org/download.html\n\n"
            "ffmpeg is required by yt-dlp to extract audio from downloaded video."
        )


def is_apple_silicon() -> bool:
    """Return True if running on Apple Silicon (arm64 macOS).

    Used to decide whether to route transcription through mlx-whisper
    (Metal GPU-accelerated) instead of faster-whisper (CPU-only on Apple).

    Returns:
        True on macOS with an arm64 (M-series) processor, False otherwise.
    """
    return sys.platform == "darwin" and platform.machine() == "arm64"


def detect_device() -> str:
    """Auto-detect the best available compute device.

    Priority:
      1. Apple Silicon → "mps"  (mlx-whisper Metal/ANE backend)
      2. CUDA GPU      → "cuda" (faster-whisper CUDA backend)
      3. Fallback      → "cpu"  (faster-whisper CPU backend)

    Returns:
        One of "mps", "cuda", or "cpu".
    """
    if is_apple_silicon():
        return "mps"
    try:
        import ctranslate2  # type: ignore[import-untyped]

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except (ImportError, Exception):
        pass
    return "cpu"


def acquire_run_lock() -> bool:
    """Attempt to acquire a process-level lock to prevent parallel runs.

    Writes the current PID to a temp lock file. If the file already exists
    and the recorded PID is still alive, returns False (lock not acquired).
    Stale lock files (crashed process) are silently overwritten.

    Returns:
        True if the lock was successfully acquired, False if another
        youtube-transcriber process is already running.
    """
    if _LOCK_FILE.exists():
        try:
            pid = int(_LOCK_FILE.read_text().strip())
            os.kill(pid, 0)  # signal 0: check existence without sending a signal
            return False  # process is alive
        except (ValueError, OSError):
            pass  # stale lock — process is gone
    _LOCK_FILE.write_text(str(os.getpid()))
    return True


def release_run_lock() -> None:
    """Release the process-level run lock if it belongs to the current process."""
    try:
        if _LOCK_FILE.exists():
            pid_text = _LOCK_FILE.read_text().strip()
            if pid_text == str(os.getpid()):
                _LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        A string like "1h 23m 45s", "4m 5s", or "37s".
    """
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def seconds_to_timestamp(seconds: float, vtt: bool = False) -> str:
    """Convert seconds to an SRT/VTT timestamp string.

    Args:
        seconds: Time in seconds.
        vtt: If True, use WebVTT format (period as millisecond separator).
             If False, use SRT format (comma as millisecond separator).

    Returns:
        A timestamp string like "00:01:23,456" (SRT) or "00:01:23.456" (VTT).
    """
    millis = int((seconds % 1) * 1000)
    total_secs = int(seconds)
    hours, remainder = divmod(total_secs, 3600)
    minutes, secs = divmod(remainder, 60)
    sep = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"
