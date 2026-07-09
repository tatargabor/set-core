"""Tests for the IKP decomposer + dispatcher wiring.

Covers the acceptance criteria of the `ikp-decomposer-dispatch` change:
IKP context in the planning prompt, planner-assigned `ikp_packs` with a
keyword-match fallback, dispatcher rule injection + input.md summary,
the `integration` category signal, and L4 testing context at review.

Run with: python -m pytest tests/test_ikp_decomposer_dispatch.py -v
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from set_orch import ikp_bridge  # noqa: E402
from set_orch.planner import _assign_ikp_packs, _build_ikp_decompose_context  # noqa: E402
from set_orch.templates import render_planning_prompt  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────


def _write_pack(packs_dir: Path, name: str, **overrides) -> Path:
    """Create a minimal on-disk IKP pack."""
    pack_dir = packs_dir / name
    pack_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "ikp": "0.2",
        "name": name,
        "display_name": name.title(),
        "category": "invoicing",
        "description": f"{name} test pack",
        "pack_version": "0.1.0",
        "capabilities": [
            {"id": "create-invoice", "name": "Create Invoice", "complexity": "medium"},
            {"id": "download-pdf", "name": "Download PDF", "complexity": "low"},
        ],
        "pitfalls": ["PDF download returns HTTP 202 while still generating — poll until 200"],
        "layers": {"knowledge": True, "planning": True},
    }
    data.update(overrides)
    (pack_dir / "pack.yaml").write_text(yaml.safe_dump(data))
    (pack_dir / "knowledge.md").write_text(
        f"# {name}\n\nAuth uses the `{name.upper()}_API_KEY` environment variable.\n"
        "Responses use CONTENT_TYPE application/json.\n"
    )
    (pack_dir / "operations.md").write_text(
        f"Set `{name.upper()}_WEBHOOK_SECRET` in production.\n"
    )
    return pack_dir


@pytest.fixture
def ikp_project(tmp_path):
    """A project root with .ikp.yaml declaring two packs."""
    packs_dir = tmp_path / "packs"
    _write_pack(packs_dir, "billingo")
    _write_pack(packs_dir, "wise-payments")

    (tmp_path / ".ikp.yaml").write_text(
        yaml.safe_dump({
            "ikp": "0.2",
            "packs": ["billingo", "wise-payments"],
            "packs_dir": str(packs_dir),
            "language": "typescript",
        })
    )
    return tmp_path


# ── AC-1 / AC-2: IKP context in the decomposition prompt ────────────


class TestDecomposeContext:
    def test_ac1_active_pipeline_builds_context(self, ikp_project):
        """AC-1: active pipeline + declared packs → non-empty ikp_context."""
        with patch.object(ikp_bridge, "has_ikp_pipeline", return_value=True), \
             patch.object(
                 ikp_bridge, "get_context_for_phase",
                 return_value="### billingo\n**Capabilities:** create-invoice",
             ):
            ctx = _build_ikp_decompose_context(str(ikp_project))

        assert "billingo" in ctx

    def test_ac2_inactive_pipeline_yields_empty_context(self, tmp_path):
        """AC-2: no .ikp.yaml → empty context, no IKP section in the prompt."""
        ctx = _build_ikp_decompose_context(str(tmp_path))
        assert ctx == ""

        prompt = render_planning_prompt(
            input_content="build a shop", specs="", ikp_context=ctx,
        )
        assert "Integration Knowledge (IKP)" not in prompt

    def test_ikp_section_rendered_when_context_present(self):
        prompt = render_planning_prompt(
            input_content="build a shop",
            specs="",
            ikp_context="### billingo\n**Capabilities:** create-invoice (medium)",
        )
        assert "## Integration Knowledge (IKP)" in prompt
        assert "create-invoice (medium)" in prompt
        assert "`ikp_packs`" in prompt

    def test_oversized_context_falls_back_to_summaries(self, ikp_project):
        """Token budget: oversized L1+L2 degrades to pack.yaml summaries."""
        config = ikp_bridge.load_ikp_config(ikp_project)
        huge = "x" * (ikp_bridge._DECOMPOSE_TOKEN_BUDGET * 4 + 10)

        with patch.object(ikp_bridge, "get_context_for_phase", return_value=huge):
            ctx = ikp_bridge.get_decompose_context(["billingo"], config)

        assert ctx != huge
        assert "create-invoice" in ctx


# ── AC-3..AC-6: planner assigns ikp_packs, with fallback ────────────


class TestPackAssignment:
    def _assign(self, project, changes):
        plan = {"changes": changes}
        _assign_ikp_packs(plan, project_path=str(project))
        return plan["changes"]

    def test_ac3_planner_assigned_packs_preserved(self, ikp_project):
        changes = self._assign(ikp_project, [
            {"name": "billingo-invoices", "scope": "Billingo API integration",
             "ikp_packs": ["billingo"]},
        ])
        assert changes[0]["ikp_packs"] == ["billingo"]

    def test_ac4_non_integration_change_stays_empty(self, ikp_project):
        changes = self._assign(ikp_project, [
            {"name": "prisma-schema", "scope": "Prisma schema — base entities",
             "ikp_packs": []},
        ])
        assert changes[0]["ikp_packs"] == []

    def test_ac5_omitted_field_defaults_to_empty_list(self, ikp_project):
        changes = self._assign(ikp_project, [
            {"name": "prisma-schema", "scope": "Prisma schema — base entities"},
        ])
        assert changes[0]["ikp_packs"] == []

    def test_ac6_keyword_fallback_assigns_from_scope(self, ikp_project):
        """AC-6: planner omitted packs but scope names a declared pack."""
        changes = self._assign(ikp_project, [
            {"name": "invoicing", "scope": "Wire up Billingo invoice generation"},
        ])
        assert changes[0]["ikp_packs"] == ["billingo"]

    def test_fallback_ignores_undeclared_names(self, ikp_project):
        changes = self._assign(ikp_project, [
            {"name": "payments", "scope": "Integrate with Stripe for checkout"},
        ])
        assert changes[0]["ikp_packs"] == []

    def test_undeclared_planner_packs_are_dropped(self, ikp_project):
        changes = self._assign(ikp_project, [
            {"name": "payments", "scope": "checkout",
             "ikp_packs": ["billingo", "stripe"]},
        ])
        assert changes[0]["ikp_packs"] == ["billingo"]

    def test_no_ikp_project_leaves_packs_empty(self, tmp_path):
        changes = self._assign(tmp_path, [
            {"name": "invoicing", "scope": "Wire up Billingo invoice generation"},
        ])
        assert changes[0]["ikp_packs"] == []


# ── AC-7..AC-9: dispatcher injection + input.md summary ─────────────


class TestDispatcherInjection:
    def test_ac7_injects_rule_file_for_declared_pack(self, ikp_project, tmp_path):
        from set_orch.dispatcher import _inject_ikp_rules

        wt = tmp_path / "wt"
        wt.mkdir()
        change = SimpleNamespace(name="billingo-invoices", ikp_packs=["billingo"])
        created_path = wt / ".claude" / "rules" / "ikp-billingo.md"

        def fake_inject(*, wt_path, pack_names, phase, language, packs_dir):
            target = wt_path / ".claude" / "rules"
            target.mkdir(parents=True, exist_ok=True)
            (target / "ikp-billingo.md").write_text("# billingo rules")
            return [target / "ikp-billingo.md"]

        with patch.object(ikp_bridge, "has_ikp_pipeline", return_value=True), \
             patch.object(ikp_bridge, "inject_rules_for_change", side_effect=fake_inject):
            summary = _inject_ikp_rules(change, str(wt), str(ikp_project), {})

        assert created_path.is_file()
        assert "## Integration Packs (IKP)" in summary

    def test_ac8_no_packs_skips_injection_entirely(self, ikp_project, tmp_path):
        from set_orch.dispatcher import _inject_ikp_rules

        wt = tmp_path / "wt"
        wt.mkdir()
        change = SimpleNamespace(name="prisma-schema", ikp_packs=[])

        with patch.object(ikp_bridge, "inject_rules_for_change") as mock_inject:
            summary = _inject_ikp_rules(change, str(wt), str(ikp_project), {})

        mock_inject.assert_not_called()
        assert summary == ""

    def test_inactive_pipeline_skips_injection(self, tmp_path):
        from set_orch.dispatcher import _inject_ikp_rules

        wt = tmp_path / "wt"
        wt.mkdir()
        change = SimpleNamespace(name="billingo-invoices", ikp_packs=["billingo"])

        with patch.object(ikp_bridge, "has_ikp_pipeline", return_value=False), \
             patch.object(ikp_bridge, "inject_rules_for_change") as mock_inject:
            summary = _inject_ikp_rules(change, str(wt), str(tmp_path), {})

        mock_inject.assert_not_called()
        assert summary == ""

    def test_injection_failure_does_not_fail_dispatch(self, ikp_project, tmp_path):
        from set_orch.dispatcher import _inject_ikp_rules

        wt = tmp_path / "wt"
        wt.mkdir()
        change = SimpleNamespace(name="billingo-invoices", ikp_packs=["billingo"])

        with patch.object(ikp_bridge, "has_ikp_pipeline", return_value=True), \
             patch.object(
                 ikp_bridge, "inject_rules_for_change",
                 side_effect=RuntimeError("pack corrupt"),
             ):
            summary = _inject_ikp_rules(change, str(wt), str(ikp_project), {})

        assert summary == ""

    def test_ac9_summary_has_capabilities_env_vars_pitfalls(self, ikp_project):
        packs_dir = ikp_project / "packs"
        summary = ikp_bridge.build_pack_summaries(["billingo"], packs_dir)

        assert "## Integration Packs (IKP)" in summary
        assert "create-invoice (medium)" in summary
        assert "BILLINGO_API_KEY" in summary
        assert "Pitfall:" in summary
        assert ".claude/rules/ikp-*.md" in summary

    def test_summary_excludes_header_like_tokens(self, ikp_project):
        summary = ikp_bridge.build_pack_summaries(["billingo"], ikp_project / "packs")
        assert "CONTENT_TYPE" not in summary

    def test_summary_empty_for_unknown_pack(self, ikp_project):
        assert ikp_bridge.build_pack_summaries(["nope"], ikp_project / "packs") == ""

    def test_input_md_renders_ikp_summary(self):
        from set_orch.dispatcher import DispatchContext, _build_input_content

        ctx = DispatchContext(ikp_summary="## Integration Packs (IKP)\n\n- **billingo**")
        content = _build_input_content("billingo-invoices", "scope text", "", ctx)

        assert "## Integration Packs (IKP)" in content
        assert "- **billingo**" in content

    def test_input_md_omits_section_without_packs(self):
        from set_orch.dispatcher import DispatchContext, _build_input_content

        ctx = DispatchContext()
        content = _build_input_content("prisma-schema", "scope text", "", ctx)

        assert "Integration Packs (IKP)" not in content


# ── AC-10: category resolver integration signal ─────────────────────


class TestCategoryResolver:
    def _resolve(self, tmp_path, ikp_packs):
        from set_orch.category_resolver import resolve_change_categories

        profile = SimpleNamespace(
            categories_from_change_type=lambda _: set(),
            categories_from_requirements=lambda _: set(),
            categories_from_paths=lambda _: set(),
            detect_scope_categories=lambda _: set(),
            detect_project_categories=lambda _: set(),
            category_taxonomy=lambda: ["general", "integration"],
        )
        with patch(
            "set_orch.category_resolver._call_llm", return_value=(set(), {}),
        ):
            return resolve_change_categories(
                change_name="c", change_type="feature", scope="s",
                req_ids=[], manifest_paths=[], deps=[],
                profile=profile, project_path=tmp_path,
                audit_log_path=str(tmp_path / "audit.jsonl"),
                ikp_packs=ikp_packs,
            )

    def test_ac10_packs_add_integration_category(self, tmp_path):
        result = self._resolve(tmp_path, ["billingo"])
        assert "integration" in result.final_categories

    def test_no_packs_omits_integration_category(self, tmp_path):
        result = self._resolve(tmp_path, [])
        assert "integration" not in result.final_categories

    def test_integration_in_web_taxonomy(self):
        sys.path.insert(
            0, os.path.join(os.path.dirname(__file__), "..", "modules", "web"),
        )
        from set_project_web.project_type import WebProjectType

        assert "integration" in WebProjectType().category_taxonomy()


# ── AC-11: L4 testing context at review ─────────────────────────────


class TestReviewContext:
    def _state_file(self, tmp_path, ikp_packs):
        import json

        state = {
            "changes": [{
                "name": "billingo-invoices",
                "scope": "Billingo integration",
                "status": "verifying",
                "ikp_packs": ikp_packs,
            }],
        }
        path = tmp_path / "state.json"
        path.write_text(json.dumps(state))
        return str(path)

    def test_ac11_review_prompt_gets_l4_context(self, tmp_path, ikp_project):
        from set_orch.verifier import _build_ikp_review_context

        # .ikp.yaml must sit next to the state file (project root).
        (tmp_path / ".ikp.yaml").write_text((ikp_project / ".ikp.yaml").read_text())
        state_file = self._state_file(tmp_path, ["billingo"])

        with patch.object(ikp_bridge, "has_ikp_pipeline", return_value=True), \
             patch.object(
                 ikp_bridge, "get_context_for_phase",
                 return_value="Sandbox: use test API key. Mock: HTTP-level.",
             ):
            ctx = _build_ikp_review_context("billingo-invoices", state_file)

        assert "Integration Testing Context (IKP)" in ctx
        assert "Sandbox: use test API key" in ctx

    def test_review_without_packs_returns_empty(self, tmp_path):
        from set_orch.verifier import _build_ikp_review_context

        state_file = self._state_file(tmp_path, [])
        assert _build_ikp_review_context("billingo-invoices", state_file) == ""

    def test_review_context_never_raises(self, tmp_path):
        from set_orch.verifier import _build_ikp_review_context

        assert _build_ikp_review_context("x", str(tmp_path / "missing.json")) == ""


# ── State round-trip: ikp_packs survives plan → state → dispatch ────


class TestStateRoundTrip:
    def test_ikp_packs_persist_through_state(self, tmp_path):
        import json

        from set_orch.state import init_state, load_state

        plan = {
            "plan_version": 1,
            "changes": [
                {"name": "billingo-invoices", "scope": "s", "ikp_packs": ["billingo"]},
                {"name": "prisma-schema", "scope": "s"},
            ],
        }
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))
        state_file = tmp_path / "state.json"

        init_state(str(plan_file), str(state_file))
        state = load_state(str(state_file))

        by_name = {c.name: c for c in state.changes}
        assert by_name["billingo-invoices"].ikp_packs == ["billingo"]
        assert by_name["prisma-schema"].ikp_packs == []
