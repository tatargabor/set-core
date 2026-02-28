## ADDED Requirements

### Requirement: Copy env files on worktree creation
`wt-new` SHALL copy `.env`, `.env.local`, `.env.development`, and `.env.development.local` from the main project directory to the new worktree if they exist and are not already present in the worktree.

#### Scenario: Env files copied from main project
- **WHEN** `wt-new my-change` creates a worktree and main project has `.env` and `.env.local`
- **THEN** both files are copied to the new worktree directory
- **AND** an info message indicates how many files were copied

#### Scenario: Env file already exists in worktree
- **WHEN** the worktree already has `.env` (e.g., from a remote branch checkout)
- **THEN** the existing file is NOT overwritten

### Requirement: Install dependencies on worktree creation
`wt-new` SHALL detect the project's package manager from lockfiles and run dependency install if `package.json` exists and `node_modules` does not.

#### Scenario: pnpm project gets dependencies installed
- **WHEN** a worktree is created for a project with `package.json` and `pnpm-lock.yaml`
- **THEN** `pnpm install --frozen-lockfile` is executed (falling back to `pnpm install`)
- **AND** an info message confirms installation

#### Scenario: No lockfile present
- **WHEN** a worktree has `package.json` but no recognized lockfile
- **THEN** dependency install is skipped with a warning

#### Scenario: Package manager not installed
- **WHEN** the detected package manager binary is not on PATH
- **THEN** dependency install is skipped with a warning (non-fatal)

#### Scenario: node_modules already exists
- **WHEN** the worktree already has `node_modules`
- **THEN** dependency install is skipped

### Requirement: Retroactive worktree bootstrap
When `dispatch_change()` finds an existing worktree that was not bootstrapped (missing .env or node_modules), it SHALL call `bootstrap_worktree()` to copy env files and install dependencies.

#### Scenario: Existing worktree without bootstrap
- **WHEN** a worktree exists but has no .env files or node_modules
- **THEN** bootstrap_worktree SHALL copy env files and install dependencies before starting the Ralph loop
