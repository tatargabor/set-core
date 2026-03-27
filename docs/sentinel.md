[< Back to README](../README.md)

# Sentinel — Orchestration Supervisor

The sentinel supervises a `set-orchestrate` run, handling crashes, checkpoints, and completion reporting. It runs as a Claude agent launched from the **web UI** ("Start Sentinel" button) or the `/set:sentinel` skill.

For non-interactive orchestration (scripts, CI), use `set-orchestrate start` directly — it has built-in recovery for individual changes but no crash recovery for the orchestrator process itself.

## How It Works

The `/set:sentinel` skill is an AI agent that starts the orchestrator, monitors it, and makes intelligent decisions:

- **Crash recovery**: Reads logs, diagnoses the error, decides whether to restart or stop
- **Checkpoint handling**: Auto-approves routine (`periodic`) checkpoints, escalates others to you
- **Stale detection**: Investigates when the orchestrator appears hung
- **Completion report**: Summarizes the run (changes, tokens, time, issues)
- **Expected pattern awareness**: Distinguishes known transient states (post-merge codegen, watchdog grace, stale cache, long MCP fetch) from real failures

**Usage** — from a Claude Code session in the project directory:

```
/set:sentinel
/set:sentinel --spec docs/v5.md --max-parallel 3
/set:sentinel --time-limit 4h
```

All arguments are passed through to `set-orchestrate start`.

**How it works:**
1. Starts `set-orchestrate start` in background
2. Polls `orchestration-state.json` every 30 seconds
3. When an event occurs (crash, checkpoint, completion), the agent makes a decision
4. Produces a summary report when done

**Cost**: Minimal — the LLM is only invoked for decisions (typically 5-10 calls per run).

## Helper Tools

The sentinel skill uses these CLI helpers:

| Tool | Purpose |
|------|---------|
| `set-sentinel-finding` | Log bugs, patterns, and assessments during the run |
| `set-sentinel-inbox` | Check for messages from the user or other agents |
| `set-sentinel-log` | Structured sentinel event logging |
| `set-sentinel-status` | Register/heartbeat sentinel status for web UI |

## State Handling

| State | Action |
|-------|--------|
| `done` | Stop — orchestration complete |
| `stopped` | Stop — user interrupted |
| `time_limit` | Stop — respect user's time limit |
| `checkpoint` | Auto-approve periodic, escalate others |
| crash (non-zero exit) | Diagnose and restart or stop |
| stale (>120s no update) | Investigate |

## Files

- `orchestration-state.json` — orchestration state (read by sentinel)
- `orchestration.log` — orchestration log (read for diagnosis)
- `.set/sentinel/stdout.log` — sentinel agent output
- `.set/sentinel/status.json` — sentinel status for web UI
- `.set/sentinel/events.jsonl` — sentinel events
- `.set/sentinel/findings.json` — bugs and observations logged during the run

## E2E Mode (Tier 3)

During E2E testing, the sentinel gains **Tier 3 authority** — it can fix set-core framework bugs and deploy them to the running test. This is restricted to set-core code only (bin/, lib/, .claude/, docs/); consumer project code is never touched. See the full scope boundary and workflow in the sentinel skill (`.claude/commands/set/sentinel.md` — "E2E Mode" section) and the E2E guide (`tests/e2e/E2E-GUIDE.md`).

## When to Use

- **Always** for production orchestration runs — the sentinel catches crashes you'd otherwise miss
- **Web UI** — click "Start Sentinel" for hands-off monitoring
- **CLI** — run `/set:sentinel` from a Claude Code session
- **Non-interactive** — use `set-orchestrate start` directly (no sentinel supervision)

---

*See also: [Orchestration](orchestration.md) · [Ralph Loop](ralph.md) · [Architecture](architecture.md)*
