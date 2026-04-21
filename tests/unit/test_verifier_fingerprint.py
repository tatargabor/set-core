"""Unit tests for verifier fingerprint + stall guard helpers.

Covers section 2 of fix-replan-stuck-gate-and-decomposer:

- `_compute_gate_fingerprint` is deterministic and order-independent.
- `_has_commits_since_stall` returns 0 on missing/invalid inputs and a
  positive count when HEAD has new commits since the epoch baseline.
"""
from __future__ import annotations

import os
import sys
import subprocess
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.verifier import (  # noqa: E402
    _compute_gate_fingerprint,
    _has_commits_since_stall,
)


class TestComputeGateFingerprint:
    def test_stable_across_calls(self):
        r = [SimpleNamespace(status="fail", gate_name="review", stats=None)]
        assert _compute_gate_fingerprint("review", r) == _compute_gate_fingerprint("review", r)

    def test_pass_differs_from_fail(self):
        r_fail = [SimpleNamespace(status="fail", gate_name="review", stats=None)]
        r_pass = [SimpleNamespace(status="pass", gate_name="review", stats=None)]
        assert _compute_gate_fingerprint("review", r_fail) != _compute_gate_fingerprint("", r_pass)

    def test_finding_order_ignored(self):
        a = [SimpleNamespace(status="fail", gate_name="review", stats={
            "findings": [{"fingerprint": "aaa"}, {"fingerprint": "bbb"}],
        })]
        b = [SimpleNamespace(status="fail", gate_name="review", stats={
            "findings": [{"fingerprint": "bbb"}, {"fingerprint": "aaa"}],
        })]
        assert _compute_gate_fingerprint("review", a) == _compute_gate_fingerprint("review", b)

    def test_explicit_finding_ids_accepted(self):
        fp = _compute_gate_fingerprint("review", finding_ids=["x", "y"])
        assert fp.startswith("sha256:")
        assert len(fp.split(":", 1)[1]) == 16

    def test_different_stop_gate_different_fingerprint(self):
        fp1 = _compute_gate_fingerprint("review", finding_ids=["x"])
        fp2 = _compute_gate_fingerprint("test", finding_ids=["x"])
        assert fp1 != fp2

    def test_empty_inputs_still_returns_sha256(self):
        fp = _compute_gate_fingerprint("", None)
        assert fp.startswith("sha256:")

    def test_duplicate_finding_ids_deduplicated(self):
        fp_unique = _compute_gate_fingerprint("review", finding_ids=["x"])
        fp_dup = _compute_gate_fingerprint("review", finding_ids=["x", "x", "x"])
        assert fp_unique == fp_dup

    def test_head_sha_changes_fingerprint(self, tmp_path):
        """Regression for craftbrew-run-20260421-0025: identical gate output
        plus different HEAD SHA must produce different fingerprints, so
        stuck_loop does not fire after a fix commit that happens to keep
        the same gate failing (or that lands between verify runs).
        """
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
        (tmp_path / "f.txt").write_text("v1")
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "c1"], check=True)

        r = [SimpleNamespace(status="fail", gate_name="i18n_check", stats=None)]
        fp1 = _compute_gate_fingerprint("i18n_check", r, wt_path=str(tmp_path))

        (tmp_path / "f.txt").write_text("v2")
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-aq", "-m", "c2"], check=True)
        fp2 = _compute_gate_fingerprint("i18n_check", r, wt_path=str(tmp_path))

        assert fp1 != fp2, \
            "HEAD moved — fingerprint must differ even though gate output is identical"

    def test_missing_wt_path_matches_legacy(self):
        """Backwards-compat: omitting wt_path yields the pre-fix fingerprint
        (so external callers not yet passing wt_path are unaffected)."""
        r = [SimpleNamespace(status="fail", gate_name="review", stats=None)]
        fp_no_wt = _compute_gate_fingerprint("review", r)
        fp_empty = _compute_gate_fingerprint("review", r, wt_path="")
        fp_bad_path = _compute_gate_fingerprint("review", r, wt_path="/nonexistent/path")
        assert fp_no_wt == fp_empty == fp_bad_path


class TestHasCommitsSinceStall:
    @pytest.fixture
    def git_wt(self, tmp_path):
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
        (tmp_path / "f.txt").write_text("v1")
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "initial"], check=True)
        return tmp_path

    def test_no_commits_after_baseline(self, git_wt):
        # baseline is "now + 60s" — no commits possible after that
        import time
        baseline = int(time.time()) + 60
        assert _has_commits_since_stall(str(git_wt), baseline) == 0

    def test_commits_after_baseline(self, git_wt):
        import time
        baseline = int(time.time()) - 60
        (git_wt / "f.txt").write_text("v2")
        subprocess.run(["git", "-C", str(git_wt), "commit", "-aq", "-m", "post-baseline"], check=True)
        assert _has_commits_since_stall(str(git_wt), baseline) >= 1

    def test_zero_baseline_returns_zero(self, git_wt):
        assert _has_commits_since_stall(str(git_wt), 0) == 0

    def test_missing_path_returns_zero(self):
        assert _has_commits_since_stall("/nonexistent/path", 100) == 0

    def test_empty_path_returns_zero(self):
        assert _has_commits_since_stall("", 100) == 0
