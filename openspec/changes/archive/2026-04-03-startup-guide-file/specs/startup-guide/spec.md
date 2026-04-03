## MODIFIED Requirements

### Requirement: Dispatcher appends startup guide to worktree CLAUDE.md
On dispatch, the dispatcher SHALL delegate startup guide generation to the project profile's `generate_startup_file()` method instead of using the hardcoded `generate_startup_guide()` function. If the profile returns content, the dispatcher SHALL write it to `START.md` in the worktree and ensure CLAUDE.md references it. If the profile returns empty, the dispatcher SHALL skip startup file generation.

#### Scenario: CLAUDE.md has no startup section
- **WHEN** the dispatcher dispatches a change to a worktree
- **AND** the worktree has no `START.md` file
- **THEN** the dispatcher SHALL call `profile.generate_startup_file(wt_path)` and write the result to `START.md`

#### Scenario: START.md already exists
- **WHEN** the dispatcher dispatches a change to a worktree
- **AND** `START.md` already exists in the worktree
- **THEN** the dispatcher SHALL regenerate it (content may have changed since last dispatch)

### Requirement: Startup guide content detection
The startup guide generator SHALL be delegated to the project profile. The hardcoded detection logic in `dispatcher.py` (`generate_startup_guide()`) SHALL be removed and replaced with a call to `profile.generate_startup_file()`.

#### Scenario: Next.js project with Prisma and Playwright
- **WHEN** the web profile's `generate_startup_file()` is called on a project with `next`, `prisma`, and `playwright.config.ts`
- **THEN** it SHALL return START.md content with install, dev server, database, and E2E sections

#### Scenario: Minimal project with only dev server
- **WHEN** the web profile's `generate_startup_file()` is called on a project with only a `dev` script
- **THEN** it SHALL return START.md content with only install and dev server sections
