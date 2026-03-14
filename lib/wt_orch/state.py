"""Typed JSON state management for orchestration engine.

Replaces complex jq pipelines with Python dataclasses. Provides atomic file
operations and validation on read/write.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any, Optional


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

    # Verification results
    test_result: Optional[str] = None
    test_stats: Optional[dict] = None
    smoke_result: Optional[str] = None
    smoke_stats: Optional[dict] = None
    review_result: Optional[str] = None
    build_result: Optional[str] = None

    # Screenshot tracking
    smoke_screenshot_dir: str = ""
    smoke_screenshot_count: int = 0
    e2e_screenshot_dir: str = ""
    e2e_screenshot_count: int = 0

    # Retry tracking
    verify_retry_count: int = 0
    redispatch_count: int = 0
    merge_retry_count: int = 0

    # Gate timings (ms)
    gate_test_ms: int = 0
    gate_review_ms: int = 0
    gate_build_ms: int = 0
    gate_verify_ms: int = 0
    gate_total_ms: int = 0

    # Optional fields from plan
    requirements: Optional[list] = None
    also_affects_reqs: Optional[list] = None

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
                "test_result", "test_stats", "smoke_result", "smoke_stats",
                "review_result", "build_result", "model",
            ):
                d[f.name] = val
            elif f.name not in ("requirements", "also_affects_reqs", "watchdog"):
                d[f.name] = val
        # Omit None-valued optional fields that weren't in the original
        if self.requirements is not None:
            d["requirements"] = self.requirements
        if self.also_affects_reqs is not None:
            d["also_affects_reqs"] = self.also_affects_reqs
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


def save_state(state: OrchestratorState, path: str) -> None:
    """Serialize state to JSON and write atomically.

    Uses tempfile + rename in the same directory to ensure atomic writes.
    Validates output is non-empty before rename.
    """
    data = state.to_dict()
    content = json.dumps(data, indent=2) + "\n"

    if len(content.strip()) < 2:  # at minimum "{}"
        raise ValueError("save_state: serialized state is empty")

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


def init_state(plan_file: str, output_path: str) -> None:
    """Initialize orchestration state from a plan file.

    Replaces the 40-line jq filter in state.sh init_state().
    """
    with open(plan_file, "r") as f:
        plan = json.load(f)

    plan_version = plan.get("plan_version", 1)
    brief_hash = plan.get("brief_hash", "")
    plan_phase = plan.get("plan_phase", "initial")
    plan_method = plan.get("plan_method", "api")

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
    )

    save_state(state, output_path)


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
