"""Tests for design source provider hooks (v0-only pipeline)."""

import inspect
from pathlib import Path


def test_null_profile_design_source_defaults():
    """NullProfile returns 'none' + empty context (no design source)."""
    from set_orch.profile_loader import NullProfile

    profile = NullProfile()
    assert profile.detect_design_source(Path(".")) == "none"
    assert profile.get_design_dispatch_context("x", "scope", Path(".")) == ""


def test_core_profile_design_source_defaults():
    """CoreProfile inherits same defaults (subclasses override)."""
    from set_orch.profile_loader import CoreProfile

    profile = CoreProfile()
    assert profile.detect_design_source(Path(".")) == "none"
    assert profile.get_design_dispatch_context("x", "scope", Path(".")) == ""


def test_copy_design_source_slice_removed():
    """The slicing method is obsolete — agents get full v0-export/ via symlink."""
    from set_orch.profile_types import ProjectType

    assert not hasattr(ProjectType, "copy_design_source_slice")


def test_detect_design_source_returns_plain_str_forward_compat():
    """Return type is str (not Literal) so plugins can return 'figma-v2' etc."""
    from set_orch.profile_types import ProjectType

    sig = inspect.signature(ProjectType.detect_design_source)
    assert sig.return_annotation is str or sig.return_annotation == "str"


def test_removed_legacy_methods_absent_from_abc():
    """Old Figma ABC methods must be gone."""
    from set_orch.profile_types import ProjectType

    for removed in (
        "build_per_change_design",
        "build_design_review_section",
    ):
        assert not hasattr(ProjectType, removed), f"ProjectType still has {removed}"


def test_legacy_get_design_dispatch_context_new_signature():
    """get_design_dispatch_context now takes (change_name, scope, project_path)."""
    from set_orch.profile_types import ProjectType

    sig = inspect.signature(ProjectType.get_design_dispatch_context)
    params = list(sig.parameters.keys())
    assert params == ["self", "change_name", "scope", "project_path"]


def test_concrete_web_profile_does_not_retain_old_methods():
    """WebProjectType must not override removed methods."""
    try:
        from set_project_web.project_type import WebProjectType
    except ImportError:
        return  # web module not installed

    for removed in (
        "build_per_change_design",
        "build_design_review_section",
    ):
        assert not hasattr(WebProjectType, removed), \
            f"WebProjectType still defines {removed}"


def test_layer_1_has_no_v0_references():
    """lib/set_orch/ must not import any v0-specific helpers (Layer 1 abstraction guard)."""
    import re
    import os

    core_dir = Path(__file__).resolve().parents[2] / "lib" / "set_orch"
    assert core_dir.is_dir(), f"core dir not found: {core_dir}"

    v0_import_re = re.compile(
        r"^\s*(?:from|import)\s+(?:set_project_web\.v0_|.*v0_importer|.*v0_manifest|.*v0_renderer|.*v0_fidelity_gate|.*v0_validator)",
        re.MULTILINE,
    )
    offenders: list[str] = []
    for p in core_dir.rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if v0_import_re.search(text):
            offenders.append(str(p.relative_to(core_dir)))
    assert not offenders, f"Layer 1 references v0-specific modules: {offenders}"


def test_dispatcher_does_not_call_removed_methods():
    """Dispatcher code must not call build_per_change_design / build_design_review_section."""
    dispatcher_path = (
        Path(__file__).resolve().parents[2] / "lib" / "set_orch" / "dispatcher.py"
    )
    src = dispatcher_path.read_text(encoding="utf-8")
    for removed in ("build_per_change_design", "build_design_review_section"):
        assert removed not in src, f"dispatcher.py still references {removed}"
