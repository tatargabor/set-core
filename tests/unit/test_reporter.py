"""Tests for lib/set_orch/reporter.py — HTML report generator.

Tests data extraction functions and Jinja2 template rendering.
"""

import json
import os
import tempfile

import pytest

from lib.set_orch.reporter import (
    AuditData,
    AuditEntry,
    ChangeEntry,
    CoverageData,
    DigestData,
    ExecutionData,
    MilestoneData,
    PhaseHeader,
    PlanData,
    ReportData,
    _extract_audit,
    _extract_coverage,
    _extract_digest,
    _extract_execution,
    _extract_milestones,
    _extract_plan,
    _format_duration,
    _format_tokens,
    extract_report_data,
    generate_report,
)


# ─── Helper Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


def _make_state(tmp_dir, state_data):
    path = os.path.join(tmp_dir, "state.json")
    _write_json(path, state_data)
    return path


def _make_plan(tmp_dir, plan_data):
    path = os.path.join(tmp_dir, "plan.json")
    _write_json(path, plan_data)
    return path


def _make_digest(tmp_dir, index=None, requirements=None, ambiguities=None, coverage=None):
    digest_dir = os.path.join(tmp_dir, "digest")
    os.makedirs(digest_dir, exist_ok=True)
    if index:
        _write_json(os.path.join(digest_dir, "index.json"), index)
    if requirements:
        _write_json(os.path.join(digest_dir, "requirements.json"), requirements)
    if ambiguities:
        _write_json(os.path.join(digest_dir, "ambiguities.json"), ambiguities)
    if coverage:
        _write_json(os.path.join(digest_dir, "coverage.json"), coverage)
    return digest_dir


# ─── Helper Function Tests ────────────────────────────────────────────


class TestFormatTokens:
    def test_small(self):
        assert _format_tokens(0) == "0"
        assert _format_tokens(500) == "500"
        assert _format_tokens(999) == "999"

    def test_thousands(self):
        assert _format_tokens(1000) == "1K"
        assert _format_tokens(1500) == "1K"
        assert _format_tokens(45000) == "45K"
        assert _format_tokens(999999) == "999K"

    def test_millions(self):
        assert _format_tokens(1000000) == "1.0M"
        assert _format_tokens(1500000) == "1.5M"
        assert _format_tokens(12345678) == "12.3M"


class TestFormatDuration:
    def test_zero(self):
        assert _format_duration(0) == "-"
        assert _format_duration(-5) == "-"

    def test_seconds_only(self):
        assert _format_duration(45) == "0m45s"

    def test_minutes_and_seconds(self):
        assert _format_duration(65) == "1m5s"
        assert _format_duration(3723) == "62m3s"

    def test_exact_minutes(self):
        assert _format_duration(120) == "2m0s"


# ─── Digest Extraction Tests ─────────────────────────────────────────


class TestExtractDigest:
    def test_missing_dir(self):
        data = _extract_digest("/nonexistent")
        assert not data.available

    def test_missing_index(self, tmp_dir):
        digest_dir = os.path.join(tmp_dir, "digest")
        os.makedirs(digest_dir)
        data = _extract_digest(digest_dir)
        assert not data.available

    def test_basic_digest(self, tmp_dir):
        digest_dir = _make_digest(tmp_dir, index={
            "spec_base_dir": "docs/",
            "source_hash": "abc123def456",
            "file_count": 5,
            "timestamp": "2026-03-14",
        })
        data = _extract_digest(digest_dir)
        assert data.available
        assert data.spec_dir == "docs/"
        assert data.source_hash == "abc123def456"
        assert data.file_count == 5

    def test_with_requirements_and_domains(self, tmp_dir):
        digest_dir = _make_digest(tmp_dir,
            index={"spec_base_dir": ".", "source_hash": "x", "file_count": 1, "timestamp": "t"},
            requirements={"requirements": [
                {"id": "R1", "domain": "auth", "status": "active"},
                {"id": "R2", "domain": "auth", "status": "active"},
                {"id": "R3", "domain": "catalog", "status": "active"},
                {"id": "R4", "domain": "catalog", "status": "removed"},
            ]},
        )
        data = _extract_digest(digest_dir)
        assert data.req_count == 3  # R4 excluded (removed)
        assert len(data.domains) == 2
        assert data.domains[0].name == "auth"
        assert data.domains[0].count == 2
        assert data.domains[1].name == "catalog"
        assert data.domains[1].count == 1

    def test_with_ambiguities(self, tmp_dir):
        digest_dir = _make_digest(tmp_dir,
            index={"spec_base_dir": ".", "source_hash": "x", "file_count": 1, "timestamp": "t"},
            ambiguities={"ambiguities": [
                {"id": "AMB-1", "type": "unclear", "description": "test", "resolution": "fixed"},
                {"id": "AMB-2", "type": "missing", "description": "test2"},
            ]},
        )
        data = _extract_digest(digest_dir)
        assert len(data.ambiguities) == 2
        assert data.ambiguities[0].resolution == "fixed"
        assert data.ambiguities[0].row_color == "background:#2e4a2e"
        assert data.ambiguities[1].resolution == "UNRESOLVED"
        assert data.ambiguities[1].row_color == "background:#4e2a2a"


# ─── Plan Extraction Tests ───────────────────────────────────────────


class TestExtractPlan:
    def test_missing_file(self):
        data = _extract_plan("/nonexistent", "/nonexistent")
        assert not data.available

    def test_basic_plan(self, tmp_dir):
        plan_path = _make_plan(tmp_dir, {"changes": [
            {"name": "add-auth", "requirements": ["R1", "R2"], "depends_on": []},
            {"name": "add-products", "requirements": ["R3"], "depends_on": ["add-auth"]},
        ]})
        data = _extract_plan(plan_path, "/nonexistent")
        assert data.available
        assert data.total_changes == 2
        assert data.changes[0].name == "add-auth"
        assert data.changes[0].req_count == 2
        assert data.changes[0].deps == "-"
        assert data.changes[1].deps == "add-auth"

    def test_with_state_status(self, tmp_dir):
        plan_path = _make_plan(tmp_dir, {"changes": [
            {"name": "c1", "requirements": [], "depends_on": []},
        ]})
        state_path = _make_state(tmp_dir, {"changes": [
            {"name": "c1", "status": "merged"},
        ]})
        data = _extract_plan(plan_path, state_path)
        assert data.changes[0].status == "merged"


# ─── Milestone Extraction Tests ──────────────────────────────────────


class TestExtractMilestones:
    def test_no_phases(self, tmp_dir):
        state_path = _make_state(tmp_dir, {"status": "running"})
        data = _extract_milestones(state_path)
        assert not data.available

    def test_with_phases(self, tmp_dir):
        state_path = _make_state(tmp_dir, {
            "current_phase": 1,
            "phases": {
                "1": {"status": "running"},
                "2": {"status": "pending"},
            },
            "changes": [
                {"name": "c1", "phase": 1, "status": "merged", "tokens_used": 100000},
                {"name": "c2", "phase": 1, "status": "running", "tokens_used": 50000},
                {"name": "c3", "phase": 2, "status": "pending", "tokens_used": 0},
            ],
        })
        data = _extract_milestones(state_path)
        assert data.available
        assert data.current_phase == 1
        assert data.phase_count == 2
        assert len(data.phases) == 2
        assert data.phases[0].num == 1
        assert data.phases[0].total == 2
        assert data.phases[0].merged == 1
        assert data.phases[0].tokens == 150000
        assert data.phases[0].tokens_display == "150K"


# ─── Execution Extraction Tests ──────────────────────────────────────


class TestExtractExecution:
    def test_no_state(self):
        data = _extract_execution("/nonexistent")
        assert not data.available

    def test_basic_execution(self, tmp_dir):
        state_path = _make_state(tmp_dir, {
            "status": "running",
            "directives": {"e2e_mode": "per_change"},
            "changes": [
                {"name": "c1", "status": "merged", "phase": 1, "tokens_used": 150000,
                 "test_result": "pass", "e2e_result": "pass", "smoke_result": "pass",
                 "started_at": "2026-03-14T10:00:00", "completed_at": "2026-03-14T10:15:00",
                 "test_stats": {"passed": 12, "failed": 0}},
                {"name": "c2", "status": "failed", "phase": 1, "tokens_used": 80000,
                 "test_result": "fail", "e2e_result": "-", "smoke_result": "-",
                 "started_at": "2026-03-14T10:10:00", "completed_at": "2026-03-14T10:20:00"},
            ],
        })
        data = _extract_execution(state_path)
        assert data.available
        assert data.orch_status == "running"
        assert data.e2e_mode == "per_change"
        assert data.total_tokens == 230000
        assert data.total_tokens_display == "230K"
        assert data.total_tests == 12

        # Check rows (no phases = no headers)
        change_rows = [r for r in data.rows if isinstance(r, ChangeEntry)]
        assert len(change_rows) == 2
        assert change_rows[0].name == "c1"
        assert change_rows[0].tokens_display == "150K"
        assert "&#10003;" in change_rows[0].test_display

    def test_with_phase_headers(self, tmp_dir):
        state_path = _make_state(tmp_dir, {
            "status": "running",
            "directives": {},
            "phases": {"1": {"status": "running"}},
            "changes": [
                {"name": "c1", "status": "merged", "phase": 1, "tokens_used": 100},
            ],
        })
        data = _extract_execution(state_path)
        # Should have a phase header + change entry
        assert len(data.rows) == 2
        assert isinstance(data.rows[0], PhaseHeader)
        assert data.rows[0].phase == 1
        assert isinstance(data.rows[1], ChangeEntry)

    def test_skip_reason(self, tmp_dir):
        state_path = _make_state(tmp_dir, {
            "status": "done",
            "directives": {},
            "changes": [
                {"name": "c1", "status": "skipped", "phase": 1, "tokens_used": 0,
                 "skip_reason": "duplicate of c2"},
            ],
        })
        data = _extract_execution(state_path)
        row = data.rows[0]
        assert isinstance(row, ChangeEntry)
        assert "duplicate of c2" in row.status_html

    def test_phase_e2e_results(self, tmp_dir):
        state_path = _make_state(tmp_dir, {
            "status": "done",
            "directives": {},
            "changes": [],
            "phase_e2e_results": [
                {"cycle": 1, "result": "pass", "duration_ms": 5000,
                 "screenshot_count": 3, "screenshot_dir": "sc/1", "timestamp": "2026-03-14"},
                {"cycle": 2, "result": "fail", "duration_ms": 8000, "timestamp": "2026-03-14"},
            ],
        })
        data = _extract_execution(state_path)
        assert len(data.phase_e2e_results) == 2
        assert data.phase_e2e_results[0].result == "pass"
        assert data.phase_e2e_results[0].duration_s == 5
        assert data.phase_e2e_results[1].result_class == "gate-fail"


# ─── Audit Extraction Tests ──────────────────────────────────────────


class TestExtractAudit:
    def test_no_audit(self, tmp_dir):
        state_path = _make_state(tmp_dir, {"status": "done"})
        data = _extract_audit(state_path)
        assert not data.available

    def test_with_audit(self, tmp_dir):
        state_path = _make_state(tmp_dir, {
            "phase_audit_results": [
                {"cycle": 1, "audit_result": "gaps_found", "model": "opus",
                 "duration_ms": 5000, "summary": "1 gap",
                 "gaps": [{"id": "GAP-1", "severity": "critical", "description": "Missing auth"}]},
                {"cycle": 2, "audit_result": "clean", "model": "sonnet", "duration_ms": 3000},
            ],
        })
        data = _extract_audit(state_path)
        assert data.available
        assert len(data.entries) == 2
        assert data.entries[0].result == "gaps_found"
        assert data.entries[0].gap_count == 1
        assert data.entries[0].badge_class == "audit-badge-gaps"
        assert data.entries[0].gaps[0].row_class == "gap-critical"
        assert data.entries[1].result == "clean"
        assert data.entries[1].badge_class == "audit-badge-clean"
        assert data.entries[1].badge_text == "Clean"


# ─── Coverage Extraction Tests ───────────────────────────────────────


class TestExtractCoverage:
    def test_no_digest(self):
        data = _extract_coverage("", "")
        assert not data.available

    def test_missing_files(self, tmp_dir):
        data = _extract_coverage(tmp_dir, "")
        assert not data.available

    def test_basic_coverage(self, tmp_dir):
        state_path = _make_state(tmp_dir, {"changes": [
            {"name": "add-auth", "status": "merged"},
            {"name": "add-products", "status": "running"},
        ]})
        digest_dir = _make_digest(tmp_dir,
            index={"spec_base_dir": ".", "source_hash": "x", "file_count": 1, "timestamp": "t"},
            requirements={"requirements": [
                {"id": "R1", "domain": "auth"},
                {"id": "R2", "domain": "auth"},
                {"id": "R3", "domain": "catalog"},
                {"id": "R4", "domain": "catalog"},
            ]},
            coverage={"coverage": {
                "R1": {"change": "add-auth"},
                "R2": {"change": "add-auth"},
                "R3": {"change": "add-products"},
            }},
        )
        data = _extract_coverage(digest_dir, state_path)
        assert data.available
        assert data.grand_total == 4
        assert data.grand_covered == 2  # R1+R2 merged
        assert data.grand_inprogress == 1  # R3 running
        assert data.grand_uncovered == 1  # R4
        assert len(data.domains) == 2

    def test_previous_phase(self, tmp_dir):
        state_path = _make_state(tmp_dir, {"changes": []})
        digest_dir = _make_digest(tmp_dir,
            index={"spec_base_dir": ".", "source_hash": "x", "file_count": 1, "timestamp": "t"},
            requirements={"requirements": [{"id": "R1", "domain": "auth"}]},
            coverage={"coverage": {"R1": {"change": "old-change", "phase": "previous"}}},
        )
        data = _extract_coverage(digest_dir, state_path)
        assert data.grand_prev_merged == 1
        assert data.grand_covered == 1
        assert data.domains[0].requirements[0].phase == "previous"


# ─── Top-Level Extraction Test ───────────────────────────────────────


class TestExtractReportData:
    def test_all_missing(self):
        data = extract_report_data("/no", "/no", "/no")
        assert isinstance(data, ReportData)
        assert not data.digest.available
        assert not data.plan.available
        assert data.timestamp  # Should have a timestamp


# ─── Template Rendering Tests ────────────────────────────────────────


class TestGenerateReport:
    def test_empty_report(self, tmp_dir):
        out = os.path.join(tmp_dir, "report.html")
        result = generate_report("/no", "/no", "/no", out)
        assert os.path.isfile(result)
        html = open(result).read()
        assert "<!DOCTYPE html>" in html
        assert "Orchestration Report" in html
        assert "Auto-refreshes every 15s" in html
        assert "not-available" in html

    def test_full_report_structure(self, tmp_dir):
        state_path = _make_state(tmp_dir, {
            "status": "running",
            "directives": {"e2e_mode": "per_change"},
            "current_phase": 1,
            "phases": {"1": {"status": "running"}},
            "changes": [
                {"name": "add-auth", "status": "merged", "phase": 1,
                 "tokens_used": 150000, "test_result": "pass",
                 "e2e_result": "pass", "smoke_result": "pass",
                 "started_at": "2026-03-14T10:00:00",
                 "completed_at": "2026-03-14T10:15:00",
                 "test_stats": {"passed": 12, "failed": 0}},
            ],
            "phase_audit_results": [
                {"cycle": 1, "audit_result": "clean", "model": "opus", "duration_ms": 3000},
            ],
        })
        plan_path = _make_plan(tmp_dir, {"changes": [
            {"name": "add-auth", "requirements": ["R1"], "depends_on": []},
        ]})
        digest_dir = _make_digest(tmp_dir,
            index={"spec_base_dir": "docs/", "source_hash": "abc123", "file_count": 2, "timestamp": "2026-03-14"},
            requirements={"requirements": [{"id": "R1", "domain": "auth", "title": "Login"}]},
            coverage={"coverage": {"R1": {"change": "add-auth"}}},
        )

        out = os.path.join(tmp_dir, "report.html")
        generate_report(state_path, plan_path, digest_dir, out)
        html = open(out).read()

        # Verify all sections present
        assert "Spec Digest" in html
        assert "abc123" in html
        assert "Plan" in html
        assert "add-auth" in html
        assert "Milestones" in html
        assert "Phase 1" in html
        assert "Execution" in html
        assert "status-merged" in html
        assert "150K" in html
        assert "&#10003;" in html  # gate pass icon
        assert "Post-Phase Audit" in html
        assert "audit-badge-clean" in html
        assert "Requirement Coverage" in html
        assert "toggleCovPhase" in html
        assert "requirements active" in html

    def test_atomic_write(self, tmp_dir):
        """Output is written atomically (temp + rename)."""
        subdir = os.path.join(tmp_dir, "sub", "dir")
        out = os.path.join(subdir, "report.html")
        result = generate_report("/no", "/no", "/no", out)
        assert os.path.isfile(result)
        # Parent dirs were created
        assert os.path.isdir(subdir)

    def test_phase_end_mode(self, tmp_dir):
        """E2E column hidden in phase_end mode."""
        state_path = _make_state(tmp_dir, {
            "status": "done",
            "directives": {"e2e_mode": "phase_end"},
            "changes": [
                {"name": "c1", "status": "merged", "phase": 1, "tokens_used": 100,
                 "test_result": "pass", "smoke_result": "pass"},
            ],
        })
        out = os.path.join(tmp_dir, "report.html")
        generate_report(state_path, "/no", "/no", out)
        html = open(out).read()
        # In phase_end mode, header should NOT have E2E column
        # Count th elements in execution table
        assert "<th>E2E</th>" not in html
