"""Tests for design profile hooks (Layer 1/2 separation)."""

import os
import subprocess
import tempfile
from unittest.mock import patch, MagicMock

import pytest


def test_core_profile_returns_noop():
    """CoreProfile base methods return no-op values."""
    from set_orch.profile_loader import CoreProfile

    profile = CoreProfile()
    assert profile.build_per_change_design("x", "scope", "/tmp", ".") is False
    assert profile.get_design_dispatch_context("scope", ".") == ""
    assert profile.build_design_review_section(".") == ""
    assert profile.fetch_design_data_model(".") == ""


def test_null_profile_returns_noop():
    """NullProfile base methods return no-op values."""
    from set_orch.profile_loader import NullProfile

    profile = NullProfile()
    assert profile.build_per_change_design("x", "scope", "/tmp", ".") is False
    assert profile.get_design_dispatch_context("scope", ".") == ""
    assert profile.build_design_review_section(".") == ""
    assert profile.fetch_design_data_model(".") == ""


def test_web_profile_build_per_change_design_writes_file():
    """WebProjectType.build_per_change_design() writes design.md when design-brief.md exists."""
    from set_project_web.project_type import WebProjectType

    wp = WebProjectType()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create design-brief.md
        docs = os.path.join(tmpdir, "docs")
        os.makedirs(docs)
        with open(os.path.join(docs, "design-brief.md"), "w") as f:
            f.write("## Page: Home\nHero section\n")

        # Mock _run_bridge to return design content
        with patch.object(wp, "_run_bridge") as mock_bridge:
            mock_bridge.side_effect = [
                "## Visual Design: Home\nHero section content",  # design_brief_for_dispatch
                "## Design Tokens\n### Colors\n- primary: #000",  # design_context_for_dispatch
            ]

            # Need to be in the tmpdir so _find_design_brief works
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = wp.build_per_change_design("test-change", "Home page", tmpdir, tmpdir)
            finally:
                os.chdir(old_cwd)

        assert result is True
        design_path = os.path.join(tmpdir, "openspec", "changes", "test-change", "design.md")
        assert os.path.isfile(design_path)
        content = open(design_path).read()
        assert "Design Context" in content
        assert "Design Tokens" in content


def test_web_profile_design_review_calls_bridge():
    """WebProjectType.build_design_review_section() returns bridge.sh output."""
    from set_project_web.project_type import WebProjectType

    wp = WebProjectType()

    with patch.object(wp, "_run_bridge", return_value="## Design Compliance\nAll tokens match."):
        result = wp.build_design_review_section("/some/dir")

    assert "Design Compliance" in result
    assert "tokens match" in result


def test_web_profile_dispatch_context_combines_tokens_and_sources():
    """WebProjectType.get_design_dispatch_context() combines tokens + sources."""
    from set_project_web.project_type import WebProjectType

    wp = WebProjectType()

    with patch.object(wp, "_run_bridge") as mock_bridge:
        mock_bridge.side_effect = [
            "## Design Tokens\nColors here",  # design_context_for_dispatch
            "## Source Files\nButton.tsx code",  # design_sources_for_dispatch
        ]
        result = wp.get_design_dispatch_context("product catalog", ".")

    assert "Design Tokens" in result
    assert "Source Files" in result


def test_web_profile_data_model():
    """WebProjectType.fetch_design_data_model() returns bridge.sh output."""
    from set_project_web.project_type import WebProjectType

    wp = WebProjectType()

    with patch.object(wp, "_run_bridge", return_value="interface Product { id: string; name: string; }"):
        result = wp.fetch_design_data_model(".")

    assert "interface Product" in result
