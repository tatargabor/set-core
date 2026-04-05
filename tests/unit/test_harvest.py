"""Unit tests for consumer harvest pipeline."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from set_orch.harvest import (
    HarvestCandidate,
    _classify_commit,
    _is_iss_fix,
    get_harvest_state,
    scan_project,
    set_harvest_state,
)


class TestISSFixDetection:
    def test_fix_colon_pattern(self):
        assert _is_iss_fix("fix: resolve e2e test failures") is True

    def test_fix_iss_pattern(self):
        assert _is_iss_fix("fix-iss-001: build gate failing") is True

    def test_fix_paren_pattern(self):
        assert _is_iss_fix("fix(auth): middleware matcher") is True

    def test_feat_not_iss(self):
        assert _is_iss_fix("feat: implement product catalog") is False

    def test_chore_not_iss(self):
        assert _is_iss_fix("chore: archive change") is False


class TestCommitClassification:
    def test_package_json_is_framework(self):
        cls, target = _classify_commit(["package.json", "src/app/page.tsx"])
        assert cls == "framework"
        assert "planning_rules" in target

    def test_playwright_config_is_framework(self):
        cls, target = _classify_commit(["playwright.config.ts"])
        assert cls == "framework"
        assert "playwright" in target

    def test_middleware_is_framework(self):
        cls, target = _classify_commit(["middleware.ts", "src/app/page.tsx"])
        assert cls == "framework"

    def test_claude_rules_is_template_divergence(self):
        cls, target = _classify_commit([".claude/rules/set-design-bridge.md"])
        assert cls == "template-divergence"
        assert "templates" in target

    def test_app_only_is_project_specific(self):
        cls, _ = _classify_commit([
            "src/app/products/page.tsx",
            "src/components/ProductCard.tsx",
        ])
        assert cls == "project-specific"

    def test_prisma_schema_is_project_specific(self):
        cls, _ = _classify_commit(["prisma/schema.prisma"])
        assert cls == "project-specific"

    def test_mixed_unknown(self):
        cls, _ = _classify_commit(["README.md", "docs/setup.md"])
        assert cls == "unknown"


class TestHarvestState:
    def test_get_set_state(self, tmp_path, monkeypatch):
        state_file = str(tmp_path / "harvest-state.json")
        monkeypatch.setattr("set_orch.harvest.HARVEST_STATE_FILE", state_file)

        assert get_harvest_state("test-project") is None
        set_harvest_state("test-project", "abc123")
        assert get_harvest_state("test-project") == "abc123"
        set_harvest_state("test-project", "def456")
        assert get_harvest_state("test-project") == "def456"

    def test_multiple_projects(self, tmp_path, monkeypatch):
        state_file = str(tmp_path / "harvest-state.json")
        monkeypatch.setattr("set_orch.harvest.HARVEST_STATE_FILE", state_file)

        set_harvest_state("proj-a", "aaa")
        set_harvest_state("proj-b", "bbb")
        assert get_harvest_state("proj-a") == "aaa"
        assert get_harvest_state("proj-b") == "bbb"


class TestScanProject:
    @pytest.fixture
    def consumer_project(self, tmp_path):
        """Create a fake consumer project with git history."""
        proj = tmp_path / "test-project"
        proj.mkdir()
        subprocess.run(["git", "init"], cwd=proj, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "main"], cwd=proj, capture_output=True)

        # Initial commit (simulates set-project init)
        (proj / "package.json").write_text('{"scripts":{"build":"next build"}}')
        (proj / "set" / "plugins").mkdir(parents=True)
        (proj / "set" / "plugins" / "project-type.yaml").write_text("type: web\n")
        subprocess.run(["git", "add", "-A"], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "chore: set-project init"], cwd=proj, capture_output=True)
        subprocess.run(["git", "tag", "v1-ready"], cwd=proj, capture_output=True)

        # Feature commit (should be skipped by harvest)
        (proj / "src" / "app").mkdir(parents=True)
        (proj / "src" / "app" / "page.tsx").write_text("export default function() {}")
        subprocess.run(["git", "add", "-A"], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feat: implement homepage"], cwd=proj, capture_output=True)

        # ISS fix commit (should be found)
        (proj / "package.json").write_text('{"scripts":{"build":"prisma generate && next build"}}')
        subprocess.run(["git", "add", "-A"], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "fix: add DB init to build script"], cwd=proj, capture_output=True)

        # Another fix
        (proj / "playwright.config.ts").write_text("export default {}")
        subprocess.run(["git", "add", "-A"], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "fix: stabilize e2e tests"], cwd=proj, capture_output=True)

        return str(proj)

    def test_finds_iss_fixes(self, consumer_project):
        init_sha = subprocess.run(
            ["git", "rev-list", "-1", "v1-ready"],
            cwd=consumer_project, capture_output=True, text=True,
        ).stdout.strip()

        candidates = scan_project("test", consumer_project, init_sha)
        assert len(candidates) == 2
        assert "DB init" in candidates[0].message
        assert "stabilize" in candidates[1].message

    def test_skips_feature_commits(self, consumer_project):
        init_sha = subprocess.run(
            ["git", "rev-list", "-1", "v1-ready"],
            cwd=consumer_project, capture_output=True, text=True,
        ).stdout.strip()

        candidates = scan_project("test", consumer_project, init_sha)
        messages = [c.message for c in candidates]
        assert not any("implement" in m for m in messages)

    def test_classifies_framework(self, consumer_project):
        init_sha = subprocess.run(
            ["git", "rev-list", "-1", "v1-ready"],
            cwd=consumer_project, capture_output=True, text=True,
        ).stdout.strip()

        candidates = scan_project("test", consumer_project, init_sha)
        assert candidates[0].classification == "framework"  # package.json
        assert candidates[1].classification == "framework"  # playwright.config.ts

    def test_chronological_order(self, consumer_project):
        init_sha = subprocess.run(
            ["git", "rev-list", "-1", "v1-ready"],
            cwd=consumer_project, capture_output=True, text=True,
        ).stdout.strip()

        candidates = scan_project("test", consumer_project, init_sha)
        dates = [c.date for c in candidates]
        assert dates == sorted(dates)
