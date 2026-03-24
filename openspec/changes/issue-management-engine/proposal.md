# Issue Management Engine (set-manager service)

## Problem

The set-core orchestration system has grown complex enough that its error handling is insufficient:

1. **Shallow fixes** — agents patch symptoms without investigating root causes, because they work in narrow context windows
2. **No triage** — every error gets the same treatment regardless of severity or complexity
3. **No human decision point** — fixes happen automatically with no opportunity for guidance
4. **No process management** — sentinels and orchestrators are started manually from agent sessions, crash without auto-restart, and die when the terminal closes
5. **No cross-environment view** — multiple running projects each have isolated findings with no unified tracking

Beyond issue management, there's a fundamental infrastructure gap: there's no persistent service that supervises the running components (sentinels, orchestrators) and provides a control plane.

## Solution

Build **set-manager** — a persistent service (systemd daemon) that serves as the control plane for set-core. It has two responsibilities:

1. **Process Supervision** — manage sentinel agents and orchestrations per-project (start, stop, health check, auto-restart)
2. **Issue Management** — a deterministic Python state machine that detects issues, orchestrates investigation and fixing, and provides human-in-the-loop controls

The key architectural principle: **the state machine controls, LLM agents work**. The Python layer handles all lifecycle transitions, timeouts, policy evaluation, and agent spawning. LLM agents only do investigation (read-only diagnosis in set-core dir) and fixing (opsx workflow in set-core dir).

```
┌─────────────────────────────────────────────────────────────────┐
│  set-manager (systemd service, always running)                   │
│                                                                  │
│  ┌─ Process Supervisor ──────────────────────────────────────┐  │
│  │  Per-project:                                              │  │
│  │  ├── Sentinel agent (spawn, health check, auto-restart)    │  │
│  │  └── Orchestrator (spawn on demand, monitor)               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ Issue Management ────────────────────────────────────────┐  │
│  │  ├── Issue Registry (persistent JSON, deduplication)       │  │
│  │  ├── State Machine (13 states, deterministic transitions)  │  │
│  │  ├── Policy Engine (auto-fix, timeouts, mute patterns)     │  │
│  │  ├── Investigation Runner (claude CLI in set-core dir)     │  │
│  │  ├── Fix Runner (opsx workflow in set-core dir)            │  │
│  │  ├── Deploy Runner (set-project init to target projects)   │  │
│  │  └── Audit Log (append-only JSONL)                         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ REST API ────────────────────────────────────────────────┐  │
│  │  Projects, sentinels, orchestrations, issues, groups,      │  │
│  │  mutes, audit — consumed by set-web                        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Scope

### In scope

**Service Infrastructure:**
1. **set-manager daemon** — systemd service, CLI (`set-manager serve/start/stop/status`)
2. **Project Supervisor** — per-project sentinel + orchestrator lifecycle management
3. **Sentinel agent spawning** — start sentinel as dedicated claude agent process, health check, auto-restart on crash
4. **Orchestration spawning** — start orchestration via existing `set-orchestrate`, monitor PID
5. **Service configuration** — projects registry, per-project settings (mode, paths)

**Issue Management:**
6. **Issue Registry** — persistent storage with deduplication (fingerprinting)
7. **Issue State Machine** — 13 states, deterministic transitions with validation
8. **Issue Groups** — batch related issues for joint investigation/fix
9. **Policy Engine** — configurable auto-fix, timeouts per severity/mode, mute patterns
10. **Investigation Runner** — python method that spawns claude CLI in set-core dir, captures structured output
11. **Fix Runner** — opsx workflow (ff → apply → verify → archive) in set-core dir, max 1 fix at a time
12. **Deploy Runner** — `set-project init` to target projects after fix
13. **Timeout/Approval Logic** — countdown-based auto-approval, configurable per severity/mode
14. **Mute Registry** — pattern-based suppression with TTL
15. **Audit Log** — append-only JSONL for every state transition
16. **REST API** — full CRUD + actions for set-web consumption
17. **Notification Integration** — Discord/email/desktop alerts

### Out of scope

- Web UI (separate change: `issue-management-console`)
- New error detection mechanisms (uses existing sentinel/watchdog/gates)
- Changes to the opsx workflow itself
- Changes to the existing sentinel findings system (coexists — issues are a layer above findings)

## Architecture

### Service topology

```
Machine
├── systemd
│   ├── set-manager.service (always running)
│   │   ├── Manager main loop (tick every 5s)
│   │   ├── REST API server (port 3112)
│   │   ├── Supervised sentinel agents:
│   │   │   ├── sentinel:craftbrew-run12 (claude agent process)
│   │   │   └── sentinel:minishop-prod   (claude agent process)
│   │   ├── Supervised orchestrations:
│   │   │   └── orch:craftbrew-run12     (set-orchestrate process)
│   │   └── Issue pipeline:
│   │       ├── Investigation agent (max 1, claude CLI)
│   │       └── Fix agent (max 1, claude CLI opsx)
│   │
│   └── set-web.service (UI, port 3111)
│       └── Proxies /api/manager/* → set-manager:3112
│
├── Project: craftbrew-run12
│   ├── .set/sentinel/ (findings, events, status — written by sentinel agent)
│   └── .set/issues/   (registry, audit — written by set-manager)
│
└── set-core repo
    └── Fix target: investigation + opsx fixes happen HERE
```

### Process supervision

```python
@dataclass
class ProjectConfig:
    name: str                    # "craftbrew-run12"
    path: Path                   # absolute path to project root
    mode: str                    # "e2e" | "production" | "development"
    sentinel_enabled: bool       # auto-start sentinel?
    auto_restart_sentinel: bool  # restart on crash?

class ProjectSupervisor:
    """Manages sentinel + orchestrator lifecycle for one project."""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self.sentinel_pid: int | None = None
        self.orchestrator_pid: int | None = None
        self.sentinel_started_at: str | None = None
        self.sentinel_crash_count: int = 0

    def start_sentinel(self) -> int:
        """Spawn sentinel as a dedicated claude agent process."""
        pid = spawn_claude_agent(
            working_dir=self.config.path,
            prompt=SENTINEL_PROMPT.format(project=self.config.name),
            session_label=f"sentinel-{self.config.name}",
        )
        self.sentinel_pid = pid
        self.sentinel_started_at = now_iso()
        self.sentinel_crash_count = 0
        return pid

    def stop_sentinel(self):
        """Gracefully stop sentinel agent."""
        if self.sentinel_pid and is_alive(self.sentinel_pid):
            kill_gracefully(self.sentinel_pid)
        self.sentinel_pid = None

    def start_orchestration(self, plan_file: str | None = None) -> int:
        """Start orchestration via set-orchestrate command."""
        cmd = f"set-orchestrate {self.config.path}"
        if plan_file:
            cmd += f" --plan {plan_file}"
        pid = spawn_command(cmd)
        self.orchestrator_pid = pid
        return pid

    def stop_orchestration(self):
        if self.orchestrator_pid and is_alive(self.orchestrator_pid):
            kill_gracefully(self.orchestrator_pid)
        self.orchestrator_pid = None

    def health_check(self) -> list[str]:
        """Check process health. Returns list of actions taken."""
        actions = []

        if self.sentinel_pid and not is_alive(self.sentinel_pid):
            actions.append(f"sentinel died (pid={self.sentinel_pid})")
            self.sentinel_pid = None
            self.sentinel_crash_count += 1

            if self.config.auto_restart_sentinel:
                self.start_sentinel()
                actions.append("sentinel auto-restarted")
            else:
                actions.append("sentinel not restarted (auto_restart=false)")

        if self.orchestrator_pid and not is_alive(self.orchestrator_pid):
            actions.append(f"orchestrator died (pid={self.orchestrator_pid})")
            self.orchestrator_pid = None
            # Don't auto-restart orchestrator — always notify
            notify(f"[{self.config.name}] Orchestrator died", urgency="critical")

        return actions

    def status(self) -> dict:
        return {
            "name": self.config.name,
            "mode": self.config.mode,
            "sentinel": {
                "pid": self.sentinel_pid,
                "alive": self.sentinel_pid and is_alive(self.sentinel_pid),
                "started_at": self.sentinel_started_at,
                "crash_count": self.sentinel_crash_count,
            },
            "orchestrator": {
                "pid": self.orchestrator_pid,
                "alive": self.orchestrator_pid and is_alive(self.orchestrator_pid),
            },
        }
```

### Data model

```python
class IssueState(Enum):
    NEW = "new"                          # just registered, awaiting triage
    INVESTIGATING = "investigating"      # investigation agent is analyzing
    DIAGNOSED = "diagnosed"              # diagnosis ready, awaiting decision
    AWAITING_APPROVAL = "awaiting_approval"  # timeout countdown running
    FIXING = "fixing"                    # opsx fix agent working in set-core dir
    VERIFYING = "verifying"              # opsx:verify running
    DEPLOYING = "deploying"              # set-project init to target environments
    RESOLVED = "resolved"                # fix deployed successfully
    DISMISSED = "dismissed"              # user/policy decided: won't fix
    MUTED = "muted"                      # matches mute pattern, suppressed
    FAILED = "failed"                    # fix attempt failed, can retry
    SKIPPED = "skipped"                  # intentionally not fixing (already resolved by group, etc.)
    CANCELLED = "cancelled"              # user stopped in-progress investigation or fix

VALID_TRANSITIONS = {
    NEW:               {INVESTIGATING, DIAGNOSED, DISMISSED, MUTED, SKIPPED},
    INVESTIGATING:     {DIAGNOSED, FAILED, CANCELLED},
    DIAGNOSED:         {AWAITING_APPROVAL, FIXING, DISMISSED, MUTED, INVESTIGATING, SKIPPED},
    AWAITING_APPROVAL: {FIXING, DISMISSED, INVESTIGATING, CANCELLED},
    FIXING:            {VERIFYING, FAILED, CANCELLED},
    VERIFYING:         {DEPLOYING, FAILED, CANCELLED},
    DEPLOYING:         {RESOLVED, FAILED},
    FAILED:            {INVESTIGATING, DISMISSED, NEW},
    MUTED:             {NEW},
    CANCELLED:         {NEW, DISMISSED},
    SKIPPED:           {NEW},
    # RESOLVED and DISMISSED are terminal
}

@dataclass
class Issue:
    id: str                          # ISS-001 (auto-sequential)
    environment: str                 # "craftbrew-run12"
    environment_path: str            # absolute path to project root
    source: str                      # "sentinel" | "gate" | "watchdog" | "user"
    state: IssueState
    severity: str                    # "unknown" | "low" | "medium" | "high" | "critical"
    group_id: str | None             # GRP-001 if grouped

    # Detection context
    error_summary: str
    error_detail: str
    fingerprint: str                 # dedup key (hash of normalized error)
    affected_files: list[str]
    affected_change: str | None      # which orchestration change triggered this
    detected_at: str                 # ISO-8601
    source_finding_id: str | None    # link back to sentinel finding if applicable
    occurrence_count: int            # incremented on dedup match (default 1)

    # Investigation
    diagnosis: Diagnosis | None
    investigation_session: str | None  # claude session ID (resumable for chat)

    # Fix
    change_name: str | None          # opsx change name: "fix-iss-001-auth-crash"
    fix_agent_pid: int | None

    # Policy
    timeout_deadline: str | None     # ISO-8601, when auto-approval fires
    timeout_started_at: str | None   # ISO-8601, when countdown began
    policy_matched: str | None       # which policy rule matched
    auto_fix: bool

    # Muting
    mute_pattern: str | None

    # Retry tracking
    retry_count: int                 # how many fix attempts (default 0)
    max_retries: int                 # from policy (default 2)

    # Timestamps
    updated_at: str
    resolved_at: str | None

@dataclass
class Diagnosis:
    root_cause: str
    impact: str                      # "low" | "medium" | "high" | "critical"
    confidence: float                # 0.0 - 1.0
    fix_scope: str                   # "single_file" | "multi_file" | "cross_module"
    suggested_fix: str               # natural language description
    affected_files: list[str]
    related_issues: list[str]        # ISS-xxx IDs
    suggested_group: str | None      # group name suggestion
    group_reason: str | None
    tags: list[str]                  # for memory integration
    raw_output: str                  # full investigation agent output (for review)

@dataclass
class IssueGroup:
    id: str                          # GRP-001
    name: str                        # "db-setup-sequence"
    issue_ids: list[str]
    primary_issue: str               # oldest or most severe
    state: IssueState                # group moves as unit
    change_name: str | None          # one opsx change for the group
    created_at: str
    reason: str                      # why grouped
    created_by: str                  # "user" | "agent"

@dataclass
class MutePattern:
    id: str                          # MUTE-001
    pattern: str                     # regex matched against error_summary + error_detail
    reason: str
    created_by: str                  # "user" | "agent" | "policy"
    created_at: str
    expires_at: str | None           # optional TTL
    match_count: int                 # how many times suppressed
    last_matched_at: str | None
    source_issue_id: str | None      # ISS-xxx that spawned this mute
```

### Severity handling

Severity starts as `unknown` at registration. Investigation determines actual severity.

```python
# Registration: severity is always "unknown"
issue = Issue(severity="unknown", ...)

# After investigation: diagnosis.impact becomes the severity
if diagnosis and diagnosis.impact:
    issue.severity = diagnosis.impact

# Policy uses severity for timeout/auto-fix decisions
# "unknown" severity = always investigate first, never auto-fix without investigation
```

### Deduplication

```python
def compute_fingerprint(source: str, error_summary: str, affected_change: str | None) -> str:
    """Normalize and hash to detect duplicate reports of the same error."""
    normalized = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '', error_summary)
    normalized = re.sub(r'PID \d+', 'PID X', normalized)
    normalized = re.sub(r'/tmp/[^\s]+', '/tmp/...', normalized)
    key = f"{source}:{affected_change or ''}:{normalized.strip()}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]

def register(self, **kwargs) -> Issue | None:
    fp = compute_fingerprint(kwargs['source'], kwargs['error_summary'], kwargs.get('affected_change'))
    existing = self.registry.find_by_fingerprint(fp, status_not_in=['resolved', 'dismissed', 'skipped'])
    if existing:
        existing.occurrence_count += 1
        existing.updated_at = now_iso()
        self.audit.log(existing, "duplicate_suppressed", count=existing.occurrence_count)
        return None  # not a new issue
    kwargs['fingerprint'] = fp
    kwargs['severity'] = 'unknown'  # always starts unknown
    return self._create_issue(**kwargs)
```

### Registration filter

Not every detection event becomes an issue:

```python
def should_register(self, source: str, severity_hint: str, error_summary: str) -> bool:
    """Filter: which detection events become issues?"""
    # Mute patterns suppress before registration
    if self.mute_registry.matches(error_summary):
        return False

    # Source-specific filters
    match source:
        case "sentinel":
            # Only findings with severity critical or warning, not info
            return severity_hint in ("critical", "warning")
        case "gate":
            # All gate failures are issues
            return True
        case "watchdog":
            # Only escalation level >= 2 (restart+)
            return True  # caller pre-filters
        case "user":
            # User-reported: always
            return True

    return True
```

### Policy configuration

Loaded from `orchestration.yaml` under an `issues:` key, or from a separate `manager.yaml`:

```yaml
manager:
  # Service settings
  port: 3112
  tick_interval_seconds: 5

  # Project registry
  projects:
    craftbrew-run12:
      path: /home/user/.local/share/set-core/e2e-runs/craftbrew-run12
      mode: e2e
      sentinel_enabled: true
      auto_restart_sentinel: true
    minishop-prod:
      path: /home/user/code/minishop
      mode: production
      sentinel_enabled: true
      auto_restart_sentinel: true

issues:
  enabled: true

  # Timeout-based auto-approval (silence = consent)
  # Values in seconds. null = never auto-approve. 0 = instant.
  timeout_by_severity:
    unknown: null               # always investigate first
    low: 120                    # 2 minutes
    medium: 300                 # 5 minutes
    high: 900                   # 15 minutes
    critical: null              # never auto-approve

  # Mode overrides
  modes:
    e2e:
      timeout_by_severity:
        unknown: 600            # investigate, but timeout after 10 min
        low: 0                  # instant
        medium: 120
        high: 300
        critical: 1800
      auto_fix_severity: [low, medium, high]
    production:
      timeout_by_severity:
        unknown: null
        low: 300
        medium: 900
        high: null
        critical: null
      auto_fix_severity: [low]

  # Auto-fix eligibility (ALL conditions must match after diagnosis)
  auto_fix_conditions:
    min_confidence: 0.85
    max_scope: "multi_file"
    blocked_tags: [db_migration, auth, security, data_loss_risk]

  # Always manual regardless of other conditions
  always_manual:
    - severity: critical
    - scope: cross_module
    - tags: [security, data_loss_risk]

  # Investigation
  investigation:
    token_budget: 50000
    timeout_seconds: 300
    template: "default"              # pluggable
    auto_investigate: true

  # Retry policy
  retry:
    max_retries: 2
    backoff_seconds: 60

  # Concurrency — max 1 fix at a time is the hard rule
  concurrency:
    max_parallel_investigations: 3
    max_parallel_fixes: 1            # ALWAYS 1. Sequential fixes only.

  # Mute patterns
  mute_patterns: []
```

### File layout

```
lib/set_orch/
├── manager/
│   ├── __init__.py              # public API
│   ├── service.py               # ServiceManager: main loop, REST API server
│   ├── supervisor.py            # ProjectSupervisor: sentinel/orch lifecycle
│   ├── config.py                # ServiceConfig, ProjectConfig loading
│   └── cli.py                   # set-manager CLI (serve, start, stop, status)
├── issues/
│   ├── __init__.py              # public API: IssueManager, Issue, IssueState
│   ├── models.py                # dataclasses
│   ├── registry.py              # IssueRegistry: CRUD, persistence, queries
│   ├── manager.py               # IssueManager: state machine tick(), transitions
│   ├── policy.py                # PolicyEngine: auto-fix, timeout, mute eval
│   ├── investigator.py          # InvestigationRunner: claude CLI spawn/monitor
│   ├── fixer.py                 # FixRunner: opsx workflow spawn/monitor
│   ├── deployer.py              # DeployRunner: set-project init pipeline
│   ├── detector.py              # DetectionBridge: reads sentinel findings → registers issues
│   ├── audit.py                 # AuditLog: append-only JSONL
│   └── templates/
│       └── default.md           # structured investigation prompt
```

### Storage layout

```
# Per-project (in project's .set/ directory)
.set/issues/
├── registry.json            # all issues + groups for this project
├── audit.jsonl              # append-only action log
├── mutes.json               # mute patterns
└── investigations/
    ├── ISS-001.md           # investigation report
    └── GRP-001.md           # group investigation report

# Global (in set-core data directory)
~/.local/share/set-core/manager/
├── config.yaml              # service config (projects, settings)
├── state.json               # running process PIDs, health status
└── cross-env-index.json     # aggregated issue stats for all projects
```

### State machine

```python
class IssueManager:
    """Deterministic controller. No LLM calls — only state transitions and agent lifecycle."""

    def tick(self):
        """Called every 5s from service main loop."""
        # Read new findings from all supervised sentinels
        self.detector.scan_all_projects()

        # Process issue queue
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
                if self.policy.is_muted(issue):
                    self._transition(issue, IssueState.MUTED)
                elif self.policy.should_auto_investigate(issue):
                    if self._can_spawn_investigation():
                        self._spawn_investigation(issue)
                        self._transition(issue, IssueState.INVESTIGATING)
                    # else: stays NEW, will retry next tick

            case IssueState.INVESTIGATING:
                if self.investigator.is_done(issue):
                    diagnosis = self.investigator.collect(issue)
                    if diagnosis:
                        issue.diagnosis = diagnosis
                        if diagnosis.impact:
                            issue.severity = diagnosis.impact
                        self._transition(issue, IssueState.DIAGNOSED)
                        self._apply_post_diagnosis_policy(issue)
                    else:
                        self._transition(issue, IssueState.FAILED)
                elif self.investigator.is_timed_out(issue):
                    self.audit.log(issue, "investigation_timeout")
                    self.investigator.kill(issue)
                    self._transition(issue, IssueState.DIAGNOSED)
                    # No diagnosis — human must decide

            case IssueState.DIAGNOSED:
                pass  # Waiting state. Routed by _apply_post_diagnosis_policy
                      # or by user action via API.

            case IssueState.AWAITING_APPROVAL:
                if now_iso() >= issue.timeout_deadline:
                    self.audit.log(issue, "timeout_auto_approved")
                    self._start_fix(issue)

            case IssueState.FIXING:
                if self.fixer.is_done(issue):
                    result = self.fixer.collect(issue)
                    if result.success:
                        self._transition(issue, IssueState.VERIFYING)
                        self._run_verify(issue)
                    else:
                        self._handle_failure(issue, result)

            case IssueState.VERIFYING:
                if self.fixer.verify_done(issue):
                    if self.fixer.verify_passed(issue):
                        self._transition(issue, IssueState.DEPLOYING)
                        self._deploy(issue)
                    else:
                        self._handle_failure(issue, self.fixer.verify_result(issue))

            case IssueState.DEPLOYING:
                if self.deployer.is_done(issue):
                    if self.deployer.succeeded(issue):
                        self._transition(issue, IssueState.RESOLVED)
                        self.notifier.on_resolved(issue)
                    else:
                        self._transition(issue, IssueState.FAILED)

            case IssueState.FAILED:
                if issue.retry_count < issue.max_retries:
                    if self._retry_backoff_elapsed(issue):
                        issue.retry_count += 1
                        self.audit.log(issue, "auto_retry", attempt=issue.retry_count)
                        self._transition(issue, IssueState.INVESTIGATING)
                        if self._can_spawn_investigation():
                            self._spawn_investigation(issue)

    def _apply_post_diagnosis_policy(self, issue: Issue):
        """Called once after diagnosis. Routes based on policy."""
        if self.policy.can_auto_fix(issue):
            timeout = self.policy.get_timeout(issue)
            if timeout == 0:
                self._start_fix(issue)
            else:
                issue.timeout_deadline = (now() + timedelta(seconds=timeout)).isoformat()
                issue.timeout_started_at = now_iso()
                self._transition(issue, IssueState.AWAITING_APPROVAL)
                self.notifier.on_awaiting(issue, timeout)

    def _start_fix(self, issue: Issue):
        """Start fix if concurrency allows (max 1 fix at a time)."""
        if self._can_spawn_fix():
            self._transition(issue, IssueState.FIXING)
            self._spawn_fix(issue)
        else:
            self.audit.log(issue, "fix_queued", reason="another_fix_running")

    def _handle_failure(self, issue: Issue, result):
        self._transition(issue, IssueState.FAILED)
        self.audit.log(issue, "fix_failed",
                       retry_count=issue.retry_count, error=str(result))

    # --- Concurrency ---

    def _can_spawn_investigation(self) -> bool:
        return self.registry.count_by_state(IssueState.INVESTIGATING) < \
               self.policy.config.concurrency.max_parallel_investigations

    def _can_spawn_fix(self) -> bool:
        # Hard rule: max 1 fix at a time
        return self.registry.count_by_state(IssueState.FIXING) == 0

    # --- User actions (called from REST API) ---

    def action_investigate(self, issue_id: str):
        issue = self.registry.get(issue_id)
        self._transition(issue, IssueState.INVESTIGATING)
        self._spawn_investigation(issue)

    def action_fix(self, issue_id: str):
        issue = self.registry.get(issue_id)
        self._start_fix(issue)

    def action_dismiss(self, issue_id: str):
        issue = self.registry.get(issue_id)
        self._transition(issue, IssueState.DISMISSED)

    def action_cancel(self, issue_id: str):
        issue = self.registry.get(issue_id)
        # Kill running agent if any
        if issue.state == IssueState.INVESTIGATING:
            self.investigator.kill(issue)
        elif issue.state in (IssueState.FIXING, IssueState.VERIFYING):
            self.fixer.kill(issue)
        self._transition(issue, IssueState.CANCELLED)

    def action_skip(self, issue_id: str, reason: str = ""):
        issue = self.registry.get(issue_id)
        self._transition(issue, IssueState.SKIPPED)
        self.audit.log(issue, "skipped", reason=reason)

    def action_mute(self, issue_id: str, pattern: str | None = None):
        issue = self.registry.get(issue_id)
        pat = pattern or re.escape(issue.error_summary)
        self.mute_registry.add(pat, reason=f"Muted from {issue.id}",
                               source_issue_id=issue.id)
        self._transition(issue, IssueState.MUTED)

    def action_extend_timeout(self, issue_id: str, extra_seconds: int):
        issue = self.registry.get(issue_id)
        if issue.state == IssueState.AWAITING_APPROVAL:
            issue.timeout_deadline = (
                datetime.fromisoformat(issue.timeout_deadline) +
                timedelta(seconds=extra_seconds)
            ).isoformat()
            self.audit.log(issue, "timeout_extended", extra_seconds=extra_seconds)
```

### Investigation runner

```python
class InvestigationRunner:
    """Spawns claude CLI for investigation. Runs in set-core directory."""

    def spawn(self, issue: Issue):
        """Start investigation agent as a claude CLI subprocess."""
        template = self._get_template(issue)
        prompt = template.format(
            issue_id=issue.id,
            environment=issue.environment,
            source=issue.source,
            affected_change=issue.affected_change or "N/A",
            severity=issue.severity,
            detected_at=issue.detected_at,
            occurrence_count=issue.occurrence_count,
            error_detail=issue.error_detail,
            open_issues_summary=self._format_open_issues(issue),
        )

        # Spawn claude CLI in set-core directory
        output_file = self._investigation_path(issue)
        pid = spawn_command(
            f"claude -p --output-file {output_file} --max-turns 20 "
            f"--prompt {shlex.quote(prompt)}",
            cwd=self.set_core_path,  # Always set-core dir
            timeout=self.config.investigation.timeout_seconds,
        )
        issue.fix_agent_pid = pid
        issue.investigation_session = self._session_id_from_pid(pid)

    def collect(self, issue: Issue) -> Diagnosis | None:
        """Parse investigation output into Diagnosis."""
        output_file = self._investigation_path(issue)
        raw_output = output_file.read_text() if output_file.exists() else ""
        if not raw_output:
            return None

        match = re.search(r'DIAGNOSIS_START\s*(\{.*?\})\s*DIAGNOSIS_END',
                         raw_output, re.DOTALL)
        if not match:
            match = re.search(r'```json\s*(\{.*?\})\s*```\s*$',
                             raw_output, re.DOTALL)

        if not match:
            self.audit.log(issue, "diagnosis_parse_failed")
            return Diagnosis(
                root_cause="Investigation completed but diagnosis not parseable",
                impact=issue.severity,
                confidence=0.0, fix_scope="unknown",
                suggested_fix="Manual review required",
                affected_files=[], related_issues=[],
                suggested_group=None, group_reason=None,
                tags=[], raw_output=raw_output,
            )

        try:
            data = json.loads(match.group(1))
            return Diagnosis(raw_output=raw_output, **data)
        except (json.JSONDecodeError, TypeError) as e:
            self.audit.log(issue, "diagnosis_parse_error", error=str(e))
            return None

    def _get_template(self, issue: Issue) -> str:
        """Pluggable templates: profile-specific > config > default."""
        if self.profile and hasattr(self.profile, 'investigation_template'):
            custom = self.profile.investigation_template(issue)
            if custom:
                return custom
        template_name = self.config.investigation.template
        template_path = Path(__file__).parent / "templates" / f"{template_name}.md"
        return template_path.read_text()
```

### Fix runner

```python
class FixRunner:
    """Runs opsx workflow in set-core directory. Max 1 at a time."""

    def spawn(self, issue: Issue):
        """Start opsx fix agent in set-core directory."""
        change_name = f"fix-{issue.id.lower()}-{slugify(issue.error_summary)[:30]}"
        issue.change_name = change_name

        prompt = FIX_PROMPT.format(
            issue_id=issue.id,
            change_name=change_name,
            diagnosis=json.dumps(asdict(issue.diagnosis), indent=2),
            environment=issue.environment,
        )

        pid = spawn_command(
            f"claude -p --max-turns 50 --prompt {shlex.quote(prompt)}",
            cwd=self.set_core_path,  # Always set-core dir
        )
        issue.fix_agent_pid = pid

FIX_PROMPT = """
You are fixing issue {issue_id} in set-core.

## Diagnosis
{diagnosis}

## Instructions
1. Run /opsx:ff {change_name} with scope based on the diagnosis above
2. Run /opsx:apply to implement the fix
3. Run /opsx:verify to validate
4. Run /opsx:archive to complete

Work in the set-core directory. Do NOT create worktrees.
Commit your changes after each step.
"""
```

### Deploy runner

```python
class DeployRunner:
    """Deploys fix to target environments via set-project init."""

    def deploy(self, issue: Issue):
        """Run set-project init on all projects that need the fix."""
        targets = self._get_deploy_targets(issue)
        for target in targets:
            spawn_command(
                f"set-project init {target}",
                cwd=self.set_core_path,
            )
        self.audit.log(issue, "deploy_started", targets=[str(t) for t in targets])

    def _get_deploy_targets(self, issue: Issue) -> list[Path]:
        """Determine which projects need the fix deployed."""
        targets = []
        # The source environment always gets the update
        targets.append(Path(issue.environment_path))
        # Optionally: all registered projects (configurable)
        if self.config.deploy_to_all:
            for proj in self.service.projects.values():
                if proj.config.path not in targets:
                    targets.append(proj.config.path)
        return targets
```

### Detection bridge

```python
class DetectionBridge:
    """Reads sentinel findings and converts to issues."""

    def scan_all_projects(self):
        """Called from manager tick(). Reads new findings from all projects."""
        for proj in self.service.projects.values():
            self._scan_project(proj)

    def _scan_project(self, proj: ProjectSupervisor):
        findings_path = proj.config.path / ".set" / "sentinel" / "findings.json"
        if not findings_path.exists():
            return

        findings = json.loads(findings_path.read_text())
        for finding in findings.get("findings", []):
            if finding["status"] != "open":
                continue
            if finding["id"] in self._processed_findings:
                continue

            self._processed_findings.add(finding["id"])

            if not self.issue_manager.should_register(
                source="sentinel",
                severity_hint=finding["severity"],
                error_summary=finding["summary"],
            ):
                continue

            self.issue_manager.register(
                source="sentinel",
                error_summary=finding["summary"],
                error_detail=finding.get("detail", ""),
                affected_change=finding.get("change"),
                environment=proj.config.name,
                environment_path=str(proj.config.path),
                source_finding_id=finding["id"],
            )
```

### Groups

```python
class IssueManager:
    # ... (continued from above)

    def action_group(self, issue_ids: list[str], name: str, reason: str) -> IssueGroup:
        """Group issues — user-initiated from console."""
        group = IssueGroup(
            id=self.registry.next_group_id(),
            name=name,
            issue_ids=issue_ids,
            primary_issue=self._pick_primary(issue_ids),
            state=IssueState.NEW,
            change_name=None,
            created_at=now_iso(),
            reason=reason,
            created_by="user",
        )
        for iid in issue_ids:
            self.registry.get(iid).group_id = group.id
        self.registry.save_group(group)
        return group

    def _process_group(self, group: IssueGroup):
        """Groups follow the same state machine as individual issues."""
        # Create a synthetic "primary issue" view and process it
        # Group state drives all member issues
        primary = self.registry.get(group.primary_issue)

        match group.state:
            case IssueState.FIXING:
                if self.fixer.is_done_group(group):
                    results = self.fixer.collect_group(group)
                    self._handle_group_results(group, results)

    def _handle_group_results(self, group: IssueGroup, results: dict[str, bool]):
        resolved = [iid for iid, ok in results.items() if ok]
        failed = [iid for iid, ok in results.items() if not ok]

        for iid in resolved:
            self._transition(self.registry.get(iid), IssueState.RESOLVED)

        if failed:
            for iid in failed:
                issue = self.registry.get(iid)
                issue.group_id = None  # standalone again
                self._transition(issue, IssueState.FAILED)

        group.state = IssueState.RESOLVED
        self.audit.log_group(group, "resolved",
                            resolved=resolved, failed=failed)
```

### REST API endpoints

```
# Project management
GET    /api/projects                              # list all projects with status
POST   /api/projects                              # register project
DELETE /api/projects/{name}                        # unregister project
GET    /api/projects/{name}/status                 # detailed project status

# Sentinel control
POST   /api/projects/{name}/sentinel/start         # start sentinel
POST   /api/projects/{name}/sentinel/stop          # stop sentinel
POST   /api/projects/{name}/sentinel/restart        # restart sentinel

# Orchestration control
POST   /api/projects/{name}/orchestration/start    # start orchestration
POST   /api/projects/{name}/orchestration/stop     # stop orchestration

# Issues
GET    /api/projects/{name}/issues                 # list issues (filterable)
GET    /api/projects/{name}/issues/{id}            # issue detail
POST   /api/projects/{name}/issues                 # register manually (user report)
POST   /api/projects/{name}/issues/{id}/investigate
POST   /api/projects/{name}/issues/{id}/fix
POST   /api/projects/{name}/issues/{id}/dismiss
POST   /api/projects/{name}/issues/{id}/cancel
POST   /api/projects/{name}/issues/{id}/skip
POST   /api/projects/{name}/issues/{id}/mute
POST   /api/projects/{name}/issues/{id}/extend-timeout
POST   /api/projects/{name}/issues/{id}/message    # send to investigation agent

# Groups
GET    /api/projects/{name}/issues/groups
POST   /api/projects/{name}/issues/groups          # create group
POST   /api/projects/{name}/issues/groups/{id}/fix

# Mutes
GET    /api/projects/{name}/issues/mutes
POST   /api/projects/{name}/issues/mutes
DELETE /api/projects/{name}/issues/mutes/{id}

# Audit & stats
GET    /api/projects/{name}/issues/audit           # audit log
GET    /api/projects/{name}/issues/stats            # counts by state/severity

# Cross-project
GET    /api/issues                                  # all issues, all projects
GET    /api/issues/stats                            # aggregated stats

# Service
GET    /api/manager/status                          # service health
GET    /api/manager/config                          # active configuration
```

### Notification hooks

```python
class IssueNotifier:
    """Dispatches notifications via existing channels (Discord/email/desktop)."""

    def on_registered(self, issue: Issue):
        notify(f"[{issue.environment}] New issue: {issue.error_summary}")

    def on_awaiting(self, issue: Issue, timeout_seconds: int):
        notify(f"[{issue.environment}] {issue.id} diagnosed — "
               f"auto-fix in {timeout_seconds}s unless you respond",
               urgency="action_required")

    def on_timeout_reminder(self, issue: Issue, pct: int):
        remaining = self._format_remaining(issue)
        notify(f"[{issue.environment}] {issue.id} auto-fix in {remaining}")

    def on_fix_started(self, issue: Issue):
        notify(f"[{issue.environment}] {issue.id} fix started")

    def on_resolved(self, issue: Issue):
        notify(f"[{issue.environment}] {issue.id} resolved")

    def on_failed(self, issue: Issue):
        notify(f"[{issue.environment}] {issue.id} fix FAILED", urgency="critical")

    def on_sentinel_died(self, project: str, crash_count: int):
        notify(f"[{project}] Sentinel crashed (#{crash_count}), auto-restarting",
               urgency="critical")
```

### Systemd units

```ini
# ~/.config/systemd/user/set-manager.service
[Unit]
Description=Set-Core Management Service
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/set-manager serve
Restart=always
RestartSec=5
WorkingDirectory=%h/code2/set-core

[Install]
WantedBy=default.target
```

```ini
# ~/.config/systemd/user/set-web.service
[Unit]
Description=Set-Core Web UI
After=set-manager.service

[Service]
Type=simple
ExecStart=%h/.local/bin/set-web serve
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

CLI:
```bash
set-manager serve              # run in foreground (for development)
set-manager start              # enable + start systemd service
set-manager stop               # stop systemd service
set-manager status             # show service status + all project states
set-manager project add <name> <path> --mode e2e
set-manager project remove <name>
set-manager project list
```

## Dependencies

- Existing: `sentinel/findings.py`, `sentinel/events.py`, `watchdog.py`, `gate_runner.py`, `notifications.py`, `api.py`, `chat.py`, `process.py`
- Existing: `set-orchestrate`, `set-project init` commands
- New external: none (pure Python, no new pip dependencies)

## Risks

1. **Investigation quality** — Mitigated by structured+pluggable templates, adequate token budget, fallback to manual review.
2. **State machine complexity** — 13 states. Mitigated by strict transition table, audit log, DIAGNOSED as deliberate pause point.
3. **Process supervision reliability** — Sentinel auto-restart could loop on persistent failures. Mitigated by crash count tracking and backoff.
4. **Fix safety** — Max 1 fix at a time + opsx:verify gate + conservative defaults.
5. **Dedup false positives** — Only dedup within same environment + change + active status.
6. **Systemd dependency** — Linux-only. Mac users need alternative (launchd). Document both.

## Success Criteria

1. `set-manager serve` starts and runs as persistent service
2. Sentinels are spawned and auto-restarted per project from the service
3. Orchestrations can be started/stopped via API
4. Issues from findings/gates/watchdog auto-register with dedup
5. Investigation agents run in set-core dir, produce parseable diagnoses
6. Fix agents execute opsx workflow in set-core dir (max 1 at a time)
7. `set-project init` deploys fixes to target environments
8. Timeout-based auto-approval works per severity/mode
9. Issue groups support joint investigation and fix
10. Mute patterns suppress known errors
11. Complete audit trail for every action
12. REST API serves all operations for set-web
13. All existing functionality unchanged
