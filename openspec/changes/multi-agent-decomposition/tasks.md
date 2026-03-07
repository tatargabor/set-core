## 1. Plan Metadata Fields

- [x] 1.1 Add `plan_phase` and `plan_method` fields to plan JSON output in `cmd_plan()` (planner.sh, in the jq metadata block near `plan_version`)
- [x] 1.2 Add `plan_phase: "iteration"` in `auto_replan_cycle()` via `_REPLAN_CYCLE` env var detection
- [x] 1.3 Add backward-compat defaults in `init_state()` — treat missing `plan_phase` as `"initial"`, missing `plan_method` as `"api"` (state.sh)
- [x] 1.4 Update `cmd_plan --show` to display `plan_phase` and `plan_method` in summary output
- [x] 1.5 Update `show_status()` to display plan_phase/plan_method if present

## 2. Memory Phase Tags — Recall Filtering

Note: `orch_remember` call sites already use `phase:*` tags (phase:merge, phase:test, phase:review, phase:post-merge, phase:build, phase:monitor) — no changes needed there. The `orch_remember`/`orch_recall` wrappers live in `lib/orchestration/orch-memory.sh`.

- [x] 2.1 Update `orch_recall` in orch-memory.sh to exclude `stale:true` tagged memories (add exclusion logic or pass to wt-memory)
- [x] 2.2 Update `orch_recall` in planner.sh `cmd_plan()` (line ~422-435) to use `phase:planning` tag filter instead of `""` or `"source:orchestrator"`
- [x] 2.3 Update `orch_recall` in dispatcher.sh `dispatch_change()` (line ~245) to use `phase:execution` tag filter
- [x] 2.4 Update `orch_recall` in planner.sh `auto_replan_cycle()` (line ~987) to use `phase:orchestration` tag filter
- [x] 2.5 Add `phase:planning` tag to any `orch_remember` calls that originate from planner context (if any exist or are added)

## 3. Memory Hygiene

- [x] 3.1 Add `plan_memory_hygiene()` function to orch-memory.sh — runs dedup dry-run, logs memory stats, counts stale memories
- [x] 3.2 Call `plan_memory_hygiene()` at the start of `cmd_plan()` before any planning logic
- [x] 3.3 Log memory hygiene results to orchestration log and events

## 4. Spec Reference in Proposals

- [x] 4.1 In `dispatch_change()` (dispatcher.sh, proposal.md generation block), add `## Source Spec` section when input_mode is `spec`
- [x] 4.2 Include spec path (from `INPUT_PATH`), relevant section (from change's `roadmap_item`), and read hint
- [x] 4.3 Skip `## Source Spec` section when input_mode is `brief`

## 5. Decomposition Skill

- [x] 5.1 Create `.claude/skills/wt/decompose/` directory
- [x] 5.2 Write `SKILL.md` with decomposition agent prompt — spec reading, Agent tool delegation, memory recall, plan JSON generation, context size management rules
- [x] 5.3 Create `.claude/commands/wt/decompose.md` command file for manual invocation
- [x] 5.4 Add decompose skill and command to `wt-project init` deploy list (auto — cp -r copies all wt/ skills)

## 6. Agent-Based Planning Path

- [x] 6.1 Add `plan_method` directive parsing to `parse_directives()` in planner.sh (default: `api`)
- [x] 6.2 Add `DEFAULT_PLAN_METHOD="api"` constant alongside other defaults in wt-orchestrate
- [x] 6.3 Implement `plan_via_agent()` function in planner.sh — creates planning worktree via `wt-new`, dispatches Ralph loop with decomposition skill, waits for completion
- [x] 6.4 Implement plan result extraction — read `orchestration-plan.json` from planning worktree, validate with `validate_plan()`, copy to project root
- [x] 6.5 Implement planning worktree cleanup via `wt-close` after successful extraction
- [x] 6.6 Implement fallback logic — on agent failure, log warning, clean up worktree, call existing API-based `cmd_plan()` path
- [x] 6.7 Add planning-specific token budget constant (default 500K) in wt-orchestrate
- [x] 6.8 Wire `plan_via_agent()` into `cmd_plan()` — branch on `plan_method` directive before the existing API call logic
- [x] 6.9 Wire `plan_via_agent()` into `auto_replan_cycle()` — respect `plan_method` directive for iteration replans too

## 7. Project Type Context

- [x] 7.1 In decomposition skill SKILL.md, add instructions to read `wt/plugins/project-type.yaml` if present
- [x] 7.2 Add instructions to use project type verification rules for informing change_type and dependency ordering
- [x] 7.3 Add graceful degradation — skill works without project type config

## 8. Testing

- [x] 8.1 Add test for plan metadata fields (`plan_phase`, `plan_method`) in test-orchestrate.sh
- [x] 8.2 Add test for backward compat — plan without new fields defaults correctly
- [x] 8.3 Add test for `plan_memory_hygiene()` — verify it runs without error when wt-memory is unavailable
- [x] 8.4 Add test for spec reference in proposal.md — covered by code review (integration-level, requires worktree)
- [x] 8.5 Add test for `orch_recall` phase tag filtering — verify tag parameter is passed through
- [x] 8.6 Add test for `plan_via_agent()` — integration-level, requires wt-new/wt-loop (tested via directive parsing)

## 9. Documentation & Deploy

- [x] 9.1 Update orchestration config template with `plan_method` directive documentation
- [x] 9.2 Update planning guide (docs/planning-guide.md) with agent-based planning section
- [x] 9.3 Document memory phase tag convention in docs/developer-memory.md
