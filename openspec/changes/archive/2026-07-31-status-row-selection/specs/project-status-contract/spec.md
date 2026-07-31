## ADDED Requirements

### Requirement: A refused write hands back the project's own reason
When a write command fails, set-core SHALL report what the project said about the failure,
not merely that it failed. Where the project wrote nothing, the answer SHALL say that
explicitly rather than presenting a bare exit code as if it were an explanation.

#### Scenario: The project explains a refusal on stderr
- **WHEN** a write command exits non-zero and writes a reason to stderr
- **THEN** that text SHALL reach the reader, capped in length, taking the LAST lines — a tool
  that logs progress before failing puts the reason at the end

#### Scenario: The project refuses silently
- **WHEN** a write command exits non-zero and writes nothing
- **THEN** the answer SHALL state that it exited and explained nothing, so that this is
  distinguishable from a refusal that gave a reason

#### Scenario: The log still carries the shape and never the text
- **WHEN** a write fails
- **THEN** the log entry SHALL carry the command, the exit code and the SIZE of the error
  output, and SHALL NOT carry its content — a log is persistence and can leave the machine,
  while a screen is neither
