# Supervisor Permanent Errors Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Supervisor distinguishes permanent errors from transient crashes
The supervisor daemon's `_restart_orchestrator()` SHALL NOT retry the orchestrator when the previous invocation failed with a permanent error — defined as an error that will recur deterministically on the next invocation regardless of elapsed time or environment changes the supervisor can influence.

Currently the supervisor treats every non-zero exit as a transient crash and retries up to `RAPID_CRASH_LIMIT` (default 3) before halting. This wastes 3 restart cycles when the underlying cause is a typo in the spec argument, a missing binary, or a corrupt state file.

Observed on 2026-04-12 minishop-run-20260412-0103 initial attempt: the supervisor was started with `spec=docs/spec.md` instead of `docs/v1-minishop.md`. The orchestrator wrote `Error: Spec file not found: docs/spec.md` to stderr three times in under a minute, exhausted the rapid-crash budget, and halted — 3 useless restart attempts.

#### Scenario: Spec file not found on first start
- **WHEN** the orchestrator exits non-zero and its stderr.log tail contains `Error: Spec file not found:`
- **THEN** the supervisor classifies the exit as PERMANENT (not transient)
- **THEN** `_restart_orchestrator()` returns `False` immediately without consuming a retry slot
- **THEN** the daemon sets `stop_reason` to `permanent_error:spec_not_found` and enters graceful shutdown
- **THEN** the manager API's next status poll surfaces the permanent-error reason so the UI can show it prominently

#### Scenario: Orchestrator crashes with a Python traceback (transient)
- **WHEN** the orchestrator exits non-zero and its stderr.log tail contains a Python `Traceback` header (`Traceback (most recent call last):`)
- **THEN** the supervisor classifies the exit as TRANSIENT
- **THEN** `_restart_orchestrator()` retries per the normal rapid-crash budget
- **THEN** the rationale is that Python exceptions might recover if the state was updated between attempts

#### Scenario: Orchestrator exits with code 127 (binary not found)
- **WHEN** the orchestrator exits with code 127
- **THEN** the supervisor classifies as PERMANENT (missing executable)
- **THEN** the daemon halts without retrying
- **THEN** `stop_reason` is `permanent_error:orchestrator_binary_missing`

### Requirement: Permanent error catalog in anomaly module
The system SHALL maintain a `PERMANENT_ERROR_SIGNALS: list[tuple[str, str]]` constant in `lib/set_orch/supervisor/anomaly.py` where each tuple is `(stderr_pattern, reason_code)`. The supervisor's `_classify_exit()` helper SHALL iterate this catalog against the last N lines of stderr.log and return the first matching reason code, or `None` if no pattern matches (= transient).

Initial catalog (based on observed errors):

```python
PERMANENT_ERROR_SIGNALS = [
    # Spec-level
    ("Error: Spec file not found:", "spec_not_found"),
    ("No such file or directory: 'docs/", "spec_not_found"),

    # Python import / module errors that cannot be retried
    ("ModuleNotFoundError: No module named 'set_orch", "orchestrator_import_broken"),
    ("ImportError: cannot import name", "orchestrator_import_broken"),

    # Exec / binary issues
    ("set-orchestrate: command not found", "orchestrator_binary_missing"),

    # Configuration
    ("Error: No directives file", "directives_missing"),
    ("Error: State file not found", "state_file_missing"),

    # Plugin system
    ("ProfileResolutionError:", "profile_resolution_failed"),
]
```

#### Scenario: Unknown stderr pattern
- **WHEN** the stderr tail does not match any entry in `PERMANENT_ERROR_SIGNALS`
- **THEN** `_classify_exit()` returns `None`
- **THEN** the supervisor treats the exit as transient and retries

#### Scenario: Adding a new permanent error
- **WHEN** a developer adds a new tuple to `PERMANENT_ERROR_SIGNALS`
- **THEN** the supervisor picks it up on the next start (no other code changes needed)
- **THEN** unit tests in `tests/unit/test_supervisor_anomaly.py` cover the classifier with the new entry

### Requirement: Manager API surfaces permanent errors prominently
The set-web manager API's `/api/{project}/sentinel/status` endpoint SHALL include a `permanent_error` field when the daemon has halted due to a permanent error. The field contains `{code, stderr_tail}` so the dashboard can render a visible error panel instead of showing the run as "stopped" with no explanation.

#### Scenario: Dashboard shows permanent error after spec typo
- **WHEN** the daemon halted with `stop_reason: permanent_error:spec_not_found`
- **WHEN** the dashboard polls `/sentinel/status`
- **THEN** the response includes `"permanent_error": {"code": "spec_not_found", "stderr_tail": "Error: Spec file not found: docs/spec.md"}`
- **THEN** the frontend renders a red banner: "Orchestrator cannot start: spec file `docs/spec.md` not found. Check the spec argument and restart."

#### Scenario: Dashboard shows normal stopped state after manual halt
- **WHEN** the daemon halted with `stop_reason: inbox_stop:user`
- **THEN** the response does NOT include `permanent_error`
- **THEN** the frontend renders the normal stopped state

### Requirement: Unit test coverage for each permanent error signal
Every entry in `PERMANENT_ERROR_SIGNALS` SHALL have a corresponding unit test in `tests/unit/test_supervisor_anomaly.py` that verifies `_classify_exit()` returns the expected reason code for that stderr pattern.

#### Scenario: Test for spec_not_found
- **WHEN** the test feeds `"Error: Spec file not found: docs/spec.md\n"` to `_classify_exit()`
- **THEN** the function returns `"spec_not_found"`

#### Scenario: Test for transient Python traceback
- **WHEN** the test feeds a mock stderr containing only a Python traceback
- **THEN** `_classify_exit()` returns `None` (= transient, retry)
