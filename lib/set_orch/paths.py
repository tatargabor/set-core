"""Centralized runtime path resolution for set-core.

Two-tier architecture:
- Shared runtime: ~/.local/share/set-core/<project>/  (orchestration, sentinel, logs, cache)
- Per-agent ephemeral: <worktree>/.set/  (loop-state, activity, PID files)

Project name resolution matches the memory system (wt-memoryd/lifecycle.py).
"""

from __future__ import annotations

import os
import subprocess


# XDG-compliant base directory
_XDG_DATA_HOME = os.environ.get(
    "XDG_DATA_HOME",
    os.path.join(os.environ.get("HOME", ""), ".local", "share"),
)
SET_TOOLS_DATA_DIR = os.path.join(_XDG_DATA_HOME, "set-core")

# Backward compat: if old data dir exists but new one doesn't, use old
_LEGACY_DATA_DIR = os.path.join(_XDG_DATA_HOME, "wt-tools")
if not os.path.exists(SET_TOOLS_DATA_DIR) and os.path.exists(_LEGACY_DATA_DIR):
    import sys
    print("WARNING: Using legacy ~/.local/share/wt-tools/ — run migrate-to-set.sh", file=sys.stderr)
    SET_TOOLS_DATA_DIR = _LEGACY_DATA_DIR

# Per-worktree agent ephemeral directory name
AGENT_DIR_NAME = ".set"
_LEGACY_AGENT_DIR = ".wt"


def resolve_project_name(project_path: str | None = None) -> str:
    """Resolve git project name, handling worktrees.

    Matches the logic in bin/wt-memory::resolve_project() and
    lib/set_memoryd/lifecycle.py::resolve_project().

    For worktrees, resolves to the main repo name so all worktrees
    share the same runtime directory.
    """
    cwd = project_path or os.getcwd()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        if result.returncode != 0:
            return "_global"
        toplevel = result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return "_global"

    # Worktree detection: git-common-dir points to main repo's .git
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        common_dir = result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, OSError):
        common_dir = ""

    if common_dir and common_dir != ".git":
        # Worktree: resolve to main repo name
        abs_common = os.path.normpath(os.path.join(toplevel, common_dir))
        return os.path.basename(os.path.dirname(abs_common))

    return os.path.basename(toplevel)


class SetRuntime:
    """Resolves shared runtime paths under ~/.local/share/set-core/<project>/.

    Usage:
        rt = SetRuntime("/path/to/project")
        state = rt.state_file          # ~/.local/share/set-core/myproject/orchestration/state.json
        agent = rt.agent_dir("/path/to/worktree")  # /path/to/worktree/.wt
    """

    def __init__(self, project_path: str | None = None, project_name: str | None = None):
        """Initialize with project path or explicit project name.

        Args:
            project_path: Path to project (or worktree). Used to resolve project name.
            project_name: Explicit project name. Overrides project_path resolution.
        """
        self._project_name = project_name or resolve_project_name(project_path)
        self.root = os.path.join(SET_TOOLS_DATA_DIR, self._project_name)

    @property
    def project_name(self) -> str:
        return self._project_name

    # --- Orchestration ---

    @property
    def orchestration_dir(self) -> str:
        return os.path.join(self.root, "orchestration")

    @property
    def state_file(self) -> str:
        return os.path.join(self.orchestration_dir, "state.json")

    @property
    def events_file(self) -> str:
        return os.path.join(self.orchestration_dir, "events.jsonl")

    @property
    def plans_dir(self) -> str:
        return os.path.join(self.orchestration_dir, "plans")

    @property
    def runs_dir(self) -> str:
        return os.path.join(self.orchestration_dir, "runs")

    @property
    def digest_dir(self) -> str:
        return os.path.join(self.orchestration_dir, "digest")

    @property
    def spec_coverage_report(self) -> str:
        return os.path.join(self.orchestration_dir, "spec-coverage-report.md")

    @property
    def report_html(self) -> str:
        return os.path.join(self.orchestration_dir, "report.html")

    def audit_log(self, cycle: int) -> str:
        return os.path.join(self.orchestration_dir, f"audit-cycle-{cycle}.log")

    # --- Sentinel ---

    @property
    def sentinel_dir(self) -> str:
        return os.path.join(self.root, "sentinel")

    @property
    def sentinel_events_file(self) -> str:
        return os.path.join(self.sentinel_dir, "events.jsonl")

    @property
    def sentinel_findings_file(self) -> str:
        return os.path.join(self.sentinel_dir, "findings.json")

    @property
    def sentinel_status_file(self) -> str:
        return os.path.join(self.sentinel_dir, "status.json")

    @property
    def sentinel_inbox_file(self) -> str:
        return os.path.join(self.sentinel_dir, "inbox.jsonl")

    @property
    def sentinel_inbox_cursor(self) -> str:
        return os.path.join(self.sentinel_dir, "inbox.cursor")

    @property
    def sentinel_archive_dir(self) -> str:
        return os.path.join(self.sentinel_dir, "archive")

    @property
    def sentinel_pid_file(self) -> str:
        return os.path.join(self.sentinel_dir, "sentinel.pid")

    # --- Logs ---

    @property
    def logs_dir(self) -> str:
        return os.path.join(self.root, "logs")

    @property
    def orchestration_log(self) -> str:
        return os.path.join(self.logs_dir, "orchestration.log")

    def change_logs_dir(self, change_name: str) -> str:
        return os.path.join(self.logs_dir, "changes", change_name)

    # --- Screenshots ---

    @property
    def screenshots_dir(self) -> str:
        return os.path.join(self.root, "screenshots")

    def smoke_screenshots_dir(self, change_name: str) -> str:
        return os.path.join(self.screenshots_dir, "smoke", change_name)

    def e2e_screenshots_dir(self, cycle: int | str) -> str:
        return os.path.join(self.screenshots_dir, "e2e", f"cycle-{cycle}")

    # --- Cache ---

    @property
    def cache_dir(self) -> str:
        return os.path.join(self.root, "cache")

    @property
    def codemaps_cache_dir(self) -> str:
        return os.path.join(self.cache_dir, "codemaps")

    @property
    def designs_cache_dir(self) -> str:
        return os.path.join(self.cache_dir, "designs")

    @property
    def skill_invocations_dir(self) -> str:
        return os.path.join(self.cache_dir, "skill-invocations")

    @property
    def last_memory_commit_file(self) -> str:
        return os.path.join(self.cache_dir, "last-memory-commit")

    @property
    def credentials_dir(self) -> str:
        return os.path.join(self.cache_dir, "credentials")

    # --- Design ---

    @property
    def design_snapshot(self) -> str:
        return os.path.join(self.root, "design-snapshot.md")

    # --- Version ---

    @property
    def version_file(self) -> str:
        return os.path.join(self.root, "version")

    # --- Per-worktree agent ephemeral ---

    @staticmethod
    def agent_dir(worktree_path: str) -> str:
        """Per-agent ephemeral directory: <worktree>/.set/
        Falls back to legacy .set/ if it exists and .set/ doesn't."""
        new_path = os.path.join(worktree_path, AGENT_DIR_NAME)
        if not os.path.exists(new_path):
            legacy = os.path.join(worktree_path, _LEGACY_AGENT_DIR)
            if os.path.exists(legacy):
                return legacy
        return new_path

    @staticmethod
    def agent_loop_state(worktree_path: str) -> str:
        return os.path.join(worktree_path, AGENT_DIR_NAME, "loop-state.json")

    @staticmethod
    def agent_activity(worktree_path: str) -> str:
        return os.path.join(worktree_path, AGENT_DIR_NAME, "activity.json")

    @staticmethod
    def agent_pid_file(worktree_path: str) -> str:
        return os.path.join(worktree_path, AGENT_DIR_NAME, "ralph-terminal.pid")

    @staticmethod
    def agent_lock_file(worktree_path: str) -> str:
        return os.path.join(worktree_path, AGENT_DIR_NAME, "scheduled_tasks.lock")

    @staticmethod
    def agent_reflection(worktree_path: str) -> str:
        return os.path.join(worktree_path, AGENT_DIR_NAME, "reflection.md")

    @staticmethod
    def agent_logs_dir(worktree_path: str) -> str:
        return os.path.join(worktree_path, AGENT_DIR_NAME, "logs")

    # --- Directory creation ---

    def ensure_dirs(self) -> None:
        """Create all shared runtime directories."""
        for d in [
            self.orchestration_dir,
            self.plans_dir,
            self.runs_dir,
            self.digest_dir,
            self.sentinel_dir,
            self.sentinel_archive_dir,
            self.logs_dir,
            self.screenshots_dir,
            self.cache_dir,
            self.codemaps_cache_dir,
            self.designs_cache_dir,
            self.skill_invocations_dir,
            self.credentials_dir,
        ]:
            os.makedirs(d, exist_ok=True)

    @staticmethod
    def ensure_agent_dir(worktree_path: str) -> str:
        """Create per-agent ephemeral directory and its subdirs.

        Also ensures /.set/ is in the worktree's .gitignore.
        Returns the agent directory path.
        """
        agent_path = os.path.join(worktree_path, AGENT_DIR_NAME)
        os.makedirs(agent_path, exist_ok=True)

        logs_path = os.path.join(agent_path, "logs")
        os.makedirs(logs_path, exist_ok=True)

        _ensure_gitignore(worktree_path)
        return agent_path


def _ensure_gitignore(project_path: str) -> None:
    """Append /.set/ to .gitignore if not already present."""
    gitignore_entry = "/.set/"
    gitignore_path = os.path.join(project_path, ".gitignore")

    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            content = f.read()
        if gitignore_entry in content:
            return
        if content and not content.endswith("\n"):
            content += "\n"
    else:
        content = ""

    with open(gitignore_path, "a") as f:
        if not content:
            f.write(f"# set-core agent runtime directory\n{gitignore_entry}\n")
        else:
            f.write(f"\n# set-core agent runtime directory\n{gitignore_entry}\n")
