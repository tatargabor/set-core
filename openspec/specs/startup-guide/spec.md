# Startup Guide Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Dispatcher appends startup guide to worktree CLAUDE.md
On dispatch, the dispatcher SHALL check the worktree's CLAUDE.md for an `## Application Startup` section. If absent, it SHALL append a generated startup guide section. If already present, it SHALL NOT overwrite it.

#### Scenario: CLAUDE.md has no startup section
- **WHEN** the dispatcher dispatches a change to a worktree
- **AND** the worktree's CLAUDE.md does not contain `## Application Startup`
- **THEN** the dispatcher SHALL append an `## Application Startup` section with detected dev server, DB, and test commands

#### Scenario: CLAUDE.md already has startup section
- **WHEN** the dispatcher dispatches a change to a worktree
- **AND** the worktree's CLAUDE.md already contains `## Application Startup`
- **THEN** the dispatcher SHALL NOT modify the existing section

#### Scenario: No CLAUDE.md exists
- **WHEN** the dispatcher dispatches a change to a worktree
- **AND** no CLAUDE.md file exists in the worktree root
- **THEN** the dispatcher SHALL create CLAUDE.md with the startup guide section

### Requirement: Startup guide content detection
The startup guide generator SHALL detect project configuration and produce relevant startup instructions. Detection SHALL include:
1. Package manager (pnpm/npm/yarn/bun) from lockfile
2. Framework dev command (`dev` script in package.json)
3. Database tool (Prisma/Drizzle) from dependencies
4. E2E test setup (Playwright config existence)

#### Scenario: Next.js project with Prisma and Playwright
- **WHEN** the project has `next` in dependencies, `prisma` in devDependencies, and `playwright.config.ts` exists
- **THEN** the startup guide SHALL include sections for dev server (`pnpm dev`), database (`npx prisma db push`), and E2E testing (`npx playwright install chromium` + `pnpm test:e2e`)

#### Scenario: Minimal project with only dev server
- **WHEN** the project has only a `dev` script in package.json and no DB or E2E tooling
- **THEN** the startup guide SHALL include only the dev server section

### Requirement: Planning rules include startup guide maintenance
The planning rules (set-project-web) SHALL instruct the planner that infrastructure and foundational changes MUST update the `## Application Startup` section in CLAUDE.md when they add new setup steps (e.g., adding a database, adding E2E testing).

#### Scenario: Infrastructure change adds Prisma
- **WHEN** the planner decomposes an infrastructure change that introduces Prisma
- **THEN** the change scope SHALL include updating CLAUDE.md's Application Startup section with database setup instructions
