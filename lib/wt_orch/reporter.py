"""HTML report generator for orchestration dashboard.

Migrated from: lib/orchestration/reporter.sh (748 LOC, 9 functions)

Extracts report data from state/digest/plan JSON files into typed dataclasses,
then renders via Jinja2 template to produce the orchestration HTML dashboard.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

# Template directory relative to this module
_TEMPLATE_DIR = Path(__file__).parent / "templates"


# ─── Helpers ──────────────────────────────────────────────────────────


def _format_tokens(n: int) -> str:
    """Format token count for display.

    Migrated from: reporter.sh token formatting (repeated in 4 places)
    """
    if n > 999_999:
        return f"{n / 1_000_000:.1f}M"
    if n > 999:
        return f"{n // 1000}K"
    return str(n)


def _format_duration(seconds: int) -> str:
    """Format seconds as 'Xm Ys'.

    Migrated from: reporter.sh duration calculation L348-363
    """
    if seconds <= 0:
        return "-"
    m, s = divmod(seconds, 60)
    return f"{m}m{s}s"


def _status_class(status: str) -> str:
    """Map status string to CSS class name.

    Migrated from: reporter.sh status-* CSS classes L51-57
    """
    return f"status-{status}"


def _gate_class(result: str) -> str:
    """Map gate result to CSS class."""
    if result == "pass":
        return "gate-pass"
    if result == "fail":
        return "gate-fail"
    return "gate-na"


def _gate_display(result: str, variant: str = "default") -> str:
    """Map gate result to display HTML."""
    if result == "pass" or (variant == "smoke" and result == "fixed"):
        return "&#10003;"
    if result == "fail":
        return "&#10007;"
    if result in ("skipped", "skip"):
        return "skip"
    if result == "skip_merged":
        return '<span title="Skipped — already merged from previous phase">-</span>'
    return "-"


def _read_json(path: str | Path) -> dict[str, Any]:
    """Read JSON file, return empty dict on any error."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _read_json_list(path: str | Path) -> list[Any]:
    """Read JSON file as list, return empty list on error."""
    try:
        with open(path) as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError, TypeError):
        return []


# ─── Data Model ───────────────────────────────────────────────────────


@dataclass
class AmbiguityEntry:
    """Single ambiguity from digest."""
    id: str = ""
    type: str = ""
    description: str = ""
    resolution: str = "UNRESOLVED"
    resolution_note: str = ""
    resolved_by: str = ""

    @property
    def row_color(self) -> str:
        if self.resolution == "fixed":
            return "background:#2e4a2e"
        if self.resolution in ("deferred", "planner-resolved"):
            return "background:#2a3a4e"
        if self.resolution == "ignored":
            return "background:#3a3a3a"
        return "background:#4e2a2a"


@dataclass
class DomainInfo:
    """Domain entry from digest."""
    name: str = ""
    count: int = 0


@dataclass
class DigestData:
    """Digest section data.

    Migrated from: reporter.sh render_digest_section() L96-155
    """
    available: bool = False
    spec_dir: str = "unknown"
    source_hash: str = "unknown"
    file_count: int = 0
    timestamp: str = "unknown"
    req_count: int = 0
    domains: list[DomainInfo] = field(default_factory=list)
    ambiguities: list[AmbiguityEntry] = field(default_factory=list)


@dataclass
class PlanChange:
    """Single change in plan table."""
    name: str = ""
    req_count: int = 0
    deps: str = "-"
    status: str = "planned"


@dataclass
class PlanData:
    """Plan section data.

    Migrated from: reporter.sh render_plan_section() L159-187
    """
    available: bool = False
    total_changes: int = 0
    changes: list[PlanChange] = field(default_factory=list)


@dataclass
class PhaseEntry:
    """Single phase in milestone table."""
    num: int = 1
    status: str = "pending"
    total: int = 0
    merged: int = 0
    tokens: int = 0
    tokens_display: str = "0"
    server_port: str = ""
    server_pid: str = ""
    server_alive: bool = False
    completed_at: str = ""


@dataclass
class MilestoneData:
    """Milestone section data.

    Migrated from: reporter.sh render_milestone_section() L191-252
    """
    available: bool = False
    current_phase: int = 1
    phase_count: int = 0
    phases: list[PhaseEntry] = field(default_factory=list)


@dataclass
class ChangeEntry:
    """Single change in execution table."""
    name: str = ""
    status: str = "planned"
    status_html: str = ""
    tokens: int = 0
    tokens_display: str = "0"
    duration_s: int = 0
    duration_display: str = "-"
    test_result: str = "-"
    test_class: str = "gate-na"
    test_display: str = "-"
    e2e_result: str = "-"
    e2e_class: str = "gate-na"
    e2e_display: str = "-"
    smoke_result: str = "-"
    smoke_class: str = "gate-na"
    smoke_display: str = "-"
    phase: int = 1
    skip_reason: str = ""
    # Screenshot info
    smoke_sc_count: int = 0
    smoke_sc_dir: str = ""
    e2e_sc_count: int = 0
    e2e_sc_dir: str = ""


@dataclass
class PhaseHeader:
    """Phase header row in execution table."""
    phase: int = 1
    merged: int = 0
    total: int = 0
    tokens_display: str = "0"


@dataclass
class PhaseE2EResult:
    """Phase-end E2E result entry."""
    cycle: str = ""
    result: str = ""
    duration_s: int = 0
    sc_count: int = 0
    sc_dir: str = ""
    timestamp: str = ""
    result_class: str = "gate-pass"


@dataclass
class ScreenshotGroup:
    """Screenshot gallery group."""
    name: str = ""
    dir: str = ""
    count: int = 0


@dataclass
class ExecutionData:
    """Execution section data.

    Migrated from: reporter.sh render_execution_section() L256-548
    """
    available: bool = False
    orch_status: str = "unknown"
    e2e_mode: str = "per_change"
    # Rows: list of (PhaseHeader | ChangeEntry) in display order
    rows: list[PhaseHeader | ChangeEntry] = field(default_factory=list)
    total_tokens: int = 0
    total_tokens_display: str = "0"
    total_duration_s: int = 0
    total_duration_display: str = "0m"
    total_tests: int = 0
    phase_e2e_results: list[PhaseE2EResult] = field(default_factory=list)
    smoke_screenshots: list[ScreenshotGroup] = field(default_factory=list)
    e2e_screenshots: list[ScreenshotGroup] = field(default_factory=list)
    latest_e2e_sc_dir: str = ""


@dataclass
class AuditGap:
    """Single gap in audit results."""
    id: str = ""
    severity: str = "minor"
    description: str = ""
    spec_reference: str = ""
    suggested_scope: str = ""

    @property
    def row_class(self) -> str:
        return "gap-critical" if self.severity == "critical" else "gap-minor"


@dataclass
class AuditEntry:
    """Single audit cycle result."""
    cycle: str = "?"
    result: str = "unknown"
    model: str = "?"
    duration_s: int = 0
    gap_count: int = 0
    summary: str = ""
    gaps: list[AuditGap] = field(default_factory=list)

    @property
    def badge_class(self) -> str:
        if self.result == "gaps_found":
            return "audit-badge-gaps"
        if self.result == "parse_error":
            return "audit-badge-error"
        return "audit-badge-clean"

    @property
    def badge_text(self) -> str:
        if self.result == "gaps_found":
            return f"{self.gap_count} gaps"
        if self.result == "parse_error":
            return "Parse Error"
        return "Clean"


@dataclass
class AuditData:
    """Audit section data.

    Migrated from: reporter.sh render_audit_section() L552-624
    """
    available: bool = False
    entries: list[AuditEntry] = field(default_factory=list)


@dataclass
class CoverageReq:
    """Single requirement in coverage table."""
    req_id: str = ""
    title: str = ""
    change: str = ""
    status: str = "uncovered"
    phase: str = ""


@dataclass
class CoverageDomain:
    """Per-domain coverage data."""
    name: str = ""
    total: int = 0
    merged: int = 0
    inprogress: int = 0
    prev_merged: int = 0
    requirements: list[CoverageReq] = field(default_factory=list)

    @property
    def active(self) -> int:
        return self.merged + self.inprogress

    @property
    def merged_pct(self) -> int:
        return (self.merged * 100 // self.total) if self.total > 0 else 0

    @property
    def inprog_pct(self) -> int:
        return (self.inprogress * 100 // self.total) if self.total > 0 else 0

    @property
    def active_pct(self) -> int:
        return self.merged_pct + self.inprog_pct


@dataclass
class CoverageData:
    """Coverage section data.

    Migrated from: reporter.sh render_coverage_section() L628-748
    """
    available: bool = False
    grand_total: int = 0
    grand_covered: int = 0
    grand_inprogress: int = 0
    grand_prev_merged: int = 0
    domains: list[CoverageDomain] = field(default_factory=list)

    @property
    def grand_active(self) -> int:
        return self.grand_covered + self.grand_inprogress

    @property
    def grand_merged_pct(self) -> int:
        return (self.grand_covered * 100 // self.grand_total) if self.grand_total > 0 else 0

    @property
    def grand_inprog_pct(self) -> int:
        return (self.grand_inprogress * 100 // self.grand_total) if self.grand_total > 0 else 0

    @property
    def grand_active_pct(self) -> int:
        return self.grand_merged_pct + self.grand_inprog_pct

    @property
    def grand_uncovered(self) -> int:
        return self.grand_total - self.grand_active


@dataclass
class ReportData:
    """Top-level report data container."""
    digest: DigestData = field(default_factory=DigestData)
    plan: PlanData = field(default_factory=PlanData)
    milestones: MilestoneData = field(default_factory=MilestoneData)
    execution: ExecutionData = field(default_factory=ExecutionData)
    audit: AuditData = field(default_factory=AuditData)
    coverage: CoverageData = field(default_factory=CoverageData)
    timestamp: str = ""


# ─── Data Extraction ──────────────────────────────────────────────────


def _extract_digest(digest_dir: str) -> DigestData:
    """Extract digest section data.

    Migrated from: reporter.sh render_digest_section() L96-155
    """
    if not digest_dir or not os.path.isdir(digest_dir):
        return DigestData()

    index_path = os.path.join(digest_dir, "index.json")
    if not os.path.isfile(index_path):
        return DigestData()

    index = _read_json(index_path)
    data = DigestData(
        available=True,
        spec_dir=index.get("spec_base_dir", "unknown"),
        source_hash=index.get("source_hash", "unknown"),
        file_count=index.get("file_count", 0),
        timestamp=index.get("timestamp", "unknown"),
    )

    # Requirements count
    req_path = os.path.join(digest_dir, "requirements.json")
    req_data = _read_json(req_path)
    reqs = req_data.get("requirements", [])
    active_reqs = [r for r in reqs if r.get("status") != "removed"]
    data.req_count = len(active_reqs)

    # Domains
    domain_set: dict[str, int] = {}
    for r in active_reqs:
        d = r.get("domain", "unknown")
        domain_set[d] = domain_set.get(d, 0) + 1
    data.domains = [DomainInfo(name=k, count=v) for k, v in sorted(domain_set.items())]

    # Ambiguities
    amb_path = os.path.join(digest_dir, "ambiguities.json")
    amb_data = _read_json(amb_path)
    for a in amb_data.get("ambiguities", []):
        data.ambiguities.append(AmbiguityEntry(
            id=a.get("id", "-"),
            type=a.get("type", "-"),
            description=a.get("description", "-"),
            resolution=a.get("resolution", "UNRESOLVED"),
            resolution_note=a.get("resolution_note", ""),
            resolved_by=a.get("resolved_by", "-"),
        ))

    return data


def _extract_plan(plan_path: str, state_path: str) -> PlanData:
    """Extract plan section data.

    Migrated from: reporter.sh render_plan_section() L159-187
    """
    if not plan_path or not os.path.isfile(plan_path):
        return PlanData()

    plan = _read_json(plan_path)
    changes_raw = plan.get("changes", [])
    state = _read_json(state_path) if state_path and os.path.isfile(state_path) else {}

    # Build status lookup from state
    status_map: dict[str, str] = {}
    for c in state.get("changes", []):
        status_map[c.get("name", "")] = c.get("status", "planned")

    data = PlanData(available=True, total_changes=len(changes_raw))
    for c in changes_raw:
        name = c.get("name", "")
        deps_list = c.get("depends_on", [])
        deps_str = ", ".join(deps_list) if deps_list else "-"
        data.changes.append(PlanChange(
            name=name,
            req_count=len(c.get("requirements", [])),
            deps=deps_str,
            status=status_map.get(name, "planned"),
        ))

    return data


def _extract_milestones(state_path: str) -> MilestoneData:
    """Extract milestone section data.

    Migrated from: reporter.sh render_milestone_section() L191-252
    """
    state = _read_json(state_path) if state_path and os.path.isfile(state_path) else {}
    if "phases" not in state or not state["phases"]:
        return MilestoneData()

    phases_raw = state["phases"]
    changes = state.get("changes", [])
    current = state.get("current_phase", 1)

    data = MilestoneData(
        available=True,
        current_phase=current,
        phase_count=len(phases_raw),
    )

    for pnum_str in sorted(phases_raw.keys(), key=lambda x: int(x)):
        pnum = int(pnum_str)
        pval = phases_raw[pnum_str]

        total = sum(1 for c in changes if c.get("phase") == pnum)
        merged = sum(1 for c in changes if c.get("phase") == pnum and c.get("status") in ("merged", "done"))
        tokens = sum(c.get("tokens_used", 0) for c in changes if c.get("phase") == pnum)

        server_pid = str(pval.get("server_pid", ""))
        server_port = str(pval.get("server_port", ""))
        # Check if server PID is alive
        server_alive = False
        if server_pid and server_pid != "null":
            try:
                os.kill(int(server_pid), 0)
                server_alive = True
            except (OSError, ValueError):
                pass

        completed_at = pval.get("completed_at", "")
        if completed_at and completed_at != "null":
            # Format: remove T, strip timezone
            completed_at = completed_at.replace("T", " ").split("+")[0]
        else:
            completed_at = ""

        data.phases.append(PhaseEntry(
            num=pnum,
            status=pval.get("status", "pending"),
            total=total,
            merged=merged,
            tokens=tokens,
            tokens_display=_format_tokens(tokens),
            server_port=server_port,
            server_pid=server_pid,
            server_alive=server_alive,
            completed_at=completed_at,
        ))

    return data


def _compute_duration(started_at: str, completed_at: str) -> int:
    """Compute duration in seconds between two ISO timestamps."""
    if not started_at or started_at == "null":
        return 0
    try:
        # Parse ISO format
        start_str = started_at.replace("T", " ").split("+")[0].split(".")[0]
        start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        if completed_at and completed_at != "null":
            end_str = completed_at.replace("T", " ").split("+")[0].split(".")[0]
            end = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        else:
            end = datetime.now()
        return max(0, int((end - start).total_seconds()))
    except (ValueError, TypeError):
        return 0


def _extract_execution(state_path: str) -> ExecutionData:
    """Extract execution section data.

    Migrated from: reporter.sh render_execution_section() L256-548
    """
    state = _read_json(state_path) if state_path and os.path.isfile(state_path) else {}
    if not state:
        return ExecutionData()

    orch_status = state.get("status", "unknown")
    e2e_mode = state.get("directives", {}).get("e2e_mode", "per_change")
    has_phases = "phases" in state
    changes = state.get("changes", [])
    # Sort by phase
    changes_sorted = sorted(changes, key=lambda c: c.get("phase", 1))

    rows: list[PhaseHeader | ChangeEntry] = []
    total_tokens = 0
    total_duration_s = 0
    total_tests = 0
    last_phase = None
    smoke_screenshots: list[ScreenshotGroup] = []
    e2e_screenshots: list[ScreenshotGroup] = []

    for c in changes_sorted:
        change_phase = c.get("phase", 1)

        # Phase header
        if has_phases and change_phase != last_phase:
            last_phase = change_phase
            ph_changes = [x for x in changes if x.get("phase") == change_phase]
            ph_merged = sum(1 for x in ph_changes if x.get("status") in ("merged", "done"))
            ph_total = len(ph_changes)
            ph_tokens = sum(x.get("tokens_used", 0) for x in ph_changes)
            rows.append(PhaseHeader(
                phase=change_phase,
                merged=ph_merged,
                total=ph_total,
                tokens_display=_format_tokens(ph_tokens),
            ))

        name = c.get("name", "")
        status = c.get("status", "planned")
        tokens = c.get("tokens_used", 0)
        total_tokens += tokens

        dur_s = _compute_duration(c.get("started_at", ""), c.get("completed_at", ""))
        total_duration_s += dur_s

        # Test result + stats
        test_result = c.get("test_result", "-")
        test_display = _gate_display(test_result)
        test_stats = c.get("test_stats") or {}
        if test_stats and test_stats != {}:
            t_pass = test_stats.get("passed", 0)
            t_fail = test_stats.get("failed", 0)
            t_total = t_pass + t_fail
            if t_total > 0:
                test_display += f" <small>{t_pass}/{t_total}</small>"
                total_tests += t_total

        # E2E result
        e2e_result = c.get("e2e_result", "-")

        # Smoke result
        smoke_result = c.get("smoke_result", "-")

        # Screenshot info
        smoke_sc_count = c.get("smoke_screenshot_count", 0) or 0
        smoke_sc_dir = c.get("smoke_screenshot_dir", "") or ""
        e2e_sc_count = c.get("e2e_screenshot_count", 0) or 0
        e2e_sc_dir = c.get("e2e_screenshot_dir", "") or ""

        # Build smoke display with screenshot link
        smoke_display = _gate_display(smoke_result, "smoke")
        if smoke_sc_count > 0 and smoke_sc_dir and smoke_sc_dir != "null":
            smoke_display += f' <a href="../../{smoke_sc_dir}" title="{smoke_sc_count} screenshots" style="text-decoration:none">&#128247;</a>'

        # Build e2e display with screenshot link
        e2e_display = _gate_display(e2e_result)
        if e2e_sc_count > 0 and e2e_sc_dir and e2e_sc_dir != "null":
            e2e_display += f' <a href="../../{e2e_sc_dir}" title="{e2e_sc_count} screenshots" style="text-decoration:none">&#128247;</a>'

        # Status HTML with skip reason
        status_html = f'<span class="status-{status}">{status}</span>'
        skip_reason = c.get("skip_reason", "") or ""
        if status == "skipped" and skip_reason:
            status_html = f'<span class="status-{status}" title="{skip_reason}">{status}</span> <small>({skip_reason})</small>'

        rows.append(ChangeEntry(
            name=name,
            status=status,
            status_html=status_html,
            tokens=tokens,
            tokens_display=_format_tokens(tokens),
            duration_s=dur_s,
            duration_display=_format_duration(dur_s),
            test_result=test_result,
            test_class=_gate_class(test_result),
            test_display=test_display,
            e2e_result=e2e_result,
            e2e_class=_gate_class(e2e_result),
            e2e_display=e2e_display,
            smoke_result=smoke_result,
            smoke_class=_gate_class(smoke_result),
            smoke_display=smoke_display,
            phase=change_phase,
            skip_reason=skip_reason,
            smoke_sc_count=smoke_sc_count,
            smoke_sc_dir=smoke_sc_dir,
            e2e_sc_count=e2e_sc_count,
            e2e_sc_dir=e2e_sc_dir,
        ))

        # Collect screenshot groups
        if smoke_sc_count > 0:
            smoke_screenshots.append(ScreenshotGroup(name=name, dir=smoke_sc_dir, count=smoke_sc_count))
        if e2e_sc_count > 0:
            e2e_screenshots.append(ScreenshotGroup(name=name, dir=e2e_sc_dir, count=e2e_sc_count))

    # Phase-end E2E results
    phase_e2e_results: list[PhaseE2EResult] = []
    for pe in state.get("phase_e2e_results", []):
        dur_ms = pe.get("duration_ms", 0)
        result = pe.get("result", "")
        phase_e2e_results.append(PhaseE2EResult(
            cycle=str(pe.get("cycle", "")),
            result=result,
            duration_s=dur_ms // 1000,
            sc_count=pe.get("screenshot_count", 0) or 0,
            sc_dir=pe.get("screenshot_dir", "") or "",
            timestamp=pe.get("timestamp", "-"),
            result_class="gate-fail" if result == "fail" else "gate-pass",
        ))

    # Latest E2E screenshot dir
    latest_e2e_sc_dir = ""
    if phase_e2e_results:
        latest_e2e_sc_dir = phase_e2e_results[-1].sc_dir

    return ExecutionData(
        available=True,
        orch_status=orch_status,
        e2e_mode=e2e_mode,
        rows=rows,
        total_tokens=total_tokens,
        total_tokens_display=_format_tokens(total_tokens),
        total_duration_s=total_duration_s,
        total_duration_display=_format_duration(total_duration_s),
        total_tests=total_tests,
        phase_e2e_results=phase_e2e_results,
        smoke_screenshots=smoke_screenshots,
        e2e_screenshots=e2e_screenshots,
        latest_e2e_sc_dir=latest_e2e_sc_dir,
    )


def _extract_audit(state_path: str) -> AuditData:
    """Extract audit section data.

    Migrated from: reporter.sh render_audit_section() L552-624
    """
    state = _read_json(state_path) if state_path and os.path.isfile(state_path) else {}
    audit_results = state.get("phase_audit_results", [])
    if not audit_results:
        return AuditData()

    entries: list[AuditEntry] = []
    for entry_raw in audit_results:
        gaps: list[AuditGap] = []
        for g in entry_raw.get("gaps", []):
            gaps.append(AuditGap(
                id=g.get("id", ""),
                severity=g.get("severity", "minor"),
                description=g.get("description", ""),
                spec_reference=g.get("spec_reference", ""),
                suggested_scope=g.get("suggested_scope", ""),
            ))
        dur_ms = entry_raw.get("duration_ms", 0)
        entries.append(AuditEntry(
            cycle=str(entry_raw.get("cycle", "?")),
            result=entry_raw.get("audit_result", "unknown"),
            model=entry_raw.get("model", "?"),
            duration_s=dur_ms // 1000,
            gap_count=len(gaps),
            summary=entry_raw.get("summary", ""),
            gaps=gaps,
        ))

    return AuditData(available=True, entries=entries)


def _extract_coverage(digest_dir: str, state_path: str) -> CoverageData:
    """Extract coverage section data.

    Migrated from: reporter.sh render_coverage_section() L628-748
    """
    if not digest_dir:
        return CoverageData()

    req_path = os.path.join(digest_dir, "requirements.json")
    cov_path = os.path.join(digest_dir, "coverage.json")
    if not os.path.isfile(req_path) or not os.path.isfile(cov_path):
        return CoverageData()

    req_data = _read_json(req_path)
    cov_data = _read_json(cov_path)
    state = _read_json(state_path) if state_path and os.path.isfile(state_path) else {}
    coverage_map = cov_data.get("coverage", {})

    # Build status lookup from state
    status_map: dict[str, str] = {}
    for c in state.get("changes", []):
        status_map[c.get("name", "")] = c.get("status", "planned")

    reqs = req_data.get("requirements", [])
    active_reqs = [r for r in reqs if r.get("status") != "removed"]

    # Group by domain
    domain_map: dict[str, list] = {}
    for r in active_reqs:
        d = r.get("domain", "unknown")
        if d not in domain_map:
            domain_map[d] = []
        domain_map[d].append(r)

    grand_total = 0
    grand_covered = 0
    grand_inprogress = 0
    grand_prev_merged = 0
    domains: list[CoverageDomain] = []

    for domain_name in sorted(domain_map.keys()):
        domain_reqs = domain_map[domain_name]
        cd = CoverageDomain(name=domain_name)

        for r in domain_reqs:
            req_id = r.get("id", "")
            title = r.get("title", "-")
            cd.total += 1
            grand_total += 1

            cov_entry = coverage_map.get(req_id, {})
            cov_change = cov_entry.get("change", "")
            cov_phase = cov_entry.get("phase", "")

            if not cov_change:
                effective_status = "uncovered"
            elif cov_phase == "previous":
                effective_status = "merged"
                cd.merged += 1
                cd.prev_merged += 1
                grand_covered += 1
                grand_prev_merged += 1
            else:
                state_status = status_map.get(cov_change, "planned")
                if state_status in ("merged", "done"):
                    effective_status = "merged"
                    cd.merged += 1
                    grand_covered += 1
                elif state_status in ("running", "verifying"):
                    effective_status = "running"
                    cd.inprogress += 1
                    grand_inprogress += 1
                elif state_status == "failed":
                    effective_status = "failed"
                elif state_status == "merge-blocked":
                    effective_status = "blocked"
                else:
                    effective_status = "planned"

            cd.requirements.append(CoverageReq(
                req_id=req_id,
                title=title,
                change=cov_change,
                status=effective_status,
                phase=cov_phase,
            ))

        domains.append(cd)

    return CoverageData(
        available=True,
        grand_total=grand_total,
        grand_covered=grand_covered,
        grand_inprogress=grand_inprogress,
        grand_prev_merged=grand_prev_merged,
        domains=domains,
    )


def extract_report_data(
    state_path: str,
    plan_path: str,
    digest_dir: str,
) -> ReportData:
    """Extract all report data from source files.

    Migrated from: reporter.sh generate_report() L10-28

    Args:
        state_path: Path to orchestration-state.json
        plan_path: Path to orchestration-plan.json
        digest_dir: Path to digest directory
    """
    return ReportData(
        digest=_extract_digest(digest_dir),
        plan=_extract_plan(plan_path, state_path),
        milestones=_extract_milestones(state_path),
        execution=_extract_execution(state_path),
        audit=_extract_audit(state_path),
        coverage=_extract_coverage(digest_dir, state_path),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


# ─── Report Generation ───────────────────────────────────────────────


def generate_report(
    state_path: str,
    plan_path: str,
    digest_dir: str,
    output_path: str = "",
) -> str:
    """Generate HTML report from orchestration data.

    Migrated from: reporter.sh generate_report() L10-28

    Extracts data from JSON files, renders Jinja2 template, writes atomically.

    Args:
        state_path: Path to orchestration-state.json
        plan_path: Path to orchestration-plan.json
        digest_dir: Path to digest directory
        output_path: Output HTML file path

    Returns:
        The output file path.
    """
    if not output_path:
        try:
            from .paths import WtRuntime
            output_path = WtRuntime().report_html
        except Exception:
            output_path = "wt/orchestration/report.html"

    data = extract_report_data(state_path, plan_path, digest_dir)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=False,  # We control HTML output directly
    )
    env.tests["instance_of_phase_header"] = lambda obj: isinstance(obj, PhaseHeader)
    template = env.get_template("report.html.j2")
    html = template.render(data=data)

    # Atomic write: tempfile + rename
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(out_path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(html)
        os.rename(tmp_path, str(out_path))
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    logger.info("Report generated: %s", output_path)
    return str(out_path)
