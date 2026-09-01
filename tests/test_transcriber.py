"""Tests for transcriber-module invariants that need no model download.

The transcription calls themselves require network and model weights and are
exercised manually. The model tables and the stdout guard are pure logic, and both
back documented landmines.
"""

from __future__ import annotations

import io
import sys
import typing

from youtube_transcriber.transcriber import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    MLX_MODEL_REPOS,
    ModelSize,
    _stdout_to_stderr,
)

# Models faster-whisper serves on CPU/CUDA for which mlx-community publishes no MLX
# conversion. On Apple Silicon these raise "has no MLX repo mapping" by design.
CPU_ONLY_MODELS = {"distil-small.en", "distil-large-v2"}


class TestModelTables:
    """AVAILABLE_MODELS gates --model; MLX_MODEL_REPOS resolves it on Apple Silicon."""

    def test_every_mlx_repo_is_a_selectable_model(self) -> None:
        assert set(MLX_MODEL_REPOS) <= set(AVAILABLE_MODELS)

    def test_every_model_has_an_mlx_repo_except_the_known_cpu_only_ones(self) -> None:
        # Adding a model to AVAILABLE_MODELS without an MLX entry fails at runtime on
        # every Apple Silicon Mac, not at parse time.
        missing = set(AVAILABLE_MODELS) - set(MLX_MODEL_REPOS)
        assert missing == CPU_ONLY_MODELS

    def test_cpu_only_models_are_still_selectable(self) -> None:
        for name in CPU_ONLY_MODELS:
            assert name in AVAILABLE_MODELS

    def test_mlx_repos_are_all_mlx_community(self) -> None:
        for name, repo in MLX_MODEL_REPOS.items():
            assert repo.startswith("mlx-community/"), f"{name} -> {repo}"

    def test_model_size_literal_matches_available_models(self) -> None:
        assert set(typing.get_args(ModelSize)) == set(AVAILABLE_MODELS)

    def test_default_model_is_usable_on_both_backends(self) -> None:
        assert DEFAULT_MODEL in AVAILABLE_MODELS
        assert DEFAULT_MODEL in MLX_MODEL_REPOS

    def test_every_model_entry_has_the_expected_keys(self) -> None:
        for name, info in AVAILABLE_MODELS.items():
            assert set(info) == {"params", "vram", "notes"}, name


class TestStdoutToStderr:
    """mlx_whisper prints per-segment output to stdout; it must not reach the transcript."""

    def test_writes_to_stdout_are_redirected_to_stderr(self) -> None:
        captured = io.StringIO()
        real_stderr = sys.stderr
        sys.stderr = captured
        try:
            with _stdout_to_stderr():
                print("[00:00.000 --> 00:05.120]  segment text")
        finally:
            sys.stderr = real_stderr
        assert "segment text" in captured.getvalue()

    def test_stdout_is_restored_on_exit(self) -> None:
        original = sys.stdout
        with _stdout_to_stderr():
            pass
        assert sys.stdout is original

    def test_stdout_is_restored_even_when_the_body_raises(self) -> None:
        original = sys.stdout
        try:
            with _stdout_to_stderr():
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert sys.stdout is original
