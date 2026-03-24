"""Dispatcher: change lifecycle — dispatch, resume, pause, recovery.

Migrated from: lib/orchestration/dispatcher.sh (sync_worktree_with_main,
bootstrap_worktree, prune_worktree_context, resolve_change_model,
dispatch_change, dispatch_via_wt_loop, dispatch_ready_changes,
pause_change, resume_change, resume_stopped_changes, resume_stalled_changes,
recover_orphaned_changes, redispatch_change, retry_failed_builds)
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .events import EventBus
from .notifications import send_notification
from .process import check_pid, safe_kill
from .root import SET_TOOLS_ROOT
from .state import (
    Change,
    OrchestratorState,
    WatchdogState,
    count_changes_by_status,
    deps_satisfied,
    get_change_status,
    get_changes_by_status,
    load_state,
    locked_state,
    topological_sort,
    update_change_field,
    update_state_field,
)
from .subprocess_utils import CommandResult, run_command, run_git

logger = logging.getLogger(__name__)

# Core generated files that can be auto-resolved during merge conflicts.
# Profile-specific patterns are added dynamically via _get_generated_file_patterns().
_CORE_GENERATED_FILE_PATTERNS = {
    ".tsbuildinfo", "next-env.d.ts",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
}

# Directory prefixes whose contents are always framework-generated and safe to
# auto-resolve with --ours/--theirs during merge. This covers .claude/* runtime
# files, .set-core/ state, build outputs, and dependency directories.
_AUTO_RESOLVE_PREFIXES = {
    ".claude/",
    ".set-core/",
    ".next/",
    "dist/",
    "build/",
    "coverage/",
    "node_modules/",
}


def _get_generated_file_patterns() -> set:
    """Return generated file patterns: core + profile-provided."""
    from .profile_loader import load_profile

    profile = load_profile()
    extra = profile.generated_file_patterns()
    if extra:
        return _CORE_GENERATED_FILE_PATTERNS | set(extra)
    return _CORE_GENERATED_FILE_PATTERNS


def _is_generated_file(path: str) -> bool:
    """Return True if path is a generated file safe to auto-resolve during merge.

    Checks both basename patterns (lockfiles, .tsbuildinfo) and directory
    prefix patterns (.claude/* runtime files).
    """
    if os.path.basename(path) in _get_generated_file_patterns():
        return True
    return any(path.startswith(prefix) for prefix in _AUTO_RESOLVE_PREFIXES)

def _build_rule_injection(scope: str, wt_path: str) -> str:
    """Scan scope keywords against rule_keyword_mapping() and return matching rule content.

    Reads matching rule files from {wt_path}/.claude/rules/, deduplicates,
    truncates to 4000 chars total. Returns formatted string with header, or "".
    """
    from .profile_loader import load_profile

    rules_dir = os.path.join(wt_path, ".claude", "rules")
    if not os.path.isdir(rules_dir):
        return ""

    profile = load_profile()
    if hasattr(profile, 'rule_keyword_mapping'):
        mapping = profile.rule_keyword_mapping()
    else:
        from .profile_loader import NullProfile
        mapping = NullProfile().rule_keyword_mapping()
    scope_lower = scope.lower()

    matched_globs: list[str] = []
    for _category, cfg in mapping.items():
        keywords = cfg.get("keywords", [])
        if any(kw.lower() in scope_lower for kw in keywords):
            matched_globs.extend(cfg.get("globs", []))

    if not matched_globs:
        return ""

    seen: set[str] = set()
    parts: list[str] = []
    total = 0
    for glob_pat in matched_globs:
        # glob_pat is relative, e.g. "web/auth-middleware.md"
        full_path = os.path.join(rules_dir, glob_pat)
        if full_path in seen or not os.path.isfile(full_path):
            continue
        seen.add(full_path)
        try:
            content = open(full_path).read()
        except OSError:
            continue
        # Strip YAML frontmatter if present
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                content = content[end + 3:].strip()
        if total + len(content) > 4000:
            break
        total += len(content)
        parts.append(content)

    if not parts:
        return ""

    return "## Relevant Patterns\n\n" + "\n\n".join(parts)


# Env files to copy from project root to worktree
ENV_FILES = [".env", ".env.local", ".env.development", ".env.development.local"]

# Orchestrator command patterns to prune from worktrees
PRUNE_PATTERNS = ["orchestrate", "sentinel", "manual"]

# Stall cooldown in seconds
STALL_COOLDOWN_SECONDS = 300


# ─── Data Types ──────────────────────────────────────────────────────


@dataclass
class SyncResult:
    """Result of worktree sync with main."""

    ok: bool
    message: str
    behind_count: int = 0
    auto_resolved: bool = False
    lockfile_regenerated: bool = False


@dataclass
class DispatchContext:
    """Context gathered for proposal enrichment."""

    memory_ctx: str = ""
    pk_context: str = ""
    sibling_context: str = ""
    design_context: str = ""
    retry_context: str = ""
    read_first_directives: list[str] = field(default_factory=list)
    conventions_summary: str = ""
    i18n_sidecar_instructions: str = ""
    cross_cutting_restrictions: list[str] = field(default_factory=list)
    review_learnings: str = ""
    review_learnings_checklist: str = ""


# ─── Worktree Preparation ────────────────────────────────────────────

_LOCKFILE_NAMES = {"package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json"}


def _reinstall_deps_if_needed(wt_path: str, old_sha: str, new_sha: str) -> None:
    """Run package manager install if lockfile or package.json changed between two commits."""
    if not old_sha or not new_sha or old_sha == new_sha:
        return
    diff_r = run_git("diff", "--name-only", f"{old_sha}..{new_sha}", cwd=wt_path)
    if diff_r.exit_code != 0:
        return
    changed = set(diff_r.stdout.strip().splitlines())
    if not changed.intersection(_LOCKFILE_NAMES):
        return
    pm = _detect_package_manager(wt_path)
    if not pm:
        return
    logger.info("sync: deps changed (%s) — running %s install in %s",
                changed.intersection(_LOCKFILE_NAMES), pm, wt_path)
    r = run_command([pm, "install"], cwd=wt_path, timeout=120)
    if r.exit_code == 0:
        logger.info("sync: %s install succeeded in %s", pm, wt_path)
    else:
        logger.warning("sync: %s install failed in %s (non-blocking)", pm, wt_path)


def sync_worktree_with_main(wt_path: str, change_name: str) -> SyncResult:
    """Merge main branch into worktree branch.

    Migrated from: dispatcher.sh sync_worktree_with_main() L5-80

    Auto-resolves conflicts in generated files (lockfiles, .tsbuildinfo).
    Aborts merge on real conflicts.
    """
    # Determine main branch
    main_branch = ""
    for branch in ("main", "master"):
        r = run_git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}", cwd=wt_path)
        if r.exit_code == 0:
            main_branch = branch
            break

    if not main_branch:
        logger.warning("sync: could not find main/master branch for %s", change_name)
        return SyncResult(ok=False, message="no main branch found")

    # Check if already up to date
    wt_branch_r = run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=wt_path)
    wt_branch = wt_branch_r.stdout.strip()

    main_head_r = run_git("rev-parse", main_branch, cwd=wt_path)
    main_head = main_head_r.stdout.strip()

    merge_base_r = run_git("merge-base", wt_branch, main_branch, cwd=wt_path)
    merge_base = merge_base_r.stdout.strip()

    if main_head == merge_base:
        logger.info("sync: %s already up to date with %s", change_name, main_branch)
        return SyncResult(ok=True, message="already up to date")

    behind_r = run_git("rev-list", "--count", f"{merge_base}..{main_head}", cwd=wt_path)
    behind_count = int(behind_r.stdout.strip()) if behind_r.exit_code == 0 else 0
    logger.info("sync: %s is %d commit(s) behind %s — merging", change_name, behind_count, main_branch)

    # Attempt merge
    merge_r = run_git(
        "merge", main_branch,
        "-m", f"Merge {main_branch} into {wt_branch} (auto-sync)",
        cwd=wt_path,
    )

    if merge_r.exit_code == 0:
        logger.info("sync: successfully merged %s into %s", main_branch, change_name)
        _reinstall_deps_if_needed(wt_path, merge_base, main_head)
        return SyncResult(ok=True, message="merged", behind_count=behind_count)

    # Check for conflicts
    conflict_r = run_git("diff", "--name-only", "--diff-filter=U", cwd=wt_path)
    conflicted_files = [f for f in conflict_r.stdout.strip().splitlines() if f.strip()]

    if conflicted_files:
        # Check if all conflicts are in generated files (basename or prefix match)
        has_non_generated = False
        for f in conflicted_files:
            if not _is_generated_file(f):
                has_non_generated = True
                break

        if not has_non_generated:
            # All conflicts in generated files — accept ours
            lockfile_regenerated = False
            for f in conflicted_files:
                run_git("checkout", "--ours", f, cwd=wt_path)
                run_git("add", f, cwd=wt_path)

            # Check if any conflicted files were lock files and regenerate
            from .profile_loader import NullProfile, load_profile

            profile = load_profile()

            # Build lockfile-to-PM map: profile first, then fallback
            lockfile_pm_map = {}
            if not isinstance(profile, NullProfile):
                pm_map_list = profile.lockfile_pm_map()
                if pm_map_list:
                    for entry in pm_map_list:
                        if isinstance(entry, dict):
                            lockfile_pm_map.update(entry)
                        elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                            lockfile_pm_map[entry[0]] = entry[1]

            # Hardcoded JS fallback
            _fallback = {
                "pnpm-lock.yaml": "pnpm",
                "yarn.lock": "yarn",
                "package-lock.json": "npm",
            }
            for lf, pm in _fallback.items():
                if lf not in lockfile_pm_map:
                    lockfile_pm_map[lf] = pm

            for f in conflicted_files:
                basename = os.path.basename(f)
                if basename in lockfile_pm_map:
                    pm = lockfile_pm_map[basename]
                    install_cmd = [pm, "install"]
                    if pm == "pnpm":
                        install_cmd = ["pnpm", "install", "--no-frozen-lockfile"]
                    logger.info(
                        "sync: regenerating %s via %s in %s",
                        basename, " ".join(install_cmd), wt_path,
                    )
                    result = run_command(install_cmd, timeout=600, cwd=wt_path)
                    if result.exit_code == 0:
                        run_git("add", f, cwd=wt_path)
                        lockfile_regenerated = True
                        logger.info("sync: lock file %s regenerated for %s", basename, change_name)
                    else:
                        logger.warning(
                            "sync: lock file regeneration failed for %s (continuing with 'ours')",
                            basename,
                        )

            run_git("commit", "--no-edit", cwd=wt_path)
            logger.info("sync: auto-resolved generated file conflicts for %s", change_name)
            _reinstall_deps_if_needed(wt_path, merge_base, main_head)
            return SyncResult(
                ok=True, message="auto-resolved", behind_count=behind_count,
                auto_resolved=True, lockfile_regenerated=lockfile_regenerated,
            )

    # Real conflicts — abort
    run_git("merge", "--abort", cwd=wt_path)
    logger.warning("sync: merge conflicts for %s — cannot auto-sync with %s", change_name, main_branch)
    return SyncResult(ok=False, message="merge conflicts", behind_count=behind_count)


def bootstrap_worktree(project_path: str, wt_path: str, change_name: str = "") -> int:
    """Copy .env files, inject port, and install deps in a worktree.

    Migrated from: dispatcher.sh bootstrap_worktree() L86-116

    Returns number of env files copied.
    """
    if not os.path.isdir(wt_path):
        return 0

    # Create per-agent .set/ ephemeral directory
    from .paths import SetRuntime
    SetRuntime.ensure_agent_dir(wt_path)

    # Copy .env files
    copied = 0
    for envfile in ENV_FILES:
        src = os.path.join(project_path, envfile)
        dst = os.path.join(wt_path, envfile)
        if os.path.isfile(src) and not os.path.isfile(dst):
            shutil.copy2(src, dst)
            copied += 1

    if copied > 0:
        logger.info("bootstrap: copied %d env file(s) to %s", copied, wt_path)

    # Install dependencies — profile first, legacy fallback
    from .profile_loader import NullProfile, load_profile

    profile = load_profile(project_path)
    if not isinstance(profile, NullProfile):
        profile.bootstrap_worktree(project_path, wt_path)
    else:
        # TODO(profile-cleanup): remove after profile adoption confirmed
        # Legacy fallback
        pkg_json = os.path.join(wt_path, "package.json")
        node_modules = os.path.join(wt_path, "node_modules")
        if os.path.isfile(pkg_json) and not os.path.isdir(node_modules):
            pm = _detect_package_manager(wt_path)
            if pm and shutil.which(pm):
                logger.info("bootstrap: installing deps with %s in %s", pm, wt_path)
                r = run_command([pm, "install", "--frozen-lockfile"], cwd=wt_path, timeout=120)
                if r.exit_code != 0:
                    r = run_command([pm, "install"], cwd=wt_path, timeout=120)
                    if r.exit_code != 0:
                        logger.warning("bootstrap: dep install failed in %s (non-fatal)", wt_path)

    # Inject worktree-specific port into .env (idempotent)
    if change_name and not isinstance(profile, NullProfile):
        port = profile.worktree_port(change_name)
        if port > 0:
            env_path = os.path.join(wt_path, ".env")
            # Check idempotency — skip if PORT= already present
            existing = ""
            if os.path.isfile(env_path):
                existing = open(env_path).read()
            if "PORT=" not in existing:
                port_vars = profile.e2e_gate_env(port)
                with open(env_path, "a") as f:
                    for k, v in port_vars.items():
                        f.write(f"{k}={v}\n")
                logger.info("bootstrap: injected port %d into %s/.env", port, wt_path)

    return copied


def _detect_package_manager(wt_path: str) -> str:
    """Detect package manager — delegates to canonical config.detect_package_manager."""
    from .config import detect_package_manager

    return detect_package_manager(wt_path)


def prune_worktree_context(wt_path: str) -> int:
    """Remove orchestrator-level commands from worktree .claude/ directory.

    Migrated from: dispatcher.sh prune_worktree_context() L123-150

    Returns number of files pruned.
    """
    claude_dir = os.path.join(wt_path, ".claude")
    if not os.path.isdir(claude_dir):
        return 0

    cmd_dir = os.path.join(wt_path, ".claude", "commands", "wt")
    if not os.path.isdir(cmd_dir):
        return 0

    pruned = 0
    for pattern in PRUNE_PATTERNS:
        for entry in os.listdir(cmd_dir):
            if not entry.startswith(pattern):
                continue
            filepath = os.path.join(cmd_dir, entry)
            if not os.path.isfile(filepath):
                continue

            # Check if tracked by git
            rel_path = os.path.relpath(filepath, wt_path)
            check_r = run_git("ls-files", "--error-unmatch", rel_path, cwd=wt_path)
            if check_r.exit_code == 0:
                run_git("rm", "-q", rel_path, cwd=wt_path)
            else:
                os.remove(filepath)
            pruned += 1

    if pruned > 0:
        logger.info("pruned %d orchestrator command(s) from worktree", pruned)
        run_git("commit", "-m", "chore: prune orchestrator commands from worktree",
                "--no-verify", cwd=wt_path)

    return pruned


# ─── Startup Guide ───────────────────────────────────────────────────


def generate_startup_guide(wt_path: str) -> str:
    """Detect project stack and generate an Application Startup guide section.

    Detects: package manager, framework dev command, DB tool (Prisma/Drizzle),
    Playwright config existence.  Returns markdown content (without the heading).
    """
    d = Path(wt_path)
    pm = _detect_package_manager(wt_path) or "npm"
    lines: list[str] = []

    lines.append(f"```bash\n{pm} install\n```\n")

    # Detect framework dev command from package.json scripts
    pkg_json = d / "package.json"
    pkg_data: dict = {}
    if pkg_json.is_file():
        try:
            pkg_data = json.loads(pkg_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    scripts = pkg_data.get("scripts", {})
    if scripts.get("dev"):
        lines.append(f"**Dev server:** `{pm} run dev`\n")

    # Detect DB tool
    all_deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
    if "prisma" in all_deps or "@prisma/client" in all_deps:
        lines.append(f"**Database:** `npx prisma db push` (or `npx prisma migrate dev`) then `npx prisma db seed` if seed script exists\n")
    elif "drizzle-orm" in all_deps:
        lines.append(f"**Database:** `npx drizzle-kit push` (or check drizzle config for migration command)\n")

    # Detect Playwright
    pw_config = any((d / name).is_file() for name in ("playwright.config.ts", "playwright.config.js"))
    if pw_config or "playwright" in all_deps or "@playwright/test" in all_deps:
        lines.append(f"**E2E tests:** `npx playwright install --with-deps chromium` then `npx playwright test`\n")

    # Test command
    for candidate in ("test", "test:unit", "test:ci"):
        if scripts.get(candidate):
            lines.append(f"**Unit tests:** `{pm} run {candidate}`\n")
            break

    return "\n".join(lines)


def append_startup_guide_to_claudemd(wt_path: str) -> bool:
    """Append ``## Application Startup`` section to worktree CLAUDE.md.

    Idempotent: if section already exists, does nothing.
    Creates CLAUDE.md if missing.

    Returns True if section was appended, False if skipped/already present.
    """
    claude_md = os.path.join(wt_path, "CLAUDE.md")

    existing = ""
    if os.path.isfile(claude_md):
        try:
            existing = Path(claude_md).read_text(encoding="utf-8")
        except OSError:
            pass

    if "## Application Startup" in existing:
        return False

    guide_content = generate_startup_guide(wt_path)
    section = f"\n\n## Application Startup\n\n{guide_content}\n"

    try:
        with open(claude_md, "a") as f:
            f.write(section)
        logger.info("Appended Application Startup guide to %s", claude_md)
        return True
    except OSError:
        logger.warning("Failed to write startup guide to %s", claude_md)
        return False


# ─── Model Routing ───────────────────────────────────────────────────


def _is_doc_change(change_name: str) -> bool:
    """Check if change name matches doc-change pattern.

    Migrated from: dispatcher.sh resolve_change_model() L163-166
    """
    return bool(
        change_name.startswith("doc-")
        or "-doc-" in change_name
        or change_name.endswith("-docs")
        or "-docs-" in change_name
    )


def resolve_change_model(
    change: Change,
    default_model: str = "opus",
    model_routing: str = "off",
) -> str:
    """Resolve effective model for a change.

    Migrated from: dispatcher.sh resolve_change_model() L157-209

    Three-tier priority:
    1. Explicit per-change model > 2. Complexity-based routing > 3. default_model
    """
    is_doc = _is_doc_change(change.name)

    # 1. Per-change explicit model (highest priority)
    explicit_model = change.model
    if explicit_model:
        # Guard: sonnet only for doc changes
        if explicit_model == "sonnet" and not is_doc:
            logger.warning(
                "overriding planner model=sonnet → opus for code change '%s'",
                change.name,
            )
            return "opus"
        return explicit_model

    # 2. Complexity-based routing
    if model_routing == "complexity":
        if change.complexity == "S" and change.change_type != "feature":
            logger.info("model routing: %s → sonnet (S-complexity, type=%s)", change.name, change.change_type)
            return "sonnet"
        if is_doc:
            return "sonnet"

    # 3. Default — doc changes always sonnet
    if is_doc:
        return "sonnet"

    return default_model


# ─── Recovery ────────────────────────────────────────────────────────


def recover_orphaned_changes(
    state_path: str,
    event_bus: EventBus | None = None,
) -> int:
    """Detect and recover orphaned changes.

    Migrated from: dispatcher.sh recover_orphaned_changes() L213-255

    Two recovery modes:
    1. No worktree, dead PID → reset to "pending" (CHANGE_RECOVERED)
    2. Worktree exists, dead/missing PID → reset to "stopped" (CHANGE_RECONCILED)
    """
    state = load_state(state_path)
    recovered = 0
    reconciled = 0

    for change in state.changes:
        if change.status not in ("running", "verifying", "stalled"):
            continue

        pid = change.ralph_pid or 0
        pid_alive = False
        if pid > 0:
            result = check_pid(pid, "set-loop")
            pid_alive = result.alive and result.match

        # Case 1: Worktree exists
        if change.worktree_path and os.path.isdir(change.worktree_path):
            if pid_alive:
                continue  # Agent is still working
            # Worktree present but agent is dead — set to "stopped" for resume
            reason = "dead_pid_live_worktree" if pid > 0 else "no_pid_live_worktree"
            logger.info("reconciling change %s: worktree exists but agent dead (was %s, reason=%s)",
                        change.name, change.status, reason)
            update_change_field(state_path, change.name, "status", "stopped", event_bus=event_bus)
            update_change_field(state_path, change.name, "ralph_pid", None, event_bus=event_bus)
            if event_bus:
                event_bus.emit("CHANGE_RECONCILED", change=change.name, data={"reason": reason})
            reconciled += 1
            continue

        # Case 2: No worktree — skip if PID is alive (running somewhere)
        if pid_alive:
            logger.warning("change %s has live process PID %d, skipping recovery", change.name, pid)
            continue

        # Orphaned (no worktree, dead PID) — reset to pending
        logger.info("recovering orphaned change: %s (was %s)", change.name, change.status)
        update_change_field(state_path, change.name, "status", "pending", event_bus=event_bus)
        update_change_field(state_path, change.name, "worktree_path", None, event_bus=event_bus)
        update_change_field(state_path, change.name, "ralph_pid", None, event_bus=event_bus)
        # Note: verify_retry_count intentionally NOT reset — preserves retry history
        # across crashes for accurate E2E reporting (LOCK-003)
        if event_bus:
            event_bus.emit("CHANGE_RECOVERED", change=change.name, data={"reason": "orphaned_after_crash"})
        recovered += 1

    if recovered > 0:
        logger.info("recovered %d orphaned change(s)", recovered)
    if reconciled > 0:
        logger.info("reconciled %d change(s) with live worktree but dead agent", reconciled)

    return recovered + reconciled


def redispatch_change(
    state_path: str,
    change_name: str,
    failure_pattern: str = "stuck",
    event_bus: EventBus | None = None,
    max_redispatch: int = 2,
) -> None:
    """Redispatch a stuck change to a fresh worktree.

    Migrated from: dispatcher.sh redispatch_change() L879-965

    Kills Ralph, salvages partial work, cleans up worktree, resets to pending.
    """
    state = load_state(state_path)
    change = _find_change(state, change_name)
    if not change:
        logger.error("redispatch: change not found: %s", change_name)
        return

    wt_path = change.worktree_path or ""
    tokens_used = change.tokens_used
    redispatch_count = change.redispatch_count

    logger.info(
        "redispatching %s (attempt %d/%d, pattern=%s)",
        change_name, redispatch_count + 1, max_redispatch, failure_pattern,
    )

    # 1. Kill Ralph PID
    pid = change.ralph_pid or 0
    if pid > 0:
        kill_result = safe_kill(pid, "set-loop", timeout=5)
        logger.info("redispatch: safe-kill PID %d for %s: %s", pid, change_name, kill_result.outcome)

    # 2. Salvage partial work
    partial_files = ""
    iter_count = 0
    if wt_path and os.path.isdir(wt_path):
        diff_r = run_git("diff", "--name-only", "HEAD", cwd=wt_path)
        if diff_r.exit_code == 0 and diff_r.stdout.strip():
            partial_files = ", ".join(diff_r.stdout.strip().splitlines())
        loop_state_path = os.path.join(wt_path, ".set", "loop-state.json")
        if os.path.isfile(loop_state_path):
            try:
                with open(loop_state_path) as f:
                    ls = json.load(f)
                iters = ls.get("iterations", [])
                iter_count = len(iters) if isinstance(iters, list) else 0
            except (json.JSONDecodeError, OSError):
                pass

    # 3. Build retry_context
    retry_prompt = (
        f"## Previous Attempt Failed (redispatch {redispatch_count}/{redispatch_count + 1})\n\n"
        f"Failure pattern: {failure_pattern}\n"
        f"Iterations completed: {iter_count}\n"
        f"Tokens used: {tokens_used}\n\n"
        f"Files modified in failed attempt: {partial_files}\n\n"
        f"Start fresh — do not repeat the same approach that led to {failure_pattern}."
    )
    update_change_field(state_path, change_name, "retry_context", retry_prompt, event_bus=event_bus)

    # 4. Increment redispatch_count
    new_count = redispatch_count + 1
    update_change_field(state_path, change_name, "redispatch_count", new_count, event_bus=event_bus)

    # 5. Emit event
    if event_bus:
        event_bus.emit("WATCHDOG_REDISPATCH", change=change_name, data={
            "redispatch_count": new_count,
            "failure_pattern": failure_pattern,
            "tokens_used": tokens_used,
            "iterations": iter_count,
        })

    # 6. Clean up old worktree
    if wt_path and os.path.isdir(wt_path):
        branch_r = run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=wt_path)
        branch_name = branch_r.stdout.strip() if branch_r.exit_code == 0 else ""
        remove_r = run_git("worktree", "remove", "--force", wt_path)
        if remove_r.exit_code != 0:
            logger.warning("redispatch: git worktree remove failed for %s, trying rm", wt_path)
            shutil.rmtree(wt_path, ignore_errors=True)
        if branch_name and branch_name != "HEAD":
            run_git("branch", "-D", branch_name)
        logger.info("redispatch: cleaned up worktree %s", wt_path)

    # 7. Reset watchdog
    with locked_state(state_path) as st:
        ch = _find_change(st, change_name)
        if ch:
            ch.watchdog = WatchdogState(
                last_activity_epoch=int(time.time()),
                action_hash_ring=[],
                consecutive_same_hash=0,
                escalation_level=0,
            )

    # 8. Clear fields and set pending
    update_change_field(state_path, change_name, "worktree_path", None, event_bus=event_bus)
    update_change_field(state_path, change_name, "ralph_pid", None, event_bus=event_bus)
    update_change_field(state_path, change_name, "status", "pending", event_bus=event_bus)

    send_notification(
        "set-orchestrate",
        f"Redispatching '{change_name}' ({failure_pattern}, attempt {new_count}/{max_redispatch})",
        urgency="normal",
    )
    logger.info("redispatch complete for %s — status set to pending", change_name)


def retry_failed_builds(
    state_path: str,
    max_retries: int = 2,
    event_bus: EventBus | None = None,
) -> int:
    """Retry changes with failed builds before triggering full replan.

    Migrated from: dispatcher.sh retry_failed_builds() L969-995

    Returns number of changes retried.
    """
    state = load_state(state_path)
    retried = 0

    for change in state.changes:
        if change.status != "failed" or change.build_result != "fail":
            continue
        gate_retry = change.extras.get("gate_retry_count", 0)
        if gate_retry >= max_retries:
            continue

        gate_retry += 1
        update_change_field(state_path, change.name, "gate_retry_count", gate_retry, event_bus=event_bus)
        logger.info("retrying failed build for %s (attempt %d/%d)", change.name, gate_retry, max_retries)

        # Build retry context with build output
        build_output = change.extras.get("build_output", "")
        retry_prompt = (
            f"Build failed. Fix the build error.\n\n"
            f"Build output:\n{build_output[:2000]}\n\n"
            f"Original scope: {change.scope}"
        )
        update_change_field(state_path, change.name, "retry_context", retry_prompt, event_bus=event_bus)
        update_change_field(state_path, change.name, "status", "pending", event_bus=event_bus)
        resume_change(state_path, change.name, event_bus=event_bus)
        retried += 1

    return retried


# ─── Core Dispatch ───────────────────────────────────────────────────


def _find_change(state: OrchestratorState, name: str) -> Change | None:
    """Find a change by name in state."""
    for c in state.changes:
        if c.name == name:
            return c
    return None


def _unique_worktree_name(project_path: str, change_name: str) -> str:
    """Return a unique worktree name, appending -N suffix if branch or dir already exists.

    Prevents collisions when a spec-switch run creates a change with the same
    name as a prior run (e.g., 'product-catalog-list' from v1 run still has
    an unmerged branch).
    """
    # Check if branch and directory are both free
    branch = f"change/{change_name}"
    wt_dir = f"{project_path}-{change_name}"
    branch_exists = run_git("rev-parse", "--verify", branch, cwd=project_path).exit_code == 0
    dir_exists = os.path.isdir(wt_dir)

    if not branch_exists and not dir_exists:
        return change_name  # no collision

    # Append numeric suffix to find a free name
    for i in range(2, 100):
        candidate = f"{change_name}-{i}"
        branch = f"change/{candidate}"
        wt_dir = f"{project_path}-{candidate}"
        branch_exists = run_git("rev-parse", "--verify", branch, cwd=project_path).exit_code == 0
        dir_exists = os.path.isdir(wt_dir)
        if not branch_exists and not dir_exists:
            logger.info("change name collision: %s exists, using %s", change_name, candidate)
            return candidate

    logger.error("could not find unique name for %s after 98 attempts", change_name)
    return change_name  # fallback to original


def _find_existing_worktree(project_path: str, change_name: str) -> str:
    """Find existing worktree path for a change.

    Tries the conventional path: <project_path>-<change_name>
    """
    wt_path = f"{project_path}-{change_name}"
    if os.path.isdir(wt_path):
        return wt_path
    # Fallback: check git worktree list
    r = run_git("worktree", "list", "--porcelain", cwd=project_path)
    if r.exit_code == 0:
        for line in r.stdout.splitlines():
            if line.startswith("worktree ") and change_name in line:
                return line.split(" ", 1)[1]
    return wt_path


# ─── Read-First & Conventions Helpers ────────────────────────────────


# Detectable paths → read-first directive templates.
# Each entry: (relative_path_to_check, directive_text)
_READ_FIRST_RULES: list[tuple[str, str]] = [
    ("prisma/schema.prisma", "Before writing database/Prisma code, read `prisma/schema.prisma` for accurate model and field names"),
    ("src/components", "Before creating new components, check `src/components/` for existing ones to reuse"),
    ("src/lib", "Before adding utility functions, check `src/lib/` for existing helpers"),
    ("src/app", "Before creating new routes, check `src/app/` for existing route structure and patterns"),
    ("src/messages", "Before adding i18n keys, check `src/messages/` for existing namespaces and key conventions"),
]


def _detect_read_first_directives(wt_path: str) -> list[str]:
    """Detect project structure and return read-first directives."""
    directives = []
    for rel_path, directive in _READ_FIRST_RULES:
        full_path = os.path.join(wt_path, rel_path)
        if os.path.exists(full_path):
            directives.append(directive)
    return directives


def _format_conventions_summary(digest_dir: str) -> str:
    """Read conventions.json from digest and format as compact markdown."""
    conv_path = os.path.join(digest_dir, "conventions.json")
    if not os.path.isfile(conv_path):
        return ""
    try:
        with open(conv_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ""

    categories = data.get("categories", [])
    if not categories:
        return ""

    lines = []
    for cat in categories:
        name = cat.get("name", "")
        rules = cat.get("rules", [])
        if not name or not rules:
            continue
        lines.append(f"**{name}:** {'; '.join(rules)}")

    return "\n".join(lines) if lines else ""


def _detect_i18n_sidecar(wt_path: str, change_name: str, namespace: str = "") -> str:
    """Detect i18n setup and generate sidecar file instructions.

    If the project uses JSON-based i18n (next-intl, react-intl), instructs
    the agent to write to a sidecar file instead of the canonical messages file.
    """
    pkg_path = os.path.join(wt_path, "package.json")
    if not os.path.isfile(pkg_path):
        return ""
    try:
        with open(pkg_path) as f:
            pkg = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ""

    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    i18n_lib = ""
    if "next-intl" in deps:
        i18n_lib = "next-intl"
    elif "react-intl" in deps:
        i18n_lib = "react-intl"
    elif "i18next" in deps or "react-i18next" in deps:
        i18n_lib = "i18next"

    if not i18n_lib:
        return ""

    # Detect messages directory
    msg_dirs = ["src/messages", "messages", "src/i18n/messages", "public/locales"]
    msg_dir = ""
    for d in msg_dirs:
        if os.path.isdir(os.path.join(wt_path, d)):
            msg_dir = d
            break

    if not msg_dir:
        return ""

    # Use change name as namespace if not provided
    ns = namespace or change_name.replace("-", "_")

    return (
        f"**i18n Sidecar Pattern ({i18n_lib}):** "
        f"Do NOT edit the main messages files in `{msg_dir}/` directly. "
        f"Instead, create sidecar files: `{msg_dir}/<locale>.{ns}.json` "
        f"with your new translation keys under a `\"{ns}\"` top-level namespace. "
        f"These will be merged into the canonical file after merge."
    )


def _build_input_content(
    change_name: str,
    scope: str,
    roadmap_item: str,
    ctx: DispatchContext,
    input_mode: str = "",
    input_path: str = "",
    retry_ctx: str = "",
    change_requirements: list[str] | None = None,
    also_affects_reqs: list[str] | None = None,
    digest_dir: str = "",
) -> str:
    """Build dispatcher-injected context for input.md.

    This file is the orchestrator's brief to the agent — separate from
    proposal.md which is the agent's own artifact.
    """
    lines = []

    lines.append("## Scope")
    lines.append(scope)
    if roadmap_item and roadmap_item != scope:
        lines.append(f"\n**Roadmap item:** {roadmap_item}")

    if input_mode == "digest" and input_path:
        lines.append(f"\n**Spec source:** `{input_path}`")

    if ctx.memory_ctx:
        lines.append(f"\n## Project Context\n{ctx.memory_ctx}")

    if ctx.pk_context:
        lines.append(f"\n{ctx.pk_context}")

    if ctx.sibling_context:
        lines.append(f"\n{ctx.sibling_context}")

    if ctx.design_context:
        lines.append(f"\n## Design Context\n{ctx.design_context}")

    # Assigned Requirements section (with AC items from digest when available)
    req_lookup: dict[str, dict] = {}
    if change_requirements or also_affects_reqs:
        req_lookup = _load_requirements_lookup(digest_dir) if digest_dir else {}

    if change_requirements:
        req_lines = []
        for rid in change_requirements:
            req = req_lookup.get(rid, {})
            title = req.get("title", rid)
            ac_items = req.get("acceptance_criteria", []) or []
            if ac_items:
                req_lines.append(f"- {rid}: {title}")
                for ac in ac_items:
                    req_lines.append(f"  - {ac}")
            else:
                brief = req.get("brief", "")
                if brief:
                    req_lines.append(f"- {rid}: {title} — {brief}")
                else:
                    req_lines.append(f"- {rid}: {title}")
        if req_lines:
            lines.append("\n## Assigned Requirements")
            lines.extend(req_lines)

    # Cross-cutting requirements (title-only, no AC)
    if also_affects_reqs:
        cross_lines = []
        for rid in also_affects_reqs:
            req = req_lookup.get(rid, {})
            title = req.get("title", rid)
            cross_lines.append(f"- {rid}: {title}")
        if cross_lines:
            lines.append("\n## Cross-Cutting Requirements (awareness only)")
            lines.extend(cross_lines)

    # Read-first directives (detected from worktree structure)
    if ctx.read_first_directives:
        lines.append("\n## Read Before Writing")
        for directive in ctx.read_first_directives:
            lines.append(f"- {directive}")

    # Project conventions (from digest)
    if ctx.conventions_summary:
        lines.append(f"\n## Project Conventions\n{ctx.conventions_summary}")

    # i18n sidecar instructions
    if ctx.i18n_sidecar_instructions:
        lines.append(f"\n## i18n Instructions\n{ctx.i18n_sidecar_instructions}")

    # Cross-cutting file restrictions
    if ctx.cross_cutting_restrictions:
        lines.append("\n## Cross-Cutting File Restrictions")
        for restriction in ctx.cross_cutting_restrictions:
            lines.append(f"- {restriction}")

    if ctx.review_learnings:
        lines.append(f"\n## Lessons from Prior Changes\n{ctx.review_learnings}")

    if ctx.review_learnings_checklist:
        lines.append(f"\n{ctx.review_learnings_checklist}")

    if retry_ctx:
        lines.append(f"\n## Retry Context\n{retry_ctx}")

    return "\n".join(lines) + "\n"


def _load_requirements_lookup(digest_dir: str) -> dict[str, dict]:
    """Load requirements.json from digest dir into a {req_id: req_dict} lookup."""
    if not digest_dir:
        return {}
    req_path = os.path.join(digest_dir, "requirements.json")
    if not os.path.isfile(req_path):
        return {}
    try:
        with open(req_path) as f:
            data = json.load(f)
        return {
            r["id"]: r
            for r in data.get("requirements", [])
            if r.get("id")
        }
    except (json.JSONDecodeError, OSError, KeyError):
        return {}


def _build_review_learnings(findings_path: str, exclude_change: str) -> str:
    """Build compact cross-change review learnings from JSONL.

    Reads review-findings.jsonl, excludes the current change's own findings,
    keeps only CRITICAL+HIGH, clusters by keyword, and returns a compact
    markdown section (max ~15 lines).
    """
    if not os.path.isfile(findings_path):
        return ""

    import re as _re
    from .review_clusters import REVIEW_PATTERN_CLUSTERS

    # Read and filter findings
    pattern_counts: dict[str, set[str]] = {}
    try:
        with open(findings_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                change = entry.get("change", "")
                if change == exclude_change:
                    continue  # skip own findings
                for issue in entry.get("issues", []):
                    sev = issue.get("severity", "")
                    if sev not in ("CRITICAL", "HIGH"):
                        continue
                    norm = _re.sub(r"\[(?:CRITICAL|HIGH)\]\s*", "", issue.get("summary", ""))[:80]
                    if norm:
                        pattern_counts.setdefault(norm, set()).add(change)
    except OSError:
        return ""

    if not pattern_counts:
        return ""

    # Cluster by keywords
    cluster_results: dict[str, set[str]] = {}
    clustered_norms: set[str] = set()
    for norm, changes_set in pattern_counts.items():
        norm_lower = norm.lower()
        for cid, keywords in REVIEW_PATTERN_CLUSTERS.items():
            if any(kw in norm_lower for kw in keywords):
                cluster_results.setdefault(cid, set()).update(changes_set)
                clustered_norms.add(norm)
                break

    # Build output lines
    lines: list[str] = []

    # Clustered patterns first (high signal)
    _CLUSTER_LABELS = {
        "no-auth": "No authentication",
        "no-csrf": "Missing CSRF protection",
        "xss": "XSS risk",
        "no-rate-limit": "Missing rate limiting",
        "secrets-exposed": "Secrets/credentials exposed",
    }
    for cid, changes_set in sorted(cluster_results.items(), key=lambda x: -len(x[1])):
        label = _CLUSTER_LABELS.get(cid, cid)
        names = ", ".join(sorted(changes_set)[:3])
        suffix = f" +{len(changes_set)-3} more" if len(changes_set) > 3 else ""
        lines.append(f"- **{label}** ({names}{suffix})")

    # Unclustered individual patterns (deduplicated, top 5)
    unclustered = {k: v for k, v in pattern_counts.items() if k not in clustered_norms}
    for norm, changes_set in sorted(unclustered.items(), key=lambda x: -len(x[1]))[:5]:
        names = ", ".join(sorted(changes_set)[:2])
        lines.append(f"- {norm.strip('*').strip()} ({names})")

    if not lines:
        return ""

    # Cap at 12 finding lines
    lines = lines[:12]

    return (
        "These patterns caused CRITICAL/HIGH failures in other changes during this run:\n"
        + "\n".join(lines)
        + f"\n\nFull details: `set/orchestration/review-findings.jsonl`"
    )


def _build_pk_context(scope: str, project_path: str) -> str:
    """Build project-knowledge context from YAML.

    Migrated from: dispatcher.sh dispatch_change() L336-371
    """
    # Find project-knowledge.yaml
    pk_candidates = [
        os.path.join(project_path, "project-knowledge.yaml"),
        os.path.join(project_path, ".claude", "project-knowledge.yaml"),
    ]
    pk_file = ""
    for p in pk_candidates:
        if os.path.isfile(p):
            pk_file = p
            break

    if not pk_file or not shutil.which("yq"):
        return ""

    # Check feature touches
    feature_touches = ""
    names_r = run_command(["yq", "-r", ".features | keys[]? // empty", pk_file], timeout=5)
    if names_r.exit_code == 0 and names_r.stdout.strip():
        for fname in names_r.stdout.strip().splitlines():
            if not fname.strip():
                continue
            if fname.lower() in scope.lower():
                touches_r = run_command(
                    ["yq", "-r", f'.features."{fname}".touches[]? // empty', pk_file],
                    timeout=5,
                )
                if touches_r.exit_code == 0 and touches_r.stdout.strip():
                    feature_touches += f"Feature '{fname}' touches: {touches_r.stdout.strip()}\n"
                ref_r = run_command(
                    ["yq", "-r", f'.features."{fname}".reference_impl // false', pk_file],
                    timeout=5,
                )
                if ref_r.exit_code == 0 and ref_r.stdout.strip() == "true":
                    feature_touches += f"Feature '{fname}' has a reference implementation — follow existing patterns.\n"

    # Cross-cutting files
    cc_r = run_command(
        ["yq", "-r", '.cross_cutting_files[]? | "- \\(.path): \\(.description // "")"', pk_file],
        timeout=5,
    )
    cc_files = cc_r.stdout.strip() if cc_r.exit_code == 0 else ""

    if not feature_touches and not cc_files:
        return ""

    pk_ctx = "## Project Knowledge\n"
    if feature_touches:
        pk_ctx += feature_touches + "\n"
    if cc_files:
        pk_ctx += f"Cross-cutting files (coordinate with other changes):\n{cc_files}\n"
    return pk_ctx


def _inject_feature_rules(project_path: str, wt_path: str, scope: str, spec_files: list[str] | None = None) -> None:
    """Inject feature-matched rule files from project-knowledge.yaml into worktree.

    Reads rules_file from matching features and copies to <wt_path>/.claude/rules/.
    Matching: spec_files paths (preferred) or feature name keyword in scope text.
    No-op if project-knowledge.yaml absent or yq not available.
    """
    pk_candidates = [
        os.path.join(project_path, ".claude", "project-knowledge.yaml"),
        os.path.join(project_path, "project-knowledge.yaml"),
    ]
    pk_file = next((p for p in pk_candidates if os.path.isfile(p)), "")
    if not pk_file or not shutil.which("yq"):
        return

    rules_dir = os.path.join(wt_path, ".claude", "rules")
    os.makedirs(rules_dir, exist_ok=True)

    names_r = run_command(["yq", "-r", ".features | keys[]? // empty", pk_file], timeout=5)
    if names_r.exit_code != 0 or not names_r.stdout.strip():
        return

    for fname in names_r.stdout.strip().splitlines():
        fname = fname.strip()
        if not fname:
            continue

        # Determine if this feature matches the change
        matched = False
        if spec_files:
            # Preferred: match feature touches globs against spec file paths
            touches_r = run_command(
                ["yq", "-r", f'.features."{fname}".touches[]? // empty', pk_file], timeout=5
            )
            if touches_r.exit_code == 0 and touches_r.stdout.strip():
                import fnmatch
                for touch_glob in touches_r.stdout.strip().splitlines():
                    for sf in spec_files:
                        if fnmatch.fnmatch(sf, touch_glob) or fnmatch.fnmatch(os.path.basename(sf), touch_glob):
                            matched = True
                            break
                    if matched:
                        break
        if not matched:
            # Fallback: feature name keyword in scope text
            matched = fname.lower().replace("_", " ") in scope.lower() or fname.lower() in scope.lower()

        if not matched:
            continue

        # Read rules_file path
        rf_r = run_command(
            ["yq", "-r", f'.features."{fname}".rules_file // empty', pk_file], timeout=5
        )
        if rf_r.exit_code != 0 or not rf_r.stdout.strip() or rf_r.stdout.strip() == "null":
            continue

        rules_file_rel = rf_r.stdout.strip()
        src_path = os.path.join(project_path, rules_file_rel)
        if not os.path.isfile(src_path):
            logger.warning("rules_file not found: %s — skipping injection for feature '%s'", src_path, fname)
            continue

        dest_path = os.path.join(rules_dir, os.path.basename(src_path))
        if os.path.isfile(dest_path):
            logger.debug("rule already exists in worktree, skipping: %s", dest_path)
            continue

        shutil.copy2(src_path, dest_path)
        logger.info("injected feature rule: %s → .claude/rules/%s", fname, os.path.basename(src_path))


def _build_sibling_context(state: OrchestratorState) -> str:
    """Build sibling change status summary.

    Migrated from: dispatcher.sh dispatch_change() L374-379
    """
    siblings = []
    for c in state.changes:
        if c.status in ("running", "dispatched", "verifying"):
            siblings.append(f"{c.name}: {c.scope[:80]}")
    if not siblings:
        return ""
    return "## Active Sibling Changes (avoid conflicts)\n" + "\n".join(siblings) + "\n"


def _recall_dispatch_memory(scope: str) -> str:
    """Recall change-specific memories for dispatch.

    Migrated from: dispatcher.sh dispatch_change() L331-333
    """
    r = run_command(
        ["set-memory", "recall", scope, "--limit", "3", "--tags", "phase:execution"],
        timeout=5,
    )
    if r.exit_code == 0 and r.stdout.strip():
        return r.stdout.strip()[:1000]
    return ""


def dispatch_change(
    state_path: str,
    change_name: str,
    default_model: str = "opus",
    model_routing: str = "off",
    team_mode: bool = False,
    context_pruning: bool = True,
    event_bus: EventBus | None = None,
    input_mode: str = "",
    input_path: str = "",
    digest_dir: str = "",
    design_snapshot_dir: str = ".",
) -> bool:
    """Dispatch a single change to a worktree.

    Migrated from: dispatcher.sh dispatch_change() L259-586

    Returns True on success, False on failure.
    """
    # Atomic status guard: verify change is "pending" and mark "dispatched"
    # inside locked_state to prevent duplicate dispatch from concurrent monitor cycles.
    with locked_state(state_path) as st:
        change = _find_change(st, change_name)
        if not change:
            logger.error("dispatch: change not found: %s", change_name)
            return False
        if change.status != "pending":
            logger.info("dispatch: change %s already dispatched (status=%s), skipping", change_name, change.status)
            return False
        change.status = "dispatched"  # Mark immediately to prevent race

    # Re-read for scope/roadmap (outside lock — non-critical reads)
    state = load_state(state_path)
    change = _find_change(state, change_name)
    scope = change.scope
    roadmap_item = change.roadmap_item

    logger.info("dispatching change: %s", change_name)
    if event_bus:
        event_bus.emit("DISPATCH", change=change_name, data={"scope": scope})

    # Reset token counters for fresh dispatch
    for field in (
        "tokens_used_prev", "tokens_used",
        "input_tokens", "output_tokens",
        "cache_read_tokens", "cache_create_tokens",
        "input_tokens_prev", "output_tokens_prev",
        "cache_read_tokens_prev", "cache_create_tokens_prev",
    ):
        update_change_field(state_path, change_name, field, 0, event_bus=event_bus)

    # Create or reuse worktree
    project_path = os.getcwd()
    wt_name = _unique_worktree_name(project_path, change_name)
    wt_path = f"{project_path}-{wt_name}"

    # Handle existing worktree gracefully — if change is already dispatched/running
    # with an active worktree, skip instead of creating a -2 suffix duplicate.
    if os.path.isdir(wt_path):
        # A pending→dispatched change should never have an existing worktree (Bug #30).
        logger.info("stale worktree for pending change %s — removing for fresh dispatch", change_name)
        run_command(["git", "worktree", "remove", wt_path, "--force"], timeout=30)
        if os.path.isdir(wt_path):
            import shutil
            shutil.rmtree(wt_path, ignore_errors=True)
        run_git("worktree", "prune")
        run_git("branch", "-D", f"change/{wt_name}")

    if not os.path.isdir(wt_path):
        # Clean stale branch
        branch_check = run_git("rev-parse", "--verify", f"change/{wt_name}")
        if branch_check.exit_code == 0:
            logger.info("removing stale branch change/%s before worktree creation", wt_name)
            run_git("branch", "-D", f"change/{wt_name}")

        wt_new_r = run_command(["set-new", wt_name, "--skip-open"], timeout=30)
        if wt_new_r.exit_code != 0:
            logger.error("failed to create worktree for %s: %s", change_name, wt_new_r.stderr)
            update_change_field(state_path, change_name, "status", "failed", event_bus=event_bus)
            return False

    # Find actual worktree path (use wt_name which may have -N suffix)
    wt_path = _find_existing_worktree(project_path, wt_name)

    # Bootstrap
    bootstrap_worktree(project_path, wt_path, change_name=change_name)

    # Config-driven env_vars → .env (after profile bootstrap, overrides profile defaults)
    try:
        _state = load_state(state_path)
        _directives = _state.extras.get("directives", {})
        env_vars = _directives.get("env_vars", {})
        if env_vars and isinstance(env_vars, dict):
            env_file = os.path.join(wt_path, ".env")
            # Read existing .env (may have been created by profile bootstrap)
            existing: dict[str, str] = {}
            if os.path.isfile(env_file):
                with open(env_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, _, v = line.partition("=")
                            existing[k.strip()] = v.strip()
            # Merge: config overrides profile
            existing.update(env_vars)
            with open(env_file, "w") as f:
                for k, v in existing.items():
                    val = v if v.startswith('"') else f'"{v}"'
                    f.write(f"{k}={val}\n")
            logger.info("bootstrap: wrote %d env var(s) to .env in %s", len(existing), wt_path)
    except Exception:
        pass  # non-fatal — env_vars is optional

    # Sync with main immediately after bootstrap — ensures archive commits (openspec/specs/,
    # openspec/changes/ deletions) from recently merged changes are present before agent starts.
    # Without this, worktrees created right after a merge miss archive commits (Bug #38).
    sync_result = sync_worktree_with_main(wt_path, change_name)
    if sync_result.ok:
        logger.info("Post-bootstrap sync: %s synced with main", change_name)
    else:
        logger.warning("Post-bootstrap sync: %s sync failed (non-blocking): %s", change_name, sync_result.message)

    # Inject feature-matched rule files from project-knowledge.yaml (post-bootstrap)
    spec_files = change.spec_files if hasattr(change, "spec_files") else None
    _inject_feature_rules(project_path, wt_path, scope, spec_files=spec_files)

    # Prune orchestrator context
    if context_pruning:
        prune_worktree_context(wt_path)

    # Cross-change review learnings
    findings_path = os.path.join(os.path.dirname(state_path), "wt", "orchestration", "review-findings.jsonl")
    review_learnings = _build_review_learnings(findings_path, change_name)

    # Profile-based persistent review checklist (cross-run)
    review_checklist = ""
    try:
        from .profile_loader import load_profile
        _profile = load_profile()
        review_checklist = _profile.review_learnings_checklist(project_path)
    except Exception:
        logger.debug("Failed to load review learnings checklist", exc_info=True)

    # Gather enrichment context
    ctx = DispatchContext(
        memory_ctx=_recall_dispatch_memory(scope),
        pk_context=_build_pk_context(scope, project_path),
        sibling_context=_build_sibling_context(state),
        review_learnings=review_learnings,
        review_learnings_checklist=review_checklist,
    )

    # Cross-cutting file restrictions from planner ownership assignment
    no_modify = change.extras.get("cross_cutting_no_modify", [])
    if no_modify:
        ctx.cross_cutting_restrictions = [
            f"DO NOT modify `{f}` — owned by another change. If you need changes to this file, note them in your commit message."
            for f in no_modify
        ]

    # Design context (tokens + hierarchy)
    bridge_path = os.path.join(SET_TOOLS_ROOT, "lib", "design", "bridge.sh")
    design_r = run_command(
        ["bash", "-c", f'source "{bridge_path}" 2>/dev/null && design_context_for_dispatch "{scope}" "{design_snapshot_dir}"'],
        timeout=5,
    ) if os.path.isfile(bridge_path) else type("R", (), {"exit_code": 1, "stdout": ""})()
    if design_r.exit_code == 0 and design_r.stdout.strip():
        ctx.design_context = design_r.stdout.strip()

    # Design source files (Figma component code matched against scope)
    if os.path.isfile(bridge_path):
        sources_r = run_command(
            ["bash", "-c", f'source "{bridge_path}" 2>/dev/null && design_sources_for_dispatch "{scope}" "{design_snapshot_dir}"'],
            timeout=10,
        )
        if sources_r.exit_code == 0 and sources_r.stdout.strip():
            if ctx.design_context:
                ctx.design_context += "\n\n" + sources_r.stdout.strip()
            else:
                ctx.design_context = sources_r.stdout.strip()

    # Proactive rule injection (keyword-matched rules from .claude/rules/)
    rule_injection = _build_rule_injection(scope, wt_path)
    if rule_injection:
        if ctx.design_context:
            ctx.design_context += "\n\n" + rule_injection
        else:
            ctx.design_context = rule_injection

    # Setup change in worktree
    _setup_change_in_worktree(
        wt_path, change_name, scope, roadmap_item, ctx,
        state_path, input_mode, input_path, digest_dir,
    )

    # Append startup guide to worktree CLAUDE.md (idempotent)
    append_startup_guide_to_claudemd(wt_path)

    # Append schema digest to worktree CLAUDE.md (replaces data-definitions.md)
    from set_orch.dispatcher_schema import append_schema_digest_to_claudemd
    append_schema_digest_to_claudemd(wt_path)

    # Update state
    update_change_field(state_path, change_name, "status", "dispatched", event_bus=event_bus)
    update_change_field(state_path, change_name, "worktree_path", wt_path, event_bus=event_bus)
    update_change_field(state_path, change_name, "started_at", datetime.now().isoformat(), event_bus=event_bus)

    # Pre-dispatch hook (call bash hook if it exists)
    hooks_path = os.path.join(SET_TOOLS_ROOT, "lib", "orchestration", "hooks.sh")
    if os.path.isfile(hooks_path):
        hook_r = run_command(
            ["bash", "-c", f'source "{hooks_path}" && run_hook pre_dispatch "{change_name}" dispatched "{wt_path}"'],
            timeout=10,
        )
        if hook_r.exit_code != 0:
            logger.warning("pre_dispatch hook blocked %s", change_name)
            update_change_field(state_path, change_name, "status", "pending", event_bus=event_bus)
            return False

    # Profile pre-dispatch checks (after directive hook, before Ralph loop)
    from .profile_loader import load_profile
    _dispatch_profile = load_profile()
    if hasattr(_dispatch_profile, "pre_dispatch_checks"):
        pre_errors = _dispatch_profile.pre_dispatch_checks(
            getattr(change, "change_type", "feature"), wt_path,
        )
        if pre_errors:
            for err in pre_errors:
                logger.error("Pre-dispatch check failed for %s: %s", change_name, err)
            update_change_field(state_path, change_name, "status", "pending", event_bus=event_bus)
            if event_bus:
                event_bus.emit("DISPATCH", change=change_name,
                               data={"result": "blocked", "reason": "pre_dispatch_check", "errors": pre_errors})
            return False

    # Dispatch via set-loop
    impl_model = resolve_change_model(change, default_model, model_routing)
    # Persist resolved model so verifier uses correct context window size
    update_change_field(state_path, change_name, "model", impl_model)
    return dispatch_via_wt_loop(
        state_path, change_name, impl_model, wt_path, scope,
        team_mode=team_mode, event_bus=event_bus,
    )


def _setup_change_in_worktree(
    wt_path: str,
    change_name: str,
    scope: str,
    roadmap_item: str,
    ctx: DispatchContext,
    state_path: str,
    input_mode: str,
    input_path: str,
    digest_dir: str,
) -> None:
    """Initialize OpenSpec change and input.md in worktree.

    Migrated from: dispatcher.sh dispatch_change() L382-561 (subshell)
    proposal.md is left for the agent to write — only input.md is pre-created.
    """
    change_dir = os.path.join(wt_path, "openspec", "changes", change_name)

    # Initialize OpenSpec change if needed
    if not os.path.isdir(change_dir):
        r = run_command(["openspec", "new", "change", change_name], cwd=wt_path, timeout=10)
        if r.exit_code != 0:
            logger.error("openspec new change failed for %s: %s", change_name, r.stderr)
        if not os.path.isdir(change_dir):
            logger.error("openspec change directory not created for %s", change_name)

    # Read retry_context (if any) before writing input.md
    state = load_state(state_path)
    change = _find_change(state, change_name)
    retry_ctx = ""
    if change:
        retry_ctx = change.extras.get("retry_context", "") or ""

    # Populate read-first directives based on worktree contents
    ctx.read_first_directives = _detect_read_first_directives(wt_path)

    # Populate conventions summary from digest
    if digest_dir:
        ctx.conventions_summary = _format_conventions_summary(digest_dir)

    # Detect i18n sidecar pattern
    ctx.i18n_sidecar_instructions = _detect_i18n_sidecar(wt_path, change_name)

    # Write input.md — dispatcher context for the agent (separate from proposal.md)
    input_md_path = os.path.join(change_dir, "input.md")
    content = _build_input_content(
        change_name, scope, roadmap_item, ctx,
        input_mode, input_path, retry_ctx,
        change_requirements=change.requirements if change else None,
        also_affects_reqs=change.also_affects_reqs if change else None,
        digest_dir=digest_dir,
    )
    os.makedirs(os.path.dirname(input_md_path), exist_ok=True)
    with open(input_md_path, "w") as f:
        f.write(content)
    logger.info("wrote input.md for %s", change_name)

    if retry_ctx:
        update_change_field(state_path, change_name, "retry_context", None)

    # Digest mode: copy spec files
    if input_mode == "digest" and digest_dir:
        _setup_digest_context(wt_path, change_name, state_path, digest_dir)


def _setup_digest_context(
    wt_path: str,
    change_name: str,
    state_path: str,
    digest_dir: str,
) -> None:
    """Copy spec files from digest to worktree .claude/spec-context/.

    Migrated from: dispatcher.sh dispatch_change() L494-537
    """
    index_path = os.path.join(digest_dir, "index.json")
    if not os.path.isfile(index_path):
        return

    try:
        with open(index_path) as f:
            index = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    spec_base_dir = index.get("spec_base_dir", "")
    state = load_state(state_path)
    change = _find_change(state, change_name)
    if not change:
        return

    spec_files = change.extras.get("spec_files", [])
    if spec_files:
        spec_ctx_dir = os.path.join(wt_path, ".claude", "spec-context")
        os.makedirs(spec_ctx_dir, exist_ok=True)
        for sf in spec_files:
            src_file = os.path.join(spec_base_dir, sf)
            if os.path.isfile(src_file):
                target_dir = os.path.join(spec_ctx_dir, os.path.dirname(sf))
                os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(src_file, target_dir)
            else:
                logger.warning("spec file not found: %s", src_file)

    # Copy conventions.json (data-definitions.md removed — replaced by schema digest)
    for extra in ("conventions.json",):
        src = os.path.join(digest_dir, extra)
        if os.path.isfile(src):
            spec_ctx_dir = os.path.join(wt_path, ".claude", "spec-context")
            os.makedirs(spec_ctx_dir, exist_ok=True)
            shutil.copy2(src, spec_ctx_dir)

    # Add .claude/spec-context/ to .gitignore
    gitignore = os.path.join(wt_path, ".gitignore")
    ignore_line = ".claude/spec-context/"
    if os.path.isfile(gitignore):
        with open(gitignore) as f:
            if ignore_line not in f.read().splitlines():
                with open(gitignore, "a") as fw:
                    fw.write(f"\n{ignore_line}\n")
    else:
        with open(gitignore, "w") as f:
            f.write(f"{ignore_line}\n")


def _kill_existing_wt_loop(wt_path: str, change_name: str) -> None:
    """Kill any existing set-loop/Claude session in a worktree before starting a new one.

    Prevents overlapping sessions that cause file conflicts and data corruption.
    """
    loop_state_path = os.path.join(wt_path, ".set", "loop-state.json")
    if not os.path.isfile(loop_state_path):
        return

    try:
        with open(loop_state_path) as f:
            ls = json.load(f)
        old_pid = int(ls.get("terminal_pid") or 0)
        if old_pid > 0:
            result = check_pid(old_pid, "set-loop")
            if result.alive and result.match:
                logger.warning(
                    "dispatch guard: killing existing set-loop PID %d in %s before new dispatch",
                    old_pid, change_name,
                )
                kill_result = safe_kill(old_pid, "set-loop", timeout=10)
                logger.info("dispatch guard: kill result for %s: %s", change_name, kill_result.outcome)
                time.sleep(1)  # Let tmux session die
        # Remove stale loop-state so new set-loop can start clean
        os.remove(loop_state_path)
        logger.info("dispatch guard: removed stale loop-state.json for %s", change_name)
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("dispatch guard: error cleaning %s: %s", change_name, e)


def dispatch_via_wt_loop(
    state_path: str,
    change_name: str,
    impl_model: str,
    wt_path: str,
    scope: str,
    team_mode: bool = False,
    event_bus: EventBus | None = None,
) -> bool:
    """Start set-loop in a worktree and verify startup.

    Migrated from: dispatcher.sh dispatch_via_wt_loop() L590-639

    Returns True if set-loop started successfully.
    """
    # Guard: kill any existing set-loop before starting a new one
    _kill_existing_wt_loop(wt_path, change_name)

    task_desc = f"Implement {change_name}: {scope[:200]}"

    cmd = [
        "set-loop", "start", task_desc,
        "--max", "30",
        "--done", "openspec",
        "--label", change_name,
        "--model", impl_model,
        "--change", change_name,
    ]
    if team_mode:
        cmd.append("--team")

    logger.info(
        "dispatch %s with model=%s budget=unlimited (iter limit: --max 30) team=%s",
        change_name, impl_model, team_mode,
    )

    # Start set-loop (fire and forget — it daemonizes via tmux)
    r = run_command(cmd, cwd=wt_path, timeout=30)

    # Poll for loop-state.json to verify startup
    loop_state_path = os.path.join(wt_path, ".set", "loop-state.json")
    retries = 0
    while not os.path.isfile(loop_state_path) and retries < 10:
        time.sleep(1)
        retries += 1

    if not os.path.isfile(loop_state_path):
        logger.error("set-loop failed to start for %s (no loop-state.json after %ds)", change_name, retries)
        if event_bus:
            event_bus.emit("ERROR", change=change_name, data={"error": "set-loop failed to start"})
        update_change_field(state_path, change_name, "status", "failed", event_bus=event_bus)
        return False

    # Extract terminal PID
    terminal_pid = 0
    try:
        with open(loop_state_path) as f:
            ls = json.load(f)
        terminal_pid = int(ls.get("terminal_pid") or 0)
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        pass

    update_change_field(state_path, change_name, "ralph_pid", terminal_pid, event_bus=event_bus)
    update_change_field(state_path, change_name, "status", "running", event_bus=event_bus)
    logger.info("ralph started for %s in %s (terminal PID %s)", change_name, wt_path, terminal_pid or "unknown")

    send_notification(
        "Change dispatched",
        f"'{change_name}' started in {wt_path}",
    )
    return True


def _load_serialize_triggers() -> list[str]:
    """Load serialize trigger patterns from plugin orchestration directives."""
    try:
        from .profile_loader import load_profile, NullProfile
        profile = load_profile()
        if isinstance(profile, NullProfile):
            return []
        directives = profile.get_orchestration_directives()
        return [
            getattr(d, "trigger", "")
            for d in directives
            if getattr(d, "action", "") == "serialize" and getattr(d, "trigger", "")
        ]
    except Exception:
        return []


def _is_serialized(name: str, state: Any, triggers: list[str]) -> bool:
    """Check if a change matches a serialize trigger and another match is running."""
    from .state import Change
    change = None
    for c in state.changes:
        if c.name == name:
            change = c
            break
    if not change:
        return False

    scope = (change.scope or "").lower()
    change_matches = any(t.lower() in scope or t.lower() in name.lower() for t in triggers)
    if not change_matches:
        return False

    # Check if any running change also matches
    for c in state.changes:
        if c.name == name:
            continue
        if c.status not in ("running", "dispatched"):
            continue
        c_scope = (c.scope or "").lower()
        if any(t.lower() in c_scope or t.lower() in c.name.lower() for t in triggers):
            return True
    return False


def dispatch_ready_changes(
    state_path: str,
    max_parallel: int,
    default_model: str = "opus",
    model_routing: str = "off",
    team_mode: bool = False,
    context_pruning: bool = True,
    event_bus: EventBus | None = None,
    input_mode: str = "",
    input_path: str = "",
    digest_dir: str = "",
    design_snapshot_dir: str = ".",
) -> int:
    """Dispatch pending changes respecting deps and parallel limits.

    Migrated from: dispatcher.sh dispatch_ready_changes() L663-723

    Returns number of changes dispatched.
    """
    state = load_state(state_path)

    running = count_changes_by_status(state, "running")
    running += count_changes_by_status(state, "dispatched")

    # Topological order from state (not plan — state carries forward after replan)
    order = topological_sort(state.changes)

    # Read current phase for milestone gating
    current_phase = state.extras.get("current_phase", 999)

    # Collect ready changes
    ready_names: list[str] = []
    for name in order:
        change = _find_change(state, name)
        if not change or change.status != "pending":
            continue
        # Phase gate
        if change.phase > current_phase:
            continue
        if deps_satisfied(state, name):
            ready_names.append(name)

    # Sort by complexity (L > M > S) to reduce tail latency
    if len(ready_names) > 1:
        priority_order = {"L": 0, "M": 1, "S": 2}
        ready_names.sort(key=lambda n: priority_order.get(
            (_find_change(state, n) or Change()).complexity, 1
        ))

    # Load plugin serialize directives
    serialize_triggers = _load_serialize_triggers()

    # Dispatch in priority order
    dispatched = 0
    for name in ready_names:
        if running >= max_parallel:
            break

        # Check serialize directives — skip if a matching change is already running
        if serialize_triggers and _is_serialized(name, state, serialize_triggers):
            logger.info("Serialize directive: deferring %s (matching change already running)", name)
            continue

        dispatch_change(
            state_path, name,
            default_model=default_model,
            model_routing=model_routing,
            team_mode=team_mode,
            context_pruning=context_pruning,
            event_bus=event_bus,
            input_mode=input_mode,
            input_path=input_path,
            digest_dir=digest_dir,
            design_snapshot_dir=design_snapshot_dir,
        )
        running += 1
        dispatched += 1

        # Re-read state after each dispatch to catch concurrent changes
        state = load_state(state_path)

    return dispatched


# ─── Lifecycle Management ────────────────────────────────────────────


def pause_change(
    state_path: str,
    change_name: str,
    event_bus: EventBus | None = None,
) -> bool:
    """Send SIGTERM to Ralph and set status to paused.

    Migrated from: dispatcher.sh pause_change() L725-747

    Returns True if pause signal sent.
    """
    state = load_state(state_path)
    change = _find_change(state, change_name)
    if not change or not change.worktree_path:
        logger.warning("no worktree found for %s", change_name)
        return False

    pid_file = os.path.join(change.worktree_path, ".set", "ralph-terminal.pid")
    if os.path.isfile(pid_file):
        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
            result = check_pid(pid, "set-loop")
            if result.alive and result.match:
                os.kill(pid, 15)  # SIGTERM
                logger.info("paused %s (SIGTERM to PID %d)", change_name, pid)
        except (ValueError, OSError):
            pass

    update_change_field(state_path, change_name, "status", "paused", event_bus=event_bus)
    return True


def resume_change(
    state_path: str,
    change_name: str,
    default_model: str = "opus",
    model_routing: str = "off",
    team_mode: bool = False,
    event_bus: EventBus | None = None,
) -> bool:
    """Resume a paused/stopped change with token snapshot.

    Migrated from: dispatcher.sh resume_change() L749-854

    Returns True if set-loop restarted successfully.
    """
    state = load_state(state_path)
    change = _find_change(state, change_name)
    if not change or not change.worktree_path or not os.path.isdir(change.worktree_path):
        logger.error("worktree not found for %s", change_name)
        return False

    wt_path = change.worktree_path
    logger.info("resuming %s in %s", change_name, wt_path)

    # Guard: kill any existing set-loop before starting a new one
    _kill_existing_wt_loop(wt_path, change_name)

    # Store watchdog progress baseline
    loop_state_path = os.path.join(wt_path, ".set", "loop-state.json")
    if os.path.isfile(loop_state_path):
        try:
            with open(loop_state_path) as f:
                ls = json.load(f)
            iters = ls.get("iterations", [])
            iter_count = len(iters) if isinstance(iters, list) else 0
            with locked_state(state_path) as st:
                ch = _find_change(st, change_name)
                if ch:
                    if not ch.watchdog:
                        ch.watchdog = WatchdogState()
                    ch.watchdog.progress_baseline = iter_count
            logger.info("set watchdog progress_baseline=%d for %s", iter_count, change_name)
        except (json.JSONDecodeError, OSError):
            pass

    # Reset merge retry counter — agent redispatch gets fresh retry budget
    with locked_state(state_path) as st:
        ch = _find_change(st, change_name)
        if ch and ch.extras.get("merge_retry_count"):
            ch.extras["merge_retry_count"] = 0

    # Snapshot cumulative tokens
    update_change_field(state_path, change_name, "tokens_used_prev", change.tokens_used, event_bus=event_bus)
    update_change_field(state_path, change_name, "input_tokens_prev", change.input_tokens, event_bus=event_bus)
    update_change_field(state_path, change_name, "output_tokens_prev", change.output_tokens, event_bus=event_bus)
    update_change_field(state_path, change_name, "cache_read_tokens_prev", change.cache_read_tokens, event_bus=event_bus)
    update_change_field(state_path, change_name, "cache_create_tokens_prev", change.cache_create_tokens, event_bus=event_bus)

    # Determine task description and done criteria
    retry_ctx = change.extras.get("retry_context") or ""
    task_desc: str
    done_criteria: str
    max_iter: int

    if retry_ctx:
        task_desc = retry_ctx
        logger.info("resuming %s with retry context (%d chars)", change_name, len(retry_ctx))
        update_change_field(state_path, change_name, "retry_context", None, event_bus=event_bus)

        is_merge_retry = change.extras.get("merge_rebase_pending", False)
        is_review_retry = "REVIEW FEEDBACK" in retry_ctx or "review" in retry_ctx.lower()[:50]
        if is_merge_retry:
            done_criteria = "merge"
            max_iter = 5
        elif is_review_retry:
            done_criteria = "test"
            max_iter = 5  # review fixes need more iterations (fix + re-test)
        else:
            done_criteria = "test"
            max_iter = 3
    else:
        task_desc = f"Continue {change_name}: {change.scope[:200]}"
        done_criteria = "openspec"
        max_iter = 30

    impl_model = resolve_change_model(change, default_model, model_routing)
    # Persist resolved model so verifier uses correct context window size
    update_change_field(state_path, change_name, "model", impl_model)

    # Resolve test command for done=test criteria
    test_command = ""
    if done_criteria == "test":
        state = load_state(state_path)
        test_command = state.extras.get("directives", {}).get("test_command", "")
        if not test_command:
            from .config import auto_detect_test_command
            test_command = auto_detect_test_command(wt_path)

    cmd = [
        "set-loop", "start", task_desc,
        "--max", str(max_iter),
        "--done", done_criteria,
        "--label", change_name,
        "--model", impl_model,
        "--change", change_name,
    ]
    if test_command:
        cmd.extend(["--test-command", test_command])
    if team_mode:
        cmd.append("--team")

    logger.info(
        "resume %s with model=%s (done=%s, max=%d) team=%s",
        change_name, impl_model, done_criteria, max_iter, team_mode,
    )

    # Start set-loop
    r = run_command(cmd, cwd=wt_path, timeout=30)

    # Verify startup
    loop_state_file = os.path.join(wt_path, ".set", "loop-state.json")
    retries = 0
    while not os.path.isfile(loop_state_file) and retries < 10:
        time.sleep(1)
        retries += 1

    if not os.path.isfile(loop_state_file):
        logger.error("set-loop failed to resume for %s", change_name)
        if event_bus:
            event_bus.emit("ERROR", change=change_name, data={"error": "set-loop failed to resume"})
        update_change_field(state_path, change_name, "status", "failed", event_bus=event_bus)
        return False

    terminal_pid = 0
    try:
        with open(loop_state_file) as f:
            ls = json.load(f)
        terminal_pid = int(ls.get("terminal_pid") or 0)
    except (json.JSONDecodeError, OSError, ValueError):
        pass

    update_change_field(state_path, change_name, "ralph_pid", terminal_pid, event_bus=event_bus)
    update_change_field(state_path, change_name, "status", "running", event_bus=event_bus)
    return True


def resume_stopped_changes(
    state_path: str,
    event_bus: EventBus | None = None,
    **resume_kwargs: Any,
) -> int:
    """Resume changes that were running when orchestrator was interrupted.

    Migrated from: dispatcher.sh resume_stopped_changes() L644-661

    Returns number of changes resumed.
    """
    state = load_state(state_path)
    resumed = 0

    for change in state.changes:
        if change.status != "stopped":
            continue
        if change.worktree_path and os.path.isdir(change.worktree_path):
            logger.info("resuming stopped change: %s", change.name)
            resume_change(state_path, change.name, event_bus=event_bus, **resume_kwargs)
            resumed += 1
        else:
            logger.info("resetting stopped change %s to pending (worktree missing)", change.name)
            update_change_field(state_path, change.name, "status", "pending", event_bus=event_bus)

    return resumed


def resume_stalled_changes(
    state_path: str,
    event_bus: EventBus | None = None,
    **resume_kwargs: Any,
) -> int:
    """Resume stalled changes after cooldown period.

    Migrated from: dispatcher.sh resume_stalled_changes() L858-874

    Returns number of changes resumed.
    """
    now = int(time.time())
    state = load_state(state_path)
    resumed = 0

    for change in state.changes:
        if change.status != "stalled":
            continue
        stalled_at = change.extras.get("stalled_at", 0)
        cooldown = now - stalled_at
        if cooldown >= STALL_COOLDOWN_SECONDS:
            logger.info("resuming stalled change %s after %ds cooldown", change.name, cooldown)
            resume_change(state_path, change.name, event_bus=event_bus, **resume_kwargs)
            resumed += 1

    return resumed
