"""Unit tests for the empty-digest dispatch halt guard."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from set_orch import engine


@pytest.fixture(autouse=True)
def _reset_digest_counter():
    """Keep each test isolated — module-level dict persists across calls."""
    engine._EMPTY_DIGEST_COUNTS.clear()
    yield
    engine._EMPTY_DIGEST_COUNTS.clear()


def _directives() -> SimpleNamespace:
    return SimpleNamespace(
        max_parallel=1, default_model="opus", model_routing="off",
        team_mode=False, context_pruning=False,
    )


def test_populated_digest_dispatches_normally(tmp_path: Path) -> None:
    sf = str(tmp_path / "state.json")
    (tmp_path / "dig").mkdir()
    with patch("set_orch.dispatcher.dispatch_ready_changes") as disp, \
         patch("set_orch.paths.LineagePaths") as lp:
        lp.from_state_file.return_value.digest_dir = str(tmp_path / "dig")
        engine._dispatch_ready_safe(sf, _directives(), MagicMock())
    disp.assert_called_once()
    assert engine._EMPTY_DIGEST_COUNTS.get(sf, 0) == 0


def test_empty_digest_first_cycle_warns_and_dispatches(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    sf = str(tmp_path / "state.json")
    with patch("set_orch.dispatcher.dispatch_ready_changes") as disp, \
         patch("set_orch.paths.LineagePaths") as lp:
        lp.from_state_file.return_value.digest_dir = ""
        with caplog.at_level(logging.WARNING):
            engine._dispatch_ready_safe(sf, _directives(), MagicMock())
    disp.assert_called_once()
    assert engine._EMPTY_DIGEST_COUNTS[sf] == 1
    assert any("digest_dir is empty" in r.getMessage() for r in caplog.records)


def test_empty_digest_second_cycle_does_not_warn_again(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    sf = str(tmp_path / "state.json")
    engine._EMPTY_DIGEST_COUNTS[sf] = 1  # already warned once
    with patch("set_orch.dispatcher.dispatch_ready_changes") as disp, \
         patch("set_orch.paths.LineagePaths") as lp:
        lp.from_state_file.return_value.digest_dir = ""
        with caplog.at_level(logging.WARNING):
            engine._dispatch_ready_safe(sf, _directives(), MagicMock())
    disp.assert_called_once()
    assert engine._EMPTY_DIGEST_COUNTS[sf] == 2
    # No *new* WARNING about empty digest this cycle
    assert not any(
        "digest_dir is empty" in r.getMessage()
        for r in caplog.records if r.levelno == logging.WARNING
    )


def test_empty_digest_threshold_halts_dispatch(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    sf = str(tmp_path / "state.json")
    engine._EMPTY_DIGEST_COUNTS[sf] = 2  # next hit = threshold
    with patch("set_orch.dispatcher.dispatch_ready_changes") as disp, \
         patch("set_orch.paths.LineagePaths") as lp:
        lp.from_state_file.return_value.digest_dir = ""
        with caplog.at_level(logging.ERROR):
            engine._dispatch_ready_safe(sf, _directives(), MagicMock())
    disp.assert_not_called()  # halted
    assert engine._EMPTY_DIGEST_COUNTS[sf] == 3
    err_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("Dispatch halted" in m for m in err_msgs)
    assert any("digest run" in m for m in err_msgs)


def test_empty_digest_after_halt_does_not_re_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    sf = str(tmp_path / "state.json")
    engine._EMPTY_DIGEST_COUNTS[sf] = 3  # already halted
    with patch("set_orch.dispatcher.dispatch_ready_changes") as disp, \
         patch("set_orch.paths.LineagePaths") as lp:
        lp.from_state_file.return_value.digest_dir = ""
        with caplog.at_level(logging.ERROR):
            engine._dispatch_ready_safe(sf, _directives(), MagicMock())
    disp.assert_not_called()
    assert engine._EMPTY_DIGEST_COUNTS[sf] == 4
    # No duplicate ERROR spam after the first halt message
    assert not any("Dispatch halted" in r.getMessage() for r in caplog.records)


def test_digest_appears_after_halt_resumes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    sf = str(tmp_path / "state.json")
    (tmp_path / "dig").mkdir()
    engine._EMPTY_DIGEST_COUNTS[sf] = 5  # was halted
    with patch("set_orch.dispatcher.dispatch_ready_changes") as disp, \
         patch("set_orch.paths.LineagePaths") as lp:
        lp.from_state_file.return_value.digest_dir = str(tmp_path / "dig")
        with caplog.at_level(logging.INFO):
            engine._dispatch_ready_safe(sf, _directives(), MagicMock())
    disp.assert_called_once()
    assert sf not in engine._EMPTY_DIGEST_COUNTS
    info_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert any("Dispatch resumed" in m for m in info_msgs)


def test_counters_are_per_state_file(tmp_path: Path) -> None:
    sf1 = str(tmp_path / "a.json")
    sf2 = str(tmp_path / "b.json")
    engine._EMPTY_DIGEST_COUNTS[sf1] = 2
    with patch("set_orch.dispatcher.dispatch_ready_changes") as disp, \
         patch("set_orch.paths.LineagePaths") as lp:
        lp.from_state_file.return_value.digest_dir = ""
        engine._dispatch_ready_safe(sf2, _directives(), MagicMock())
    # sf2 is at cycle 1 — still dispatches; sf1 counter untouched
    disp.assert_called_once()
    assert engine._EMPTY_DIGEST_COUNTS[sf1] == 2
    assert engine._EMPTY_DIGEST_COUNTS[sf2] == 1
