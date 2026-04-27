# Spec: diagnostic-framework

Core diagnostic rule system in set-core that intercepts orchestration failures before they cascade.

## Requirements

### REQ-DIAG-001: DiagnosticRule ABC
- `DiagnosticRule` abstract base class in `lib/set_orch/diagnostic.py`
- Abstract method: `diagnose(ctx: DiagnosticContext) -> Optional[DiagnosticResult]`
- Fields: `name: str`, `failure_types: list[str]`
- `failure_types` filters which failures the rule handles: `["build_broken", "verify_exhausted", "merge_blocked", "smoke_failed"]`
- Return `None` if rule doesn't apply (not this failure pattern)

### REQ-DIAG-002: DiagnosticContext dataclass
- Captures all failure state: `change_name`, `failure_type`, `build_output` (last 10K), `review_output`, `merge_output`
- Includes paths: `state_file`, `wt_path`, `config_path`
- Includes change object: `change: Change`, `verify_retry_count`, `tokens_used`
- Built by the runner from available state at failure time

### REQ-DIAG-003: DiagnosticResult dataclass
- `action`: one of `"fix_config"`, `"retry"`, `"skip"`, `"skip_downstream"`, `"escalate"`
- `config_patches: dict` — key-value updates for config.yaml
- `gitattributes_rules: list[str]` — lines to append to .gitattributes
- `state_patches: dict` — field updates for the change in orchestration-state.json
- `retry_context: str` — inject into agent retry prompt
- `model_override: str` — override model for retry (e.g., "opus-1m")
- `report: str` — human-readable finding
- `severity: str` — "fix", "workaround", "escalate"

### REQ-DIAG-004: DiagnosticRunner
- `run_diagnostics(ctx: DiagnosticContext, rules: list[DiagnosticRule]) -> Optional[DiagnosticResult]`
- Executes rules in order; first non-None result wins
- Applies result actions:
  - `fix_config` → patch config.yaml, retry the operation
  - `retry` → reset retry count, inject retry_context, resume change
  - `skip` → mark change as skipped
  - `skip_downstream` → mark all dependents as `dep_blocked`
  - `escalate` → fall through to existing behavior (mark failed)
- Logs diagnostic result to structured log
- Emits `DIAGNOSTIC_FIRED` event

### REQ-DIAG-005: Profile Interface Extension
- Add `diagnostic_rules() -> list[DiagnosticRule]` to `NullProfile` in `profile_loader.py`
- Default implementation returns empty list (no project-specific diagnostics)
- Runner loads rules: built-in core rules + profile rules

### REQ-DIAG-006: Built-in DependencyCascadeRule
- Handles `failure_type == "verify_exhausted"` or any terminal failure
- Finds all changes depending on the failed change (direct + transitive)
- Marks dependents as `dep_blocked` (new status) with reason
- Returns `skip_downstream` action
- Fixes Bug #26 (dependency cascade deadlock from Run #4, #5, #6)

### REQ-DIAG-007: Built-in ContextOverflowRule
- Handles `failure_type == "verify_exhausted"`
- Detects `context_tokens_end > context_window * 0.9` from change state
- If current model is not `*-1m`: returns `retry` with `model_override: "{model}-1m"`
- Fixes Bug #27 (auth change context overflow from Run #5)

### REQ-DIAG-008: Engine Integration — Three Failure Paths
- **verify_exhausted**: Before marking `failed` in `gate_runner.py`, call `run_diagnostics()`
- **merge_blocked**: Before giving up in `merger.py`, call `run_diagnostics()`
- **build_broken_on_main**: In `_retry_broken_main_build_safe()`, call `run_diagnostics()` instead of simple retry
- Each path constructs appropriate `DiagnosticContext` and handles the result

### REQ-DIAG-009: Findings Reporting
- Diagnostic results written to `change.extras.diagnostic_history` (array of {timestamp, rule, action, report})
- Emit `DIAGNOSTIC_FIRED` event to orchestration-state-events.jsonl
- Log at WARNING level with rule name and action

## Acceptance Criteria

- [ ] AC-1: WHEN verify retries exhaust for a change THEN diagnostic rules execute before marking failed
- [ ] AC-2: WHEN a built-in rule matches (e.g., context overflow) THEN the config/model is patched and change retried
- [ ] AC-3: WHEN a change fails with dependents THEN DependencyCascadeRule marks dependents as `dep_blocked` instead of leaving them `pending` forever
- [ ] AC-4: WHEN no diagnostic rule matches THEN existing behavior unchanged (change marked failed)
- [ ] AC-5: WHEN profile returns custom rules THEN they execute after built-in rules
