"""Tests for youtube_transcriber.formatters — output format functions."""

import json

import pytest

from youtube_transcriber.formatters import (
    format_json,
    format_srt,
    format_text,
    format_vtt,
)
from youtube_transcriber.transcriber import TranscriptResult, TranscriptSegment

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_result() -> TranscriptResult:
    """A TranscriptResult with no segments."""
    return TranscriptResult(segments=[], language="en", duration=0.0)


@pytest.fixture
def single_segment_result() -> TranscriptResult:
    """A TranscriptResult with one segment."""
    return TranscriptResult(
        segments=[TranscriptSegment(start=0.0, end=4.2, text=" Hello, world.")],
        language="en",
        duration=4.2,
    )


@pytest.fixture
def multi_segment_result() -> TranscriptResult:
    """A TranscriptResult with multiple segments."""
    return TranscriptResult(
        segments=[
            TranscriptSegment(start=0.0, end=4.2, text=" Hello, world."),
            TranscriptSegment(start=4.5, end=8.1, text=" This is a test."),
            TranscriptSegment(start=8.5, end=12.0, text=" Third segment."),
        ],
        language="es",
        duration=12.0,
    )


# ---------------------------------------------------------------------------
# format_text
# ---------------------------------------------------------------------------


class TestFormatText:
    def test_empty_result(self, empty_result):
        assert format_text(empty_result) == ""

    def test_single_segment(self, single_segment_result):
        output = format_text(single_segment_result)
        assert output == "Hello, world."

    def test_multiple_segments_separated_by_newlines(self, multi_segment_result):
        output = format_text(multi_segment_result)
        assert "Hello, world." in output
        assert "This is a test." in output
        assert "Third segment." in output
        # Paragraphs separated by blank line
        assert "\n\n" in output

    def test_leading_trailing_whitespace_stripped(self):
        result = TranscriptResult(
            segments=[TranscriptSegment(start=0, end=1, text="  spaces everywhere  ")],
            language="en",
            duration=1.0,
        )
        assert format_text(result) == "spaces everywhere"

    def test_blank_segments_skipped(self):
        result = TranscriptResult(
            segments=[
                TranscriptSegment(start=0, end=1, text="Hello"),
                TranscriptSegment(start=1, end=2, text="   "),  # whitespace only
                TranscriptSegment(start=2, end=3, text="World"),
            ],
            language="en",
            duration=3.0,
        )
        output = format_text(result)
        assert "Hello" in output
        assert "World" in output
        # Blank segment should not inject extra blank lines
        parts = [p for p in output.split("\n\n") if p.strip()]
        assert len(parts) == 2


# ---------------------------------------------------------------------------
# format_json
# ---------------------------------------------------------------------------


class TestFormatJson:
    def test_valid_json(self, multi_segment_result):
        output = format_json(multi_segment_result)
        data = json.loads(output)  # should not raise
        assert isinstance(data, dict)

    def test_top_level_keys(self, multi_segment_result):
        data = json.loads(format_json(multi_segment_result))
        assert "language" in data
        assert "duration" in data
        assert "segments" in data

    def test_language_preserved(self, multi_segment_result):
        data = json.loads(format_json(multi_segment_result))
        assert data["language"] == "es"

    def test_duration_preserved(self, multi_segment_result):
        data = json.loads(format_json(multi_segment_result))
        assert data["duration"] == pytest.approx(12.0)

    def test_segment_count(self, multi_segment_result):
        data = json.loads(format_json(multi_segment_result))
        assert len(data["segments"]) == 3

    def test_segment_fields(self, single_segment_result):
        data = json.loads(format_json(single_segment_result))
        seg = data["segments"][0]
        assert "start" in seg
        assert "end" in seg
        assert "text" in seg

    def test_segment_text_stripped(self, single_segment_result):
        data = json.loads(format_json(single_segment_result))
        assert data["segments"][0]["text"] == "Hello, world."

    def test_empty_result(self, empty_result):
        data = json.loads(format_json(empty_result))
        assert data["segments"] == []


# ---------------------------------------------------------------------------
# format_srt
# ---------------------------------------------------------------------------


class TestFormatSrt:
    def test_empty_result(self, empty_result):
        assert format_srt(empty_result) == ""

    def test_starts_with_index_1(self, single_segment_result):
        output = format_srt(single_segment_result)
        assert output.startswith("1\n")

    def test_contains_arrow(self, single_segment_result):
        output = format_srt(single_segment_result)
        assert " --> " in output

    def test_srt_uses_comma_separator(self, single_segment_result):
        output = format_srt(single_segment_result)
        # SRT timestamps use comma for milliseconds, not period
        assert "," in output
        assert "." not in output.split("\n")[1]  # timestamp line

    def test_multiple_segments_indexed(self, multi_segment_result):
        output = format_srt(multi_segment_result)
        assert "1\n" in output
        assert "2\n" in output
        assert "3\n" in output

    def test_text_content_present(self, multi_segment_result):
        output = format_srt(multi_segment_result)
        assert "Hello, world." in output
        assert "This is a test." in output

    def test_blocks_separated_by_blank_line(self, multi_segment_result):
        output = format_srt(multi_segment_result)
        blocks = output.split("\n\n")
        assert len(blocks) == 3

    def test_timestamp_format(self):
        result = TranscriptResult(
            segments=[TranscriptSegment(start=3723.456, end=3727.0, text="Test")],
            language="en",
            duration=3727.0,
        )
        output = format_srt(result)
        assert "01:02:03,456" in output


# ---------------------------------------------------------------------------
# format_vtt
# ---------------------------------------------------------------------------


class TestFormatVtt:
    def test_starts_with_webvtt_header(self, single_segment_result):
        output = format_vtt(single_segment_result)
        assert output.startswith("WEBVTT")

    def test_empty_result_still_has_header(self, empty_result):
        output = format_vtt(empty_result)
        assert "WEBVTT" in output

    def test_uses_period_for_millis(self, single_segment_result):
        output = format_vtt(single_segment_result)
        lines = output.split("\n")
        # Find the timestamp line
        timestamp_line = next(line for line in lines if " --> " in line)
        assert "." in timestamp_line
        assert "," not in timestamp_line

    def test_contains_arrow(self, single_segment_result):
        output = format_vtt(single_segment_result)
        assert " --> " in output

    def test_text_content_present(self, multi_segment_result):
        output = format_vtt(multi_segment_result)
        assert "Hello, world." in output
        assert "This is a test." in output

    def test_no_numeric_block_index(self, multi_segment_result):
        # VTT does not have numeric block indices like SRT does
        output = format_vtt(multi_segment_result)
        lines = output.split("\n")
        # The only content lines should be header, blank lines, timestamps, and text
        for line in lines:
            stripped = line.strip()
            if stripped and stripped != "WEBVTT" and "-->" not in stripped:
                # Should be text, not a bare number
                assert not stripped.isdigit(), (
                    f"VTT output should not have bare index numbers, found: {stripped!r}"
                )
