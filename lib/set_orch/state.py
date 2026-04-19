"""Typed JSON state management for orchestration engine.

Replaces complex jq pipelines with Python dataclasses. Provides atomic file
operations and validation on read/write. Phase 2 adds mutations, locking,
dependency graph, phase management, and crash recovery.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import subprocess
import tempfile
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Generator, Optional

if TYPE_CHECKING:
    from .events import EventBus

logger = logging.getLogger(__name__)


_JOURNALED_FIELDS: frozenset[str] = frozenset(
    {
        "build_result",
        "test_result",
        "e2e_result",
        "smoke_result",
        "review_result",
        "scope_check_result",
        "rules_result",
        "e2e_coverage_result",
        "build_output",
        "test_output",
        "e2e_output",
        "smoke_output",
        "review_output",
        "scope_check_output",
        "rules_output",
        "e2e_coverage_output",
        "gate_build_ms",
        "gate_test_ms",
        "gate_e2e_ms",
        "gate_review_ms",
        "gate_smoke_ms",
        "gate_scope_check_ms",
        "gate_rules_ms",
        "gate_e2e_coverage_ms",
        "retry_context",
        "status",
        "current_step",
    }
)

_JOURNAL_SEQ_CACHE: dict[str, int] = {}


def _journal_path(state_file: str, change_name: str) -> str:
    return os.path.join(os.path.dirname(state_file), "journals", f"{change_name}.jsonl")


def _seed_seq_from_file(path: str) -> int:
    """Read the last JSONL line of an existing journal and extract its `seq`.

    The process-local cache resets on daemon restart. Without re-seeding
    from disk the new process would start at seq=1 and collide with
    entries written by the previous process lifetime, corrupting the
    journal-reader's seq-based ordering.
    """
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size == 0:
                return 0
            read_size = min(size, 4096)
            f.seek(size - read_size)
            chunk = f.read(read_size)
        text = chunk.decode("utf-8", errors="replace")
        last = text.rstrip("\n").rsplit("\n", 1)[-1].strip()
        if not last:
            return 0
        entry = json.loads(last)
        seq = entry.get("seq", 0)
        return int(seq) if isinstance(seq, (int, float)) else 0
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return 0


def _append_journal(
    state_file: str,
    change_name: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
) -> None:
    path = _journal_path(state_file, change_name)
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)

    if path not in _JOURNAL_SEQ_CACHE:
        _JOURNAL_SEQ_CACHE[path] = _seed_seq_from_file(path)
    seq = _JOURNAL_SEQ_CACHE[path] + 1
    _JOURNAL_SEQ_CACHE[path] = seq

    # Local-with-offset per eccdbea8 timestamp unification — journal
    # entries are surfaced in the UI alongside event-stream timestamps
    # and must use the same format to sort correctly as strings.
    entry = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
        "field": field_name,
        "old": old_value,
        "new": new_value,
        "seq": seq,
    }

    try:
        line = json.dumps(entry, ensure_ascii=False)
    except (TypeError, ValueError):
        try:
            line = json.dumps(entry, default=str, ensure_ascii=False)
        except (TypeError, ValueError, UnicodeEncodeError):
            sanitized = {
                "ts": entry["ts"],
                "field": field_name,
                "old": repr(old_value),
                "new": repr(new_value),
                "seq": seq,
            }
            line = json.dumps(sanitized, ensure_ascii=True)

    data = (line + "\n").encode("utf-8", errors="replace")

    with open(path, "ab") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(data)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class StateCorruptionError(Exception):
    """Raised when state JSON is invalid or structurally corrupt."""

    def __init__(self, path: str, detail: str):
        self.path = path
        self.detail = detail
        super().__init__(f"Corrupt state at {path}: {detail}")


@dataclass
class WatchdogState:
    """Per-change watchdog tracking state."""

    last_activity_epoch: int = 0
    action_hash_ring: list[str] = field(default_factory=list)
    consecutive_same_hash: int = 0
    escalation_level: int = 0
    progress_baseline: int = 0
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "last_activity_epoch": self.last_activity_epoch,
            "action_hash_ring": self.action_hash_ring,
            "consecutive_same_hash": self.consecutive_same_hash,
            "escalation_level": self.escalation_level,
            "progress_baseline": self.progress_baseline,
        }
        d.update(self.extras)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> WatchdogState:
        known = {f.name for f in fields(cls) if f.name != "extras"}
        kwargs = {k: v for k, v in data.items() if k in known}
        extras = {k: v for k, v in data.items() if k not in known}
        return cls(**kwargs, extras=extras)


@dataclass
class Change:
    """A single change in the orchestration state."""

    # From plan (always present)
    name: str = ""
    scope: str = ""
    complexity: str = "M"
    change_type: str = "feature"
    depends_on: list[str] = field(default_factory=list)
    roadmap_item: str = ""
    model: Optional[str] = None
    skip_review: bool = False
    skip_test: bool = False
    has_manual_tasks: bool = False
    phase: int = 1
    gate_hints: Optional[dict] = None

    # Runtime state
    status: str = "pending"
    worktree_path: Optional[str] = None
    ralph_pid: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Token tracking
    tokens_used: int = 0
    tokens_used_prev: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_create_tokens: int = 0
    input_tokens_prev: int = 0
    output_tokens_prev: int = 0
    cache_read_tokens_prev: int = 0
    cache_create_tokens_prev: int = 0

    # Lifecycle step tracking
    current_step: Optional[str] = None  # planning, implementing, fixing, integrating, merging, archiving, done

    # Verification results
    test_result: Optional[str] = None
    test_stats: Optional[dict] = None
    smoke_result: Optional[str] = None
    smoke_stats: Optional[dict] = None
    e2e_result: Optional[str] = None
    review_result: Optional[str] = None
    build_result: Optional[str] = None

    # Gate output logs (last 2000 chars for display)
    build_output: Optional[str] = None
    test_output: Optional[str] = None
    e2e_output: Optional[str] = None

    # Screenshot tracking
    smoke_screenshot_dir: str = ""
    smoke_screenshot_count: int = 0
    e2e_screenshot_dir: str = ""
    e2e_screenshot_count: int = 0

    # Retry tracking
    verify_retry_count: int = 0
    redispatch_count: int = 0
    merge_retry_count: int = 0

    # Context window metrics (optional — absent on old state files)
    context_tokens_start: Optional[int] = None  # cache_create_tokens after iteration 1
    context_tokens_end: Optional[int] = None    # total_cache_create at loop completion
    context_breakdown_start: Optional[dict] = None  # {base_context, memory_injection, prompt_overhead, tool_output} from iter 1

    # Gate timings (ms)
    gate_test_ms: int = 0
    gate_review_ms: int = 0
    gate_build_ms: int = 0
    gate_verify_ms: int = 0
    gate_e2e_ms: int = 0
    gate_total_ms: int = 0

    # Optional fields from plan
    requirements: Optional[list] = None
    also_affects_reqs: Optional[list] = None

    # Lineage + sentinel-session attribution (additive; old states load with None).
    # `spec_lineage_id` survives replan and same-spec restart so historic entries
    # remain queryable; `sentinel_session_id` survives replan but is regenerated
    # at every fresh sentinel start so individual sessions stay distinguishable.
    spec_lineage_id: Optional[str] = None
    sentinel_session_id: Optional[str] = None
    sentinel_session_started_at: Optional[str] = None

    # Watchdog state (nested)
    watchdog: Optional[WatchdogState] = None

    # Catch-all for unknown fields
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {}
        for f in fields(self):
            if f.name == "extras":
                continue
            val = getattr(self, f.name)
            if f.name == "watchdog" and val is not None:
                d["watchdog"] = val.to_dict()
            elif val is not None or f.name in (
                "worktree_path", "ralph_pid", "started_at", "completed_at",
                "current_step",
                "test_result", "test_stats", "smoke_result", "smoke_stats",
                "e2e_result", "review_result", "build_result",
                "build_output", "test_output", "e2e_output", "model",
            ):
                d[f.name] = val
            elif f.name not in (
                "requirements", "also_affects_reqs", "watchdog", "gate_hints",
                "spec_lineage_id", "sentinel_session_id", "sentinel_session_started_at",
            ):
                d[f.name] = val
        # Omit None-valued optional fields that weren't in the original
        if self.requirements is not None:
            d["requirements"] = self.requirements
        if self.also_affects_reqs is not None:
            d["also_affects_reqs"] = self.also_affects_reqs
        if self.gate_hints is not None:
            d["gate_hints"] = self.gate_hints
        if self.spec_lineage_id is not None:
            d["spec_lineage_id"] = self.spec_lineage_id
        if self.sentinel_session_id is not None:
            d["sentinel_session_id"] = self.sentinel_session_id
        if self.sentinel_session_started_at is not None:
            d["sentinel_session_started_at"] = self.sentinel_session_started_at
        d.update(self.extras)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Change:
        known = {f.name for f in fields(cls) if f.name != "extras"}
        kwargs = {}
        extras = {}
        for k, v in data.items():
            if k == "watchdog" and isinstance(v, dict):
                kwargs["watchdog"] = WatchdogState.from_dict(v)
            elif k in known:
                kwargs[k] = v
            else:
                extras[k] = v
        if extras:
            _name = kwargs.get("name", "?")
            _seen = getattr(cls, "_extras_logged", set())
            if _name not in _seen:
                logger.debug("Change %s: %d unknown fields in extras: %s", _name, len(extras), list(extras.keys()))
                _seen.add(_name)
                cls._extras_logged = _seen
        return cls(**kwargs, extras=extras)


@dataclass
class TokenStats:
    """Aggregated token statistics."""

    total: int = 0
    input_total: int = 0
    output_total: int = 0
    cache_read_total: int = 0
    cache_create_total: int = 0


@dataclass
class OrchestratorState:
    """Top-level orchestration state."""

    plan_version: int = 1
    brief_hash: str = ""
    plan_phase: str = "initial"
    plan_method: str = "api"
    status: str = "running"
    created_at: str = ""
    changes: list[Change] = field(default_factory=list)
    checkpoints: list[dict] = field(default_factory=list)
    merge_queue: list[str] = field(default_factory=list)
    changes_since_checkpoint: int = 0
    cycle_started_at: Optional[str] = None
    last_smoke_pass_commit: str = ""

    # Lineage attribution — `spec_lineage_id` is the canonical project-relative
    # POSIX path of the `--spec` file the sentinel was last started with.
    # `sentinel_session_id` is a fresh hex token at every sentinel start; it
    # survives mid-session replan so all changes a session produced share an id.
    spec_lineage_id: Optional[str] = None
    sentinel_session_id: Optional[str] = None
    sentinel_session_started_at: Optional[str] = None

    # Catch-all for unknown fields (directives, replan_cycle, etc.)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {}
        for f in fields(self):
            if f.name == "extras":
                continue
            val = getattr(self, f.name)
            if f.name == "changes":
                d["changes"] = [c.to_dict() for c in val]
            else:
                d[f.name] = val
        d.update(self.extras)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> OrchestratorState:
        known = {f.name for f in fields(cls) if f.name != "extras"}
        kwargs = {}
        extras = {}
        for k, v in data.items():
            if k == "changes" and isinstance(v, list):
                kwargs["changes"] = [Change.from_dict(c) for c in v]
            elif k in known:
                kwargs[k] = v
            else:
                extras[k] = v
        return cls(**kwargs, extras=extras)


def load_state(path: str) -> OrchestratorState:
    """Load and validate orchestration state from JSON file.

    Raises StateCorruptionError on invalid/corrupt JSON or missing required fields.
    """
    try:
        with open(path, "r") as f:
            raw = f.read()
    except OSError as e:
        raise StateCorruptionError(path, f"cannot read file: {e}")

    if not raw.strip():
        raise StateCorruptionError(path, "file is empty")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise StateCorruptionError(path, f"invalid JSON: {e}")

    if not isinstance(data, dict):
        raise StateCorruptionError(path, f"expected object, got {type(data).__name__}")

    if "changes" not in data:
        raise StateCorruptionError(path, "missing required field: changes")

    if not isinstance(data["changes"], list):
        raise StateCorruptionError(path, "changes must be an array")

    return OrchestratorState.from_dict(data)


def _lock_path(state_path: str) -> str:
    """Return the advisory lock file path for a state file."""
    return os.path.abspath(state_path) + ".lock"


def save_state(state: OrchestratorState, path: str) -> None:
    """Serialize state to JSON and write atomically under flock.

    Migrated from: state.sh save via with_state_lock + safe_jq_update.
    Uses fcntl.flock advisory lock + tempfile/rename for atomic writes.
    """
    data = state.to_dict()
    content = json.dumps(data, indent=2) + "\n"

    if len(content.strip()) < 2:  # at minimum "{}"
        raise ValueError("save_state: serialized state is empty")

    dir_path = os.path.dirname(os.path.abspath(path))
    lock_file = _lock_path(path)

    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.rename(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


@contextmanager
def locked_state(path: str) -> Generator[OrchestratorState, None, None]:
    """Context manager: load state under flock, yield for modification, save on exit.

    Usage:
        with locked_state(runtime.state_file) as state:
            state.status = "stopped"
        # state saved atomically, lock released

    Migrated from: state.sh with_state_lock pattern.
    """
    lock_file = _lock_path(path)
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        logger.debug("State lock acquired: %s", path)
        state = load_state(path)
        yield state
        # Save without re-acquiring lock (we already hold it)
        data = state.to_dict()
        content = json.dumps(data, indent=2) + "\n"
        if len(content.strip()) < 2:
            raise ValueError("locked_state: serialized state is empty")
        dir_path = os.path.dirname(os.path.abspath(path))
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.rename(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        logger.debug("State lock released: %s", path)
        lock_fd.close()


def init_state(
    plan_file: str,
    output_path: str,
    spec_path: Optional[str] = None,
    project_path: Optional[str] = None,
    sentinel_session_id: Optional[str] = None,
) -> None:
    """Initialize orchestration state from a plan file.

    Replaces the 40-line jq filter in state.sh init_state().

    Lineage attribution (`spec_lineage_id`, `sentinel_session_id`,
    `sentinel_session_started_at`) is captured here so every change born of
    this plan inherits it.  When `spec_path` is omitted we fall back to the
    plan's persisted `input_path`; when neither is available the state is
    created without lineage attribution and a WARNING is logged so the
    caller stays observable.

    Pass `sentinel_session_id` to preserve a session id across plan
    rewrites (e.g., replan reuses the running sentinel's id); leave `None`
    at fresh sentinel start to mint a new id.
    """
    import uuid

    with open(plan_file, "r") as f:
        plan = json.load(f)

    plan_version = plan.get("plan_version", 1)
    brief_hash = plan.get("brief_hash", "")
    plan_phase = plan.get("plan_phase", "initial")
    plan_method = plan.get("plan_method", "api")

    # Derive the lineage id from the spec the sentinel was started with,
    # or fall back to whatever the planner stamped on the plan.  Plans
    # generated before this change carry no `input_path`, so older runs
    # land with `spec_lineage_id = None` — readers fall back to
    # `__legacy__` per the migration spec.
    resolved_spec = spec_path or plan.get("input_path")
    spec_lineage_id: Optional[str] = None
    if resolved_spec:
        if not project_path:
            project_path = os.path.dirname(os.path.abspath(plan_file))
        try:
            from set_orch.types import canonicalise_spec_path
            spec_lineage_id = canonicalise_spec_path(resolved_spec, project_path)
        except (ValueError, OSError) as exc:
            logger.warning(
                "init_state: cannot canonicalise spec_path=%r project=%r: %s — "
                "spec_lineage_id will be None",
                resolved_spec, project_path, exc,
            )
    else:
        logger.warning(
            "init_state(plan=%s): no spec_path provided and plan has no "
            "input_path — state will lack spec_lineage_id, archive entries "
            "will be tagged __legacy__",
            plan_file,
        )

    session_id = sentinel_session_id or uuid.uuid4().hex
    session_started_at = datetime.now().astimezone().isoformat()

    changes = []
    for c in plan.get("changes", []):
        change = Change(
            name=c["name"],
            scope=c.get("scope", ""),
            complexity=c.get("complexity", "M"),
            change_type=c.get("change_type", "feature"),
            depends_on=c.get("depends_on", []),
            roadmap_item=c.get("roadmap_item", ""),
            model=c.get("model", None),
            skip_review=c.get("skip_review", False),
            skip_test=c.get("skip_test", False),
            has_manual_tasks=c.get("has_manual_tasks", False),
            phase=c.get("phase", 1),
            spec_lineage_id=spec_lineage_id,
            sentinel_session_id=session_id,
            sentinel_session_started_at=session_started_at,
        )
        if "requirements" in c:
            change.requirements = c["requirements"]
        if "also_affects_reqs" in c:
            change.also_affects_reqs = c["also_affects_reqs"]
        changes.append(change)

    state = OrchestratorState(
        plan_version=plan_version,
        brief_hash=brief_hash,
        plan_phase=plan_phase,
        plan_method=plan_method,
        status="running",
        created_at=datetime.now().astimezone().isoformat(),
        changes=changes,
        spec_lineage_id=spec_lineage_id,
        sentinel_session_id=session_id,
        sentinel_session_started_at=session_started_at,
    )

    save_state(state, output_path)
    logger.info(
        "State initialized: %d changes from %s → %s (lineage=%s session=%s)",
        len(changes), plan_file, output_path, spec_lineage_id, session_id[:8],
    )


def query_changes(
    state: OrchestratorState, status: Optional[str] = None
) -> list[Change]:
    """Filter changes by status. Returns all changes if status is None."""
    if status is None:
        return list(state.changes)
    return [c for c in state.changes if c.status == status]


def aggregate_tokens(state: OrchestratorState) -> TokenStats:
    """Aggregate token usage across all changes."""
    stats = TokenStats()
    for c in state.changes:
        stats.total += c.tokens_used
        stats.input_total += c.input_tokens
        stats.output_total += c.output_tokens
        stats.cache_read_total += c.cache_read_tokens
        stats.cache_create_total += c.cache_create_tokens
    return stats


# ─── State Mutation Functions (Phase 2) ──────────────────────────────
# Migrated from: lib/orchestration/state.sh update_state_field(),
# update_change_field(), get_change_status(), get_changes_by_status(),
# count_changes_by_status()


def update_state_field(
    path: str, field_name: str, value: Any, event_bus: EventBus | None = None
) -> None:
    """Update a top-level field in state (locked + validated).

    Migrated from: state.sh update_state_field() L73-77
    """
    with locked_state(path) as state:
        old_value = getattr(state, field_name, state.extras.get(field_name))
        if field_name in {f.name for f in fields(OrchestratorState) if f.name != "extras"}:
            setattr(state, field_name, value)
        else:
            state.extras[field_name] = value
        if value != old_value:
            logger.info("State update: %s = %r (was: %r)", field_name, value, old_value)


def update_change_field(
    path: str,
    change_name: str,
    field_name: str,
    value: Any,
    event_bus: EventBus | None = None,
    hook_scripts: dict[str, str] | None = None,
) -> None:
    """Update a change's field in state (locked + validated).

    Automatically emits STATE_CHANGE event when status transitions,
    TOKENS event on significant deltas (>10K), and triggers on_fail hook.

    Migrated from: state.sh update_change_field() L80-131
    """
    with locked_state(path) as state:
        change = _find_change(state, change_name)
        if change is None:
            raise ValueError(f"Change not found: {change_name}")

        old_status = change.status if field_name == "status" else None
        old_tokens = change.tokens_used if field_name == "tokens_used" else None
        old_value = getattr(change, field_name, change.extras.get(field_name))

        # Set the field
        known = {f.name for f in fields(Change) if f.name != "extras"}
        if field_name in known:
            setattr(change, field_name, value)
        else:
            change.extras[field_name] = value

        if value != old_value:
            logger.info("State update: %s.%s = %r (was: %r)", change_name, field_name, value, old_value)

            if field_name in _JOURNALED_FIELDS:
                try:
                    _append_journal(path, change_name, field_name, old_value, value)
                except BaseException as exc:
                    logger.warning(
                        "_append_journal failed for %s.%s: %s", change_name, field_name, exc
                    )

        # Emit STATE_CHANGE event on status transitions
        if field_name == "status" and event_bus and old_status is not None:
            new_status = value
            if old_status != new_status:
                event_bus.emit(
                    "STATE_CHANGE",
                    change=change_name,
                    data={"from": old_status, "to": new_status},
                )
                # Trigger on_fail hook when transitioning to failed
                if new_status == "failed" and hook_scripts:
                    hook_script = hook_scripts.get("on_fail")
                    if hook_script:
                        run_hook(
                            "on_fail",
                            hook_script,
                            change_name,
                            new_status,
                            change.worktree_path or "",
                            event_bus=event_bus,
                        )

        # Emit TOKENS event on significant token updates
        if field_name == "tokens_used" and event_bus and old_tokens is not None:
            delta = value - old_tokens
            if abs(delta) > 10000:
                event_bus.emit(
                    "TOKENS",
                    change=change_name,
                    data={"delta": delta, "total": value},
                )


def get_change_status(state: OrchestratorState, name: str) -> str:
    """Get a change's status. Returns empty string if not found.

    Migrated from: state.sh get_change_status() L134-142
    """
    change = _find_change(state, name)
    return change.status if change else ""


def get_changes_by_status(state: OrchestratorState, status: str) -> list[str]:
    """Get all change names with a specific status.

    Migrated from: state.sh get_changes_by_status() L145-153
    """
    return [c.name for c in state.changes if c.status == status]


def count_changes_by_status(state: OrchestratorState, status: str) -> int:
    """Count changes with a specific status.

    Migrated from: state.sh count_changes_by_status() L156-164
    """
    return sum(1 for c in state.changes if c.status == status)


def _find_change(state: OrchestratorState, name: str) -> Change | None:
    """Find a change by name."""
    for c in state.changes:
        if c.name == name:
            return c
    return None


# ─── Dependency Graph Operations (Phase 2) ───────────────────────────
# Migrated from: lib/orchestration/state.sh deps_satisfied(), deps_failed(),
# cascade_failed_deps(), topological_sort()


def deps_satisfied(state: OrchestratorState, change_name: str) -> bool:
    """Check if all depends_on for a change are merged or skipped.

    Migrated from: state.sh deps_satisfied() L167-184
    """
    change = _find_change(state, change_name)
    if not change or not change.depends_on:
        return True

    for dep_name in change.depends_on:
        dep = _find_change(state, dep_name)
        if dep is None or dep.status not in ("merged", "skipped"):
            return False
    return True


def deps_failed(state: OrchestratorState, change_name: str) -> bool:
    """Check if any depends_on for a change has failed (terminal state).

    Note: merge-blocked is NOT a failure — the work is done, only merge is stuck.

    Migrated from: state.sh deps_failed() L186-207
    """
    change = _find_change(state, change_name)
    if not change or not change.depends_on:
        return False

    for dep_name in change.depends_on:
        dep = _find_change(state, dep_name)
        if dep and dep.status == "failed":
            return True
    return False


def cascade_failed_deps(
    state: OrchestratorState, event_bus: EventBus | None = None
) -> int:
    """Mark pending changes as failed if their dependencies have failed.

    Prevents deadlock where failed deps leave children stuck in pending forever.

    Migrated from: state.sh cascade_failed_deps() L210-236

    Returns:
        Number of changes cascaded to failed.
    """
    cascaded = 0
    for change in state.changes:
        if change.status != "pending":
            continue
        if not deps_failed(state, change.name):
            continue

        # Find the specific failed dependency
        failed_dep = ""
        for dep_name in change.depends_on:
            dep = _find_change(state, dep_name)
            if dep and dep.status == "failed":
                failed_dep = dep_name
                break

        if event_bus:
            event_bus.emit(
                "CASCADE_FAILED",
                change=change.name,
                data={"reason": "dependency_failed", "failed_dep": failed_dep},
            )

        change.status = "failed"
        change.extras["failure_reason"] = f"dependency {failed_dep} failed"
        logger.warning("Cascade failed: %s → failed (dependency %s failed)", change.name, failed_dep)
        cascaded += 1

    if cascaded:
        logger.info("Cascade failed deps: %d changes cascaded to failed", cascaded)
    return cascaded


class CircularDependencyError(Exception):
    """Raised when topological sort detects a cycle."""


def topological_sort(changes: list[Change] | list[dict]) -> list[str]:
    """Return change names in dependency-respecting execution order.

    Migrated from: state.sh topological_sort() L286-324

    Args:
        changes: List of Change dataclasses or dicts with 'name' and 'depends_on'.

    Returns:
        List of change names in topological order.

    Raises:
        CircularDependencyError: If a dependency cycle is detected.
    """
    # Normalize input
    if changes and isinstance(changes[0], dict):
        graph = {c["name"]: c.get("depends_on", []) for c in changes}
    else:
        graph = {c.name: list(c.depends_on) for c in changes}

    # Build adjacency: if B depends on A, then A -> B
    adj: dict[str, list[str]] = {name: [] for name in graph}
    in_deg: dict[str, int] = {name: 0 for name in graph}
    for name, deps in graph.items():
        for d in deps:
            if d in adj:
                adj[d].append(name)
                in_deg[name] += 1
            else:
                logger.warning("Dependency %r of change %r not found in plan — ignoring", d, name)

    queue = deque(sorted(n for n in graph if in_deg[n] == 0))
    result: list[str] = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in sorted(adj[node]):
            in_deg[neighbor] -= 1
            if in_deg[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(graph):
        raise CircularDependencyError(
            f"Circular dependency detected among: "
            f"{sorted(set(graph) - set(result))}"
        )

    return result


# ─── Phase Management (Phase 2) ─────────────────────────────────────
# Migrated from: lib/orchestration/state.sh _init_phase_state(),
# apply_phase_overrides(), all_phase_changes_terminal(), advance_phase()

_TERMINAL_STATUSES = frozenset({"merged", "failed", "skipped", "done"})

# Statuses that count as NOT in-flight for dispatch parallel-limit purposes.
# A change is "in flight" (counts toward the running total) UNLESS it is in
# one of these states. We use a whitelist (not a blacklist of in-flight states)
# so that adding a new intermediate state in the future fails safe — it will
# be treated as in-flight and block new dispatches until classified.
_NOT_IN_FLIGHT_STATUSES = frozenset({
    "merged",       # successfully merged to main
    "skipped",      # skipped by merge policy
    "skip_merged",  # skipped via merge policy + recorded as merged
    "failed",       # terminal failure, will not retry
    "pending",      # not yet dispatched
    "dep-blocked",  # waiting for dependency, not yet dispatched
})


def count_in_flight_changes(state: "OrchestratorState") -> int:
    """Count changes currently in flight (occupying a parallel slot).

    A change is in-flight if it has been dispatched and has not yet reached
    a terminal/pending state. This includes: dispatched, running, done,
    verifying, integrating, integration-failed, integration-e2e-failed,
    integration-coverage-failed, fixing, merge-blocked, stalled, paused,
    stopped, waiting:human, waiting:budget, and any future intermediate state.
    """
    return sum(1 for c in state.changes if c.status not in _NOT_IN_FLIGHT_STATUSES)


def init_phase_state(state: OrchestratorState) -> None:
    """Compute unique phases from changes and create phase tracking state.

    Migrated from: state.sh _init_phase_state() L42-70
    """
    phases = sorted({c.phase for c in state.changes})
    if len(phases) <= 1:
        # No phase management needed for single phase
        return

    phase_dict = {}
    for p in phases:
        phase_dict[str(p)] = {
            "status": "running" if p == phases[0] else "pending",
            "tag": None,
            "server_port": None,
            "server_pid": None,
            "completed_at": None,
        }

    state.extras["current_phase"] = phases[0]
    state.extras["phases"] = phase_dict


def apply_phase_overrides(
    state: OrchestratorState, overrides: dict[str, int]
) -> None:
    """Apply phase overrides from directives and recalculate phase state.

    Migrated from: state.sh apply_phase_overrides() L22-38

    Args:
        overrides: Dict of {change_name: phase_number}.
    """
    if not overrides:
        return

    for change in state.changes:
        if change.name in overrides:
            change.phase = overrides[change.name]

    # Recalculate phases
    init_phase_state(state)


def all_phase_changes_terminal(state: OrchestratorState, phase: int) -> bool:
    """Check if all changes in the current phase are terminal.

    Migrated from: state.sh all_phase_changes_terminal() L241-250
    """
    phase_changes = [c for c in state.changes if c.phase == phase]
    if not phase_changes:
        return True
    return all(c.status in _TERMINAL_STATUSES for c in phase_changes)


def advance_phase(
    state: OrchestratorState, event_bus: EventBus | None = None
) -> bool:
    """Advance to the next phase. Returns True if advanced, False if no more phases.

    Migrated from: state.sh advance_phase() L253-281
    """
    phases = state.extras.get("phases")
    if not phases:
        return False

    current = state.extras.get("current_phase", 1)

    # Mark current phase as completed
    cp_key = str(current)
    if cp_key in phases:
        phases[cp_key]["status"] = "completed"
        phases[cp_key]["completed_at"] = datetime.now().astimezone().isoformat()

    # Find next phase
    phase_nums = sorted(int(k) for k in phases.keys())
    next_phases = [p for p in phase_nums if p > current]

    if not next_phases:
        logger.info("Phase advance: no more phases after %d", current)
        return False

    next_phase = next_phases[0]
    state.extras["current_phase"] = next_phase
    phases[str(next_phase)]["status"] = "running"
    logger.info("Phase advance: %d → %d", current, next_phase)

    if event_bus:
        event_bus.emit(
            "PHASE_ADVANCED",
            data={"from": current, "to": next_phase},
        )

    return True


# ─── Crash Recovery (Phase 2) ───────────────────────────────────────
# Migrated from: lib/orchestration/state.sh reconstruct_state_from_events()


def reconstruct_state_from_events(
    state_path: str,
    events_path: str | None = None,
    event_bus: EventBus | None = None,
) -> bool:
    """Rebuild state from events JSONL by replaying state transitions.

    Preserves plan-origin fields (scope, complexity, depends_on) from the
    existing state file and only updates runtime fields (status, tokens).

    Migrated from: state.sh reconstruct_state_from_events() L867-996

    Returns:
        True if reconstruction succeeded, False if not possible.
    """
    # Derive events file from state file if not provided
    if events_path is None:
        base = state_path.replace("-state.json", "").replace(".json", "")
        events_path = base + "-events.jsonl"

    if not os.path.isfile(events_path):
        logger.warning("Cannot reconstruct state: no events file at %s", events_path)
        return False

    if not os.path.isfile(state_path):
        logger.warning("Cannot reconstruct state: no state file at %s", state_path)
        return False

    # Read events
    try:
        with open(events_path, "r") as f:
            lines = f.readlines()
    except OSError as e:
        logger.warning("Cannot read events file: %s", e)
        return False

    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not events:
        logger.warning("Cannot reconstruct state: events file is empty")
        return False

    event_count = len(events)
    logger.info("Reconstructing state from %d events in %s", event_count, events_path)

    # Load existing state (preserves plan structure)
    state = load_state(state_path)

    # 1. Replay STATE_CHANGE events to get final per-change status
    final_statuses: dict[str, str] = {}
    for e in events:
        if e.get("type") == "STATE_CHANGE" and e.get("change"):
            data = e.get("data", {})
            if "to" in data:
                final_statuses[e["change"]] = data["to"]

    for change in state.changes:
        if change.name in final_statuses:
            change.status = final_statuses[change.name]

    # 2. Replay TOKENS events to get latest token counts
    final_tokens: dict[str, int] = {}
    for e in events:
        if e.get("type") == "TOKENS" and e.get("change"):
            data = e.get("data", {})
            if "total" in data:
                final_tokens[e["change"]] = data["total"]

    for change in state.changes:
        if change.name in final_tokens:
            change.tokens_used = final_tokens[change.name]

    # 3. Running changes become stalled (no live process)
    for change in state.changes:
        if change.status in ("running", "stalled", "stuck"):
            logger.warning("Crash recovery: reset %s from %s to stalled", change.name, change.status)
            change.status = "stalled"

    # 4. Derive overall orchestration status
    all_done = all(
        c.status in ("done", "merged", "completed", "archived", "skipped")
        for c in state.changes
    )
    state.status = "done" if all_done else "stopped"

    # 5. Save reconstructed state
    save_state(state, state_path)

    if event_bus:
        event_bus.emit(
            "STATE_RECONSTRUCTED",
            data={"event_count": event_count, "status": state.status},
        )

    return True


# ─── Hook Runner (Phase 2) ──────────────────────────────────────────
# Migrated from: lib/orchestration/state.sh run_hook() L331-361


def run_hook(
    hook_name: str,
    hook_script: str | None,
    change_name: str,
    status: str = "",
    wt_path: str = "",
    event_bus: EventBus | None = None,
) -> bool:
    """Execute a lifecycle hook script.

    Returns True if hook passes (exit 0) or is not configured,
    False if hook blocks (non-zero exit).

    Migrated from: state.sh run_hook() L331-361
    """
    if not hook_script:
        return True

    if not os.path.isfile(hook_script):
        logger.warning("Hook %s: script not found: %s", hook_name, hook_script)
        return True

    if not os.access(hook_script, os.X_OK):
        logger.warning("Hook %s: script not executable: %s", hook_name, hook_script)
        return True

    logger.info("Running hook %s for %s: %s", hook_name, change_name, hook_script)
    try:
        result = subprocess.run(
            [hook_script, change_name, status, wt_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("Hook %s passed for %s", hook_name, change_name)
            return True
        else:
            reason = result.stderr.strip() or "unknown"
            logger.error("Hook %s blocked %s: %s", hook_name, change_name, reason)
            if event_bus:
                event_bus.emit(
                    "HOOK_BLOCKED",
                    change=change_name,
                    data={"hook": hook_name, "reason": reason},
                )
            return False
    except subprocess.TimeoutExpired:
        logger.error("Hook %s timed out for %s", hook_name, change_name)
        if event_bus:
            event_bus.emit(
                "HOOK_BLOCKED",
                change=change_name,
                data={"hook": hook_name, "reason": "timeout"},
            )
        return False
    except OSError as e:
        logger.error("Hook %s execution error for %s: %s", hook_name, change_name, e)
        return True
