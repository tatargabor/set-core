## ADDED Requirements

### Requirement: CLI entry point
The system SHALL provide a `bin/wt-audit` command with subcommands `scan` and `help`.

#### Scenario: Run scan on current project
- **WHEN** user runs `wt-audit scan` in a registered wt-tools project directory
- **THEN** system scans all 6 dimensions and prints a structured report to stdout

#### Scenario: Run scan with JSON output
- **WHEN** user runs `wt-audit scan --json`
- **THEN** system outputs a JSON object with `project`, `timestamp`, `dimensions`, and `summary` fields

#### Scenario: Run scan on non-project directory
- **WHEN** user runs `wt-audit scan` in a directory not registered with wt-project
- **THEN** system prints an error message and exits with code 1

#### Scenario: Show help
- **WHEN** user runs `wt-audit --help` or `wt-audit help`
- **THEN** system prints usage information listing available subcommands and options

### Requirement: Claude Code config dimension
The system SHALL check `.claude/settings.json` for permissions, hooks, agents, and rules.

#### Scenario: Check permissions
- **WHEN** `.claude/settings.json` exists and has `permissions.allow` entries
- **THEN** report status ✅ with count of allow/deny rules

#### Scenario: Missing permissions
- **WHEN** `.claude/settings.json` has no `permissions` key or empty `allow` array
- **THEN** report status ❌ with guidance to add safe commands for the detected stack

#### Scenario: Check memory hooks
- **WHEN** `.claude/settings.json` has hooks containing `wt-hook-memory`
- **THEN** report status ✅ with count of hook events configured

#### Scenario: Missing memory hooks
- **WHEN** hooks do not contain `wt-hook-memory` entries
- **THEN** report status ❌ with guidance to run `wt-deploy-hooks`

#### Scenario: Check agents
- **WHEN** `.claude/agents/` directory contains `.md` files
- **THEN** report status ✅ listing agent names and their model settings

#### Scenario: No agents directory
- **WHEN** `.claude/agents/` does not exist or is empty
- **THEN** report status ⚠️ with guidance pointing to reference.md for recommended agents

#### Scenario: Check rules
- **WHEN** `.claude/rules/` directory contains `.md` files
- **THEN** report status ✅ listing rule files and their path globs

#### Scenario: No project-specific rules
- **WHEN** `.claude/rules/` only contains wt-tools managed rules (prefixed `wt-`) or is empty
- **THEN** report status ⚠️ with guidance to create path-scoped rules for distinct code areas

### Requirement: Design documentation dimension
The system SHALL check for `docs/design/*.md` files covering standard categories.

#### Scenario: All standard categories present
- **WHEN** `docs/design/` contains files matching at least 3 of: `ui-conventions`, `functional-conventions`, `data-model`, `deployment`, `code-hygiene`
- **THEN** report status ✅ listing each file with line count and last modified date

#### Scenario: No design docs
- **WHEN** `docs/design/` does not exist or is empty
- **THEN** report status ❌ with guidance listing source directories to READ for each category based on detected stack

#### Scenario: Partial design docs
- **WHEN** `docs/design/` exists but covers fewer than 3 standard categories
- **THEN** report status ⚠️ listing present and missing categories with source pointers

### Requirement: OpenSpec config dimension
The system SHALL check `openspec/config.yaml` for populated context.

#### Scenario: Config with context
- **WHEN** `openspec/config.yaml` exists and has a non-empty `context` field
- **THEN** report status ✅

#### Scenario: Config without context
- **WHEN** `openspec/config.yaml` exists but `context` field is empty or missing
- **THEN** report status ⚠️ with guidance to populate tech stack, domain, key patterns, and design doc references

#### Scenario: No OpenSpec
- **WHEN** `openspec/config.yaml` does not exist
- **THEN** report status ❌ with guidance to run `openspec init`

### Requirement: Code signals dimension
The system SHALL check for code quality indicators.

#### Scenario: Large files detected
- **WHEN** any source file (`.ts`, `.tsx`, `.js`, `.jsx`, `.py`, `.astro`, `.vue`, `.svelte`) exceeds 400 lines
- **THEN** report status ⚠️ listing files with their line counts, sorted descending

#### Scenario: No large files
- **WHEN** no source files exceed 400 lines
- **THEN** report status ✅

#### Scenario: Unused code tooling
- **WHEN** `package.json` contains a script for unused code detection (knip, depcheck, or similar)
- **THEN** report status ✅ with the script name

#### Scenario: No unused code tooling
- **WHEN** no unused code detection script is found
- **THEN** report status ⚠️ with guidance to add knip or equivalent

### Requirement: CLAUDE.md structure dimension
The system SHALL check CLAUDE.md for key structural elements.

#### Scenario: CLAUDE.md with conventions
- **WHEN** `CLAUDE.md` exists and contains references to design docs or convention sections
- **THEN** report status ✅

#### Scenario: CLAUDE.md without conventions
- **WHEN** `CLAUDE.md` exists but has no convention references
- **THEN** report status ⚠️ with guidance to add convention summaries pointing to design docs

#### Scenario: No CLAUDE.md
- **WHEN** `CLAUDE.md` does not exist
- **THEN** report status ❌

### Requirement: Gitignore dimension
The system SHALL check `.gitignore` for sensitive file patterns.

#### Scenario: Sensitive patterns covered
- **WHEN** `.gitignore` includes patterns for `.env*`, `CLAUDE.local.md`, `.claude/settings.local.json`
- **THEN** report status ✅

#### Scenario: Missing sensitive patterns
- **WHEN** `.gitignore` is missing any of the above patterns
- **THEN** report status ⚠️ listing the missing patterns

### Requirement: Stack detection
The system SHALL detect the project's tech stack from filesystem signals.

#### Scenario: Detect from framework config
- **WHEN** `next.config.*` exists in the project root
- **THEN** system identifies stack as Next.js and adjusts guidance file paths accordingly

#### Scenario: Detect from package.json
- **WHEN** `package.json` lists framework dependencies (astro, next, vite, etc.)
- **THEN** system identifies the primary framework and key dependencies (ORM, CSS framework, UI library)

#### Scenario: Unknown stack
- **WHEN** no recognized framework config or dependencies are found
- **THEN** system uses generic guidance (no framework-specific file paths)

### Requirement: Guidance with source pointers
Each ❌ or ⚠️ finding SHALL include guidance with concrete READ source pointers.

#### Scenario: Missing design doc with detectable sources
- **WHEN** `docs/design/ui-conventions.md` is missing and `src/components/` exists
- **THEN** guidance includes `READ: src/components/**/*.tsx` and `READ: package.json (UI deps)`

#### Scenario: Missing permissions with detected stack
- **WHEN** permissions are missing and stack is detected as Next.js with pnpm
- **THEN** guidance includes recommended safe commands: `pnpm lint`, `pnpm build`, `npx tsc`, `git status/diff/log/add/commit`

### Requirement: Summary output
The scan SHALL end with a summary line showing pass/warn/fail counts.

#### Scenario: Mixed results
- **WHEN** scan completes with 12 passes, 3 warnings, 2 failures
- **THEN** output ends with: `Summary: ✅ 12  ⚠️ 3  ❌ 2`

### Requirement: Reference document
The system SHALL include a `lib/audit/reference.md` describing the target state.

#### Scenario: Reference content
- **WHEN** the LLM reads `lib/audit/reference.md`
- **THEN** it finds category descriptions for all 6 dimensions: what each design doc should cover, what agents/rules are recommended, what OpenSpec config fields are useful — without framework-specific content or templates
