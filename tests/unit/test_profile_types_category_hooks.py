"""Tests for the seven category-resolver hooks on `ProjectType`.

The category resolver (`lib/set_orch/category_resolver.py`) consumes
these hooks polymorphically. Each hook has a documented no-op default
on the ABC so:

1. `NullProfile` (used when no project type plugin is loaded) yields a
   safe baseline: all categories → `{"general"}` only, taxonomy =
   `["general"]`, no scope/path/REQ inference.
2. Plugin authors can override one or two hooks at a time without
   needing to implement all seven.
3. Existing plugins that subclass `ProjectType` directly (rather than
   `CoreProfile`) keep working — their unimplemented hooks return the
   ABC default, not `NotImplementedError`.

These tests pin the contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from set_orch.profile_loader import CoreProfile, NullProfile


@pytest.fixture
def null_profile():
    return NullProfile()


@pytest.fixture
def core_profile():
    return CoreProfile()


# ─── detect_project_categories ──────────────────────────────────────────


def test_null_profile_project_categories_default(null_profile, tmp_path):
    """NullProfile MUST return only `{general}` regardless of project state."""
    assert null_profile.detect_project_categories(tmp_path) == {"general"}


def test_core_profile_project_categories_default(core_profile, tmp_path):
    """CoreProfile inherits the universal `{general}` default."""
    assert core_profile.detect_project_categories(tmp_path) == {"general"}


# ─── detect_scope_categories ────────────────────────────────────────────


def test_null_profile_scope_categories_empty(null_profile):
    """No scope inference by default — even auth-laden text."""
    assert null_profile.detect_scope_categories(
        "Add /login page with NextAuth + Prisma session storage"
    ) == set()


def test_null_profile_scope_categories_empty_input(null_profile):
    assert null_profile.detect_scope_categories("") == set()


# ─── categories_from_paths ──────────────────────────────────────────────


def test_null_profile_paths_empty(null_profile):
    """No path classification by default — even paths that scream API/DB."""
    assert null_profile.categories_from_paths([
        "src/app/api/users/route.ts",
        "prisma/schema.prisma",
        "src/middleware.ts",
    ]) == set()


def test_null_profile_paths_empty_list(null_profile):
    assert null_profile.categories_from_paths([]) == set()


# ─── categories_from_change_type ────────────────────────────────────────


def test_null_profile_change_type_empty(null_profile):
    """No phase mapping by default."""
    for ct in ("foundational", "feature", "infrastructure", "schema",
               "cleanup-before", "cleanup-after"):
        assert null_profile.categories_from_change_type(ct) == set(), (
            f"NullProfile.categories_from_change_type({ct!r}) must be empty"
        )


def test_null_profile_change_type_unknown(null_profile):
    assert null_profile.categories_from_change_type("nonsense") == set()


# ─── categories_from_requirements ───────────────────────────────────────


def test_null_profile_requirements_empty(null_profile):
    """No REQ-prefix inference by default."""
    assert null_profile.categories_from_requirements([
        "REQ-AUTH-001", "REQ-API-USERS-002:AC-1", "REQ-NAV-007",
    ]) == set()


def test_null_profile_requirements_empty_list(null_profile):
    assert null_profile.categories_from_requirements([]) == set()


# ─── category_taxonomy ──────────────────────────────────────────────────


def test_null_profile_taxonomy_universal_only(null_profile):
    """Universal baseline: only `general`."""
    assert null_profile.category_taxonomy() == ["general"]


def test_taxonomy_always_includes_general(null_profile, core_profile):
    """Every taxonomy MUST include `general` so the universal-bucket
    contract holds."""
    assert "general" in null_profile.category_taxonomy()
    assert "general" in core_profile.category_taxonomy()


# ─── project_summary_for_classifier ─────────────────────────────────────


def test_null_profile_summary_empty(null_profile, tmp_path):
    """No project context by default — empty string."""
    assert null_profile.project_summary_for_classifier(tmp_path) == ""


# ─── llm_classifier_model ───────────────────────────────────────────────


def test_default_model_is_sonnet(null_profile, core_profile):
    """Default LLM is Sonnet 4.6 — chosen for additive edge-case
    detection per design.md D3. Profiles can override to Haiku or
    None."""
    assert null_profile.llm_classifier_model == "claude-sonnet-4-6"
    assert core_profile.llm_classifier_model == "claude-sonnet-4-6"


def test_llm_model_can_be_disabled():
    """A profile that returns None disables LLM augmentation entirely
    (purely deterministic resolution)."""
    from set_orch.profile_types import ProjectType, ProjectTypeInfo

    class _NoLLM(NullProfile):
        @property
        def llm_classifier_model(self) -> str | None:
            return None

    assert _NoLLM().llm_classifier_model is None


# ─── Plugin partial-override scenario ───────────────────────────────────


def test_partial_override_does_not_break_other_hooks(tmp_path):
    """A plugin that overrides only `categories_from_paths` MUST still
    return the ABC defaults for the other six hooks. This protects the
    'one-hook-at-a-time' developer experience."""
    from set_orch.profile_types import ProjectTypeInfo

    class _PartialPlugin(NullProfile):
        @property
        def info(self) -> ProjectTypeInfo:
            return ProjectTypeInfo(name="partial", version="0.0.1",
                                   description="test", parent="base")

        def categories_from_paths(self, paths: list[str]) -> set[str]:
            return {"frontend"} if any(p.endswith(".tsx") for p in paths) else set()

    p = _PartialPlugin()
    # Overridden hook works
    assert p.categories_from_paths(["x.tsx"]) == {"frontend"}
    # Other hooks return ABC defaults (no NotImplementedError)
    assert p.detect_project_categories(tmp_path) == {"general"}
    assert p.detect_scope_categories("oauth login") == set()
    assert p.categories_from_change_type("feature") == set()
    assert p.categories_from_requirements(["REQ-AUTH-001"]) == set()
    assert p.category_taxonomy() == ["general"]
    assert p.project_summary_for_classifier(tmp_path) == ""
    assert p.llm_classifier_model == "claude-sonnet-4-6"
