# Dispatch Worktree Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Sync worktree with main branch
The system SHALL merge the main branch (main) into a worktree branch before dispatch. If the worktree is already up-to-date, no merge SHALL occur. Generated file conflicts (lockfiles, .tsbuildinfo) SHALL be auto-resolved with `--ours` strategy. Real conflicts SHALL cause merge abort and return failure.

#### Scenario: Worktree already up to date
- **WHEN** the worktree branch merge-base equals main branch HEAD
- **THEN** the function returns success with a log message "already up to date"

#### Scenario: Clean merge succeeds
- **WHEN** the worktree is behind main by N commits and no conflicts exist
- **THEN** main is merged into the worktree branch and the function returns success

#### Scenario: Generated file conflicts auto-resolved
- **WHEN** merge conflicts exist only in generated files (*.tsbuildinfo, package-lock.json, yarn.lock, pnpm-lock.yaml)
- **THEN** conflicts are resolved with `--ours` strategy, committed, and the function returns success

#### Scenario: Real conflicts cause abort
- **WHEN** merge conflicts exist in non-generated files
- **THEN** the merge is aborted and the function returns failure

### Requirement: Bootstrap worktree environment
The system SHALL copy missing .env files from the project root to the worktree and install dependencies using the detected package manager (pnpm/yarn/bun/npm) when node_modules is missing. The operation SHALL be idempotent.

#### Scenario: Copy env files
- **WHEN** .env files exist in project root but not in worktree
- **THEN** .env, .env.local, .env.development, .env.development.local are copied

#### Scenario: Install dependencies
- **WHEN** package.json exists in worktree and node_modules does not
- **THEN** dependencies are installed using the detected package manager

#### Scenario: Already bootstrapped worktree
- **WHEN** all env files exist and node_modules is present
- **THEN** no action is taken (idempotent)

### Requirement: Prune orchestrator context from worktree
The system SHALL remove orchestrator-level commands (orchestrate*, sentinel*, manual*) from worktree `.claude/commands/wt/` directory. Tracked files SHALL be removed via `git rm`, untracked via filesystem delete. If files were pruned, a commit SHALL be created.

#### Scenario: Prune tracked orchestrator commands
- **WHEN** orchestrator command files exist as tracked git files in worktree
- **THEN** files are removed via `git rm` and a commit is created

#### Scenario: No orchestrator commands present
- **WHEN** no matching command files exist
- **THEN** no action is taken, no commit is created
