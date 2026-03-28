[< Back to Index](../INDEX.md)

# Sentinel — Orchestration Supervisor

The sentinel is an AI supervisor that watches your orchestration run, handles crashes, approves checkpoints, and produces a summary report when done.

## Why Use It

Without the sentinel, a crash in the orchestrator process means your run stops and you have to notice and restart it manually. The sentinel:

- **Detects crashes** — reads logs, diagnoses the error, decides whether to restart
- **Auto-approves checkpoints** — routine periodic checkpoints pass automatically; unusual ones escalate to you
- **Detects stalls** — investigates when the orchestrator appears hung (>120s no update)
- **Reports results** — summarizes the run: changes, tokens, time, issues

**Cost is minimal** — the LLM is only invoked for decisions (typically 5-10 calls per entire run).

## Starting the Sentinel

### From the Web Dashboard (recommended)

Open `http://localhost:7400`, select your project, and click **Start**.

![Dashboard with sentinel controls](../images/auto/web/dashboard-overview.png)

### From Claude Code

```
/set:sentinel
/set:sentinel --spec docs/v5.md --max-parallel 3
/set:sentinel --time-limit 4h
```

### Without Sentinel (direct)

```bash
set-orchestrate --spec docs/spec.md plan
set-orchestrate start
```

This has built-in recovery for individual changes but no crash recovery for the orchestrator process itself.

## How It Works

1. Starts `set-orchestrate start` in background
2. Polls `orchestration-state.json` every 30 seconds
3. On events (crash, checkpoint, completion) — makes a decision
4. Produces a summary report when done

### Decision Table

| Event | Sentinel Action |
|-------|----------------|
| `done` | Stop — orchestration complete |
| `stopped` | Stop — user interrupted |
| `time_limit` | Stop — respect user's time limit |
| `checkpoint` | Auto-approve periodic, escalate others |
| Crash (non-zero exit) | Diagnose from logs, restart or stop |
| Stale (>120s no update) | Investigate cause |

## Monitoring

The sentinel tab in the dashboard shows real-time supervisor events:

![Sentinel tab](../images/auto/web/tab-sentinel.png)

Findings (bugs, patterns, observations) are logged during the run and visible in the learnings tab:

![Learnings tab](../images/auto/web/tab-learnings.png)

## Helper Tools

| Tool | Purpose |
|------|---------|
| `set-sentinel-finding` | Log bugs, patterns, and assessments |
| `set-sentinel-inbox` | Check for messages from user or agents |
| `set-sentinel-log` | Structured event logging |
| `set-sentinel-status` | Register/heartbeat for web UI |

## Files

| File | Purpose |
|------|---------|
| `orchestration-state.json` | Orchestration state (read by sentinel) |
| `orchestration.log` | Orchestration log (for diagnosis) |
| `.set/sentinel/stdout.log` | Sentinel agent output |
| `.set/sentinel/events.jsonl` | Sentinel events |
| `.set/sentinel/findings.json` | Bugs and observations |

---

*Next: [Orchestration Guide](orchestration.md) · [Dashboard](dashboard.md) · [Quick Start](quick-start.md)*

<!-- specs: sentinel-dashboard, sentinel-polling, sentinel-findings, sentinel-events -->
