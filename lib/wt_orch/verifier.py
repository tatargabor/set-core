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
from .subprocess_utils import CommandResult, run_claude, run_command, run_git

logger = logging.getLogger(__name__)

# Paths considered non-implementation (filtered in scope checks)
# Source: verifier.sh verify_merge_scope / verify_implementation_scope
ARTIFACT_PREFIXES = (
    "openspec/changes/",
    "openspec/specs/",
    ".claude/",
    "orchestration",
    ".wt-tools/",
)

BOOTSTRAP_FILES = {
    "prisma/dev.db", ".gitignore",
}

BOOTSTRAP_PATTERNS = ("*.lock", "*-lock.yaml", "*.lockb", "jest.config.*", "jest.setup.*", ".env*")

# Default timeouts
DEFAULT_TEST_TIMEOUT = 120
DEFAULT_SMOKE_TIMEOUT = 180
DEFAULT_SMOKE_FIX_MAX_RETRIES = 3
DEFAULT_SMOKE_FIX_MAX_TURNS = 15
DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT = 30
DEFAULT_MAX_VERIFY_RETRIES = 2
DEFAULT_REVIEW_MODEL = "sonnet"
DEFAULT_E2E_TIMEOUT = 120
E2E_PORT_BASE = 3100


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

    Looks for web security rule files (deployed by wt-project init) and returns
    a condensed version for injection into review retry prompts.
    """
    rules_dir = Path(wt_path) / ".claude" / "rules"
    if not rules_dir.is_dir():
        return ""

    # Collect web-related rule files (may be in rules/ or rules/web/)
    rule_files = []
    for pattern in ("web/*.md", "wt-web-*.md", "*web-security*.md", "*auth-middleware*.md"):
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


def _get_merge_base(wt_path: str) -> str:
    """Get merge-base of worktree branch vs origin/HEAD, main, or master."""
    for ref in ("origin/HEAD", "main", "master"):
        result = run_git("merge-base", "HEAD", ref, cwd=wt_path)
        if result.exit_code == 0 and result.stdout.strip():
            return result.stdout.strip()
    return "HEAD~5"


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

    # Build assigned requirements section
    section = "\n## Assigned Requirements (this change owns these)"
    for req_id in change.requirements:
        req = digest_reqs.get(req_id)
        if not req:
            section += f"\n- {req_id}: (not found in digest)"
            logger.warning("build_req_review_section: %s not found in digest requirements.json", req_id)
        else:
            title = req.get("title", "")
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

    # Add coverage check instruction
    section += """

## Requirement Coverage Check
For each ASSIGNED requirement above, verify the diff contains implementation evidence.
If a requirement has NO corresponding code in the diff, report:
  ISSUE: [CRITICAL] REQ-ID has no implementation in the diff
Cross-cutting requirements are for awareness — do not flag them as missing."""

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

    diff_output = diff_result.stdout
    if len(diff_output) > 30000:
        diff_output = diff_output[:30000] + "\n...diff truncated at 30000 chars..."

    # Build requirement section
    req_section = ""
    if state_file:
        req_section = build_req_review_section(change_name, state_file, digest_dir)

    # Build design compliance section (empty if no snapshot)
    design_compliance = ""
    if design_snapshot_dir:
        from .root import WT_TOOLS_ROOT
        bridge_path = os.path.join(WT_TOOLS_ROOT, "lib", "design", "bridge.sh")
        if os.path.isfile(bridge_path):
            design_r = run_command(
                ["bash", "-c",
                 f'source "{bridge_path}" 2>/dev/null && build_design_review_section "{design_snapshot_dir}"'],
                timeout=5,
            )
            if design_r.exit_code == 0 and design_r.stdout.strip():
                design_compliance = design_r.stdout.strip()
            elif design_r.exit_code != 0 and design_r.stderr.strip():
                logger.warning("Design review section failed: %s", design_r.stderr[:200])

    # Build review prompt via template
    template_input = json.dumps({
        "scope": scope,
        "diff_output": diff_output,
        "req_section": req_section,
        "design_compliance": design_compliance,
    })

    template_result = run_command(
        ["wt-orch-core", "template", "review", "--input-file", "-"],
        stdin_data=template_input,
    )
    if template_result.exit_code != 0:
        logger.warning("Failed to render review template for %s", change_name)
        return ReviewResult(has_critical=False, output="")

    review_prompt = template_result.stdout

    # Run review via Claude
    claude_result = run_claude(review_prompt, model=review_model)
    if claude_result.exit_code != 0:
        # Escalate to opus if not already
        if review_model != "opus":
            logger.warning("Code review failed with %s for %s, escalating to opus", review_model, change_name)
            claude_result = run_claude(review_prompt, model="opus")
            if claude_result.exit_code != 0:
                logger.warning("Code review failed with opus for %s — skipping", change_name)
                return ReviewResult(has_critical=False, output="")
        else:
            logger.warning("Code review failed for %s — skipping", change_name)
            return ReviewResult(has_critical=False, output="")

    review_output = claude_result.stdout
    logger.info("Code review complete for %s (%d chars)", change_name, len(review_output))

    # Check for CRITICAL severity
    has_critical = bool(re.search(
        r"\[CRITICAL\]|severity.*critical|CRITICAL:", review_output, re.IGNORECASE,
    ))

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
    src = os.path.join(cwd or ".", "test-results")
    if not os.path.isdir(src):
        return 0
    dst = os.path.join("wt", "orchestration", "e2e-screenshots", change_name)
    os.makedirs(dst, exist_ok=True)
    count = 0
    for root, _dirs, files in os.walk(src):
        for fname in files:
            if fname.endswith(".png"):
                shutil.copy2(os.path.join(root, fname), dst)
                count += 1
    return count


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
            ["wt-orch-core", "template", "fix", "--input-file", "-"],
            stdin_data=template_input,
        )
        if template_result.exit_code != 0:
            logger.error("Failed to render fix template for %s attempt %d", change_name, attempt)
            continue

        fix_prompt = template_result.stdout
        fix_result = run_claude(
            fix_prompt, model="sonnet",
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
    import random

    logger.info("Phase-end E2E: starting on main branch")
    if event_bus:
        event_bus.emit("PHASE_E2E_STARTED", data={})

    e2e_port = E2E_PORT_BASE + random.randint(0, 99)
    start_ms = int(time.monotonic() * 1000)

    # Screenshot directory
    state = load_state(state_file)
    cycle = state.extras.get("replan_cycle", 0)
    screenshot_dir = f"wt/orchestration/e2e-screenshots/cycle-{cycle}"
    os.makedirs(screenshot_dir, exist_ok=True)

    # Run E2E
    env = {"PLAYWRIGHT_OUTPUT_DIR": screenshot_dir, "PW_PORT": str(e2e_port)}
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

    # Cleanup dev server
    run_command(["pkill", "-f", f"pnpm dev.*--port {e2e_port}"], timeout=5)
    run_command(["pkill", "-f", f"next dev.*--port {e2e_port}"], timeout=5)

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
            "wt-orchestrate",
            "Phase-end E2E failed! Failures will be included in replan context.",
            "warning",
        )
        update_state_field(state_file, "phase_e2e_failure_context", e2e_output_truncated)
    else:
        send_notification(
            "wt-orchestrate",
            "Phase-end E2E passed! All integrated tests green.",
            "normal",
        )
        update_state_field(state_file, "phase_e2e_failure_context", "")

    return e2e_result == "pass"


# ─── Poll Change ─────────────────────────────────────────────────────
# Source: verifier.sh poll_change (lines 597-778)


def _read_loop_state(wt_path: str) -> dict:
    """Read loop-state.json from worktree .claude/ directory."""
    loop_state_path = os.path.join(wt_path, ".claude", "loop-state.json")
    if not os.path.isfile(loop_state_path):
        return {}
    try:
        with open(loop_state_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _read_loop_state_mtime(wt_path: str) -> int:
    """Get mtime of loop-state.json as epoch seconds."""
    loop_state_path = os.path.join(wt_path, ".claude", "loop-state.json")
    try:
        return int(os.path.getmtime(loop_state_path))
    except OSError:
        return 0


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
            pid_result = check_pid(ralph_pid, "wt-loop")
            if not pid_result.alive or not pid_result.match:
                logger.error(
                    "Terminal process %d for %s is dead, no loop-state found",
                    ralph_pid, change_name,
                )
                update_change_field(state_file, change_name, "status", "failed")
                return "dead"
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

    # Fallback: if loop-state has 0 tokens, try wt-usage
    if tokens == 0:
        loop_started = loop_state.get("started_at", "")
        derived_dir = wt_path.replace("/", "-")
        home = os.environ.get("HOME", "")
        projects_dir = os.path.join(home, ".claude", "projects", derived_dir)
        if loop_started and os.path.isdir(projects_dir):
            script_dir = os.environ.get("SCRIPT_DIR", os.path.dirname(os.path.abspath(__file__)))
            usage_cmd = os.path.join(script_dir, "..", "..", "bin", "wt-usage")
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
                pid_result = check_pid(terminal_pid, "wt-loop")
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
                "wt-orchestrate",
                f"Change '{change_name}' needs human action. Run: wt-manual show {change_name}",
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
                "wt-orchestrate",
                f"Change '{change_name}' budget checkpoint — run 'wt-loop resume' to continue",
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

    gate_test_ms = 0
    gate_review_ms = 0
    gate_verify_ms = 0
    gate_build_ms = 0
    gate_e2e_ms = 0

    # Per-change skip flags
    skip_test = change.skip_test
    skip_review = change.skip_review

    # ── Step 1: Build verification (VG-BUILD) ──
    if wt_path and os.path.isfile(os.path.join(wt_path, "package.json")):
        build_command = _detect_build_command(wt_path)
        if build_command:
            from .dispatcher import _detect_package_manager
            pm = _detect_package_manager(wt_path) or "npm"

            logger.info("Verify gate: build start for %s (%s run %s)", change_name, pm, build_command)
            start_ms = int(time.monotonic() * 1000)

            build_result = run_command(
                [pm, "run", build_command], timeout=600, cwd=wt_path,
            )
            gate_build_ms = int(time.monotonic() * 1000) - start_ms
            update_change_field(state_file, change_name, "gate_build_ms", gate_build_ms)

            if build_result.exit_code != 0:
                logger.error("Verify gate: build failed for %s (exit %d)", change_name, build_result.exit_code)
                update_change_field(state_file, change_name, "build_result", "fail")
                build_output = build_result.stdout + build_result.stderr
                update_change_field(state_file, change_name, "build_output", build_output[-2000:])

                # Retry logic
                if verify_retry_count < max_verify_retries:
                    verify_retry_count += 1
                    update_change_field(state_file, change_name, "verify_retry_count", verify_retry_count)
                    update_change_field(state_file, change_name, "status", "verify-failed")
                    scope = change.scope or ""
                    retry_prompt = (
                        f"Build failed after implementation. Fix the build errors.\n\n"
                        f"Build command: {pm} run {build_command}\n"
                        f"Build output (last 2000 chars):\n{build_output[-2000:]}\n\n"
                        f"Original scope: {scope}"
                    )
                    update_change_field(state_file, change_name, "retry_context", retry_prompt)
                    _snapshot_retry_tokens(state_file, change_name, wt_path)
                    from .dispatcher import resume_change
                    resume_change(state_file, change_name)
                    return

                update_change_field(state_file, change_name, "status", "failed")
                send_notification("wt-orchestrate", f"Change '{change_name}' failed build after {max_verify_retries} retries", "critical")
                return

            logger.info("Verify gate: build passed for %s (%dms)", change_name, gate_build_ms)
            update_change_field(state_file, change_name, "build_result", "pass")

    # ── Step 2: Run tests (VG-1) ──
    test_result_str = "skip"
    test_output = ""
    if skip_test:
        test_result_str = "skipped"
        logger.info("Verify gate: tests skipped for %s (skip_test=true)", change_name)
    elif test_command and wt_path:
        update_change_field(state_file, change_name, "status", "verifying")
        logger.info("Verify gate: test start for %s", change_name)

        start_ms = int(time.monotonic() * 1000)
        tr = run_tests_in_worktree(wt_path, test_command, test_timeout)
        gate_test_ms = int(time.monotonic() * 1000) - start_ms
        update_change_field(state_file, change_name, "gate_test_ms", gate_test_ms)

        test_result_str = "pass" if tr.passed else "fail"
        test_output = tr.output

        if tr.stats and (tr.stats.get("passed", 0) + tr.stats.get("failed", 0)) > 0:
            update_change_field(state_file, change_name, "test_stats", tr.stats)

    update_change_field(state_file, change_name, "test_result", test_result_str)
    update_change_field(state_file, change_name, "test_output", test_output[:2000])

    if test_result_str == "fail":
        if verify_retry_count < max_verify_retries:
            verify_retry_count += 1
            update_change_field(state_file, change_name, "verify_retry_count", verify_retry_count)
            update_change_field(state_file, change_name, "status", "verify-failed")
            scope = change.scope or ""
            retry_prompt = (
                f"Tests failed after implementation. Fix the failing tests.\n\n"
                f"Test command: {test_command}\nTest output:\n{test_output}\n\n"
                f"Original scope: {scope}"
            )
            update_change_field(state_file, change_name, "retry_context", retry_prompt)
            _snapshot_retry_tokens(state_file, change_name, wt_path)
            from .dispatcher import resume_change
            resume_change(state_file, change_name)
            return

        update_change_field(state_file, change_name, "status", "failed")
        send_notification("wt-orchestrate", f"Change '{change_name}' failed tests after {max_verify_retries} retries", "critical")
        return

    # ── Step 3: E2E tests (VG-E2E) ──
    e2e_result_str = "skip"
    if e2e_command and wt_path:
        import random
        e2e_test_count = _count_e2e_tests(wt_path)
        has_pw_config = (
            os.path.isfile(os.path.join(wt_path, "playwright.config.ts"))
            or os.path.isfile(os.path.join(wt_path, "playwright.config.js"))
        )
        if has_pw_config and e2e_test_count > 0:
            update_change_field(state_file, change_name, "status", "verifying")
            e2e_port = E2E_PORT_BASE + random.randint(0, 99)
            logger.info("Verify gate: e2e start for %s (PW_PORT=%d)", change_name, e2e_port)

            start_ms = int(time.monotonic() * 1000)
            e2e_env = {"PW_PORT": str(e2e_port)}
            e2e_cmd_result = run_command(
                ["bash", "-c", e2e_command],
                timeout=e2e_timeout, cwd=wt_path, env=e2e_env,
                max_output_size=4000,
            )
            gate_e2e_ms = int(time.monotonic() * 1000) - start_ms
            update_change_field(state_file, change_name, "gate_e2e_ms", gate_e2e_ms)

            e2e_result_str = "pass" if e2e_cmd_result.exit_code == 0 else "fail"
            e2e_output = e2e_cmd_result.stdout + e2e_cmd_result.stderr

            # Cleanup dev server
            run_command(["pkill", "-f", f"pnpm dev.*--port {e2e_port}"], timeout=5)
            run_command(["pkill", "-f", f"next dev.*--port {e2e_port}"], timeout=5)

            # Collect screenshots
            e2e_sc_dir = f"wt/orchestration/e2e-screenshots/{change_name}"
            os.makedirs(e2e_sc_dir, exist_ok=True)
            wt_test_results = os.path.join(wt_path, "test-results")
            if os.path.isdir(wt_test_results):
                for item in os.listdir(wt_test_results):
                    src = os.path.join(wt_test_results, item)
                    dst = os.path.join(e2e_sc_dir, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
            e2e_sc_count = sum(
                1 for _r, _d, files in os.walk(e2e_sc_dir) for f in files if f.endswith(".png")
            )
            update_change_field(state_file, change_name, "e2e_screenshot_dir", e2e_sc_dir)
            update_change_field(state_file, change_name, "e2e_screenshot_count", e2e_sc_count)

            update_change_field(state_file, change_name, "e2e_result", e2e_result_str)
            update_change_field(state_file, change_name, "e2e_output", e2e_output[:4000])

            if e2e_result_str == "fail":
                if verify_retry_count < max_verify_retries:
                    verify_retry_count += 1
                    update_change_field(state_file, change_name, "verify_retry_count", verify_retry_count)
                    update_change_field(state_file, change_name, "status", "verify-failed")
                    scope = change.scope or ""
                    retry_prompt = (
                        f"E2E tests (Playwright) failed. Fix the failing E2E tests or the code they test.\n\n"
                        f"E2E command: {e2e_command}\nE2E output:\n{e2e_output}\n\n"
                        f"Original scope: {scope}"
                    )
                    update_change_field(state_file, change_name, "retry_context", retry_prompt)
                    _snapshot_retry_tokens(state_file, change_name, wt_path)
                    from .dispatcher import resume_change
                    resume_change(state_file, change_name)
                    return

                update_change_field(state_file, change_name, "status", "failed")
                send_notification("wt-orchestrate", f"Change '{change_name}' failed E2E after {max_verify_retries} retries", "critical")
                return
        else:
            e2e_result_str = "skipped"

    # ── Step 4: Pre-merge scope check (BLOCKING) ──
    scope_result = verify_implementation_scope(change_name, wt_path) if wt_path else ScopeCheckResult(has_implementation=True)
    if not scope_result.has_implementation:
        update_change_field(state_file, change_name, "scope_check", "fail")
        if verify_retry_count < max_verify_retries:
            verify_retry_count += 1
            update_change_field(state_file, change_name, "verify_retry_count", verify_retry_count)
            update_change_field(state_file, change_name, "status", "verify-failed")
            scope = change.scope or ""
            retry_prompt = (
                "The change has NO implementation code — only OpenSpec artifacts and config files. "
                "Run /opsx:apply to implement the tasks, then mark the change as done.\n\n"
                f"Original scope: {scope}"
            )
            update_change_field(state_file, change_name, "retry_context", retry_prompt)
            _snapshot_retry_tokens(state_file, change_name, wt_path)
            from .dispatcher import resume_change
            resume_change(state_file, change_name)
            return

        update_change_field(state_file, change_name, "status", "failed")
        send_notification("wt-orchestrate", f"Change '{change_name}' failed scope check after {max_verify_retries} retries", "critical")
        return

    update_change_field(state_file, change_name, "scope_check", "pass")

    # ── Step 4b: Test file existence check ──
    if wt_path:
        merge_base = _get_merge_base(wt_path)
        diff_result = run_git("diff", "--name-only", f"{merge_base}..HEAD", cwd=wt_path)
        test_files_count = 0
        if diff_result.exit_code == 0:
            for f in diff_result.stdout.strip().split("\n"):
                if re.search(r"\.(test|spec)\.", f):
                    test_files_count += 1

        if test_files_count == 0:
            update_change_field(state_file, change_name, "has_tests", False)
            change_type = change.change_type or "feature"
            if not skip_test and change_type in ("feature", "infrastructure", "foundational"):
                logger.error("Verify gate: %s (type=%s) has NO test files — blocking", change_name, change_type)
                if verify_retry_count < max_verify_retries:
                    verify_retry_count += 1
                    update_change_field(state_file, change_name, "verify_retry_count", verify_retry_count)
                    update_change_field(state_file, change_name, "status", "verify-failed")
                    scope = change.scope or ""
                    retry_prompt = (
                        f"Verify failed: no test files found (*.test.* or *.spec.* patterns).\n\n"
                        f"IMPORTANT: First ensure ALL implementation from the scope below is complete "
                        f"and committed. Then add tests for the implemented functionality.\n\n"
                        f"Scope (implement this fully, then add tests):\n{scope}"
                    )
                    update_change_field(state_file, change_name, "retry_context", retry_prompt)
                    _snapshot_retry_tokens(state_file, change_name, wt_path)
                    from .dispatcher import resume_change
                    resume_change(state_file, change_name)
                    return

                update_change_field(state_file, change_name, "status", "failed")
                send_notification("wt-orchestrate", f"Change '{change_name}' failed test file check", "critical")
                return
            else:
                logger.warning("Verify gate: %s (type=%s) has no test files — non-blocking", change_name, change_type)
        else:
            update_change_field(state_file, change_name, "has_tests", True)

    # ── Step 5: LLM Code Review (VG-4) ──
    if skip_review:
        update_change_field(state_file, change_name, "review_result", "skipped")
    elif review_before_merge and wt_path:
        logger.info("Verify gate: review start for %s", change_name)
        scope = change.scope or ""

        start_ms = int(time.monotonic() * 1000)
        rr = review_change(change_name, wt_path, scope, review_model, state_file=state_file, design_snapshot_dir=design_snapshot_dir)
        gate_review_ms = int(time.monotonic() * 1000) - start_ms
        update_change_field(state_file, change_name, "gate_review_ms", gate_review_ms)

        if rr.has_critical:
            update_change_field(state_file, change_name, "review_result", "critical")
            update_change_field(state_file, change_name, "review_output", rr.output[:2000])
            # Review gets +1 extra retry beyond the shared limit because it runs
            # last — build/test retries may have consumed the budget already
            review_retry_limit = max_verify_retries + 1
            if verify_retry_count < review_retry_limit:
                verify_retry_count += 1
                update_change_field(state_file, change_name, "verify_retry_count", verify_retry_count)
                update_change_field(state_file, change_name, "status", "verify-failed")

                # Extract concrete fix instructions from review output
                fix_instructions = _extract_review_fixes(rr.output)
                flagged_reqs = ", ".join(sorted(set(re.findall(r"REQ-[A-Z0-9]+-\d+", rr.output))))

                parts = ["CRITICAL CODE REVIEW FAILURE. You MUST fix these security/quality issues.\n"]

                if fix_instructions:
                    parts.append("=== REQUIRED FIXES (apply each one) ===")
                    parts.append(fix_instructions)
                    parts.append("=== END REQUIRED FIXES ===\n")

                # Inject web security rules if available in the worktree
                security_guide = _load_security_rules(wt_path)
                if security_guide:
                    parts.append("=== SECURITY REFERENCE (follow these patterns) ===")
                    parts.append(security_guide)
                    parts.append("=== END SECURITY REFERENCE ===\n")

                if flagged_reqs:
                    parts.append(f"Requirements with no implementation evidence: {flagged_reqs}\n")

                parts.append(f"Full review output:\n{rr.output[:1500]}\n")
                parts.append(
                    "INSTRUCTIONS: Open each FILE listed above, go to the LINE, and apply the FIX. "
                    "Use the SECURITY REFERENCE patterns above to ensure your fix is correct. "
                    "Commit after fixing. Do NOT work on new features — only fix the issues above."
                )

                retry_prompt = "\n".join(parts)
                update_change_field(state_file, change_name, "retry_context", retry_prompt)
                _snapshot_retry_tokens(state_file, change_name, wt_path)
                from .dispatcher import resume_change
                resume_change(state_file, change_name)
                return

            update_change_field(state_file, change_name, "status", "failed")
            send_notification("wt-orchestrate", f"Change '{change_name}' has critical review issues after retries", "critical")
            return

        update_change_field(state_file, change_name, "review_result", "pass")
        update_change_field(state_file, change_name, "review_output", rr.output[:2000])

    # ── Step 5b: Verification rules ──
    if wt_path:
        rule_result = evaluate_verification_rules(change_name, wt_path, event_bus=event_bus)
        if rule_result.errors > 0:
            update_change_field(state_file, change_name, "status", "verify-failed")
            if verify_retry_count < max_verify_retries:
                verify_retry_count += 1
                update_change_field(state_file, change_name, "verify_retry_count", verify_retry_count)
                from .dispatcher import resume_change
                resume_change(state_file, change_name)
                return
            update_change_field(state_file, change_name, "status", "failed")
            send_notification("wt-orchestrate", f"Change '{change_name}' failed verification rules", "critical")
            return

    # ── Step 6: Spec verify ──
    gate_spec_coverage = "skipped"
    start_ms = int(time.monotonic() * 1000)
    verify_ok = True
    verify_output = ""

    if wt_path and shutil.which("claude"):
        verify_cmd_result = run_claude(
            f"IMPORTANT: Memory is not branch/worktree-aware — verify against filesystem, never skip checks based on memory alone.\nRun /opsx:verify {change_name}",
            extra_args=["--max-turns", "15"],
            cwd=wt_path,
        )
        verify_output = verify_cmd_result.stdout
        if verify_cmd_result.exit_code != 0:
            verify_ok = False

    gate_verify_ms = int(time.monotonic() * 1000) - start_ms
    update_change_field(state_file, change_name, "gate_verify_ms", gate_verify_ms)

    if verify_ok and verify_output:
        if "VERIFY_RESULT: PASS" in verify_output:
            gate_spec_coverage = "pass"
            update_change_field(state_file, change_name, "spec_coverage_result", "pass")
        elif "VERIFY_RESULT: FAIL" in verify_output:
            gate_spec_coverage = "fail"
            update_change_field(state_file, change_name, "spec_coverage_result", "fail")
            logger.warning("Spec coverage FAIL for %s — non-blocking, proceeding to merge", change_name)
        else:
            # Soft-fail: if all other gates passed, treat missing VERIFY_RESULT as warning
            # The /opsx:verify skill sometimes doesn't output the sentinel within max-turns
            other_gates_pass = (
                change.test_result in ("pass", None)
                and change.build_result in ("pass", None)
                and change.review_result in ("pass", None)
            )
            if other_gates_pass:
                logger.warning(
                    "Verify gate: no VERIFY_RESULT sentinel in output for %s — "
                    "all other gates passed, treating as PASS (soft-pass)",
                    change_name,
                )
                gate_spec_coverage = "pass"
                update_change_field(state_file, change_name, "spec_coverage_result", "soft-pass")
            else:
                verify_ok = False
                gate_spec_coverage = "fail"
                update_change_field(state_file, change_name, "spec_coverage_result", "fail")
                logger.error("Verify gate: no VERIFY_RESULT sentinel in output for %s — treating as FAIL", change_name)

    if not verify_ok:
        if verify_retry_count < max_verify_retries:
            verify_retry_count += 1
            update_change_field(state_file, change_name, "verify_retry_count", verify_retry_count)
            update_change_field(state_file, change_name, "status", "verify-failed")
            scope = change.scope or ""
            verify_tail = verify_output[-2000:] if verify_output else ""
            retry_prompt = f"Verify failed. Fix the issues.\n\nVerify output (last 2000 chars):\n{verify_tail}\n\nOriginal scope: {scope}"
            update_change_field(state_file, change_name, "retry_context", retry_prompt)
            _snapshot_retry_tokens(state_file, change_name, wt_path)
            from .dispatcher import resume_change
            resume_change(state_file, change_name)
            return

        update_change_field(state_file, change_name, "status", "failed")
        send_notification("wt-orchestrate", f"Change '{change_name}' failed verify after retries", "critical")
        return

    # ── Store gate totals ──
    gate_total_ms = gate_test_ms + gate_e2e_ms + gate_review_ms + gate_verify_ms + gate_build_ms
    update_change_field(state_file, change_name, "gate_total_ms", gate_total_ms)

    gate_retry_tokens = change.extras.get("gate_retry_tokens", 0)
    gate_retry_count = change.extras.get("gate_retry_count", 0)
    gate_has_tests = change.extras.get("has_tests", False)

    logger.info(
        "Verify gate: %s total %dms (build=%d, test=%d, review=%d, verify=%d, retries=%d, retry_tokens=%d)",
        change_name, gate_total_ms, gate_build_ms, gate_test_ms, gate_review_ms,
        gate_verify_ms, gate_retry_count, gate_retry_tokens,
    )

    if event_bus:
        event_bus.emit("VERIFY_GATE", change=change_name, data={
            "test": test_result_str,
            "test_ms": gate_test_ms,
            "build_ms": gate_build_ms,
            "review_ms": gate_review_ms,
            "verify_ms": gate_verify_ms,
            "total_ms": gate_total_ms,
            "retries": gate_retry_count,
            "retry_tokens": gate_retry_tokens,
            "scope_check": "pass",
            "has_tests": gate_has_tests,
            "spec_coverage": gate_spec_coverage,
            "spec_coverage_blocking": False,
        })

    # ── Post-verify hook ──
    # run_hook is bash-side — Python emits event, bash handles hook execution

    # ── Step 7: Mark done and queue merge ──
    update_change_field(state_file, change_name, "status", "done")
    update_change_field(state_file, change_name, "completed_at", datetime.now(timezone.utc).isoformat())

    # Increment changes since checkpoint
    with locked_state(state_file) as state:
        state.changes_since_checkpoint += 1

    # Queue merge based on policy
    if merge_policy in ("eager", "checkpoint"):
        with locked_state(state_file) as state:
            if change_name not in state.merge_queue:
                state.merge_queue.append(change_name)
        logger.info("%s added to merge queue (policy: %s)", change_name, merge_policy)


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


def _count_e2e_tests(wt_path: str) -> int:
    """Count E2E test files in worktree."""
    e2e_dir = os.path.join(wt_path, "tests", "e2e")
    if not os.path.isdir(e2e_dir):
        return 0
    count = 0
    for _root, _dirs, files in os.walk(e2e_dir):
        for f in files:
            if f.endswith(".spec.ts") or f.endswith(".spec.js"):
                count += 1
    return count


def _snapshot_retry_tokens(state_file: str, change_name: str, wt_path: str) -> None:
    """Snapshot current tokens before retry for cost tracking."""
    loop_state = _read_loop_state(wt_path) if wt_path else {}
    snap = int(loop_state.get("total_tokens", 0))
    update_change_field(state_file, change_name, "retry_tokens_start", snap)
