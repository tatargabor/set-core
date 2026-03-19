"""Tests for wt_orch.planner — Planning, validation, scope overlap, test infra detection."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from wt_orch.planner import (
    ScopeOverlap,
    TestInfra,
    TriageStatus,
    ValidationResult,
    _assign_cross_cutting_ownership,
    _extract_scope_keywords,
    build_decomposition_context,
    check_scope_overlap,
    check_triage_gate,
    detect_test_infra,
    enrich_plan_metadata,
    estimate_tokens,
    validate_plan,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


VALID_PLAN = {
    "plan_version": 1,
    "brief_hash": "abc123",
    "changes": [
        {
            "name": "add-auth",
            "scope": "Add authentication system with login registration password reset",
            "complexity": "L",
            "change_type": "feature",
            "depends_on": [],
        },
        {
            "name": "fix-login",
            "scope": "Fix login page validation error handling display",
            "complexity": "S",
            "change_type": "bugfix",
            "depends_on": ["add-auth"],
        },
    ],
}


# ─── validate_plan ──────────────────────────────────────────────────


class TestValidatePlan:
    def test_valid_plan(self, tmp_dir):
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(VALID_PLAN, f)

        result = validate_plan(plan_path)
        assert isinstance(result, ValidationResult)
        assert result.ok
        assert len(result.errors) == 0

    def test_invalid_json(self, tmp_dir):
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            f.write("not json {{{")

        result = validate_plan(plan_path)
        assert not result.ok
        assert any("not valid JSON" in e for e in result.errors)

    def test_missing_file(self, tmp_dir):
        result = validate_plan(os.path.join(tmp_dir, "nonexistent.json"))
        assert not result.ok
        assert any("Cannot read" in e for e in result.errors)

    def test_missing_required_fields(self, tmp_dir):
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump({"changes": []}, f)

        result = validate_plan(plan_path)
        assert not result.ok
        assert any("plan_version" in e for e in result.errors)
        assert any("brief_hash" in e for e in result.errors)

    def test_bad_change_names(self, tmp_dir):
        plan = {
            "plan_version": 1,
            "brief_hash": "abc",
            "changes": [
                {"name": "BAD_NAME", "scope": "test", "complexity": "S", "depends_on": []},
                {"name": "also bad", "scope": "test", "complexity": "S", "depends_on": []},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        result = validate_plan(plan_path)
        assert not result.ok
        assert any("kebab-case" in e for e in result.errors)

    def test_valid_kebab_names(self, tmp_dir):
        plan = {
            "plan_version": 1,
            "brief_hash": "abc",
            "changes": [
                {"name": "add-feature-1", "scope": "alpha bravo charlie delta echo", "complexity": "S", "depends_on": []},
                {"name": "fix-bug-2", "scope": "foxtrot golf hotel india juliet", "complexity": "S", "depends_on": []},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        result = validate_plan(plan_path)
        assert result.ok

    def test_missing_depends_on_target(self, tmp_dir):
        plan = {
            "plan_version": 1,
            "brief_hash": "abc",
            "changes": [
                {"name": "feature-a", "scope": "alpha bravo charlie delta echo", "complexity": "S", "depends_on": ["nonexistent"]},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        result = validate_plan(plan_path)
        assert not result.ok
        assert any("nonexistent" in e for e in result.errors)

    def test_circular_dependency(self, tmp_dir):
        plan = {
            "plan_version": 1,
            "brief_hash": "abc",
            "changes": [
                {"name": "feature-a", "scope": "alpha bravo charlie delta echo", "complexity": "S", "depends_on": ["feature-b"]},
                {"name": "feature-b", "scope": "foxtrot golf hotel india juliet", "complexity": "S", "depends_on": ["feature-a"]},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        result = validate_plan(plan_path)
        assert not result.ok
        assert any("Circular" in e for e in result.errors)

    def test_digest_mode_validates_requirements(self, tmp_dir):
        plan = {
            "plan_version": 1,
            "brief_hash": "abc",
            "changes": [
                {
                    "name": "feature-a",
                    "scope": "alpha bravo charlie delta echo foxtrot golf hotel",
                    "complexity": "S",
                    "depends_on": [],
                    "requirements": ["REQ-001", "REQ-FAKE"],
                },
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        reqs = {"requirements": [{"id": "REQ-001", "status": "active"}]}
        req_path = os.path.join(tmp_dir, "requirements.json")
        with open(req_path, "w") as f:
            json.dump(reqs, f)

        result = validate_plan(plan_path, digest_dir=tmp_dir)
        # REQ-FAKE should generate a warning
        assert any("REQ-FAKE" in w for w in result.warnings)

    def test_to_dict(self):
        r = ValidationResult(errors=["e1"], warnings=["w1"])
        d = r.to_dict()
        assert d == {"errors": ["e1"], "warnings": ["w1"]}

    def test_source_items_valid_refs(self, tmp_dir):
        """source_items with valid change refs pass validation."""
        plan = {
            **VALID_PLAN,
            "source_items": [
                {"id": "SI-1", "text": "Auth system", "change": "add-auth"},
                {"id": "SI-2", "text": "Login fix", "change": "fix-login"},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        result = validate_plan(plan_path)  # no digest_dir → single-file mode
        assert result.ok

    def test_source_items_invalid_ref_errors(self, tmp_dir):
        """source_items referencing non-existent changes produce errors."""
        plan = {
            **VALID_PLAN,
            "source_items": [
                {"id": "SI-1", "text": "Auth system", "change": "nonexistent-change"},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        result = validate_plan(plan_path)
        assert not result.ok
        assert any("non-existent change" in e for e in result.errors)

    def test_source_items_null_change_warns(self, tmp_dir):
        """source_items with change: null produce warnings."""
        plan = {
            **VALID_PLAN,
            "source_items": [
                {"id": "SI-1", "text": "Auth system", "change": "add-auth"},
                {"id": "SI-2", "text": "Admin bulk export", "change": None},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        result = validate_plan(plan_path)
        assert result.ok  # warnings don't block
        assert any("SI-2" in w and "excluded" in w.lower() for w in result.warnings)

    def test_no_source_items_no_digest_warns(self, tmp_dir):
        """Missing source_items in non-digest mode warns about no coverage tracking."""
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(VALID_PLAN, f)

        result = validate_plan(plan_path)  # no digest_dir, no source_items
        assert any("coverage tracking unavailable" in w for w in result.warnings)


# ─── generate_coverage_report ──────────────────────────────────────


class TestGenerateCoverageReport:
    def test_digest_mode_static(self, tmp_dir):
        """Digest mode without state_file renders COVERED/UNCOVERED."""
        from wt_orch.planner import generate_coverage_report

        digest_dir = os.path.join(tmp_dir, "digest")
        os.makedirs(digest_dir)
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump({"requirements": [
                {"id": "REQ-1", "title": "Auth"},
                {"id": "REQ-2", "title": "Cart"},
            ]}, f)

        plan = {"changes": [{"name": "auth-change", "requirements": ["REQ-1"]}]}
        output = os.path.join(tmp_dir, "report.md")
        generate_coverage_report(plan=plan, digest_dir=digest_dir, output_path=output)

        content = open(output).read()
        assert "REQ-1" in content
        assert "COVERED" in content
        assert "UNCOVERED" in content

    def test_digest_mode_state_aware(self, tmp_dir):
        """Digest mode with state_file renders MERGED/PENDING."""
        from wt_orch.planner import generate_coverage_report

        digest_dir = os.path.join(tmp_dir, "digest")
        os.makedirs(digest_dir)
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump({"requirements": [
                {"id": "REQ-1", "title": "Auth"},
                {"id": "REQ-2", "title": "Cart"},
            ]}, f)

        state_file = os.path.join(tmp_dir, "state.json")
        with open(state_file, "w") as f:
            json.dump({"changes": [
                {"name": "auth-change", "status": "merged"},
                {"name": "cart-change", "status": "failed"},
            ]}, f)

        plan = {
            "changes": [
                {"name": "auth-change", "requirements": ["REQ-1"]},
                {"name": "cart-change", "requirements": ["REQ-2"]},
            ],
        }
        output = os.path.join(tmp_dir, "report.md")
        generate_coverage_report(
            plan=plan, digest_dir=digest_dir, output_path=output, state_file=state_file,
        )

        content = open(output).read()
        assert "MERGED" in content
        assert "FAILED" in content

    def test_source_items_mode(self, tmp_dir):
        """Single-file mode renders source_items with EXCLUDED for null-change."""
        from wt_orch.planner import generate_coverage_report

        plan = {
            "changes": [{"name": "my-change"}],
            "source_items": [
                {"id": "SI-1", "text": "Feature A", "change": "my-change"},
                {"id": "SI-2", "text": "Feature B", "change": None},
            ],
        }
        output = os.path.join(tmp_dir, "report.md")
        generate_coverage_report(plan=plan, output_path=output)

        content = open(output).read()
        assert "SI-1" in content
        assert "SI-2" in content
        assert "EXCLUDED" in content
        assert "my-change" in content


# ─── check_scope_overlap ────────────────────────────────────────────


class TestCheckScopeOverlap:
    def test_no_overlap(self, tmp_dir):
        plan = {
            "changes": [
                {"name": "auth", "scope": "authentication login password security credentials"},
                {"name": "docs", "scope": "documentation readme markdown writing"},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        overlaps = check_scope_overlap(plan_path)
        assert len(overlaps) == 0

    def test_high_overlap(self, tmp_dir):
        plan = {
            "changes": [
                {"name": "auth-login", "scope": "authentication login page validation error handling display"},
                {"name": "auth-fix", "scope": "authentication login page validation fix error display"},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        overlaps = check_scope_overlap(plan_path)
        assert len(overlaps) > 0
        assert overlaps[0].similarity >= 40

    def test_insufficient_keywords_skip(self, tmp_dir):
        plan = {
            "changes": [
                {"name": "tiny-a", "scope": "ab cd"},
                {"name": "tiny-b", "scope": "ab cd"},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        overlaps = check_scope_overlap(plan_path)
        # Short words under 3 chars excluded, so both scopes empty → skipped
        assert len(overlaps) == 0

    def test_active_change_overlap(self, tmp_dir):
        plan = {
            "changes": [
                {"name": "new-auth", "scope": "authentication login password security credentials validation"},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        state = {
            "changes": [
                {"name": "old-auth", "scope": "authentication login password security credentials handling", "status": "running"},
            ],
        }
        state_path = os.path.join(tmp_dir, "state.json")
        with open(state_path, "w") as f:
            json.dump(state, f)

        overlaps = check_scope_overlap(plan_path, state_path=state_path)
        assert any(o.name_b == "old-auth" for o in overlaps)

    def test_cross_cutting_hazard(self, tmp_dir):
        plan = {
            "changes": [
                {"name": "feature-a", "scope": "modify routes.ts add new endpoint for users"},
                {"name": "feature-b", "scope": "update routes.ts for admin dashboard"},
            ],
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        # Create a YAML file for project knowledge
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not available")

        pk = {"cross_cutting_files": [{"path": "src/routes.ts"}]}
        pk_path = os.path.join(tmp_dir, "project-knowledge.yaml")
        with open(pk_path, "w") as f:
            yaml.dump(pk, f)

        overlaps = check_scope_overlap(plan_path, pk_path=pk_path)
        # Should detect cross-cutting file overlap (100% marker)
        cc_overlaps = [o for o in overlaps if o.similarity == 100]
        assert len(cc_overlaps) > 0

    def test_extract_scope_keywords(self):
        words = _extract_scope_keywords("Add authentication login and Security")
        assert "authentication" in words
        assert "login" in words
        assert "security" in words
        assert "add" in words
        assert "and" in words
        # Short words (<3 chars) excluded
        assert "ab" not in _extract_scope_keywords("ab cd ef")


# ─── detect_test_infra ──────────────────────────────────────────────


class TestDetectTestInfra:
    def test_vitest_project(self, tmp_dir):
        with open(os.path.join(tmp_dir, "vitest.config.ts"), "w") as f:
            f.write("export default {}")
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump({"scripts": {"test": "vitest"}}, f)
        with open(os.path.join(tmp_dir, "pnpm-lock.yaml"), "w") as f:
            f.write("")
        os.makedirs(os.path.join(tmp_dir, "src"))
        with open(os.path.join(tmp_dir, "src", "app.test.ts"), "w") as f:
            f.write("")

        infra = detect_test_infra(tmp_dir)
        assert infra.framework == "vitest"
        assert infra.config_exists is True
        assert infra.test_file_count >= 1
        assert infra.test_command == "pnpm run test"

    def test_pytest_project(self, tmp_dir):
        with open(os.path.join(tmp_dir, "pyproject.toml"), "w") as f:
            f.write("[tool.pytest.ini_options]\nminversion = '6.0'\n")
        os.makedirs(os.path.join(tmp_dir, "tests"))
        with open(os.path.join(tmp_dir, "tests", "test_main.py"), "w") as f:
            f.write("")

        infra = detect_test_infra(tmp_dir)
        assert infra.framework == "pytest"
        assert infra.config_exists is True
        assert infra.test_file_count >= 1
        assert infra.has_helpers is True  # tests/ dir exists

    def test_no_infra(self, tmp_dir):
        infra = detect_test_infra(tmp_dir)
        assert infra.framework == ""
        assert infra.config_exists is False
        assert infra.test_file_count == 0
        assert infra.test_command == ""

    def test_test_command_detection_npm(self, tmp_dir):
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump({"scripts": {"test:unit": "jest"}}, f)
        # No lockfile → defaults to npm
        infra = detect_test_infra(tmp_dir)
        assert infra.test_command == "npm run test:unit"

    def test_test_command_detection_yarn(self, tmp_dir):
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump({"scripts": {"test": "jest"}}, f)
        with open(os.path.join(tmp_dir, "yarn.lock"), "w") as f:
            f.write("")
        infra = detect_test_infra(tmp_dir)
        assert infra.test_command == "yarn run test"

    def test_jest_detected_from_devdeps(self, tmp_dir):
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump({"devDependencies": {"jest": "^29.0.0"}, "scripts": {"test": "jest"}}, f)

        infra = detect_test_infra(tmp_dir)
        assert infra.framework == "jest"

    def test_to_dict(self):
        infra = TestInfra(framework="vitest", config_exists=True, test_file_count=5, has_helpers=True, test_command="pnpm run test")
        d = infra.to_dict()
        assert d["framework"] == "vitest"
        assert d["test_file_count"] == 5


# ─── check_triage_gate ──────────────────────────────────────────────


class TestCheckTriageGate:
    def test_no_ambiguities_file(self, tmp_dir):
        status = check_triage_gate(tmp_dir)
        assert status.status == "no_ambiguities"

    def test_empty_ambiguities(self, tmp_dir):
        with open(os.path.join(tmp_dir, "ambiguities.json"), "w") as f:
            json.dump({"ambiguities": []}, f)

        status = check_triage_gate(tmp_dir)
        assert status.status == "no_ambiguities"

    def test_needs_triage(self, tmp_dir):
        amb = {"ambiguities": [{"id": "AMB-001", "text": "unclear requirement"}]}
        with open(os.path.join(tmp_dir, "ambiguities.json"), "w") as f:
            json.dump(amb, f)

        status = check_triage_gate(tmp_dir)
        assert status.status == "needs_triage"
        assert status.count == 1

    def test_has_untriaged(self, tmp_dir):
        amb = {"ambiguities": [
            {"id": "AMB-001", "text": "unclear"},
            {"id": "AMB-002", "text": "ambiguous"},
        ]}
        with open(os.path.join(tmp_dir, "ambiguities.json"), "w") as f:
            json.dump(amb, f)

        # Triage file exists but only covers AMB-001
        triage = "### AMB-001\nDecision: defer\nNote: later\n"
        with open(os.path.join(tmp_dir, "triage.md"), "w") as f:
            f.write(triage)

        status = check_triage_gate(tmp_dir)
        assert status.status == "has_untriaged"
        assert status.count == 1

    def test_has_fixes(self, tmp_dir):
        amb = {"ambiguities": [{"id": "AMB-001", "text": "unclear"}]}
        with open(os.path.join(tmp_dir, "ambiguities.json"), "w") as f:
            json.dump(amb, f)

        triage = "### AMB-001\nDecision: fix\nNote: update spec\n"
        with open(os.path.join(tmp_dir, "triage.md"), "w") as f:
            f.write(triage)

        status = check_triage_gate(tmp_dir)
        assert status.status == "has_fixes"
        assert status.count == 1

    def test_passed(self, tmp_dir):
        amb = {"ambiguities": [{"id": "AMB-001", "text": "unclear"}]}
        with open(os.path.join(tmp_dir, "ambiguities.json"), "w") as f:
            json.dump(amb, f)

        triage = "### AMB-001\nDecision: defer\nNote: not critical\n"
        with open(os.path.join(tmp_dir, "triage.md"), "w") as f:
            f.write(triage)

        status = check_triage_gate(tmp_dir)
        assert status.status == "passed"
        assert status.count == 1

    def test_auto_defer(self, tmp_dir):
        amb = {"ambiguities": [
            {"id": "AMB-001", "text": "unclear"},
            {"id": "AMB-002", "text": "ambiguous"},
        ]}
        with open(os.path.join(tmp_dir, "ambiguities.json"), "w") as f:
            json.dump(amb, f)

        status = check_triage_gate(tmp_dir, auto_defer=True)
        assert status.status == "passed"
        assert status.count == 2


# ─── enrich_plan_metadata ───────────────────────────────────────────


class TestEnrichPlanMetadata:
    def test_initial_plan(self, tmp_dir):
        plan_data = {"changes": [{"name": "add-auth", "scope": "test", "depends_on": []}]}

        result = enrich_plan_metadata(
            plan_data,
            hash_val="abc123",
            input_mode="brief",
            input_path="/tmp/roadmap.md",
            plan_version=1,
        )

        assert result["plan_version"] == 1
        assert result["brief_hash"] == "abc123"
        assert result["input_mode"] == "brief"
        assert result["plan_phase"] == "initial"
        assert "created_at" in result

    def test_replan_strips_depends_on(self, tmp_dir):
        plan_data = {
            "changes": [
                {"name": "feature-a", "scope": "test", "depends_on": ["feature-b", "old-done"]},
                {"name": "feature-b", "scope": "test", "depends_on": []},
            ],
        }

        state = {
            "changes": [
                {"name": "old-done", "status": "merged"},
            ],
        }
        state_path = os.path.join(tmp_dir, "state.json")
        with open(state_path, "w") as f:
            json.dump(state, f)

        result = enrich_plan_metadata(
            plan_data,
            hash_val="xyz",
            input_mode="spec",
            input_path="/tmp/spec.md",
            plan_version=2,
            replan_cycle=1,
            state_path=state_path,
        )

        assert result["plan_phase"] == "iteration"
        # old-done should be stripped (not in current plan), feature-b should remain
        feature_a = next(c for c in result["changes"] if c["name"] == "feature-a")
        assert "old-done" not in feature_a["depends_on"]
        assert "feature-b" in feature_a["depends_on"]


# ─── build_decomposition_context ────────────────────────────────────


class TestBuildDecompositionContext:
    def test_brief_mode(self, tmp_dir):
        roadmap = os.path.join(tmp_dir, "roadmap.md")
        with open(roadmap, "w") as f:
            f.write("# Roadmap\n## Next\n- Add auth\n- Fix bugs\n")

        ctx = build_decomposition_context(
            input_mode="brief",
            input_path=roadmap,
        )

        assert isinstance(ctx, dict)
        assert "input_content" in ctx
        assert "input_mode" in ctx
        assert ctx["input_mode"] == "brief"

    def test_with_optional_contexts(self, tmp_dir):
        roadmap = os.path.join(tmp_dir, "roadmap.md")
        with open(roadmap, "w") as f:
            f.write("# Roadmap\n## Next\n- Feature\n")

        ctx = build_decomposition_context(
            input_mode="brief",
            input_path=roadmap,
            existing_specs="auth-spec, user-spec",
            active_changes="fix-login",
            memory_context="Previous iteration had merge conflicts",
            test_infra_context="Test Infrastructure: vitest (config found)",
        )

        assert isinstance(ctx, dict)
        # Optional contexts should appear in the dict (key is "specs" in the context dict)
        assert ctx.get("specs") == "auth-spec, user-spec"
        assert ctx.get("active_changes") == "fix-login"
        assert ctx.get("memory") == "Previous iteration had merge conflicts"

    def test_digest_mode(self, tmp_dir):
        # Create a minimal digest directory structure
        os.makedirs(os.path.join(tmp_dir, "digest"))
        index = {
            "source_hash": "abc",
            "conventions": "Use TypeScript",
            "data_model": "REST API",
            "execution_hints": "Run tests first",
        }
        with open(os.path.join(tmp_dir, "digest", "index.json"), "w") as f:
            json.dump(index, f)

        ctx = build_decomposition_context(
            input_mode="digest",
            input_path=os.path.join(tmp_dir, "digest"),
        )

        assert isinstance(ctx, dict)
        assert ctx["input_mode"] == "digest"


# ─── estimate_tokens ────────────────────────────────────────────────


class TestEstimateTokens:
    def test_basic(self, tmp_dir):
        f = os.path.join(tmp_dir, "test.txt")
        with open(f, "w") as fh:
            fh.write("word " * 100)  # 100 words

        tokens = estimate_tokens(f)
        assert tokens == (100 * 13 + 5) // 10  # 130

    def test_missing_file(self):
        assert estimate_tokens("/nonexistent/path.txt") == 0


class TestCrossCuttingOwnership:
    """Tests for _assign_cross_cutting_ownership()."""

    def test_single_owner_assigned(self):
        """First change mentioning a file becomes owner, others get depends_on."""
        plan = {"changes": [
            {"name": "auth", "scope": "Add auth middleware.ts for route protection", "depends_on": []},
            {"name": "admin", "scope": "Add admin routes, update middleware.ts", "depends_on": []},
        ]}
        _assign_cross_cutting_ownership(plan)
        admin = next(c for c in plan["changes"] if c["name"] == "admin")
        assert "auth" in admin["depends_on"]
        assert "middleware.ts" in admin.get("cross_cutting_no_modify", [])

    def test_owner_not_restricted(self):
        """Owner should NOT get cross_cutting_no_modify."""
        plan = {"changes": [
            {"name": "auth", "scope": "Create middleware.ts", "depends_on": []},
            {"name": "admin", "scope": "Update middleware.ts for admin", "depends_on": []},
        ]}
        _assign_cross_cutting_ownership(plan)
        auth = next(c for c in plan["changes"] if c["name"] == "auth")
        assert "cross_cutting_no_modify" not in auth or "middleware.ts" not in auth.get("cross_cutting_no_modify", [])

    def test_no_overlap_no_changes(self):
        """Changes that don't share files get no ownership."""
        plan = {"changes": [
            {"name": "auth", "scope": "Add login page", "depends_on": []},
            {"name": "cart", "scope": "Add cart functionality", "depends_on": []},
        ]}
        _assign_cross_cutting_ownership(plan)
        for c in plan["changes"]:
            assert c.get("cross_cutting_no_modify", []) == []

    def test_single_change_no_assignment(self):
        plan = {"changes": [
            {"name": "auth", "scope": "Create middleware.ts", "depends_on": []},
        ]}
        _assign_cross_cutting_ownership(plan)
        assert plan["changes"][0].get("cross_cutting_no_modify", []) == []

    def test_depends_on_not_duplicated(self):
        """If depends_on already has the owner, don't add again."""
        plan = {"changes": [
            {"name": "auth", "scope": "Add layout.tsx and middleware.ts", "depends_on": []},
            {"name": "admin", "scope": "Update layout.tsx and middleware.ts", "depends_on": ["auth"]},
        ]}
        _assign_cross_cutting_ownership(plan)
        admin = next(c for c in plan["changes"] if c["name"] == "admin")
        assert admin["depends_on"].count("auth") == 1
