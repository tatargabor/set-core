## 1. Orchestrator Pause

- [x] 1.1 Add `_get_issue_owned_changes(project_path)` helper in `lib/set_orch/engine.py` — reads `.set/issues/registry.json`, returns set of change names with active issues [REQ: orchestrator-issue-pause/REQ-1]
- [x] 1.2 In `resume_stalled_changes` (dispatcher.py), skip changes in issue-owned set with log warning [REQ: orchestrator-issue-pause/REQ-2, REQ-4]
- [x] 1.3 In `execute_merge_queue` (merger.py), skip changes in issue-owned set with log warning [REQ: orchestrator-issue-pause/REQ-3, REQ-4]

## 2. Issue Auto-Resolve

- [x] 2.1 Add `_check_affected_change_merged()` method in `lib/set_orch/issues/manager.py` — reads orchestration-state.json, returns True if affected_change is "merged" [REQ: issue-auto-resolve/REQ-1]
- [x] 2.2 In IssueManager.tick(), before _process(): if affected_change merged → auto-resolve [REQ: issue-auto-resolve/REQ-2, REQ-3]
- [x] 2.3 Auto-resolve calls _mark_source_finding_resolved() [REQ: issue-auto-resolve/REQ-3]
