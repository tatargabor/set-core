"""Issue Manager — deterministic state machine for issue lifecycle."""

from __future__ import annotations

import logging
import os
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
        # Pick up external writers (sentinel's escalate_change_to_fix_iss,
        # recovery-tool purges) — without this the cached snapshot from
        # startup never sees new issues.
        try:
            changed = self.registry.reload_from_disk()
            if changed:
                logger.info("Registry reloaded from disk; %d active issue(s)",
                            sum(1 for _ in self.registry.active()))
        except Exception as e:
            logger.warning("Registry reload failed: %s", e)
        for issue in self.registry.active():
            # Auto-resolve if orchestrator already merged the affected change
            if self._check_affected_change_merged(issue):
                continue
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
                        self._retry_parent_after_resolved(issue)
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
        if new_state == IssueState.DIAGNOSED and not issue.diagnosed_at:
            issue.diagnosed_at = now_iso()
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

    def _retry_parent_after_resolved(self, issue: Issue) -> None:
        """After a circuit-breaker fix-iss resolves, reset the parent change
        back to `pending` so the orchestrator picks it up again.

        Without this, the parent stays `failed:<reason>` (terminal) forever —
        the fix-iss child merged its focused fix, but the parent's own scope
        (which was aborted mid-run by the breaker) is never retried. The
        orchestrator's dispatcher only picks up `pending` changes, so we have
        to actively un-fail the parent.

        Scope is intentionally narrow:
        - only for `source.startswith("circuit-breaker:")` issues
        - only if the parent is in a `failed:*` terminal state
        - uses `reset_change_to_pending()` so all gate cache/stuck-loop
          residuals are cleared — a fresh dispatch after the child's fix has
          been merged into main sees the updated code and a clean slate.
        """
        if not issue.source.startswith("circuit-breaker:"):
            return
        parent_name = issue.affected_change
        if not parent_name:
            return
        env_path = issue.environment_path
        if not env_path:
            return
        try:
            from pathlib import Path
            from ..state import locked_state
            from ..recovery import reset_change_to_pending
            from ..change_cleanup import cleanup_change_artifacts
            state_file = Path(env_path) / "orchestration-state.json"
            if not state_file.is_file():
                logger.warning(
                    "Cannot retry parent %s for %s: state file missing at %s",
                    parent_name, issue.id, state_file,
                )
                return

            # Clean up on-disk artifacts BEFORE the in-memory reset. If we
            # reset first, the dispatcher's next cycle sees the dangling
            # branch+worktree, bumps to `<name>-2`, and we've just seeded the
            # very collision this path was meant to prevent. Cleanup failure
            # is non-blocking: we still reset so the parent exits the terminal
            # failed:* state — a half-reset is worse than a degraded-cleanup
            # reset because it leaves the state machine stuck.
            project_path = str(Path(env_path).resolve())
            cleanup_result = None
            cleanup_error = None
            try:
                cleanup_result = cleanup_change_artifacts(parent_name, project_path)
                if cleanup_result.warnings:
                    self.audit.log(
                        issue.id,
                        "parent_retry_cleanup_degraded",
                        parent=parent_name,
                        warnings=cleanup_result.warnings,
                    )
            except Exception as _ce:
                cleanup_error = str(_ce)
                logger.warning(
                    "cleanup_change_artifacts failed for parent %s: %s",
                    parent_name, _ce, exc_info=True,
                )
                self.audit.log(
                    issue.id,
                    "parent_retry_cleanup_degraded",
                    parent=parent_name,
                    error=cleanup_error,
                )

            reset_done = False
            with locked_state(str(state_file)) as s:
                for ch in s.changes:
                    if ch.name != parent_name:
                        continue
                    if not ch.status.startswith("failed:"):
                        logger.info(
                            "Parent %s is %s (not failed:*) — skipping auto-retry",
                            parent_name, ch.status,
                        )
                        break
                    prior_status = ch.status
                    reset_change_to_pending(ch)
                    reset_done = True
                    self.audit.log(
                        issue.id,
                        "parent_retry_requested",
                        parent=parent_name,
                        prior_status=prior_status,
                        cleanup_worktree_removed=(
                            cleanup_result.worktree_removed if cleanup_result else False
                        ),
                        cleanup_branch_removed=(
                            cleanup_result.branch_removed if cleanup_result else False
                        ),
                        cleanup_warnings=(
                            cleanup_result.warnings if cleanup_result else []
                        ),
                    )
                    logger.info(
                        "Reset parent %s (%s → pending) after %s resolved "
                        "(cleanup: wt=%s branch=%s)",
                        parent_name, prior_status, issue.id,
                        cleanup_result.worktree_removed if cleanup_result else "skipped",
                        cleanup_result.branch_removed if cleanup_result else "skipped",
                    )
                    break
            if not reset_done:
                logger.info(
                    "No failed parent found for %s (affected_change=%s)",
                    issue.id, parent_name,
                )
        except Exception as e:
            logger.warning(
                "Failed to reset parent %s after %s: %s",
                parent_name, issue.id, e,
            )

    def _deploy(self, issue: Issue):
        if self.deployer:
            self.deployer.deploy(issue)

    def _check_affected_change_merged(self, issue: Issue) -> bool:
        """Check if the affected change was merged by the orchestrator.

        If so, auto-resolve the issue — the orchestrator already fixed the problem.
        Returns True if issue was auto-resolved (caller should skip _process).
        """
        if not issue.affected_change or not issue.environment_path:
            return False
        if issue.state in (IssueState.RESOLVED, IssueState.DISMISSED,
                           IssueState.MUTED, IssueState.CANCELLED, IssueState.SKIPPED):
            return False

        import json, os
        from ..paths import LineagePaths as _LP_im
        state_path = _LP_im(issue.environment_path).state_file
        if not os.path.isfile(state_path):
            return False
        try:
            with open(state_path) as f:
                state = json.load(f)
            for change in state.get("changes", []):
                if change.get("name") == issue.affected_change and change.get("status") == "merged":
                    logger.info("%s: affected change '%s' merged by orchestrator — auto-resolving",
                                issue.id, issue.affected_change)
                    self.audit.log(issue.id, "auto_resolved_by_orchestrator",
                                   affected_change=issue.affected_change)
                    issue.resolved_at = now_iso()
                    self._transition(issue, IssueState.RESOLVED)
                    self._mark_source_finding_resolved(issue)

                    # Purge the orphan fix-iss child that was never needed —
                    # the parent resolved its own issue by merging. Without
                    # this, the linked child sits pending on disk, gets
                    # picked up by the dispatcher next cycle, and an agent
                    # spawns against a stale proposal.
                    try:
                        purge_result = _purge_fix_iss_child(
                            issue,
                            str(state_path),
                            issue.environment_path,
                            reason="parent_merged",
                        )
                        if purge_result["state_removed"] or purge_result["dir_removed"]:
                            self.audit.log(
                                issue.id, "fix_iss_orphan_purged",
                                child_name=issue.change_name,
                                state_removed=purge_result["state_removed"],
                                dir_removed=purge_result["dir_removed"],
                                reason="parent_merged",
                            )
                    except Exception as _pe:
                        logger.warning(
                            "%s: orphan fix-iss purge failed for parent=%s: %s",
                            issue.id, issue.affected_change, _pe, exc_info=True,
                        )

                    if self.notifier:
                        self.notifier.on_resolved(issue)
                    return True
        except (json.JSONDecodeError, OSError):
            pass
        return False

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

    def action_resolve(self, issue_id: str, reason: str = "manual_resolve"):
        """Operator escape hatch — transition an issue to RESOLVED.

        Used when a diagnosed issue blocks the merge queue and automatic
        resolution has not fired yet. Goes through _transition so any
        active investigator/fixer is killed, the state machine validates
        the transition, and audit entries record the operator rationale.
        """
        issue = self.registry.get(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        if issue.state == IssueState.INVESTIGATING and self.investigator:
            try:
                self.investigator.kill(issue)
            except Exception:
                logger.warning(
                    "Failed to kill investigator on resolve for %s", issue_id, exc_info=True,
                )
        elif issue.state in (IssueState.FIXING, IssueState.VERIFYING) and self.fixer:
            try:
                self.fixer.kill(issue)
            except Exception:
                logger.warning(
                    "Failed to kill fixer on resolve for %s", issue_id, exc_info=True,
                )
        self._transition(issue, IssueState.RESOLVED)
        from datetime import datetime, timezone

        issue.resolved_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        self.registry.save()
        self.audit.log(issue.id, "manual_resolve", reason=reason)

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
            affected_change=kwargs.get("affected_change"),
        ):
            logger.info(
                "Skipping issue registration: severity=%s change=%s summary=%s",
                severity_hint,
                kwargs.get("affected_change"),
                (kwargs.get("error_summary") or "")[:80],
            )
            return None

        issue = self.registry.register(**kwargs)
        if issue:
            self.audit.log(issue.id, "registered",
                           source=issue.source, environment=issue.environment)
            if self.notifier:
                self.notifier.on_registered(issue)
        return issue


# ─── Fix-iss Auto-Escalation (section 10 of fix-replan-stuck-gate-and-decomposer)
# Module-level helper (not on IssueManager) so the engine/verifier can invoke
# it without holding an IssueManager handle — escalation is a single-shot
# state mutation + proposal write, driven from circuit breakers.

_FRAMEWORK_PATH_PREFIXES = (
    "lib/set_orch/",
    "modules/",
    "templates/core/rules/",
    ".claude/rules/",
)


def _classify_fix_target(finding_paths: list[str]) -> str:
    """Return "framework" if any finding path lives under set-core's own
    source tree, otherwise "consumer". The distinction decides whether the
    fix-iss proposal targets set-core (framework bug) or the user project.
    """
    for path in finding_paths:
        if not path:
            continue
        for prefix in _FRAMEWORK_PATH_PREFIXES:
            if path.startswith(prefix):
                return "framework"
    return "consumer"


_ACTIVE_CHILD_STATUSES = frozenset({
    "dispatched", "running", "verifying", "integrating",
})

_TERMINAL_FAILURE_STATUSES = frozenset({
    "integration-failed", "merge-failed",
})

_RESOLVED_ISSUE_STATES = frozenset({
    "resolved", "dismissed", "muted", "cancelled", "skipped",
})


def scan_fix_iss_orphans(project_path: str) -> list[dict]:
    """Enumerate orphan fix-iss artifacts across state, registry, and filesystem.

    An entry is an orphan if any of:
    1. Parent change status is `merged` AND linked fix-iss child state entry
       still exists with non-terminal status.
    2. Issue is RESOLVED/DISMISSED/MUTED/CANCELLED AND linked fix-iss child
       state entry exists with non-terminal status.
    3. openspec `fix-iss-*` directory exists with NO corresponding
       state.changes entry AND NO active issue in the registry referencing it.

    Returns a list of orphan records; each is a dict with:
        child_name, parent_name, parent_status, issue_id, issue_state,
        state_entry_present, dir_present, reason (which criterion matched),
        safe_to_remove (bool — False if child is actively dispatched).
    """
    import json as _json
    from pathlib import Path as _Path

    project = _Path(project_path).resolve()
    state_file = project / "orchestration-state.json"
    registry_file = project / ".set" / "issues" / "registry.json"
    openspec_changes = project / "openspec" / "changes"

    # Load state (if present)
    state_changes: dict[str, dict] = {}
    if state_file.is_file():
        try:
            with open(state_file) as f:
                _s = _json.load(f)
            for c in _s.get("changes", []):
                if isinstance(c, dict) and c.get("name"):
                    state_changes[c["name"]] = c
        except (OSError, ValueError):
            pass

    # Load registry (if present)
    issues: list[dict] = []
    if registry_file.is_file():
        try:
            with open(registry_file) as f:
                _r = _json.load(f)
            issues = [i for i in _r.get("issues", []) if isinstance(i, dict)]
        except (OSError, ValueError):
            pass

    # Index issues by linked change_name for fast cross-lookup
    issues_by_child: dict[str, dict] = {}
    for i in issues:
        cn = i.get("change_name")
        if cn:
            issues_by_child[cn] = i

    # Index openspec fix-iss dirs
    existing_dirs: set[str] = set()
    if openspec_changes.is_dir():
        for entry in openspec_changes.iterdir():
            if entry.is_dir() and entry.name.startswith("fix-iss-"):
                existing_dirs.add(entry.name)

    orphans: list[dict] = []
    seen: set[str] = set()

    # Criteria 1 & 2: state-entry-based scan
    for name, ch in state_changes.items():
        if not name.startswith("fix-iss-"):
            continue
        status = ch.get("status", "")
        if status in _ACTIVE_CHILD_STATUSES or status == "merged":
            continue
        if status in _TERMINAL_FAILURE_STATUSES:
            continue

        # Find the parent: first via issue registry, fall back to the
        # fix-iss state entry's `depends_on` field (which _register_fix_iss_in_state
        # populates with `[parent_name]`).
        issue = issues_by_child.get(name)
        parent_name = issue.get("affected_change") if issue else None
        if not parent_name:
            deps = ch.get("depends_on") or []
            if isinstance(deps, list) and deps:
                parent_name = deps[0]
        parent = state_changes.get(parent_name) if parent_name else None
        parent_status = parent.get("status") if parent else "<unknown>"
        issue_state = (issue.get("state") or "").lower() if issue else ""

        reason = None
        if parent and parent.get("status") == "merged":
            reason = "parent_merged"
        elif issue_state in _RESOLVED_ISSUE_STATES:
            reason = "issue_resolved"

        if reason is None:
            continue

        orphans.append({
            "child_name": name,
            "parent_name": parent_name or "<unknown>",
            "parent_status": parent_status,
            "issue_id": issue.get("id") if issue else None,
            "issue_state": issue_state,
            "state_entry_present": True,
            "dir_present": name in existing_dirs,
            "reason": reason,
            "safe_to_remove": True,
        })
        seen.add(name)

    # Criterion 3: dir-only divergence (dir present, no state entry, no live issue)
    for dir_name in existing_dirs - seen:
        if dir_name in state_changes:
            continue  # state entry exists, handled above
        issue = issues_by_child.get(dir_name)
        issue_state = (issue.get("state") or "").lower() if issue else ""
        if issue and issue_state not in _RESOLVED_ISSUE_STATES:
            # Live issue still references this child — not an orphan
            continue
        orphans.append({
            "child_name": dir_name,
            "parent_name": (issue.get("affected_change") if issue else "<unknown>"),
            "parent_status": "<no-state>",
            "issue_id": issue.get("id") if issue else None,
            "issue_state": issue_state,
            "state_entry_present": False,
            "dir_present": True,
            "reason": "fs_state_divergence",
            "safe_to_remove": True,
        })

    return orphans


def _purge_fix_iss_child(
    issue: Issue,
    state_file: str,
    project_path: str,
    *,
    reason: str,
) -> dict:
    """Remove an orphan fix-iss child's state entry and openspec directory.

    Safe-by-default: skip removal when the child is actively being worked on.
    Idempotent: a no-op when both state entry and directory are already gone.

    Args:
        issue: The parent issue whose `change_name` links the fix-iss child.
        state_file: Path to `orchestration-state.json`.
        project_path: Project root (used to derive `openspec/changes/` path).
        reason: Short string recorded in the INFO log (e.g. "parent_merged",
            "issue_resolved_manually", "cli_cleanup").

    Returns:
        {"state_removed": bool, "dir_removed": bool, "skipped_reason": str|None}
    """
    import shutil
    from ..state import locked_state

    result = {"state_removed": False, "dir_removed": False, "skipped_reason": None}

    child_name = issue.change_name or ""
    if not child_name or not child_name.startswith("fix-iss-"):
        result["skipped_reason"] = "not_a_fix_iss_child"
        logger.debug(
            "_purge_fix_iss_child: issue %s has no fix-iss child_name (%r), skipping",
            issue.id, child_name,
        )
        return result

    parent_name = issue.affected_change or "<unknown>"
    changes_dir = os.path.join(project_path, "openspec", "changes", child_name)

    # Read current state to decide safety
    child_status: Optional[str] = None
    if os.path.isfile(state_file):
        try:
            import json
            with open(state_file) as f:
                state = json.load(f)
            for c in state.get("changes", []):
                if c.get("name") == child_name:
                    child_status = c.get("status")
                    break
        except (OSError, ValueError):
            logger.debug("_purge_fix_iss_child: could not read %s", state_file)

    # Safety: active dispatches must not be yanked out from under an agent
    if child_status in _ACTIVE_CHILD_STATUSES:
        result["skipped_reason"] = "active_dispatch"
        logger.warning(
            "_purge_fix_iss_child: %s has active status=%s — skipping cleanup "
            "(reason=%s, parent=%s). Use the orphan-cleanup CLI to force.",
            child_name, child_status, reason, parent_name,
        )
        return result

    # Already merged — not an orphan, no-op
    if child_status == "merged":
        result["skipped_reason"] = "already_merged"
        logger.debug(
            "_purge_fix_iss_child: %s already merged — no orphan to clean",
            child_name,
        )
        return result

    # Remove state entry if present
    if child_status is not None:
        try:
            with locked_state(state_file) as s:
                before = len(s.changes)
                s.changes = [c for c in s.changes if c.name != child_name]
                if len(s.changes) < before:
                    result["state_removed"] = True
        except Exception as _e:
            logger.warning(
                "_purge_fix_iss_child: state removal failed for %s: %s",
                child_name, _e,
            )

    # Remove openspec dir if present
    if os.path.isdir(changes_dir):
        try:
            shutil.rmtree(changes_dir)
            result["dir_removed"] = True
        except OSError as _e:
            logger.warning(
                "_purge_fix_iss_child: shutil.rmtree failed for %s: %s",
                changes_dir, _e,
            )

    if result["state_removed"] or result["dir_removed"]:
        logger.info(
            "_purge_fix_iss_child: removed %s (reason=%s, parent=%s, "
            "state_removed=%s, dir_removed=%s)",
            child_name, reason, parent_name,
            result["state_removed"], result["dir_removed"],
        )
    else:
        logger.debug(
            "_purge_fix_iss_child: no artifacts found for %s (reason=%s)",
            child_name, reason,
        )

    return result


def _next_fix_iss_name(openspec_root: str, slug_hint: str) -> str:
    """Pick the next fix-iss-NNN slug. Scans existing `openspec/changes/`
    for the highest fix-iss-<N> and increments.
    """
    import re
    changes_dir = os.path.join(openspec_root, "changes")
    n = 0
    if os.path.isdir(changes_dir):
        for entry in os.listdir(changes_dir):
            m = re.match(r"^fix-iss-(\d{3})", entry)
            if m:
                n = max(n, int(m.group(1)))
    slug = slug_hint or "auto-escalation"
    return f"fix-iss-{n + 1:03d}-{slug}"


def _claim_fix_iss_dir(openspec_root: str, slug_hint: str) -> tuple[str, str]:
    """Atomically claim the next fix-iss-NNN directory name.

    Uses `os.mkdir` (NOT `makedirs(exist_ok=True)`) so two concurrent
    callers cannot both claim the same slug. On collision we bump N and
    retry. Returns (fix_iss_name, change_dir_path).
    """
    import re
    changes_dir = os.path.join(openspec_root, "changes")
    os.makedirs(changes_dir, exist_ok=True)
    slug = slug_hint or "auto-escalation"
    # Start from the current max + 1 and try upward on collision.
    n = 0
    for entry in os.listdir(changes_dir):
        m = re.match(r"^fix-iss-(\d{3})", entry)
        if m:
            n = max(n, int(m.group(1)))
    for attempt in range(20):
        candidate = f"fix-iss-{n + 1 + attempt:03d}-{slug}"
        candidate_dir = os.path.join(changes_dir, candidate)
        try:
            os.mkdir(candidate_dir)
            return candidate, candidate_dir
        except FileExistsError:
            continue
    raise RuntimeError(
        "Could not claim a unique fix-iss-NNN slug after 20 attempts — "
        "concurrent escalations colliding on the same changes/ directory"
    )


def _register_fix_iss_in_state(
    state_file: str, parent_name: str, fix_iss_name: str, target: str,
) -> None:
    """Append the auto-created fix-iss to state.changes so the dispatcher
    picks it up on the next monitor poll.

    Phase is the parent's phase + 1 by default — the fix-iss should run
    AFTER the failed parent (which is now terminal), not concurrently with
    peers that may still be running. It carries `depends_on=[parent]` only
    as a breadcrumb; the phase bump is what actually orders execution.
    """
    from ..state import Change, locked_state
    with locked_state(state_file) as state:
        if any(c.name == fix_iss_name for c in state.changes):
            return
        parent = next((c for c in state.changes if c.name == parent_name), None)
        parent_phase = parent.phase if parent else 1
        change = Change(
            name=fix_iss_name,
            scope=(
                f"Auto-escalated diagnostic change for `{parent_name}` "
                f"(target={target}). See proposal.md for findings."
            ),
            complexity="S",
            change_type="fix",
            depends_on=[parent_name] if parent else [],
            phase=parent_phase + 1,
            status="pending",
            spec_lineage_id=(parent.spec_lineage_id if parent else None),
            sentinel_session_id=(parent.sentinel_session_id if parent else None),
            sentinel_session_started_at=(
                parent.sentinel_session_started_at if parent else None
            ),
        )
        state.changes.append(change)
        # Register the new phase in the phases dict so phase-gate logic lets
        # the fix-iss dispatch. Copy the parent's phase entry structure.
        phases = state.extras.get("phases")
        if isinstance(phases, dict):
            key = str(change.phase)
            if key not in phases:
                phases[key] = {"status": "pending"}
            state.extras["phases"] = phases


def escalate_change_to_fix_iss(
    *,
    state_file: str,
    change_name: str,
    stop_gate: str,
    findings: list | None = None,
    escalation_reason: str = "retry_budget_exhausted",
    event_bus=None,
) -> str:
    """Create a diagnostic fix-iss change for a parent that hit a circuit
    breaker (retry budget / stuck loop / token runaway).

    Writes `openspec/changes/<fix-iss-name>/proposal.md`, updates the parent
    change's `fix_iss_child` on state, and emits `FIX_ISS_ESCALATED`.

    Returns the new change name.
    """
    import os as _os
    import re as _re
    from datetime import datetime as _dt
    from ..state import load_state, locked_state, update_change_field

    # Resolve openspec root from state_file path (state lives alongside
    # openspec/ under a project root).
    project_root = _os.path.dirname(_os.path.abspath(state_file))
    # state_file may live under set/ or similar; walk up until we find openspec/
    for _ in range(8):
        if _os.path.isdir(_os.path.join(project_root, "openspec")):
            break
        parent = _os.path.dirname(project_root)
        if parent == project_root:
            break
        project_root = parent
    openspec_root = _os.path.join(project_root, "openspec")

    # Idempotency: if the parent already has a linked fix-iss child that is
    # still live, return the existing name instead of creating a duplicate.
    # This handles two scenarios:
    # 1. Legitimate re-escalation racing (two circuit-breakers firing close
    #    together on the same parent).
    # 2. Operator-driven purge then re-trigger: the state link points at a
    #    gone child, and we auto-repair by clearing the stale link.
    try:
        _current_state = load_state(state_file)
        _parent = next(
            (c for c in _current_state.changes if c.name == change_name), None,
        )
        _prior_link = getattr(_parent, "fix_iss_child", None) if _parent else None
        if _prior_link:
            _prior_entry = next(
                (c for c in _current_state.changes if c.name == _prior_link), None,
            )
            _prior_dir = _os.path.join(openspec_root, "changes", _prior_link)
            _prior_status = _prior_entry.status if _prior_entry else None
            _entry_ok = (
                _prior_entry is not None
                and _prior_status not in _TERMINAL_FAILURE_STATUSES
                and _prior_status != "merged"
            )
            _dir_ok = _os.path.isdir(_prior_dir)
            if _entry_ok and _dir_ok:
                logger.info(
                    "escalate_change_to_fix_iss: parent %s already has live "
                    "fix-iss child %s (status=%s) — returning existing name, "
                    "skipping re-escalation (reason=%s)",
                    change_name, _prior_link, _prior_status, escalation_reason,
                )
                return _prior_link
            # Stale link — auto-repair and proceed with fresh claim
            logger.warning(
                "escalate_change_to_fix_iss: parent %s has stale fix_iss_child "
                "link to %s (entry_status=%s, dir_ok=%s) — clearing and "
                "re-escalating (reason=%s)",
                change_name, _prior_link, _prior_status, _dir_ok, escalation_reason,
            )
            update_change_field(state_file, change_name, "fix_iss_child", None)
    except Exception:
        # Never let idempotency-check prevent escalation on unexpected error
        logger.debug(
            "Idempotency check failed for parent=%s; proceeding with fresh "
            "escalation", change_name, exc_info=True,
        )

    finding_paths: list[str] = []
    for f in findings or []:
        if isinstance(f, dict):
            p = f.get("file") or f.get("path") or ""
            if p:
                finding_paths.append(p)
        elif hasattr(f, "file") and getattr(f, "file"):
            finding_paths.append(getattr(f, "file"))
    target = _classify_fix_target(finding_paths)

    slug_hint = _re.sub(r"[^a-z0-9-]+", "-", change_name.lower()).strip("-")[:20] or "change"
    # Claim an exclusive fix-iss-NNN directory via os.mkdir so concurrent
    # escalations for the same parent cannot collide on the proposal file.
    fix_iss_name, change_dir = _claim_fix_iss_dir(openspec_root, slug_hint)
    proposal_path = _os.path.join(change_dir, "proposal.md")

    # Include runaway metadata in the proposal when available — the circuit
    # breakers stash baseline/current/delta on the parent change's extras.
    runaway_section = ""
    try:
        from ..state import load_state as _load
        st = _load(state_file)
        parent = next((c for c in st.changes if c.name == change_name), None)
        if parent and escalation_reason == "token_runaway":
            runaway_section = (
                "\n### Runaway metadata\n"
                f"- baseline: {parent.token_runaway_baseline}\n"
                f"- current input_tokens: {parent.input_tokens}\n"
                f"- delta: {(parent.input_tokens or 0) - (parent.token_runaway_baseline or 0)}\n"
            )
    except Exception:
        pass

    findings_section = ""
    if finding_paths:
        findings_section = "\n### Finding paths\n" + "\n".join(
            f"- {p}" for p in finding_paths[:20]
        ) + "\n"

    proposal = f"""## Why
Parent change `{change_name}` hit a circuit breaker ({escalation_reason}) on
stop_gate=`{stop_gate or "—"}`. Auto-escalated at {_dt.utcnow().isoformat()}Z.

## What Changes
Investigate the root cause and produce a targeted fix. Diagnose whether the
problem is a framework defect or a consumer-project bug before implementing.

## Capabilities
- investigation-runner

## Impact
Gated to a single parent change until the diagnosis lands. The parent
change has been marked `failed:{escalation_reason}` and its dispatch
slot is released to this fix-iss.

## Fix Target
{target}
{findings_section}{runaway_section}
"""
    with open(proposal_path, "w") as fh:
        fh.write(proposal)

    update_change_field(state_file, change_name, "fix_iss_child", fix_iss_name)

    # Register the fix-iss change in state so the next monitor poll will
    # dispatch it (task 10.7). Without this the proposal on disk is invisible
    # to dispatch_ready_changes() which iterates state.changes only.
    try:
        _register_fix_iss_in_state(state_file, change_name, fix_iss_name, target)
    except Exception:
        logger.warning(
            "Could not register fix-iss %s in orchestration state — "
            "operator must add it manually", fix_iss_name, exc_info=True,
        )

    # Surface the escalation in the web Issues tab. Without this, operators
    # see the fix-iss change in the plan but the Issues list stays empty
    # even though a circuit breaker tripped — a confusing signal.
    try:
        from pathlib import Path as _Path
        from .registry import IssueRegistry as _IssueRegistry
        issue_reg = _IssueRegistry(_Path(project_root))
        registered = issue_reg.register(
            source=f"circuit-breaker:{escalation_reason}",
            error_summary=(
                f"{change_name} escalated to {fix_iss_name} "
                f"({escalation_reason}, target={target})"
            ),
            error_detail=(
                f"Parent change `{change_name}` hit a circuit breaker on "
                f"stop_gate=`{stop_gate or '—'}`. A diagnostic fix-iss change "
                f"was created: openspec/changes/{fix_iss_name}/. The parent "
                f"is marked `failed:{escalation_reason}`."
            ),
            affected_change=change_name,
            environment_path=project_root,
            affected_files=finding_paths[:20],
        )
        # Link the issue to the existing fix-iss change. Without this
        # link, IssueManager._process sees a NEW issue and spawns
        # /opsx:ff, which generates a DIFFERENT change_name from the
        # error_summary slug — producing a GHOST duplicate fix-iss
        # change and a dead investigation. Observed on
        # craftbrew-run-20260421-0025 backfill where each circuit-breaker
        # issue spawned a second orphan fix-iss with a mangled name
        # (fix-iss-001-catalog-listings-and-homepage vs the real
        # fix-iss-001-catalog-listings-and).
        if registered is not None:
            registered.change_name = fix_iss_name
            issue_reg.save()
    except Exception:
        logger.warning(
            "Could not register circuit-breaker issue for %s — issues tab "
            "will not reflect the escalation", change_name, exc_info=True,
        )

    if event_bus is not None:
        event_bus.emit(
            "FIX_ISS_ESCALATED",
            change=change_name,
            data={
                "fix_iss_child": fix_iss_name,
                "escalation_reason": escalation_reason,
                "target": target,
                "stop_gate": stop_gate,
            },
        )
    logger.warning(
        "Auto-escalated %s → %s (reason=%s, target=%s)",
        change_name, fix_iss_name, escalation_reason, target,
    )
    return fix_iss_name
