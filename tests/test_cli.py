"""Tests for the CLI contract that agents depend on.

Covers the exit codes, the --output video-ID injection rule, and the stdout/stderr
split. The download and transcription are stubbed out, so nothing here touches the
network or a model.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import pytest
from click.testing import CliRunner

from youtube_transcriber import cli as cli_module
from youtube_transcriber.cli import cli
from youtube_transcriber.transcriber import TranscriptResult, TranscriptSegment

VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
VIDEO_ID = "dQw4w9WgXcQ"


@pytest.fixture
def stub_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Replace ffmpeg check, run lock, download, and transcription with stubs."""
    monkeypatch.setattr(cli_module, "check_ffmpeg", lambda: None)
    monkeypatch.setattr(cli_module, "acquire_run_lock", lambda: True)
    monkeypatch.setattr(cli_module, "release_run_lock", lambda: None)

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00")

    @contextmanager
    def fake_download(url, verbose=True, cookies_from_browser=None):
        yield audio

    def fake_transcribe(audio_path, **kwargs):
        return TranscriptResult(
            segments=[
                TranscriptSegment(start=0.0, end=2.0, text=" Hello world."),
                TranscriptSegment(start=2.0, end=4.0, text=" Second segment."),
            ],
            language="en",
            duration=4.0,
        )

    monkeypatch.setattr(
        "youtube_transcriber.downloader.download_audio", fake_download
    )
    monkeypatch.setattr(
        "youtube_transcriber.transcriber.transcribe_audio", fake_transcribe
    )
    return fake_transcribe


class TestExitCodes:
    """Documented in README and AGENTS.md: 0 success, 1 runtime failure, 2 usage error."""

    def test_help_exits_0(self) -> None:
        assert CliRunner().invoke(cli, ["--help"]).exit_code == 0

    def test_version_exits_0(self) -> None:
        result = CliRunner().invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "youtube-transcriber" in result.output

    def test_bare_invocation_exits_2(self) -> None:
        # Not 0 — click raises NoArgsIsHelpError, which is a UsageError.
        assert CliRunner().invoke(cli, []).exit_code == 2

    def test_models_command_exits_0(self) -> None:
        result = CliRunner().invoke(cli, ["models"])
        assert result.exit_code == 0
        assert "turbo" in result.output

    def test_non_youtube_url_exits_2(self) -> None:
        result = CliRunner().invoke(cli, ["transcribe", "https://example.com/watch?v=x"])
        assert result.exit_code == 2

    def test_garbage_url_exits_2(self) -> None:
        assert CliRunner().invoke(cli, ["transcribe", "not-a-url"]).exit_code == 2

    def test_subdomain_spoof_exits_2(self) -> None:
        result = CliRunner().invoke(
            cli, ["transcribe", "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ"]
        )
        assert result.exit_code == 2

    def test_playlist_url_exits_2(self) -> None:
        # No video ID: this tool transcribes one video per invocation.
        result = CliRunner().invoke(
            cli, ["transcribe", "https://www.youtube.com/playlist?list=PLabc"]
        )
        assert result.exit_code == 2

    def test_unknown_model_exits_2(self, stub_pipeline) -> None:
        result = CliRunner().invoke(cli, ["transcribe", VIDEO_URL, "--model", "nope"])
        assert result.exit_code == 2

    def test_unknown_format_exits_2(self, stub_pipeline) -> None:
        result = CliRunner().invoke(cli, ["transcribe", VIDEO_URL, "--format", "nope"])
        assert result.exit_code == 2

    def test_missing_ffmpeg_exits_1(
        self, monkeypatch: pytest.MonkeyPatch, stub_pipeline
    ) -> None:
        import click

        def boom() -> None:
            raise click.ClickException("ffmpeg is not installed or not on PATH.")

        monkeypatch.setattr(cli_module, "check_ffmpeg", boom)
        result = CliRunner().invoke(cli, ["transcribe", VIDEO_URL])
        assert result.exit_code == 1

    def test_held_run_lock_exits_1(
        self, monkeypatch: pytest.MonkeyPatch, stub_pipeline
    ) -> None:
        monkeypatch.setattr(cli_module, "acquire_run_lock", lambda: False)
        result = CliRunner().invoke(cli, ["transcribe", VIDEO_URL])
        assert result.exit_code == 1

    def test_successful_run_exits_0(self, stub_pipeline) -> None:
        result = CliRunner().invoke(cli, ["transcribe", VIDEO_URL, "--quiet"])
        assert result.exit_code == 0


class TestStdoutContract:
    """stdout carries the transcript and nothing else; progress goes to stderr."""

    def test_transcript_goes_to_stdout(self, stub_pipeline) -> None:
        result = CliRunner().invoke(cli, ["transcribe", VIDEO_URL, "--quiet"])
        assert result.stdout.strip() == "Hello world.\n\nSecond segment."

    def test_quiet_keeps_stdout_free_of_progress(self, stub_pipeline) -> None:
        result = CliRunner().invoke(cli, ["transcribe", VIDEO_URL, "--quiet"])
        assert "Step 1/2" not in result.stdout
        assert "Device:" not in result.stdout

    def test_banner_goes_to_stderr_not_stdout(self, stub_pipeline) -> None:
        result = CliRunner().invoke(cli, ["transcribe", VIDEO_URL])
        assert "Step 1/2" not in result.stdout
        assert "Step 1/2" in result.stderr
        assert "Hello world." in result.stdout

    def test_json_format_produces_parseable_stdout(self, stub_pipeline) -> None:
        result = CliRunner().invoke(
            cli, ["transcribe", VIDEO_URL, "--format", "json", "--quiet"]
        )
        payload = json.loads(result.stdout)
        assert payload["language"] == "en"
        assert len(payload["segments"]) == 2

    def test_stdout_is_empty_when_output_file_is_used(
        self, stub_pipeline, tmp_path: Path
    ) -> None:
        target = tmp_path / "t.txt"
        result = CliRunner().invoke(
            cli, ["transcribe", VIDEO_URL, "--quiet", "--output", str(target)]
        )
        assert result.exit_code == 0
        assert result.stdout.strip() == ""


class TestOutputFilenameInjection:
    """The video ID is injected so two videos never overwrite each other's transcript."""

    def test_video_id_injected_into_stem(self, stub_pipeline, tmp_path: Path) -> None:
        result = CliRunner().invoke(
            cli,
            ["transcribe", VIDEO_URL, "--quiet", "--output", str(tmp_path / "t.txt")],
        )
        assert result.exit_code == 0
        assert (tmp_path / f"t_{VIDEO_ID}.txt").exists()

    def test_video_id_not_duplicated_when_already_present(
        self, stub_pipeline, tmp_path: Path
    ) -> None:
        # The skill's /tmp/transcript_<video_id>.txt pattern depends on this branch.
        name = f"transcript_{VIDEO_ID}.txt"
        result = CliRunner().invoke(
            cli, ["transcribe", VIDEO_URL, "--quiet", "--output", str(tmp_path / name)]
        )
        assert result.exit_code == 0
        assert (tmp_path / name).exists()
        assert not (tmp_path / f"transcript_{VIDEO_ID}_{VIDEO_ID}.txt").exists()

    def test_suffix_and_parent_are_preserved(self, stub_pipeline, tmp_path: Path) -> None:
        nested = tmp_path / "out"
        nested.mkdir()
        CliRunner().invoke(
            cli,
            [
                "transcribe", VIDEO_URL, "--quiet",
                "--format", "srt",
                "--output", str(nested / "subs.srt"),
            ],
        )
        assert (nested / f"subs_{VIDEO_ID}.srt").exists()

    def test_missing_parent_directory_is_created(
        self, stub_pipeline, tmp_path: Path
    ) -> None:
        # A transcript is expensive to produce; a missing directory must not discard it.
        target = tmp_path / "does" / "not" / "exist" / "t.txt"
        result = CliRunner().invoke(
            cli, ["transcribe", VIDEO_URL, "--quiet", "--output", str(target)]
        )
        assert result.exit_code == 0
        assert (target.parent / f"t_{VIDEO_ID}.txt").exists()

    def test_output_file_contains_the_transcript(
        self, stub_pipeline, tmp_path: Path
    ) -> None:
        CliRunner().invoke(
            cli, ["transcribe", VIDEO_URL, "--quiet", "--output", str(tmp_path / "t.txt")]
        )
        written = (tmp_path / f"t_{VIDEO_ID}.txt").read_text(encoding="utf-8")
        assert written == "Hello world.\n\nSecond segment."
