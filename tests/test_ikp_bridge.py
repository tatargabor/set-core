"""Tests for ikp_bridge — IKP integration into set-core orchestration pipeline.

TDD: these tests define the expected API BEFORE implementation.
Run with: python -m pytest tests/test_ikp_bridge.py -v
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))


# ── Prerequisite: IKP package is available ──────────────────────────

class TestIkpPackageAvailability:
    """Verify the ikp package is installed and its API surface matches expectations."""

    def test_ikp_importable(self):
        import ikp  # noqa: F401

    def test_ikp_loader_api(self):
        from ikp.loader import load_pack, discover_packs, load_manifest
        from ikp.schema import Layer
        assert callable(load_pack)
        assert callable(discover_packs)
        assert callable(load_manifest)

    def test_ikp_injector_api(self):
        from ikp.injector import inject_to_rules, inject_to_context
        assert callable(inject_to_rules)
        assert callable(inject_to_context)

    def test_ikp_schema_enums(self):
        from ikp.schema import Layer
        assert Layer.KNOWLEDGE == "knowledge"
        assert Layer.PLANNING == "planning"
        assert Layer.IMPLEMENTATION == "implementation"
        assert Layer.TESTING == "testing"
        assert Layer.OPERATIONS == "operations"

    def test_discover_packs_finds_billingo(self):
        from ikp.loader import discover_packs
        packs = discover_packs()
        assert "billingo" in packs
        assert "wise-payments" in packs
        assert "google-gmail" in packs

    def test_load_manifest_billingo(self):
        from ikp.loader import load_manifest
        m = load_manifest("billingo")
        assert m.display_name == "Billingo"
        assert len(m.capabilities) > 0
        assert len(m.available_layers()) >= 3

    def test_load_pack_with_layer_filter(self):
        from ikp.loader import load_pack
        from ikp.schema import Layer
        pack = load_pack("billingo", layers=[Layer.KNOWLEDGE, Layer.PLANNING])
        assert len(pack.layers) == 2
        layer_types = [l.layer for l in pack.layers]
        assert Layer.KNOWLEDGE in layer_types
        assert Layer.PLANNING in layer_types

    def test_load_pack_with_language_filter(self):
        from ikp.loader import load_pack
        from ikp.schema import Layer
        pack = load_pack("billingo", layers=[Layer.IMPLEMENTATION], language="typescript")
        assert len(pack.layers) == 1
        assert pack.layers[0].language == "typescript"

    def test_to_context_returns_markdown(self):
        from ikp.loader import load_pack
        from ikp.schema import Layer
        pack = load_pack("billingo", layers=[Layer.KNOWLEDGE])
        ctx = pack.to_context()
        assert isinstance(ctx, str)
        assert len(ctx) > 100
        assert "Billingo" in ctx

    def test_inject_to_rules_creates_file(self):
        from ikp.injector import inject_to_rules
        from ikp.schema import Layer
        with tempfile.TemporaryDirectory() as tmpdir:
            result = inject_to_rules(
                "billingo",
                target_dir=Path(tmpdir),
                layers=[Layer.KNOWLEDGE],
            )
            assert result.exists()
            assert result.name == "ikp-billingo.md"
            content = result.read_text()
            assert "Billingo" in content


# ── IKP Bridge Module Tests ─────────────────────────────────────────

class TestIkpConfig:
    """Test .ikp.yaml loading and IkpConfig dataclass."""

    def _write_ikp_yaml(self, tmpdir, content):
        p = Path(tmpdir) / ".ikp.yaml"
        p.write_text(content)
        return tmpdir

    def test_load_valid_config(self):
        from set_orch.ikp_bridge import load_ikp_config
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_ikp_yaml(tmpdir, """
ikp: "0.2"
packs:
  - billingo
  - wise-payments
packs_dir: ~/code2/ikp/packs
language: typescript
""")
            cfg = load_ikp_config(Path(tmpdir))
            assert cfg is not None
            assert cfg.packs == ["billingo", "wise-payments"]
            assert cfg.language == "typescript"
            assert "~" not in str(cfg.packs_dir)  # expanded

    def test_load_missing_config_returns_none(self):
        from set_orch.ikp_bridge import load_ikp_config
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = load_ikp_config(Path(tmpdir))
            assert cfg is None

    def test_load_empty_packs_list(self):
        from set_orch.ikp_bridge import load_ikp_config
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_ikp_yaml(tmpdir, """
ikp: "0.2"
packs: []
packs_dir: ~/code2/ikp/packs
language: typescript
""")
            cfg = load_ikp_config(Path(tmpdir))
            assert cfg is not None
            assert cfg.packs == []

    def test_tilde_expansion(self):
        from set_orch.ikp_bridge import load_ikp_config
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_ikp_yaml(tmpdir, """
ikp: "0.2"
packs:
  - stripe
packs_dir: ~/code2/ikp/packs
language: typescript
""")
            cfg = load_ikp_config(Path(tmpdir))
            assert cfg.packs_dir == Path.home() / "code2" / "ikp" / "packs"


class TestHasIkpPipeline:
    """Test has_ikp_pipeline() detection logic."""

    def _write_ikp_yaml(self, tmpdir):
        p = Path(tmpdir) / ".ikp.yaml"
        p.write_text("""
ikp: "0.2"
packs:
  - billingo
packs_dir: ~/code2/ikp/packs
language: typescript
""")
        return tmpdir

    def test_returns_true_when_all_conditions_met(self):
        from set_orch.ikp_bridge import has_ikp_pipeline
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_ikp_yaml(tmpdir)
            assert has_ikp_pipeline(Path(tmpdir)) is True

    def test_returns_false_when_directive_none(self):
        from set_orch.ikp_bridge import has_ikp_pipeline
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_ikp_yaml(tmpdir)
            assert has_ikp_pipeline(Path(tmpdir), {"ikp_pipeline": "none"}) is False

    def test_returns_false_when_no_config(self):
        from set_orch.ikp_bridge import has_ikp_pipeline
        with tempfile.TemporaryDirectory() as tmpdir:
            assert has_ikp_pipeline(Path(tmpdir)) is False

    def test_returns_false_when_empty_packs(self):
        from set_orch.ikp_bridge import has_ikp_pipeline
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".ikp.yaml"
            p.write_text("ikp: '0.2'\npacks: []\npacks_dir: /tmp\nlanguage: ts\n")
            assert has_ikp_pipeline(Path(tmpdir)) is False

    @patch("set_orch.ikp_bridge._ikp_available", return_value=False)
    def test_returns_false_when_package_unavailable(self, mock_avail):
        from set_orch.ikp_bridge import has_ikp_pipeline
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_ikp_yaml(tmpdir)
            assert has_ikp_pipeline(Path(tmpdir)) is False


class TestGetContextForPhase:
    """Test phase-based layer loading."""

    def test_decompose_loads_l1_l2(self):
        from set_orch.ikp_bridge import get_context_for_phase, IkpConfig
        cfg = IkpConfig(
            packs=["billingo"],
            packs_dir=Path.home() / "code2" / "ikp" / "packs",
            language="typescript",
        )
        ctx = get_context_for_phase("decompose", ["billingo"], cfg)
        assert isinstance(ctx, str)
        assert len(ctx) > 0
        assert "billingo" in ctx.lower() or "Billingo" in ctx

    def test_dispatch_loads_l1_l3(self):
        from set_orch.ikp_bridge import get_context_for_phase, IkpConfig
        cfg = IkpConfig(
            packs=["billingo"],
            packs_dir=Path.home() / "code2" / "ikp" / "packs",
            language="typescript",
        )
        ctx = get_context_for_phase("dispatch", ["billingo"], cfg)
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_verify_loads_l4_l1(self):
        from set_orch.ikp_bridge import get_context_for_phase, IkpConfig
        cfg = IkpConfig(
            packs=["billingo"],
            packs_dir=Path.home() / "code2" / "ikp" / "packs",
            language="typescript",
        )
        ctx = get_context_for_phase("verify", ["billingo"], cfg)
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_unknown_pack_returns_partial(self):
        from set_orch.ikp_bridge import get_context_for_phase, IkpConfig
        cfg = IkpConfig(
            packs=["billingo", "nonexistent-pack"],
            packs_dir=Path.home() / "code2" / "ikp" / "packs",
            language="typescript",
        )
        ctx = get_context_for_phase("decompose", ["billingo", "nonexistent-pack"], cfg)
        assert "Billingo" in ctx
        # nonexistent pack should be skipped, not crash

    def test_multiple_packs(self):
        from set_orch.ikp_bridge import get_context_for_phase, IkpConfig
        cfg = IkpConfig(
            packs=["billingo", "wise-payments"],
            packs_dir=Path.home() / "code2" / "ikp" / "packs",
            language="typescript",
        )
        ctx = get_context_for_phase("decompose", ["billingo", "wise-payments"], cfg)
        assert "Billingo" in ctx
        assert "Wise" in ctx


class TestInjectRulesForChange:
    """Test rule file injection into worktree."""

    def test_creates_rule_file(self):
        from set_orch.ikp_bridge import inject_rules_for_change
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_dir = Path(tmpdir) / ".claude" / "rules"
            rules_dir.mkdir(parents=True)
            inject_rules_for_change(
                wt_path=Path(tmpdir),
                pack_names=["billingo"],
                phase="implement",
                language="typescript",
                packs_dir=Path.home() / "code2" / "ikp" / "packs",
            )
            rule_file = rules_dir / "ikp-billingo.md"
            assert rule_file.exists()
            content = rule_file.read_text()
            assert "Billingo" in content
            assert len(content) > 100

    def test_creates_multiple_rule_files(self):
        from set_orch.ikp_bridge import inject_rules_for_change
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_dir = Path(tmpdir) / ".claude" / "rules"
            rules_dir.mkdir(parents=True)
            inject_rules_for_change(
                wt_path=Path(tmpdir),
                pack_names=["billingo", "google-gmail"],
                phase="implement",
                language="typescript",
                packs_dir=Path.home() / "code2" / "ikp" / "packs",
            )
            assert (rules_dir / "ikp-billingo.md").exists()
            assert (rules_dir / "ikp-google-gmail.md").exists()

    def test_creates_rules_dir_if_missing(self):
        from set_orch.ikp_bridge import inject_rules_for_change
        with tempfile.TemporaryDirectory() as tmpdir:
            inject_rules_for_change(
                wt_path=Path(tmpdir),
                pack_names=["billingo"],
                phase="implement",
                language="typescript",
                packs_dir=Path.home() / "code2" / "ikp" / "packs",
            )
            assert (Path(tmpdir) / ".claude" / "rules" / "ikp-billingo.md").exists()

    def test_skips_unknown_pack(self):
        from set_orch.ikp_bridge import inject_rules_for_change
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_dir = Path(tmpdir) / ".claude" / "rules"
            rules_dir.mkdir(parents=True)
            inject_rules_for_change(
                wt_path=Path(tmpdir),
                pack_names=["nonexistent-pack"],
                phase="implement",
                language="typescript",
                packs_dir=Path.home() / "code2" / "ikp" / "packs",
            )
            assert not (rules_dir / "ikp-nonexistent-pack.md").exists()


class TestGracefulDegradation:
    """Test that bridge functions never crash when IKP is unavailable."""

    @patch("set_orch.ikp_bridge._ikp_available", return_value=False)
    def test_get_context_returns_empty_when_unavailable(self, mock_avail):
        from set_orch.ikp_bridge import get_context_for_phase, IkpConfig
        cfg = IkpConfig(
            packs=["billingo"],
            packs_dir=Path("/nonexistent"),
            language="typescript",
        )
        ctx = get_context_for_phase("decompose", ["billingo"], cfg)
        assert ctx == ""

    @patch("set_orch.ikp_bridge._ikp_available", return_value=False)
    def test_inject_rules_noop_when_unavailable(self, mock_avail):
        from set_orch.ikp_bridge import inject_rules_for_change
        with tempfile.TemporaryDirectory() as tmpdir:
            inject_rules_for_change(
                wt_path=Path(tmpdir),
                pack_names=["billingo"],
                phase="implement",
                language="typescript",
                packs_dir=Path("/nonexistent"),
            )
            rules_dir = Path(tmpdir) / ".claude" / "rules"
            assert not rules_dir.exists() or not list(rules_dir.glob("ikp-*.md"))


# ── Hook Point Verification ─────────────────────────────────────────

class TestExistingHookPoints:
    """Verify that the code patterns we plan to hook into actually exist."""

    def test_config_directive_defaults_exists(self):
        from set_orch.config import DIRECTIVE_DEFAULTS
        assert isinstance(DIRECTIVE_DEFAULTS, dict)
        assert "design_pipeline" in DIRECTIVE_DEFAULTS

    def test_design_pipeline_directive_pattern(self):
        from set_orch.config import DIRECTIVE_DEFAULTS
        assert DIRECTIVE_DEFAULTS["design_pipeline"] == "auto"

    def test_profile_has_design_pipeline_method(self):
        from set_orch.profile_loader import NullProfile
        p = NullProfile()
        assert hasattr(p, "has_design_pipeline")

    def test_profile_detect_design_source_method(self):
        from set_orch.profile_loader import NullProfile
        p = NullProfile()
        assert hasattr(p, "detect_design_source")
        assert p.detect_design_source(Path(".")) == "none"

    def test_profile_get_design_dispatch_context_method(self):
        from set_orch.profile_loader import NullProfile
        p = NullProfile()
        assert hasattr(p, "get_design_dispatch_context")

    def test_profile_category_taxonomy_method(self):
        from set_orch.profile_loader import NullProfile
        p = NullProfile()
        assert hasattr(p, "category_taxonomy")

    def test_profile_planning_rules_method(self):
        from set_orch.profile_loader import NullProfile
        p = NullProfile()
        assert hasattr(p, "planning_rules")
        assert isinstance(p.planning_rules(), str)

    def test_build_decomposition_context_exists(self):
        from set_orch.planner import build_decomposition_context
        assert callable(build_decomposition_context)

    def test_deploy_v0_export_function_exists(self):
        from set_orch.dispatcher import _deploy_v0_export_to_worktree
        assert callable(_deploy_v0_export_to_worktree)


# ── External Design Repo Tests ──────────────────────────────────────

class TestCssTokenExtraction:
    """Test design token extraction from globals.css."""

    def _write_globals_css(self, tmpdir, content):
        app_dir = Path(tmpdir) / "app"
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "globals.css").write_text(content)

    def test_extract_root_variables(self):
        from set_orch.ikp_bridge import _extract_css_tokens
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_globals_css(tmpdir, """
:root {
  --background: oklch(0.985 0 0);
  --foreground: oklch(0.205 0 0);
  --primary: oklch(0.205 0 0);
}
.dark {
  --background: oklch(0.178 0 0);
  --foreground: oklch(0.940 0 0);
}
""")
            tokens = _extract_css_tokens(Path(tmpdir) / "app" / "globals.css")
            assert "--background" in tokens["light"]
            assert "--background" in tokens["dark"]
            assert "oklch(0.985 0 0)" in tokens["light"]["--background"]

    def test_missing_globals_returns_empty(self):
        from set_orch.ikp_bridge import _extract_css_tokens
        tokens = _extract_css_tokens(Path("/nonexistent/globals.css"))
        assert tokens == {"light": {}, "dark": {}}

    def test_format_design_tokens_markdown(self):
        from set_orch.ikp_bridge import _format_design_tokens
        tokens = {
            "light": {"--background": "oklch(0.985 0 0)", "--primary": "oklch(0.205 0 0)"},
            "dark": {"--background": "oklch(0.178 0 0)", "--primary": "oklch(0.940 0 0)"},
        }
        md = _format_design_tokens(tokens)
        assert "## Design Tokens" in md
        assert "--background" in md
        assert "light" in md.lower() or "Light" in md


class TestExternalDesignRuleInjection:
    """Test .set-designer/design-rules/ symlink injection."""

    def test_inject_design_rules(self):
        from set_orch.ikp_bridge import _inject_external_design_rules
        with tempfile.TemporaryDirectory() as design_dir, \
             tempfile.TemporaryDirectory() as wt_dir:
            # Create design rules in external repo
            rules_path = Path(design_dir) / ".set-designer" / "design-rules"
            rules_path.mkdir(parents=True)
            (rules_path / "color-tokens.md").write_text("# Color token rules")
            (rules_path / "component-library.md").write_text("# Component rules")

            # Create .claude/rules in worktree
            wt_rules = Path(wt_dir) / ".claude" / "rules"
            wt_rules.mkdir(parents=True)

            count = _inject_external_design_rules(Path(design_dir), Path(wt_dir))
            assert count == 2
            assert (wt_rules / "design-color-tokens.md").exists()
            assert (wt_rules / "design-component-library.md").exists()

    def test_missing_design_rules_dir(self):
        from set_orch.ikp_bridge import _inject_external_design_rules
        with tempfile.TemporaryDirectory() as design_dir, \
             tempfile.TemporaryDirectory() as wt_dir:
            count = _inject_external_design_rules(Path(design_dir), Path(wt_dir))
            assert count == 0
