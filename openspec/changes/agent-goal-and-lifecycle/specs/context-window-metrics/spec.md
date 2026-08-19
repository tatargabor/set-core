## REMOVED Requirements

### Requirement: Context window size constant

**Reason**: Measured 2026-08-19 — the runtime reports `context_window.context_window_size` **per
model** in the payload it hands a hook: 200 000 for `claude-haiku-4-5-20251001` in the probe, while
this repository's own sessions run a 1M window. A fixed `CONTEXT_WINDOW_SIZE = 200_000` is therefore
not merely inflexible, it is currently wrong, and every utilization percentage derived from it is
wrong by the same factor — in the direction that reports a comfortable session as nearly full.

The requirement is removed rather than modified because its surviving scenario asserted the constant's
existence by name (*"Constant is defined and used"*). Rewriting that scenario's body to assert the
opposite while keeping its name would leave the name contradicting the check, which is the defect
class this repository already refuses.

**Migration**: `monitor.py` drops the constant and takes the size from the reported window for the
session's model. A session for which no size is reported yields `unknown` utilization; the set-web
change list renders that as unknown rather than as a percentage. No stored state changes shape —
`context_tokens_start` / `context_tokens_end` are unaffected, only the divisor and the case where
there is none.

## ADDED Requirements

### Requirement: Context window size is taken from what the runtime reports for the model in use
The monitor SHALL obtain the context window size from what the runtime reports for the session's
model, and SHALL NOT define or apply a fixed size. Where no size is reported, utilization SHALL be
reported as unknown, and SHALL NOT be computed against a substituted or previously seen value.

#### Scenario: The size comes from the model in use
- **WHEN** utilization is computed for a change
- **THEN** the divisor is the window size the runtime reported for that session's model
- **AND** no fixed constant participates in the figure

#### Scenario: An unreported size yields unknown, not a substituted percentage
- **WHEN** no window size is available for a session
- **THEN** utilization is reported as unknown
- **AND** no percentage is computed from a default or from a size seen for another session

#### Scenario: Unknown utilization is displayed as unknown
- **WHEN** the set-web change list renders a change whose utilization is unknown
- **THEN** it shows that the figure is unavailable
- **AND** it does not show a zero, a blank, or a percentage
