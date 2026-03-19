## Why

The v6 orchestration runs revealed that the Ralph loop burns 10-30x more tokens than necessary. Root causes: every iteration starts a new Claude session (full context rebuild), token budget enforcement causes restart cascades, there's no per-iteration logging for post-mortem analysis, no real-time visibility into what Claude is doing, and the done detection has blind spots. Combined, these turned a 50K-token manual task into 1.6M tokens across 4 changes.

## What Changes

- **Session continuation**: Replace the "new session per iteration" model with `--resume` session continuation. The Claude session runs until it finishes (or times out), and if it exits incomplete, the next iteration resumes it instead of starting fresh. This eliminates the 30-50K token context rebuild per iteration.
- **Per-iteration logging**: Each Claude invocation writes to a separate log file (`.claude/logs/ralph-iter-NNN.log`) for post-mortem analysis. Today everything goes to a single log or nowhere.
- **Token budget → human checkpoint**: Instead of auto-stopping and triggering orchestrator restart cascades, budget exceeded transitions to `waiting:budget` status — the loop pauses and waits for human approval to continue or stop. Like `waiting:human` but for budget.
- **Real-time terminal output**: Use `--output-format stream-json` with a real-time parser that displays tool use events (file reads, edits, skill invocations) in the terminal as they happen. Today the terminal shows nothing during Claude execution.
- **Robust done detection**: Add a universal safety net — if tasks.md exists and all tasks are `[x]`, treat as done regardless of `done_criteria` type. Prevents loops where `openspec` criteria misses completion.

## Capabilities

### New Capabilities
- `ralph-loop-logging`: Per-iteration log file management — separate log per Claude invocation, log rotation, structured filenames for analysis
- `ralph-session-continuation`: Resume-based iteration model — track session IDs, use `--resume` for incomplete work, fall back to new session on resume failure
- `ralph-realtime-output`: Stream-json based real-time terminal output — parse Claude events, display tool use progress, maintain full log alongside

### Modified Capabilities
- `ralph-loop`: Token budget enforcement changes from auto-stop to `waiting:budget` human checkpoint; done detection adds universal tasks.md safety net
- `loop-token-budget`: Budget exceeded behavior changes from stop+restart to pause+wait

## Impact

- `bin/wt-loop` — major refactor of `cmd_run()`: claude invocation method, log file management, budget enforcement, done check, real-time output parsing
- `bin/set-orchestrate` — must recognize `waiting:budget` status (no auto-restart, treat like `waiting:human`)
- `openspec/specs/ralph-loop/spec.md` — new requirements for session continuation, logging, real-time output
- `openspec/specs/loop-token-budget/spec.md` — budget exceeded behavior change
