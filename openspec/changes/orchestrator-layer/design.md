## Context

The wt-tools pipeline has a mature implementation layer: Ralph (wt-loop) autonomously runs Claude sessions, tracks progress via tasks.md, detects stalls, and manages token budgets. OpenSpec skills (ff, apply, verify, archive) handle artifact creation and implementation. Memory persists across sessions. Agent messaging enables cross-worktree coordination.

The gap is between developer intent and execution. Today the developer manually runs `/opsx:ff`, reviews output, runs `/opsx:apply`, monitors Ralph, runs `wt-merge`, and repeats. For projects with a clear functional direction, this human-in-the-loop pattern is the bottleneck.

The existing `detect_next_change_action()` in wt-loop already sequences multiple changes (ff → apply → done) but only within a single worktree. The orchestrator lifts this pattern to the project level: multiple changes, multiple worktrees, dependency ordering, and lifecycle management.

## Goals / Non-Goals

**Goals:**
- Developer expresses intent via a project brief document; system decomposes into changes and executes them
- Changes run through the full OpenSpec pipeline (ff → apply → verify) without human intervention
- Configurable merge policy (eager, checkpoint-gated, manual)
- Mid-flight mutation: pause, resume, replan, replace individual changes
- Human checkpoints with progress summaries at configurable intervals
- GUI dashboard showing dependency graph, change progress, and merge queue

**Non-Goals:**
- Multi-machine orchestration (stays single-machine, multiple worktrees)
- Automatic project brief generation (developer writes and maintains the brief)
- Replacing the existing OpenSpec skill workflow (orchestrator calls the same skills)
- CI/CD integration (orchestrator is local development tooling)
- Cost optimization or automatic model selection

## Decisions

### D1: Bash orchestrator with Claude decomposition calls

The orchestrator (`wt-orchestrate`) is a bash script. It uses Claude only for the decomposition step (brief → change plan) via a single `claude -p` call. All orchestration logic — state tracking, dispatch, monitoring, merge — is deterministic bash.

**Why not a persistent Claude session as orchestrator?** A Claude session would cost tokens continuously while monitoring, could hallucinate actions, and is harder to interrupt/resume. The decomposition step benefits from LLM reasoning; the orchestration loop does not.

**Alternatives considered:**
- Python script: more readable but adds a dependency. Bash aligns with all existing wt-tools.
- Claude Agent SDK: overkill for sequential dispatch + polling. The orchestrator's job is mostly `while true; sleep; check_status`.

### D2: Orchestration state machine

Each change in a plan follows this lifecycle:

```
pending → dispatched → running → [paused] → done
                         ↓                    ↓
                       stalled              merged
                         ↓
                       failed
```

State transitions:
- `pending → dispatched`: orchestrator creates worktree + starts Ralph
- `dispatched → running`: Ralph picks up and begins work
- `running → done`: Ralph reports tasks complete
- `running → stalled`: Ralph detects stall (no commits N iterations)
- `running → paused`: developer or orchestrator pauses via `wt-orchestrate pause`
- `paused → running`: developer resumes via `wt-orchestrate resume`
- `done → merged`: tests pass + merge policy satisfied → `wt-merge` runs
- `stalled/failed`: orchestrator notifies developer, waits for intervention

The orchestrator polls `loop-state.json` per worktree every 30 seconds. No new IPC mechanism needed — Ralph already writes state to this file.

### D3: Project brief format

Extends `openspec/project.md` into `openspec/project-brief.md`. Backwards-compatible — all existing project.md sections remain valid. New sections:

```markdown
## Feature Roadmap
### Done
- [description of completed capability]

### Next
- [description]: [optional details, constraints, dependencies]
- [description]: [optional details]

### Ideas
- [vague concept for future consideration]

## Orchestrator Directives
- max_parallel: 3
- merge_policy: checkpoint    # eager | checkpoint | manual
- checkpoint_every: 2         # pause after N changes complete
- test_command: PYTHONPATH=. python -m pytest tests/ -v --tb=short
- notification: desktop       # desktop | gui | none
```

**Why a markdown document, not YAML/JSON?** The brief is primarily written and read by humans. Markdown with a structured "Orchestrator Directives" section (parsed as key-value) gives the best of both worlds.

The `## Next` section is the orchestrator's input. Each bullet becomes a candidate change. The decomposition step refines these into concrete OpenSpec changes with dependency ordering.

### D4: Decomposition via Claude

A single `claude -p` call receives:
1. The project brief (full document)
2. List of existing specs (names + one-line descriptions)
3. List of existing changes (active + recently archived)
4. Memory context (top 5 relevant memories via `wt-memory recall`)

The prompt asks Claude to:
- Parse the "Next" section of the brief
- Propose concrete change names (kebab-case)
- Write a one-paragraph scope for each change
- Define dependencies between changes
- Estimate relative complexity (S/M/L)

Output format: JSON written to `orchestration-plan.json`:

```json
{
  "plan_version": 1,
  "brief_hash": "<sha256 of project-brief.md>",
  "created_at": "2026-02-26T10:00:00Z",
  "changes": [
    {
      "name": "add-user-model",
      "scope": "Create User entity with email, hashed password, timestamps...",
      "complexity": "M",
      "depends_on": [],
      "roadmap_item": "User authentication system"
    },
    {
      "name": "add-auth-middleware",
      "scope": "JWT-based auth middleware...",
      "complexity": "M",
      "depends_on": ["add-user-model"],
      "roadmap_item": "User authentication system"
    }
  ]
}
```

The developer reviews this plan (`wt-orchestrate plan --show`) and approves (`wt-orchestrate start`). No auto-start.

### D5: Change dispatch and execution

For each change ready to run (dependencies satisfied, under max_parallel limit):

1. `wt-new <change-name>` — create worktree
2. Copy the change scope into the worktree as a seed file (`openspec/changes/<name>/brief-context.md`)
3. `wt-loop start --max 30 --done openspec` — start Ralph

Ralph's existing `detect_next_change_action()` handles the ff → apply sequencing within the worktree. No modifications needed for this part.

The orchestrator's monitor loop:
```bash
while not all_done; do
    for each active_change:
        status = read loop-state.json
        if status == "done":
            run_tests(change)
            if tests_pass && merge_policy_allows:
                wt-merge(change)
                unlock_dependents(change)
            elif tests_fail:
                mark_failed(change)
                notify_developer(change)
        elif status == "stalled" || status == "stuck":
            notify_developer(change)

    dispatch_ready_changes()  # deps met + under parallel limit

    if checkpoint_reached():
        send_summary()
        wait_for_approval()

    sleep 30
done
```

### D6: Mid-flight mutation

Three mutation operations:

**Pause:** `wt-orchestrate pause <change>` or `wt-orchestrate pause --all`
- Sends SIGTERM to the Ralph terminal PID (read from `.claude/ralph-terminal.pid`)
- Ralph's existing trap handler records state and sets status to "stopped"
- Orchestrator marks change as "paused" in its own state
- No new mechanism needed — Ralph already handles graceful SIGTERM

**Resume:** `wt-orchestrate resume <change>`
- Restarts Ralph in the existing worktree: `cd <worktree> && wt-loop start --max 30 --done openspec`
- Ralph picks up from where it left off (tasks.md tracks progress)

**Replan:** `wt-orchestrate replan`
- Reads current state (which changes are done/active/pending)
- Reads updated project-brief.md
- Calls Claude with both: "Given this state, what changes are needed now?"
- Claude can: keep existing pending changes, add new ones, mark some as unnecessary
- Developer approves the updated plan
- Active changes continue unless explicitly paused

### D7: Auto-merge pipeline

Merge policy is configured in the project brief's `Orchestrator Directives`:

| Policy | Behavior |
|--------|----------|
| `eager` | Auto-merge immediately when change is done + tests pass |
| `checkpoint` | Queue merges, execute at next human checkpoint |
| `manual` | Never auto-merge; developer runs `wt-merge` manually |

Default: `checkpoint`

Pre-merge checks (always, regardless of policy):
1. All tasks in tasks.md are checked (`- [x]`)
2. `test_command` from directives passes (if configured)
3. No merge conflicts with target branch (dry-run merge check)

If merge conflicts exist, the change is marked as "merge-blocked" and the developer is notified.

After merge:
1. Close worktree (`wt-close <change>`)
2. Update orchestration state
3. Check if any pending changes are now unblocked
4. Dispatch newly unblocked changes

### D8: Human checkpoint system

Checkpoint triggers (configurable):
- Every N changes complete (`checkpoint_every: 2`)
- On stall/failure (always — not configurable)
- On plan completion (always)

Checkpoint delivery:
1. **Desktop notification** via `notify-send` (existing pattern from wt-loop)
2. **Summary file** written to `orchestration-summary.md` (human-readable)
3. **GUI integration** — wt-control reads orchestration-state.json (same pattern as Ralph status)

Summary contents:
- Completed changes (with test results)
- Active changes (iteration progress, token usage)
- Pending changes (what's next)
- Merge queue (what's waiting for approval)
- Total token consumption

Approval: `wt-orchestrate approve` or `wt-orchestrate approve --merge` (approve + flush merge queue). The orchestrator blocks (polling state file) until approval arrives.

### D9: GUI orchestrator view

Extension to the existing wt-control GUI, not a separate application. New panel/tab showing:

- **Dependency graph** — visual DAG of changes with status colors (green=done, blue=running, gray=pending, red=failed)
- **Change cards** — per-change detail: iteration count, task progress, token usage
- **Merge queue** — changes waiting for merge with approve/reject buttons
- **Timeline** — horizontal timeline showing completed changes and projected completion

Data source: `orchestration-state.json` + per-worktree `loop-state.json` (already read by GUI for Ralph status).

This is a Phase 2 deliverable — the CLI orchestrator works standalone without GUI support.

### D10: Pre-create proposal.md instead of brief-context.md

The original design called for writing a `brief-context.md` seed file into the worktree. Problem: nobody reads it. When Ralph runs `/opsx:ff`, the ff skill has no mechanism to consume an arbitrary context file — it only looks at existing OpenSpec artifacts.

**Fix:** The orchestrator pre-creates `proposal.md` from the plan's scope text instead. This slots into the existing OpenSpec artifact graph:

```
Orchestrator creates:   proposal.md (from plan scope)
Ralph ff detects:       proposal DONE → skip → create design, specs, tasks
Ralph apply detects:    tasks.md exists → implement
```

The proposal is minimal (generated from the scope paragraph), but sufficient for ff to produce design and specs. If the decomposition scope is detailed enough, the ff agent has good context.

### D11: Verify step in orchestrator pipeline

The pipeline is ff → apply → **verify** → done. Ralph's `detect_next_change_action()` only knows ff and apply. Rather than modifying Ralph (complex, affects all users), the orchestrator runs verify externally after Ralph reports "done":

```
Ralph done → orchestrator runs test_command → orchestrator runs /opsx:verify via claude -p → merge
```

The verify step is a single `claude -p "Run /opsx:verify <change>" --max-turns 5` call. If verify finds issues, the orchestrator can restart Ralph to fix them (up to 1 retry).

### D12: Orchestrator cleanup trap

The orchestrator monitor loop needs its own signal handling. On SIGTERM/SIGINT:

1. Update orchestration-state.json status to "stopped"
2. Optionally pause all running Ralph loops (configurable: `pause_on_exit: true`)
3. Log the stop event

Ralph loops continue running independently if not paused — they have their own stall detection and will eventually stop. This is by design: the orchestrator is a coordinator, not a supervisor.

### D13: Orchestrator logging

All orchestrator output is logged to `.claude/orchestration.log` (same directory as other wt-tools state files). Log entries include:

- Timestamps for all state transitions
- Dispatch events (which change, which worktree)
- Monitor poll results (status changes only, not every poll)
- Merge events (success/conflict)
- Checkpoint events
- Errors and notifications sent

Log rotation: truncate at 100KB on startup (keep last 50KB).

### D14: Token budget directive

New directive in project brief:

```
- token_budget: 500000    # total token budget across all changes
```

The orchestrator tracks cumulative tokens from all `loop-state.json` files. When total exceeds the budget:
1. Trigger a checkpoint (regardless of checkpoint_every)
2. Include token breakdown in summary
3. Wait for approval before continuing

Default: no limit (0 = unlimited). This is a soft limit — it pauses for approval rather than killing running loops.

## Risks / Trade-offs

**[Decomposition quality]** Claude may produce poor change decomposition (too granular, wrong dependencies, missing changes).
→ Mitigation: Human approval gate before execution. The replan command allows correction. Memory accumulates decomposition patterns over time.

**[Merge conflicts between parallel changes]** Two parallel changes may conflict when merging to main.
→ Mitigation: Pre-merge dry-run check. If conflict detected, second change is queued and developer is notified. Dependency graph should minimize this by expressing known conflicts.

**[Token cost]** Running multiple Ralph loops in parallel multiplies token consumption.
→ Mitigation: `max_parallel` directive caps concurrency. Token tracking per change (existing wt-loop feature) makes cost visible. Checkpoint summaries include token totals.

**[Stale plan]** Brief changes while orchestrator is running.
→ Mitigation: `replan` command. The orchestrator tracks `brief_hash` and can detect when the brief has changed since the plan was created, displaying a warning.

**[Ralph limitations]** Ralph's stall detection is conservative (2 iterations with no commits). A change that makes progress but doesn't commit will be falsely marked as stalled.
→ Mitigation: Existing artifact-creation detection already helps (creates in wt-loop count as progress). No additional changes needed — this is a known limitation.

**[Complexity]** The orchestrator adds a new layer of abstraction on top of already complex tooling.
→ Mitigation: The orchestrator is optional — all existing manual workflows continue to work. Incremental adoption: start with `wt-orchestrate plan` only (review decomposition), then graduate to `wt-orchestrate start`.

## Testing Strategy

### Parallel execution model

Multiple worktrees run simultaneously, each on its own branch. Key invariants:

- **Worktrees are fully isolated**: separate directories, separate branches, separate `.claude/` state
- **Merges are sequential**: the orchestrator merges one change at a time to main, never concurrently
- **Dependencies enforce ordering**: a change with `depends_on: [X]` does NOT start until X is merged
- **Merge conflicts detected pre-merge**: dry-run `git merge --no-commit --no-ff` + `git merge --abort` before real merge. If conflict → mark "merge-blocked", notify developer.

### Test levels

**Level 1 — Unit tests (bash functions, no Claude calls):**
- `parse_brief`: feed sample project-brief.md, verify extracted Next items and directives
- `parse_directives`: verify defaults for missing keys, warning on invalid values
- `topological_sort`: verify dependency ordering, circular dependency detection
- `update_state` / `get_change_status`: verify JSON read/write roundtrip
- Method: `wt-orchestrate self-test` subcommand that runs assertions internally

**Level 2 — Integration test (plan generation, requires Claude):**
- Create a dummy `project-brief.md` with 3 features in Next section
- Run `wt-orchestrate plan` → verify `orchestration-plan.json` structure
- Verify: change names are kebab-case, dependencies are valid, no circular deps
- Cost: one Claude decomposition call (~5-10k tokens)

**Level 3 — End-to-end (single change through full pipeline):**
- Dummy project with one trivial feature in brief (e.g., "add a hello.txt file")
- `wt-orchestrate start` → Ralph creates worktree, runs ff+apply, completes
- Verify: change goes through pending→dispatched→running→done→merged
- Verify: worktree created, proposal pre-created, tasks checked, merge to main
- Cost: one Ralph session (~20-50k tokens)

**Level 4 — Pilot (real project, multiple features):**
- Real project with 2-3 actual features in brief
- Full parallel execution with dependencies
- Validates: decomposition quality, parallel safety, merge pipeline, checkpoints
- This is the final validation before trusting the orchestrator for production use
