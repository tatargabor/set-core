"""Tests: Playwright env vars flow from directive → gate → subprocess env.

See OpenSpec change: fix-e2e-infra-systematic (T1.2.4).

The e2e gate was killed at the outer timeout while Playwright's inner
`globalTimeout` still believed it had 3600s — no useful failure list, just
a kill. This regression test guards the env-var flow that aligns them.
"""

from __future__ import annotations

import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))
sys.path.insert(0, str(_ROOT / "modules" / "web"))


def test_e2e_gate_env_includes_pw_timeout_and_fresh_server():
    from set_project_web.project_type import WebProjectType

    profile = WebProjectType()
    env = profile.e2e_gate_env(3142, timeout_seconds=600, fresh_server=True)

    assert env["PW_PORT"] == "3142"
    assert env["PORT"] == "3142"
    assert env["PW_TIMEOUT"] == "600", (
        "PW_TIMEOUT must flow so Playwright.globalTimeout matches the gate budget"
    )
    assert env["PW_FRESH_SERVER"] == "1", (
        "PW_FRESH_SERVER must be set so webServer skips reuseExistingServer"
    )
    # Backward-compat preservation
    assert env["PLAYWRIGHT_SCREENSHOT"] == "on"
    assert env["PRISMA_USER_CONSENT_FOR_DANGEROUS_AI_ACTION"] == "true"


def test_e2e_gate_env_omits_timeout_when_none():
    from set_project_web.project_type import WebProjectType

    profile = WebProjectType()
    env = profile.e2e_gate_env(3150, timeout_seconds=None, fresh_server=False)

    assert "PW_TIMEOUT" not in env, "Unset timeout must NOT inject a stale value"
    assert "PW_FRESH_SERVER" not in env, "fresh_server=False must not set PW_FRESH_SERVER"


def test_abstract_default_signature_accepts_kwargs():
    """The ProjectType ABC default must accept the new kwargs without crashing
    — external plugins that don't override still need to be called with them."""
    from set_orch.profile_loader import NullProfile

    profile = NullProfile()
    env = profile.e2e_gate_env(3000, timeout_seconds=600, fresh_server=True)
    assert env == {}


def test_playwright_config_template_reads_env_vars():
    """The shipped playwright.config.ts must honor PW_TIMEOUT, PW_PORT,
    PW_FRESH_SERVER so the env vars injected by the gate actually take effect."""
    cfg = (
        _ROOT
        / "modules/web/set_project_web/templates/nextjs/playwright.config.ts"
    ).read_text()
    # PW_PORT was already present; preserve.
    assert "process.env.PW_PORT" in cfg
    # New in T1.2:
    assert "process.env.PW_TIMEOUT" in cfg, "config must derive globalTimeout from PW_TIMEOUT"
    assert "process.env.PW_FRESH_SERVER" in cfg, "config must honor PW_FRESH_SERVER"
    assert "reuseExistingServer: !process.env.CI" in cfg, (
        "CI runs must not reuse an existing server"
    )
