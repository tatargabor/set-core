"""Issue Registry — persistent storage with CRUD, dedup, and queries."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

from .models import (
    ACTIVE_STATES,
    ATTENTION_STATES,
    DONE_STATES,
    IN_PROGRESS_STATES,
    Issue,
    IssueGroup,
    IssueState,
    MutePattern,
    compute_fingerprint,
    now_iso,
)


class IssueRegistry:
    """Persistent issue storage backed by JSON files in .set/issues/."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.issues_dir = project_path / ".set" / "issues"
        self.registry_path = self.issues_dir / "registry.json"
        self.mutes_path = self.issues_dir / "mutes.json"
        self.investigations_dir = self.issues_dir / "investigations"

        self._issues: dict[str, Issue] = {}
        self._groups: dict[str, IssueGroup] = {}
        self._mutes: dict[str, MutePattern] = {}
        self._next_issue_num: int = 1
        self._next_group_num: int = 1
        self._next_mute_num: int = 1

        self._ensure_dirs()
        self._load()

    def _ensure_dirs(self):
        self.issues_dir.mkdir(parents=True, exist_ok=True)
        self.investigations_dir.mkdir(parents=True, exist_ok=True)

    # --- Persistence ---

    def _load(self):
        if self.registry_path.exists():
            try:
                data = json.loads(self.registry_path.read_text())
                for d in data.get("issues", []):
                    issue = Issue.from_dict(d)
                    self._issues[issue.id] = issue
                for d in data.get("groups", []):
                    group = IssueGroup.from_dict(d)
                    self._groups[group.id] = group
                # Compute next IDs
                if self._issues:
                    nums = [int(i.id.split("-")[1]) for i in self._issues.values()]
                    self._next_issue_num = max(nums) + 1
                if self._groups:
                    nums = [int(g.id.split("-")[1]) for g in self._groups.values()]
                    self._next_group_num = max(nums) + 1
            except (json.JSONDecodeError, KeyError):
                pass

    def reload_from_disk(self) -> bool:
        """Re-read registry.json so external writers (the sentinel-side
        `escalate_change_to_fix_iss`, recovery-tool purges) are picked up.

        Without this, the set-web-hosted IssueManager keeps its startup-time
        snapshot and cannot see NEW issues created mid-run — investigator
        never spawns and the fix-iss pipeline hangs.

        Returns True if the on-disk mtime changed since the last load.
        """
        try:
            mtime = self.registry_path.stat().st_mtime if self.registry_path.exists() else 0.0
        except OSError:
            mtime = 0.0
        last = getattr(self, "_last_registry_mtime", None)
        if last is not None and mtime == last:
            return False
        self._issues.clear()
        self._groups.clear()
        self._next_issue_num = 1
        self._next_group_num = 1
        self._load()
        self._last_registry_mtime = mtime
        return True

        if self.mutes_path.exists():
            try:
                data = json.loads(self.mutes_path.read_text())
                for d in data.get("mutes", []):
                    mute = MutePattern.from_dict(d)
                    self._mutes[mute.id] = mute
                if self._mutes:
                    nums = [int(m.id.split("-")[1]) for m in self._mutes.values()]
                    self._next_mute_num = max(nums) + 1
            except (json.JSONDecodeError, KeyError):
                pass

    def save(self):
        """Persist registry to disk with atomic write."""
        data = {
            "issues": [i.to_dict() for i in self._issues.values()],
            "groups": [g.to_dict() for g in self._groups.values()],
        }
        self._atomic_write(self.registry_path, data)

    def save_mutes(self):
        """Persist mute patterns to disk."""
        data = {"mutes": [m.to_dict() for m in self._mutes.values()]}
        self._atomic_write(self.mutes_path, data)

    def _atomic_write(self, path: Path, data: dict):
        content = json.dumps(data, indent=2, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            os.write(fd, content.encode())
            os.close(fd)
            os.replace(tmp, str(path))
        except Exception:
            os.close(fd) if not os.get_inheritable(fd) else None
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # --- Issue CRUD ---

    def next_issue_id(self) -> str:
        iid = f"ISS-{self._next_issue_num:03d}"
        self._next_issue_num += 1
        return iid

    def add(self, issue: Issue):
        self._issues[issue.id] = issue
        self.save()

    def get(self, issue_id: str) -> Optional[Issue]:
        return self._issues.get(issue_id)

    def all_issues(self) -> list[Issue]:
        return list(self._issues.values())

    def remove(self, issue_id: str):
        self._issues.pop(issue_id, None)
        self.save()

    # --- Deduplication ---

    def find_by_fingerprint(
        self, fingerprint: str, status_not_in: Optional[list[str]] = None
    ) -> Optional[Issue]:
        """Find an existing issue with the same fingerprint that isn't in excluded states."""
        excluded = set(status_not_in or [])
        for issue in self._issues.values():
            if issue.fingerprint == fingerprint and issue.state.value not in excluded:
                return issue
        return None

    def register(
        self,
        source: str,
        error_summary: str,
        error_detail: str = "",
        affected_change: Optional[str] = None,
        environment: str = "",
        environment_path: str = "",
        affected_files: Optional[list[str]] = None,
        source_finding_id: Optional[str] = None,
    ) -> Optional[Issue]:
        """Register a new issue with deduplication. Returns None if duplicate."""
        fp = compute_fingerprint(source, error_summary, affected_change)

        existing = self.find_by_fingerprint(
            fp, status_not_in=["resolved", "dismissed", "skipped", "cancelled"]
        )
        if existing:
            existing.occurrence_count += 1
            existing.updated_at = now_iso()
            self.save()
            return None

        issue = Issue(
            id=self.next_issue_id(),
            environment=environment,
            environment_path=environment_path,
            source=source,
            state=IssueState.NEW,
            severity="unknown",
            error_summary=error_summary,
            error_detail=error_detail,
            fingerprint=fp,
            affected_files=affected_files or [],
            affected_change=affected_change,
            source_finding_id=source_finding_id,
        )
        self.add(issue)
        return issue

    # --- Queries ---

    def auto_resolve_for_change(
        self,
        change_name: str,
        reason: str = "change_merged_auto_resolve",
    ) -> list[str]:
        """Transition all open issues tagged to `change_name` to RESOLVED.

        Called from merger.merge_change() after a successful merge. Issues
        in terminal states (resolved, dismissed, muted, skipped, cancelled)
        are left alone. Returns the list of resolved issue IDs.

        Safe to call from any context — failure writes a WARNING but does
        not raise (see merger hook).
        """
        from datetime import datetime, timezone

        terminal = {
            IssueState.RESOLVED,
            IssueState.DISMISSED,
            IssueState.MUTED,
            IssueState.SKIPPED,
            IssueState.CANCELLED,
        }
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        resolved: list[str] = []
        for issue in self._issues.values():
            if issue.affected_change != change_name:
                continue
            if issue.state in terminal:
                continue
            issue.state = IssueState.RESOLVED
            issue.resolved_at = now
            issue.updated_at = now
            resolved.append(issue.id)
        if resolved:
            self.save()
            try:
                from .audit import AuditLog

                audit = AuditLog(self.project_path)
                for iss_id in resolved:
                    # Spec mandates the exact action name so post-run audit
                    # tooling can grep for it.
                    audit.log(
                        iss_id,
                        "change_merged_auto_resolve",
                        reason=reason,
                        change=change_name,
                        from_state="diagnosed",
                        to_state="resolved",
                    )
            except Exception:
                # Audit write failure must not break the caller — the
                # merger's try/except would catch anything but we prefer
                # to swallow here to keep the data-mutation and
                # observability paths independent.
                pass
        return resolved

    def by_state(self, state: IssueState) -> list[Issue]:
        return [i for i in self._issues.values() if i.state == state]

    def by_severity(self, severity: str) -> list[Issue]:
        return [i for i in self._issues.values() if i.severity == severity]

    def active(self) -> list[Issue]:
        """Issues that need processing (not terminal)."""
        return [i for i in self._issues.values() if i.state in ACTIVE_STATES]

    def needs_attention(self) -> list[Issue]:
        return [i for i in self._issues.values() if i.state in ATTENTION_STATES]

    def in_progress(self) -> list[Issue]:
        return [i for i in self._issues.values() if i.state in IN_PROGRESS_STATES]

    def done(self) -> list[Issue]:
        return [i for i in self._issues.values() if i.state in DONE_STATES]

    def count_by_state(self, state: IssueState) -> int:
        return sum(1 for i in self._issues.values() if i.state == state)

    def stats(self) -> dict:
        by_state: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for i in self._issues.values():
            by_state[i.state.value] = by_state.get(i.state.value, 0) + 1
            by_severity[i.severity] = by_severity.get(i.severity, 0) + 1

        total_open = len(self.active()) + len(self.needs_attention())
        total_resolved = self.count_by_state(IssueState.RESOLVED)

        # Find nearest timeout
        nearest = None
        for i in self.by_state(IssueState.AWAITING_APPROVAL):
            if i.timeout_deadline:
                if nearest is None or i.timeout_deadline < nearest:
                    nearest = i.timeout_deadline

        return {
            "by_state": by_state,
            "by_severity": by_severity,
            "total_open": total_open,
            "total_resolved": total_resolved,
            "nearest_timeout": nearest,
        }

    # --- Group Management ---

    def next_group_id(self) -> str:
        gid = f"GRP-{self._next_group_num:03d}"
        self._next_group_num += 1
        return gid

    def create_group(
        self,
        name: str,
        issue_ids: list[str],
        reason: str = "",
        created_by: str = "user",
    ) -> IssueGroup:
        primary = issue_ids[0]
        gid = self.next_group_id()

        # Set group_id on all member issues
        for iid in issue_ids:
            issue = self.get(iid)
            if issue:
                issue.group_id = gid

        group = IssueGroup(
            id=gid,
            name=name,
            issue_ids=list(issue_ids),
            primary_issue=primary,
            reason=reason,
            created_by=created_by,
        )

        self._groups[gid] = group
        self.save()
        return group

    def save_group(self, group: IssueGroup):
        self._groups[group.id] = group
        self.save()

    def get_group(self, group_id: str) -> Optional[IssueGroup]:
        return self._groups.get(group_id)

    def all_groups(self) -> list[IssueGroup]:
        return list(self._groups.values())

    def active_groups(self) -> list[IssueGroup]:
        return [
            g for g in self._groups.values()
            if g.state not in (IssueState.RESOLVED, IssueState.DISMISSED)
        ]

    # --- Mute Patterns ---

    def next_mute_id(self) -> str:
        mid = f"MUTE-{self._next_mute_num:03d}"
        self._next_mute_num += 1
        return mid

    def add_mute(
        self,
        pattern: str,
        reason: str,
        created_by: str = "user",
        expires_at: Optional[str] = None,
        source_issue_id: Optional[str] = None,
    ) -> MutePattern:
        mute = MutePattern(
            id=self.next_mute_id(),
            pattern=pattern,
            reason=reason,
            created_by=created_by,
            expires_at=expires_at,
            source_issue_id=source_issue_id,
        )
        self._mutes[mute.id] = mute
        self.save_mutes()
        return mute

    def remove_mute(self, mute_id: str):
        self._mutes.pop(mute_id, None)
        self.save_mutes()

    def get_mute(self, mute_id: str) -> Optional[MutePattern]:
        return self._mutes.get(mute_id)

    def all_mutes(self) -> list[MutePattern]:
        return list(self._mutes.values())

    def matches_mute(self, error_summary: str, error_detail: str = "") -> Optional[MutePattern]:
        """Check if text matches any active (non-expired) mute pattern."""
        text = f"{error_summary}\n{error_detail}"
        for mute in self._mutes.values():
            if mute.is_expired():
                continue
            try:
                if re.search(mute.pattern, text, re.IGNORECASE):
                    mute.match_count += 1
                    mute.last_matched_at = now_iso()
                    self.save_mutes()
                    return mute
            except re.error:
                continue
        return None
