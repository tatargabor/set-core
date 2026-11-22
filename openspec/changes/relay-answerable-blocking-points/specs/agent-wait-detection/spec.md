## ADDED Requirements

### Requirement: The detector records its verdict for the turn

Whenever the detector decides a turn, it SHALL write a verdict record for the session under the relay's state directory. A decision is any of: classified, skipped because `stop_hook_active` is set, or the classifier failed. The record SHALL hold the turn key, the verdict (`WAITING`, `DONE`, `SKIPPED` or `UNKNOWN`) and the time. The turn key SHALL be the runtime's prompt id when the Stop payload carries one, and otherwise a hash of the final message. The record SHALL hold no message text. A newer record for the same session SHALL replace the older one. The re-ask behaviour for `WAITING` SHALL stay unchanged.

#### Scenario: A finished turn leaves a DONE verdict

- **WHEN** the relay is on and the classifier answers DONE
- **THEN** the verdict record for that session names DONE and that turn's key, and the hook's output is unchanged (none)

#### Scenario: The continued turn after a re-ask

- **WHEN** a turn ends with `stop_hook_active` true
- **THEN** the verdict record names SKIPPED for that turn, and no classifier runs

#### Scenario: The relay is off

- **WHEN** the relay is off
- **THEN** no verdict record is written
