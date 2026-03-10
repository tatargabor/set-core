# The Sentinel

## Why Does the Supervisor Need a Supervisor?

The orchestrator itself is a process — and processes sometimes die. OOM kill, API timeout, unexpected exception, broken pipe. If the orchestrator runs overnight without supervision and stops, the developer finds a half-finished state in the morning.

`wt-sentinel` answers this problem: a supervisor that watches the orchestrator, and if it stops, tries to restart it. It operates in two modes: **bash mode** (cost-free, deterministic) and **agent mode** (LLM-based, intelligent decision-making).

## Bash Sentinel

The bash sentinel is a standalone script that wraps the `wt-orchestrate start` command:

```bash
wt-sentinel --spec docs/v3.md --time-limit 5h
# ↑ all options are passed through to the orchestrator
```

### Crash Recovery with Exponential Backoff

When the orchestrator stops, the sentinel doesn't restart immediately — it waits with exponential backoff:

```
Crash 1: wait 30s  (+ 0-25% jitter)
Crash 2: wait 60s
Crash 3: wait 120s
Crash 4: wait 240s (maximum)
Crash 5: give up → SENTINEL_FAILED event
```

If the orchestrator ran for at least 5 minutes (sustained run), the counter and backoff reset. This distinguishes startup errors (configuration problem that always kills immediately) from runtime crashes (API timeout that happens once and then runs fine).

### Liveness Detection

The sentinel doesn't parse logs — it watches the events file modification time (mtime):

```
Orchestrator → WATCHDOG_HEARTBEAT (every 15s) → events.jsonl mtime updates
Sentinel → polls mtime (every 10s)
  → If >180s since last change → orchestrator is stuck
  → SIGTERM → 30s wait → SIGKILL if needed → restart
```

The `WATCHDOG_HEARTBEAT` event is emitted by the monitor loop every cycle. If it's missing for more than 3 minutes, the sentinel intervenes.

### State Recovery

Before every restart, the sentinel attempts to repair the state:

1. **Event-based reconstruction**: If `orchestration-state.json` is older than the events log, the sentinel reconstructs state from event replay — which change was where, how many tokens were used
2. **Dead PID detection**: Checks PIDs of `running` changes. If the process is no longer alive, the change moves to `stalled` status (the watchdog will handle it)
3. **State normalization**: If orchestrator status is `running` but no process exists, sets it to `stopped`

### Exit Classification

The sentinel distinguishes between **terminal** and **transient** exits:

| State | Category | Sentinel Action |
|-------|----------|----------------|
| `done` | Terminal | Stops, no restart |
| `stopped` | Terminal | Stops |
| `time_limit` | Terminal | Stops |
| `plan_review` | Terminal | Stops (human decision needed) |
| Any crash | Transient | Restart with backoff |

## Agent Sentinel

The `/wt:sentinel` skill runs as a Claude Code session and makes intelligent decisions:

### Tiered Intervention

The agent sentinel operates on this principle: **don't intervene in orchestration-level problems** — the orchestrator has built-in recovery.

| Tier | When | Examples |
|------|------|---------|
| **Tier 1 — Don't intervene** | Orchestration-level problem | merge-blocked, test fail, verify retry, replan |
| **Tier 2 — Intervene** | Process-level problem | Crash, hang, terminal state, checkpoint |

Merge conflict? The orchestrator handles it with 3-layer conflict resolution. Test failure? The orchestrator retries. Individual change failed? The orchestrator continues with the rest. The agent sentinel only steps in when the orchestrator process itself is stuck.

### Checkpoint Handling

- **Periodic checkpoint** (after N merges): automatic approval
- **Budget checkpoint** (token hard limit): escalate to user
- **Other checkpoints**: user decision needed

### Autonomy Rules

The sentinel operates with special rules:

- **Never ask before fixing** — if there's a bug, fix it, commit it, restart
- **Never ask before restarting** — after a crash, cleanup and restart without confirmation
- **Polling must never stop on its own** — after a fix, continue; after a restart, continue; after context compact, continue

\begin{keypoint}
The sentinel provides dual protection: the bash sentinel watches the process cost-free and restarts automatically, while the agent sentinel analyzes the situation with LLM and makes intelligent decisions. For production runs, the bash sentinel is the baseline; the agent sentinel is optional, useful for E2E testing and development.
\end{keypoint}

## Sentinel Events

The sentinel writes directly to the events JSONL (no dependency on the `events.sh` module):

| Event | Meaning |
|-------|---------|
| `SENTINEL_RESTART` | Orchestrator stopped, restarting (exit code, backoff, crash count) |
| `SENTINEL_FAILED` | 5 rapid crashes, sentinel gave up |
| `STATE_RECONSTRUCTED` | State reconstructed from events |
