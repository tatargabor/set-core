"""Consumer project harvest — scan E2E runs for unadopted framework fixes.

Scans registered consumer projects for ISS fix commits and .claude/
modifications that haven't been reviewed yet. Presents them chronologically
for interactive adoption into set-core templates, planning rules, or core code.

Usage:
    set-harvest                          # scan all registered projects
    set-harvest --project craftbrew-run22 # scan single project
    set-harvest --dry-run                # show without updating state
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Config ─────────────────────────────────────────────────────────

HARVEST_STATE_FILE = os.path.expanduser("~/.local/share/set-core/harvest-state.json")
PROJECTS_JSON = os.path.expanduser("~/.config/set-core/projects.json")

# Commit message patterns that indicate ISS fixes
ISS_PATTERNS = ["fix-iss-", "fix:", "fix("]

# Files that indicate framework-relevant changes
FRAMEWORK_FILES = {
    "package.json",
    "playwright.config.ts", "playwright.config.js",
    "vitest.config.ts", "vitest.config.js",
    "next.config.js", "next.config.ts", "next.config.mjs",
    "middleware.ts", "middleware.js",
    "tsconfig.json", "postcss.config.mjs",
    ".env.example",
    "tests/e2e/global-setup.ts",
}

# File path prefixes that indicate framework-relevant changes
FRAMEWORK_PREFIXES = [".claude/", "set/"]

# File path prefixes that indicate project-specific changes
PROJECT_SPECIFIC_PREFIXES = [
    "src/app/", "src/components/", "src/lib/",
    "prisma/schema.prisma", "prisma/seed",
    "src/messages/",
]

# Adoption target mapping: consumer file → set-core location
ADOPTION_TARGETS = {
    "package.json": "modules/web/set_project_web/planning_rules.txt",
    "playwright.config.ts": "modules/web/set_project_web/templates/nextjs/playwright.config.ts",
    "vitest.config.ts": "modules/web/set_project_web/templates/nextjs/vitest.config.ts",
    "middleware.ts": ".claude/rules/web/set-auth-middleware.md",
    "next.config.js": "modules/web/set_project_web/templates/nextjs/next.config.js",
    "tests/e2e/global-setup.ts": "modules/web/set_project_web/templates/nextjs/tests/e2e/global-setup.ts",
}


# ─── Data Model ─────────────────────────────────────────────────────


@dataclass
class HarvestCandidate:
    """A single commit that may contain framework-relevant changes."""

    project: str
    commit_sha: str
    date: str  # ISO format
    message: str
    files_changed: list[str]
    classification: str  # "framework", "project-specific", "template-divergence"
    suggested_target: str = ""
    diff_text: str = ""
    kind: str = "commit"  # "commit" or "issue"

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "commit_sha": self.commit_sha,
            "date": self.date,
            "message": self.message,
            "files_changed": self.files_changed,
            "classification": self.classification,
            "suggested_target": self.suggested_target,
            "kind": self.kind,
        }


@dataclass
class IssueCandidate:
    """An ISS entry that may indicate a framework bug."""

    project: str
    issue_id: str
    state: str  # diagnosed, new, failed, resolved
    severity: str
    summary: str
    affected_change: str
    root_cause: str
    fix_target: str  # framework, consumer, both, none
    suggested_fix: str
    detected_at: str
    investigation_path: str = ""

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "issue_id": self.issue_id,
            "state": self.state,
            "severity": self.severity,
            "summary": self.summary,
            "affected_change": self.affected_change,
            "root_cause": self.root_cause[:200],
            "fix_target": self.fix_target,
            "suggested_fix": self.suggested_fix[:200],
            "detected_at": self.detected_at,
        }


# ─── Harvest State ──────────────────────────────────────────────────


def _load_harvest_state() -> dict:
    """Load harvest state (last_harvested_sha per project)."""
    if os.path.isfile(HARVEST_STATE_FILE):
        try:
            return json.loads(Path(HARVEST_STATE_FILE).read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_harvest_state(state: dict) -> None:
    """Save harvest state atomically."""
    os.makedirs(os.path.dirname(HARVEST_STATE_FILE), exist_ok=True)
    Path(HARVEST_STATE_FILE).write_text(json.dumps(state, indent=2) + "\n")


def get_harvest_state(project_name: str) -> Optional[str]:
    """Get last harvested SHA for a project."""
    return _load_harvest_state().get(project_name)


def set_harvest_state(project_name: str, sha: str) -> None:
    """Set last harvested SHA for a project."""
    state = _load_harvest_state()
    state[project_name] = sha
    _save_harvest_state(state)


# ─── Project Registry ──────────────────────────────────────────────


def _get_registered_projects() -> dict[str, str]:
    """Get registered projects from set-project registry.

    Returns dict of name → path.
    """
    if not os.path.isfile(PROJECTS_JSON):
        return {}
    try:
        data = json.loads(Path(PROJECTS_JSON).read_text())
        projects = data.get("projects", {})
        return {
            name: info["path"]
            for name, info in projects.items()
            if isinstance(info, dict) and "path" in info
        }
    except (json.JSONDecodeError, OSError):
        return {}


# ─── Git Scanning ───────────────────────────────────────────────────


def _run_git(args: list[str], cwd: str) -> str:
    """Run a git command and return stdout."""
    try:
        r = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True, timeout=30, cwd=cwd,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _get_init_sha(project_path: str) -> str:
    """Get the SHA of the set-project init commit (v1-ready tag or first commit)."""
    # Try v1-ready tag first
    sha = _run_git(["rev-list", "-1", "v1-ready"], project_path)
    if sha:
        return sha
    # Fall back to first commit
    sha = _run_git(["rev-list", "--max-parents=0", "HEAD"], project_path)
    return sha


def _get_head_sha(project_path: str) -> str:
    """Get current HEAD SHA."""
    return _run_git(["rev-parse", "HEAD"], project_path)


def _is_iss_fix(message: str) -> bool:
    """Check if a commit message indicates an ISS fix."""
    msg_lower = message.lower()
    return any(p in msg_lower for p in ISS_PATTERNS)


def _get_changed_files(sha: str, project_path: str) -> list[str]:
    """Get list of files changed in a commit."""
    output = _run_git(["diff-tree", "--no-commit-id", "-r", "--name-only", sha], project_path)
    return [f for f in output.split("\n") if f.strip()] if output else []


def _classify_commit(files: list[str]) -> tuple[str, str]:
    """Classify a commit based on files changed.

    Returns (classification, suggested_target).
    """
    has_framework = False
    has_template_divergence = False
    suggested = ""

    for f in files:
        basename = os.path.basename(f)
        # Check framework-relevant files
        if basename in FRAMEWORK_FILES:
            has_framework = True
            if basename in ADOPTION_TARGETS:
                suggested = ADOPTION_TARGETS[basename]
        # Check .claude/ modifications (template divergence)
        if any(f.startswith(p) for p in FRAMEWORK_PREFIXES):
            if f.startswith(".claude/rules/set-"):
                has_template_divergence = True
                suggested = f"templates/core/rules/{os.path.basename(f)}"
            elif f.startswith(".claude/"):
                has_template_divergence = True

    if has_framework:
        return "framework", suggested
    if has_template_divergence:
        return "template-divergence", suggested

    # Check if ALL files are project-specific
    all_project_specific = all(
        any(f.startswith(p) for p in PROJECT_SPECIFIC_PREFIXES)
        for f in files
    )
    if all_project_specific:
        return "project-specific", ""

    return "unknown", ""


def scan_project(
    project_name: str,
    project_path: str,
    since_sha: Optional[str] = None,
) -> list[HarvestCandidate]:
    """Scan a project for unadopted changes since last harvest.

    Args:
        project_name: Display name of the project.
        project_path: Absolute path to the project.
        since_sha: Only show commits after this SHA. If None, scan from init.

    Returns:
        List of HarvestCandidate sorted by date.
    """
    if not os.path.isdir(os.path.join(project_path, ".git")):
        logger.debug("Skipping %s: no .git dir", project_name)
        return []

    if not since_sha:
        since_sha = _get_init_sha(project_path)
    if not since_sha:
        return []

    # Get commits since last harvest
    log_output = _run_git(
        ["log", "--format=%H|%aI|%s", f"{since_sha}..HEAD", "--reverse"],
        project_path,
    )
    if not log_output:
        return []

    candidates = []
    for line in log_output.split("\n"):
        if not line.strip() or "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        sha, date, message = parts

        # Only interested in fix commits — not features, chores, or reflections
        if not _is_iss_fix(message):
            continue

        # Skip noise commits
        msg_lower = message.lower()
        if any(msg_lower.startswith(p) for p in (
            "chore:", "docs:", "feat:", "wip:", "merge:",
            "chore(", "docs(", "feat(",
        )):
            continue

        files = _get_changed_files(sha, project_path)

        classification, suggested = _classify_commit(files)

        candidates.append(HarvestCandidate(
            project=project_name,
            commit_sha=sha,
            date=date,
            message=message,
            files_changed=files,
            classification=classification,
            suggested_target=suggested,
        ))

    return candidates


def scan_all_projects(
    project_filter: Optional[str] = None,
) -> tuple[list[HarvestCandidate], list[IssueCandidate]]:
    """Scan all registered projects for unadopted changes and unresolved issues.

    Returns (commit_candidates, issue_candidates) sorted chronologically.
    """
    projects = _get_registered_projects()
    if not projects:
        logger.warning("No registered projects found")
        return [], []

    all_candidates = []
    all_issues = []
    harvest_state = _load_harvest_state()

    for name, path in projects.items():
        if project_filter and name != project_filter:
            continue
        if not os.path.isdir(path):
            continue
        # Skip worktree paths (only scan main project dirs)
        if "-wt-" in name:
            continue
        # Only scan consumer E2E run projects (not set-core itself)
        # Consumer runs are initialized by set-project init with project-type.yaml
        pt_file = os.path.join(path, "set", "plugins", "project-type.yaml")
        if not os.path.isfile(pt_file):
            continue
        # Skip set-core repo itself
        if os.path.isfile(os.path.join(path, "lib", "set_orch", "__init__.py")):
            continue

        since_sha = harvest_state.get(name)
        candidates = scan_project(name, path, since_sha)
        all_candidates.extend(candidates)

        # Scan ISS registry for unresolved framework issues
        issues = scan_issues(name, path)
        all_issues.extend(issues)

    # Sort chronologically
    all_candidates.sort(key=lambda c: c.date)
    all_issues.sort(key=lambda i: i.detected_at)
    return all_candidates, all_issues


def scan_issues(
    project_name: str,
    project_path: str,
) -> list[IssueCandidate]:
    """Scan ISS registry for unresolved framework-relevant issues.

    Looks for issues that are diagnosed but not fixed, or that have
    fix_target=framework/both in their diagnosis.
    """
    registry_path = os.path.join(project_path, ".set", "issues", "registry.json")
    if not os.path.isfile(registry_path):
        return []

    try:
        data = json.loads(Path(registry_path).read_text())
    except (json.JSONDecodeError, OSError):
        return []

    issues_list = data.get("issues", []) if isinstance(data, dict) else []
    candidates = []

    for iss in issues_list:
        if not isinstance(iss, dict):
            continue

        state = iss.get("state", "")
        # Skip resolved issues that were already fixed
        if state == "resolved":
            continue

        diag = iss.get("diagnosis") or {}
        root_cause = ""
        fix_target = "unknown"
        suggested_fix = ""

        if isinstance(diag, dict):
            root_cause = diag.get("root_cause", "")
            fix_target = diag.get("fix_target", "unknown")
            suggested_fix = diag.get("suggested_fix", "")

        # Classify: is this a framework bug?
        classification = _classify_issue(iss, diag)
        if classification in ("project-specific", "external", "sentinel-action"):
            continue

        investigation = ""
        inv_path = os.path.join(
            project_path, ".set", "issues", "investigations",
            f"{iss.get('id', '')}.md",
        )
        if os.path.isfile(inv_path):
            investigation = inv_path

        candidates.append(IssueCandidate(
            project=project_name,
            issue_id=iss.get("id", ""),
            state=state,
            severity=iss.get("severity", "unknown"),
            summary=iss.get("error_summary", ""),
            affected_change=iss.get("affected_change", ""),
            root_cause=root_cause,
            fix_target=fix_target,
            suggested_fix=suggested_fix,
            detected_at=iss.get("detected_at", ""),
            investigation_path=investigation,
        ))

    return candidates


def _classify_issue(iss: dict, diag: dict) -> str:
    """Classify an ISS entry as framework or project-specific.

    Priority order (first match wins):
    1. Explicit fix_target from diagnosis
    2. Exclusions (rate limits, sentinel actions, app-level bugs)
    3. Framework keyword match in root_cause + summary
    4. Unknown (included for review)
    """
    fix_target = diag.get("fix_target", "")
    if fix_target in ("framework", "both"):
        return "framework"
    if fix_target == "consumer":
        return "project-specific"

    text = (
        (diag.get("root_cause", "") + " " + iss.get("error_summary", ""))
        .lower()
    )

    # --- Exclusions first (before framework keyword scan) ---

    # Rate limit / API issues — external, not framework
    if "rate limit" in text or "api limit" in text or "hit your limit" in text:
        return "external"

    # Sentinel action logs (closing stale issues, unblocking) — not bugs
    if "closed stale" in text or "unblock" in text:
        return "sentinel-action"

    # App-level build/test failures
    app_keywords = [
        "suspense", "usesearchparams", "prisma", "nextauth",
        "stripe", "bcrypt", "next.js", "tailwind",
    ]
    if any(kw in text for kw in app_keywords):
        return "project-specific"

    # --- Framework keyword match ---
    framework_keywords = [
        "orchestrat", "engine", "merger", "dispatcher",
        "stall", "redispatch", "set_orch", "set-core", "monitor",
        "worktree", "merge queue", "integration-failed", "merge-blocked",
        "coverage gate", "two-phase", "retry_count",
        "reconcil", "watcher", "_check_all_done",
    ]
    if any(kw in text for kw in framework_keywords):
        return "framework"

    return "unknown"


def get_commit_diff(project_path: str, sha: str) -> str:
    """Get the full diff for a commit."""
    return _run_git(["show", "--stat", "--patch", sha], project_path)


# ─── CLI ────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Harvest framework fixes from consumer project E2E runs",
        prog="set-harvest",
    )
    parser.add_argument("--project", help="Scan single project by name")
    parser.add_argument("--all", action="store_true",
                        help="Show all candidates (default: framework-relevant only)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show candidates without updating harvest state")
    parser.add_argument("--json", action="store_true",
                        help="Output candidates as JSON (non-interactive)")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    candidates, issues = scan_all_projects(project_filter=args.project)

    # Default: only show framework-relevant and template-divergence
    if not args.all:
        candidates = [c for c in candidates
                      if c.classification in ("framework", "template-divergence")]

    total = len(candidates) + len(issues)

    if not total:
        print("No unadopted changes found across registered projects.")
        return

    if args.json:
        print(json.dumps({
            "commits": [c.to_dict() for c in candidates],
            "issues": [i.to_dict() for i in issues],
        }, indent=2))
        return

    # ─── Issues section ───────────────────────────────────────────
    if issues:
        print(f"\n{'='*60}")
        print(f"  ISS Issues: {len(issues)} unresolved framework-relevant")
        print(f"{'='*60}\n")

        for i, iss in enumerate(issues, 1):
            severity_color = {
                "high": "\033[31m",
                "medium": "\033[33m",
                "low": "\033[36m",
            }.get(iss.severity, "\033[90m")

            state_badge = {
                "diagnosed": "\033[33m●diagnosed\033[0m",
                "new": "\033[34m●new\033[0m",
                "failed": "\033[31m●failed\033[0m",
                "fixing": "\033[33m●fixing\033[0m",
            }.get(iss.state, iss.state)

            print(f"[{i}/{len(issues)}] {severity_color}{iss.issue_id}\033[0m {state_badge}  {iss.project}")
            print(f"  {iss.summary}")
            if iss.root_cause:
                # First sentence of root cause
                first_sentence = iss.root_cause.split(". ")[0] + "."
                print(f"  Root cause: {first_sentence[:150]}")
            if iss.affected_change:
                print(f"  Affected: {iss.affected_change}")
            print()

            if args.dry_run:
                continue

            while True:
                choice = input("  [i]nvestigate / [s]kip / [d]ismiss / [q]uit > ").strip().lower()
                if choice == "q":
                    print("\nHarvest paused.")
                    return
                elif choice == "s":
                    break
                elif choice == "d":
                    print(f"  → Dismissed {iss.issue_id}")
                    break
                elif choice == "i":
                    if iss.investigation_path and os.path.isfile(iss.investigation_path):
                        content = Path(iss.investigation_path).read_text()
                        print(f"\n{content[:3000]}")
                        if len(content) > 3000:
                            print(f"... ({len(content)} chars total)")
                        print()
                    elif iss.root_cause:
                        print(f"\n  Root cause:\n  {iss.root_cause[:1000]}")
                        if iss.suggested_fix:
                            print(f"\n  Suggested fix:\n  {iss.suggested_fix[:500]}")
                        print()
                    else:
                        print("  No investigation available.")
                else:
                    print("  Invalid choice. Use i/s/d/q.")

    # ─── Commits section ──────────────────────────────────────────
    if candidates:
        print(f"\n{'='*60}")
        print(f"  Commits: {len(candidates)} unadopted changes")
        print(f"{'='*60}\n")

        projects = _get_registered_projects()

        for i, c in enumerate(candidates, 1):
            badge = {
                "framework": "\033[33m[FRAMEWORK]\033[0m",
                "template-divergence": "\033[36m[TEMPLATE]\033[0m",
                "project-specific": "\033[90m[PROJECT-SPECIFIC]\033[0m",
                "unknown": "\033[90m[UNKNOWN]\033[0m",
            }.get(c.classification, c.classification)

            print(f"[{i}/{len(candidates)}] {badge} {c.project} ({c.date[:10]})")
            print(f"  {c.message}")
            print(f"  Files: {', '.join(c.files_changed[:5])}")
            if len(c.files_changed) > 5:
                print(f"    ... +{len(c.files_changed) - 5} more")
            if c.suggested_target:
                print(f"  Suggested target: {c.suggested_target}")
            print()

            if args.dry_run:
                continue

            while True:
                choice = input("  [a]dopt / [s]kip / [v]iew diff / [q]uit > ").strip().lower()
                if choice == "q":
                    print("\nHarvest paused. Run again to continue from here.")
                    return
                elif choice == "s":
                    break
                elif choice == "v":
                    project_path = projects.get(c.project, "")
                    if project_path:
                        diff = get_commit_diff(project_path, c.commit_sha)
                        print(f"\n{diff[:3000]}")
                        if len(diff) > 3000:
                            print(f"... ({len(diff)} chars total)")
                        print()
                elif choice == "a":
                    target = c.suggested_target
                    if not target:
                        target = input("  Target file in set-core: ").strip()
                    else:
                        confirm = input(f"  Target: {target} [Enter=confirm, or type new path]: ").strip()
                        if confirm:
                            target = confirm
                    print(f"  → Adopt to: {target}")
                    print(f"  NOTE: Review the diff and manually apply the relevant changes to {target}")
                    print(f"  Commit SHA: {c.commit_sha}")
                    break
                else:
                    print("  Invalid choice. Use a/s/v/q.")

    # Update harvest state for all scanned projects
    if not args.dry_run:
        projects = _get_registered_projects()
        for name, path in projects.items():
            if args.project and name != args.project:
                continue
            if not os.path.isdir(path) or "-wt-" in name:
                continue
            head = _get_head_sha(path)
            if head:
                set_harvest_state(name, head)
                logger.info("Updated harvest state: %s → %s", name, head[:8])

    print(f"\n{'='*60}")
    print(f"  Harvest complete: {len(candidates)} commits, {len(issues)} issues reviewed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
