## Context

The current `wt-sentinel` is a 123-line bash loop that blindly restarts `wt-orchestrate start` on crash with 30s backoff. It has bugs (restarts on `time_limit`), no logging, no notifications, and cannot reason about failures. An agent-based sentinel can read logs, diagnose crashes, auto-approve routine checkpoints, and produce reports — all using Haiku for cost efficiency.

Current code: `bin/wt-sentinel` (bash wrapper), `bin/wt-orchestrate` (orchestrator with state.json + .log), `.claude/skills/wt/SKILL.md` (worktree skill), `.claude/commands/wt/loop.md` (wt-loop skill pattern).

## Goals / Non-Goals

**Goals:**
- Replace dumb bash restart loop with an agent skill that can reason about orchestration state
- Correct state handling: stop on `time_limit`, `done`, `stopped`; restart only on crash
- Log-based crash diagnosis before deciding to restart
- Auto-approve routine (`periodic`) checkpoints
- Escalate non-routine situations to user
- Summary report on completion or terminal failure
- Usage documentation

**Non-Goals:**
- Active beavatkozás (merge conflict resolution, worktree fixes) — that's v3
- New wt-orchestrate features or state changes — sentinel reads existing state
- Complex multi-model routing — Haiku for everything in v2
- Replacing wt-loop — sentinel is orchestration-specific, wt-loop is general-purpose

## Decisions

### 1. Skill-based agent, not bash loop

**Decision:** Create a `/wt:sentinel` skill (command file + SKILL.md section) that runs as a Claude agent session. The agent starts `wt-orchestrate start` via `Bash` tool in background, then enters a poll loop reading state.json and logs.

**Why:** An agent can read log lines, understand error messages, and make informed decisions. A bash loop can only check exit codes.

**Alternative considered:** Keep bash sentinel, add smarts via helper scripts. Rejected — the core value is LLM reasoning about failure context.

**Implementation:**
- `.claude/commands/wt/sentinel.md` — skill command file with the agent prompt
- The skill prompt contains the decision tree, escalation rules, and report format
- No new binary needed — the agent uses existing `Bash`, `Read` tools

### 2. Poll loop pattern

**Decision:** The agent runs a `while true` bash poll loop (like the current sentinel), checking state.json every 15 seconds. When the orchestrator exits or the state changes to a terminal state, the agent processes the result.

```
Agent session:
  1. Start orchestrator: Bash(wt-orchestrate start "$@" &)
  2. Poll loop: Bash(while true; read state.json; sleep 15; done)
  3. On state change → agent decides next action
  4. Loop back to poll or exit with report
```

**Why:** The agent doesn't need to be "awake" (using LLM tokens) during normal operation. The poll loop runs in bash, only invoking the LLM when a decision is needed (crash, checkpoint, completion, etc.). This keeps Haiku cost minimal — maybe 5-10 LLM calls per orchestration run.

**Key insight:** The poll script itself detects events and breaks out of the loop to return control to the agent only when something needs a decision. Normal "still running" polls stay in bash.

### 3. Decision tree

**Decision:** The agent follows this priority order when the poll loop returns:

| State | Exit Code | Agent Action |
|-------|-----------|-------------|
| `done` | 0 | Final report → stop |
| `stopped` | 0 | "User stopped" → stop |
| `time_limit` | 0 | Summary of progress → stop |
| `checkpoint` | (running) | Read reason → auto-approve if `periodic`, escalate otherwise |
| `running` but stale (>120s no state update) | (running) | Investigate: check PID, read last log lines, decide |
| (crash) | non-zero | Read last 50 log lines → diagnose → restart or give up |

**Escalation:** If the agent cannot confidently decide (unknown error pattern, non-periodic checkpoint, 3+ consecutive crashes), it stops and reports to the user rather than guessing.

### 4. Crash diagnosis

**Decision:** On crash (non-zero exit), the agent reads the last 50 lines of orchestration.log and the state.json, then decides:

- **Known recoverable patterns** (e.g., "jq: error", transient file lock, network timeout): restart with backoff
- **Known fatal patterns** (e.g., "No such file", missing dependency, auth error): stop and report
- **Unknown pattern**: restart once, if crashes again with same pattern → stop and report

**Why:** The current sentinel restarts blindly up to 5 times. An LLM can read the error and make a better call on the first try.

**Rapid crash limit preserved:** Max 5 restarts regardless of diagnosis, as a safety net.

### 5. Checkpoint auto-approve

**Decision:** The agent reads `checkpoints[-1].reason` from state.json. If reason is `periodic` (routine time-based checkpoint), auto-approve by writing `approved: true` + timestamp. For any other reason, report to user and wait.

**Why:** Periodic checkpoints exist as a safety pause — if someone is watching (the sentinel agent), they can be auto-approved. Non-periodic checkpoints (budget exceeded, too many failures) require human judgment.

**Implementation:** Same atomic write pattern as the TUI approve action (temp file + rename).

### 6. Stale state detection

**Decision:** Before each restart, check orchestration-state.json:
- `status == "running"` but no orchestrator process → reset to `stopped`
- `status == "checkpoint"` but no orchestrator process → leave as-is (checkpoint persists across restarts)
- Any other state → leave as-is

**Why:** The current sentinel only handles "running" stale state. "checkpoint" should persist because the orchestrator resumes from it.

### 7. Reporting

**Decision:** On terminal events (done, time_limit, give-up), the agent produces a summary:

```
## Orchestration Report
- Status: done / time_limit / failed
- Duration: Xh Ym (active) / Xh Ym (wall)
- Changes: N/M complete
- Tokens: X.XM
- Restarts: N (reasons: ...)
- Issues: (any notable errors or warnings from logs)
```

**Why:** The user who started the sentinel may not be watching. A summary at the end captures the important information.

### 8. Bash sentinel kept as fallback

**Decision:** Keep `bin/wt-sentinel` but fix the `time_limit` bug (add it to the clean-exit conditions). The agent skill is the recommended way, but the bash fallback works for environments without Claude agent access.

**Fixes to bash sentinel:**
- Add `time_limit` to clean exit states
- Default any `exit 0` to stop (not restart)
- Log to orchestration.log (append `[sentinel]` prefixed lines)
