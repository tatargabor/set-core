# Proposal: Memory Hook Optimization

## Why

The shodh-memory hook system injects context into every Claude Code prompt via 5 event hooks (SessionStart, UserPromptSubmit, PostToolUse, PostToolUseFailure, SubagentStart/Stop). Real-world data from orchestration runs reveals severe token waste:

- **36,587 PostToolUse recall calls** logged — most using garbage queries (task IDs, `jq` commands, `find` output) that return irrelevant memories
- **~48% of per-session tokens** consumed by memory injection, not actual work
- **Same memory injected repeatedly** across different hook fires with different context IDs (content dedup broken)
- **MIN_RELEVANCE = 0.3** allows nearly everything through
- **No token budget** — if 5 memories match, all 5 are injected regardless of total size
- **No way to disable/reduce hooks** for orchestration runs where token efficiency matters most

An orchestration run with 6 changes burns ~900K tokens on memory injection alone — nearly half the session budget.

## What Changes

- **Disable PostToolUse memory recall by default** — this is the single largest source of waste (36,587 of 45,416 recall calls). Make it opt-in via environment variable.
- **Raise relevance threshold** from 0.3 to 0.55 to filter low-quality matches.
- **Reduce injection limits** — UserPromptSubmit 5→3, SessionStart 5→3.
- **Add content-based dedup** — prevent same memory content from being injected under different context IDs.
- **Truncate displayed content** — cap each memory at 300 chars in hook output (storage stays at 500).
- **Add per-injection token budget** — max 800 tokens per hook fire, skip remaining memories if exceeded.
- **Add hook mode env var** (`SET_MEMORY_HOOKS`) — `full` (current), `lite` (SessionStart + UserPromptSubmit only), `off` (disabled).
- **Add hit-rate metrics** — log whether injected memories were referenced by the assistant, enabling data-driven tuning.
- **BREAKING**: PostToolUse (Read/Bash) memory recall disabled by default. Set `SET_MEMORY_HOOKS=full` to restore old behavior.

## Capabilities

### New Capabilities

- `memory-hook-modes`: Environment-based hook mode control (`full`/`lite`/`off`)

### Modified Capabilities

- (none — memory hooks are not currently specced; this change establishes the first spec)

## Impact

- **Files modified**: `lib/set_hooks/events.py`, `lib/set_hooks/memory_ops.py`, `lib/set_hooks/util.py`
- **Consumer projects**: Hook behavior changes immediately for all projects using set-core hooks (deployed via `set-project init`). The `lite` default means consumer orchestration runs automatically benefit.
- **Token savings**: Estimated 50-70% reduction in memory injection overhead.
- **Risk**: Potential loss of occasionally useful PostToolUse context. Mitigated by `full` mode opt-in and hit-rate metrics for future tuning.
