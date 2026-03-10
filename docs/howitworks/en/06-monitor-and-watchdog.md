# Monitor and Watchdog

## The Monitor Loop

The heart of the orchestrator is the `monitor_loop()` function, which runs indefinitely after the `start` command is issued. Its job: check the status of all active changes every 15 seconds and take the appropriate action.

![The monitor loop cycle](diagrams/rendered/05-monitor-loop.png){width=90%}

### The Poll Cycle

In every 15-second cycle, the following occurs:

1. **Status check**: Inspect orchestrator status (running/paused/stopped)
2. **Active change polling**: Call `poll_change()` for every `running` and `verifying` change
3. **Watchdog check**: Call `watchdog_check()` for stall detection
4. **Suspended changes**: Check whether `paused` or `budget_exceeded` changes have finished
5. **Token budget**: Soft and hard limit checks
6. **Verify-failed recovery**: Retry if the retry limit allows
7. **Dispatch**: Start new changes if slots are available
8. **Merge queue**: Process the merge queue
9. **Stall recovery**: Restart stalled changes
10. **Cascade failure**: Propagate failed dependencies
11. **Replan**: If everything is done and `auto_replan` is active, next phase

### poll_change()

`poll_change()` is the most important function. For a single change:

- Reads the `loop-state.json` file from the worktree
- Updates token counters in the state file
- If `status == "done"` → starts the verify pipeline (test → review → verify → smoke → E2E)
- If `status == "error"` → retry or fail

### Active Time Tracking

The monitor doesn't measure wall clock time, but **active time**:

- Only counts when at least one Ralph loop is running (`any_loop_active()`)
- Doesn't count during token budget waits
- Doesn't count during pause
- Active time accumulates across restarts

```
Wall time:    |████████░░████████░░░░████████|  3 hours
Active time:  |████████  ████████    ████████|  2 hours
               ^running  ^pause      ^running
```

## The Watchdog System

The watchdog's job is detecting and handling "stuck" changes. Every active change has its own watchdog state.

![Watchdog escalation levels](diagrams/rendered/06-watchdog-escalation.png){width=90%}

### Detection Mechanisms

#### 1. Timeout Detection

Different timeouts per status:

| Status | Default Timeout | Description |
|--------|----------------|-------------|
| `running` | 600s (10 min) | During implementation |
| `verifying` | 300s (5 min) | During verify pipeline |
| `dispatched` | 120s (2 min) | After dispatch, before Ralph starts |

If more time has elapsed since the last activity than the timeout, escalation begins.

#### 2. Action Hash Loop Detection

The watchdog maintains a "hash ring" for every change:

```json
{
  "action_hash_ring": ["abc123", "abc123", "abc123", "abc123", "abc123"],
  "consecutive_same_hash": 5
}
```

The action hash is computed from key fields of `loop-state.json` (iteration number, token count, status). If the hash is identical N consecutive times (default: 5) → the agent is stuck.

#### 3. Artifact Creation Grace Period

Between dispatch and Ralph loop start, there is a "grace period": the agent is creating OpenSpec artifacts (proposal, design, specs, tasks) and there is no `loop-state.json` yet. The watchdog recognizes this and does not escalate.

### Escalation Levels

| Level | Action | Description |
|-------|--------|-------------|
| **L1** | Warning | Log entry + notification. No intervention. |
| **L2** | Restart | Stop and restart the Ralph loop. Context pruning activates. |
| **L3** | Redispatch | Complete worktree rebuild. Max `max_redispatch` (default: 2) times. |
| **L4** | Give up | Change moves to `failed` status. Notification sent. |

The escalation levels represent gradual intervention. L1 only watches — perhaps the agent will solve the problem on its own (e.g., a long build running). L2 restarts the loop with fresh context — this is the most common recovery, successful about 70% of the time. L3 starts everything from scratch: fresh worktree, fresh branch, full redispatch — expensive, but if L2 doesn't help, this is the last chance. L4 gives up the fight: better to lose one change than burn infinite tokens.

### Recovery Detection

If an escalated change shows activity again (e.g., the hash changes after an L2 restart), the escalation **automatically resets**:

```
L2 (restart) → activity detected → level reset → L0
```

\begin{keypoint}
The watchdog is the only safety net that prevents a stuck agent from consuming tokens indefinitely. In production runs, the watchdog\_timeout and max\_redispatch values should be tuned to the project's characteristics.
\end{keypoint}

## Token Safety Nets

The monitor loop provides two levels of token protection:

### Soft Limit (`token_budget`)

If total token usage across all changes exceeds the `token_budget` value:

- Running loops can finish their current iteration
- New changes **do not** start
- As soon as usage drops below the budget, dispatch resumes

### Hard Limit (`token_hard_limit`)

If total tokens (including previous replan cycles) reach the hard limit:

- **Checkpoint** activates: the orchestrator stops
- Human approval is required to continue
- After approval, the limit is raised

```bash
wt-orchestrate approve   # approve, continue
```

## Time Limit

The `time_limit` directive (default: 5 hours) limits **active** runtime:

```bash
wt-orchestrate --time-limit 4h start     # 4 hour limit
wt-orchestrate --time-limit none start   # no limit
```

When the limit expires:

1. Status changes to `time_limit`
2. Notification sent
3. Summary email sent
4. HTML report generated
5. Execution stops, but worktrees remain

Execution can be resumed: `wt-orchestrate start` — the timer continues where it left off.

## Memory and Auditing

Every 10 polls (~2.5 minutes), the monitor loop automatically:

- `orch_memory_stats()`: memory system health
- `orch_gate_stats()`: gate statistics
- `orch_memory_audit()`: memory audit (duplicate detection)

This ensures the memory system remains healthy during long runs.
