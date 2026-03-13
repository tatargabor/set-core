## Context

Ralph loop (`wt-loop`) runs Claude Code iteratively to complete tasks. Each iteration invokes Claude in interactive mode (not `-p` print mode), giving it access to skills, MCP tools, hooks, and context calculation. The current approach is sequential: Claude works through tasks one by one within each iteration.

Claude Code has Agent Teams — a built-in feature for spawning autonomous teammate agents that share a task list and communicate via messages. Teams work within a single Claude session (no separate processes). Key tools: TeamCreate, Agent (with team_name), SendMessage, TaskCreate/TaskUpdate/TaskList, TeamDelete.

Previous attempt (2026-03-13) tried Agent Teams at the orchestrator/bash level, spawning subagents via `-p` mode. This failed because `-p` mode subagents lack skills, MCP tools, and `.claude/` context. That approach was fundamentally wrong — it tried to replace the orchestration layer.

This change takes the opposite approach: modify only the **prompt** to teach Claude how to use teams **within** an iteration. All existing infrastructure (watchdog, budget, state machine, token tracking) stays untouched.

## Goals / Non-Goals

**Goals:**
- Enable Claude to parallelize independent tasks within a Ralph iteration using Agent Teams
- Provide clear prompt guidance on when teams help vs when they hurt
- Track team usage metrics for future optimization
- Keep it opt-in (`--team` flag) so default behavior is unchanged

**Non-Goals:**
- NOT changing the orchestration layer (dispatcher, monitor, verifier, merger)
- NOT replacing the watchdog or any existing stall detection
- NOT adding inter-worktree team coordination (teams stay within one worktree)
- NOT making teams mandatory — Claude decides per-iteration whether to use them
- NOT supporting teams in resumed sessions (fresh session per team iteration)

## Decisions

### D1: Prompt injection vs engine modification
**Decision:** Modify `build_prompt()` to append team instructions when `team_mode=true`.
**Rationale:** The Ralph engine is bash — it can't meaningfully orchestrate Claude teams. But Claude in interactive mode can. By injecting team knowledge into the prompt, Claude uses teams naturally. The engine stays simple.
**Alternative considered:** Engine-level team management via bash (previous attempt) — rejected due to `-p` mode limitations.

### D2: Opt-in via --team flag
**Decision:** Team mode is opt-in, stored in loop-state.json as `team_mode: bool`.
**Rationale:** Teams add complexity and token cost. Not all tasks benefit from parallelization. Users should explicitly opt in. Default behavior must remain unchanged.
**Alternative considered:** Auto-detect based on task count — rejected as too magic, hard to debug.

### D3: Team lead = Claude session, teammates = Agent tool subagents
**Decision:** The main Claude session acts as team lead. Teammates are spawned via `Agent` tool with `subagent_type: "general-purpose"` and `mode: "bypassPermissions"`.
**Rationale:** The Agent tool spawns full-capability subagents in the same interactive mode context. Using `bypassPermissions` lets teammates write files without permission prompts. The `general-purpose` type gives full tool access including Edit, Write, Bash.
**Alternative considered:** Using `isolation: "worktree"` for each teammate — rejected because teammates need to modify the same worktree's files, not isolated copies.

### D4: Single commit by team lead after all teammates finish
**Decision:** Only the team lead creates git commits. Teammates make file changes but don't commit.
**Rationale:** Multiple teammates committing simultaneously causes race conditions and messy git history. A single commit after all work is done gives clean history and lets the lead resolve any conflicts.

### D5: Team instructions as a prompt block, not a separate file
**Decision:** The team instructions text lives as a heredoc/string in `prompt.sh`, not as a separate file.
**Rationale:** Keeps it co-located with the rest of the prompt building logic. It's ~40-60 lines of instruction text. A separate file would add indirection for minimal benefit.
**Alternative considered:** `.claude/team-instructions.md` template file — rejected as over-engineering for a prompt block.

### D6: Metrics via iteration state, not separate tracking
**Decision:** Add `team_spawned`, `teammates_count`, `team_tasks_parallel` fields to each iteration record in loop-state.json.
**Rationale:** Iteration records already track tokens, commits, timeouts. Team metrics fit naturally. No new files or data stores needed.
**Implementation note:** These fields are aspirational — Claude reports team usage in its output, and the engine parses them post-iteration from the log file or a structured output mechanism. For v1, we rely on the iteration log containing team-related output.

### D7: Cleanup via prompt instructions, not engine hooks
**Decision:** The prompt instructs Claude to call TeamDelete and send shutdown_request before exiting. The engine does NOT attempt to clean up teams via bash.
**Rationale:** Teams are a Claude-level concept (in-process). The bash engine can't interact with Claude's internal team state. By putting cleanup in the prompt, Claude handles it naturally. The existing `cleanup_on_exit` trap handles process-level cleanup (killing child processes) if things go wrong.

## Risks / Trade-offs

- **[Token cost increase]** Teams spawn additional agents, each consuming tokens → Mitigation: Prompt includes threshold (3+ tasks minimum) and Claude decides whether parallelization is worthwhile. Budget enforcement still applies.
- **[File conflicts between teammates]** Two teammates editing the same file → Mitigation: Prompt warns against parallelizing tasks that share files. Team lead reviews combined changes before committing.
- **[Prompt ignored]** Claude may not follow team instructions consistently → Mitigation: Instructions are clear and use the existing pattern of "YOUR TASK (MANDATORY)". Opt-in means only users who want teams enable it. Sequential fallback always works.
- **[Orphan teams on timeout]** If iteration times out mid-team, team state may linger → Mitigation: Next iteration prompt includes orphan detection. Process-level cleanup kills child agents.
- **[Stall detection interference]** Team work may look like "no commits" to the engine (commits happen after team finishes) → Mitigation: Teams complete within a single iteration. The existing `has_artifact_progress` check detects modified files even without commits.

## Open Questions

- Q1: Should we cap the number of teammates? (e.g., max 3) — Tentatively yes, to bound token cost. Include in prompt as guidance.
- Q2: How to extract team metrics from Claude output? — v1: parse iteration log for TeamCreate/TeamDelete patterns. v2: structured output to a metrics file.
