## ADDED Requirements

### Requirement: Exponential back-off on retry_budget_exhausted
When the supervisor's trigger executor records `skipped: retry_budget_exhausted` for a `(trigger, change, reason)` tuple, the next evaluation of that same tuple SHALL be suppressed until an exponential back-off window has elapsed. The back-off schedule SHALL be: 60s, 120s, 240s, 480s, 600s (cap). The window resets when the trigger fires successfully (not skipped) or when the detector's observed state transitions out of the condition that produced the trigger.

Prior behavior (to be removed): the `log_silence` detector fired every 15s and produced `skipped: retry_budget_exhausted` events in an unbroken stream (observed 15× in 4 minutes on `craftbrew-run-20260418-1719` between 05:58 and 06:02).

#### Scenario: First retry-budget-exhausted records back-off start
- **WHEN** the trigger executor evaluates `(log_silence, "", reason="orchestration.log silent for 300s")` and the retry budget is exhausted
- **THEN** the executor SHALL record `back_off_until = now + 60s` on `SupervisorStatus.trigger_backoffs[tuple_key]`
- **AND** emit one `SUPERVISOR_TRIGGER` event with `skipped: retry_budget_exhausted`
- **AND** subsequent evaluations within 60s SHALL NOT emit any event for the same tuple

#### Scenario: Back-off grows on repeated exhaustion
- **WHEN** 60s have elapsed and the same tuple is still exhausted
- **THEN** the executor SHALL emit exactly one `SUPERVISOR_TRIGGER` event
- **AND** set the next `back_off_until = now + 120s`
- **AND** repeat with 240s, 480s, 600s (cap)

#### Scenario: Back-off resets on transition
- **WHEN** the detector's `is_triggered()` returns `False` on a subsequent poll cycle (e.g. `log_silence` detects the log has new lines, `integration_failed` detects the status transitioned out of failed)
- **THEN** the tuple's `back_off_until` and step SHALL be cleared from `trigger_backoffs`
- **AND** a future re-entry of the condition SHALL start back-off at 60s again

### Requirement: trigger_backoffs persisted in SupervisorStatus
The `SupervisorStatus` dataclass SHALL gain a `trigger_backoffs: dict[str, BackoffEntry]` field where `BackoffEntry = {step: int, back_off_until: float}` and the key format is `f"{trigger}::{change}::{reason_hash}"`.

Key format rules:
- `trigger` is the detector name (e.g. `log_silence`, `integration_failed`).
- `change` is the change name when the trigger is change-scoped, or the empty string `""` when the trigger is orchestration-scoped (detectors like `log_silence` that fire without a specific change context).
- `reason_hash` is the hex SHA1 of the detector's `reason` string, truncated to 12 chars.

The field SHALL be serialised to `.set/supervisor/status.json`.

#### Scenario: BackoffEntry round-trips through JSON
- **WHEN** a `SupervisorStatus` with `trigger_backoffs={"log_silence::::abc123def456": {"step": 2, "back_off_until": 1776571400.0}}` is saved and reloaded
- **THEN** the reloaded status SHALL have the same `trigger_backoffs` entries

#### Scenario: Orchestration-scoped trigger uses empty change segment
- **WHEN** a `log_silence` trigger fires with no change context
- **THEN** the key SHALL be `"log_silence::::<reason_hash>"` (with `change=""`)
- **AND** SHALL NOT use `None` or `"*"` or any other placeholder
