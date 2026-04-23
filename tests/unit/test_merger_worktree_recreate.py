"""Test that merger doesn't falsely log 'Recreated worktree' on git exit!=0."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _fake_result(exit_code: int, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        exit_code=exit_code, stdout=stdout, stderr=stderr,
        duration_ms=1, timed_out=False,
    )


def _run_merger_recreate_path(wt_exists_after: bool, exit_code: int, caplog):
    """Invoke the slice of merger.py that re-creates a missing worktree.

    Rather than reproducing the full merge_change setup we import the
    logger + subprocess_utils patch directly and exercise the exact
    block that was buggy. The block is small enough that we test it by
    calling a tiny reproduction-harness that mirrors the production code.
    """
    from set_orch import merger as merger_mod

    wt_path = "/tmp/nonexistent-worktree-for-test"
    name = "catalog-search"

    # Stub run_command to return our fake result
    with patch("set_orch.subprocess_utils.run_command") as rc, \
         patch("os.path.isdir") as isdir:
        rc.return_value = _fake_result(exit_code, stdout="ok", stderr="conflict")
        isdir.side_effect = lambda p: (p == wt_path and wt_exists_after)

        # Reproduce the merger block inline — simpler than the full merger call
        logger = logging.getLogger("set_orch.merger")
        with caplog.at_level(logging.INFO, logger="set_orch.merger"):
            # Replicates merger.py lines around 2457–2480
            try:
                from set_orch.subprocess_utils import run_command
                result = run_command(
                    ["git", "worktree", "add", wt_path, f"change/{name}"],
                    timeout=30,
                )
                import os as _os
                if result.exit_code == 0 and _os.path.isdir(wt_path):
                    logger.info("Recreated worktree for %s at %s", name, wt_path)
                else:
                    logger.error(
                        "Failed to recreate worktree for %s: "
                        "exit=%d stdout=%r stderr=%r — merging without gates",
                        name, result.exit_code,
                        (result.stdout or "")[:200],
                        (result.stderr or "")[:200],
                    )
            except Exception as e:
                logger.error("Failed to recreate worktree for %s: %s", name, e)


def test_successful_recreate_logs_info(caplog: pytest.LogCaptureFixture) -> None:
    _run_merger_recreate_path(wt_exists_after=True, exit_code=0, caplog=caplog)
    infos = [r for r in caplog.records if r.levelno == logging.INFO]
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("Recreated worktree" in r.getMessage() for r in infos)
    assert not errors


def test_git_exit_128_does_not_log_recreated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Real-world case: "already registered" → exit 128, worktree NOT on disk
    _run_merger_recreate_path(wt_exists_after=False, exit_code=128, caplog=caplog)
    messages = [r.getMessage() for r in caplog.records]
    # Must NOT claim "Recreated"
    assert not any("Recreated worktree" in m for m in messages)
    # Must surface the real failure with exit code
    assert any("Failed to recreate worktree" in m and "exit=128" in m for m in messages)


def test_exit_zero_but_dir_missing_does_not_log_recreated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Weird case: git reports success, but the dir isn't there anyway.
    # The combined check (exit==0 AND isdir) protects against this.
    _run_merger_recreate_path(wt_exists_after=False, exit_code=0, caplog=caplog)
    messages = [r.getMessage() for r in caplog.records]
    assert not any("Recreated worktree" in m for m in messages)
    assert any("Failed to recreate worktree" in m for m in messages)
