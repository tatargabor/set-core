## MODIFIED Requirements

### Requirement: Topic-based recall from prompt text
The recall hook SHALL extract topic keywords from the user's prompt text and use them as the recall query. If an OpenSpec change name is detected (opsx:ff, opsx:apply, opsx:explore, opsx:new, opsx:continue, or openspec- prefixed skills), it SHALL be included in the query. The hook SHALL NOT use change-boundary detection or debounce — it SHALL recall on every prompt. The underlying `set-memory proactive` command now includes hybrid fallback, so short and non-English queries SHALL return relevant results when they exist in memory.

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

#### Scenario: Short non-English query finds relevant memory
- **WHEN** user submits a prompt with short non-English text (e.g., "levelibéka")
- **AND** a memory exists with matching content
- **THEN** the recall SHALL return that memory via hybrid fallback
- **AND** it SHALL appear in the additionalContext output
