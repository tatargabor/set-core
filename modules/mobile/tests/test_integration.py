"""Integration tests for MobileProjectType — all profile methods callable."""

import pytest
from set_project_mobile import MobileProjectType


class TestAllMethodsCallable:
    @pytest.fixture
    def pt(self):
        return MobileProjectType()

    def test_basic_profile_methods(self, pt):
        assert isinstance(pt.get_templates(), list)
        assert isinstance(pt.get_verification_rules(), list)
        assert isinstance(pt.get_orchestration_directives(), list)

    def test_all_profile_methods_callable(self, pt):
        assert isinstance(pt.planning_rules(), str)
        assert isinstance(pt.security_checklist(), str)
        assert isinstance(pt.generated_file_patterns(), list)
        assert isinstance(pt.ignore_patterns(), list)
        assert isinstance(pt.gate_overrides("anything"), dict)
        assert isinstance(pt.cross_cutting_files(), list)
