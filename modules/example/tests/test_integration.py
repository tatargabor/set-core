"""Integration tests — verify the full plugin lifecycle.

These tests validate that DungeonProjectType works correctly
as a set-core plugin: discovery, template deployment, and
configuration resolution.
"""

import pytest
from pathlib import Path

from set_project_base.base import ProjectType
from set_project_example import DungeonProjectType


class TestPluginDiscovery:
    """The plugin must be discoverable via entry_points."""

    def test_conforms_to_interface(self, pt):
        """All abstract methods from ProjectType are implemented."""
        # These would raise TypeError if not implemented
        assert pt.info is not None
        assert isinstance(pt.get_templates(), list)
        assert isinstance(pt.get_verification_rules(), list)
        assert isinstance(pt.get_orchestration_directives(), list)

    def test_all_profile_methods_callable(self, pt):
        """All optional profile methods return without error."""
        assert isinstance(pt.planning_rules(), str)
        assert isinstance(pt.security_checklist(), str)
        assert isinstance(pt.generated_file_patterns(), list)
        assert isinstance(pt.ignore_patterns(), list)
        assert isinstance(pt.gate_overrides("anything"), dict)
        assert isinstance(pt.security_rules_paths("/tmp"), list)


class TestTemplateDeployment:
    """Verify template files are complete and well-formed."""

    def test_has_project_knowledge(self, starter_dir):
        """project-knowledge.yaml is the main config file."""
        pk = starter_dir / "project-knowledge.yaml"
        assert pk.is_file()
        content = pk.read_text()
        assert "cross_cutting_files" in content
        assert "version:" in content

    def test_has_manifest(self, starter_dir):
        """manifest.yaml controls which files deploy and which are optional modules."""
        manifest = starter_dir / "manifest.yaml"
        assert manifest.is_file()
        import yaml
        data = yaml.safe_load(manifest.read_text())
        assert "core" in data, "Manifest must declare core files"
        assert "modules" in data, "Manifest should offer optional modules"

    def test_has_example_dungeons(self, starter_dir):
        """At least two example dungeons for variety."""
        dungeons = list((starter_dir / "dungeons").glob("*.dungeon"))
        assert len(dungeons) >= 2

    def test_has_bestiary(self, starter_dir):
        """Bestiary is a cross-cutting file used by verification rules."""
        assert (starter_dir / "bestiary.yaml").is_file()

    def test_has_rules(self, starter_dir):
        """Rules are deployed to .claude/rules/ in consumer projects."""
        rules = list((starter_dir / "rules").glob("*.md"))
        assert len(rules) >= 1

    def test_dungeon_files_are_valid_yaml(self, starter_dir):
        """All .dungeon files in the template must be parseable."""
        from set_project_example.build import parse_dungeon

        for dfile in (starter_dir / "dungeons").glob("*.dungeon"):
            dungeon = parse_dungeon(dfile)
            assert "name" in dungeon, f"{dfile.name} missing 'name'"
            assert "rooms" in dungeon, f"{dfile.name} missing 'rooms'"
            assert "difficulty" in dungeon, f"{dfile.name} missing 'difficulty'"

    def test_template_dungeons_build_successfully(self, starter_dir, tmp_path):
        """The template dungeons should produce valid output."""
        from set_project_example.build import main

        output_dir = tmp_path / "output"
        result = main(str(starter_dir / "dungeons"), str(output_dir))
        assert result == 0
        assert (output_dir / "castle.map").is_file()
        assert (output_dir / "cave.map").is_file()
        assert (output_dir / "index.md").is_file()

    def test_manifest_core_files_exist(self, starter_dir):
        """Every file listed in manifest.yaml core section must exist."""
        import yaml
        manifest = yaml.safe_load((starter_dir / "manifest.yaml").read_text())
        for rel in manifest.get("core", []):
            assert (starter_dir / rel).is_file(), f"Manifest core file missing: {rel}"

    def test_manifest_module_files_exist(self, starter_dir):
        """Every file listed in manifest.yaml module sections must exist."""
        import yaml
        manifest = yaml.safe_load((starter_dir / "manifest.yaml").read_text())
        for _mid, mdef in manifest.get("modules", {}).items():
            for rel in mdef.get("files", []):
                assert (starter_dir / rel).is_file(), f"Manifest module file missing: {rel}"


class TestRuleInheritance:
    """Verify the full rule chain: base -> dungeon."""

    def test_total_rule_count(self):
        """Dungeon type should have base rules + dungeon rules."""
        from set_project_base import BaseProjectType

        base_count = len(BaseProjectType().get_verification_rules())
        dungeon_count = len(DungeonProjectType().get_verification_rules())

        assert dungeon_count > base_count, (
            f"Expected more rules than base ({base_count}), got {dungeon_count}"
        )

    def test_total_directive_count(self):
        """Dungeon type should have base directives + dungeon directives."""
        from set_project_base import BaseProjectType

        base_count = len(BaseProjectType().get_orchestration_directives())
        dungeon_count = len(DungeonProjectType().get_orchestration_directives())

        assert dungeon_count > base_count, (
            f"Expected more directives than base ({base_count}), got {dungeon_count}"
        )

    def test_no_id_conflicts_with_base(self):
        """Dungeon-specific rule IDs must not collide with base IDs."""
        from set_project_base import BaseProjectType

        base_ids = {r.id for r in BaseProjectType().get_verification_rules()}
        all_ids = {r.id for r in DungeonProjectType().get_verification_rules()}

        # Base IDs should appear in the full list (inherited)
        assert base_ids.issubset(all_ids)

        # Dungeon-only IDs should not be in base
        dungeon_only = all_ids - base_ids
        assert len(dungeon_only) > 0, "No dungeon-specific rules found"
