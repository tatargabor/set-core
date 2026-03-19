## Why

The memory hook architecture has 3 layers that all depend on agent compliance: CLAUDE.md ambient instructions, SKILL.md inline hooks, and Stop hook text reminders. In practice, agents skip all three when focused on the main task. We need an agent-independent 4th layer that automatically extracts insights from the session transcript after opsx/openspec skill execution — a hard guarantee that knowledge is never lost.

## What Changes

- Enhance `wt-hook-memory-save` to read `transcript_path` from Stop hook stdin (currently discarded via `cat > /dev/null`)
- Detect whether opsx/openspec skills were invoked during the session by scanning the transcript JSONL
- When skills were active: extract the last ~50 transcript entries, pipe to a small LLM (claude haiku via CLI) for insight extraction, save results to `set-memory remember`
- Keep existing commit-based design choice extraction as a parallel path
- Add `stop_hook_active` check to prevent infinite loops

## Capabilities

### New Capabilities
- `transcript-memory-extraction`: Automatic extraction of session insights (errors, learnings, user corrections, discovered patterns) from Claude Code transcript JSONL after opsx/openspec skill execution, using a small LLM call

### Modified Capabilities

## Impact

- `bin/wt-hook-memory-save`: Major rewrite — reads stdin, adds transcript scanning and LLM extraction alongside existing commit logic
- Cost: ~1-2 cent per triggered session (haiku call), only fires when opsx skills detected in transcript
- Dependency: `claude` CLI must be available on PATH for the LLM extraction step
- Timeout: current 30s may need increase for LLM call; or run extraction async
