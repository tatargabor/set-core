# Issue Actions

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- State-aware action button rendering
- Action buttons trigger API calls and optimistic UI updates
- Timeout countdown with progress bar
- Confirmation dialogs for destructive actions (dismiss, cancel)
- Mute pattern dialog with auto-generated pattern
- Extend timeout dialog

### Out of scope
- Keyboard shortcuts for actions
- Undo for actions (transitions are permanent)
- Batch actions on issue detail (only on list via multi-select)

## Requirements

### Requirement: State-aware button rendering
The action bar SHALL show only buttons valid for the current issue state. The mapping SHALL be:

| State | Buttons |
|-------|---------|
| NEW | Investigate, Dismiss, Mute, Skip |
| INVESTIGATING | Cancel, Dismiss |
| DIAGNOSED | Fix Now, Investigate More, Dismiss, Mute, Skip |
| AWAITING_APPROVAL | Fix Now, Extend Timeout, Cancel, Dismiss |
| FIXING | Cancel |
| VERIFYING | Cancel |
| DEPLOYING | (none) |
| RESOLVED | (view only) |
| DISMISSED | Reopen |
| MUTED | Unmute |
| FAILED | Retry, Investigate More, Dismiss |
| SKIPPED | Reopen |
| CANCELLED | Reopen, Dismiss |

#### Scenario: DIAGNOSED state buttons
- **WHEN** viewing an issue in DIAGNOSED state
- **THEN** buttons shown are: Fix Now, Investigate More, Dismiss, Mute, Skip

#### Scenario: FIXING state buttons
- **WHEN** viewing an issue in FIXING state
- **THEN** only Cancel button is shown

#### Scenario: RESOLVED state
- **WHEN** viewing a RESOLVED issue
- **THEN** no action buttons are shown (view only)

### Requirement: Action API calls
Each button SHALL call the corresponding API endpoint. On success, the issue state SHALL update optimistically. On failure, an error toast SHALL appear.

#### Scenario: Fix Now clicked
- **WHEN** user clicks "Fix Now" on a DIAGNOSED issue
- **THEN** POST /api/projects/{name}/issues/{id}/fix is called and state updates to FIXING (or shows "queued" if another fix is running)

#### Scenario: API error
- **WHEN** an action API call returns HTTP 409 (invalid transition)
- **THEN** an error toast shows "Cannot perform this action in current state" and the issue is re-fetched

### Requirement: Timeout countdown display
For AWAITING_APPROVAL issues, a countdown timer SHALL show remaining time with a progress bar. The timer SHALL update every second (client-side, based on timeout_deadline).

#### Scenario: Countdown display
- **WHEN** an issue is AWAITING_APPROVAL with timeout_deadline 3 minutes from now
- **THEN** the countdown shows "Auto-fix in 3:00" with a progress bar at the corresponding percentage

#### Scenario: Countdown reaches zero
- **WHEN** the countdown reaches 0
- **THEN** the UI re-fetches the issue (which should now be FIXING) and updates accordingly

### Requirement: Confirmation dialogs
Dismiss and Cancel actions SHALL show a confirmation dialog before executing. The dialog SHALL explain the consequence.

#### Scenario: Dismiss confirmation
- **WHEN** user clicks "Dismiss"
- **THEN** a dialog shows "Dismiss ISS-003? This marks the issue as won't-fix." with Confirm/Cancel buttons

### Requirement: Mute pattern dialog
The "Mute" button SHALL open a dialog pre-filled with an auto-generated regex pattern from the issue's error_summary. The user can edit the pattern and add a reason. Optionally set an expiry.

#### Scenario: Mute dialog
- **WHEN** user clicks "Mute Pattern" on an issue
- **THEN** a dialog shows with pre-filled pattern, editable reason field, and optional expiry date picker

### Requirement: Extend timeout dialog
The "Extend Timeout" button SHALL open a dialog where the user can add extra minutes to the countdown.

#### Scenario: Extend by 5 minutes
- **WHEN** user clicks "Extend Timeout" and enters 5 minutes
- **THEN** POST .../extend-timeout is called with 300 seconds and the countdown updates
