"""Web-specific gate executors — e2e (Playwright) and lint (forbidden patterns).

Moved from lib/set_orch/verifier.py as part of profile-driven-gate-registry.
These executors are registered by WebProjectType.register_gates().
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
import shutil
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from set_orch.state import Change

logger = logging.getLogger(__name__)

# Runtime error indicators in E2E output — if any appear, the page has client-side errors
# even if HTTP returned 200.
E2E_RUNTIME_ERROR_INDICATORS = [
    "Functions are not valid as a child",
    "Hydration failed because",
    "There was an error while hydrating",
    "Minified React error",
    "Error: Text content does not match",
    "Unhandled Runtime Error",
    "data-nextjs-error",
    "Internal error: Error: ",
]


# ─── E2E Helpers ─────────────────────────────────────────────────────


def _check_e2e_runtime_errors(output: str) -> list[str]:
    """Scan E2E output for client-side runtime error indicators."""
    found = []
    output_lower = output.lower()
    for indicator in E2E_RUNTIME_ERROR_INDICATORS:
        if indicator.lower() in output_lower:
            found.append(indicator)
    return found


def _extract_e2e_failure_ids(output: str) -> set[str]:
    """Extract unique failure identifiers from Playwright output."""
    ids: set[str] = set()
    for m in re.finditer(r"^\s*\d+\)\s+\[.*?\]\s+[›»]\s+([^\s:]+\.spec\.\w+:\d+)", output, re.MULTILINE):
        ids.add(m.group(1))
    return ids


def _parse_playwright_config(wt_path: str) -> dict:
    """Parse Playwright config for testDir and webServer presence."""
    config_path = None
    for name in ("playwright.config.ts", "playwright.config.js"):
        candidate = os.path.join(wt_path, name)
        if os.path.isfile(candidate):
            config_path = candidate
            break

    if not config_path:
        return {"config_path": None, "test_dir": None, "has_web_server": False}

    try:
        with open(config_path) as f:
            content = f.read()
    except OSError:
        return {"config_path": config_path, "test_dir": None, "has_web_server": False}

    test_dir = None
    m = re.search(r'testDir:\s*["\']([^"\']+)["\']', content)
    if m:
        raw = m.group(1)
        test_dir = raw.lstrip("./") if raw.startswith("./") else raw

    has_web_server = "webServer" in content

    return {
        "config_path": config_path,
        "test_dir": test_dir,
        "has_web_server": has_web_server,
    }


def _count_e2e_tests(wt_path: str, pw_config: dict | None = None) -> tuple[int, str]:
    """Count E2E test files in worktree."""
    if pw_config is None:
        pw_config = _parse_playwright_config(wt_path)

    if not pw_config["config_path"]:
        return 0, ""

    test_dir = pw_config.get("test_dir")
    if test_dir:
        search_dirs = [test_dir]
    else:
        search_dirs = ["tests/e2e", "e2e", "test/e2e", "tests"]

    count = 0
    searched = []
    for d in search_dirs:
        abs_dir = os.path.join(wt_path, d)
        if not os.path.isdir(abs_dir):
            continue
        searched.append(d)
        for _root, _dirs, files in os.walk(abs_dir):
            for f in files:
                if f.endswith(".spec.ts") or f.endswith(".spec.js"):
                    count += 1

    searched_desc = ", ".join(searched) if searched else ", ".join(search_dirs)
    return count, searched_desc


def _get_or_create_e2e_baseline(
    e2e_command: str, e2e_timeout: int, project_root: str,
) -> dict | None:
    """Run Playwright on main and cache baseline failures."""
    from set_orch.subprocess_utils import run_command, run_git
    from set_orch.verifier import parse_test_output

    try:
        from set_orch.paths import SetRuntime
        baseline_path = os.path.join(SetRuntime().orchestration_dir, "e2e-baseline.json")
    except Exception:
        baseline_path = os.path.join("wt", "orchestration", "e2e-baseline.json")

    main_sha = run_git("rev-parse", "HEAD", cwd=project_root).stdout.strip()
    if os.path.isfile(baseline_path):
        try:
            with open(baseline_path) as f:
                cached = json.load(f)
            if cached.get("main_sha") == main_sha:
                cached["failures"] = set(cached.get("failures", []))
                return cached
            logger.info("E2E baseline stale (main moved to %s) — regenerating", main_sha[:8])
        except (json.JSONDecodeError, OSError):
            pass

    logger.info("Creating E2E baseline on main (%s)...", main_sha[:8])
    result = run_command(
        ["bash", "-c", e2e_command],
        timeout=e2e_timeout, cwd=project_root, max_output_size=8000,
    )
    output = result.stdout + result.stderr
    stats = parse_test_output(output)
    failures = _extract_e2e_failure_ids(output)

    baseline = {
        "main_sha": main_sha,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "failures": list(failures),
        "total": stats.get("total", 0),
        "passed": stats.get("passed", 0),
        "failed": stats.get("failed", 0),
    }

    try:
        os.makedirs(os.path.dirname(baseline_path), exist_ok=True)
        with open(baseline_path, "w") as f:
            json.dump(baseline, f, indent=2)
        logger.info("E2E baseline cached: %d passed, %d failed on main", baseline["passed"], baseline["failed"])
    except OSError:
        logger.warning("Failed to cache E2E baseline")

    baseline["failures"] = failures
    return baseline


def _auto_detect_e2e_command(wt_path: str, profile=None) -> str:
    """Auto-detect e2e command by delegating to the project-type profile."""
    if profile is not None and hasattr(profile, "detect_e2e_command"):
        try:
            cmd = profile.detect_e2e_command(wt_path)
            if cmd:
                logger.info("E2E command detected via profile: %s", cmd)
                return cmd
        except Exception:
            pass
    return ""


# ─── E2E Gate Executor ───────────────────────────────────────────────


def execute_e2e_gate(
    change_name: str, change: "Change", wt_path: str,
    e2e_command: str, e2e_timeout: int, e2e_health_timeout: int,
    profile=None,
) -> "GateResult":
    """E2E gate: run Playwright tests with baseline comparison.

    Only NEW failures (not present on main) count as gate failures.
    Requires Playwright webServer config to manage the dev server.
    """
    from set_orch.gate_runner import GateResult
    from set_orch.subprocess_utils import run_command, run_git
    from set_orch.verifier import parse_test_output

    # Auto-detect e2e_command if not explicitly configured
    auto_detected = False
    if not e2e_command and wt_path:
        e2e_command = _auto_detect_e2e_command(wt_path, profile)
        auto_detected = bool(e2e_command)

    if not e2e_command or not wt_path:
        return GateResult("e2e", "skipped", output="e2e_command not configured")

    pw_config = _parse_playwright_config(wt_path)
    if not pw_config["config_path"]:
        return GateResult("e2e", "skipped",
                          output="no playwright.config.ts/js found in worktree")

    e2e_test_count, searched_desc = _count_e2e_tests(wt_path, pw_config)
    if e2e_test_count == 0:
        if auto_detected:
            scope = change.scope or ""
            return GateResult(
                "e2e", "fail",
                output=f"no e2e test files found (searched: {searched_desc})",
                retry_context=(
                    "E2E tests required for feature changes when Playwright is configured.\n\n"
                    f"Playwright config found but no test files in: {searched_desc}\n\n"
                    "Write E2E tests for the implemented functionality, then commit them.\n\n"
                    f"Original scope: {scope}"
                ),
            )
        return GateResult("e2e", "skipped",
                          output=f"no e2e test files found (searched: {searched_desc})")

    if not pw_config["has_web_server"]:
        return GateResult("e2e", "skipped",
                          output="playwright.config has no webServer — "
                                 "Playwright must manage the dev server via webServer config")

    # Build env with port isolation from profile
    e2e_env: dict[str, str] = {}
    if profile and hasattr(profile, "worktree_port"):
        port = profile.worktree_port(change_name)
        if port > 0 and hasattr(profile, "e2e_gate_env"):
            e2e_env.update(profile.e2e_gate_env(port))
    # Fallback: read PORT from worktree .env if profile didn't set it
    if "PW_PORT" not in e2e_env:
        env_file = os.path.join(wt_path, ".env")
        if os.path.isfile(env_file):
            try:
                for line in open(env_file):
                    if line.startswith("PW_PORT="):
                        e2e_env["PW_PORT"] = line.strip().split("=", 1)[1]
                    elif line.startswith("PORT=") and "PORT" not in e2e_env:
                        e2e_env["PORT"] = line.strip().split("=", 1)[1]
            except OSError:
                pass

    # Pre-gate hook (DB setup, migrations, seed)
    if profile and hasattr(profile, "e2e_pre_gate"):
        if not profile.e2e_pre_gate(wt_path, e2e_env):
            return GateResult("e2e", "skipped", output="e2e_pre_gate returned False")

    # Run E2E tests
    try:
        e2e_cmd_result = run_command(
            ["bash", "-c", e2e_command],
            timeout=e2e_timeout, cwd=wt_path, env=e2e_env,
            max_output_size=4000,
        )
    finally:
        # Post-gate hook (cleanup) — always runs
        if profile and hasattr(profile, "e2e_post_gate"):
            try:
                profile.e2e_post_gate(wt_path)
            except Exception:
                pass  # non-fatal cleanup
    e2e_output = e2e_cmd_result.stdout + e2e_cmd_result.stderr

    # Collect screenshots
    try:
        from set_orch.paths import SetRuntime
        e2e_sc_dir = os.path.join(SetRuntime().screenshots_dir, "e2e", change_name)
    except Exception:
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

    raw_status = "pass" if e2e_cmd_result.exit_code == 0 else "fail"

    # Check for runtime errors even on pass
    runtime_errors = _check_e2e_runtime_errors(e2e_output)
    if runtime_errors:
        logger.warning(
            "E2E runtime errors detected for %s: %s",
            change_name, ", ".join(runtime_errors),
        )

    if raw_status == "pass":
        output_text = e2e_output[:4000]
        if runtime_errors:
            output_text = (
                f"WARNING: {len(runtime_errors)} runtime error(s) detected in E2E output: "
                f"{', '.join(runtime_errors)}\n\n" + output_text[:3500]
            )
        return GateResult(
            "e2e", "pass", output=output_text,
            stats=parse_test_output(e2e_output) if e2e_output else None,
        )

    # E2E failed — check baseline to filter pre-existing failures
    wt_failures = _extract_e2e_failure_ids(e2e_output)
    project_root = os.path.dirname(wt_path.rstrip("/"))
    toplevel = run_git("rev-parse", "--show-toplevel", cwd=wt_path)
    if toplevel.exit_code == 0:
        main_wt = run_git("worktree", "list", "--porcelain", cwd=wt_path)
        for line in main_wt.stdout.split("\n"):
            if line.startswith("worktree ") and not line.endswith(os.path.basename(wt_path)):
                project_root = line.split(" ", 1)[1]
                break

    baseline = None
    try:
        baseline = _get_or_create_e2e_baseline(e2e_command, e2e_timeout, project_root)
    except Exception as e:
        logger.warning("E2E baseline creation failed (using all-failures mode): %s", e)

    if baseline:
        baseline_failures = baseline.get("failures", set())
        if isinstance(baseline_failures, list):
            baseline_failures = set(baseline_failures)
        new_failures = wt_failures - baseline_failures
        pre_existing = wt_failures & baseline_failures
        logger.info(
            "E2E baseline comparison: %d new failures, %d pre-existing on main",
            len(new_failures), len(pre_existing),
        )
        if not new_failures:
            return GateResult(
                "e2e", "pass",
                output=f"E2E: {len(pre_existing)} pre-existing failures on main (no new regressions)\n\n"
                       + e2e_output[:3000],
                stats=parse_test_output(e2e_output) if e2e_output else None,
            )
        e2e_output_header = (
            f"E2E: {len(new_failures)} NEW failures (+ {len(pre_existing)} pre-existing on main)\n"
            f"New failures: {', '.join(sorted(new_failures))}\n\n"
        )
        e2e_output = e2e_output_header + e2e_output[:3500]

    result = GateResult(
        "e2e", "fail", output=e2e_output[:4000],
        stats=parse_test_output(e2e_output) if e2e_output else None,
    )
    scope = change.scope or ""
    # Point agent to failure screenshots in worktree
    screenshot_hint = ""
    wt_test_results = os.path.join(wt_path, "test-results")
    if os.path.isdir(wt_test_results):
        png_files = []
        for root, _dirs, files in os.walk(wt_test_results):
            for f in files:
                if f.endswith(".png"):
                    png_files.append(os.path.relpath(os.path.join(root, f), wt_path))
        if png_files:
            screenshot_hint = (
                f"\n\nFailure screenshots (READ these for visual context):\n"
                + "\n".join(f"- {p}" for p in png_files[:10])
            )

    result.retry_context = (
        f"E2E tests (Playwright) failed. Fix the failing E2E tests or the code they test.\n\n"
        f"E2E command: {e2e_command}\nE2E output:\n{e2e_output[:2000]}\n"
        f"{screenshot_hint}\n\n"
        f"Original scope: {scope}"
    )
    return result


# ─── Lint Helpers ────────────────────────────────────────────────────


def _load_forbidden_patterns(wt_path: str, profile=None) -> list[dict]:
    """Load forbidden patterns from profile plugin + project-knowledge.yaml."""
    patterns: list[dict] = []

    if profile is not None and hasattr(profile, "get_forbidden_patterns"):
        try:
            patterns.extend(profile.get_forbidden_patterns())
        except Exception:
            logger.warning("Failed to load forbidden patterns from profile", exc_info=True)

    pk_path = os.path.join(wt_path, "project-knowledge.yaml")
    if os.path.isfile(pk_path):
        try:
            import yaml
            with open(pk_path) as f:
                pk = yaml.safe_load(f) or {}
            fp = pk.get("verification", {}).get("forbidden_patterns", [])
            if isinstance(fp, list):
                patterns.extend(fp)
        except Exception:
            logger.warning("Failed to load forbidden_patterns from project-knowledge.yaml", exc_info=True)

    return patterns


def _is_comment_line(content: str) -> bool:
    """Check if a line is a code comment (should be skipped by lint)."""
    stripped = content.strip()
    # Single-line comments (JS/TS/Python/Shell)
    if stripped.startswith("//") or stripped.startswith("#"):
        return True
    # Block comment lines (JSDoc, multi-line comments)
    if stripped.startswith("*") or stripped.startswith("/**") or stripped.startswith("*/"):
        return True
    # Markdown-style documentation in code
    if stripped.startswith("- ") and "**" in stripped:
        return True
    return False


def _extract_added_lines(diff_output: str, skip_comments: bool = True) -> list[tuple[str, int, str]]:
    """Parse unified diff, return (file_path, approx_line, content) for added lines.

    When skip_comments=True (default), comment lines are excluded from results
    to prevent false positives when agents mention forbidden patterns in fix comments.
    """
    results: list[tuple[str, int, str]] = []
    current_file = ""
    current_line = 0

    for line in diff_output.split("\n"):
        if line.startswith("+++ b/"):
            current_file = line[6:]
            current_line = 0
        elif line.startswith("@@ "):
            match = re.search(r"\+(\d+)", line)
            if match:
                current_line = int(match.group(1)) - 1
        elif line.startswith("+") and not line.startswith("+++"):
            current_line += 1
            content = line[1:]
            if skip_comments and _is_comment_line(content):
                continue
            results.append((current_file, current_line, content))
        elif not line.startswith("-"):
            current_line += 1

    return results


# ─── Lint Gate Executor ──────────────────────────────────────────────


def execute_lint_gate(
    change_name: str, change: "Change", wt_path: str,
    profile=None,
) -> "GateResult":
    """Lint gate: deterministic grep-based forbidden pattern scanning."""
    from set_orch.gate_runner import GateResult
    from set_orch.subprocess_utils import run_git

    if not wt_path:
        return GateResult("lint", "pass")

    patterns = _load_forbidden_patterns(wt_path, profile)
    if not patterns:
        return GateResult("lint", "pass", output="no forbidden patterns configured")

    # Get merge base for diff
    from set_orch.verifier import _get_merge_base
    merge_base = _get_merge_base(wt_path)
    diff_result = run_git("diff", f"{merge_base}..HEAD", cwd=wt_path)
    if diff_result.exit_code != 0:
        return GateResult("lint", "pass", output="could not generate diff")

    added_lines = _extract_added_lines(diff_result.stdout)
    if not added_lines:
        return GateResult("lint", "pass")

    critical_matches: list[str] = []
    warning_matches: list[str] = []

    for pat_dict in patterns:
        pattern = pat_dict.get("pattern", "")
        severity = pat_dict.get("severity", "warning").lower()
        message = pat_dict.get("message", "")
        file_glob = pat_dict.get("file_glob", "")

        if not pattern:
            continue

        try:
            regex = re.compile(pattern)
        except re.error:
            logger.warning("Invalid forbidden pattern regex: %s", pattern)
            continue

        for file_path, line_num, content in added_lines:
            if file_glob and not fnmatch.fnmatch(file_path, file_glob):
                continue

            if regex.search(content):
                match_str = f"  File: {file_path} (line {line_num})\n  Pattern: {pattern}\n  Rule: {message}"
                if severity == "critical":
                    critical_matches.append(match_str)
                else:
                    warning_matches.append(match_str)

    if critical_matches:
        retry_ctx = "FORBIDDEN PATTERN(S) DETECTED:\n\n" + "\n\n".join(critical_matches)
        retry_ctx += "\n\nFix the root cause. Do NOT use type casts or workarounds to bypass."
        if warning_matches:
            retry_ctx += "\n\nWarnings (non-blocking):\n" + "\n".join(warning_matches)
        return GateResult(
            "lint", "fail",
            output=f"{len(critical_matches)} critical, {len(warning_matches)} warning pattern match(es)",
            retry_context=retry_ctx,
        )

    if warning_matches:
        return GateResult(
            "lint", "pass",
            output=f"{len(warning_matches)} warning pattern match(es):\n" + "\n".join(warning_matches),
        )

    return GateResult("lint", "pass")
