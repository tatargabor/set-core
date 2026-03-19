## 1. CLI: Forget Operations

- [x] 1.1 Add `cmd_forget` function to `bin/set-memory` — single memory delete by ID (`m.forget(memory_id)`)
- [x] 1.2 Add `forget --all --confirm` variant (`m.forget_all()`) — reject without `--confirm`
- [x] 1.3 Add `forget --older-than <days>` variant (`m.forget_by_age(days)`)
- [x] 1.4 Add `forget --tags <t1,t2>` variant (`m.forget_by_tags(tags)`)
- [x] 1.5 Add `forget --pattern <regex>` variant (`m.forget_by_pattern(pattern)`)

## 2. CLI: Enhanced Recall and List

- [x] 2.1 Add `--mode` parameter to `cmd_recall` — pass `mode=` to `m.recall()` (default: omit for backwards compat)
- [x] 2.2 Add `--tags` parameter to `cmd_recall` — pass `tags=` to `m.recall()` for tag-based filtering
- [x] 2.3 Add `--type` and `--limit` parameters to `cmd_list` — pass to `m.list_memories(limit=, memory_type=)`

## 3. CLI: Introspection Commands

- [x] 3.1 Add `cmd_context` function — `m.context_summary()` with optional topic argument
- [x] 3.2 Add `cmd_brain` function — `m.brain_state()` JSON output
- [x] 3.3 Add `cmd_get` function — `m.get_memory(memory_id)` single memory retrieval

## 4. CLI: Maintenance Commands

- [x] 4.1 Add `--index` flag to `cmd_health` — `m.index_health()` JSON output
- [x] 4.2 Add `cmd_repair` function — `m.repair_index()` JSON output

## 5. CLI: Usage and Dispatch

- [x] 5.1 Update `usage()` function with all new commands grouped by category (Forget, Introspection, Maintenance, Enhanced options)
- [x] 5.2 Update `main()` case dispatch to route new commands (forget, context, brain, get, repair)

## 6. SKILL.md: Invalid Type Cleanup

- [x] 6.1 Fix `openspec-apply-change/SKILL.md` Step 7: `--type Observation` → `--type Learning`, `--type Event` → `--type Context`
- [x] 6.2 Fix `openspec-archive-change/SKILL.md` Step 7: `--type Event` → `--type Context`
- [x] 6.3 Fix `openspec-explore/SKILL.md`: remove `Observation` from type option lists → `<Decision|Learning|Context>`
- [x] 6.4 Fix `openspec-continue-change/SKILL.md`: remove `Observation` from type option lists → `<Decision|Learning|Context>`
- [x] 6.5 Fix `openspec-ff-change/SKILL.md`: remove `Observation` from type option lists → `<Decision|Learning|Context>`

## 7. SKILL.md: Structured Tags Migration

- [x] 7.1 Update `openspec-apply-change/SKILL.md` — recall and remember tags: `repo,<change-name>,error` → `change:<name>,phase:apply,source:agent,error` (and similar for all tag instances)
- [x] 7.2 Update `openspec-archive-change/SKILL.md` — remember tags: `repo,<change-name>,schema` → `change:<name>,phase:archive,source:agent,<topic>`
- [x] 7.3 Update `openspec-continue-change/SKILL.md` — mid-flow tags: `repo,<change-name>,<topic>` → `change:<name>,phase:continue,source:user,<topic>`
- [x] 7.4 Update `openspec-ff-change/SKILL.md` — mid-flow tags: `repo,<change-name>,<topic>` → `change:<name>,phase:ff,source:user,<topic>`
- [x] 7.5 Update `openspec-explore/SKILL.md` — remember tags: `<topic>,<relevant-keywords>` → `change:<topic>,phase:explore,source:user,<keywords>`

## 8. SKILL.md: Enhanced Recall in Hooks

- [x] 8.1 Update `openspec-continue-change/SKILL.md` recall: add `--mode hybrid --tags change:<name>`
- [x] 8.2 Update `openspec-ff-change/SKILL.md` recall: add `--mode hybrid --tags change:<name>`
- [x] 8.3 Update `openspec-apply-change/SKILL.md` recall: add `--mode hybrid --tags change:<name>`
- [x] 8.4 Update `openspec-explore/SKILL.md` recall: add `--mode hybrid` (no `--tags` — free exploration)
- [x] 8.5 Update `openspec-new-change/SKILL.md` recall: add `--mode hybrid`

## 9. SKILL.md: New Memory Hooks (Verify + Sync-specs)

- [x] 9.1 Add recall hook to `openspec-verify-change/SKILL.md` — before verification: `set-memory recall "<change-name> verification issues" --limit 5 --mode hybrid --tags change:<name>`
- [x] 9.2 Add remember hook to `openspec-verify-change/SKILL.md` — after verification: save problems as Learning, patterns as Learning
- [x] 9.3 Add remember hook to `openspec-sync-specs/SKILL.md` — save merge decisions as Decision when conflicts are resolved

## 10. SKILL.md: Agent Self-Reflection Steps

- [x] 10.1 Add self-reflection step to `openspec-continue-change/SKILL.md` — session-end agent review, save insights with `source:agent`, confirm `[Agent insights saved: N items]`
- [x] 10.2 Add self-reflection step to `openspec-ff-change/SKILL.md` — session-end agent review, save insights with `source:agent`
- [x] 10.3 Add self-reflection step to `openspec-explore/SKILL.md` — session-end agent review, save insights with `source:agent`

## 11. CLAUDE.md: Update Ambient Memory Tags

- [x] 11.1 Update CLAUDE.md "Proactive Memory" section — align ambient save instructions with new structured tag format (`source:user`, appropriate topic tags)

## 12. Documentation

- [x] 12.1 Update `docs/developer-memory.md` — document new CLI commands (forget, context, brain, get, repair), enhanced recall flags, tagging strategy
- [x] 12.2 Update `docs/readme-guide.md` — add new CLI commands to the CLI reference section
- [x] 12.3 Update `README.md` — regenerate memory section with new capabilities
