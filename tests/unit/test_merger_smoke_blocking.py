"""Tests for merger integration-e2e smoke phase blocking.

See OpenSpec change: block-integration-smoke-fail

Before this change the smoke phase was non-blocking — a smoke failure
logged a warning, set `_smoke_failed = True`, and continued to Phase 2.
If Phase 2 passed, the merge proceeded even though a sibling test just
regressed. This wasted ~70 minutes in one observed run because the
change merged broken state and the regression only surfaced on a later
retry cycle.

The fix makes smoke phase blocking by default (directive
`integration_smoke_blocking = True`). When smoke fails:
- Phase 2 is skipped (no point running own tests on broken state)
- The change status goes to "integration-e2e-failed"
- A smoke-specific retry context is built
- The retry counter is incremented
- _run_integration_gates returns False

Operators can opt out via `integration_smoke_blocking: false` to
preserve the old warning-only behavior.
"""

import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))

from set_orch import merger, subprocess_utils
from set_orch.state import Change
from set_orch.subprocess_utils import CommandResult


SMOKE_FAIL_OUTPUT = """
> my-app@0.1.0 test:e2e
> playwright test

Running 4 tests using 1 worker

  1) [chromium] \u203a tests/e2e/product-catalog.spec.ts:33:7 \u203a REQ-CAT-001 \u003e REQ-CAT-001:AC-1

    Error: expect(received).toHaveCount(expected)

    Expected: 6
    Received: 7

  1 failed
    [chromium] \u203a tests/e2e/product-catalog.spec.ts:33:7 \u003e REQ-CAT-001:AC-1
  3 passed (45s)
"""

OWN_TESTS_PASS_OUTPUT = """
> my-app@0.1.0 test:e2e
> playwright test

Running 20 tests using 1 worker

  20 passed (60s)
"""

BUILD_PASS = CommandResult(0, "build ok\n", "", 5000, False)
TEST_PASS = CommandResult(0, "ok\n", "", 500, False)
DEP_PASS = CommandResult(0, "deps ok\n", "", 1000, False)


class FakeWebProfile:
    """Minimal profile stub implementing the methods merger._run_integration_gates uses."""

    def detect_build_command(self, wt_path):
        return "pnpm build"

    def detect_test_command(self, wt_path):
        return "pnpm test"

    def detect_e2e_command(self, wt_path):
        return "pnpm test:e2e"

    def detect_dep_install_command(self, wt_path):
        return "pnpm install"

    def extract_first_test_name(self, spec_path):
        # Return a non-empty string so the smoke path is taken
        return f"REQ-SMOKE-{os.path.basename(spec_path).split('.')[0]}"

    def e2e_smoke_command(self, base_cmd, test_names):
        return f"{base_cmd} -g \"{'|'.join(test_names)}\""

    def e2e_scoped_command(self, base_cmd, spec_files):
        return f"{base_cmd} -- {' '.join(spec_files)}"

    def worktree_port(self, change_name):
        return 3101

    def e2e_gate_env(self, port):
        return {"PW_PORT": str(port), "PORT": str(port)}


def _make_wt(tmp_path):
    """Create a wt with main = [product-catalog.spec.ts], feature = main + own-feature.spec.ts.

    This gives _detect_own_spec_files a realistic git topology so it can
    correctly classify own-feature.spec.ts as "owned by this change" and
    product-catalog.spec.ts as "inherited from main".
    """
    wt = os.path.join(str(tmp_path), "wt")
    os.makedirs(os.path.join(wt, "tests", "e2e"))
    with open(os.path.join(wt, "playwright.config.ts"), "w") as f:
        f.write('export default { testDir: "./tests/e2e" };')
    # Sibling spec — already on main
    with open(os.path.join(wt, "tests", "e2e", "product-catalog.spec.ts"), "w") as f:
        f.write('import { test } from "@playwright/test";\ntest("sibling", async () => {});\n')

    # Create main branch with just the sibling spec
    os.system(
        f'cd "{wt}" && git init -q -b main '
        f'&& git config user.email test@test.test '
        f'&& git config user.name test '
        f'&& git add . '
        f'&& git commit -qm "main-baseline" 2>/dev/null'
    )

    # Add the own spec on a feature branch
    with open(os.path.join(wt, "tests", "e2e", "own-feature.spec.ts"), "w") as f:
        f.write('import { test } from "@playwright/test";\ntest("own", async () => {});\n')
    os.system(
        f'cd "{wt}" && git checkout -q -b feature '
        f'&& git add . '
        f'&& git commit -qm "add own-feature" 2>/dev/null'
    )
    return wt


def _make_state_file(tmp_path, integration_smoke_blocking=True):
    """Create a minimal state file with the directive flag set.

    Note: directives go at the TOP LEVEL of the state JSON (as an unknown
    field that gets captured into state.extras by OrchestratorState.from_dict).
    """
    state_path = os.path.join(str(tmp_path), "state.json")
    state = {
        "plan_version": 1,
        "brief_hash": "test",
        "status": "running",
        "created_at": "2026-04-11T12:00:00+02:00",
        "changes": [{
            "name": "admin-products",
            "scope": "add admin CRUD",
            "status": "integrating",
        }],
        "merge_queue": [],
        "checkpoints": [],
        "changes_since_checkpoint": 0,
        # Top-level — captured into state.extras["directives"] by the loader
        "directives": {
            "integration_smoke_blocking": integration_smoke_blocking,
            "e2e_retry_limit": 3,
        },
    }
    with open(state_path, "w") as f:
        json.dump(state, f)
    return state_path


@pytest.fixture
def tmp_path_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _install_run_command_sequence(monkeypatch, results):
    """Queue CommandResult objects for gate-executor run_command calls.

    `git` calls (used internally by _detect_own_spec_files etc.) pass through
    to the real subprocess so the test can rely on a real git topology.
    """
    import subprocess
    from set_orch.subprocess_utils import run_command as real_run_command

    calls = {"commands": []}
    queue = {"idx": 0}

    def fake_run_command(cmd, **kwargs):
        # Pass-through for direct git invocations used by _detect_own_spec_files
        if isinstance(cmd, list) and len(cmd) >= 1 and cmd[0] == "git":
            return real_run_command(cmd, **kwargs)

        # Otherwise, return from the queue — this is a gate-executor call
        idx = queue["idx"]
        queue["idx"] += 1
        calls["commands"].append(cmd[-1] if isinstance(cmd, list) else str(cmd))
        if idx < len(results):
            return results[idx]
        return results[-1]

    monkeypatch.setattr(subprocess_utils, "run_command", fake_run_command)
    return calls


# ─── Smoke blocking tests ─────────────────────────────────────────────


class TestSmokeFailBlocksByDefault:
    def test_smoke_fail_blocks_merge_and_redispatches(self, tmp_path_dir, monkeypatch):
        """When smoke fails and directive is True (default), merge is blocked + redispatched."""
        wt = _make_wt(tmp_path_dir)
        state_file = _make_state_file(tmp_path_dir, integration_smoke_blocking=True)
        profile = FakeWebProfile()

        # Sequence: dep install (pass), build (pass), test (pass), smoke (FAIL)
        smoke_fail = CommandResult(1, SMOKE_FAIL_OUTPUT, "", 5000, False)
        calls = _install_run_command_sequence(
            monkeypatch,
            [DEP_PASS, BUILD_PASS, TEST_PASS, smoke_fail],
        )

        change = Change(name="admin-products", scope="add admin CRUD", status="integrating")
        result = merger._run_integration_gates(
            change_name="admin-products",
            change=change,
            wt_path=wt,
            state_file=state_file,
            profile=profile,
        )

        # Return False — gate blocked the merge
        assert result is False

        # Own-tests call was NEVER made — verify by looking at the command log
        own_tests_calls = [
            c for c in calls["commands"]
            if "own-feature.spec.ts" in c and "-- " in c
        ]
        assert len(own_tests_calls) == 0, (
            f"Phase 2 (own tests) should not run after smoke fail — "
            f"found calls: {calls['commands']}"
        )

        # Verify state was updated — fields are written top-level via update_change_field
        with open(state_file) as f:
            state = json.load(f)
        ch = next(c for c in state["changes"] if c["name"] == "admin-products")
        assert ch["status"] == "integration-e2e-failed"
        assert ch.get("integration_e2e_retry_count") == 1
        assert "smoke" in (ch.get("retry_context") or "").lower()

    def test_retry_context_lists_sibling_specs(self, tmp_path_dir, monkeypatch):
        """The retry context explicitly names the sibling spec file(s) that failed."""
        wt = _make_wt(tmp_path_dir)
        state_file = _make_state_file(tmp_path_dir, integration_smoke_blocking=True)
        profile = FakeWebProfile()

        smoke_fail = CommandResult(1, SMOKE_FAIL_OUTPUT, "", 5000, False)
        _install_run_command_sequence(
            monkeypatch,
            [DEP_PASS, BUILD_PASS, TEST_PASS, smoke_fail],
        )

        change = Change(name="admin-products", scope="add admin CRUD", status="integrating")
        merger._run_integration_gates(
            change_name="admin-products",
            change=change,
            wt_path=wt,
            state_file=state_file,
            profile=profile,
        )

        with open(state_file) as f:
            state = json.load(f)
        ch = next(c for c in state["changes"] if c["name"] == "admin-products")
        retry_ctx = ch.get("retry_context") or ""

        # Starts with a smoke-phase explanation
        assert "sibling" in retry_ctx.lower() or "smoke" in retry_ctx.lower()
        # Names the failing sibling
        assert "product-catalog.spec.ts" in retry_ctx
        # Points at the conventions rule
        assert "testing-conventions" in retry_ctx.lower() or "afterEach" in retry_ctx


class TestSmokePassLetsMergeProceed:
    def test_smoke_pass_then_own_pass_returns_true(self, tmp_path_dir, monkeypatch):
        """When both phases pass, the gate returns True and the merge proceeds."""
        wt = _make_wt(tmp_path_dir)
        state_file = _make_state_file(tmp_path_dir, integration_smoke_blocking=True)
        profile = FakeWebProfile()

        smoke_pass = CommandResult(0, "3 passed (45s)\n", "", 45000, False)
        own_pass = CommandResult(0, OWN_TESTS_PASS_OUTPUT, "", 60000, False)
        _install_run_command_sequence(
            monkeypatch,
            [DEP_PASS, BUILD_PASS, TEST_PASS, smoke_pass, own_pass],
        )

        change = Change(name="admin-products", scope="add admin CRUD", status="integrating")
        result = merger._run_integration_gates(
            change_name="admin-products",
            change=change,
            wt_path=wt,
            state_file=state_file,
            profile=profile,
        )

        assert result is True
        with open(state_file) as f:
            state = json.load(f)
        ch = next(c for c in state["changes"] if c["name"] == "admin-products")
        # Status did NOT change to integration-e2e-failed
        assert ch["status"] != "integration-e2e-failed"


class TestDirectiveOverride:
    def test_non_blocking_override_preserves_old_behavior(self, tmp_path_dir, monkeypatch, caplog):
        """With integration_smoke_blocking=False, smoke fail does not block — Phase 2 runs."""
        import logging
        caplog.set_level(logging.WARNING, logger="set_orch.merger")

        wt = _make_wt(tmp_path_dir)
        state_file = _make_state_file(tmp_path_dir, integration_smoke_blocking=False)
        profile = FakeWebProfile()

        smoke_fail = CommandResult(1, SMOKE_FAIL_OUTPUT, "", 5000, False)
        own_pass = CommandResult(0, OWN_TESTS_PASS_OUTPUT, "", 60000, False)
        _install_run_command_sequence(
            monkeypatch,
            [DEP_PASS, BUILD_PASS, TEST_PASS, smoke_fail, own_pass],
        )

        change = Change(name="admin-products", scope="add admin CRUD", status="integrating")
        result = merger._run_integration_gates(
            change_name="admin-products",
            change=change,
            wt_path=wt,
            state_file=state_file,
            profile=profile,
        )

        # Merge proceeds because Phase 2 passes — old non-blocking behavior
        assert result is True

        # Status should NOT be integration-e2e-failed
        with open(state_file) as f:
            state = json.load(f)
        ch = next(c for c in state["changes"] if c["name"] == "admin-products")
        assert ch["status"] != "integration-e2e-failed"

        # A WARNING about non-blocking smoke fail should be in the log
        non_blocking_warnings = [
            r for r in caplog.records
            if r.levelname == "WARNING"
            and "smoke" in r.message.lower()
            and "non-blocking" in r.message.lower()
        ]
        assert non_blocking_warnings, (
            f"expected a non-blocking smoke warning, got: {[r.message for r in caplog.records]}"
        )
