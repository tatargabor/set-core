"""Tests for set_orch.templates — Safe structured text generation."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.templates import (
    escape_for_prompt,
    render_fix_prompt,
    render_planning_prompt,
    render_proposal,
    render_review_prompt,
    render_build_fix_prompt,
)


class TestEscapeForPrompt:
    def test_plain_text_passthrough(self):
        assert escape_for_prompt("hello world") == "hello world"

    def test_dollar_sign(self):
        result = escape_for_prompt("function $foo() { return $bar; }")
        assert "$foo" in result
        assert "$bar" in result

    def test_backticks(self):
        result = escape_for_prompt("Error: `undefined` is not a function")
        assert "`undefined`" in result

    def test_eof_marker(self):
        result = escape_for_prompt("some text\nEOF\nmore text")
        assert "EOF" in result

    def test_empty_string(self):
        assert escape_for_prompt("") == ""

    def test_none_like(self):
        assert escape_for_prompt("") == ""


class TestRenderProposal:
    def test_all_fields(self):
        result = render_proposal(
            change_name="add-auth",
            scope="Add authentication system",
            roadmap_item="Authentication and authorization",
            memory_ctx="Previous auth attempts failed",
            spec_ref="docs/spec.md",
        )
        assert "## Why" in result
        assert "Authentication and authorization" in result
        assert "Add authentication system" in result
        assert "`add-auth`" in result
        assert "## Context from Memory" in result
        assert "Previous auth attempts" in result
        assert "## Source Spec" in result
        assert "`docs/spec.md`" in result

    def test_optional_fields_empty(self):
        result = render_proposal(
            change_name="fix-bug",
            scope="Fix login",
            roadmap_item="Bug fix",
        )
        assert "## Why" in result
        assert "## Context from Memory" not in result
        assert "## Source Spec" not in result

    def test_special_chars_in_scope(self):
        result = render_proposal(
            change_name="test",
            scope="Fix $HOME path `expansion` in tests",
            roadmap_item="item",
        )
        assert "$HOME" in result
        assert "`expansion`" in result


class TestRenderReviewPrompt:
    def test_basic_review(self):
        result = render_review_prompt(
            scope="Add login page",
            diff_output="+ const login = () => {}",
            req_section="REQ-AUTH-01",
        )
        assert "senior code reviewer" in result
        assert "Add login page" in result
        assert "```diff" in result
        assert "const login" in result
        assert "REQ-AUTH-01" in result
        assert "REVIEW PASS" in result

    def test_special_chars_in_diff(self):
        diff = 'const home = "$HOME";\nconst cmd = `ls -la`;'
        result = render_review_prompt(scope="test", diff_output=diff)
        assert "$HOME" in result
        assert "`ls -la`" in result

    def test_truncation(self):
        huge_diff = "x" * 60_000
        result = render_review_prompt(scope="test", diff_output=huge_diff)
        assert "truncated" in result
        assert len(result) < 55_000  # truncated to 50k + template overhead


class TestRenderFixPrompt:
    def test_smoke_variant(self):
        result = render_fix_prompt(
            change_name="add-auth",
            scope="",
            output_tail="Error: test failed\n  at line 42",
            smoke_cmd="npm test",
            variant="smoke",
        )
        assert "Post-merge smoke/e2e tests failed" in result
        assert "add-auth" in result
        assert "npm test" in result
        assert "Error: test failed" in result

    def test_scoped_variant(self):
        result = render_fix_prompt(
            change_name="add-auth",
            scope="Auth system scope",
            output_tail="FAIL: login.test.ts",
            smoke_cmd="npm test",
            modified_files="src/auth.ts\nsrc/login.ts",
            variant="scoped",
        )
        assert "MAY ONLY modify files" in result
        assert "src/auth.ts" in result

    def test_output_truncation_smoke(self):
        huge_output = "x" * 5000
        result = render_fix_prompt(
            change_name="test",
            scope="",
            output_tail=huge_output,
            smoke_cmd="test",
            variant="smoke",
        )
        # Should only include last 2000 chars
        lines = result.split("\n")
        # The output section should be limited
        assert "last 2000 chars" in result


class TestRenderBuildFixPrompt:
    def test_basic(self):
        result = render_build_fix_prompt(
            pm="npm",
            build_cmd="build",
            build_output="TS2304: Cannot find name 'Foo'",
        )
        assert "npm run build" in result
        assert "Cannot find name" in result
        assert "fix: repair main branch build errors" in result


class TestRenderPlanningPrompt:
    def test_spec_mode_basic(self):
        result = render_planning_prompt(
            input_content="# My Spec\n- Feature A\n- Feature B",
            specs="No existing specs",
            mode="spec",
        )
        assert "software architect analyzing" in result
        assert "Project Specification" in result
        assert "Feature A" in result
        assert "kebab-case" in result
        assert "phase_detected" in result

    def test_brief_mode_basic(self):
        result = render_planning_prompt(
            input_content="# My Brief\nBuild a todo app",
            specs="No specs",
            mode="brief",
        )
        assert "decomposing a project brief" in result
        assert "Project Brief" in result
        assert "Build a todo app" in result

    def test_replan_context(self):
        result = render_planning_prompt(
            input_content="spec content",
            specs="",
            mode="spec",
            replan_ctx={
                "completed": "add-auth, add-login",
                "cycle": 2,
                "memory": "Previous cycle had merge conflicts",
                "e2e_failures": "login.spec.ts: timeout waiting for element",
            },
        )
        assert "Already Completed (cycle 2)" in result
        assert "add-auth, add-login" in result
        assert "Orchestration History" in result
        assert "merge conflicts" in result
        assert "E2E Test Failures" in result
        assert "login.spec.ts" in result

    def test_initial_plan_no_replan(self):
        result = render_planning_prompt(
            input_content="spec",
            specs="",
            mode="spec",
        )
        # The replan-specific SECTIONS should not appear (note: the static task
        # instruction mentions "Already Completed" as a reference, which is fine)
        assert "## IMPORTANT: Already Completed" not in result
        assert "## Orchestration History" not in result
        assert "## Phase-End E2E Test Failures" not in result

    def test_memory_context(self):
        result = render_planning_prompt(
            input_content="spec",
            specs="",
            memory="Auth system uses JWT tokens",
            mode="spec",
        )
        assert "## Project Memory" in result
        assert "JWT tokens" in result

    def test_empty_memory_omitted(self):
        result = render_planning_prompt(
            input_content="spec",
            specs="",
            memory="",
            mode="spec",
        )
        assert "## Project Memory" not in result

    def test_digest_mode(self):
        result = render_planning_prompt(
            input_content="spec",
            specs="",
            mode="spec",
            input_mode="digest",
        )
        assert "spec_files" in result
        assert "requirements" in result
        assert "also_affects_reqs" in result
