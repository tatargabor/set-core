## ADDED Requirements

### Requirement: Clickable memory cards
Memory cards in the browse dialog SHALL be clickable. The cursor SHALL change to a pointing hand when hovering over a card.

#### Scenario: User clicks a memory card
- **WHEN** user clicks on a memory card in the browse dialog (summary, list, or search view)
- **THEN** a detail dialog opens showing the full memory content

### Requirement: Memory detail dialog
The system SHALL display a `MemoryDetailDialog` showing the complete, untruncated memory content.

#### Scenario: Detail dialog content
- **WHEN** the detail dialog opens for a memory
- **THEN** it SHALL display: type badge with color, creation date, full content text (word-wrapped, selectable), tags, and memory ID

#### Scenario: Detail dialog fetches via wt-memory get
- **WHEN** the memory has an `id` field
- **THEN** the dialog SHALL fetch the full record via `wt-memory get <id>` and display the result

#### Scenario: Memory without ID (summary mode fallback)
- **WHEN** the memory dict has no `id` field
- **THEN** the dialog SHALL display whatever content is available from the card's existing data

### Requirement: Detail dialog stays on top
The detail dialog SHALL have `WindowStaysOnTopHint` set, consistent with all other dialogs in the application.

#### Scenario: Dialog visibility
- **WHEN** the detail dialog is open
- **THEN** it SHALL appear above the browse dialog and other windows

### Requirement: Detail dialog close
The detail dialog SHALL have a Close button and support closing via Escape key.

#### Scenario: Close via button
- **WHEN** user clicks the Close button
- **THEN** the dialog closes

#### Scenario: Close via Escape
- **WHEN** user presses Escape while the detail dialog is focused
- **THEN** the dialog closes
