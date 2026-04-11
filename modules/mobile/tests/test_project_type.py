"""Tests for MobileProjectType."""

import pytest
from pathlib import Path
from set_project_mobile import MobileProjectType
from set_project_web import WebProjectType
from set_orch.profile_types import TemplateInfo, VerificationRule, OrchestrationDirective


class TestMetadata:
    def test_info_name(self, pt):
        assert pt.info.name == "mobile"

    def test_info_version(self, pt):
        assert pt.info.version == "0.1.0"

    def test_info_parent(self, pt):
        assert pt.info.parent == "web"

    def test_inherits_from_web(self, pt):
        assert isinstance(pt, WebProjectType)


class TestTemplates:
    def test_has_capacitor_nextjs_template(self, pt):
        templates = pt.get_templates()
        ids = [t.id for t in templates]
        assert "capacitor-nextjs" in ids

    def test_templates_are_template_info(self, pt):
        for tmpl in pt.get_templates():
            assert isinstance(tmpl, TemplateInfo)

    def test_capacitor_template_dir_exists(self, pt):
        tdir = pt.get_template_dir("capacitor-nextjs")
        assert tdir is not None
        assert tdir.is_dir()

    def test_web_template_accessible_via_mro(self, pt):
        """Inherited 'nextjs' template from WebProjectType resolves correctly."""
        tdir = pt.get_template_dir("nextjs")
        assert tdir is not None
        assert tdir.is_dir()
        # Should resolve to web module's directory, not mobile's
        assert "modules/web" in str(tdir) or "set_project_web" in str(tdir)


class TestVerificationRules:
    def test_inherits_core_rules(self, pt):
        rules = pt.get_verification_rules()
        rule_ids = [r.id for r in rules]
        # Core rules
        assert "file-size-limit" in rule_ids
        assert "no-secrets-in-source" in rule_ids
        assert "todo-tracking" in rule_ids

    def test_inherits_web_rules(self, pt):
        rules = pt.get_verification_rules()
        rule_ids = [r.id for r in rules]
        assert "i18n-completeness" in rule_ids

    def test_has_mobile_rules(self, pt):
        rules = pt.get_verification_rules()
        rule_ids = [r.id for r in rules]
        assert "capacitor-config-exists" in rule_ids
        assert "capacitor-plugin-consistency" in rule_ids

    def test_mobile_rules_are_additive(self, pt):
        web_pt = WebProjectType()
        web_count = len(web_pt.get_verification_rules())
        mobile_count = len(pt.get_verification_rules())
        assert mobile_count > web_count


class TestOrchestrationDirectives:
    def test_inherits_core_directives(self, pt):
        directives = pt.get_orchestration_directives()
        ids = [d.id for d in directives]
        assert "install-deps-npm" in ids
        assert "no-parallel-lockfile" in ids

    def test_inherits_web_directives(self, pt):
        directives = pt.get_orchestration_directives()
        ids = [d.id for d in directives]
        assert "no-parallel-i18n" in ids

    def test_has_mobile_directives(self, pt):
        directives = pt.get_orchestration_directives()
        ids = [d.id for d in directives]
        assert "cap-sync-after-config" in ids
        assert "no-parallel-ios-native" in ids
        assert "no-parallel-android-native" in ids

    def test_mobile_directives_are_additive(self, pt):
        web_pt = WebProjectType()
        web_count = len(web_pt.get_orchestration_directives())
        mobile_count = len(pt.get_orchestration_directives())
        assert mobile_count > web_count


class TestEngineIntegration:
    def test_detect_build_command_with_ios(self, pt, tmp_path):
        """With ios/App/ and capacitor.config.ts, returns combined command."""
        (tmp_path / "ios" / "App").mkdir(parents=True)
        (tmp_path / "capacitor.config.ts").touch()
        (tmp_path / "package.json").write_text('{}')
        cmd = pt.detect_build_command(str(tmp_path))
        assert cmd is not None
        assert "cap sync" in cmd

    def test_detect_build_command_without_ios(self, pt, tmp_path):
        """Without ios/, falls back to web detection."""
        (tmp_path / "package.json").write_text('{"scripts": {"build": "next build"}}')
        cmd = pt.detect_build_command(str(tmp_path))
        # Falls back to web — may return pnpm build or None depending on detection
        if cmd:
            assert "cap sync" not in cmd

    def test_planning_rules_not_empty(self, pt):
        rules = pt.planning_rules()
        assert len(rules) > 0
        assert "Capacitor" in rules or "mobile" in rules.lower()

    def test_cross_cutting_files_includes_capacitor(self, pt):
        files = pt.cross_cutting_files()
        assert "capacitor.config.ts" in files

    def test_ignore_patterns_includes_native_build(self, pt):
        patterns = pt.ignore_patterns()
        assert any("ios" in p for p in patterns)

    def test_security_checklist_not_empty(self, pt):
        checklist = pt.security_checklist()
        assert len(checklist) > 0
        assert "API key" in checklist or "Transport Security" in checklist
