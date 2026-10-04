## IN SCOPE
- The per-account opt-in, stored outside every repository
- A scheduled Claude Code pane with Run now, snooze 1 h, tomorrow and off
- A single asker across concurrent sessions
- Importing an existing opt-in once

## OUT OF SCOPE
- A FleetView panel, which needs a plugin API that does not exist
- Running collection unattended, or from a cloud routine

## ADDED Requirements

### Requirement: Per-account opt-in outside the repository
The scheduled pane SHALL be active only when `~/.config/set-core/feed-watch.json` has an enabled entry for the current project whose account equals the session's Claude account e-mail. The opt-in SHALL NOT be written into any repository.

#### Scenario: Another account
- **WHEN** the plugin is loaded in a session authenticated as a different account
- **THEN** no pane and no notification SHALL appear

#### Scenario: Opt-in command
- **WHEN** the user runs `set-feed-watch optin on --times 08:30,18:30`
- **THEN** the entry SHALL be written under `~/.config/set-core/`
- **AND** the project's working tree SHALL be unchanged

### Requirement: Scheduled pane with four actions
At each declared local time, an active session SHALL offer a pane with the actions "Run now", "snooze 1 h", "tomorrow" and "off". "Run now" SHALL start the feed-watch skill in that session. A missed slot SHALL stay due until the next declared time replaces it.

#### Scenario: Snooze
- **WHEN** the user picks "snooze 1 h"
- **THEN** no pane SHALL appear for 60 minutes

#### Scenario: Off
- **WHEN** the user picks "off"
- **THEN** the opt-in SHALL be disabled, and the pane SHALL not appear again until the user re-enables it

### Requirement: One session asks
When several sessions are active, at most one SHALL show the pane for a given slot, using a lease held in the shared state file.

#### Scenario: Two sessions at the slot time
- **WHEN** two sessions reach the same due slot
- **THEN** only the one holding the lease SHALL show the pane, until it is answered or the lease expires

### Requirement: Import of an existing opt-in
`set-feed-watch optin import <path>` SHALL copy the enabled flag, account and times from an existing opt-in file into set-core's config once, and SHALL NOT modify the source file.

#### Scenario: Import
- **WHEN** an existing opt-in file is imported
- **THEN** set-core's entry SHALL carry the same account and times
- **AND** the source file SHALL be byte-identical afterwards
