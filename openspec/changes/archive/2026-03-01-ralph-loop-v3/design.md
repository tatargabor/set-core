## Design

### Feature 1: FF exhausted recovery — auto-generate tasks.md

**Problem**: When `ff_attempts >= ff_max_retries` and no `tasks.md` exists, the loop stalls with no recovery path. The agent wasted tokens and the change is stuck.

**Solution**: Instead of stalling, generate a minimal `tasks.md` from existing artifacts.

**Implementation**:

At the ff_exhausted detection point (wt-loop ~line 1199), before marking as stalled:

1. Read `proposal.md` from the change directory
2. If `design.md` exists, read it too
3. Generate a single-task `tasks.md`:
   ```markdown
   # Tasks

   - [ ] Implement the change as described in proposal.md and design.md
   ```
4. Log warning: "Generated fallback tasks.md from proposal (ff exhausted)"
5. Reset `ff_attempts` to 0
6. Continue the loop — next iteration will see tasks.md and use `apply:` action

**Why minimal?** The ff skill failed to create detailed tasks. A single task still gives the agent clear direction — it can read proposal.md and design.md for scope. Trying to generate a detailed task breakdown in bash would be over-engineering.

**Edge cases**:
- No proposal.md → stall as before (shouldn't happen — orchestrator pre-creates it)
- Fallback tasks.md already exists from previous recovery → don't overwrite, just reset ff_attempts

### Feature 2: Real-time terminal output

**Problem**: Claude output is piped through `tee` which uses 64KB kernel pipe buffer. The full output only appears when Claude finishes — no visibility during execution.

**Solution**: Use `stdbuf -oL` for line-buffered output.

**Implementation**:

Change the Claude invocation pipe (wt-loop ~line 934-939):

```bash
# Before:
echo "$prompt" | env -u CLAUDECODE claude ... --verbose 2>&1 | tee -a "$iter_log_file"

# After:
echo "$prompt" | env -u CLAUDECODE stdbuf -oL claude ... --verbose 2>&1 | stdbuf -oL tee -a "$iter_log_file"
```

`stdbuf -oL` forces line-buffered stdout. Both `claude` and `tee` need it:
- `claude` stdout → line-buffered (shows output as it generates)
- `tee` stdout → line-buffered (passes through to terminal immediately)

**Why not stream-json?** `--output-format stream-json` only works with `--print` mode, but we need interactive mode for skills and hooks. `--verbose` + `stdbuf -oL` gives real-time visibility within the existing interactive architecture.

**Fallback**: `stdbuf` may not exist on all systems (it's part of GNU coreutils). Check availability and fall back to unbuffered pipe without `stdbuf`.

## Decisions

- Minimal single-task fallback over LLM-generated task breakdown (simplicity, no extra token cost)
- `stdbuf -oL` over `script -c` PTY wrapper (simpler, no pseudo-terminal complications)
- Keep interactive mode (not `--print`) to preserve skill/hook support
