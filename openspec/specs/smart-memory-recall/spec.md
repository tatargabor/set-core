## MODIFIED Requirements

### Requirement: Topic-based recall from prompt text
The recall hook SHALL extract topic keywords from the user's prompt text and use them as the recall query. If an OpenSpec change name is detected (opsx:ff, opsx:apply, opsx:explore, opsx:new, opsx:continue, or openspec- prefixed skills), it SHALL be included in the query. The hook SHALL NOT use change-boundary detection or debounce — it SHALL recall on every prompt.

#### Scenario: Prompt contains opsx:ff with change name
- **WHEN** user submits a prompt containing `opsx:ff add-dark-mode`
- **THEN** the recall query SHALL include "add-dark-mode" as primary term
- **AND** the recall SHALL execute (no boundary check)

#### Scenario: Prompt contains opsx:explore with topic
- **WHEN** user submits a prompt containing `opsx:explore memory hooks`
- **THEN** the recall query SHALL include "memory hooks"
- **AND** the recall SHALL execute

#### Scenario: Prompt is a plain question without opsx
- **WHEN** user submits "How do I connect to the database?"
- **THEN** the recall query SHALL use the first 200 characters of the prompt
- **AND** the recall SHALL execute

#### Scenario: Same prompt submitted twice
- **WHEN** user submits the same prompt twice in a session
- **THEN** the hook SHALL recall on both submissions (no debounce)

#### Scenario: No openspec directory
- **WHEN** the project has no `openspec/` directory
- **THEN** the hook SHALL still work using prompt-based recall

### Requirement: additionalContext output format
The recall hook SHALL output results using the `additionalContext` JSON field for discrete injection, instead of plain text stdout.

#### Scenario: Recall returns memories
- **WHEN** recall returns 1 or more memories
- **THEN** the hook SHALL output JSON with `hookSpecificOutput.hookEventName` set to `"UserPromptSubmit"`
- **AND** `hookSpecificOutput.additionalContext` containing the formatted memory text
- **AND** the text SHALL be prefixed with `=== PROJECT MEMORY ===`

#### Scenario: No memories found
- **WHEN** recall returns no memories
- **THEN** the hook SHALL exit 0 with no output

### Requirement: OpenSpec change enrichment
When an OpenSpec change name is detected, the recall hook SHALL also check for change-specific artifacts (design.md decisions, revision notes) and include relevant context.

#### Scenario: Change has design decisions in memory
- **WHEN** user starts `opsx:apply product-catalog`
- **AND** memories tagged `change:product-catalog,decisions` exist
- **THEN** the additionalContext SHALL include those decision memories
- **AND** SHALL be formatted as "Design decisions for product-catalog: ..."

### Requirement: Timeout safety
The recall hook SHALL complete within its 15-second timeout even if set-memory recall is slow.

#### Scenario: set-memory recall hangs
- **WHEN** set-memory recall takes >10 seconds
- **THEN** the hook exits silently (killed by Claude Code timeout)

