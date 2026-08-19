"""Fleet — the agent sessions running on this machine, and what they are doing.

Layer 1 (abstract). Nothing here knows what kind of project it is looking at; a
project is a git repository with a working directory, and that is all.

Three questions, from three different sources, kept apart because conflating
them is how a false value gets on screen:

    discovery — WHO is running, and where.   Read from process state and the
                runtime's own session records. Identity only.
    state     — WHAT they are doing.         Read from the session log itself,
                never from a status field, because the status field is stale.
    instruct  — what happened to a message.  Read from the channel's answer
                about what it DID, never from the send call's own success.

(The package holds more than these three — the terminal owner and its client,
the layout, the scopes. Those are mechanism; the three above are the sources.)

Measured 2026-08-18 on this machine, and the split follows the measurement:
the session record's identity fields matched live processes 23 of 23, while its
`status` field had a median age of 11 hours and a maximum of 83.
"""

from .discovery import Agent, ProjectEntry, discover_agents, discover_projects
from .state import AgentState, read_state
from .instruct import (
    DeliveryReport,
    Instructability,
    Seat,
    Waiter,
    instruct_agent,
    instructability,
    live_waiters,
    orphaned_waiters,
    read_seats,
    send_instruction,
)

__all__ = [
    "Agent",
    "ProjectEntry",
    "AgentState",
    "discover_agents",
    "discover_projects",
    "read_state",
    "Seat",
    "Waiter",
    "Instructability",
    "DeliveryReport",
    "read_seats",
    "instructability",
    "send_instruction",
    "instruct_agent",
    "live_waiters",
    "orphaned_waiters",
]
