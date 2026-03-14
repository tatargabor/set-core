## ADDED Requirements

### Requirement: Design compliance section in code review

The verifier SHALL include a design compliance section in the code review prompt when a `design-snapshot.md` exists in the project.

#### Scenario: Review with design snapshot
- **WHEN** `review_change()` runs for a change
- **AND** `design-snapshot.md` exists in the project root
- **THEN** the review prompt includes a "Design Compliance Check" section
- **AND** the section contains the Design Tokens from the snapshot (colors, typography, spacing)
- **AND** instructs the reviewer to compare Tailwind classes in the diff against design token values

#### Scenario: Review without design snapshot
- **WHEN** `review_change()` runs for a change
- **AND** no `design-snapshot.md` exists
- **THEN** no design compliance section is added to the review prompt
- **AND** the review proceeds as before

### Requirement: Design compliance severity

Design compliance issues SHALL be reported as WARNING severity, not CRITICAL. They SHALL NOT block merging.

#### Scenario: Design token mismatch detected
- **WHEN** the reviewer finds that a diff uses `bg-primary` (mapped to #030213/near-black)
- **AND** the design tokens specify interactive elements should use `bg-blue-600`
- **THEN** the reviewer reports: `ISSUE: [WARNING] Design token mismatch — diff uses primary (#030213) but design specifies blue-600 for interactive elements`

#### Scenario: Typography size mismatch
- **WHEN** the reviewer finds `text-2xl` in the diff for a heading
- **AND** the design tokens specify `text-3xl` for that heading level
- **THEN** the reviewer reports a WARNING with the expected vs actual sizes

#### Scenario: Design warning does not block merge
- **WHEN** the review contains design WARNINGs but no CRITICAL issues
- **THEN** the verify gate passes (returns 0)
- **AND** the warnings are logged for visibility

### Requirement: Design token extraction for review

The system SHALL extract a concise token summary from `design-snapshot.md` for the review prompt, limited to actionable design tokens.

#### Scenario: Token extraction content
- **WHEN** design tokens are extracted for the review prompt
- **THEN** the extraction includes: primary colors (background, foreground, primary, destructive, accent), border-radius values, typography scale (h1-h4 sizes and weights), and shadow definitions
- **AND** excludes chart colors, sidebar colors, and other non-UI-critical tokens

#### Scenario: Token extraction size
- **WHEN** the design snapshot contains 50+ design tokens
- **THEN** the extracted token summary for review is limited to the 15-20 most UI-critical tokens
