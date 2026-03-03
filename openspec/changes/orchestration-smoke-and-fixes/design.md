## Context

`wt-orchestrate` (4960 lines) manages the full lifecycle of parallel changes: planning → dispatch → loop → verify → merge → post-merge. Two persistent bugs affect every orchestration run:

1. **ff→apply gap**: `wt-loop`'s `build_prompt()` correctly detects `ff:*` and `apply:*` states via `detect_next_change_action()`, but there's an iteration boundary between ff completing and apply starting. Memory injection from the previous iteration ("artifacts complete, ready for apply") confuses the agent, wasting 1 iteration (~60K tokens) per affected change.

2. **Non-blocking smoke with blind fixer**: `merge_change()` (lines 4323-4376) runs smoke after merge, but failures don't block subsequent merges. The fix prompt gives a generic sonnet agent only the last 2000 chars of smoke output — no change scope, no modified files list, no artifacts. Result: 17% fix rate.

Existing test coverage: `tests/orchestrator/test-orchestrate.sh` tests parsing (parse_next_items, parse_directives), state management (init_state, update_change_field), and topological sort — but nothing for the merge pipeline, smoke pipeline, or dispatch flow.

## Goals / Non-Goals

**Goals:**
- Eliminate ff→apply wasted iteration by chaining within the same loop iteration
- Make smoke a configurable blocking gate with health check and scoped fix agent
- Create integration tests that exercise merge pipeline, smoke pipeline, and failure paths using mock repos (no Claude calls)
- Preserve backwards compatibility — `smoke_blocking: false` (default) keeps existing behavior

**Non-Goals:**
- Rewriting the entire merge pipeline — only the smoke section changes
- Adding E2E tests with real Claude calls — integration tests use stubs
- Changing sentinel behavior — sentinel observes new states but its logic doesn't change
- Fixing the LLM merge conflict resolver — that's a separate change

## Decisions

### D1: ff→apply chaining — same-iteration continuation

**Decision**: After an ff iteration completes and `detect_next_change_action()` returns `apply:*`, inject the apply prompt into the *current* Claude session rather than ending the iteration and starting a new one.

**Where**: `wt-loop` main loop, around line 1240 (post-iteration ff tracking section).

**How**: Currently after detecting `post_action == apply:*` (meaning ff succeeded, tasks.md was created), the loop ends the iteration and starts a new one. Instead:
1. After ff iteration completes, check `post_action`
2. If `apply:*` → don't increment iteration, don't end — build a new prompt with the apply instruction and pipe it to a second `claude` invocation in the same iteration
3. Record both the ff and apply phases in the iteration's metadata

**Why not option B (ff skill chains apply)**: Skills should be composable. The ff skill creates artifacts; the loop decides what happens next. Putting chaining logic in the skill creates coupling.

**Fallback**: If the chained apply invocation fails or times out, the iteration ends normally. The next iteration will pick up `apply:*` as before — no regression.

### D2: Smoke blocking gate with health check

**Decision**: Replace the current smoke section in `merge_change()` with a multi-phase pipeline:

```
merge_change() {
    ...existing merge + post_merge_command + build...

    if smoke_blocking:
        health_check(smoke_url, 30s)
          ├─ fail → status=smoke_blocked, notify sentinel, return
          └─ pass → run_smoke()
                      ├─ pass → status=completed, return
                      └─ fail → smoke_fix_loop(max_retries)
                                  ├─ fixed → status=completed, return
                                  └─ exhausted → status=smoke_failed, notify sentinel, return
    else:
        ...existing non-blocking smoke (unchanged)...
}
```

**Health check**: `curl -s -o /dev/null -w '%{http_code}' http://localhost:$PORT` with configurable timeout and a 5-second recompile buffer after post_merge_command. Extracts PORT from smoke_command URL.

**Scoped fix prompt vs current generic prompt**:

| | Current | New |
|---|---|---|
| Model | sonnet (generic) | configurable (default: sonnet) |
| Context | 2000 chars smoke output | smoke output + change scope + modified files + artifacts |
| Scope constraint | none | "MAY ONLY modify files from this change" |
| Verification | re-run smoke only | unit tests + build + smoke |
| Revert | none | auto `git revert` if unit tests/build break |
| Retries | 1 attempt | configurable (default: 3) |

**Modified files list**: Extract from merge commit diff: `git diff HEAD~1 --name-only`. Pass to fix prompt so the agent knows exactly what changed.

**Auto-revert safety**: After each fix attempt, run unit tests and build. If either fails, `git revert HEAD --no-edit` to undo the fix, then try again. This prevents fix attempts from making things worse.

### D3: New orchestration.yaml directives

```yaml
smoke_blocking: false           # default false for backwards compat
smoke_fix_token_budget: 500000  # per smoke fix session
smoke_fix_max_turns: 15         # per attempt
smoke_fix_max_retries: 3        # fix+re-smoke cycles
smoke_health_check_url: ""      # auto-extracted from smoke_command if empty
smoke_health_check_timeout: 30  # seconds to wait for server
```

Parsing: Add to `parse_directives()` alongside existing `smoke_command` and `smoke_timeout`.

### D4: State machine extension

New states for merged changes:

```
merged → smoking → completed
                 → smoke_failed (terminal — needs human)
         smoke_blocked (terminal — needs human)
```

`smoking` is set when health check passes and smoke tests start running. This lets the sentinel detect stuck smoke phases (>15 min in `smoking` state).

State field additions to each change in state.json:
- `smoke_result`: "pass" | "fail" | "fixed" | "blocked" (already exists, keep)
- `smoke_status`: "pending" | "checking" | "running" | "fixing" | "done" | "failed" | "blocked" (new, granular)
- `smoke_fix_attempts`: number (new)

### D5: Integration test architecture

**Approach**: Source `wt-orchestrate` functions (same pattern as existing `test-orchestrate.sh` — `eval "$(sed '/^main/d' ...)"`) then call individual functions with controlled state.

**Mock infrastructure**:
- `setup_test_repo()`: Creates a temp git repo with main branch, a feature branch with a commit, and configurable merge scenario (clean merge, conflict)
- `stub_run_claude()`: Replaces `run_claude` function — returns predetermined exit code, optionally creates files
- `stub_smoke_command()`: Script that returns configurable exit code (0=pass, 1=fail)
- `stub_health_check()`: Returns configurable HTTP status code

**Test lifecycle**: Each test creates a temp dir, initializes state, runs the function under test, asserts on state.json values, cleans up.

**What we DON'T test**:
- Actual Claude API calls
- Real wt-loop/terminal spawning
- Real worktree creation (use plain git branches instead)
- Sentinel polling (sentinel tests are separate)

### D6: Output-level idle iteration detection

**Decision**: After each iteration, compute an MD5 hash of the iteration's output (last 200 lines). Track the hash in `loop-state.json`. If the same hash repeats `max_idle_iterations` (default 3) consecutive times, stop the loop with status `idle`.

**Where**: `wt-loop` post-iteration section, after writing to `loop-state.json`.

**How**:
1. After iteration completes, extract last 200 lines of `iter_log_file`
2. Compute hash: `tail -200 "$iter_log_file" | md5sum | cut -d' ' -f1`
3. Compare with `last_output_hash` in loop state
4. If match: increment `idle_count`; if different: reset `idle_count` to 0, update hash
5. If `idle_count >= max_idle_iterations`: set loop status to `idle`, exit

**Why content hash vs byte count**: Byte count alone could false-positive on different outputs that happen to be the same length. MD5 of the actual content is definitive. 200-line window avoids hashing large iteration logs while capturing the distinctive output pattern.

**Interaction with stall detection**: Idle detection (same output) is orthogonal to stall detection (no commits). A loop can be idle but not stalled (producing identical output with commits — unlikely but possible). Both independently trigger loop stop.

**Config**: `--max-idle N` flag, stored in `loop-state.json` as `max_idle_iterations`. Default 3.

### D7: LLM merge resolver — additive pattern enhancement

**Decision**: Add explicit instructions and examples for the "both sides add to the same list" pattern in the LLM merge conflict resolver prompt.

**Where**: `wt-merge` `llm_resolve_conflicts()`, the `prompt` variable (around line 143).

**Changes to the prompt**:

1. Add a section after the general instructions:
```
IMPORTANT — Additive conflict pattern:
When both sides ADD new entries to the same list, array, object literal, import block,
or similar collection — KEEP ALL entries from BOTH sides. Do NOT pick one side.

Example:
<<<<<<< HEAD
  "action_a",
  "action_b",
=======
  "action_x",
  "action_y",
>>>>>>> feature

Correct resolution:
  "action_a",
  "action_b",
  "action_x",
  "action_y",
```

2. The existing instruction "keep both sides' changes where possible (integrate, don't pick one side)" stays, but the additive example makes the pattern concrete.

**Why prompt change only (no code change)**: The conflict hunk extraction and resolution pipeline work correctly. The issue is purely in the LLM's interpretation of the merge task. An explicit example in the prompt is the minimal fix with highest impact.

### D8: Integration test coverage for new features

**Decision**: Extend the integration test plan to cover idle detection and additive merge resolution.

Additional test scenarios:
- **Idle detection**: 3 iterations producing identical output → loop stops with `idle` status
- **Idle reset**: identical output for 2 iterations, then different output → idle counter resets
- **Additive merge**: two branches both append to the same file/array → LLM resolver stub produces merged output

## Risks / Trade-offs

### R1: ff→apply chaining may increase iteration complexity
The main loop is already complex (~500 lines). Adding a "chain" path means an iteration can have two Claude invocations. Mitigation: clearly document the chain path, and if the chained invocation fails, fall through to normal next-iteration behavior.

### R2: Smoke blocking could slow down multi-change orchestration
With `smoke_blocking: true`, each merge must wait for smoke to complete (potentially including fix retries) before the next change can merge. For a 7-change run with 30s smoke per change, this adds ~3.5 minutes. With fix retries, worst case ~15 minutes. Mitigation: default is `false`; users opt in when they want the safety guarantee.

### R3: Health check URL extraction is heuristic
Extracting PORT from smoke_command URL (`grep -oP 'localhost:\K\d+'`) could miss non-standard formats. Mitigation: `smoke_health_check_url` directive allows explicit override.

### R4: Integration tests are fragile with real git operations
Git commands can behave differently across versions. Mitigation: test only state management and function outputs, not git internals. Use `git init` with minimal config.

### R5: Idle detection false positives on legitimate slow progress
Some legitimate scenarios produce similar-looking output across iterations (e.g., "continuing work on task 3/10" repeatedly). Mitigation: hash the full 200-line window, which includes varying details like timestamps and file paths. Also, 3 consecutive identical outputs is a very strong signal — legitimate progress always has variation in the output.

### R6: Additive merge prompt may increase token usage
Adding an example to the merge prompt increases its size by ~200 tokens. Mitigation: negligible compared to the conflict context that follows (typically 500-5000 tokens).
