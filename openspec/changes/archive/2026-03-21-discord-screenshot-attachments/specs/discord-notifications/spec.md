## MODIFIED Requirements

### Requirement: Discord notifications support file attachments
The Discord event handler SHALL support posting file attachments alongside text and embed messages, enabling screenshot delivery through the existing event routing.

#### Scenario: Event with screenshot data
- **WHEN** an event contains `screenshot_dir` and `screenshot_count > 0` in its data payload
- **THEN** the event handler calls the appropriate screenshot posting function

#### Scenario: Event without screenshot data
- **WHEN** an event has no `screenshot_dir` or `screenshot_count == 0`
- **THEN** the event handler behaves identically to current behavior (text/embed only)
