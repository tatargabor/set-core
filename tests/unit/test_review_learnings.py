"""Tests for review learnings persistence and checklist generation."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ─── T17: _extract_change_review_patterns ────────────────────────────

class TestExtractChangeReviewPatterns:
    """Test _extract_change_review_patterns from merger.py."""

    def test_extracts_critical_high_for_change(self, tmp_path):
        from lib.set_orch.merger import _extract_change_review_patterns

        findings = tmp_path / "review-findings.jsonl"
        findings.write_text(
            json.dumps({
                "change": "auth",
                "issues": [
                    {"severity": "CRITICAL", "summary": "[CRITICAL] No auth on /api/users", "fix": "Add middleware"},
                    {"severity": "HIGH", "summary": "[HIGH] Missing rate limit", "fix": "Add limiter"},
                    {"severity": "MEDIUM", "summary": "[MEDIUM] Console.log left", "fix": "Remove"},
                ],
            }) + "\n"
            + json.dumps({
                "change": "catalog",
                "issues": [
                    {"severity": "CRITICAL", "summary": "[CRITICAL] XSS risk", "fix": "Sanitize"},
                ],
            }) + "\n"
        )

        patterns = _extract_change_review_patterns(str(findings), "auth")

        assert len(patterns) == 2  # CRITICAL + HIGH only, not MEDIUM
        assert patterns[0]["pattern"] == "No auth on /api/users"
        assert patterns[0]["severity"] == "CRITICAL"
        assert patterns[0]["fix_hint"] == "Add middleware"
        assert patterns[1]["pattern"] == "Missing rate limit"

    def test_returns_empty_for_missing_file(self):
        from lib.set_orch.merger import _extract_change_review_patterns

        result = _extract_change_review_patterns("/nonexistent/path.jsonl", "test")
        assert result == []

    def test_deduplicates_by_normalized_pattern(self, tmp_path):
        from lib.set_orch.merger import _extract_change_review_patterns

        findings = tmp_path / "review-findings.jsonl"
        # Same pattern across two attempts
        for attempt in [1, 2]:
            findings.write_text(
                findings.read_text() if findings.exists() else ""
            )
            with open(findings, "a") as f:
                f.write(json.dumps({
                    "change": "auth",
                    "attempt": attempt,
                    "issues": [
                        {"severity": "CRITICAL", "summary": "[CRITICAL] No auth middleware", "fix": "Add it"},
                    ],
                }) + "\n")

        patterns = _extract_change_review_patterns(str(findings), "auth")
        assert len(patterns) == 1  # Deduplicated


# ─── T14: _classify_patterns ─────────────────────────────────────────

class TestClassifyPatterns:
    """Test _classify_patterns on ProjectType base class."""

    def test_fallback_on_failure(self):
        from lib.set_orch.profile_types import ProjectType

        # Create a minimal concrete subclass
        class TestProfile(ProjectType):
            @property
            def info(self):
                from lib.set_orch.profile_types import ProjectTypeInfo
                return ProjectTypeInfo(name="test", version="0.1", description="Test")

            def get_templates(self):
                return []

        profile = TestProfile()
        patterns = [
            {"pattern": "No auth middleware", "fix_hint": "Add it"},
            {"pattern": "Budapest postal code regex", "fix_hint": "Use string match"},
        ]

        # Mock run_claude_logged to fail
        with patch("lib.set_orch.subprocess_utils.run_claude_logged") as mock_claude:
            mock_result = MagicMock()
            mock_result.exit_code = 1
            mock_claude.return_value = mock_result

            result = profile._classify_patterns(patterns)

        # All should fall back to "project"
        assert all(p["scope"] == "project" for p in result)

    def test_successful_classification(self):
        from lib.set_orch.profile_types import ProjectType, ProjectTypeInfo

        class TestProfile(ProjectType):
            @property
            def info(self):
                return ProjectTypeInfo(name="web", version="0.1", description="Test")

            def get_templates(self):
                return []

        profile = TestProfile()
        patterns = [
            {"pattern": "No auth middleware", "fix_hint": "Add it"},
            {"pattern": "Budapest postal code", "fix_hint": "Use prefix"},
        ]

        with patch("lib.set_orch.subprocess_utils.run_claude_logged") as mock_claude:
            mock_result = MagicMock()
            mock_result.exit_code = 0
            mock_result.stdout = json.dumps([
                {"pattern": "No auth middleware", "scope": "template"},
                {"pattern": "Budapest postal code", "scope": "project"},
            ])
            mock_claude.return_value = mock_result

            result = profile._classify_patterns(patterns)

        assert result[0]["scope"] == "template"
        assert result[1]["scope"] == "project"

    def test_empty_patterns(self):
        from lib.set_orch.profile_types import ProjectType, ProjectTypeInfo

        class TestProfile(ProjectType):
            @property
            def info(self):
                return ProjectTypeInfo(name="test", version="0.1", description="Test")

            def get_templates(self):
                return []

        profile = TestProfile()
        result = profile._classify_patterns([])
        assert result == []


# ─── T15: persist_review_learnings ───────────────────────────────────

class TestPersistReviewLearnings:
    """Test persist_review_learnings writes to both JSONLs correctly."""

    def _make_profile(self, config_dir):
        from lib.set_orch.profile_types import ProjectType, ProjectTypeInfo

        class TestProfile(ProjectType):
            @property
            def info(self):
                return ProjectTypeInfo(name="web", version="0.1", description="Test")

            def get_templates(self):
                return []

        profile = TestProfile()
        # Patch the template path to use temp dir
        profile._learnings_template_path = lambda ensure_dir=False: config_dir / "web.jsonl"
        return profile

    def test_writes_to_both_jsonls(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        project_dir = tmp_path / "project"
        (project_dir / "wt" / "orchestration").mkdir(parents=True)

        profile = self._make_profile(config_dir)

        patterns = [
            {"pattern": "No auth", "severity": "CRITICAL", "scope": "template",
             "fix_hint": "Add middleware", "source_changes": ["auth"]},
            {"pattern": "Budapest regex", "severity": "HIGH", "scope": "project",
             "fix_hint": "Use prefix", "source_changes": ["cart"]},
        ]

        # Skip classification (already classified)
        with patch.object(profile, "_classify_patterns", return_value=patterns):
            profile.persist_review_learnings(patterns, str(project_dir))

        # Check template JSONL
        tpl_entries = []
        with open(config_dir / "web.jsonl") as f:
            for line in f:
                tpl_entries.append(json.loads(line.strip()))
        assert len(tpl_entries) == 1
        assert tpl_entries[0]["pattern"] == "No auth"

        # Check project JSONL
        proj_path = project_dir / "wt" / "orchestration" / "review-learnings.jsonl"
        proj_entries = []
        with open(proj_path) as f:
            for line in f:
                proj_entries.append(json.loads(line.strip()))
        assert len(proj_entries) == 1
        assert proj_entries[0]["pattern"] == "Budapest regex"

    def test_deduplicates_and_increments_count(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Pre-seed with existing entry
        tpl_path = config_dir / "web.jsonl"
        tpl_path.write_text(json.dumps({
            "pattern": "No auth",
            "severity": "CRITICAL",
            "scope": "template",
            "count": 2,
            "last_seen": "2026-01-01T00:00:00Z",
            "source_changes": ["old-change"],
            "fix_hint": "Add middleware",
        }) + "\n")

        profile = self._make_profile(config_dir)

        patterns = [
            {"pattern": "No auth", "severity": "CRITICAL", "scope": "template",
             "fix_hint": "Add middleware", "source_changes": ["new-change"]},
        ]

        with patch.object(profile, "_classify_patterns", return_value=patterns):
            profile.persist_review_learnings(patterns, str(tmp_path))

        entries = []
        with open(tpl_path) as f:
            for line in f:
                entries.append(json.loads(line.strip()))
        assert len(entries) == 1
        assert entries[0]["count"] == 3  # was 2, now 3
        assert "new-change" in entries[0]["source_changes"]

    def test_caps_at_50(self, tmp_path):
        from lib.set_orch.profile_types import ProjectType

        entries = []
        for i in range(55):
            entries.append({
                "pattern": f"Pattern {i}",
                "severity": "HIGH",
                "scope": "template",
                "count": 1,
                "last_seen": f"2026-01-{i % 28 + 1:02d}T00:00:00Z",
                "source_changes": [],
                "fix_hint": "",
            })
        new = [{"pattern": "New one", "severity": "CRITICAL", "scope": "template",
                "source_changes": [], "fix_hint": ""}]

        result = ProjectType._merge_learnings(entries, new, "2026-03-22T00:00:00Z", cap=50)
        assert len(result) <= 50


# ─── T16: review_learnings_checklist ─────────────────────────────────

class TestReviewLearningsChecklist:
    """Test review_learnings_checklist output format and merging."""

    def test_formats_with_tags(self, tmp_path):
        from lib.set_orch.profile_types import ProjectType, ProjectTypeInfo

        class TestProfile(ProjectType):
            @property
            def info(self):
                return ProjectTypeInfo(name="web", version="0.1", description="Test")

            def get_templates(self):
                return []

            def _review_baseline_items(self):
                return ["bcrypt for passwords, NEVER sha256"]

        profile = TestProfile()
        profile._learnings_template_path = lambda ensure_dir=False: tmp_path / "web.jsonl"

        # Write template JSONL
        (tmp_path / "web.jsonl").write_text(json.dumps({
            "pattern": "No auth middleware",
            "count": 3,
            "scope": "template",
        }) + "\n")

        # Write project JSONL
        proj_dir = tmp_path / "project" / "wt" / "orchestration"
        proj_dir.mkdir(parents=True)
        (proj_dir / "review-learnings.jsonl").write_text(json.dumps({
            "pattern": "Budapest postal code regex",
            "count": 2,
            "scope": "project",
        }) + "\n")

        result = profile.review_learnings_checklist(str(tmp_path / "project"))

        assert "## Review Learnings Checklist" in result
        assert "[project, seen 2x]" in result
        assert "[template, seen 3x]" in result
        assert "[baseline]" in result
        assert "Budapest" in result
        assert "No auth" in result
        assert "bcrypt" in result

    def test_caps_at_15_lines(self, tmp_path):
        from lib.set_orch.profile_types import ProjectType, ProjectTypeInfo

        class TestProfile(ProjectType):
            @property
            def info(self):
                return ProjectTypeInfo(name="web", version="0.1", description="Test")

            def get_templates(self):
                return []

            def _review_baseline_items(self):
                return [f"Baseline item {i}" for i in range(20)]

        profile = TestProfile()
        profile._learnings_template_path = lambda ensure_dir=False: tmp_path / "web.jsonl"

        result = profile.review_learnings_checklist(str(tmp_path / "nonexistent"))

        lines = [l for l in result.split("\n") if l.startswith("- ")]
        assert len(lines) <= 15

    def test_returns_empty_when_nothing(self, tmp_path):
        from lib.set_orch.profile_types import ProjectType, ProjectTypeInfo

        class TestProfile(ProjectType):
            @property
            def info(self):
                return ProjectTypeInfo(name="core", version="0.1", description="Test")

            def get_templates(self):
                return []

        profile = TestProfile()
        profile._learnings_template_path = lambda ensure_dir=False: tmp_path / "core.jsonl"

        result = profile.review_learnings_checklist(str(tmp_path))
        assert result == ""


# ─── T18: Integration round-trip ─────────────────────────────────────

class TestRoundTrip:
    """Test persist → checklist round-trip."""

    def test_persisted_items_appear_in_checklist(self, tmp_path):
        from lib.set_orch.profile_types import ProjectType, ProjectTypeInfo

        class TestProfile(ProjectType):
            @property
            def info(self):
                return ProjectTypeInfo(name="web", version="0.1", description="Test")

            def get_templates(self):
                return []

        profile = TestProfile()
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        profile._learnings_template_path = lambda ensure_dir=False: config_dir / "web.jsonl"

        project_dir = tmp_path / "project"
        (project_dir / "wt" / "orchestration").mkdir(parents=True)

        patterns = [
            {"pattern": "XSS via innerHTML", "severity": "CRITICAL", "scope": "template",
             "fix_hint": "Use textContent", "source_changes": ["dashboard"]},
            {"pattern": "Admin seed password exposed", "severity": "HIGH", "scope": "project",
             "fix_hint": "Use env var", "source_changes": ["seed"]},
        ]

        with patch.object(profile, "_classify_patterns", return_value=patterns):
            profile.persist_review_learnings(patterns, str(project_dir))

        checklist = profile.review_learnings_checklist(str(project_dir))

        assert "XSS via innerHTML" in checklist
        assert "[template, seen 1x]" in checklist
        assert "Admin seed password exposed" in checklist
        assert "[project, seen 1x]" in checklist
