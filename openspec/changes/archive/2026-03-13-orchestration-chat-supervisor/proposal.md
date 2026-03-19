## Why

The orchestration chat tab spawns a vanilla `claude -p` session with no context about its role as an orchestration supervisor. The agent cannot monitor, query, or control the running orchestration without the user manually explaining what commands to use each time. This makes the chat tab useless for its primary purpose: mobile orchestration supervision.

## What Changes

- New `lib/set_orch/chat_context.py` module that builds a dynamic system prompt on every message, including:
  - Role description (Level 2 reactive supervisor)
  - Live orchestration state snapshot from `orchestration-state.json`
  - Condensed `orchestration.yaml` config summary
  - Available commands reference (set-orch-core, set-orchestrate, wt-loop, etc.)
- `lib/set_orch/chat.py` passes the dynamic context via `--append-system-prompt` on every `claude -p --resume` invocation
- Agent responds in Hungarian by default (configurable)

## Capabilities

### New Capabilities
- `chat-supervisor-context`: Dynamic system prompt injection for orchestration chat — role description, state snapshot, config summary, tools reference

### Modified Capabilities
- `orchestration-chat`: Existing chat capability gains supervisor context injection via --append-system-prompt

## Impact

- `lib/set_orch/chat.py` — adds `--append-system-prompt` flag to claude invocation, imports context builder
- `lib/set_orch/chat_context.py` — new file, reads state/config files from project path
- No frontend changes
- No new dependencies (uses stdlib json/pathlib for file reading)
