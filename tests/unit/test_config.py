"""Tests for wt_orch.config."""

import json
import textwrap
from pathlib import Path

import pytest

from wt_orch.config import (
    DIRECTIVE_DEFAULTS,
    auto_detect_smoke_command,
    auto_detect_test_command,
    brief_hash,
    find_input,
    find_openspec_dir,
    format_duration,
    load_config_file,
    parse_directives,
    parse_duration,
    parse_next_items,
    resolve_directives,
)


# ─── parse_duration ──────────────────────────────────────────────────


class TestParseDuration:
    def test_plain_number_as_minutes(self):
        assert parse_duration("30") == 1800

    def test_hours_and_minutes(self):
        assert parse_duration("1h30m") == 5400

    def test_hours_only(self):
        assert parse_duration("2h") == 7200

    def test_minutes_only(self):
        assert parse_duration("45m") == 2700

    def test_zero(self):
        assert parse_duration("0") == 0

    def test_invalid_returns_zero(self):
        assert parse_duration("abc") == 0

    def test_whitespace_stripped(self):
        assert parse_duration("  30  ") == 1800


# ─── format_duration ─────────────────────────────────────────────────


class TestFormatDuration:
    def test_hours_and_minutes(self):
        assert format_duration(5400) == "1h30m"

    def test_hours_only(self):
        assert format_duration(7200) == "2h"

    def test_minutes_only(self):
        assert format_duration(300) == "5m"

    def test_zero(self):
        assert format_duration(0) == "0m"

    def test_large_value(self):
        assert format_duration(18000) == "5h"


# ─── brief_hash ──────────────────────────────────────────────────────


class TestBriefHash:
    def test_hash_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h = brief_hash(f)
        assert len(h) == 64  # SHA-256 hex digest
        assert h == brief_hash(f)  # deterministic

    def test_different_content(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        assert brief_hash(f1) != brief_hash(f2)

    def test_nonexistent_returns_unknown(self):
        assert brief_hash("/nonexistent/path") == "unknown"


# ─── parse_next_items ────────────────────────────────────────────────


class TestParseNextItems:
    def test_with_next_section(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text(textwrap.dedent("""\
            # Project
            ## Overview
            ### Next
            - item1
            - item2
            ### Done
            - old item
        """))
        assert parse_next_items(f) == ["item1", "item2"]

    def test_no_next_section(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text("# Project\n## Overview\nSome text\n")
        assert parse_next_items(f) == []

    def test_next_terminated_by_h2(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text(textwrap.dedent("""\
            ### Next
            - item1
            ## Other Section
            - not included
        """))
        assert parse_next_items(f) == ["item1"]

    def test_empty_items_skipped(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text("### Next\n- item1\n-  \n- item2\n")
        assert parse_next_items(f) == ["item1", "item2"]

    def test_nonexistent_file(self):
        assert parse_next_items("/nonexistent") == []


# ─── parse_directives ────────────────────────────────────────────────


class TestParseDirectives:
    def test_valid_directives(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text(textwrap.dedent("""\
            # Project
            ## Orchestrator Directives
            - max_parallel: 5
            - merge_policy: eager
            - test_timeout: 600
            ## Next
        """))
        d = parse_directives(f)
        assert d["max_parallel"] == 5
        assert d["merge_policy"] == "eager"
        assert d["test_timeout"] == 600

    def test_defaults_when_no_directives(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text("# Project\n## Overview\n")
        d = parse_directives(f)
        assert d["max_parallel"] == DIRECTIVE_DEFAULTS["max_parallel"]
        assert d["merge_policy"] == DIRECTIVE_DEFAULTS["merge_policy"]

    def test_invalid_value_uses_default(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text(textwrap.dedent("""\
            ## Orchestrator Directives
            - max_parallel: abc
        """))
        d = parse_directives(f)
        assert d["max_parallel"] == DIRECTIVE_DEFAULTS["max_parallel"]

    def test_invalid_enum_uses_default(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text(textwrap.dedent("""\
            ## Orchestrator Directives
            - merge_policy: invalid_policy
        """))
        d = parse_directives(f)
        assert d["merge_policy"] == DIRECTIVE_DEFAULTS["merge_policy"]

    def test_boolean_directives(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text(textwrap.dedent("""\
            ## Orchestrator Directives
            - auto_replan: true
            - pause_on_exit: false
        """))
        d = parse_directives(f)
        assert d["auto_replan"] is True
        assert d["pause_on_exit"] is False

    def test_none_input(self):
        d = parse_directives(None)
        assert d["max_parallel"] == DIRECTIVE_DEFAULTS["max_parallel"]

    def test_milestones_nested(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text(textwrap.dedent("""\
            ## Orchestrator Directives
            - milestones_enabled: true
            - milestones_base_port: 4000
        """))
        d = parse_directives(f)
        assert d["milestones"]["enabled"] is True
        assert d["milestones"]["base_port"] == 4000

    def test_hooks_omitted_when_empty(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text("## Orchestrator Directives\n")
        d = parse_directives(f)
        assert "hook_pre_dispatch" not in d
        assert "hook_on_fail" not in d

    def test_hooks_present_when_set(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text(textwrap.dedent("""\
            ## Orchestrator Directives
            - hook_pre_dispatch: ./scripts/pre-dispatch.sh
        """))
        d = parse_directives(f)
        assert d["hook_pre_dispatch"] == "./scripts/pre-dispatch.sh"

    def test_without_bullet_prefix(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text(textwrap.dedent("""\
            ## Orchestrator Directives
            max_parallel: 4
            merge_policy: manual
        """))
        d = parse_directives(f)
        assert d["max_parallel"] == 4
        assert d["merge_policy"] == "manual"

    def test_smoke_dev_server_omitted_when_empty(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text("## Orchestrator Directives\n")
        d = parse_directives(f)
        assert "smoke_dev_server_command" not in d

    def test_watchdog_omitted_when_none(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text("## Orchestrator Directives\n")
        d = parse_directives(f)
        assert "watchdog_timeout" not in d
        assert "watchdog_loop_threshold" not in d


# ─── load_config_file ────────────────────────────────────────────────


class TestLoadConfigFile:
    def test_yaml_file(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("max_parallel: 5\nmerge_policy: manual\n")
        d = load_config_file(f)
        assert d["max_parallel"] == 5
        assert d["merge_policy"] == "manual"

    def test_no_file(self):
        assert load_config_file(None) == {}
        assert load_config_file("") == {}

    def test_nonexistent_file(self):
        assert load_config_file("/nonexistent/config.yaml") == {}

    def test_boolean_values(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("auto_replan: true\npause_on_exit: false\n")
        d = load_config_file(f)
        assert d["auto_replan"] is True
        assert d["pause_on_exit"] is False


# ─── resolve_directives ──────────────────────────────────────────────


class TestResolveDirectives:
    def test_cli_overrides_config(self, tmp_path):
        doc = tmp_path / "brief.md"
        doc.write_text(textwrap.dedent("""\
            ## Orchestrator Directives
            - max_parallel: 2
        """))
        config = tmp_path / "config.yaml"
        config.write_text("max_parallel: 3\n")
        d = resolve_directives(doc, config_path=config, cli_overrides={"max_parallel": 5})
        assert d["max_parallel"] == 5

    def test_config_overrides_doc(self, tmp_path):
        doc = tmp_path / "brief.md"
        doc.write_text(textwrap.dedent("""\
            ## Orchestrator Directives
            - max_parallel: 2
        """))
        config = tmp_path / "config.yaml"
        config.write_text("max_parallel: 4\n")
        d = resolve_directives(doc, config_path=config)
        assert d["max_parallel"] == 4

    def test_directory_input_skips_doc(self, tmp_path):
        d = resolve_directives(tmp_path)
        assert d["max_parallel"] == DIRECTIVE_DEFAULTS["max_parallel"]


# ─── find_input ──────────────────────────────────────────────────────


class TestFindInput:
    def test_spec_directory(self, tmp_path):
        spec_dir = tmp_path / "specs"
        spec_dir.mkdir()
        mode, path = find_input(spec_override=str(spec_dir))
        assert mode == "digest"
        assert path == str(spec_dir.resolve())

    def test_spec_file(self, tmp_path):
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec")
        mode, path = find_input(spec_override=str(spec_file))
        assert mode == "digest"
        assert path == str(spec_file.resolve())

    def test_spec_not_found(self):
        with pytest.raises(FileNotFoundError):
            find_input(spec_override="/nonexistent/spec.md")

    def test_brief_with_next(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        openspec = tmp_path / "openspec"
        openspec.mkdir()
        brief = openspec / "project-brief.md"
        brief.write_text("### Next\n- task1\n- task2\n")
        mode, path = find_input()
        assert mode == "brief"

    def test_no_input_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError):
            find_input()


# ─── find_openspec_dir ───────────────────────────────────────────────


class TestFindOpenspecDir:
    def test_openspec_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "openspec").mkdir()
        assert find_openspec_dir() == "openspec"

    def test_default_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert find_openspec_dir() == "openspec"


# ─── auto_detect_test_command ────────────────────────────────────────


class TestAutoDetectTestCommand:
    def test_npm_test(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"test": "jest"}}))
        assert auto_detect_test_command(str(tmp_path)) == "npm run test"

    def test_pnpm_from_lockfile(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"test": "vitest"}}))
        (tmp_path / "pnpm-lock.yaml").write_text("")
        assert auto_detect_test_command(str(tmp_path)) == "pnpm run test"

    def test_yarn_from_lockfile(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"test:unit": "jest --unit"}}))
        (tmp_path / "yarn.lock").write_text("")
        assert auto_detect_test_command(str(tmp_path)) == "yarn run test:unit"

    def test_bun_from_lockfile(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"test": "bun test"}}))
        (tmp_path / "bun.lockb").write_text("")
        assert auto_detect_test_command(str(tmp_path)) == "bun run test"

    def test_priority_order(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"test:unit": "jest", "test:ci": "vitest"}}))
        # test:unit comes before test:ci
        assert auto_detect_test_command(str(tmp_path)) == "npm run test:unit"

    def test_no_package_json(self, tmp_path):
        assert auto_detect_test_command(str(tmp_path)) == ""

    def test_no_test_script(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"build": "tsc"}}))
        assert auto_detect_test_command(str(tmp_path)) == ""


# ─── auto_detect_smoke_command ───────────────────────────────────


class TestAutoDetectSmokeCommand:
    def test_build_script_present(self, tmp_path):
        """build + test combined when build script exists."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"build": "tsc", "test": "jest"}}))
        result = auto_detect_smoke_command(str(tmp_path))
        assert "build" in result
        assert "&&" in result
        assert "test" in result

    def test_build_ci_preferred(self, tmp_path):
        """build:ci takes precedence over build."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"build": "tsc", "build:ci": "tsc --noEmit", "test": "jest"}}))
        result = auto_detect_smoke_command(str(tmp_path))
        assert "build:ci" in result

    def test_no_build_script(self, tmp_path):
        """No build script → falls back to test_command alone."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"test": "jest"}}))
        result = auto_detect_smoke_command(str(tmp_path))
        assert "build" not in result
        assert "test" in result

    def test_no_test_script(self, tmp_path):
        """No test script → empty string."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"build": "tsc"}}))
        assert auto_detect_smoke_command(str(tmp_path)) == ""

    def test_pnpm_lockfile(self, tmp_path):
        """Detects pnpm from lockfile."""
        (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n")
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"build": "tsc", "test": "vitest"}}))
        result = auto_detect_smoke_command(str(tmp_path))
        assert result.startswith("pnpm")
        assert "pnpm run build && pnpm run test" == result
