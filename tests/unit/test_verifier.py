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
