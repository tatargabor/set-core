## ADDED Requirements

### Requirement: Chat button opens correct project
When clicking the chat button in a project header, the chat dialog SHALL open for that specific project.

#### Scenario: Click chat in project A header
- **GIVEN** projects "set-core" and "mediapipe" are displayed
- **WHEN** user clicks the chat button in "mediapipe" project header
- **THEN** ChatDialog opens with project="mediapipe"
- **AND** messages shown are from mediapipe's .wt-control/chat/messages.jsonl

#### Scenario: Click chat in project B header
- **GIVEN** projects "set-core" and "mediapipe" are displayed
- **WHEN** user clicks the chat button in "set-core" project header
- **THEN** ChatDialog opens with project="set-core"
- **AND** messages shown are from set-core's .wt-control/chat/messages.jsonl

### Requirement: Menu chat uses active project
When opening chat from the menu (not project header), the chat SHALL use the active project.

#### Scenario: Open chat from menu
- **WHEN** user opens chat from Project menu
- **THEN** ChatDialog opens with the active project (first worktree's project)
