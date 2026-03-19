# Execution

## Dispatch: The Change Begins

When all of a change's dependencies are satisfied (merged status), `dispatch_ready_changes()` starts execution. The process:

![The complete dispatch and Ralph loop flow](diagrams/rendered/04-dispatch-ralph.png){width=95%}

### 1. Worktree Creation

```bash
set-new <change-name>
# → .claude/worktrees/<change-name>/
# → branch: change/<change-name>
```

`set-new` creates an isolated git worktree where the agent can work freely without affecting the main branch.

### 2. Bootstrap

`bootstrap_worktree()` ensures the worktree is operational:

- Copying `.env` files from the project root
- Installing dependencies (if `package-lock.json` is newer)
- `.env.local`, `.env.development` files are also copied

### 3. Synchronization with Main Branch

`sync_worktree_with_main()` ensures the worktree is built on the latest main:

- If the worktree is up-to-date → skip
- If there's a difference → `git merge main` into the worktree branch
- Generated file conflicts (lock file, `.tsbuildinfo`) → automatic `--ours` resolution
- Real code conflicts → merge abort, warning

### 4. Ralph Loop Start

```bash
set-loop start --change <name> --model <model_id> --max-turns <N>
```

The Ralph PID is saved to the state file.

## The Ralph Loop

The Ralph loop starts with the `set-loop` command and executes an iterative development cycle:

### Iteration Cycle

In each iteration:

1. A **Claude Code session** starts in the worktree
2. The agent receives the **scope** (task description) and optional **retry context**
3. The agent **writes code**, runs tests, modifies files
4. `loop-state.json` is updated at the end of the iteration

### loop-state.json

The iteration state is stored in a JSON file:

```json
{
  "status": "running",           // running | done | error
  "iteration": 5,
  "max_turns": 20,
  "model": "claude-opus-4-6",
  "started_at": "2026-03-10T14:00:00Z",
  "tokens_used": 450000,
  "input_tokens": 300000,
  "output_tokens": 150000,
  "cache_read_tokens": 120000,
  "last_activity": "2026-03-10T14:15:30Z"
}
```

### Completion Conditions

The Ralph loop stops in the following cases:

| Condition | Result |
|-----------|--------|
| Agent signals: done | `status: "done"` |
| `max_turns` reached | `status: "done"` (forced) |
| Token limit reached | `status: "done"` |
| Fatal error | `status: "error"` |

### Context Pruning

The `context_pruning: true` directive (default) enables context window optimization:

- Output from the agent's previous iterations is summarized
- Only the essential parts remain instead of the full conversation
- This reduces token usage and improves quality

## Model Routing

The `model_routing` directive allows different changes to use different models:

- **`off`** (default): every change uses the `default_model`
- Change-specific override in the plan: `"model": "sonnet"`

Typical configuration:

```yaml
default_model: opus        # complex features
review_model: sonnet       # code review (faster, cheaper)
summarize_model: haiku     # summarization (fastest)
```

### Complexity-Based Routing

The planner indicates change size with the `complexity` field:

| Complexity | Characteristics | Typical Model |
|------------|----------------|---------------|
| **S** (Small) | Config, docs, simple fix | sonnet |
| **M** (Medium) | Feature, refactor | opus |
| **L** (Large) | Architecture, cross-cutting | opus |

## Parallel Execution

The `max_parallel` directive controls how many worktrees can have active agents simultaneously:

```
max_parallel: 3

T=0    [auth-system] ─────────────────────────── done → verify
T=0    [api-endpoints] ──────────────────── done → verify
T=0    [config-update] ──── done → verify → merge
T=15   [user-profile] ────────────────── (dispatch after auth merged)
T=30   [dashboard] ────────── (dispatch after slot free)
```

The dispatch logic:

1. Count the `running` + `dispatched` + `verifying` changes
2. If fewer than `max_parallel` → find the next ready change
3. A change is "ready" if: `pending` status AND every `depends_on` entry is `merged`

\begin{keypoint}
Parallel execution doesn't mean all changes run simultaneously. The DAG and max\_parallel together determine the execution schedule. A 15-change plan with parallelism of 3 typically runs in 5-6 "waves."
\end{keypoint}

## Pause and Resume

Execution can be suspended and resumed at any time:

```bash
set-orchestrate pause auth-system    # one change
set-orchestrate pause --all          # all changes
set-orchestrate resume auth-system   # resume
set-orchestrate resume --all         # resume all
```

`pause` stops the Ralph loop (PID kill), but the worktree remains. `resume` restarts the loop, optionally with retry context.

## Token Tracking

Each change's token usage is tracked in real time:

- `tokens_used`: total tokens (input + output)
- `input_tokens`, `output_tokens`: detailed breakdown
- `cache_read_tokens`, `cache_create_tokens`: prompt cache statistics

The `_prev` fields store totals from previous iterations (counting remains accurate after restarts).
