"""The vocabulary both backends share: the identity of an agent, and its errors.

Kept out of `__init__` so a backend can import it without importing the
dispatcher that imports the backend. Kept out of either backend so neither owns
a name the other must reach across for.

The naming carries a deliberate compromise. `unit_name()` produces
`set-agent-<label>.scope` on every platform, and `.scope` is systemd's word.
Keeping it is not an oversight: the string is an IDENTITY, it is written into
records, matched in logs and compared against what a previous run stored, and
changing its shape per platform would mean the same agent had two names
depending on where it ran. macOS treats it as an opaque token. A reader who
knows systemd should read the suffix as a convention this framework kept, not as
a claim that a transient unit exists.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

#: Every agent this framework starts carries this prefix, so the fleet can tell
#: its own agents from every other process on the machine without keeping a list
#: anywhere. The name is the record.
SCOPE_PREFIX = "set-agent-"

#: See the module docstring — a convention on both platforms, systemd's on one.
UNIT_SUFFIX = ".scope"


class ScopeError(RuntimeError):
    """An agent could not be started, stopped or verified."""


@dataclass
class Scope:
    """One framework-owned agent, in the one shape every backend returns.

    `cgroup` is systemd's answer and is empty on platforms that have none; it is
    kept in the shared shape rather than pushed into a backend-specific subclass
    because callers log it, and a field that is sometimes absent is harder to
    read than one that is sometimes empty.
    """

    unit: str
    #: The first live pid the agent holds, or None when it holds none.
    pid: Optional[int]
    cgroup: str
    #: Whether the agent is running. Deliberately NOT the same question as "is it
    #: gone": a systemd unit in `deactivating` is neither, and its processes are
    #: still alive.
    active: bool
    #: Every live pid. An agent normally holds one, but one that spawns children
    #: holds more, and stopping is a property of the agent rather than of any one
    #: of them.
    pids: List[int] = field(default_factory=list)
    #: The backend's raw state word. systemd's `ActiveState` on Linux. Kept
    #: because collapsing it into `active` throws away the one distinction that
    #: matters when stopping. MEASURED 2026-08-18 on a live interactive agent —
    #: `stop()` returned "gone" in 0.0s and logged "stopped on SIGTERM" while the
    #: scope was `deactivating` and its pid was still alive.
    state: str = ""

    @property
    def label(self) -> str:
        """The part of the name after the prefix — what the caller asked for."""
        if self.unit.startswith(SCOPE_PREFIX):
            return self.unit[len(SCOPE_PREFIX):-len(UNIT_SUFFIX)]
        return self.unit


def sanitize(label: str) -> str:
    """A label made safe for a unit name, without becoming ambiguous.

    Unit names accept a narrow alphabet; a caller's label may not. Substituting
    the offending characters silently would let two different labels collapse
    onto one unit name — and the name is an identity here, so a collision would
    stop the wrong agent. Anything substituted is therefore followed by a short
    digest of the original.
    """
    safe = re.sub(r"[^A-Za-z0-9_.-]", "-", label).strip("-") or "agent"
    if safe != label:
        import hashlib
        safe = f"{safe}-{hashlib.sha256(label.encode()).hexdigest()[:6]}"
    return safe


def unit_name(label: str) -> str:
    return f"{SCOPE_PREFIX}{sanitize(label)}{UNIT_SUFFIX}"


def as_unit_name(unit: str) -> str:
    """Normalise a name to a unit name without inventing a nonsense one.

    Appending the suffix unconditionally turns `set-web.service` into
    `set-web.service.scope`, which does not exist — so a refusal downstream would
    be right for the wrong reason, and its message would name a unit nobody asked
    about.

    Was `_as_scope`. Renamed when `owner.py` was found reaching for it through
    the underscore: a name a caller outside the module depends on is part of the
    contract whatever it is spelled, and leaving it private would have let the
    platform split define it on one backend only.
    """
    import os
    if "." in os.path.basename(unit):
        return unit
    return f"{unit}{UNIT_SUFFIX}"
