<!-- NOTE: Existing dispatch-core requirements (model resolution, wt-loop backend, phase gating, proposal enrichment, design context injection) are preserved unchanged. This delta only adds the startup guide step. -->

## MODIFIED Requirements

### Requirement: Dispatcher prepares worktree CLAUDE.md with startup guide
The `dispatch_change()` function SHALL call the startup guide generator after copying artifacts to the worktree. The generator SHALL append an `## Application Startup` section to CLAUDE.md if one does not already exist.

#### Scenario: First dispatch to fresh worktree
- **WHEN** `dispatch_change()` prepares a worktree for the first time
- **AND** the worktree's CLAUDE.md has no `## Application Startup` section
- **THEN** the dispatcher SHALL append the generated startup guide

#### Scenario: Re-dispatch to existing worktree (retry)
- **WHEN** `dispatch_change()` re-dispatches a change after verify failure
- **AND** the worktree's CLAUDE.md already contains `## Application Startup`
- **THEN** the dispatcher SHALL NOT modify the startup section

## ADDED Requirements

### Requirement: Build-inclusive smoke command auto-detection
The config module SHALL provide `auto_detect_smoke_command(directory)` that resolves the smoke command using this chain:
1. Explicit `smoke_command` from orchestration.yaml (if non-empty)
2. If a build script exists (`build` or `build:ci` in package.json): `<pm> run build && <test_command>`
3. Fall back to `test_command` alone

#### Scenario: Build script exists and no explicit smoke_command
- **WHEN** `auto_detect_smoke_command()` is called
- **AND** orchestration.yaml has no `smoke_command` set
- **AND** package.json has a `build` script
- **AND** the detected test command is `pnpm test`
- **THEN** the function SHALL return `pnpm run build && pnpm test`

#### Scenario: Explicit smoke_command in config
- **WHEN** `auto_detect_smoke_command()` is called
- **AND** orchestration.yaml has `smoke_command: "pnpm test:smoke"`
- **THEN** the function SHALL return `pnpm test:smoke` (config takes precedence)

#### Scenario: No build script and no explicit smoke_command
- **WHEN** `auto_detect_smoke_command()` is called
- **AND** orchestration.yaml has no `smoke_command` set
- **AND** package.json has no `build` or `build:ci` script
- **THEN** the function SHALL fall back to the test_command
