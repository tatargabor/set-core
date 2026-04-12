## ADDED Requirements

### Requirement: Issue ownership self-resolves on change merge
The issue registry SHALL automatically resolve any open issue whose `affected_change` transitions to `merged` (or `skip_merged`), without operator intervention. This prevents the merge queue from being permanently blocked by a `diagnosed` state issue after the underlying fix has landed.

Current behavior (the bug we observed on 2026-04-12 minishop-run-20260412-0103): ephemeral Claude triggers write findings via `set-sentinel-finding add`, each finding creates an `ISS-NNN` issue, and the issue registry transitions through `new → investigating → diagnosed`. The merge queue in `merger.py::execute_merge_queue` skips any change that appears in `_get_issue_owned_changes()`, which returns every change with a non-terminal issue. Since `diagnosed` is non-terminal, the merge queue is locked forever unless someone (a) manually edits `.set/issues/registry.json` to flip the state, or (b) writes a follow-up ephemeral Claude that uses `set-sentinel-finding update` to transition the issue.

The run was unblocked on 2026-04-12 at ~10:18 local time by manually editing three issue states from `diagnosed` to `fixed`. That manual step MUST not be required.

#### Scenario: Change merges while an issue is in `diagnosed` state
- **WHEN** a change `foundation-setup` has an open issue `ISS-001` in state `diagnosed` with `affected_change: "foundation-setup"`
- **WHEN** the merge queue successfully merges `foundation-setup` to main (status transitions to `merged`)
- **THEN** `ISS-001` is automatically transitioned from `diagnosed` to `fixed` by the same `merge_change()` code path that records the successful merge
- **THEN** the audit log records `{"action": "transition:fixed", "from_state": "diagnosed", "to_state": "fixed", "reason": "change_merged_auto_resolve"}`
- **THEN** any future polls of `_get_issue_owned_changes()` no longer return `foundation-setup`

#### Scenario: Change has multiple issues, some still investigating
- **WHEN** a change has `ISS-001` (state=diagnosed) and `ISS-002` (state=investigating) both tagged `affected_change: "foundation-setup"`
- **WHEN** the change merges
- **THEN** both `ISS-001` and `ISS-002` are transitioned to `fixed` atomically
- **THEN** the rationale is that the merge pipeline itself is the ground truth — if gates pass and merge succeeds, every finding attached to that change is implicitly resolved

#### Scenario: Cross-change issues are NOT auto-resolved
- **WHEN** a change `auth-navigation` merges successfully AND an open issue `ISS-042` has `affected_change: "product-catalog"` (a different change)
- **THEN** `ISS-042` remains in its current state
- **THEN** only issues tagged to the merging change are resolved

### Requirement: Auto-resolve is non-blocking best-effort
The auto-resolve step in `merge_change()` SHALL be wrapped in try/except so any failure (unwritable registry, corrupt JSON, file lock contention) logs a WARNING and does NOT prevent the merge from completing.

#### Scenario: Registry file is unwritable during merge
- **WHEN** `merge_change()` completes successfully but the subsequent registry update fails (permission denied, disk full, corrupted JSON)
- **THEN** a WARNING is logged including the change name, issue IDs attempted, and the underlying error
- **THEN** the merge itself remains committed (status = merged, branch merged to main)
- **THEN** the stale `diagnosed` issues remain in the registry and will be re-detected on the next `_get_issue_owned_changes()` call — but they no longer block this change (it's already merged, not in `state.merge_queue`)

### Requirement: Diagnosed-state timeout as safety net
The issue registry SHALL record a `diagnosed_at` timestamp when transitioning into `diagnosed`. If an issue has been in `diagnosed` state for longer than `DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS` (default: 3600 seconds = 1 hour), the orchestration engine's watchdog SHALL log a WARNING and emit an `ISSUE_DIAGNOSED_TIMEOUT` event.

The intent is NOT automatic transition (that could mask real problems), but explicit visibility: if the supervisor wrote a diagnosis but nothing is fixing the finding, the operator should know.

#### Scenario: Issue stuck in diagnosed for > 1 hour
- **WHEN** `ISS-050` has been in state `diagnosed` since 08:00 UTC and the current time is 09:05 UTC
- **THEN** the watchdog emits `ISSUE_DIAGNOSED_TIMEOUT` with `issue_id`, `change`, `age_seconds`
- **THEN** the supervisor's canary run picks up the event on its next fire and includes it in the structured diff
- **THEN** the canary Claude has visibility to recommend a manual resolution path

#### Scenario: Issue resolved before timeout
- **WHEN** `ISS-050` is auto-resolved by a successful change merge 30 minutes after entering `diagnosed`
- **THEN** no timeout event fires
- **THEN** the watchdog's periodic check skips the resolved issue

### Requirement: Manager API to resolve issues
The set-web manager API SHALL expose a `POST /api/{project}/issues/{iss_id}/resolve` endpoint that transitions an issue to `fixed` with operator-supplied rationale. This is the explicit escape hatch when auto-resolve and timeout visibility are not enough.

#### Scenario: Operator manually resolves a stuck issue
- **WHEN** the operator POSTs `{"reason": "false positive — scope boundary"}` to `/api/my-project/issues/ISS-042/resolve`
- **THEN** the issue state transitions to `fixed`
- **THEN** the audit log records `{"action": "transition:fixed", "reason": "manual: false positive — scope boundary", "source": "operator_api"}`
- **THEN** if the issue was blocking a change in `state.merge_queue`, the next merge-queue drain picks it up

#### Scenario: Attempt to resolve a non-existent issue
- **WHEN** the operator POSTs to an `iss_id` not present in the registry
- **THEN** the endpoint returns HTTP 404 with `{"error": "issue_not_found"}`
