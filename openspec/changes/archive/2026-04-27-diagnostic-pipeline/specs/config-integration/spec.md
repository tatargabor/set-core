# Spec: config-integration

Declarative failure policy configuration and engine integration.

## Requirements

### REQ-CONFIG-001: on_failure Config Section
- New `diagnostics` section in config.yaml:
  ```yaml
  diagnostics:
    enabled: true
    on_verify_exhausted: diagnose  # diagnose | fail
    on_merge_blocked: diagnose
    on_build_broken: diagnose
    on_dependency_failed: skip     # skip | block | replan
    max_diagnostic_retries: 1
  ```
- Parsed in `config.py` with validation
- Defaults: all `diagnose` except `on_dependency_failed: skip`

### REQ-CONFIG-002: dep_blocked Change Status
- New change status: `dep_blocked`
- Meaning: this change cannot proceed because a dependency failed
- Contains `extras.blocked_reason`: "Dependency '{dep_name}' failed"
- Monitor skips `dep_blocked` changes (no dispatch, no retry)
- If blocked dependency is later retried and succeeds → `dep_blocked` changes return to `pending`

### REQ-CONFIG-003: Engine Failure Path Integration
- `engine.py _poll_active_changes()`: when verify returns "failed", check `diagnostics.on_verify_exhausted`
  - If `diagnose`: call `run_diagnostics()` before marking failed
  - If `fail`: existing behavior (mark failed immediately)
- `merger.py _handle_merge_conflict()`: when merge-blocked, check `diagnostics.on_merge_blocked`
- `engine.py _retry_broken_main_build_safe()`: check `diagnostics.on_build_broken`

### REQ-CONFIG-004: Diagnostic Config Patching
- `DiagnosticRunner.apply_config_patches(result)`:
  - Reads config.yaml
  - Merges `result.config_patches` (additive, not destructive)
  - Writes back
  - Reloads directives
- Only patches declared keys — never removes existing config
- Logs each patch applied

### REQ-CONFIG-005: Diagnostic Event Emission
- New event type: `DIAGNOSTIC_FIRED`
- Data: `{rule: str, action: str, change: str, report: str, patches: dict}`
- Written to orchestration-state-events.jsonl
- Visible in web dashboard event feed

## Acceptance Criteria

- [ ] AC-1: WHEN `diagnostics.enabled: false` in config THEN no diagnostic rules execute on failure
- [ ] AC-2: WHEN `on_dependency_failed: skip` and a change fails THEN dependents are marked `dep_blocked` with reason
- [ ] AC-3: WHEN a diagnostic rule applies config patches THEN config.yaml is updated and directives reloaded
- [ ] AC-4: WHEN `dep_blocked` change's dependency is retried successfully THEN the blocked change returns to `pending`
- [ ] AC-5: WHEN diagnostic fires THEN `DIAGNOSTIC_FIRED` event is emitted to events.jsonl
