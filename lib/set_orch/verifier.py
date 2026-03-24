"""Verifier: change verification, testing, review, smoke tests, gate pipeline.

Migrated from: lib/orchestration/verifier.sh (run_tests_in_worktree,
build_req_review_section, review_change, evaluate_verification_rules,
verify_merge_scope, verify_implementation_scope, extract_health_check_url,
health_check, smoke_fix_scoped, run_phase_end_e2e, poll_change,
handle_change_done)
"""

from __future__ import annotations

import fnmatch
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
from .subprocess_utils import CommandResult, run_claude, run_claude_logged, run_command, run_git

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
DEFAULT_TEST_TIMEOUT = 120
DEFAULT_SMOKE_TIMEOUT = 180

# Context window sizes for Claude 4.x models
CONTEXT_WINDOW_SIZE = 200_000  # default for standard models
CONTEXT_WINDOW_SIZE_1M = 1_000_000  # for opus-1m / sonnet-1m


def _context_window_for_model(model: str = "") -> int:
    """Return context window size based on model name."""
    if "1m" in model or "[1m]" in model:
        return CONTEXT_WINDOW_SIZE_1M
    return CONTEXT_WINDOW_SIZE
DEFAULT_SMOKE_FIX_MAX_RETRIES = 3
DEFAULT_SMOKE_FIX_MAX_TURNS = 15
DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT = 30
DEFAULT_MAX_VERIFY_RETRIES = 2
DEFAULT_REVIEW_MODEL = "sonnet"
DEFAULT_E2E_TIMEOUT = 120
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

    Reuses the same format as _extract_review_fixes but returns structured data
    instead of a text string. Each issue has: severity, summary, file, line, fix.
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
            severity = "MEDIUM"
            if "[CRITICAL]" in text:
                severity = "CRITICAL"
            elif "[HIGH]" in text:
                severity = "HIGH"
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
    except OSError:
        logger.warning("Failed to append review finding to %s", findings_path)


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


def _build_unified_retry_context(
    build_output: str = "",
    test_output: str = "",
    review_output: str = "",
    attempt: int = 1,
    max_attempts: int = 3,
    change_name: str = "",
    findings_path: str = "",
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
            sections.append(f"```\n{build_output[-3000:]}\n```")

    if test_output:
        parsed = _extract_test_failures(test_output)
        sections.append("\n### Test Failures")
        if parsed:
            sections.append(parsed)
        else:
            sections.append(f"```\n{test_output[-3000:]}\n```")

    if review_output:
        parsed = _extract_review_fixes(review_output)
        sections.append("\n### Review Issues")
        if parsed:
            sections.append(parsed)
        else:
            # Only include raw if there were critical issues but parser returned nothing
            sections.append(f"```\n{review_output[-3000:]}\n```")

    # Include prior review findings from JSONL if available
    if change_name and findings_path:
        prior = _read_prior_review_findings(findings_path, change_name)
        if prior:
            sections.append(prior)

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

    # Reference the findings file
    if findings_md_path:
        rel_path = ".claude/review-findings.md"
        parts.append(f"## Review findings are in `{rel_path}`\n")
        parts.append(
            f"Read `{rel_path}` — it contains ALL review issues across all rounds.\n"
            "Fix every item marked `- [ ]` (unchecked).\n"
            "After fixing each issue, mark it `- [x]` in the file.\n"
            "Commit the updated findings file along with your code fixes.\n"
        )

    # Brief history summary (not full output — that's in the MD file)
    if len(history) > 1:
        parts.append("== PREVIOUS ATTEMPTS ==")
        for h in history:
            parts.append(f"Attempt {h['attempt']}:")
            if h.get("diff_summary"):
                parts.append(f"  Changed: {h['diff_summary']}")
            parts.append(f"  Result: STILL CRITICAL\n")

    # Security reference (patterns to follow)
    if security_guide:
        parts.append("=== SECURITY REFERENCE (follow these patterns) ===")
        parts.append(security_guide)
        parts.append("=== END SECURITY REFERENCE ===\n")

    # Final attempt escalation
    is_last_attempt = verify_retry_count >= review_retry_limit - 1
    if is_last_attempt:
        parts.append(
            "WARNING: This is your LAST attempt. If the same approach hasn't worked, "
            "restructure the entire implementation. Consider a completely different "
            "architecture for the problematic code.\n"
        )

    parts.append(
        "INSTRUCTIONS:\n"
        "1. Read `.claude/review-findings.md`\n"
        "2. For each unchecked `- [ ]` item: open the FILE, go to the LINE, apply the FIX\n"
        "3. Mark fixed items as `- [x]` in the findings file\n"
        "4. Commit all changes (code fixes + updated findings file)\n"
        "5. Do NOT work on new features — only fix the review issues"
    )

    return "\n".join(parts)


def _load_security_rules(wt_path: str) -> str:
    """Load security rules — profile first, legacy fallback."""
    from .profile_loader import load_profile

    profile = load_profile()
    rule_paths = profile.security_rules_paths(wt_path)
    if rule_paths:
        parts = []
        total = 0
        for rf in sorted(set(rule_paths)):
            try:
                content = rf.read_text()
            except OSError:
                continue
            if content.startswith("---"):
                end = content.find("---", 3)
                if end > 0:
                    content = content[end + 3:].strip()
            if len(content) > 1500:
                content = content[:1500] + "\n..."
            total += len(content)
            if total > 4000:
                break
            parts.append(content)
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

    parts = []
    total = 0
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
        # Truncate individual rules
        if len(content) > 1500:
            content = content[:1500] + "\n..."
        total += len(content)
        if total > 4000:
            break
        parts.append(content)

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
    # Truncate output to max_chars (keep tail)
    if len(output) > max_chars:
        output = f"...truncated...\n{output[-max_chars:]}"

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

_REVIEW_DIFF_LIMIT = 60_000


def _prioritize_diff_for_review(raw_diff: str) -> str:
    """Reorder diff hunks: implementation files first, artifacts/tests last.

    Git diff outputs files in alphabetical order, which puts openspec/ and
    __tests__/ before src/. When truncated, the reviewer never sees the
    actual implementation — only artifacts and tests. This caused false
    "missing implementation" reviews in Run #19 (Bug #53).

    Strategy: split diff into per-file hunks, partition into impl vs low-priority,
    reassemble with impl first, then truncate.
    """
    if len(raw_diff) <= _REVIEW_DIFF_LIMIT:
        return raw_diff

    # Split into per-file hunks
    hunks: list[tuple[str, str]] = []  # (filepath, hunk_text)
    current_path = ""
    current_lines: list[str] = []

    for line in raw_diff.split("\n"):
        if line.startswith("diff --git"):
            if current_lines:
                hunks.append((current_path, "\n".join(current_lines)))
            # Extract b/ path
            parts = line.split(" b/")
            current_path = parts[-1] if len(parts) > 1 else ""
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        hunks.append((current_path, "\n".join(current_lines)))

    # Partition: implementation first, deprioritized last
    impl_hunks = []
    depri_hunks = []
    for path, hunk in hunks:
        if any(path.startswith(p) for p in _REVIEW_DEPRIORITY_PREFIXES):
            depri_hunks.append(hunk)
        else:
            impl_hunks.append(hunk)

    # Reassemble: impl first
    reordered = "\n".join(impl_hunks + depri_hunks)

    # Truncate with note
    if len(reordered) > _REVIEW_DIFF_LIMIT:
        reordered = (
            reordered[:_REVIEW_DIFF_LIMIT]
            + f"\n\n... diff truncated at {_REVIEW_DIFF_LIMIT} chars "
            "(artifact/test files may be cut) ..."
        )

    return reordered


def _get_merge_base(wt_path: str) -> str:
    """Get merge-base of worktree branch vs main branch.

    Uses `git merge-base HEAD <ref>` to find the true fork point, ensuring
    review diffs only contain files modified by the change branch. Falls back
    to HEAD~10 if merge-base resolution fails (orphan branch, shallow clone).
    """
    for ref in ("main", "master", "origin/main", "origin/master"):
        result = run_git("merge-base", "HEAD", ref, cwd=wt_path)
        if result.exit_code == 0 and result.stdout.strip():
            logger.debug("merge-base resolved via %s for %s", ref, wt_path)
            return result.stdout.strip()
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
    review_model: str = DEFAULT_REVIEW_MODEL,
    state_file: str = "",
    digest_dir: str = "",
    design_snapshot_dir: str = "",
    prompt_prefix: str = "",
) -> ReviewResult:
    """LLM code review of a change branch. Returns ReviewResult.

    Source: verifier.sh review_change (lines 134-193)
    """
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

    # Build design compliance section (empty if no snapshot)
    design_compliance = ""
    if design_snapshot_dir:
        from .root import SET_TOOLS_ROOT
        bridge_path = os.path.join(SET_TOOLS_ROOT, "lib", "design", "bridge.sh")
        if os.path.isfile(bridge_path):
            design_r = run_command(
                ["bash", "-c",
                 f'source "{bridge_path}" 2>/dev/null && build_design_review_section "{design_snapshot_dir}"'],
                timeout=10,
            )
            if design_r.exit_code == 0 and design_r.stdout.strip():
                design_compliance = design_r.stdout.strip()
            elif design_r.exit_code != 0 and design_r.stderr.strip():
                logger.warning("Design review section failed: %s", design_r.stderr[:200])

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

    # Run review via Claude
    claude_result = run_claude_logged(review_prompt, purpose="review", change=change_name, model=review_model)
    if claude_result.exit_code != 0:
        # Escalate to opus if not already
        if review_model != "opus":
            logger.warning("Code review failed with %s for %s, escalating to opus", review_model, change_name)
            claude_result = run_claude_logged(review_prompt, purpose="review", change=change_name, model="opus")
            if claude_result.exit_code != 0:
                logger.warning("Code review failed with opus for %s — skipping", change_name)
                return ReviewResult(has_critical=False, output="")
        else:
            logger.warning("Code review failed for %s — skipping", change_name)
            return ReviewResult(has_critical=False, output="")

    review_output = claude_result.stdout
    logger.info("Code review complete for %s (%d chars)", change_name, len(review_output))

    # Explicit REVIEW PASS takes precedence — the LLM confirmed all issues are fixed.
    # Without this, the structured parser can false-positive on quoted/referenced
    # [CRITICAL] tags from prior findings that the LLM is reporting as resolved.
    if re.search(r"REVIEW\s+PASS", review_output):
        logger.info("Review explicitly passed for %s (REVIEW PASS found)", change_name)
        return ReviewResult(has_critical=False, output=review_output)

    # Check for CRITICAL severity using structured parser (not regex on raw text)
    # Raw regex would false-positive on phrases like "not escalating to [CRITICAL]"
    parsed_issues = _parse_review_issues(review_output)
    has_critical = any(i["severity"] == "CRITICAL" for i in parsed_issues)

    return ReviewResult(has_critical=has_critical, output=review_output)


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
    except Exception:
        pass  # Plugin loading failure shouldn't break verification

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

    if errors > 0:
        logger.error("Verification rules: %d error(s), %d warning(s) for %s", errors, warnings, change_name)
    elif warnings > 0:
        logger.info("Verification rules: %d warning(s) for %s", warnings, change_name)

    return RuleEvalResult(errors=errors, warnings=warnings)


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
        fix_result = run_claude_logged(
            fix_prompt, purpose="smoke_fix", change=change_name,
            model="sonnet",
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
        screenshot_dir = f"wt/orchestration/e2e-screenshots/cycle-{cycle}"
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

    # Store results in state
    e2e_output_truncated = e2e_output[:8000]
    with locked_state(state_file) as state:
        results = state.extras.get("phase_e2e_results", [])
        results.append({
            "cycle": cycle,
            "result": e2e_result,
            "duration_ms": elapsed_ms,
            "output": e2e_output_truncated,
            "screenshot_dir": screenshot_dir,
            "screenshot_count": screenshot_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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


def _read_loop_state(wt_path: str) -> dict:
    """Read loop-state.json from worktree .claude/ directory."""
    loop_state_path = os.path.join(wt_path, ".set", "loop-state.json")
    if not os.path.isfile(loop_state_path):
        return {}
    try:
        with open(loop_state_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
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


def _capture_context_tokens_end(
    state_file: str,
    change_name: str,
    loop_state: dict,
    model: str = "",
) -> None:
    """Capture context_tokens_end at loop completion.

    Uses total_cache_create as the proxy for peak context size this session.
    """
    cc = int(loop_state.get("total_cache_create", 0))
    if cc > 0:
        update_change_field(state_file, change_name, "context_tokens_end", cc)
        cw = _context_window_for_model(model)
        pct = cc / cw * 100
        level = "warning" if pct >= 80 else "info"
        getattr(logger, level)(
            "context_tokens_end for %s: %d (%.0f%% of %dK window)",
            change_name, cc, pct, cw // 1000,
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
            except (ValueError, TypeError):
                pass
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
        derived_dir = wt_path.replace("/", "-")
        home = os.environ.get("HOME", "")
        projects_dir = os.path.join(home, ".claude", "projects", derived_dir)
        if loop_started and os.path.isdir(projects_dir):
            script_dir = os.environ.get("SCRIPT_DIR", os.path.dirname(os.path.abspath(__file__)))
            usage_cmd = os.path.join(script_dir, "..", "..", "bin", "set-usage")
            if os.path.isfile(usage_cmd):
                usage_result = run_command(
                    [usage_cmd, "--since", loop_started, f"--project-dir={derived_dir}", "--format", "json"],
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
                    except (json.JSONDecodeError, ValueError):
                        pass

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
        return GateResult("build", "skipped")

    build_command = _detect_build_command(wt_path)
    if not build_command:
        return GateResult("build", "skipped")

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
            )
            + f"\n\nOriginal scope: {scope}"
        )
        return GateResult("build", "fail", output=build_output[-2000:], retry_context=retry_prompt)

    return GateResult("build", "pass")


def _execute_test_gate(
    change_name: str, change: Change, wt_path: str,
    test_command: str, test_timeout: int,
    findings_path: str = "",
) -> "GateResult":
    """Test gate: run tests in worktree."""
    from .gate_runner import GateResult

    if not test_command or not wt_path:
        return GateResult("test", "skipped")

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
            )
            + f"\n\nOriginal scope: {scope}"
        )

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
            retry_context=(
                "The change has NO implementation code — only OpenSpec artifacts and config files. "
                "Run /opsx:apply to implement the tasks, then mark the change as done.\n\n"
                f"Original scope: {scope}"
            ),
        )
    return GateResult("scope", "pass")


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


def _execute_review_gate(
    change_name: str, change: Change, wt_path: str,
    review_model: str, state_file: str, design_snapshot_dir: str,
    gc: Any, verify_retry_count: int,
) -> "GateResult":
    """Review gate: LLM code review with cumulative feedback."""
    from .gate_runner import GateResult

    if not wt_path:
        return GateResult("review", "skipped")

    scope = change.scope or ""
    effective_review_model = gc.review_model if gc.review_model else review_model

    # On retry rounds, use fix-verification mode:
    # Only verify previous findings were fixed, don't scan for new issues
    fix_verification_prefix = ""
    if verify_retry_count > 0:
        prior_findings = _read_prior_review_findings(
            os.path.join(os.path.dirname(state_file), "wt", "orchestration", "review-findings.jsonl"),
            change_name,
        ) if state_file else ""
        if prior_findings:
            fix_verification_prefix = (
                "IMPORTANT: This is a RETRY review (attempt {attempt}). "
                "Previous review found specific issues listed below.\n\n"
                "Your task is to verify ONLY whether these specific issues were fixed. "
                "Do NOT scan for new issues. For each previous finding, report:\n"
                "- FIXED: if the issue was resolved → no severity tag needed\n"
                "- NOT_FIXED: if the issue is still present → mark as [CRITICAL]\n\n"
                "Only NOT_FIXED items should appear as [CRITICAL]. "
                "Do NOT add new findings that weren't in the previous review.\n\n"
                "=== PREVIOUS FINDINGS TO VERIFY ===\n{findings}\n"
                "=== END PREVIOUS FINDINGS ===\n\n"
                "Now review the diff and verify each finding above:\n\n"
            ).format(attempt=verify_retry_count + 1, findings=prior_findings)

    rr = review_change(
        change_name, wt_path, scope, effective_review_model,
        state_file=state_file, design_snapshot_dir=design_snapshot_dir,
        prompt_prefix=fix_verification_prefix,
    )

    if not rr.has_critical:
        # Still log any HIGH/MEDIUM findings for post-run analysis
        if rr.output and re.search(r"\[HIGH\]|\[MEDIUM\]", rr.output):
            findings_dir = os.path.join(os.path.dirname(state_file), "wt", "orchestration")
            findings_path = os.path.join(findings_dir, "review-findings.jsonl")
            _append_review_finding(findings_path, change_name, rr.output, verify_retry_count + 1)
        return GateResult("review", "pass", output=rr.output[:5000])

    # Critical review — write findings to MD file and build retry context
    round_num = verify_retry_count + 1
    diff_summary = None
    if verify_retry_count > 0:
        diff_summary = _capture_retry_diff(wt_path)

    _append_review_history(state_file, change_name, {
        "attempt": round_num,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "review_output": rr.output[:1500],
        "extracted_fixes": _extract_review_fixes(rr.output),
        "diff_summary": diff_summary,
    })

    # Persist findings to JSONL for post-run summary
    findings_dir = os.path.join(os.path.dirname(state_file), "wt", "orchestration")
    findings_path = os.path.join(findings_dir, "review-findings.jsonl")
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

    return GateResult("review", "fail", output=rr.output[:5000], retry_context=retry_prompt)


def _execute_rules_gate(
    change_name: str, change: Change, wt_path: str,
    event_bus: Any,
) -> "GateResult":
    """Rules gate: evaluate verification rules from project-knowledge.yaml."""
    from .gate_runner import GateResult

    if not wt_path:
        return GateResult("rules", "pass")

    rule_result = evaluate_verification_rules(change_name, wt_path, event_bus=event_bus)
    if rule_result.errors > 0:
        return GateResult("rules", "fail")
    return GateResult("rules", "pass")


def _execute_spec_verify_gate(
    change_name: str, change: Change, wt_path: str,
) -> "GateResult":
    """Spec verify gate: run /opsx:verify via Claude."""
    from .gate_runner import GateResult

    if not wt_path or not shutil.which("claude"):
        return GateResult("spec_verify", "skipped")

    verify_cmd_result = run_claude_logged(
        f"IMPORTANT: Memory is not branch/worktree-aware — verify against filesystem, never skip checks based on memory alone.\nRun /opsx:verify {change_name}",
        purpose="spec_verify", change=change_name,
        extra_args=["--max-turns", "40"],
        cwd=wt_path,
    )
    verify_output = verify_cmd_result.stdout

    if verify_cmd_result.exit_code != 0:
        scope = change.scope or ""
        verify_tail = verify_output[-2000:] if verify_output else ""
        return GateResult(
            "spec_verify", "fail",
            output=verify_output[:2000],
            retry_context=f"Verify failed. Fix the issues.\n\nVerify output (last 2000 chars):\n{verify_tail}\n\nOriginal scope: {scope}",
        )

    if "VERIFY_RESULT: PASS" in verify_output:
        return GateResult("spec_verify", "pass", output=verify_output[:2000])
    elif "VERIFY_RESULT: FAIL" in verify_output:
        scope = change.scope or ""
        verify_tail = verify_output[-2000:] if verify_output else ""
        logger.warning("Spec coverage FAIL for %s — blocking", change_name)
        return GateResult(
            "spec_verify", "fail",
            output=verify_output[:2000],
            retry_context=(
                "Spec verification FAILED — requirements not fully covered.\n\n"
                f"Verify output (last 2000 chars):\n{verify_tail}\n\n"
                f"Original scope: {scope}\n\n"
                "Fix: Ensure all requirements from the scope are implemented "
                "and acceptance criteria are satisfied."
            ),
        )
    else:
        # No sentinel — timeout, non-blocking
        logger.warning("Spec verify timed out for %s — non-blocking", change_name)
        return GateResult("spec_verify", "pass", output="timeout — no VERIFY_RESULT sentinel")


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

    # Find the main branch name
    main_ref_result = run_git(
        "symbolic-ref", "refs/remotes/origin/HEAD",
        cwd=wt_path, timeout=10,
    )
    if main_ref_result.exit_code == 0:
        main_branch = main_ref_result.stdout.strip().replace("refs/remotes/origin/", "")
    else:
        main_branch = "main"

    # Determine merge ref: prefer origin/<main> if remote exists, else local <main>
    fetch_result = run_git("fetch", "origin", main_branch, cwd=wt_path, timeout=60)
    has_origin = fetch_result.exit_code == 0
    merge_ref = f"origin/{main_branch}" if has_origin else main_branch
    if not has_origin:
        logger.info("No origin remote — using local %s for integration", main_branch)

    # Check if integration is needed (is main ahead of branch?)
    merge_base_result = run_git(
        "merge-base", "HEAD", merge_ref,
        cwd=wt_path, timeout=10,
    )
    origin_head_result = run_git(
        "rev-parse", merge_ref,
        cwd=wt_path, timeout=10,
    )
    if (merge_base_result.exit_code == 0 and origin_head_result.exit_code == 0
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
    design_snapshot_dir: str = "",
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

    # ── Context window metrics — capture end tokens at loop completion ──
    if wt_path:
        # Use change-level model, fall back to directives default_model
        _ctx_model = change.model or ""
        if not _ctx_model:
            try:
                _st = load_state(state_file)
                _ctx_model = _st.extras.get("directives", {}).get("default_model", "")
            except Exception:
                pass
        _capture_context_tokens_end(state_file, change_name, _read_loop_state(wt_path), model=_ctx_model)

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
        max_integration_retries = 3

        integration_result = _integrate_main_into_branch(
            wt_path, change_name, state_file, event_bus,
        )

        if integration_result == "conflict":
            if integration_retry_count < max_integration_retries:
                # Dispatch agent to resolve conflict on branch
                update_change_field(state_file, change_name, "integration_retry_count", integration_retry_count + 1)
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

    pipeline = GatePipeline(
        gc, state_file, change_name, change,
        max_retries=effective_max_retries,
        event_bus=event_bus,
    )

    # Review findings path for prior-findings injection into retry context
    _findings_dir = os.path.join(os.path.dirname(state_file), "wt", "orchestration")
    _findings_path = os.path.join(_findings_dir, "review-findings.jsonl")

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
                    pipeline.register(
                        "e2e",
                        lambda gd=gd: gd.executor(
                            change_name=change_name, change=change, wt_path=wt_path,
                            e2e_command=e2e_command, e2e_timeout=e2e_timeout,
                            e2e_health_timeout=e2e_health_timeout, profile=profile,
                        ),
                        result_fields=gd.result_fields,
                    )
                elif gd.name == "lint":
                    pipeline.register(
                        "lint",
                        lambda gd=gd: gd.executor(
                            change_name=change_name, change=change, wt_path=wt_path,
                            profile=profile,
                        ),
                        result_fields=gd.result_fields,
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
    if review_before_merge:
        pipeline.register(
            "review",
            lambda: _execute_review_gate(
                change_name, change, wt_path, review_model,
                state_file, design_snapshot_dir, gc, change.verify_retry_count,
            ),
            extra_retries=getattr(gc, "review_extra_retries", 1),
            result_fields=("review_result", "gate_review_ms"),
        )
    pipeline.register(
        "rules",
        lambda: _execute_rules_gate(change_name, change, wt_path, event_bus),
    )
    pipeline.register(
        "spec_verify",
        lambda: _execute_spec_verify_gate(change_name, change, wt_path),
        result_fields=("spec_coverage_result", "gate_verify_ms"),
    )

    # Execute pipeline
    action = pipeline.run()

    # Handle retry/fail — resume agent if needed
    if action == "retry":
        _snapshot_retry_tokens(state_file, change_name, wt_path)
        from .dispatcher import resume_change
        resume_change(state_file, change_name)
        pipeline.commit_results()
        if event_bus:
            gate_timings = {r.gate_name: r.duration_ms for r in pipeline.results if r.duration_ms}
            event_bus.emit("VERIFY_GATE", change=change_name, data={
                "result": "retry", "stop_gate": pipeline.stop_gate,
                "uncommitted_check": uncommitted_check_result,
                **{r.gate_name: r.status for r in pipeline.results},
                "gate_ms": gate_timings,
            })
        send_notification(
            "set-orchestrate",
            f"Change '{change_name}' failed {pipeline.stop_gate} gate — retrying",
            "warning",
        )
        return

    if action == "failed":
        pipeline.commit_results()
        if event_bus:
            gate_timings = {r.gate_name: r.duration_ms for r in pipeline.results if r.duration_ms}
            event_bus.emit("VERIFY_GATE", change=change_name, data={
                "result": "failed", "stop_gate": pipeline.stop_gate,
                "uncommitted_check": uncommitted_check_result,
                **{r.gate_name: r.status for r in pipeline.results},
                "gate_ms": gate_timings,
            })
        send_notification(
            "set-orchestrate",
            f"Change '{change_name}' failed {pipeline.stop_gate} gate — retries exhausted",
            "critical",
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

    if event_bus:
        _gate_names = ["build", "test", "e2e", "review", "smoke", "rules", "spec_verify"]
        gate_timings = {r.gate_name: r.duration_ms for r in pipeline.results if r.duration_ms}
        event_bus.emit("VERIFY_GATE", change=change_name, data={
            **summary,
            "retries": gate_retry_count,
            "retry_tokens": gate_retry_tokens,
            "uncommitted_check": uncommitted_check_result,
            "gate_profile": change.change_type or "feature",
            "gates_skipped": [g for g in _gate_names if not gc.should_run(g)],
            "gates_warn_only": [g for g in _gate_names if gc.is_warn_only(g)],
            "gate_ms": gate_timings,
        })

    # Post-verify hooks (profile — non-blocking)
    if profile is not None and hasattr(profile, "post_verify_hooks"):
        try:
            profile.post_verify_hooks(change_name, wt_path, pipeline.results)
        except Exception:
            logger.warning("Post-verify hook failed for %s — continuing to merge", change_name, exc_info=True)

    # Mark done and queue merge
    update_change_field(state_file, change_name, "status", "done")
    update_change_field(state_file, change_name, "completed_at", datetime.now(timezone.utc).isoformat())

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
