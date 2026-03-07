## Context

The orchestration planner (`lib/orchestration/planner.sh`) currently builds a single large prompt containing spec content, memory, requirements, project knowledge, and test infrastructure context, then makes one Claude API call to decompose it into changes. This works for simple specs but has fundamental limitations:

- **No codebase awareness**: The planner never reads actual code — it decomposes based on spec text alone
- **No iterative refinement**: One-shot decomposition with no ability to explore and adjust
- **Context overflow**: Large specs get summarized (lossy) to fit the prompt
- **No memory filtering**: All recalled memories enter the prompt regardless of relevance to planning vs execution
- **No spec access during execution**: Worker agents only see proposal.md, cannot consult the original spec

The dispatch and execution pipeline (worktree creation, Ralph loops, monitoring, verification, merging) works well and should remain unchanged. Only the planning phase needs to become agent-based.

## Goals / Non-Goals

**Goals:**
- Agent-based decomposition that can explore codebase before planning
- Phase-tagged memory to prevent cross-contamination between planning and execution
- Spec reference mechanism for worker agents
- Backward-compatible plan format — existing dispatch pipeline unchanged
- Both API and agent planning methods available (directive-controlled)

**Non-Goals:**
- Replacing the existing API-based planning (it stays as fallback/default for simple cases)
- Multi-agent teams (TeammateTool) — too experimental, we use Agent tool sub-agents instead
- Changing the execution pipeline (dispatch, Ralph loops, monitoring, merging)
- Implementing `plan_type` (decomposition/spike/hotfix) — deferred until practice shows need

## Decisions

### D1: Planning runs in a worktree with Ralph loop

**Choice:** Same infrastructure as change execution — worktree + `wt-loop`
**Over:** Agent tool subprocess in main session, or Claude Code Agent Teams

**Rationale:**
- Sentinel can monitor planning the same way it monitors changes
- Crash recovery works the same way (event-based state reconstruction)
- Token tracking works the same way
- No new infrastructure needed

**Implementation:**
- `cmd_plan()` checks directive `plan_method: agent|api` (default: `api` for backward compat)
- When `agent`: creates a planning worktree (`wt-planning-v{N}`), dispatches Ralph with decomposition skill
- Ralph output: writes `orchestration-plan.json` to a known path in the worktree
- `cmd_plan()` copies the result back to project root
- Planning worktree is cleaned up after successful plan extraction

### D2: Single planning agent with Agent tool sub-agents

**Choice:** One Ralph loop instance that uses Claude's built-in Agent tool for parallel exploration
**Over:** Multiple specialized planning agents coordinated by orchestrator

**Rationale:**
- The Agent tool already supports Explore subagent type (fast codebase search)
- The planning agent can spawn multiple Explore agents in parallel (spec analysis, code scanning, requirements)
- Orchestrator complexity stays minimal — it just dispatches one "planning change"
- Sub-agent context doesn't pollute the main planning context

**Planning agent workflow:**
1. Read spec file + project type config
2. Agent tool (Explore): scan codebase for relevant patterns, existing implementations
3. Agent tool (Explore): analyze requirements registry
4. Memory recall with `phase:planning` tag filter
5. Synthesize into `orchestration-plan.json`
6. Write output file

### D3: Plan metadata fields

**Choice:** Add `plan_phase` and `plan_method` to `orchestration-plan.json`
**Over:** Separate file types or naming conventions

**Fields:**
```json
{
  "plan_version": 2,
  "plan_phase": "initial",
  "plan_method": "agent",
  "planning_worktree": "wt-planning-v2",
  ...
}
```

- `plan_phase`: `"initial"` (first decomposition from spec) or `"iteration"` (replan after completed changes)
- `plan_method`: `"api"` (current single LLM call) or `"agent"` (worktree + Ralph)
- `planning_worktree`: name of the worktree used (agent method only, for debugging)
- All fields optional — existing plans without these fields treated as `plan_phase: "initial"`, `plan_method: "api"`

### D4: Spec reference in proposal.md

**Choice:** Add `## Source Spec` section to proposal.md with path and section reference
**Over:** Copying spec to worktree, or relying on git access

**Format:**
```markdown
## Source Spec
- Path: `wt/orchestration/specs/v12-minicrm.md`
- Section: `### 3.2 Contact Management`
- Full spec available via: `cat wt/orchestration/specs/v12-minicrm.md`
```

**Rationale:**
- Worker agent can read the file directly (it's in the worktree via git)
- No duplication, always current
- Agent decides when to consult — not forced into context

### D5: Memory phase tags

**Choice:** Tag-based memory segmentation with phase-filtered recall
**Over:** Separate memory stores per phase, or no filtering

**Tag convention:**
| Tag | Source | Used in |
|-----|--------|---------|
| `phase:planning` | Decomposition learnings | Decomposition recall |
| `phase:execution` | Ralph loop learnings | Worker dispatch |
| `phase:verification` | Verifier/merge learnings | Verifier prompt |
| `phase:orchestration` | Orchestrator operational | Iteration replan |
| `scope:<change-name>` | Change-specific | Dispatch, resume |

**Recall filtering:**
```bash
# Current (unfiltered):
orch_recall "$scope" 3 ""

# New (phase-filtered):
orch_recall "$scope" 3 "phase:planning"
```

The `orch_recall` function already accepts a tags parameter (3rd arg) — it just needs to be used consistently.

### D6: Memory hygiene before decomposition

**Choice:** Lightweight pre-decomposition cleanup step
**Over:** No cleanup (current), or aggressive pruning

**Steps:**
1. Run `wt-memory dedup --dry-run` — log count, don't auto-delete
2. Check for stale memories (tagged `stale:true`) — exclude from recall
3. Log memory stats for the run log

**Rationale:**
- Non-destructive by default (dry-run only)
- Prevents known-bad memories from influencing planning
- Stats give visibility into memory health per orchestration run

### D7: Decomposition skill design

**Choice:** New `/wt:decompose` skill in `.claude/skills/wt/decompose/`
**Over:** Embedding the prompt in bash, or reusing existing skills

**The skill prompt instructs the agent to:**
1. Read the spec file (path from env or argument)
2. Read `wt/plugins/project-type.yaml` if exists — understand verification rules, conventions
3. Read `wt/knowledge/project-knowledge.yaml` if exists — cross-cutting files, features
4. Scan `wt/requirements/*.yaml` — active requirements
5. Use Agent tool (Explore) to scan codebase for existing implementations matching spec topics
6. Recall memories with `phase:planning` tag
7. List existing OpenSpec specs and active changes to avoid duplication
8. Generate `orchestration-plan.json` following the existing schema
9. Apply the same validation rules currently in `validate_plan()`

**Context size management:**
- Skill prompt explicitly limits what to load: "Do NOT read entire spec into context if >200 lines — use Agent tool to analyze sections"
- Sub-agents return summaries, not full file contents
- Project knowledge and requirements are read directly (small files)

## Risks / Trade-offs

**[Agent planning costs more tokens]** → Mitigated by: directive control (`plan_method: api` stays default), token budget for planning worktree (default 500K), simple specs don't need agent planning

**[Planning worktree adds latency]** → Mitigated by: only used when `plan_method: agent`, worktree creation is ~5s, cleanup is automatic. For iteration replans the worktree already exists context.

**[Memory tag convention requires adoption]** → Mitigated by: existing `orch_remember` and `orch_recall` wrappers centralize all orchestrator memory operations — only these functions need tag injection. Worker agents get tags via hook configuration.

**[Agent may produce invalid plan JSON]** → Mitigated by: same `validate_plan()` runs on agent output. If validation fails, orchestrator falls back to API method with warning.

## Migration Plan

1. **Phase 1 — Metadata & tags** (no behavior change): Add `plan_phase`/`plan_method` fields to plan output. Add phase tags to `orch_remember`/`orch_recall`. Deploy memory hygiene step. All backward compatible.

2. **Phase 2 — Decomposition skill**: Create `/wt:decompose` skill. Test in isolation (manual invocation).

3. **Phase 3 — Agent path integration**: Add `plan_method: agent` directive support to `cmd_plan()`. Planning worktree lifecycle. Result extraction.

4. **Phase 4 — Spec reference**: Add `## Source Spec` to proposal.md generation in dispatcher. Deploy to consumer projects.

## Open Questions

1. **Planning worktree cleanup timing** — Immediately after plan extraction, or keep until dispatch completes (for debugging)?
2. **Iteration replan** — Should iteration replans always use agent method, or respect the directive? Initial instinct: respect directive, but iteration context is richer so agent method benefits more.
3. **Fallback behavior** — If agent planning fails (timeout, invalid output), should it auto-fallback to API method silently, or fail and let sentinel handle?
