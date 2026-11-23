# VERIFY_GATE Event Schema Specification

## Purpose

Define a consistent payload schema for the `VERIFY_GATE` event so all 12 emit sites in `verifier.py` and `merger.py` produce data dicts that can be parsed with the same `data.get("gate")` / `data.get("result")` calls. Without this, dashboard consumers see empty fields on a majority of events because verifier-side emits use `stop_gate` instead of `gate` (or omit both keys on the pass path).

## ADDED Requirements

### Requirement: verify-gate-event-schema-consistent

Every `VERIFY_GATE` event emitted via `event_bus.emit("VERIFY_GATE", change=..., data=...)` SHALL include both of the following keys in its `data` dict:

- `"gate"` — string, the gate name responsible for the event. Empty string `""` is permitted ONLY for the all-pass case (no specific stop gate). Non-empty values are gate identifiers (`"build"`, `"test"`, `"e2e"`, `"e2e-smoke"`, `"review"`, `"scope_check"`, `"rules"`, `"spec_verify"`, `"design-fidelity"`, `"required-components"`, `"i18n_check"`, `"lint"`, `"test_files"`, `"e2e_coverage"`, `"uncommitted_check"`).
- `"result"` — string, one of `"pass"`, `"fail"`, `"retry"`, `"failed"`, `"skip"`, `"warn-fail"`.

Existing `"stop_gate"` keys (verifier.py retry/failed paths) SHALL be retained for back-compat, but the new `"gate"` key SHALL be added alongside with the same value.

The pass-path emit (verifier.py:4437-4455) SHALL set `"gate": ""` and `"result": "pass"`, signaling "all gates passed, no specific stop gate". Consumers MUST detect a successful pipeline via `result == "pass"`, not via the absence of a `gate` key.

A regression test SHALL assert that `grep -nE 'event_bus\.emit\("VERIFY_GATE"' lib/set_orch/verifier.py lib/set_orch/merger.py | wc -l` returns at least 12 — preventing accidental removal of an emit site without spec review.

#### Scenario: pass-emit-has-gate-and-result-keys

- **GIVEN** a verify pipeline where every gate (build, test, scope_check, test_files, e2e_coverage, review, rules, spec_verify) returns `status="pass"` or `status="skipped"`
- **WHEN** `handle_change_done` reaches the all-pass emit (verifier.py line ~4455)
- **THEN** the emitted `VERIFY_GATE` event's data dict contains `"gate": ""`
- **AND** the data dict contains `"result": "pass"`

#### Scenario: retry-emit-has-gate-and-result-keys

- **GIVEN** a verify pipeline where the `build` gate fails (blocking) and retries are still available
- **WHEN** `handle_change_done` reaches the retry emit (verifier.py line ~4349)
- **THEN** the emitted `VERIFY_GATE` event's data dict contains `"gate": "build"`
- **AND** the data dict contains `"result": "retry"`
- **AND** the data dict contains `"stop_gate": "build"` (back-compat alias)

#### Scenario: failed-emit-has-gate-and-result-keys

- **GIVEN** a verify pipeline where the `e2e` gate has failed and `verify_retry_count >= max_retries`
- **WHEN** `handle_change_done` reaches the failed emit (verifier.py line ~4372)
- **THEN** the emitted `VERIFY_GATE` event's data dict contains `"gate": "e2e"`
- **AND** the data dict contains `"result": "failed"`
- **AND** the data dict contains `"stop_gate": "e2e"` (back-compat alias)

#### Scenario: uncommitted-check-has-gate-and-result-keys

- **GIVEN** a worktree with uncommitted changes that the auto-commit step cannot resolve
- **WHEN** `handle_change_done` reaches the uncommitted-check emit (verifier.py line ~4062)
- **THEN** the emitted `VERIFY_GATE` event's data dict contains `"gate": "uncommitted_check"`
- **AND** the data dict contains `"result": "fail"`

#### Scenario: merger-emits-already-conformant

- **GIVEN** any of the 8 merger.py integration-phase emit sites (lines 1793, 1851, 1860, 1868, 2022, 2195, 2269, 2407)
- **WHEN** the integration-phase pipeline reaches that site
- **THEN** the emitted `VERIFY_GATE` event's data dict already contains both `"gate"` and `"result"` keys (no change required)
