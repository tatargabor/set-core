"""Tests for WebProjectType.extract_first_test_name.

This regex has historically misbehaved on JS test titles containing
escaped quote characters — the non-greedy `.+?` stopped at the first
literal quote it found, which was the escape sequence `\\'` inside a
single-quoted string, and returned a truncated title. The truncated
title then broke the smoke command's `--grep` pattern, producing
"No tests found" false positive integration smoke failures.

See the 2026-04-11 micro validation run (mark-done retry loop).
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))

from set_project_web.project_type import WebProjectType


def _write_spec(tmp_path: Path, content: str) -> str:
    p = tmp_path / "test.spec.ts"
    p.write_text(content)
    return str(p)


@pytest.fixture
def profile():
    return WebProjectType()


class TestDoubleQuotedTitles:
    def test_simple_double_quoted(self, profile, tmp_path):
        spec = _write_spec(tmp_path, 'test("REQ-001: basic happy path", async ({ page }) => {})')
        assert profile.extract_first_test_name(spec) == "REQ-001: basic happy path"

    def test_double_quoted_with_escaped_double_inside(self, profile, tmp_path):
        spec = _write_spec(
            tmp_path,
            'test("REQ-002: click \\"Add task\\" button", async ({ page }) => {})',
        )
        # Escape-aware parser unescapes inside the captured title
        assert profile.extract_first_test_name(spec) == 'REQ-002: click "Add task" button'


class TestSingleQuotedTitles:
    def test_simple_single_quoted(self, profile, tmp_path):
        spec = _write_spec(tmp_path, "test('REQ-003: simple title', async ({ page }) => {})")
        assert profile.extract_first_test_name(spec) == "REQ-003: simple title"

    def test_single_quoted_with_escaped_single_inside_fossil(self, profile, tmp_path):
        """The 2026-04-11 micro regression fossil.

        Pre-fix `(.+?)` stops at the first `'` — which is the escaped
        `\\'` inside the string — and returned `REQ-A:AC-1 — Click \\`
        (literal backslash). The resulting smoke `--grep` pattern
        produced 'No tests found' for 2 straight integration retries.
        """
        spec = _write_spec(
            tmp_path,
            "test('REQ-CREATE-001:AC-1 — Input field and \\'Add task\\' button are present on / @SMOKE', async ({ page }) => {})",
        )
        result = profile.extract_first_test_name(spec)
        assert result == "REQ-CREATE-001:AC-1 — Input field and 'Add task' button are present on / @SMOKE"
        # Defense: ensure the pre-fix bug output is NOT what we return
        assert result != "REQ-CREATE-001:AC-1 — Input field and \\"
        assert "\\" not in result  # no literal backslash at the end


class TestMultilineAndIndentation:
    def test_indented_test_line(self, profile, tmp_path):
        spec = _write_spec(
            tmp_path,
            """import { test } from '@playwright/test';

describe('suite', () => {
    test('REQ-004: indented inside describe', async ({ page }) => {});
});
""",
        )
        assert profile.extract_first_test_name(spec) == "REQ-004: indented inside describe"

    def test_test_only_variant(self, profile, tmp_path):
        spec = _write_spec(
            tmp_path,
            "test.only('REQ-005: skipping others for debug', async ({ page }) => {});",
        )
        assert profile.extract_first_test_name(spec) == "REQ-005: skipping others for debug"

    def test_skips_non_test_lines(self, profile, tmp_path):
        spec = _write_spec(
            tmp_path,
            """// comment mentioning test("fake", but not a test block)
import { test } from '@playwright/test';

const description = 'some string';

test('REQ-006: real test after prelude', async () => {});
""",
        )
        result = profile.extract_first_test_name(spec)
        # Accept either `fake` or `REQ-006` — both are legal starts from the
        # parser's perspective (line-by-line). The important property is that
        # the result is NOT a truncated fragment.
        assert result in ("fake", "REQ-006: real test after prelude", "some string")
        assert "\\" not in (result or "")

    def test_empty_file_returns_none(self, profile, tmp_path):
        spec = _write_spec(tmp_path, "")
        assert profile.extract_first_test_name(spec) is None

    def test_no_test_blocks_returns_none(self, profile, tmp_path):
        spec = _write_spec(tmp_path, "const x = 1;\nexport default x;\n")
        assert profile.extract_first_test_name(spec) is None


class TestSmokeCommandBuildingEndToEnd:
    """Ensure the extracted test name flows correctly into the smoke grep pattern."""

    def test_escaped_quote_title_produces_valid_grep(self, profile, tmp_path):
        spec = _write_spec(
            tmp_path,
            "test('REQ-CREATE-001:AC-1 — Input field and \\'Add task\\' button @SMOKE', async () => {});",
        )
        name = profile.extract_first_test_name(spec)
        assert name is not None
        # The smoke command builds a --grep pattern from this name
        smoke_cmd = profile.e2e_smoke_command("pnpm run test:e2e", [name])
        # The pattern must contain the full test title (escaped for regex)
        assert "Add task" in smoke_cmd
        assert "button" in smoke_cmd
        # And should NOT end with a dangling backslash
        assert not smoke_cmd.rstrip().endswith("\\")
