"""Tests for the DungeonProjectType — demonstrates every extension point.

These tests serve as both validation AND documentation. Each test shows
how a specific ProjectType method works and what it returns. Copy and
adapt these when building your own project type.
"""

from pathlib import Path

import pytest

from set_project_base import BaseProjectType
from set_project_base.base import (
    OrchestrationDirective,
    ProjectType,
    TemplateInfo,
    VerificationRule,
)
from set_project_example import DungeonProjectType


# ── 1. Inheritance ────────────────────────────────────────

class TestInheritance:
    """Project types form an inheritance chain.

    DungeonProjectType -> BaseProjectType -> ProjectType (ABC)

    This means dungeon projects automatically get base rules
    (file-size-limit, no-secrets, todo-tracking) plus their own.
    """

    def test_is_instance_of_abstract_base(self, pt):
        assert isinstance(pt, ProjectType)

    def test_extends_base_project_type(self, pt):
        assert isinstance(pt, BaseProjectType)

    def test_is_concrete(self, pt):
        """Can be instantiated — all abstract methods are implemented."""
        assert pt is not None


# ── 2. Metadata (info) ───────────────────────────────────

class TestInfo:
    """The info property returns ProjectTypeInfo with metadata.

    - name: used for entry_points registration and CLI
    - version: for compatibility tracking
    - parent: declares inheritance (enables rule merging)
    """

    def test_has_name(self, pt):
        assert pt.info.name == "dungeon"

    def test_has_version(self, pt):
        assert pt.info.version
        parts = pt.info.version.split(".")
        assert len(parts) == 3, "Version should be semver (x.y.z)"

    def test_declares_parent(self, pt):
        """parent='base' means base rules are inherited."""
        assert pt.info.parent == "base"

    def test_has_description(self, pt):
        assert pt.info.description
        assert len(pt.info.description) > 10


# ── 3. Templates ──────────────────────────────────────────

class TestTemplates:
    """Templates provide starter files for new projects.

    When a user runs `set-project init --project-type dungeon --template starter`,
    the files from template_dir are deployed to their project.
    """

    def test_has_at_least_one_template(self, pt):
        templates = pt.get_templates()
        assert len(templates) >= 1

    def test_template_is_template_info(self, pt):
        for tmpl in pt.get_templates():
            assert isinstance(tmpl, TemplateInfo)

    def test_template_has_required_fields(self, pt):
        for tmpl in pt.get_templates():
            assert tmpl.id, "Template needs an id"
            assert tmpl.description, "Template needs a description"
            assert tmpl.template_dir, "Template needs a template_dir"

    def test_starter_template_exists(self, pt):
        """The starter template is the primary one for this example."""
        ids = [t.id for t in pt.get_templates()]
        assert "starter" in ids

    def test_template_dir_exists(self, pt):
        """The template directory must actually exist on disk."""
        for tmpl in pt.get_templates():
            template_dir = pt.get_template_dir(tmpl.id)
            assert template_dir is not None, f"get_template_dir('{tmpl.id}') returned None"
            assert template_dir.is_dir(), f"Template dir does not exist: {template_dir}"

    def test_starter_has_dungeon_files(self, pt, starter_dir):
        """The starter template includes example .dungeon files."""
        dungeon_files = list(starter_dir.glob("dungeons/*.dungeon"))
        assert len(dungeon_files) >= 1, "Starter should include at least one .dungeon file"

    def test_starter_has_rules(self, pt, starter_dir):
        """The starter template includes .claude/rules/ markdown files."""
        rule_files = list(starter_dir.glob("rules/*.md"))
        assert len(rule_files) >= 1, "Starter should include at least one rule file"

    def test_starter_has_manifest(self, pt, starter_dir):
        """The manifest.yaml controls which files are deployed and which are optional."""
        assert (starter_dir / "manifest.yaml").is_file()


# ── 4. Verification Rules ────────────────────────────────

class TestVerificationRules:
    """Verification rules run during opsx:verify to catch problems.

    Each rule has:
    - id: unique identifier
    - description: human-readable explanation
    - check: the type of check (cross-file-key-parity, pattern-audit, etc.)
    - severity: error, warning, or info
    - config: check-specific configuration
    """

    def test_returns_list_of_rules(self, pt):
        rules = pt.get_verification_rules()
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_rules_are_verification_rule_instances(self, pt):
        for rule in pt.get_verification_rules():
            assert isinstance(rule, VerificationRule)

    def test_rules_have_required_fields(self, pt):
        for rule in pt.get_verification_rules():
            assert rule.id, f"Rule missing id: {rule}"
            assert rule.description, f"Rule {rule.id} missing description"
            assert rule.check, f"Rule {rule.id} missing check type"
            assert rule.severity in ("error", "warning", "info"), (
                f"Rule {rule.id} has invalid severity: {rule.severity}"
            )

    def test_rule_ids_are_unique(self, pt):
        ids = [r.id for r in pt.get_verification_rules()]
        assert len(ids) == len(set(ids)), f"Duplicate rule IDs: {ids}"

    def test_inherits_base_rules(self, pt):
        """Should include base rules like file-size-limit and no-secrets."""
        ids = [r.id for r in pt.get_verification_rules()]
        assert "file-size-limit" in ids, "Missing inherited base rule"
        assert "no-secrets-in-source" in ids, "Missing inherited base rule"

    def test_has_dungeon_specific_rules(self, pt):
        """Should include dungeon-specific rules beyond base."""
        ids = [r.id for r in pt.get_verification_rules()]
        assert "exit-target-exists" in ids
        assert "no-orphan-rooms" in ids
        assert "unique-room-ids" in ids

    def test_exit_target_rule_is_error(self, pt):
        """Broken exits are errors — the dungeon is unplayable."""
        rules = {r.id: r for r in pt.get_verification_rules()}
        assert rules["exit-target-exists"].severity == "error"

    def test_orphan_room_rule_is_warning(self, pt):
        """Orphan rooms are warnings — they're dead content, not broken."""
        rules = {r.id: r for r in pt.get_verification_rules()}
        assert rules["no-orphan-rooms"].severity == "warning"


# ── 5. Orchestration Directives ───────────────────────────

class TestOrchestrationDirectives:
    """Orchestration directives tell the sentinel how to coordinate work.

    Each directive has:
    - id: unique identifier
    - trigger: when this directive applies
    - action: what to do (serialize, post-merge, warn, flag-for-review)
    - config: action-specific configuration
    """

    def test_returns_list_of_directives(self, pt):
        directives = pt.get_orchestration_directives()
        assert isinstance(directives, list)
        assert len(directives) > 0

    def test_directives_are_correct_type(self, pt):
        for d in pt.get_orchestration_directives():
            assert isinstance(d, OrchestrationDirective)

    def test_directives_have_required_fields(self, pt):
        for d in pt.get_orchestration_directives():
            assert d.id, f"Directive missing id: {d}"
            assert d.trigger, f"Directive {d.id} missing trigger"
            assert d.action, f"Directive {d.id} missing action"

    def test_directive_ids_are_unique(self, pt):
        ids = [d.id for d in pt.get_orchestration_directives()]
        assert len(ids) == len(set(ids)), f"Duplicate directive IDs: {ids}"

    def test_inherits_base_directives(self, pt):
        ids = [d.id for d in pt.get_orchestration_directives()]
        assert "install-deps-python" in ids, "Missing inherited base directive"

    def test_has_dungeon_specific_directives(self, pt):
        ids = [d.id for d in pt.get_orchestration_directives()]
        assert "no-parallel-dungeon-edit" in ids
        assert "rebuild-maps" in ids

    def test_serialize_prevents_parallel_dungeon_edits(self, pt):
        """Two agents editing the same .dungeon file -> merge conflict.
        The serialize action ensures they run sequentially."""
        directives = {d.id: d for d in pt.get_orchestration_directives()}
        d = directives["no-parallel-dungeon-edit"]
        assert d.action == "serialize"
        assert "dungeon" in d.trigger.lower()

    def test_rebuild_maps_is_post_merge(self, pt):
        """After a .dungeon change merges, regenerate the maps."""
        directives = {d.id: d for d in pt.get_orchestration_directives()}
        d = directives["rebuild-maps"]
        assert d.action == "post-merge"
        assert "command" in d.config


# ── 6. Profile Methods ────────────────────────────────────

class TestProfileMethods:
    """Profile methods let the engine auto-detect project characteristics.

    These are optional — the base class provides sensible defaults.
    Override only what's relevant for your domain.
    """

    def test_planning_rules_returns_string(self, pt):
        rules = pt.planning_rules()
        assert isinstance(rules, str)
        assert len(rules) > 0

    def test_planning_rules_mentions_dungeon_concepts(self, pt):
        rules = pt.planning_rules()
        assert "dungeon" in rules.lower() or "room" in rules.lower()

    def test_security_rules_paths_returns_list(self, pt, tmp_path):
        """security_rules_paths() returns rule files for verify retry context."""
        paths = pt.security_rules_paths(str(tmp_path))
        assert isinstance(paths, list)
        # Falls back to bundled template rules when no project rules exist
        assert len(paths) >= 1
        assert paths[0].name == "dungeon-integrity.md"

    def test_security_rules_paths_prefers_project_rules(self, pt, tmp_path):
        """When project has .claude/rules/dungeon-*.md, those take priority."""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "dungeon-custom.md").write_text("# Custom rule")
        paths = pt.security_rules_paths(str(tmp_path))
        assert any("dungeon-custom.md" in str(p) for p in paths)

    def test_security_checklist_returns_string(self, pt):
        checklist = pt.security_checklist()
        assert isinstance(checklist, str)
        assert "- [ ]" in checklist, "Should be a markdown checklist"

    def test_generated_file_patterns(self, pt):
        """Generated files are auto-resolved during merge conflicts."""
        patterns = pt.generated_file_patterns()
        assert isinstance(patterns, list)
        assert "output/*.map" in patterns
        assert "output/*.stats" in patterns

    def test_ignore_patterns(self, pt):
        """These paths are excluded from digest/codemap generation."""
        patterns = pt.ignore_patterns()
        assert "output/" in patterns
        assert "__pycache__" in patterns

    def test_gate_overrides_for_lore(self, pt):
        """Lore changes (flavor text) don't need tests."""
        overrides = pt.gate_overrides("lore")
        assert overrides.get("test_files_required") is False

    def test_gate_overrides_for_unknown_type(self, pt):
        """Unknown change types get no overrides (empty dict)."""
        overrides = pt.gate_overrides("something-random")
        assert overrides == {}


# ── 7. Detection Methods ─────────────────────────────────

class TestDetection:
    """Detection methods auto-discover project tools and commands.

    The engine calls these to figure out how to test, build, and
    serve the project without manual configuration.
    """

    def test_detect_test_command_with_pyproject_pytest(self, pt, tmp_path):
        """Detects pytest when pyproject.toml has [tool.pytest]."""
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
        cmd = pt.detect_test_command(str(tmp_path))
        assert cmd == "pytest"

    def test_detect_test_command_with_pytest_ini(self, pt, tmp_path):
        """Detects pytest when pytest.ini exists."""
        (tmp_path / "pytest.ini").write_text("[pytest]\n")
        cmd = pt.detect_test_command(str(tmp_path))
        assert cmd == "pytest"

    def test_detect_test_command_with_setup_cfg(self, pt, tmp_path):
        """Detects pytest when setup.cfg exists."""
        (tmp_path / "setup.cfg").write_text("[tool:pytest]\n")
        cmd = pt.detect_test_command(str(tmp_path))
        assert cmd == "pytest"

    def test_detect_test_command_with_tests_dir(self, pt, tmp_path):
        """Detects pytest when tests/ directory has test files."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_hello.py").write_text("def test(): pass")
        cmd = pt.detect_test_command(str(tmp_path))
        assert cmd == "pytest"

    def test_detect_test_command_returns_none_if_no_tests(self, pt, tmp_path):
        """Returns None when no test infrastructure is found."""
        cmd = pt.detect_test_command(str(tmp_path))
        assert cmd is None

    def test_detect_build_command_with_dungeons(self, pt, tmp_path):
        """Detects build command when .dungeon files exist."""
        (tmp_path / "dungeons").mkdir()
        (tmp_path / "dungeons" / "test.dungeon").write_text("name: Test")
        cmd = pt.detect_build_command(str(tmp_path))
        assert cmd is not None
        assert "build" in cmd

    def test_detect_build_command_returns_none_if_no_dungeons(self, pt, tmp_path):
        """Returns None when no .dungeon files exist."""
        cmd = pt.detect_build_command(str(tmp_path))
        assert cmd is None


# ── 8. Entry Point Discovery ─────────────────────────────

class TestEntryPoint:
    """The plugin must be discoverable via Python entry_points.

    This is how set-core finds project types at runtime. The
    pyproject.toml registers: dungeon = "set_project_example:DungeonProjectType"
    """

    def test_entry_point_is_discoverable(self):
        """Verify the 'dungeon' entry point resolves to DungeonProjectType."""
        from importlib.metadata import entry_points

        eps = entry_points(group="set_tools.project_types")
        names = [ep.name for ep in eps]
        assert "dungeon" in names, (
            "Entry point 'dungeon' not found in set_tools.project_types. "
            "Is set-project-example installed? Run: pip install -e ."
        )

    def test_entry_point_loads_correct_class(self):
        """The entry point loads to DungeonProjectType."""
        from importlib.metadata import entry_points

        eps = entry_points(group="set_tools.project_types")
        ep = next(ep for ep in eps if ep.name == "dungeon")
        cls = ep.load()
        assert cls is DungeonProjectType
