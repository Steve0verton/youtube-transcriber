"""Logging configuration for youtube-transcriber.

Provides a single ``setup_logging`` function that configures the root logger
with a rotating file handler when the user passes ``--log``.

Usage::

    from youtube_transcriber.logging_config import setup_logging
    setup_logging(log_path)  # then use logging.getLogger(__name__) anywhere
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

# Module-level logger — used only within this file
_log = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path.home() / ".local" / "share" / "youtube-transcriber" / "debug.log"

# Format: timestamp | level | module | message
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_path: Path | None = None, *, level: int = logging.DEBUG) -> Path:
    """Configure file-based debug logging for the entire application.

    Sets up a rotating file handler (5 MB × 3 backups) on the root logger so
    that ``logging.getLogger(__name__)`` in any module automatically writes to
    the log file.  A brief confirmation is printed to stderr.

    Args:
        log_path: Path to write the log file.  Defaults to
            ``~/.local/share/youtube-transcriber/debug.log``.
        level: Logging level for the file handler (default: ``logging.DEBUG``).

    Returns:
        The resolved path where the log file is written.
    """
    resolved = log_path or DEFAULT_LOG_PATH
    resolved.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        resolved,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # Quiet down noisy third-party loggers that flood at DEBUG
    for noisy in ("urllib3", "httpx", "httpcore", "huggingface_hub", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _log.info("Logging initialised → %s", resolved)
    return resolved
