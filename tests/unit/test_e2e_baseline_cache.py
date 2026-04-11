"""Tests for E2E baseline cache hardening — lock, port isolation, dirty-tree skip, fail-closed main detection.

See OpenSpec change: harden-e2e-baseline-cache

Five risks identified in the baseline-cache investigation:
1. No lock on regeneration → concurrent callers race
2. No explicit PW_PORT on baseline run → parent env bleeds through
3. No dirty-tree check on project_root → stale workspace poisons cache
4. Cache only invalidated on main_sha change → (accepted as known limitation)
5. Main-worktree detection falls back to wrong directory on git failure

These tests cover risks 1, 2, 3, and 5. Risk 4 is documented in the design
but not asserted here.
"""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))

from set_orch import subprocess_utils
from set_orch.state import Change
from set_orch.subprocess_utils import CommandResult


# Minimal Playwright output that passes the failure-ID regex — used as a
# successful baseline response.
SAMPLE_BASELINE_OUTPUT = """
Running 5 tests using 1 worker

  5 passed (45s)
"""


def _git_result(stdout="", exit_code=0):
    return CommandResult(exit_code, stdout, "", 10, False)


def _cmd_result(stdout=SAMPLE_BASELINE_OUTPUT, exit_code=0):
    return CommandResult(exit_code, stdout, "", 45000, False)


# ─── 4.2-4.4: _detect_main_worktree ──────────────────────────────────


class TestDetectMainWorktree:
    def test_success(self, tmp_path, monkeypatch):
        """Valid git topology → returns the main path."""
        wt = str(tmp_path / "wt")
        main = str(tmp_path / "main")
        os.makedirs(wt)
        os.makedirs(main)
        # Give main a .git entry so validation passes
        with open(os.path.join(main, ".git"), "w") as f:
            f.write("gitdir: ../real\n")

        def fake_run_git(*args, **kwargs):
            if args[:2] == ("rev-parse", "--show-toplevel"):
                return _git_result(main + "\n")
            if args[:2] == ("worktree", "list"):
                return _git_result(f"worktree {main}\nbranch refs/heads/main\n\nworktree {wt}\nbranch refs/heads/feature\n")
            return _git_result()

        monkeypatch.setattr(subprocess_utils, "run_git", fake_run_git)
        from set_project_web.gates import _detect_main_worktree

        assert _detect_main_worktree(wt) == main

    def test_rev_parse_fails(self, tmp_path, monkeypatch):
        """git rev-parse exit != 0 → None."""
        wt = str(tmp_path / "wt")
        os.makedirs(wt)

        monkeypatch.setattr(
            subprocess_utils, "run_git",
            lambda *a, **k: _git_result(exit_code=1),
        )
        from set_project_web.gates import _detect_main_worktree

        assert _detect_main_worktree(wt) is None

    def test_worktree_list_empty(self, tmp_path, monkeypatch):
        """worktree list returns only the current wt → no main → None."""
        wt = str(tmp_path / "wt")
        os.makedirs(wt)

        def fake_run_git(*args, **kwargs):
            if args[:2] == ("rev-parse", "--show-toplevel"):
                return _git_result(wt + "\n")
            if args[:2] == ("worktree", "list"):
                return _git_result(f"worktree {wt}\nbranch refs/heads/feature\n")
            return _git_result()

        monkeypatch.setattr(subprocess_utils, "run_git", fake_run_git)
        from set_project_web.gates import _detect_main_worktree

        assert _detect_main_worktree(wt) is None

    def test_detected_path_has_no_dot_git(self, tmp_path, monkeypatch):
        """worktree list returns a valid path but no .git entry → None."""
        wt = str(tmp_path / "wt")
        main = str(tmp_path / "bogus")
        os.makedirs(wt)
        os.makedirs(main)  # exists but NO .git

        def fake_run_git(*args, **kwargs):
            if args[:2] == ("rev-parse", "--show-toplevel"):
                return _git_result(main + "\n")
            if args[:2] == ("worktree", "list"):
                return _git_result(f"worktree {main}\nbranch refs/heads/main\n\nworktree {wt}\nbranch refs/heads/feature\n")
            return _git_result()

        monkeypatch.setattr(subprocess_utils, "run_git", fake_run_git)
        from set_project_web.gates import _detect_main_worktree

        assert _detect_main_worktree(wt) is None


# ─── 4.5-4.6: _is_project_root_clean ─────────────────────────────────


class TestIsProjectRootClean:
    def test_empty_output_means_clean(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            subprocess_utils, "run_git",
            lambda *a, **k: _git_result(stdout=""),
        )
        from set_project_web.gates import _is_project_root_clean

        assert _is_project_root_clean(str(tmp_path)) is True

    def test_nonempty_output_means_dirty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            subprocess_utils, "run_git",
            lambda *a, **k: _git_result(stdout=" M some/file.ts\n?? another.log\n"),
        )
        from set_project_web.gates import _is_project_root_clean

        assert _is_project_root_clean(str(tmp_path)) is False


# ─── 4.7: baseline port env ──────────────────────────────────────────


class TestBaselinePortIsolation:
    def test_baseline_run_uses_dedicated_port(self, tmp_path, monkeypatch):
        """Baseline run must pass PW_PORT=3199 in env, regardless of parent env."""
        # Set a conflicting parent env
        monkeypatch.setenv("PW_PORT", "3105")

        # Ensure baseline cache dir is isolated
        orch_dir = tmp_path / "orch-dir"
        os.makedirs(orch_dir, exist_ok=True)
        monkeypatch.setattr(
            "set_orch.paths.SetRuntime",
            lambda: type("R", (), {"orchestration_dir": str(orch_dir)})(),
        )

        # Clean git, valid HEAD
        monkeypatch.setattr(
            subprocess_utils, "run_git",
            lambda *a, **k: _git_result(stdout="abc123\n" if a[:2] == ("rev-parse", "HEAD") else ""),
        )

        captured_envs = []

        def fake_run_command(cmd, **kwargs):
            captured_envs.append(kwargs.get("env"))
            return _cmd_result()

        monkeypatch.setattr(subprocess_utils, "run_command", fake_run_command)

        from set_project_web.gates import _get_or_create_e2e_baseline, _E2E_BASELINE_PORT
        project_root = str(tmp_path / "project-root")
        os.makedirs(project_root)

        result = _get_or_create_e2e_baseline("pnpm test:e2e", 300, project_root)

        assert len(captured_envs) == 1, "run_command called exactly once for baseline"
        env = captured_envs[0]
        assert env is not None, "baseline run must pass env= argument"
        assert env.get("PW_PORT") == str(_E2E_BASELINE_PORT), (
            f"baseline env PW_PORT should be {_E2E_BASELINE_PORT}, got {env.get('PW_PORT')}"
        )
        assert env["PW_PORT"] != "3105", "parent env PW_PORT must not leak into baseline run"


# ─── 4.8: dirty project root skips cache ─────────────────────────────


class TestDirtyRootSkipsCache:
    def test_dirty_root_runs_baseline_but_does_not_persist(self, tmp_path, monkeypatch, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger="set_project_web.gates")

        orch_dir = tmp_path / "orch-dir"
        os.makedirs(orch_dir, exist_ok=True)
        monkeypatch.setattr(
            "set_orch.paths.SetRuntime",
            lambda: type("R", (), {"orchestration_dir": str(orch_dir)})(),
        )

        def fake_run_git(*args, **kwargs):
            if args[:2] == ("rev-parse", "HEAD"):
                return _git_result(stdout="dirty123\n")
            if args[:2] == ("status", "--porcelain"):
                return _git_result(stdout=" M src/uncommitted-edit.ts\n")
            return _git_result()

        monkeypatch.setattr(subprocess_utils, "run_git", fake_run_git)
        monkeypatch.setattr(subprocess_utils, "run_command", lambda *a, **k: _cmd_result())

        from set_project_web.gates import _get_or_create_e2e_baseline
        project_root = str(tmp_path / "project-root")
        os.makedirs(project_root)

        result = _get_or_create_e2e_baseline("pnpm test:e2e", 300, project_root)

        # Baseline was computed (not None) but not cached
        assert result is not None
        assert result.get("cacheable") is False

        # File must NOT exist on disk
        baseline_file = orch_dir / "e2e-baseline.json"
        assert not baseline_file.exists(), "dirty-root baseline must not persist"

        # Warning logged
        dirty_warnings = [
            r for r in caplog.records
            if r.levelname == "WARNING" and "dirty project root" in r.message.lower()
        ]
        assert dirty_warnings, f"expected WARNING about dirty project root, got: {[r.message for r in caplog.records]}"


# ─── 4.9: lock + peer already regenerated ────────────────────────────


class TestBaselineLock:
    def test_peer_cache_written_before_lock_is_reused(self, tmp_path, monkeypatch):
        """Post-lock re-check: a fresh cache written before we acquire the lock is reused.

        Note: this test simulates the peer write indirectly — the hook fires
        during `_is_project_root_clean` (before lock acquisition) rather than
        inside the lock-wait itself. It exercises the POST-LOCK re-check code
        path: after we acquire the exclusive lock, the function re-reads the
        cache file and if a peer already wrote a fresh entry, we return it
        without spawning a duplicate e2e run. True concurrent lock-contention
        is not tested here (would require threads) — the re-check logic is
        what matters, and that is what this test validates.
        """
        orch_dir = tmp_path / "orch-dir"
        os.makedirs(orch_dir, exist_ok=True)
        monkeypatch.setattr(
            "set_orch.paths.SetRuntime",
            lambda: type("R", (), {"orchestration_dir": str(orch_dir)})(),
        )

        baseline_path = orch_dir / "e2e-baseline.json"
        # Write a STALE baseline with old main_sha
        baseline_path.write_text(json.dumps({
            "main_sha": "old",
            "failures": [],
            "timestamp": "2026-01-01T00:00:00Z",
            "total": 5, "passed": 5, "failed": 0,
        }))

        # Simulate a peer by having the "dirty check" call also write the fresh cache
        # (a heuristic hook: after the stale-check passes, before run_command is invoked)
        def fake_run_git(*args, **kwargs):
            if args[:2] == ("rev-parse", "HEAD"):
                return _git_result(stdout="new\n")
            if args[:2] == ("status", "--porcelain"):
                # Peer writes fresh cache here, while "we" are about to acquire the lock
                baseline_path.write_text(json.dumps({
                    "main_sha": "new",
                    "failures": ["peer.spec.ts:10"],
                    "timestamp": "2026-01-01T00:00:01Z",
                    "total": 10, "passed": 9, "failed": 1,
                }))
                return _git_result(stdout="")
            return _git_result()

        monkeypatch.setattr(subprocess_utils, "run_git", fake_run_git)

        run_command_called = {"n": 0}
        def fake_run_command(*args, **kwargs):
            run_command_called["n"] += 1
            return _cmd_result()
        monkeypatch.setattr(subprocess_utils, "run_command", fake_run_command)

        from set_project_web.gates import _get_or_create_e2e_baseline
        project_root = str(tmp_path / "project-root")
        os.makedirs(project_root)

        result = _get_or_create_e2e_baseline("pnpm test:e2e", 300, project_root)

        # Assert: peer's result returned, no run_command call
        assert result is not None
        assert "peer.spec.ts:10" in result.get("failures", set()), (
            f"expected peer's failure in result, got: {result}"
        )
        assert run_command_called["n"] == 0, "should not have re-run baseline after peer update"


# ─── 4.10: atomic write on failure ───────────────────────────────────


class TestAtomicWrite:
    def test_write_failure_preserves_previous_cache(self, tmp_path, monkeypatch):
        """If json.dump raises mid-write, the old cache file is either preserved or absent — never partial."""
        orch_dir = tmp_path / "orch-dir"
        os.makedirs(orch_dir, exist_ok=True)
        monkeypatch.setattr(
            "set_orch.paths.SetRuntime",
            lambda: type("R", (), {"orchestration_dir": str(orch_dir)})(),
        )

        baseline_path = orch_dir / "e2e-baseline.json"
        # Write an OLD cache with previous content
        OLD_CONTENT = json.dumps({
            "main_sha": "old",
            "failures": ["old.spec.ts:5"],
            "timestamp": "2026-01-01T00:00:00Z",
            "total": 5, "passed": 4, "failed": 1,
        })
        baseline_path.write_text(OLD_CONTENT)

        # Git says main advanced → need regeneration
        monkeypatch.setattr(
            subprocess_utils, "run_git",
            lambda *a, **k: _git_result(stdout="new\n" if a[:2] == ("rev-parse", "HEAD") else ""),
        )
        monkeypatch.setattr(subprocess_utils, "run_command", lambda *a, **k: _cmd_result())

        # Make json.dump raise on first call inside the function
        import json as json_mod
        orig_dump = json_mod.dump
        raise_on_dump = {"remaining": 1}
        def failing_dump(*args, **kwargs):
            if raise_on_dump["remaining"] > 0:
                raise_on_dump["remaining"] -= 1
                raise IOError("simulated disk-full")
            return orig_dump(*args, **kwargs)
        monkeypatch.setattr(json_mod, "dump", failing_dump)

        from set_project_web.gates import _get_or_create_e2e_baseline
        project_root = str(tmp_path / "project-root")
        os.makedirs(project_root)

        # Call may raise or swallow — either is acceptable as long as the file is intact
        try:
            _get_or_create_e2e_baseline("pnpm test:e2e", 300, project_root)
        except (IOError, OSError):
            pass

        # File must be either absent OR the old content — never partial
        if baseline_path.exists():
            content = baseline_path.read_text()
            loaded = json.loads(content)  # must be valid JSON
            assert loaded.get("main_sha") == "old", (
                f"expected old content preserved, got main_sha={loaded.get('main_sha')}"
            )


# ─── 4.11: main detection None → skip baseline in execute_e2e_gate ────


class TestExecuteE2eGateFailClosed:
    def test_detection_none_skips_baseline(self, tmp_path, monkeypatch):
        """When _detect_main_worktree returns None, baseline is skipped and all wt failures are new."""
        wt = str(tmp_path / "wt")
        os.makedirs(os.path.join(wt, "tests", "e2e"))
        with open(os.path.join(wt, "playwright.config.ts"), "w") as f:
            f.write('export default { testDir: "./tests/e2e", webServer: { command: "next dev" } };')
        with open(os.path.join(wt, "tests", "e2e", "foo.spec.ts"), "w") as f:
            f.write('import { test } from "@playwright/test"; test("a", async () => {});')
        os.system(f'cd "{wt}" && git init -q && git add . && git commit -qm init 2>/dev/null')

        orch_dir = tmp_path / "orch-dir"
        os.makedirs(orch_dir, exist_ok=True)
        monkeypatch.setattr(
            "set_orch.paths.SetRuntime",
            lambda: type("R", (), {"orchestration_dir": str(orch_dir)})(),
        )

        # Real Playwright-shaped failure output — wt_failures will not be empty
        FAIL_OUTPUT = """
> my-app@0.1.0 test:e2e
> playwright test

Running 3 tests using 1 worker

  1) [chromium] \u203a tests/e2e/foo.spec.ts:45:7 \u203a some test

    Error: expected 1 got 2

  2) [chromium] \u203a tests/e2e/foo.spec.ts:60:7 \u203a another test

    Error: expected 3 got 4

  2 failed
  1 passed (30s)
"""
        wt_run_result = CommandResult(1, FAIL_OUTPUT, "", 30000, False)

        run_command_calls = []
        def fake_run_command(*args, **kwargs):
            run_command_calls.append(kwargs.get("cwd"))
            return wt_run_result
        monkeypatch.setattr(subprocess_utils, "run_command", fake_run_command)

        # Force _detect_main_worktree to return None (simulate git topology failure)
        import set_project_web.gates as gates_mod
        monkeypatch.setattr(gates_mod, "_detect_main_worktree", lambda _: None)

        # Stub run_git for any ancillary calls (should not matter here)
        monkeypatch.setattr(
            subprocess_utils, "run_git",
            lambda *a, **k: _git_result(exit_code=1),
        )

        change = Change(name="test-change", scope="test scope", status="verifying")
        result = gates_mod.execute_e2e_gate(
            change_name="test-change",
            change=change,
            wt_path=wt,
            e2e_command="pnpm test:e2e",
            e2e_timeout=300,
            e2e_health_timeout=30,
        )

        # Only the worktree run — NO baseline regeneration call
        assert len(run_command_calls) == 1, (
            f"expected exactly 1 run_command call (wt run), got {len(run_command_calls)}: {run_command_calls}"
        )

        # Gate returned fail with both failure IDs in output
        assert result.status == "fail"
        assert "foo.spec.ts:45" in result.output
        assert "foo.spec.ts:60" in result.output
        # No "pre-existing" masking language
        assert "pre-existing" not in result.output.lower()
