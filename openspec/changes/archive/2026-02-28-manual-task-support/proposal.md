## Why

The orchestration system (set-orchestrate + wt-loop) is fully autonomous — Ralph picks up tasks, implements them, and the verify gate merges. But real-world projects have steps that **require human action**: providing API keys, creating accounts on third-party services, approving designs, configuring webhooks, etc. Currently these tasks cause Ralph to stall silently because it can't proceed without the missing input, wasting iterations before hitting the stall threshold. The user has no visibility into *what* is needed or *why* the agent stopped.

## What Changes

- **New `[?]` task checkbox syntax** in tasks.md marking tasks that require human intervention (alongside existing `[ ]` pending and `[x]` done)
- **`### Manual:` instruction sections** in tasks.md providing detailed step-by-step instructions for each manual task (what to do, links, expected input format)
- **`waiting:human` loop status** in wt-loop — when Ralph detects only `[?]` tasks remain (all `[ ]` auto-tasks done), it exits cleanly with this status instead of stalling
- **Orchestrator awareness** — set-orchestrate's `poll_change()` recognizes `waiting:human` and displays it prominently instead of treating it as a stall/failure
- **`wt-manual` CLI tool** — new command to show pending manual tasks, provide input (secrets → .env files), confirm completion, and resume the agent loop
- **Planner prompt update** — teach the planner LLM to generate `[?]` tasks with `### Manual:` sections when a change involves external services, secrets, or human decisions

## Capabilities

### New Capabilities
- `manual-task-syntax`: The `[?]` checkbox format, `### Manual:` instruction sections, and tasks.md parsing logic for manual task detection
- `manual-task-detection`: wt-loop detection of manual-only remaining tasks and `waiting:human` status transition, plus orchestrator handling
- `manual-task-cli`: The `wt-manual` command — `show`, `input`, `done`, and `resume` subcommands for human interaction with paused changes

### Modified Capabilities
- `ralph-loop`: Add `waiting:human` status and manual task detection to check_done / stall logic
- `orchestration-engine`: poll_change handles `waiting:human`, status display shows manual task info
- `planning-guide`: Planner prompt teaches LLM to generate `[?]` tasks for external/human-dependent steps

## Impact

- **bin/wt-loop**: New status `waiting:human`, modified `check_tasks_done()` and stall detection logic
- **bin/set-orchestrate**: `poll_change()` case for `waiting:human`, status display formatting, planner prompt for `[?]` task generation
- **bin/wt-manual** (new): CLI tool ~200-300 lines for manual task interaction
- **No breaking changes**: existing `[ ]` / `[x]` tasks work exactly as before; `[?]` is purely additive
