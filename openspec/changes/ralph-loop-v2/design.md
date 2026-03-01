## Context

The Ralph loop (`bin/wt-loop`) runs Claude Code iteratively in a terminal to complete tasks. Each iteration spawns a new `claude` process via pipe: `echo "$prompt" | claude --verbose`. This means every iteration rebuilds context from scratch (30-50K tokens), there's no per-iteration log separation, no real-time visibility, and token budget enforcement auto-stops and triggers orchestrator restart cascades.

The v6 orchestration runs on sales-raketa showed 24x token overhead (1.6M vs 50K manual) for trivial tasks. Key failure modes: sessions ending before FF completes all artifacts, budget exceeded → restart → budget exceeded cascade, 22+ no-op iterations with no done detection, and zero visibility into what Claude was doing during execution.

Claude CLI supports: `--resume <session-id>` (resume specific session, interactive mode), `--continue` (resume most recent, interactive mode), `--session-id <uuid>` (pre-assign session ID), `--output-format stream-json` (print mode only). Interactive mode is required for skills (`/opsx:ff`, `/opsx:apply`) and hooks.

## Goals / Non-Goals

**Goals:**
- Eliminate context rebuild overhead by resuming sessions instead of starting fresh
- Per-iteration log files for post-mortem analysis
- Token budget checkpoint that pauses for human decision (not auto-restart)
- Real-time terminal output showing Claude's tool use progress
- Universal done detection safety net (tasks.md all-checked = done)

**Non-Goals:**
- Changing the `--print` vs interactive mode decision (staying interactive for skill support)
- Rewriting the orchestrator's dispatch model
- Session persistence across machine restarts
- Changing how openspec artifacts are generated (the FF skill itself)

## Decisions

### D1: Session continuation via `--resume <session-id>`

Use `--session-id <uuid>` on first iteration to pre-assign a known session ID, stored in `loop-state.json`. On subsequent iterations, use `--resume <session-id>` to continue where Claude left off.

**Why not `--continue`**: It resumes the *most recent* session in the directory, which could be wrong if another process ran Claude in between. Explicit session ID is deterministic.

**Fallback**: If `--resume` fails (session expired, corrupted), fall back to new session with a new UUID. Log a warning.

**Prompt changes**: First iteration gets the full task prompt. Resume iterations get a shorter continuation prompt: "Continue where you left off. Check tasks.md for remaining work."

**Alternative considered**: Keep new sessions but pass more context via files instead of prompt. Rejected — doesn't solve the fundamental 30-50K overhead of Claude re-reading CLAUDE.md, design docs, etc.

### D2: Per-iteration log files

Each Claude invocation writes to `.claude/logs/ralph-iter-NNN.log` (zero-padded 3 digits). The `script -c` PTY wrapper (already used for output) tees to both terminal and log file.

Format: `.claude/logs/ralph-iter-001.log`, `.claude/logs/ralph-iter-002.log`, etc.

Old single `ralph-loop.log` is replaced. On loop start, create `.claude/logs/` directory. No rotation — logs accumulate per loop run. The `.claude/` directory is gitignored.

### D3: Token budget → `waiting:budget` human checkpoint

When `total_tokens > token_budget`:
1. Update status to `"waiting:budget"` (not `"budget_exceeded"`)
2. Display checkpoint banner with current/budget numbers
3. Send `notify-send` notification
4. **Do not exit** — enter a wait loop (sleep + poll state file for `status` change)

Human can then:
- `wt-loop resume` → changes status back to `"running"`, loop continues from same session
- `wt-loop budget <N>` → updates `token_budget` in state, status back to `"running"`
- `wt-loop stop` → normal stop

The orchestrator recognizes `waiting:budget` like `waiting:human` — no auto-restart, no stall count increment.

**Why wait loop, not exit**: If we exit, the session dies and `--resume` needs to restart the process. If we wait, the Claude session is still warm in memory (though not actively running). The Ralph bash process just sleeps. When unpaused, the next iteration starts immediately with `--resume` — no process restart overhead.

**Alternative considered**: Soft warning only (log but don't stop). Rejected — defeats the purpose of human oversight for runaway loops.

### D4: Real-time terminal output via verbose + `script`

Since `--output-format stream-json` only works with `--print` mode (which doesn't support skills), we use the existing `script -c` PTY wrapper approach which gives real-time terminal output natively.

The `--verbose` flag already shows tool use events in interactive mode. With `script -c "claude ..."` wrapping, the PTY ensures line-buffered output → events appear in real-time on terminal AND in the per-iteration log file.

Enhancement: Add a post-iteration log summary that extracts key events from the log:
- Files read/written
- Skills invoked
- Errors encountered
- Token usage

This is a simple grep/awk over the log file after Claude exits, displayed in the iteration summary.

**Alternative considered**: Switch to `--print` mode with `stream-json`. Rejected — loses skill and hook support, which is critical for openspec workflow.

### D5: Universal done detection safety net

After each iteration's existing done check, add a fallback:

```
if NOT done by primary criteria:
    if tasks.md exists AND all tasks are [x]:
        → mark done with warning: "Done by tasks.md fallback (primary criteria: {type} said not done)"
```

This catches the case where `done_criteria: openspec` uses `detect_next_change_action` which may have edge cases, but the actual tasks.md is fully checked off. The warning ensures visibility that the fallback fired.

## Risks / Trade-offs

**[Risk: Session resume failures]** → Fallback to new session with warning. Track resume failure count in state. If resume fails 3 times, permanently switch to new-session mode for this loop.

**[Risk: Budget wait loop holds terminal]** → The terminal is already dedicated to this Ralph loop. The wait loop displays a clear banner and polls every 30s. User can always Ctrl+C to kill.

**[Risk: Log file growth]** → Each iteration log can be 1-10MB (verbose output). 10 iterations = 10-100MB. Acceptable for debugging — `.claude/` is gitignored. Could add size-based cleanup later.

**[Risk: `script` wrapper compatibility]** → Already in use for benchmark mode. Works on Linux (`script -f -q -c`). macOS needs different flags (`script -q`). The existing `SCRIPT_CMD` detection handles this.

**[Trade-off: Wait loop vs exit on budget]** → Wait loop is simpler (no process restart) but holds terminal resources. If the user forgets about the loop, it sits idle forever. Mitigated by notification and by orchestrator tracking the status.
