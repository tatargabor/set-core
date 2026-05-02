"""Verifier: change verification, testing, review, smoke tests, gate pipeline.

Migrated from: lib/orchestration/verifier.sh (run_tests_in_worktree,
build_req_review_section, review_change, evaluate_verification_rules,
verify_merge_scope, verify_implementation_scope, extract_health_check_url,
health_check, smoke_fix_scoped, run_phase_end_e2e, poll_change,
handle_change_done)
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .events import EventBus
from .config import DIRECTIVE_DEFAULTS
from .notifications import send_notification
from .process import check_pid
from .state import (
    Change,
    OrchestratorState,
    load_state,
    locked_state,
    update_change_field,
    update_state_field,
)
from .subprocess_utils import CommandResult, detect_default_branch, run_claude, run_claude_logged, run_command, run_git
from .truncate import smart_truncate, smart_truncate_structured, truncate_with_budget

logger = logging.getLogger(__name__)

# Paths considered non-implementation (filtered in scope checks)
# Source: verifier.sh verify_merge_scope / verify_implementation_scope
ARTIFACT_PREFIXES = (
    "openspec/changes/",
    "openspec/specs/",
    ".claude/",
    "orchestration",
    ".set-core/",
)

BOOTSTRAP_FILES = {
    "prisma/dev.db", ".gitignore",
}

BOOTSTRAP_PATTERNS = ("*.lock", "*-lock.yaml", "*.lockb", "jest.config.*", "jest.setup.*", ".env*")

# Default timeouts
DEFAULT_TEST_TIMEOUT = 600
DEFAULT_SMOKE_TIMEOUT = 180

# Context window sizes for Claude 4.x models
CONTEXT_WINDOW_SIZE = 200_000  # legacy/standard window
CONTEXT_WINDOW_SIZE_1M = 1_000_000  # default for Claude 4.x family in 2026


def _context_window_for_model(model: str = "") -> int:
    """Return context window size based on model name.

    Default: 1M (Claude 4.x family). Use explicit [200k] suffix for legacy.
    """
    m = model.lower()
    if "[200k]" in m or "200k" in m:
        return CONTEXT_WINDOW_SIZE
    # All Claude 4.x models default to 1M (opus, sonnet, haiku, claude-opus-4-x, etc.)
    return CONTEXT_WINDOW_SIZE_1M
DEFAULT_SMOKE_FIX_MAX_RETRIES = 3
DEFAULT_SMOKE_FIX_MAX_TURNS = 15
DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT = 30
DEFAULT_MAX_VERIFY_RETRIES = 2
# DEPRECATED — kept as an empty string for any external import. Code
# inside this module uses model_config.resolve_model("review") at call
# time so operator overrides via orchestration.yaml::models.review take
# effect without restart.
DEFAULT_REVIEW_MODEL = ""
DEFAULT_E2E_TIMEOUT = 3600  # 1h ceiling. 600s/1200s caused repeated false timeouts on
# realistic web suites (>50 routes, prisma seed, next build, 100+ tests). The gate
# is fail-closed on real timeout — a high ceiling just gives slow infra room without
# masking regressions. See OpenSpec change: fix-retry-context-signal-loss audit.
E2E_HEALTH_TIMEOUT = 30  # seconds; override via config e2e_health_timeout

# ─── Data Structures ────────────────────────────────────────────────

@dataclass
class TestResult:
    """Result of running tests in a worktree."""
    passed: bool
    output: str
    exit_code: int
    stats: dict | None = None  # {passed: N, failed: N, suites: N, type: "jest"|"playwright"}


@dataclass
class ReviewResult:
    """Result of LLM code review."""
    has_critical: bool
    output: str


def _classifier_enabled(state_file: str) -> bool:
    """Read the llm_verdict_classifier_enabled directive from state.

    Defaults to True — the classifier is on by default as a safety net
    against the two known silent-pass incidents. Operators can disable
    it via `llm_verdict_classifier_enabled: false` in orchestration
    config if Sonnet cost becomes a concern.
    """
    if not state_file:
        return True
    try:
        from .state import load_state
        state = load_state(state_file)
        directives = state.extras.get("directives", {}) if state else {}
        return bool(directives.get("llm_verdict_classifier_enabled", True))
    except Exception as exc:
        logger.debug("_classifier_enabled: defaulting to True (error reading state: %s)", exc)
        return True


def _extract_review_fixes(review_output: str) -> str:
    """Extract structured FILE+LINE+FIX blocks from review output.

    Parses the review format:
        ISSUE: [CRITICAL] description
        FILE: path/to/file
        LINE: ~42
        FIX: concrete code fix

    Returns a concise fix list for the retry prompt.
    """
    fixes = []
    current_file = ""
    current_line = ""
    current_issue = ""
    current_fix = ""

    for line in review_output.split("\n"):
        stripped = line.strip()
        if stripped.startswith("ISSUE:"):
            # Save previous block if exists
            if current_file and (current_fix or current_issue):
                fixes.append(
                    f"- {current_file}:{current_line} — {current_issue}\n"
                    f"  FIX: {current_fix}" if current_fix else
                    f"- {current_file}:{current_line} — {current_issue}"
                )
            current_issue = stripped[6:].strip()
            current_file = ""
            current_line = ""
            current_fix = ""
        elif stripped.startswith("FILE:"):
            current_file = stripped[5:].strip().strip("`")
        elif stripped.startswith("LINE:"):
            current_line = stripped[5:].strip().lstrip("~")
        elif stripped.startswith("FIX:") or stripped.startswith("Fix:"):
            current_fix = stripped[4:].strip()

    # Don't forget last block
    if current_file and (current_fix or current_issue):
        fixes.append(
            f"- {current_file}:{current_line} — {current_issue}\n"
            f"  FIX: {current_fix}" if current_fix else
            f"- {current_file}:{current_line} — {current_issue}"
        )

    return "\n".join(fixes)


def _parse_review_issues(review_output: str) -> list[dict]:
    """Parse review output into structured issue dicts.

    Severity is derived ONLY from the inline `[LOW|MEDIUM|HIGH|CRITICAL]`
    tag on the `ISSUE:` line — single source of truth. A secondary body
    or summary scan would produce the severity drift observed in the
    log audit (9/30 findings where inline tag and summary scan disagreed).

    Reuses the same format as _extract_review_fixes but returns structured data
    instead of a text string. Each issue has: severity, summary, file, line, fix.

    NOTE: this parser only handles the first-round review format
    (`ISSUE: [TAG]` inline). Retry reviews use a different markdown
    structure (`### Finding N:` headers, `**NOT_FIXED** [CRITICAL]`
    annotations) that this parser does NOT recognise — that format is
    handled by the LLM verdict classifier fallback in `review_change()`.
    """
    issues = []
    current: dict = {}

    for line in review_output.split("\n"):
        stripped = line.strip()
        if stripped.startswith("ISSUE:") or stripped.startswith("**ISSUE:"):
            if current.get("summary"):
                issues.append(current)
            text = stripped.lstrip("*").lstrip()
            if text.startswith("ISSUE:"):
                text = text[6:].strip()
            # Severity: inline [TAG] on the ISSUE line is the single
            # source of truth. Default to MEDIUM when no tag is present
            # (matches long-standing behaviour; the classifier fallback
            # handles unusual formats).
            severity = "MEDIUM"
            if "[CRITICAL]" in text:
                severity = "CRITICAL"
            elif "[HIGH]" in text:
                severity = "HIGH"
            elif "[LOW]" in text:
                severity = "LOW"
            current = {"severity": severity, "summary": text, "file": "", "line": "", "fix": ""}
        elif stripped.startswith("FILE:") or stripped.startswith("**FILE:"):
            current["file"] = stripped.lstrip("*").lstrip()[5:].strip().strip("`")
        elif stripped.startswith("LINE:"):
            current["line"] = stripped[5:].strip().lstrip("~")
        elif stripped.startswith("FIX:") or stripped.startswith("Fix:"):
            current["fix"] = stripped[4:].strip()

    if current.get("summary"):
        issues.append(current)

    return issues


def _append_review_finding(findings_path: str, change_name: str,
                           review_output: str, attempt: int) -> None:
    """Append structured review findings to JSONL log.

    Called when a review gate finds issues (any severity). The JSONL file
    is read at run end to generate the review findings summary.
    """
    issues = _parse_review_issues(review_output)
    if not issues:
        return

    entry = {
        "change": change_name,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "attempt": attempt,
        "issue_count": len(issues),
        "critical_count": sum(1 for i in issues if i["severity"] == "CRITICAL"),
        "high_count": sum(1 for i in issues if i["severity"] == "HIGH"),
        "issues": issues,
    }

    try:
        os.makedirs(os.path.dirname(findings_path), exist_ok=True)
        with open(findings_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        logger.warning(
            "Review finding lost — cannot write to %s: %s",
            findings_path, e,
        )


def generate_review_findings_summary(findings_path: str, output_path: str) -> str:
    """Generate a markdown summary of all review findings from a run.

    Reads the JSONL log, groups issues by pattern, and writes a summary
    that can be used for post-run analysis and rules improvement.

    Returns the output path, or empty string if no findings.
    """
    if not os.path.isfile(findings_path):
        return ""

    entries = []
    try:
        with open(findings_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to read review findings from %s", findings_path)
        return ""

    if not entries:
        return ""

    # Collect all issues and group by pattern (normalized summary)
    all_issues: list[dict] = []
    for entry in entries:
        for issue in entry.get("issues", []):
            all_issues.append({**issue, "change": entry["change"], "attempt": entry["attempt"]})

    # Group by severity
    critical = [i for i in all_issues if i["severity"] == "CRITICAL"]
    high = [i for i in all_issues if i["severity"] == "HIGH"]

    # Deduplicate by (change, summary_prefix) — same issue across retries
    seen = set()
    unique_issues = []
    for issue in all_issues:
        key = (issue["change"], issue["summary"][:60])
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    # Group by change
    by_change: dict[str, list[dict]] = {}
    for issue in unique_issues:
        by_change.setdefault(issue["change"], []).append(issue)

    # Build summary
    lines = ["# Review Findings Summary\n"]
    lines.append(f"**Total findings**: {len(unique_issues)} unique issues "
                 f"({len(critical)} CRITICAL, {len(high)} HIGH) "
                 f"across {len(by_change)} change(s)\n")

    # Recurring patterns (appear in 2+ changes)
    pattern_counts: dict[str, int] = {}
    for issue in unique_issues:
        # Normalize: strip severity tag, take first 50 chars
        norm = re.sub(r"\[(?:CRITICAL|HIGH|MEDIUM)\]\s*", "", issue["summary"])[:50]
        pattern_counts[norm] = pattern_counts.get(norm, 0) + 1

    recurring = {k: v for k, v in pattern_counts.items() if v >= 2}
    if recurring:
        lines.append("## Recurring Patterns\n")
        for pattern, count in sorted(recurring.items(), key=lambda x: -x[1]):
            lines.append(f"- **{pattern}**: {count} occurrences")
        lines.append("")

    # Per-change details
    lines.append("## Per-Change Details\n")
    for change_name, issues in sorted(by_change.items()):
        crits = sum(1 for i in issues if i["severity"] == "CRITICAL")
        lines.append(f"### {change_name} ({crits} CRITICAL, {len(issues)} total)\n")
        for issue in issues:
            sev = issue["severity"]
            lines.append(f"- **[{sev}]** {issue['summary']}")
            if issue.get("file"):
                lines.append(f"  - File: `{issue['file']}`{' L' + issue['line'] if issue.get('line') else ''}")
            if issue.get("fix"):
                lines.append(f"  - Fix: {issue['fix']}")
        lines.append("")

    content = "\n".join(lines)
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)
        logger.info("Review findings summary written: %s (%d issues)", output_path, len(unique_issues))
    except OSError:
        logger.warning("Failed to write review findings summary to %s", output_path)
        return ""

    return output_path


# ─── Build Error & Test Failure Parsers ──────────────────────────────

# TypeScript error: src/file.tsx(67,5): error TS2339: Property 'x' does not exist
_TS_ERROR_RE = re.compile(
    r"^(.+?)\((\d+),\d+\):\s*error\s+(TS\d+):\s*(.+)$", re.MULTILINE
)
# TypeScript error alt format: src/file.tsx:67:5 - error TS2339: Property 'x' does not exist
_TS_ERROR_ALT_RE = re.compile(
    r"^(.+?):(\d+):\d+\s*-\s*error\s+(TS\d+):\s*(.+)$", re.MULTILINE
)
# Next.js module not found: Module not found: Can't resolve 'foo' in '/path/to/dir'
_MODULE_NOT_FOUND_RE = re.compile(
    r"Module not found:\s*(?:Can't resolve\s*)?'([^']+)'", re.MULTILINE
)
# Next.js route export violation
_ROUTE_EXPORT_RE = re.compile(
    r"(?:\"([^\"]+)\")\s+is not a valid (?:Next\.js )?(?:route|page) export", re.MULTILINE
)


def _extract_build_errors(build_output: str) -> str:
    """Extract structured build errors from TypeScript/Next.js output.

    Returns formatted lines like:
        - src/file.tsx:67 — TS2339: Property 'x' does not exist on type 'Y'

    Falls back to empty string if no known patterns match.
    """
    errors: list[str] = []
    seen: set[str] = set()

    for m in _TS_ERROR_RE.finditer(build_output):
        key = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
        if key not in seen:
            seen.add(key)
            errors.append(f"- {m.group(1)}:{m.group(2)} — {m.group(3)}: {m.group(4)}")

    for m in _TS_ERROR_ALT_RE.finditer(build_output):
        key = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
        if key not in seen:
            seen.add(key)
            errors.append(f"- {m.group(1)}:{m.group(2)} — {m.group(3)}: {m.group(4)}")

    for m in _MODULE_NOT_FOUND_RE.finditer(build_output):
        entry = f"- Module not found: '{m.group(1)}'"
        if entry not in errors:
            errors.append(entry)

    for m in _ROUTE_EXPORT_RE.finditer(build_output):
        errors.append(f"- Invalid route export: \"{m.group(1)}\"")

    return "\n".join(errors)


# Jest/Vitest FAIL pattern: FAIL src/tests/foo.test.ts
_TEST_FAIL_BLOCK_RE = re.compile(r"^\s*(?:FAIL)\s+(.+?)$", re.MULTILINE)
# Test name + assertion: ✕ should calculate shipping (5 ms)
_TEST_NAME_RE = re.compile(r"^\s*[✕×✗●]\s+(.+?)(?:\s+\(\d+\s*m?s\))?\s*$", re.MULTILINE)
# Expected/received: Expected: 1500 / Received: undefined
_EXPECTED_RE = re.compile(r"^\s*Expected:\s*(.+)$", re.MULTILINE)
_RECEIVED_RE = re.compile(r"^\s*Received:\s*(.+)$", re.MULTILINE)


def _extract_test_failures(test_output: str) -> str:
    """Extract structured test failures from Jest/Vitest output.

    Returns formatted lines like:
        - checkout.test.ts: "should calculate shipping" — Expected 1500, received undefined
    """
    failures: list[str] = []

    # Find FAIL file blocks
    fail_files = _TEST_FAIL_BLOCK_RE.findall(test_output)

    # Find failed test names
    test_names = _TEST_NAME_RE.findall(test_output)

    # Find expected/received pairs
    expected_matches = _EXPECTED_RE.findall(test_output)
    received_matches = _RECEIVED_RE.findall(test_output)

    if test_names:
        for i, name in enumerate(test_names):
            file_ctx = fail_files[0].strip() if fail_files else ""
            assertion = ""
            if i < len(expected_matches) and i < len(received_matches):
                assertion = f" — Expected {expected_matches[i].strip()}, received {received_matches[i].strip()}"
            if file_ctx:
                failures.append(f"- {file_ctx}: \"{name}\"{assertion}")
            else:
                failures.append(f"- \"{name}\"{assertion}")
    elif fail_files:
        # No individual test names extracted, list failing files
        for f in fail_files:
            failures.append(f"- FAIL {f.strip()}")

    return "\n".join(failures)


# ─── Unified Retry Context ──────────────────────────────────────────


def _render_cached_gates_section(change: "Change | None") -> str:
    """Render a '## Cached Gates' section for the retry prompt.

    Section 12.15 of fix-replan-stuck-gate-and-decomposer. Lists every gate
    whose prior verdict is currently being reused (consecutive_cache_uses
    > 0). The agent uses this to know which prior findings still hold.

    Returns "" when there are no cached gates to report.
    """
    if change is None:
        return ""
    tracking = getattr(change, "gate_retry_tracking", None) or {}
    cached_entries = [
        (name, entry) for name, entry in tracking.items()
        if entry and getattr(entry, "consecutive_cache_uses", 0) > 0
    ]
    if not cached_entries:
        return ""
    lines = ["## Cached Gates"]
    lines.append(
        "The following gates reused their prior verdict (no re-run) — "
        "their findings still apply unless you've modified their scope:",
    )
    cached_entries.sort(key=lambda kv: kv[0])
    for name, entry in cached_entries:
        sha = (entry.last_verdict_sha or "?")[:8]
        reuses = entry.consecutive_cache_uses
        lines.append(f"- **{name}** — reused from {sha} ({reuses}× consecutive)")
    return "\n".join(lines)


def _build_unified_retry_context(
    build_output: str = "",
    test_output: str = "",
    review_output: str = "",
    attempt: int = 1,
    max_attempts: int = 3,
    change_name: str = "",
    findings_path: str = "",
    change: "Change | None" = None,
) -> str:
    """Build a single structured retry block combining all gate results.

    Replaces ad-hoc truncated raw dumps with parsed, actionable sections.
    When findings_path and change_name are provided, includes prior review
    findings from the JSONL log for additional context.
    """
    sections: list[str] = []
    sections.append(f"## Retry Context (Attempt {attempt}/{max_attempts})")
    sections.append("")
    sections.append(
        "Before fixing, re-read the files listed below. "
        "Do NOT rely on your memory of the file contents."
    )

    if build_output:
        parsed = _extract_build_errors(build_output)
        sections.append("\n### Build Errors")
        if parsed:
            sections.append(parsed)
        else:
            # Unknown build format — fall back to truncated raw
            sections.append(f"```\n{smart_truncate_structured(build_output, 3000)}\n```")

    if test_output:
        parsed = _extract_test_failures(test_output)
        sections.append("\n### Test Failures")
        if parsed:
            sections.append(parsed)
        else:
            sections.append(f"```\n{smart_truncate_structured(test_output, 3000)}\n```")

    if review_output:
        parsed = _extract_review_fixes(review_output)
        sections.append("\n### Review Issues")
        if parsed:
            sections.append(parsed)
        else:
            # Parser returned nothing — retry-round format (`### Finding N:`)
            # or non-standard output. Include a large raw dump so the agent
            # can pair FILE/LINE/FIX by finding instead of guessing.
            sections.append(f"```\n{smart_truncate_structured(review_output, 30_000)}\n```")

    # Include prior review findings from JSONL if available
    if change_name and findings_path:
        prior = _read_prior_review_findings(findings_path, change_name)
        if prior:
            sections.append(prior)

    # Section 12.15: surface cached-gate verdicts so the agent knows
    # which prior findings still hold.
    cached = _render_cached_gates_section(change)
    if cached:
        sections.append("")
        sections.append(cached)

    return "\n".join(sections)


def _read_prior_review_findings(findings_path: str, change_name: str) -> str:
    """Read prior review findings for a change from the JSONL log.

    Returns formatted section string, or empty string if no findings.
    """
    if not os.path.isfile(findings_path):
        return ""

    try:
        matching_issues: list[dict] = []
        with open(findings_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("change") != change_name:
                    continue
                for issue in entry.get("issues", []):
                    matching_issues.append(issue)

        if not matching_issues:
            return ""

        # Deduplicate by (summary[:60])
        seen: set[str] = set()
        unique: list[dict] = []
        for issue in matching_issues:
            key = issue.get("summary", "")[:60]
            if key not in seen:
                seen.add(key)
                unique.append(issue)

        lines = ["\n### Prior Review Findings"]
        lines.append(f"Previous reviews found {len(unique)} issue(s) for this change:")
        for issue in unique[:10]:  # Cap at 10 to avoid prompt bloat
            sev = issue.get("severity", "?")
            summary = issue.get("summary", "")
            file_path = issue.get("file", "")
            line_num = issue.get("line", "")
            loc = f" ({file_path}" + (f" L{line_num}" if line_num else "") + ")" if file_path else ""
            lines.append(f"- **[{sev}]** {summary}{loc}")
        return "\n".join(lines)

    except OSError:
        return ""


# ─── Cumulative Review Feedback ─────────────────────────────────────


def _append_review_history(
    state_file: str, change_name: str, entry: dict,
) -> None:
    """Append a review attempt entry to change.extras.review_history."""
    with locked_state(state_file) as st:
        for c in st.changes:
            if c.name == change_name:
                history = c.extras.get("review_history", [])
                history.append(entry)
                c.extras["review_history"] = history
                break


def _get_review_history(state_file: str, change_name: str) -> list[dict]:
    """Read review_history from change extras."""
    state = load_state(state_file)
    for c in state.changes:
        if c.name == change_name:
            return c.extras.get("review_history", [])
    return []


def _capture_retry_diff(wt_path: str) -> str | None:
    """Capture what the agent changed in the last retry (git diff --stat HEAD~1)."""
    result = run_git("diff", "--stat", "HEAD~1", cwd=wt_path, timeout=10)
    if result.exit_code == 0 and result.stdout.strip():
        return result.stdout.strip()[:500]
    return None


# ─── Review Findings MD (per-change, committed to branch) ─────────


def _review_findings_md_path(wt_path: str) -> str:
    """Return path to the review findings MD file in the worktree."""
    return os.path.join(wt_path, ".claude", "review-findings.md")


def _read_existing_findings(md_path: str) -> list[dict]:
    """Parse existing review-findings.md into a list of issue dicts.

    Each item has: severity, file, line, summary, fix, status ('open'|'fixed').
    """
    items: list[dict] = []
    if not os.path.isfile(md_path):
        return items
    try:
        with open(md_path) as f:
            for line in f:
                line = line.rstrip()
                # Match: - [ ] [CRITICAL] file:line — summary
                # or:    - [x] [HIGH] file:line — summary
                m = re.match(
                    r"^- \[([ x])\] \[(\w+)\]\s+(`[^`]+`|[^\s]+?)(?::(\S+))?\s*—\s*(.+)",
                    line,
                )
                if m:
                    status = "fixed" if m.group(1) == "x" else "open"
                    items.append({
                        "severity": m.group(2),
                        "file": m.group(3).strip("`"),
                        "line": m.group(4) or "",
                        "summary": m.group(5).strip(),
                        "fix": "",
                        "status": status,
                    })
                # Match FIX line (indented under an item)
                elif line.startswith("  FIX:") and items:
                    items[-1]["fix"] = line[6:].strip()
    except OSError:
        pass
    return items


def _issue_key(issue: dict) -> str:
    """Unique key for deduplication: file + line + normalized summary prefix."""
    summary = issue.get("summary", "")
    # Strip severity tags and markdown bold for consistent matching
    summary = re.sub(r"\[(?:CRITICAL|HIGH|MEDIUM|LOW)\]\s*", "", summary)
    summary = summary.strip().lstrip("*").rstrip("*").strip()
    return f"{issue.get('file', '')}:{issue.get('line', '')}:{summary[:40]}"


def _write_review_findings_md(
    wt_path: str,
    change_name: str,
    new_issues: list[dict],
    round_num: int,
) -> str:
    """Write/append review findings to .claude/review-findings.md.

    Reads existing file, identifies NEW issues (not seen before),
    reopens previously-fixed issues if reviewer flagged them again,
    and appends a new round section.

    Returns the path to the MD file.
    """
    md_path = _review_findings_md_path(wt_path)
    existing = _read_existing_findings(md_path)
    existing_keys = {_issue_key(i) for i in existing}

    # Categorize new issues
    truly_new: list[dict] = []
    reopened: list[dict] = []
    for issue in new_issues:
        key = _issue_key(issue)
        if key in existing_keys:
            # Check if it was marked fixed — if so, reopen
            for ex in existing:
                if _issue_key(ex) == key and ex["status"] == "fixed":
                    reopened.append(issue)
                    break
            # If still open, skip (already tracked)
        else:
            truly_new.append(issue)

    # If nothing new and nothing reopened, no update needed
    if not truly_new and not reopened:
        return md_path

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Build the new round section
    lines: list[str] = []

    # Header if file doesn't exist yet
    if not os.path.isfile(md_path) or os.path.getsize(md_path) == 0:
        lines.append(f"# Review Findings: {change_name}\n")

    lines.append(f"\n## Round {round_num} — {ts}\n")

    if reopened:
        lines.append("### Reopened (fix was insufficient)\n")
        for issue in reopened:
            sev = issue.get("severity", "MEDIUM")
            f = issue.get("file", "?")
            ln = issue.get("line", "")
            loc = f"`{f}`:{ln}" if ln else f"`{f}`"
            summary = re.sub(r"\[(?:CRITICAL|HIGH|MEDIUM|LOW)\]\s*", "", issue.get("summary", "")).strip().strip("*").strip()
            lines.append(f"- [ ] [{sev}] {loc} — {summary}")
            if issue.get("fix"):
                lines.append(f"  FIX: {issue['fix']}")

    if truly_new:
        if reopened:
            lines.append("")
        lines.append("### New issues\n")
        for issue in truly_new:
            sev = issue.get("severity", "MEDIUM")
            f = issue.get("file", "?")
            ln = issue.get("line", "")
            loc = f"`{f}`:{ln}" if ln else f"`{f}`"
            summary = re.sub(r"\[(?:CRITICAL|HIGH|MEDIUM|LOW)\]\s*", "", issue.get("summary", "")).strip().strip("*").strip()
            lines.append(f"- [ ] [{sev}] {loc} — {summary}")
            if issue.get("fix"):
                lines.append(f"  FIX: {issue['fix']}")

    lines.append("")

    # Append to file
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    with open(md_path, "a") as f:
        f.write("\n".join(lines))

    # Commit the findings file to the branch
    import subprocess as _sp
    _sp.run(["git", "-C", wt_path, "add", md_path], capture_output=True, timeout=10)
    _sp.run(
        ["git", "-C", wt_path, "commit", "-m",
         f"chore: update review findings (round {round_num})"],
        capture_output=True, timeout=10,
    )

    return md_path


def _group_review_findings_by_severity(review_output: str) -> dict[str, list[dict]]:
    """Parse findings and return them grouped by severity tier."""
    issues = _parse_review_issues(review_output)
    groups: dict[str, list[dict]] = {
        "CRITICAL": [],
        "HIGH": [],
        "MEDIUM": [],
        "LOW": [],
    }
    for i in issues:
        sev = (i.get("severity") or "").upper()
        if sev in groups:
            groups[sev].append(i)
    return groups


def _render_grouped_findings_section(grouped: dict[str, list[dict]]) -> str:
    """Render findings as Must Fix / Should Fix / Nice to Have sections.

    Applied per Part 8 severity rubric: CRITICAL+HIGH → Must Fix,
    MEDIUM → Should Fix (if trivial), LOW → Nice to Have.
    """
    must_fix = grouped["CRITICAL"] + grouped["HIGH"]
    should_fix = grouped["MEDIUM"]
    nice_to_have = grouped["LOW"]

    sections: list[str] = []
    if must_fix:
        sections.append("## Must Fix")
        for i in must_fix:
            sev = i.get("severity", "").upper()
            summary = i.get("summary", "").strip()
            file = i.get("file", "").strip()
            line = i.get("line", "").strip()
            loc = f" ({file}:{line})" if file else ""
            sections.append(f"- [{sev}] {summary}{loc}")
    if should_fix:
        sections.append("\n## Should Fix (if trivial)")
        for i in should_fix:
            summary = i.get("summary", "").strip()
            sections.append(f"- {summary}")
    if nice_to_have:
        sections.append("\n## Nice to Have")
        for i in nice_to_have:
            summary = i.get("summary", "").strip()
            sections.append(f"- {summary}")

    if not sections:
        return ""
    sections.append(
        "\nFocus on Must Fix first. Move to Should Fix only if there is "
        "capacity. Skip Nice to Have unless the fix is a one-line change."
    )
    return "\n".join(sections) + "\n\n"


def _build_review_retry_prompt(
    state_file: str,
    change_name: str,
    current_review_output: str,
    security_guide: str,
    verify_retry_count: int,
    review_retry_limit: int,
    findings_md_path: str = "",
) -> str:
    """Build retry prompt referencing the review findings MD file.

    The detailed findings are in the committed .claude/review-findings.md.
    The prompt tells the agent to read that file and fix unchecked items.
    """
    history = _get_review_history(state_file, change_name)

    parts = [f'CRITICAL CODE REVIEW FAILURE for "{change_name}". You MUST fix the review issues.\n']

    # Severity-grouped findings summary — per Part 8 rubric, the agent
    # prioritizes CRITICAL+HIGH (Must Fix) over MEDIUM (Should Fix) and LOW
    # (Nice to Have). Previous prompts mixed all findings at the same
    # level, causing agents to spend retry cycles on cosmetic issues.
    #
    # NOTE: _parse_review_issues (which drives grouped_section) only
    # understands the first-round review format (`ISSUE: [TAG]`). Retry
    # rounds use `### Finding N:` / `**NOT_FIXED** [CRITICAL]` headers,
    # which the parser silently mixes up — FILE/LINE/FIX fields can land
    # on the wrong finding. We keep the grouped summary as a quick overview
    # but ALSO embed the full raw review output below so the agent sees
    # the reviewer's intent verbatim, parser bugs or not.
    grouped = _group_review_findings_by_severity(current_review_output)
    grouped_section = _render_grouped_findings_section(grouped)
    if grouped_section:
        parts.append(grouped_section)

    # Raw review output — authoritative source. 50K char safety ceiling to
    # protect against pathological LLM outputs (reviews are typically
    # 3-15KB; 50K gives 3-5x headroom without risking prompt bloat).
    if current_review_output:
        raw_budget = 50_000
        raw = (
            current_review_output
            if len(current_review_output) <= raw_budget
            else smart_truncate_structured(current_review_output, raw_budget)
        )
        parts.append(
            "## Full reviewer output (authoritative — pair FILE/LINE/FIX by finding, "
            "not by the grouped summary above)\n\n"
            f"```\n{raw}\n```\n"
        )

    # Reference the findings file
    if findings_md_path:
        rel_path = ".claude/review-findings.md"
        parts.append(f"## Review findings are in `{rel_path}`\n")
        parts.append(
            f"Read `{rel_path}` — it contains ALL review issues across all rounds.\n"
            "Fix every item marked `- [ ]` (unchecked).\n"
            "After fixing each issue, mark it `- [x]` in the file.\n"
            "Commit the updated findings file along with your code fixes.\n"
            "NOTE: The markdown findings file is generated by a parser that can\n"
            "mislabel FILE/LINE/FIX for retry-round review formats. When the\n"
            "markdown disagrees with the reviewer output above, trust the raw\n"
            "reviewer output.\n"
        )

    # Brief history summary (not full output — that's in the MD file)
    if len(history) > 1:
        parts.append("== PREVIOUS ATTEMPTS ==")
        for h in history:
            parts.append(f"Attempt {h['attempt']}:")
            if h.get("diff_summary"):
                parts.append(f"  Changed: {h['diff_summary']}")
            parts.append(f"  Result: STILL CRITICAL\n")

    # Security reference — don't embed the full text (it's already in
    # .claude/rules/), just remind the agent to check it
    if security_guide:
        parts.append(
            "SECURITY: Read `.claude/rules/` for security patterns. "
            "All review issues must comply with the security rules in that directory.\n"
        )

    # Final attempt escalation
    is_last_attempt = verify_retry_count >= review_retry_limit - 1
    if is_last_attempt:
        parts.append(
            "WARNING: This is your LAST attempt. If the same approach hasn't worked, "
            "restructure the entire implementation. Consider a completely different "
            "architecture for the problematic code.\n"
        )

    parts.append(
        "## DO NOT CREATE NEW BUGS WHILE FIXING\n\n"
        "Each retry round costs the change a retry budget slot. If your fix introduces\n"
        "an ANALOGOUS bug in an adjacent branch (the reviewer found it in the `try`, you\n"
        "silently leave the same issue in the `catch`), the next review round will flag the\n"
        "NEW bug and consume another retry. This is how changes exhaust their retry budget\n"
        "and fail to merge even when the reviewer's fix suggestions are correct.\n\n"
        "For every function/file you modify in this retry, run the reviewer's checklist\n"
        "over YOUR changes BEFORE you commit:\n\n"
        "- [ ] Every `try/catch` — does the `catch` produce the same safety invariant as the\n"
        "      successful path? (e.g., if success returns an invalidated session on tokenVersion\n"
        "      mismatch, the DB-error catch must ALSO invalidate — NEVER return the token-provided\n"
        "      identity on DB error. \"Fail closed\", not \"fail open\".)\n"
        "- [ ] Every type coercion/cast — is the runtime value guaranteed to match the type?\n"
        "      `value as T` must hold for every branch that flows into it.\n"
        "- [ ] Every fallback / default / `||` / `??` — does the fallback weaken a security\n"
        "      invariant the primary path enforces?\n"
        "- [ ] Every transactional boundary — are you checking the precondition INSIDE the\n"
        "      transaction? (TOCTOU: read-then-write outside a transaction is a race.)\n"
        "- [ ] Every auth/tenant assertion — does it fire on ALL code paths that reach the\n"
        "      sensitive operation, including the error paths?\n\n"
        "**Specific pattern-match from prior findings:** if the reviewer flagged a bug in a\n"
        "catch block, examine every OTHER catch block in the same file for the analogous bug.\n"
        "Fix all of them in this commit — do NOT rely on a future round to catch the next one.\n\n"
        "## INSTRUCTIONS:\n"
        "1. Read `.claude/review-findings.md`\n"
        "2. For each unchecked `- [ ]` item: open the FILE, go to the LINE, apply the FIX\n"
        "3. AFTER applying each fix: run the self-review checklist above over the MODIFIED function\n"
        "4. Fix any analogous issues you discover in the same commit\n"
        "5. Mark fixed items as `- [x]` in the findings file\n"
        "6. Commit all changes (code fixes + updated findings file)\n"
        "7. Do NOT work on new features — only fix the review issues + adjacent regressions"
    )

    return "\n".join(parts)


def _load_security_rules(wt_path: str) -> str:
    """Load security rules — profile first, legacy fallback."""
    from .profile_loader import load_profile

    profile = load_profile()
    rule_paths = profile.security_rules_paths(wt_path)
    if rule_paths:
        rule_items = []
        for rf in sorted(set(rule_paths)):
            try:
                content = rf.read_text()
            except OSError:
                continue
            if content.startswith("---"):
                end = content.find("---", 3)
                if end > 0:
                    content = content[end + 3:].strip()
            rule_items.append((rf.name, content))
        included, omitted = truncate_with_budget(rule_items, 4000)
        parts = [content for _, content in included]
        if omitted:
            parts.append(f"\n({len(omitted)} rules omitted for space: {', '.join(omitted)})")
        return "\n\n".join(parts)

    # TODO(profile-cleanup): remove after profile adoption confirmed
    return _load_web_security_rules(wt_path)


def _load_web_security_rules(wt_path: str) -> str:
    """Load web security rules from the worktree's .claude/rules/ if available.

    Looks for web security rule files (deployed by set-project init) and returns
    a condensed version for injection into review retry prompts.
    """
    rules_dir = Path(wt_path) / ".claude" / "rules"
    if not rules_dir.is_dir():
        return ""

    # Collect web-related rule files (may be in rules/ or rules/web/)
    rule_files = []
    for pattern in ("web/*.md", "set-web-*.md", "*web-security*.md", "*auth-middleware*.md"):
        rule_files.extend(rules_dir.glob(pattern))

    if not rule_files:
        return ""

    rule_items = []
    for rf in sorted(set(rule_files)):
        try:
            content = rf.read_text()
        except OSError:
            continue
        # Strip YAML front matter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                content = content[end + 3:].strip()
        rule_items.append((rf.name, content))

    included, omitted = truncate_with_budget(rule_items, 4000)
    parts = [content for _, content in included]
    if omitted:
        parts.append(f"\n({len(omitted)} rules omitted for space: {', '.join(omitted)})")

    return "\n\n".join(parts)


@dataclass
class ScopeCheckResult:
    """Result of implementation scope check."""
    has_implementation: bool
    first_impl_file: str = ""
    all_files: list[str] = field(default_factory=list)


@dataclass
class RuleEvalResult:
    """Result of verification rule evaluation."""
    errors: int = 0
    warnings: int = 0
    messages: list = field(default_factory=list)


# ─── Test Runner ─────────────────────────────────────────────────────
# Source: verifier.sh run_tests_in_worktree (lines 13-32)


def run_tests_in_worktree(
    wt_path: str,
    test_command: str,
    test_timeout: int = DEFAULT_TEST_TIMEOUT,
    max_chars: int = 2000,
) -> TestResult:
    """Run tests in a worktree with timeout. Captures exit code + truncated output."""
    result = run_command(
        ["bash", "-c", test_command],
        timeout=test_timeout,
        cwd=wt_path,
    )

    output = result.stdout + result.stderr
    # Truncate output preserving head (setup errors) + tail (summary)
    if len(output) > max_chars:
        output = smart_truncate(output, max_chars)

    passed = result.exit_code == 0 and not result.timed_out
    stats = _parse_test_stats(output) if output else None

    return TestResult(
        passed=passed,
        output=output,
        exit_code=result.exit_code if not result.timed_out else -1,
        stats=stats,
    )


def parse_test_output(output: str) -> dict:
    """Parse test runner output for structured pass/fail counts.

    Returns dict with keys: framework, passed, failed, total.
    Falls back to {"framework": "unknown", "passed": 0, "failed": 0, "total": 0}
    if output format is unrecognized.
    """
    stats = _parse_test_stats(output)
    if stats:
        return {
            "framework": stats.get("type", "unknown"),
            "passed": stats.get("passed", 0),
            "failed": stats.get("failed", 0),
            "total": stats.get("passed", 0) + stats.get("failed", 0),
        }
    return {"framework": "unknown", "passed": 0, "failed": 0, "total": 0}


def _parse_test_stats(output: str) -> dict | None:
    """Parse test counts from Jest/Vitest/Playwright output.

    Source: verifier.sh handle_change_done (lines 1027-1051)
    """
    # Jest/Vitest: "Tests:  X passed, Y total" or "X failed, Y passed"
    passed_match = re.findall(r"(\d+) passed", output)
    failed_match = re.findall(r"(\d+) failed", output)
    suites_match = re.search(r"Test Suites:.*?(\d+) passed", output)

    t_passed = int(passed_match[-1]) if passed_match else 0
    t_failed = int(failed_match[-1]) if failed_match else 0

    if t_passed + t_failed == 0:
        return None

    t_suites = int(suites_match.group(1)) if suites_match else 0
    # Detect framework type
    t_type = "jest" if suites_match else ("playwright" if t_passed > 0 else "unknown")

    return {
        "passed": t_passed,
        "failed": t_failed,
        "suites": t_suites,
        "type": t_type,
    }


# ─── Scope Checks ───────────────────────────────────────────────────
# Source: verifier.sh verify_merge_scope (lines 276-317), verify_implementation_scope (lines 324-367)


def _is_artifact_or_bootstrap(filepath: str) -> bool:
    """Check if a file is an artifact, config, or bootstrap file."""
    for prefix in ARTIFACT_PREFIXES:
        if filepath.startswith(prefix):
            return True
    if filepath in BOOTSTRAP_FILES:
        return True
    for pattern in BOOTSTRAP_PATTERNS:
        if fnmatch.fnmatch(os.path.basename(filepath), pattern):
            return True
    return False


def verify_merge_scope(change_name: str, cwd: str | None = None) -> ScopeCheckResult:
    """Post-merge: verify merge brought implementation files, not just artifacts.

    Source: verifier.sh verify_merge_scope (lines 276-317)
    """
    result = run_git("diff", "--name-only", "HEAD~1", cwd=cwd)
    if result.exit_code != 0 or not result.stdout.strip():
        logger.warning("Post-merge scope: no diff files found for %s (skip)", change_name)
        return ScopeCheckResult(has_implementation=True)  # skip = pass

    files = [f for f in result.stdout.strip().split("\n") if f]

    for f in files:
        if not _is_artifact_or_bootstrap(f):
            logger.info("Post-merge: scope verification passed for %s (first: %s)", change_name, f)
            return ScopeCheckResult(has_implementation=True, first_impl_file=f, all_files=files)

    logger.error(
        "Post-merge: scope verification FAILED — only artifact/bootstrap files merged for %s",
        change_name,
    )
    return ScopeCheckResult(has_implementation=False, all_files=files)


# Paths deprioritized in review diff — artifacts/tests go AFTER implementation
_REVIEW_DEPRIORITY_PREFIXES = (
    "openspec/",
    ".claude/",
    "__tests__/",
    "tests/",
    "test/",
    "docs/",
)

_REVIEW_DIFF_LIMIT = 80_000


def _prioritize_diff_for_review(raw_diff: str) -> str:
    """Build review diff: full diff for impl files, stat summary for low-priority.

    Git diff outputs files alphabetically, putting openspec/ and tests/ before
    src/. Blind truncation caused a false "missing E2E test file" review when
    the test diff was cut — the reviewer couldn't tell the file existed.

    Strategy: split diff into per-file hunks, always include impl files in full.
    For deprioritized files (tests, openspec, docs), include full diff only if
    space allows — otherwise include a stat summary so the reviewer knows they
    exist and how large they are. No file is ever silently dropped.
    """
    # Split into per-file hunks
    hunks: list[tuple[str, str]] = []  # (filepath, hunk_text)
    current_path = ""
    current_lines: list[str] = []

    for line in raw_diff.split("\n"):
        if line.startswith("diff --git"):
            if current_lines:
                hunks.append((current_path, "\n".join(current_lines)))
            parts = line.split(" b/")
            current_path = parts[-1] if len(parts) > 1 else ""
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        hunks.append((current_path, "\n".join(current_lines)))

    # Partition
    impl_hunks: list[tuple[str, str]] = []
    depri_hunks: list[tuple[str, str]] = []
    for path, hunk in hunks:
        if any(path.startswith(p) for p in _REVIEW_DEPRIORITY_PREFIXES):
            depri_hunks.append((path, hunk))
        else:
            impl_hunks.append((path, hunk))

    # Always include all impl hunks in full
    parts = [hunk for _, hunk in impl_hunks]
    impl_size = sum(len(h) for h in parts)

    # Budget remaining for deprioritized files
    budget = _REVIEW_DIFF_LIMIT - impl_size

    if budget >= sum(len(h) for _, h in depri_hunks):
        # Everything fits — include full diffs
        parts.extend(hunk for _, hunk in depri_hunks)
    else:
        # Include depri files that fit in full, summarize the rest
        full_depri = []
        summarized = []
        remaining = budget - 500  # reserve space for summary header

        for path, hunk in depri_hunks:
            if remaining >= len(hunk):
                full_depri.append(hunk)
                remaining -= len(hunk) + 1
            else:
                # Count added/removed lines for stat summary
                added = sum(1 for ln in hunk.split("\n") if ln.startswith("+") and not ln.startswith("+++"))
                removed = sum(1 for ln in hunk.split("\n") if ln.startswith("-") and not ln.startswith("---"))
                summarized.append((path, added, removed))

        parts.extend(full_depri)

        if summarized:
            stat_lines = [
                "\n\n--- Files present but diff omitted for space "
                "(DO NOT report these as missing) ---"
            ]
            for path, added, removed in summarized:
                stat_lines.append(f"  {path}  | +{added} -{removed}")
            parts.append("\n".join(stat_lines))

    return "\n".join(parts)


def _get_merge_base(wt_path: str) -> str:
    """Get merge-base of worktree branch vs main branch.

    Uses `git merge-base HEAD <ref>` to find the true fork point, ensuring
    review diffs only contain files modified by the change branch. Falls back
    to the root commit if merge-base resolution fails (first change in new repo).
    """
    main = detect_default_branch(wt_path)
    for ref in (main, f"origin/{main}"):
        result = run_git("merge-base", "HEAD", ref, cwd=wt_path)
        if result.exit_code == 0 and result.stdout.strip():
            logger.debug("merge-base resolved via %s for %s", ref, wt_path)
            return result.stdout.strip()
    # Fallback: find the root commit (works for first change in new repo)
    root_result = run_git("rev-list", "--max-parents=0", "HEAD", cwd=wt_path)
    if root_result.exit_code == 0 and root_result.stdout.strip():
        root = root_result.stdout.strip().splitlines()[0]
        logger.info("merge-base: using root commit %s for %s (no main branch)", root[:8], wt_path)
        return root
    logger.warning("merge-base failed for %s — falling back to HEAD~10", wt_path)
    return "HEAD~10"


def verify_implementation_scope(change_name: str, wt_path: str) -> ScopeCheckResult:
    """Pre-merge: verify change branch has implementation files.

    Source: verifier.sh verify_implementation_scope (lines 324-367)
    """
    merge_base = _get_merge_base(wt_path)
    result = run_git("diff", "--name-only", f"{merge_base}..HEAD", cwd=wt_path)

    if result.exit_code != 0 or not result.stdout.strip():
        logger.warning("Scope check: no diff files found for %s (skip)", change_name)
        return ScopeCheckResult(has_implementation=True)  # skip = pass

    files = [f for f in result.stdout.strip().split("\n") if f]

    for f in files:
        if not _is_artifact_or_bootstrap(f):
            logger.info("Scope check: implementation files found for %s (first: %s)", change_name, f)
            return ScopeCheckResult(has_implementation=True, first_impl_file=f, all_files=files)

    logger.error(
        "Scope check: FAILED — only artifact/bootstrap files found for %s", change_name,
    )
    return ScopeCheckResult(has_implementation=False, all_files=files)


# ─── Requirement-Aware Review ────────────────────────────────────────
# Source: verifier.sh build_req_review_section (lines 40-128)


def build_req_review_section(
    change_name: str,
    state_file: str,
    digest_dir: str = "",
) -> str:
    """Build a prompt section listing assigned and cross-cutting requirements.

    Source: verifier.sh build_req_review_section (lines 40-128)
    """
    if not digest_dir:
        digest_dir = os.environ.get("DIGEST_DIR", "")
    req_file = os.path.join(digest_dir, "requirements.json") if digest_dir else ""

    if not req_file or not os.path.isfile(req_file):
        return ""

    # Load state
    state = load_state(state_file)
    change = None
    for c in state.changes:
        if c.name == change_name:
            change = c
            break

    if not change or not change.requirements:
        return ""

    # Load digest requirements
    try:
        with open(req_file) as f:
            digest_data = json.load(f)
        digest_reqs = {r["id"]: r for r in digest_data.get("requirements", [])}
    except (json.JSONDecodeError, KeyError, OSError):
        return ""

    # Build assigned requirements section (with AC checkboxes when available)
    has_any_ac = False
    section = "\n## Assigned Requirements (this change owns these)"
    for req_id in change.requirements:
        req = digest_reqs.get(req_id)
        if not req:
            section += f"\n- {req_id}: (not found in digest)"
            logger.warning("build_req_review_section: %s not found in digest requirements.json", req_id)
        else:
            title = req.get("title", "")
            ac_items = req.get("acceptance_criteria", []) or []
            if ac_items:
                has_any_ac = True
                section += f"\n- {req_id}: {title}"
                for ac in ac_items:
                    section += f"\n  - [ ] {ac}"
            else:
                brief = req.get("brief", "")
                section += f"\n- {req_id}: {title} — {brief}"

    # Build cross-cutting requirements section
    also_affects = change.also_affects_reqs
    if also_affects:
        section += "\n\n## Cross-Cutting Requirements (awareness only)"
        for also_id in also_affects:
            req = digest_reqs.get(also_id)
            if not req:
                section += f"\n- {also_id}: (not found in digest)"
            else:
                section += f"\n- {also_id}: {req.get('title', '')}"

    # Add coverage check instruction (AC-aware when AC items are present)
    if has_any_ac:
        section += """

## Requirement Coverage Check
For each ASSIGNED requirement above:
- If the requirement has `[ ]` acceptance criteria checkboxes, verify EACH checkbox item
  has corresponding implementation evidence in the diff. For any AC item with no evidence, report:
    ISSUE: [CRITICAL] REQ-ID: "<ac item text>" not implemented in diff
- If the requirement has no acceptance criteria (just title — brief), verify the requirement
  has ANY implementation evidence in the diff. If none, report:
    ISSUE: [CRITICAL] REQ-ID has no implementation in the diff
Cross-cutting requirements are for awareness — do not flag them as missing."""
    else:
        section += """

## Requirement Coverage Check
For each ASSIGNED requirement above, verify the diff contains implementation evidence.
If a requirement has NO corresponding code in the diff, report:
  ISSUE: [CRITICAL] REQ-ID has no implementation in the diff
Cross-cutting requirements are for awareness — do not flag them as missing."""

    section += """

## Overshoot Check
Review the diff for new routes, endpoints, components, database tables, or public exports
that do NOT correspond to any assigned requirement above.
If found, report:
  ISSUE: [WARNING] Potential overshoot — new <route/component/export> not in assigned requirements: <item>
Note: Internal helper functions and utilities that serve an assigned requirement are NOT overshoot.
Only flag new user-facing features, routes, or exports that have no spec backing."""

    return section


# ─── Code Review ─────────────────────────────────────────────────────
# Source: verifier.sh review_change (lines 134-193)


def review_change(
    change_name: str,
    wt_path: str,
    scope: str,
    review_model: str = "",
    state_file: str = "",
    digest_dir: str = "",
    prompt_prefix: str = "",
) -> ReviewResult:
    """LLM code review of a change branch. Returns ReviewResult.

    Source: verifier.sh review_change (lines 134-193)
    """
    # Resolve review model via the unified config (CLI/ENV/yaml/profile/defaults)
    # when no explicit override was passed in.
    if not review_model:
        from .model_config import resolve_model
        review_model = resolve_model("review", project_dir=wt_path)

    # Generate diff
    merge_base = _get_merge_base(wt_path)
    diff_result = run_git("diff", f"{merge_base}..HEAD", cwd=wt_path)
    if diff_result.exit_code != 0:
        logger.warning("Could not generate diff for %s review", change_name)
        return ReviewResult(has_critical=False, output="")

    diff_output = _prioritize_diff_for_review(diff_result.stdout)

    # Build requirement section
    req_section = ""
    if state_file:
        req_section = build_req_review_section(change_name, state_file, digest_dir)

    # Design compliance now enforced via the design-fidelity integration
    # gate (web module), not an inline code-review section. See
    # v0_fidelity_gate.py in modules/web/.
    design_compliance = ""

    # Load security rules for first review attempt
    security_rules = _load_security_rules(wt_path)

    # Build review prompt via template
    template_input = json.dumps({
        "scope": scope,
        "diff_output": diff_output,
        "req_section": req_section,
        "design_compliance": design_compliance,
        "security_rules": security_rules,
        "change_name": change_name,
    })

    template_result = run_command(
        ["set-orch-core", "template", "review", "--input-file", "-"],
        stdin_data=template_input,
    )
    if template_result.exit_code != 0:
        logger.warning("Failed to render review template for %s", change_name)
        return ReviewResult(has_critical=False, output="")

    review_prompt = template_result.stdout

    # Prepend fix-verification instructions on retry rounds
    if prompt_prefix:
        review_prompt = prompt_prefix + review_prompt

    # Snapshot Claude session dir before the call so we can locate the new
    # session file afterwards and persist a verdict sidecar (single source
    # of truth for the dashboard's session outcome — see gate_verdict.py).
    from .gate_verdict import snapshot_session_files
    session_baseline = snapshot_session_files(wt_path)

    # Run review via Claude — 15 min timeout (default 5 min was too short for
    # large changes with many spec files, causing silent "skipping" pass-through)
    claude_result = run_claude_logged(
        review_prompt, purpose="review", change=change_name, model=review_model,
        timeout=900, cwd=wt_path,
    )
    if claude_result.exit_code != 0:
        # Escalate to the configured escalation model if not already there.
        from .model_config import resolve_model
        escalation_model = resolve_model("review_escalation", project_dir=wt_path)
        if review_model != escalation_model:
            logger.warning(
                "Code review failed with %s for %s (exit=%d, timed_out=%s) — escalating to %s",
                review_model, change_name, claude_result.exit_code,
                claude_result.timed_out, escalation_model,
            )
            claude_result = run_claude_logged(
                review_prompt, purpose="review", change=change_name,
                model=escalation_model,
                timeout=900, cwd=wt_path,
            )
            if claude_result.exit_code != 0:
                logger.error(
                    "Code review failed with %s for %s (exit=%d, timed_out=%s) — skipping (FALSE PASS)",
                    escalation_model, change_name, claude_result.exit_code, claude_result.timed_out,
                )
                _persist_review_verdict(
                    cwd=wt_path, baseline=session_baseline, change_name=change_name,
                    has_critical=False, parsed_issues=[],
                    source="exec_failed",
                    summary=f"opus exit={claude_result.exit_code} timed_out={claude_result.timed_out} — forced pass",
                )
                return ReviewResult(has_critical=False, output="")
        else:
            logger.error(
                "Code review failed for %s (exit=%d, timed_out=%s) — skipping (FALSE PASS)",
                change_name, claude_result.exit_code, claude_result.timed_out,
            )
            _persist_review_verdict(
                cwd=wt_path, baseline=session_baseline, change_name=change_name,
                has_critical=False, parsed_issues=[],
                source="exec_failed",
                summary=f"opus exit={claude_result.exit_code} timed_out={claude_result.timed_out} — forced pass",
            )
            return ReviewResult(has_critical=False, output="")

    review_output = claude_result.stdout
    logger.info("Code review complete for %s (%d chars)", change_name, len(review_output))

    # Fast path: parse the review output for structured `ISSUE: [TAG]` inline
    # findings. This handles first-round reviews (which always use this format)
    # cheaply and deterministically, and is the only path that ever runs when
    # the llm_verdict_classifier_enabled directive is False.
    parsed_issues = _parse_review_issues(review_output)
    fast_path_critical = sum(1 for i in parsed_issues if i["severity"] == "CRITICAL")
    has_critical = fast_path_critical > 0
    verdict_source = "fast_path"
    classifier_downgrades: list[dict] = []

    # Defense in depth: ALWAYS run the LLM verdict classifier on every
    # non-trivial review output (not just retries, not just zero-finding
    # cases). The fast-path regex was the source of two confirmed
    # silent-pass incidents because it could not parse retry-format
    # markdown (`### Finding N:` headers, `**NOT_FIXED** [CRITICAL]`
    # annotations, `**REVIEW BLOCKED**` summaries). The classifier is a
    # format-agnostic second Sonnet pass that reads the review text and
    # returns a structured verdict.
    #
    # We take the WORSE of (fast_path_critical, classifier_critical_count)
    # so neither path can silently lose findings. The cost is one extra
    # Sonnet call per review (~$0.001 + ~5s) — acceptable to eliminate
    # the silent-pass class of bug entirely.
    if len(review_output) >= 500 and _classifier_enabled(state_file):
        from .llm_verdict import REVIEW_SCHEMA, classify_verdict
        logger.info(
            "Gate[review] running classifier (fast_path=%d critical) on %d bytes",
            fast_path_critical, len(review_output),
        )
        try:
            from .events import event_bus as _ev
        except Exception:
            _ev = None
        cls_result = classify_verdict(
            review_output,
            REVIEW_SCHEMA,
            purpose="review",
            event_bus=_ev,
            scope_context=scope,
        )
        if cls_result.error is None:
            classifier_downgrades = list(cls_result.downgrades or [])
            cls_critical = cls_result.critical_count
            if cls_critical > fast_path_critical:
                # Classifier found findings the fast-path missed —
                # merge gets blocked, classifier wins.
                first_summary = (
                    cls_result.findings[0].get("summary", "")
                    if cls_result.findings else ""
                )[:160]
                logger.error(
                    "Gate[review] classifier found %d critical (fast_path missed %d) "
                    "for %s — merge blocked. Pattern: %s",
                    cls_critical, cls_critical - fast_path_critical,
                    change_name, first_summary,
                )
                has_critical = True
                parsed_issues = [
                    {
                        "severity": f.get("severity", "CRITICAL"),
                        "summary": f.get("summary", ""),
                        "file": f.get("file", ""),
                        "line": f.get("line", ""),
                        "fix": f.get("fix", ""),
                    }
                    for f in cls_result.findings
                ]
                verdict_source = "classifier_override"
            elif cls_critical < fast_path_critical:
                # Fast-path was stricter than classifier.
                # Only respect classifier downgrades when:
                #   (a) the classifier actually provided downgrade entries
                #   (b) the downgrades account for the gap — the sum of
                #       downgraded-from-CRITICAL entries must cover the
                #       reduction. Without this the classifier could zero
                #       out critical_count with an empty findings list
                #       and bypass a real CRITICAL the fast path caught.
                downgrade_critical_count = sum(
                    1
                    for d in classifier_downgrades
                    if (d.get("from") or "").upper() == "CRITICAL"
                )
                delta = fast_path_critical - cls_critical
                if classifier_downgrades and downgrade_critical_count >= delta:
                    logger.info(
                        "Gate[review] classifier downgraded %d findings per rubric "
                        "(fast_path=%d critical → classifier=%d critical, delta=%d covered) for %s",
                        len(classifier_downgrades),
                        fast_path_critical,
                        cls_critical,
                        delta,
                        change_name,
                    )
                    has_critical = cls_critical > 0
                    parsed_issues = [
                        {
                            "severity": f.get("severity", "MEDIUM"),
                            "summary": f.get("summary", ""),
                            "file": f.get("file", ""),
                            "line": f.get("line", ""),
                            "fix": f.get("fix", ""),
                        }
                        for f in cls_result.findings
                    ]
                    verdict_source = "classifier_downgrade"
                else:
                    if classifier_downgrades:
                        logger.warning(
                            "Gate[review] classifier claimed %d downgrades but only "
                            "%d were from CRITICAL (delta=%d) — rejecting and keeping "
                            "fast_path verdict for %s",
                            len(classifier_downgrades),
                            downgrade_critical_count,
                            delta,
                            change_name,
                        )
                    else:
                        logger.info(
                            "Gate[review] fast_path stricter (%d) than classifier (%d) for %s — "
                            "keeping fast_path verdict", fast_path_critical, cls_critical, change_name,
                        )
                    verdict_source = "fast_path_stricter"
            else:
                logger.info(
                    "Gate[review] classifier and fast_path agree (%d critical) for %s "
                    "(elapsed=%dms)", cls_critical, change_name, cls_result.elapsed_ms,
                )
                verdict_source = "classifier_confirmed"
        else:
            logger.warning(
                "Gate[review] classifier failed for %s (error=%s, elapsed=%dms) — "
                "falling through with fast-path verdict",
                change_name, cls_result.error, cls_result.elapsed_ms,
            )
            verdict_source = "classifier_failed"

    _persist_review_verdict(
        cwd=wt_path, baseline=session_baseline, change_name=change_name,
        has_critical=has_critical, parsed_issues=parsed_issues,
        source=verdict_source,
        downgrades=classifier_downgrades,
    )
    return ReviewResult(has_critical=has_critical, output=review_output)


def _persist_review_verdict(
    *,
    cwd: str,
    baseline: set[str],
    change_name: str,
    has_critical: bool,
    parsed_issues: list[dict],
    source: str,
    summary: str = "",
    downgrades: list[dict] | None = None,
) -> None:
    """Write a `<session_id>.verdict.json` next to the review's Claude session.

    Single source of truth for the dashboard's session outcome — replaces
    the older keyword-heuristic in `api/sessions.py::_session_outcome`.
    Best-effort: any failure logs a warning but never breaks the gate.
    """
    try:
        from .gate_verdict import persist_gate_verdict
        sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for i in parsed_issues:
            sev = (i.get("severity") or "").upper()
            if sev in sev_counts:
                sev_counts[sev] += 1
        if not summary:
            if has_critical:
                first = (parsed_issues[0].get("summary", "") if parsed_issues else "")[:160]
                summary = f"{sev_counts['CRITICAL']} critical via {source}: {first}"
            else:
                summary = f"0 critical findings (source={source})"
        persist_gate_verdict(
            cwd=cwd,
            baseline=baseline,
            change_name=change_name,
            gate="review",
            verdict="fail" if has_critical else "pass",
            critical_count=sev_counts["CRITICAL"],
            high_count=sev_counts["HIGH"],
            medium_count=sev_counts["MEDIUM"],
            low_count=sev_counts["LOW"],
            source=source,
            summary=summary,
            downgrades=downgrades or [],
        )
    except Exception:
        logger.warning("review verdict sidecar persist failed", exc_info=True)


# ─── Verification Rules ─────────────────────────────────────────────
# Source: verifier.sh evaluate_verification_rules (lines 200-269)


def _find_project_knowledge_file() -> str:
    """Find project-knowledge.yaml in common locations."""
    candidates = [
        "project-knowledge.yaml",
        ".claude/project-knowledge.yaml",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return ""


def evaluate_verification_rules(
    change_name: str,
    wt_path: str,
    pk_file: str = "",
    event_bus: EventBus | None = None,
) -> RuleEvalResult:
    """Evaluate verification rules from project-knowledge.yaml against git diff.

    Source: verifier.sh evaluate_verification_rules (lines 200-269)
    """
    if not pk_file:
        pk_file = _find_project_knowledge_file()
    if not pk_file or not os.path.isfile(pk_file):
        return RuleEvalResult()

    # Load YAML — try yaml module, fall back to yq subprocess
    rules = []
    try:
        import yaml
        with open(pk_file) as f:
            data = yaml.safe_load(f)
        rules = data.get("verification_rules", []) or []
    except ImportError:
        # Fall back to yq
        result = run_command(["yq", "-r", ".verification_rules | length // 0", pk_file])
        if result.exit_code != 0 or result.stdout.strip() == "0":
            return RuleEvalResult()
        # Can't easily iterate with yq, skip
        return RuleEvalResult()
    except Exception:
        return RuleEvalResult()

    # Merge plugin verification rules (plugin rules take precedence on ID collision)
    try:
        from .profile_loader import load_profile, NullProfile
        profile = load_profile()
        if not isinstance(profile, NullProfile):
            plugin_rules = profile.get_verification_rules()
            if plugin_rules:
                # Convert VerificationRule dataclass instances to dicts
                yaml_ids = {r.get("id") or r.get("name", "") for r in rules}
                for pr in plugin_rules:
                    pr_dict = {
                        "name": getattr(pr, "id", ""),
                        "id": getattr(pr, "id", ""),
                        "check": getattr(pr, "check", ""),
                        "severity": getattr(pr, "severity", "warning"),
                        "trigger": getattr(pr, "config", {}).get("trigger", "*"),
                    }
                    if pr_dict["id"] in yaml_ids:
                        # Plugin overrides YAML rule with same ID
                        rules = [r for r in rules if r.get("id", r.get("name", "")) != pr_dict["id"]]
                    rules.append(pr_dict)
    except Exception as _e:
        logger.warning("Profile verification rules failed: %s", _e)

    if not rules:
        return RuleEvalResult()

    # Get changed files
    merge_base = _get_merge_base(wt_path)
    diff_result = run_git("diff", "--name-only", f"{merge_base}..HEAD", cwd=wt_path)
    if diff_result.exit_code != 0 or not diff_result.stdout.strip():
        return RuleEvalResult()

    changed_files = [f for f in diff_result.stdout.strip().split("\n") if f]

    errors = 0
    warnings = 0
    messages: list[str] = []

    for rule in rules:
        trigger = rule.get("trigger", "")
        if not trigger:
            continue

        severity = rule.get("severity", "warning")
        rule_name = rule.get("name", "unnamed")
        check_desc = rule.get("check", "")

        # Check if any changed file matches the trigger glob
        matched = any(fnmatch.fnmatch(f, trigger) for f in changed_files)

        if matched:
            msg = f"[{severity.upper()}] {rule_name}: {check_desc}"
            messages.append(msg)
            if severity == "error":
                logger.error("Verification rule '%s' triggered (error): %s", rule_name, check_desc)
                errors += 1
            else:
                logger.warning("Verification rule '%s' triggered (warning): %s", rule_name, check_desc)
                warnings += 1

            if event_bus:
                event_bus.emit(
                    "VERIFY_RULE", change=change_name,
                    data={"rule": rule_name, "severity": severity, "check": check_desc},
                )

    if not messages:
        messages.append(f"Rules check passed: {len(rules)} rule(s) evaluated, {len(changed_files)} file(s) in diff.")

    if errors > 0:
        logger.error("Verification rules: %d error(s), %d warning(s) for %s", errors, warnings, change_name)
    elif warnings > 0:
        logger.info("Verification rules: %d warning(s) for %s", warnings, change_name)

    return RuleEvalResult(errors=errors, warnings=warnings, messages=messages)


# ─── Health Check ────────────────────────────────────────────────────
# Source: verifier.sh extract_health_check_url (lines 373-380), health_check (lines 384-406)


def extract_health_check_url(smoke_cmd: str) -> str:
    """Extract health check URL from smoke command.

    Source: verifier.sh extract_health_check_url (lines 373-380)
    """
    match = re.search(r"localhost:(\d+)", smoke_cmd)
    if match:
        return f"http://localhost:{match.group(1)}"
    return ""


def health_check(url: str, timeout_secs: int = DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT) -> bool:
    """Health check: verify dev server is responding.

    Source: verifier.sh health_check (lines 384-406)
    """
    if not url:
        return True  # No URL to check — skip

    logger.info("Health check: waiting for %s (timeout: %ds)", url, timeout_secs)
    elapsed = 0
    while elapsed < timeout_secs:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                code = resp.getcode()
                if 200 <= code < 400:
                    logger.info("Health check: server responding (%d)", code)
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
            pass
        time.sleep(1)
        elapsed += 1

    logger.error("Health check: server not responding after %ds", timeout_secs)
    return False


# ─── Smoke Fix ───────────────────────────────────────────────────────
# Source: verifier.sh smoke_fix_scoped (lines 412-500)


def _collect_smoke_screenshots(change_name: str, cwd: str | None = None) -> int:
    """Collect Playwright test-results screenshots for a change."""
    from .gate_runner import collect_screenshots

    src = os.path.join(cwd or ".", "test-results")
    return collect_screenshots(change_name, src, "smoke")


def smoke_fix_scoped(
    change_name: str,
    smoke_cmd: str,
    smoke_timeout: int,
    smoke_output: str,
    state_file: str,
    max_retries: int = DEFAULT_SMOKE_FIX_MAX_RETRIES,
    max_turns: int = DEFAULT_SMOKE_FIX_MAX_TURNS,
    log_file: str = "",
) -> bool:
    """Scoped smoke fix agent: uses change context for higher fix rate.

    Source: verifier.sh smoke_fix_scoped (lines 412-500)
    Returns True if smoke eventually passes.
    """
    # Get modified files from merge commit
    diff_result = run_git("diff", "HEAD~1", "--name-only")
    modified_files = diff_result.stdout.strip() if diff_result.exit_code == 0 else ""

    # Get change scope from state
    state = load_state(state_file)
    change_scope = ""
    for c in state.changes:
        if c.name == change_name:
            change_scope = c.scope or ""
            break

    # Multi-change context
    multi_change_context = ""
    last_smoke_commit = state.extras.get("last_smoke_pass_commit", "")
    if last_smoke_commit:
        log_result = run_git("log", "--oneline", f"{last_smoke_commit}..HEAD", "--merges")
        if log_result.exit_code == 0 and log_result.stdout.strip():
            lines = log_result.stdout.strip().split("\n")
            if len(lines) > 1:
                multi_change_context = (
                    "\n## Multiple changes merged since last smoke pass\n"
                    f"{log_result.stdout.strip()}\n\n"
                    "Multiple changes were merged since the last smoke pass. "
                    "The failure may be caused by an interaction between changes, not just the last one."
                )

    for attempt in range(1, max_retries + 1):
        update_change_field(state_file, change_name, "smoke_fix_attempts", attempt)
        update_change_field(state_file, change_name, "smoke_status", "fixing")
        logger.info("Smoke fix attempt %d/%d for %s", attempt, max_retries, change_name)

        # Build fix prompt via template
        template_input = json.dumps({
            "change_name": change_name,
            "scope": change_scope,
            "output_tail": smoke_output,
            "smoke_cmd": smoke_cmd,
            "modified_files": modified_files,
            "multi_change_context": multi_change_context,
            "variant": "scoped",
        })
        template_result = run_command(
            ["set-orch-core", "template", "fix", "--input-file", "-"],
            stdin_data=template_input,
        )
        if template_result.exit_code != 0:
            logger.error("Failed to render fix template for %s attempt %d", change_name, attempt)
            continue

        fix_prompt = template_result.stdout
        from .model_config import resolve_model
        fix_prompt_model = resolve_model("review", project_dir=wt_path)
        fix_result = run_claude_logged(
            fix_prompt, purpose="smoke_fix", change=change_name,
            model=fix_prompt_model,
            extra_args=["--max-turns", str(max_turns)],
        )
        if fix_result.exit_code != 0:
            logger.error("Smoke fix agent failed (exit %d) for %s attempt %d", fix_result.exit_code, change_name, attempt)
            continue

        # Verify fix didn't break unit tests
        state = load_state(state_file)
        test_cmd = state.extras.get("directives", {}).get("test_command", "")
        if test_cmd:
            test_result = run_command(["bash", "-c", test_cmd], timeout=600)
            if test_result.exit_code != 0:
                logger.error("Smoke fix broke unit tests — reverting (attempt %d)", attempt)
                run_git("revert", "HEAD", "--no-edit")
                continue

        # Re-run smoke to verify fix
        recheck_result = run_command(["bash", "-c", smoke_cmd], timeout=smoke_timeout)
        _collect_smoke_screenshots(change_name)

        if recheck_result.exit_code == 0:
            logger.info("Smoke fix SUCCEEDED for %s (attempt %d)", change_name, attempt)
            return True
        else:
            logger.error("Smoke still failing after fix attempt %d", attempt)
            smoke_output = recheck_result.stdout + recheck_result.stderr

    logger.error("Smoke fix exhausted all %d retries for %s", max_retries, change_name)
    return False


# ─── Phase-End E2E ───────────────────────────────────────────────────
# Source: verifier.sh run_phase_end_e2e (lines 507-593)


def run_phase_end_e2e(
    e2e_command: str,
    state_file: str,
    e2e_timeout: int = DEFAULT_E2E_TIMEOUT,
    event_bus: EventBus | None = None,
) -> bool:
    """Run Playwright E2E tests on main after all changes in a phase merged.

    Source: verifier.sh run_phase_end_e2e (lines 507-593)
    Returns True if tests passed.
    """
    logger.info("Phase-end E2E: starting on main branch")
    if event_bus:
        event_bus.emit("PHASE_E2E_STARTED", data={})

    # Detect Playwright webServer config
    try:
        from set_project_web.gates import _parse_playwright_config
        pw_config = _parse_playwright_config(os.getcwd())
    except ImportError:
        pw_config = {"config_path": None, "test_dir": None, "has_web_server": False}
    if not pw_config["has_web_server"]:
        logger.warning("Phase-end E2E: no webServer in playwright.config — skipping")
        return True  # Non-blocking skip

    start_ms = int(time.monotonic() * 1000)

    # Screenshot directory
    state = load_state(state_file)
    cycle = state.extras.get("replan_cycle", 0)
    try:
        from .paths import SetRuntime
        screenshot_dir = SetRuntime().e2e_screenshots_dir(cycle)
    except Exception:
        screenshot_dir = f"set/orchestration/e2e-screenshots/cycle-{cycle}"
    os.makedirs(screenshot_dir, exist_ok=True)

    # Run E2E — Playwright manages dev server via webServer config
    # Use unique port to avoid collisions with running agent worktrees
    import hashlib
    port_offset = int(hashlib.md5(f"phase-e2e-{cycle}".encode()).hexdigest()[:4], 16) % 1000
    e2e_port = 5000 + port_offset
    env: dict[str, str] = {"PLAYWRIGHT_OUTPUT_DIR": screenshot_dir}
    try:
        from .profile_loader import load_profile
        profile = load_profile()
        if hasattr(profile, "e2e_gate_env"):
            try:
                env.update(profile.e2e_gate_env(
                    e2e_port, timeout_seconds=e2e_timeout, fresh_server=True,
                ))
            except TypeError:
                env.update(profile.e2e_gate_env(e2e_port))
    except Exception:
        pass

    test_result = run_command(
        ["bash", "-c", e2e_command],
        timeout=e2e_timeout,
        cwd=os.getcwd(),
        env=env,
        max_output_size=8000,
    )

    e2e_result = "pass" if test_result.exit_code == 0 else "fail"
    e2e_output = test_result.stdout + test_result.stderr
    elapsed_ms = int(time.monotonic() * 1000) - start_ms

    if e2e_result == "pass":
        logger.info("Phase-end E2E: all tests passed")
    else:
        logger.error("Phase-end E2E: tests failed (rc=%d)", test_result.exit_code)

    # Collect Playwright artifacts
    test_results_dir = "test-results"
    if os.path.isdir(test_results_dir):
        for item in os.listdir(test_results_dir):
            src = os.path.join(test_results_dir, item)
            dst = os.path.join(screenshot_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        logger.info("Phase-end E2E: copied test-results/ to %s", screenshot_dir)

    # Count screenshots
    screenshot_count = sum(
        1 for _root, _dirs, files in os.walk(screenshot_dir)
        for f in files if f.endswith(".png")
    )
    logger.info(
        "Phase-end E2E: took %dms, result=%s, screenshots=%d",
        elapsed_ms, e2e_result, screenshot_count,
    )

    # Store results in state — use head+tail-preserving truncation since
    # assertion errors and stack traces live at the end of Playwright output.
    # A head-only slice drops the evidence that replan context needs. See
    # OpenSpec change: fix-retry-context-signal-loss (Bug A audit site).
    e2e_output_truncated = smart_truncate_structured(e2e_output, 8000)
    with locked_state(state_file) as state:
        results = state.extras.get("phase_e2e_results", [])
        results.append({
            "cycle": cycle,
            "result": e2e_result,
            "duration_ms": elapsed_ms,
            "output": e2e_output_truncated,
            "screenshot_dir": screenshot_dir,
            "screenshot_count": screenshot_count,
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        })
        state.extras["phase_e2e_results"] = results

    if event_bus:
        event_bus.emit(
            "PHASE_E2E_COMPLETED", data={
                "result": e2e_result, "duration_ms": elapsed_ms, "cycle": cycle,
            },
        )

    if e2e_result == "fail":
        send_notification(
            "set-orchestrate",
            "Phase-end E2E failed! Failures will be included in replan context.",
            "warning",
        )
        update_state_field(state_file, "phase_e2e_failure_context", e2e_output_truncated)
    else:
        send_notification(
            "set-orchestrate",
            "Phase-end E2E passed! All integrated tests green.",
            "normal",
        )
        update_state_field(state_file, "phase_e2e_failure_context", "")

    return e2e_result == "pass"


# ─── Poll Change ─────────────────────────────────────────────────────
# Source: verifier.sh poll_change (lines 597-778)


def _read_head_sha(wt_path: str) -> str:
    """Return the short HEAD SHA of the worktree, or '' on any git error."""
    if not wt_path or not os.path.isdir(wt_path):
        return ""
    try:
        import subprocess as _sp
        r = _sp.run(
            ["git", "-C", wt_path, "rev-parse", "--short=12", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, Exception):
        return ""


def _compute_gate_fingerprint(
    stop_gate: str,
    results: list[Any] | None = None,
    finding_ids: list[str] | None = None,
    wt_path: str = "",
) -> str:
    """Return a stable short SHA of (stop_gate, sorted(finding_ids), HEAD_sha).

    The circuit breakers (stuck-loop + token-runaway) compare fingerprints
    across iterations: identical fingerprints across N stuck exits mean the
    gate signature is unchanged — nothing has been fixed. If callers pass
    raw `GateResult` objects via `results`, we derive finding_ids from
    failing gate names so pass→pass vs fail→fail stay distinguishable.

    When `wt_path` is provided and refers to a git worktree, the current
    HEAD SHA is folded into the fingerprint. This closes a loophole where
    an agent commits a fix between iterations but the gate output happens
    to be identical (same failing gate, same finding ids) — the old
    fingerprint would collide and stuck_loop would fire even though the
    code genuinely moved forward (observed in craftbrew-run-20260421-0025
    on catalog-listings-and-homepage, 3 commits, 1 verify_gate run).
    """
    ids: list[str] = list(finding_ids or [])
    for r in results or []:
        status = getattr(r, "status", "")
        if status in ("fail", "warn-fail"):
            ids.append(f"gate:{getattr(r, 'gate_name', '?')}:{status}")
        # Structured findings stashed on stats/extras take precedence.
        stats = getattr(r, "stats", None) or {}
        for f in (stats.get("findings") or []):
            if isinstance(f, dict) and f.get("fingerprint"):
                ids.append(f"find:{f['fingerprint']}")
    head_sha = _read_head_sha(wt_path)
    payload_parts: list[Any] = [stop_gate or "pass", sorted(set(ids))]
    if head_sha:
        payload_parts.append(f"head:{head_sha}")
    payload = json.dumps(payload_parts, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(
        payload.encode("utf-8", errors="replace"),
    ).hexdigest()[:16]


def _has_commits_since_stall(wt_path: str, since_epoch: int) -> int:
    """Return the count of commits on HEAD since the given wall-clock epoch.

    Used by the stale-detection guard: if the agent exited stuck/stopped but
    committed fixes after the last stall marker, we must NOT re-write
    `status=stalled` — the engine's re-gate handler will pick it up instead.
    Returns 0 on any git error (fail-closed: keep existing stall behavior).
    """
    if not wt_path or not os.path.isdir(wt_path) or since_epoch <= 0:
        return 0
    try:
        import subprocess as _sp
        result = _sp.run(
            [
                "git", "-C", wt_path, "log",
                f"--since=@{int(since_epoch)}",
                "--oneline",
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return 0
        return sum(1 for ln in result.stdout.splitlines() if ln.strip())
    except (OSError, Exception) as exc:
        logger.debug("_has_commits_since_stall: git log failed for %s: %s", wt_path, exc)
        return 0


def _read_loop_state(wt_path: str) -> dict:
    """Read loop-state.json from worktree .claude/ directory."""
    loop_state_path = os.path.join(wt_path, ".set", "loop-state.json")
    if not os.path.isfile(loop_state_path):
        logger.debug("_read_loop_state: file missing at %s", loop_state_path)
        return {}
    try:
        with open(loop_state_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as _e:
        logger.debug("_read_loop_state: parse failed for %s: %s", loop_state_path, _e)
        return {}


def _read_loop_state_mtime(wt_path: str) -> int:
    """Get mtime of loop-state.json as epoch seconds."""
    loop_state_path = os.path.join(wt_path, ".set", "loop-state.json")
    try:
        return int(os.path.getmtime(loop_state_path))
    except OSError:
        return 0


def _capture_context_tokens_start(
    state_file: str,
    change_name: str,
    change: "Change",
    loop_state: dict,
) -> None:
    """Capture context_tokens_start after the first iteration completes.

    Uses cache_create_tokens from iteration 1 as the proxy for initial context size.
    Only written once (skipped if already set).
    """
    if change.context_tokens_start is not None:
        return  # already captured
    iterations = loop_state.get("iterations", [])
    if not iterations:
        return
    iter1 = iterations[0]
    if not iter1.get("ended"):
        return  # iteration 1 not complete yet
    cc = int(iter1.get("cache_create_tokens", 0))
    if cc > 0:
        update_change_field(state_file, change_name, "context_tokens_start", cc)
        cw = _context_window_for_model(change.model or "")
        logger.debug("context_tokens_start for %s: %d (%.0f%%)", change_name, cc, cc / cw * 100)
    # Store context breakdown from iteration 1 if available
    breakdown = iter1.get("context_breakdown")
    if breakdown and isinstance(breakdown, dict):
        update_change_field(state_file, change_name, "context_breakdown_start", breakdown)


def _capture_context_tokens_end(
    state_file: str,
    change_name: str,
    loop_state: dict,
    model: str = "",
) -> None:
    """Capture context_tokens_end at loop completion.

    Uses MAX cache_create_tokens across iterations as the proxy for peak
    context size — this is what was loaded into a single iteration. The
    legacy `total_cache_create` was cumulative and over-reported by N×.
    """
    iterations = loop_state.get("iterations") or []
    peak = 0
    for it in iterations:
        try:
            v = int(it.get("cache_create_tokens", 0) or 0)
            if v > peak:
                peak = v
        except (TypeError, ValueError):
            continue
    # Fallback for older loop-state.json without per-iter breakdown
    if peak == 0:
        peak = int(loop_state.get("total_cache_create", 0) or 0)
    if peak > 0:
        update_change_field(state_file, change_name, "context_tokens_end", peak)
        cw = _context_window_for_model(model)
        pct = peak / cw * 100
        level = "warning" if pct >= 80 else "info"
        getattr(logger, level)(
            "context_tokens_end for %s: %d (%.0f%% of %dK window, peak across %d iter)",
            change_name, peak, pct, cw // 1000, len(iterations) or 1,
        )


def _accumulate_tokens(
    state_file: str,
    change_name: str,
    loop_tokens: dict,
) -> None:
    """Add current loop tokens to _prev accumulators and update state.

    Source: verifier.sh poll_change (lines 674-685)
    """
    state = load_state(state_file)
    change = None
    for c in state.changes:
        if c.name == change_name:
            change = c
            break
    if not change:
        return

    token_fields = [
        ("tokens_used", "total", "tokens_used_prev"),
        ("input_tokens", "input", "input_tokens_prev"),
        ("output_tokens", "output", "output_tokens_prev"),
        ("cache_read_tokens", "cache_read", "cache_read_tokens_prev"),
        ("cache_create_tokens", "cache_create", "cache_create_tokens_prev"),
    ]
    for state_field, loop_key, prev_field in token_fields:
        current = loop_tokens.get(loop_key, 0)
        prev = getattr(change, prev_field, 0)
        update_change_field(state_file, change_name, state_field, current + prev)


def poll_change(
    change_name: str,
    state_file: str,
    **kwargs: Any,
) -> str | None:
    """Poll loop-state.json and dispatch based on status.

    Source: verifier.sh poll_change (lines 597-778)
    Returns the detected ralph_status or None if skipped.
    """
    state = load_state(state_file)
    change = None
    for c in state.changes:
        if c.name == change_name:
            change = c
            break
    if not change or not change.worktree_path:
        return None

    wt_path = change.worktree_path

    # Worktree gone — likely merged+archived
    if not os.path.isdir(wt_path):
        if change.status in ("running", "verifying"):
            logger.info(
                "Worktree %s gone for %s (status=%s) — likely merged+archived, skipping poll",
                wt_path, change_name, change.status,
            )
        return None

    loop_state = _read_loop_state(wt_path)

    if not loop_state:
        # No loop-state yet — check if terminal process is dead
        ralph_pid = change.ralph_pid or 0
        if ralph_pid > 0:
            pid_result = check_pid(ralph_pid, "set-loop")
            if not pid_result.alive or not pid_result.match:
                logger.error(
                    "Terminal process %d for %s is dead, no loop-state found",
                    ralph_pid, change_name,
                )
                update_change_field(state_file, change_name, "status", "failed")
                return "dead"
        elif change.started_at:
            # ralph_pid=0 means agent never registered or already exited.
            # If started_at is old enough (>300s), treat as dead agent.
            import datetime as _dt
            try:
                started = _dt.datetime.fromisoformat(str(change.started_at))
                if started.tzinfo is None:
                    # started_at is typically local time without tz — compare with local now
                    age_secs = (
                        _dt.datetime.now() - started
                    ).total_seconds()
                else:
                    age_secs = (
                        _dt.datetime.now(_dt.timezone.utc) - started
                    ).total_seconds()
                if age_secs > 300:
                    logger.error(
                        "Change %s has ralph_pid=0, no loop-state, started %ds ago — treating as dead agent",
                        change_name, int(age_secs),
                    )
                    update_change_field(state_file, change_name, "status", "failed")
                    return "dead"
            except (ValueError, TypeError) as _e:
                logger.debug("started_at parse failed for %s: %s", change_name, _e)
        return None

    # Extract tokens (safely handle malformed values)
    def _safe_int(val: object) -> int:
        try:
            return int(val)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0

    tokens = _safe_int(loop_state.get("total_tokens", 0))
    in_tok = _safe_int(loop_state.get("total_input_tokens", 0))
    out_tok = _safe_int(loop_state.get("total_output_tokens", 0))
    cr_tok = _safe_int(loop_state.get("total_cache_read", 0))
    cc_tok = _safe_int(loop_state.get("total_cache_create", 0))

    # Fallback: if loop-state has 0 tokens, try set-usage
    if tokens == 0:
        loop_started = loop_state.get("started_at", "")
        mangled = wt_path.lstrip("/").replace("/", "-").replace(".", "-").replace("_", "-")
        claude_project_dir = f"-{mangled}"
        home = os.environ.get("HOME", "")
        projects_dir = os.path.join(home, ".claude", "projects", claude_project_dir)
        if loop_started and os.path.isdir(projects_dir):
            script_dir = os.environ.get("SCRIPT_DIR", os.path.dirname(os.path.abspath(__file__)))
            usage_cmd = os.path.join(script_dir, "..", "..", "bin", "set-usage")
            if os.path.isfile(usage_cmd):
                usage_result = run_command(
                    [usage_cmd, "--since", loop_started, f"--project-dir={claude_project_dir}", "--format", "json"],
                    timeout=10,
                )
                if usage_result.exit_code == 0:
                    try:
                        usage_data = json.loads(usage_result.stdout)
                        in_tok = int(usage_data.get("input_tokens", 0))
                        out_tok = int(usage_data.get("output_tokens", 0))
                        cr_tok = int(usage_data.get("cache_read_tokens", 0))
                        cc_tok = int(usage_data.get("cache_creation_tokens", 0))
                        tokens = in_tok + out_tok
                    except (json.JSONDecodeError, ValueError) as _e:
                        logger.debug("set-usage JSON parse failed: %s", _e)

    # Accumulate tokens
    _accumulate_tokens(state_file, change_name, {
        "total": tokens,
        "input": in_tok,
        "output": out_tok,
        "cache_read": cr_tok,
        "cache_create": cc_tok,
    })

    # Context window metrics — capture start after first iteration completes
    _capture_context_tokens_start(state_file, change_name, change, loop_state)

    ralph_status = loop_state.get("status", "unknown")

    if ralph_status == "done":
        handle_change_done(change_name, state_file, **kwargs)

    elif ralph_status == "running":
        # Stale detection: >300s mtime + dead PID → mark stalled
        mtime = _read_loop_state_mtime(wt_path)
        now_epoch = int(time.time())
        stale_secs = now_epoch - mtime

        if stale_secs > 300:
            terminal_pid = change.ralph_pid or 0
            if terminal_pid > 0:
                pid_result = check_pid(terminal_pid, "set-loop")
                if pid_result.alive and pid_result.match:
                    return ralph_status  # PID alive = long iteration
            logger.warning(
                "Change %s loop-state stale (%ds, PID %d dead) — marking stalled",
                change_name, stale_secs, terminal_pid,
            )
            update_change_field(state_file, change_name, "status", "stalled")
            update_change_field(state_file, change_name, "stalled_at", int(time.time()))

    elif ralph_status == "waiting:human":
        cur_status = change.status
        if cur_status == "dispatched":
            logger.info("Change %s manual tasks resolved — resuming", change_name)
            from .dispatcher import resume_change
            resume_change(state_file, change_name)
            return ralph_status

        if cur_status != "waiting:human":
            update_change_field(state_file, change_name, "status", "waiting:human")
            # Log manual task summary
            manual_tasks = loop_state.get("manual_tasks", [])
            for mt in manual_tasks[:5]:
                logger.info("  [%s] %s (%s)", mt.get("id", "?"), mt.get("description", ""), mt.get("type", ""))
            send_notification(
                "set-orchestrate",
                f"Change '{change_name}' needs human action. Run: set-manual show {change_name}",
                "normal",
            )

    elif ralph_status in ("budget_exceeded", "waiting:budget"):
        cur_status = change.status
        if cur_status not in ("waiting:budget", "budget_exceeded"):
            update_change_field(state_file, change_name, "status", "waiting:budget")
            budget_tokens = int(loop_state.get("total_tokens", 0))
            budget_limit = int(loop_state.get("token_budget", 0))
            logger.warning(
                "Change %s budget checkpoint: %dK / %dK — waiting for human",
                change_name, budget_tokens // 1000, budget_limit // 1000,
            )
            send_notification(
                "set-orchestrate",
                f"Change '{change_name}' budget checkpoint — run 'set-loop resume' to continue",
                "normal",
            )

    elif ralph_status in ("stopped", "stalled", "stuck"):
        # Re-read loop-state: race window check
        recheck = _read_loop_state(wt_path)
        if recheck.get("status") == "done":
            handle_change_done(change_name, state_file, **kwargs)
            return "done"

        # Stale-detection guard: before writing status=stalled, check whether
        # the agent has committed fixes since the last stall marker. If yes,
        # the engine's _poll_active_changes handler will route to re-gate —
        # overwriting status here would mask progress and fool the watchdog
        # into thinking the change is idle.
        prior_stall = int(change.extras.get("stalled_at", 0) or 0) if change.extras else 0
        # If we have no prior stall, use a 1h look-back window so a freshly
        # dispatched stuck agent with new commits is still detected.
        baseline_epoch = prior_stall if prior_stall > 0 else int(time.time()) - 3600
        new_commits = _has_commits_since_stall(wt_path, baseline_epoch)
        if new_commits > 0 and ralph_status == "stuck":
            logger.debug(
                "Skipping stall write for %s: %d new commits since %d (engine will re-gate)",
                change_name, new_commits, baseline_epoch,
            )
            return ralph_status

        logger.warning("Change %s %s — marking stalled for watchdog", change_name, ralph_status)
        update_change_field(state_file, change_name, "status", "stalled")
        update_change_field(state_file, change_name, "stalled_at", int(time.time()))

    return ralph_status


# ─── Gate Executors ──────────────────────────────────────────────────
# Each executor returns a GateResult. The GatePipeline calls them in order.


def _execute_build_gate(
    change_name: str, change: Change, wt_path: str,
    findings_path: str = "",
) -> "GateResult":
    """Build gate: detect build command, clear .next cache, run build."""
    from .gate_runner import GateResult

    if not wt_path or not os.path.isfile(os.path.join(wt_path, "package.json")):
        logger.debug("Gate[build]: no package.json in %s", wt_path)
        logger.info("Gate[build] END %s result=skipped", change_name)
        return GateResult("build", "skipped")

    build_command = _detect_build_command(wt_path)
    if not build_command:
        logger.info("Gate[build] END %s result=skipped", change_name)
        return GateResult("build", "skipped")

    logger.info("Gate[build] START %s wt=%s cmd=%s", change_name, wt_path, build_command)

    from .dispatcher import _detect_package_manager
    pm = _detect_package_manager(wt_path) or "npm"

    # Clear stale .next cache to prevent ENOENT build failures
    next_dir = os.path.join(wt_path, ".next")
    if os.path.isdir(next_dir):
        shutil.rmtree(next_dir, ignore_errors=True)

    build_result = run_command([pm, "run", build_command], timeout=600, cwd=wt_path)

    if build_result.exit_code != 0:
        build_output = build_result.stdout + build_result.stderr
        scope = change.scope or ""
        build_fix_count = change.extras.get("build_fix_attempt_count", 0)
        retry_prompt = (
            f"Build failed after implementation. Fix the build errors.\n\n"
            f"Build command: {pm} run {build_command}\n\n"
            + _build_unified_retry_context(
                build_output=build_output,
                attempt=build_fix_count + 1,
                max_attempts=3,
                change_name=change_name,
                findings_path=findings_path,
                change=change,
            )
            + f"\n\nOriginal scope: {scope}"
        )
        logger.info("Gate[build] END %s result=fail", change_name)
        return GateResult("build", "fail", output=smart_truncate_structured(build_output, 2000), retry_context=retry_prompt)

    logger.info("Gate[build] END %s result=pass", change_name)
    return GateResult("build", "pass")


def _execute_test_gate(
    change_name: str, change: Change, wt_path: str,
    test_command: str, test_timeout: int,
    findings_path: str = "",
) -> "GateResult":
    """Test gate: run tests in worktree.

    No-tests handling: when `test_command` is set but the consumer project has
    no test files, most runners exit non-zero by default, which would make this
    gate block. Web consumers avoid that via `passWithNoTests: true` in their
    vitest.config (shipped in the template). If a consumer configures a runner
    that still exits non-zero on no tests, see merger.py for the
    "no tests found" → skipped downgrade used by the integration gate.
    """
    from .gate_runner import GateResult

    if not test_command or not wt_path:
        logger.info("Gate[test] END %s result=skipped", change_name)
        return GateResult("test", "skipped")

    logger.info("Gate[test] START %s wt=%s cmd=%s", change_name, wt_path, test_command)

    tr = run_tests_in_worktree(wt_path, test_command, test_timeout)

    result = GateResult(
        "test",
        "pass" if tr.passed else "fail",
        output=tr.output,
        stats=tr.stats if tr.stats and (tr.stats.get("passed", 0) + tr.stats.get("failed", 0)) > 0 else None,
    )

    if not tr.passed:
        scope = change.scope or ""
        result.retry_context = (
            f"Tests failed after implementation. Fix the failing tests.\n\n"
            f"Test command: {test_command}\n\n"
            + _build_unified_retry_context(
                test_output=tr.output,
                change_name=change_name,
                findings_path=findings_path,
                change=change,
            )
            + f"\n\nOriginal scope: {scope}"
        )

    logger.info("Gate[test] END %s result=%s", change_name, result.status)
    return result



# E2E and lint gate executors moved to modules/web/set_project_web/gates.py


def _execute_scope_gate(
    change_name: str, change: Change, wt_path: str,
) -> "GateResult":
    """Scope gate: verify change branch has implementation files."""
    from .gate_runner import GateResult

    if not wt_path:
        return GateResult("scope", "pass")

    scope_result = verify_implementation_scope(change_name, wt_path)
    if not scope_result.has_implementation:
        scope = change.scope or ""
        return GateResult(
            "scope", "fail",
            output="No implementation code found — only OpenSpec artifacts and config files.",
            retry_context=(
                "The change has NO implementation code — only OpenSpec artifacts and config files. "
                "Run /opsx:apply to implement the tasks, then mark the change as done.\n\n"
                f"Original scope: {scope}"
            ),
        )
    # Report what was found
    all_files = getattr(scope_result, 'all_files', []) or []
    first = getattr(scope_result, 'first_impl_file', '')
    output_lines = [f"Scope check passed: {len(all_files)} file(s) in diff."]
    if first:
        output_lines.append(f"  First impl: {first}")
    return GateResult("scope", "pass", output="\n".join(output_lines))


def _execute_test_files_gate(
    change_name: str, change: Change, wt_path: str, gc: Any,
) -> "GateResult":
    """Test files gate: verify test files exist in diff."""
    from .gate_runner import GateResult

    if not wt_path:
        return GateResult("test_files", "pass")

    merge_base = _get_merge_base(wt_path)
    diff_result = run_git("diff", "--name-only", f"{merge_base}..HEAD", cwd=wt_path)
    test_files_count = 0
    if diff_result.exit_code == 0:
        for f in diff_result.stdout.strip().split("\n"):
            if re.search(r"\.(test|spec)\.", f):
                test_files_count += 1

    if gc.test_files_required and test_files_count == 0:
        scope = change.scope or ""
        return GateResult(
            "test_files", "fail",
            retry_context=(
                f"Verify failed: no test files found (*.test.* or *.spec.* patterns).\n\n"
                f"IMPORTANT: First ensure ALL implementation from the scope below is complete "
                f"and committed. Then add tests for the implemented functionality.\n\n"
                f"Scope (implement this fully, then add tests):\n{scope}"
            ),
        )

    return GateResult("test_files", "pass", stats={"test_files_count": test_files_count})


def _execute_e2e_coverage_gate(
    change_name: str, change: Change, wt_path: str, state_file: str,
) -> "GateResult":
    """Check e2e test coverage against scope requirements.

    Scans *.spec.ts files in the diff for assertion patterns matching
    scope keywords. Produces a coverage report for the review gate.
    Non-blocking (warn) — the review gate decides whether to fail.
    """
    from .gate_runner import GateResult

    if not wt_path:
        logger.info("Gate[e2e-coverage] END %s result=pass (no wt_path)", change_name)
        return GateResult("e2e_coverage", "pass")

    # Always run the navigation lint — even when scope-based CRUD checks
    # are skipped — because the white-screenshot anti-pattern (test() bodies
    # without page.goto, or readFileSync source-content assertions in
    # tests/e2e/*.spec.ts) is independent of CRUD scope and produces
    # blank artifacts in the per-attempt gallery for any change.
    nav_lint_findings = _lint_e2e_navigation(wt_path)

    # Testdir-drift canary (e2e-testdir-drift-guard): warn at PR-time when
    # playwright.config.ts testDir does not contain the spec-densest dir.
    # Complementary to the runtime self-heal in gates.py.
    testdir_finding = _lint_playwright_testdir_consistency(wt_path)
    if testdir_finding:
        logger.info(
            "playwright_testdir_consistency_warn change=%s stale_testdir=%s "
            "canonical_candidate=%s stale_spec_count=%d canonical_spec_count=%d",
            change_name,
            testdir_finding["declared_testdir"],
            testdir_finding["canonical_candidate"],
            testdir_finding["declared_count"],
            testdir_finding["canonical_count"],
        )

    scope = (change.scope or "").lower()
    if not scope:
        if nav_lint_findings or testdir_finding:
            warn_lines = []
            if nav_lint_findings:
                logger.warning(
                    "E2E navigation lint for %s: %d test(s) without page.goto",
                    change_name, len(nav_lint_findings),
                )
                warn_lines.append(_format_nav_lint_output(nav_lint_findings))
            if testdir_finding:
                warn_lines.append(
                    f"[testdir-drift] {testdir_finding['hint']}: "
                    f"declared testDir=\"{testdir_finding['declared_testdir']}\" "
                    f"({testdir_finding['declared_count']} specs) vs "
                    f"densest=\"{testdir_finding['canonical_candidate']}\" "
                    f"({testdir_finding['canonical_count']} specs)"
                )
            logger.info("Gate[e2e-coverage] END %s result=warn (lint)", change_name)
            return GateResult(
                "e2e_coverage", "warn",
                output="\n\n".join(warn_lines),
            )
        logger.info("Gate[e2e-coverage] END %s result=pass (no scope)", change_name)
        return GateResult("e2e_coverage", "pass")

    # Extract required operations from scope keywords. Patterns require
    # USER-FACING context so that file-creation instructions
    # ("create prisma/schema.prisma") and test-setup instructions
    # ("delete all items in beforeAll") don't false-positive as CRUD
    # requirements. Caught on nano-run-20260412-1941 where the `infra`
    # foundation change was flagged for missing create/delete E2E
    # coverage despite having no user-facing CRUD in scope.
    required = []
    crud_keywords = {
        "create": [
            r"\bcreate\s+(?:new|an?)\s+(?:item|product|entry|record|post|user)",
            r"\badd\s+(?:new|an?|the)\s+(?:item|product|entry|record|user)",
            r"\bnew\s+(?:item|product|entry|record|user)\s+(?:form|button|dialog|modal|page)",
            r"\b(?:submit|click)\s+(?:the\s+)?(?:add|create)\s+(?:button|form)",
            r"\bform\s+(?:to|that)\s+(?:create|add)",
            r"\bserver\s+action.*\b(?:to|for)\s+(?:create|add)",
        ],
        "update": [
            r"\bedit\s+(?:the\s+)?(?:item|product|entry|record|name|title)",
            r"\bupdate\s+(?:the\s+)?(?:item|product|entry|record|name|title)",
            r"\bmodify\s+(?:the\s+)?(?:item|product|entry|record)",
            r"\bchange\s+(?:the\s+)?(?:name|title|status)\s+(?:of|for)",
        ],
        "delete": [
            r"\bdelete\s+(?:the\s+)?(?:item|product|entry|record|user|button)",
            r"\bremove\s+(?:the\s+)?(?:item|product|entry|record|user)",
            r"\bconfirmation\s+(?:dialog|modal|prompt)\s+(?:for|before)",
            r"\btrash\s+(?:icon|button)",
        ],
    }
    for op, keywords in crud_keywords.items():
        if any(re.search(kw, scope) for kw in keywords):
            required.append(op)

    if not required:
        if nav_lint_findings:
            logger.warning(
                "E2E navigation lint for %s: %d test(s) without page.goto",
                change_name, len(nav_lint_findings),
            )
            logger.info("Gate[e2e-coverage] END %s result=warn (nav-lint)", change_name)
            return GateResult(
                "e2e_coverage", "warn",
                output=_format_nav_lint_output(nav_lint_findings),
            )
        logger.info("Gate[e2e-coverage] END %s result=pass (no requirements)", change_name)
        return GateResult("e2e_coverage", "pass")

    logger.info("Gate[e2e-coverage] START %s reqs=%d", change_name, len(required))

    # Scan spec.ts files in diff for assertion patterns
    merge_base = _get_merge_base(wt_path)
    diff_result = run_git("diff", f"{merge_base}..HEAD", "--", "*.spec.ts", cwd=wt_path)
    diff_content = (diff_result.stdout or "").lower() if diff_result.exit_code == 0 else ""

    assertion_patterns = {
        "create": [r"fill\(", r"getbyrole\(['\"]button['\"].*(?:create|add|submit)", r"\.click\("],
        "update": [r"fill\(", r"getbyrole\(['\"]button['\"].*(?:save|update|edit)", r"\.click\("],
        "delete": [r"getbyrole\(['\"](?:button|dialog)['\"].*(?:delete|remove|confirm)", r"\.click\("],
    }

    tested = []
    missing = []
    for op in required:
        patterns = assertion_patterns.get(op, [])
        found = any(re.search(p, diff_content) for p in patterns)
        if found:
            tested.append(op)
        else:
            missing.append(op)

    # Store report in extras for review gate
    report = {
        "scope_requires": required,
        "tested": tested,
        "missing": missing,
    }
    try:
        update_change_field(state_file, change_name, "e2e_coverage_report", report)
    except Exception as _e:
        logger.debug("Failed to store e2e_coverage_report: %s", _e)

    if missing or nav_lint_findings:
        parts = []
        if missing:
            gap_text = ", ".join(f"{op}: NOT TESTED" for op in missing)
            logger.warning("E2E coverage gaps for %s: %s", change_name, gap_text)
            parts.append(
                f"E2E coverage gaps: {gap_text}. Tested: {', '.join(tested) or 'none'}."
            )
        if nav_lint_findings:
            logger.warning(
                "E2E navigation lint for %s: %d test(s) without page.goto",
                change_name, len(nav_lint_findings),
            )
            parts.append(_format_nav_lint_output(nav_lint_findings))
        logger.info("Gate[e2e-coverage] END %s result=warn", change_name)
        return GateResult("e2e_coverage", "warn", output="\n".join(parts))

    logger.info("Gate[e2e-coverage] END %s result=pass", change_name)
    return GateResult("e2e_coverage", "pass", stats={"tested": tested})


def _lint_e2e_navigation(wt_path: str) -> list[dict]:
    """Find Playwright tests in tests/e2e/*.spec.ts that never call page.goto.

    Such tests leave the browser tab on about:blank, producing empty/white
    screenshots in the per-attempt artifact gallery — useless for review and
    forensic debugging. Source-level assertions like
    `expect(readFileSync(path)).toContain(...)` are the most common offender:
    they request the {page} fixture (which boots Chromium) but never navigate.
    Such checks belong in unit tests (vitest), not Playwright E2E.

    Returns a list of findings, one per offending test().
    Each finding: {file, test_name, reason, line}.
    """
    e2e_dir = os.path.join(wt_path, "tests", "e2e")
    if not os.path.isdir(e2e_dir):
        return []

    findings: list[dict] = []
    test_re = re.compile(
        r"\btest(?:\.only|\.skip)?\s*\(\s*(['\"])(?P<name>(?:\\.|(?!\1).)*)\1",
    )

    for fn in sorted(os.listdir(e2e_dir)):
        if not fn.endswith((".spec.ts", ".spec.js")):
            continue
        path = os.path.join(e2e_dir, fn)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                src = f.read()
        except OSError:
            continue

        # Walk each test() block: find its opening line, then find its
        # matching closing brace by counting depth. Naive but adequate for
        # the standard skeleton output (no nested test() inside test()).
        i = 0
        for m in test_re.finditer(src):
            test_name = m.group("name")
            block_start = m.end()
            # Find the start of the test body — first '{' after the match
            brace_idx = src.find("{", block_start)
            if brace_idx == -1:
                continue
            depth = 1
            j = brace_idx + 1
            while j < len(src) and depth > 0:
                ch = src[j]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                j += 1
            body = src[brace_idx + 1: j - 1] if depth == 0 else src[brace_idx + 1:]
            line_no = src.count("\n", 0, m.start()) + 1
            i += 1

            has_goto = bool(re.search(r"\bpage\s*\.\s*goto\s*\(", body))
            uses_fs_read = bool(re.search(r"\b(?:readFileSync|fs\.readFile|readFile)\s*\(", body))
            is_skipped = bool(re.search(r"\btest\.skip\s*\(", body)) or "test.skip(" in m.group(0)

            if is_skipped:
                continue

            if uses_fs_read:
                findings.append({
                    "file": f"tests/e2e/{fn}",
                    "test_name": test_name,
                    "line": line_no,
                    "reason": "uses readFileSync/fs.readFile — source-content "
                              "assertion belongs in a unit test (vitest), not "
                              "Playwright E2E. Will produce blank screenshot.",
                })
                continue

            if not has_goto:
                findings.append({
                    "file": f"tests/e2e/{fn}",
                    "test_name": test_name,
                    "line": line_no,
                    "reason": "no page.goto() — tab stays on about:blank, "
                              "screenshot will be blank/white.",
                })

    return findings


def _lint_playwright_testdir_consistency(wt_path: str) -> dict | None:
    """Detect playwright.config.ts testDir / spec layout divergence.

    Returns a finding dict (warn-level) or None if no divergence detected.
    Heuristic: warn when (a) declared testDir has zero specs but specs exist
    elsewhere, OR (b) another directory has at least 3× the spec count of the
    declared testDir. Never returns a fail-level finding — this is a canary,
    not a hard gate.

    Mirrors the runtime self-heal in `modules/web/set_project_web/gates.py`
    (`_self_heal_testdir_drift`) but fires at PR-time before merge.
    """
    config_path = None
    for name in ("playwright.config.ts", "playwright.config.js"):
        candidate = os.path.join(wt_path, name)
        if os.path.isfile(candidate):
            config_path = candidate
            break
    if config_path is None:
        return None

    try:
        with open(config_path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None

    m = re.search(
        r"^\s*testDir\s*:\s*\"(?P<val>[^\"]*)\"",
        text,
        flags=re.MULTILINE,
    )
    if not m:
        return None
    declared = m.group("val").strip()
    if declared.startswith("./"):
        declared = declared[2:]
    declared = declared.rstrip("/") or "."

    skip = {"node_modules", ".next", ".git", "dist", "build", "coverage", ".venv", "__pycache__"}
    counts: dict[str, int] = {}
    total = 0
    for dirpath, dirnames, filenames in os.walk(wt_path):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith((".spec.ts", ".spec.tsx")):
                rel = os.path.relpath(os.path.join(dirpath, fn), wt_path)
                parent = os.path.dirname(rel) or "."
                counts[parent] = counts.get(parent, 0) + 1
                total += 1
                if total >= 200:
                    break
        if total >= 200:
            break
    if not counts:
        return None

    declared_count = counts.get(declared, 0)
    densest_dir, densest_count = max(counts.items(), key=lambda kv: kv[1])
    if declared_count == densest_count:
        return None

    if declared_count == 0 or densest_count >= 3 * max(declared_count, 1):
        return {
            "declared_testdir": declared,
            "declared_count": declared_count,
            "canonical_candidate": densest_dir,
            "canonical_count": densest_count,
            "hint": "playwright.config.ts testDir vs spec layout divergence",
        }
    return None


def _format_nav_lint_output(findings: list[dict]) -> str:
    """Render nav-lint findings as a single human-readable warn output."""
    lines = [
        f"E2E navigation lint: {len(findings)} test(s) flagged "
        f"(blank-screenshot anti-pattern):",
    ]
    for f in findings[:20]:
        lines.append(
            f"  - {f['file']}:{f['line']} '{f['test_name']}' — {f['reason']}"
        )
    if len(findings) > 20:
        lines.append(f"  ... and {len(findings) - 20} more")
    lines.append(
        "Fix: add `await page.goto('/path')` + DOM locator assertion. "
        "If the AC is structural (file content, type signature), move to "
        "tests/unit/ instead of tests/e2e/."
    )
    return "\n".join(lines)


def _execute_review_gate(
    change_name: str, change: Change, wt_path: str,
    review_model: str, state_file: str,
    gc: Any, verify_retry_count: int,
) -> "GateResult":
    """Review gate: LLM code review with cumulative feedback."""
    from .gate_runner import GateResult

    if not wt_path:
        logger.info("Gate[review] END %s result=skipped", change_name)
        return GateResult("review", "skipped")

    scope = change.scope or ""
    effective_review_model = gc.review_model if gc.review_model else review_model

    logger.info("Gate[review] START %s wt=%s model=%s", change_name, wt_path, effective_review_model)

    # On retry rounds, use fix-verification mode:
    # Only verify previous findings were fixed, don't scan for new issues
    fix_verification_prefix = ""
    if verify_retry_count > 0:
        from .paths import LineagePaths as _LP_vrp
        prior_findings = _read_prior_review_findings(
            _LP_vrp(os.path.dirname(state_file)).review_findings,
            change_name,
        ) if state_file else ""
        if prior_findings:
            fix_verification_prefix = (
                "IMPORTANT: This is a RETRY review (attempt {attempt}).\n\n"
                "Your review has TWO jobs:\n\n"
                "**Job 1 — VERIFY the prior findings below were fixed.**\n"
                "For each finding, report FIXED (resolved) or NOT_FIXED [CRITICAL] (still present).\n"
                "Do NOT re-scan the parts of the code that were ALREADY CORRECT in round 1\n"
                "for \"new\" issues — those are out of scope for this retry round.\n\n"
                "**Job 2 — AUDIT the agent's FIX DIFF for NEW regressions the fix introduced.**\n"
                "The agent may have fixed the flagged issue but introduced an analogous bug\n"
                "in an adjacent branch (e.g., fixed the happy path but left a fail-open catch;\n"
                "fixed one catch but introduced the same bug in another). Scan the agent's\n"
                "ADDITIONS (not the unchanged surrounding code) with the exhaustive checklist:\n"
                "  * every `catch` produces the same safety invariant as its corresponding success path\n"
                "  * every new cast holds for every caller branch\n"
                "  * every new fallback does not weaken a security invariant\n"
                "  * every new transaction checks preconditions INSIDE the transaction\n"
                "  * every new auth/tenant assertion fires on ALL paths, including error paths\n"
                "For NEW critical bugs the agent introduced in THIS round's diff, emit them as\n"
                "[CRITICAL] with a note: `(REGRESSION introduced by fix)`. These count toward\n"
                "retry exhaustion — the agent must fix both the prior finding and its own\n"
                "regression in the next round.\n\n"
                "DO NOT flag: (a) issues in code that was in the original diff and was NOT\n"
                "previously flagged (round 1 already had its chance), (b) style/polish,\n"
                "(c) missing features outside scope.\n\n"
                "=== PREVIOUS FINDINGS TO VERIFY ===\n{findings}\n"
                "=== END PREVIOUS FINDINGS ===\n\n"
                "Now verify each finding above and audit the fix diff for regressions:\n\n"
            ).format(attempt=verify_retry_count + 1, findings=prior_findings)

    # Inject e2e coverage gaps into review prompt if available
    e2e_coverage_prefix = ""
    coverage_report = change.extras.get("e2e_coverage_report")
    if coverage_report and coverage_report.get("missing"):
        missing = coverage_report["missing"]
        tested = coverage_report.get("tested", [])
        gap_lines = "\n".join(f"  - {op}: NOT TESTED" for op in missing)
        ok_lines = "\n".join(f"  - {op}: tested" for op in tested) if tested else "  (none)"
        e2e_coverage_prefix = (
            "⚠ E2E COVERAGE GAPS (from automated scan):\n"
            f"{gap_lines}\n"
            f"Tested operations:\n{ok_lines}\n\n"
            "Treat missing CRUD/mutation coverage as [CRITICAL] — "
            "the agent must add e2e tests that exercise these operations "
            "(form fill → submit → verify result), not just page-load tests.\n\n"
        )

    # shadcn/ui enforcement: if components.json exists, reviewer must NOT recommend removing it
    shadcn_prefix = ""
    if wt_path and os.path.isfile(os.path.join(wt_path, "components.json")):
        shadcn_prefix = (
            "IMPORTANT: This project uses shadcn/ui (components.json exists). "
            "shadcn/ui components are MANDATORY — do NOT recommend removing components.json, "
            "utils.ts, or shadcn dependencies. If shadcn components are missing, that is a "
            "[CRITICAL] issue — the agent must install and use them.\n\n"
        )

    # Persistent review learnings injection — the reviewer must enforce these
    learnings_prefix = ""
    if state_file and verify_retry_count == 0:
        # Only inject on first review (retries focus on fixing prior findings)
        try:
            from .profile_loader import load_profile as _load_review_profile
            from .templates import classify_diff_content
            _review_profile = _load_review_profile()
            project_path = os.path.dirname(state_file)
            # Scope-filter learnings to the change's content categories so
            # the reviewer only sees relevant patterns (auth change → only
            # auth+general learnings, not database/frontend noise).
            _review_cats = classify_diff_content(scope) or None
            checklist = _review_profile.review_learnings_checklist(
                project_path, content_categories=_review_cats,
            )
            if checklist:
                # Extract individual items from the markdown checklist. Items
                # are formatted as "- <pattern> [source, seen Nx]".
                checklist_lines = [
                    line for line in checklist.splitlines()
                    if line.startswith("- ")
                ]
                if checklist_lines:
                    learnings_prefix = (
                        "REVIEW LEARNINGS — patterns from prior runs that the reviewer MUST check:\n"
                        + "\n".join(checklist_lines[:30])
                        + "\n\n"
                        "Each line ends with '[source, seen Nx]' where N is how many times the "
                        "pattern was previously observed. If the diff violates a pattern with "
                        "'seen 3x' or more AND CRITICAL severity context, flag it as [CRITICAL]. "
                        "For other violated patterns, flag as [HIGH].\n\n"
                    )
                    logger.info(
                        "Gate[review] injected %d learnings (cats=%s) into review prompt for %s",
                        len(checklist_lines[:30]), _review_cats or "all", change_name,
                    )
        except Exception:
            logger.debug("Failed to load learnings for review gate", exc_info=True)

    combined_prefix = shadcn_prefix + learnings_prefix + e2e_coverage_prefix + fix_verification_prefix

    rr = review_change(
        change_name, wt_path, scope, effective_review_model,
        state_file=state_file,
        prompt_prefix=combined_prefix,
    )

    if not rr.has_critical:
        # Still log any HIGH/MEDIUM findings for post-run analysis
        if rr.output and re.search(r"\[HIGH\]|\[MEDIUM\]", rr.output):
            from .paths import LineagePaths as _LP_vhm
            findings_path = _LP_vhm(os.path.dirname(state_file)).review_findings
            _append_review_finding(findings_path, change_name, rr.output, verify_retry_count + 1)
        logger.info("Gate[review] END %s result=pass", change_name)
        return GateResult("review", "pass", output=smart_truncate_structured(rr.output, 5000))

    # Critical review — write findings to MD file and build retry context
    round_num = verify_retry_count + 1
    diff_summary = None
    if verify_retry_count > 0:
        diff_summary = _capture_retry_diff(wt_path)

    _append_review_history(state_file, change_name, {
        "attempt": round_num,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        # Review output is LLM reasoning — the verdict and specific findings
        # live near the tail. Head-only slice would drop them. See OpenSpec
        # change: fix-retry-context-signal-loss (audit).
        "review_output": smart_truncate_structured(rr.output, 1500),
        "extracted_fixes": _extract_review_fixes(rr.output),
        "diff_summary": diff_summary,
    })

    # Persist findings to JSONL for post-run summary (LineagePaths.review_findings)
    from .paths import LineagePaths as _LP_vrf
    findings_path = _LP_vrf(os.path.dirname(state_file)).review_findings
    _append_review_finding(findings_path, change_name, rr.output, round_num)

    # Write/append to review-findings.md in worktree (committed to branch)
    new_issues = _parse_review_issues(rr.output)
    md_path = ""
    if new_issues and wt_path:
        try:
            md_path = _write_review_findings_md(wt_path, change_name, new_issues, round_num)
            logger.info("Review findings MD updated for %s round %d (%d issues)", change_name, round_num, len(new_issues))
        except Exception:
            logger.warning("Failed to write review findings MD for %s", change_name, exc_info=True)

    review_extra = getattr(gc, "review_extra_retries", 1)
    security_guide = _load_security_rules(wt_path)
    review_retry_limit = (gc.max_retries if gc.max_retries is not None else 2) + review_extra
    retry_prompt = _build_review_retry_prompt(
        state_file, change_name, rr.output,
        security_guide, verify_retry_count, review_retry_limit,
        findings_md_path=md_path,
    )

    logger.info("Gate[review] END %s result=fail", change_name)
    return GateResult("review", "fail", output=smart_truncate_structured(rr.output, 5000), retry_context=retry_prompt)


def _execute_rules_gate(
    change_name: str, change: Change, wt_path: str,
    event_bus: Any,
) -> "GateResult":
    """Rules gate: evaluate verification rules from project-knowledge.yaml."""
    from .gate_runner import GateResult

    if not wt_path:
        return GateResult("rules", "pass")

    rule_result = evaluate_verification_rules(change_name, wt_path, event_bus=event_bus)
    output = "\n".join(rule_result.messages)
    if rule_result.errors > 0:
        return GateResult("rules", "fail", output=output)
    return GateResult("rules", "pass", output=output)


def _parse_critical_count(output: str) -> int | None:
    """Parse the `CRITICAL_COUNT: N` sentinel from spec-verify LLM output.

    The spec-verify prompt asks the LLM to emit an explicit critical-findings
    count as the second-to-last line, alongside `VERIFY_RESULT: PASS|FAIL`.
    This is deliberately NOT a body-regex heuristic — past heuristic-based
    CRITICAL detection misdiagnosed real findings, so we rely on the model
    self-reporting instead.

    Robustness rules:
      - Only the LAST occurrence in the output counts. Quoted echoes of
        prior runs ("the previous report said CRITICAL_COUNT: 0 ...")
        appear earlier in the prose; the genuine sentinel the LLM emitted
        as its sign-off is always the last one.
      - Only the last 4 KB of output is scanned. The sentinel must be
        near the end (the prompt explicitly says "second-to-last line")
        and bounding the scan eliminates false matches from large quoted
        documents in the middle of the output.
      - Anchored at line start with `re.MULTILINE` so a quoted prefix
        like `> CRITICAL_COUNT: 0` does NOT match.

    Returns:
        The parsed integer count (>= 0).
        None if the sentinel is absent or unparseable — callers should treat
        this as "unknown" and NOT downgrade the verdict.
    """
    if not output:
        return None
    tail = output[-4096:] if len(output) > 4096 else output
    matches = re.findall(r"^\s*CRITICAL_COUNT:\s*(\d+)\b", tail, re.MULTILINE)
    if not matches:
        return None
    try:
        return int(matches[-1])
    except ValueError:
        return None


def _persist_spec_verify_verdict(
    *,
    cwd: str,
    baseline: set[str],
    change_name: str,
    verdict: str,
    critical_count: int = 0,
    source: str,
    summary: str = "",
) -> None:
    """Write a `<session_id>.verdict.json` next to the spec_verify session.

    Single source of truth for the dashboard's session outcome — same
    pattern as `_persist_review_verdict`. Best-effort: any failure logs
    a warning but never breaks the gate.
    """
    try:
        from .gate_verdict import persist_gate_verdict
        persist_gate_verdict(
            cwd=cwd,
            baseline=baseline,
            change_name=change_name,
            gate="spec_verify",
            verdict=verdict,
            critical_count=critical_count,
            source=source,
            summary=summary or f"verdict={verdict} source={source}",
        )
    except Exception:
        logger.warning("spec_verify verdict sidecar persist failed", exc_info=True)


def _classify_spec_verify_outcome(
    cmd_result: "ClaudeResult", verify_output: str,
) -> tuple[str, str]:
    """Classify a spec_verify LLM invocation into one of three categories.

    Returns a (category, terminal_reason) tuple where category is one of:
    - "verdict":    LLM produced VERIFY_RESULT: PASS or FAIL — sentinel is
                    authoritative regardless of exit code.
    - "infra":      LLM hit max_turns or the subprocess timed out before
                    producing a sentinel. Infrastructure failure — should
                    NOT consume a retry slot or trigger impl re-dispatch.
    - "ambiguous":  No sentinel, no detectable infra cause. Hand off to the
                    classifier fallback path.

    `terminal_reason` is a short string ("max_turns", "timeout", or "") used
    for logging and event payloads. Empty for "verdict" and "ambiguous".
    """
    if "VERIFY_RESULT: PASS" in verify_output or "VERIFY_RESULT: FAIL" in verify_output:
        return ("verdict", "")
    # Subprocess-level timeout is always infra, even with empty stdout.
    if getattr(cmd_result, "timed_out", False):
        return ("infra", "timeout")
    # Stream-json output embeds a terminal_reason; max_turns means the
    # LLM exhausted --max-turns without producing a verdict. Regex on raw
    # stdout string so partial/truncated JSON still matches.
    if re.search(r'"terminal_reason"\s*:\s*"max_turns"', verify_output):
        return ("infra", "max_turns")
    return ("ambiguous", "")


def _execute_spec_verify_gate(
    change_name: str, change: Change, wt_path: str, *,
    state_file: str = "",
) -> "GateResult":
    """Spec verify gate: run /opsx:verify via Claude."""
    from .gate_runner import GateResult

    if not wt_path or not shutil.which("claude"):
        logger.info("Gate[spec-verify] END %s result=skipped", change_name)
        return GateResult("spec_verify", "skipped")

    logger.info("Gate[spec-verify] START %s wt=%s", change_name, wt_path)

    verify_prompt = (
        f"IMPORTANT: Memory is not branch/worktree-aware — verify against filesystem, never skip checks based on memory alone.\n"
        f"Run /opsx:verify {change_name}\n\n"
        f"CRITICAL: Your FINAL TWO output lines MUST be exactly:\n"
        f"  CRITICAL_COUNT: <integer count of CRITICAL-severity findings, 0 if none>\n"
        f"  VERIFY_RESULT: PASS|FAIL\n"
        f"\n"
        f"Rules for CRITICAL_COUNT:\n"
        f"  - Count ONLY findings you marked as CRITICAL severity in your report.\n"
        f"  - WARNING and SUGGESTION findings do NOT count — use 0 if you only have those.\n"
        f"  - Be honest: the orchestrator uses this count to downgrade VERIFY_RESULT: FAIL\n"
        f"    with CRITICAL_COUNT: 0 to PASS (the warnings will still surface in logs).\n"
        f"\n"
        f"Both sentinels are parsed by the orchestrator. Without them the gate cannot\n"
        f"determine the verdict and will default to FAIL-safe behavior."
    )

    # Snapshot the Claude session dir so we can locate the new session
    # JSONL afterwards and persist a verdict sidecar (single source of
    # truth for the dashboard's session outcome — see gate_verdict.py).
    from .gate_verdict import snapshot_session_files
    session_baseline = snapshot_session_files(wt_path)

    # Start with the configured spec_verify model (default sonnet —
    # cheaper, sufficient for verification checks), escalate to the
    # configured escalation model on failure. Same pattern as review gate.
    from .model_config import resolve_model
    _initial_model = resolve_model("spec_verify", project_dir=wt_path)
    _escalation_model = resolve_model("spec_verify_escalation", project_dir=wt_path)
    _MAX_TURNS_DEFAULT = 40
    _MAX_TURNS_RETRY = 80  # doubled budget for the infra-failure retry path
    verify_cmd_result = run_claude_logged(
        verify_prompt,
        purpose="spec_verify", change=change_name,
        model=_initial_model,
        extra_args=["--max-turns", str(_MAX_TURNS_DEFAULT)],
        cwd=wt_path,
        timeout=900,
    )
    sonnet_duration_ms = verify_cmd_result.duration_ms
    sonnet_tokens = (
        getattr(verify_cmd_result, "input_tokens", 0)
        + getattr(verify_cmd_result, "output_tokens", 0)
    )

    # Escalate if the initial pass didn't produce a sentinel (classifier-path
    # friendliness: we still escalate on bare exit!=0 for back-compat, but
    # the classification at the end is what drives the verdict).
    if (
        verify_cmd_result.exit_code != 0
        or "VERIFY_RESULT:" not in (verify_cmd_result.stdout or "")
    ):
        logger.warning(
            "Gate[spec-verify] %s didn't emit sentinel for %s (exit=%d, timed_out=%s) — escalating to %s",
            _initial_model, change_name, verify_cmd_result.exit_code,
            verify_cmd_result.timed_out, _escalation_model,
        )
        verify_cmd_result = run_claude_logged(
            verify_prompt,
            purpose="spec_verify", change=change_name,
            model=_escalation_model,
            extra_args=["--max-turns", str(_MAX_TURNS_DEFAULT)],
            cwd=wt_path,
            timeout=900,
        )

    verify_output = verify_cmd_result.stdout
    opus_duration_ms = verify_cmd_result.duration_ms

    # Three-category classification (see _classify_spec_verify_outcome):
    #   verdict   — VERIFY_RESULT sentinel present, trust it
    #   infra     — max_turns / timeout, do NOT consume a retry slot
    #   ambiguous — no sentinel + no detectable infra cause → classifier
    category, terminal_reason = _classify_spec_verify_outcome(
        verify_cmd_result, verify_output,
    )
    if category == "infra":
        # Retry ONCE at doubled max-turns budget. If the retry also lands
        # in the infra bucket, abstain — gate skipped, no retry slot
        # consumed, no impl re-dispatch.
        logger.warning(
            "Gate[spec-verify] %s: infra failure (reason=%s, exit=%d, timed_out=%s) — retrying %s with max-turns=%d",
            change_name, terminal_reason, verify_cmd_result.exit_code,
            verify_cmd_result.timed_out, _escalation_model, _MAX_TURNS_RETRY,
        )
        retry_cmd_result = run_claude_logged(
            verify_prompt,
            purpose="spec_verify", change=change_name,
            model=_escalation_model,
            extra_args=["--max-turns", str(_MAX_TURNS_RETRY)],
            cwd=wt_path,
            timeout=900,
        )
        verify_output = retry_cmd_result.stdout
        verify_cmd_result = retry_cmd_result
        opus_duration_ms += retry_cmd_result.duration_ms
        category, terminal_reason = _classify_spec_verify_outcome(
            retry_cmd_result, verify_output,
        )
        if category == "infra":
            total_tokens = sonnet_tokens + (
                getattr(retry_cmd_result, "input_tokens", 0)
                + getattr(retry_cmd_result, "output_tokens", 0)
            )
            logger.warning(
                "Gate[spec-verify] %s: infra failure persisted after doubled-budget retry "
                "(reason=%s, sonnet=%dms, opus_total=%dms, total_tokens=%d) — abstaining "
                "(gate skipped, retry slot NOT consumed)",
                change_name, terminal_reason, sonnet_duration_ms,
                opus_duration_ms, total_tokens,
            )
            _persist_spec_verify_verdict(
                cwd=wt_path, baseline=session_baseline, change_name=change_name,
                verdict="skipped", critical_count=0, source="infra_fail",
                summary=f"terminal_reason={terminal_reason or 'unknown'} — abstained",
            )
            logger.info("Gate[spec-verify] END %s result=skipped (infra_fail)", change_name)
            result = GateResult(
                "spec_verify", "skipped",
                output=smart_truncate(verify_output, 2000) if verify_output else "",
            )
            # Surface the infra-fail via GateResult so gate_runner can emit
            # it on the VERIFY_GATE event data payload. This does NOT
            # consume a retry slot (skipped status is non-blocking).
            result.infra_fail = True
            result.terminal_reason = terminal_reason or "unknown"
            return result
        # Retry succeeded — fall through to verdict/ambiguous handling below.

    if "VERIFY_RESULT: PASS" in verify_output:
        logger.info("Gate[spec-verify] END %s result=pass", change_name)
        _persist_spec_verify_verdict(
            cwd=wt_path, baseline=session_baseline, change_name=change_name,
            verdict="pass", critical_count=0, source="fast_path",
            summary="VERIFY_RESULT: PASS sentinel matched",
        )
        return GateResult("spec_verify", "pass", output=smart_truncate(verify_output, 2000))
    elif "VERIFY_RESULT: FAIL" in verify_output:
        # Severity threshold via explicit LLM self-reported CRITICAL_COUNT
        # sentinel. If the LLM says "CRITICAL_COUNT: 0" alongside FAIL, the
        # FAIL was driven by WARNING/SUGGESTION-level findings only, so we
        # downgrade to PASS. If the sentinel is missing or > 0, keep the
        # conservative behavior and block the merge.
        critical_count = _parse_critical_count(verify_output)
        if critical_count == 0:
            logger.warning(
                "Gate[spec-verify] %s: LLM emitted VERIFY_RESULT: FAIL with "
                "CRITICAL_COUNT: 0 — downgrading to PASS (warning-level findings "
                "only). Tail: %s",
                change_name,
                verify_output[-400:].replace("\n", " | "),
            )
            logger.info(
                "Gate[spec-verify] END %s result=pass (warnings-only)", change_name
            )
            _persist_spec_verify_verdict(
                cwd=wt_path, baseline=session_baseline, change_name=change_name,
                verdict="pass", critical_count=0, source="fast_path_warning_only",
                summary="VERIFY_RESULT: FAIL with CRITICAL_COUNT: 0 — downgraded to pass",
            )
            return GateResult("spec_verify", "pass", output=smart_truncate(verify_output, 2000))

        scope = change.scope or ""
        # 50K raw passthrough for the retry prompt — spec_verify LLM reports
        # contain structured finding lists (FILE/LINE/FIX per item) that a
        # 2000-char head+tail truncation can chop mid-finding. Typical
        # reports are 5-20KB; 50K gives headroom for dense runs.
        raw_budget = 50_000
        verify_raw = (
            verify_output
            if verify_output and len(verify_output) <= raw_budget
            else (smart_truncate_structured(verify_output, raw_budget) if verify_output else "")
        )
        sentinel_note = (
            f"CRITICAL_COUNT={critical_count}"
            if critical_count is not None
            else "CRITICAL_COUNT sentinel missing (backward-compat fail)"
        )
        logger.warning(
            "Spec coverage FAIL for %s — blocking (%s)", change_name, sentinel_note
        )
        logger.info("Gate[spec-verify] END %s result=fail", change_name)
        _persist_spec_verify_verdict(
            cwd=wt_path, baseline=session_baseline, change_name=change_name,
            verdict="fail", critical_count=critical_count or 1, source="fast_path",
            summary=f"VERIFY_RESULT: FAIL with {sentinel_note}",
        )
        return GateResult(
            "spec_verify", "fail",
            output=smart_truncate(verify_output, 2000),
            retry_context=(
                "Spec verification FAILED — CRITICAL findings present.\n\n"
                "## Full verify output (authoritative — pair FILE/LINE/FIX by finding)\n\n"
                f"```\n{verify_raw}\n```\n\n"
                f"Original scope: {scope}\n\n"
                "Fix: Address every CRITICAL finding listed above. "
                "WARNING-level findings are informational and do not block the gate."
            ),
        )
    else:
        # No sentinel found — agent didn't write VERIFY_RESULT line.
        # Defense in depth: if the classifier is enabled, run a second
        # Sonnet pass on the verify output to extract a structured verdict.
        # The old backward-compat path (silent pass with [ANOMALY] warning)
        # is only used when the classifier is disabled or errors out.
        classifier_enabled = _classifier_enabled(state_file)
        if classifier_enabled:
            from .llm_verdict import SPEC_VERIFY_SCHEMA, classify_verdict
            try:
                from .events import event_bus as _ev
            except Exception:
                _ev = None
            logger.warning(
                "[ANOMALY] Spec verify: missing VERIFY_RESULT sentinel for %s — "
                "running classifier fallback on %d chars",
                change_name, len(verify_output),
            )
            cls_result = classify_verdict(
                verify_output,
                SPEC_VERIFY_SCHEMA,
                purpose="spec_verify_fallback",
                event_bus=_ev,
            )
            if cls_result.error is None and cls_result.critical_count == 0:
                logger.warning(
                    "Gate[spec-verify] %s: classifier confirmed no critical findings "
                    "(missing sentinel) — passing with warning. Elapsed: %dms",
                    change_name, cls_result.elapsed_ms,
                )
                logger.info(
                    "Gate[spec-verify] END %s result=pass (classifier-confirmed-no-sentinel)",
                    change_name,
                )
                _persist_spec_verify_verdict(
                    cwd=wt_path, baseline=session_baseline, change_name=change_name,
                    verdict="pass", critical_count=0, source="classifier_confirmed",
                    summary="missing sentinel — classifier confirmed 0 critical",
                )
                return GateResult(
                    "spec_verify", "pass",
                    output=smart_truncate(verify_output, 2000) or "missing VERIFY_RESULT sentinel — classifier confirmed 0 critical",
                )
            if cls_result.error is None and cls_result.critical_count > 0:
                scope = change.scope or ""
                first_summary = (cls_result.findings[0].get("summary", "") if cls_result.findings else "")[:160]
                logger.error(
                    "Gate[spec-verify] %s: classifier found %d critical issues "
                    "in output that had no sentinel. Pattern: %s",
                    change_name, cls_result.critical_count, first_summary,
                )
                findings_text = "\n".join(
                    f"- [{f.get('severity', 'CRITICAL')}] {f.get('summary', '')} "
                    f"({f.get('file', '?')}:{f.get('line', '?')})"
                    for f in cls_result.findings
                )
                logger.info("Gate[spec-verify] END %s result=fail (classifier)", change_name)
                _persist_spec_verify_verdict(
                    cwd=wt_path, baseline=session_baseline, change_name=change_name,
                    verdict="fail", critical_count=cls_result.critical_count,
                    source="classifier_override",
                    summary=f"missing sentinel; classifier found {cls_result.critical_count} critical",
                )
                return GateResult(
                    "spec_verify", "fail",
                    output=smart_truncate(verify_output, 2000),
                    retry_context=(
                        "Spec verification FAILED — classifier detected CRITICAL findings "
                        "in the verify output (no VERIFY_RESULT sentinel was present).\n\n"
                        f"Findings:\n{findings_text}\n\n"
                        f"Original scope: {scope}\n\n"
                        "Fix: Address every CRITICAL finding listed above AND ensure "
                        "the verify skill emits the VERIFY_RESULT and CRITICAL_COUNT sentinel "
                        "lines so the gate can read the verdict directly next time."
                    ),
                )
            # Classifier errored — fail closed (no trustworthy signal)
            logger.error(
                "Gate[spec-verify] %s: no sentinel AND classifier error (%s) — failing closed",
                change_name, cls_result.error,
            )
            scope = change.scope or ""
            logger.info("Gate[spec-verify] END %s result=fail (no-sentinel-no-classifier)", change_name)
            _persist_spec_verify_verdict(
                cwd=wt_path, baseline=session_baseline, change_name=change_name,
                verdict="fail", critical_count=1, source="classifier_failed",
                summary=f"missing sentinel + classifier error: {cls_result.error}",
            )
            return GateResult(
                "spec_verify", "fail",
                output=smart_truncate(verify_output, 2000) or "missing VERIFY_RESULT sentinel and classifier failed",
                retry_context=(
                    "Spec verification verdict could not be determined — the verify "
                    "skill did not emit the VERIFY_RESULT/CRITICAL_COUNT sentinel lines "
                    "AND the classifier fallback failed. Re-run /opsx:verify and "
                    f"ensure the final two lines are exactly:\n"
                    "  CRITICAL_COUNT: <integer>\n  VERIFY_RESULT: PASS|FAIL\n\n"
                    f"Original scope: {scope}"
                ),
            )
        # Classifier disabled AND no sentinel: fail closed. The previous
        # backward-compat behaviour (silent pass with [ANOMALY] log) was a
        # known silent-merge risk — see audit. There is no trustworthy
        # signal here, so we block the merge and ask the verify skill
        # to be rerun with the sentinel format. Operators who want the
        # old "lenient" behaviour should re-enable the classifier.
        scope = change.scope or ""
        logger.error(
            "Gate[spec-verify] %s: missing VERIFY_RESULT sentinel AND classifier "
            "disabled — failing closed (no trustworthy signal)",
            change_name,
        )
        logger.info("Gate[spec-verify] END %s result=fail (missing-sentinel-no-classifier)", change_name)
        _persist_spec_verify_verdict(
            cwd=wt_path, baseline=session_baseline, change_name=change_name,
            verdict="fail", critical_count=1, source="missing_sentinel_classifier_disabled",
            summary="missing VERIFY_RESULT sentinel + classifier disabled — failing closed",
        )
        return GateResult(
            "spec_verify", "fail",
            output=smart_truncate(verify_output, 2000) or "missing VERIFY_RESULT sentinel and classifier disabled",
            retry_context=(
                "Spec verification verdict could not be determined — the verify "
                "skill did not emit the VERIFY_RESULT/CRITICAL_COUNT sentinel lines "
                "and the LLM verdict classifier is disabled in directives. "
                "Re-run /opsx:verify and ensure the final two lines are exactly:\n"
                "  CRITICAL_COUNT: <integer>\n  VERIFY_RESULT: PASS|FAIL\n\n"
                f"Original scope: {scope}"
            ),
        )


# ─── Integrate Main Into Branch ─────────────────────────────────────


def _integrate_main_into_branch(
    wt_path: str,
    change_name: str,
    state_file: str,
    event_bus: Any = None,
) -> str:
    """Merge main into the feature branch (worktree) before running gates.

    Returns:
        "ok" — integration succeeded (or was a no-op)
        "conflict" — merge conflict, agent needs to resolve on branch
        "failed" — git error (not conflict)
    """
    update_change_field(state_file, change_name, "status", "integrating")

    main_branch = detect_default_branch(wt_path)

    # Determine merge ref: prefer origin/<main> if remote exists, else local <main>
    fetch_result = run_git("fetch", "origin", main_branch, cwd=wt_path, timeout=60, best_effort=True)
    has_origin = fetch_result.exit_code == 0
    merge_ref = f"origin/{main_branch}" if has_origin else main_branch
    if not has_origin:
        logger.info("No origin remote — using local %s for integration", main_branch)

    # Check if integration is needed (is main ahead of branch?)
    origin_head_result = run_git(
        "rev-parse", merge_ref,
        cwd=wt_path, timeout=10,
    )
    if origin_head_result.exit_code != 0:
        # merge_ref doesn't exist (no origin, no local main — first change in new repo)
        logger.info("Integration skip for %s — %s ref not found (first change?)", change_name, merge_ref)
        return "ok"
    merge_base_result = run_git(
        "merge-base", "HEAD", merge_ref,
        cwd=wt_path, timeout=10,
    )
    if (merge_base_result.exit_code == 0
            and merge_base_result.stdout.strip() == origin_head_result.stdout.strip()):
        logger.info("Integration skip for %s — branch already up-to-date with %s", change_name, main_branch)
        return "ok"

    # Stash any dirty files before merge (agents may leave uncommitted changes)
    stash_result = run_git("stash", "--include-untracked", cwd=wt_path, timeout=30)
    did_stash = stash_result.exit_code == 0 and "No local changes" not in stash_result.stdout

    # Merge main into branch
    logger.info("Integrating %s into %s for %s", main_branch, "branch", change_name)
    merge_result = run_git(
        "merge", merge_ref,
        "-m", f"Merge {main_branch} into branch for pre-gate integration",
        cwd=wt_path, timeout=120,
    )

    if merge_result.exit_code == 0:
        logger.info("Integration merge succeeded for %s", change_name)
        if did_stash:
            run_git("stash", "pop", cwd=wt_path, timeout=30)
        if event_bus:
            event_bus.emit("INTEGRATION", change=change_name, data={"result": "ok"})
        return "ok"

    # Check for conflict markers
    conflict_check = run_git("diff", "--name-only", "--diff-filter=U", cwd=wt_path, timeout=10)
    has_conflicts = conflict_check.exit_code == 0 and conflict_check.stdout.strip()

    if has_conflicts:
        # Abort the failed merge so worktree is clean for agent
        run_git("merge", "--abort", cwd=wt_path, timeout=10)
        if did_stash:
            run_git("stash", "pop", cwd=wt_path, timeout=30)
        conflicted_files = conflict_check.stdout.strip()
        logger.warning("Integration merge conflict for %s: %s", change_name, conflicted_files[:200])
        if event_bus:
            event_bus.emit("INTEGRATION", change=change_name, data={"result": "conflict", "files": conflicted_files[:500]})
        return "conflict"

    # Non-conflict git error
    logger.error("Integration merge failed for %s: %s", change_name, merge_result.stderr[:300])
    run_git("merge", "--abort", cwd=wt_path, timeout=10)
    if did_stash:
        run_git("stash", "pop", cwd=wt_path, timeout=30)
    return "failed"


# ─── Universal Gate Definitions ──────────────────────────────────────

def _get_universal_gates():
    """Return UNIVERSAL_GATES list (lazy to avoid forward-reference issues)."""
    from .gate_runner import GateDefinition
    return [
        GateDefinition(
            "build", _execute_build_gate,
            position="start",
            own_retry_counter="build_fix_attempt_count",
            result_fields=("build_result", "gate_build_ms"),
            run_on_integration=True,
        ),
        GateDefinition(
            "test", _execute_test_gate,
            position="after:build",
            result_fields=("test_result", "gate_test_ms"),
            run_on_integration=True,
        ),
        GateDefinition(
            "scope_check", _execute_scope_gate,
            position="after:test",
        ),
        GateDefinition(
            "test_files", _execute_test_files_gate,
            position="after:scope_check",
        ),
        GateDefinition(
            "review", _execute_review_gate,
            position="before:end",
            extra_retries=3,
            result_fields=("review_result", "gate_review_ms"),
        ),
        GateDefinition(
            "rules", _execute_rules_gate,
            position="after:review",
        ),
        GateDefinition(
            "spec_verify", _execute_spec_verify_gate,
            position="end",
            result_fields=("spec_coverage_result", "gate_verify_ms"),
        ),
    ]


# ─── Handle Change Done / Verify Gate Pipeline ──────────────────────
# Source: verifier.sh handle_change_done (lines 782-1453)


def handle_change_done(
    change_name: str,
    state_file: str,
    test_command: str = "",
    merge_policy: str = "eager",
    test_timeout: int = DEFAULT_TEST_TIMEOUT,
    max_verify_retries: int = DEFAULT_MAX_VERIFY_RETRIES,
    review_before_merge: bool = False,
    review_model: str = DEFAULT_REVIEW_MODEL,
    smoke_command: str = "",
    smoke_timeout: int = DEFAULT_SMOKE_TIMEOUT,
    smoke_blocking: bool = False,
    smoke_fix_max_retries: int = DEFAULT_SMOKE_FIX_MAX_RETRIES,
    smoke_fix_max_turns: int = DEFAULT_SMOKE_FIX_MAX_TURNS,
    smoke_health_check_url: str = "",
    smoke_health_check_timeout: int = DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT,
    e2e_command: str = "",
    e2e_timeout: int = DEFAULT_E2E_TIMEOUT,
    e2e_health_timeout: int = E2E_HEALTH_TIMEOUT,
    event_bus: EventBus | None = None,
    **kwargs: Any,
) -> None:
    """Full verify gate pipeline: build → test → e2e → scope → review → rules → verify → merge queue.

    Source: verifier.sh handle_change_done (lines 782-1453)
    """
    logger.info(
        "Change %s completed, running checks... (review_before_merge=%s, test_command=%s)",
        change_name, review_before_merge, test_command,
    )

    state = load_state(state_file)
    change = None
    for c in state.changes:
        if c.name == change_name:
            change = c
            break
    if not change:
        logger.error("Change %s not found in state", change_name)
        return

    wt_path = change.worktree_path or ""
    verify_retry_count = change.verify_retry_count

    # Section 12 task 12.8: `verify_retry_index` distinguishes first run
    # (0 → policy bypassed, every gate runs fully) from retries (≥1 →
    # cached/scoped policy consulted). Mirror it from `verify_retry_count`
    # on entry so the pipeline sees the correct index for THIS run; the
    # pipeline itself increments `verify_retry_count` on blocking
    # failures, so the NEXT invocation observes the bumped value.
    change.verify_retry_index = int(verify_retry_count or 0)
    update_change_field(
        state_file, change_name, "verify_retry_index",
        change.verify_retry_index,
    )

    if not wt_path:
        logger.warning("handle_change_done: wt_path empty for %s — critical checks will be skipped", change_name)

    # Update the per-worktree e2e manifest with actual spec files (task 11.1)
    if wt_path and os.path.isdir(wt_path):
        _e2e_dir = os.path.join(wt_path, "tests", "e2e")
        if os.path.isdir(_e2e_dir):
            _actual_specs = sorted([
                f"tests/e2e/{fn}" for fn in os.listdir(_e2e_dir)
                if fn.endswith((".spec.ts", ".spec.js"))
            ])
            if _actual_specs:
                from .paths import LineagePaths as _LP_vm
                _manifest_path = _LP_vm.e2e_manifest_for_worktree(wt_path)
                try:
                    _manifest = {}
                    if os.path.isfile(_manifest_path):
                        _manifest = json.loads(Path(_manifest_path).read_text())
                    _manifest["spec_files"] = _actual_specs
                    Path(_manifest_path).write_text(json.dumps(_manifest, indent=2))
                    logger.info("Updated e2e manifest (%s): %d spec files: %s", _manifest_path, len(_actual_specs), _actual_specs)
                except Exception as _e:
                    logger.debug("Failed to update e2e manifest: %s", _e)

    # ANOMALY: agent completed with 0 commits (task 3.1)
    if wt_path and os.path.isdir(wt_path):
        try:
            _main_branch = detect_default_branch(wt_path)
            _ahead_r = run_command(
                ["git", "rev-list", "--count", f"{_main_branch}..HEAD"],
                timeout=5, cwd=wt_path,
            )
            _ahead = int(_ahead_r.stdout.strip()) if _ahead_r.exit_code == 0 else -1
            if _ahead == 0:
                logger.warning(
                    "[ANOMALY] Agent for %s completed but 0 commits on branch "
                    "— possible false-done",
                    change_name,
                )
        except Exception as _e:
            logger.debug("Git commit count check failed: %s", _e)

    # ── Context window metrics — capture end tokens at loop completion ──
    if wt_path:
        # Use change-level model, fall back to directives default_model
        _ctx_model = change.model or ""
        if not _ctx_model:
            try:
                _st = load_state(state_file)
                _ctx_model = _st.extras.get("directives", {}).get("default_model", "")
            except Exception as _e:
                logger.debug("Model resolution from state failed: %s", _e)
        _capture_context_tokens_end(state_file, change_name, _read_loop_state(wt_path), model=_ctx_model)
        # Detect duplicate file reads across the change's sessions —
        # surfaces "agent re-read same file N times" waste signals.
        try:
            from .session_analysis import update_duplicate_reads
            update_duplicate_reads(state_file, change_name, wt_path)
        except Exception:
            logger.debug("duplicate_reads detection raised", exc_info=True)

    # ── Retry token tracking ──
    retry_tokens_start = change.extras.get("retry_tokens_start", 0)
    if retry_tokens_start > 0:
        loop_state = _read_loop_state(wt_path)
        current_tokens = int(loop_state.get("total_tokens", 0))
        retry_diff = max(0, current_tokens - retry_tokens_start)
        prev_retry_tokens = change.extras.get("gate_retry_tokens", 0)
        prev_retry_count = change.extras.get("gate_retry_count", 0)
        update_change_field(state_file, change_name, "gate_retry_tokens", prev_retry_tokens + retry_diff)
        update_change_field(state_file, change_name, "gate_retry_count", prev_retry_count + 1)
        update_change_field(state_file, change_name, "retry_tokens_start", 0)
        logger.info(
            "Verify gate: retry cost for %s: +%d tokens (total retries: %d)",
            change_name, retry_diff, prev_retry_count + 1,
        )

    # ── Merge-rebase fast path ──
    merge_rebase_pending = change.extras.get("merge_rebase_pending", False)
    if merge_rebase_pending:
        update_change_field(state_file, change_name, "merge_rebase_pending", False)
        logger.info("Change %s returning from agent-assisted rebase — testing merge cleanness", change_name)
        # Dry-run merge test is done by bash caller (merge_change)
        # This is a simplified path — the bash wrapper handles the full logic
        return

    uncommitted_check_result = "clean"

    # ── Step 0: Uncommitted work check ──
    if wt_path:
        from .git_utils import git_has_uncommitted_work

        has_uncommitted, uncommitted_summary = git_has_uncommitted_work(wt_path)
        if has_uncommitted:
            import subprocess as _sp
            logger.info("Verify gate: auto-committing leftover files in %s: %s", change_name, uncommitted_summary)
            _sp.run(["git", "-C", wt_path, "add", "-A"], capture_output=True, timeout=10)
            _sp.run(
                ["git", "-C", wt_path, "commit", "-m", "chore: commit leftover files (auto-committed by verify gate)"],
                capture_output=True, timeout=10,
            )
            has_uncommitted, uncommitted_summary = git_has_uncommitted_work(wt_path)

        if has_uncommitted:
            uncommitted_check_result = f"dirty: {uncommitted_summary}"
            reason = f"Uncommitted work in worktree: {uncommitted_summary}"
            logger.warning("Verify gate: %s for %s (even after auto-commit)", reason, change_name)
            update_change_field(state_file, change_name, "verify_result", reason)
            update_change_field(state_file, change_name, "uncommitted_check", uncommitted_check_result)

            if verify_retry_count < max_verify_retries:
                update_change_field(state_file, change_name, "status", "pending")
                update_change_field(state_file, change_name, "verify_retry_count", verify_retry_count + 1)
                update_change_field(state_file, change_name, "retry_context",
                                    f"## Verify Gate Failure\n\n{reason}\n\nPlease commit or remove all uncommitted files before declaring done.")
            else:
                update_change_field(state_file, change_name, "status", "failed")

            if event_bus:
                event_bus.emit("VERIFY_GATE", change=change_name, data={
                    "result": "fail", "reason": reason,
                    "uncommitted_check": uncommitted_check_result,
                })
            return

    # ── Step 0.5: Integrate main into branch before gates ──
    if wt_path:
        integration_retry_count = change.extras.get("integration_retry_count", 0)
        # verify-gate-resilience-fixes: directive-overridable; default 5 (was 3).
        _state = load_state(state_file)
        max_integration_retries = _state.extras.get("directives", {}).get(
            "max_integration_retries", DIRECTIVE_DEFAULTS["max_integration_retries"],
        )

        integration_result = _integrate_main_into_branch(
            wt_path, change_name, state_file, event_bus,
        )

        if integration_result == "conflict":
            if integration_retry_count < max_integration_retries:
                # Dispatch agent to resolve conflict on branch.
                # IMPORTANT: set `merge_rebase_pending=True` so dispatcher picks
                # `done_criteria="merge"` (checks `_check_merge_done` — branch
                # merges cleanly with main). Without this flag the dispatcher
                # falls through to `done_criteria="test"`, which never matches
                # a merge resolution, so the loop runs to max_iterations
                # while the agent no-ops in iter 2+ saying "merge already
                # done" — eventually the engine marks it stalled even though
                # the work was completed in iter 1.
                update_change_field(state_file, change_name, "integration_retry_count", integration_retry_count + 1)
                update_change_field(state_file, change_name, "merge_rebase_pending", True)
                update_change_field(state_file, change_name, "status", "verify-failed")
                update_change_field(state_file, change_name, "retry_context",
                    f"Integration merge conflict: main has diverged from your branch.\n\n"
                    f"Run `git merge origin/main` in the worktree to pull in main's changes.\n"
                    f"Resolve any conflicts, commit, and the pipeline will re-run gates.\n\n"
                    f"This is attempt {integration_retry_count + 1}/{max_integration_retries}."
                )
                from .dispatcher import resume_change
                _snapshot_retry_tokens(state_file, change_name, wt_path)
                resume_change(state_file, change_name)
                logger.info("Integration conflict for %s — agent dispatched to resolve", change_name)
                return
            else:
                update_change_field(state_file, change_name, "status", "integration-failed")
                logger.error("Integration failed for %s — retries exhausted", change_name)
                if event_bus:
                    event_bus.emit("INTEGRATION", change=change_name, data={"result": "failed", "reason": "retries_exhausted"})
                return

        if integration_result == "failed":
            update_change_field(state_file, change_name, "status", "integration-failed")
            logger.error("Integration git error for %s — marking failed", change_name)
            return

        # integration_result == "ok" — proceed to gates

    # ── Resolve gate config ──
    from .gate_profiles import resolve_gate_config
    from .profile_loader import load_profile

    profile = load_profile()
    directives = state.extras.get("directives", {})
    gc = resolve_gate_config(change, profile, directives)
    effective_max_retries = gc.max_retries if gc.max_retries is not None else max_verify_retries

    # ── Run gate pipeline ──
    from .gate_runner import GatePipeline

    _parallel_groups: list[set[str]] = []
    if profile is not None and hasattr(profile, "parallel_gate_groups"):
        try:
            _parallel_groups = list(profile.parallel_gate_groups() or [])
        except Exception:
            logger.warning(
                "parallel_gate_groups() threw — falling back to serial",
                exc_info=True,
            )

    # Pull max_consecutive_cache_uses from directives (section 12, default 2).
    _mccu = 2
    try:
        with locked_state(state_file) as _st_mccu:
            _mccu_val = (_st_mccu.extras.get("directives", {}) or {}).get(
                "max_consecutive_cache_uses", 2,
            )
            _mccu = int(_mccu_val) if _mccu_val is not None else 2
    except Exception:
        _mccu = 2

    pipeline = GatePipeline(
        gc, state_file, change_name, change,
        max_retries=effective_max_retries,
        event_bus=event_bus,
        parallel_groups=_parallel_groups,
        profile=profile,
        max_consecutive_cache_uses=_mccu,
    )

    # Review findings path for prior-findings injection into retry context
    from .paths import LineagePaths as _LP_vpf
    _findings_path = _LP_vpf(os.path.dirname(state_file)).review_findings

    # Register gates in execution order
    pipeline.register(
        "build",
        lambda: _execute_build_gate(change_name, change, wt_path, findings_path=_findings_path),
        own_retry_counter="build_fix_attempt_count",
        result_fields=("build_result", "gate_build_ms"),
    )
    pipeline.register(
        "test",
        lambda: _execute_test_gate(change_name, change, wt_path, test_command, test_timeout, findings_path=_findings_path),
        result_fields=("test_result", "gate_test_ms"),
    )
    # Register profile gates (e2e, lint from web module if available)
    if profile is not None and hasattr(profile, "register_gates"):
        try:
            for gd in profile.register_gates():
                if gd.phase != "pre-merge":
                    continue
                if gd.name == "e2e":
                    # Scope E2E to own spec files only (FIX 5) — same as
                    # merger's two-phase approach. Inherited specs are NOT
                    # re-run here (they'll be checked at merge integration).
                    _own_specs: list[str] | None = None
                    try:
                        from .merger import _detect_own_spec_files
                        _own_specs = _detect_own_spec_files(wt_path) or None
                        if _own_specs:
                            logger.info(
                                "Verify gate: scoping e2e to %d own spec(s) for %s: %s",
                                len(_own_specs), change_name,
                                [os.path.basename(s) for s in _own_specs],
                            )
                    except Exception as exc:
                        logger.warning(
                            "Verify gate: own-spec detection failed for %s — falling back to full suite: %s",
                            change_name, exc,
                        )
                    pipeline.register(
                        "e2e",
                        lambda gd=gd, sf=_own_specs: gd.executor(
                            change_name=change_name, change=change, wt_path=wt_path,
                            e2e_command=e2e_command, e2e_timeout=e2e_timeout,
                            e2e_health_timeout=e2e_health_timeout, profile=profile,
                            spec_files=sf,
                            scoped_subset=pipeline._gate_scoped_subset.get("e2e"),
                        ),
                        result_fields=gd.result_fields,
                    )
                else:
                    # Generic profile gate: standard signature
                    # (change_name, change, wt_path, profile). Covers lint,
                    # design-fidelity, i18n_check, and any future profile-
                    # registered gate without needing a name-keyed branch here.
                    pipeline.register(
                        gd.name,
                        lambda gd=gd: gd.executor(
                            change_name=change_name, change=change, wt_path=wt_path,
                            profile=profile,
                        ),
                        result_fields=gd.result_fields,
                    )
                    logger.debug(
                        "Registered profile gate: %s for %s (generic path)",
                        gd.name, change_name,
                    )
        except Exception:
            logger.warning("Failed to register profile gates", exc_info=True)

    pipeline.register(
        "scope_check",
        lambda: _execute_scope_gate(change_name, change, wt_path),
    )
    pipeline.register(
        "test_files",
        lambda: _execute_test_files_gate(change_name, change, wt_path, gc),
    )
    pipeline.register(
        "e2e_coverage",
        lambda: _execute_e2e_coverage_gate(change_name, change, wt_path, state_file),
    )
    pipeline.register(
        "spec_verify",
        lambda: _execute_spec_verify_gate(change_name, change, wt_path, state_file=state_file),
        result_fields=("spec_coverage_result", "gate_verify_ms"),
    )
    pipeline.register(
        "rules",
        lambda: _execute_rules_gate(change_name, change, wt_path, event_bus),
    )
    if review_before_merge:
        pipeline.register(
            "review",
            lambda: _execute_review_gate(
                change_name, change, wt_path, review_model,
                state_file, gc, change.verify_retry_count,
            ),
            extra_retries=getattr(gc, "review_extra_retries", 1),
            result_fields=("review_result", "gate_review_ms"),
        )

    # Execute pipeline — record wall time so we can enforce the cumulative
    # retry budget (section 13 of fix-replan-stuck-gate-and-decomposer).
    _pipeline_start_ms = int(time.monotonic() * 1000)
    action = pipeline.run()
    _pipeline_wall_ms = int(time.monotonic() * 1000) - _pipeline_start_ms

    # Atomically increment the cumulative retry wall time. Doing the
    # read-modify-write inside `locked_state` prevents a race with any
    # other poll cycle that might have bumped the same field while the
    # pipeline ran. Also read `max_retry_wall_time_ms` from the latest
    # state snapshot.
    _new_wall_total = 0
    _wall_budget = 0
    with locked_state(state_file) as _st_lock:
        _wall_budget = int(
            (_st_lock.extras.get("directives", {}) or {}).get(
                "max_retry_wall_time_ms", 1_800_000,
            ) or 0,
        )
        for _c in _st_lock.changes:
            if _c.name == change_name:
                _c.retry_wall_time_ms = int(_c.retry_wall_time_ms or 0) + _pipeline_wall_ms
                _new_wall_total = _c.retry_wall_time_ms
                break

    if _wall_budget > 0 and _new_wall_total >= _wall_budget:
        logger.error(
            "retry wall-time budget exhausted for %s: %d >= %d ms — escalating to fix-iss",
            change_name, _new_wall_total, _wall_budget,
        )
        # Snapshot the budget that was active at the failure point —
        # engine._recover_from_raised_limits compares this to the current
        # directive to decide whether to give the change another shot.
        update_change_field(
            state_file, change_name, "wall_time_budget_at_failure", _wall_budget,
        )
        update_change_field(state_file, change_name, "status", "failed:retry_wall_time_exhausted")
        if event_bus:
            event_bus.emit(
                "RETRY_WALL_TIME_EXHAUSTED",
                change=change_name,
                data={
                    "cumulative_ms": _new_wall_total,
                    "budget_ms": _wall_budget,
                    "retry_count": change.verify_retry_count + 1,
                },
            )
        try:
            from .issues.manager import escalate_change_to_fix_iss
            escalate_change_to_fix_iss(
                state_file=state_file,
                change_name=change_name,
                stop_gate=pipeline.stop_gate,
                findings=[],
                escalation_reason="retry_wall_time_exhausted",
                event_bus=event_bus,
            )
        except Exception:
            logger.warning(
                "escalate_change_to_fix_iss failed for %s (retry_wall_time_exhausted)",
                change_name, exc_info=True,
            )
        return

    # Handle retry/fail — resume agent if needed
    if action == "retry":
        _snapshot_retry_tokens(state_file, change_name, wt_path)
        from .dispatcher import resume_change
        resume_change(state_file, change_name)
        pipeline.commit_results()
        fingerprint = _compute_gate_fingerprint(pipeline.stop_gate, pipeline.results, wt_path=wt_path)
        update_change_field(state_file, change_name, "last_gate_fingerprint", fingerprint)
        if event_bus:
            gate_timings = {r.gate_name: r.duration_ms for r in pipeline.results if r.duration_ms}
            _retry_evt: dict = {
                "result": "retry", "stop_gate": pipeline.stop_gate,
                "fingerprint": fingerprint,
                "uncommitted_check": uncommitted_check_result,
                **{r.gate_name: r.status for r in pipeline.results},
                "gate_ms": gate_timings,
            }
            if getattr(pipeline, "parallel_group_runs", None):
                _retry_evt["parallel_group"] = pipeline.parallel_group_runs
            event_bus.emit("VERIFY_GATE", change=change_name, data=_retry_evt)
        send_notification(
            "set-orchestrate",
            f"Change '{change_name}' failed {pipeline.stop_gate} gate — retrying",
            "warning",
        )
        return

    if action == "failed":
        pipeline.commit_results()
        fingerprint = _compute_gate_fingerprint(pipeline.stop_gate, pipeline.results, wt_path=wt_path)
        update_change_field(state_file, change_name, "last_gate_fingerprint", fingerprint)
        if event_bus:
            gate_timings = {r.gate_name: r.duration_ms for r in pipeline.results if r.duration_ms}
            _failed_evt: dict = {
                "result": "failed", "stop_gate": pipeline.stop_gate,
                "fingerprint": fingerprint,
                "uncommitted_check": uncommitted_check_result,
                **{r.gate_name: r.status for r in pipeline.results},
                "gate_ms": gate_timings,
            }
            if getattr(pipeline, "parallel_group_runs", None):
                _failed_evt["parallel_group"] = pipeline.parallel_group_runs
            event_bus.emit("VERIFY_GATE", change=change_name, data=_failed_evt)
        send_notification(
            "set-orchestrate",
            f"Change '{change_name}' failed {pipeline.stop_gate} gate — retries exhausted",
            "critical",
        )
        # Section 10 task 10.4: auto-escalate to fix-iss on retry-budget
        # exhaustion. Parent is already marked "failed" by the pipeline;
        # we just upgrade the status and create the diagnostic child.
        update_change_field(state_file, change_name, "status", "failed:retry_budget_exhausted")
        try:
            _findings: list[dict] = []
            for r in pipeline.results:
                stats = getattr(r, "stats", None) or {}
                for f in stats.get("findings", []) or []:
                    if isinstance(f, dict):
                        _findings.append(f)
            from .issues.manager import escalate_change_to_fix_iss
            escalate_change_to_fix_iss(
                state_file=state_file,
                change_name=change_name,
                stop_gate=pipeline.stop_gate,
                findings=_findings,
                escalation_reason="retry_budget_exhausted",
                event_bus=event_bus,
            )
        except Exception:
            logger.warning(
                "escalate_change_to_fix_iss failed for %s (retry_budget_exhausted)",
                change_name, exc_info=True,
            )
        return

    # ── All gates passed — commit results and queue merge ──
    summary = pipeline.commit_results()

    gate_retry_tokens = change.extras.get("gate_retry_tokens", 0)
    gate_retry_count = change.extras.get("gate_retry_count", 0)

    logger.info(
        "Verify gate: %s total %dms (retries=%d, retry_tokens=%d)",
        change_name, summary.get("total_ms", 0), gate_retry_count, gate_retry_tokens,
    )

    # Pass path — compute + persist fingerprint too so the circuit breakers
    # can distinguish "passed" signatures across iterations ("pass" vs "pass
    # with warn-fails" are different gate states).
    pass_fingerprint = _compute_gate_fingerprint("", pipeline.results, wt_path=wt_path)
    update_change_field(state_file, change_name, "last_gate_fingerprint", pass_fingerprint)

    if event_bus:
        _gate_names = [
            "build", "test", "e2e", "lint", "smoke",
            "scope_check", "test_files", "e2e_coverage",
            "spec_verify", "rules", "review",
        ]
        gate_timings = {r.gate_name: r.duration_ms for r in pipeline.results if r.duration_ms}
        # Surface any infra-failure signals from individual gates so the
        # event consumer can filter infra anomalies from real code faults
        # without parsing verdict sidecars.
        _infra_fails = [
            {"gate": r.gate_name, "terminal_reason": r.terminal_reason}
            for r in pipeline.results
            if getattr(r, "infra_fail", False)
        ]
        _event_data: dict = {
            **summary,
            "retries": gate_retry_count,
            "retry_tokens": gate_retry_tokens,
            "uncommitted_check": uncommitted_check_result,
            "gate_profile": change.change_type or "feature",
            "gates_skipped": [g for g in _gate_names if not gc.should_run(g)],
            "gates_warn_only": [g for g in _gate_names if gc.is_warn_only(g)],
            "gate_ms": gate_timings,
            "fingerprint": pass_fingerprint,
        }
        if _infra_fails:
            _event_data["infra_fail"] = True
            _event_data["infra_fails"] = _infra_fails
        # Surface any parallel-batch decisions made during this pipeline run
        # so consumers can see which gates ran concurrently (task 8.5).
        if getattr(pipeline, "parallel_group_runs", None):
            _event_data["parallel_group"] = pipeline.parallel_group_runs
        event_bus.emit("VERIFY_GATE", change=change_name, data=_event_data)

    # Post-verify hooks (profile — non-blocking)
    if profile is not None and hasattr(profile, "post_verify_hooks"):
        try:
            profile.post_verify_hooks(change_name, wt_path, pipeline.results)
        except Exception:
            logger.warning("Post-verify hook failed for %s — continuing to merge", change_name, exc_info=True)

    # Mark done and queue merge
    update_change_field(state_file, change_name, "status", "done")
    update_change_field(state_file, change_name, "completed_at", datetime.now(timezone.utc).astimezone().isoformat())

    with locked_state(state_file) as state:
        state.changes_since_checkpoint += 1

    with locked_state(state_file) as state:
        if change_name not in state.merge_queue:
            state.merge_queue.append(change_name)
    logger.info("%s added to merge queue", change_name)


# ─── Helpers ─────────────────────────────────────────────────────────


def _detect_build_command(wt_path: str) -> str:
    """Detect build command from package.json scripts."""
    pkg_path = os.path.join(wt_path, "package.json")
    if not os.path.isfile(pkg_path):
        return ""
    try:
        with open(pkg_path) as f:
            pkg = json.load(f)
        scripts = pkg.get("scripts", {})
        if "build:ci" in scripts:
            return "build:ci"
        if "build" in scripts:
            return "build"
    except (json.JSONDecodeError, OSError):
        pass
    return ""


def _snapshot_retry_tokens(state_file: str, change_name: str, wt_path: str) -> None:
    """Snapshot current tokens before retry for cost tracking."""
    loop_state = _read_loop_state(wt_path) if wt_path else {}
    snap = int(loop_state.get("total_tokens", 0))
    update_change_field(state_file, change_name, "retry_tokens_start", snap)
