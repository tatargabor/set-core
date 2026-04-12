"""Regression tests for execute_e2e_gate timeout + unparseable-fail masking.

See OpenSpec change: fix-e2e-gate-timeout-masking

The worktree-stage e2e gate in modules/web/set_project_web/gates.py used to
return PASS on runs where Playwright timed out or crashed before emitting a
parseable failure list. The root cause was that the baseline-comparison branch
treated `wt_failures = set()` as "no new failures" and took the PASS exit.

Empirical evidence from the investigation (see design doc):
- Full suite run: 104 passed (2.6m) = 156s
- Default e2e_timeout = 120s → always times out on realistic web suites
- run_command(timeout=120) returns exit_code=-1, timed_out=True, truncated stdout
- _extract_e2e_failure_ids on the truncated tail: 0 matches
- execute_e2e_gate on those inputs: returns status="pass" (the bug)

These tests reproduce each scenario and assert the FIXED behavior (status="fail").
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))

from set_orch import subprocess_utils
from set_orch.state import Change
from set_orch.subprocess_utils import CommandResult


# Real-world truncated Playwright output captured mid-run (from the investigation).
# Note the ANSI prefixes and the absence of any "N passed" / "1) [chromium]" lines.
TIMED_OUT_STDOUT = """
> my-app@0.1.0 test:e2e /home/tg/demo/project
> playwright test

Running 104 tests using 1 worker

[1A[2K[1/104] [chromium] \u203a tests/e2e/admin-products.spec.ts:15:7 \u203a REQ-ADM-001:AC-1
[1A[2K[2/104] [chromium] \u203a tests/e2e/admin-products.spec.ts:24:7 \u203a REQ-ADM-001:AC-2
[1A[2K[38/104] [chromium] \u203a tests/e2e/checkout-orders.spec.ts:130:7 \u203a REQ-ORD-003:AC-2
[1A[2K[39/104] [chromium] \u203a tests/e2e/checkout-orders.spec.ts:145:7 \u203a REQ-ORD-004:AC-1
"""

# Synthetic crash output — no numbered failure list, just a segfault trace.
CRASH_STDOUT = """
> my-app@0.1.0 test:e2e /home/tg/demo/project
> playwright test

Running 104 tests using 1 worker

Segmentation fault (core dumped)
Error: Playwright test runner crashed unexpectedly
"""

# Real Playwright failure list with a summary — the baseline-comparison happy path.
REAL_FAILURE_STDOUT = """
> my-app@0.1.0 test:e2e /home/tg/demo/project
> playwright test

Running 10 tests using 1 worker

  1) [chromium] \u203a tests/e2e/foo.spec.ts:45:7 \u203a Listing shows 6 products

    Error: expect(received).toHaveCount(expected)

    Expected: 6
    Received: 7

      43 |     const cards = page.getByTestId("product-card");
    > 44 |     await expect(cards).toHaveCount(6);
         |                         ^

  1 failed
    [chromium] \u203a tests/e2e/foo.spec.ts:45:7 \u203a Listing shows 6 products
  9 passed (45s)
"""


def _make_wt(tmp_path) -> str:
    """Create a minimal git-initialised worktree with a playwright.config.ts and a dummy spec."""
    wt = os.path.join(tmp_path, "wt")
    os.makedirs(os.path.join(wt, "tests", "e2e"))
    with open(os.path.join(wt, "playwright.config.ts"), "w") as f:
        f.write('export default { testDir: "./tests/e2e", webServer: { command: "next dev" } };')
    with open(os.path.join(wt, "tests", "e2e", "foo.spec.ts"), "w") as f:
        f.write('import { test } from "@playwright/test"; test("a", async () => {});')
    # git init + commit so run_git calls inside the gate don't fail
    os.system(f"cd {wt} && git init -q && git add . && git commit -qm init 2>/dev/null")
    return wt


def _make_change() -> "Change":
    return Change(name="test-change", scope="Test scope for e2e gate", status="verifying")


@pytest.fixture
def tmp_wt():
    with tempfile.TemporaryDirectory() as tmp:
        yield _make_wt(tmp)


def _install_run_command_sequence(monkeypatch, results: list):
    """Queue a sequence of CommandResult objects to be returned by run_command."""
    calls = {"n": 0}

    def fake_run_command(cmd, **kwargs):
        idx = calls["n"]
        calls["n"] += 1
        if idx < len(results):
            return results[idx]
        return results[-1]  # repeat last for any trailing calls

    monkeypatch.setattr(subprocess_utils, "run_command", fake_run_command)
    return calls


def _install_run_git_stub(monkeypatch):
    """Stub run_git so project_root detection works without a real git worktree."""
    def fake_run_git(*args, **kwargs):
        if args[:2] == ("rev-parse", "--show-toplevel"):
            return CommandResult(0, "/tmp/fake-main\n", "", 10, False)
        if args[:2] == ("worktree", "list"):
            return CommandResult(0, "worktree /tmp/fake-main\nbranch refs/heads/main\n", "", 10, False)
        if args[:2] == ("rev-parse", "HEAD"):
            return CommandResult(0, "abc123def456\n", "", 10, False)
        return CommandResult(0, "", "", 10, False)

    monkeypatch.setattr(subprocess_utils, "run_git", fake_run_git)


def test_timeout_returns_fail(tmp_wt, monkeypatch, tmp_path):
    """Timed-out run (exit_code=-1, timed_out=True) MUST return FAIL, not masked PASS.

    This is the primary bug. Before the fix, execute_e2e_gate entered the
    baseline-comparison branch with wt_failures=set() and returned PASS.
    """
    timeout_result = CommandResult(
        exit_code=-1,
        stdout=TIMED_OUT_STDOUT,
        stderr="",
        duration_ms=120000,
        timed_out=True,
    )
    # Second call (baseline regen on main) — clean pass
    baseline_result = CommandResult(
        exit_code=0,
        stdout="  10 passed (45s)\n",
        stderr="",
        duration_ms=45000,
        timed_out=False,
    )
    # Point the baseline file elsewhere so the test is isolated
    monkeypatch.setattr(
        "set_orch.paths.SetRuntime",
        lambda: type("R", (), {"orchestration_dir": str(tmp_path / "orch-dir")})(),
    )
    os.makedirs(str(tmp_path / "orch-dir"), exist_ok=True)

    _install_run_command_sequence(monkeypatch, [timeout_result, baseline_result])
    _install_run_git_stub(monkeypatch)

    from set_project_web.gates import execute_e2e_gate

    result = execute_e2e_gate(
        change_name="test-change",
        change=_make_change(),
        wt_path=tmp_wt,
        e2e_command="pnpm test:e2e",
        e2e_timeout=120,
        e2e_health_timeout=30,
    )

    assert result.status == "fail", (
        f"Timed-out run must return FAIL, got {result.status!r}. "
        f"Output: {result.output[:500]}"
    )
    assert "timed out" in result.output.lower() or "timeout" in result.output.lower(), (
        f"Output should mention timeout; got: {result.output[:200]}"
    )
    assert result.retry_context, "Retry context should be set for the agent"
    assert "infrastructure" in result.retry_context.lower() or "did not finish" in result.retry_context.lower()


def test_unparseable_nonzero_exit_returns_fail(tmp_wt, monkeypatch, tmp_path):
    """Non-zero exit with no parseable failure list MUST return FAIL, not masked PASS.

    Covers crashes, OOMs, formatter drift, and any case where the Playwright
    summary didn't make it to stdout.
    """
    crash_result = CommandResult(
        exit_code=2,
        stdout=CRASH_STDOUT,
        stderr="",
        duration_ms=5000,
        timed_out=False,
    )
    baseline_result = CommandResult(
        exit_code=0,
        stdout="  10 passed (45s)\n",
        stderr="",
        duration_ms=45000,
        timed_out=False,
    )
    monkeypatch.setattr(
        "set_orch.paths.SetRuntime",
        lambda: type("R", (), {"orchestration_dir": str(tmp_path / "orch-dir")})(),
    )
    os.makedirs(str(tmp_path / "orch-dir"), exist_ok=True)

    _install_run_command_sequence(monkeypatch, [crash_result, baseline_result])
    _install_run_git_stub(monkeypatch)

    from set_project_web.gates import execute_e2e_gate

    result = execute_e2e_gate(
        change_name="test-change",
        change=_make_change(),
        wt_path=tmp_wt,
        e2e_command="pnpm test:e2e",
        e2e_timeout=120,
        e2e_health_timeout=30,
    )

    assert result.status == "fail", (
        f"Crashed run must return FAIL, got {result.status!r}. "
        f"Output: {result.output[:500]}"
    )
    assert "no parseable" in result.output.lower() or "crash" in result.output.lower() or "infra" in result.output.lower()


def test_extract_failure_ids_strips_ansi_cursor_codes():
    """Regression: Playwright emits \\x1b[1A\\x1b[2K cursor-control codes
    before each progress line when stdout is a tty. The failure-line regex
    uses `^\\s*` which does not match escape bytes, so the extractor used
    to miss every ANSI-prefixed failure and trigger the "unparseable crash"
    guard. Caught on nano-run-20260412-1941 where a `toHaveCount({min: 2})`
    syntax error was misdiagnosed as a Playwright crash.
    """
    from set_project_web.gates import _extract_e2e_failure_ids

    ansi_output = (
        "Running 7 tests using 1 worker\n\n"
        "\x1b[1A\x1b[2K[1/7] [chromium] \u203a tests/e2e/infra.spec.ts:8:7 \u203a AC-1\n"
        "\x1b[1A\x1b[2K[4/7] (retries) [chromium] \u203a tests/e2e/infra.spec.ts:19:7 \u203a AC-3 (retry #1)\n"
        "\x1b[1A\x1b[2K  1) [chromium] \u203a tests/e2e/infra.spec.ts:19:7 \u203a REQ-INFRA-001:AC-3 \n"
        "\n    Error: locator._expect: expectedNumber: expected float, got object\n"
        "\x1b[1A\x1b[2K  1 failed\n"
        "    [chromium] \u203a tests/e2e/infra.spec.ts:19:7 \u203a REQ-INFRA-001:AC-3\n"
        "  6 passed (12.1s)\n"
    )
    ids = _extract_e2e_failure_ids(ansi_output)
    assert ids == {"tests/e2e/infra.spec.ts:19"}, (
        f"Expected to extract the ANSI-prefixed failure id, got {ids!r}"
    )


def test_real_failure_enters_baseline_comparison(tmp_wt, monkeypatch, tmp_path):
    """Real Playwright failure with a parseable numbered list MUST flow through
    the baseline comparison (existing behavior preserved).
    """
    fail_result = CommandResult(
        exit_code=1,
        stdout=REAL_FAILURE_STDOUT,
        stderr="",
        duration_ms=60000,
        timed_out=False,
    )
    # Baseline on main: nothing fails there
    baseline_result = CommandResult(
        exit_code=0,
        stdout="  10 passed (45s)\n",
        stderr="",
        duration_ms=45000,
        timed_out=False,
    )
    monkeypatch.setattr(
        "set_orch.paths.SetRuntime",
        lambda: type("R", (), {"orchestration_dir": str(tmp_path / "orch-dir")})(),
    )
    os.makedirs(str(tmp_path / "orch-dir"), exist_ok=True)

    _install_run_command_sequence(monkeypatch, [fail_result, baseline_result])
    _install_run_git_stub(monkeypatch)

    from set_project_web.gates import execute_e2e_gate

    result = execute_e2e_gate(
        change_name="test-change",
        change=_make_change(),
        wt_path=tmp_wt,
        e2e_command="pnpm test:e2e",
        e2e_timeout=120,
        e2e_health_timeout=30,
    )

    assert result.status == "fail", (
        f"Real failure with parseable list must return FAIL, got {result.status!r}"
    )
    assert "foo.spec.ts:45" in result.output, (
        f"New failure should appear in output; got: {result.output[:500]}"
    )


def test_pre_fix_bug_snapshot(tmp_wt, monkeypatch, tmp_path):
    """Regression fossil — asserts the FIXED behavior for the exact inputs
    captured during the investigation. See OpenSpec change fix-e2e-gate-timeout-masking.

    Before the fix, this scenario returned status='pass' with the output header
    'E2E: 0 pre-existing failures on main (no new regressions)' — a confirmed
    false positive. The fix flips this to status='fail'.
    """
    timeout_result = CommandResult(
        exit_code=-1,
        stdout=TIMED_OUT_STDOUT,
        stderr="",
        duration_ms=120003,
        timed_out=True,
    )
    # Clean main — nothing to mask
    baseline_result = CommandResult(
        exit_code=0,
        stdout="  10 passed (45s)\n",
        stderr="",
        duration_ms=45000,
        timed_out=False,
    )
    monkeypatch.setattr(
        "set_orch.paths.SetRuntime",
        lambda: type("R", (), {"orchestration_dir": str(tmp_path / "orch-dir")})(),
    )
    os.makedirs(str(tmp_path / "orch-dir"), exist_ok=True)

    _install_run_command_sequence(monkeypatch, [timeout_result, baseline_result])
    _install_run_git_stub(monkeypatch)

    from set_project_web.gates import execute_e2e_gate

    result = execute_e2e_gate(
        change_name="test-change",
        change=_make_change(),
        wt_path=tmp_wt,
        e2e_command="pnpm test:e2e",
        e2e_timeout=120,
        e2e_health_timeout=30,
    )

    # The fix must turn this from pass → fail
    assert result.status == "fail", (
        f"BUG REGRESSION: execute_e2e_gate must return FAIL on timed-out runs. "
        f"Got status={result.status!r}, output={result.output[:300]}"
    )
    # Confirm we did NOT see the buggy masking message
    assert "no new regressions" not in result.output, (
        "Regression: the buggy 'no new regressions' message is back — "
        "the timeout guard clause must run before baseline comparison."
    )
