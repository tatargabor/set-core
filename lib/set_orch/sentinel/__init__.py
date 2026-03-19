"""Sentinel structured event logging, findings, status, and inbox.

Usage:
    from set_orch.sentinel import SentinelEventLogger, SentinelFindings, SentinelStatus

All sentinel runtime data lives under .set/sentinel/ in the project root.
"""

from set_orch.sentinel.events import SentinelEventLogger
from set_orch.sentinel.findings import SentinelFindings
from set_orch.sentinel.status import SentinelStatus
from set_orch.sentinel.inbox import check_inbox
from set_orch.sentinel.set_dir import ensure_set_dir

__all__ = [
    "SentinelEventLogger",
    "SentinelFindings",
    "SentinelStatus",
    "check_inbox",
    "ensure_set_dir",
]
