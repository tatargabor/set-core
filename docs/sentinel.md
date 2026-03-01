# wt-sentinel — Orchestration Supervisor

`wt-sentinel` supervises a `wt-orchestrate` run, handling crashes, checkpoints, and completion reporting.

## Two Modes

### Agent mode (recommended): `/wt:sentinel`

An AI agent that starts the orchestrator, monitors it, and makes intelligent decisions:

- **Crash recovery**: Reads logs, diagnoses the error, decides whether to restart or stop
- **Checkpoint handling**: Auto-approves routine (`periodic`) checkpoints, escalates others to you
- **Stale detection**: Investigates when the orchestrator appears hung
- **Completion report**: Summarizes the run (changes, tokens, time, issues)

**Usage** — from a Claude Code session in the project directory:

```
/wt:sentinel
/wt:sentinel --spec docs/v5.md --max-parallel 3
/wt:sentinel --time-limit 4h
```

All arguments are passed through to `wt-orchestrate start`.

**How it works:**
1. Starts `wt-orchestrate start` in background
2. Polls `orchestration-state.json` every 15 seconds (in bash — no LLM cost)
3. When an event occurs (crash, checkpoint, completion), the agent makes a decision
4. Produces a summary report when done

**Cost**: Minimal — the LLM is only invoked for decisions (typically 5-10 calls per run using Haiku).

### Bash mode (fallback): `wt-sentinel`

A simple bash wrapper for environments without Claude agent access:

```bash
wt-sentinel
wt-sentinel --spec docs/v5.md --max-parallel 3
```

**What it does:**
- Restarts on crash with 30s backoff
- Stops on clean exit (`done`, `stopped`, `time_limit`)
- Gives up after 5 rapid crashes (<5 min each)
- Logs to both stdout and `orchestration.log`

**What it doesn't do** (vs agent mode):
- No log-based crash diagnosis
- No checkpoint auto-approve
- No stale investigation
- No completion report

## State Handling

Both modes handle orchestration states the same way:

| State | Action |
|-------|--------|
| `done` | Stop — orchestration complete |
| `stopped` | Stop — user interrupted |
| `time_limit` | Stop — respect user's time limit |
| `checkpoint` | Agent: auto-approve periodic, escalate others. Bash: n/a |
| crash (non-zero exit) | Diagnose and restart or stop |
| stale (>120s no update) | Agent: investigate. Bash: n/a |

## Files

- `orchestration-state.json` — orchestration state (read by sentinel)
- `orchestration.log` — orchestration log (read for diagnosis, written to by bash sentinel)
- `sentinel.pid` — bash sentinel PID file (cleaned up on exit)

## When to Use

- **Always** for production orchestration runs — the sentinel catches crashes you'd otherwise miss
- **Agent mode** when you're starting from a Claude session and want hands-off monitoring
- **Bash mode** when running from a script, cron, or CI without Claude agent access
