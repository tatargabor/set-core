"""Tests for template resolution on the `base` (CoreProfile) project type.

Both cases here were found by running `set-project init --project-type base`
against a real project for the first time. It crashed, and neither failure was
visible from reading the code: one is a directory that a declaration promises
and the tree does not contain, the other is an abstract method whose implicit
None is reached through an MRO walk.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.profile_deploy import resolve_template
from set_orch.profile_loader import CoreProfile
from set_orch.profile_types import ProjectType


class TestTheBaseTypeShipsTheTemplateItDeclares:
    """`CoreProfile` advertised `templates/default` and the directory did not
    exist, so `--project-type base` failed for every project on earth. A
    declaration is not a file — the same shape as "a declaration is not data"."""

    def test_every_declared_template_directory_exists(self):
        profile = CoreProfile()
        declared = profile.get_templates()
        assert declared, "the base type must declare at least one template"
        for tmpl in declared:
            resolved = profile.get_template_dir(tmpl.id)
            assert resolved is not None, f"{tmpl.id}: get_template_dir returned None"
            assert resolved.is_dir(), f"{tmpl.id}: {resolved} is not a directory"
            assert any(resolved.iterdir()), f"{tmpl.id}: {resolved} is empty"

    def test_resolve_template_succeeds_with_no_explicit_id(self):
        # This is the path `set-project init --project-type base` takes: one
        # template declared, so the id is inferred rather than passed.
        template_id, template_dir = resolve_template(CoreProfile(), None)
        assert template_id == "default"
        assert template_dir.is_dir()


class TestAnUnknownTemplateIsAnError_NotACrash:
    """`get_template_dir` walks the MRO and calls `get_templates` on EVERY class
    that defines it, including the abstract base whose body is a docstring. When
    the requested id matched nothing earlier in the MRO, that None was iterated
    and the deploy died with `TypeError: 'NoneType' object is not iterable` —
    which reads as a bug in the caller rather than as "no such template"."""

    def test_the_abstract_get_templates_returns_a_list_not_none(self):
        assert ProjectType.__dict__["get_templates"](object()) == []

    def test_an_unknown_id_raises_a_named_error(self):
        with pytest.raises(ValueError) as exc:
            resolve_template(CoreProfile(), "no-such-template")
        assert "no-such-template" in str(exc.value)
        assert "Available" in str(exc.value)

    def test_get_template_dir_returns_None_for_an_unknown_id(self):
        assert CoreProfile().get_template_dir("no-such-template") is None
