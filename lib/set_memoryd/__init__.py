"""set-memoryd: per-project memory daemon for shodh-memory.

Eliminates ~1580ms CLI overhead by keeping MemorySystem persistent.
"""

from .client import MemoryClient, DaemonError, DaemonUnavailable
from .lifecycle import is_running, start, stop, ensure_running, resolve_project

__all__ = [
    "MemoryClient",
    "DaemonError",
    "DaemonUnavailable",
    "is_running",
    "start",
    "stop",
    "ensure_running",
    "resolve_project",
]
