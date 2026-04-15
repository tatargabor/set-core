"""Tests: e2e gate fails on flaky tests when PW_FLAKY_FAILS=1.

Root cause surfaced on craftbrew-run-20260415-0146 auth-and-accounts:
  REQ-AUTH-001:AC-3 registered user but signIn() raced session-cookie
  propagation. Playwright retried (retries: 1) and the second attempt
  passed once timing stabilized. exit_code=0 → gate PASSED → merge.

  Production users don't retry. The bug ships with a green gate.

Fix surface:
  (a) playwright.config.ts honors PW_FLAKY_FAILS=1 (retries: 0)
  (b) gate runner parses "N flaky" summary and treats flaky>0 as fail
  (c) profile.e2e_gate_env injects PW_FLAKY_FAILS=1 in orchestration
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))
sys.path.insert(0, str(_ROOT / "modules" / "web"))


def test_count_flaky_tests_extracts_playwright_summary():
    from set_project_web.gates import _count_flaky_tests

    out = """
Running 40 tests using 1 worker.

  1 flaky
    [chromium] > tests/e2e/auth-and-accounts.spec.ts:49:7 > REQ-AUTH-001:AC-3

  40 passed (45.0s)
"""
    assert _count_flaky_tests(out) == 1


def test_count_flaky_tests_returns_zero_when_no_flaky_line():
    from set_project_web.gates import _count_flaky_tests

    out = "Running 40 tests\n\n40 passed (30.0s)\n"
    assert _count_flaky_tests(out) == 0


def test_count_flaky_tests_handles_multiple_summaries():
    from set_project_web.gates import _count_flaky_tests

    out = """
1 flaky
(retry report)

3 flaky
42 passed (60s)
"""
    # max of multiple matches
    assert _count_flaky_tests(out) == 3


def test_count_flaky_tests_strips_ansi():
    from set_project_web.gates import _count_flaky_tests

    out = "\x1b[33m2 flaky\x1b[0m\n\x1b[32m40 passed\x1b[0m\n"
    assert _count_flaky_tests(out) == 2


def test_count_flaky_tests_empty_input():
    from set_project_web.gates import _count_flaky_tests
    assert _count_flaky_tests("") == 0
    assert _count_flaky_tests(None) == 0  # type: ignore[arg-type]


def test_profile_e2e_gate_env_injects_pw_flaky_fails():
    """Orchestration context: every e2e run must disable Playwright retries
    via PW_FLAKY_FAILS=1 so a passing-on-retry test counts as failure."""
    from set_project_web.project_type import WebProjectType

    env = WebProjectType().e2e_gate_env(3147, timeout_seconds=600, fresh_server=True)
    assert env.get("PW_FLAKY_FAILS") == "1", (
        "Orchestration must set PW_FLAKY_FAILS=1 so the Playwright config runs "
        "with retries: 0 — flaky = bug, not jitter"
    )


def test_playwright_config_honors_pw_flaky_fails():
    """Template config must read PW_FLAKY_FAILS and set retries: 0 accordingly."""
    cfg = (
        _ROOT
        / "modules/web/set_project_web/templates/nextjs/playwright.config.ts"
    ).read_text()
    assert "PW_FLAKY_FAILS" in cfg
    assert "retries: process.env.PW_FLAKY_FAILS" in cfg, (
        "retries must branch on PW_FLAKY_FAILS — otherwise the env var is ignored"
    )
