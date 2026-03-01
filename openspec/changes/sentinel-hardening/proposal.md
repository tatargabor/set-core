## Why

The current `wt-sentinel` is a dumb bash loop — it restarts on crash with backoff but cannot reason about *why* something failed. It also has bugs: restarts on `time_limit` (ignoring user intent), doesn't handle all states, has no logging or notifications.

An agent-based sentinel can read logs, diagnose crashes, make informed restart/stop decisions, auto-approve routine checkpoints, and produce summary reports. This replaces the bash sentinel with a skill-driven Claude agent that uses Haiku for cost-efficient monitoring.

## What Changes

- Replace `bin/wt-sentinel` bash loop with an agent skill (`/wt:sentinel`)
- Agent starts `wt-orchestrate start` in background, then polls state.json + logs
- Intelligent decision-making: crash diagnosis from logs, checkpoint auto-approve (periodic only), time_limit stop with summary, stale state investigation
- Escalation to user for non-routine situations
- Final report on orchestration completion
- Usage documentation

## Capabilities

### New Capabilities
- `agent-sentinel`: Agent-based orchestration supervisor skill with intelligent monitoring and decision-making

### Modified Capabilities
- `orchestrator-sentinel`: Replace bash loop with agent-driven supervision

## Impact

- `bin/wt-sentinel` — replaced by agent skill (kept as minimal fallback or removed)
- `.claude/skills/wt/` — new sentinel skill prompt
- `docs/` — sentinel usage documentation
- No changes to `wt-orchestrate` itself
