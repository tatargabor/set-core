# The Sentinel

## Why Does the Supervisor Need a Supervisor?

The orchestrator itself is a process — and processes sometimes die. OOM kill, API timeout, unexpected exception, broken pipe. If the orchestrator runs overnight without supervision and stops, the developer finds a half-finished state in the morning.

The sentinel answers this problem: a Claude agent that watches the orchestrator, and if it stops, analyzes the situation and decides how to proceed. It is launched from the **web UI** ("Start Sentinel" button) or via the `/set:sentinel` skill.

For non-interactive use (CI, scripts), `set-orchestrate start` runs the orchestrator directly without sentinel supervision.

## How It Works

The sentinel runs as a Claude Code session (via `supervisor.py`) that polls orchestration state every 30 seconds and makes intelligent decisions:

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

### Helper Tools

The sentinel uses CLI helpers to interact with the system:

| Tool | Purpose |
|------|---------|
| `set-sentinel-finding` | Log bugs, patterns, and assessments during the run |
| `set-sentinel-inbox` | Check for messages from the user or other agents |
| `set-sentinel-log` | Structured event logging |
| `set-sentinel-status` | Register/heartbeat sentinel status for web UI |

\begin{keypoint}
The sentinel provides intelligent supervision: it analyzes orchestrator state with LLM and makes decisions about crashes, hangs, and checkpoints. For simple non-interactive runs, `set-orchestrate start` is sufficient — the orchestrator has built-in crash recovery for individual changes.
\end{keypoint}

## Sentinel Events

The sentinel writes to the events JSONL:

| Event | Meaning |
|-------|---------|
| `SENTINEL_RESTART` | Orchestrator stopped, restarting (exit code, reason) |
| `SENTINEL_FAILED` | Multiple rapid crashes, sentinel gave up |
| `STATE_RECONSTRUCTED` | State reconstructed from events |
