## Why

The verify gate retry system has two gaps that waste tokens and reduce success rates: (1) merge conflict retries blindly re-attempt the same `wt-merge` without updating the source branch, so if the LLM merge resolution failed once, all 5 retries fail identically; (2) test/review failure retries store detailed failure context (`retry_context`) in state but `resume_change()` never reads it — the agent gets a generic "Continue X" prompt with zero information about what failed. Additionally, memory recall could enrich retry context with relevant past experience.

## What Changes

- **Merge conflict agent-assisted rebase**: On merge conflict, instead of just retrying the merge, resume the agent in the worktree to merge main into the branch and resolve conflicts. Once the agent finishes, retry the merge (which should now be clean since the branch already incorporates main).
- **Retry context passthrough**: `resume_change()` reads `retry_context` from state and includes it in the task description passed to `wt-loop`, so the agent knows exactly what tests failed or what review issues were found.
- **Memory-enriched retries**: Before resuming an agent for retry, recall relevant memories (recent merges, past failures for similar changes) and include them in the retry prompt. This gives the agent inter-change context.

## Capabilities

### New Capabilities
- `verify-retry-context`: Improvements to how the orchestrator handles verify gate retries — merge conflict resolution via agent rebase, retry context passthrough, and memory-enriched retry prompts

### Modified Capabilities

## Impact

- **Code**: `bin/set-orchestrate` — `resume_change()`, `merge_change()`, `retry_merge_queue()`, `handle_change_done()`
- **Dependencies**: None new — uses existing `wt-merge`, `wt-loop`, `orch_recall`/`orch_remember`
- **Systems**: Agents in worktrees will receive richer retry prompts; merge conflict flow changes from "retry same merge" to "agent rebase + retry merge"
