"""Regression tests for execute_e2e_gate retry_context truncation.

See OpenSpec change: fix-retry-context-signal-loss (Bug A).

Before the fix, modules/web/set_project_web/gates.py built retry_context with
a head-only slice (`e2e_output[:2000]`). In long E2E runs the first 2000 chars
were dominated by prisma/next setup noise, and Playwright assertion errors —
which live near the end of stdout — were truncated away. The impl agent then
saw only the failing test *names*, not *why* they failed, and would guess
that shared code needed rewriting (scope creep).

These tests assert the FIXED behavior:
- Error tail is preserved in retry_context via smart_truncate_structured
- Output shorter than budget passes through unchanged
- Failing-test header survives truncation
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


# Synthetic Playwright output mimicking the real-world failure pattern that
# motivated this change:
#   head (~10K):  prisma setup / next build noise
#   middle (~5K): per-test registration list
#   tail (~2K):   assertion error with the root cause
_PRISMA_NOISE = (
    "Prisma schema loaded from prisma/schema.prisma\n"
    "Datasource \"db\": SQLite database \"dev.db\" at \"file:./dev.db\"\n"
    "The SQLite database \"dev.db\" at \"file:./dev.db\" was successfully reset.\n"
    "Running generate... (Use --skip-generate to skip the generators)\n"
    "Running generate... - Prisma Client\n"
    "Generated Prisma Client (v6.19.3) to ./node_modules/@prisma/client in 91ms\n"
    "Running seed command `tsx prisma/seed.ts` ...\n"
    "Seed completed successfully\n"
    "[global-setup] Building Next.js for production serving...\n"
) * 50  # ~10K chars of setup noise

_TEST_LIST = (
    "[1/50] [chromium] tests/e2e/cart.spec.ts:10:7 REQ-CART-001:AC-1\n"
    "[2/50] [chromium] tests/e2e/cart.spec.ts:20:7 REQ-CART-001:AC-2\n"
    "[3/50] [chromium] tests/e2e/checkout.spec.ts:40:7 REQ-CH-001:AC-1\n"
) * 50  # ~5K chars of per-test list

_ASSERTION_ERROR_TAIL = (
    "\n"
    "  1) [chromium] \u203a tests/e2e/checkout.spec.ts:161:7 \u203a REQ-PR-001:AC-3\n"
    "\n"
    "    Error: expect(received).toHaveText(expected)\n"
    "\n"
    "    Expected: \"Free shipping applied\"\n"
    "    Received: \"Shipping: 1990 Ft\"\n"
    "\n"
    "      159 |     await page.getByTestId('checkout-submit').click();\n"
    "    > 160 |     const msg = page.getByTestId('shipping-msg');\n"
    "         |                 ^\n"
    "      161 |     await expect(msg).toHaveText('Free shipping applied');\n"
    "\n"
    "      at tests/e2e/checkout.spec.ts:161:25\n"
    "\n"
    "  1 failed\n"
    "    [chromium] \u203a tests/e2e/checkout.spec.ts:161:7 \u203a REQ-PR-001:AC-3\n"
    "  49 passed (62.1s)\n"
)


def _make_wt(tmp_path) -> str:
    wt = os.path.join(tmp_path, "wt")
    os.makedirs(os.path.join(wt, "tests", "e2e"))
    with open(os.path.join(wt, "playwright.config.ts"), "w") as f:
        f.write('export default { testDir: "./tests/e2e", webServer: { command: "next dev" } };')
    with open(os.path.join(wt, "tests", "e2e", "foo.spec.ts"), "w") as f:
        f.write('import { test } from "@playwright/test"; test("a", async () => {});')
    os.system(f"cd {wt} && git init -q && git add . && git commit -qm init 2>/dev/null")
    return wt


def _make_change() -> "Change":
    return Change(name="test-change", scope="Test scope for e2e retry_context", status="verifying")


@pytest.fixture
def tmp_wt():
    with tempfile.TemporaryDirectory() as tmp:
        yield _make_wt(tmp)


def _install_run_command_sequence(monkeypatch, results: list):
    calls = {"n": 0}

    def fake_run_command(cmd, **kwargs):
        idx = calls["n"]
        calls["n"] += 1
        if idx < len(results):
            return results[idx]
        return results[-1]

    monkeypatch.setattr(subprocess_utils, "run_command", fake_run_command)
    return calls


def _install_run_git_stub(monkeypatch):
    def fake_run_git(*args, **kwargs):
        if args[:2] == ("rev-parse", "--show-toplevel"):
            return CommandResult(0, "/tmp/fake-main\n", "", 10, False)
        if args[:2] == ("worktree", "list"):
            return CommandResult(0, "worktree /tmp/fake-main\nbranch refs/heads/main\n", "", 10, False)
        if args[:2] == ("rev-parse", "HEAD"):
            return CommandResult(0, "abc123def456\n", "", 10, False)
        return CommandResult(0, "", "", 10, False)

    monkeypatch.setattr(subprocess_utils, "run_git", fake_run_git)


def _run_gate(tmp_wt, monkeypatch, tmp_path, stdout: str):
    fail_result = CommandResult(
        exit_code=1, stdout=stdout, stderr="", duration_ms=60000, timed_out=False,
    )
    baseline_result = CommandResult(
        exit_code=0, stdout="  10 passed (45s)\n", stderr="", duration_ms=45000, timed_out=False,
    )
    monkeypatch.setattr(
        "set_orch.paths.SetRuntime",
        lambda: type("R", (), {"orchestration_dir": str(tmp_path / "orch-dir")})(),
    )
    os.makedirs(str(tmp_path / "orch-dir"), exist_ok=True)

    _install_run_command_sequence(monkeypatch, [fail_result, baseline_result])
    _install_run_git_stub(monkeypatch)

    from set_project_web.gates import execute_e2e_gate

    return execute_e2e_gate(
        change_name="test-change",
        change=_make_change(),
        wt_path=tmp_wt,
        e2e_command="pnpm test:e2e",
        e2e_timeout=120,
        e2e_health_timeout=30,
    )


def test_retry_context_preserves_assertion_error_tail(tmp_wt, monkeypatch, tmp_path):
    """AC-1: 32k output with assertion errors at the tail must reach retry_context.

    With a 6000-char budget and head_ratio=0.3, the head is 1800 chars and the
    tail is 4200 chars. The 2000-char assertion-error tail must fit.
    """
    big_output = _PRISMA_NOISE + _TEST_LIST + _ASSERTION_ERROR_TAIL
    assert len(big_output) > 15000

    result = _run_gate(tmp_wt, monkeypatch, tmp_path, big_output)

    assert result.status == "fail"
    assert result.retry_context
    # The critical assertion — one of the error signal markers must appear
    ctx = result.retry_context
    signal_markers = [
        "toHaveText",
        "Expected: \"Free shipping applied\"",
        "Error:",
        "expect(received)",
    ]
    assert any(m in ctx for m in signal_markers), (
        f"retry_context dropped assertion error tail; "
        f"last 400 chars: {ctx[-400:]!r}"
    )


def test_retry_context_does_not_end_in_prisma_generate(tmp_wt, monkeypatch, tmp_path):
    """Regression: pre-fix retry_context ended with 'Running generate... ['.

    The old [:2000] slice cut mid-line inside prisma setup output. Assert
    the new truncation does not reproduce that exact literal symptom.
    """
    big_output = _PRISMA_NOISE + _TEST_LIST + _ASSERTION_ERROR_TAIL

    result = _run_gate(tmp_wt, monkeypatch, tmp_path, big_output)

    # The E2E output section should NOT cut mid-sentence on "Running generate... ["
    # (the original observed symptom). The tail should contain structured content.
    assert not result.retry_context.rstrip().endswith("Running generate... ["), (
        "retry_context still ends inside prisma generate noise"
    )


def test_retry_context_passthrough_when_under_budget(tmp_wt, monkeypatch, tmp_path):
    """AC-2: output smaller than the truncation budget must appear verbatim.

    No truncation marker should be added when the content fits.
    """
    small_output = (
        "Running 2 tests using 1 worker\n"
        "  1) [chromium] \u203a tests/e2e/small.spec.ts:10:7 \u203a AC-1\n"
        "   Error: expect(received).toBe(expected)\n"
        "   Expected: true\n"
        "   Received: false\n"
        "  1 failed\n"
        "    [chromium] \u203a tests/e2e/small.spec.ts:10:7 \u203a AC-1\n"
        "  1 passed (2.0s)\n"
    )
    assert len(small_output) < 1000

    result = _run_gate(tmp_wt, monkeypatch, tmp_path, small_output)

    assert result.status == "fail"
    ctx = result.retry_context
    # The complete small output should appear without truncation marker
    assert "expect(received).toBe(expected)" in ctx
    assert "truncated" not in ctx.lower() or "[truncated" not in ctx


def test_retry_context_preserves_failing_test_header(tmp_wt, monkeypatch, tmp_path):
    """AC-3: many-failure header must appear verbatim before any truncation.

    Even if the Playwright output is large, the 'E2E: N NEW failures' + comma-
    separated failure id list must not be cut — the agent needs those ids.
    """
    # Synthesize a Playwright summary with many failing tests so the header
    # generated by execute_e2e_gate is substantial.
    failures = "\n".join(
        f"  {i}) [chromium] \u203a tests/e2e/gen.spec.ts:{10 + i}:7 \u203a REQ-{i}"
        for i in range(1, 35)
    )
    many_failures_stdout = (
        "Running 50 tests using 1 worker\n"
        + failures
        + "\n  34 failed\n"
        + "\n".join(
            f"    [chromium] tests/e2e/gen.spec.ts:{10 + i}:7 REQ-{i}"
            for i in range(1, 35)
        )
        + "\n  16 passed (120.0s)\n"
    )
    big_output = _PRISMA_NOISE + many_failures_stdout + _ASSERTION_ERROR_TAIL

    # Stub _detect_main_worktree + _get_or_create_e2e_baseline so the
    # baseline-comparison branch runs (that is where the "NEW failures"
    # header is prepended).
    from set_project_web import gates as gates_mod
    monkeypatch.setattr(gates_mod, "_detect_main_worktree", lambda wt: "/tmp/fake-main")
    monkeypatch.setattr(
        gates_mod, "_get_or_create_e2e_baseline",
        lambda *a, **kw: {"failures": [], "main_sha": "abc123def456"},
    )

    result = _run_gate(tmp_wt, monkeypatch, tmp_path, big_output)

    ctx = result.retry_context
    # Header is prepended by execute_e2e_gate itself, and must appear intact
    assert "NEW failures" in ctx, f"Missing header in retry_context head: {ctx[:600]!r}"
    assert "tests/e2e/gen.spec.ts:11" in ctx, (
        f"Failure id list dropped from header; head 1500 chars: {ctx[:1500]!r}"
    )
