"""Build health check and LLM-assisted fixing.

Migrated from: lib/orchestration/builder.sh (151 LOC)
Provides: check_base_build(), fix_base_build()
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .subprocess_utils import CommandResult, run_claude, run_command

logger = logging.getLogger(__name__)


# ─── Dataclasses ─────────────────────────────────────────────────


@dataclass
class BuildResult:
    """Result of a build health check."""

    status: str  # "pass", "fail", "skip"
    output: str = ""
    package_manager: str = ""


# ─── Session Cache ───────────────────────────────────────────────
# Migrated from: builder.sh:BASE_BUILD_STATUS etc.

_build_cache: dict[str, Any] = {
    "status": "",  # "", "pass", "fail"
    "output": "",
    "fix_attempted": "",  # "", "sonnet", "both", "done"
}


def reset_build_cache() -> None:
    """Reset the session build cache."""
    _build_cache["status"] = ""
    _build_cache["output"] = ""
    _build_cache["fix_attempted"] = ""


# ─── Base Build Health Check ─────────────────────────────────────
# Migrated from: builder.sh:check_base_build()


def check_base_build(project_path: str) -> BuildResult:
    """Run the project's build command and cache the result.

    Auto-detects package manager and build command from package.json.
    Caches result per session: subsequent calls return cached result.

    Args:
        project_path: Path to the project directory.

    Returns:
        BuildResult with status, output, and package_manager.
    """
    # Return cached result
    if _build_cache["status"] == "pass":
        return BuildResult(status="pass", package_manager=_detect_pm(project_path))
    elif _build_cache["status"] == "fail":
        return BuildResult(
            status="fail",
            output=_build_cache["output"],
            package_manager=_detect_pm(project_path),
        )

    pm = _detect_pm(project_path)
    build_cmd = _detect_build_cmd(project_path)

    if not build_cmd:
        _build_cache["status"] = "pass"
        return BuildResult(status="skip", package_manager=pm)

    logger.info("Base build check: running %s run %s in %s", pm, build_cmd, project_path)

    result = run_command(
        [pm, "run", build_cmd],
        timeout=300,
        cwd=project_path,
    )

    if result.exit_code == 0:
        _build_cache["status"] = "pass"
        logger.info("Base build check: PASS")
        return BuildResult(status="pass", output=result.stdout, package_manager=pm)
    else:
        _build_cache["status"] = "fail"
        _build_cache["output"] = result.stdout + result.stderr
        logger.warning("Base build check: FAIL — main branch has build errors")
        return BuildResult(
            status="fail",
            output=_build_cache["output"],
            package_manager=pm,
        )


# ─── LLM-Assisted Build Fix ─────────────────────────────────────
# Migrated from: builder.sh:fix_base_build_with_llm()


def fix_base_build(
    project_path: str,
    error_output: str = "",
) -> BuildResult:
    """Attempt to fix build errors using LLM agent.

    Single attempt guard: won't retry if both sonnet and opus already failed.

    Args:
        project_path: Path to the project directory.
        error_output: Build error output (uses cached if empty).

    Returns:
        BuildResult after fix attempt.
    """
    if _build_cache["fix_attempted"] == "both":
        logger.info("Base build fix: both sonnet and opus failed — skipping")
        return BuildResult(status="fail", output=error_output or _build_cache["output"])

    if not error_output:
        error_output = _build_cache["output"]

    pm = _detect_pm(project_path)
    build_cmd = _detect_build_cmd(project_path) or "build"

    # Choose model: escalate to opus if sonnet already failed
    if _build_cache["fix_attempted"] == "sonnet":
        model = "opus"
        logger.info("Base build fix: sonnet failed previously, escalating to opus")
    else:
        model = "sonnet"

    fix_prompt = f"""The main branch has build errors that are blocking all worktree builds.
Fix these TypeScript/build errors directly on the main branch.

Build command: {pm} run {build_cmd}
Build output (last 3000 chars):
{error_output[-3000:]}

Instructions:
1. Analyze the build errors above carefully
2. Fix the root cause (type errors, missing imports, missing @types packages, schema mismatches, etc.)
3. Run: {pm} run {build_cmd} — confirm it passes
4. Commit the fix with message: "fix: repair main branch build errors"

Do NOT create a worktree — fix directly in the current directory."""

    logger.info("Base build fix: attempting LLM-assisted fix (model=%s)", model)

    fix_result = run_claude(
        fix_prompt,
        timeout=600,
        model=model,
        extra_args=["--max-turns", "20"],
        cwd=project_path,
    )

    if fix_result.exit_code == 0:
        # Re-check build (reset cache only on confirmed success)
        _build_cache["status"] = ""
        _build_cache["output"] = ""
        result = check_base_build(project_path)
        if result.status == "pass":
            logger.info("Base build fix: SUCCESS (model=%s)", model)
            _build_cache["fix_attempted"] = "done"
            return result
        # Fix applied but build still fails — don't corrupt fix_attempted state
        logger.warning("Base build fix: LLM fix applied but rebuild still fails (model=%s)", model)

    # Track which model failed
    if _build_cache["fix_attempted"] == "sonnet":
        _build_cache["fix_attempted"] = "both"
        logger.error("Base build fix: opus also failed — manual intervention needed")
    else:
        _build_cache["fix_attempted"] = "sonnet"
        logger.warning("Base build fix: sonnet failed — will try opus on next attempt")

    return BuildResult(status="fail", output=error_output, package_manager=pm)


# ─── Helpers ─────────────────────────────────────────────────────


def _detect_pm(project_path: str) -> str:
    """Detect package manager — profile first, legacy fallback."""
    from .profile_loader import load_profile

    profile = load_profile(project_path)
    pm = profile.detect_package_manager(project_path)
    if pm:
        return pm

    # Legacy fallback
    p = Path(project_path)
    if (p / "bun.lockb").is_file() or (p / "bun.lock").is_file():
        return "bun"
    elif (p / "pnpm-lock.yaml").is_file():
        return "pnpm"
    elif (p / "yarn.lock").is_file():
        return "yarn"
    return "npm"


def _detect_build_cmd(project_path: str) -> str:
    """Detect build command — profile first, legacy fallback."""
    from .profile_loader import load_profile

    profile = load_profile(project_path)
    cmd = profile.detect_build_command(project_path)
    if cmd:
        # Profile returns full command like "pnpm run build" — extract script name
        # since caller does `pm run <script>`
        parts = cmd.split()
        if len(parts) >= 3 and parts[1] == "run":
            return parts[2]
        return cmd

    # Legacy fallback
    pkg_json = Path(project_path) / "package.json"
    if not pkg_json.is_file():
        return ""

    try:
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
        scripts = data.get("scripts", {})
        if "build:ci" in scripts:
            return "build:ci"
        elif "build" in scripts:
            return "build"
    except (json.JSONDecodeError, OSError):
        pass

    return ""
