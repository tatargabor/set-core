"""Orchestration planner: validation, decomposition context, scope overlap.

Migrated from: lib/orchestration/planner.sh (estimate_tokens, summarize_spec,
detect_test_infra, auto_detect_test_command, validate_plan, check_scope_overlap,
find_project_knowledge_file, check_triage_gate, build_decomposition_context,
enrich_plan_metadata, collect_replan_context)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ─── Data Types ──────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """Result of plan JSON validation."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict:
        return {"errors": self.errors, "warnings": self.warnings}


@dataclass
class ScopeOverlap:
    """Detected scope overlap between two changes."""

    name_a: str
    name_b: str
    similarity: int  # percentage 0-100

    def to_dict(self) -> dict:
        return {"name_a": self.name_a, "name_b": self.name_b, "similarity": self.similarity}


@dataclass
class TestInfra:
    """Detected test infrastructure in a project."""

    framework: str = ""
    config_exists: bool = False
    test_file_count: int = 0
    has_helpers: bool = False
    test_command: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TriageStatus:
    """Result of triage gate evaluation."""

    status: str  # no_ambiguities | needs_triage | has_untriaged | has_fixes | passed
    count: int = 0

    def to_dict(self) -> dict:
        return {"status": self.status, "count": self.count}


# ─── Token Estimation ────────────────────────────────────────────────
# Migrated from: planner.sh estimate_tokens() L9-14


def estimate_tokens(file_path: str) -> int:
    """Estimate token count from word count (rough: words * 1.3).

    Migrated from: planner.sh estimate_tokens() L9-14
    """
    try:
        text = Path(file_path).read_text(errors="replace")
        words = len(text.split())
        return (words * 13 + 5) // 10
    except OSError:
        return 0


# ─── Spec Summarization ──────────────────────────────────────────────
# Migrated from: planner.sh summarize_spec() L17-56


def summarize_spec(
    spec_path: str,
    phase_hint: str = "",
    model: str = "haiku",
) -> str:
    """Summarize a large spec document for decomposition.

    Migrated from: planner.sh summarize_spec() L17-56

    Args:
        spec_path: Path to the spec file.
        phase_hint: Optional phase to focus on.
        model: Model to use for summarization.

    Returns:
        Summary text, or truncated content on failure.
    """
    from .subprocess_utils import run_claude_logged

    spec_content = Path(spec_path).read_text(errors="replace")

    phase_instruction = ""
    if phase_hint:
        phase_instruction = (
            f"The user wants to focus on phase: {phase_hint}. "
            "Extract that phase in full detail."
        )

    summary_prompt = (
        "You are a technical analyst. This specification document is too large "
        "to process in full.\n"
        "Create a structured summary for a software architect who needs to "
        "decompose it into implementable changes.\n\n"
        "## Specification Document\n"
        f"{spec_content}\n\n"
        "## Task\n"
        "Create a condensed summary containing:\n"
        "1. **Table of Contents** with completion status for each section/phase "
        '(use markers from the document: checkboxes, emoji, "done"/"implemented"/"kész" etc.)\n'
        "2. **Next Actionable Phase** — extract the FULL content of the first "
        "incomplete phase/priority section\n"
        f"{phase_instruction}\n\n"
        "Output ONLY the summary in markdown. Keep it under 3000 words.\n"
        "Do NOT add commentary — just the structured summary."
    )

    try:
        result = run_claude_logged(summary_prompt, purpose="decompose_summary", model=model)
        if result.exit_code == 0 and result.stdout:
            logger.info("Spec summarization complete (%d chars)", len(result.stdout))
            return result.stdout
    except Exception as e:
        logger.error("Spec summarization failed: %s", e)

    # Fallback: truncate
    logger.warning("Spec summarization failed — falling back to truncation")
    return spec_content[:32000]


# ─── Test Infrastructure Detection ────────────────────────────────────
# Migrated from: planner.sh detect_test_infra() L60-129, auto_detect_test_command() L131-160


def _auto_detect_test_command(project_dir: str) -> str:
    """Detect test command — profile first, legacy fallback."""
    from .profile_loader import load_profile

    profile = load_profile(project_dir)
    cmd = profile.detect_test_command(project_dir)
    if cmd:
        return cmd

    # TODO(profile-cleanup): remove after profile adoption confirmed
    # Legacy fallback — delegates PM detection to canonical function
    from .config import detect_package_manager

    pkg_path = Path(project_dir) / "package.json"
    if not pkg_path.exists():
        return ""

    try:
        pkg = json.loads(pkg_path.read_text())
    except (json.JSONDecodeError, OSError):
        return ""

    pkg_mgr = detect_package_manager(project_dir)
    scripts = pkg.get("scripts", {})
    for candidate in ("test", "test:unit", "test:ci"):
        if scripts.get(candidate):
            return f"{pkg_mgr} run {candidate}"

    return ""


def detect_test_infra(project_dir: str = ".") -> TestInfra:
    """Scan project directory for test infrastructure.

    Migrated from: planner.sh detect_test_infra() L60-129
    """
    p = Path(project_dir)
    framework = ""
    config_exists = False

    # Check for test framework configs
    if list(p.glob("vitest.config.*")):
        framework = "vitest"
        config_exists = True
    elif list(p.glob("jest.config.*")):
        framework = "jest"
        config_exists = True
    else:
        pyproject = p / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                if "[tool.pytest" in content:
                    framework = "pytest"
                    config_exists = True
            except OSError:
                pass
        if not framework and (p / "pytest.ini").exists():
            framework = "pytest"
            config_exists = True

    # Check package.json for test framework in devDependencies
    if not framework:
        pkg_path = p / "package.json"
        if pkg_path.exists():
            try:
                pkg = json.loads(pkg_path.read_text())
                dev_deps = pkg.get("devDependencies", {})
                for fw in ("vitest", "jest", "mocha"):
                    if fw in dev_deps:
                        framework = fw
                        break
            except (json.JSONDecodeError, OSError):
                pass

    # Count test files (excluding node_modules, .git)
    test_file_count = 0
    exclude_dirs = {"node_modules", ".git", "__pycache__", ".venv", "venv"}
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in files:
            if (
                ".test." in f
                or ".spec." in f
                or (f.startswith("test_") and f.endswith(".py"))
            ):
                test_file_count += 1

    # Check for test helper directories
    has_helpers = False
    for d in ("src/test", "__tests__", "test", "tests", "src/__tests__"):
        if (p / d).is_dir():
            has_helpers = True
            break

    if not has_helpers:
        # Check for helper files
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for f in files:
                if "test-helper" in f or "factory" in f or "fixtures" in f:
                    has_helpers = True
                    break
            if has_helpers:
                break

    test_command = _auto_detect_test_command(project_dir)

    return TestInfra(
        framework=framework,
        config_exists=config_exists,
        test_file_count=test_file_count,
        has_helpers=has_helpers,
        test_command=test_command,
    )


# ─── Plan Validation ─────────────────────────────────────────────────
# Migrated from: planner.sh validate_plan() L164-250


_KEBAB_CASE_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def validate_plan(
    plan_path: str,
    digest_dir: str | None = None,
    max_change_target: int | None = None,
) -> ValidationResult:
    """Validate plan JSON structure, fields, dependencies, and coverage.

    Migrated from: planner.sh validate_plan() L164-250

    Args:
        plan_path: Path to the plan JSON file.
        digest_dir: Optional digest directory for requirement coverage validation.
        max_change_target: Maximum allowed changes. If set, enforced as hard error.

    Returns:
        ValidationResult with errors and warnings.
    """
    from .state import topological_sort

    result = ValidationResult()

    # Check JSON structure
    try:
        with open(plan_path, "r") as f:
            plan = json.load(f)
    except json.JSONDecodeError:
        result.errors.append("Plan file is not valid JSON")
        return result
    except OSError as e:
        result.errors.append(f"Cannot read plan file: {e}")
        return result

    # Check required fields
    for fld in ("plan_version", "brief_hash", "changes"):
        if not plan.get(fld):
            result.errors.append(f"Plan missing required field: {fld}")

    changes = plan.get("changes", [])
    if not isinstance(changes, list):
        result.errors.append("'changes' must be an array")
        return result

    # Check change names are kebab-case
    all_names = set()
    bad_names = []
    for c in changes:
        name = c.get("name", "")
        all_names.add(name)
        if not _KEBAB_CASE_RE.match(name):
            bad_names.append(name)
    if bad_names:
        result.errors.append(
            f"Invalid change names (must be kebab-case): {', '.join(bad_names)}"
        )

    # Hard validation: change count
    if max_change_target is not None and len(changes) > max_change_target:
        result.errors.append(
            f"Plan has {len(changes)} changes, max allowed is {max_change_target}. "
            "Merge related changes."
        )

    # Hard validation: complexity, model, scope length per change
    for c in changes:
        cname = c.get("name", "?")
        complexity = c.get("complexity", "")
        if complexity and complexity not in ("S", "M"):
            result.errors.append(
                f"Change '{cname}' has complexity {complexity}. "
                "Split into S or M changes."
            )
        model = c.get("model", "")
        if model and model not in ("opus", "sonnet"):
            result.errors.append(
                f"Change '{cname}' has invalid model '{model}'. "
                "Use 'opus' or 'sonnet'."
            )
        scope = c.get("scope", "")
        if len(scope) > 2000:
            result.errors.append(
                f"Change '{cname}' scope is {len(scope)} chars (max 2000). "
                "Split the change or reduce scope."
            )

    # Check depends_on references exist
    all_deps = set()
    for c in changes:
        for dep in c.get("depends_on", []):
            all_deps.add(dep)

    missing = all_deps - all_names
    if missing:
        result.errors.append(
            f"depends_on references non-existent changes: {', '.join(sorted(missing))}"
        )

    # Check for circular dependencies
    try:
        topological_sort(changes)
    except Exception:
        result.errors.append("Circular dependency detected in change graph")

    # Digest-mode validation: check requirement references
    if digest_dir:
        req_file = Path(digest_dir) / "requirements.json"
        if req_file.exists():
            try:
                req_data = json.loads(req_file.read_text())
                all_req_ids = {
                    r["id"]
                    for r in req_data.get("requirements", [])
                    if r.get("status") != "removed"
                }

                # Check requirements reference valid IDs
                for c in changes:
                    for rid in c.get("requirements", []):
                        if rid not in all_req_ids:
                            result.warnings.append(
                                f"Plan references non-existent requirement: {rid}"
                            )
                    for rid in c.get("also_affects_reqs", []):
                        if rid not in all_req_ids:
                            result.warnings.append(
                                f"Plan references non-existent requirement: {rid}"
                            )

                # Check also_affects_reqs have a primary owner
                primary_owned = set()
                for c in changes:
                    primary_owned.update(c.get("requirements", []))

                for c in changes:
                    for aaid in c.get("also_affects_reqs", []):
                        if aaid not in primary_owned:
                            result.warnings.append(
                                f"also_affects_reqs '{aaid}' has no primary owner "
                                "in any change's requirements[]"
                            )

                # Parse deferred_requirements (task 6.2)
                deferred_requirement_ids: set[str] = set()
                deferred_entries = plan.get("deferred_requirements", [])
                if isinstance(deferred_entries, list):
                    for entry in deferred_entries:
                        if not isinstance(entry, dict):
                            continue
                        did = entry.get("id", "")
                        reason = entry.get("reason", "")
                        if not did or not reason:
                            result.warnings.append(
                                f"deferred_requirements entry missing 'id' or 'reason': {entry}"
                            )
                            continue
                        if did not in all_req_ids:
                            result.warnings.append(
                                f"Deferred requirement ID not found in digest: {did}"
                            )
                        else:
                            deferred_requirement_ids.add(did)
                            result.warnings.append(
                                f"Deferred requirement: {did} — {reason}"
                            )

                # Reverse requirement coverage check (task 6.1)
                all_assigned: set[str] = set()
                for c in changes:
                    all_assigned.update(c.get("requirements", []))
                    all_assigned.update(c.get("also_affects_reqs", []))

                unassigned = all_req_ids - all_assigned
                unexplained = unassigned - deferred_requirement_ids
                for rid in sorted(unexplained):
                    result.errors.append(
                        f"Requirement not covered by any change and not deferred: {rid}"
                    )

            except (json.JSONDecodeError, OSError):
                logger.warning("Could not read requirements.json for coverage validation")

    # Source items validation (single-file mode — no digest)
    if not digest_dir:
        source_items = plan.get("source_items", [])
        if not source_items:
            result.warnings.append(
                "No source_items in plan and no digest_dir — "
                "coverage tracking unavailable for this run"
            )
        elif isinstance(source_items, list):
            for si in source_items:
                if not isinstance(si, dict):
                    continue
                si_change = si.get("change")
                si_id = si.get("id", "?")
                if si_change is None:
                    result.warnings.append(
                        f"Source item {si_id} intentionally excluded (change: null)"
                    )
                elif si_change and si_change not in all_names:
                    result.errors.append(
                        f"Source item {si_id} references non-existent change: {si_change}"
                    )

    # Check scope overlap
    overlaps = check_scope_overlap(plan_path)
    for ov in overlaps:
        result.warnings.append(
            f"Scope overlap detected: '{ov.name_a}' ↔ '{ov.name_b}' "
            f"({ov.similarity}% keyword similarity)"
        )

    # Test load validation: warn if a change has too many required tests
    if digest_dir:
        _plan_file = os.path.join(digest_dir, "test-plan.json")
        if os.path.isfile(_plan_file):
            try:
                from .test_coverage import TestPlan
                _tp = TestPlan.from_dict(json.loads(Path(_plan_file).read_text()))
                for c in changes:
                    _reqs = c.get("requirements", [])
                    if not _reqs:
                        continue
                    _req_set = set(_reqs)
                    _entries = [e for e in _tp.entries if e.req_id in _req_set]
                    _total = sum(e.min_tests for e in _entries)
                    if _total > 40:
                        _cname = c.get('name', '?')
                        logger.warning(
                            "Change %s has %d required tests (%d REQs) — consider splitting",
                            _cname, _total, len(_reqs),
                        )
                        result.warnings.append(
                            f"Change '{_cname}' has {_total} required tests "
                            f"({len(_reqs)} REQs) — consider splitting into smaller changes"
                        )
            except Exception:
                pass

    # Plan validation summary (task 5.3)
    logger.info(
        "Plan validated: %d changes, %d warnings, %d errors",
        len(changes), len(result.warnings), len(result.errors),
    )

    # Spec coverage annotation report (after successful validation)
    if not result.errors:
        try:
            generate_coverage_report(
                plan=plan,
                digest_dir=digest_dir or "",
                output_path=_default_coverage_path(),
                plan_path=plan_path,
            )
        except Exception as exc:
            logger.warning("Could not generate spec coverage report: %s", exc)

    # Design-manifest coverage (profile-driven). Layer 1 orchestrates the
    # call; the concrete profile (e.g. WebProjectType) enforces the rule.
    try:
        from .profile_loader import load_profile as _load_design_profile

        _design_profile = _load_design_profile()
        project_path = Path(plan_path).parent.parent  # …/openspec/changes/<name>/plan.json? fallback to cwd
        if not project_path.is_dir():
            project_path = Path.cwd()
        design_violations = _design_profile.validate_plan_design_coverage(plan, project_path)
        for v in design_violations:
            result.errors.append(f"Design coverage: {v}")
    except Exception:
        logger.debug("validate_plan_design_coverage raised", exc_info=True)

    return result


def _default_coverage_path() -> str:
    try:
        from .paths import SetRuntime
        return SetRuntime().spec_coverage_report
    except Exception:
        return "set/orchestration/spec-coverage-report.md"


def generate_coverage_report(
    plan: dict,
    digest_dir: str = "",
    output_path: str = "",
    state_file: str = "",
    plan_path: str = "",
) -> None:
    """Generate a markdown coverage report mapping requirements/source items to changes.

    Supports two modes:
    - Digest mode: reads requirements.json from digest_dir
    - Single-file mode: reads source_items from plan JSON

    When state_file is provided, renders live statuses (MERGED, DISPATCHED, etc.)
    instead of static COVERED.
    """
    if not output_path:
        output_path = _default_coverage_path()

    # Load change statuses from state (if available)
    change_statuses: dict[str, str] = {}
    if state_file:
        try:
            state_data = json.loads(Path(state_file).read_text(encoding="utf-8"))
            for c in state_data.get("changes", []):
                name = c.get("name", "")
                if name:
                    change_statuses[name] = c.get("status", "pending")
        except (json.JSONDecodeError, OSError):
            pass

    # Try digest mode first
    all_reqs: list[dict] = []
    if digest_dir:
        req_file = Path(digest_dir) / "requirements.json"
        if req_file.exists():
            try:
                req_data = json.loads(req_file.read_text())
                all_reqs = [r for r in req_data.get("requirements", []) if r.get("status") != "removed"]
            except (json.JSONDecodeError, OSError):
                pass

    # Fall back to source_items from plan (single-file mode)
    source_items: list[dict] = []
    if not all_reqs:
        source_items = plan.get("source_items", [])
        if not source_items and plan_path:
            try:
                plan_data = json.loads(Path(plan_path).read_text(encoding="utf-8"))
                source_items = plan_data.get("source_items", [])
            except (json.JSONDecodeError, OSError):
                pass

    if not all_reqs and not source_items:
        return

    changes = plan.get("changes", [])
    deferred_entries = {
        e["id"]: e.get("reason", "")
        for e in plan.get("deferred_requirements", [])
        if isinstance(e, dict) and e.get("id")
    }

    # Build req_id → change names mapping
    req_to_changes: dict[str, list[str]] = {}
    for c in changes:
        for rid in c.get("requirements", []):
            req_to_changes.setdefault(rid, []).append(c["name"])
        for rid in c.get("also_affects_reqs", []):
            req_to_changes.setdefault(rid, []).append(f"{c['name']} (cross)")

    lines = [
        "# Spec Coverage Report",
        "",
        "| ID | Title | Status | Change(s) |",
        "|----|-------|--------|-----------|",
    ]

    covered = deferred = uncovered = 0

    def _status_for_changes(change_names: list[str]) -> str:
        """Derive display status from change statuses (state-aware when available)."""
        if not change_statuses:
            return "COVERED"
        # Use the most advanced status among owning changes
        statuses = [change_statuses.get(n.replace(" (cross)", ""), "pending") for n in change_names]
        if any(s == "merged" for s in statuses):
            return "MERGED"
        if any(s == "failed" for s in statuses):
            return "FAILED"
        if any(s in ("running", "verifying") for s in statuses):
            return "DISPATCHED"
        return "PENDING"

    if all_reqs:
        # Digest mode
        for req in all_reqs:
            rid = req.get("id", "")
            title = req.get("title", rid)
            if rid in req_to_changes:
                status = _status_for_changes(req_to_changes[rid])
                change_list = ", ".join(req_to_changes[rid])
                covered += 1
            elif rid in deferred_entries:
                status = f"DEFERRED: {deferred_entries[rid]}"
                change_list = "—"
                deferred += 1
            else:
                status = "UNCOVERED"
                change_list = "—"
                uncovered += 1
            lines.append(f"| {rid} | {title} | {status} | {change_list} |")
    else:
        # Single-file mode (source_items)
        for si in source_items:
            si_id = si.get("id", "?")
            text = si.get("text", "")
            si_change = si.get("change")
            if si_change:
                status = _status_for_changes([si_change])
                change_list = si_change
                covered += 1
            elif si_change is None:
                status = "EXCLUDED"
                change_list = "—"
                deferred += 1
            else:
                status = "UNCOVERED"
                change_list = "—"
                uncovered += 1
            lines.append(f"| {si_id} | {text} | {status} | {change_list} |")

    total = len(all_reqs) or len(source_items)
    lines += [
        "",
        f"**Summary**: {covered} covered, {deferred} deferred, {uncovered} uncovered "
        f"(total: {total})",
    ]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n"
    try:
        from .archive import archive_and_write

        archive_dir = str(Path(output_path).parent / "archive" / "spec-coverage")
        archive_and_write(
            output_path,
            content,
            archive_dir=archive_dir,
            reason="coverage-regen",
        )
    except Exception as exc:
        logger.warning(
            "archive_and_write failed for coverage report, falling back to direct write: %s",
            exc,
        )
        Path(output_path).write_text(content)
    logger.info("Spec coverage report written to %s", output_path)


# ─── Scope Overlap Detection ─────────────────────────────────────────
# Migrated from: planner.sh check_scope_overlap() L253-373


def _extract_scope_keywords(scope_text: str) -> set[str]:
    """Extract lowercase keywords (3+ chars) from scope text.

    Migrated from: planner.sh check_scope_overlap() L263-270
    """
    words = re.findall(r"[a-z]{3,}", scope_text.lower())
    return set(words)


def check_scope_overlap(
    plan_path: str,
    state_path: str | None = None,
    pk_path: str | None = None,
) -> list[ScopeOverlap]:
    """Detect overlapping scopes between changes in a plan.

    Migrated from: planner.sh check_scope_overlap() L253-373

    Uses Jaccard similarity on scope keywords. Warns at >= 40%.

    Args:
        plan_path: Path to plan JSON file.
        state_path: Optional state file for checking against active changes.
        pk_path: Optional project-knowledge.yaml for cross-cutting file detection.

    Returns:
        List of ScopeOverlap instances.
    """
    try:
        with open(plan_path, "r") as f:
            plan = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    changes = plan.get("changes", [])
    if len(changes) < 2 and not state_path:
        return []

    overlaps: list[ScopeOverlap] = []

    # Build keyword sets for each change
    scope_words: dict[str, set[str]] = {}
    names = []
    for c in changes:
        name = c.get("name", "")
        names.append(name)
        scope_words[name] = _extract_scope_keywords(c.get("scope", ""))

    # Pairwise Jaccard comparison
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            name_a, name_b = names[i], names[j]
            words_a, words_b = scope_words[name_a], scope_words[name_b]

            # Skip if either has very few words
            if len(words_a) < 3 or len(words_b) < 3:
                continue

            intersection = len(words_a & words_b)
            union = len(words_a | words_b)

            if union > 0:
                similarity = intersection * 100 // union
                if similarity >= 40:
                    overlaps.append(ScopeOverlap(name_a, name_b, similarity))
                    logger.warning(
                        "Scope overlap: %s ↔ %s = %d%% (intersection=%d, union=%d)",
                        name_a, name_b, similarity, intersection, union,
                    )

    # Also check against active worktrees (if state file exists)
    if state_path and os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                state = json.load(f)

            active_statuses = {"running", "dispatched", "done"}
            for sc in state.get("changes", []):
                if sc.get("status") not in active_statuses:
                    continue
                active_name = sc.get("name", "")
                active_words = _extract_scope_keywords(sc.get("scope", ""))
                if len(active_words) < 3:
                    continue

                for name in names:
                    if name == active_name:
                        continue
                    words = scope_words.get(name, set())
                    if len(words) < 3:
                        continue

                    intersection = len(words & active_words)
                    union = len(words | active_words)
                    if union > 0:
                        similarity = intersection * 100 // union
                        if similarity >= 40:
                            overlaps.append(ScopeOverlap(name, active_name, similarity))
                            logger.warning(
                                "Overlap with active: %s ↔ %s = %d%%",
                                name, active_name, similarity,
                            )
        except (json.JSONDecodeError, OSError):
            logger.warning("Could not read state file for overlap check")

    # Check cross-cutting file mentions if project-knowledge.yaml exists
    if pk_path and os.path.exists(pk_path):
        try:
            import yaml
        except ImportError:
            logger.debug("PyYAML not available, skipping project-knowledge check")
        else:
            try:
                with open(pk_path, "r") as f:
                    pk = yaml.safe_load(f)

                cc_files = pk.get("cross_cutting_files", [])
                for cc in cc_files:
                    cc_path = cc.get("path", "")
                    if not cc_path:
                        continue
                    cc_basename = os.path.basename(cc_path).lower()

                    touching_changes = []
                    for name in names:
                        scope_text = ""
                        for c in changes:
                            if c.get("name") == name:
                                scope_text = c.get("scope", "")
                                break
                        if cc_basename in scope_text.lower():
                            touching_changes.append(name)

                    if len(touching_changes) >= 2:
                        logger.warning(
                            "Cross-cutting file '%s' may be touched by: %s",
                            cc_path, ", ".join(touching_changes),
                        )
                        # Record as overlap warning (with 100% as special marker)
                        for k in range(len(touching_changes)):
                            for m in range(k + 1, len(touching_changes)):
                                overlaps.append(
                                    ScopeOverlap(
                                        touching_changes[k],
                                        touching_changes[m],
                                        100,  # cross-cutting marker
                                    )
                                )
            except (OSError, Exception) as e:
                logger.warning("Could not read project-knowledge file: %s", e)

    return overlaps


# ─── Triage Gate ──────────────────────────────────────────────────────
# Migrated from: planner.sh check_triage_gate() L388-446


def check_triage_gate(
    digest_dir: str,
    auto_defer: bool = False,
) -> TriageStatus:
    """Check triage status for ambiguities.

    Migrated from: planner.sh check_triage_gate() L388-446

    Args:
        digest_dir: Path to the digest directory.
        auto_defer: If True, auto-defer all ambiguities (automated mode).

    Returns:
        TriageStatus with status string and ambiguity count.
    """
    amb_path = Path(digest_dir) / "ambiguities.json"
    if not amb_path.exists():
        return TriageStatus(status="no_ambiguities")

    try:
        amb_data = json.loads(amb_path.read_text())
    except (json.JSONDecodeError, OSError):
        return TriageStatus(status="no_ambiguities")

    ambiguities = amb_data.get("ambiguities", [])
    amb_count = len(ambiguities)
    if amb_count == 0:
        return TriageStatus(status="no_ambiguities")

    # Auto-defer mode
    if auto_defer:
        logger.info("Auto-deferred %d ambiguities (automated mode)", amb_count)
        return TriageStatus(status="passed", count=amb_count)

    triage_path = Path(digest_dir) / "triage.md"
    if not triage_path.exists():
        return TriageStatus(status="needs_triage", count=amb_count)

    # Parse triage decisions from triage.md
    decisions = _parse_triage_decisions(triage_path)
    amb_ids = [a.get("id", "") for a in ambiguities]

    # Check for untriaged items
    untriaged_count = sum(
        1 for aid in amb_ids
        if aid not in decisions or not decisions[aid].get("decision")
    )
    if untriaged_count > 0:
        return TriageStatus(status="has_untriaged", count=untriaged_count)

    # Check for "fix" items
    fix_count = sum(
        1 for d in decisions.values()
        if d.get("decision") == "fix"
    )
    if fix_count > 0:
        return TriageStatus(status="has_fixes", count=fix_count)

    return TriageStatus(status="passed", count=amb_count)


def _parse_triage_decisions(triage_path: Path) -> dict[str, dict]:
    """Parse triage.md for decisions. Returns {id: {decision, note}}.

    Simplified parser matching the markdown format from digest.sh generate_triage_md.
    """
    decisions: dict[str, dict] = {}
    try:
        content = triage_path.read_text()
    except OSError:
        return decisions

    current_id = ""
    for line in content.splitlines():
        # Match "### AMB-xxx" headers
        m = re.match(r"^###\s+(AMB-\S+)", line)
        if m:
            current_id = m.group(1)
            decisions[current_id] = {"decision": "", "note": ""}
            continue

        if current_id:
            # Match "Decision: xxx"
            m = re.match(r"^Decision:\s*(.*)", line, re.IGNORECASE)
            if m:
                decisions[current_id]["decision"] = m.group(1).strip().lower()
                continue
            # Match "Note: xxx"
            m = re.match(r"^Note:\s*(.*)", line, re.IGNORECASE)
            if m:
                decisions[current_id]["note"] = m.group(1).strip()

    return decisions


# ─── Decomposition Context Assembly ──────────────────────────────────
# Migrated from: planner.sh cmd_plan() L638-963


def build_decomposition_context(
    input_mode: str,
    input_path: str,
    *,
    phase_hint: str = "",
    existing_specs: str = "",
    active_changes: str = "",
    memory_context: str = "",
    design_context: str = "",
    pk_context: str = "",
    req_context: str = "",
    test_infra_context: str = "",
    coverage_info: str = "",
    replan_ctx: dict | None = None,
    team_mode: bool = False,
) -> dict:
    """Assemble all context needed for the planning prompt.

    Migrated from: planner.sh cmd_plan() L638-963

    Gathers input content, builds context sections, and returns a dict
    suitable for passing to templates.render_planning_prompt().

    Args:
        input_mode: "brief", "spec", or "digest"
        input_path: Path to input file or digest directory
        Various context strings and flags.

    Returns:
        Dict with all context fields for template rendering.
    """
    input_content = ""

    if input_mode == "digest":
        # input_path is the original spec dir (e.g. "docs/"), but digest
        # output lives in set/orchestration/digest/. Use that instead.
        digest_dir = os.path.join(os.getcwd(), "set", "orchestration", "digest")
        input_content = _build_digest_content(digest_dir)
    else:
        try:
            input_content = Path(input_path).read_text(errors="replace")
        except OSError:
            logger.error("Cannot read input file: %s", input_path)

    mode = "brief" if input_mode == "brief" else "spec"

    phase_instruction = ""
    if phase_hint:
        phase_instruction = (
            f"The user requested phase: {phase_hint}. "
            "Focus decomposition on items matching this phase."
        )

    # Read max_parallel from directives (state file) if available
    max_parallel = 3  # default
    try:
        state_path = os.path.join(os.getcwd(), "orchestration-state.json")
        if os.path.isfile(state_path):
            with open(state_path) as _sf:
                _sd = json.load(_sf)
            max_parallel = _sd.get("extras", {}).get("directives", {}).get("max_parallel", 3)
    except Exception:
        pass

    return {
        "input_content": input_content,
        "specs": existing_specs,
        "memory": memory_context,
        "replan_ctx": replan_ctx or {},
        "mode": mode,
        "phase_instruction": phase_instruction,
        "input_mode": input_mode,
        "test_infra_context": test_infra_context,
        "pk_context": pk_context,
        "req_context": req_context,
        "active_changes": active_changes,
        "coverage_info": coverage_info,
        "design_context": design_context,
        "team_mode": team_mode,
        "max_parallel": max_parallel,
    }


def _build_digest_content(digest_dir: str) -> str:
    """Build decomposition input content from digest directory.

    Migrated from: planner.sh cmd_plan() L754-848
    """
    d = Path(digest_dir)
    sections: list[str] = []

    # Conventions
    conv_path = d / "conventions.json"
    if conv_path.exists():
        try:
            sections.append(
                f"## Project Conventions (apply to ALL changes)\n{conv_path.read_text()}\n"
            )
        except OSError:
            pass

    # Data model — data-definitions.md removed (LLM-generated, caused naming drift).
    # Replaced by auto-parsed schema digest injected at dispatch time.

    # Execution hints
    index_path = d / "index.json"
    if index_path.exists():
        try:
            idx = json.loads(index_path.read_text())
            hints = idx.get("execution_hints")
            if hints and hints != {}:
                sections.append(
                    f"## Execution Hints (optional guidance from spec author)\n"
                    f"{json.dumps(hints)}\n"
                )
        except (json.JSONDecodeError, OSError):
            pass

    # Domain summaries
    domains_dir = d / "domains"
    if domains_dir.is_dir():
        domain_parts = ["## Domain Summaries\n"]
        for domain_file in sorted(domains_dir.glob("*.md")):
            dname = domain_file.stem
            try:
                domain_parts.append(f"### {dname}\n{domain_file.read_text()}\n")
            except OSError:
                pass
        if len(domain_parts) > 1:
            sections.append("".join(domain_parts))

    # Requirements (compact)
    req_path = d / "requirements.json"
    if req_path.exists():
        try:
            req_data = json.loads(req_path.read_text())
            compact = [
                {"id": r["id"], "title": r.get("title", ""), "domain": r.get("domain", ""), "brief": r.get("brief", "")}
                for r in req_data.get("requirements", [])
            ]
            req_count = len(compact)
            sections.append(
                f"## Requirements ({req_count} total)\n"
                f"{json.dumps({'requirements': compact})}\n"
            )
        except (json.JSONDecodeError, OSError):
            pass

    # Dependencies
    deps_path = d / "dependencies.json"
    if deps_path.exists():
        try:
            sections.append(f"## Cross-references\n{deps_path.read_text()}\n")
        except OSError:
            pass

    # Deferred ambiguities
    amb_path = d / "ambiguities.json"
    if amb_path.exists():
        try:
            amb_data = json.loads(amb_path.read_text())
            deferred = [
                a for a in amb_data.get("ambiguities", [])
                if a.get("resolution") == "deferred" or "resolution" not in a
            ]
            if deferred:
                deferred_json = json.dumps({"ambiguities": deferred})
                sections.append(
                    f"## Deferred Ambiguities ({len(deferred)} items — you MUST resolve each)\n"
                    "For each deferred ambiguity below, include a \"resolved_ambiguities\" "
                    "entry in the change that addresses the affected requirements. "
                    "Specify your decision and rationale.\n\n"
                    f"{deferred_json}\n"
                )
        except (json.JSONDecodeError, OSError):
            pass

    return "\n".join(sections)


# ─── Plan Metadata Enrichment ─────────────────────────────────────────
# Migrated from: planner.sh cmd_plan() L1049-1092

def _assign_cross_cutting_ownership(plan_data: dict, profile=None) -> None:
    """Assign ownership of cross-cutting files to changes.

    When multiple changes mention the same unsplittable file in their scope,
    the first change (by plan order) becomes the owner. Others get a depends_on
    on the owner and a `cross_cutting_no_modify` list of files they must not touch.
    """
    changes = plan_data.get("changes", [])
    if len(changes) < 2:
        return

    # Get cross-cutting files from profile (or empty if no profile)
    cc_files: list[str] = []
    if profile is not None:
        cc_files = profile.cross_cutting_files()

    if not cc_files:
        return

    # Build a map: file_basename → [change_names that mention it]
    file_touchers: dict[str, list[str]] = {}
    for cc_file in cc_files:
        for c in changes:
            scope_lower = c.get("scope", "").lower()
            if cc_file.lower() in scope_lower:
                file_touchers.setdefault(cc_file, []).append(c["name"])

    # Assign ownership: first toucher owns, others get depends_on
    for cc_file, touchers in file_touchers.items():
        if len(touchers) < 2:
            continue

        owner = touchers[0]
        logger.info(
            "Cross-cutting: %s owned by '%s', serializing: %s",
            cc_file, owner, touchers[1:],
        )

        for non_owner_name in touchers[1:]:
            for c in changes:
                if c["name"] == non_owner_name:
                    # Add depends_on
                    deps = c.setdefault("depends_on", [])
                    if owner not in deps:
                        deps.append(owner)
                    # Track files this change must not modify
                    no_modify = c.setdefault("cross_cutting_no_modify", [])
                    if cc_file not in no_modify:
                        no_modify.append(cc_file)
                    break


def enrich_plan_metadata(
    plan_data: dict,
    hash_val: str,
    input_mode: str,
    input_path: str,
    plan_version: int = 1,
    replan_cycle: int | None = None,
    state_path: str | None = None,
) -> dict:
    """Add metadata fields to a raw plan JSON.

    Migrated from: planner.sh cmd_plan() L1049-1092

    Args:
        plan_data: Raw plan dict from Claude decomposition.
        hash_val: Input content hash.
        input_mode: "brief", "spec", or "digest".
        input_path: Path to the input file.
        plan_version: Plan version number.
        replan_cycle: If set, indicates a replan iteration.
        state_path: State file for replan depends_on stripping.

    Returns:
        Enriched plan dict with metadata.
    """
    plan_phase = "iteration" if replan_cycle is not None else "initial"
    plan_method = os.environ.get("_PLAN_METHOD", "api")

    # Compute input hash
    input_hash = ""
    if input_path and os.path.isfile(input_path):
        try:
            input_hash = hashlib.sha256(
                Path(input_path).read_bytes()
            ).hexdigest()
        except OSError:
            pass

    plan_data.update({
        "plan_version": plan_version,
        "brief_hash": hash_val,
        "created_at": datetime.now().astimezone().isoformat(),
        "input_mode": input_mode,
        "input_path": input_path,
        "input_hash": input_hash,
        "plan_phase": plan_phase,
        "plan_method": plan_method,
    })

    # Assign i18n namespaces to changes (non-overlapping, derived from change name)
    for c in plan_data.get("changes", []):
        ns = c["name"].replace("-", "_")
        c.setdefault("i18n_namespace", ns)

    # Cross-cutting file ownership: detect from profile or scope text.
    # When multiple changes mention the same unsplittable file, assign the first as
    # owner and add depends_on to others (serialization at dispatch).
    try:
        from .profile_loader import load_profile
        _profile = load_profile()
    except Exception:
        _profile = None
    _assign_cross_cutting_ownership(plan_data, profile=_profile)

    # During replan, strip depends_on references to completed changes
    if replan_cycle is not None and state_path and os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                state = json.load(f)

            completed_names = {
                c["name"]
                for c in state.get("changes", [])
                if c.get("status") in ("done", "merged", "merge-blocked")
            }
            plan_names = {c["name"] for c in plan_data.get("changes", [])}

            for c in plan_data.get("changes", []):
                deps = c.get("depends_on", [])
                # Keep only deps that are in the current plan
                c["depends_on"] = [d for d in deps if d in plan_names]
        except (json.JSONDecodeError, OSError):
            logger.warning("Could not read state for replan depends_on stripping")

    return plan_data


# ─── Replan Context Collection ────────────────────────────────────────
# Migrated from: planner.sh auto_replan_cycle() L1280-1343


def collect_replan_context(state_path: str) -> dict:
    """Gather completed change info for the next replan cycle.

    Migrated from: planner.sh auto_replan_cycle() L1280-1343

    Args:
        state_path: Path to the orchestration state file.

    Returns:
        Dict with completed names, roadmap items, file lists, and E2E failure context.
    """
    result: dict[str, Any] = {
        "completed_names": "",
        "completed_roadmap": "",
        "file_context": "",
        "memory": "",
        "e2e_failures": "",
    }

    try:
        with open(state_path, "r") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        return result

    completed_statuses = {"done", "merged", "merge-blocked"}
    completed_changes = [
        c for c in state.get("changes", [])
        if c.get("status") in completed_statuses
    ]

    result["completed_names"] = ", ".join(c["name"] for c in completed_changes)
    result["completed_roadmap"] = "; ".join(
        c.get("roadmap_item", "") for c in completed_changes if c.get("roadmap_item")
    )

    # Gather file lists from merged changes via git log
    merged_names = [
        c["name"] for c in completed_changes if c.get("status") == "merged"
    ]
    file_parts: list[str] = []
    for cname in merged_names:
        try:
            git_result = subprocess.run(
                [
                    "git", "log", "--all", "--oneline", "--diff-filter=ACMR",
                    "--name-only", "--format=", f"--grep={cname}", "--",
                ],
                capture_output=True, text=True, timeout=10,
            )
            if git_result.returncode == 0 and git_result.stdout.strip():
                files = sorted(set(git_result.stdout.strip().splitlines()))[:20]
                file_parts.append(f"{cname}: {' '.join(files)}")
        except (subprocess.TimeoutExpired, OSError):
            pass

    if file_parts:
        result["file_context"] = "\n".join(file_parts)

    # E2E failure context
    e2e_ctx = state.get("phase_e2e_failure_context", "")
    if e2e_ctx and e2e_ctx != "null":
        result["e2e_failures"] = (
            "Phase-end E2E tests failed on the integrated codebase. "
            "These failures indicate integration issues that must be "
            "addressed in the next phase:\n\n" + str(e2e_ctx)
        )

    return result


# ─── Domain-Parallel Decompose Phases ─────────────────────────────────


def _load_domain_data(digest_dir: str) -> dict:
    """Load domain summaries and requirements grouped by domain from digest.

    Returns dict with:
        domains: list of {name, summary, requirements}
        conventions: str
        dependencies: str
        ambiguities: str
        domain_summaries_text: str (formatted for prompts)
        all_requirements: list of dicts
    """
    d = Path(digest_dir)
    result: dict[str, Any] = {
        "domains": [],
        "conventions": "",
        "dependencies": "",
        "ambiguities": "",
        "domain_summaries_text": "",
        "all_requirements": [],
    }

    # Conventions
    conv_path = d / "conventions.json"
    if conv_path.exists():
        try:
            result["conventions"] = conv_path.read_text()
        except OSError:
            pass

    # Dependencies
    deps_path = d / "dependencies.json"
    if deps_path.exists():
        try:
            result["dependencies"] = deps_path.read_text()
        except OSError:
            pass

    # Ambiguities (deferred only)
    amb_path = d / "ambiguities.json"
    if amb_path.exists():
        try:
            amb_data = json.loads(amb_path.read_text())
            deferred = [
                a for a in amb_data.get("ambiguities", [])
                if a.get("resolution") == "deferred" or "resolution" not in a
            ]
            if deferred:
                result["ambiguities"] = json.dumps({"ambiguities": deferred})
        except (json.JSONDecodeError, OSError):
            pass

    # Requirements
    req_path = d / "requirements.json"
    all_reqs: list[dict] = []
    if req_path.exists():
        try:
            req_data = json.loads(req_path.read_text())
            all_reqs = req_data.get("requirements", [])
        except (json.JSONDecodeError, OSError):
            pass
    result["all_requirements"] = all_reqs

    # Group requirements by domain
    reqs_by_domain: dict[str, list[dict]] = {}
    for r in all_reqs:
        domain = r.get("domain", "misc")
        reqs_by_domain.setdefault(domain, []).append(r)

    # Domain summaries from domains/*.md
    domains_dir = d / "domains"
    domain_names = set(reqs_by_domain.keys())
    if domains_dir.is_dir():
        for f in sorted(domains_dir.glob("*.md")):
            domain_names.add(f.stem)

    summary_parts = []
    for dname in sorted(domain_names):
        summary = ""
        summary_file = domains_dir / f"{dname}.md" if domains_dir.is_dir() else None
        if summary_file and summary_file.exists():
            try:
                summary = summary_file.read_text()
            except OSError:
                pass

        domain_reqs = reqs_by_domain.get(dname, [])
        compact_reqs = [
            {"id": r["id"], "title": r.get("title", ""), "brief": r.get("brief", "")}
            for r in domain_reqs
        ]

        result["domains"].append({
            "name": dname,
            "summary": summary,
            "requirements": compact_reqs,
            "requirements_json": json.dumps({"requirements": compact_reqs}),
        })
        summary_parts.append(f"### {dname}\n{summary}\nRequirements: {len(compact_reqs)}")

    result["domain_summaries_text"] = "\n\n".join(summary_parts)
    return result


def _phase1_planning_brief(
    domain_data: dict,
    *,
    test_infra_context: str = "",
    existing_specs: str = "",
    active_changes: str = "",
    memory_context: str = "",
    model: str = "opus",
    max_parallel: int = 3,
) -> dict:
    """Phase 1: Generate planning brief from domain summaries."""
    from .subprocess_utils import run_claude_logged
    from .templates import render_brief_prompt

    prompt = render_brief_prompt(
        domain_summaries=domain_data["domain_summaries_text"],
        dependencies=domain_data["dependencies"],
        conventions=domain_data["conventions"],
        test_infra_context=test_infra_context,
        existing_specs=existing_specs,
        active_changes=active_changes,
        memory_context=memory_context,
        max_parallel=max_parallel,
    )

    logger.info("Phase 1: generating planning brief (%d domains)", len(domain_data["domains"]))
    result = run_claude_logged(prompt, purpose="decompose_brief", timeout=600, model=model, extra_args=["--max-turns", "3"])
    if result.exit_code != 0:
        raise RuntimeError(f"Phase 1 (planning brief) failed (exit {result.exit_code})")

    brief = _parse_plan_response(result.stdout)
    if not brief:
        raise RuntimeError("Phase 1: could not parse planning brief JSON")

    # Validate required fields
    for field in ("domain_priorities", "resource_ownership", "cross_cutting_changes", "phasing_strategy"):
        if field not in brief:
            brief[field] = [] if field in ("domain_priorities", "cross_cutting_changes") else {} if field == "resource_ownership" else ""

    logger.info(
        "Phase 1 complete: %d domain priorities, %d cross-cutting changes, %d resource assignments",
        len(brief.get("domain_priorities", [])),
        len(brief.get("cross_cutting_changes", [])),
        len(brief.get("resource_ownership", {})),
    )
    return brief


def _build_test_plan_context(digest_dir: str, requirement_ids: list[str]) -> str:
    """Build test plan context from test-plan.json for planner prompt injection.

    Returns formatted markdown with test expectations per REQ, or empty string
    if no test plan or no matching entries.
    """
    if not digest_dir:
        return ""
    plan_path = os.path.join(digest_dir, "test-plan.json")
    if not os.path.isfile(plan_path):
        return ""
    try:
        from .test_coverage import TestPlan
        plan = TestPlan.from_dict(json.loads(Path(plan_path).read_text()))
        req_set = set(requirement_ids)
        entries = [e for e in plan.entries if e.req_id in req_set]
        if not entries:
            return ""

        # Task 5.1: log test plan injection
        logger.info(
            "Injecting %d test plan entries for %d requirements into planner prompt",
            len(entries), len(req_set),
        )

        lines = [
            f"\n## E2E Test Expectations ({len(entries)} scenarios)",
            "The following test scenarios are required for the requirements in this domain.",
            "Each change MUST include E2E tasks covering its assigned scenarios.",
            "MEDIUM risk = happy + negative test. HIGH risk = happy + 2 negative tests.",
            "Do NOT collapse these into a narrative summary — list each scenario as a separate task.",
        ]
        for e in entries:
            cats = ", ".join(e.categories)
            lines.append(f"- {e.req_id}: {e.scenario_name} [{e.risk}] — {e.min_tests} test(s) ({cats})")
        return "\n".join(lines)
    except Exception:
        return ""


def _decompose_single_domain(
    domain: dict,
    planning_brief_json: str,
    conventions: str,
    *,
    test_infra_context: str = "",
    design_context: str = "",
    test_plan_context: str = "",
    model: str = "opus",
    max_parallel: int = 3,
) -> dict:
    """Decompose a single domain into changes. Called in parallel."""
    from .subprocess_utils import run_claude_logged
    from .templates import render_domain_decompose_prompt

    prompt = render_domain_decompose_prompt(
        domain_name=domain["name"],
        domain_summary=domain["summary"],
        domain_requirements=domain["requirements_json"],
        planning_brief=planning_brief_json,
        conventions=conventions,
        test_infra_context=test_infra_context,
        design_context=design_context + ("\n" + test_plan_context if test_plan_context else ""),
        max_parallel=max_parallel,
    )

    logger.info("Phase 2: decomposing domain '%s' (%d reqs)", domain["name"], len(domain["requirements"]))
    result = run_claude_logged(prompt, purpose="decompose_domain", timeout=900, model=model, extra_args=["--max-turns", "5"])
    if result.exit_code != 0:
        raise RuntimeError(f"Phase 2 domain '{domain['name']}' failed (exit {result.exit_code})")

    domain_plan = _parse_plan_response(result.stdout)
    if not domain_plan:
        raise RuntimeError(f"Phase 2: could not parse domain '{domain['name']}' plan JSON")

    changes = domain_plan.get("changes", [])
    logger.info("Phase 2: domain '%s' → %d changes", domain["name"], len(changes))
    return domain_plan


def _phase2_parallel_decompose(
    domain_data: dict,
    planning_brief: dict,
    *,
    test_infra_context: str = "",
    design_context: str = "",
    digest_dir: str = "",
    model: str = "opus",
    max_parallel: int = 3,
) -> dict[str, dict]:
    """Phase 2: Decompose all domains in parallel."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    domains = domain_data["domains"]
    if not domains:
        return {}

    brief_json = json.dumps(planning_brief, indent=2)
    conventions = domain_data["conventions"]

    results: dict[str, dict] = {}
    max_workers = min(len(domains), 6)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _decompose_single_domain,
                domain,
                brief_json,
                conventions,
                test_infra_context=test_infra_context,
                design_context=design_context,
                test_plan_context=_build_test_plan_context(
                    digest_dir,
                    [r.get("id", "") for r in domain.get("requirements", [])],
                ) if digest_dir else "",
                model=model,
                max_parallel=max_parallel,
            ): domain["name"]
            for domain in domains
        }

        for future in as_completed(futures):
            domain_name = futures[future]
            results[domain_name] = future.result()  # raises if domain failed

    logger.info("Phase 2 complete: %d domains decomposed", len(results))
    return results


def _phase3_merge_plans(
    domain_plans: dict[str, dict],
    planning_brief: dict,
    domain_data: dict,
    *,
    coverage_info: str = "",
    replan_ctx: dict | None = None,
    model: str = "opus",
) -> dict:
    """Phase 3: Merge domain plans into unified orchestration plan."""
    from .subprocess_utils import run_claude_logged
    from .templates import render_merge_prompt

    # Format domain plans for the prompt
    plan_parts = []
    for domain_name, plan in sorted(domain_plans.items()):
        changes = plan.get("changes", [])
        plan_parts.append(f"### Domain: {domain_name} ({len(changes)} changes)\n{json.dumps(plan, indent=2)}")

    # Add cross-cutting changes from brief
    cc_changes = planning_brief.get("cross_cutting_changes", [])
    if cc_changes:
        plan_parts.append(f"### Cross-Cutting Changes (from planning brief)\n{json.dumps(cc_changes, indent=2)}")

    prompt = render_merge_prompt(
        domain_plans="\n\n".join(plan_parts),
        planning_brief=json.dumps(planning_brief, indent=2),
        dependencies=domain_data["dependencies"],
        ambiguities=domain_data["ambiguities"],
        coverage_info=coverage_info,
        replan_ctx=replan_ctx,
    )

    logger.info("Phase 3: merging %d domain plans", len(domain_plans))
    result = run_claude_logged(prompt, purpose="decompose_merge", timeout=900, model=model, extra_args=["--max-turns", "5"])
    if result.exit_code != 0:
        raise RuntimeError(f"Phase 3 (merge) failed (exit {result.exit_code})")

    merged_plan = _parse_plan_response(result.stdout)
    if not merged_plan:
        raise RuntimeError("Phase 3: could not parse merged plan JSON")

    total_changes = len(merged_plan.get("changes", []))
    logger.info("Phase 3 complete: %d total changes in merged plan", total_changes)
    return merged_plan


def _save_domain_plans(
    planning_brief: dict,
    domain_plans: dict[str, dict],
) -> None:
    """Save Phase 1 brief and Phase 2 domain plans for selective replan."""
    domains_file = os.path.join(os.getcwd(), "orchestration-plan-domains.json")
    data = {
        "brief": planning_brief,
        "domain_plans": domain_plans,
        "created_at": datetime.now().astimezone().isoformat(),
    }
    with open(domains_file, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Saved domain plans to %s", domains_file)


def _try_domain_parallel_decompose(
    digest_dir: str,
    state_path: str,
    test_infra_context: str,
    design_context: str,
    model: str,
    max_parallel: int,
    replan_ctx: dict | None,
    team_mode: bool,
) -> dict | None:
    """Try the 3-phase domain-parallel decompose. Returns plan_data or raises."""
    logger.info("Using domain-parallel decompose pipeline")

    domain_data = _load_domain_data(digest_dir)

    # Gather existing specs summary
    existing_specs = ""
    try:
        specs_dir = os.path.join(os.getcwd(), "openspec", "specs")
        if os.path.isdir(specs_dir):
            spec_names = [d.name for d in Path(specs_dir).iterdir() if d.is_dir()]
            if spec_names:
                existing_specs = "Existing specs: " + ", ".join(sorted(spec_names))
    except Exception:
        pass

    # Coverage info
    coverage_info = ""
    try:
        from .digest import check_coverage_gaps
        coverage_info = check_coverage_gaps(state_path, digest_dir) if state_path else ""
    except Exception:
        pass

    # Phase 1: Planning Brief
    planning_brief = _phase1_planning_brief(
        domain_data,
        test_infra_context=test_infra_context,
        existing_specs=existing_specs,
        model=model,
        max_parallel=max_parallel,
    )

    # Phase 2: Domain Decompose (parallel)
    domain_plans = _phase2_parallel_decompose(
        domain_data,
        planning_brief,
        test_infra_context=test_infra_context,
        design_context=design_context,
        digest_dir=digest_dir,
        model=model,
        max_parallel=max_parallel,
    )

    # Save domain plans for selective replan
    _save_domain_plans(planning_brief, domain_plans)

    # Phase 3: Merge & Resolve
    return _phase3_merge_plans(
        domain_plans,
        planning_brief,
        domain_data,
        coverage_info=coverage_info,
        replan_ctx=replan_ctx,
        model=model,
    )


# ─── Planning Pipeline ────────────────────────────────────────────────


def run_planning_pipeline(
    input_mode: str,
    input_path: str,
    *,
    state_path: str = "",
    model: str = "opus",
    team_mode: bool = False,
    replan_ctx: dict | None = None,
    replan_cycle: int | None = None,
) -> dict:
    """Orchestrate the full planning flow in Python.

    Steps: input detection → freshness check → triage gate → design bridge →
    Claude call → response parse → plan enrichment.

    Args:
        input_mode: "brief", "spec", or "digest".
        input_path: Path to input file or digest directory.
        state_path: Path to state file (for replan context).
        model: Model to use for Claude call.
        team_mode: Enable team mode in decomposition.
        replan_ctx: Replan context dict (if replanning).
        replan_cycle: Replan cycle number (if replanning).

    Returns:
        Enriched plan dict ready to write.

    Raises:
        RuntimeError: If planning fails.
    """
    from .subprocess_utils import run_claude_logged

    # 1. Freshness check for digest mode
    if input_mode == "digest":
        from .digest import check_digest_freshness
        freshness = check_digest_freshness(input_path)
        if freshness == "stale":
            logger.warning("Digest is stale — consider re-running set-orchestrate digest")

    # 2. Triage gate
    digest_dir = os.path.join(os.getcwd(), "set", "orchestration", "digest") if input_mode == "digest" else ""
    if digest_dir:
        triage_status = check_triage_gate(digest_dir)
        if triage_status.status in ("needs_triage", "has_untriaged", "has_fixes"):
            auto_defer = os.environ.get("TRIAGE_AUTO_DEFER", "false") == "true"
            if auto_defer:
                logger.info("Triage: auto-deferring %d ambiguities", triage_status.count)
                check_triage_gate(digest_dir, auto_defer=True)
            else:
                raise RuntimeError(
                    f"Triage gate: {triage_status.count} unresolved ambiguities block planning. "
                    f"Status: {triage_status.status}. Edit triage.md or set TRIAGE_AUTO_DEFER=true."
                )

    # 3. Design context: v0 pipeline uses per-change design-source/ populated
    #    by the dispatcher, not a global snapshot at plan time. The planner
    #    still reads v0-export/globals.css tokens + design-manifest.yaml for
    #    design awareness, when they exist.
    design_context = _fetch_design_context(force=bool(replan_ctx))

    # 4. Test infra detection
    test_infra = detect_test_infra()
    test_infra_context = ""
    if test_infra.test_command:
        test_infra_context = f"Test command: {test_infra.test_command}"

    # Compute input hash for metadata
    input_hash = ""
    try:
        if os.path.isfile(input_path):
            input_hash = hashlib.sha256(Path(input_path).read_bytes()).hexdigest()
        elif os.path.isdir(input_path):
            input_hash = hashlib.sha256(input_path.encode()).hexdigest()
    except OSError:
        pass

    # Read max_parallel from directives
    max_parallel = 3
    try:
        _sp = os.path.join(os.getcwd(), "orchestration-state.json")
        if os.path.isfile(_sp):
            with open(_sp) as _sf:
                _sd = json.load(_sf)
            max_parallel = _sd.get("extras", {}).get("directives", {}).get("max_parallel", 3)
    except Exception:
        pass

    # 5. Domain-parallel decompose (digest mode) or single-call (brief/spec)
    # Threshold: domain-parallel only for large specs (30+ requirements)
    DOMAIN_PARALLEL_MIN_REQS = 30

    if input_mode == "digest":
        # Count requirements to decide decompose strategy
        req_count = 0
        try:
            req_path = os.path.join(digest_dir, "requirements.json")
            if os.path.isfile(req_path):
                with open(req_path) as _rf:
                    req_count = len(json.load(_rf).get("requirements", []))
        except Exception:
            pass

        plan_data = None
        if req_count >= DOMAIN_PARALLEL_MIN_REQS:
            # Large spec: try domain-parallel pipeline
            try:
                plan_data = _try_domain_parallel_decompose(
                    digest_dir, state_path, test_infra_context, design_context,
                    model, max_parallel, replan_ctx, team_mode,
                )
            except Exception as e:
                logger.warning("Domain-parallel decompose failed (%s) — falling back to single-call", e)
        else:
            logger.info("Small spec (%d reqs < %d threshold) — using single-call decompose", req_count, DOMAIN_PARALLEL_MIN_REQS)

        if plan_data is None:
            # Fallback: single-call decompose (same path as brief/spec mode)
            logger.info("Using single-call decompose fallback for digest mode")
            context = build_decomposition_context(
                input_mode, input_path,
                replan_ctx=replan_ctx,
                design_context=design_context,
                test_infra_context=test_infra_context,
                team_mode=team_mode,
            )
            from .templates import render_planning_prompt
            prompt = render_planning_prompt(**context)
            result = run_claude_logged(prompt, purpose="decompose", timeout=1800, model=model, extra_args=["--max-turns", "10"])
            if result.exit_code != 0:
                raise RuntimeError(f"Claude decomposition failed (exit {result.exit_code})")
            plan_data = _parse_plan_response(result.stdout)
            if not plan_data:
                raise RuntimeError("Could not parse decomposition response")
    else:
        # ── Single-call flow for brief/spec mode ──
        context = build_decomposition_context(
            input_mode, input_path,
            replan_ctx=replan_ctx,
            design_context=design_context,
            test_infra_context=test_infra_context,
            team_mode=team_mode,
        )

        from .templates import render_planning_prompt
        prompt = render_planning_prompt(**context)

        result = run_claude_logged(prompt, purpose="decompose", timeout=1800, model=model, extra_args=["--max-turns", "10"])
        if result.exit_code != 0:
            raise RuntimeError(f"Claude planning call failed (exit {result.exit_code})")

        plan_data = _parse_plan_response(result.stdout)
        if not plan_data:
            debug_path = Path("/tmp/set-decompose-response.txt")
            debug_path.write_text(result.stdout[:10000] if result.stdout else "(empty)")
            logger.error("Decompose response dumped to %s (len=%d)", debug_path, len(result.stdout or ""))
            raise RuntimeError("Could not parse plan JSON from Claude response")

    # 8. Validate
    plan_file_tmp = "/tmp/set-plan-validate.json"
    with open(plan_file_tmp, "w") as f:
        json.dump(plan_data, f, indent=2)

    _max_ct = max_parallel * 2
    validation = validate_plan(plan_file_tmp, max_change_target=_max_ct)
    if not validation.ok:
        logger.warning("Plan validation issues (max_change_target=%d): %s", _max_ct, validation.errors)

    # 9. Enrich metadata
    plan_data = enrich_plan_metadata(
        plan_data,
        input_hash,
        input_mode,
        input_path,
        replan_cycle=replan_cycle,
        state_path=state_path,
    )

    return plan_data


def plan_via_agent(
    spec_path: str,
    plan_filename: str,
    phase_hint: str = "",
) -> bool:
    """Agent-based planning via worktree + Ralph loop.

    Creates a planning worktree, dispatches Ralph with the decomposition
    skill, waits for completion, extracts orchestration-plan.json.

    Args:
        spec_path: Path to the spec input file.
        plan_filename: Path to write the resulting plan.
        phase_hint: Optional phase to focus on.

    Returns:
        True if plan was successfully extracted and validated.
    """
    from .subprocess_utils import run_command

    # Determine planning worktree name
    plan_version = 1
    if os.path.isfile(plan_filename):
        try:
            with open(plan_filename) as f:
                plan_version = json.load(f).get("plan_version", 0) + 1
        except (json.JSONDecodeError, OSError):
            pass
    wt_name = f"set-planning-v{plan_version}"

    logger.info("plan_via_agent: starting (spec=%s, phase_hint=%s)", spec_path, phase_hint)

    # Create planning worktree
    result = run_command(["set-new", wt_name], timeout=30)
    wt_path = result.stdout.strip() if result.exit_code == 0 else ""

    if not wt_path or not Path(wt_path).is_dir():
        # Try finding it
        find_result = run_command(
            ["git", "worktree", "list", "--porcelain"], timeout=10
        )
        for line in find_result.stdout.splitlines():
            if line.startswith("worktree ") and wt_name in line:
                wt_path = line.replace("worktree ", "").strip()
                break
        if not wt_path or not Path(wt_path).is_dir():
            logger.error("plan_via_agent: worktree path not found for %s", wt_name)
            return False

    logger.info("plan_via_agent: worktree at %s", wt_path)

    # Build task description
    task_desc = f"Decompose the specification at '{spec_path}' into an orchestration execution plan."
    if phase_hint:
        task_desc += f" Focus on phase: {phase_hint}."
    task_desc += " Use the /set:decompose skill. Write the result to orchestration-plan.json in the project root."

    # Dispatch Ralph loop
    env = dict(os.environ)
    env["SPEC_PATH"] = spec_path
    if phase_hint:
        env["PHASE_HINT"] = phase_hint

    loop_result = run_command(
        ["set-loop", "start", task_desc, "--max", "10", "--model", "opus",
         "--label", wt_name, "--change", wt_name],
        timeout=1800,
        cwd=wt_path,
        env=env,
    )

    # Check if plan was produced
    agent_plan = Path(wt_path) / "orchestration-plan.json"
    if not agent_plan.is_file():
        logger.error("plan_via_agent: no plan produced (loop rc=%d)", loop_result.exit_code)
        run_command(["set-close", wt_name, "--force"], timeout=30)
        return False

    # Validate
    validation = validate_plan(str(agent_plan))
    if not validation.ok:
        logger.error("plan_via_agent: plan failed validation: %s", validation.errors)
        run_command(["set-close", wt_name, "--force"], timeout=30)
        return False

    # Extract plan
    import shutil
    shutil.copy2(str(agent_plan), plan_filename)
    logger.info("plan_via_agent: plan extracted from %s", agent_plan)

    # Add agent metadata
    try:
        with open(plan_filename) as f:
            plan_data = json.load(f)
        plan_data["planning_worktree"] = wt_name
        with open(plan_filename, "w") as f:
            json.dump(plan_data, f, indent=2)
    except (json.JSONDecodeError, OSError):
        pass

    # Cleanup
    run_command(["set-close", wt_name, "--force"], timeout=30)
    return True



def _fetch_design_context(force: bool = False) -> str:
    """Load design context for the planner (v0 pipeline).

    The planner needs to see EVERY manifest route (so it can bind each
    route to a change). Earlier drafts capped the combined output at
    5000 chars and truncated the manifest mid-route on large scaffolds
    (22+ routes). We now:

      - never truncate the manifest (planner correctness depends on it)
      - extract ONLY the :root CSS-variable block from globals.css
        (strips prose/comments, keeps every token)
      - leave the non-authoritative vibe brief untruncated

    Args:
        force: ignored (kept for signature compatibility).

    Returns:
        design context string (no hard size cap) or empty string.
    """
    parts: list[str] = []

    manifest_path = Path("docs") / "design-manifest.yaml"
    if manifest_path.is_file():
        try:
            parts.append("## Design Manifest (routes)\n" + manifest_path.read_text())
        except OSError:
            pass

    globals_candidates = [
        Path("shadcn") / "globals.css",
        Path("v0-export") / "app" / "globals.css",
    ]
    for g in globals_candidates:
        if g.is_file():
            try:
                root_block = _extract_globals_root_block(g)
                if root_block:
                    parts.append("## Design Tokens (globals.css :root)\n" + root_block)
                    break
            except OSError:
                continue

    brief = Path("docs") / "design-brief.md"
    if brief.is_file():
        try:
            body = brief.read_text(errors="replace")
            if body.strip():
                parts.append("## Design Vibe Notes (non-authoritative)\n" + body)
        except OSError:
            pass

    if not parts:
        logger.info("No v0 design manifest or globals.css — planner runs without design context")
        return ""
    return "\n\n".join(parts)


def _extract_globals_root_block(css_path: Path) -> str:
    """Return the :root { ... } block from a CSS file, or "" if absent.

    Keeps every CSS custom property declaration — no per-token cap —
    because the planner uses these to decide which semantic tokens
    exist in the theme (and thus what the agent will find in
    design-source/).
    """
    import re as _re

    text = css_path.read_text(errors="replace")
    m = _re.search(r":root\s*\{[^}]*\}", text, _re.DOTALL)
    return m.group(0) if m else ""


def _parse_plan_response(response_text: str) -> dict | None:
    """Extract plan JSON from Claude response text."""
    text = response_text.strip()

    # Direct parse
    try:
        data = json.loads(text)
        if "changes" in data:
            logger.debug("Plan response parsed: direct JSON (%d changes)", len(data.get("changes", [])))
            return data
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if "changes" in data:
                logger.debug("Plan response parsed: markdown fence (%d changes)", len(data.get("changes", [])))
                return data
        except json.JSONDecodeError:
            pass

    # Brace scanning
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        try:
            data = json.loads(text[first:last + 1])
            if "changes" in data:
                logger.debug("Plan response parsed: brace scan (%d changes)", len(data.get("changes", [])))
                return data
        except json.JSONDecodeError:
            pass

    logger.warning("Plan response parse failed: no valid JSON with 'changes' key (response length=%d)", len(text))
    return None
