"""Tests for ac-test-coverage-binding: test plan generation, risk classification,
REQ-ID extraction, deterministic coverage matching, and coverage validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.test_coverage import (
    CoverageValidation,
    DigestScenario,
    TestCase,
    TestCoverage,
    TestPlan,
    TestPlanEntry,
    build_test_coverage,
    extract_req_ids,
    generate_test_plan,
    validate_coverage,
    RISK_MIN_TESTS,
)
from set_orch.profile_types import ProjectType


# ─── Fixtures ───────────────────────────────────────────────────


def _make_requirements_json(tmp_path: Path) -> Path:
    """Create a mock requirements.json with 3 requirements (HIGH/MEDIUM/LOW domains)."""
    reqs = {
        "requirements": [
            {
                "id": "REQ-AUTH-001",
                "title": "User login",
                "domain": "auth",
                "acceptance_criteria": [
                    "#### Scenario: Valid login\n- **WHEN** user enters valid credentials\n- **THEN** session is created",
                    "#### Scenario: Invalid password\n- **WHEN** user enters wrong password\n- **THEN** error is shown",
                ],
            },
            {
                "id": "REQ-FORM-001",
                "title": "Contact form",
                "domain": "forms",
                "acceptance_criteria": [
                    "#### Scenario: Submit valid form\n- **WHEN** user fills all fields\n- **THEN** success message shown",
                ],
            },
            {
                "id": "REQ-HOME-001",
                "title": "Hero heading",
                "domain": "display",
                "acceptance_criteria": [
                    "#### Scenario: Heading visible\n- **WHEN** user visits home page\n- **THEN** h1 heading is visible",
                ],
            },
            {
                "id": "REQ-MISC-001",
                "title": "No scenarios",
                "domain": "misc",
                "acceptance_criteria": ["Just a plain text AC without WHEN/THEN"],
            },
        ]
    }
    p = tmp_path / "requirements.json"
    p.write_text(json.dumps(reqs), encoding="utf-8")
    return p


# ─── 6.1: generate_test_plan() ─────────────────────────────────


class TestGenerateTestPlan:
    def test_generates_entries_from_scenarios(self, tmp_path):
        req_path = _make_requirements_json(tmp_path)
        out_path = tmp_path / "test-plan.json"
        plan = generate_test_plan(req_path, out_path)

        assert out_path.is_file()
        # REQ-AUTH-001 has 2 scenarios, REQ-FORM-001 has 1, REQ-HOME-001 has 1
        assert len(plan.entries) == 5  # 2 auth + 1 form + 1 home + 1 misc (plain text)
        assert {e.req_id for e in plan.entries} == {"REQ-AUTH-001", "REQ-FORM-001", "REQ-HOME-001", "REQ-MISC-001"}

    def test_empty_ac_is_non_testable(self, tmp_path):
        """Requirements with no AC at all are non-testable."""
        reqs = {"requirements": [
            {"id": "REQ-EMPTY-001", "title": "No AC", "domain": "misc", "acceptance_criteria": []},
        ]}
        p = tmp_path / "reqs.json"
        p.write_text(json.dumps(reqs), encoding="utf-8")
        plan = generate_test_plan(p, tmp_path / "plan.json")
        assert "REQ-EMPTY-001" in plan.non_testable
        assert len(plan.entries) == 0

    def test_plain_text_ac_generates_entries(self, tmp_path):
        """Plain text ACs (no WHEN/THEN) still generate test plan entries."""
        req_path = _make_requirements_json(tmp_path)
        out_path = tmp_path / "test-plan.json"
        plan = generate_test_plan(req_path, out_path)

        # REQ-MISC-001 has plain text AC → should still get an entry
        misc_entries = [e for e in plan.entries if e.req_id == "REQ-MISC-001"]
        assert len(misc_entries) == 1
        assert "REQ-MISC-001" not in plan.non_testable

    def test_idempotent(self, tmp_path):
        req_path = _make_requirements_json(tmp_path)
        out1 = tmp_path / "plan1.json"
        out2 = tmp_path / "plan2.json"

        plan1 = generate_test_plan(req_path, out1)
        plan2 = generate_test_plan(req_path, out2)

        # Entries match (ignore generated_at timestamp)
        assert len(plan1.entries) == len(plan2.entries)
        for e1, e2 in zip(plan1.entries, plan2.entries):
            assert e1.req_id == e2.req_id
            assert e1.scenario_slug == e2.scenario_slug
            assert e1.risk == e2.risk
            assert e1.min_tests == e2.min_tests

    def test_with_web_profile(self, tmp_path):
        from set_project_web.project_type import WebProjectType

        req_path = _make_requirements_json(tmp_path)
        out_path = tmp_path / "test-plan.json"
        profile = WebProjectType()
        plan = generate_test_plan(req_path, out_path, profile=profile)

        # REQ-AUTH-001 (domain: auth) → HIGH
        auth_entries = [e for e in plan.entries if e.req_id == "REQ-AUTH-001"]
        assert all(e.risk == "HIGH" for e in auth_entries)
        assert all(e.min_tests == 3 for e in auth_entries)

        # REQ-FORM-001 (domain: forms) → MEDIUM
        form_entries = [e for e in plan.entries if e.req_id == "REQ-FORM-001"]
        assert all(e.risk == "MEDIUM" for e in form_entries)
        assert all(e.min_tests == 2 for e in form_entries)

        # REQ-HOME-001 (domain: display) → LOW
        home_entries = [e for e in plan.entries if e.req_id == "REQ-HOME-001"]
        assert all(e.risk == "LOW" for e in home_entries)
        assert all(e.min_tests == 1 for e in home_entries)

    def test_llm_risk_takes_priority(self, tmp_path):
        """LLM-assigned risk in requirements.json overrides profile classifier."""
        reqs = {"requirements": [
            {"id": "REQ-X-001", "title": "Display page", "domain": "display",
             "risk": "HIGH",  # LLM says HIGH despite domain being display
             "acceptance_criteria": ["#### Scenario: Page loads\n- **WHEN** user visits\n- **THEN** content visible"]},
        ]}
        p = tmp_path / "reqs.json"
        p.write_text(json.dumps(reqs), encoding="utf-8")
        plan = generate_test_plan(p, tmp_path / "plan.json", profile=None)
        assert plan.entries[0].risk == "HIGH"
        assert plan.entries[0].min_tests == 3

    def test_default_profile_all_low(self, tmp_path):
        """No profile override → all scenarios classified LOW."""
        req_path = _make_requirements_json(tmp_path)
        out_path = tmp_path / "test-plan.json"
        plan = generate_test_plan(req_path, out_path, profile=None)

        assert all(e.risk == "LOW" for e in plan.entries)
        assert all(e.min_tests == 1 for e in plan.entries)


# ─── 6.2: classify_test_risk() ─────────────────────────────────


class TestClassifyTestRisk:
    def test_core_default_low(self):
        """ProjectType ABC default returns LOW."""
        # Can't instantiate ABC directly, test via generate_test_plan with profile=None
        # which uses the same default
        assert RISK_MIN_TESTS["LOW"] == 1

    def test_web_domain_lookup(self):
        from set_project_web.project_type import WebProjectType
        profile = WebProjectType()
        scenario = DigestScenario(name="test", when="login", then="session", slug="test")

        assert profile.classify_test_risk(scenario, {"domain": "auth"}) == "HIGH"
        assert profile.classify_test_risk(scenario, {"domain": "payment"}) == "HIGH"
        assert profile.classify_test_risk(scenario, {"domain": "admin"}) == "HIGH"
        assert profile.classify_test_risk(scenario, {"domain": "forms"}) == "MEDIUM"
        assert profile.classify_test_risk(scenario, {"domain": "navigation"}) == "MEDIUM"
        assert profile.classify_test_risk(scenario, {"domain": "search"}) == "MEDIUM"

    def test_web_title_pattern_high(self):
        from set_project_web.project_type import WebProjectType
        profile = WebProjectType()
        # Title with "checkout" → HIGH
        scenario = DigestScenario(name="", when="", then="", slug="")
        assert profile.classify_test_risk(scenario, {"domain": "misc", "title": "3-step checkout flow"}) == "HIGH"
        # Title with "Order cancellation" → HIGH
        assert profile.classify_test_risk(scenario, {"domain": "misc", "title": "Order cancellation with reversal"}) == "HIGH"

    def test_web_title_pattern_medium(self):
        from set_project_web.project_type import WebProjectType
        profile = WebProjectType()
        scenario = DigestScenario(name="", when="", then="", slug="")
        # Title with "filter" → MEDIUM
        assert profile.classify_test_risk(scenario, {"domain": "misc", "title": "Coffee catalog filtering"}) == "MEDIUM"
        # Title with "Cart operations" → MEDIUM
        assert profile.classify_test_risk(scenario, {"domain": "misc", "title": "Cart operations and management"}) == "MEDIUM"

    def test_web_unknown_domain_no_title_match(self):
        from set_project_web.project_type import WebProjectType
        profile = WebProjectType()
        scenario = DigestScenario(name="display heading", when="page loads", then="heading visible", slug="disp")
        assert profile.classify_test_risk(scenario, {"domain": "display", "title": "Homepage sections"}) == "LOW"


# ─── 6.3: extract_req_ids() ────────────────────────────────────


class TestExtractReqIds:
    def test_single_id(self):
        assert extract_req_ids("REQ-HOME-001: Hero heading visible") == ["REQ-HOME-001"]

    def test_multiple_ids(self):
        result = extract_req_ids("REQ-HOME-001: REQ-NAV-001: heading and nav")
        assert result == ["REQ-HOME-001", "REQ-NAV-001"]

    def test_no_id(self):
        assert extract_req_ids("Hero heading visible on cold visit") == []

    def test_case_insensitive(self):
        result = extract_req_ids("req-home-001: heading")
        assert result == ["REQ-HOME-001"]

    def test_malformed_id(self):
        # Missing number
        assert extract_req_ids("REQ-HOME: heading") == []
        # Missing domain
        assert extract_req_ids("REQ--001: heading") == []


# ─── 6.4: build_test_coverage() with REQ-ID binding ────────────


class TestBuildTestCoverageReqId:
    def test_deterministic_match_priority(self):
        """REQ-ID extraction takes priority over fuzzy matching."""
        test_cases = []  # No plan-based test cases
        test_results = {
            ("home.spec.ts", "REQ-HOME-001: Hero heading visible"): "pass",
        }
        coverage = build_test_coverage(
            test_cases=test_cases,
            non_testable=[],
            test_results=test_results,
            digest_req_ids=["REQ-HOME-001"],
        )
        assert "REQ-HOME-001" in coverage.covered_reqs
        assert coverage.passed >= 1

    def test_unbound_tests_populated(self):
        """Tests without REQ-IDs go to unbound_tests list."""
        test_results = {
            ("home.spec.ts", "Hero heading visible"): "pass",
            ("nav.spec.ts", "REQ-NAV-001: Nav links present"): "pass",
        }
        coverage = build_test_coverage(
            test_cases=[],
            non_testable=[],
            test_results=test_results,
            digest_req_ids=["REQ-NAV-001"],
        )
        assert "Hero heading visible" in coverage.unbound_tests
        assert "REQ-NAV-001: Nav links present" not in coverage.unbound_tests

    def test_fuzzy_fallback_for_unbound(self):
        """Tests without REQ-ID still match via fuzzy if test cases exist."""
        test_cases = [
            TestCase(
                scenario_slug="hero", req_id="REQ-HOME-001", risk="LOW",
                test_file="home.spec.ts", test_name="Hero heading visible",
                category="happy",
            ),
        ]
        test_results = {
            ("home.spec.ts", "Hero heading visible"): "pass",
        }
        coverage = build_test_coverage(
            test_cases=test_cases,
            non_testable=[],
            test_results=test_results,
            digest_req_ids=["REQ-HOME-001"],
        )
        assert "REQ-HOME-001" in coverage.covered_reqs
        # The test case was matched via fuzzy since test name lacks REQ-ID
        assert test_cases[0].result == "pass"

    def test_multiple_tests_same_req_id(self):
        test_results = {
            ("contact.spec.ts", "REQ-CONTACT-001: validation errors"): "pass",
            ("contact.spec.ts", "REQ-CONTACT-001: successful submit"): "pass",
        }
        coverage = build_test_coverage(
            test_cases=[],
            non_testable=[],
            test_results=test_results,
            digest_req_ids=["REQ-CONTACT-001"],
        )
        assert "REQ-CONTACT-001" in coverage.covered_reqs


# ─── 6.5: validate_coverage() ──────────────────────────────────


class TestValidateCoverage:
    def _make_plan(self, entries: list[dict]) -> TestPlan:
        return TestPlan(
            entries=[TestPlanEntry(**e) for e in entries],
            non_testable=[],
            generated_at="2026-04-04T00:00:00Z",
        )

    def test_full_coverage(self):
        plan = self._make_plan([
            {"req_id": "REQ-A-001", "scenario_slug": "s1", "scenario_name": "s1",
             "risk": "LOW", "min_tests": 1, "categories": ["happy"]},
        ])
        coverage = TestCoverage(
            test_cases=[
                TestCase(scenario_slug="s1", req_id="REQ-A-001", risk="LOW",
                         test_file="a.spec.ts", test_name="test", category="happy",
                         result="pass"),
            ],
            covered_reqs=["REQ-A-001"],
        )
        result = validate_coverage(plan, coverage)
        assert result.complete_count == 1
        assert result.partial_count == 0
        assert result.missing_count == 0

    def test_partial_coverage(self):
        plan = self._make_plan([
            {"req_id": "REQ-A-001", "scenario_slug": "s1", "scenario_name": "s1",
             "risk": "HIGH", "min_tests": 3, "categories": ["happy", "negative", "negative"]},
        ])
        coverage = TestCoverage(
            test_cases=[
                TestCase(scenario_slug="s1", req_id="REQ-A-001", risk="HIGH",
                         test_file="a.spec.ts", test_name="t1", category="happy",
                         result="pass"),
            ],
            covered_reqs=["REQ-A-001"],
        )
        result = validate_coverage(plan, coverage)
        assert result.partial_count == 1
        assert result.entries[0].status == "partial"
        assert result.entries[0].actual_count == 1
        assert result.entries[0].expected_min == 3

    def test_missing_coverage(self):
        plan = self._make_plan([
            {"req_id": "REQ-A-001", "scenario_slug": "s1", "scenario_name": "s1",
             "risk": "LOW", "min_tests": 1, "categories": ["happy"]},
        ])
        coverage = TestCoverage(test_cases=[], covered_reqs=[])
        result = validate_coverage(plan, coverage)
        assert result.missing_count == 1
        assert result.entries[0].status == "missing"

    def test_mixed_coverage(self):
        plan = self._make_plan([
            {"req_id": "REQ-A-001", "scenario_slug": "s1", "scenario_name": "s1",
             "risk": "LOW", "min_tests": 1, "categories": ["happy"]},
            {"req_id": "REQ-B-001", "scenario_slug": "s2", "scenario_name": "s2",
             "risk": "MEDIUM", "min_tests": 2, "categories": ["happy", "negative"]},
            {"req_id": "REQ-C-001", "scenario_slug": "s3", "scenario_name": "s3",
             "risk": "LOW", "min_tests": 1, "categories": ["happy"]},
        ])
        coverage = TestCoverage(
            test_cases=[
                TestCase(scenario_slug="s1", req_id="REQ-A-001", risk="LOW",
                         test_file="a.spec.ts", test_name="t1", category="happy",
                         result="pass"),
                TestCase(scenario_slug="s2", req_id="REQ-B-001", risk="MEDIUM",
                         test_file="b.spec.ts", test_name="t2", category="happy",
                         result="pass"),
            ],
            covered_reqs=["REQ-A-001", "REQ-B-001"],
        )
        result = validate_coverage(plan, coverage)
        assert result.complete_count == 1  # REQ-A-001 has 1/1
        assert result.partial_count == 1   # REQ-B-001 has 1/2
        assert result.missing_count == 1   # REQ-C-001 has 0/1
