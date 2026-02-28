## Context

wt-loop (Ralph) processes tasks.md checkboxes autonomously. When a task requires human action (e.g., "paste your Stripe API key"), Ralph attempts it, fails, and eventually stalls. The orchestrator sees `stalled` and retries up to 3 times before marking `failed`. The user never gets a clear signal about what's needed.

Key code touchpoints:
- `bin/wt-loop` lines 296-306: `check_tasks_done()` counts `- [ ]` patterns
- `bin/wt-loop` lines 873-930: stall detection (no commits → stall_count++)
- `bin/wt-orchestrate` lines 3240-3303: `poll_change()` handles `done|running|stopped|stalled|stuck`
- `bin/wt-orchestrate` lines 1690-1760: planner prompt generates change decomposition

## Goals / Non-Goals

**Goals:**
- Human tasks are clearly marked in tasks.md with `[?]` syntax
- wt-loop detects when only manual tasks remain and exits with `waiting:human` (not stalled)
- Orchestrator distinguishes `waiting:human` from stall/failure — no auto-retry, no failure escalation
- `wt-manual` CLI lets user see what's needed, provide input, confirm completion, and resume
- Planner generates `[?]` tasks with instructions when changes involve external services/secrets
- Other non-blocked changes continue running while one waits for human input

**Non-Goals:**
- TUI redesign — the existing status display gets a new status icon, no structural changes
- Interactive agent-assisted manual task completion (future: `wt-manual help` launching a mini Claude session)
- Task-level dependency graph within tasks.md (section ordering is sufficient)
- Centralized secret store across worktrees (per-worktree .env files are sufficient for now)
- Validation of user-provided inputs beyond basic format hints

## Decisions

### D1: `[?]` checkbox syntax for manual tasks

**Decision**: Use `- [?] task description` as the markdown syntax.

**Rationale**: Follows the existing `[ ]` / `[x]` convention naturally. `?` semantically means "needs human answer". Minimal parser change (one regex). Renders visibly different in markdown viewers.

**Alternatives rejected**:
- `[manual]` tag after `[ ]` — ambiguous, Ralph would still try to execute the `[ ]` task
- Emoji prefix (`🧑`) — not grep-friendly, encoding issues in bash
- Separate `manual-tasks.md` file — fragments the task model, planner needs to know about two files

### D2: Section-level blocking (not task-level dependency)

**Decision**: Manual tasks block subsequent tasks *within the same section*. Tasks in other sections can proceed independently.

**Rationale**: tasks.md sections already represent logical phases. Adding explicit `[after:3.3]` dependency tags adds complexity for little gain — the planner already groups related tasks in sections. If task 3.3 is `[?]` and 3.4 depends on it, they're in the same section by design.

### D3: `waiting:human` as a wt-loop status (not a done_criteria)

**Decision**: Add `waiting:human` as a new loop status value alongside `running|done|stalled|stuck|stopped`. Detection happens in the stall detection block, not in `check_done()`.

**Rationale**: `waiting:human` is not a "done criteria" — it's a runtime condition. The done criteria is still `tasks` (all checkboxes resolved). The detection point is when Ralph would otherwise stall: no commits, no progress, but `[?]` tasks exist → `waiting:human` instead of incrementing stall_count.

**Implementation**: After the stall detection block (line ~884), before incrementing stall_count:
```
if [?] tasks exist in tasks.md:
    status = "waiting:human"
    write manual task info to loop-state.json
    exit 0
else:
    stall_count++  (existing behavior)
```

### D4: Manual task info in loop-state.json

**Decision**: When entering `waiting:human`, write structured info to loop-state.json:
```json
{
  "status": "waiting:human",
  "manual_tasks": [
    {
      "id": "3.3",
      "description": "Configure Stripe API keys",
      "type": "input",
      "input_key": "STRIPE_SECRET_KEY"
    }
  ],
  "waiting_since": "2026-02-28T..."
}
```

**Rationale**: The orchestrator can read this without parsing tasks.md itself. The `wt-manual` CLI reads it too. Single source of truth for what's pending.

### D5: `wt-manual` as standalone CLI (not a Claude skill)

**Decision**: `bin/wt-manual` is a bash script, not a Claude Code skill.

**Rationale**: Manual tasks are resolved by the *user*, not by Claude. A skill would require an active Claude session. The CLI works from any terminal — the user might be monitoring orchestration in one terminal and running `wt-manual` in another.

Subcommands:
- `wt-manual list` — show all changes with pending manual tasks
- `wt-manual show <change>` — detailed instructions for a specific change
- `wt-manual input <change> <KEY> <value>` — provide a value (written to worktree's `.env.local`)
- `wt-manual done <change> <task-id>` — mark a confirm-type task as complete
- `wt-manual resume <change>` — resume the Ralph loop after manual tasks are resolved

### D6: Orchestrator poll_change handling

**Decision**: Add `waiting:human` case to poll_change() (alongside done/running/stalled/stuck):
- Do NOT increment stall_count
- Do NOT auto-resume
- Update change status to `"waiting:human"` in orchestration-state.json
- Log prominently with manual task summary
- Continue dispatching/polling other changes normally

### D7: `### Manual:` instruction format in tasks.md

**Decision**: Instructions for manual tasks are inline in tasks.md under `### Manual: <task-id>` headers:
```markdown
- [?] 3.3 Configure Stripe API keys [input:STRIPE_SECRET_KEY]

### Manual: 3.3 — Configure Stripe API Keys

**What to do:**
1. Go to https://dashboard.stripe.com/apikeys
2. Copy the Secret key

**Input:** STRIPE_SECRET_KEY
**Format:** sk_test_... or sk_live_...
**Target:** .env.local
```

**Rationale**: Keeps everything in one file. The planner generates tasks.md anyway — adding instruction sections is natural. `wt-manual show` parses these sections for display.

### D8: Input storage in .env.local

**Decision**: Secret inputs are written to `<worktree>/.env.local`. Non-secret inputs (confirmations, choices) are recorded by marking the task `[x]` in tasks.md.

**Rationale**: `.env.local` is the standard convention for local secrets (gitignored by default). Per-worktree storage avoids cross-contamination. After merge, the user copies secrets to the main project's .env — this is already standard practice.

## Risks / Trade-offs

### R1: Claude might not respect `[?]` tasks
Ralph (Claude) could still attempt to complete `[?]` tasks by guessing values. **Mitigation**: The prompt builder should include an instruction: "Tasks marked `[?]` require human action — do NOT attempt to complete them. Skip them and work on remaining `[ ]` tasks."

### R2: Planner may not generate `[?]` tasks consistently
The planner LLM may forget to mark external-dependency tasks as manual. **Mitigation**: Add explicit examples in the planner prompt. Plan-review skill checks for common patterns (API keys, external service setup) that should be `[?]`.

### R3: Section-level blocking may be too coarse
A `[?]` task in section 3 blocks all of section 3, even if some later tasks in that section don't depend on it. **Acceptable**: The planner should group dependent tasks together. If this becomes a problem, task-level `[after:X.Y]` tags can be added later without breaking changes.

### R4: .env.local doesn't persist across worktrees
When a change merges and a new worktree needs the same secret, the user must provide it again. **Acceptable for now**: This is the standard .env workflow. A project-level secret store can be added as a future enhancement.
