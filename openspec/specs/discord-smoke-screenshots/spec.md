## ADDED Requirements

## IN SCOPE
- Post smoke test failure screenshots to the run's Discord thread
- Spoiler-tag images so they don't clutter the thread
- Skip if no screenshots exist or Discord not connected

## OUT OF SCOPE
- Posting screenshots for successful smoke tests
- Screenshot diffing or visual regression

### Requirement: Smoke failure screenshots posted to thread
When a smoke test fails and screenshots were collected, the system SHALL post the screenshots to the active run's Discord thread as spoiler-tagged file attachments.

#### Scenario: Smoke failure with screenshots
- **WHEN** a change transitions to `verify-failed` status
- **AND** `SetRuntime().smoke_screenshots_dir(change_name)` contains `.png` files
- **THEN** the screenshots are posted to the run thread with `spoiler=True`
- **AND** the message includes the change name and "smoke failed"

#### Scenario: Smoke failure without screenshots
- **WHEN** a change transitions to `verify-failed` status
- **AND** no screenshots exist in the smoke directory
- **THEN** no screenshot message is posted (existing text-only notification still fires)

#### Scenario: Discord not connected
- **WHEN** screenshots are available but the Discord bot is not connected
- **THEN** screenshots are not posted and no error is raised
