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
from datetime import datetime, timezone
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
from .subprocess_utils import CommandResult, detect_default_branch, run_command, run_git
from .truncate import smart_truncate_structured, truncate_with_budget

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
        logger.debug("_build_rule_injection: rules_dir missing: %s", rules_dir)
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
        logger.debug("_build_rule_injection: no keyword matches in scope for %d categories", len(mapping))
        return ""

    seen: set[str] = set()
    rule_items: list[tuple[str, str]] = []
    for glob_pat in matched_globs:
        # glob_pat is relative, e.g. "web/auth-middleware.md"
        full_path = os.path.join(rules_dir, glob_pat)
        if full_path in seen or not os.path.isfile(full_path):
            continue
        seen.add(full_path)
        try:
            content = open(full_path).read()
        except OSError:
            logger.debug("_build_rule_injection: unreadable rule file: %s", full_path)
            continue
        # Strip YAML frontmatter if present
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                content = content[end + 3:].strip()
        rule_items.append((os.path.basename(full_path), content))

    if not rule_items:
        logger.debug("_build_rule_injection: no rule content loaded from %d matched globs", len(matched_globs))
        return ""

    included, omitted = truncate_with_budget(rule_items, 4000)
    parts = [content for _, content in included]
    if omitted:
        parts.append(f"\n({len(omitted)} rules omitted for space: {', '.join(omitted)})")

    return "## Relevant Patterns\n\n" + "\n\n".join(parts)


def _deploy_v0_export_to_worktree(project_path: str, wt_path: str) -> bool:
    """Create a symlink <wt>/v0-export -> <project>/v0-export.

    Agents get the full v0 design source as a reference tree inside the
    worktree. The symlink points to the project root's v0-export so
    updates to the design (e.g., a v2 orchestration run that imports a
    newer v0 export) propagate to all worktrees without re-deployment.

    Returns True if the deploy succeeded or was already in place.
    Returns False if v0-export/ is absent at the project root (non-v0
    project — caller is a no-op).
    """
    from pathlib import Path

    src = Path(project_path) / "v0-export"
    if not src.is_dir():
        return False

    dst = Path(wt_path) / "v0-export"
    if dst.is_symlink():
        return True
    if dst.exists():
        logger.warning(
            "worktree has a non-symlink v0-export at %s; skipping deploy", dst,
        )
        return True

    try:
        # Absolute symlink — simplest correct behavior; the worktree is
        # always local to this machine. If portability becomes an issue
        # we can switch to a relative path.
        dst.symlink_to(src.resolve(), target_is_directory=True)
        logger.info("deployed v0-export symlink: %s -> %s", dst, src)
        return True
    except OSError:
        logger.error(
            "failed to create v0-export symlink %s -> %s", dst, src, exc_info=True,
        )
        return False


def _build_resume_preamble(change_name: str, wt_path: str) -> str:
    """Build context restoration preamble for resume_change.

    Lists files the agent should re-read to refresh design/conventions/tests
    context that may have been lost from the conversation history during
    long-running sessions or claude --resume compaction.
    """
    file_list = []
    n = 1

    input_md = f"openspec/changes/{change_name}/input.md"
    if os.path.isfile(os.path.join(wt_path, input_md)):
        file_list.append(f"{n}. `{input_md}` — original task scope, requirements, design context")
        n += 1

    design_md = f"openspec/changes/{change_name}/design.md"
    if os.path.isfile(os.path.join(wt_path, design_md)):
        file_list.append(f"{n}. `{design_md}` — design tokens and Figma source code")
        n += 1

    skeleton_spec = f"tests/e2e/{change_name}.spec.ts"
    if os.path.isfile(os.path.join(wt_path, skeleton_spec)):
        file_list.append(
            f"{n}. `{skeleton_spec}` — test skeleton (fill bodies, do NOT recreate structure)"
        )
        n += 1

    rules_dir = os.path.join(wt_path, ".claude", "rules")
    if os.path.isdir(rules_dir):
        try:
            convention_files = sorted(
                f for f in os.listdir(rules_dir) if f.endswith("-conventions.md")
            )
        except OSError:
            convention_files = []
        if convention_files:
            file_list.append(
                f"{n}. `.claude/rules/{convention_files[0]}` — project conventions (UI library, styling)"
            )

    if not file_list:
        return ""

    parts = [
        "## Context Restoration",
        "",
        "Before fixing the issue below, RE-READ these files to refresh your context:",
        "",
        *file_list,
        "",
        "**Key reminders:**",
        "- Use EXACT design tokens from design.md — do NOT fall back to shadcn defaults",
        "- Follow the Figma source code structure for components (sidebar, layout, colors)",
        "- Keep the test skeleton structure intact — only fill in test bodies",
        "",
        "## Fix Required",
    ]
    return "\n".join(parts)


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
        logger.debug("_reinstall_deps_if_needed: sha unchanged or invalid")
        return
    diff_r = run_git("diff", "--name-only", f"{old_sha}..{new_sha}", cwd=wt_path)
    if diff_r.exit_code != 0:
        logger.debug("_reinstall_deps_if_needed: sha unchanged or invalid")
        return
    changed = set(diff_r.stdout.strip().splitlines())
    if not changed.intersection(_LOCKFILE_NAMES):
        logger.debug("_reinstall_deps_if_needed: no lockfile changes detected")
        return
    pm = _detect_package_manager(wt_path)
    if not pm:
        logger.debug("_reinstall_deps_if_needed: no package manager detected in %s", wt_path)
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
    main_branch = detect_default_branch(wt_path)
    r = run_git("show-ref", "--verify", "--quiet", f"refs/heads/{main_branch}", cwd=wt_path)
    if r.exit_code != 0:
        logger.info("sync: no %s branch for %s — skipping (first change?)", main_branch, change_name)
        return SyncResult(ok=True, message="no main branch — first change")

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


def _merge_e2e_manifest(
    existing: dict | None,
    change_name: str,
    change_reqs: list[str],
) -> dict:
    """Merge a dispatch's REQs into an existing e2e manifest payload.

    Cumulative semantics: the worktree was just branched from main, so any
    existing manifest on disk reflects prior merged changes' REQ
    coverage. We MERGE the current change's REQs rather than overwrite —
    otherwise every dispatch wipes the cumulative REQ list and downstream
    tooling (review gate, spec-verify, harvesters) reads a broken history.
    verifier.py only updates `spec_files` afterwards, so we don't need to
    track new spec files here beyond the change's own.

    Pure function — accepts a parsed dict (or None) and returns the merged
    dict. Callers handle the file I/O.
    """
    if not isinstance(existing, dict):
        existing = {}

    prior_reqs = existing.get("requirements") or []
    if not isinstance(prior_reqs, list):
        prior_reqs = []
    # Historic manifests stored requirements as `[{"id": ..., ...}, ...]`;
    # the current schema stores `["REQ-X-001", ...]`. Normalize before
    # dedup — dict.fromkeys on mixed types raises TypeError: unhashable
    # type 'dict' and blocks dispatch (observed on
    # craftbrew-run-20260421-0025: foundation-setup merged a dict-shape
    # manifest into main, next dispatch for email-dispatch-library
    # raised at the merge and the change got stuck in `dispatched`).
    def _req_id(r):
        if isinstance(r, dict):
            return r.get("id") or r.get("req_id") or ""
        return str(r) if r else ""
    normalized_prior = [rid for rid in (_req_id(r) for r in prior_reqs) if rid]
    normalized_new = [rid for rid in (_req_id(r) for r in change_reqs) if rid]
    merged_reqs = list(dict.fromkeys(normalized_prior + normalized_new))

    prior_spec_files = existing.get("spec_files") or []
    if not isinstance(prior_spec_files, list):
        prior_spec_files = []
    own_spec = f"tests/e2e/{change_name}.spec.ts"
    merged_specs = list(dict.fromkeys(list(prior_spec_files) + [own_spec]))

    prior_by_change = existing.get("requirements_by_change") or {}
    if not isinstance(prior_by_change, dict):
        prior_by_change = {}
    else:
        prior_by_change = dict(prior_by_change)  # don't mutate caller's dict
    prior_by_change[change_name] = list(change_reqs)

    return {
        "change": change_name,
        "spec_files": merged_specs,
        "requirements": merged_reqs,
        "requirements_by_change": prior_by_change,
    }


def _write_e2e_manifest(wt_path: str, change_name: str, change_reqs: list[str]) -> None:
    """Read existing manifest (if any), merge in current change, write back."""
    from .paths import LineagePaths
    manifest_path = LineagePaths.e2e_manifest_for_worktree(wt_path)
    existing: dict = {}
    if os.path.isfile(manifest_path):
        try:
            existing = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except (json.JSONDecodeError, OSError):
            existing = {}

    prior_req_count = len(existing.get("requirements") or [])
    manifest_data = _merge_e2e_manifest(existing, change_name, change_reqs)

    try:
        with open(manifest_path, "w") as mf:
            json.dump(manifest_data, mf, indent=2)
        logger.info(
            "Wrote per-worktree e2e manifest for %s: %d spec files, %d "
            "requirements (own=%d, prior=%d)",
            change_name,
            len(manifest_data["spec_files"]),
            len(manifest_data["requirements"]),
            len(change_reqs),
            prior_req_count,
        )
    except OSError:
        logger.debug("Failed to write per-worktree e2e manifest (non-fatal)")


def bootstrap_worktree(project_path: str, wt_path: str, change_name: str = "") -> int:
    """Copy .env files, inject port, and install deps in a worktree.

    Migrated from: dispatcher.sh bootstrap_worktree() L86-116

    Returns number of env files copied.
    """
    if not os.path.isdir(wt_path):
        logger.debug("copy_env_files: wt_path missing: %s", wt_path)
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
        logger.debug("prune_worktree_context: .claude dir missing in %s", wt_path)
        return 0

    cmd_dir = os.path.join(wt_path, ".claude", "commands", "wt")
    if not os.path.isdir(cmd_dir):
        logger.debug("prune_worktree_context: commands/wt dir missing in %s", wt_path)
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


# ─── Startup File ────────────────────────────────────────────────────


def _write_startup_file(project_path: str) -> bool:
    """Generate START.md via profile and write to project root.

    Delegates to profile.generate_startup_file(). Always overwrites
    (content is auto-generated). Returns True if written, False if skipped.
    """
    try:
        from .profile_loader import load_profile, NullProfile
        profile = load_profile()
        if isinstance(profile, NullProfile):
            return False
        content = profile.generate_startup_file(project_path)
        if not content:
            return False
        start_md = os.path.join(project_path, "START.md")
        Path(start_md).write_text(content, encoding="utf-8")
        logger.info("Generated START.md in %s", project_path)
        return True
    except Exception:
        logger.debug("Failed to generate START.md (non-critical)", exc_info=True)
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
        # Guard: sonnet only for safe change types (doc, infrastructure, cleanup)
        # Feature changes should use opus unless they only have test-fill tasks
        if explicit_model == "sonnet" and not is_doc:
            change_type = getattr(change, "change_type", "") or ""
            if change_type in ("feature",):
                logger.warning(
                    "overriding planner model=sonnet → opus for feature change '%s'",
                    change.name,
                )
                return "opus"
            # Allow sonnet for infrastructure, cleanup, foundational
            logger.info(
                "allowing planner model=sonnet for %s (type=%s)",
                change.name, change_type,
            )
        return explicit_model

    # 2. Complexity-based routing
    if model_routing == "complexity":
        if change.complexity == "S" and change.change_type != "feature":
            logger.info("model routing: %s → sonnet (S-complexity, type=%s)", change.name, change.change_type)
            return "sonnet"
        if change.complexity == "S" and change.change_type == "infrastructure":
            return "sonnet"
        if is_doc:
            return "sonnet"

    # 3. Default — doc changes always sonnet
    if is_doc:
        return "sonnet"

    return default_model


# ─── Recovery ────────────────────────────────────────────────────────


def _cleanup_stale_change_artifacts(project_dir: str, change_name: str) -> None:
    """Remove the `change/<name>` branch + its worktree if 0 commits ahead of main.

    Called from `recover_orphaned_changes` Case 2 (orphan without recorded
    worktree_path). A crashed dispatch can leave a worktree+branch on disk
    that state.json doesn't know about; without cleanup the next dispatch
    hits `_unique_worktree_name`'s collision-suffix path and produces a `-N`
    pair that the merger's hardcoded branch lookup can't see — the root of
    the craftbrew-run-20260421-0025 ghost-merge bug.

    Preserves branches with committed work (>0 commits ahead) — those are
    the legitimate redispatch-resume case, handled elsewhere.
    """
    stale_branch = f"change/{change_name}"
    br_check = run_git(
        "rev-parse", "--verify", stale_branch,
        cwd=project_dir, best_effort=True,
    )
    if br_check.exit_code != 0:
        return  # no stale branch — nothing to clean

    main_branch = detect_default_branch(project_dir)
    ahead_r = run_git(
        "rev-list", "--count", f"{main_branch}..{stale_branch}",
        cwd=project_dir, best_effort=True,
    )
    try:
        ahead = int(ahead_r.stdout.strip() or "0") if ahead_r.exit_code == 0 else 0
    except ValueError:
        ahead = 0

    if ahead > 0:
        logger.warning(
            "recovery: stale branch %s has %d commits ahead of %s — preserving "
            "(next dispatch will use -N suffix)",
            stale_branch, ahead, main_branch,
        )
        return

    # Find the worktree registered against this branch
    stale_wt_path = ""
    wt_list_r = run_git("worktree", "list", "--porcelain", cwd=project_dir)
    if wt_list_r.exit_code == 0:
        last_wt = ""
        for line in wt_list_r.stdout.splitlines():
            if line.startswith("worktree "):
                last_wt = line[len("worktree "):]
            elif line == f"branch refs/heads/{stale_branch}":
                stale_wt_path = last_wt
                break

    if stale_wt_path and os.path.isdir(stale_wt_path):
        rm_r = run_git(
            "worktree", "remove", "--force", stale_wt_path,
            cwd=project_dir, best_effort=True,
        )
        if rm_r.exit_code != 0:
            logger.warning(
                "recovery: `git worktree remove` failed for %s (%s) — falling back to rmtree",
                stale_wt_path, rm_r.stderr.strip()[:200],
            )
            shutil.rmtree(stale_wt_path, ignore_errors=True)
            run_git("worktree", "prune", cwd=project_dir, best_effort=True)
        logger.info(
            "recovery: removed stale worktree %s (branch=%s, 0 commits ahead)",
            stale_wt_path, stale_branch,
        )

    del_r = run_git("branch", "-D", stale_branch, cwd=project_dir, best_effort=True)
    if del_r.exit_code == 0:
        logger.info(
            "recovery: deleted stale empty branch %s (0 commits ahead of %s)",
            stale_branch, main_branch,
        )
    else:
        logger.warning(
            "recovery: failed to delete stale branch %s: %s",
            stale_branch, del_r.stderr.strip()[:200],
        )


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
        # `dispatched` is the post-bootstrap / pre-running state: the
        # engine has created the worktree and written input.md, but
        # hasn't observed the ralph spawn yet. If dispatch raised an
        # exception between those steps (e.g. dict-shape reqs in the
        # e2e manifest on craftbrew-run-20260421-0025), the change
        # gets stranded there and no further recovery fires. Treat it
        # like `running` for reconciliation so orphaned dispatches
        # can be reset to pending and re-tried.
        if change.status not in ("running", "verifying", "stalled", "dispatched"):
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
            # Poisoned-context signal: the agent we're reconciling died. F5's
            # guard in resume_change keys off stall_reason to decide whether
            # to reuse the session_id. Without this marker, a silent orphan
            # recovery path (crash between poll_active's stall-write and the
            # recovery) would skip F5 entirely and rehydrate the same poisoned
            # session.
            update_change_field(
                state_path, change.name, "stall_reason",
                f"dead_running_agent_orphan_{reason}",
                event_bus=event_bus,
            )
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
        # Clean up any stale worktree+branch the crashed dispatch left on disk
        # but didn't persist in state. Without this, _unique_worktree_name sees
        # the orphan branch, generates `-N`, and the merger's hardcoded
        # `change/<name>` lookup fires Case 2 "already merged" on the empty
        # original branch — silently discarding the agent's work. Observed in
        # craftbrew-run-20260421-0025 (email-dispatch-library ghost merge).
        _cleanup_stale_change_artifacts(os.path.dirname(state_path), change.name)
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
            except (json.JSONDecodeError, OSError) as e:
                logger.debug("Could not read loop-state for iter_count: %s", e)

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
            f"Build output:\n{smart_truncate_structured(build_output, 2000, head_ratio=0.7)}\n\n"
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
    branch_exists = run_git("rev-parse", "--verify", branch, cwd=project_path, best_effort=True).exit_code == 0
    dir_exists = os.path.isdir(wt_dir)

    if not branch_exists and not dir_exists:
        return change_name  # no collision

    # Append numeric suffix to find a free name
    for i in range(2, 100):
        candidate = f"{change_name}-{i}"
        branch = f"change/{candidate}"
        wt_dir = f"{project_path}-{candidate}"
        branch_exists = run_git("rev-parse", "--verify", branch, cwd=project_path, best_effort=True).exit_code == 0
        dir_exists = os.path.isdir(wt_dir)
        if not branch_exists and not dir_exists:
            logger.info("change name collision: %s exists, using %s", change_name, candidate)
            return candidate

    logger.error("could not find unique name for %s after 98 attempts", change_name)
    return change_name  # fallback to original


def _find_existing_worktree(project_path: str, change_name: str) -> str:
    """Find existing worktree path for a change.

    Matches basenames EXACTLY against both naming conventions:
    - `{project}-{change}` (Python direct `git worktree add`)
    - `{project}-wt-{change}` (bash `set-new` default)
    Plus their numeric-suffix variants (`-2`, `-3`, ...).

    When multiple candidates match (collision-suffix leftovers), the
    highest-numbered suffix wins — this is the most recently created
    worktree and almost always the live one. Stale unsuffixed leftovers
    from a failed reset-without-cleanup would be older.

    Returns the conventional path `{project}-{change}` when no worktree
    matches, matching the prior behavior of callers that use the return
    value as a would-be path for a fresh `git worktree add`.
    """
    project_name = os.path.basename(project_path.rstrip("/"))

    # Collect candidates: (suffix_rank, path). suffix=0 means unsuffixed.
    candidates: list[tuple[int, str]] = []
    r = run_git("worktree", "list", "--porcelain", cwd=project_path, best_effort=True)
    if r.exit_code == 0:
        for line in r.stdout.splitlines():
            if not line.startswith("worktree "):
                continue
            wt_path = line.split(" ", 1)[1].strip()
            basename = os.path.basename(wt_path)
            rank = _match_worktree_basename(basename, project_name, change_name)
            if rank is not None:
                candidates.append((rank, wt_path))

    if not candidates:
        # No git-registered worktree matches; return the conventional
        # would-be path so the caller can treat this as "does not exist
        # yet" via a downstream os.path.isdir check.
        return f"{project_path}-{change_name}"

    if len(candidates) > 1:
        logger.debug(
            "_find_existing_worktree: %d candidates for %s: %s",
            len(candidates), change_name,
            [(r_, p) for r_, p in candidates],
        )

    # Highest suffix wins (max by rank). Tie-break on rank collision (e.g.
    # mixed-convention rank-0: both `{project}-wt-{name}` and `{project}-{name}`
    # at rank 0): prefer the `-wt-` convention because `set-new` creates it
    # by default — plain-convention paths are less-common direct-add leftovers.
    wt_prefix = f"{project_name}-wt-"

    def _sort_key(pair: tuple[int, str]) -> tuple[int, int]:
        rank, path = pair
        basename = os.path.basename(path)
        tiebreak = 1 if basename.startswith(wt_prefix) else 0
        return (rank, tiebreak)

    candidates.sort(key=_sort_key, reverse=True)
    return candidates[0][1]


def _match_worktree_basename(
    basename: str, project_name: str, change_name: str,
) -> int | None:
    """Return suffix rank if `basename` matches the change, else None.

    Matches exactly against four pattern families:
    - `{project}-{change}`            → rank 0
    - `{project}-{change}-N`          → rank N
    - `{project}-wt-{change}`         → rank 0
    - `{project}-wt-{change}-N`       → rank N

    The caller adds project-prefix-free patterns separately if needed.
    """
    for prefix in (f"{project_name}-wt-", f"{project_name}-"):
        if not basename.startswith(prefix):
            continue
        tail = basename[len(prefix):]
        if tail == change_name:
            return 0
        if tail.startswith(f"{change_name}-"):
            suffix = tail[len(change_name) + 1:]
            if suffix.isdigit():
                return int(suffix)
    return None


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
        logger.debug("_build_conventions_summary: conventions.json missing in %s", digest_dir)
        return ""
    try:
        with open(conv_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.debug("_build_conventions_summary: failed to parse conventions.json in %s", digest_dir)
        return ""

    categories = data.get("categories", [])
    if not categories:
        logger.debug("_build_conventions_summary: no categories in conventions.json")
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
        logger.debug("_detect_i18n_sidecar: package.json missing in %s", wt_path)
        return ""
    try:
        with open(pkg_path) as f:
            pkg = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.debug("_detect_i18n_sidecar: failed to parse package.json in %s", wt_path)
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
        logger.debug("_detect_i18n_sidecar: no i18n lib found in %s", wt_path)
        return ""

    # Detect messages directory
    msg_dirs = ["src/messages", "messages", "src/i18n/messages", "public/locales"]
    msg_dir = ""
    for d in msg_dirs:
        if os.path.isdir(os.path.join(wt_path, d)):
            msg_dir = d
            break

    if not msg_dir:
        logger.debug("_detect_i18n_sidecar: no message dir found in %s", wt_path)
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


_LEARNINGS_SECTION_MARKER = "<!-- AUTOREFRESH:review-learnings -->"
_LEARNINGS_SECTION_END = "<!-- /AUTOREFRESH:review-learnings -->"


def _learnings_file_path(project_path: str) -> str:
    from .paths import LineagePaths
    return LineagePaths(project_path).review_learnings


def _render_learnings_section(project_path: str) -> str:
    """Render a bounded review-learnings checklist block for injection.

    Returns the block body WITHOUT surrounding blank-line separators — the
    caller is responsible for concatenation. This keeps repeated refreshes
    idempotent: the same input yields byte-identical output.
    """
    try:
        from .profile_loader import load_profile

        profile = load_profile()
        checklist = profile.review_learnings_checklist(project_path) or ""
    except Exception:
        return ""
    if not checklist.strip():
        return ""
    lines = [ln for ln in checklist.splitlines() if ln.startswith("- ")]
    if not lines:
        return ""
    body = "\n".join(lines[:30])
    return (
        f"{_LEARNINGS_SECTION_MARKER}\n"
        "## Current Review Learnings\n"
        "Patterns surfaced by prior merged changes. Check each against your diff:\n"
        f"{body}\n"
        f"{_LEARNINGS_SECTION_END}\n"
    )


def _replace_learnings_section(content: str, new_section: str) -> str:
    """Replace any prior AUTOREFRESH learnings block with `new_section`.

    If no prior block exists and `new_section` is non-empty, append it with
    a single blank-line separator. Repeated calls are idempotent — the same
    input yields the same output.
    """
    start = content.find(_LEARNINGS_SECTION_MARKER)
    if start != -1:
        end = content.find(_LEARNINGS_SECTION_END, start)
        if end != -1:
            end_after = end + len(_LEARNINGS_SECTION_END)
            prefix = content[:start].rstrip("\n")
            suffix = content[end_after:].lstrip("\n")
            if not new_section:
                merged = prefix + "\n"
                if suffix:
                    merged += "\n" + suffix
                return merged
            merged = prefix + "\n\n" + new_section
            if suffix:
                merged = merged.rstrip("\n") + "\n\n" + suffix
            return merged
    if not new_section:
        return content
    base = content.rstrip("\n")
    return base + "\n\n" + new_section


def _learnings_refresh_directive(project_path: str) -> bool:
    """Return False if the operator disabled learnings refresh via directive.

    Reads the resolver's directives file directly — we cannot import
    the parsed Directives here because the dispatcher is called from
    contexts that don't have an orchestration state yet. Failure to read
    the directives file defaults to enabled (the spec default).
    """
    from .paths import LineagePaths
    path = LineagePaths(project_path).directives_file
    if not os.path.isfile(path):
        return True
    try:
        with open(path) as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return True
    val = raw.get("refresh_input_on_learnings_update", True)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() not in ("0", "false", "no", "off")
    return True


def _maybe_refresh_input_md(
    change_name: str,
    wt_path: str,
    project_path: str,
) -> bool:
    """Regenerate the learnings section of input.md when newer learnings exist.

    Returns True if input.md was rewritten, False otherwise. Non-blocking:
    any failure logs a WARNING and returns False — the ralph loop must
    never crash because of a refresh hiccup.
    """
    if not _learnings_refresh_directive(project_path):
        logger.debug(
            "Input refresh skipped for %s — directive refresh_input_on_learnings_update is False",
            change_name,
        )
        return False

    input_md_path = os.path.join(
        wt_path, "openspec", "changes", change_name, "input.md"
    )
    if not os.path.isfile(input_md_path):
        return False

    learnings_path = _learnings_file_path(project_path)
    if not os.path.isfile(learnings_path):
        return False

    try:
        input_mtime = os.path.getmtime(input_md_path)
        learnings_mtime = os.path.getmtime(learnings_path)
    except OSError as exc:
        logger.warning(
            "Input refresh mtime check failed for %s: %s", change_name, exc
        )
        return False

    if learnings_mtime <= input_mtime:
        logger.debug(
            "Input refresh skipped for %s — learnings not newer "
            "(learnings=%.0f, input=%.0f)",
            change_name, learnings_mtime, input_mtime,
        )
        return False

    try:
        content = open(input_md_path).read()
        new_section = _render_learnings_section(project_path)
        updated = _replace_learnings_section(content, new_section)
        if updated == content:
            # No-op: section was already up to date (e.g. learnings file
            # touched but content unchanged). Touch the input.md so the
            # next mtime compare skips cleanly.
            os.utime(input_md_path, None)
            return False
        tmp_path = input_md_path + ".tmp"
        with open(tmp_path, "w") as f:
            f.write(updated)
        os.replace(tmp_path, input_md_path)
        logger.info(
            "Input refresh for %s — learnings mtime %.0f > input mtime %.0f",
            change_name, learnings_mtime, input_mtime,
        )
        return True
    except OSError as exc:
        logger.warning(
            "Input refresh rewrite failed for %s: %s", change_name, exc
        )
        return False


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

    # Post-process scope: if test plan entries exist, remove narrative E2E
    # descriptions to prevent conflict with the structured Required Tests section
    _test_plan_entries = None
    if digest_dir and change_requirements:
        _test_plan_entries = _load_test_plan(digest_dir, change_requirements)
        if _test_plan_entries:
            import re as _re
            # Match common E2E narrative patterns in planner scope:
            #   "E2E: cold-visit loads homepage..."
            #   "E2E tests/e2e/cart.spec.ts — cold-visit, add product..."
            #   "Tests: tests/e2e/smoke.spec.ts..."
            _new_scope = _re.sub(
                r'(?:E2E[:\s]|Tests?[:\s]).*?tests/e2e/\S+.*?(?=\n\n|\n[A-Z]|\Z)',
                'E2E: See "Required Tests" section below for the authoritative test list.',
                scope,
                flags=_re.DOTALL,
            )
            if _new_scope == scope:
                # Try simpler pattern: "E2E:..." on a single line
                _new_scope = _re.sub(
                    r'E2E:.*?(?=\n\n|\n[A-Z]|\Z)',
                    'E2E: See "Required Tests" section below for the authoritative test list.',
                    scope,
                    flags=_re.DOTALL,
                )
            if _new_scope == scope:
                logger.debug(
                    "Scope E2E post-processing: no narrative E2E pattern for %s "
                    "(test plan has %d entries — Required Tests section will be appended)",
                    change_name, len(_test_plan_entries),
                )
            else:
                logger.info(
                    "Scope E2E post-processing: replaced narrative for %s with Required Tests pointer",
                    change_name,
                )
            scope = _new_scope
            # Strip any remaining tests/e2e/*.spec.ts references that could
            # mislead the agent into writing fewer tests than Required Tests demands
            scope = _re.sub(
                r'tests/e2e/\S+\.spec\.ts\S*',
                '',
                scope,
            )

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
                for i, ac in enumerate(ac_items, 1):
                    req_lines.append(f"  - {rid}:AC-{i}: {ac}")
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

    # Required Tests section (from generated test-plan.json)
    # Use pre-loaded entries from scope post-processing if available
    test_plan_entries = _test_plan_entries
    if test_plan_entries is None and digest_dir and change_requirements:
        test_plan_entries = _load_test_plan(digest_dir, change_requirements)
    if test_plan_entries:
        logger.info(
            "Required Tests injected for %s: %d entries from test plan",
            change_name, len(test_plan_entries),
        )
        _threshold_pct = 80  # default; configurable via e2e_coverage_threshold directive
        _skeleton_note = (
            f"\n**A test skeleton has been pre-generated at `tests/e2e/{change_name}.spec.ts`** "
            f"with {len(test_plan_entries)} test blocks marked `// TODO: implement`. "
            f"Fill in the test bodies — do NOT delete or rename test blocks.\n"
        )
        lines.append(
            f"\n## Required Tests (MANDATORY — coverage gate will block if incomplete)\n"
            f"{_skeleton_note}"
            f"Each test block is prefixed with an AC-ID (e.g., `REQ-HOME-001:AC-1`). "
            f"Do NOT rename or remove the AC-ID prefix — it enables coverage tracking.\n"
            "Tag SMOKE tests with: "
            "`test('REQ-HOME-001: ...', { tag: '@smoke' }, async ({ page }) => { ... })`\n"
            f"Minimum test count: {len(test_plan_entries)} "
            f"(coverage gate blocks below {_threshold_pct}%)."
        )
        for entry in test_plan_entries:
            cats = ", ".join(entry.categories)
            entry_type = getattr(entry, "type", "functional") or "functional"
            tag = "**[SMOKE]**" if entry_type == "smoke" else "**[FUNCTIONAL]**"
            ac_label = getattr(entry, "ac_id", "") or entry.req_id
            lines.append(
                f"- {ac_label}: {entry.scenario_name} [{entry.risk}] "
                f"— {entry.min_tests} test(s) ({cats}) {tag}"
            )
        lines.append(
            f"\nTotal: {len(test_plan_entries)} required test scenarios. "
            f"The integration gate verifies coverage before allowing merge."
        )

    if retry_ctx:
        lines.append(f"\n## Retry Context\n{retry_ctx}")

    return "\n".join(lines) + "\n"


def _load_requirements_lookup(digest_dir: str) -> dict[str, dict]:
    """Load requirements.json from digest dir into a {req_id: req_dict} lookup."""
    if not digest_dir:
        logger.debug("_load_requirements_lookup: digest_dir is empty")
        return {}
    req_path = os.path.join(digest_dir, "requirements.json")
    if not os.path.isfile(req_path):
        logger.debug("_load_requirements_lookup: requirements.json missing in %s", digest_dir)
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


def _rewrite_e2e_tasks(wt_path: str, change_name: str, skeleton_path: str, test_count: int) -> None:
    """Post-process tasks.md to replace narrative E2E tasks with skeleton fill instruction.

    Finds lines referencing tests/e2e/*.spec.ts or E2E test creation and replaces
    them with a single "fill test bodies" task pointing to the skeleton.
    """
    import re as _re
    import glob

    # Find tasks.md in the worktree (could be in openspec/changes/<name>/ or root)
    tasks_candidates = glob.glob(os.path.join(wt_path, "openspec", "changes", "*", "tasks.md"))
    if not tasks_candidates:
        return

    tasks_path = tasks_candidates[0]
    try:
        content = open(tasks_path, encoding="utf-8").read()
    except OSError:
        return

    lines = content.split("\n")
    new_lines = []
    in_e2e_section = False
    e2e_tasks_replaced = False
    skeleton_task_added = False

    for line in lines:
        # Detect E2E section header (e.g., "## 12. E2E Tests")
        if _re.match(r'^## \d+\.\s*E2E\b', line, _re.IGNORECASE):
            in_e2e_section = True
            new_lines.append(line)
            continue

        # Detect next section header (exit E2E section)
        if in_e2e_section and _re.match(r'^## \d+\.', line):
            in_e2e_section = False

        # Replace E2E task lines
        if in_e2e_section and _re.match(r'^- \[ \].*(?:tests/e2e/|spec\.ts|E2E|REQ-)', line, _re.IGNORECASE):
            if not skeleton_task_added:
                spec_basename = os.path.basename(skeleton_path)
                new_lines.append(
                    f"- [ ] Fill test bodies in tests/e2e/{spec_basename} "
                    f"({test_count} test blocks marked // TODO: implement)"
                )
                skeleton_task_added = True
                e2e_tasks_replaced = True
            # Skip original E2E task line
            continue

        new_lines.append(line)

    if e2e_tasks_replaced:
        with open(tasks_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
        logger.info(
            "Rewrote E2E tasks in %s → single skeleton fill task (%d blocks)",
            tasks_path, test_count,
        )


def _load_test_plan(digest_dir: str, change_req_ids: list[str]) -> list:
    """Load test-plan.json and filter entries by change's requirement IDs."""
    if not digest_dir:
        logger.warning("_load_test_plan: digest_dir is empty — agent won't get Required Tests section")
        return []
    plan_path = os.path.join(digest_dir, "test-plan.json")
    if not os.path.isfile(plan_path):
        logger.warning(
            "_load_test_plan: test-plan.json not found at %s — agent won't get Required Tests section",
            plan_path,
        )
        return []
    try:
        from .test_coverage import TestPlan
        with open(plan_path) as f:
            data = json.load(f)
        plan = TestPlan.from_dict(data)
        req_set = set(change_req_ids)
        entries = [e for e in plan.entries if e.req_id in req_set]
        if entries:
            logger.info(
                "Loaded %d test plan entries for change (%d requirements)",
                len(entries), len(req_set),
            )
        else:
            logger.warning(
                "_load_test_plan: 0 entries matched %d requirements (%s) in %s (%d total entries) "
                "— agent won't get Required Tests section",
                len(req_set), list(req_set)[:3], plan_path, len(plan.entries),
            )
        return entries
    except (json.JSONDecodeError, OSError, KeyError):
        logger.warning("_load_test_plan: failed to parse %s", plan_path, exc_info=True)
        return []


def _build_review_learnings(
    findings_path: str, exclude_change: str,
    content_categories: "set[str] | None" = None,
) -> str:
    """Build compact cross-change review learnings from JSONL.

    Reads the review-findings file, excludes the current change's own findings,
    keeps only CRITICAL+HIGH, clusters by keyword, and returns a compact
    markdown section (max ~15 lines).

    When content_categories is provided, filters patterns to those relevant
    to the change scope (plus "general" patterns always included).
    """
    if not os.path.isfile(findings_path):
        logger.debug("_build_review_learnings: findings_path missing: %s", findings_path)
        return ""

    import re as _re
    from .review_clusters import REVIEW_PATTERN_CLUSTERS

    # Build category filter from content_categories if provided.
    # Note: empty set() is treated the same as None — both mean "no
    # category signal, include all entries". This prevents false
    # negatives when classify_diff_content() can't categorize a scope.
    from .profile_types import ProjectType
    _accepted_cats = None
    if content_categories:
        _accepted_cats = content_categories | {"general"}

    def _pattern_matches_categories(text: str) -> bool:
        if _accepted_cats is None:
            return True
        cats = set(ProjectType._assign_categories(text))
        return bool(cats & _accepted_cats)

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
                    if norm and _pattern_matches_categories(norm):
                        pattern_counts.setdefault(norm, set()).add(change)
    except OSError:
        return ""

    if not pattern_counts:
        logger.debug("_build_review_learnings: no patterns found in %s", findings_path)
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
        "idor": "IDOR / missing ownership check",
        "cascade-delete": "Cascade delete / data loss",
        "race-condition": "Race condition / non-atomic operation",
        "missing-validation": "Missing input validation",
        "open-redirect": "Open redirect vulnerability",
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

    from .paths import LineagePaths as _LP_rf
    _findings_rel = os.path.relpath(
        _LP_rf(os.getcwd()).review_findings, os.getcwd()
    )
    return (
        "These patterns caused CRITICAL/HIGH failures in other changes during this run:\n"
        + "\n".join(lines)
        + f"\n\nFull details: `{_findings_rel}`"
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
        logger.debug(
            "_build_pk_context: pk_file=%s, yq=%s — checked candidates: %s",
            pk_file or "not found",
            "available" if shutil.which("yq") else "missing",
            pk_candidates,
        )
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
        logger.debug("_build_pk_context: no feature touches or cross-cutting files found")
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
        logger.debug(
            "_inject_feature_rules: pk_file=%s, yq=%s",
            pk_file or "not found",
            "available" if shutil.which("yq") else "missing",
        )
        return

    rules_dir = os.path.join(wt_path, ".claude", "rules")
    os.makedirs(rules_dir, exist_ok=True)

    names_r = run_command(["yq", "-r", ".features | keys[]? // empty", pk_file], timeout=5)
    if names_r.exit_code != 0 or not names_r.stdout.strip():
        logger.debug("_inject_feature_rules: feature names cmd failed or empty for %s", pk_file)
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

    # Reset per-dispatch retry counters. A change that exhausted its
    # verify/gate/build budget on a prior dispatch (or had its counters
    # persisted across a restart) must start fresh — otherwise the first
    # verify failure trips `retries exhausted` in one iteration.
    # `merge_stall_attempts` is deliberately NOT reset: it is monotonic
    # across re-dispatches to drive the merge-stall circuit-breaker.
    # `ff_retry_count` is reset by `_recover_merge_blocked_safe` on
    # *new* issue resolutions only (engine.py) — leaving it here would
    # double-reset and re-enable the old toggle bug.
    for field in (
        "verify_retry_count", "gate_retry_count", "build_fix_attempt_count",
    ):
        update_change_field(state_path, change_name, field, 0, event_bus=event_bus)

    # Create or reuse worktree
    project_path = os.getcwd()

    # Reset-failed reuse path: if state already tracks a worktree for this
    # change (i.e., engine.reset_failed_changes preserved it), the
    # dispatcher MUST reuse it instead of creating a `-N` collision suffix.
    # Otherwise the agent gets dropped into a fresh worktree and has to
    # `/opsx:ff` every artifact again, burning 80k+ tokens on work it had
    # already committed — the exact bug reset_failed was designed to avoid.
    #
    # Derive wt_name from the preserved path so `-2`/`-3` suffixed worktrees
    # from prior redispatch cycles are honored (the path anchors the branch
    # name as `change/<wt_name>`). Only reuse if BOTH the dir AND the
    # matching branch still exist — otherwise fall through to fresh create.
    preserved_wt = change.worktree_path or ""
    preserved_wt_name = ""
    if preserved_wt:
        expected_prefix = f"{project_path}-"
        if preserved_wt.startswith(expected_prefix):
            preserved_wt_name = preserved_wt[len(expected_prefix):]
            # Worktree dirs created via `set-new` (bash) get a "wt-" prefix in
            # their basename, but the branch they track is `change/{change_name}`
            # without that prefix. Strip the "wt-" to get the branch suffix.
            if preserved_wt_name.startswith("wt-"):
                preserved_wt_name = preserved_wt_name[len("wt-"):]
    preserved_branch_ok = False
    if preserved_wt_name:
        # Try the derived name first, fall back to the change_name for robustness
        # against older worktrees whose dir naming predates current conventions.
        for candidate in (preserved_wt_name, change_name):
            if run_git(
                "rev-parse", "--verify", f"change/{candidate}",
                cwd=project_path, best_effort=True,
            ).exit_code == 0:
                preserved_branch_ok = True
                preserved_wt_name = candidate
                break
    if (
        preserved_wt
        and preserved_wt_name
        and os.path.isdir(preserved_wt)
        and preserved_branch_ok
    ):
        logger.info(
            "dispatch: reusing preserved worktree for %s at %s (reset-failed path)",
            change_name, preserved_wt,
        )
        wt_name = preserved_wt_name
        wt_path = preserved_wt
        # Skip the collision-resolution below — the worktree+branch are ours
        # on purpose, not a stale leftover.
    else:
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
            # Don't delete the branch yet — it may have committed artifacts worth preserving

    if not os.path.isdir(wt_path):
        branch_name = f"change/{wt_name}"
        branch_check = run_git("rev-parse", "--verify", branch_name, best_effort=True)

        if branch_check.exit_code == 0:
            # Branch exists — check if it has commits ahead of main worth preserving
            main_branch = detect_default_branch()
            ahead_r = run_git("rev-list", "--count", f"{main_branch}..{branch_name}")
            ahead_count = int(ahead_r.stdout.strip()) if ahead_r.exit_code == 0 else 0

            if ahead_count > 0:
                # Branch has committed work — create worktree from existing branch
                logger.info(
                    "redispatch: preserving branch %s with %d commits ahead of %s",
                    branch_name, ahead_count, main_branch,
                )
                wt_new_r = run_command(
                    ["git", "worktree", "add", wt_path, branch_name],
                    timeout=30,
                )
                if wt_new_r.exit_code != 0:
                    # Fallback: branch may have conflicts, create fresh
                    logger.warning(
                        "redispatch: failed to reuse branch %s, falling back to fresh: %s",
                        branch_name, wt_new_r.stderr,
                    )
                    run_git("branch", "-D", branch_name)
                    wt_new_r = run_command(["set-new", wt_name, "--skip-open"], timeout=30)
            else:
                # Branch has no unique commits — safe to delete and recreate
                logger.info("removing stale branch %s (0 commits ahead) before fresh dispatch", branch_name)
                run_git("branch", "-D", branch_name)
                wt_new_r = run_command(["set-new", wt_name, "--skip-open"], timeout=30)
        else:
            # No existing branch — normal fresh dispatch
            wt_new_r = run_command(["set-new", wt_name, "--skip-open"], timeout=30)

        if wt_new_r.exit_code != 0:
            logger.error("failed to create worktree for %s: %s", change_name, wt_new_r.stderr)
            update_change_field(state_path, change_name, "status", "failed", event_bus=event_bus)
            return False

    # Find actual worktree path (use wt_name which may have -N suffix)
    wt_path = _find_existing_worktree(project_path, wt_name)

    # Bootstrap
    bootstrap_worktree(project_path, wt_path, change_name=change_name)

    # Persist the deterministic worktree port so the gate runner reads the
    # same value at e2e time regardless of profile re-instantiation. Without
    # this the gate re-computes it from scratch — still deterministic, but
    # opaque to observability and un-overridable. See OpenSpec change:
    # fix-e2e-infra-systematic (T1.5).
    try:
        from .profile_loader import load_profile as _lp, NullProfile as _NP
        _p_for_port = _lp(project_path)
        if not isinstance(_p_for_port, _NP) and hasattr(_p_for_port, "worktree_port"):
            _assigned_port = int(_p_for_port.worktree_port(change_name))
            if _assigned_port > 0 and int(
                change.extras.get("assigned_e2e_port", 0)
            ) != _assigned_port:
                # update_change_field routes unknown field names straight into
                # change.extras[field_name]. Passing literal "extras" would
                # create change.extras["extras"] = {...}; use the individual
                # key instead so it lands at the top of extras.
                update_change_field(
                    state_path, change_name, "assigned_e2e_port",
                    _assigned_port, event_bus=event_bus,
                )
                change.extras["assigned_e2e_port"] = _assigned_port
                logger.info(
                    "dispatch %s: persisted assigned_e2e_port=%d",
                    change_name, _assigned_port,
                )
    except Exception:
        logger.debug("Failed to persist assigned_e2e_port", exc_info=True)

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
    except Exception as _e:
        logger.warning("Failed to write env_vars to .env in %s: %s", wt_path, _e)

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

    # Classify scope text for content-aware learnings filtering
    from .templates import classify_diff_content
    _content_categories = classify_diff_content(scope)
    if _content_categories:
        logger.debug("Dispatch %s: content categories from scope: %s", change_name, _content_categories)

    # Cross-change review learnings (scope-filtered)
    from .paths import LineagePaths as _LP_disp
    findings_path = _LP_disp(os.path.dirname(state_path)).review_findings
    review_learnings = _build_review_learnings(findings_path, change_name, content_categories=_content_categories)

    # Profile-based persistent review checklist (cross-run, scope-filtered)
    review_checklist = ""
    try:
        from .profile_loader import load_profile
        _profile = load_profile()
        review_checklist = _profile.review_learnings_checklist(
            project_path, content_categories=_content_categories or None,
        )
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

    # Design source deployment + dispatch context (v0-only pipeline).
    # The full v0-export/ is symlinked into the worktree so the agent has
    # reference-level access to every design file. The dispatch-context
    # markdown points to focus files + shared layer + tokens.
    # Per design D8: when the profile declares a design source (!= "none"),
    # ANY exception from the profile methods fails the dispatch loudly with
    # reason `design-provider-error`.
    project_path = os.path.dirname(state_path) or os.getcwd()
    try:
        from .profile_loader import load_profile as _load_profile_for_design
        _design_profile = _load_profile_for_design()
        _design_source_id = _design_profile.detect_design_source(Path(project_path))
    except Exception:
        logger.error("detect_design_source raised for %s", change_name, exc_info=True)
        _design_source_id = "none"

    if _design_source_id != "none":
        try:
            _deploy_v0_export_to_worktree(project_path, wt_path)
            _ctx_md = _design_profile.get_design_dispatch_context(
                change_name, scope, Path(project_path),
            )
            if _ctx_md:
                ctx.design_context = _ctx_md
                logger.info(
                    "Design context injected (%d chars, source=%s) for %s",
                    len(_ctx_md), _design_source_id, change_name,
                )
        except Exception:
            logger.error(
                "design-provider-error for %s (source=%s) — dispatch FAILED",
                change_name, _design_source_id, exc_info=True,
            )
            return False
    else:
        try:
            _ctx_md = _design_profile.get_design_dispatch_context(
                change_name, scope, Path(project_path),
            )
            if _ctx_md:
                ctx.design_context = _ctx_md
        except Exception:
            logger.debug("Defensive design context raised (source=none)", exc_info=True)

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

    # Generate START.md via profile (replaces old inline CLAUDE.md startup guide)
    _write_startup_file(wt_path)

    # Append schema digest to worktree CLAUDE.md (replaces data-definitions.md)
    from set_orch.dispatcher_schema import append_schema_digest_to_claudemd
    append_schema_digest_to_claudemd(wt_path)

    # Write the per-worktree e2e manifest for ownership detection at gate time.
    change_reqs = list(getattr(change, "requirements", []) or [])
    _write_e2e_manifest(wt_path, change_name, change_reqs)

    # Generate test skeleton from test-plan.json (deterministic structure)
    _skeleton_path = ""
    _skeleton_count = 0
    if digest_dir and change_reqs:
        try:
            from .test_scaffold import generate_skeleton
            from .profile_loader import load_profile as _load_scaffold_profile
            _scaffold_profile = _load_scaffold_profile(project_path)
            _scaffold_entries = _load_test_plan(digest_dir, change_reqs)
            if _scaffold_entries and hasattr(_scaffold_profile, "render_test_skeleton"):
                _skeleton_path, _skeleton_count = generate_skeleton(
                    test_plan_entries=_scaffold_entries,
                    change_name=change_name,
                    worktree_path=wt_path,
                    profile=_scaffold_profile,
                )
                if _skeleton_count > 0:
                    # Post-process tasks.md: replace E2E tasks with "fill skeleton"
                    _rewrite_e2e_tasks(wt_path, change_name, _skeleton_path, _skeleton_count)
        except Exception:
            logger.debug("Test skeleton generation failed (non-fatal)", exc_info=True)

    # Update state
    update_change_field(state_path, change_name, "status", "dispatched", event_bus=event_bus)
    update_change_field(state_path, change_name, "current_step", "planning", event_bus=event_bus)
    update_change_field(state_path, change_name, "worktree_path", wt_path, event_bus=event_bus)
    update_change_field(state_path, change_name, "started_at", datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"), event_bus=event_bus)

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

    # Dispatch summary log (task 1.1)
    _n_reqs = len(change_reqs) if change_reqs else 0
    _n_test_entries = 0
    if digest_dir and change_reqs:
        _n_test_entries = len(_load_test_plan(digest_dir, change_reqs))
    _has_design = "yes" if _design_source_id != "none" else "no"
    _retry_n = change.redispatch_count if hasattr(change, "redispatch_count") else 0
    logger.info(
        "Dispatched %s: requirements=%d, test_plan_entries=%d, "
        "digest_dir=%s, design=%s, retry=%d",
        change_name, _n_reqs, _n_test_entries,
        "set" if digest_dir else "empty", _has_design, _retry_n,
    )

    # ANOMALY: feature change with 0 requirements (task 1.2)
    _change_type = getattr(change, "change_type", "feature") or "feature"
    if _change_type == "feature" and _n_reqs == 0:
        logger.warning(
            "[ANOMALY] Feature change %s dispatched with 0 requirements "
            "— agent won't get Required Tests",
            change_name,
        )

    # ANOMALY: has requirements but 0 test plan entries (task 1.3)
    if _n_reqs > 0 and _n_test_entries == 0 and digest_dir:
        logger.warning(
            "[ANOMALY] %s has %d requirements but 0 test plan entries "
            "— test-plan.json may not match",
            change_name, _n_reqs,
        )

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
        # Preserve the retry context into extras.last_retry_context BEFORE
        # clearing it. The main retry_context field gets cleared because it's
        # already been consumed — written into input.md above. But if the
        # agent subsequently hard-fails (verify-retry budget exhausted), we
        # want post-mortem analysis to still see what the last feedback was.
        # extras.last_retry_context is never cleared on dispatch, so it
        # survives until the next retry cycle overwrites it OR the run ends.
        update_change_field(state_path, change_name, "last_retry_context", retry_ctx)
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
        logger.debug("_setup_digest_context: index.json missing in %s", digest_dir)
        return

    try:
        with open(index_path) as f:
            index = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.debug("_setup_digest_context: failed to parse index.json in %s", digest_dir)
        return

    spec_base_dir = index.get("spec_base_dir", "")
    state = load_state(state_path)
    change = _find_change(state, change_name)
    if not change:
        logger.debug("_setup_digest_context: change %s not found in state", change_name)
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
    The loop-state.json is preserved (not deleted) so that ``init_loop_state`` can
    reuse the previous ``session_id`` for Claude ``--resume``, keeping the prompt
    cache warm across dispatcher-level restarts (e.g. gate retry fixes).
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
        # NOTE: loop-state.json is intentionally NOT removed here. init_loop_state()
        # reads the prior session_id + resume_failures to allow Claude --resume
        # to reuse the cached prompt prefix. Change-name guard in init_loop_state
        # prevents cross-change cache poisoning if worktree is reused.
        prior_sid = ls.get("session_id") or ""
        logger.info(
            "dispatch guard: preserving loop-state.json for %s (session_id=%s)",
            change_name, prior_sid[:8] if prior_sid else "none",
        )
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("dispatch guard: error reading state for %s: %s", change_name, e)


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

    # Per-iteration timeout. set-loop's CLI default (45m) is too tight for
    # framework-integration fix cycles on web projects: a single iteration
    # may burn 40+ minutes when the agent has to iterate through several
    # Playwright approaches (observed on craftbrew-run-20260415-0146
    # admin-products — agent was on the right keyboard-nav track but
    # SIGTERM'd at minute 45 mid-solution, losing context continuity).
    # 90m gives enough headroom without masking truly stuck agents.
    iteration_timeout_min = 90

    cmd = [
        "set-loop", "start", task_desc,
        "--max", "30",
        "--done", "openspec",
        "--label", change_name,
        "--model", impl_model,
        "--change", change_name,
        "--iteration-timeout", str(iteration_timeout_min),
    ]
    if team_mode:
        cmd.append("--team")

    logger.info(
        "dispatch %s with model=%s budget=unlimited (iter limit: --max 30, "
        "iter timeout: %dm) team=%s",
        change_name, impl_model, iteration_timeout_min, team_mode,
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
    except (json.JSONDecodeError, OSError, ValueError, TypeError) as exc:
        logger.error("Failed to parse loop-state.json for %s: %s", change_name, exc)

    if terminal_pid <= 0:
        logger.error(
            "dispatch_via_wt_loop: invalid terminal_pid=%s for %s — failing dispatch",
            terminal_pid, change_name,
        )
        if event_bus:
            event_bus.emit("ERROR", change=change_name, data={"error": f"invalid terminal_pid={terminal_pid}"})
        update_change_field(state_path, change_name, "status", "failed", event_bus=event_bus)
        return False

    update_change_field(state_path, change_name, "ralph_pid", terminal_pid, event_bus=event_bus)
    update_change_field(state_path, change_name, "status", "running", event_bus=event_bus)
    logger.info("ralph started for %s in %s (terminal PID %d)", change_name, wt_path, terminal_pid)

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
    except Exception as e:
        logger.warning("Failed to load serialize triggers: %s", e)
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


def _iss_owned_change_names(state_path: str) -> set[str]:
    """Return the set of change names currently owned by the ISS pipeline.

    A change is "owned" when an active Issue (not in terminal/pending
    state) carries it as `change_name`. The engine must skip these so
    the ISS investigator + fix runner can drive the /opsx:ff and
    /opsx:apply steps without colliding with a parallel worktree
    dispatch on the same openspec change.

    Returns an empty set when `.set/issues/registry.json` is missing,
    empty, or unreadable — ISS is optional; absence means engine
    dispatches everything as before.
    """
    try:
        import json as _json
        from os import path as _p
        # The registry lives alongside the state file, not inside set/.
        # Resolve: state_path may be at project-root or lineage variant;
        # `.set/issues/registry.json` is always at project root.
        project_dir = _p.dirname(_p.abspath(state_path))
        # Walk up if the state file is nested (e.g. under a lineage dir).
        for _ in range(3):
            candidate = _p.join(project_dir, ".set", "issues", "registry.json")
            if _p.isfile(candidate):
                reg_path = candidate
                break
            parent = _p.dirname(project_dir)
            if parent == project_dir:
                return set()
            project_dir = parent
        else:
            return set()
        with open(reg_path) as fh:
            data = _json.load(fh)
        # States where the ISS owns the change — matches ACTIVE_STATES.
        # `new` is included so the engine backs off between a fresh escalation
        # (filesystem registry write) and the set-web tick-loop picking it up
        # and spawning the investigator (≤30s). Without this, the engine's
        # 15s dispatcher loop can fire first, creating a parallel Ralph worktree
        # on the same openspec change — predictable git conflicts. If the ISS
        # pipeline fails to transition the issue out of `new`, that is a bug
        # we want visible (stalled pending change + NEW issue in the UI)
        # rather than masked by a double-dispatch.
        active = {
            "new",
            "investigating", "diagnosed", "awaiting_approval",
            "fixing", "verifying", "deploying", "failed",
        }
        out: set[str] = set()
        for i in data.get("issues", []):
            if (i.get("state") or "").lower() not in active:
                continue
            cn = (i.get("change_name") or "").strip()
            if cn:
                out.add(cn)
        return out
    except (OSError, ValueError, KeyError):
        return set()


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
) -> int:
    """Dispatch pending changes respecting deps and parallel limits.

    Migrated from: dispatcher.sh dispatch_ready_changes() L663-723

    Returns number of changes dispatched.
    """
    state = load_state(state_path)

    # Fail-fast halt: if any change has reached terminal "failed" status, do
    # not dispatch further work. The operator must investigate (fix scope,
    # reset status, bump retries) before new changes start. Prevents sibling
    # changes from silently burning tokens while a peer is broken and also
    # avoids wasting work when the failed change is likely a blocker for
    # reviewers. To resume: reset the failed change's status (e.g. pending).
    failed_names = [c.name for c in state.changes if c.status == "failed"]
    if failed_names:
        logger.warning(
            "Halt on failure: %s failed — suppressing new dispatches "
            "(reset status to pending to resume)",
            ", ".join(failed_names),
        )
        return 0

    # Whitelist-based counting: every change that is NOT in a terminal/pending
    # state counts toward the parallel limit. This is safer than blacklisting
    # specific in-flight states — adding a new intermediate status in the
    # future will fail safe (block dispatches) until explicitly classified.
    # See state.py:_NOT_IN_FLIGHT_STATUSES for the whitelist.
    from .state import count_in_flight_changes
    running = count_in_flight_changes(state)

    # Topological order from state (not plan — state carries forward after replan)
    order = topological_sort(state.changes)

    # Read current phase for milestone gating
    current_phase = state.extras.get("current_phase", 999)

    # Collect ready changes
    iss_owned = _iss_owned_change_names(state_path)
    ready_names: list[str] = []
    for name in order:
        change = _find_change(state, name)
        if not change or change.status != "pending":
            continue
        # Phase gate
        if change.phase > current_phase:
            continue
        # ISS pipeline owns this change end-to-end — an active Issue is
        # investigating or fixing it via /opsx:ff + /opsx:apply in the
        # set-core directory. Dispatching it again through the engine's
        # worktree pipeline would run two agents concurrently on the
        # same openspec change, with predictable git conflicts.
        if name in iss_owned:
            logger.debug(
                "Skipping dispatch for %s — owned by active ISS pipeline", name,
            )
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
        except (ValueError, OSError) as e:
            logger.warning("Failed to pause %s: %s", change_name, e)

    update_change_field(state_path, change_name, "status", "paused", event_bus=event_bus)
    if event_bus:
        event_bus.emit("MANUAL_STOP", change=change_name)
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

    # Reset merge-rebase retry counter — an agent redispatch produces a
    # fresh commit tree so the git-conflict counter starts from zero. Do
    # NOT touch `integration_e2e_retry_count` here: that counter limits
    # how many times we ask the agent to fix the SAME smoke/own-test
    # failure, and clearing it on every dispatch would create an infinite
    # loop against a persistent gate failure (observed in micro E2E run).
    with locked_state(state_path) as st:
        ch = _find_change(st, change_name)
        if ch:
            if ch.extras.get("merge_retry_count"):
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

    # Determine retry type FIRST so we can skip session resume for unsafe cases.
    is_merge_retry = change.extras.get("merge_rebase_pending", False)
    is_review_retry = "REVIEW FEEDBACK" in retry_ctx or "review" in retry_ctx.lower()[:50]

    # Stall recovery guard: if this resume is the fallout of a dead-agent /
    # context-overflow stall, the preserved session CARRIES the context that
    # killed the agent. Resuming it loads the same poisoned context back in
    # → overflow again → stall again → circular. The reasons that imply a
    # poisoned context are: the ralph process died with no commits, the
    # verify agent was found dead mid-gate, or the fix loop ran itself empty.
    # Token runaway / capacity_limit_pct also mean "context was already huge".
    # In all those cases we MUST force a fresh session even when everything
    # else about resume looks clean.
    _stall_reason = ""
    try:
        _st = load_state(state_path)
        _ch = _find_change(_st, change_name)
        if _ch is not None:
            _stall_reason = str(_ch.extras.get("stall_reason") or "")
    except Exception:
        pass
    _poisoned_stall_prefixes = (
        "dead_running_agent_",
        "dead_verify_agent",
        "verify_timeout",
        "fix_loop_no_progress_",
        "token_runaway",
        "context_overflow",
    )
    is_poisoned_stall_recovery = bool(_stall_reason) and any(
        _stall_reason.startswith(p) for p in _poisoned_stall_prefixes
    )

    # Check if a Claude session can be SAFELY resumed. Session resume keeps the
    # prompt cache warm and avoids re-reading files, but it also carries over
    # prior conversation history which can "poison" the fix if the context changed
    # underneath the agent. Guardrails:
    #   1. Merge rebase retries → NEVER resume. The main branch moved, the agent's
    #      prior view of the codebase is stale, and applying old code to new base
    #      causes conflicts and hallucinations.
    #   2. Stale session (> 60 min since last activity) → fresh start. Claude's
    #      auto-compaction may have summarized away important details, and long-
    #      delayed resumes increase hallucination risk.
    #   3. Too many prior resume failures → fresh start (existing behavior).
    #   4. Change name must match (already enforced in init_loop_state).
    #   5. Poisoned-stall recovery → fresh start (agent was killed BY the
    #      preserved context — reusing it just re-triggers the failure).
    has_resumable_session = False
    resume_skip_reason = ""
    if is_merge_retry:
        resume_skip_reason = "merge_rebase_pending (main branch changed)"
    elif is_poisoned_stall_recovery:
        resume_skip_reason = f"poisoned_stall_recovery ({_stall_reason})"
    elif os.path.isfile(loop_state_path):
        try:
            with open(loop_state_path) as f:
                _ls = json.load(f)
            _prior_sid = _ls.get("session_id") or ""
            _prior_change = _ls.get("change") or ""
            _prior_resume_failures = int(_ls.get("resume_failures") or 0)
            _prior_started = _ls.get("started_at", "")
            # Age check: how old is this session?
            session_age_min = 0
            if _prior_started:
                try:
                    from datetime import datetime, timezone
                    prior_dt = datetime.fromisoformat(_prior_started.replace("Z", "+00:00"))
                    if prior_dt.tzinfo is None:
                        prior_dt = prior_dt.replace(tzinfo=timezone.utc)
                    session_age_min = (datetime.now(timezone.utc) - prior_dt).total_seconds() / 60
                except (ValueError, TypeError):
                    pass

            if not _prior_sid:
                resume_skip_reason = "no prior session_id"
            elif _prior_change != change_name:
                resume_skip_reason = f"change name mismatch ({_prior_change!r} != {change_name!r})"
            elif _prior_resume_failures >= 3:
                resume_skip_reason = f"too many prior resume failures ({_prior_resume_failures})"
            elif session_age_min > 60:
                resume_skip_reason = f"session too old ({session_age_min:.0f} min > 60 min)"
            else:
                has_resumable_session = True
        except (json.JSONDecodeError, OSError, ValueError) as e:
            resume_skip_reason = f"state read error: {e}"
    else:
        resume_skip_reason = "no loop-state.json"

    if has_resumable_session:
        logger.info("resume_change %s: session resume ELIGIBLE — cache stays warm", change_name)
    elif retry_ctx or is_poisoned_stall_recovery:
        logger.info("resume_change %s: fresh session (%s)", change_name, resume_skip_reason)
        # Clear the preserved session_id so init_loop_state won't reuse it.
        # Poisoned-stall recovery hits this branch EVEN without retry_ctx,
        # because the cause of the stall (context overflow / dead agent)
        # lives inside that session — reusing it guarantees a repeat stall.
        try:
            with open(loop_state_path) as f:
                _ls = json.load(f)
            _ls["session_id"] = None
            _ls["resume_failures"] = 0
            with open(loop_state_path, "w") as f:
                json.dump(_ls, f, indent=2)
            logger.debug("cleared preserved session_id for %s (unsafe to resume)", change_name)
        except (json.JSONDecodeError, OSError, ValueError):
            pass
        # Clear stall_reason once we're acting on it — next stall will set it
        # again with its own cause, so we don't carry a stale signal forward.
        if is_poisoned_stall_recovery:
            update_change_field(
                state_path, change_name, "stall_reason", None,
                event_bus=event_bus,
            )

    if retry_ctx:
        if has_resumable_session:
            # Session will resume — files already in context, no preamble needed.
            task_desc = retry_ctx
            logger.info(
                "resuming %s with retry context (%d chars, session resume — preamble skipped)",
                change_name, len(retry_ctx),
            )
        else:
            preamble = _build_resume_preamble(change_name, wt_path)
            task_desc = (preamble + "\n\n" + retry_ctx) if preamble else retry_ctx
            logger.info(
                "resuming %s with retry context (%d chars + %d preamble, fresh session)",
                change_name, len(retry_ctx), len(preamble),
            )
        # Preserve into extras.last_retry_context for post-mortem (see dispatch_change
        # comment above — same rationale: on hard-fail we want the history).
        update_change_field(state_path, change_name, "last_retry_context", retry_ctx, event_bus=event_bus)
        update_change_field(state_path, change_name, "retry_context", None, event_bus=event_bus)
        update_change_field(state_path, change_name, "current_step", "fixing", event_bus=event_bus)
        if is_merge_retry:
            done_criteria = "merge"
            max_iter = 7
        elif is_review_retry:
            done_criteria = "test"
            max_iter = 7  # review fixes need more iterations (fix + re-test)
        else:
            done_criteria = "test"
            max_iter = 5
    else:
        # No retry_context — normal resume. BUT if the change was previously
        # in a fix loop (verify_retry_count > 0 and current_step was "fixing"),
        # preserve fix mode so the agent gets fix-appropriate context.
        prev_step = change.current_step or "implementing"
        if prev_step == "fixing" and change.verify_retry_count > 0:
            logger.info(
                "resume %s: preserving current_step=fixing (verify_retry_count=%d, retry_context consumed)",
                change_name, change.verify_retry_count,
            )
            update_change_field(state_path, change_name, "current_step", "fixing", event_bus=event_bus)
            last_ctx = (change.extras or {}).get("last_retry_context", "")
            if not last_ctx:
                logger.warning("resume %s: last_retry_context empty — agent gets generic fix prompt", change_name)
            task_desc = last_ctx or f"Continue fixing {change_name}: {change.scope[:200]}"
            done_criteria = "test"
            max_iter = 5
        else:
            task_desc = f"Continue {change_name}: {change.scope[:200]}"
            done_criteria = "openspec"
            max_iter = 30
            update_change_field(state_path, change_name, "current_step", "implementing", event_bus=event_bus)

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

    # Same 90m iteration timeout as initial dispatch — set-loop's CLI default
    # (45m) SIGTERM's the agent mid-solution on web E2E retries. Without this
    # override the resume path silently falls back to 45m and every long fix
    # iteration dies at minute 45 (observed on craftbrew-run-20260415-1225
    # checkout-and-orders — agent mid-fix SIGTERM'd, 27 E2E failures not
    # addressed, status=stalled).
    iteration_timeout_min = 90

    cmd = [
        "set-loop", "start", task_desc,
        "--max", str(max_iter),
        "--done", done_criteria,
        "--label", change_name,
        "--model", impl_model,
        "--change", change_name,
        "--iteration-timeout", str(iteration_timeout_min),
    ]
    if test_command:
        cmd.extend(["--test-command", test_command])
    if team_mode:
        cmd.append("--team")

    logger.info(
        "resume %s with model=%s (done=%s, max=%d, iter timeout=%dm) team=%s",
        change_name, impl_model, done_criteria, max_iter, iteration_timeout_min, team_mode,
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
    if event_bus:
        event_bus.emit("MANUAL_RESUME", change=change_name)
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


def resume_paused_changes(
    state_path: str,
    event_bus: EventBus | None = None,
    **resume_kwargs: Any,
) -> int:
    """Resume changes that were paused by a non-graceful orchestrator shutdown.

    Context
    -------
    engine.shutdown() sets every in-flight change to `paused` with the comment
    "so they resume on restart". But the dispatch loop EXCLUDES paused from
    ready-to-dispatch (see `change.status not in ("paused", ...)`), and no
    other routine picks them up either. Without this function, a sentinel
    restart (or forced kill after the 90s grace period) parks all active
    changes in "paused" permanently — the user has to manually POST to
    `/api/.../resume` for each one.

    Behavior
    --------
    For each paused change with a valid worktree: call `resume_change` (which
    replays retry_context and reuses the Claude session cache). Paused changes
    whose worktree is gone are NOT re-dispatched here — orphan cleanup already
    transitions those to "pending" in `_cleanup_orphans`.

    Returns
    -------
    Number of paused changes resumed.

    See also
    --------
    resume_stopped_changes — for changes in "stopped" status (different code
    path, usually legacy). We keep both because the distinction matters for
    event emission (CHANGE_RESUMED vs CHANGE_STARTED).
    """
    state = load_state(state_path)
    resumed = 0

    for change in state.changes:
        if change.status != "paused":
            continue
        if not (change.worktree_path and os.path.isdir(change.worktree_path)):
            # Let orphan cleanup handle it — it'll transition to "pending".
            logger.info(
                "skipping resume of paused %s — worktree missing (orphan cleanup will recover)",
                change.name,
            )
            continue
        logger.info("resuming paused change: %s", change.name)
        if resume_change(state_path, change.name, event_bus=event_bus, **resume_kwargs):
            resumed += 1

    if resumed:
        logger.info("resume_paused_changes: resumed %d change(s)", resumed)
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

    # Check which changes are owned by the issue pipeline (with timestamps)
    from .engine import _get_issue_owned_changes_with_ts
    issue_owned = _get_issue_owned_changes_with_ts()

    ISSUE_OWNERSHIP_TIMEOUT = 1800  # 30 minutes

    for change in state.changes:
        if change.status != "stalled":
            continue
        if change.name in issue_owned:
            ownership_start = issue_owned[change.name]
            ownership_duration = now - ownership_start
            if ownership_duration < ISSUE_OWNERSHIP_TIMEOUT:
                logger.info(
                    "skipping stalled %s — owned by issue pipeline (%ds/%ds)",
                    change.name, ownership_duration, ISSUE_OWNERSHIP_TIMEOUT,
                )
                continue
            else:
                logger.warning(
                    "releasing issue ownership for %s — timed out after %ds (limit %ds)",
                    change.name, ownership_duration, ISSUE_OWNERSHIP_TIMEOUT,
                )
        stalled_at = change.extras.get("stalled_at", 0)
        cooldown = now - stalled_at
        if cooldown >= STALL_COOLDOWN_SECONDS:
            _stall_reason = change.extras.get("stall_reason", "unknown")
            logger.info(
                "Recovering stalled %s — stalled for %ds, reason=%s",
                change.name, cooldown, _stall_reason,
            )
            resume_change(state_path, change.name, event_bus=event_bus, **resume_kwargs)
            resumed += 1

    return resumed
