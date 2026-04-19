from __future__ import annotations

"""Event bus with JSONL persistence for orchestration audit trail.

Migrated from: lib/orchestration/events.sh (emit_event, rotate_events_log, query_events)

Combines two concerns:
1. JSONL file writer — append-only event log (backward-compatible format)
2. In-process event bus — subscribe(type, handler) for Python consumers
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Default rotation threshold
DEFAULT_MAX_SIZE = 1048576  # 1MB
DEFAULT_MAX_ARCHIVES = 3
ROTATION_CHECK_INTERVAL = 100  # check every N emissions


class EventBus:
    """Event bus with JSONL file persistence.

    Usage:
        bus = EventBus()
        bus.emit("STATE_CHANGE", change="add-auth", data={"status": "running"})
        bus.subscribe("STATE_CHANGE", handler_fn)
        events = bus.query(type="STATE_CHANGE", last_n=20)
    """

    def __init__(
        self,
        log_path: str | Path | None = None,
        max_size: int = DEFAULT_MAX_SIZE,
        enabled: bool = True,
    ):
        self._log_path: Path | None = Path(log_path) if log_path else None
        self._max_size = max_size
        self._enabled = enabled
        self._emit_count = 0
        self._subscribers: dict[str, list[Callable]] = {}

    @property
    def log_path(self) -> Path | None:
        """Get or lazily resolve the log path."""
        if self._log_path is None:
            self._log_path = _resolve_log_path()
        return self._log_path

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def emit(
        self,
        event_type: str,
        change: str = "",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Emit a structured event to JSONL file and notify subscribers.

        Migrated from: events.sh:emit_event() L19-61

        Args:
            event_type: Event type (e.g., "STATE_CHANGE", "CHECKPOINT").
            change: Change name (empty for orchestrator-level events).
            data: Event data dict (default {}).
        """
        if not self._enabled:
            return

        ts = datetime.now(timezone.utc).astimezone().isoformat()
        event_data = data or {}

        # Build event dict — field order matters for compatibility
        event: dict[str, Any] = {"ts": ts, "type": event_type}
        if change:
            event["change"] = change
        event["data"] = event_data

        # Write to JSONL file
        path = self.log_path
        if path:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, separators=(",", ":")) + "\n")
            except (OSError, IOError) as e:
                logger.error("Failed to write event: %s", e)

        # Notify subscribers
        self._notify(event_type, event)

        # Periodic rotation check
        self._emit_count += 1
        if self._emit_count % ROTATION_CHECK_INTERVAL == 0:
            self.rotate_log()

    def rotate_log(self) -> None:
        """Archive events log when it exceeds max_size. Keep last N archives.

        Migrated from: events.sh:rotate_events_log() L66-86
        """
        path = self.log_path
        if not path or not path.is_file():
            return

        try:
            size = path.stat().st_size
        except OSError:
            return

        if size <= self._max_size:
            return

        # Rename with timestamp
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        archive = path.with_name(f"{path.stem}-{ts}{path.suffix}")
        try:
            path.rename(archive)
            path.touch()
            logger.info("Events log rotated: %s (%d bytes)", archive.name, size)
        except OSError as e:
            logger.error("Failed to rotate events log: %s", e)
            return

        # Keep only last N archives
        pattern = f"{path.stem}-*{path.suffix}"
        archives = sorted(path.parent.glob(pattern), reverse=True)
        for old in archives[DEFAULT_MAX_ARCHIVES:]:
            try:
                old.unlink()
            except OSError:
                pass

    def query(
        self,
        *,
        event_type: str | None = None,
        change: str | None = None,
        since: str | None = None,
        last_n: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query events from the JSONL log.

        Migrated from: events.sh:query_events() L92-139

        Args:
            event_type: Filter by event type.
            change: Filter by change name.
            since: Filter by timestamp (ISO 8601, >= comparison).
            last_n: Only scan last N lines.

        Returns:
            List of matching event dicts.
        """
        path = self.log_path
        if not path or not path.is_file():
            return []

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, IOError):
            return []

        if last_n is not None and last_n > 0:
            lines = lines[-last_n:]

        results: list[dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event_type and event.get("type") != event_type:
                continue
            if change and event.get("change") != change:
                continue
            if since and event.get("ts", "") < since:
                continue

            results.append(event)

        return results

    def format_table(self, events: list[dict[str, Any]]) -> str:
        """Format events as a human-readable table.

        Migrated from: events.sh:query_events() L123-137 (formatted table output)
        """
        if not events:
            return "No events found."

        lines = []
        header = f"{'Timestamp':<25} {'Type':<20} {'Change':<25} Data"
        sep = f"{'─' * 25} {'─' * 20} {'─' * 25} ────"
        lines.append(header)
        lines.append(sep)

        for e in events:
            ts = e.get("ts", "")[:25]
            etype = e.get("type", "")
            echange = e.get("change", "-")
            edata = json.dumps(e.get("data", {}), separators=(",", ":"))
            lines.append(f"{ts:<25} {etype:<20} {echange:<25} {edata}")

        return "\n".join(lines)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to events of a given type.

        Use "*" for wildcard (receives all events).

        Args:
            event_type: Event type to subscribe to, or "*" for all.
            handler: Callable(event_dict) invoked synchronously on emit.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def _notify(self, event_type: str, event: dict[str, Any]) -> None:
        """Notify subscribers for this event type + wildcard subscribers."""
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error("Event handler error for %s: %s", event_type, e)

        # Wildcard subscribers
        if event_type != "*":
            for handler in self._subscribers.get("*", []):
                try:
                    handler(event)
                except Exception as e:
                    logger.error("Wildcard event handler error: %s", e)


def _resolve_log_path() -> Path | None:
    """Resolve events log path.

    Priority:
    1. SetRuntime resolution (shared runtime dir)
    2. Legacy: STATE_FILENAME env var → sibling events file
    3. Legacy fallback: LineagePaths.events_file basename in cwd
    """
    try:
        from .paths import SetRuntime
        rt = SetRuntime()
        return Path(rt.events_file)
    except Exception:
        pass

    # Legacy fallback
    state_file = os.environ.get("STATE_FILENAME")
    if state_file:
        stem = Path(state_file).stem.replace("-state", "")
        return Path(state_file).parent / f"{stem}-events.jsonl"
    from .paths import LineagePaths as _LP_ev
    return Path(os.path.basename(_LP_ev(os.getcwd()).events_file))


# Module-level singleton — used by run_claude_logged() to emit LLM_CALL events.
# monitor_loop() syncs this to the per-project events file at startup.
event_bus = EventBus()
