"""Output formatters for transcript results.

Each public function accepts a TranscriptResult and returns a formatted string
in the corresponding output format (plain text, JSON, SRT, or WebVTT).
"""

from __future__ import annotations

import json

from youtube_transcriber.transcriber import TranscriptResult
from youtube_transcriber.utils import seconds_to_timestamp


def format_text(result: TranscriptResult) -> str:
    """Format transcript as clean plain text.

    Joins all segment texts with single-space separation. This is the default
    output format — ideal for piping into LLMs.

    Args:
        result: The TranscriptResult to format.

    Returns:
        A single string containing the full transcript.
    """
    return "\n\n".join(seg.text.strip() for seg in result.segments if seg.text.strip())


def format_json(result: TranscriptResult) -> str:
    """Format transcript as JSON with timestamps and metadata.

    Args:
        result: The TranscriptResult to format.

    Returns:
        A pretty-printed JSON string with "language", "duration", and "segments".

    Example output::

        {
          "language": "en",
          "duration": 423.5,
          "segments": [
            {"start": 0.0, "end": 4.2, "text": "Hello, world."},
            ...
          ]
        }
    """
    output = {
        "language": result.language,
        "duration": round(result.duration, 3),
        "segments": [
            {
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
            }
            for seg in result.segments
        ],
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


def format_srt(result: TranscriptResult) -> str:
    """Format transcript as an SRT (SubRip) subtitle file.

    Args:
        result: The TranscriptResult to format.

    Returns:
        A string in SRT format with sequential indices and HH:MM:SS,mmm timestamps.

    Example output::

        1
        00:00:00,000 --> 00:00:04,200
        Hello, world.

        2
        00:00:04,500 --> 00:00:08,100
        This is the second subtitle.
    """
    blocks: list[str] = []
    for index, seg in enumerate(result.segments, start=1):
        start_ts = seconds_to_timestamp(seg.start, vtt=False)
        end_ts = seconds_to_timestamp(seg.end, vtt=False)
        text = seg.text.strip()
        if text:
            blocks.append(f"{index}\n{start_ts} --> {end_ts}\n{text}")
    return "\n\n".join(blocks)


def format_vtt(result: TranscriptResult) -> str:
    """Format transcript as a WebVTT subtitle file.

    Args:
        result: The TranscriptResult to format.

    Returns:
        A string in WebVTT format, starting with the required "WEBVTT" header.

    Example output::

        WEBVTT

        00:00:00.000 --> 00:00:04.200
        Hello, world.

        00:00:04.500 --> 00:00:08.100
        This is the second subtitle.
    """
    blocks: list[str] = ["WEBVTT\n"]
    for seg in result.segments:
        start_ts = seconds_to_timestamp(seg.start, vtt=True)
        end_ts = seconds_to_timestamp(seg.end, vtt=True)
        text = seg.text.strip()
        if text:
            blocks.append(f"{start_ts} --> {end_ts}\n{text}")
    return "\n\n".join(blocks)


FORMAT_FUNCTIONS = {
    "text": format_text,
    "json": format_json,
    "srt": format_srt,
    "vtt": format_vtt,
}
