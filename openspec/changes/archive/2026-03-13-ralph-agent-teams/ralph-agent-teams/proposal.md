## Why

Ralph iterations currently execute sequentially — one Claude session works through tasks one by one within each iteration. For changes with multiple independent implementation tasks (e.g., "create 3 API routes + 3 UI pages"), this is slow because the tasks could be parallelized. Claude Code's Agent Teams feature (TeamCreate, Agent tool with team_name, SendMessage) is available in interactive mode — the same mode Ralph already uses. By modifying the Ralph engine prompt to instruct Claude to spawn Agent Teams for parallelizable work within iterations, we can speed up implementation without changing the existing infrastructure (watchdog, budget, state machine, orchestrator).

Previous attempt (2026-03-13, archived) tried Agent Teams at the orchestrator/bash level — failed because `-p` mode subagents lack skills, MCP tools, and context calculation. This approach is fundamentally different: the prompt instructs Claude in interactive mode to use teams, where all capabilities are available.

## What Changes

- Modify `build_prompt()` in `lib/loop/prompt.sh` to inject Agent Teams instructions when team mode is enabled
- Add `team_mode` configuration option to `wt-loop start` (opt-in flag `--team`, defaults to off)
- Store team mode setting in loop-state.json so engine reads it per-iteration
- Add team cleanup logic between Ralph iterations (TeamDelete leftover teams)
- Track team metrics (teammates spawned, parallel tasks completed) in iteration state
- Add Agent Teams guidance to the prompt that teaches Claude when to parallelize vs when sequential is better

## Capabilities

### New Capabilities
- `ralph-team-prompt`: The prompt injection that instructs Claude on Agent Teams usage — when to spawn teams, how to decompose tasks for parallel execution, teammate coordination patterns, and when NOT to use teams (simple sequential tasks)
- `ralph-team-config`: Configuration and state management for team mode — CLI flag, loop-state field, iteration-level metrics tracking
- `ralph-team-lifecycle`: Team cleanup between iterations — ensure no orphan teams/agents persist across iteration boundaries, handle interrupted teams gracefully

### Modified Capabilities
- `ralph-loop`: The engine prompt building changes to conditionally include team instructions based on config

## Impact

- **Files modified**: `lib/loop/prompt.sh` (prompt building), `lib/loop/engine.sh` (cleanup hook, metrics), `lib/loop/state.sh` (team fields in state), `bin/wt-loop` (--team flag)
- **No changes to**: orchestration layer, watchdog, verifier, merger, dispatcher — all remain untouched
- **Risk**: Low — team mode is opt-in, default behavior unchanged. Prompt injection is additive.
- **Dependencies**: Claude Code Agent Teams (TeamCreate, Agent tool, SendMessage) — stable API available since early 2026
