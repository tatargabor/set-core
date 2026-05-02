"""Centralized runtime path resolution for set-core.

Two-tier architecture:
- Shared runtime: ~/.local/share/set-core/<project>/  (orchestration, sentinel, logs, cache)
- Per-agent ephemeral: <worktree>/.set/  (loop-state, activity, PID files)

Project name resolution matches the memory system (set_memoryd/lifecycle.py).

Lineage-aware resolution (`LineagePaths`) layers on top of `SetRuntime` to
provide per-lineage views of the orchestration history while keeping the
"live" lineage's filenames unchanged.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Optional

from set_orch.types import LineageId, slug

logger = logging.getLogger(__name__)


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

    Matches the logic in bin/set-memory::resolve_project() and
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
        agent = rt.agent_dir("/path/to/worktree")  # /path/to/worktree/.set
    """

    def __init__(self, project_path: str | None = None, project_name: str | None = None):
        """Initialize with project path or explicit project name.

        Args:
            project_path: Path to project (or worktree). Used to resolve project name.
            project_name: Explicit project name. Overrides project_path resolution.
        """
        self._project_name = project_name or resolve_project_name(project_path)
        self.root = os.path.join(SET_TOOLS_DATA_DIR, "runtime", self._project_name)

        # Auto-migrate legacy runtime dir (pre-runtime/ subdirectory)
        old_root = os.path.join(SET_TOOLS_DATA_DIR, self._project_name)
        if os.path.isdir(old_root) and not os.path.isdir(self.root):
            import shutil
            os.makedirs(os.path.dirname(self.root), exist_ok=True)
            try:
                shutil.move(old_root, self.root)
            except OSError:
                pass  # Migration best-effort; old path still works

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


def append_jsonl(path: str, record: dict) -> None:
    """Append a single JSON record as one line to ``path``.

    POSIX guarantees atomic writes for ``< PIPE_BUF`` (typically 4096)
    bytes when a file is opened with ``O_APPEND``, so concurrent
    appenders interleave at line boundaries rather than corrupting each
    other's records. Records exceeding PIPE_BUF can theoretically tear,
    but our category-resolver records run ~500–800 bytes so this is
    safe in practice.

    The parent directory is created on demand. The file is closed
    immediately after the write so no fd leaks if the caller is in a
    long-running loop.
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":"), default=str) + "\n")


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


# ---------------------------------------------------------------------------
# Lineage-aware path resolver
# ---------------------------------------------------------------------------


class LineagePaths:
    """Per-lineage view of the orchestration filesystem.

    Construction:
        LineagePaths(project_path, lineage_id="docs/spec-v1.md")
        LineagePaths(project_path)  # implicit live lineage

    A `LineagePaths` instance is read-only: every property returns a path
    string, never a file handle.  When the requested lineage is the live
    lineage (or `lineage_id is None`), live filenames are returned
    (`orchestration-plan.json`, `digest/`, …).  Otherwise the slug-suffixed
    sibling is returned (`orchestration-plan-<slug>.json`, `digest-<slug>/`,
    …) IF it exists on disk; if it does not exist the resolver falls back
    to the live path and emits a DEBUG log so callers stay observable.

    The "live" determination is driven by `state.spec_lineage_id` written
    into `state.json` at sentinel start.  Callers that want to bypass the
    fallback (e.g., the API layer that needs to return `unavailable` rather
    than live data) should check `is_live` and `lineage_specific_exists()`
    explicitly before reading.
    """

    def __init__(
        self,
        project_path: str,
        lineage_id: Optional[LineageId] = None,
        runtime: Optional[SetRuntime] = None,
    ) -> None:
        self.project_path = os.path.abspath(project_path)
        self.lineage_id: Optional[LineageId] = lineage_id
        self._runtime = runtime or SetRuntime(self.project_path)
        self._slug: Optional[str] = slug(lineage_id) if lineage_id else None

    # ---- lineage classification -------------------------------------------

    @property
    def runtime(self) -> SetRuntime:
        return self._runtime

    @property
    def slug(self) -> Optional[str]:
        return self._slug

    @property
    def is_live(self) -> bool:
        """True when this resolver targets the lineage that is currently live.

        Reads the persisted `state.spec_lineage_id` from `state.json`.  If
        no lineage was provided, treats the resolver as live (the typical
        callsite).  If state.json is missing or corrupt, returns False so
        callers do not silently overwrite an unknown other lineage.
        """
        if self.lineage_id is None:
            return True
        state = self._read_state()
        return state.get("spec_lineage_id") == self.lineage_id

    def _read_state(self) -> dict:
        try:
            with open(self._runtime.state_file, "r") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _resolve(self, live_path: str, slugged_path: str) -> str:
        """Pick `slugged_path` for non-live lineages when it exists, else live.

        Logs at DEBUG when falling back so we can audit silently-missing
        lineage-specific files in production logs.
        """
        if self.is_live:
            return live_path
        if os.path.exists(slugged_path):
            return slugged_path
        logger.debug(
            "LineagePaths fallback: %s missing for lineage=%s — using live %s",
            slugged_path,
            self.lineage_id,
            live_path,
        )
        return live_path

    def _slugged(self, base_dir: str, stem: str, suffix: str) -> str:
        if not self._slug:
            return os.path.join(base_dir, f"{stem}{suffix}")
        return os.path.join(base_dir, f"{stem}-{self._slug}{suffix}")

    # ---- shorthand for external callers ------------------------------------

    @property
    def orchestration_dir(self) -> str:
        return self._runtime.orchestration_dir

    # ---- core orchestration files (in shared runtime dir) ------------------

    @property
    def state_file(self) -> str:
        # state.json is the single live state.  Lineage-specific historic
        # snapshots are inside `state-archive.jsonl`, not as siblings.
        return self._runtime.state_file

    @property
    def state_archive(self) -> str:
        # state-archive.jsonl is append-only; entries are tagged with
        # spec_lineage_id and filtered at read time.  No per-lineage copy.
        return os.path.join(self._runtime.orchestration_dir, "state-archive.jsonl")

    @property
    def plan_file(self) -> str:
        live = os.path.join(self._runtime.orchestration_dir, "orchestration-plan.json")
        slugged = self._slugged(self._runtime.orchestration_dir, "orchestration-plan", ".json")
        return self._resolve(live, slugged)

    @property
    def plan_domains_file(self) -> str:
        live = os.path.join(
            self._runtime.orchestration_dir, "orchestration-plan-domains.json"
        )
        slugged = self._slugged(
            self._runtime.orchestration_dir, "orchestration-plan-domains", ".json"
        )
        return self._resolve(live, slugged)

    @property
    def events_file(self) -> str:
        """Live event stream — primary source for the API and state reconstruction.

        Contains STATE_CHANGE, GATE_*, MERGE_*, LLM_CALL, ITERATION_END,
        WATCHDOG_HEARTBEAT, MONITOR_HEARTBEAT, and most lifecycle events.
        Readers also enumerate `rotated_event_files` to pick up older cycles.
        See spec `events-api`.
        """
        return os.path.join(
            self._runtime.orchestration_dir, "orchestration-events.jsonl"
        )

    @property
    def state_events_file(self) -> str:
        """Narrow event stream — back-compat source for forensics and migrations.

        Currently receives DIGEST_*, MEMORY_HYGIENE, SHUTDOWN_*,
        CHANGE_STOPPING/STOPPED. Readers should prefer `events_file`; this
        path is retained as a fallback for older runs and bash-side tooling.
        """
        return os.path.join(
            self._runtime.orchestration_dir, "orchestration-state-events.jsonl"
        )

    @property
    def rotated_event_files(self) -> list[str]:
        """All `orchestration-events-cycle*.jsonl` siblings, sorted ascending."""
        import glob

        pattern = os.path.join(
            self._runtime.orchestration_dir, "orchestration-events-cycle*.jsonl"
        )
        return sorted(glob.glob(pattern), key=_cycle_sort_key)

    @property
    def rotated_state_event_files(self) -> list[str]:
        import glob

        pattern = os.path.join(
            self._runtime.orchestration_dir,
            "orchestration-state-events-cycle*.jsonl",
        )
        return sorted(glob.glob(pattern), key=_cycle_sort_key)

    @property
    def digest_dir(self) -> str:
        # The digest tree is decomposed under the project tree, not the
        # SetRuntime runtime dir — planner.py / engine.py / api code all
        # write to `<project>/set/orchestration/digest/`.  Per-lineage
        # siblings (`digest-<slug>/`) live next to the live `digest/`.
        project_orch = os.path.join(
            self.project_path, "set", "orchestration",
        )
        live = os.path.join(project_orch, "digest")
        if not self._slug:
            return live
        slugged = os.path.join(project_orch, f"digest-{self._slug}")
        if self.is_live:
            return live
        if os.path.isdir(slugged):
            return slugged
        logger.debug(
            "LineagePaths fallback: digest dir %s missing for lineage=%s — using live %s",
            slugged,
            self.lineage_id,
            live,
        )
        return live

    @property
    def coverage_report(self) -> str:
        # spec-coverage-report.md lives inside the project under
        # set/orchestration/ (planner.py writes it relative to cwd).
        return os.path.join(
            self.project_path, "set", "orchestration", "spec-coverage-report.md"
        )

    @property
    def coverage_history(self) -> str:
        return os.path.join(
            self.project_path, "set", "orchestration", "spec-coverage-history.jsonl"
        )

    @property
    def e2e_manifest_history(self) -> str:
        return os.path.join(
            self.project_path, "set", "orchestration", "e2e-manifest-history.jsonl"
        )

    @property
    def worktrees_history(self) -> str:
        return os.path.join(
            self.project_path, "set", "orchestration", "worktrees-history.json"
        )

    @property
    def directives_file(self) -> str:
        return os.path.join(
            self.project_path, "set", "orchestration", "directives.json"
        )

    @property
    def config_yaml(self) -> str:
        return os.path.join(
            self.project_path, "set", "orchestration", "config.yaml"
        )

    @property
    def review_learnings(self) -> str:
        return os.path.join(
            self.project_path, "set", "orchestration", "review-learnings.jsonl"
        )

    @property
    def review_findings(self) -> str:
        return os.path.join(
            self.project_path, "set", "orchestration", "review-findings.jsonl"
        )

    @property
    def specs_archive_dir(self) -> str:
        return os.path.join(self.project_path, "openspec", "changes", "archive")

    # ---- supervisor / sentinel ---------------------------------------------

    @property
    def supervisor_status(self) -> str:
        return os.path.join(self.project_path, ".set", "supervisor", "status.json")

    @property
    def supervisor_status_history(self) -> str:
        return os.path.join(
            self.project_path, ".set", "supervisor", "status-history.jsonl"
        )

    # ---- issues registry ---------------------------------------------------

    @property
    def issues_registry(self) -> str:
        return os.path.join(self.project_path, ".set", "issues", "registry.json")

    # ---- category resolver state ------------------------------------------

    @property
    def category_classifications(self) -> str:
        """Append-only audit log of every category-resolver invocation.

        One JSON line per dispatch (cache hit, cache miss, or LLM
        failure). Read by ``insights.py`` for project-insights
        aggregation and by the resolver itself for cache lookups.

        Lives under ``.set/state/`` (per-worktree ephemeral state)
        because classifications are derived from the worktree's scope
        and depend on the worktree's project state — they are NOT a
        cross-worktree shared resource.
        """
        return os.path.join(
            self.project_path, ".set", "state", "category-classifications.jsonl"
        )

    @property
    def project_insights(self) -> str:
        """Aggregated project-level category trends, rewritten after
        every successful change merge.

        Schema documented in
        ``openspec/specs/project-insights-aggregator/spec.md``.
        Consumed by:

        - ``category_resolver.resolve_change_categories`` as a bias for
          deterministic detection (seeds ``common_categories`` for the
          current change_type)
        - The Sonnet prompt as a one-paragraph project-context summary

        Lives under ``.set/state/`` next to ``category-classifications
        .jsonl`` (same write-domain).
        """
        return os.path.join(
            self.project_path, ".set", "state", "project-insights.json"
        )

    # ---- per-worktree / per-change resolvers -------------------------------

    @staticmethod
    def e2e_manifest_for_worktree(worktree_path: str) -> str:
        return os.path.join(worktree_path, "e2e-manifest.json")

    @staticmethod
    def reflection_for_worktree(worktree_path: str) -> str:
        return os.path.join(worktree_path, ".set", "reflection.md")

    def artifacts_dir_for_change(self, change_name: str) -> str:
        return os.path.join(
            self.project_path, "openspec", "changes", change_name
        )

    # ---- introspection -----------------------------------------------------

    def slugged_path(self, *, kind: str) -> str:
        """Return the slug-suffixed sibling for `kind` regardless of existence.

        Used by writers (e.g. the rotation routine) that need to construct
        the slugged destination path before the file/dir is created.
        Falls back to the live filename when the resolver targets the
        live lineage — in which case slugging is a no-op.

        Supported `kind` values: `plan_file`, `plan_domains_file`,
        `digest_dir`.
        """
        if not self._slug:
            # Live lineage — no slug to apply.
            return getattr(self, kind)
        orch = self._runtime.orchestration_dir
        if kind == "plan_file":
            return self._slugged(orch, "orchestration-plan", ".json")
        if kind == "plan_domains_file":
            return self._slugged(orch, "orchestration-plan-domains", ".json")
        if kind == "digest_dir":
            project_orch = os.path.join(self.project_path, "set", "orchestration")
            return os.path.join(project_orch, f"digest-{self._slug}")
        raise ValueError(f"slugged_path: unknown kind {kind!r}")

    def lineage_specific_exists(self, attr: str) -> bool:
        """Return True iff the requested property's slugged copy exists.

        Useful for API endpoints that must distinguish between "no data"
        and "fell back to the live lineage's data".
        """
        if not self._slug:
            return True  # live lineage always "exists"
        # Re-derive the slugged path WITHOUT going through fallback resolution.
        if attr in ("plan_file",):
            return os.path.exists(
                self._slugged(self._runtime.orchestration_dir, "orchestration-plan", ".json")
            )
        if attr in ("plan_domains_file",):
            return os.path.exists(
                self._slugged(
                    self._runtime.orchestration_dir,
                    "orchestration-plan-domains",
                    ".json",
                )
            )
        if attr == "digest_dir":
            return os.path.isdir(
                os.path.join(
                    self.project_path, "set", "orchestration",
                    f"digest-{self._slug}",
                )
            )
        # All other paths are append-only / lineage-tagged at write time.
        return True

    # ---- migration helper --------------------------------------------------

    @classmethod
    def from_state_file(
        cls, state_file: str, project_path: Optional[str] = None,
    ) -> "LineagePaths":
        """Build a LineagePaths from a known `state.json` path.

        The orchestration_dir is taken to be `dirname(state_file)` —
        canonical SetRuntime layout uses `~/.../runtime/<proj>/orchestration/
        state.json`, but this classmethod also tolerates non-canonical
        test layouts where state.json sits at an arbitrary directory.

        Callers that ALSO need project-relative paths (set/orchestration/,
        .set/) should pass `project_path` so those properties resolve to
        the right place.

        Lineage attribution is read from the state file itself.
        """
        orch_dir = os.path.dirname(os.path.abspath(state_file))
        runtime_root = os.path.dirname(orch_dir)
        project_name = os.path.basename(runtime_root) or "_local"

        # Build a SetRuntime-equivalent object whose `orchestration_dir`
        # resolves to the actual parent of state.json regardless of the
        # canonical layout.  We achieve this by setting `root` to a value
        # that, combined with the SetRuntime property formula
        # `root + "/orchestration"`, yields `orch_dir`.
        rt = _StateAnchoredRuntime(project_name=project_name, orch_dir=orch_dir)

        live_lineage: Optional[str] = None
        try:
            with open(state_file, "r") as fh:
                state = json.load(fh)
            live_lineage = state.get("spec_lineage_id")
        except (OSError, json.JSONDecodeError):
            pass

        return cls(
            project_path or runtime_root,
            lineage_id=LineageId(live_lineage) if live_lineage else None,
            runtime=rt,
        )

    @classmethod
    def from_project(cls, project_path: str) -> "LineagePaths":
        """Resolve the live lineage from disk and return a bound resolver.

        Callers that have not yet been migrated to thread `lineage_id` end
        up here.  We log at WARNING so the residual call sites remain
        visible while migration is in progress.
        """
        rt = SetRuntime(project_path)
        try:
            with open(rt.state_file, "r") as fh:
                state = json.load(fh)
            live_lineage = state.get("spec_lineage_id")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            live_lineage = None
        logger.warning(
            "LineagePaths.from_project called without explicit lineage_id "
            "(project=%s, live_lineage=%s) — caller should be migrated to "
            "pass lineage_id explicitly",
            project_path,
            live_lineage,
        )
        return cls(
            project_path,
            lineage_id=LineageId(live_lineage) if live_lineage else None,
            runtime=rt,
        )


class _StateAnchoredRuntime(SetRuntime):
    """SetRuntime variant whose `orchestration_dir` is forced to a given path.

    Used by `LineagePaths.from_state_file` so callers that pass a
    `state.json` outside the canonical `runtime/<proj>/orchestration/`
    layout (e.g., test fixtures placing state.json at the project root)
    still get correctly-relative sibling paths.
    """

    def __init__(self, project_name: str, orch_dir: str) -> None:
        # Skip SetRuntime.__init__'s legacy-migration logic — we already
        # know exactly where orchestration files live.
        self._project_name = project_name
        self.root = os.path.dirname(orch_dir)
        self._orch_dir_override = orch_dir

    @property
    def orchestration_dir(self) -> str:  # type: ignore[override]
        return self._orch_dir_override


def _cycle_sort_key(path: str) -> tuple:
    """Sort `*-cycleN.jsonl` siblings by their integer cycle id.

    Files without a parseable cycle suffix sort first, in path order, so
    surprising names do not silently disappear from the iteration.
    """
    base = os.path.basename(path)
    # Pull the digit run between '-cycle' and '.jsonl'
    import re as _re

    m = _re.search(r"-cycle(\d+)\.", base)
    if not m:
        return (0, base)
    return (1, int(m.group(1)))
