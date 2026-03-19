"""Tests for wt_orch.verifier — Test runner, scope checks, review, rules, polling."""

import json
import os
import shutil
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from wt_orch.verifier import (
    ScopeCheckResult,
    TestResult,
    _is_artifact_or_bootstrap,
    _parse_test_stats,
    extract_health_check_url,
    build_req_review_section,
    evaluate_verification_rules,
    _accumulate_tokens,
    _append_review_history,
    _build_review_retry_prompt,
    _build_unified_retry_context,
    _extract_build_errors,
    _extract_test_failures,
    _get_review_history,
)
from wt_orch.state import Change, OrchestratorState


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def state_file(tmp_dir):
    """Create a minimal state file for testing."""
    path = os.path.join(tmp_dir, "state.json")
    state = {
        "plan_version": 1,
        "brief_hash": "test",
        "status": "running",
        "created_at": "2026-03-14T10:00:00",
        "changes": [],
        "merge_queue": [],
        "checkpoints": [],
        "changes_since_checkpoint": 0,
    }
    with open(path, "w") as f:
        json.dump(state, f)
    return path


def _write_state(path: str, changes: list[dict]) -> None:
    """Helper to write state with changes."""
    state = {
        "plan_version": 1,
        "brief_hash": "test",
        "status": "running",
        "created_at": "2026-03-14T10:00:00",
        "changes": changes,
        "merge_queue": [],
        "checkpoints": [],
        "changes_since_checkpoint": 0,
    }
    with open(path, "w") as f:
        json.dump(state, f)


# ─── _parse_test_stats ──────────────────────────────────────────────


class TestParseTestStats:
    def test_jest_output(self):
        output = """
Test Suites:  3 passed, 3 total
Tests:        2 failed, 15 passed, 17 total
"""
        stats = _parse_test_stats(output)
        assert stats is not None
        assert stats["passed"] == 15
        assert stats["failed"] == 2
        assert stats["suites"] == 3
        assert stats["type"] == "jest"

    def test_playwright_output(self):
        output = """
  5 passed (12.3s)
"""
        stats = _parse_test_stats(output)
        assert stats is not None
        assert stats["passed"] == 5
        assert stats["failed"] == 0
        assert stats["type"] == "playwright"

    def test_playwright_with_failures(self):
        output = """
  1 failed, 4 passed (8.1s)
"""
        stats = _parse_test_stats(output)
        assert stats is not None
        assert stats["passed"] == 4
        assert stats["failed"] == 1

    def test_vitest_output(self):
        output = """
Tests  12 passed (3)
"""
        stats = _parse_test_stats(output)
        assert stats is not None
        assert stats["passed"] == 12

    def test_no_stats(self):
        assert _parse_test_stats("some random output") is None

    def test_empty_output(self):
        assert _parse_test_stats("") is None


# ─── _is_artifact_or_bootstrap ──────────────────────────────────────


class TestIsArtifactOrBootstrap:
    def test_openspec_changes(self):
        assert _is_artifact_or_bootstrap("openspec/changes/foo/tasks.md") is True

    def test_openspec_specs(self):
        assert _is_artifact_or_bootstrap("openspec/specs/auth/spec.md") is True

    def test_claude_config(self):
        assert _is_artifact_or_bootstrap(".claude/settings.json") is True

    def test_orchestration(self):
        assert _is_artifact_or_bootstrap("orchestration-state.json") is True

    def test_wt_tools(self):
        assert _is_artifact_or_bootstrap(".wt-tools/config.yaml") is True

    def test_lock_file(self):
        assert _is_artifact_or_bootstrap("pnpm-lock.yaml") is True

    def test_env_file(self):
        assert _is_artifact_or_bootstrap(".env.local") is True

    def test_jest_config(self):
        assert _is_artifact_or_bootstrap("jest.config.ts") is True

    def test_gitignore(self):
        assert _is_artifact_or_bootstrap(".gitignore") is True

    def test_prisma_db(self):
        assert _is_artifact_or_bootstrap("prisma/dev.db") is True

    def test_implementation_file(self):
        assert _is_artifact_or_bootstrap("src/components/Button.tsx") is False

    def test_test_file(self):
        assert _is_artifact_or_bootstrap("tests/unit/test_auth.py") is False

    def test_readme(self):
        assert _is_artifact_or_bootstrap("README.md") is False


# ─── extract_health_check_url ───────────────────────────────────────


class TestExtractHealthCheckUrl:
    def test_with_port(self):
        assert extract_health_check_url("pnpm dev --port 3000 && curl localhost:3000") == "http://localhost:3000"

    def test_no_port(self):
        assert extract_health_check_url("npm test") == ""

    def test_custom_port(self):
        assert extract_health_check_url("check localhost:8080/health") == "http://localhost:8080"

    def test_first_port_wins(self):
        url = extract_health_check_url("localhost:3000 and localhost:4000")
        assert url == "http://localhost:3000"


# ─── build_req_review_section ───────────────────────────────────────


class TestBuildReqReviewSection:
    def test_no_digest_dir(self, state_file):
        """Returns empty when no digest directory."""
        result = build_req_review_section("test-change", state_file, digest_dir="")
        assert result == ""

    def test_no_requirements(self, state_file, tmp_dir):
        """Returns empty when change has no requirements."""
        _write_state(state_file, [{
            "name": "test-change",
            "scope": "test",
            "complexity": "M",
            "change_type": "feature",
            "depends_on": [],
            "status": "running",
            "tokens_used": 0, "tokens_used_prev": 0,
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "input_tokens_prev": 0, "output_tokens_prev": 0,
            "cache_read_tokens_prev": 0, "cache_create_tokens_prev": 0,
            "verify_retry_count": 0, "redispatch_count": 0, "merge_retry_count": 0,
        }])

        digest_dir = os.path.join(tmp_dir, "digest")
        os.makedirs(digest_dir)
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump({"requirements": [{"id": "REQ-1", "title": "Test", "brief": "desc"}]}, f)

        result = build_req_review_section("test-change", state_file, digest_dir=digest_dir)
        assert result == ""

    def test_with_requirements(self, state_file, tmp_dir):
        """Returns section when change has requirements."""
        _write_state(state_file, [{
            "name": "test-change",
            "scope": "test",
            "complexity": "M",
            "change_type": "feature",
            "depends_on": [],
            "status": "running",
            "requirements": ["REQ-1", "REQ-2"],
            "tokens_used": 0, "tokens_used_prev": 0,
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "input_tokens_prev": 0, "output_tokens_prev": 0,
            "cache_read_tokens_prev": 0, "cache_create_tokens_prev": 0,
            "verify_retry_count": 0, "redispatch_count": 0, "merge_retry_count": 0,
        }])

        digest_dir = os.path.join(tmp_dir, "digest")
        os.makedirs(digest_dir)
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump({"requirements": [
                {"id": "REQ-1", "title": "Auth", "brief": "Login system"},
                {"id": "REQ-2", "title": "API", "brief": "REST endpoints"},
            ]}, f)

        result = build_req_review_section("test-change", state_file, digest_dir=digest_dir)
        assert "REQ-1: Auth" in result
        assert "REQ-2: API" in result
        assert "Assigned Requirements" in result
        assert "Requirement Coverage Check" in result

    def test_with_also_affects(self, state_file, tmp_dir):
        """Includes cross-cutting requirements section."""
        _write_state(state_file, [{
            "name": "test-change",
            "scope": "test",
            "complexity": "M",
            "change_type": "feature",
            "depends_on": [],
            "status": "running",
            "requirements": ["REQ-1"],
            "also_affects_reqs": ["REQ-X"],
            "tokens_used": 0, "tokens_used_prev": 0,
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "input_tokens_prev": 0, "output_tokens_prev": 0,
            "cache_read_tokens_prev": 0, "cache_create_tokens_prev": 0,
            "verify_retry_count": 0, "redispatch_count": 0, "merge_retry_count": 0,
        }])

        digest_dir = os.path.join(tmp_dir, "digest")
        os.makedirs(digest_dir)
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump({"requirements": [
                {"id": "REQ-1", "title": "Auth", "brief": "Login"},
                {"id": "REQ-X", "title": "Cross", "brief": "Shared"},
            ]}, f)

        result = build_req_review_section("test-change", state_file, digest_dir=digest_dir)
        assert "Cross-Cutting Requirements" in result
        assert "REQ-X: Cross" in result

    def test_ac_checkboxes_rendered(self, state_file, tmp_dir):
        """When requirements have acceptance_criteria, renders as checkboxes."""
        _write_state(state_file, [{
            "name": "test-change",
            "scope": "test",
            "complexity": "M",
            "change_type": "feature",
            "depends_on": [],
            "status": "running",
            "requirements": ["REQ-1"],
            "tokens_used": 0, "tokens_used_prev": 0,
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "input_tokens_prev": 0, "output_tokens_prev": 0,
            "cache_read_tokens_prev": 0, "cache_create_tokens_prev": 0,
            "verify_retry_count": 0, "redispatch_count": 0, "merge_retry_count": 0,
        }])

        digest_dir = os.path.join(tmp_dir, "digest")
        os.makedirs(digest_dir)
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump({"requirements": [
                {
                    "id": "REQ-1",
                    "title": "Add to cart",
                    "brief": "Users can add items",
                    "acceptance_criteria": [
                        "POST /api/cart/items → 201",
                        "Stock decremented by quantity",
                    ],
                },
            ]}, f)

        result = build_req_review_section("test-change", state_file, digest_dir=digest_dir)
        assert "REQ-1: Add to cart" in result
        assert "- [ ] POST /api/cart/items → 201" in result
        assert "- [ ] Stock decremented by quantity" in result
        # Brief should NOT appear when AC is present
        assert "Users can add items" not in result
        # AC-aware coverage check instruction
        assert "ac item text" in result.lower() or "AC item" in result

    def test_ac_absent_falls_back_to_brief(self, state_file, tmp_dir):
        """When acceptance_criteria is absent, falls back to title — brief."""
        _write_state(state_file, [{
            "name": "test-change",
            "scope": "test",
            "complexity": "M",
            "change_type": "feature",
            "depends_on": [],
            "status": "running",
            "requirements": ["REQ-1"],
            "tokens_used": 0, "tokens_used_prev": 0,
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "input_tokens_prev": 0, "output_tokens_prev": 0,
            "cache_read_tokens_prev": 0, "cache_create_tokens_prev": 0,
            "verify_retry_count": 0, "redispatch_count": 0, "merge_retry_count": 0,
        }])

        digest_dir = os.path.join(tmp_dir, "digest")
        os.makedirs(digest_dir)
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump({"requirements": [
                {"id": "REQ-1", "title": "Auth", "brief": "Login system"},
            ]}, f)

        result = build_req_review_section("test-change", state_file, digest_dir=digest_dir)
        assert "REQ-1: Auth — Login system" in result
        # Coarse-grained check (no AC items)
        assert "REQ-ID has no implementation" in result


# ─── evaluate_verification_rules ────────────────────────────────────


class TestEvaluateVerificationRules:
    def test_no_pk_file(self):
        """Returns empty result when no project-knowledge.yaml."""
        result = evaluate_verification_rules("test", "/tmp", pk_file="/nonexistent")
        assert result.errors == 0
        assert result.warnings == 0

    def test_with_rules(self, tmp_dir):
        """Evaluates rules against changed files."""
        pk_file = os.path.join(tmp_dir, "project-knowledge.yaml")

        try:
            import yaml
            with open(pk_file, "w") as f:
                yaml.dump({
                    "verification_rules": [
                        {"name": "schema-check", "trigger": "prisma/*.prisma", "severity": "error", "check": "Run prisma validate"},
                        {"name": "doc-check", "trigger": "docs/*.md", "severity": "warning", "check": "Check links"},
                    ]
                }, f)
        except ImportError:
            pytest.skip("PyYAML not available")

        # Can't easily test with real git diff, but we verify the function loads rules
        result = evaluate_verification_rules("test", tmp_dir, pk_file=pk_file)
        # No changed files (no git repo) → 0 errors/warnings
        assert result.errors == 0
        assert result.warnings == 0

    def test_empty_rules(self, tmp_dir):
        """Returns empty result when rules list is empty."""
        pk_file = os.path.join(tmp_dir, "project-knowledge.yaml")

        try:
            import yaml
            with open(pk_file, "w") as f:
                yaml.dump({"verification_rules": []}, f)
        except ImportError:
            pytest.skip("PyYAML not available")

        result = evaluate_verification_rules("test", tmp_dir, pk_file=pk_file)
        assert result.errors == 0


# ─── _accumulate_tokens ─────────────────────────────────────────────


class TestAccumulateTokens:
    def test_adds_prev_tokens(self, state_file):
        """Accumulates current loop tokens with _prev values."""
        _write_state(state_file, [{
            "name": "token-test",
            "scope": "test",
            "complexity": "M",
            "change_type": "feature",
            "depends_on": [],
            "status": "running",
            "tokens_used": 0,
            "tokens_used_prev": 5000,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_create_tokens": 0,
            "input_tokens_prev": 3000,
            "output_tokens_prev": 2000,
            "cache_read_tokens_prev": 1000,
            "cache_create_tokens_prev": 500,
            "verify_retry_count": 0,
            "redispatch_count": 0,
            "merge_retry_count": 0,
        }])

        _accumulate_tokens(state_file, "token-test", {
            "total": 10000,
            "input": 6000,
            "output": 4000,
            "cache_read": 2000,
            "cache_create": 1000,
        })

        with open(state_file) as f:
            st = json.load(f)
        c = st["changes"][0]
        assert c["tokens_used"] == 15000  # 10000 + 5000
        assert c["input_tokens"] == 9000   # 6000 + 3000
        assert c["output_tokens"] == 6000  # 4000 + 2000

    def test_nonexistent_change(self, state_file):
        """Handles nonexistent change gracefully."""
        _write_state(state_file, [])
        # Should not raise
        _accumulate_tokens(state_file, "nonexistent", {"total": 100, "input": 50, "output": 50, "cache_read": 0, "cache_create": 0})


# ─── Poll status routing ────────────────────────────────────────────


class TestPollStatusRouting:
    """Test the status dispatch logic of poll_change conceptually."""

    def test_missing_worktree_skips(self, state_file):
        """poll_change returns None when worktree_path is missing."""
        _write_state(state_file, [{
            "name": "no-wt",
            "scope": "test",
            "complexity": "M",
            "change_type": "feature",
            "depends_on": [],
            "status": "running",
            "worktree_path": None,
            "tokens_used": 0, "tokens_used_prev": 0,
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "input_tokens_prev": 0, "output_tokens_prev": 0,
            "cache_read_tokens_prev": 0, "cache_create_tokens_prev": 0,
            "verify_retry_count": 0, "redispatch_count": 0, "merge_retry_count": 0,
        }])
        from wt_orch.verifier import poll_change
        result = poll_change("no-wt", state_file)
        assert result is None

    def test_gone_worktree_skips(self, state_file):
        """poll_change returns None when worktree directory is gone."""
        _write_state(state_file, [{
            "name": "gone-wt",
            "scope": "test",
            "complexity": "M",
            "change_type": "feature",
            "depends_on": [],
            "status": "running",
            "worktree_path": "/nonexistent/path/gone",
            "tokens_used": 0, "tokens_used_prev": 0,
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "input_tokens_prev": 0, "output_tokens_prev": 0,
            "cache_read_tokens_prev": 0, "cache_create_tokens_prev": 0,
            "verify_retry_count": 0, "redispatch_count": 0, "merge_retry_count": 0,
        }])
        from wt_orch.verifier import poll_change
        result = poll_change("gone-wt", state_file)
        assert result is None

    def test_no_loop_state_no_pid(self, state_file, tmp_dir):
        """poll_change returns None when no loop-state and no PID."""
        wt_path = os.path.join(tmp_dir, "worktree")
        os.makedirs(wt_path)
        _write_state(state_file, [{
            "name": "no-loop",
            "scope": "test",
            "complexity": "M",
            "change_type": "feature",
            "depends_on": [],
            "status": "running",
            "worktree_path": wt_path,
            "ralph_pid": 0,
            "tokens_used": 0, "tokens_used_prev": 0,
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "input_tokens_prev": 0, "output_tokens_prev": 0,
            "cache_read_tokens_prev": 0, "cache_create_tokens_prev": 0,
            "verify_retry_count": 0, "redispatch_count": 0, "merge_retry_count": 0,
        }])
        from wt_orch.verifier import poll_change
        result = poll_change("no-loop", state_file)
        assert result is None


# ─── Uncommitted work guard in handle_change_done ────────────


class TestHandleChangeDoneUncommittedGuard:
    """Uncommitted work blocks the verify gate before VG-BUILD."""

    def _make_change(self, tmp_dir, state_file, wt_name="uc-test"):
        wt_path = os.path.join(tmp_dir, wt_name)
        os.makedirs(os.path.join(wt_path, ".claude"), exist_ok=True)
        _write_state(state_file, [{
            "name": wt_name,
            "scope": "test uncommitted",
            "complexity": "S",
            "change_type": "feature",
            "depends_on": [],
            "status": "running",
            "worktree_path": wt_path,
            "ralph_pid": 0,
            "tokens_used": 0, "tokens_used_prev": 0,
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "input_tokens_prev": 0, "output_tokens_prev": 0,
            "cache_read_tokens_prev": 0, "cache_create_tokens_prev": 0,
            "verify_retry_count": 0, "redispatch_count": 0, "merge_retry_count": 0,
        }])
        return wt_path

    def test_uncommitted_work_fails_gate(self, tmp_dir, state_file):
        from unittest.mock import patch
        from wt_orch.verifier import handle_change_done

        wt_path = self._make_change(tmp_dir, state_file)

        with patch("wt_orch.git_utils.git_has_uncommitted_work", return_value=(True, "3 modified, 7 untracked")):
            handle_change_done("uc-test", state_file, max_verify_retries=2)

        # Should have set status to pending (retry)
        with open(state_file) as f:
            state = json.load(f)
        change = state["changes"][0]
        assert change["status"] == "pending"
        assert change["verify_retry_count"] == 1
        assert "uncommitted" in change.get("verify_result", "").lower()

    def test_clean_worktree_proceeds_past_guard(self, tmp_dir, state_file):
        """Clean worktree does NOT trigger the uncommitted guard."""
        from unittest.mock import patch
        from wt_orch.verifier import handle_change_done

        wt_path = self._make_change(tmp_dir, state_file)

        with patch("wt_orch.git_utils.git_has_uncommitted_work", return_value=(False, "")) as mock_check:
            # The full pipeline will fail for other reasons (no test files, etc.)
            # but that's fine — we only verify uncommitted guard didn't block
            handle_change_done("uc-test", state_file, max_verify_retries=2)
            mock_check.assert_called_once_with(wt_path)

        with open(state_file) as f:
            state = json.load(f)
        change = state["changes"][0]
        # verify_result should NOT contain "uncommitted"
        verify_result = change.get("verify_result", "")
        assert "uncommitted" not in verify_result.lower()

    def test_uncommitted_exhausts_retries_fails(self, tmp_dir, state_file):
        from unittest.mock import patch
        from wt_orch.verifier import handle_change_done

        wt_path = self._make_change(tmp_dir, state_file)
        # Set retry count at max already
        from wt_orch.state import update_change_field
        update_change_field(state_file, "uc-test", "verify_retry_count", 2)

        with patch("wt_orch.git_utils.git_has_uncommitted_work", return_value=(True, "1 untracked")):
            handle_change_done("uc-test", state_file, max_verify_retries=2)

        with open(state_file) as f:
            state = json.load(f)
        change = state["changes"][0]
        assert change["status"] == "failed"


# ─── Cumulative Review Feedback ─────────────────────────────────────


class TestAppendReviewHistory:
    def test_creates_and_appends(self, state_file):
        _write_state(state_file, [{"name": "auth", "status": "running"}])

        _append_review_history(state_file, "auth", {
            "attempt": 1,
            "review_output": "CRITICAL: cookie check",
            "extracted_fixes": "middleware.ts:35",
            "diff_summary": None,
        })
        history = _get_review_history(state_file, "auth")
        assert len(history) == 1
        assert history[0]["attempt"] == 1
        assert history[0]["diff_summary"] is None

        _append_review_history(state_file, "auth", {
            "attempt": 2,
            "review_output": "CRITICAL: no expiry check",
            "extracted_fixes": "middleware.ts:42",
            "diff_summary": "src/middleware.ts | 5 +++--",
        })
        history = _get_review_history(state_file, "auth")
        assert len(history) == 2
        assert history[1]["diff_summary"] == "src/middleware.ts | 5 +++--"

    def test_nonexistent_change(self, state_file):
        _write_state(state_file, [{"name": "other", "status": "running"}])
        _append_review_history(state_file, "missing", {"attempt": 1})
        assert _get_review_history(state_file, "missing") == []


class TestBuildReviewRetryPrompt:
    def test_first_attempt_no_previous_section(self, state_file):
        _write_state(state_file, [{"name": "auth", "status": "running"}])
        _append_review_history(state_file, "auth", {
            "attempt": 1,
            "review_output": "ISSUE: [CRITICAL] bad auth\nFILE: src/m.ts\nLINE: 35\nFIX: validate token",
            "extracted_fixes": "src/m.ts:35 — bad auth",
            "diff_summary": None,
        })

        prompt = _build_review_retry_prompt(
            state_file, "auth",
            "ISSUE: [CRITICAL] bad auth\nFILE: src/m.ts\nLINE: 35\nFIX: validate token",
            "", 1, 3,
        )
        assert "PREVIOUS ATTEMPTS" not in prompt
        assert "CRITICAL CODE REVIEW FAILURE" in prompt
        assert "LAST attempt" not in prompt

    def test_second_attempt_has_previous_section(self, state_file):
        _write_state(state_file, [{"name": "auth", "status": "running"}])
        _append_review_history(state_file, "auth", {
            "attempt": 1,
            "review_output": "bad cookie",
            "extracted_fixes": "m.ts:35 — cookie",
            "diff_summary": None,
        })
        _append_review_history(state_file, "auth", {
            "attempt": 2,
            "review_output": "still bad",
            "extracted_fixes": "m.ts:42 — expiry",
            "diff_summary": "src/m.ts | 5 +++--",
        })

        prompt = _build_review_retry_prompt(
            state_file, "auth", "still bad", "", 2, 3,
        )
        assert "PREVIOUS ATTEMPTS" in prompt
        assert "DO NOT REPEAT" in prompt
        assert "m.ts:35" in prompt  # prior attempt fix
        assert "src/m.ts | 5 +++--" in prompt  # prior diff
        assert "fundamentally different strategy" in prompt

    def test_final_attempt_escalation(self, state_file):
        _write_state(state_file, [{"name": "auth", "status": "running"}])
        for i in range(3):
            _append_review_history(state_file, "auth", {
                "attempt": i + 1,
                "review_output": f"issue {i}",
                "extracted_fixes": f"fix {i}",
                "diff_summary": f"diff {i}" if i > 0 else None,
            })

        prompt = _build_review_retry_prompt(
            state_file, "auth", "issue 2", "", 2, 3,
        )
        assert "LAST attempt" in prompt
        assert "restructure the entire implementation" in prompt


class TestExtractBuildErrors:
    """Tests for _extract_build_errors() — TypeScript/Next.js build parser."""

    def test_ts_error_paren_format(self):
        output = "src/app/page.tsx(67,5): error TS2339: Property 'total' does not exist on type 'Order'"
        result = _extract_build_errors(output)
        assert "src/app/page.tsx:67" in result
        assert "TS2339" in result
        assert "Property 'total'" in result

    def test_ts_error_colon_format(self):
        output = "src/lib/utils.ts:12:3 - error TS2304: Cannot find name 'foo'"
        result = _extract_build_errors(output)
        assert "src/lib/utils.ts:12" in result
        assert "TS2304" in result

    def test_multiple_errors_deduped(self):
        output = (
            "src/a.tsx(1,1): error TS2339: Prop X\n"
            "src/a.tsx(1,1): error TS2339: Prop X\n"
            "src/b.tsx(2,1): error TS2345: Type Y\n"
        )
        result = _extract_build_errors(output)
        assert result.count("src/a.tsx:1") == 1
        assert "src/b.tsx:2" in result

    def test_module_not_found(self):
        output = "Module not found: Can't resolve '@/components/Foo' in '/app/src'"
        result = _extract_build_errors(output)
        assert "Module not found" in result
        assert "@/components/Foo" in result

    def test_no_known_patterns_returns_empty(self):
        assert _extract_build_errors("some random output") == ""

    def test_mixed_errors(self):
        output = (
            "src/page.tsx(10,1): error TS2339: Missing prop\n"
            "Module not found: Can't resolve 'missing-pkg'\n"
        )
        result = _extract_build_errors(output)
        assert "TS2339" in result
        assert "missing-pkg" in result


class TestExtractTestFailures:
    """Tests for _extract_test_failures() — Jest/Vitest parser."""

    def test_jest_fail_with_assertion(self):
        output = (
            " FAIL src/tests/checkout.test.ts\n"
            "  ✕ should calculate shipping (5 ms)\n"
            "    Expected: 1500\n"
            "    Received: undefined\n"
        )
        result = _extract_test_failures(output)
        assert "checkout.test.ts" in result
        assert "should calculate shipping" in result
        assert "Expected 1500" in result
        assert "received undefined" in result

    def test_multiple_failing_tests(self):
        output = (
            " FAIL src/tests/cart.test.ts\n"
            "  ✕ should add item (3 ms)\n"
            "    Expected: 1\n"
            "    Received: 0\n"
            "  ✕ should remove item (2 ms)\n"
            "    Expected: 0\n"
            "    Received: 1\n"
        )
        result = _extract_test_failures(output)
        assert "should add item" in result
        assert "should remove item" in result

    def test_fail_file_only_no_test_names(self):
        output = " FAIL src/tests/broken.test.ts\n  SyntaxError: Unexpected token\n"
        result = _extract_test_failures(output)
        assert "FAIL" in result
        assert "broken.test.ts" in result

    def test_no_failures_returns_empty(self):
        output = " PASS src/tests/good.test.ts\n  ✓ works (1 ms)\n"
        assert _extract_test_failures(output) == ""


class TestUnifiedRetryContext:
    """Tests for _build_unified_retry_context()."""

    def test_build_only(self):
        result = _build_unified_retry_context(
            build_output="src/a.tsx(1,1): error TS2339: Bad prop",
            attempt=1, max_attempts=3,
        )
        assert "## Retry Context (Attempt 1/3)" in result
        assert "### Build Errors" in result
        assert "TS2339" in result
        assert "re-read the files" in result

    def test_test_only(self):
        result = _build_unified_retry_context(
            test_output=" FAIL src/test.ts\n  ✕ fails (1 ms)\n    Expected: 1\n    Received: 0\n",
            attempt=2, max_attempts=3,
        )
        assert "### Test Failures" in result
        assert "fails" in result

    def test_combined_build_and_review(self):
        result = _build_unified_retry_context(
            build_output="src/a.tsx(1,1): error TS2339: X",
            review_output="ISSUE: [CRITICAL] Missing auth\nFILE: src/api.ts\nLINE: ~10\nFIX: Add guard",
            attempt=1, max_attempts=3,
        )
        assert "### Build Errors" in result
        assert "### Review Issues" in result
        assert "TS2339" in result
        assert "Missing auth" in result

    def test_fallback_to_raw_on_unknown_format(self):
        result = _build_unified_retry_context(
            build_output="ERROR: something weird happened that we can't parse",
            attempt=1, max_attempts=2,
        )
        assert "### Build Errors" in result
        assert "```" in result  # raw fallback wrapped in code block
        assert "something weird happened" in result

    def test_reread_instruction_always_present(self):
        result = _build_unified_retry_context(
            build_output="src/a.tsx(1,1): error TS2339: X",
        )
        assert "re-read the files" in result

    def test_review_retry_no_raw_when_fixes_extracted(self):
        """Review retry prompt should NOT include raw output when fix_instructions exist."""
        review_output = (
            "ISSUE: [CRITICAL] SQL injection\n"
            "FILE: src/api.ts\n"
            "LINE: ~42\n"
            "FIX: Use parameterized query\n"
        )
        prompt = _build_review_retry_prompt.__wrapped__(review_output) if hasattr(_build_review_retry_prompt, '__wrapped__') else None
        # Test via unified context instead
        result = _build_unified_retry_context(review_output=review_output)
        assert "src/api.ts" in result
        assert "SQL injection" in result
        # Should use structured format, not raw fallback
        assert "```" not in result
