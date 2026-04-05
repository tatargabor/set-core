from __future__ import annotations

"""Structured event logging to shared sentinel directory."""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

from set_orch.sentinel.set_dir import ensure_set_dir

logger = logging.getLogger(__name__)

EVENTS_FILE = "events.jsonl"


class SentinelEventLogger:
    """Append-only JSONL event logger for sentinel activity.

    Events are written to sentinel/events.jsonl with atomic appends.
    """

    def __init__(self, project_path: str):
        self.project_path = os.path.abspath(project_path)
        self.sentinel_dir = ensure_set_dir(self.project_path)
        self.events_file = os.path.join(self.sentinel_dir, EVENTS_FILE)

    def _emit(self, event_type: str, **kwargs) -> dict:
        """Write a single event to events.jsonl. Returns the event dict."""
        event = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "epoch": int(time.time()),
            "type": event_type,
            **kwargs,
        }
        line = json.dumps(event, ensure_ascii=False) + "\n"
        with open(self.events_file, "a") as f:
            f.write(line)
        logger.info("Sentinel event: %s — %s", event_type, {k: v for k, v in kwargs.items() if v})
        return event

    def poll(
        self,
        state: str,
        change: Optional[str] = None,
        iteration: Optional[int] = None,
    ) -> dict:
        """Log a state poll event."""
        return self._emit(
            "poll",
            state=state,
            change=change or "",
            iteration=iteration,
        )

    def crash(
        self,
        pid: int,
        exit_code: int,
        stderr_tail: str = "",
    ) -> dict:
        """Log an orchestrator crash."""
        return self._emit(
            "crash",
            pid=pid,
            exit_code=exit_code,
            stderr_tail=stderr_tail[:500],
        )

    def restart(self, new_pid: int, attempt: int) -> dict:
        """Log an orchestrator restart."""
        return self._emit("restart", new_pid=new_pid, attempt=attempt)

    def decision(self, action: str, reason: str) -> dict:
        """Log an autonomous decision."""
        return self._emit("decision", action=action, reason=reason)

    def escalation(self, reason: str, context: str = "") -> dict:
        """Log an escalation to the user."""
        return self._emit("escalation", reason=reason, context=context)

    def finding(
        self,
        finding_id: str,
        severity: str,
        change: str,
        summary: str,
    ) -> dict:
        """Log a finding discovery event."""
        return self._emit(
            "finding",
            finding_id=finding_id,
            severity=severity,
            change=change,
            summary=summary,
        )

    def assessment(self, scope: str, summary: str) -> dict:
        """Log an assessment event."""
        return self._emit("assessment", scope=scope, summary=summary)

    def message_received(self, sender: str, content: str) -> dict:
        """Log an incoming message."""
        return self._emit("message_received", sender=sender, content=content)

    def message_sent(self, recipient: str, content: str) -> dict:
        """Log an outgoing message."""
        return self._emit("message_sent", recipient=recipient, content=content)

    def tail(self, since_epoch: Optional[int] = None, limit: int = 200) -> list[dict]:
        """Read events, optionally filtered by timestamp.

        Args:
            since_epoch: Only return events after this Unix timestamp.
            limit: Max number of events to return (newest first truncation).
        """
        if not os.path.exists(self.events_file):
            return []

        events = []
        with open(self.events_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if since_epoch and event.get("epoch", 0) <= since_epoch:
                    continue
                events.append(event)

        # Return the last `limit` events
        if len(events) > limit:
            events = events[-limit:]
        return events
