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

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "commit_sha": self.commit_sha,
            "date": self.date,
            "message": self.message,
            "files_changed": self.files_changed,
            "classification": self.classification,
            "suggested_target": self.suggested_target,
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
) -> list[HarvestCandidate]:
    """Scan all registered projects for unadopted changes.

    Returns candidates sorted chronologically across all projects.
    """
    projects = _get_registered_projects()
    if not projects:
        logger.warning("No registered projects found")
        return []

    all_candidates = []
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

    # Sort chronologically
    all_candidates.sort(key=lambda c: c.date)
    return all_candidates


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

    candidates = scan_all_projects(project_filter=args.project)

    # Default: only show framework-relevant and template-divergence
    if not args.all:
        candidates = [c for c in candidates
                      if c.classification in ("framework", "template-divergence")]

    if not candidates:
        print("No unadopted changes found across registered projects.")
        return

    if args.json:
        print(json.dumps([c.to_dict() for c in candidates], indent=2))
        return

    # Interactive presentation
    print(f"\n{'='*60}")
    print(f"  Harvest: {len(candidates)} unadopted changes found")
    print(f"{'='*60}\n")

    projects = _get_registered_projects()

    for i, c in enumerate(candidates, 1):
        # Classification badge
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

        # Interactive prompt
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
    print(f"  Harvest complete: {len(candidates)} changes reviewed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
