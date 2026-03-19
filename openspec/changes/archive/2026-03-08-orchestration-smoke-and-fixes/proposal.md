## Why

Two bugs persist across multiple orchestration runs (v8, v9) that waste tokens and leave smoke tests unreliable:

1. **ff→apply not chaining** — After `opsx:ff` creates artifacts, the next Ralph iteration wastes ~60K tokens reading "artifacts complete, ready for apply" without running it. Self-recovers on iter 3 but affects ~30% of changes per run. In v8 this caused 12+ idle iterations per stuck change; in v9 it still wastes 1 iteration per affected change.

2. **Post-merge smoke is non-blocking with a blind generic fixer** — Smoke tests run after merge but failures don't block subsequent merges. The fix agent (generic sonnet with 2000 chars of output, no change context) has a 17% fix rate and wastes ~100K tokens per run on failed fix attempts. Real code issues can accumulate silently across merges.

3. **No idle iteration detection** — When the loop agent produces identical output across consecutive iterations (same byte count, same content hash), the loop continues indefinitely. In production v8 runs, this caused 12+ identical iterations on a single change before the orchestrator's stall detection (which monitors `loop-state.json` freshness, not output content) kicked in. The existing `loop-idle-detection` spec covers FF retry limits, but not general output-level idle detection.

4. **LLM conflict resolver fails on additive list patterns** — When two parallel changes both add entries to the same array/list/object, the `llm_resolve_conflicts()` function in `wt-merge` fails to produce output. The prompt says "keep both sides' changes where possible" but lacks explicit guidance for the common "both sides append to the same collection" pattern. Production v8 required manual sentinel intervention to merge 3 files where both sides added entries to the same array.

5. **No integration tests for the orchestration pipeline** — `set-orchestrate` (4960 lines) has only unit tests for parsing and state management. The merge pipeline, smoke pipeline, dispatch flow, and failure recovery paths are untested.

Evidence from two production orchestration runs:

**v8 run** (8 changes, 2 phases):
- 2 sentinel interventions required:
  1. Smoke test infra fix — parallel workers overwhelmed dev server. Generic smoke fixer couldn't diagnose infra vs code issue.
  2. Manual merge conflict resolution — two changes both added entries to the same array in 3 files. LLM conflict resolver failed on this "both sides add to same list" pattern.
- ~30 wasted iterations total (12+ per stuck change from ff→apply bug + idle loop)
- No output-level idle detection — one change ran 12 identical iterations producing the same ~300 bytes each time
- Orchestrator crashed on merge failure (now handled by retry queue, but no regression test exists)

**v9 run** (7 changes, 1 phase):
- 0 sentinel interventions (fully autonomous)
- 2 wasted iterations (ff→apply bug, self-recovered on iter 3)
- Stall detection worked — deal-reports stalled (0 tokens in 3 min), auto-retried successfully
- 5/7 smoke failures — all caused by stale dev server (not restarted after merges), not code bugs. Generic fixer succeeded 1/6 times (17%), wasted ~100K tokens on the other 5.
- Post-hoc verification: all 23 smoke tests passed when dev server was restarted

**Key pattern**: v8 sentinel fixes (workers config, merge conflict resolution) represent the kind of scoped, context-aware fixes that the current generic smoke fixer can't do. The v9 improvement (0 interventions) came from better spec quality, not tool fixes — the bugs are still there.

## What Changes

### Fix 1: ff→apply explicit chaining in wt-loop (existing)

**Current behavior**: `detect_next_change_action()` in `wt-loop` correctly returns `ff:*` or `apply:*`, and `build_prompt()` generates the right instruction. The problem is that after an ff iteration, the agent commits artifacts and stops — but the *next* iteration sometimes reads from memory "artifacts complete, ready for apply" and gets confused between memory context and the explicit `/opsx:apply` instruction in the prompt.

**Root cause analysis**: Reading `wt-loop` lines 668-678, the ff instruction says "commit the artifacts and stop". The next iteration calls `detect_next_change_action()` again, gets `apply:*`, and produces a prompt with `/opsx:apply`. This *should* work — but in practice the agent's memory injection ("ready for apply") conflicts with the skill invocation, causing 1 wasted iteration.

**Fix**: After an ff iteration completes (tasks.md created), instead of ending the iteration and starting a new one, continue in the same iteration by re-detecting the action and appending the apply prompt. This eliminates the iteration boundary where memory confusion occurs.

Implementation: In the main loop (around line 1240), after detecting that `post_action` is `apply:*` (ff succeeded), set a flag to chain immediately rather than starting a new iteration.

### Fix 2: Output-level idle iteration detection in wt-loop

**Current behavior**: `wt-loop` tracks stalls via commit count (`stall_threshold`, default 2 consecutive iterations with no new commits). But when the agent produces output without committing (e.g., printing "No remaining work" or "artifacts complete"), this doesn't trigger stall detection because the iteration technically "ran".

**Root cause**: The loop has no content-level deduplication. Each iteration's output is logged but never compared to the previous iteration's output.

**Fix**: After each iteration, compute a content hash (md5sum of the last N lines of output). If the same hash appears `max_idle_iterations` (default 3) times consecutively, mark the loop as `idle` and stop it. This catches the pattern where the agent repeats the same message without making progress.

Implementation: In the post-iteration section of `wt-loop`, after recording the iteration in `loop-state.json`, hash the iteration output and compare with the previous hash. Track `idle_count` alongside `stall_count`.

### Fix 3: LLM merge conflict resolver — additive list pattern

**Current behavior**: `llm_resolve_conflicts()` in `wt-merge` extracts conflict hunks and prompts Claude: "keep both sides' changes where possible." For additive conflicts (both sides add entries to the same array, object, or import list), the resolver often fails to produce output.

**Root cause**: The prompt doesn't explicitly recognize the "both sides append" pattern. The LLM sees `<<<<<<< HEAD ... ======= ... >>>>>>>` and sometimes picks one side instead of concatenating both.

**Fix**: Add explicit guidance in the LLM resolver prompt for the additive pattern:
1. Detect if both sides are adding new entries (no deletions, no modifications — pure additions)
2. Add a specific instruction: "When both sides ADD new entries to the same list, array, object, or import block, KEEP ALL entries from both sides in a merged result"
3. Provide an example of the pattern in the prompt

Implementation: Modify the `prompt` variable in `llm_resolve_conflicts()` (around line 143 of `wt-merge`).

### Fix 4: Smoke as blocking gate with scoped fix agent (existing)

Replace the current non-blocking smoke pipeline (lines 4323-4376 of `set-orchestrate`) with:

1. After merge + post_merge_command → **health_check** dev server (curl localhost:PORT, 30s timeout, 5s recompile buffer)
2. If no server → `smoke_blocked` status, sentinel notification, release lock
3. If server OK → run smoke
4. If smoke passes → `completed`, release merge lock
5. If smoke fails → **scoped smoke-fix phase** on main (not generic sonnet):
   - Prompt includes: change scope, modified files list, smoke output, artifacts context
   - Max retries (configurable), token budget, max turns per attempt
   - After each fix: unit tests + build verify (auto-revert if broken)
   - Re-run smoke after each fix
   - Pass → `completed` / Still fail → `smoke_failed`, sentinel notification

New `orchestration.yaml` directives:
```yaml
smoke_blocking: true            # smoke blocks next merge (default: false for backwards compat)
smoke_fix_token_budget: 500000  # max tokens per smoke fix session
smoke_fix_max_turns: 15         # max Claude turns per attempt
smoke_fix_max_retries: 3        # max fix+re-smoke cycles
```

New state transitions:
| State | Meaning | Next merge allowed? |
|---|---|---|
| `merged` | Code on main, smoke pending | NO (if smoke_blocking) |
| `smoking` | Smoke/fix in progress | NO |
| `completed` | All green | YES |
| `smoke_failed` | Fix agent couldn't fix, max retries | NO (pipeline blocked) |
| `smoke_blocked` | No dev server responding | NO (pipeline blocked) |

The merge lock (`flock`) extends through the entire smoke+fix pipeline when `smoke_blocking: true`.

### Fix 5: Orchestration integration tests (existing)

Create `tests/orchestrator/test-orchestrate-integration.sh` — tests the merge pipeline, smoke pipeline, and failure scenarios using mock git repos and stub commands (no real Claude calls).

Test scenarios (derived from v8+v9 production runs):

**Merge pipeline:**
- **Happy flow**: merge → post_merge_command → build pass → smoke pass → completed
- **Merge conflict → retry**: merge fails → status=merge-blocked → retry with updated branch → merged (v8 bug #5: orchestrator used to crash here)
- **Merge conflict → agent rebase**: merge fails → agent-assisted rebase → retry → merged
- **Post-merge build fail → LLM fix**: merge → build broken → auto-fix → build pass → continue
- **Post-merge scope verify**: merge with only artifact files (no implementation) → warning

**Smoke pipeline:**
- **Smoke pass**: merge → smoke pass → status=completed
- **Smoke fail + fix success**: merge → smoke fail → scoped fix agent → smoke pass → status=completed
- **Smoke fail + fix exhausted**: merge → smoke fail → fix fails max_retries times → status=smoke_failed → sentinel notification
- **Health check fail (stale server)**: merge → curl localhost fails → status=smoke_blocked → sentinel notification (v9 root cause: server not restarted after merge)
- **Smoke blocking gate**: with `smoke_blocking: true`, second merge waits until first change's smoke is green
- **Smoke non-blocking (legacy)**: with `smoke_blocking: false`, merges proceed regardless of smoke result

**Dispatch + loop control:**
- **ff→apply chaining**: ff iteration creates tasks.md → same iteration chains apply (no iteration boundary)
- **ff failure + fallback**: ff fails to create tasks.md → retry → fallback tasks generation
- **Stall detection**: no commits for N iterations → stalled status (v8 bug #2: didn't exist, 12+ idle iterations)
- **Repeated commit message detection**: same commit message N times → stalled (v8: agent kept producing identical outputs)
- **Idle iteration with artifact progress**: ff creates files but no commits → not counted as stall

**Sentinel-observable events:**
- All state transitions emit parseable events for sentinel polling
- smoke_failed and smoke_blocked produce critical notifications
- Merge-blocked produces warning notification
- State.json reflects correct status at each step

Test infrastructure:
- Temporary git repos with real branches and merges
- Stub `run_claude` that returns predetermined outputs
- Configurable stub smoke commands (pass/fail/timeout)
- Assert on state.json field values after each operation

## Capabilities

### New Capabilities
- `orchestration-smoke-blocking`: Blocking smoke gate with health check, scoped fix agent, new state machine, and configurable directives
- `loop-idle-detection-v2`: Output-level idle iteration detection via content hashing — stops loops that repeat the same output
- `merge-additive-resolver`: Enhanced LLM merge conflict resolution for additive list/array/import patterns
- `orchestration-integration-tests`: Integration test suite for set-orchestrate merge/smoke/dispatch/failure flows

### Modified Capabilities
- `dispatch-and-loop-control`: ff→apply explicit chaining — eliminate iteration boundary between ff and apply phases

## Impact

- `bin/set-orchestrate` — merge_change() rewrite: health_check(), smoke blocking gate, scoped fix prompt, new states, new directives parsing
- `bin/wt-loop` — ff→apply chaining in main loop + output-level idle detection (content hash comparison)
- `bin/wt-merge` — enhanced LLM resolver prompt with additive pattern guidance and example
- `tests/orchestrator/test-orchestrate-integration.sh` — new file (~400-600 lines)
- `tests/orchestrator/test-orchestrate.sh` — new tests for health_check(), smoke state parsing, idle detection
- `tests/test-merge.sh` — new test cases for additive conflict resolution
- No breaking changes — `smoke_blocking` defaults to false, `max_idle_iterations` defaults to 3, existing behavior preserved
