"""Issue Manager — deterministic state machine for issue lifecycle."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from .audit import AuditLog
from .models import (
    VALID_TRANSITIONS,
    Issue,
    IssueGroup,
    IssueState,
    now_iso,
)
from .policy import IssuesPolicyConfig, PolicyEngine
from .registry import IssueRegistry

logger = logging.getLogger(__name__)


class InvalidTransitionError(Exception):
    pass


class IssueManager:
    """Deterministic controller. No LLM calls — only state transitions and agent lifecycle."""

    def __init__(
        self,
        registry: IssueRegistry,
        audit: AuditLog,
        policy: PolicyEngine,
        investigator=None,
        fixer=None,
        deployer=None,
        notifier=None,
    ):
        self.registry = registry
        self.audit = audit
        self.policy = policy
        self.investigator = investigator
        self.fixer = fixer
        self.deployer = deployer
        self.notifier = notifier
        self._reminder_sent: dict[str, set[int]] = {}  # issue_id -> {50, 80}

    @property
    def enabled(self) -> bool:
        return self.policy.config.enabled

    # --- Core tick loop ---

    def tick(self):
        """Called every N seconds. Pure state machine — no LLM calls."""
        for issue in self.registry.active():
            self._process(issue)
        for group in self.registry.active_groups():
            self._process_group(group)
        self._check_timeout_reminders()

    def _process(self, issue: Issue):
        if issue.group_id:
            return  # group drives lifecycle

        match issue.state:
            case IssueState.NEW:
                if self.registry.matches_mute(issue.error_summary, issue.error_detail):
                    self._transition(issue, IssueState.MUTED)
                elif self.policy.should_auto_investigate(issue):
                    if self._can_spawn_investigation():
                        self._spawn_investigation(issue)
                        self._transition(issue, IssueState.INVESTIGATING)

            case IssueState.INVESTIGATING:
                if self.investigator and self.investigator.is_done(issue):
                    diagnosis = self.investigator.collect(issue)
                    if diagnosis:
                        issue.diagnosis = diagnosis
                        if diagnosis.impact and diagnosis.impact != "unknown":
                            issue.severity = diagnosis.impact
                        self._transition(issue, IssueState.DIAGNOSED)
                        self._apply_post_diagnosis_policy(issue)
                    else:
                        self._transition(issue, IssueState.FAILED)
                elif self.investigator and self.investigator.is_timed_out(issue):
                    self.audit.log(issue.id, "investigation_timeout")
                    self.investigator.kill(issue)
                    # Try to collect partial results — proposal.md may exist even after timeout
                    diagnosis = self.investigator.collect(issue)
                    if diagnosis:
                        issue.diagnosis = diagnosis
                        if diagnosis.impact and diagnosis.impact != "unknown":
                            issue.severity = diagnosis.impact
                        self._transition(issue, IssueState.DIAGNOSED)
                        self._apply_post_diagnosis_policy(issue)
                    else:
                        self._transition(issue, IssueState.DIAGNOSED)

            case IssueState.DIAGNOSED:
                pass  # Waiting state — routed by _apply_post_diagnosis_policy or user action

            case IssueState.AWAITING_APPROVAL:
                if issue.timeout_deadline and now_iso() >= issue.timeout_deadline:
                    self.audit.log(issue.id, "timeout_auto_approved",
                                   waited_seconds=self._elapsed_since_timeout_start(issue))
                    self._start_fix(issue)

            case IssueState.FIXING:
                if self.fixer and self.fixer.is_done(issue):
                    result = self.fixer.collect(issue)
                    if result and result.get("success"):
                        # Fix agent (/opsx:apply) handles implement + test + commit + archive
                        # No separate verify/deploy needed — go straight to RESOLVED
                        issue.resolved_at = now_iso()
                        self._transition(issue, IssueState.RESOLVED)
                        self._mark_source_finding_resolved(issue)
                        if self.notifier:
                            self.notifier.on_resolved(issue)
                    else:
                        self._handle_failure(issue, result)

            case IssueState.VERIFYING:
                # Legacy path — kept for in-flight issues during upgrade
                if self.fixer and self.fixer.verify_done(issue):
                    issue.resolved_at = now_iso()
                    self._transition(issue, IssueState.RESOLVED)
                    if self.notifier:
                        self.notifier.on_resolved(issue)

            case IssueState.DEPLOYING:
                # Legacy path — deployer is not used, resolve immediately
                issue.resolved_at = now_iso()
                self._transition(issue, IssueState.RESOLVED)
                if self.notifier:
                    self.notifier.on_resolved(issue)

            case IssueState.FAILED:
                if issue.retry_count < issue.max_retries:
                    if self._retry_backoff_elapsed(issue):
                        issue.retry_count += 1
                        self.audit.log(issue.id, "auto_retry", attempt=issue.retry_count)
                        self._transition(issue, IssueState.INVESTIGATING)
                        if self._can_spawn_investigation():
                            self._spawn_investigation(issue)

    def _process_group(self, group: IssueGroup):
        """Groups follow the same lifecycle as individual issues."""
        match group.state:
            case IssueState.FIXING:
                if self.fixer and self.fixer.is_done_group(group):
                    results = self.fixer.collect_group(group)
                    self._handle_group_results(group, results)
            case _:
                pass  # Most group states are driven by user actions

    # --- State transitions ---

    def _transition(self, issue: Issue, new_state: IssueState):
        """Validate and execute state transition."""
        old_state = issue.state
        valid = VALID_TRANSITIONS.get(old_state, set())
        if new_state not in valid:
            raise InvalidTransitionError(
                f"Cannot transition {issue.id} from {old_state.value} to {new_state.value}. "
                f"Valid: {[s.value for s in valid]}"
            )
        issue.state = new_state
        issue.updated_at = now_iso()
        self.registry.save()
        self.audit.log(issue.id, f"transition:{new_state.value}",
                       from_state=old_state.value, to_state=new_state.value)
        logger.info(f"{issue.id}: {old_state.value} → {new_state.value}")

    # --- Policy routing ---

    def _apply_post_diagnosis_policy(self, issue: Issue):
        """Called once after diagnosis. Routes based on policy."""
        if self.policy.can_auto_fix(issue):
            timeout = self.policy.get_timeout(issue)
            if timeout == 0:
                self._start_fix(issue)
            elif timeout is not None:
                issue.timeout_deadline = (
                    datetime.now(timezone.utc) + timedelta(seconds=timeout)
                ).isoformat()
                issue.timeout_started_at = now_iso()
                issue.auto_fix = True
                issue.policy_matched = f"auto-fix-timeout-{timeout}s"
                self.registry.save()
                self._transition(issue, IssueState.AWAITING_APPROVAL)
                if self.notifier:
                    self.notifier.on_awaiting(issue, timeout)
        # else: stays DIAGNOSED, user decides

    def _start_fix(self, issue: Issue):
        """Start fix if concurrency allows (max 1 fix at a time)."""
        if self._can_spawn_fix():
            self._transition(issue, IssueState.FIXING)
            self._spawn_fix(issue)
        else:
            self.audit.log(issue.id, "fix_queued", reason="another_fix_running")

    def _handle_failure(self, issue: Issue, result):
        self._transition(issue, IssueState.FAILED)
        self.audit.log(issue.id, "fix_failed",
                       retry_count=issue.retry_count,
                       max_retries=issue.max_retries,
                       error=str(result) if result else "unknown")
        if self.notifier:
            self.notifier.on_failed(issue)

    def _deploy(self, issue: Issue):
        if self.deployer:
            self.deployer.deploy(issue)

    def _mark_source_finding_resolved(self, issue: Issue):
        """Mark the source sentinel finding as fixed when issue resolves."""
        if not issue.source_finding_id or not issue.environment_path:
            return
        detector = getattr(self, '_detector', None)
        if detector and hasattr(detector, 'mark_finding_resolved'):
            detector.mark_finding_resolved(issue.environment_path, issue.source_finding_id)

    # --- Agent spawning ---

    def _spawn_investigation(self, issue: Issue):
        if self.investigator:
            self.investigator.spawn(issue)
            self.audit.log(issue.id, "investigation_spawned")

    def _spawn_fix(self, issue: Issue):
        if self.fixer:
            self.fixer.spawn(issue)
            self.audit.log(issue.id, "fix_spawned",
                           change_name=issue.change_name)
            if self.notifier:
                self.notifier.on_fix_started(issue)

    # --- Concurrency ---

    def _can_spawn_investigation(self) -> bool:
        active = self.registry.count_by_state(IssueState.INVESTIGATING)
        return active < self.policy.config.concurrency.max_parallel_investigations

    def _can_spawn_fix(self) -> bool:
        return self.registry.count_by_state(IssueState.FIXING) == 0

    # --- Timeouts ---

    def _elapsed_since_timeout_start(self, issue: Issue) -> int:
        if not issue.timeout_started_at:
            return 0
        try:
            started = datetime.fromisoformat(issue.timeout_started_at)
            return int((datetime.now(timezone.utc) - started).total_seconds())
        except ValueError:
            return 0

    def _retry_backoff_elapsed(self, issue: Issue) -> bool:
        backoff = self.policy.config.retry.backoff_seconds
        try:
            updated = datetime.fromisoformat(issue.updated_at)
            elapsed = (datetime.now(timezone.utc) - updated).total_seconds()
            return elapsed >= backoff
        except ValueError:
            return True

    def _check_timeout_reminders(self):
        """Send notifications at 50% and 80% of timeout window."""
        if not self.notifier:
            return
        for issue in self.registry.by_state(IssueState.AWAITING_APPROVAL):
            if not issue.timeout_started_at or not issue.timeout_deadline:
                continue
            pct = self._timeout_elapsed_pct(issue)
            sent = self._reminder_sent.setdefault(issue.id, set())
            if pct >= 80 and 80 not in sent:
                self.notifier.on_timeout_reminder(issue, 80)
                sent.add(80)
            elif pct >= 50 and 50 not in sent:
                self.notifier.on_timeout_reminder(issue, 50)
                sent.add(50)

    def _timeout_elapsed_pct(self, issue: Issue) -> float:
        if not issue.timeout_started_at or not issue.timeout_deadline:
            return 0.0
        try:
            started = datetime.fromisoformat(issue.timeout_started_at)
            deadline = datetime.fromisoformat(issue.timeout_deadline)
            now = datetime.now(timezone.utc)
            total = (deadline - started).total_seconds()
            elapsed = (now - started).total_seconds()
            return (elapsed / total * 100) if total > 0 else 100.0
        except ValueError:
            return 0.0

    # --- Group handling ---

    def _handle_group_results(self, group: IssueGroup, results: dict[str, bool]):
        resolved = [iid for iid, ok in results.items() if ok]
        failed = [iid for iid, ok in results.items() if not ok]

        for iid in resolved:
            issue = self.registry.get(iid)
            if issue:
                issue.resolved_at = now_iso()
                self._transition(issue, IssueState.RESOLVED)

        if failed:
            for iid in failed:
                issue = self.registry.get(iid)
                if issue:
                    issue.group_id = None
                    self._transition(issue, IssueState.FAILED)

        group.state = IssueState.RESOLVED
        self.registry.save_group(group)
        self.audit.log_group(group.id, "resolved", resolved=resolved, failed=failed)

    # --- User actions (called from REST API) ---

    def action_investigate(self, issue_id: str):
        issue = self.registry.get(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        self._transition(issue, IssueState.INVESTIGATING)
        self._spawn_investigation(issue)

    def action_fix(self, issue_id: str):
        issue = self.registry.get(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        self._start_fix(issue)

    def action_dismiss(self, issue_id: str):
        issue = self.registry.get(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        self._transition(issue, IssueState.DISMISSED)

    def action_cancel(self, issue_id: str):
        issue = self.registry.get(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        if issue.state == IssueState.INVESTIGATING and self.investigator:
            self.investigator.kill(issue)
        elif issue.state in (IssueState.FIXING, IssueState.VERIFYING) and self.fixer:
            self.fixer.kill(issue)
        self._transition(issue, IssueState.CANCELLED)

    def action_skip(self, issue_id: str, reason: str = ""):
        issue = self.registry.get(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        self._transition(issue, IssueState.SKIPPED)
        self.audit.log(issue.id, "skipped", reason=reason)

    def action_mute(self, issue_id: str, pattern: Optional[str] = None):
        issue = self.registry.get(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        import re as _re
        pat = pattern or _re.escape(issue.error_summary[:100])
        self.registry.add_mute(
            pattern=pat,
            reason=f"Muted from {issue.id}",
            source_issue_id=issue.id,
        )
        issue.mute_pattern = pat
        self._transition(issue, IssueState.MUTED)

    def action_extend_timeout(self, issue_id: str, extra_seconds: int):
        issue = self.registry.get(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        if issue.state != IssueState.AWAITING_APPROVAL or not issue.timeout_deadline:
            raise InvalidTransitionError("Can only extend timeout for AWAITING_APPROVAL issues")
        new_deadline = (
            datetime.fromisoformat(issue.timeout_deadline) + timedelta(seconds=extra_seconds)
        ).isoformat()
        issue.timeout_deadline = new_deadline
        self.registry.save()
        self.audit.log(issue.id, "timeout_extended", extra_seconds=extra_seconds,
                       new_deadline=new_deadline)
        # Reset reminders
        self._reminder_sent.pop(issue.id, None)

    def action_group(self, issue_ids: list[str], name: str, reason: str = "") -> IssueGroup:
        return self.registry.create_group(
            name=name, issue_ids=issue_ids, reason=reason, created_by="user"
        )

    def action_reopen(self, issue_id: str):
        issue = self.registry.get(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        self._transition(issue, IssueState.NEW)

    # --- Registration (called from DetectionBridge) ---

    def register(self, **kwargs) -> Optional[Issue]:
        """Register a new issue. Returns None if muted or duplicate."""
        severity_hint = kwargs.pop("severity_hint", "unknown")
        mute = self.registry.matches_mute(
            kwargs.get("error_summary", ""),
            kwargs.get("error_detail", ""),
        )
        if not self.policy.should_register(
            source=kwargs.get("source", ""),
            severity_hint=severity_hint,
            error_summary=kwargs.get("error_summary", ""),
            mute_match=mute,
        ):
            return None

        issue = self.registry.register(**kwargs)
        if issue:
            self.audit.log(issue.id, "registered",
                           source=issue.source, environment=issue.environment)
            if self.notifier:
                self.notifier.on_registered(issue)
        return issue
