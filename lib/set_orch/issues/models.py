"""Data models for the issue management engine."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS = 3600  # 1 hour


class IssueState(str, Enum):
    NEW = "new"
    INVESTIGATING = "investigating"
    DIAGNOSED = "diagnosed"
    AWAITING_APPROVAL = "awaiting_approval"
    FIXING = "fixing"
    VERIFYING = "verifying"
    DEPLOYING = "deploying"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    MUTED = "muted"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


VALID_TRANSITIONS: dict[IssueState, set[IssueState]] = {
    IssueState.NEW: {
        IssueState.INVESTIGATING, IssueState.DIAGNOSED,
        IssueState.DISMISSED, IssueState.MUTED, IssueState.SKIPPED,
        IssueState.RESOLVED,
    },
    IssueState.INVESTIGATING: {
        IssueState.DIAGNOSED, IssueState.RESOLVED, IssueState.FAILED, IssueState.CANCELLED,
    },
    IssueState.DIAGNOSED: {
        IssueState.AWAITING_APPROVAL, IssueState.FIXING, IssueState.RESOLVED,
        IssueState.DISMISSED, IssueState.MUTED,
        IssueState.INVESTIGATING, IssueState.SKIPPED,
    },
    IssueState.AWAITING_APPROVAL: {
        IssueState.FIXING, IssueState.RESOLVED, IssueState.DISMISSED,
        IssueState.INVESTIGATING, IssueState.CANCELLED,
    },
    IssueState.FIXING: {
        IssueState.VERIFYING, IssueState.RESOLVED, IssueState.FAILED, IssueState.CANCELLED,
    },
    IssueState.VERIFYING: {
        IssueState.DEPLOYING, IssueState.RESOLVED, IssueState.FAILED, IssueState.CANCELLED,
    },
    IssueState.DEPLOYING: {
        IssueState.RESOLVED, IssueState.FAILED,
    },
    IssueState.FAILED: {
        IssueState.INVESTIGATING, IssueState.DISMISSED, IssueState.NEW,
        # Allow FAILED → RESOLVED when the underlying cause is resolved
        # by something other than the issue pipeline — most commonly when
        # the orchestrator merges the affected change (observed on
        # craftbrew-run-20260409-0034, ISS-001 and ISS-007 spammed error
        # logs every 30s because `failed → resolved` was rejected).
        IssueState.RESOLVED,
    },
    IssueState.MUTED: {
        IssueState.NEW,
    },
    IssueState.CANCELLED: {
        IssueState.NEW, IssueState.DISMISSED,
    },
    IssueState.SKIPPED: {
        IssueState.NEW,
    },
    # Terminal states — no transitions out
    IssueState.RESOLVED: set(),
    IssueState.DISMISSED: set(),
}

# States that are considered "active" (not terminal)
ACTIVE_STATES = {
    s for s in IssueState
    if s not in (IssueState.RESOLVED, IssueState.DISMISSED,
                 IssueState.MUTED, IssueState.SKIPPED, IssueState.CANCELLED)
}

# States that need attention from the user
ATTENTION_STATES = {
    IssueState.NEW, IssueState.DIAGNOSED, IssueState.AWAITING_APPROVAL,
}

# States where work is in progress
IN_PROGRESS_STATES = {
    IssueState.INVESTIGATING, IssueState.FIXING,
    IssueState.VERIFYING, IssueState.DEPLOYING,
}

# Terminal/done states
DONE_STATES = {
    IssueState.RESOLVED, IssueState.DISMISSED, IssueState.MUTED,
    IssueState.SKIPPED, IssueState.CANCELLED, IssueState.FAILED,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def compute_fingerprint(
    source: str, error_summary: str, affected_change: Optional[str] = None
) -> str:
    """Normalize and hash to detect duplicate reports of the same error."""
    normalized = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.\d]*[Z+\-\d:]*', '', error_summary)
    normalized = re.sub(r'PID \d+', 'PID X', normalized)
    normalized = re.sub(r'/tmp/[^\s]+', '/tmp/...', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    key = f"{source}:{affected_change or ''}:{normalized}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


@dataclass
class Diagnosis:
    root_cause: str
    impact: str = "unknown"  # low | medium | high | critical
    confidence: float = 0.0
    fix_scope: str = "unknown"  # single_file | multi_file | cross_module
    suggested_fix: str = ""
    affected_files: list[str] = field(default_factory=list)
    related_issues: list[str] = field(default_factory=list)
    suggested_group: Optional[str] = None
    group_reason: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    raw_output: str = ""
    fix_target: str = "consumer"  # "consumer" = fix in consumer project, "framework" = fix in set-core

    def to_dict(self) -> dict:
        return {
            "root_cause": self.root_cause,
            "impact": self.impact,
            "confidence": self.confidence,
            "fix_scope": self.fix_scope,
            "suggested_fix": self.suggested_fix,
            "affected_files": self.affected_files,
            "related_issues": self.related_issues,
            "suggested_group": self.suggested_group,
            "group_reason": self.group_reason,
            "tags": self.tags,
            "raw_output": self.raw_output,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Diagnosis:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Issue:
    id: str
    environment: str
    environment_path: str
    source: str  # sentinel | gate | watchdog | user
    state: IssueState
    severity: str = "unknown"  # unknown | low | medium | high | critical
    group_id: Optional[str] = None

    # Detection context
    error_summary: str = ""
    error_detail: str = ""
    fingerprint: str = ""
    affected_files: list[str] = field(default_factory=list)
    affected_change: Optional[str] = None
    detected_at: str = field(default_factory=now_iso)
    source_finding_id: Optional[str] = None
    occurrence_count: int = 1

    # Investigation
    diagnosis: Optional[Diagnosis] = None
    investigation_session: Optional[str] = None

    # Fix
    change_name: Optional[str] = None
    fix_agent_pid: Optional[int] = None

    # Policy
    timeout_deadline: Optional[str] = None
    timeout_started_at: Optional[str] = None
    policy_matched: Optional[str] = None
    auto_fix: bool = False

    # Muting
    mute_pattern: Optional[str] = None

    # Retry tracking
    retry_count: int = 0
    max_retries: int = 2

    # Timestamps
    updated_at: str = field(default_factory=now_iso)
    resolved_at: Optional[str] = None
    diagnosed_at: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "environment": self.environment,
            "environment_path": self.environment_path,
            "source": self.source,
            "state": self.state.value,
            "severity": self.severity,
            "group_id": self.group_id,
            "error_summary": self.error_summary,
            "error_detail": self.error_detail,
            "fingerprint": self.fingerprint,
            "affected_files": self.affected_files,
            "affected_change": self.affected_change,
            "detected_at": self.detected_at,
            "source_finding_id": self.source_finding_id,
            "occurrence_count": self.occurrence_count,
            "diagnosis": self.diagnosis.to_dict() if self.diagnosis else None,
            "investigation_session": self.investigation_session,
            "change_name": self.change_name,
            "fix_agent_pid": self.fix_agent_pid,
            "timeout_deadline": self.timeout_deadline,
            "timeout_started_at": self.timeout_started_at,
            "policy_matched": self.policy_matched,
            "auto_fix": self.auto_fix,
            "mute_pattern": self.mute_pattern,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "updated_at": self.updated_at,
            "resolved_at": self.resolved_at,
            "diagnosed_at": self.diagnosed_at,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Issue:
        d = dict(data)
        d["state"] = IssueState(d["state"])
        diag = d.pop("diagnosis", None)
        if diag:
            d["diagnosis"] = Diagnosis.from_dict(diag)
        # Filter to known fields
        known = cls.__dataclass_fields__
        d = {k: v for k, v in d.items() if k in known}
        return cls(**d)


@dataclass
class IssueGroup:
    id: str
    name: str
    issue_ids: list[str]
    primary_issue: str
    state: IssueState = IssueState.NEW
    change_name: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    reason: str = ""
    created_by: str = "user"  # user | agent

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "issue_ids": self.issue_ids,
            "primary_issue": self.primary_issue,
            "state": self.state.value,
            "change_name": self.change_name,
            "created_at": self.created_at,
            "reason": self.reason,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> IssueGroup:
        d = dict(data)
        d["state"] = IssueState(d["state"])
        known = cls.__dataclass_fields__
        d = {k: v for k, v in d.items() if k in known}
        return cls(**d)


@dataclass
class MutePattern:
    id: str
    pattern: str
    reason: str
    created_by: str = "user"  # user | agent | policy
    created_at: str = field(default_factory=now_iso)
    expires_at: Optional[str] = None
    match_count: int = 0
    last_matched_at: Optional[str] = None
    source_issue_id: Optional[str] = None

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) >= expiry
        except ValueError:
            return False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pattern": self.pattern,
            "reason": self.reason,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "match_count": self.match_count,
            "last_matched_at": self.last_matched_at,
            "source_issue_id": self.source_issue_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MutePattern:
        known = cls.__dataclass_fields__
        d = {k: v for k, v in data.items() if k in known}
        return cls(**d)
