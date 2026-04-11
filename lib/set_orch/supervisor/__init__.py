"""set-supervisor — Python daemon that replaces the Claude-driven sentinel.

Architecture (3 layers):

1. Python daemon (this package): cheap, always on. Process monitoring,
   state.json polling, events.jsonl tailing, crash recovery, SIGTERM
   handling. Zero LLM cost on the routine path.

2. Ephemeral Claude trigger (Phase 2): fresh `claude -p` subprocess
   spawned on anomaly signals (crash, stall, integration-failed,
   unknown event type, error rate spike, log silence). Focused
   single-task prompt, 10-min timeout, exits on completion.

3. Canary Claude check (Phase 2): periodic (every 15 min) fresh
   ephemeral Claude that reads a structured diff since last canary
   and returns CANARY_VERDICT: ok|note|warn|stop.

Phase 1 (this commit) ships Layer 1 only. Layer 2/3 are orthogonal
follow-ups — the daemon has stub hooks ready for them.

Entry point: `bin/set-supervisor` → `daemon.SupervisorDaemon.run()`.

See OpenSpec change: sentinel-supervisor-redesign
"""

from __future__ import annotations

from .daemon import SupervisorDaemon, SupervisorConfig
from .state import SupervisorStatus, read_status, write_status

__all__ = [
    "SupervisorDaemon",
    "SupervisorConfig",
    "SupervisorStatus",
    "read_status",
    "write_status",
]
