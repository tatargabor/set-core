## Two-Way Sync

```
Orchestrator                          Issue Pipeline
     │                                      │
     │  ① reads registry.json               │
     │  "auth-nav owned by ISS-001"         │
     │  → skip retry/redispatch             │
     │                                      │
     │                          ② reads orchestration-state.json
     │                          "auth-nav: merged"
     │                          → ISS-001 auto-resolved
     │                                      │
```

## Direction 1: Orchestrator → Pause

Helper function `_get_issue_owned_changes(project_path)`:
- Reads `.set/issues/registry.json`
- Returns set of change names where issue state is in {investigating, fixing, awaiting_approval}
- Called from `_resume_stalled_safe` and `_retry_merge_queue_safe`
- Changes in the returned set are skipped (not retried/redispatched)

Lightweight: reads a small JSON file, no LLM calls, no process spawning.

## Direction 2: Issue Pipeline → Auto-Resolve

In `IssueManager.tick()`, before processing each issue:
- If `issue.affected_change` is set and state is active (not resolved/failed)
- Read `orchestration-state.json` from `issue.environment_path`
- If the affected change has status "merged" → auto-resolve the issue

This check runs every tick (~5s) so it catches merges quickly.

## Edge Case: Issue Has No affected_change

Some issues aren't tied to a specific change (e.g., "build broken on main"). These don't auto-resolve — they need the fix pipeline to complete.
