# Cheat Sheet Curation Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Auto-promote error fixes to cheat sheet
The Stop hook's haiku extraction step SHALL evaluate extracted error→fix memories for cheat-sheet worthiness and add the `cheat-sheet` tag to entries that describe reusable operational patterns.

#### Scenario: Error fix is reusable (e.g., DB connection pattern)
- **WHEN** the haiku extraction identifies a memory like "DB password is in .env.local, not .env"
- **AND** this describes a reusable operational pattern
- **THEN** the memory SHALL be saved with tags including `cheat-sheet`
- **AND** the `cheat-sheet` tag SHALL be in addition to existing tags

#### Scenario: Error fix is session-specific
- **WHEN** the haiku extraction identifies a memory like "fixed typo in variable name"
- **AND** this is a one-time fix not reusable across sessions
- **THEN** the memory SHALL NOT receive the `cheat-sheet` tag

### Requirement: Convention memories auto-promote to cheat sheet
All memories extracted as `Convention` type (which maps to Learning with `convention` tag) SHALL also receive the `cheat-sheet` tag automatically.

#### Scenario: Convention extracted from session
- **WHEN** the haiku extraction identifies a convention like "all list endpoints return { data, total, page, limit }"
- **THEN** the memory SHALL be saved with tags including both `convention` and `cheat-sheet`

### Requirement: Cheat sheet promotion criteria in haiku prompt
The haiku extraction prompt SHALL include instructions to identify cheat-sheet-worthy entries based on: (1) soft operational patterns and project conventions, (2) environment-specific configuration hints, (3) command patterns that aid productivity. The prompt SHALL explicitly exclude hard constraints, credentials, and mandatory rules from cheat-sheet promotion — those belong in `.claude/rules.yaml` instead.

#### Scenario: Haiku prompt includes cheat-sheet criteria
- **WHEN** the Stop hook runs haiku extraction
- **THEN** the prompt SHALL instruct haiku to output a `CheatSheet` type for reusable soft conventions
- **AND** CheatSheet entries SHALL be saved as Learning type with `cheat-sheet` tag
- **AND** the extraction SHALL be limited to 2 cheat-sheet entries per session

#### Scenario: Credential-like content is NOT promoted to cheat-sheet
- **WHEN** the haiku extraction identifies content like "DB password is X" or "use login Y for table Z"
- **THEN** this SHALL NOT receive the `cheat-sheet` tag
- **AND** haiku MAY note in the extracted insight that a rule entry may be appropriate

#### Scenario: Soft convention IS promoted to cheat-sheet
- **WHEN** the haiku extraction identifies a convention like "pytest needs PYTHONPATH=. to run correctly"
- **THEN** this SHALL receive the `cheat-sheet` tag as before
