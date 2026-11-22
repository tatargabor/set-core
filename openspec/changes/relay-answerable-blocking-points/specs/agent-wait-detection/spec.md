## MODIFIED Requirements

### Requirement: The detector acts only while the relay is on and ready

The hook SHALL exit 0 with no output, without starting any process, in any of these cases:
- the question relay is not enabled or not ready;
- the final message is empty;
- it runs inside the classifier's own session;
- `stop_hook_active` is true AND the session's previous verdict record names `WAITING`, meaning the continuation follows the detector's own re-ask.

A `stop_hook_active` turn that follows anything else SHALL be classified like any other turn. Measured 2026-11-22: a session woken by an `asyncRewake` continuation ends its next turn with `stop_hook_active: true`. Skipping every such turn would make a channel-continued session invisible to the relay after its first continuation.

#### Scenario: Relay off

- **WHEN** a turn ends and the relay is off
- **THEN** the hook exits with no output and runs no classifier

#### Scenario: Already continued once

- **WHEN** a turn ends with `stop_hook_active` true and the session's previous verdict was `WAITING`
- **THEN** the hook exits with no output and runs no classifier

#### Scenario: A turn woken from the channel

- **WHEN** a turn ends with `stop_hook_active` true and the session's previous verdict was `DONE`
- **THEN** the classifier runs, and the turn is decided like any other

## ADDED Requirements

### Requirement: The detector records its verdict for the turn

Whenever the detector decides a turn while the relay is on, it SHALL write a verdict record for the session under the relay's state directory. A decision is any of: classified, skipped (see the requirement above), or the classifier failed. The record SHALL hold the turn key, the verdict (`WAITING`, `DONE`, `SKIPPED` or `UNKNOWN`) and the time. The turn key SHALL be the Stop payload's `prompt_id` (measured present on 2.1.330), falling back to a hash of the final message. The record SHALL hold no message text. A newer record for the same session SHALL replace the older one. The re-ask behaviour for `WAITING` SHALL stay unchanged.

#### Scenario: A finished turn leaves a DONE verdict

- **WHEN** the relay is on and the classifier answers DONE
- **THEN** the verdict record for that session names DONE and that turn's key, and the hook's output is unchanged (none)

#### Scenario: The continued turn after a re-ask

- **WHEN** a turn ends with `stop_hook_active` true after a `WAITING` verdict
- **THEN** the verdict record names SKIPPED for that turn, and no classifier runs

#### Scenario: The relay is off

- **WHEN** the relay is off
- **THEN** no verdict record is written
