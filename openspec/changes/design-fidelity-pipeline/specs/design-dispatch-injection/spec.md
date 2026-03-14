## ADDED Requirements

### Requirement: Design context extraction for dispatch

The dispatcher SHALL extract design context from `design-snapshot.md` when dispatching a change that involves UI work. The extraction SHALL produce a frame-filtered subset containing design tokens and relevant component hierarchies.

#### Scenario: Dispatch with design snapshot available
- **WHEN** `dispatch_change()` is called for a change
- **AND** `design-snapshot.md` exists in the project root (or `$DESIGN_SNAPSHOT_DIR`)
- **THEN** the system extracts the Design Tokens section (colors, typography, spacing, radius)
- **AND** extracts Component Hierarchy sections whose frame names appear in the change scope text (case-insensitive match)
- **AND** appends the extracted content to the change's `proposal.md` under a `## Design Context` header

#### Scenario: Dispatch without design snapshot
- **WHEN** `dispatch_change()` is called for a change
- **AND** no `design-snapshot.md` exists
- **THEN** the existing `design_ref` behavior is preserved (single-line reference if planner provided one)
- **AND** no error or warning is emitted

#### Scenario: No frame matches in scope
- **WHEN** `dispatch_change()` is called
- **AND** `design-snapshot.md` exists
- **AND** no frame names from the snapshot appear in the change scope text
- **THEN** only the Design Tokens section is injected (tokens are always relevant)
- **AND** a note is added: "No specific frame matches found — refer to design-snapshot.md for full hierarchy"

### Requirement: Design context size limit

The injected design context in the proposal SHALL be limited to 150 lines maximum to prevent context bloat.

#### Scenario: Context within limit
- **WHEN** the extracted design context is 120 lines
- **THEN** the full content is appended to the proposal

#### Scenario: Context exceeds limit
- **WHEN** the extracted design context exceeds 150 lines
- **THEN** the Design Tokens section is always included in full
- **AND** frame hierarchies are truncated with "...truncated — read design-snapshot.md for full hierarchy"
- **AND** total output does not exceed 150 lines

### Requirement: Frame matching from scope text

The system SHALL match frame names from the design snapshot against the change scope text using case-insensitive substring matching.

#### Scenario: Exact frame name in scope
- **WHEN** scope contains "matching Figma ProductGrid frame"
- **AND** design snapshot has a frame named "ProductGrid"
- **THEN** the ProductGrid component hierarchy is included in the dispatch context

#### Scenario: Multiple frame matches
- **WHEN** scope mentions "AdminDashboard" and "AdminProducts"
- **AND** design snapshot has frames for both
- **THEN** both frame hierarchies are included in the dispatch context

#### Scenario: Partial name match
- **WHEN** scope mentions "cart page" or "Cart"
- **AND** design snapshot has a frame named "Cart"
- **THEN** the Cart frame hierarchy is matched and included
