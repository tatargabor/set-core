## Context

The orchestrator's verify gate pipeline (test → review → verify) supports retries via `resume_change()`, and merge conflicts are retried via `retry_merge_queue()`. Two problems exist:

1. **Merge retry is blind**: `retry_merge_queue()` calls `merge_change()` which runs `wt-merge --llm-resolve`. If the LLM conflict resolution fails, retrying the identical merge is futile — the source branch hasn't changed. All 5 retries produce the same result.

2. **Retry context is orphaned**: `handle_change_done()` builds a `retry_context` string (test command, test output, scope) and stores it in state, but `resume_change()` ignores it — it only passes `"Continue $change_name: $scope"` to `wt-loop`.

3. **No memory recall on retry**: The orchestrator saves merge/test/review outcomes as memories (via `orch_remember`), but never recalls them when preparing a retry prompt.

## Goals / Non-Goals

**Goals:**
- On merge conflict, have the agent rebase the branch onto main and resolve conflicts before retrying the merge
- Pass stored `retry_context` (test output, review feedback) to the agent during retry
- Recall relevant memories before retry to give the agent inter-change context

**Non-Goals:**
- Changing the `wt-merge` script itself (it already has LLM resolve)
- Changing `wt-loop`'s prompt building (keep changes in `resume_change()` task description)
- Adding new retry limits or backoff strategies
- Modifying how `handle_change_done()` builds `retry_context` (already correct)

## Decisions

### **Choice**: Agent-assisted rebase for merge conflicts

On merge conflict (after `wt-merge --llm-resolve` fails), the orchestrator resumes the agent in the worktree with a task: "Merge main into your branch and resolve conflicts." The agent runs `git merge origin/main` (or rebase), resolves conflicts using its understanding of the code, commits, and exits. Then `handle_change_done()` fires, the merge is retried, and it should succeed since the branch now incorporates main.

**Alternative considered**: Rebase the branch automatically (without the agent). Rejected because automated rebase can produce conflicts that need code understanding to resolve — the agent already has context about the change.

**Alternative considered**: Skip merge retry entirely and re-dispatch the change from scratch. Rejected because it wastes all the agent's work.

**Flow:**
```
merge_change() fails
  → status = "merge-blocked"
  → store retry_context with merge conflict info
  → resume_change() with rebase task
  → agent merges main into branch, resolves conflicts
  → handle_change_done() fires
  → retry merge (should now be clean fast-forward-like merge)
```

### **Choice**: resume_change() reads retry_context from state

Instead of modifying `wt-loop` to read orchestrator state, `resume_change()` reads the `retry_context` field from state and prepends it to the task description. This keeps the change localized to one function.

```bash
resume_change() {
    local retry_ctx
    retry_ctx=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .retry_context // empty' "$STATE_FILENAME")
    # Unescape JSON string (retry_context is stored as JSON-escaped)
    retry_ctx=$(echo "$retry_ctx" | jq -r '. // empty' 2>/dev/null || true)

    local task_desc
    if [[ -n "$retry_ctx" ]]; then
        task_desc="$retry_ctx"
    else
        task_desc="Continue $change_name: ${scope:0:200}"
    fi
}
```

**Why not modify wt-loop?** The task description is the natural place for retry context — it's what the agent sees first. No need to add a new channel.

### **Choice**: Memory recall before retry

Before resuming an agent for retry, call `orch_recall` with the change name as query (no tag filter) to capture both orchestrator and agent memories. Append recalled content to the retry prompt as a `## Context from Memory` section.

This means:
- Test failure retry gets memories about what other agents learned about testing patterns
- Merge conflict retry gets memories about what recently merged and what files were affected
- Review failure retry gets memories about past review feedback

**Why no tag filter?** Agent-generated memories (from worktree hooks) may be more relevant than orchestrator memories for fixing code issues.

### **Choice**: Merge conflict retry uses resume_change, not a separate mechanism

Rather than adding a new "rebase-and-retry" function, merge conflict handling reuses the existing `resume_change()` flow. The difference is:
- Current: `retry_merge_queue` → `merge_change` (same merge, same result)
- New: first conflict → `resume_change` with rebase task → agent resolves → `handle_change_done` → `merge_change` (clean merge)

The `retry_merge_queue` function still exists as a fallback for cases where the agent rebase also fails, but the primary path is agent-assisted.

### **Choice**: Clear retry_context after resume

After `resume_change()` reads and uses `retry_context`, it clears the field in state. This prevents stale context from leaking into future resumes (e.g., if the change is paused and resumed for a different reason).

## Risks / Trade-offs

**[Extra agent iteration for merge]** Agent-assisted rebase adds one Ralph loop iteration (~2-5 min) compared to instant merge retry. But the current instant retry always fails, so this is strictly better.

**[Agent may fail to rebase]** The agent might not resolve the merge conflict correctly. Mitigated by: (1) the agent has full code context, (2) if the agent fails, the change goes through `handle_change_done` → test → merge again, eventually hitting the retry limit.

**[Task description size]** Including full test output in the task description could be large. Mitigated by the existing 2000-char truncation on `test_output` and the `retry_context` construction.

**[Memory recall latency]** One additional `orch_recall` per retry (~200ms). Negligible compared to the agent iteration time.
