# Design: Sentinel Supervisor — Python Daemon + Ephemeral Claude

## Context

The Claude-driven sentinel in its current form is an architectural accident. Its roots go back to the era when the orchestrator itself was a bash script and a Claude conversation was the only available supervision vehicle. Since then, the orchestrator has become a Python service with its own watchdog, event bus, state store, and gate pipeline — but the sentinel has stayed in its original shape as a long-lived `claude -p` conversation that polls the orchestrator's state every 2 minutes.

This design captures the target shape after the redesign. The goal is to keep every valuable property the current sentinel provides (crash recovery, Tier 3 intervention, open-ended oversight, final completion report) while eliminating the idle-polling cost and context exhaustion mode that make it unusable for any run longer than 40 minutes.

## Goals

1. **Zero LLM cost on routine polling.** When nothing is happening, the supervisor spends no tokens.
2. **Preserve all Tier 3 LLM intervention capability.** Integration-failed diagnosis, crash diagnosis, stall escalation, non-periodic checkpoint decisions, and final completion reports all still get LLM attention — but only when triggered.
3. **Preserve open-ended oversight.** A periodic canary Claude check (15-30 min) gives the LLM a scheduled chance to notice things the trigger signals missed. Without this, the Python daemon is deaf to semantic/subtle issues.
4. **Survive arbitrary-length runs.** No context accumulation. No 30-40 min wall. A 12-hour run is just a long sequence of short Python poll cycles and a handful of ephemeral Claude spawns.
5. **Observability parity or better.** Every supervisor action (poll, trigger, canary, ephemeral spawn, decision) emits a structured event so the web dashboard can render the supervision history.
6. **Reversible rollout.** A directive flag lets operators fall back to the old sentinel if the Python daemon misbehaves in production.

## Non-goals

- Replacing the orchestrator's internal watchdog (`watchdog.py`). The supervisor wraps the orchestrator, it does not compete with its existing monitoring.
- Merging the supervisor into the orchestrator process. Keeping them separate lets each be restarted independently — the orchestrator's crash does not take the supervisor down with it.
- Replacing `set-loop` / `run_claude_logged` / `run_orchestrate` — the supervisor uses these as-is.
- Replacing the gate pipeline or the merger. Those are the orchestrator's job.
- Replacing the user-facing `/set:start` skill. The skill still exists; it just calls the manager API which in turn invokes `set-supervisor` instead of `claude -p`.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│  Layer 1 — Python daemon (set-supervisor, always on)      │
│                                                            │
│  startup:                                                  │
│    - validate spec + project registration                  │
│    - spawn set-orchestrate subprocess (captured PID)       │
│    - write supervisor.status.json                          │
│    - enter monitor loop                                    │
│                                                            │
│  monitor loop (every ~15s):                                │
│    - check orch PID alive                                  │
│    - stat orchestration-state.json (mtime diff)            │
│    - tail events.jsonl since last cursor                   │
│    - classify new events → structured signals              │
│    - maintain counters: last_progress_ts, error_window,    │
│      unknown_event_types, crash_count, poll_cycle          │
│    - evaluate trigger rules                                │
│    - if trigger hit → spawn Layer 2                        │
│    - if 15 min since last canary → spawn Layer 3           │
│    - sleep 15s                                             │
│                                                            │
│  shutdown:                                                 │
│    - SIGTERM handler → trigger final-report Claude         │
│    - wait for orchestrator exit                            │
│    - write terminal status.json                            │
└────────────────────────────────────────────────────────────┘
                  │                           │
                  ▼                           ▼
┌─────────────────────────────┐   ┌──────────────────────────────┐
│ Layer 2 — Trigger Claude    │   │ Layer 3 — Canary Claude      │
│ (ephemeral, rare, focused)  │   │ (ephemeral, periodic, broad) │
│                             │   │                              │
│ Each invocation:            │   │ Every 15 min:                │
│   - fresh claude -p         │   │   - fresh claude -p          │
│   - --model sonnet (default)│   │   - --model sonnet           │
│   - single-shot budget      │   │   - context = structured     │
│     (~10 min, ~30k tokens)  │   │     diff since last canary   │
│   - writes findings + fix   │   │   - prompt: "anything off?"  │
│     actions to events.jsonl │   │   - response drives action   │
│   - exits                   │   │                              │
└─────────────────────────────┘   └──────────────────────────────┘
```

## Decisions

### 1. Daemon is Python, not bash or systemd unit

Python gives us access to the existing set_orch modules (state loading, event bus, profile loader) without duplicating them. A bash supervisor would need to reimplement state.json parsing, lock handling, and event emission.

We do not use systemd for process supervision because:
- The manager API is the deployment surface, not systemd
- Consumer projects may run on macOS or inside Docker where systemd is unavailable
- Manager-launched supervisors need to be killable from the web UI without root access

The daemon installs a SIGTERM handler that cleanly shuts down the orchestrator (graceful subprocess.terminate with timeout) and then emits a final completion report via a Layer 2 ephemeral Claude before exiting.

### 2. Monitor loop runs every 15 seconds, not continuously

15 seconds is fast enough for human-scale orchestration (the orchestrator itself polls every 15s by default) and cheap enough that the daemon's CPU cost is negligible. The loop does O(1) syscalls per cycle: `os.kill(pid, 0)`, `os.stat`, `file.seek`+`read`, plus a few string compares. No subprocess, no JSON parsing of large files, no git commands.

Anomaly signals are detected incrementally: the daemon maintains its own cursor into `events.jsonl` and a rolling window of counters. It does not re-scan the whole log on every poll.

### 3. Trigger signals are anomaly-generic, not bug-specific

The daemon does not hard-code every known failure mode. It hard-codes a small set of "something is off" signals that catch most failures regardless of root cause:

| Signal | Description | Triggered action |
|---|---|---|
| `process_crash` | `os.kill(pid, 0)` fails AND state.status != "done" | restart orchestrator; on 3rd rapid crash → spawn Layer 2 for diagnosis |
| `state_stall` | `state.mtime` unchanged for >5 min AND status == "running" | spawn Layer 2 |
| `token_stall` | change tokens_used > 500k AND no commit in 30 min | spawn Layer 2 |
| `integration_failed` | any change.status == "integration-failed" | spawn Layer 2 |
| `non_periodic_checkpoint` | checkpoint event with reason != "periodic" | spawn Layer 2 |
| `unknown_event_type` | new event type appears in events.jsonl that is not in the known set | spawn Layer 2 (first occurrence only) |
| `error_rate_spike` | WARN/ERROR lines in orchestration.log > 3× rolling baseline | spawn Layer 2 |
| `log_silence` | no new log lines in 5 min AND process alive | spawn Layer 2 |
| `terminal_state` | status == "done" / "time_limit" / "stopped" and process dead | spawn Layer 2 for final report, then exit |

Adding a new trigger is a PR to `anomaly.py`. Operators can add project-local triggers via a YAML config in `set/supervisor/triggers.yaml` (future work).

### 4. Ephemeral Claude invocations are single-shot

Each Layer 2 call is `claude -p --model sonnet --max-turns 25 --resume <session_id>`. The prompt is focused: the trigger name, the relevant state snippet, and the list of allowed actions ("restart orch", "reset change", "log finding", "escalate to user"). The Claude exits when the task is done — either by calling a CLI command (`set-sentinel-finding add`) or by writing a result to a designated file.

No session is resumed across triggers. Each spawn is stateless from Claude's perspective; the daemon tracks state.

The per-trigger budget is:
- Timeout: 10 minutes (`timeout 600`)
- Max turns: 25 (well above what any single task needs)
- Model: sonnet by default, opus for `integration_failed` and `non_periodic_checkpoint`

### 5. Canary check uses structured diff, not raw log

The canary prompt is built by the daemon:

```
## Canary check @ 14:23:00 (poll cycle 47)

### Since last check (14:08):
- Merged: foundation
- Running: create-task (retry 1, 320k tokens, 0 commits in 12 min)
- Pending: checkout, auth

### Events (non-heartbeat):
- DISPATCH foundation → STATE_CHANGE → CHANGE_DONE → VERIFY_GATE pass → MERGE_SUCCESS
- DISPATCH create-task → STATE_CHANGE → e2e-smoke fail → retry dispatch

### Log anomalies:
- 0 ERROR lines
- 2 WARN lines: "e2e baseline cache miss", "playwright webserver slow start"

### New event types: (none)

### Gate ms moving average: build 10s, test 0.5s, e2e 18s, review 70s

### Question: does anything here warrant escalation?
```

The canary reads this ~2-5k token context and replies with one of:
- `OK — continuing` (no action)
- `NOTE — <observation>` (log to events, continue)
- `WARN — <issue> — <suggested action>` (daemon escalates)
- `STOP — <critical issue>` (daemon halts orchestrator for user decision)

The response format is a single sentinel line at the end: `CANARY_VERDICT: ok|note|warn|stop`, parsed by `_parse_canary_verdict()`. This reuses the sentinel-pattern from spec_verify and the safety-first fail-safe behavior: if the verdict line is missing, the daemon treats it as `note` (log and continue) — never escalates on ambiguity.

### 6. Canary cadence is 15 minutes, not 2 minutes

Fifteen minutes is chosen because:
- Typical ralph iteration is 3-15 minutes, so one canary check per iteration cycle is enough granularity
- The cost of each canary is ~2-5k tokens, so 4 checks per hour is well under $0.10
- The orchestrator's built-in watchdog handles ~30s granularity, so the canary does not need to overlap it
- Real issues that manifest faster than 15 minutes are caught by Layer 2 triggers, not the canary

Operators can override via a directive: `canary_interval_minutes: 10` (future work).

### 7. The ephemeral Claude writes results via CLI, not stdout

The daemon does not parse Claude's natural-language output to extract actions. Instead, it gives each ephemeral Claude a set of CLI commands it can invoke:

- `set-sentinel-finding add/update`
- `set-sentinel-status heartbeat`
- `set-orchestrate restart <pid>` (future)
- `set-supervisor mark-change-reset <name>` (future)

Claude's `tool_use` blocks are Bash invocations to these commands, which the daemon watches via the events.jsonl. This is the same pattern the orchestrator already uses for ralph agents — no new infrastructure.

Claude's prose output is logged to `set/supervisor/claude-<trigger>-<ts>.log` for post-hoc review but does not drive decisions.

### 8. State files

Two new files under `set/supervisor/`:

- `supervisor.status.json` — daemon metadata: started_at, pid, orch_pid, poll_cycle, last_canary_at, last_trigger_at, triggers_fired (counter by type)
- `supervisor.events.jsonl` — append-only log of daemon actions: every trigger fire, every canary result, every ephemeral Claude spawn and its exit code

The existing `orchestration-events.jsonl` receives summary events (`SUPERVISOR_START`, `SUPERVISOR_TRIGGER`, `CANARY_CHECK`, `SUPERVISOR_STOP`) so the web dashboard does not need a new reader for the supervisor-specific file.

### 9. Rollout directive

Add `supervisor_mode: str = "python"` to the Directives dataclass. Values:
- `python` (default): new set-supervisor daemon
- `claude`: old sentinel.md Claude conversation (backward compat)
- `off`: no supervision (manual run, for CI or debug)

The manager API reads this directive when starting a sentinel and dispatches accordingly. Operators can flip to `claude` without a redeploy if the Python daemon hits an unexpected issue.

## Alternatives considered

### A. Keep the Claude sentinel, add periodic `/clear` context reset

**Rejected.** This is the minimum-change path. It keeps the idle polling cost entirely and only fixes the context exhaustion. A 4-hour run still burns 600k+ tokens for zero-value routine polling. The symptom (context death) is addressed but the root cause (LLM on the routine path) is not.

### B. Pure cron-fired ephemeral Claude, no Python daemon

**Rejected.** Attractive for simplicity — just put a cron entry that runs `claude -p "check this project"` every 3 minutes — but three problems:

1. Cron's minimum granularity is 1 minute on Linux, so real-time crash recovery has up to 1 minute latency. A crashed orchestrator is invisible until the next cron fire.
2. Cross-check state (rapid_crashes counter, last_canary_at) must live in a file that the cron entries read/write with racy semantics.
3. Every cron fire spawns Claude even when nothing is happening — the routine-polling cost is not eliminated, just distributed.

The Python daemon does the cheap routine work for free and only invokes Claude when something is actually off. Cron's simplicity is not worth the lost efficiency.

### C. Fold the supervisor into the orchestrator process

**Rejected.** The orchestrator already has `watchdog.py` for change-level monitoring. Merging the supervisor into the same process would:
- Couple orchestrator crashes to supervisor crashes (the whole point of the supervisor is to be independent)
- Require the orchestrator to know about Claude invocation (currently it does not, only ralph does)
- Complicate the set-web manager's process model

Keeping them as separate processes is a clean boundary.

### D. Use the set-web manager's watchfiles-based event detection

**Considered.** The manager already watches `orchestration-state.json` and `events.jsonl` for the web dashboard. Extending it to also fire supervisor triggers would avoid a new process. But:
- The manager is a user-facing API server; adding daemon-style responsibilities to it muddles the boundary
- The manager runs as a single process across all projects — a buggy trigger for project A could stall project B's requests
- Process isolation per project is valuable

Separate `set-supervisor` daemon per project is cleaner.

## Risks

1. **Canary false positives.** A conservative canary escalates on every minor anomaly, causing unnecessary orchestrator halts. Mitigation: the canary response format explicitly encodes severity (`ok|note|warn|stop`), only `stop` halts the run, and `warn` is rate-limited to once per 30 min per issue pattern.

2. **Trigger coverage gaps.** A novel failure mode that produces neither a crash, stall, nor error spike could slip past the Layer 2 triggers. The canary is the safety net — it sees the broad picture every 15 min. If both miss it, that is still better than the current sentinel, which also misses it (and also dies at 40 min).

3. **Daemon crash.** If `set-supervisor` itself crashes, the orchestrator continues headless. Mitigation: a minimal watchdog script runs the daemon under a `while true; do set-supervisor ... ; sleep 10; done` loop at the manager level. Daemon restart is cheap (no state beyond the cursor into events.jsonl, which is persisted).

4. **Classifier reuse.** The `llm_verdict.classify_verdict()` helper added for gate output parsing can be reused for parsing canary responses and trigger-Claude diagnoses. Risk: overloading the classifier with diverging schemas. Mitigation: each invocation passes its own schema; the helper is schema-agnostic.

5. **Rollout during in-flight runs.** Switching `supervisor_mode` mid-run would leave the old sentinel still alive. Mitigation: the directive is read at sentinel-start time only, never mid-run. Switching requires stopping the current supervisor first.

6. **Missing LLM context for decisions.** Tier 3 triggered Claudes are ephemeral and have no memory of prior triggers. If the same issue recurs 3 times in a row, the triggered Claude has no "you already tried X twice" context. Mitigation: the daemon appends prior trigger outcomes to the trigger prompt ("this is the 3rd integration-failed on change Y in the last 30 min — previous attempts: ..."), giving Claude the relevant history without a long conversation.

## Open questions

- **Where does `set-supervisor` live on disk?** Currently `bin/set-supervisor` would be simplest, but maybe it belongs inside the engine alongside `set-orchestrate`.
- **How does the web dashboard render canary results?** A new "Canary" tab per project? Or inline in the existing logs view?
- **Should the canary write back to the orchestration-state.json** (e.g. setting a "canary-flagged" field on a change) so other consumers can see the flag?
- **What is the right default for `supervisor_mode`?** `python` for new deployments, but existing deployments might need `claude` as the default until we are confident in the daemon.
- **Should trigger budgets be per-trigger or shared?** Currently each trigger has its own timeout. A shared "max 10 triggers per hour" rate limit might also make sense.
