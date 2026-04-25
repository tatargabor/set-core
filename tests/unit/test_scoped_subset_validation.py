"""Unit tests for scoped-subset spec-existence pre-validation in gate_runner.

Background: before this fix, the e2e gate would log
`Scoped gate: e2e running on N subset items: [bogus_path]`
when `retry_diff_files` returned paths that did not exist in the worktree.
The bogus subprocess spawn would find 0 specs and trigger fallback to the
full 24-spec suite, wasting ~30 min per retry.

The fix: filter `subset` against `Path.exists()` before entering scoped mode.
If 0 valid paths remain, return None so the caller falls through.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _fake_runner(tmp_path: Path, subset_returned: list[str]):
    """Construct a minimal GateRunner-like object exercising _try_scoped_run."""
    from set_orch.gate_runner import GatePipeline
    from set_orch.state import Change

    runner = GatePipeline.__new__(GatePipeline)
    runner.change_name = "test-change"
    runner.change = Change(name="test-change", verify_retry_index=1)
    runner.change.worktree_path = str(tmp_path)
    runner.profile = MagicMock()
    runner.profile.gate_scope_filter = MagicMock(return_value=subset_returned)
    runner.max_consecutive_cache_uses = 2
    # Stub the prior-tracking lookup: a verdict_sha is required so
    # `_try_scoped_run` does not bail before the existence filter.
    fake_entry = MagicMock()
    fake_entry.last_verdict_sha = "abc1234"
    fake_entry.consecutive_cache_uses = 0
    runner._prior_tracking = MagicMock(return_value=fake_entry)
    # Stub _retry_diff_files to return some files (any non-empty list works
    # as the trigger; gate_scope_filter mock decides what subset is offered).
    runner._retry_diff_files = MagicMock(return_value=["src/x.tsx"])
    return runner


def test_subset_with_all_valid_paths(tmp_path: Path):
    """All paths exist → subset returned verbatim."""
    (tmp_path / "tests" / "e2e").mkdir(parents=True)
    spec1 = tmp_path / "tests" / "e2e" / "real-spec-1.spec.ts"
    spec2 = tmp_path / "tests" / "e2e" / "real-spec-2.spec.ts"
    spec1.touch()
    spec2.touch()
    runner = _fake_runner(tmp_path, [
        "tests/e2e/real-spec-1.spec.ts",
        "tests/e2e/real-spec-2.spec.ts",
    ])
    result = runner._try_scoped_run("e2e")
    assert result == [
        "tests/e2e/real-spec-1.spec.ts",
        "tests/e2e/real-spec-2.spec.ts",
    ]


def test_subset_with_all_bogus_paths_returns_none(tmp_path: Path):
    """0 valid paths → return None (fall through to fallback)."""
    runner = _fake_runner(tmp_path, [
        "tests/e2e/cookieconsentbanner.spec.ts",
        "tests/e2e/product-card.spec.ts",
    ])
    result = runner._try_scoped_run("e2e")
    assert result is None, (
        "Expected None when all subset paths are non-existent, "
        f"got {result!r}"
    )


def test_subset_with_mixed_paths_keeps_only_valid(tmp_path: Path):
    """Mixed valid/bogus → only valid paths in subset."""
    (tmp_path / "tests" / "e2e").mkdir(parents=True)
    valid1 = tmp_path / "tests" / "e2e" / "exists-1.spec.ts"
    valid2 = tmp_path / "tests" / "e2e" / "exists-2.spec.ts"
    valid1.touch()
    valid2.touch()
    runner = _fake_runner(tmp_path, [
        "tests/e2e/exists-1.spec.ts",
        "tests/e2e/bogus-1.spec.ts",
        "tests/e2e/exists-2.spec.ts",
        "tests/e2e/bogus-2.spec.ts",
    ])
    result = runner._try_scoped_run("e2e")
    assert result == [
        "tests/e2e/exists-1.spec.ts",
        "tests/e2e/exists-2.spec.ts",
    ]


def test_no_worktree_path_skips_validation(tmp_path: Path):
    """When worktree_path is empty, existence filter is skipped."""
    runner = _fake_runner(tmp_path, ["tests/e2e/x.spec.ts"])
    runner.change.worktree_path = ""  # disable filter
    result = runner._try_scoped_run("e2e")
    # Without filter, subset is returned even though path doesn't exist
    assert result == ["tests/e2e/x.spec.ts"]
