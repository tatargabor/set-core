"""Investigation Runner — spawn /opsx:ff to diagnose and plan fix."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..model_config import resolve_model
from ..subprocess_utils import resolve_model_id
from .audit import AuditLog
from .models import Diagnosis, Issue, now_iso
from .policy import IssuesPolicyConfig

logger = logging.getLogger(__name__)


def _slugify(text: str, max_len: int = 30) -> str:
    """Convert text to kebab-case slug."""
    s = re.sub(r'[^a-z0-9\s-]', '', text.lower())
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    return s[:max_len].rstrip('-')


class InvestigationRunner:
    """Spawns /opsx:ff to investigate and create fix artifacts."""

    def __init__(
        self,
        set_core_path: Path,
        config: IssuesPolicyConfig,
        audit: AuditLog,
        profile=None,
    ):
        self.set_core_path = set_core_path
        self.config = config
        self.audit = audit
        self.profile = profile
        self._processes: dict[str, subprocess.Popen] = {}
        self._started_at: dict[str, datetime] = {}
        self._stdout_files: dict[str, object] = {}
        self._change_names: dict[str, str] = {}

    def spawn(self, issue: Issue):
        """Start investigation via /opsx:ff — creates proposal + design + tasks.

        The investigation targets a specific `change_name` under
        `openspec/changes/`. If the issue already has `change_name` set
        (e.g. a circuit-breaker escalation pre-created a fix-iss change
        via `escalate_change_to_fix_iss()`), REUSE that name so the
        investigator's `/opsx:ff` extends the existing change rather
        than spawning a ghost duplicate with a slug-derived name. When
        the slot is empty, derive a slug from the issue summary.
        """
        change_name = (issue.change_name or "").strip()
        if not change_name:
            change_name = f"fix-{issue.id.lower()}-{_slugify(issue.error_summary)}"
        self._change_names[issue.id] = change_name
        issue.change_name = change_name

        error_text = issue.error_detail or issue.error_summary or "No error details"

        prompt = INVESTIGATION_PROMPT.format(
            issue_id=issue.id,
            change_name=change_name,
            environment=issue.environment,
            error_detail=error_text,
            affected_change=issue.affected_change or "N/A",
        )

        output_file = self._investigation_path(issue)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        stdout_fh = open(output_file, "w")

        # Resolve via the unified config — investigation is a supervisor-class
        # diagnostic run; route through `supervisor` role so operators can
        # override via models.supervisor in orchestration.yaml.
        project_cwd = issue.environment_path or str(self.set_core_path)
        investigation_model = resolve_model_id(
            resolve_model("supervisor", project_dir=project_cwd)
        )

        # No --max-turns: rely on timeout + 5h Anthropic session window;
        # the policy.investigation.max_turns knob is intentionally ignored.
        cmd = [
            "claude", "-p",
            "--model", investigation_model,
            "--verbose", "--output-format", "stream-json",
            "--dangerously-skip-permissions",
            prompt,
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=project_cwd,
                stdout=stdout_fh,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            self._stdout_files[issue.id] = stdout_fh
            self._processes[issue.id] = proc
            self._started_at[issue.id] = datetime.now(timezone.utc)
            issue.fix_agent_pid = proc.pid
            logger.info(f"Investigation /opsx:ff spawned for {issue.id}, PID={proc.pid}, change={change_name}")

            # Extract session_id from stream-json output (first line has it)
            self._extract_session_id(issue, output_file)
        except FileNotFoundError:
            logger.error("claude CLI not found — cannot spawn investigation")
            self.audit.log(issue.id, "investigation_spawn_failed", error="claude not found")

    def _extract_session_id(self, issue: Issue, output_file: Path, max_wait: float = 5.0):
        """Read session_id from stream-json output. Waits briefly for first line."""
        import time
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            try:
                with open(output_file) as f:
                    line = f.readline()
                    if line.strip():
                        data = json.loads(line)
                        sid = data.get("session_id")
                        if sid:
                            issue.investigation_session = sid
                            logger.info("Investigation session for %s: %s", issue.id, sid)
                            return
            except (json.JSONDecodeError, OSError):
                pass
            time.sleep(0.5)
        logger.debug("Could not extract session_id for %s within %.1fs", issue.id, max_wait)

    def is_done(self, issue: Issue) -> bool:
        proc = self._processes.get(issue.id)
        if proc is None:
            # Process reference lost (restart?) — check PID liveness
            if issue.fix_agent_pid:
                try:
                    os.kill(issue.fix_agent_pid, 0)
                    return False  # PID still alive
                except (ProcessLookupError, PermissionError):
                    return True  # PID dead — done
            return True  # No PID, no process — must be done
        return proc.poll() is not None

    def is_timed_out(self, issue: Issue) -> bool:
        started = self._started_at.get(issue.id)
        if not started:
            return False
        timeout = self.config.investigation.timeout_seconds
        if timeout <= 0:
            return False  # 0 = no timeout, let agent finish
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        return elapsed > timeout

    def kill(self, issue: Issue):
        proc = self._processes.pop(issue.id, None)
        if proc and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        self._started_at.pop(issue.id, None)
        fh = self._stdout_files.pop(issue.id, None)
        if fh:
            try:
                fh.close()
            except OSError:
                pass
        issue.fix_agent_pid = None

    def collect(self, issue: Issue) -> Optional[Diagnosis]:
        """Parse diagnosis from /opsx:ff artifacts (proposal.md)."""
        self._processes.pop(issue.id, None)
        self._started_at.pop(issue.id, None)
        fh = self._stdout_files.pop(issue.id, None)
        if fh:
            try:
                fh.close()
            except OSError:
                pass

        change_name = self._change_names.pop(issue.id, issue.change_name or "")
        project_path = Path(issue.environment_path) if issue.environment_path else self.set_core_path

        # Read proposal.md — this IS the diagnosis (works even after restart)
        proposal_path = project_path / "openspec" / "changes" / change_name / "proposal.md"
        if not proposal_path.exists():
            self.audit.log(issue.id, "investigation_no_proposal", change=change_name)
            logger.warning("No proposal.md found at %s for %s", proposal_path, issue.id)
            return None

        proposal = proposal_path.read_text()

        # Check tasks.md exists (confirms /opsx:ff completed)
        tasks_path = project_path / "openspec" / "changes" / change_name / "tasks.md"
        tasks_exist = tasks_path.exists()

        # Extract diagnosis from proposal content
        diagnosis = self._parse_proposal(proposal, tasks_exist)
        diagnosis.raw_output = proposal
        return diagnosis

    def _parse_proposal(self, proposal: str, has_tasks: bool, *,
                        classifier_enabled: bool = True) -> Diagnosis:
        """Extract diagnosis fields from proposal.md content.

        Priority order for each field:
        1. Explicit sentinel — `**Impact:** high`, `**Fix-Scope:** single_file`,
           `**Target:** framework`, `**Confidence:** 0.9`. The sentinel is
           trusted verbatim when present (no drift vs. downstream auto-fix).
        2. LLM verdict classifier — a second Sonnet pass that reads the
           proposal and returns a structured JSON diagnosis. This handles
           proposals that the investigation agent writes in free-form
           markdown without the sentinel format.
        3. Keyword heuristic fallback — only when the classifier errors out
           (timeout, non-JSON). Uses word-boundary matching to avoid
           false positives like "criticality" → high.

        See OpenSpec change: llm-verdict-classifier
        """
        # ─── 1. Sentinel pass ──────────────────────────────
        impact_m = re.search(
            r"\*\*Impact:\*\*\s*(low|medium|high)", proposal, re.IGNORECASE,
        )
        fix_scope_m = re.search(
            r"\*\*Fix-Scope:\*\*\s*(single_file|multi_file|config_override)",
            proposal, re.IGNORECASE,
        )
        target_m = re.search(
            r"\*\*Target:\*\*\s*(framework|consumer|both)", proposal, re.IGNORECASE,
        )
        confidence_m = re.search(
            r"\*\*Confidence:\*\*\s*(\d+(?:\.\d+)?|\.\d+)", proposal,
        )

        impact = impact_m.group(1).lower() if impact_m else None
        fix_scope = fix_scope_m.group(1).lower() if fix_scope_m else None
        fix_target = target_m.group(1).lower() if target_m else None

        sentinel_confidence: Optional[float] = None
        if confidence_m:
            try:
                raw = float(confidence_m.group(1))
                sentinel_confidence = raw / 100.0 if raw > 1.0 else raw
            except ValueError:
                sentinel_confidence = None

        # ─── 2. Classifier fallback (fills missing fields) ─────
        classifier_used = False
        classifier_failed = False
        missing = [
            name for name, val in
            (("impact", impact), ("fix_scope", fix_scope), ("fix_target", fix_target))
            if val is None
        ]
        if missing and classifier_enabled:
            try:
                from ..llm_verdict import INVESTIGATOR_SCHEMA, classify_verdict
                try:
                    from ..events import event_bus as _ev
                except Exception:
                    _ev = None
                cls_result = classify_verdict(
                    proposal,
                    INVESTIGATOR_SCHEMA,
                    purpose="investigator",
                    event_bus=_ev,
                )
                if cls_result.error is None:
                    classifier_used = True
                    rj = cls_result.raw_json or {}
                    if impact is None and rj.get("impact"):
                        val = str(rj.get("impact", "")).lower()
                        if val in ("low", "medium", "high"):
                            impact = val
                    if fix_scope is None and rj.get("fix_scope"):
                        val = str(rj.get("fix_scope", "")).lower()
                        if val in ("single_file", "multi_file", "config_override"):
                            fix_scope = val
                    if fix_target is None and rj.get("fix_target"):
                        val = str(rj.get("fix_target", "")).lower()
                        if val in ("framework", "consumer", "both"):
                            fix_target = val
                    if sentinel_confidence is None and rj.get("confidence") is not None:
                        try:
                            raw = float(rj.get("confidence", 0))
                            sentinel_confidence = raw / 100.0 if raw > 1.0 else raw
                        except (TypeError, ValueError):
                            pass
                else:
                    classifier_failed = True
                    logger.warning(
                        "Investigator classifier failed (error=%s) — falling back to heuristic",
                        cls_result.error,
                    )
            except Exception as exc:
                classifier_failed = True
                logger.warning(
                    "Investigator classifier import or call failed: %s — falling back to heuristic",
                    exc,
                )
        elif missing and not classifier_enabled:
            # Operator disabled the classifier — go straight to heuristic
            classifier_failed = True

        # ─── 3. Keyword heuristic — word-boundary matching ────
        if impact is None:
            impact = self._heuristic_impact(proposal)
        if fix_scope is None:
            fix_scope = self._heuristic_fix_scope(proposal)
        if fix_target is None:
            fix_target = self._heuristic_fix_target(proposal)

        # ─── 4. Root cause + suggested fix (section extraction) ──
        root_cause = ""
        for header in [r"##\s*(?:Problem|Why|Root Cause|Background)", r"##\s*\w+"]:
            match = re.search(header + r"\s*\n\s*(.+?)(?:\n\n|\n##)", proposal, re.DOTALL | re.IGNORECASE)
            if match:
                root_cause = match.group(1).strip()[:500]
                break
        if not root_cause:
            for line in proposal.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-") and len(line) > 20:
                    root_cause = line[:500]
                    break

        suggested_fix = ""
        for header in [r"##\s*(?:What|Solution|Fix|Scope)", r"##\s*\w+"]:
            match = re.search(header + r"\s*\n\s*(.+?)(?:\n\n|\n##)", proposal, re.DOTALL | re.IGNORECASE)
            if match and match.group(1).strip() != root_cause:
                suggested_fix = match.group(1).strip()[:500]
                break

        # ─── 5. Confidence ────────────────────────────────
        if sentinel_confidence is not None:
            confidence = sentinel_confidence
        else:
            confidence = 0.5
            if root_cause and suggested_fix:
                confidence = 0.8
            if has_tasks:
                confidence = 0.95

        # Penalise when we had to fall through to the keyword heuristic —
        # the verdict is less trustworthy than sentinel or classifier paths.
        if classifier_failed:
            confidence = max(0.0, confidence - 0.1)

        return Diagnosis(
            root_cause=root_cause or "See proposal.md for details",
            impact=impact,
            confidence=confidence,
            fix_scope=fix_scope,
            suggested_fix=suggested_fix or "See tasks.md for implementation plan",
            affected_files=[],
            related_issues=[],
            tags=[],
            fix_target=fix_target,
        )

    @staticmethod
    def _heuristic_impact(proposal: str) -> str:
        """Word-boundary keyword match for impact classification.

        Uses `\\b` boundaries so "criticality" and "not critical" do not
        trip the "critical" keyword. Scans the raw text (not lowercased)
        via the IGNORECASE flag.
        """
        high_patterns = [r"\bcritical\b", r"\bblocker\b", r"\bpermanently block",
                          r"\bpipeline blocked\b"]
        low_patterns = [r"\bminor\b", r"\bcosmetic\b", r"\bwarning\b"]
        for p in high_patterns:
            if re.search(p, proposal, re.IGNORECASE):
                return "high"
        for p in low_patterns:
            if re.search(p, proposal, re.IGNORECASE):
                return "low"
        return "medium"

    @staticmethod
    def _heuristic_fix_scope(proposal: str) -> str:
        config_patterns = [r"\bconfig\.yaml\b", r"\bconfig override\b",
                            r"\bvitest\.config\b", r"\bplaywright\.config\b"]
        multi_patterns = [r"\bmultiple files\b", r"\bcross-module\b", r"\bseveral files\b"]
        for p in config_patterns:
            if re.search(p, proposal, re.IGNORECASE):
                return "config_override"
        for p in multi_patterns:
            if re.search(p, proposal, re.IGNORECASE):
                return "multi_file"
        return "single_file"

    @staticmethod
    def _heuristic_fix_target(proposal: str) -> str:
        framework_patterns = [
            r"\bmerger\b", r"\bdispatcher\b", r"\bgate\b", r"\bprofile\b",
            r"\borchestrat", r"\bset-core\b", r"\bset_orch\b",
            r"\bff-only\b", r"\bfast-forward\b", r"\bintegration gate\b",
            r"\bmerge strategy\b", r"\blib/set_orch\b", r"\bframework bug\b",
        ]
        for p in framework_patterns:
            if re.search(p, proposal, re.IGNORECASE):
                return "framework"
        return "consumer"

    def _investigation_path(self, issue: Issue) -> Path:
        project_path = Path(issue.environment_path) if issue.environment_path else self.set_core_path
        return project_path / ".set" / "issues" / "investigations" / f"{issue.id}.md"


INVESTIGATION_PROMPT = """Investigate and plan a fix for issue {issue_id}.

## Issue
**Environment:** {environment}
**Affected change:** {affected_change}

**Error:**
```
{error_detail}
```

## Framework Knowledge

This project uses **set-core orchestration**:
- Config: the orchestration config file (LineagePaths.config_yaml) — overrides for test/e2e/build commands
- Gates: merger runs build → test → e2e before merging
- Profile: `set/plugins/project-type.yaml` → web profile auto-detects commands
- Common fixes:
  - vitest "no test files" → add `passWithNoTests: true` to vitest.config.ts
  - build fail → check deps installed, type errors
  - e2e fail → playwright needs install + dev server

## Source corruption recognition

If you read a source file and notice:
- duplicate top-level imports (the same `import` statement appearing 2 or more times)
- repeated blocks of code (the same function body, JSX block, switch case, or route definition appearing back-to-back)
- merge conflict markers left in the file (`<<<<<<<`, `=======`, `>>>>>>>`)

Do NOT keep re-reading the file hoping to make sense of it — you will burn turns on noise. Emit your diagnosis immediately:
- root cause: **source corruption (duplicate blocks from bad merge/auto-fix)**
- recommended fix: run `git diff HEAD~1 -- <file>` to see what changed, remove the duplicates, then retry the parent

A partial diagnosis with a clear fix path beats burning your remaining turns on a corrupted file. This rule overrides the usual "investigate thoroughly" guidance when the file is clearly mechanically corrupted.

## Instructions

Run `/opsx:ff {change_name}` to create a structured fix plan. The proposal should describe:
- What is broken and why (root cause)
- What needs to change (exact files and content)
- Impact if not fixed

## Fix Target Classification

**IMPORTANT:** Add a "## Fix Target" section to your proposal with this format:

```
## Fix Target
- **Target:** framework | consumer | both
- **Reasoning:** [your analysis]
```

How to decide:
- **framework** — This bug would affect ANY project using set-core (merger bug, gate bug, template defect, planning rule missing). The fix goes in set-core's codebase.
- **consumer** — This bug is specific to THIS project (merge conflict between two changes, missing file, wrong config value). The fix goes in the local repo.
- **both** — Root cause is in set-core (template or rule defect) BUT this project also needs a local fix for the already-deployed broken state.

The /opsx:ff command will create proposal.md, design.md, specs, and tasks.md — everything needed for the fix agent to implement with /opsx:apply.
"""
