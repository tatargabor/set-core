## Why

The issue pipeline and orchestrator are blind to each other. In minishop-run5:
- ISS-001 was filed for `auth-navigation` integration-failed
- The orchestrator's own retry_merge_queue resolved the merge conflict and merged auth-navigation
- But ISS-001 stayed stuck at "diagnosed" — nobody told the issue pipeline that the problem was solved
- Meanwhile, the orchestrator could have been competing with the fix agent if it had proceeded to auto-fix

Two problems:
1. **Orchestrator doesn't know** when the issue pipeline is actively fixing a change → may retry/redispatch and interfere
2. **Issue pipeline doesn't know** when the orchestrator resolved the affected change → issues stay stuck

## What Changes

- Add `_get_issue_owned_changes()` helper that reads `.set/issues/registry.json` for active issues
- Orchestrator skips retry/redispatch for changes owned by the issue pipeline (investigating/fixing)
- Issue manager auto-resolves issues whose affected_change reached "merged" in orchestration state
- Issue manager tick checks orchestration-state.json for affected change status

## Capabilities

### New Capabilities
- `orchestrator-issue-pause` — Orchestrator defers to issue pipeline for changes being investigated/fixed
- `issue-auto-resolve` — Issues auto-resolve when orchestrator merges their affected change

## Impact

- `lib/set_orch/engine.py` — pause check before resume_stalled and retry_merge
- `lib/set_orch/issues/manager.py` — auto-resolve check in tick()
