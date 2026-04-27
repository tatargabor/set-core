# Schema Digest Generation Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Auto-parse ORM schema at dispatch time
The dispatcher SHALL parse the project's ORM schema file (e.g., `prisma/schema.prisma`) at dispatch time and generate a structured digest containing model names, field names with types, relation names, and enum values. The digest SHALL be appended to the worktree's `CLAUDE.md` as a `## Project Schema (auto-generated, readonly)` section.

#### Scenario: Prisma schema parsed and injected
- **WHEN** dispatcher prepares a worktree for a change AND the project contains `prisma/schema.prisma`
- **THEN** the worktree's `CLAUDE.md` SHALL contain a `## Project Schema` section listing all models, their fields (name + type), relations, and enums extracted directly from the schema file

#### Scenario: Schema digest reflects current schema
- **WHEN** the Prisma schema has been modified since the last dispatch
- **THEN** the generated digest SHALL reflect the current schema contents, not a cached version

#### Scenario: Idempotent injection
- **WHEN** the `## Project Schema` section already exists in CLAUDE.md
- **THEN** the dispatcher SHALL replace the existing section with freshly parsed content rather than appending a duplicate

#### Scenario: No ORM schema present
- **WHEN** no recognized ORM schema file exists in the project
- **THEN** the dispatcher SHALL skip schema digest generation without error

### Requirement: Schema digest replaces data-definitions.md injection
The dispatcher SHALL NOT copy `data-definitions.md` to worktree `.claude/spec-context/` when a schema digest has been generated. The auto-parsed digest supersedes the LLM-generated data definitions.

#### Scenario: data-definitions.md not copied when digest exists
- **WHEN** dispatcher generates a schema digest from the ORM schema
- **THEN** `data-definitions.md` SHALL NOT be copied to `.claude/spec-context/`

#### Scenario: Fallback when no ORM schema
- **WHEN** no ORM schema file is detected AND `data-definitions.md` exists in the digest directory
- **THEN** `data-definitions.md` SHALL still be copied to `.claude/spec-context/` as a fallback

### Requirement: Follow append_startup_guide_to_claudemd pattern
The implementation SHALL follow the existing `append_startup_guide_to_claudemd()` pattern in dispatcher.py: idempotent append to CLAUDE.md, create CLAUDE.md if missing, log success/failure.

#### Scenario: CLAUDE.md does not exist
- **WHEN** the worktree has no CLAUDE.md
- **THEN** the function SHALL create CLAUDE.md with the schema digest section

#### Scenario: Pattern consistency
- **WHEN** the schema digest is appended
- **THEN** the function SHALL return True on success and False on failure, matching the startup guide function signature

### Requirement: Detect framework conventions from package.json
The dispatcher SHALL detect framework versions from `package.json` dependencies (NextAuth, next-intl, Tailwind, Next.js, Prisma) and include version-appropriate API patterns in the schema digest section.

#### Scenario: NextAuth detected
- **WHEN** `package.json` contains `next-auth` as a dependency
- **THEN** the digest SHALL include the correct auth pattern (e.g., `getServerSession(authOptions)` for v4, `auth()` for v5)

#### Scenario: No package.json
- **WHEN** the project has no `package.json`
- **THEN** framework detection SHALL be skipped without error
