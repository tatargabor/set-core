"""Test: reviewer prompt + retry-review prompt enforce exhaustive single-pass
scanning and regression prevention.

Observed pattern on craftbrew-run-20260415-0146 auth-and-accounts: the reviewer
found one CRITICAL per round in the same `src/auth.ts` session callback —
round 3 flagged "double type cast on tokenVersion mismatch", round 6 (retries
exhausted) flagged "DB-error catch bypasses tokenVersion invalidation". Both
were fail-open-on-error bugs in sibling branches of the same function.

The agent fixed each as surfaced and committed a correct final fix 3 minutes
AFTER retry exhaustion (65621a9). A single-pass exhaustive review + an
agent-side regression-preventive fix prompt would have bundled both issues
into one round and saved the change.

These tests pin the prompt CONTENT so future edits can't silently drop the
directives. They do NOT assert LLM behavior — only that the framework hands
the model the right instructions.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))


# ─── Reviewer prompt — single-pass exhaustive scan ─────────────────────


def test_review_prompt_contains_exhaustive_scan_directive():
    from set_orch.templates import render_review_prompt

    prompt = render_review_prompt(
        scope="Implement auth with JWT + tokenVersion invalidation.",
        diff_output="+ export async function session() { try { ... } catch { return {}; } }",
    )
    assert "Exhaustive Single-Pass Scan" in prompt, (
        "Reviewer prompt must declare exhaustive single-pass scanning"
    )
    # Anti-whack-a-mole directives
    assert "EVERY CRITICAL and HIGH" in prompt
    assert "Do NOT defer findings to a future round" in prompt
    # Specific pattern-match coaching for the bug class observed
    assert "fail-open" in prompt.lower(), (
        "Prompt must coach the reviewer on the fail-open pattern (biggest observed cause)"
    )
    assert "every other catch" in prompt.lower() or "every catch" in prompt.lower(), (
        "Reviewer must be told to scan sibling catches when one is flagged"
    )


def test_review_prompt_contains_mental_checklist():
    from set_orch.templates import render_review_prompt

    prompt = render_review_prompt(scope="x", diff_output="x")
    # Mental checklist the reviewer runs before emitting findings
    for item in [
        "Happy path",
        "catch",
        "fallback",
        "type coercion",
        "auth",
    ]:
        assert item.lower() in prompt.lower(), (
            f"Reviewer checklist must reference '{item}'"
        )


def test_review_prompt_still_respects_scope_rubric():
    """Regression: the new scan directive must not drop the existing
    scope-boundary and severity-rubric sections."""
    from set_orch.templates import render_review_prompt

    prompt = render_review_prompt(scope="x", diff_output="x")
    # Pre-existing sections survive
    assert "Scope Boundaries" in prompt
    assert "Severity Rubric" in prompt
    assert "CRITICAL" in prompt and "HIGH" in prompt
    # Output format preserved
    assert "REVIEW PASS" in prompt
    assert "ISSUE: [severity]" in prompt


# ─── Retry prompt (agent fix side) — regression prevention ─────────────


def _fake_state_file_with_review_history(
    tmp_path: Path, change_name: str, attempt_count: int = 2,
) -> str:
    """Seed a minimal state.json so _build_review_retry_prompt can find history."""
    import json

    state = {
        "status": "running",
        "changes": [{
            "name": change_name,
            "status": "verify-failed",
            "scope": "auth",
            "verify_retry_count": attempt_count,
            "review_history": [
                {"attempt": i + 1, "diff_summary": f"round {i+1} fix", "critical_count": 1}
                for i in range(attempt_count)
            ],
        }],
    }
    p = tmp_path / "state.json"
    p.write_text(json.dumps(state))
    return str(p)


def test_retry_prompt_contains_regression_prevention_block(tmp_path: Path):
    from set_orch.verifier import _build_review_retry_prompt

    state_file = _fake_state_file_with_review_history(tmp_path, "auth-and-accounts", 2)
    prompt = _build_review_retry_prompt(
        state_file=state_file,
        change_name="auth-and-accounts",
        current_review_output=(
            "### CRITICAL\n"
            "**ISSUE: [CRITICAL] Session callback DB-error catch bypasses tokenVersion**\n"
            "FILE: src/auth.ts\nLINE: 20-27\n"
            "FIX: return an invalidated session on DB error\n"
        ),
        security_guide="",
        verify_retry_count=2,
        review_retry_limit=5,
    )
    assert "DO NOT CREATE NEW BUGS WHILE FIXING" in prompt, (
        "Retry prompt must explicitly warn about introducing new bugs"
    )
    # Explicit reference to the fail-open pattern with actionable guidance
    assert '"Fail closed"' in prompt or "Fail closed" in prompt
    # Self-review checklist present
    for item in ["try/catch", "type coercion", "fallback", "transactional", "auth"]:
        assert item in prompt.lower() or item.replace("/", "/") in prompt, item
    # Explicit instruction to scan sibling branches after a fix
    assert "every OTHER catch" in prompt or "every other catch" in prompt


def test_retry_prompt_includes_raw_review_output(tmp_path: Path):
    """Agent must still see the reviewer's verbatim findings — not just the summary."""
    from set_orch.verifier import _build_review_retry_prompt

    state_file = _fake_state_file_with_review_history(tmp_path, "auth-and-accounts", 1)
    review_text = (
        "## Review\n"
        "ISSUE: [CRITICAL] tokenVersion mismatch returns valid session\n"
        "FILE: src/auth.ts\nLINE: 22\n"
        "FIX: return {} instead of session.user populated from jwt\n"
    )
    prompt = _build_review_retry_prompt(
        state_file=state_file,
        change_name="auth-and-accounts",
        current_review_output=review_text,
        security_guide="",
        verify_retry_count=1,
        review_retry_limit=5,
    )
    assert "tokenVersion mismatch returns valid session" in prompt, (
        "Verbatim reviewer output must be preserved in the retry prompt"
    )
    assert "FIX: return {} instead" in prompt


def test_retry_prompt_instruction_ordering_self_review_before_commit(tmp_path: Path):
    """The instruction list must order: fix → self-review checklist → commit.
    Agents follow numbered lists top-down; if commit comes before the
    self-review step, the regression prevention is effectively dead.
    """
    from set_orch.verifier import _build_review_retry_prompt

    state_file = _fake_state_file_with_review_history(tmp_path, "auth-and-accounts", 1)
    prompt = _build_review_retry_prompt(
        state_file=state_file,
        change_name="auth-and-accounts",
        current_review_output="[CRITICAL] x\nFILE: a.ts\nLINE: 1\nFIX: y",
        security_guide="",
        verify_retry_count=0,
        review_retry_limit=5,
    )
    # Find positions of the key numbered steps.
    apply_fix_pos = prompt.find("apply the FIX")
    self_review_pos = prompt.find("self-review checklist")
    commit_pos = prompt.find("Commit all changes")
    assert apply_fix_pos < self_review_pos < commit_pos, (
        f"Order wrong: apply={apply_fix_pos}, self_review={self_review_pos}, "
        f"commit={commit_pos} — self-review MUST come before commit"
    )


# ─── Reviewer retry-mode prompt (fix_verification_prefix) ──────────────


def test_retry_review_scans_fix_diff_for_regressions():
    """In retry rounds the reviewer must both (a) verify prior findings were
    fixed, and (b) audit the agent's fix diff for new regressions. The prior
    implementation explicitly said 'Do NOT scan for new issues' — but the
    agent's fix code IS new code, and regressions there must still be flagged.
    """
    # Build the prefix the way the review gate builds it: format with a
    # placeholder prior-findings block.
    from set_orch.verifier import _read_prior_review_findings  # noqa
    # Extract the prefix template via a small reproducer. The prefix is
    # inline in review_gate; rather than refactor, we rebuild the same
    # string here from the literal template and assert our new directives
    # landed there by re-rendering via the review gate path's inline literal.
    # We test the OBSERVABLE output by stubbing _read_prior_review_findings
    # and calling the gate with verify_retry_count=2.
    from types import SimpleNamespace

    from set_orch import verifier

    # Minimal stand-in stubs — only enough for the prefix branch to execute.
    captured_prompt_prefix = {"value": ""}

    def _fake_review_change(*args, **kwargs):
        captured_prompt_prefix["value"] = kwargs.get("prompt_prefix", "")
        return SimpleNamespace(has_critical=False, output="")

    fake_change = SimpleNamespace(
        scope="auth", extras={}, name="auth-and-accounts",
    )
    fake_gc = SimpleNamespace(
        review_model="opus", is_blocking=lambda _: False,
    )

    with (
        patch.object(verifier, "review_change", side_effect=_fake_review_change),
        patch.object(
            verifier, "_read_prior_review_findings",
            return_value="[CRITICAL] Session callback catch bypasses tokenVersion\nFILE: src/auth.ts",
        ),
        patch.object(verifier, "_write_review_findings_md", return_value=None),
        patch.object(verifier, "_append_review_finding", return_value=None),
        patch.object(verifier, "_append_review_history", return_value=None),
    ):
        # Drive the review gate just enough to populate prompt_prefix.
        verifier._execute_review_gate(
            change_name="auth-and-accounts",
            change=fake_change,
            wt_path="/tmp/fake-wt",
            review_model="opus",
            state_file="/tmp/fake-state.json",
            design_snapshot_dir="",
            verify_retry_count=2,
            gc=fake_gc,
        )

    prefix = captured_prompt_prefix["value"]
    # New dual-job framing
    assert "Job 1" in prefix and "Job 2" in prefix, (
        "Retry-review prefix must declare two jobs: verify prior + audit fix diff"
    )
    # Must explicitly allow flagging regressions introduced by the fix
    assert "REGRESSION introduced by fix" in prefix
    # Must keep the "don't re-scan previously-correct code" discipline
    assert "Do NOT re-scan" in prefix or "do NOT re-scan" in prefix
    # Must still include the prior findings verbatim
    assert "Session callback catch bypasses tokenVersion" in prefix
