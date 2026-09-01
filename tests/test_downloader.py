"""Tests for the yt-dlp downloader wrapper.

Covers JS-runtime discovery only — the actual download needs network, so it is
exercised manually. The runtime probe is pure path logic and guards a landmine:
yt-dlp requires the dict form of ``js_runtimes`` and raises ValueError on the CLI
string form.
"""

from __future__ import annotations

import datetime
import pathlib

import pytest

from youtube_transcriber.downloader import (
    _find_js_runtime,
    _homebrew_keg_paths,
    _nvm_version_key,
    _warn_if_yt_dlp_stale,
    _yt_dlp_age_days,
)


class TestNvmVersionKey:
    """The nvm fallback must select the newest installed Node, not the first by name."""

    def test_parses_version_into_int_tuple(self) -> None:
        assert _nvm_version_key(pathlib.Path("v22.9.0")) == (22, 9, 0)

    def test_double_digit_major_sorts_above_single_digit(self) -> None:
        # The bug this guards: a plain name sort ranks "v9.11.2" above "v22.9.0".
        assert _nvm_version_key(pathlib.Path("v22.9.0")) > _nvm_version_key(
            pathlib.Path("v9.11.2")
        )

    def test_non_version_directory_sorts_lowest(self) -> None:
        # nvm also creates alias directories alongside the version directories.
        assert _nvm_version_key(pathlib.Path("default")) == (-1,)
        assert _nvm_version_key(pathlib.Path("default")) < _nvm_version_key(
            pathlib.Path("v9.11.2")
        )

    def test_sorting_a_realistic_set_puts_newest_last(self) -> None:
        names = ["v9.11.2", "v10.24.1", "v18.20.4", "v20.11.1", "v22.9.0"]
        ordered = sorted((pathlib.Path(n) for n in names), key=_nvm_version_key)
        assert ordered[-1].name == "v22.9.0"


class TestFindJsRuntime:
    """yt-dlp's js_runtimes option is a dict; the CLI string form raises ValueError."""

    def test_returns_dict_shape_not_cli_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "youtube_transcriber.downloader.shutil.which",
            lambda name: "/usr/bin/node" if name == "node" else None,
        )
        result = _find_js_runtime()
        assert result == {"node": {"path": "/usr/bin/node"}}

    def test_prefers_node_over_deno_and_bun(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "youtube_transcriber.downloader.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        assert list(_find_js_runtime()) == ["node"]

    def test_falls_through_to_deno_when_node_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "youtube_transcriber.downloader.shutil.which",
            lambda name: "/usr/bin/deno" if name == "deno" else None,
        )
        # Neutralise the absolute-path fallbacks so only PATH discovery is under test.
        monkeypatch.setattr(pathlib.Path, "is_file", lambda self: False)
        monkeypatch.setattr(pathlib.Path, "is_dir", lambda self: False)
        assert _find_js_runtime() == {"deno": {"path": "/usr/bin/deno"}}

    def test_returns_none_when_no_runtime_anywhere(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "youtube_transcriber.downloader.shutil.which", lambda name: None
        )
        monkeypatch.setattr(pathlib.Path, "is_file", lambda self: False)
        monkeypatch.setattr(pathlib.Path, "is_dir", lambda self: False)
        assert _find_js_runtime() is None


class TestHomebrewKegPaths:
    """Homebrew versioned formulas (node@22) never appear in /opt/homebrew/bin."""

    def test_finds_a_versioned_keg(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        keg = tmp_path / "node@22" / "bin"
        keg.mkdir(parents=True)
        (keg / "node").write_text("")
        monkeypatch.setattr(
            "youtube_transcriber.downloader.Path",
            _prefix_patched_path(tmp_path),
        )
        assert _homebrew_keg_paths("node") == [str(keg / "node")]

    def test_returns_empty_when_no_kegs_exist(self) -> None:
        assert _homebrew_keg_paths("definitely-not-a-runtime") == []

    def test_orders_newest_version_first(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        for version in ("node@18", "node@22", "node@9"):
            binary = tmp_path / version / "bin"
            binary.mkdir(parents=True)
            (binary / "node").write_text("")
        monkeypatch.setattr(
            "youtube_transcriber.downloader.Path",
            _prefix_patched_path(tmp_path),
        )
        found = _homebrew_keg_paths("node")
        assert [pathlib.Path(p).parent.parent.name for p in found] == [
            "node@22",
            "node@18",
            "node@9",
        ]


def _prefix_patched_path(tmp_path):
    """Return a Path subclass that redirects the Homebrew opt prefixes to tmp_path."""

    class _PatchedPath(pathlib.Path):
        def __new__(cls, *args, **kwargs):
            if args and str(args[0]) in ("/opt/homebrew/opt", "/usr/local/opt"):
                # Only the first prefix resolves; the second points somewhere empty.
                target = tmp_path if str(args[0]) == "/opt/homebrew/opt" else tmp_path / "_none"
                return pathlib.Path(target)
            return pathlib.Path(*args, **kwargs)

    return _PatchedPath


class TestYtDlpStaleness:
    """A stale yt-dlp is the top cause of download failure and presents opaquely."""

    def test_age_is_computed_from_the_date_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "youtube_transcriber.downloader._yt_dlp_version", lambda: "2026.3.17"
        )
        assert _yt_dlp_age_days(today=datetime.date(2026, 9, 1)) == 168

    def test_single_digit_month_and_day_parse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "youtube_transcriber.downloader._yt_dlp_version", lambda: "2026.8.19"
        )
        assert _yt_dlp_age_days(today=datetime.date(2026, 8, 20)) == 1

    def test_non_date_version_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "youtube_transcriber.downloader._yt_dlp_version", lambda: "unknown"
        )
        assert _yt_dlp_age_days() is None

    def test_fresh_yt_dlp_produces_no_warning(
        self, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        monkeypatch.setattr(
            "youtube_transcriber.downloader._yt_dlp_age_days", lambda: 3
        )
        _warn_if_yt_dlp_stale(verbose=True)
        assert capsys.readouterr().err == ""

    def test_stale_yt_dlp_warns_on_stderr_not_stdout(
        self, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        monkeypatch.setattr(
            "youtube_transcriber.downloader._yt_dlp_age_days", lambda: 400
        )
        _warn_if_yt_dlp_stale(verbose=True)
        out, err = capsys.readouterr()
        assert out == ""            # stdout carries only the transcript
        assert "400 days old" in err
