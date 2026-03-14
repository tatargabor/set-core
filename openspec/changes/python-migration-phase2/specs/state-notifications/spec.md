## Purpose
Desktop (notify-send) and email (Resend API) notification dispatch.
## Requirements

## ADDED Requirements

### Requirement: Multi-channel notification dispatch
The system SHALL provide `send_notification(title, body, urgency, channels)` that dispatches notifications to configured channels. Channels are `"desktop"`, `"email"`, or `"none"`. Urgency is `"normal"` or `"critical"`.

#### Scenario: Desktop notification
- **WHEN** channel includes `"desktop"` and `notify-send` is available
- **THEN** a desktop notification is sent via `notify-send` with the given urgency
- **AND** failures are logged but do not raise exceptions

#### Scenario: Email notification
- **WHEN** channel includes `"email"` and Resend API credentials are configured
- **THEN** an email is sent with HTML body including title, body, timestamp, and project name
- **AND** critical urgency messages get a `[CRITICAL]` subject prefix

#### Scenario: None channel
- **WHEN** channel is `"none"`
- **THEN** the notification is logged but not dispatched to any external service

#### Scenario: Missing notify-send
- **WHEN** channel includes `"desktop"` but `notify-send` is not installed
- **THEN** the desktop channel is skipped silently (no error)

### Requirement: Hook runner
The system SHALL provide `run_hook(hook_name, hook_script, change_name, status, wt_path)` that executes lifecycle hook scripts. It SHALL return `True` if the hook passes (exit 0) or is not configured, `False` if the hook blocks (non-zero exit).

#### Scenario: Hook passes
- **WHEN** the hook script exits with code 0
- **THEN** `run_hook` returns `True` and logs success

#### Scenario: Hook blocks
- **WHEN** the hook script exits with a non-zero code
- **THEN** `run_hook` returns `False`
- **AND** the stderr output is captured as the blocking reason
- **AND** a `HOOK_BLOCKED` event is emitted

#### Scenario: Hook not configured
- **WHEN** `hook_script` is `None` or empty
- **THEN** `run_hook` returns `True` (no-op)

#### Scenario: Hook script not executable
- **WHEN** the hook script path exists but is not executable
- **THEN** `run_hook` returns `True` and logs a warning
