"""Sentinel structured event logging, findings, status, and inbox.

Usage:
    from wt_orch.sentinel import SentinelEventLogger, SentinelFindings, SentinelStatus

All sentinel runtime data lives under .wt/sentinel/ in the project root.
"""

from wt_orch.sentinel.events import SentinelEventLogger
from wt_orch.sentinel.findings import SentinelFindings
from wt_orch.sentinel.status import SentinelStatus
from wt_orch.sentinel.inbox import check_inbox
from wt_orch.sentinel.wt_dir import ensure_wt_dir

__all__ = [
    "SentinelEventLogger",
    "SentinelFindings",
    "SentinelStatus",
    "check_inbox",
    "ensure_wt_dir",
]
