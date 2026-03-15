## ADDED Requirements

### Requirement: Prisma client generation after install
The web profile `bootstrap_worktree()` must run `prisma generate` after dependency installation if the project uses Prisma.

#### Scenario: Worktree with Prisma schema
- **WHEN** `prisma/schema.prisma` exists in the worktree after `pnpm install` completes
- **THEN** `npx prisma generate` is executed in the worktree directory
- **AND** the command runs with a 60-second timeout
- **AND** failure is logged but does not fail the overall bootstrap (non-fatal)

#### Scenario: Worktree without Prisma
- **WHEN** `prisma/schema.prisma` does not exist in the worktree
- **THEN** the prisma generate step is skipped entirely

### Requirement: Playwright browser installation after install
The web profile `bootstrap_worktree()` must install Playwright browsers if the project uses Playwright for E2E testing.

#### Scenario: Worktree with Playwright dependency
- **WHEN** `@playwright/test` appears in `devDependencies` of `package.json`
- **THEN** `npx playwright install chromium` is executed in the worktree directory
- **AND** the command runs with a 120-second timeout
- **AND** failure is logged but does not fail the overall bootstrap (non-fatal)

#### Scenario: Worktree without Playwright
- **WHEN** `@playwright/test` is not in `devDependencies`
- **THEN** the playwright install step is skipped entirely

### Requirement: Post-install hook ordering
Post-install hooks run in a defined order after the base dependency install.

#### Scenario: Full bootstrap sequence
- **WHEN** a new worktree is created for a web project with both Prisma and Playwright
- **THEN** the bootstrap runs in order: (1) `pnpm install`, (2) `prisma generate`, (3) `playwright install chromium`
- **AND** each step is independent — failure of one does not skip subsequent steps
