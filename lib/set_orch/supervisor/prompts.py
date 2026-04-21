"""Per-trigger prompt templates for ephemeral Claude spawns.

Two-part structure for prompt-cache friendliness:

  STABLE HEADER (cacheable across spawns)
    - Role description
    - Allowed CLI tools and hard rules
    - Output contract: end with VERDICT line

  VARIABLE BODY (built per call)
    - Trigger-specific context
    - Optional prior-attempts summary

Splitting them this way means the second and subsequent ephemeral
Claudes get a cache hit on the header (which is byte-identical) and
only the body counts as fresh tokens.

Adding a new trigger: write a `_build_<name>` function with the standard
signature and register it in `_TRIGGER_BUILDERS`. The fall-through is
`_build_generic` so an unknown trigger still produces a usable prompt.
"""

from __future__ import annotations

from dataclasses import dataclass


STABLE_HEADER = """\
You are the set-supervisor's diagnostic agent. The Python supervisor daemon
detected an anomaly in the orchestration run and spawned you to:

  1. Read the relevant context (logs, events, state).
  2. Decide what action to take.
  3. Either fix it (if obvious) or write a finding for the user.
  4. Respond with a single VERDICT line at the end.

Allowed actions (call as Bash commands):
  - set-sentinel-finding add  --severity <bug|observation|pattern|regression> --change <name> --summary "..." [--detail "..."]
  - set-sentinel-finding update <id> --status <fixed|wont-fix|escalated>
  - set-sentinel-status heartbeat
  - git log / git status / git diff   (read-only investigation)
  - cat / grep / find                  (log inspection)

Hard rules:
  - You may NOT run set-orchestrate restart, set-supervisor stop, git push,
    or any destructive command. The daemon owns process lifecycle.
  - You may NOT spend more than 10 minutes wall clock; the daemon will kill you.
  - You MUST end your reply with one of:
        VERDICT: ok       — false alarm, no action needed
        VERDICT: fixed    — you fixed the underlying issue
        VERDICT: noted    — you logged a finding, no fix attempted
        VERDICT: escalate — manual user attention required
"""


@dataclass
class TriggerPrompt:
    """Result of building a trigger prompt: header + body."""
    header: str
    body: str

    @property
    def full(self) -> str:
        return f"{self.header}\n\n{self.body}"


def build_trigger_prompt(
    *,
    trigger: str,
    reason: str,
    change: str = "",
    context: dict | None = None,
    project_path: str = "",
    spec: str = "",
    prior_attempts_summary: str = "",
) -> TriggerPrompt:
    """Build a prompt for the given trigger type.

    Falls back to a generic template for unknown trigger types so a new
    detector that hasn't grown a custom template yet still gets a usable
    prompt.
    """
    builder = _TRIGGER_BUILDERS.get(trigger, _build_generic)
    body = builder(
        reason=reason,
        change=change,
        context=context or {},
        project_path=project_path,
        spec=spec,
    )
    if prior_attempts_summary:
        body = f"{prior_attempts_summary}\n\n{body}"
    return TriggerPrompt(header=STABLE_HEADER, body=body)


# ── Common intro ─────────────────────────────────────────


def _intro(
    trigger: str, reason: str, project_path: str, spec: str, change: str,
) -> str:
    parts = [f"## Trigger: {trigger}"]
    if change:
        parts.append(f"Change: {change}")
    parts.append(f"Reason: {reason}")
    if project_path:
        parts.append(f"Project: {project_path}")
    if spec:
        parts.append(f"Spec: {spec}")
    return "\n".join(parts)


# ── Per-trigger builders ─────────────────────────────────


def _build_process_crash(*, reason, change, context, project_path, spec) -> str:
    return (
        _intro("process_crash", reason, project_path, spec, change) + "\n\n"
        "The orchestrator process is gone but the run is not in a terminal "
        "state. The daemon will restart it automatically — your job is to "
        "figure out WHY it crashed and write a finding.\n\n"
        "Steps:\n"
        "  1. tail -200 of orchestration.log under the runtime logs/ dir\n"
        "  2. Inspect the most recent ERROR or stack trace\n"
        "  3. If the cause is a known recoverable bug, log a finding (severity=bug)\n"
        "  4. If unknown, log a finding (severity=bug) and VERDICT: escalate\n"
    )


def _build_integration_failed(*, reason, change, context, project_path, spec) -> str:
    tokens = context.get("tokens", 0)
    return (
        _intro("integration_failed", reason, project_path, spec, change) + "\n\n"
        f"This change has burned {tokens} tokens before hitting integration "
        "failure. Read the most recent VERIFY_GATE / INTEGRATION events for "
        "this change and the agent's last log lines, then decide:\n"
        "  - obvious one-line fix → make it, log finding=fixed\n"
        "  - non-obvious → log severity=bug, VERDICT: escalate\n"
        "  - flaky / retry-worthy → VERDICT: noted with severity=observation\n"
    )


def _build_state_stall(*, reason, change, context, project_path, spec) -> str:
    return (
        _intro("state_stall", reason, project_path, spec, change) + "\n\n"
        "The orchestration state file has not moved. Either the dispatcher "
        "is stuck waiting for a worker, or a ralph loop has hung. Look at:\n"
        "  - dispatcher logs (last few minutes)\n"
        "  - any worktree's loop-state.json mtime\n"
        "  - the watchdog event stream\n"
        "Goal: identify which subsystem is stuck and log a finding."
    )


def _build_token_stall(*, reason, change, context, project_path, spec) -> str:
    tokens = context.get("tokens", 0)
    stall = context.get("stall_seconds", 0)
    return (
        _intro("token_stall", reason, project_path, spec, change) + "\n\n"
        f"Change is at {tokens} tokens with no progress for {stall}s. Look "
        "at the agent's loop iterations — is it spinning on the same failing "
        "test? Same lint error? If yes, log a finding describing the spin "
        "pattern. Bias toward severity=pattern, VERDICT: noted."
    )


def _build_non_periodic_checkpoint(*, reason, change, context, project_path, spec) -> str:
    cp_reason = context.get("checkpoint_reason", "")
    return (
        _intro("non_periodic_checkpoint", reason, project_path, spec, change) + "\n\n"
        f"A non-periodic checkpoint fired (reason={cp_reason!r}). The "
        "orchestrator chose to mark this point as significant. Read the "
        "events around the checkpoint and decide if user attention is "
        "needed. Most checkpoints are informational — bias toward "
        "VERDICT: noted with severity=observation."
    )


def _build_unknown_event_type(*, reason, change, context, project_path, spec) -> str:
    et = context.get("event_type", "?")
    return (
        _intro("unknown_event_type", reason, project_path, spec, change) + "\n\n"
        f"A new event type {et!r} appeared in events.jsonl that the "
        "supervisor doesn't recognise. Either someone added it without "
        "updating the known set, or the orchestrator is emitting garbage. "
        "Inspect the event payload and log a finding so the supervisor's "
        "KNOWN_EVENT_TYPES set can be updated."
    )


def _build_error_rate_spike(*, reason, change, context, project_path, spec) -> str:
    warns = context.get("warn_count", 0)
    errors = context.get("error_count", 0)
    baseline = context.get("baseline", 0)
    return (
        _intro("error_rate_spike", reason, project_path, spec, change) + "\n\n"
        f"Log severity spike: {warns} WARN + {errors} ERROR vs baseline "
        f"{baseline}. Read the new ERROR lines and decide whether they "
        "represent a real failure escalation or routine noise. If real, "
        "log a finding with the dominant pattern."
    )


def _build_log_silence(*, reason, change, context, project_path, spec) -> str:
    silence = context.get("silence_seconds", 0)
    return (
        _intro("log_silence", reason, project_path, spec, change) + "\n\n"
        f"orchestration.log has been silent for {silence}s but the "
        "process is still alive. Likely deadlock or a blocked syscall. "
        "Inspect with `ps`, the most recent events, and any worktree "
        "loop-state files. Log a finding."
    )


def _build_terminal_state(*, reason, change, context, project_path, spec) -> str:
    status = context.get("status", "?")
    return (
        _intro("terminal_state", reason, project_path, spec, change) + "\n\n"
        f"Orchestration reached terminal status {status!r} and the "
        "process is gone. Your job is to write the FINAL REPORT for this "
        "run:\n"
        "  - count of merged vs failed changes\n"
        "  - any unmerged-but-not-failed changes\n"
        "  - top 5 anomalies the supervisor saw during the run\n"
        "  - one-paragraph summary suitable for the user\n"
        "Use `set-sentinel-finding add --severity observation --change _run` "
        "to record the final report. The `observation` severity + `_run` "
        "change scope tells the issue pipeline this is an informational "
        "record, NOT a bug to investigate — it will not spawn an "
        "investigator or create a fix change.\n"
        "End with VERDICT: noted."
    )


def _build_generic(*, reason, change, context, project_path, spec) -> str:
    return (
        _intro("generic", reason, project_path, spec, change) + "\n\n"
        "(no specialised template — use general diagnostics, log a "
        "finding describing what you found)"
    )


_TRIGGER_BUILDERS = {
    "process_crash": _build_process_crash,
    "integration_failed": _build_integration_failed,
    "state_stall": _build_state_stall,
    "token_stall": _build_token_stall,
    "non_periodic_checkpoint": _build_non_periodic_checkpoint,
    "unknown_event_type": _build_unknown_event_type,
    "error_rate_spike": _build_error_rate_spike,
    "log_silence": _build_log_silence,
    "terminal_state": _build_terminal_state,
}
