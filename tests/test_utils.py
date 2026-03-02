"""Tests for youtube_transcriber.utils — URL parsing and helper functions."""


from youtube_transcriber.utils import (
    extract_video_id,
    format_duration,
    is_youtube_url,
    seconds_to_timestamp,
)


class TestExtractVideoId:
    """Tests for extract_video_id()."""

    # --- Valid URLs that should return an ID ---

    def test_standard_watch_url(self):
        vid = extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert vid == "dQw4w9WgXcQ"

    def test_watch_url_no_www(self):
        vid = extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ")
        assert vid == "dQw4w9WgXcQ"

    def test_watch_url_with_extra_params(self):
        vid = extract_video_id(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s&list=PL123"
        )
        assert vid == "dQw4w9WgXcQ"

    def test_short_url(self):
        vid = extract_video_id("https://youtu.be/dQw4w9WgXcQ")
        assert vid == "dQw4w9WgXcQ"

    def test_short_url_with_timestamp(self):
        vid = extract_video_id("https://youtu.be/dQw4w9WgXcQ?t=30")
        assert vid == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        vid = extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ")
        assert vid == "dQw4w9WgXcQ"

    def test_embed_url(self):
        vid = extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ")
        assert vid == "dQw4w9WgXcQ"

    def test_live_url(self):
        vid = extract_video_id("https://www.youtube.com/live/dQw4w9WgXcQ")
        assert vid == "dQw4w9WgXcQ"

    def test_no_scheme(self):
        vid = extract_video_id("youtube.com/watch?v=dQw4w9WgXcQ")
        assert vid == "dQw4w9WgXcQ"

    # --- Invalid URLs that should return None ---

    def test_not_a_url(self):
        assert extract_video_id("not a url") is None

    def test_empty_string(self):
        assert extract_video_id("") is None

    def test_non_youtube_url(self):
        assert extract_video_id("https://vimeo.com/123456789") is None

    def test_youtube_channel_url(self):
        # Channel URLs don't have a video ID
        assert extract_video_id("https://www.youtube.com/@channelname") is None

    def test_youtube_playlist_url_no_video(self):
        # Playlist URL without v= param
        assert extract_video_id("https://www.youtube.com/playlist?list=PLxyz") is None


class TestIsYoutubeUrl:
    """Tests for is_youtube_url()."""

    def test_www_youtube_com(self):
        assert is_youtube_url("https://www.youtube.com/watch?v=abc12345678") is True

    def test_youtu_be(self):
        assert is_youtube_url("https://youtu.be/abc12345678") is True

    def test_youtube_without_www(self):
        assert is_youtube_url("https://youtube.com/watch?v=abc") is True

    def test_not_youtube(self):
        assert is_youtube_url("https://vimeo.com/123") is False

    def test_empty(self):
        assert is_youtube_url("") is False

    def test_random_string(self):
        assert is_youtube_url("hello world") is False

    def test_subdomain_spoof_rejected(self):
        # A URL with youtube.com as a subdomain of another domain must be rejected
        assert is_youtube_url("https://youtube.com.evil.com/watch?v=abc") is False

    def test_path_spoof_rejected(self):
        # youtube.com appearing only in the path must be rejected
        assert is_youtube_url("https://evil.com/youtube.com/watch?v=abc") is False


class TestFormatDuration:
    """Tests for format_duration()."""

    def test_seconds_only(self):
        assert format_duration(37.0) == "37s"

    def test_minutes_and_seconds(self):
        assert format_duration(245.0) == "4m 5s"

    def test_hours_minutes_seconds(self):
        assert format_duration(5025.0) == "1h 23m 45s"

    def test_exactly_one_hour(self):
        assert format_duration(3600.0) == "1h 0m 0s"

    def test_zero(self):
        assert format_duration(0.0) == "0s"

    def test_fractional_seconds_truncated(self):
        # Sub-second precision is truncated, not rounded
        assert format_duration(37.9) == "37s"


class TestSecondsToTimestamp:
    """Tests for seconds_to_timestamp()."""

    def test_srt_format_basic(self):
        ts = seconds_to_timestamp(0.0, vtt=False)
        assert ts == "00:00:00,000"

    def test_srt_format_with_millis(self):
        ts = seconds_to_timestamp(1.5, vtt=False)
        assert ts == "00:00:01,500"

    def test_srt_format_hours(self):
        ts = seconds_to_timestamp(3723.456, vtt=False)
        assert ts == "01:02:03,456"

    def test_vtt_format_uses_period(self):
        ts = seconds_to_timestamp(0.0, vtt=True)
        assert ts == "00:00:00.000"

    def test_vtt_format_with_millis(self):
        ts = seconds_to_timestamp(1.5, vtt=True)
        assert ts == "00:00:01.500"

    def test_srt_vs_vtt_only_separator_differs(self):
        srt = seconds_to_timestamp(42.123, vtt=False)
        vtt = seconds_to_timestamp(42.123, vtt=True)
        assert srt.replace(",", ".") == vtt
