"""Utility helpers for youtube-transcriber.

Provides URL validation, video ID extraction, GPU availability detection,
and ffmpeg presence checks.
"""

from __future__ import annotations

import re
import shutil
from urllib.parse import parse_qs, urlparse

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


def detect_device() -> str:
    """Auto-detect the best available compute device.

    Tries to import CTranslate2 (used by faster-whisper) to check for CUDA.
    Falls back to CPU if CUDA is unavailable.

    Returns:
        "cuda" if a CUDA-capable GPU is available, otherwise "cpu".
    """
    try:
        import ctranslate2  # type: ignore[import-untyped]

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except (ImportError, Exception):
        pass
    return "cpu"


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
